from __future__ import annotations

import asyncio

import pytest

from server.app.main import app
from server.app.repositories.database import run_transaction, transaction_identity
from server.app.services.playback_service import PlaybackService
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.tests.invariants.assertions import (
    assert_execution_relationship,
    server_snapshot,
)
from server.tests.support.playback import mutate, run, start


def wire(playback, publisher, coordinator):
    return PlaybackService(
        queue_manager=playback.queue_manager,
        history_service=playback.history_service,
        autoplay=playback.autoplay,
        player=playback.player,
        library_repository=playback.library_repository,
        event_publisher=publisher,
        coordinator=coordinator,
    )


def request(operation, target):
    if operation in {"play-next", "queue"}:
        return "POST", f"/api/playback/songs/a/{operation}", None, 200
    if operation == "clear":
        return "DELETE", "/api/playback/queue", None, 204
    path = f"/api/playback/queue/items/{target.queue_item_id}"
    return ("PUT", path, {}, 200) if operation == "reorder" else ("DELETE", path, None, 204)


@pytest.mark.parametrize("operation", ["play-next", "queue", "reorder", "delete", "clear"])
def test_queue_only_notification_preserves_current_occurrence_and_history(
    real_client, monkeypatch, operation,
):
    """Missing/early queue invalidation must fail despite successful REST mutation."""
    client, library, player, playback = real_client
    start(client)
    # A pending occurrence shares the current URI but retains separate identities.
    duplicate = run(playback.play_next("a"))
    before = server_snapshot(playback)
    current = next(i for i in before[0].items if i.position == 0)
    bindings = assert_execution_relationship(playback, player)
    assert bindings[current.queue_item_id].mpd_song_id != bindings[duplicate.queue_item_id].mpd_song_id
    songs = run(library.list_songs())
    playlists = run(app.state.playlist_service.revision_content())
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events, committed = [], []

    class Publisher:
        async def publish(self, event):
            with pytest.raises(RuntimeError, match="requires an active transaction"):
                transaction_identity(library.path)
            snapshot = await asyncio.wait_for(service.queue_manager.queue_repository.get_snapshot(), 1)
            assert snapshot.revision > before[0].revision
            assert await service.queue_manager.get_playback_state() == before[1]
            assert await service.history_service.list_history() == before[2]
            assert service.history_service.active_event == before[3]
            assert service.history_service.session_id == before[4]
            committed.append(snapshot)
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    method, endpoint, body, code = request(operation, duplicate)
    response = mutate(client, method, endpoint, body, key="queue-only")
    assert response.status_code == code, response.text
    assert subscriber.pending is not None, "committed queue-only delta was never registered"
    assert subscriber.pending.domains == frozenset({"queue"})
    assert len(events) == 1 and events[0].event_type == "playback.changed"
    assert events[0].domains == frozenset({"queue"})
    final = server_snapshot(service)
    assert committed == [final[0]] and final[1:] == before[1:]
    # Preserve the original per-operation Queue CAS policy, including refill mutations.
    delta = 2 if operation == "clear" else 1
    assert final[0].revision == before[0].revision + delta
    after = assert_execution_relationship(service, player, current_id=current.queue_item_id)
    assert after[current.queue_item_id].mpd_song_id == bindings[current.queue_item_id].mpd_song_id
    # PB-REORDER/DELETE freeze retained engine IDs. PB-INSERT freezes current;
    # insertion still proves a bijection of distinct occurrences, not URI deduplication.
    retained = set(bindings) & set(after) if operation in {"reorder", "delete"} else {current.queue_item_id}
    assert {i: after[i].mpd_song_id for i in retained} == {
        i: bindings[i].mpd_song_id for i in retained
    }
    if operation == "delete":
        assert duplicate.queue_item_id not in after
    elif operation == "reorder":
        assert after[duplicate.queue_item_id].position == len(after) - 1
    elif operation in {"play-next", "queue"}:
        added = set(after) - set(bindings)
        assert len(added) == 1
        item = next(i for i in final[0].items if i.queue_item_id in added)
        assert item.song_id == "a"
        assert item.position == (1 if operation == "play-next" else len(after) - 1)
    else:
        assert all(i.source == "AUTOPLAY" for i in final[0].items if i.position > 0)
    assert run(library.list_songs()) == songs
    assert run(app.state.playlist_service.revision_content()) == playlists
    marker, entries = coordinator.marker(), run(player.queue_entries())
    assert marker.library_revision == marker.playlist_revision == 0
    replay = mutate(client, method, endpoint, body, key="queue-only")
    assert replay.status_code == code and replay.content == response.content
    assert server_snapshot(service) == final and run(player.queue_entries()) == entries
    assert coordinator.marker() == marker and len(events) == 1


