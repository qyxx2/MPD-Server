from __future__ import annotations

import asyncio
import inspect
from shutil import copy2

import pytest

from server.app.main import app
from server.app.models.library import Song
from server.app.models.queue import PlaybackContext
from server.app.repositories.database import (
    initialize_database,
    on_transaction_commit,
    run_transaction,
    transaction_identity,
)
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playback_state_repository import PlaybackStateRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.repositories.queue_repository import QueueRepository
from server.app.services.library_scanner import LibraryScanner
from server.app.services.playlist_service import PlaylistService, SongNotFoundError
from server.app.services.queue_manager import QueueManager
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.tests.support.playback import mutate, run, start


def test_playlist_versions_follow_outer_delta_and_replay(real_client, monkeypatch):
    """Missing Service staging loses committed versions; terminal/replay must be atomic."""
    client, library, player, playback = real_client
    start(client)
    queue = client.get("/api/playback/queue").json()
    history = client.get("/api/history").json()
    active = playback.history_service.active_event.model_copy(deep=True)
    session = playback.history_service.session_id
    status = run(player.status())
    songs = run(library.list_songs())
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            # Network/async publication must be outside the transaction lock.
            with pytest.raises(RuntimeError, match="requires an active transaction"):
                transaction_identity(library.path)
            await asyncio.wait_for(service.list_playlists(), 1)
            events.append(event)
            await coordinator.publish(event)

    assert "coordinator" in inspect.signature(PlaylistService).parameters, (
        "PlaylistService lacks committed playlist revision integration"
    )
    service = PlaylistService(
        app.state.playlist_service._repository, Publisher(), coordinator=coordinator,
    )
    monkeypatch.setattr(app.state, "playlist_service", service)
    baseline = run(service.revision_content())
    records = app.state.idempotency_service._repository
    original_create = records.create

    async def fail_terminal(**kwargs):
        raise RuntimeError("terminal write failed")

    monkeypatch.setattr(records, "create", fail_terminal)
    with pytest.raises(RuntimeError, match="terminal write failed"):
        mutate(client, "POST", "/api/playlists", {"name": "Created"}, key="create")
    assert run(service.revision_content()) == baseline
    assert run(records.get_by_key("create")) is None
    assert coordinator.marker().playlist_revision == 0
    assert subscriber.pending is None
    assert events == []

    monkeypatch.setattr(records, "create", original_create)
    created = mutate(client, "POST", "/api/playlists", {"name": "Created"}, key="create")
    assert created.status_code == 201, created.text
    assert coordinator.marker().playlist_revision == 1
    assert subscriber.pending.domains == frozenset({"playlist"})
    assert subscriber.pending.revisions == {"library": 0, "playlist": 1}
    assert [event.event_type for event in events] == ["playlist.changed"]
    marker = coordinator.marker()
    replay = mutate(client, "POST", "/api/playlists", {"name": "Created"}, key="create")
    assert replay.json() == created.json()
    assert coordinator.marker() == marker
    assert len(events) == 1
    base = f"/api/playlists/{created.json()['playlist_id']}"

    def operation(method, path, body, expected_status, delta, key):
        before = coordinator.marker().playlist_revision
        count = len(events)
        response = mutate(client, method, path, body, key=key)
        assert response.status_code == expected_status, response.text
        assert coordinator.marker().playlist_revision == before + delta
        assert len(events) == count + delta
        return response

    operation("PATCH", base, {"name": "Created"}, 200, 0, "same-name")
    operation("PATCH", base, {"name": "Renamed"}, 200, 1, "rename")
    operation("POST", base + "/songs", {"song_id": "a"}, 200, 1, "add-a")
    operation("POST", base + "/songs", {"song_id": "a"}, 409, 0, "duplicate")
    operation("POST", base + "/songs", {"song_id": "b"}, 200, 1, "add-b")
    operation("PUT", base + "/songs/order", {"ordered_song_ids": ["b", "a"]}, 200, 1, "order")
    operation("PUT", base + "/songs/order", {"ordered_song_ids": ["b", "a"]}, 200, 0, "same-order")
    operation("PUT", "/api/favorites/a", None, 200, 1, "favorite")
    operation("PUT", "/api/favorites/a", None, 200, 0, "same-favorite")
    operation("DELETE", "/api/favorites/a", None, 204, 1, "unfavorite")
    operation("DELETE", base + "/songs/a", None, 204, 1, "remove")
    operation("DELETE", base, None, 204, 1, "delete")
    before_save = run(service.revision_content())
    marker = coordinator.marker()
    count = len(events)
    monkeypatch.setattr(records, "create", fail_terminal)
    with pytest.raises(RuntimeError, match="terminal write failed"):
        mutate(client, "POST", "/api/playback/queue/save-as-playlist", {"name": "Saved"}, key="save")
    assert run(service.revision_content()) == before_save
    assert coordinator.marker() == marker
    assert len(events) == count
    assert run(records.get_by_key("save")) is None
    monkeypatch.setattr(records, "create", original_create)
    saved = operation(
        "POST", "/api/playback/queue/save-as-playlist",
        {"name": "Saved"}, 200, 1, "save",
    )
    assert saved.json()["song_ids"] == ["b", "c", "a"]  # includes existing AutoPlay refill
    marker = coordinator.marker()
    count = len(events)
    replay = mutate(client, "POST", "/api/playback/queue/save-as-playlist", {"name": "Saved"}, key="save")
    assert replay.json() == saved.json()
    assert coordinator.marker() == marker
    assert len(events) == count
    assert coordinator.marker().library_revision == 0
    assert run(library.list_songs()) == songs
    assert client.get("/api/playback/queue").json() == queue
    assert client.get("/api/history").json() == history
    assert playback.history_service.active_event == active
    assert playback.history_service.session_id == session
    assert run(player.status()) == status


