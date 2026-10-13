import asyncio

from server.app.player.mock_mpd import MockMPD
from server.app.player.models import DatabaseUpdateStatus
from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.services.library_scanner import LibraryScanner
from server.app.services.library_sync_service import LibrarySyncService


def test_disconnect_timeout_retry_and_shutdown_preserve_business_state(
    tmp_path, media_fixture_dir
):
    async def run():
        db = str(tmp_path / "state.db")
        await initialize_database(db)
        repository = LibraryRepository(db)
        file = media_fixture_dir / "metadata.flac"

        class IndexedPlayer(MockMPD):
            async def database_update_status(self):
                self._check("database_update_status")
                return DatabaseUpdateStatus(updating=False)

        player = IndexedPlayer(library_uris=(str(file),))
        await player.queue_add("queue-only.flac")
        queue = await player.queue_entries()
        status = await player.status()
        now = [0.0]
        sleeps = []
        service = None
        checking_timeout = False
        timed_out = asyncio.Event()

        async def sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds
            if seconds == 2 and checking_timeout:
                # Hold the failed phase; a virtual retry must not race the
                # observer and hide the terminal state under the next attempt.
                timed_out.set()
                await asyncio.Event().wait()
            if seconds == 5:
                player.reconnect()
            await asyncio.sleep(0)

        service = LibrarySyncService(
            LibraryScanner(repository),
            player,
            media_fixture_dir,
            clock=lambda: now[0],
            sleep=sleep,
        )
        player.disconnect()
        activity = await service.request_scan((file,), "manual")
        task = asyncio.create_task(service.run())
        for _ in range(1000):
            if service.get_state().status == "SYNCED":
                break
            await asyncio.sleep(0.001)
        assert service.get_state().status == "SYNCED"
        assert service.get_state().activity_id == activity
        assert [s for s in sleeps if s > 1][:2] == [2, 5]
        assert await player.queue_entries() == queue
        assert (await player.status()).model_dump() == status.model_dump()
        # Update accepted but exact URI absent must consume the full budget.
        checking_timeout = True
        player.library_uris.clear()
        sleeps.clear()
        await service.request_scan((file,), "manual")
        await asyncio.wait_for(timed_out.wait(), 1)
        state = service.get_state()
        assert state.status == "FAILED"
        assert state.error_code == "MPD_SYNC_TIMEOUT"
        assert sum(s for s in sleeps if s == 1) >= 60
        assert len(await repository.list_songs()) == 1
        await service.close()
        await asyncio.wait_for(task, 1)
        assert await player.queue_entries() == queue

    asyncio.run(run())


