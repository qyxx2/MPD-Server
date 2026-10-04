from __future__ import annotations

import asyncio
import importlib
import importlib.util
import sqlite3

import anyio
import pytest

from server.app.api.realtime_schemas import FullStateSnapshotResponse
from server.app.main import app
from server.tests.api.test_realtime_state import state_client
from server.tests.invariants.assertions import server_snapshot
from server.tests.support.playback import real_client, run

__all__ = ["real_client", "state_client"]


class ControlledSocket:
    """Only network scheduling is faked; capture and mutations use real Services."""

    def __init__(self):
        self.initial_started = asyncio.Event()
        self.release_initial = asyncio.Event()
        self.frames = asyncio.Queue()
        self.incoming = asyncio.Queue()
        self.close_codes = []

    async def accept(self):
        pass

    async def send_json(self, frame):
        if frame["type"] == "snapshot":
            self.initial_started.set()
            await self.release_initial.wait()
        await self.frames.put(frame)

    async def receive(self):
        return await self.incoming.get()

    async def close(self, code):
        self.close_codes.append(code)


def connection_manager(state, coordinator):
    module = "server.app.services.realtime_connections"
    assert importlib.util.find_spec(module) is not None, "initial/live connection manager missing"
    return importlib.import_module(module).RealtimeConnections(
        state_service=state, coordinator=coordinator,
        snapshot_encoder=lambda snapshot: FullStateSnapshotResponse.model_validate(
            snapshot.model_dump(),
        ).model_dump(mode="json"),
    )


def test_last_mutation_during_initial_send_is_not_lost(state_client):
    """Subscribing after send or losing the pending watermark leaves the last commit invisible."""
    _, state, playback, _, _, coordinator, _, _ = state_client
    manager = connection_manager(state, coordinator)
    before = server_snapshot(playback)

    async def scenario():
        socket = ControlledSocket()
        task = asyncio.create_task(manager.connect(socket))
        try:
            await asyncio.wait_for(socket.initial_started.wait(), 1)
            # Sending cannot hold the capture/commit lock.
            await asyncio.wait_for(playback.pause(), 1)
            marker = coordinator.marker()
            socket.release_initial.set()
            first = await asyncio.wait_for(socket.frames.get(), 1)
            last = await asyncio.wait_for(socket.frames.get(), 1)
            assert first["type"] == "snapshot" and first["protocol_version"] == 1
            assert first["state"]["playback"]["state"] == "PLAYING"
            assert first["sequence"] < last["sequence"] == marker.sequence
            assert last == {
                "type": "invalidate", "protocol_version": 1, "epoch": marker.epoch,
                "sequence": marker.sequence, "domains": ["playback"],
                "revisions": {"library": 0, "playlist": 0},
            }
        finally:
            socket.release_initial.set()
            socket.incoming.put_nowait({"type": "websocket.disconnect"})
            await asyncio.wait_for(task, 1)
        assert not coordinator._subscriptions

    run(scenario())
    after = server_snapshot(playback)
    assert after[0] == before[0]
    assert after[1].state == "PAUSED"
    assert after[1].song_id == before[1].song_id
    assert after[1].playback_context_id == before[1].playback_context_id
    assert after[2:] == before[2:]


@pytest.mark.parametrize("window", ["before_register", "after_register", "inside_capture", "after_capture"])
def test_last_change_at_each_registration_capture_window(state_client, monkeypatch, window):
    """Every last mutation is covered by the first cut or a later monotonic invalidation."""
    _, state, playback, _, _, coordinator, _, _ = state_client
    manager = connection_manager(state, coordinator)

    async def scenario():
        reached, release = asyncio.Event(), asyncio.Event()
        socket = ControlledSocket()
        socket.release_initial.set()
        original_subscribe = coordinator.subscribe_committed
        original_capture = state.get_full_snapshot
        original_read = playback.queue_manager.get_snapshot

        async def gated_subscribe():
            if window == "before_register":
                reached.set()
                await release.wait()
            subscription = await original_subscribe()
            if window == "after_register":
                reached.set()
                await release.wait()
            return subscription

        async def gated_capture():
            snapshot = await original_capture()
            reached.set()
            await release.wait()
            return snapshot

        async def gated_read():
            snapshot = await original_read()
            reached.set()
            await release.wait()
            return snapshot

        if window in {"before_register", "after_register"}:
            monkeypatch.setattr(coordinator, "subscribe_committed", gated_subscribe)
        elif window == "after_capture":
            monkeypatch.setattr(state, "get_full_snapshot", gated_capture)
        else:
            monkeypatch.setattr(playback.queue_manager, "get_snapshot", gated_read)

        task = asyncio.create_task(manager.connect(socket))
        try:
            await asyncio.wait_for(reached.wait(), 1)
            if window == "inside_capture":
                started = asyncio.Event()

                async def change():
                    started.set()
                    await playback.pause()

                writer = asyncio.create_task(change())
                await asyncio.wait_for(started.wait(), 1)
                assert not writer.done(), "capture did not serialize the concurrent mutation"
                release.set()
                await asyncio.wait_for(writer, 1)
            else:
                await asyncio.wait_for(playback.pause(), 1)
                release.set()
            marker = coordinator.marker()
            first = await asyncio.wait_for(socket.frames.get(), 1)
            assert first["type"] == "snapshot"
            assert first["epoch"] == first["state"]["epoch"] == marker.epoch
            assert first["sequence"] == first["state"]["sequence"]
            if first["state"]["playback"]["state"] == "PAUSED":
                assert first["sequence"] >= marker.sequence
            else:
                last = await asyncio.wait_for(socket.frames.get(), 1)
                assert last["type"] == "invalidate" and last["domains"] == ["playback"]
                assert last["sequence"] >= marker.sequence > first["sequence"]
                assert last["revisions"] == {"library": 0, "playlist": 0}
        finally:
            release.set()
            socket.incoming.put_nowait({"type": "websocket.disconnect"})
            await asyncio.wait_for(task, 1)
        assert not coordinator._subscriptions

    run(scenario())