@pytest.mark.parametrize("operation", ["play-next", "queue", "reorder", "delete", "clear"])
def test_queue_terminal_failure_rolls_back_then_retry_and_replay(real_client, monkeypatch, operation):
    client, library, player, playback = real_client
    start(client)
    target = run(playback.play_next("a"))
    before = server_snapshot(playback)
    current = next(i for i in before[0].items if i.position == 0)
    current_mpd_id = run(player.status()).song_id
    coordinator = RealtimeCoordinator(library.path)
    subscriber, events = coordinator.subscribe(), []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    records = app.state.idempotency_service._repository
    original_create = records.create

    async def fail_terminal(**kwargs):
        assert subscriber.pending is None and events == []
        assert coordinator.marker().sequence == 0
        raise RuntimeError("terminal write failed")

    method, endpoint, body, code = request(operation, target)
    monkeypatch.setattr(records, "create", fail_terminal)
    with pytest.raises(RuntimeError, match="terminal write failed"):
        mutate(client, method, endpoint, body, key="retry")
    assert server_snapshot(service) == before
    assert run(records.get_by_key("retry")) is None
    assert subscriber.pending is None and events == []
    assert coordinator.marker().sequence == 0
    # External side effects survive SQLite rollback; retry uses existing sync rules.
    assert run(player.status()).song_id == current_mpd_id
    monkeypatch.setattr(records, "create", original_create)
    response = mutate(client, method, endpoint, body, key="retry")
    assert response.status_code == code, response.text
    assert subscriber.pending.domains == frozenset({"queue"})
    assert [e.domains for e in events] == [frozenset({"queue"})]
    final = server_snapshot(service)
    assert final[1:] == before[1:]
    assert_execution_relationship(service, player, current_id=current.queue_item_id)
    assert run(player.status()).song_id == current_mpd_id
    marker, entries = coordinator.marker(), run(player.queue_entries())
    replay = mutate(client, method, endpoint, body, key="retry")
    assert replay.status_code == code and replay.content == response.content
    assert coordinator.marker() == marker and len(events) == 1
    assert server_snapshot(service) == final and run(player.queue_entries()) == entries


@pytest.mark.parametrize("queue_first", [False, True])
def test_joint_queue_and_transport_commit_has_all_changed_domains(real_client, queue_first):
    """RT-PLAYBACK: a later producer must not overwrite an earlier domain delta."""
    client, library, _, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(library.path)
    subscriber, events = coordinator.subscribe(), []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    before = server_snapshot(service)

    async def scenario():
        async def outer(_):
            if queue_first:
                await service.add_to_queue("a")
                await service.seek(17)
            else:
                await service.seek(17)
                await service.add_to_queue("a")
            assert coordinator.marker().sequence == 0
            assert subscriber.pending is None and events == []

        await run_transaction(library.path, outer)

    run(scenario())
    assert coordinator.marker().sequence == 1
    assert subscriber.pending.domains == frozenset({"playback", "queue"})
    assert [e.domains for e in events] == [frozenset({"playback", "queue"})]
    final = server_snapshot(service)
    assert final[0].revision == before[0].revision + 1
    assert final[1].position_seconds == 17
    assert final[1].playback_context_id == before[1].playback_context_id
    assert final[2:] == before[2:]


