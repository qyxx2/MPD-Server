from __future__ import annotations

from server.app.player.models import PlayerState
from server.tests.support.playback import run, start


def test_unclassified_external_stop_does_not_fabricate_history(real_client):
    """P §8.8 / PB-HISTORY-001: status alone cannot prove user Stop intent."""
    client, _, player, service = real_client
    start(client)
    queue = run(service.queue_manager.get_snapshot())
    state = run(service.queue_manager.get_playback_state())
    history = run(service.history_service.get_availability())
    assert state is not None and state.autoplay_enabled
    assert history.active_event is not None and history.session_id is not None
    assert run(service.history_service.list_history()) == []

    # External control: no PlaybackService.stop or user Stop request exists.
    # The service receives only transport status, with no causal evidence.
    run(player.stop())
    assert run(player.status()).state == PlayerState.STOPPED
    run(service.reconcile_external_status())

    after = run(service.queue_manager.get_playback_state())
    assert after is not None
    actual = {
        "events": run(service.history_service.list_history()),
        "history": run(service.history_service.get_availability()),
        "autoplay_enabled": after.autoplay_enabled,
        "context_id": after.playback_context_id,
        "queue": run(service.queue_manager.get_snapshot()),
    }
    assert actual == {
        "events": [],
        "history": history,
        "autoplay_enabled": True,
        "context_id": state.playback_context_id,
        "queue": queue,
    }
