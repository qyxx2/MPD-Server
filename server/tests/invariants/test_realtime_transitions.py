from __future__ import annotations

import asyncio

import pytest

from server.app.main import app
from server.app.models.queue import PlaybackContext
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


def prepare(client, playback, operation):
    items = start(client)
    if operation == "previous":
        assert mutate(client, "POST", "/api/playback/next", key="prepare").status_code == 200
    target = next(i for i in items if i["song_id"] == ("a" if operation == "delete" else "b"))
    endpoint = {
        "start": "/api/playback/tracks/b/play",
        "context": "/api/playback/collections/play",
        "play-now": f"/api/playback/queue/items/{target['queue_item_id']}/play",
        "next": "/api/playback/next",
        "previous": "/api/playback/previous",
        "delete": f"/api/playback/queue/items/{target['queue_item_id']}",
    }[operation]
    body = {"source_type": "SONGS", "song_ids": ["b", "c"]} if operation == "context" else None
    return "DELETE" if operation == "delete" else "POST", endpoint, body


@pytest.mark.parametrize("operation", ["start", "context", "play-now", "next", "previous", "delete"])
def test_transition_notification_matches_committed_history(real_client, monkeypatch, operation):
    """RT-PLAYBACK: omitted/early/partial staging or replayed History must fail."""
    client, library, player, playback = real_client
    method, endpoint, body = prepare(client, playback, operation)
    before = server_snapshot(playback)
    songs = run(library.list_songs())
    playlists = run(app.state.playlist_service.revision_content())
    outputs = run(player.outputs())
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events, committed = [], []
    expected_song = "a" if operation == "previous" else "b"
    expected_history = ([("b", "SWITCH_AWAY"), ("a", "SWITCH_AWAY")]
                        if operation == "previous" else [("a", "SWITCH_AWAY")])

    class Publisher:
        async def publish(self, event):
            with pytest.raises(RuntimeError, match="requires an active transaction"):
                transaction_identity(library.path)
            # Lock-free independent reader sees the joint state, never an intermediate frame.
            async def read(_):
                return (await service.queue_manager.queue_repository.get_snapshot(),
                        await service.queue_manager.get_playback_state(),
                        await service.history_service.list_history(),
                        service.history_service.active_event, service.history_service.session_id)
            snapshot = await asyncio.wait_for(run_transaction(library.path, read), 1)
            assert snapshot[1].song_id == expected_song
            assert [(e.song_id, e.reason) for e in snapshot[2]] == expected_history
            assert snapshot[3].song_id == expected_song
            assert snapshot[4] == before[4]
            committed.append(snapshot)
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    records = app.state.idempotency_service._repository
    original_create = records.create

    async def fail_terminal(**kwargs):
        assert coordinator.marker().sequence == 0
        assert subscriber.pending is None and events == []
        raise RuntimeError("transition terminal failed")

    monkeypatch.setattr(records, "create", fail_terminal)
    with pytest.raises(RuntimeError, match="transition terminal failed"):
        mutate(client, method, endpoint, body, key="transition")
    assert server_snapshot(service) == before
    assert run(records.get_by_key("transition")) is None
    assert coordinator.marker().sequence == 0 and subscriber.pending is None and events == []

    monkeypatch.setattr(records, "create", original_create)
    response = mutate(client, method, endpoint, body, key="transition")
    assert response.status_code == (204 if operation == "delete" else 200), response.text
    assert subscriber.pending is not None, "confirmed current/history delta was never registered"
    domains = frozenset({"playback", "queue", "history"})
    assert subscriber.pending.domains == domains
    assert coordinator.marker().sequence == 1
    assert [e.event_type for e in events] == ["playback.changed"]
    assert events[0].domains == domains
    final = server_snapshot(service)
    assert committed == [final]
    assert final[0].revision > before[0].revision
    assert_execution_relationship(service, player)
    if operation in {"play-now", "next", "previous", "delete"}:
        assert final[1].playback_context_id == before[1].playback_context_id
    if operation in {"start", "context"}:
        assert final[1].playback_context_id != before[1].playback_context_id
    assert run(library.list_songs()) == songs
    assert run(app.state.playlist_service.revision_content()) == playlists
    assert run(player.outputs()) == outputs
    marker, entries = coordinator.marker(), run(player.queue_entries())
    assert marker.library_revision == marker.playlist_revision == 0
    replay = mutate(client, method, endpoint, body, key="transition")
    assert replay.status_code == response.status_code and replay.content == response.content
    assert coordinator.marker() == marker and len(events) == 1
    assert server_snapshot(service) == final and run(player.queue_entries()) == entries