async def apply(service, operation, target, *, expected_revision=None):
    if operation == "play-next":
        return await service.play_next("a")
    if operation == "queue":
        return await service.add_to_queue("a")
    if operation == "clear":
        return await service.clear(expected_revision=expected_revision)
    if operation == "reorder":
        return await service.reorder(target.queue_item_id, expected_revision=expected_revision)
    return await service.delete(target.queue_item_id, expected_revision=expected_revision)


@pytest.mark.parametrize("operation", ["play-next", "queue", "reorder", "delete", "clear"])
def test_queue_confirmation_and_outer_commit_barriers(real_client, monkeypatch, operation):
    client, library, player, playback = real_client
    start(client)
    target = run(playback.play_next("a"))
    before = server_snapshot(playback)
    coordinator = RealtimeCoordinator(library.path)
    subscriber, events = coordinator.subscribe(), []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    original_status = player.status

    async def scenario():
        confirming, release = asyncio.Event(), asyncio.Event()

        async def held_status():
            confirming.set()
            await release.wait()
            return await original_status()

        monkeypatch.setattr(player, "status", held_status)

        async def outer(_):
            await apply(service, operation, target)
            assert coordinator.marker().sequence == 0
            assert subscriber.pending is None and events == []

        task = asyncio.create_task(run_transaction(library.path, outer))
        await asyncio.wait_for(confirming.wait(), 1)
        assert subscriber.pending is None and events == []
        assert coordinator.marker().sequence == 0
        assert service.history_service.active_event == before[3]
        assert service.history_service.session_id == before[4]
        release.set()
        await asyncio.wait_for(task, 1)
        assert coordinator.marker().sequence == 1
        assert subscriber.pending.domains == frozenset({"queue"})
        assert [e.domains for e in events] == [frozenset({"queue"})]

    run(scenario())
    assert server_snapshot(service)[1:] == before[1:]


@pytest.mark.parametrize("operation", ["play-next", "queue", "reorder", "delete", "clear"])
@pytest.mark.parametrize("failure", ["unavailable", "status", "wrong_occurrence"])
def test_unconfirmed_queue_mutation_never_notifies(real_client, monkeypatch, operation, failure):
    client, library, player, playback = real_client
    start(client)
    target = run(playback.play_next("a"))
    before = server_snapshot(playback)
    original_status = player.status
    duplicate_id = run(player.queue_entries())[1].mpd_song_id
    coordinator = RealtimeCoordinator(library.path)
    subscriber, events = coordinator.subscribe(), []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    if failure == "unavailable":
        player.disconnect()
    elif failure == "status":
        player.fail_next("status")
    else:
        async def wrong_occurrence():
            return (await original_status()).model_copy(update={"song_id": duplicate_id})
        monkeypatch.setattr(player, "status", wrong_occurrence)
    method, endpoint, body, _ = request(operation, target)
    response = mutate(client, method, endpoint, body, key="unconfirmed")
    assert response.status_code == (503 if failure == "unavailable" else 502), response.text
    assert server_snapshot(service) == before
    assert run(app.state.idempotency_service._repository.get_by_key("unconfirmed")) is None
    assert coordinator.marker().sequence == 0
    assert subscriber.pending is None and events == []


@pytest.mark.parametrize("availability", ["MISSING", "UNREADABLE"])
def test_current_availability_change_does_not_end_session_during_queue_clear(
    real_client, availability,
):
    client, library, player, playback = real_client
    start(client)
    song = run(library.get_song("a"))
    run(library.upsert_song(song.model_copy(update={"availability_status": availability})))
    before = server_snapshot(playback)
    current = next(i for i in before[0].items if i.position == 0)
    current_id = run(player.status()).song_id
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    service = wire(playback, None, coordinator)
    run(service.clear())
    assert subscriber.pending.domains == frozenset({"queue"})
    assert server_snapshot(service)[1:] == before[1:]
    assert run(player.status()).song_id == current_id
    assert_execution_relationship(service, player, current_id=current.queue_item_id)
    assert coordinator.marker().library_revision == coordinator.marker().playlist_revision == 0


