from __future__ import annotations

import pytest

from server.app.player.models import PlayerState
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.tests.invariants.assertions import (
    assert_execution_relationship,
    server_snapshot,
)
from server.tests.support.playback import mutate, run, start


@pytest.mark.parametrize("reported", [PlayerState.PLAYING, PlayerState.PAUSED])
def test_unconfirmed_stop_preserves_all_authorities(real_client, monkeypatch, reported):
    client, _, player, service = real_client
    start(client)
    queue = service.queue_manager
    history = service.history_service
    before = run(queue.queue_repository.get_snapshot())
    state = run(queue.get_playback_state())
    active, session = history.active_event, history.session_id
    actual_stop, actual_status = player.stop, player.status

    async def ineffective_stop():
        pass

    async def non_stopped_status():
        return (await actual_status()).model_copy(update={"state": reported})

    monkeypatch.setattr(player, "stop", ineffective_stop)
    monkeypatch.setattr(player, "status", non_stopped_status)
    response = mutate(client, "POST", "/api/playback/stop", key="unconfirmed-stop")
    records = IdempotencyRepository(queue.queue_repository.path)
    # Collect every relationship violation so RED demonstrates the whole defect.
    observed = {
        "http": response.status_code,
        "snapshot": run(queue.queue_repository.get_snapshot()) == before,
        "state": run(queue.get_playback_state()) == state,
        "history": run(history.list_history()) == [],
        "active": history.active_event == active,
        "session": history.session_id == session,
        "no_terminal": run(records.get_by_key("unconfirmed-stop")) is None,
    }
    assert observed == dict.fromkeys(observed, True) | {"http": 502}
    assert response.json()["error"]["code"] == "PLAYBACK_RECONCILIATION_FAILED"
    monkeypatch.setattr(player, "stop", actual_stop)
    monkeypatch.setattr(player, "status", actual_status)
    retry = mutate(client, "POST", "/api/playback/stop", key="unconfirmed-stop")
    assert retry.status_code == 200, retry.text
    assert retry.json()["state"] == "STOPPED"
    assert run(player.status()).state == PlayerState.STOPPED
    assert [(e.song_id, e.reason) for e in run(history.list_history())] == [
        ("a", "STOP")
    ]
    assert history.active_event is None and history.session_id is None
    events = run(history.list_history())
    replay = mutate(client, "POST", "/api/playback/stop", key="unconfirmed-stop")
    assert replay.json() == retry.json()
    assert run(history.list_history()) == events


@pytest.mark.parametrize("failure", ["command", "unavailable", "status"])
def test_stop_transport_failure_rolls_back_and_retries(real_client, failure):
    client, _, player, service = real_client
    start(client)
    before = server_snapshot(service)
    if failure == "unavailable":
        player.disconnect()
    else:
        player.fail_next("stop" if failure == "command" else "status")
    response = mutate(client, "POST", "/api/playback/stop", key="stop-failure")
    assert response.status_code == (503 if failure == "unavailable" else 502)
    assert response.json()["error"]["code"] == (
        "PLAYER_UNAVAILABLE" if failure == "unavailable" else "PLAYER_COMMAND_FAILED"
    )
    assert server_snapshot(service) == before
    records = IdempotencyRepository(service.queue_manager.queue_repository.path)
    assert run(records.get_by_key("stop-failure")) is None
    player.reconnect()
    retry = mutate(client, "POST", "/api/playback/stop", key="stop-failure")
    assert retry.status_code == 200, retry.text
    assert_execution_relationship(service, player)
    assert [
        (e.song_id, e.reason) for e in run(service.history_service.list_history())
    ] == [("a", "STOP")]
    final = server_snapshot(service)
    assert (
        mutate(client, "POST", "/api/playback/stop", key="stop-failure").json()
        == retry.json()
    )
    assert server_snapshot(service) == final
