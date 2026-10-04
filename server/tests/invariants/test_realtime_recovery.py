from __future__ import annotations

import asyncio
from copy import deepcopy
from shutil import copy2

import pytest

from server.app.main import app
from server.app.models.output import OutputMode
from server.app.models.queue import PlaybackContext
from server.app.services import library_scanner as scanner_module
from server.app.services.library_scanner import LibraryScanner
from server.app.services.playlist_service import PlaylistService
from server.tests.api.test_realtime_state import state_client
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_realtime_handoff import (
    ControlledSocket,
    connection_manager,
)
from server.tests.support.playback import mutate, real_client, run

__all__ = ["real_client", "state_client"]


class ProtocolProbe:
    """Test-only protocol consumer; no application store or business inference."""

    def __init__(self):
        self.generation = 0
        self.state = None
        self.required_sequence = 0

    def connect(self, frame):
        assert frame["type"] == "snapshot" and frame["protocol_version"] == 1
        assert frame["epoch"] == frame["state"]["epoch"]
        assert frame["sequence"] == frame["state"]["sequence"]
        self.generation += 1
        self.state = deepcopy(frame["state"])
        self.required_sequence = frame["sequence"]
        return self.generation

    def invalidate(self, frame):
        assert frame["type"] == "invalidate"
        assert frame["epoch"] == self.state["epoch"]
        self.required_sequence = max(self.required_sequence, frame["sequence"])

    def apply(self, state, generation):
        if generation != self.generation or state["epoch"] != self.state["epoch"]:
            return False
        if state["sequence"] < self.required_sequence:
            return False
        if state["sequence"] <= self.state["sequence"]:
            return False
        self.state = deepcopy(state)
        return True


def without_capture_time(state):
    state = deepcopy(state)
    state.pop("captured_at")
    return state


@pytest.mark.parametrize("availability", ["AVAILABLE", "MISSING", "UNREADABLE"])
@pytest.mark.parametrize("disconnected_port", [False, True])
def test_reconnect_replaces_all_domains_and_epoch(
    state_client, tmp_path, media_fixture_dir, monkeypatch, availability, disconnected_port,
):
    """A cached first frame, partial replacement or replayed mutation loses committed domains."""
    client, state, playback, player, library, coordinator, _, output = state_client
    monkeypatch.setattr(app.state, "realtime_coordinator", coordinator)
    playlists = PlaylistService(
        app.state.playlist_service._repository, coordinator=coordinator, event_publisher=coordinator,
    )
    monkeypatch.setattr(app.state, "playlist_service", playlists)
    scanner = LibraryScanner(library, coordinator=coordinator, event_publisher=coordinator)
    probe = ProtocolProbe()
    with client.websocket_connect("/api/realtime") as socket:
        old_generation = probe.connect(socket.receive_json())
    old = deepcopy(probe.state)
    assert not coordinator._subscriptions

    root = tmp_path / "music"
    root.mkdir()
    target = root / "track.flac"
    copy2(media_fixture_dir / "metadata.flac", target)
    song_id = run(scanner.scan_paths([target])).added_song_ids[0]
    player._songs.append(str(target))
    player._durations[str(target)] = 300
    playlist = run(playlists.create_playlist("during disconnect"))
    run(playlists.add_song(playlist.playlist_id, song_id))
    run(playlists.set_favorite(song_id, True))
    run(playback.play_context(PlaybackContext(
        context_id="recovered-context", source_type="SONGS", ordered_song_ids=(song_id, song_id),
    )))
    run(playback.next())
    terminal_response = mutate(client, "POST", "/api/playback/seek", {"seconds": 17}, key="recover-seek")
    assert terminal_response.status_code == 200, terminal_response.text
    run(output.set_enabled(OutputMode.NAS_DAC, False))
    run(playback.observe())
    if availability == "MISSING":
        target.rename(tmp_path / "saved.flac")
        run(scanner.scan_full(root))
    elif availability == "UNREADABLE":
        def unreadable(_):
            raise PermissionError("fixture media unavailable")

        with monkeypatch.context() as patch:
            patch.setattr(scanner_module, "parse_media_file", unreadable)
            run(scanner.scan_paths([target]))
    if disconnected_port:
        player.disconnect()
        run(playback.observe())
        run(output.get_state())

    before = server_snapshot(playback)
    songs = run(library.list_songs())
    membership = run(playlists.revision_content())
    port_queue, port_outputs = deepcopy(player._queue), deepcopy(player._outputs)
    terminals = app.state.idempotency_service._repository
    terminal = run(terminals.get_by_key("recover-seek"))
    assert terminal is not None
    marker = coordinator.marker()
    expected = run(state.get_full_snapshot()).model_dump(mode="json")
    expected["current_song"] = client.get(f"/api/library/songs/{song_id}").json()
    history = client.get("/api/history").json()

    async def forbidden(*args, **kwargs):
        raise AssertionError("reconnect attempted external I/O or business recovery/control")

    with monkeypatch.context() as patch:
        for name in ("status", "queue_entries", "outputs", "play", "pause", "stop", "seek",
                     "queue_add", "queue_delete", "queue_move", "queue_clear", "queue_play",
                     "set_output_enabled"):
            patch.setattr(player, name, forbidden)
        patch.setattr(playback, "reconcile_external_status", forbidden)
        with client.websocket_connect("/api/realtime") as socket:
            frame = socket.receive_json()
            generation = probe.connect(frame)
            current = client.get("/api/state").json()
            assert without_capture_time(probe.state) == without_capture_time(expected)
            assert without_capture_time(current) == without_capture_time(expected)
            assert not probe.apply(old, old_generation)
            assert not probe.apply(current, generation), "same sequence must be idempotently ignored"
    assert probe.state["sequence"] > old["sequence"]
    assert probe.state["current_song"]["song_id"] == song_id
    assert probe.state["current_song"]["availability_status"] == availability
    assert probe.state["playback"]["state"] == "PLAYING"
    assert probe.state["playback"]["playback_context_id"] == "recovered-context"
    assert probe.state["playback_observation"]["position_seconds"] == 17
    assert probe.state["playback_observation"]["freshness"] == ("stale" if disconnected_port else "fresh")
    assert probe.state["output_observation"]["freshness"] == ("stale" if disconnected_port else "fresh")
    assert probe.state["output"]["last_request"]["status"] == "SUCCEEDED"
    assert probe.state["history"]["has_entries"] is True
    assert probe.state["history"]["active_event"]["song_id"] == song_id
    assert probe.state["revisions"] == {"library": 1 if availability == "AVAILABLE" else 2, "playlist": 3}
    manual = [i for i in probe.state["queue"]["items"] if i["source"] == "MANUAL"]
    assert [i["song_id"] for i in manual] == [song_id, "a", song_id]
    assert [i["position"] for i in manual] == [-1, -2, 0]
    assert len({i["queue_item_id"] for i in manual}) == 3
    assert run(playlists.list_song_ids(playlist.playlist_id)) == [song_id]
    assert run(playlists.list_favorite_song_ids()) == [song_id]
    assert client.get("/api/history").json() == history
    assert server_snapshot(playback) == before
    assert run(library.list_songs()) == songs
    assert run(playlists.revision_content()) == membership
    assert player._queue == port_queue and player._outputs == port_outputs
    assert run(terminals.get_by_key("recover-seek")) == terminal
    assert coordinator.marker() == marker and not coordinator._subscriptions
    replay = mutate(client, "POST", "/api/playback/seek", {"seconds": 17}, key="recover-seek")
    assert replay.json() == terminal_response.json()
    assert server_snapshot(playback) == before and coordinator.marker() == marker


