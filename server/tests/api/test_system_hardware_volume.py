"""SYS-HARDWARE-VOLUME-001: REST state and confirmed hardware Mixer control."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from server.app.main import app
from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.models import OutputInfo
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.services.hardware_volume_manager import HardwareVolumeManager
from server.tests.support.playback import mutate, real_client

__all__ = ["real_client"]


def _capabilities() -> MPDCapabilities:
    return replace(
        MPDCapabilities.from_commands({
            "status", "currentsong", "setvol", "outputs", "playlistinfo",
        }),
        verified_operations=frozenset({"queue_entries"}),
    )


def _manager(service, player, *, enabled=True) -> HardwareVolumeManager:
    capabilities = _capabilities()
    return HardwareVolumeManager(
        player=VerifiedPlayerPort(player, capabilities),
        capabilities=capabilities,
        enabled=enabled,
        selector=lambda candidates: candidates[0],
        operation_runner=service.run_output_operation,
        coordinator=app.state.realtime_coordinator,
    )


@pytest.fixture
def volume_api(real_client, monkeypatch):
    client, _, player, service = real_client
    player._outputs = [OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=True)]
    player._volume = 47
    manager = _manager(service, player)
    monkeypatch.setattr(app.state, "hardware_volume_manager", manager)

    calls = []
    original_check = player._check

    def record(command):
        calls.append(command)
        return original_check(command)

    monkeypatch.setattr(player, "_check", record)
    yield client, player, manager, calls, service


def volume_put(client, volume_percent, *, key="hardware-volume-key"):
    return mutate(
        client,
        "PUT",
        "/api/system/hardware-volume",
        {"volumePercent": volume_percent},
        key=key,
    )


def test_get_returns_fresh_state_with_complete_camel_case_snapshot(volume_api):
    client, _, _, calls, _ = volume_api

    response = client.get("/api/system/hardware-volume")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"]["status"] == "AVAILABLE"
    assert payload["state"]["volumePercent"] == 47
    assert payload["state"]["outputName"] == "USB DAC"
    assert payload["state"]["outputPlugin"] == "alsa"
    assert payload["state"]["outputEnabled"] is True
    assert payload["state"]["controlSource"] == "MPD_HARDWARE_MIXER"
    assert payload["state"]["stale"] is False
    assert payload["observation"]["freshness"] == "fresh"
    assert payload["observation"]["observedAt"] is not None
    assert payload["lastRequest"] is None
    assert "last_request" not in payload
    assert "volume_percent" not in payload["state"]
    assert calls.count("status") == 1
    assert calls.count("outputs") == 1


def test_get_returns_unknown_without_fabricating_volume_when_target_is_missing(volume_api):
    client, player, _, _, _ = volume_api
    player._outputs = []

    response = client.get("/api/system/hardware-volume")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["status"] == "UNAVAILABLE"
    assert payload["state"]["volumePercent"] is None
    assert payload["state"]["stale"] is False
    assert payload["state"]["errorCode"] == "HARDWARE_VOLUME_UNAVAILABLE"
    assert payload["observation"]["freshness"] == "unknown"
    assert payload["observation"]["errorCode"] == "HARDWARE_VOLUME_UNAVAILABLE"


def test_get_preserves_last_confirmed_volume_as_stale_after_player_disconnect(volume_api):
    client, player, manager, _, _ = volume_api
    asyncio.run(manager.get_state(read_timeout=5))
    player.disconnect()

    response = client.get("/api/system/hardware-volume")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["status"] == "UNAVAILABLE"
    assert payload["state"]["volumePercent"] == 47
    assert payload["state"]["stale"] is True
    assert payload["state"]["errorCode"] == "PLAYER_UNAVAILABLE"
    assert payload["observation"]["freshness"] == "stale"
    assert payload["observation"]["errorCode"] == "PLAYER_UNAVAILABLE"


def test_get_maps_missing_manager_to_503_error_envelope(volume_api, monkeypatch):
    client, _, _, _, _ = volume_api
    monkeypatch.setattr(app.state, "hardware_volume_manager", None)

    response = client.get("/api/system/hardware-volume")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "HARDWARE_VOLUME_UNAVAILABLE"


def test_get_reports_disabled_capability_without_touching_mpd(volume_api, monkeypatch):
    client, player, _, calls, service = volume_api
    disabled = _manager(service, player, enabled=False)
    monkeypatch.setattr(app.state, "hardware_volume_manager", disabled)
    calls.clear()

    response = client.get("/api/system/hardware-volume")

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["status"] == "UNSUPPORTED"
    assert payload["state"]["volumePercent"] is None
    assert payload["state"]["errorCode"] == "HARDWARE_VOLUME_NOT_CONFIGURED"
    assert payload["observation"]["freshness"] == "unknown"
    assert payload["observation"]["errorCode"] == "HARDWARE_VOLUME_NOT_CONFIGURED"
    assert calls == []


@pytest.mark.parametrize("invalid", [True, False, 1.5, "47", -1, 101, None])
def test_put_rejects_non_strict_or_out_of_range_volume_without_setvol(volume_api, invalid):
    client, _, _, calls, _ = volume_api

    response = volume_put(client, invalid, key=f"invalid-{invalid!r}")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "set_volume" not in calls


def test_put_rejects_unknown_fields_without_setvol(volume_api):
    client, _, _, calls, _ = volume_api

    response = mutate(
        client,
        "PUT",
        "/api/system/hardware-volume",
        {"volumePercent": 61, "volume": 61},
        key="unknown-field",
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "set_volume" not in calls


def test_put_requires_global_idempotency_key_before_touching_mpd(volume_api):
    client, _, _, calls, _ = volume_api

    response = client.put("/api/system/hardware-volume", json={"volumePercent": 61})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    assert "set_volume" not in calls


def test_put_returns_confirmed_readback_and_replay_does_not_repeat_setvol(volume_api):
    client, player, _, calls, service = volume_api
    response = volume_put(client, 63)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["state"]["status"] == "AVAILABLE"
    assert payload["state"]["volumePercent"] == 63
    assert payload["state"]["stale"] is False
    assert payload["observation"]["freshness"] == "fresh"
    assert payload["lastRequest"]["requestedPercent"] == 63
    assert payload["lastRequest"]["status"] == "SUCCEEDED"
    assert payload["lastRequest"]["errorCode"] is None
    assert player._volume == 63
    assert calls.count("set_volume") == 1

    path = service.queue_manager.queue_repository.path
    terminal = asyncio.run(IdempotencyRepository(path).get_by_key("hardware-volume-key"))
    assert terminal is not None
    assert terminal.response_status == 200
    assert terminal.response_body == response.text

    replay = volume_put(client, 63)
    assert replay.status_code == 200
    assert replay.text == response.text
    assert calls.count("set_volume") == 1

    conflict = volume_put(client, 64)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert calls.count("set_volume") == 1
    assert player._volume == 63


def test_put_maps_mpd_status_command_failure_to_hardware_unavailable(volume_api):
    client, player, _, calls, _ = volume_api
    player.fail_next("status", "MPD status command failed")

    response = volume_put(client, 64)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "HARDWARE_VOLUME_UNAVAILABLE"
    assert "set_volume" not in calls


def test_put_maps_mpd_setvol_rejection_to_502(volume_api):
    client, player, _, calls, _ = volume_api
    player.fail_next("set_volume", "MPD rejected setvol")

    response = volume_put(client, 64)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "HARDWARE_VOLUME_WRITE_FAILED"
    assert "set_volume" in calls
    assert player._volume == 47


def test_put_maps_missing_hardware_target_to_503_without_setvol(volume_api):
    client, player, _, calls, _ = volume_api
    player._outputs = []

    response = volume_put(client, 64)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "HARDWARE_VOLUME_UNAVAILABLE"
    assert "set_volume" not in calls


def test_put_maps_ambiguous_alsa_target_to_400_without_setvol(volume_api):
    client, player, manager, calls, _ = volume_api
    player._outputs = [
        OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=True),
        OutputInfo(id=38, name="Second DAC", plugin="alsa", enabled=True),
    ]
    manager.selector = None

    response = volume_put(client, 64)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "HARDWARE_VOLUME_OUTPUT_AMBIGUOUS"
    assert "set_volume" not in calls


def test_put_maps_disabled_hardware_volume_capability_to_400_without_mpd_side_effects(
    volume_api, monkeypatch,
):
    client, player, _, calls, service = volume_api
    monkeypatch.setattr(
        app.state, "hardware_volume_manager", _manager(service, player, enabled=False),
    )
    calls.clear()

    response = volume_put(client, 64)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "HARDWARE_VOLUME_NOT_CONFIGURED"
    assert calls == []


def test_put_maps_disconnected_player_to_503(volume_api):
    client, player, _, calls, _ = volume_api
    player.disconnect()

    response = volume_put(client, 64)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PLAYER_UNAVAILABLE"
    assert "set_volume" not in calls


def test_put_maps_readback_mismatch_to_502_and_never_reports_success(volume_api, monkeypatch):
    client, player, _, calls, _ = volume_api

    async def acknowledge_without_changing_mixer(_volume):
        calls.append("set_volume")

    monkeypatch.setattr(player, "set_volume", acknowledge_without_changing_mixer)

    response = volume_put(client, 64)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "HARDWARE_VOLUME_RECONCILIATION_FAILED"
    assert calls.count("set_volume") == 1
    assert player._volume == 47


def test_openapi_declares_strict_camel_case_hardware_volume_contract(volume_api):
    client, _, _, _, _ = volume_api

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schemas = response.json()["components"]["schemas"]
    request_schema = schemas["HardwareVolumeSetRequest"]
    assert set(request_schema["properties"]) == {"volumePercent"}
    assert request_schema["additionalProperties"] is False
    assert request_schema["required"] == ["volumePercent"]
    assert request_schema["properties"]["volumePercent"]["type"] == "integer"
    assert request_schema["properties"]["volumePercent"]["minimum"] == 0
    assert request_schema["properties"]["volumePercent"]["maximum"] == 100
    get_response_ref = response.json()["paths"]["/api/system/hardware-volume"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    result_schema = schemas[get_response_ref.rsplit("/", 1)[-1]]
    assert set(result_schema["properties"]) == {"state", "observation", "lastRequest"}
    state_ref = result_schema["properties"]["state"]["$ref"]
    state_schema = schemas[state_ref.rsplit("/", 1)[-1]]
    assert set(state_schema["properties"]) == {
        "status", "volumePercent", "outputName", "outputPlugin", "outputEnabled",
        "controlSource", "errorCode", "errorMessage", "updatedAt", "stale",
    }
    observation_ref = result_schema["properties"]["observation"]["$ref"]
    observation_schema = schemas[observation_ref.rsplit("/", 1)[-1]]
    assert set(observation_schema["properties"]) == {
        "observedAt", "freshness", "errorCode", "errorMessage",
    }
    request_ref = result_schema["properties"]["lastRequest"]["anyOf"][0]["$ref"]
    request_schema = schemas[request_ref.rsplit("/", 1)[-1]]
    assert set(request_schema["properties"]) == {
        "requestedPercent", "status", "errorCode", "errorMessage", "updatedAt",
    }
    assert not {"rawLeft", "rawRight", "decibels"}.intersection(state_schema["properties"])
    get_responses = response.json()["paths"]["/api/system/hardware-volume"]["get"]["responses"]
    assert get_responses["503"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
    put_responses = response.json()["paths"]["/api/system/hardware-volume"]["put"]["responses"]
    assert {"200", "400", "422", "502", "503"}.issubset(put_responses)
    assert put_responses["400"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