async def direct_fixture(tmp_path, *, publisher=None):
    path = str(tmp_path / "playlist.db")
    await initialize_database(path)
    library = LibraryRepository(path)
    for song_id in "abc":
        await library.upsert_song(Song(
            song_id=song_id, title=song_id, file_uri=f"{song_id}.flac",
            availability_status={"a": "AVAILABLE", "b": "MISSING", "c": "UNREADABLE"}[song_id],
        ))
    coordinator = RealtimeCoordinator(path)
    repository = PlaylistRepository(path)
    service = PlaylistService(repository, publisher, coordinator=coordinator)
    return path, library, repository, service, coordinator


@pytest.mark.parametrize("mode", ["commit", "restore", "rollback", "cancel"])
def test_direct_playlist_outer_delta_preserves_unavailable_members(tmp_path, mode):
    """Per-member versions/events or timestamp comparisons expose false deltas."""
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    async def scenario():
        path, library, repository, service, coordinator = await direct_fixture(
            tmp_path, publisher=Publisher(),
        )
        songs = await library.list_songs()
        playlist = await service.save_queue_as_playlist("Kept", ["c", "a", "b"])
        assert await service.list_song_ids(playlist.playlist_id) == ["c", "a", "b"]
        assert coordinator.marker().playlist_revision == 1
        assert len(events) == 1
        await service.set_favorite("b", True)
        baseline = await service.revision_content()
        marker = coordinator.marker()
        events.clear()
        subscription = coordinator.subscribe()

        async def outer(_):
            await service.update_playlist(playlist.playlist_id, "Changed")
            await service.reorder_playlist(playlist.playlist_id, ["b", "c", "a"])
            await service.set_favorite("c", True)
            assert coordinator.marker() == marker
            assert events == []
            assert subscription.pending is None
            if mode == "restore":
                await service.update_playlist(playlist.playlist_id, "Kept")
                await service.reorder_playlist(playlist.playlist_id, ["c", "a", "b"])
                await service.set_favorite("c", False)
                temporary = await service.create_playlist("Temporary")
                await service.delete_playlist(temporary.playlist_id)
            elif mode == "rollback":
                raise RuntimeError("outer failed")
            elif mode == "cancel":
                raise asyncio.CancelledError()

        if mode in {"rollback", "cancel"}:
            error = RuntimeError if mode == "rollback" else asyncio.CancelledError
            with pytest.raises(error):
                await run_transaction(path, outer)
        else:
            await run_transaction(path, outer)
        if mode == "commit":
            assert coordinator.marker().playlist_revision == marker.playlist_revision + 1
            assert len(events) == 1
            assert subscription.pending.revisions["playlist"] == marker.playlist_revision + 1
            assert await repository.list_song_ids(playlist.playlist_id) == ["b", "c", "a"]
            assert await repository.list_favorite_song_ids() == ["c", "b"]
        else:
            assert await service.revision_content() == baseline
            assert coordinator.marker() == marker
            assert subscription.pending is None
            assert events == []
        assert coordinator.marker().library_revision == 0
        assert await library.list_songs() == songs

    asyncio.run(scenario())