def test_initial_failure_has_no_success_frame_and_retry_preserves_all_authorities(
    state_client, monkeypatch,
):
    _, state, playback, player, library, coordinator, _, output = state_client
    manager = connection_manager(state, coordinator)
    before = server_snapshot(playback)
    songs = run(library.list_songs())
    port_queue = run(player.queue_entries())
    port_outputs = run(player.outputs())
    receipt = output.get_cached_state()
    marker = coordinator.marker()

    async def scenario():
        original = playback.history_service.get_availability

        async def failed():
            raise RuntimeError("history unavailable")

        socket = ControlledSocket()
        monkeypatch.setattr(playback.history_service, "get_availability", failed)
        await asyncio.wait_for(manager.connect(socket), 1)
        assert socket.close_codes == [1011]
        assert socket.frames.empty() and not coordinator._subscriptions
        monkeypatch.setattr(playback.history_service, "get_availability", original)
        retry = ControlledSocket()
        retry.release_initial.set()
        task = asyncio.create_task(manager.connect(retry))
        try:
            first = await asyncio.wait_for(retry.frames.get(), 1)
            assert first["type"] == "snapshot" and first["sequence"] == marker.sequence
            assert first["state"]["queue"] == before[0].model_dump(mode="json")
            assert first["state"]["history"]["active_event"] == before[3].model_dump(mode="json")
        finally:
            retry.incoming.put_nowait({"type": "websocket.disconnect"})
            await asyncio.wait_for(task, 1)
        assert not coordinator._subscriptions and not manager._connections

    run(scenario())
    assert server_snapshot(playback) == before
    assert run(library.list_songs()) == songs
    assert run(player.queue_entries()) == port_queue and run(player.outputs()) == port_outputs
    assert output.get_cached_state() == receipt and coordinator.marker() == marker


def test_delayed_domain_callback_never_rolls_back_live_revisions(real_client, monkeypatch):
    """Real producer commit order, not callback completion order, owns delivered versions."""
    coordinator = app.state.realtime_coordinator
    manager = connection_manager(app.state.state_service, coordinator)
    playlist = app.state.playlist_service
    before = server_snapshot(real_client[3])

    async def scenario():
        socket = ControlledSocket()
        held, release = asyncio.Event(), asyncio.Event()
        original_publish = coordinator.publish
        calls = 0

        async def delayed_publish(event):
            nonlocal calls
            calls += 1
            if calls == 1:
                held.set()
                await release.wait()
            await original_publish(event)

        monkeypatch.setattr(coordinator, "publish", delayed_publish)
        task = asyncio.create_task(manager.connect(socket))
        writer = None
        try:
            await asyncio.wait_for(socket.initial_started.wait(), 1)
            writer = asyncio.create_task(playlist.create_playlist("first"))
            await asyncio.wait_for(held.wait(), 1)
            await asyncio.wait_for(playlist.create_playlist("last"), 1)
            intermediate = coordinator.marker()
            release.set()
            await asyncio.wait_for(writer, 1)
            final = coordinator.marker()
            assert final.playlist_revision == intermediate.playlist_revision == 2
            socket.release_initial.set()
            first = await asyncio.wait_for(socket.frames.get(), 1)
            sequence = first["sequence"]
            revision = first["state"]["revisions"]["playlist"]
            while sequence < final.sequence:
                frame = await asyncio.wait_for(socket.frames.get(), 1)
                assert frame["type"] == "invalidate" and frame["epoch"] == final.epoch
                assert frame["sequence"] > sequence
                assert frame["revisions"]["playlist"] >= revision
                assert frame["revisions"]["library"] == 0
                sequence, revision = frame["sequence"], frame["revisions"]["playlist"]
            assert revision == 2
            assert [p.name for p in await playlist.list_playlists()] == ["first", "last"]
        finally:
            release.set()
            socket.release_initial.set()
            if writer is not None:
                await writer
            socket.incoming.put_nowait({"type": "websocket.disconnect"})
            await asyncio.wait_for(task, 1)
        assert not coordinator._subscriptions

    run(scenario())
    assert server_snapshot(real_client[3]) == before