def test_temporarily_unreadable_new_file_is_retried_after_becoming_stable(
    tmp_path, media_fixture_dir, monkeypatch
):
    from server.app.services import library_scan_prepare as library_scanner

    async def run():
        db = str(tmp_path / "retry.db")
        await initialize_database(db)
        repo = LibraryRepository(db)
        file = media_fixture_dir / "metadata.flac"
        parse = library_scanner.parse_media_file
        attempts = []

        def temporarily_unreadable(path):
            attempts.append(path)
            if len(attempts) == 1:
                raise PermissionError("being written")
            return parse(path)

        monkeypatch.setattr(library_scanner, "parse_media_file", temporarily_unreadable)

        class Player(MockMPD):
            async def database_update_status(self):
                return DatabaseUpdateStatus(updating=False)

        player = Player(library_uris=(str(file),))
        sleeps = []

        async def sleep(seconds):
            sleeps.append(seconds)
            await asyncio.sleep(0)

        service = LibrarySyncService(
            LibraryScanner(repo), player, media_fixture_dir, sleep=sleep
        )
        activity = await service.request_scan((file,), "automatic")
        task = asyncio.create_task(service.run())
        try:
            for _ in range(1000):
                if service.get_state().status == "SYNCED":
                    break
                await asyncio.sleep(0.001)
            assert service.get_state().status == "SYNCED"
            assert service.get_state().activity_id == activity
            assert len(await repo.list_songs()) == 1
            assert len(attempts) == 2
            assert sleeps == [2]
        finally:
            await service.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_acceptance_rollback_never_starts_job_or_mpd_control(tmp_path):
    from server.app.repositories.database import run_transaction

    async def run():
        db = str(tmp_path / "rollback.db")
        await initialize_database(db)
        player = MockMPD()
        service = LibrarySyncService(
            LibraryScanner(LibraryRepository(db)), player, tmp_path
        )

        async def rollback(_):
            await service.request_scan(None, "manual")
            raise ValueError("rollback")

        try:
            await run_transaction(db, rollback)
        except ValueError:
            pass
        task = asyncio.create_task(service.run())
        await asyncio.sleep(0.01)
        assert service.get_state().status == "IDLE"
        assert (await player.database_update_status()).job_id is None
        await service.close()
        await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_retry_cap_and_cancellation_do_not_repeat_scan_or_touch_business_rows(
    tmp_path, media_fixture_dir
):
    import sqlite3

    async def run():
        db = str(tmp_path / "cap.db")
        await initialize_database(db)
        repo = LibraryRepository(db)
        file = media_fixture_dir / "metadata.flac"
        player = MockMPD(library_uris=(str(file),))
        player.disconnect()
        waits = []
        stopped = asyncio.Event()

        async def sleep(seconds):
            waits.append(seconds)
            if len(waits) == 5:
                stopped.set()
                await asyncio.Event().wait()
            await asyncio.sleep(0)

        service = LibrarySyncService(
            LibraryScanner(repo), player, media_fixture_dir, sleep=sleep
        )
        await service.request_scan((file,), "manual")
        task = asyncio.create_task(service.run())
        await asyncio.wait_for(stopped.wait(), 1)
        assert waits == [2, 5, 15, 30, 30]
        state = service.get_state()
        assert state.generation == 1
        assert state.status == "FAILED"
        with sqlite3.connect(db) as connection:
            before = list(connection.iterdump())
        await service.close()
        await asyncio.wait_for(task, 1)
        with sqlite3.connect(db) as connection:
            assert list(connection.iterdump()) == before
        assert len(await repo.list_songs()) == 1

    asyncio.run(run())


def test_confirmation_budget_starts_after_scanner_commit(tmp_path, media_fixture_dir):
    async def run():
        db = str(tmp_path / "budget.db")
        await initialize_database(db)
        now = [0.0]
        file = media_fixture_dir / "metadata.flac"

        class SlowScanner(LibraryScanner):
            async def prepare(self, *args, **kwargs):
                batch = await super().prepare(*args, **kwargs)
                now[0] += 120  # parsing time is not the MPD confirmation budget
                return batch

        class Player(MockMPD):
            async def database_update_status(self):
                return DatabaseUpdateStatus(updating=False)

        service = LibrarySyncService(
            SlowScanner(LibraryRepository(db)),
            Player(library_uris=(str(file),)),
            media_fixture_dir,
            clock=lambda: now[0],
        )
        await service.request_scan((file,), "manual")
        task = asyncio.create_task(service.run())
        try:
            for _ in range(1000):
                if service.get_state().status in {"SYNCED", "FAILED"}:
                    break
                await asyncio.sleep(0.001)
            assert service.get_state().status == "SYNCED"
        finally:
            await service.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_missing_requested_root_cannot_report_synced(tmp_path):
    async def run():
        db = str(tmp_path / "missing.db")
        await initialize_database(db)
        updates = []

        class Player(MockMPD):
            async def update_database(self):
                updates.append("update")

            async def database_update_status(self):
                return DatabaseUpdateStatus(updating=False)

        service = LibrarySyncService(
            LibraryScanner(LibraryRepository(db)), Player(), tmp_path
        )
        await service.request_scan((tmp_path / "unavailable-root",), "manual")
        task = asyncio.create_task(service.run())
        try:
            for _ in range(1000):
                if service.get_state().status in {"FAILED", "SYNCED"}:
                    break
                await asyncio.sleep(0.001)
            assert service.get_state().status == "FAILED"
            assert updates == []
        finally:
            await service.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())
