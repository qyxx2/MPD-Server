from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import StreamingResponse

from server.app.main import app
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.services.idempotency_service import IdempotencyService
from server.app.services.realtime_connections import RealtimeConnections
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.tests.api.test_realtime_state import state_client
from server.tests.invariants.test_output_serialization import authority_snapshot
from server.tests.invariants.test_realtime_handoff import (
    ControlledSocket,
    connection_manager,
)
from server.tests.support.playback import real_client, run

__all__ = ["real_client", "state_client"]


def test_queue_budget_is_injectable_and_never_unbounded(tmp_path):
    path = str(tmp_path / "budget.db")
    assert RealtimeCoordinator(path).subscribe().queue.maxsize == 64
    coordinator = RealtimeCoordinator(path, queue_capacity=2)
    subscription = coordinator.subscribe()
    assert subscription.queue.maxsize == 2
    for capacity in (0, -1):
        with pytest.raises(ValueError):
            RealtimeCoordinator(path, queue_capacity=capacity)


def request():
    async def receive():
        return {"type": "http.request", "body": b"{}", "more_body": False}

    return Request({
        "type": "http", "method": "POST", "path": "/api/playback/pause",
        "headers": [(b"idempotency-key", b"delivery-pause")],
    }, receive)


@pytest.mark.parametrize("close_fails", [False, True])
@pytest.mark.parametrize("phase", ["initial", "live"])
def test_overflow_and_timeout_isolate_clients_and_preserve_commit(
    state_client, monkeypatch, caplog, close_fails, phase,
):
    """An overflow must interrupt even a blocked initial send, outside the commit owner."""
    _, state, playback, player, library, coordinator, _, output = state_client
    manager = connection_manager(state, coordinator)
    monkeypatch.setattr(coordinator, "_queue_capacity", 1)

    async def scenario():
        baseline = asyncio.all_tasks()
        before = await authority_snapshot(playback)
        port_queue, port_outputs = await player.queue_entries(), await player.outputs()
        songs = await library.list_songs()
        playlists = await app.state.playlist_service.list_playlists()
        favorites = await app.state.playlist_service.list_favorite_song_ids()
        receipt = output.get_cached_state()
        records = IdempotencyRepository(library.path)
        idempotency = IdempotencyService(records)
        calls = []
        closed = asyncio.Event()
        blocked = asyncio.Event()

        class SlowSocket(ControlledSocket):
            async def send_json(self, frame):
                if (frame["type"] == "snapshot") == (phase == "initial"):
                    blocked.set()
                    await asyncio.Event().wait()
                else:
                    await super().send_json(frame)

            async def close(self, code):
                await super().close(code)
                closed.set()
                if close_fails:
                    raise OSError("broken close")

        slow, healthy = SlowSocket(), ControlledSocket()
        slow.release_initial.set()
        healthy.release_initial.set()
        slow_task = asyncio.create_task(manager.connect(slow))
        healthy_task = asyncio.create_task(manager.connect(healthy))

        async def pause(_):
            calls.append("pause")
            await playback.pause()
            return StreamingResponse(iter([b'{"paused":true}']))

        try:
            if phase == "initial":
                await asyncio.wait_for(blocked.wait(), 1)
            else:
                await asyncio.wait_for(slow.frames.get(), 1)
            await asyncio.wait_for(healthy.frames.get(), 1)
            response = await asyncio.wait_for(idempotency.execute(request(), pause), 1)
            assert response.status_code == 200
            first = await asyncio.wait_for(healthy.frames.get(), 1)
            await asyncio.wait_for(blocked.wait(), 1)
            for seconds in (2, 3):
                await asyncio.wait_for(playback.seek(seconds), 1)
                last = await asyncio.wait_for(healthy.frames.get(), 1)
            assert last["sequence"] > first["sequence"]
            assert last["sequence"] == coordinator.marker().sequence
            terminal = await records.get_by_key("delivery-pause")
            assert terminal is not None
            # Independent SQLite read, not the writer's transaction or response.
            committed = await authority_snapshot(playback)
            assert committed[1].state == "PAUSED"
            assert committed[0] == before[0] and committed[2:] == before[2:]
            assert committed[1].song_id == before[1].song_id
            assert committed[1].playback_context_id == before[1].playback_context_id
            assert await player.queue_entries() == port_queue
            assert await player.outputs() == port_outputs
            assert await library.list_songs() == songs
            assert await app.state.playlist_service.list_playlists() == playlists
            assert await app.state.playlist_service.list_favorite_song_ids() == favorites
            assert output.get_cached_state() == receipt
            replay = await idempotency.execute(request(), pause)
            assert replay.status_code == 200 and replay.body == response.body
            assert calls == ["pause"] and await records.get_by_key("delivery-pause") == terminal
            # No 10-second wait for a dead sender after an overflow notification.
            await asyncio.wait_for(closed.wait(), .2)
            await asyncio.wait_for(slow_task, 1)
            assert slow.close_codes == [1013] and slow.frames.empty()
            assert len(coordinator._subscriptions) == len(manager._connections) == 1
            assert await authority_snapshot(playback) == committed
            marker = coordinator.marker()
            await playback.seek(4)
            update = await asyncio.wait_for(healthy.frames.get(), 1)
            assert update["sequence"] == coordinator.marker().sequence > marker.sequence
        finally:
            slow_task.cancel()
            healthy.incoming.put_nowait({"type": "websocket.disconnect"})
            await asyncio.gather(slow_task, healthy_task, return_exceptions=True)
        assert not coordinator._subscriptions and not manager._connections
        assert asyncio.all_tasks() == baseline

    run(scenario())
    assert "Realtime delivery failed connection=" in caplog.text
    if close_fails:
        assert "Realtime close failed connection=" in caplog.text


