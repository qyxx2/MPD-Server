import asyncio
import sqlite3
from dataclasses import replace

import pytest

from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.mock_mpd import MockMPD
from server.app.player.models import DatabaseUpdateStatus
from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.services.library_scanner import LibraryScanner
from server.app.services.library_sync_service import LibrarySyncService


def test_commit_update_confirmation_and_next_generation_are_ordered(
    tmp_path, media_fixture_dir
):
    async def run():
        db = str(tmp_path / "sync.db")
        await initialize_database(db)
        repo = LibraryRepository(db)
        first = media_fixture_dir / "metadata.flac"
        second = media_fixture_dir / "sidecar.mp3"
        entered = asyncio.Event()
        release = asyncio.Event()
        order = []
        service = None

        class Player(MockMPD):
            async def database_update_status(self):
                self._check("database_update_status")
                return DatabaseUpdateStatus(updating=False)

            async def update_database(self):
                assert service.get_state().status == "SYNCING"
                with sqlite3.connect(db) as connection:
                    assert (
                        connection.execute("select count(*) from songs").fetchone()[0]
                        >= 1
                    )
                order.append(("update", service.get_state().generation))
                if len(order) == 1:
                    entered.set()
                    await release.wait()
                await super().update_database()

            async def has_library_uri(self, uri):
                order.append(("confirm", service.get_state().generation, uri))
                return await super().has_library_uri(uri)

        player = Player(library_uris=(str(first), str(second)))
        service = LibrarySyncService(LibraryScanner(repo), player, media_fixture_dir)
        first_id = await service.request_scan((first,), "manual")
        task = asyncio.create_task(service.run())
        try:
            await asyncio.wait_for(entered.wait(), 1)
            assert service.get_state().activity_id == first_id
            second_id = await service.request_scan((second,), "automatic")
            release.set()
            for _ in range(1000):
                if (
                    service.get_state().activity_id == second_id
                    and service.get_state().status == "SYNCED"
                ):
                    break
                await asyncio.sleep(0.001)
            assert service.get_state().activity_id == second_id
            assert service.get_state().generation == 2
            assert service.get_state().status == "SYNCED"
            assert len(await repo.list_songs()) == 2
            assert [x for x in order if x[0] == "update"] == [
                ("update", 1),
                ("update", 2),
            ]
            # Removal reconciles MS and confirms absence of the original URI.
            first.unlink()
            player.library_uris.remove(str(first))
            # Full scan excludes the deliberately broken fixture.
            (media_fixture_dir / "broken.mp3").unlink()
            (media_fixture_dir / "no_lyrics.mp3").unlink()
            player.library_uris.add(str(media_fixture_dir / "sidecar.mp3"))
            third_id = await service.request_scan(None, "manual")
            for _ in range(1000):
                if (
                    service.get_state().activity_id == third_id
                    and service.get_state().status == "SYNCED"
                ):
                    break
                await asyncio.sleep(0.001)
            assert service.get_state().status == "SYNCED"
            old = await repo.find_song_by_file_uri(str(first))
            assert old.availability_status == "MISSING"
            assert ("confirm", 3, str(first)) in order
            assert await player.queue_entries() == []
        finally:
            await service.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_library_query_requires_its_own_runtime_evidence_and_not_queue_membership():
    async def run():
        player = MockMPD(library_uris=("indexed.flac",))
        await player.queue_add("queue-only.flac")
        caps = MPDCapabilities.from_commands({"find"})
        port = VerifiedPlayerPort(player, caps)
        with pytest.raises(PlayerCommandError, match="runtime behavior not verified"):
            await port.has_library_uri("indexed.flac")
        port = VerifiedPlayerPort(
            player, replace(caps, verified_operations=frozenset({"has_library_uri"}))
        )
        assert await port.has_library_uri("indexed.flac") is True
        assert await port.has_library_uri("queue-only.flac") is False
        player.disconnect()
        with pytest.raises(PlayerUnavailable):
            await port.has_library_uri("indexed.flac")

    asyncio.run(run())


