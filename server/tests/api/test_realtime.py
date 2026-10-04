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