def test_failed_direct_save_is_atomic_even_without_propagation(tmp_path):
    """A partial save must not leave a Playlist or consume a version."""
    async def scenario():
        _, _, repository, service, coordinator = await direct_fixture(tmp_path)
        baseline = await service.revision_content()
        marker = coordinator.marker()
        for candidate in (service, PlaylistService(repository)):
            with pytest.raises(SongNotFoundError):
                await candidate.save_queue_as_playlist("Failed", ["a", "absent"])
            assert await service.revision_content() == baseline
            assert coordinator.marker() == marker
            with pytest.raises(ValueError, match="duplicate songs"):
                await candidate.save_queue_as_playlist("Duplicate", ["a", "a"])
            assert await service.revision_content() == baseline
        playlist = await service.save_queue_as_playlist("Retry", ["a", "c"])
        assert await service.list_song_ids(playlist.playlist_id) == ["a", "c"]
        assert coordinator.marker().playlist_revision == 1

    asyncio.run(scenario())


def test_library_and_playlist_share_one_outer_commit_and_restart(tmp_path, media_fixture_dir):
    """Independent nested commits would expose one domain without the other version."""
    async def scenario():
        path = str(tmp_path / "joint.db")
        await initialize_database(path)
        root = tmp_path / "music"
        root.mkdir()
        copy2(media_fixture_dir / "metadata.flac", root / "track.flac")
        library = LibraryRepository(path)
        coordinator = RealtimeCoordinator(path)
        subscription = coordinator.subscribe()
        scanner = LibraryScanner(library, coordinator=coordinator)
        playlists = PlaylistService(PlaylistRepository(path), coordinator=coordinator)

        async def joint(_):
            result = await scanner.scan_full(root)
            song_id = result.added_song_ids[0]
            playlist = await playlists.save_queue_as_playlist("Joint", [song_id])
            await playlists.set_favorite(song_id, True)
            assert coordinator.marker().sequence == 0
            assert subscription.pending is None
            return song_id, playlist.playlist_id

        song_id, playlist_id = await run_transaction(path, joint)
        marker = coordinator.marker()
        assert (marker.sequence, marker.library_revision, marker.playlist_revision) == (1, 1, 1)
        assert subscription.pending.domains == frozenset({"library", "playlist"})
        assert subscription.pending.revisions == {"library": 1, "playlist": 1}
        playlist_content = await playlists.revision_content()
        # A real rescan to MISSING only changes Library, preserving resource membership.
        (root / "track.flac").unlink()
        await scanner.scan_full(root)
        assert coordinator.marker().library_revision == 2
        assert coordinator.marker().playlist_revision == 1
        assert await playlists.revision_content() == playlist_content
        assert await playlists.list_song_ids(playlist_id) == [song_id]
        assert await playlists.list_favorite_song_ids() == [song_id]
        assert (await library.get_song(song_id)).availability_status == "MISSING"
        fresh = RealtimeCoordinator(path)
        restored = PlaylistService(PlaylistRepository(path), coordinator=fresh)
        assert fresh.marker().epoch != marker.epoch
        assert (fresh.marker().sequence, fresh.marker().library_revision, fresh.marker().playlist_revision) == (0, 0, 0)
        assert await restored.revision_content() == playlist_content
        assert (await LibraryRepository(path).get_song(song_id)).availability_status == "MISSING"

    asyncio.run(scenario())