class FakeClock:
    """Advance network deadlines explicitly; real task scheduling and cancellation remain."""

    def __init__(self):
        self.now = 0
        self.deadlines = {}

    def advance(self, seconds):
        self.now += seconds
        for expired, deadline in tuple(self.deadlines.items()):
            if deadline <= self.now and not expired.done():
                expired.set_result(None)

    async def wait_for(self, operation, timeout):
        task = asyncio.create_task(operation)
        expired = asyncio.get_running_loop().create_future()
        self.deadlines[expired] = self.now + timeout
        try:
            done, _ = await asyncio.wait((task, expired), return_when=asyncio.FIRST_COMPLETED)
            if task in done:
                return task.result()
            raise TimeoutError("fake network deadline expired")
        finally:
            self.deadlines.pop(expired)
            expired.cancel()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("phase", ["initial", "live"])
@pytest.mark.parametrize("exit_mode", ["close_timeout", "cancel_during_close"])
def test_send_timeout_and_blocked_close_release_resources_without_rollback(
    state_client, monkeypatch, phase, exit_mode,
):
    from server.app.services import realtime_connections

    _, state, playback, player, library, coordinator, _, output = state_client
    clock = FakeClock()
    # Override only the connection module's deadline scheduler, not the loop,
    # Service/DB operations, or the test's real-time deadlock guards.
    monkeypatch.setattr(realtime_connections, "asyncio", SimpleNamespace(
        **{name: getattr(asyncio, name) for name in (
            "create_task", "wait", "FIRST_COMPLETED", "gather",
        )}, wait_for=clock.wait_for,
    ))
    manager = connection_manager(state, coordinator)
    assert manager._send_timeout == 10

    async def scenario():
        baseline = asyncio.all_tasks()
        before = await authority_snapshot(playback)
        port_queue, port_outputs = await player.queue_entries(), await player.outputs()
        receipt = output.get_cached_state()
        records = IdempotencyRepository(library.path)
        idempotency = IdempotencyService(records)
        blocked, closing = asyncio.Event(), asyncio.Event()
        send_cleaned, receive_cleaned, close_cleaned = (
            asyncio.Event(), asyncio.Event(), asyncio.Event(),
        )
        calls = []

        class BrokenSocket(ControlledSocket):
            async def send_json(self, frame):
                if (frame["type"] == "snapshot") == (phase == "initial"):
                    blocked.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        send_cleaned.set()
                else:
                    await super().send_json(frame)

            async def receive(self):
                try:
                    return await super().receive()
                finally:
                    await asyncio.sleep(0)
                    receive_cleaned.set()

            async def close(self, code):
                await super().close(code)
                # Unsubscribe/cancel/await must precede a potentially stuck close.
                assert len(coordinator._subscriptions) == len(manager._connections) == 1
                assert send_cleaned.is_set() and receive_cleaned.is_set()
                closing.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    close_cleaned.set()

        slow, healthy = BrokenSocket(), ControlledSocket()
        slow.release_initial.set()
        healthy.release_initial.set()
        slow_task = asyncio.create_task(manager.connect(slow))
        healthy_task = asyncio.create_task(manager.connect(healthy))

        async def pause(_):
            calls.append("pause")
            await playback.pause()
            return StreamingResponse(iter([b'{"paused":true}']))

        try:
            await asyncio.wait_for(healthy.frames.get(), 1)
            if phase == "live":
                assert (await asyncio.wait_for(slow.frames.get(), 1))["type"] == "snapshot"
            else:
                await asyncio.wait_for(blocked.wait(), 1)
            response = await asyncio.wait_for(idempotency.execute(request(), pause), 1)
            await asyncio.wait_for(healthy.frames.get(), 1)
            await asyncio.wait_for(blocked.wait(), 1)
            terminal = await records.get_by_key("delivery-pause")
            assert terminal is not None
            committed = await authority_snapshot(playback)
            assert committed[0] == before[0] and committed[2:] == before[2:]
            assert committed[1].state == "PAUSED"
            clock.advance(10)
            await asyncio.wait_for(closing.wait(), 1)
            assert slow.close_codes == [1013]
            assert not slow_task.done()
            # A healthy client's last mutation remains deliverable during close.
            await asyncio.wait_for(playback.seek(4), 1)
            last = await asyncio.wait_for(healthy.frames.get(), 1)
            assert last["sequence"] == coordinator.marker().sequence
            marker = coordinator.marker()
            replay = await idempotency.execute(request(), pause)
            assert replay.status_code == 200 and replay.body == response.body
            assert calls == ["pause"] and coordinator.marker() == marker
            assert await records.get_by_key("delivery-pause") == terminal
            if exit_mode == "close_timeout":
                clock.advance(10)
                await asyncio.wait_for(slow_task, 1)
            else:
                slow_task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await slow_task
            assert close_cleaned.is_set()
            after = await authority_snapshot(playback)
            assert after[0] == before[0] and after[2:] == before[2:]
            assert after[1].song_id == before[1].song_id
            assert after[1].playback_context_id == before[1].playback_context_id
            assert await player.queue_entries() == port_queue
            assert await player.outputs() == port_outputs
            assert output.get_cached_state() == receipt
        finally:
            slow_task.cancel()
            healthy.incoming.put_nowait({"type": "websocket.disconnect"})
            await asyncio.gather(slow_task, healthy_task, return_exceptions=True)
        assert not coordinator._subscriptions and not manager._connections
        assert not clock.deadlines and asyncio.all_tasks() == baseline

    run(scenario())


def test_send_budget_is_injectable(state_client):
    _, state, _, _, _, coordinator, _, _ = state_client
    manager = RealtimeConnections(
        state_service=state, coordinator=coordinator, snapshot_encoder=lambda _: {},
        send_timeout=.5,
    )
    assert manager._send_timeout == .5
