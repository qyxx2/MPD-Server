from __future__ import annotations

import pytest

from server.app.api.realtime_schemas import PlaybackObservationResponse
from server.app.main import app
from server.app.services.history_service import HistoryService
from server.app.services.playback_service import PlaybackService
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.app.services.state_service import StateService
from server.tests.api.test_realtime_state import state_client
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_realtime_recovery import without_capture_time
from server.tests.support.playback import real_client, run

__all__ = ["real_client", "state_client"]


def test_additive_observation_fields_default_for_old_public_constructors():
    response = PlaybackObservationResponse.model_validate({
        "actual_state": None,
        "matches_current": None,
        "position_seconds": None,
        "duration_seconds": None,
        "observed_at": None,
        "freshness": "unknown",
        "reconciliation_required": False,
        "error_code": None,
        "error_message": None,
    })
    assert response.actual_current is None
    assert response.actual_freshness == "unknown"
    assert response.bound_queue_item_id is None
    assert response.sync_status == "UNBOUND"


@pytest.mark.parametrize(
    "recovery",
    ["refresh", "new-browser", "ws-reconnect", "service-restart", "mpd-restart"],
)
def test_fresh_browser_reconnect_and_restart_show_truthful_full_state(
    state_client, monkeypatch, recovery,
):
    """Every fresh consumer gets the same actual/business split from one full model."""
    client, state, playback, player, library, coordinator, _, output = state_client
    run(playback.observe())
    before = server_snapshot(playback)
    old_epoch = coordinator.marker().epoch

    if recovery == "service-restart":
        coordinator = RealtimeCoordinator(library.path)
        history = HistoryService(
            playback.queue_manager.queue_repository,
            playback.history_service.history_repository,
        )
        playback = PlaybackService(
            queue_manager=playback.queue_manager,
            history_service=history,
            autoplay=playback.autoplay,
            player=player,
            library_repository=library,
            coordinator=coordinator,
        )
        run(playback.observe())
        state = StateService(
            coordinator=coordinator,
            queue_manager=playback.queue_manager,
            history_service=history,
            library_service=app.state.library_service,
            playback_service=playback,
            output_snapshot=output.get_cached_state,
            output_observation=output.get_observation,
        )
    elif recovery == "mpd-restart":
        player.reconnect()
        run(playback.observe())

    monkeypatch.setattr(app.state, "playback_service", playback)
    monkeypatch.setattr(app.state, "state_service", state)
    monkeypatch.setattr(app.state, "realtime_coordinator", coordinator)

    if recovery == "ws-reconnect":
        with client.websocket_connect("/api/realtime") as first_socket:
            first_socket.receive_json()

    with client.websocket_connect("/api/realtime") as socket:
        frame = socket.receive_json()
    response = client.get("/api/state")
    assert response.status_code == 200, response.text
    get_state = response.json()
    ws_state = frame["state"]

    assert frame["type"] == "snapshot" and frame["protocol_version"] == 1
    assert without_capture_time(ws_state) == without_capture_time(get_state)
    assert ws_state["current_song"]["song_id"] == "a"
    assert ws_state["playback_observation"]["actual_current"]["uri"] == "a.flac"
    assert ws_state["playback_observation"]["actual_freshness"] == "fresh"
    expected_position = None if recovery in {"service-restart", "mpd-restart"} else 0
    assert ws_state["playback_observation"]["position_seconds"] == expected_position

    if recovery == "service-restart":
        assert coordinator.marker().epoch != old_epoch
        assert ws_state["history"]["active_event"] is None
        assert ws_state["history"]["session_id"] is None
        assert ws_state["playback_observation"]["bound_queue_item_id"] is None
        assert ws_state["playback_observation"]["sync_status"] == "UNBOUND"
        assert server_snapshot(playback)[0:2] == before[0:2]
    elif recovery == "mpd-restart":
        assert coordinator.marker().epoch == old_epoch
        assert ws_state["playback_observation"]["bound_queue_item_id"] is None
        assert ws_state["playback_observation"]["sync_status"] != "CONFIRMED"
    else:
        assert ws_state["playback_observation"]["bound_queue_item_id"] is not None
        assert ws_state["playback_observation"]["sync_status"] == "CONFIRMED"
        assert server_snapshot(playback) == before