def test_playlist_version_visible_before_blocked_publisher_and_late_event(tmp_path):
    """Late publication must not hide the last committed change or regress its marker."""
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        events = []

        class Publisher:
            async def publish(self, event):
                if not started.is_set():
                    started.set()
                    await release.wait()
                events.append(event)
                await coordinator.publish(event)

        path, _, _, service, coordinator = await direct_fixture(tmp_path, publisher=Publisher())
        subscription = coordinator.subscribe()
        writer = asyncio.create_task(service.save_queue_as_playlist("First", ["a", "b"]))
        try:
            await asyncio.wait_for(started.wait(), 1)

            async def cut(_):
                playlist = next(p for p in await service.list_playlists() if p.name == "First")
                return await service.list_song_ids(playlist.playlist_id), coordinator.marker()

            members, marker = await asyncio.wait_for(run_transaction(path, cut), 1)
            assert members == ["a", "b"]
            assert (marker.library_revision, marker.playlist_revision) == (0, 1)
            assert subscription.pending.revisions == {"library": 0, "playlist": 1}
            await service.create_playlist("Latest")
            latest = coordinator.marker()
            assert latest.playlist_revision == 2
        finally:
            release.set()
            await writer
        assert len(events) == 2
        assert coordinator.marker().sequence > latest.sequence
        assert coordinator.marker().playlist_revision == 2
        assert subscription.pending.revisions == {"library": 0, "playlist": 2}

    asyncio.run(scenario())


def test_playlist_post_commit_failure_and_cancel_keep_committed_change(tmp_path, caplog):
    async def scenario():
        class BrokenPublisher:
            async def publish(self, event):
                raise RuntimeError("playlist publisher unavailable")

        path, _, _, service, coordinator = await direct_fixture(tmp_path, publisher=BrokenPublisher())
        subscription = coordinator.subscribe()
        playlist = await service.create_playlist("Kept")
        assert coordinator.marker().playlist_revision == 1
        assert subscription.pending.revisions["playlist"] == 1
        started = asyncio.Event()

        async def blocked():
            started.set()
            await asyncio.Event().wait()

        async def outer(_):
            on_transaction_commit(path, blocked)
            await service.update_playlist(playlist.playlist_id, "Last change")

        task = asyncio.create_task(run_transaction(path, outer))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (await service.get_playlist(playlist.playlist_id)).name == "Last change"
        assert coordinator.marker().playlist_revision == 2
        assert subscription.pending.revisions["playlist"] == 2
        # No later mutation is needed for the last change to be visible.
        assert service._changes == {}  # canceled earlier callback must release its outer owner

    asyncio.run(scenario())
    assert "playlist publisher unavailable" in caplog.text


@pytest.mark.parametrize("cancel", [False, True])
def test_direct_queue_save_never_exposes_partial_playlist(tmp_path, cancel):
    """Repository-level propagation must not split the existing direct Service save."""
    async def scenario():
        observed = []

        class Publisher:
            async def publish(self, event):
                saved = next(p for p in await service.list_playlists() if p.name == "Saved")
                observed.append((
                    coordinator.marker().playlist_revision,
                    await service.list_song_ids(saved.playlist_id),
                ))
                if cancel:
                    raise asyncio.CancelledError()

        path, _, playlists, service, coordinator = await direct_fixture(tmp_path, publisher=Publisher())
        queue = QueueRepository(path)
        await queue.replace_with_context(PlaybackContext(
            context_id="kept", source_type="PLAYLIST", source_id="origin",
            ordered_song_ids=("a", "b", "c"),
        ))
        before = await queue.get_snapshot()
        manager = QueueManager(queue, PlaybackStateRepository(path), playlists)
        if cancel:
            with pytest.raises(asyncio.CancelledError):
                await manager.save_as_playlist("Saved")
        else:
            await manager.save_as_playlist("Saved")
        assert observed == [(1, ["b", "c"])]
        saved = next(p for p in await service.list_playlists() if p.name == "Saved")
        assert await service.list_song_ids(saved.playlist_id) == ["b", "c"]
        assert coordinator.marker().playlist_revision == 1
        assert await queue.get_snapshot() == before

    asyncio.run(scenario())