@pytest.mark.parametrize("stopped", [False, True])
def test_explicit_reconciliation_propagates_only_committed_existing_delta(real_client, stopped):
    """Missing explicit-path staging loses changes; this does not authorize recovery."""
    client, library, player, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    # Reuse the committed occurrence binding; construction alone proves none.
    service._observations.binding = playback._observations.binding
    before = server_snapshot(service)
    run(player.stop() if stopped else player.pause())

    async def failing(_):
        await service.reconcile_external_status()
        assert coordinator.marker().sequence == 0 and subscriber.pending is None and events == []
        raise RuntimeError("outer failed")

    with pytest.raises(RuntimeError, match="outer failed"):
        run(run_transaction(library.path, failing))
    assert server_snapshot(service) == before
    assert coordinator.marker().sequence == 0 and subscriber.pending is None and events == []
    result = run(service.reconcile_external_status())
    final = server_snapshot(service)
    assert final[0] == before[0]
    assert final[2:] == before[2:]
    if stopped:
        assert result.outcome == "UNKNOWN" and result.reconciliation_required
        assert final == before
        assert coordinator.marker().sequence == 0
        assert subscriber.pending is None and events == []
    else:
        assert result.outcome == "APPLIED"
        assert final[1].state == "PAUSED"
        assert subscriber.pending is not None, "explicit reconciliation delta was not registered"
        assert subscriber.pending.domains == frozenset({"playback"})
        assert [e.domains for e in events] == [frozenset({"playback"})]
        assert coordinator.marker().sequence == 1
    run(service.reconcile_external_status())
    assert coordinator.marker().sequence == (0 if stopped else 1)
    assert len(events) == (0 if stopped else 1)
    assert server_snapshot(service)[2:] == final[2:]


def test_empty_context_and_no_successor_have_no_phantom_transition(real_client):
    """Read-like early returns must not fabricate History or bump sequence."""
    client, library, player, playback = real_client
    start(client)
    run(playback.queue_manager.clear())
    for song_id in "abc":
        song = run(library.get_song(song_id))
        run(library.upsert_song(song.model_copy(update={"availability_status": "MISSING"})))
    run(playback._sync_player_queue())
    before = server_snapshot(playback)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    service = wire(playback, None, coordinator)
    run(service.play_context(PlaybackContext(context_id="empty", source_type="SONGS", ordered_song_ids=())))
    run(service.next())
    run(service.previous())
    assert server_snapshot(service) == before
    assert coordinator.marker().sequence == 0 and subscriber.pending is None
    assert run(player.status()).song_uri == "a.flac"


@pytest.mark.parametrize("operation", ["start", "context", "play-now", "next", "previous", "delete"])
@pytest.mark.parametrize("failure", ["command", "status", "disconnected"])
def test_failed_transition_does_not_publish_and_can_retry(real_client, monkeypatch, operation, failure):
    """Failed external confirmation must not leak persisted/runtime success."""
    client, library, player, playback = real_client
    method, endpoint, body = prepare(client, playback, operation)
    before = server_snapshot(playback)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    if failure == "disconnected":
        player.disconnect()
    else:
        player.fail_next("play" if failure == "command" else "status")
    response = mutate(client, method, endpoint, body, key="failed-transition")
    assert response.status_code == (503 if failure == "disconnected" else 502), response.text
    assert server_snapshot(service) == before
    assert run(app.state.idempotency_service._repository.get_by_key("failed-transition")) is None
    assert coordinator.marker().sequence == 0 and subscriber.pending is None and events == []
    player.reconnect()
    retry = mutate(client, method, endpoint, body, key="failed-transition")
    assert retry.status_code == (204 if operation == "delete" else 200), retry.text
    assert coordinator.marker().sequence == 1
    assert [e.domains for e in events] == [frozenset({"playback", "queue", "history"})]
    assert_execution_relationship(service, player)
    final, marker = server_snapshot(service), coordinator.marker()
    assert mutate(client, method, endpoint, body, key="failed-transition").content == retry.content
    assert server_snapshot(service) == final and coordinator.marker() == marker and len(events) == 1