@pytest.mark.parametrize("operation", ["play-next", "queue", "reorder", "delete"])
@pytest.mark.parametrize("availability", ["MISSING", "UNREADABLE"])
def test_unavailable_pending_keeps_existing_rejection_and_no_notification(
    real_client, monkeypatch, operation, availability,
):
    client, library, _, playback = real_client
    start(client)
    target = run(playback.play_next("a"))
    song = run(library.get_song("c"))
    run(library.upsert_song(song.model_copy(update={"availability_status": availability})))
    before = server_snapshot(playback)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    service = wire(playback, None, coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    method, endpoint, body, _ = request(operation, target)
    response = mutate(client, method, endpoint, body, key="availability")
    assert response.status_code == 404, response.text
    assert server_snapshot(service) == before
    assert coordinator.marker().sequence == 0 and subscriber.pending is None
    assert run(app.state.idempotency_service._repository.get_by_key("availability")) is None


@pytest.mark.parametrize("after_commit", [False, True])
def test_queue_cancellation_preserves_commit_boundary(real_client, after_commit):
    client, library, player, playback = real_client
    start(client)
    before = server_snapshot(playback)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()

    class Publisher:
        async def publish(self, event):
            asyncio.current_task().cancel()
            await asyncio.sleep(0)

    service = wire(playback, Publisher() if after_commit else None, coordinator)

    async def scenario():
        async def outer(_):
            await service.add_to_queue("a")
            if not after_commit:
                asyncio.current_task().cancel()
                await asyncio.sleep(0)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.create_task(run_transaction(library.path, outer))

    run(scenario())
    assert server_snapshot(service)[1:] == before[1:]
    if after_commit:
        assert coordinator.marker().sequence == 1
        assert subscriber.pending.domains == frozenset({"queue"})
        assert len(run(service.queue_manager.list_items())) == len(before[0].items) + 1
        assert_execution_relationship(service, player)
    else:
        assert server_snapshot(service) == before
        assert coordinator.marker().sequence == 0 and subscriber.pending is None


@pytest.mark.parametrize("operation", ["reorder", "delete", "clear"])
def test_revision_conflict_precedes_player_changes_and_notification(real_client, operation):
    from server.app.repositories.queue_repository import QueueRevisionConflictError

    client, library, player, playback = real_client
    start(client)
    target = run(playback.play_next("a"))
    before, entries = server_snapshot(playback), run(player.queue_entries())
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    service = wire(playback, None, coordinator)
    with pytest.raises(QueueRevisionConflictError):
        run(apply(service, operation, target, expected_revision=before[0].revision - 1))
    assert server_snapshot(service) == before
    assert run(player.queue_entries()) == entries
    assert coordinator.marker().sequence == 0 and subscriber.pending is None


def test_publisher_failure_preserves_queue_terminal_and_invalidation(real_client, monkeypatch, caplog):
    client, library, _, playback = real_client
    start(client)
    before = server_snapshot(playback)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()

    class Publisher:
        async def publish(self, event):
            raise RuntimeError("queue delivery failed")

    service = wire(playback, Publisher(), coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    response = mutate(client, "POST", "/api/playback/songs/a/queue", key="delivery")
    assert response.status_code == 200, response.text
    assert "queue delivery failed" in caplog.text
    assert subscriber.pending.domains == frozenset({"queue"})
    assert server_snapshot(service)[1:] == before[1:]
    terminal = run(app.state.idempotency_service._repository.get_by_key("delivery"))
    assert terminal is not None and terminal.response_status == 200
    marker, final = coordinator.marker(), server_snapshot(service)
    assert mutate(client, "POST", "/api/playback/songs/a/queue", key="delivery").json() == response.json()
    assert coordinator.marker() == marker and server_snapshot(service) == final
