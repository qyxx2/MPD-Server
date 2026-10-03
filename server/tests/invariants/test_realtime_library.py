from __future__ import annotations

import asyncio
import inspect
import os
import sqlite3
from datetime import datetime, timezone
from shutil import copy2

import pytest
from mutagen.flac import FLAC

from server.app.models.history import HistoryEvent
from server.app.repositories.database import initialize_database, run_transaction
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.services.library_scanner import LibraryScanner
from server.app.services.library_service import LibraryService
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.tests.support.playback import mutate, run, start


def library_fixture(tmp_path, media_fixture_dir):
    path = str(tmp_path / "library.db")
    root = tmp_path / "music"
    root.mkdir()
    target = root / "track.flac"
    copy2(media_fixture_dir / "metadata.flac", target)
    return path, root, target, LibraryRepository(path)


def test_outer_scan_waits_for_commit_and_keeps_completion_order(
    tmp_path, media_fixture_dir,
):
    """Premature finalize leaks external effects on an HTTP outer rollback."""
    path, root, _, repository = library_fixture(tmp_path, media_fixture_dir)

    async def scenario():
        await initialize_database(path)
        order = []

        class Updater:
            async def update_database(self):
                with sqlite3.connect(path) as connection:
                    assert connection.execute("SELECT count(*) FROM songs").fetchone() == (1,)
                order.append("update")

        class Publisher:
            async def publish(self, event):
                assert order == ["commit", "update"]
                assert len(event.result.added_song_ids) == 1
                order.append("completion")

        scanner = LibraryScanner(repository, Publisher(), Updater())

        async def failing_outer(_):
            await scanner.scan_full(root)
            assert order == []
            raise RuntimeError("terminal failed")

        with pytest.raises(RuntimeError, match="terminal failed"):
            await run_transaction(path, failing_outer)
        assert await repository.list_songs() == []
        assert order == []

        async def success_outer(_):
            from server.app.repositories.database import on_transaction_visible

            on_transaction_visible(path, lambda: order.append("commit"))
            result = await scanner.scan_full(root)
            assert order == []
            return result

        result = await run_transaction(path, success_outer)
        assert order == ["commit", "update", "completion"]
        assert (await repository.get_song(result.added_song_ids[0])).title == "Test Song"

    asyncio.run(scenario())