@pytest.mark.parametrize("operation", ["start", "context", "play-now", "next", "previous", "delete"])
def test_transition_confirmation_barrier_and_outer_commit(real_client, monkeypatch, operation):
    """Before actual confirmation and outer commit there is no success notice."""
    client, library, player, playback = real_client
    prepare(client, playback, operation)
    before = server_snapshot(playback)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    target = next(i for i in before[0].items if i.song_id == ("a" if operation == "delete" else "b"))
    original_status = player.status

    async def scenario():
        confirming, release = asyncio.Event(), asyncio.Event()

        async def held_status():
            confirming.set()
            await release.wait()
            return await original_status()

        monkeypatch.setattr(player, "status", held_status)

        async def outer(_):
            if operation == "start":
                await service.start_track("b")
            elif operation == "context":
                await service.play_context(PlaybackContext(
                    context_id="explicit-order", source_type="SONGS", ordered_song_ids=("b", "c"),
                ))
            elif operation == "play-now":
                await service.play_now(target.queue_item_id)
            elif operation == "delete":
                await service.delete(target.queue_item_id)
            else:
                await getattr(service, operation)()
            assert coordinator.marker().sequence == 0 and subscriber.pending is None and events == []

        task = asyncio.create_task(run_transaction(library.path, outer))
        await asyncio.wait_for(confirming.wait(), 1)
        assert service.history_service.active_event == before[3]
        assert service.history_service.session_id == before[4]
        assert coordinator.marker().sequence == 0 and subscriber.pending is None and events == []
        release.set()
        await asyncio.wait_for(task, 1)
        assert coordinator.marker().sequence == 1
        assert [e.domains for e in events] == [frozenset({"playback", "queue", "history"})]
        assert subscriber.pending.domains == events[0].domains

    run(scenario())
    assert_execution_relationship(service, player)


@pytest.mark.parametrize("operation", ["next", "delete"])
@pytest.mark.parametrize("candidate", ["available", "missing", "unreadable", "none"])
def test_successor_selection_preserves_history_and_joint_domains(real_client, monkeypatch, operation, candidate):
    """Unavailable skipping must notify only real deltas, not fabricate active History."""
    client, library, player, playback = real_client
    items = start(client)
    current = next(i for i in items if i["position"] == 0)
    if candidate in {"missing", "unreadable"}:
        song = run(library.get_song("b"))
        run(library.upsert_song(song.model_copy(update={"availability_status": candidate.upper()})))
    elif candidate == "none":
        for song_id in "abc":
            song = run(library.get_song(song_id))
            run(library.upsert_song(song.model_copy(update={"availability_status": "MISSING"})))
    before = server_snapshot(playback)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    response = mutate(client, "POST" if operation == "next" else "DELETE",
                      "/api/playback/next" if operation == "next" else
                      f"/api/playback/queue/items/{current['queue_item_id']}", key="successor")
    assert response.status_code == (200 if operation == "next" else 204), response.text
    final = server_snapshot(service)
    domains = frozenset({"queue"} if candidate == "none" and operation == "next"
                        else {"queue", "playback", "history"})
    assert subscriber.pending.domains == domains
    assert [e.domains for e in events] == [domains] and coordinator.marker().sequence == 1
    if candidate == "none" and operation == "next":
        assert final[1:] == before[1:]
        assert run(player.status()).song_uri == "a.flac"
    elif candidate == "none":
        assert final[1].state == "STOPPED" and not final[1].autoplay_enabled
        assert final[3:] == (None, None)
        assert [(e.song_id, e.reason) for e in final[2]] == [("a", "STOP")]
        assert run(player.status()).state.value == "stopped"
    else:
        expected = "b" if candidate == "available" else "c"
        assert final[1].song_id == final[3].song_id == expected
        assert [(e.song_id, e.reason) for e in final[2]] == [("a", "SWITCH_AWAY")]
        assert_execution_relationship(service, player)
    assert coordinator.marker().library_revision == coordinator.marker().playlist_revision == 0