def test_socket_capture_never_reads_player_or_mutates_business(state_client, monkeypatch):
    _, state, playback, player, library, coordinator, _, output = state_client
    manager = connection_manager(state, coordinator)
    before = server_snapshot(playback)
    songs = run(library.list_songs())
    marker = coordinator.marker()
    receipt = output.get_cached_state()

    async def forbidden(*args, **kwargs):
        raise AssertionError("connection performed external I/O or recovery/control")

    for name in ("status", "queue_entries", "outputs", "play", "pause", "stop", "seek",
                 "queue_add", "queue_delete", "queue_move", "queue_clear", "queue_play",
                 "set_output_enabled", "update_database"):
        monkeypatch.setattr(player, name, forbidden)
    monkeypatch.setattr(playback, "reconcile_external_status", forbidden)

    async def scenario():
        socket = ControlledSocket()
        socket.release_initial.set()
        task = asyncio.create_task(manager.connect(socket))
        try:
            frame = await asyncio.wait_for(socket.frames.get(), 1)
            assert frame["state"]["queue"] == before[0].model_dump(mode="json")
            assert frame["state"]["playback_observation"]["freshness"] == "unknown"
            assert frame["state"]["history"]["active_event"] == before[3].model_dump(mode="json")
            assert frame["state"]["output"] == receipt.model_dump(mode="json")
        finally:
            socket.incoming.put_nowait({"type": "websocket.disconnect"})
            await asyncio.wait_for(task, 1)
        assert not coordinator._subscriptions

    run(scenario())
    assert server_snapshot(playback) == before and run(library.list_songs()) == songs
    assert coordinator.marker() == marker and output.get_cached_state() == receipt


def test_failed_registration_boundary_leaves_no_subscription(state_client, monkeypatch):
    """A failed read-boundary commit cannot orphan a subscription before connect owns it."""
    from server.app.repositories import database

    _, state, playback, _, _, coordinator, _, _ = state_client
    manager = connection_manager(state, coordinator)
    before = server_snapshot(playback)
    marker = coordinator.marker()

    class RejectCommit(sqlite3.Connection):
        def commit(self):
            raise sqlite3.OperationalError("subscription boundary commit failed")

    async def scenario():
        socket = ControlledSocket()
        with monkeypatch.context() as patch:
            patch.setattr(database, "_connect", lambda p: sqlite3.connect(p, factory=RejectCommit))
            await asyncio.wait_for(manager.connect(socket), 1)
        assert socket.close_codes == [1011] and socket.frames.empty()
        assert not coordinator._subscriptions and not manager._connections

    run(scenario())
    assert server_snapshot(playback) == before and coordinator.marker() == marker


def test_asgi_cancellation_awaits_connection_children(state_client):
    """ASGI cancel scopes must not interrupt the ordinary disconnect cleanup await."""
    _, state, playback, _, _, coordinator, _, _ = state_client
    manager = connection_manager(state, coordinator)
    before = server_snapshot(playback)

    async def scenario():
        cleaned = asyncio.Event()
        baseline_tasks = asyncio.all_tasks()

        class Socket(ControlledSocket):
            async def receive(self):
                try:
                    return await super().receive()
                finally:
                    # A real ASGI receive can need a checkpoint to release resources.
                    await asyncio.sleep(0)
                    cleaned.set()

        socket = Socket()
        socket.release_initial.set()
        async with anyio.create_task_group() as group:
            group.start_soon(manager.connect, socket)
            assert (await asyncio.wait_for(socket.frames.get(), 1))["type"] == "snapshot"
            group.cancel_scope.cancel()
        assert cleaned.is_set(), "child cleanup was interrupted by repeated ASGI cancellation"
        assert not coordinator._subscriptions and not manager._connections
        assert asyncio.all_tasks() == baseline_tasks

    run(scenario())
    assert server_snapshot(playback) == before
