"""F8: REST receipts match confirmed output and preserve playback authorities."""

import asyncio
import json

import pytest

from server.app.api.system_schemas import OutputSnapshotResponse
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.tests.api.test_system_output_mutations import output_api, output_put
from server.tests.invariants.test_output_serialization import authority_snapshot
from server.tests.support.playback import start

__all__ = ["output_api"]


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("already_satisfied", [True, False])
def test_output_mutation_response_matches_confirmed_service_and_port(
    output_api, enabled, already_satisfied,
):
    client, player, service, manager, calls, events, path = output_api
    start(client)

    async def prepare():
        await service.add_to_queue("a")
        await service.pause()
        await service.seek(17)
        await player.set_repeat(True)
        await player.set_random(True)
        await player.set_volume(23)
        player._outputs[0].enabled = enabled if already_satisfied else not enabled
        return (await authority_snapshot(service), await player.status(),
                await player.queue_entries(), await player.outputs())

    before, status, entries, outputs = asyncio.run(prepare())
    calls.clear()
    response = output_put(client, enabled)
    assert response.status_code == 200, response.text
    assert response.json()["states"][0]["status"] == ("ACTIVE" if enabled else "INACTIVE")
    assert response.json()["states"][0]["stale"] is False
    assert response.json()["last_request"]["enabled"] is enabled
    assert response.json()["last_request"]["status"] == "SUCCEEDED"
    assert calls.count("set_output_enabled") == (0 if already_satisfied else 1)
    assert set(calls) <= {"outputs", "status", "queue_entries", "set_output_enabled"}
    assert len(events) == (0 if already_satisfied else 1)
    if events:
        assert response.json() == json.loads(OutputSnapshotResponse.model_validate(
            events[0].snapshot.model_dump(),
        ).model_dump_json(by_alias=True))
    record = asyncio.run(IdempotencyRepository(path).get_by_key("output-key"))
    assert record.response_body == response.text
    assert asyncio.run(authority_snapshot(service)) == before
    assert asyncio.run(player.status()) == status
    assert asyncio.run(player.queue_entries()) == entries
    assert asyncio.run(player.outputs()) == [outputs[0].model_copy(update={"enabled": enabled}), outputs[1]]
    observed = asyncio.run(manager.get_state())
    assert observed.states[0].status == response.json()["states"][0]["status"]


@pytest.mark.parametrize("failure,expected_status,expected_code", [
    ("unsupported", 400, "OUTPUT_MODE_UNSUPPORTED"),
    ("ambiguous", 400, "OUTPUT_AMBIGUOUS"),
    ("selector", 400, "OUTPUT_SELECTION_FAILED"),
    ("unavailable", 503, "OUTPUT_UNAVAILABLE"),
    ("capability", 503, "OUTPUT_CAPABILITY_UNVERIFIED"),
    ("offline", 503, "PLAYER_UNAVAILABLE"),
    ("command", 502, "PLAYER_COMMAND_FAILED"),
    ("ack", 502, "OUTPUT_RECONCILIATION_FAILED"),
    ("playback", 502, "OUTPUT_RECONCILIATION_FAILED"),
    ("timeout_after_effect", 503, "PLAYER_UNAVAILABLE"),
])
def test_output_http_failure_preserves_authorities_and_actual_facts(
    output_api, monkeypatch, failure, expected_status, expected_code,
):
    from server.app.player.capabilities import MPDCapabilities
    from server.app.player.ports import PlayerUnavailable

    client, player, service, manager, calls, events, path = output_api
    start(client)
    before = asyncio.run(authority_snapshot(service))
    status = asyncio.run(player.status())
    entries = asyncio.run(player.queue_entries())
    control = player.set_output_enabled
    if failure == "ambiguous":
        player._outputs.append(player._outputs[0].model_copy(update={"id": 72}))
    elif failure == "selector":
        manager.selector = lambda candidates: None
    elif failure == "unavailable":
        player._outputs = player._outputs[1:]
    elif failure == "capability":
        manager.capabilities = MPDCapabilities.from_commands(set())
    elif failure == "offline":
        player.disconnect()
    elif failure == "command":
        player.fail_next("set_output_enabled", "rejected")
    elif failure == "ack":
        async def no_effect(output_id, enabled):
            player._check("set_output_enabled")
        monkeypatch.setattr(player, "set_output_enabled", no_effect)
    elif failure == "playback":
        async def diverged_status():
            return status.model_copy(update={"volume": 99})
        # After the output effect the playback guard must reject drift.
        async def drift(output_id, enabled):
            await control(output_id, enabled)
            monkeypatch.setattr(player, "status", diverged_status)
        monkeypatch.setattr(player, "set_output_enabled", drift)
    elif failure == "timeout_after_effect":
        async def timeout(output_id, enabled):
            await control(output_id, enabled)
            raise PlayerUnavailable("timeout after output effect")
        monkeypatch.setattr(player, "set_output_enabled", timeout)
    outputs = asyncio.run(player.outputs()) if failure != "offline" else list(player._outputs)
    calls.clear()
    response = output_put(client, mode="CLIENT_STREAM" if failure == "unsupported" else "NAS_DAC")
    assert response.status_code == expected_status, response.text
    assert response.json()["error"]["code"] == expected_code
    assert response.json()["error"]["message"]
    if failure == "command":
        assert response.json()["error"]["details"]["command"] == "set_output_enabled"
    assert events == []
    assert asyncio.run(IdempotencyRepository(path).get_by_key("output-key")) is None
    assert asyncio.run(authority_snapshot(service)) == before
    player.reconnect()
    assert asyncio.run(player.queue_entries()) == entries
    changed = failure in {"playback", "timeout_after_effect"}
    assert asyncio.run(player.outputs()) == (
        [outputs[0].model_copy(update={"enabled": True}), *outputs[1:]] if changed else outputs
    )
    if failure != "playback":
        assert asyncio.run(player.status()) == status
    actual = client.get("/api/system/output").json()
    if changed:
        assert actual["states"][0]["status"] == "ACTIVE"
        assert actual["last_request"]["status"] == "SWITCH_FAILED"