def test_delete_after_stop_notifies_queue_without_restarting_history(real_client):
    """PB-DELETE-CURRENT: propagation cannot restart a stopped session."""
    client, library, player, playback = real_client
    items = start(client)
    run(playback.stop())
    before = server_snapshot(playback)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    service = wire(playback, None, coordinator)
    run(service.delete(next(i["queue_item_id"] for i in items if i["position"] == 0)))
    assert subscriber.pending.domains == frozenset({"queue"})
    assert coordinator.marker().sequence == 1
    final = server_snapshot(service)
    # Existing confirmation saves updated_at even when the business state is unchanged.
    assert final[1].model_dump(exclude={"updated_at"}) == before[1].model_dump(exclude={"updated_at"})
    assert final[2:] == before[2:]
    assert run(player.status()).state.value == "stopped"


@pytest.mark.parametrize("after_commit", [False, True])
def test_transition_cancellation_keeps_joint_commit_boundary(real_client, after_commit):
    """Cancellation must discard precommit changes and retain committed invalidation."""
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
            await service.next()
            if not after_commit:
                asyncio.current_task().cancel()
                await asyncio.sleep(0)

        with pytest.raises(asyncio.CancelledError):
            await asyncio.create_task(run_transaction(library.path, outer))

    run(scenario())
    if after_commit:
        assert coordinator.marker().sequence == 1
        assert subscriber.pending.domains == frozenset({"queue", "playback", "history"})
        assert [(e.song_id, e.reason) for e in run(service.history_service.list_history())] == [("a", "SWITCH_AWAY")]
        assert_execution_relationship(service, player)
    else:
        assert server_snapshot(service) == before
        assert coordinator.marker().sequence == 0 and subscriber.pending is None


def test_outer_joint_mutations_publish_only_final_history(real_client):
    """Several producers in one owner must merge, without an intermediate frame."""
    client, library, player, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)

    async def outer(_):
        await service.add_to_queue("a")
        await service.next()
        await service.pause()
        assert coordinator.marker().sequence == 0 and subscriber.pending is None and events == []

    run(run_transaction(library.path, outer))
    assert coordinator.marker().sequence == 1
    assert [e.domains for e in events] == [frozenset({"queue", "playback", "history"})]
    assert subscriber.pending.domains == events[0].domains
    assert run(service.queue_manager.get_playback_state()).state == "PAUSED"
    assert [(e.song_id, e.reason) for e in run(service.history_service.list_history())] == [("a", "SWITCH_AWAY")]
    assert_execution_relationship(service, player)


def test_transition_publisher_failure_preserves_terminal_and_replay(real_client, monkeypatch, caplog):
    """Delivery failure must not reclassify a confirmed joint commit as failure."""
    client, library, player, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()

    class Publisher:
        async def publish(self, event):
            raise RuntimeError("transition delivery failed")

    service = wire(playback, Publisher(), coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    response = mutate(client, "POST", "/api/playback/next", key="delivery")
    assert response.status_code == 200, response.text
    assert "transition delivery failed" in caplog.text
    assert coordinator.marker().sequence == 1
    assert subscriber.pending.domains == frozenset({"queue", "playback", "history"})
    assert_execution_relationship(service, player)
    terminal = run(app.state.idempotency_service._repository.get_by_key("delivery"))
    assert terminal is not None and terminal.response_status == 200
    final, marker = server_snapshot(service), coordinator.marker()
    assert mutate(client, "POST", "/api/playback/next", key="delivery").content == response.content
    assert server_snapshot(service) == final and coordinator.marker() == marker
