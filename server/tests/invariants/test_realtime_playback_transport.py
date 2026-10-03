from __future__ import annotations

import asyncio
import inspect

import pytest

from server.app.main import app
from server.app.player.models import PlayerState
from server.app.repositories.database import run_transaction, transaction_identity
from server.app.services.playback_service import PlaybackService
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.tests.invariants.assertions import server_snapshot
from server.tests.support.playback import mutate, run, start


def wire(playback, publisher, coordinator):
    assert "coordinator" in inspect.signature(PlaybackService).parameters, (
        "PlaybackService lacks committed transport propagation"
    )
    return PlaybackService(
        queue_manager=playback.queue_manager,
        history_service=playback.history_service,
        autoplay=playback.autoplay,
        player=playback.player,
        library_repository=playback.library_repository,
        event_publisher=publisher,
        coordinator=coordinator,
    )


@pytest.mark.parametrize("operation", ["pause", "seek", "stop"])
def test_transport_event_waits_for_confirmation_and_outer_commit(
    real_client, monkeypatch, operation,
):
    """RT-PLAYBACK: early/missing staging, rollback leaks and replay are bugs."""
    client, library, player, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            with pytest.raises(RuntimeError, match="requires an active transaction"):
                transaction_identity(library.path)
            # A separate read can see the complete committed state, including History.
            state = await asyncio.wait_for(service.queue_manager.get_playback_state(), 1)
            history = await service.history_service.list_history()
            assert state.state == ("PAUSED" if operation == "pause" else
                                   "STOPPED" if operation == "stop" else "PLAYING")
            assert [(e.song_id, e.reason) for e in history] == (
                [("a", "STOP")] if operation == "stop" else []
            )
            events.append(event)
            await coordinator.publish(event)

    service = wire(playback, Publisher(), coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    before = server_snapshot(service)
    songs = run(library.list_songs())
    playlists = run(app.state.playlist_service.revision_content())
    entries = run(player.queue_entries())
    endpoint = f"/api/playback/{operation}"
    body = {"seconds": 17} if operation == "seek" else None
    records = app.state.idempotency_service._repository
    original_create = records.create

    async def fail_terminal(**kwargs):
        # Operation has confirmed its external result, but is not committed yet.
        assert coordinator.marker().sequence == 0
        assert subscriber.pending is None and events == []
        raise RuntimeError("terminal write failed")

    monkeypatch.setattr(records, "create", fail_terminal)
    with pytest.raises(RuntimeError, match="terminal write failed"):
        mutate(client, "POST", endpoint, body, key="transport")
    assert server_snapshot(service) == before
    assert run(records.get_by_key("transport")) is None
    assert coordinator.marker().sequence == 0
    assert subscriber.pending is None and events == []
    monkeypatch.setattr(records, "create", original_create)
    response = mutate(client, "POST", endpoint, body, key="transport")
    assert response.status_code == 200, response.text
    domains = frozenset({"playback", "history"} if operation == "stop" else {"playback"})
    assert subscriber.pending.domains == domains
    assert [event.event_type for event in events] == ["playback.changed"]
    assert events[0].domains == domains
    assert coordinator.marker().library_revision == coordinator.marker().playlist_revision == 0
    assert run(service.queue_manager.queue_repository.get_snapshot()) == before[0]
    assert run(service.queue_manager.get_playback_state()).playback_context_id == before[1].playback_context_id
    if operation != "stop":
        assert server_snapshot(service)[2:] == before[2:]
    else:
        assert service.history_service.active_event is None
        assert service.history_service.session_id is None
    assert run(player.queue_entries()) == entries
    assert run(library.list_songs()) == songs
    assert run(app.state.playlist_service.revision_content()) == playlists
    marker, final = coordinator.marker(), server_snapshot(service)
    assert mutate(client, "POST", endpoint, body, key="transport").json() == response.json()
    assert coordinator.marker() == marker
    assert len(events) == 1 and server_snapshot(service) == final


@pytest.mark.parametrize("operation", ["pause", "seek", "stop"])
def test_confirmation_and_commit_barriers_hide_transport_notification(
    real_client, monkeypatch, operation,
):
    client, library, player, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    baseline = server_snapshot(service)
    original_status = player.status

    async def scenario():
        confirming, release = asyncio.Event(), asyncio.Event()

        async def held_status():
            confirming.set()
            await release.wait()
            return await original_status()

        monkeypatch.setattr(player, "status", held_status)

        async def outer(_):
            result = await (service.seek(17) if operation == "seek" else
                            getattr(service, operation)())
            assert coordinator.marker().sequence == 0
            assert subscriber.pending is None and events == []
            return result

        task = asyncio.create_task(run_transaction(library.path, outer))
        await asyncio.wait_for(confirming.wait(), 1)
        # Stop must not finalize History until PlayerPort confirmation returns.
        assert service.history_service.active_event == baseline[3]
        assert service.history_service.session_id == baseline[4]
        assert coordinator.marker().sequence == 0
        assert subscriber.pending is None and events == []
        release.set()
        await asyncio.wait_for(task, 1)
        assert coordinator.marker().sequence == 1
        assert len(events) == 1
        assert subscriber.pending.domains == events[0].domains

    run(scenario())


@pytest.mark.parametrize("operation", ["pause", "seek", "stop"])
@pytest.mark.parametrize("failure", ["command", "status", "unavailable"])
def test_failed_transport_has_no_success_notification(real_client, monkeypatch, operation, failure):
    client, library, player, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    before = server_snapshot(service)
    if failure == "unavailable":
        player.disconnect()
    else:
        player.fail_next(operation if failure == "command" else "status")
    response = mutate(client, "POST", f"/api/playback/{operation}",
                      {"seconds": 17} if operation == "seek" else None, key="failure")
    assert response.status_code == (503 if failure == "unavailable" else 502)
    assert server_snapshot(service) == before
    assert run(app.state.idempotency_service._repository.get_by_key("failure")) is None
    assert coordinator.marker().sequence == 0
    assert subscriber.pending is None and events == []


def test_unconfirmed_stop_never_publishes_history(real_client, monkeypatch):
    client, library, player, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    before = server_snapshot(service)
    original_stop = player.stop

    async def ineffective_stop():
        pass

    monkeypatch.setattr(player, "stop", ineffective_stop)
    assert mutate(client, "POST", "/api/playback/stop", key="stop").status_code == 502
    assert run(player.status()).state == PlayerState.PLAYING
    assert server_snapshot(service) == before
    assert coordinator.marker().sequence == 0
    assert subscriber.pending is None and events == []
    monkeypatch.setattr(player, "stop", original_stop)
    assert mutate(client, "POST", "/api/playback/stop", key="stop").status_code == 200
    assert len(events) == 1
    assert subscriber.pending.domains == frozenset({"playback", "history"})


def test_outer_transport_delta_noop_and_output_runner_isolation(real_client):
    client, library, player, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    events = []

    class Publisher:
        async def publish(self, event):
            events.append(event)

    service = wire(playback, Publisher(), coordinator)
    before = server_snapshot(service)

    async def scenario():
        async def reverted(_):
            await service.seek(17)
            await service.seek(0)

        await run_transaction(library.path, reverted)
        await service.seek(0)
        assert coordinator.marker().sequence == 0
        assert subscriber.pending is None and events == []

        async def output(lifecycle):
            await player.set_output_enabled(0, False)

        await service.run_output_operation(output)
        assert not (await player.outputs())[0].enabled
        assert coordinator.marker().sequence == 0
        assert subscriber.pending is None and events == []

        async def joint(_):
            await service.seek(17)
            await service.stop()

        await run_transaction(library.path, joint)
        assert coordinator.marker().sequence == 1
        assert [e.domains for e in events] == [frozenset({"playback", "history"})]
        assert subscriber.pending.domains == events[0].domains
        await service.stop()
        await service.pause()
        await service.seek(3)
        assert coordinator.marker().sequence == 1 and len(events) == 1

    run(scenario())
    assert run(service.queue_manager.queue_repository.get_snapshot()) == before[0]
    assert [(e.song_id, e.reason) for e in run(service.history_service.list_history())] == [("a", "STOP")]


@pytest.mark.parametrize("after_commit", [False, True])
def test_transport_cancellation_preserves_correct_commit_boundary(real_client, after_commit):
    client, library, _, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()

    class Publisher:
        async def publish(self, event):
            asyncio.current_task().cancel()
            await asyncio.sleep(0)

    service = wire(playback, Publisher() if after_commit else None, coordinator)
    before = server_snapshot(service)

    async def scenario():
        async def outer(_):
            await service.stop()
            if not after_commit:
                asyncio.current_task().cancel()
                await asyncio.sleep(0)

        with pytest.raises(asyncio.CancelledError):
            await asyncio.create_task(run_transaction(library.path, outer))

    run(scenario())
    if after_commit:
        assert coordinator.marker().sequence == 1
        assert subscriber.pending.domains == frozenset({"playback", "history"})
        assert run(service.queue_manager.get_playback_state()).state == "STOPPED"
        assert [(e.song_id, e.reason) for e in run(service.history_service.list_history())] == [("a", "STOP")]
        assert service.history_service.active_event is None
    else:
        assert server_snapshot(service) == before
        assert coordinator.marker().sequence == 0 and subscriber.pending is None


def test_publisher_failure_keeps_transport_terminal_and_invalidation(real_client, monkeypatch, caplog):
    client, library, _, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()

    class Publisher:
        async def publish(self, event):
            raise RuntimeError("delivery failed")

    service = wire(playback, Publisher(), coordinator)
    monkeypatch.setattr(app.state, "playback_service", service)
    response = mutate(client, "POST", "/api/playback/stop", key="publish-failure")
    assert response.status_code == 200, response.text
    assert "delivery failed" in caplog.text
    assert coordinator.marker().sequence == 1
    assert subscriber.pending.domains == frozenset({"playback", "history"})
    assert [(e.song_id, e.reason) for e in run(service.history_service.list_history())] == [("a", "STOP")]
    terminal = run(app.state.idempotency_service._repository.get_by_key("publish-failure"))
    assert terminal is not None and terminal.response_status == 200
    marker, final = coordinator.marker(), server_snapshot(service)
    assert mutate(client, "POST", "/api/playback/stop", key="publish-failure").json() == response.json()
    assert coordinator.marker() == marker and server_snapshot(service) == final
