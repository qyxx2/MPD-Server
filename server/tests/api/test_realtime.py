from __future__ import annotations

import pytest
from starlette.websockets import WebSocketDisconnect

from server.app.main import app
from server.tests.api.test_realtime_state import state_client
from server.tests.invariants.assertions import server_snapshot
from server.tests.support.playback import mutate, real_client, run

__all__ = ["real_client", "state_client"]


@pytest.fixture
def ws_state_client(state_client, monkeypatch):
    # The legacy fixture replaces the aggregate and producers together.
    monkeypatch.setattr(app.state, "realtime_coordinator", state_client[5])
    return state_client


def test_realtime_route_sends_full_public_snapshot_then_committed_invalidation(ws_state_client):
    client, _, playback, _, _, coordinator, _, _ = ws_state_client
    before = server_snapshot(playback)
    with client.websocket_connect("/api/realtime") as socket:
        first = socket.receive_json()
        assert first["type"] == "snapshot" and first["protocol_version"] == 1
        state = first["state"]
        current = client.get("/api/state").json()
        state.pop("captured_at")
        current.pop("captured_at")
        assert state == current
        assert first["epoch"] == state["epoch"] == coordinator.marker().epoch
        assert first["sequence"] == state["sequence"]
        assert state["current_song"] == client.get("/api/library/songs/a").json()
        assert state["queue"] == before[0].model_dump(mode="json")
        assert [i["song_id"] for i in state["queue"]["items"] if i["source"] == "MANUAL"] == [
            "a", "a", "b",
        ]
        assert any(i["source"] == "AUTOPLAY" for i in state["queue"]["items"])
        assert server_snapshot(playback) == before
        result = mutate(client, "POST", "/api/playback/pause", key="ws-pause")
        assert result.status_code == 200, result.text
        live = socket.receive_json()
        assert live["type"] == "invalidate" and live["protocol_version"] == 1
        assert live["epoch"] == first["epoch"]
        assert live["sequence"] > first["sequence"]
        assert live["revisions"] == {"library": 0, "playlist": 0}
        assert live["domains"] == ["playback"]
        assert client.get("/api/state").json()["playback"]["state"] == "PAUSED"
    assert not coordinator._subscriptions
    assert server_snapshot(playback)[2:] == before[2:]


