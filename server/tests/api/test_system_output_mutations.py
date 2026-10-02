"""SYS-WRITE-001: real output mutation HTTP boundary."""

import asyncio

import pytest

from server.app.main import app
from server.app.player.models import OutputInfo
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.tests.invariants.test_output_enable import enable_manager
from server.tests.support.playback import mutate, real_client

__all__ = ["real_client"]


@pytest.fixture
def output_api(real_client, monkeypatch):
    client, _, player, service = real_client
    player._outputs = [
        OutputInfo(id=37, name="DAC", plugin="alsa", enabled=False),
        OutputInfo(id=0, name="stream", plugin="httpd", enabled=True),
    ]
    events, calls = [], []
    check = player._check

    def record(command):
        calls.append(command)
        return check(command)

    monkeypatch.setattr(player, "_check", record)
    path = service.queue_manager.queue_repository.path

    class Publisher:
        async def publish(self, event):
            # Fresh task reads committed terminal without inheriting an active UoW.
            terminal = await asyncio.wait_for(asyncio.create_task(
                IdempotencyRepository(path).get_by_key("output-key"),
            ), 3)
            assert terminal is not None
            events.append(event)

    manager = enable_manager(service, player, event_publisher=Publisher(), monotonic_clock=lambda: 0.0)
    monkeypatch.setattr(app.state, "output_manager", manager)
    yield client, player, service, manager, calls, events, path


def output_put(client, enabled=True, mode="NAS_DAC", key="output-key"):
    return mutate(client, "PUT", "/api/system/output", {"mode": mode, "enabled": enabled}, key=key)


def test_output_put_returns_confirmed_receipt(output_api):
    client, player, _, _, calls, events, path = output_api
    response = output_put(client)
    assert response.status_code == 200, response.text
    assert response.json()["states"][0]["status"] == "ACTIVE"
    assert response.json()["last_request"]["status"] == "SUCCEEDED"
    assert asyncio.run(player.outputs())[0].enabled is True
    assert calls.count("set_output_enabled") == 1
    assert len(events) == 1
    terminal = asyncio.run(IdempotencyRepository(path).get_by_key("output-key"))
    assert terminal.response_body == response.text


@pytest.mark.parametrize("body", [
    {}, {"mode": "NAS_DAC"}, {"enabled": True},
    {"mode": "invalid", "enabled": True},
    {"mode": "NAS_DAC", "enabled": "false"},
    {"mode": "NAS_DAC", "enabled": 1},
    {"mode": "NAS_DAC", "enabled": None},
])
def test_invalid_output_request_has_no_side_effect_or_terminal(output_api, body):
    client, _, _, _, calls, events, path = output_api
    response = mutate(client, "PUT", "/api/system/output", body, key="invalid")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert calls == events == []
    assert asyncio.run(IdempotencyRepository(path).get_by_key("invalid")) is None


def test_missing_key_and_key_conflicts_preserve_output(output_api):
    client, _, _, _, calls, events, path = output_api
    missing = client.put("/api/system/output", json={"mode": "NAS_DAC", "enabled": True})
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert calls == events == []
    assert output_put(client).status_code == 200
    before_calls, before_events = list(calls), list(events)
    conflict = output_put(client, False)
    scope = mutate(client, "POST", "/api/playback/stop", key="output-key")
    assert conflict.status_code == scope.status_code == 409
    assert conflict.json()["error"]["code"] == scope.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert calls == before_calls
    assert events == before_events
    assert asyncio.run(IdempotencyRepository(path).get_by_key("output-key")).response_status == 200


@pytest.mark.parametrize("enabled", [True, False])
def test_reserved_mode_is_a_typed_http_failure(output_api, enabled):
    client, _, _, _, calls, events, path = output_api
    response = output_put(client, enabled, "CLIENT_STREAM")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OUTPUT_MODE_UNSUPPORTED"
    assert response.json()["error"]["message"]
    assert calls == events == []
    assert asyncio.run(IdempotencyRepository(path).get_by_key("output-key")) is None