def test_real_query_maps_and_matches_exact_uri_without_port_lock_nesting(tmp_path):
    from server.app.player.mpd_adapter import MPDAdapter
    from server.app.player.music_uri import MusicUriMapper

    async def run():
        commands = []
        replies = [
            b"file: prefix/Other.flac\nOK\n",
            "file: prefix/中文 space.flac\nOK\n".encode(),
            b"OK\n",
        ]

        async def handle(reader, writer):
            writer.write(b"OK MPD 0.23.5\n")
            await writer.drain()
            try:
                while raw := await reader.readline():
                    commands.append(raw.decode().rstrip())
                    writer.write(replies.pop(0))
                    await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        adapter = MPDAdapter(
            "127.0.0.1",
            port=server.sockets[0].getsockname()[1],
            uri_mapper=MusicUriMapper(tmp_path, "prefix"),
        )
        try:
            uri = str(tmp_path / "中文 space.flac")
            assert await asyncio.wait_for(adapter.has_library_uri(uri), 1) is False
            assert await asyncio.wait_for(adapter.has_library_uri(uri), 1) is True
            assert await asyncio.wait_for(adapter.has_library_uri(uri), 1) is False
            assert commands == ['find file "prefix/中文 space.flac"'] * 3
        finally:
            await adapter.close()
            server.close()
            await server.wait_closed()

    asyncio.run(run())


def test_runtime_startup_scheduler_and_shutdown_share_one_owner(
    tmp_path, media_fixture_dir
):
    from server.app.services.library_runtime import LibraryRuntime

    async def run():
        db = str(tmp_path / "runtime.db")
        await initialize_database(db)
        root = tmp_path / "music"
        root.mkdir()
        player = MockMPD()
        scanner = LibraryScanner(LibraryRepository(db))
        service = LibrarySyncService(scanner, player, root)
        runtime = LibraryRuntime(
            service,
            root,
            scan_interval_seconds=0.01,
            debounce_seconds=0.001,
            check_interval_seconds=0.01,
        )
        task = asyncio.create_task(runtime.run())
        await asyncio.sleep(0.005)
        assert service.get_state().generation >= 1
        with pytest.raises(RuntimeError, match="owner"):
            await runtime.run()
        await runtime.close()
        await asyncio.wait_for(task, 1)
        assert service.get_state().status != "SYNCED"  # Mock update is still busy

    asyncio.run(run())