def test_overflow_reconnect_captures_last_commit_without_incremental_replay(state_client, monkeypatch):
    """A reconnect that needs missed events or an old cursor cannot recover the last commit."""
    _, state, playback, _, _, coordinator, _, _ = state_client
    monkeypatch.setattr(coordinator, "_queue_capacity", 1)
    manager = connection_manager(state, coordinator)

    async def scenario():
        baseline = asyncio.all_tasks()
        slow = ControlledSocket()
        task = asyncio.create_task(manager.connect(slow))
        try:
            await asyncio.wait_for(slow.initial_started.wait(), 1)
            await playback.pause()
            await playback.seek(19)
            await asyncio.wait_for(task, 1)
            assert slow.close_codes == [1013] and slow.frames.empty()
            committed = await playback.queue_manager.get_playback_state()
            queue = await playback.queue_manager.get_snapshot()
            history = await playback.history_service.get_availability()
            marker = coordinator.marker()
            recovered = ControlledSocket()
            recovered.release_initial.set()
            reconnect = asyncio.create_task(manager.connect(recovered))
            try:
                frame = await asyncio.wait_for(recovered.frames.get(), 1)
                assert frame["type"] == "snapshot"
                assert frame["sequence"] == marker.sequence
                assert frame["state"]["playback"] == committed.model_dump(mode="json")
                assert frame["state"]["playback"]["position_seconds"] == 19
                assert frame["state"]["queue"] == queue.model_dump(mode="json")
                assert frame["state"]["history"] == history.model_dump(mode="json")
                assert recovered.frames.empty(), "reconnect replayed missed invalidations"
                assert coordinator.marker() == marker
            finally:
                recovered.incoming.put_nowait({"type": "websocket.disconnect"})
                await asyncio.wait_for(reconnect, 1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        assert not manager._connections and not coordinator._subscriptions
        assert asyncio.all_tasks() == baseline

    run(scenario())