def test_initial_local_read_failure_closes_1011_and_unsubscribes(ws_state_client, monkeypatch):
    client, _, playback, _, _, coordinator, _, _ = ws_state_client
    before = server_snapshot(playback)

    async def failed():
        raise RuntimeError("local capture unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(playback.queue_manager, "get_snapshot", failed)
        with client.websocket_connect("/api/realtime") as socket:
            with pytest.raises(WebSocketDisconnect) as failure:
                socket.receive_json()
            assert failure.value.code == 1011
    assert not coordinator._subscriptions
    assert server_snapshot(playback) == before
    with client.websocket_connect("/api/realtime") as socket:
        assert socket.receive_json()["type"] == "snapshot"
    assert not coordinator._subscriptions


def test_root_coordinator_is_shared_by_websocket_and_real_playlist_producer(real_client):
    client = real_client[0]
    coordinator = app.state.realtime_coordinator
    with client.websocket_connect("/api/realtime") as socket:
        first = socket.receive_json()
        result = mutate(client, "POST", "/api/playlists", {"name": "ws playlist"}, key="ws-pl")
        assert result.status_code == 201, result.text
        live = socket.receive_json()
        assert live["domains"] == ["playlist"]
        assert live["sequence"] > first["sequence"]
        assert live["revisions"] == {"library": 0, "playlist": 1}
        # The existing post-commit domain callback may reassert invalidation
        # with the latest marker; notifications do not promise exactly once.
        committed = coordinator.marker()
        while live["sequence"] < committed.sequence:
            newer = socket.receive_json()
            assert newer["sequence"] > live["sequence"]
            assert newer["revisions"] == live["revisions"]
            live = newer
        replay = mutate(client, "POST", "/api/playlists", {"name": "ws playlist"}, key="ws-pl")
        assert replay.json() == result.json()
        assert coordinator.marker() == committed
        playlists = run(app.state.playlist_service.list_playlists())
        assert [(p.playlist_id, p.name) for p in playlists] == [
            (result.json()["playlist_id"], "ws playlist"),
        ]
    assert not coordinator._subscriptions


def test_concurrent_gets_never_replace_newer_connection_waterline(ws_state_client, monkeypatch):
    """A late older response, same sequence or pre-invalidation cut must not be applied."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    from copy import deepcopy

    from server.tests.invariants.test_realtime_recovery import (
        ProtocolProbe,
        without_capture_time,
    )

    client, state, playback, _, _, coordinator, _, _ = ws_state_client
    before = server_snapshot(playback)
    probe = ProtocolProbe()
    captured, release = asyncio.Event(), asyncio.Event()
    original = state.get_full_snapshot
    hold_next = True

    async def delayed_capture():
        nonlocal hold_next
        hold = hold_next
        hold_next = False
        result = await original()
        if hold:
            captured.set()
            await release.wait()
        return result

    with client.websocket_connect("/api/realtime") as socket:
        generation = probe.connect(socket.receive_json())
        monkeypatch.setattr(state, "get_full_snapshot", delayed_capture)
        with ThreadPoolExecutor(max_workers=1) as workers:
            pending = workers.submit(client.get, "/api/state")
            try:
                client.portal.call(asyncio.wait_for, captured.wait(), 1)
                response = mutate(client, "POST", "/api/playback/pause", key="recovery-race")
                assert response.status_code == 200, response.text
                live = socket.receive_json()
                probe.invalidate(live)
                # The first GET is captured, but not returned; the second crosses
                # the later commit and returns first, without holding any DB lock.
                newest = client.get("/api/state")
                assert newest.status_code == 200, newest.text
                assert newest.json()["sequence"] == coordinator.marker().sequence
                assert probe.apply(newest.json(), generation)
                assert probe.state["playback"]["state"] == "PAUSED"
                accepted = deepcopy(probe.state)
            finally:
                client.portal.call(release.set)
            older = pending.result(timeout=2)
        assert older.status_code == 200, older.text
        assert older.json()["playback"]["state"] == "PLAYING"
        assert older.json()["sequence"] < live["sequence"]
        assert not probe.apply(older.json(), generation)
        assert not probe.apply(newest.json(), generation)
        assert probe.state == accepted
        # If the newest GET has not returned yet, a cut below the known
        # invalidation waterline also cannot pretend recovery succeeded.
        another_probe = ProtocolProbe()
        another_generation = another_probe.connect({
            "type": "snapshot", "protocol_version": 1,
            "epoch": older.json()["epoch"], "sequence": older.json()["sequence"],
            "state": older.json(),
        })
        another_probe.invalidate(live)
        assert not another_probe.apply(older.json(), another_generation)
        assert another_probe.apply(newest.json(), another_generation)
        assert without_capture_time(another_probe.state) == without_capture_time(probe.state)
    assert not coordinator._subscriptions
    after = server_snapshot(playback)
    assert after[0] == before[0] and after[2:] == before[2:]
    assert after[1].state == "PAUSED" and after[1].song_id == before[1].song_id
    assert after[1].playback_context_id == before[1].playback_context_id


@pytest.mark.parametrize("active", [False, True])
def test_real_lifespan_restart_replaces_epoch_and_discards_late_old_get(
    tmp_path, monkeypatch, media_fixture_dir, active,
):
    """Reusing an epoch, runtime sample or old request after restart corrupts the new baseline."""
    from copy import deepcopy
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from server.app.models.output import OutputMode
    from server.app.player.capabilities import MPDCapabilities
    from server.app.player.mock_mpd import MockMPD
    from server.app.player.models import OutputInfo
    from server.tests.invariants.test_realtime_observation import FakeClock
    from server.tests.invariants.test_realtime_recovery import (
        ProtocolProbe,
        without_capture_time,
    )

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "restart.db"))
    capabilities = replace(
        MPDCapabilities.from_commands({"outputs", "enableoutput", "disableoutput", "status",
                                       "currentsong", "playlistinfo"}),
        verified_operations=frozenset({"queue_entries", "set_output_enabled"}),
    )
    monkeypatch.setattr(app.state, "mpd_capabilities", capabilities, raising=False)
    probe = ProtocolProbe()
    with TestClient(app) as client:
        playback = app.state.playback_service
        player = MockMPD([str(media_fixture_dir / "metadata.flac")])
        player._outputs = [OutputInfo(id=1, name="DAC", plugin="alsa", enabled=True)]
        playback.player = app.state.output_manager.player = player
        if active:
            result = run(app.state.library_scanner.scan_paths([media_fixture_dir / "metadata.flac"]))
            song_id = result.added_song_ids[0]
            run(playback.start_track(song_id))
            run(playback.start_track(song_id))
            run(playback.seek(23))
            run(playback.observe())
            run(app.state.output_manager.set_enabled(OutputMode.NAS_DAC, False))
            playlist = run(app.state.playlist_service.create_playlist("survives restart"))
            run(app.state.playlist_service.add_song(playlist.playlist_id, song_id))
            run(app.state.playlist_service.set_favorite(song_id, True))
        with client.websocket_connect("/api/realtime") as socket:
            old_generation = probe.connect(socket.receive_json())
            old_get = client.get("/api/state").json()
        old_coordinator = app.state.realtime_coordinator
        queue = run(app.state.queue_manager.get_snapshot())
        playback_state = run(app.state.queue_manager.get_playback_state())
        history = client.get("/api/history").json()
        membership = run(app.state.playlist_service.revision_content())
        songs = run(app.state.library_service.list_songs())
        old_epoch = probe.state["epoch"]
    assert not old_coordinator._subscriptions

    with TestClient(app) as client:
        coordinator = app.state.realtime_coordinator
        # With no sample, OutputManager dates its unknown representation at
        # read time. Hold that clock, not its data, for the WS/HTTP comparison.
        monkeypatch.setattr(app.state.output_manager, "_clock", FakeClock())
        with client.websocket_connect("/api/realtime") as socket:
            generation = probe.connect(socket.receive_json())
            new = deepcopy(probe.state)
            assert new["epoch"] != old_epoch
            assert new["sequence"] == 0 and new["revisions"] == {"library": 0, "playlist": 0}
            assert new["queue"] == queue.model_dump(mode="json")
            assert new["playback"] == (playback_state.model_dump(mode="json") if active else None)
            assert new["history"] == {
                "has_entries": active, "active_event": None, "session_id": None,
            }
            assert new["playback_observation"]["freshness"] == "unknown"
            assert new["playback_observation"]["position_seconds"] is None
            assert new["playback_observation"]["matches_current"] is None
            assert new["output_observation"]["freshness"] == "unknown"
            assert new["output"]["last_request"] is None
            if active:
                assert old_get["sequence"] > new["sequence"]
                assert old_get["playback_observation"]["position_seconds"] == 23
                assert new["current_song"] == client.get(f"/api/library/songs/{song_id}").json()
            else:
                assert new["current_song"] is None and new["queue"]["items"] == []
            assert not probe.apply(old_get, old_generation)
            assert not probe.apply(old_get, generation), "old epoch must not replace new connection"
            assert probe.state == new
            current = client.get("/api/state")
            assert current.status_code == 200, current.text
            assert without_capture_time(current.json()) == without_capture_time(new)
            assert not probe.apply(current.json(), generation)
        assert not coordinator._subscriptions
        assert run(app.state.queue_manager.get_snapshot()) == queue
        assert run(app.state.queue_manager.get_playback_state()) == playback_state
        assert run(app.state.playlist_service.revision_content()) == membership
        assert run(app.state.library_service.list_songs()) == songs
        assert client.get("/api/history").json() == history
        assert coordinator.marker().sequence == 0


def test_failed_reconnect_keeps_old_view_until_fresh_full_retry(ws_state_client, monkeypatch):
    """A failed required read must not become a successful cached or partial reconnect."""
    from copy import deepcopy

    from server.tests.invariants.test_realtime_recovery import (
        ProtocolProbe,
        without_capture_time,
    )

    client, _, playback, _, _, coordinator, _, _ = ws_state_client
    probe = ProtocolProbe()
    with client.websocket_connect("/api/realtime") as socket:
        probe.connect(socket.receive_json())
    old = deepcopy(probe.state)
    response = mutate(client, "POST", "/api/playback/pause", key="failed-reconnect-pause")
    assert response.status_code == 200, response.text
    before = server_snapshot(playback)
    marker = coordinator.marker()
    terminal = run(app.state.idempotency_service._repository.get_by_key("failed-reconnect-pause"))
    assert terminal is not None

    async def failed():
        raise RuntimeError("required local snapshot domain unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(playback.history_service, "get_availability", failed)
        with client.websocket_connect("/api/realtime") as socket:
            with pytest.raises(WebSocketDisconnect) as failure:
                socket.receive_json()
            assert failure.value.code == 1011
        http = client.get("/api/state")
        assert http.status_code == 503 and set(http.json()) == {"error"}
        assert http.json()["error"]["code"] == "STATE_SNAPSHOT_UNAVAILABLE"
    assert probe.state == old and not coordinator._subscriptions
    assert coordinator.marker() == marker and server_snapshot(playback) == before
    with client.websocket_connect("/api/realtime") as socket:
        probe.connect(socket.receive_json())
        assert probe.state["sequence"] == marker.sequence > old["sequence"]
        assert probe.state["playback"]["state"] == "PAUSED"
        assert without_capture_time(probe.state) == without_capture_time(client.get("/api/state").json())
    assert coordinator.marker() == marker and server_snapshot(playback) == before
    assert run(app.state.idempotency_service._repository.get_by_key("failed-reconnect-pause")) == terminal
    assert not coordinator._subscriptions