def test_mount_replaced_during_scan_never_commits_mass_missing(
    tmp_path, media_fixture_dir
):
    from server.app.models.library import Song

    async def run():
        db = str(tmp_path / "mount.db")
        await initialize_database(db)
        repo = LibraryRepository(db)
        root = tmp_path / "mounted"
        root.mkdir()
        old = await repo.upsert_song(
            Song(title="Keep", file_uri=str(root / "old.flac"))
        )

        class RacingScanner(LibraryScanner):
            async def _scan_files(self, paths):
                batch = await super()._scan_files(paths)
                root.rename(tmp_path / "unmounted")
                root.mkdir()
                return batch

        service = LibrarySyncService(RacingScanner(repo), MockMPD(), root)
        await service.request_scan(None, "manual")
        task = asyncio.create_task(service.run())
        try:
            for _ in range(1000):
                if service.get_state().status == "FAILED":
                    break
                await asyncio.sleep(0.001)
            restored = await repo.get_song(old.song_id)
            assert restored.availability_status == "AVAILABLE"
            assert service.get_state().status == "FAILED"
        finally:
            await service.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_runtime_does_not_duplicate_startup_before_scheduled_interval(tmp_path):
    from server.app.services.library_runtime import LibraryRuntime

    async def run():
        db = str(tmp_path / "startup.db")
        await initialize_database(db)
        root = tmp_path / "music"
        root.mkdir()
        updates = []

        class Player(MockMPD):
            async def update_database(self):
                updates.append("update")

            async def database_update_status(self):
                return DatabaseUpdateStatus(updating=False)

        service = LibrarySyncService(
            LibraryScanner(LibraryRepository(db)), Player(), root
        )
        runtime = LibraryRuntime(service, root, scan_interval_seconds=0.2)
        task = asyncio.create_task(runtime.run())
        try:
            await asyncio.sleep(0.05)
            assert updates == ["update"]
            await asyncio.sleep(0.2)
            assert len(updates) == 2
        finally:
            await runtime.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_new_generation_keeps_unconfirmed_targets_from_failed_generation(
    tmp_path, media_fixture_dir
):
    async def run():
        db = str(tmp_path / "pending.db")
        await initialize_database(db)
        repo = LibraryRepository(db)
        first = media_fixture_dir / "metadata.flac"
        second = media_fixture_dir / "sidecar.mp3"

        # A failed first generation cannot become invisible after the second URI succeeds.
        class Player(MockMPD):
            async def database_update_status(self):
                return DatabaseUpdateStatus(updating=False)

        player = Player(library_uris=(str(second),))
        now = [0.0]
        failed = asyncio.Event()

        async def sleep(seconds):
            if seconds == 2:
                failed.set()
                await asyncio.Event().wait()
            now[0] += seconds
            await asyncio.sleep(0)

        service = LibrarySyncService(
            LibraryScanner(repo),
            player,
            media_fixture_dir,
            clock=lambda: now[0],
            sleep=sleep,
        )
        await service.request_scan((first,), "manual")
        task = asyncio.create_task(service.run())
        try:
            await asyncio.wait_for(failed.wait(), 1)
            await service.request_scan((second,), "automatic")
            for _ in range(1000):
                if (
                    service.get_state().generation == 2
                    and service.get_state().status != "SYNCING"
                ):
                    break
                await asyncio.sleep(0.001)
            assert service.get_state().generation == 2
            assert service.get_state().status == "FAILED"
            assert service.get_state().failed_count == 1
        finally:
            await service.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_runtime_initial_media_is_not_rescanned_by_detector(
    tmp_path, media_fixture_dir
):
    from server.app.services.library_runtime import LibraryRuntime

    async def run():
        db = str(tmp_path / "initial.db")
        await initialize_database(db)
        root = tmp_path / "music"
        root.mkdir()
        file = root / "metadata.flac"
        file.write_bytes((media_fixture_dir / "metadata.flac").read_bytes())
        updates = []

        class Player(MockMPD):
            async def update_database(self):
                updates.append("update")

            async def database_update_status(self):
                return DatabaseUpdateStatus(updating=False)

        service = LibrarySyncService(
            LibraryScanner(LibraryRepository(db)),
            Player(library_uris=(str(file),)),
            root,
        )
        runtime = LibraryRuntime(
            service,
            root,
            scan_interval_seconds=10,
            check_interval_seconds=0.01,
            debounce_seconds=0.005,
        )
        task = asyncio.create_task(runtime.run())
        try:
            await asyncio.sleep(0.1)
            assert service.get_state().status == "SYNCED"
            assert updates == ["update"]
        finally:
            await runtime.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_failed_move_absence_confirmation_survives_the_next_generation(
    tmp_path, media_fixture_dir
):
    async def run():
        db = str(tmp_path / "move.db")
        await initialize_database(db)
        repo = LibraryRepository(db)
        old_uri = media_fixture_dir / "metadata.flac"
        moved_uri = media_fixture_dir / "moved.flac"
        second = media_fixture_dir / "sidecar.mp3"
        await LibraryScanner(repo).scan_paths([old_uri])
        original = await repo.find_song_by_file_uri(str(old_uri))
        old_uri.rename(moved_uri)

        class Player(MockMPD):
            async def database_update_status(self):
                return DatabaseUpdateStatus(updating=False)

        player = Player(library_uris=(str(old_uri), str(moved_uri), str(second)))
        now = [0.0]
        failed = asyncio.Event()

        async def sleep(seconds):
            if seconds == 2:
                failed.set()
                await asyncio.Event().wait()
            now[0] += seconds
            await asyncio.sleep(0)

        service = LibrarySyncService(
            LibraryScanner(repo),
            player,
            media_fixture_dir,
            clock=lambda: now[0],
            sleep=sleep,
        )
        await service.request_scan((moved_uri,), "automatic")
        task = asyncio.create_task(service.run())
        try:
            await asyncio.wait_for(failed.wait(), 1)
            assert (await repo.get_song(original.song_id)).file_uri == str(moved_uri)
            await service.request_scan((second,), "automatic")
            for _ in range(1000):
                if (
                    service.get_state().generation == 2
                    and service.get_state().status != "SYNCING"
                ):
                    break
                await asyncio.sleep(0.001)
            assert service.get_state().generation == 2
            assert service.get_state().status == "FAILED"
            assert service.get_state().failed_count == 1
            # A newer round can finish only after MPD drops the original path.
            player.library_uris.remove(str(old_uri))
            third = await service.request_scan((second,), "manual")
            for _ in range(1000):
                if (
                    service.get_state().activity_id == third
                    and service.get_state().status == "SYNCED"
                ):
                    break
                await asyncio.sleep(0.001)
            assert service.get_state().status == "SYNCED"
            assert service.get_state().confirmed_count == 3
            assert (await repo.get_song(original.song_id)).file_uri == str(moved_uri)
        finally:
            await service.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())