def test_real_metadata_move_and_availability_preserve_references(
    tmp_path, media_fixture_dir, monkeypatch,
):
    """A scan must invalidate content without deleting unavailable memberships/history."""
    path, root, target, repository = library_fixture(tmp_path, media_fixture_dir)

    async def scenario():
        await initialize_database(path)
        coordinator = RealtimeCoordinator(path)
        scanner = LibraryScanner(repository, coordinator=coordinator)
        initial_bytes = target.read_bytes()
        result = await scanner.scan_full(root)
        assert target.read_bytes() == initial_bytes
        song_id = result.added_song_ids[0]
        playlists = PlaylistRepository(path)
        playlist = await playlists.create_playlist("Kept")
        await playlists.add_song(playlist.playlist_id, song_id)
        await playlists.set_favorite(song_id, True)
        history = HistoryRepository(path)
        await history.record_history(HistoryEvent(
            song_id=song_id, started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            reason="USER_NEXT", session_id="kept",
        ))
        saved_history = await history.list_history()

        async def preserved(expected_revision, status):
            assert coordinator.marker().library_revision == expected_revision
            assert coordinator.marker().playlist_revision == 0
            assert await playlists.list_song_ids(playlist.playlist_id) == [song_id]
            assert await playlists.list_favorite_song_ids() == [song_id]
            assert await history.list_history() == saved_history
            assert (await repository.get_song(song_id)).availability_status == status

        await preserved(1, "AVAILABLE")
        tags = FLAC(target)
        tags["title"] = ["Changed title"]
        tags.save()
        changed_bytes = target.read_bytes()
        await scanner.scan_paths([target])
        assert target.read_bytes() == changed_bytes
        assert (await repository.get_song(song_id)).title == "Changed title"
        await preserved(2, "AVAILABLE")
        moved = root / "moved.flac"
        target.rename(moved)
        result = await scanner.scan_full(root)
        assert result.moved_song_ids == (song_id,)
        assert (await repository.get_song(song_id)).file_uri == str(moved)
        await preserved(3, "AVAILABLE")

        from server.app.services import library_scanner as scanner_module

        with monkeypatch.context() as patch:
            def unreadable(_):
                raise PermissionError("source unavailable")

            patch.setattr(scanner_module, "parse_media_file", unreadable)
            await scanner.scan_paths([moved])
        await preserved(4, "UNREADABLE")
        await scanner.scan_paths([moved])
        await preserved(5, "AVAILABLE")
        moved.unlink()
        await scanner.scan_full(root)
        await preserved(6, "MISSING")
        await scanner.scan_full(root)
        await preserved(6, "MISSING")

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["rollback", "cancel", "restore", "batch"])
def test_outer_scan_delta_rollback_cancel_restore_and_batch(
    tmp_path, media_fixture_dir, mode,
):
    path, root, target, repository = library_fixture(tmp_path, media_fixture_dir)

    async def scenario():
        await initialize_database(path)
        coordinator = RealtimeCoordinator(path)
        events = []

        class Publisher:
            async def publish(self, event):
                events.append(event)

        scanner = LibraryScanner(repository, Publisher(), coordinator=coordinator)
        await scanner.scan_full(root)
        events.clear()
        baseline = await LibraryService(repository).revision_content()
        marker = coordinator.marker()
        original_bytes = target.read_bytes()
        original_stat = target.stat()

        def restore_source():
            target.write_bytes(original_bytes)
            os.utime(target, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

        async def outer(_):
            tags = FLAC(target)
            tags["title"] = ["Temporary"]
            tags.save()
            await scanner.scan_paths([target])
            assert coordinator.marker() == marker
            assert events == []
            if mode == "rollback":
                raise RuntimeError("outer failure")
            if mode == "cancel":
                raise asyncio.CancelledError()
            if mode == "restore":
                restore_source()
                await scanner.scan_paths([target])
            else:
                tags["title"] = ["Final"]
                tags.save()
                await scanner.scan_paths([target])

        if mode in {"rollback", "cancel"}:
            exception = RuntimeError if mode == "rollback" else asyncio.CancelledError
            with pytest.raises(exception):
                await run_transaction(path, outer)
            assert await LibraryService(repository).revision_content() == baseline
            assert coordinator.marker() == marker
            assert events == []
            restore_source()
            await scanner.scan_paths([target])
            assert await LibraryService(repository).revision_content() == baseline
            assert coordinator.marker().library_revision == 1
        else:
            await run_transaction(path, outer)
            if mode == "restore":
                assert await LibraryService(repository).revision_content() == baseline
            assert coordinator.marker().library_revision == (1 if mode == "restore" else 2)
            assert len(events) == 2
            assert (await repository.list_songs())[0].title == (
                "Test Song" if mode == "restore" else "Final"
            )

    asyncio.run(scenario())


def test_post_commit_publisher_failure_and_cancel_keep_content_visible(
    tmp_path, media_fixture_dir, caplog,
):
    path, root, target, repository = library_fixture(tmp_path, media_fixture_dir)

    async def scenario():
        await initialize_database(path)
        coordinator = RealtimeCoordinator(path)
        subscriber = coordinator.subscribe()

        class BrokenPublisher:
            async def publish(self, event):
                raise RuntimeError("publisher unavailable")

        scanner = LibraryScanner(repository, BrokenPublisher(), coordinator=coordinator)
        result = await scanner.scan_full(root)
        assert coordinator.marker().library_revision == 1
        assert subscriber.pending.revisions["library"] == 1
        assert await repository.get_song(result.added_song_ids[0]) is not None

        started = asyncio.Event()

        class BlockedUpdater:
            async def update_database(self):
                started.set()
                await asyncio.Event().wait()

        scanner.mpd_updater = BlockedUpdater()
        tags = FLAC(target)
        tags["title"] = ["Last change"]
        tags.save()
        task = asyncio.create_task(scanner.scan_paths([target]))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (await repository.list_songs())[0].title == "Last change"
        assert coordinator.marker().library_revision == 2
        assert subscriber.valid
        assert subscriber.pending.revisions == {"library": 2, "playlist": 0}

    asyncio.run(scenario())
    assert "publisher unavailable" in caplog.text


def test_http_terminal_failure_retry_replay_preserve_other_domains(
    real_client, tmp_path, media_fixture_dir, monkeypatch,
):
    """HTTP child-task scans must share the terminal transaction and never replay effects."""
    from server.app.main import app

    client, repository, player, playback = real_client
    _, root, target, _ = library_fixture(tmp_path, media_fixture_dir)
    start(client)
    queue_before = client.get("/api/playback/queue").json()
    history_before = client.get("/api/history").json()
    active_before = playback.history_service.active_event.model_copy(deep=True)
    session_before = playback.history_service.session_id
    player_before = run(player.status())
    coordinator = RealtimeCoordinator(repository.path)
    subscription = coordinator.subscribe()
    events, updates = [], []

    class Updater:
        async def update_database(self):
            updates.append("update")

    class Publisher:
        async def publish(self, event):
            events.append(event)
            await coordinator.publish(event)

    scanner = LibraryScanner(repository, Publisher(), Updater(), coordinator=coordinator)
    monkeypatch.setattr(app.state, "library_scanner", scanner)
    records = app.state.idempotency_service._repository
    original_create = records.create

    async def fail_terminal(**kwargs):
        raise RuntimeError("terminal write failed")

    monkeypatch.setattr(records, "create", fail_terminal)
    with pytest.raises(RuntimeError, match="terminal write failed"):
        mutate(client, "POST", "/api/library/scan", {"root": str(root)}, key="scan")
    assert run(repository.find_song_by_file_uri(str(target))) is None
    assert run(records.get_by_key("scan")) is None
    assert (coordinator.marker().library_revision, coordinator.marker().sequence) == (0, 0)
    assert subscription.pending is None
    assert events == updates == []

    monkeypatch.setattr(records, "create", original_create)
    response = mutate(client, "POST", "/api/library/scan", {"root": str(root)}, key="scan")
    assert response.status_code == 200, response.text
    marker = coordinator.marker()
    assert (marker.library_revision, marker.playlist_revision) == (1, 0)
    assert len(events) == len(updates) == 1
    replay = mutate(client, "POST", "/api/library/scan", {"root": str(root)}, key="scan")
    assert replay.status_code == 200
    assert replay.json() == response.json()
    assert coordinator.marker() == marker
    assert len(events) == len(updates) == 1
    assert client.get("/api/playback/queue").json() == queue_before
    assert client.get("/api/history").json() == history_before
    assert playback.history_service.active_event == active_before
    assert playback.history_service.session_id == session_before
    assert run(player.status()) == player_before


def test_late_scan_completion_reasserts_latest_content_version(
    tmp_path, media_fixture_dir,
):
    path, root, target, repository = library_fixture(tmp_path, media_fixture_dir)

    async def scenario():
        await initialize_database(path)
        coordinator = RealtimeCoordinator(path)
        subscription = coordinator.subscribe()
        started, release = asyncio.Event(), asyncio.Event()
        completions = []
        updates = 0

        class Updater:
            async def update_database(self):
                nonlocal updates
                updates += 1
                if updates == 1:
                    started.set()
                    await release.wait()

        class Publisher:
            async def publish(self, event):
                completions.append(event)
                await coordinator.publish(event)

        scanner = LibraryScanner(repository, Publisher(), Updater(), coordinator=coordinator)
        first = asyncio.create_task(scanner.scan_full(root))
        try:
            await asyncio.wait_for(started.wait(), 1)
            tags = FLAC(target)
            tags["title"] = ["Latest"]
            tags.save()
            second = await scanner.scan_paths([target])
            intermediate = coordinator.marker()
            assert intermediate.library_revision == 2
            assert completions[0].result == second
        finally:
            release.set()
            initial = await first
        assert completions[1].result == initial
        assert coordinator.marker().library_revision == 2
        assert coordinator.marker().sequence > intermediate.sequence
        assert subscription.pending.revisions == {"library": 2, "playlist": 0}
        assert (await repository.list_songs())[0].title == "Latest"
        fresh = RealtimeCoordinator(path)
        assert fresh.marker().epoch != coordinator.marker().epoch
        assert (fresh.marker().library_revision, fresh.marker().playlist_revision) == (0, 0)
        assert (await repository.list_songs())[0].title == "Latest"

    asyncio.run(scenario())


def test_content_revision_is_visible_before_optional_update_and_completion(
    tmp_path, media_fixture_dir,
):
    """Registering revisions after optional I/O leaves a stale committed cut."""
    assert "coordinator" in inspect.signature(LibraryScanner).parameters, (
        "scanner lacks committed content revision integration"
    )
    path, root, _, repository = library_fixture(tmp_path, media_fixture_dir)

    async def scenario():
        await initialize_database(path)
        coordinator = RealtimeCoordinator(path)
        subscription = coordinator.subscribe()
        started, release = asyncio.Event(), asyncio.Event()
        events = []

        class Updater:
            async def update_database(self):
                started.set()
                await release.wait()
                raise RuntimeError("MPD unavailable")

        class Publisher:
            async def publish(self, event):
                events.append(event)
                await coordinator.publish(event)

        scanner = LibraryScanner(repository, Publisher(), Updater(), coordinator=coordinator)
        writer = asyncio.create_task(scanner.scan_full(root))
        try:
            await asyncio.wait_for(started.wait(), 1)

            async def cut(_):
                return await repository.list_songs(), coordinator.marker()

            songs, marker = await asyncio.wait_for(run_transaction(path, cut), 1)
            assert [song.title for song in songs] == ["Test Song"]
            assert (marker.sequence, marker.library_revision, marker.playlist_revision) == (1, 1, 0)
            assert subscription.pending.revisions == {"library": 1, "playlist": 0}
            assert events == []
        finally:
            release.set()
            result = await writer
        assert events[0].result == result
        assert events[0].mpd_update_error == "MPD unavailable"
        assert coordinator.marker().library_revision == 1
        assert subscription.pending.sequence >= marker.sequence

        before = await LibraryService(repository).revision_content()
        await scanner.scan_full(root)
        assert await LibraryService(repository).revision_content() == before
        assert coordinator.marker().library_revision == 1
        assert len(events) == 2
        assert events[1].result.updated_song_ids == result.added_song_ids
        assert events[1].mpd_update_error == "MPD unavailable"

    asyncio.run(scenario())
