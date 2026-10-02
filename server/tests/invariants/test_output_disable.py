"""F6: disabling the selected output never owns a playback transition."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from server.app.models.output import OutputMode
from server.app.player.models import OutputInfo
from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.app.repositories.database import run_transaction
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.services.output_manager import OutputError
from server.tests.invariants.test_output_enable import (
    enable_capabilities,
    enable_manager,
)
from server.tests.invariants.test_output_event_transactions import create_terminal
from server.tests.invariants.test_output_serialization import authority_snapshot
from server.tests.support.playback import start


@pytest.mark.parametrize("state", ["playing", "paused", "stopped", "empty", "unknown", "natural"])
@pytest.mark.parametrize("already_disabled", [False, True])
@pytest.mark.parametrize("other_enabled", [False, True])
def test_disable_is_not_playback_stop(
    real_client, monkeypatch, state, already_disabled, other_enabled,
):
    client, _, player, service = real_client
    if state != "empty":
        start(client)

    async def scenario():
        if state != "empty":
            await service.add_to_queue("a")
            await service.seek(17)
        if state == "paused":
            await service.pause()
        elif state == "stopped":
            await service.stop()
        await player.set_repeat(True)
        await player.set_random(True)
        await player.set_volume(23)
        player._outputs = [
            OutputInfo(id=37, name="DAC", plugin="alsa", enabled=not already_disabled),
            OutputInfo(id=8, name="Other DAC", plugin="alsa", enabled=other_enabled),
            OutputInfo(id=0, name="Stream", plugin="httpd", enabled=other_enabled),
        ]
        original_status = player.status
        if state == "unknown":
            async def unknown_status():
                return (await original_status()).model_copy(update={"elapsed_seconds": None})
            monkeypatch.setattr(player, "status", unknown_status)
        before = await authority_snapshot(service)
        status, entries, outputs = await player.status(), await player.queue_entries(), await player.outputs()
        calls, commands, events = [], [], []
        now = 100.0
        check, original_command = player._check, player.set_output_enabled

        def record(command):
            calls.append(command)
            check(command)

        async def command(output_id, enabled):
            nonlocal now
            commands.append((output_id, enabled))
            await original_command(output_id, enabled)
            if state == "natural":
                player._elapsed += 2
                now += 2

        class Publisher:
            async def publish(self, event):
                assert calls[-2:] == ["status", "queue_entries"]
                assert await asyncio.wait_for(
                    asyncio.create_task(authority_snapshot(service)), 3,
                ) == before
                events.append(event)

        monkeypatch.setattr(player, "_check", record)
        monkeypatch.setattr(player, "set_output_enabled", command)
        manager = enable_manager(
            service, player, selector=lambda candidates: candidates[0],
            event_publisher=Publisher(), monotonic_clock=lambda: now,
        )
        receipt = await manager.set_enabled(OutputMode.NAS_DAC, False)
        assert receipt.states[0].status == "INACTIVE"
        assert receipt.states[0].stale is False
        assert receipt.last_request.status == "SUCCEEDED"
        assert receipt.last_request.enabled is False
        assert receipt.last_request.error_code is None
        assert receipt.states[1].status == "UNAVAILABLE"
        assert all(getattr(s, field) is None for s in receipt.states for field in (
            "target_client_id", "stream_url", "format", "sample_rate", "bit_depth", "channels",
        ))
        assert commands == ([] if already_disabled else [(37, False)])
        # A whitelist proves zero Stop/Play/seek/Queue/mode mutations.
        assert not set(calls) - {"outputs", "status", "queue_entries", "set_output_enabled"}
        assert len(events) == int(not already_disabled)
        assert await authority_snapshot(service) == before
        assert await player.queue_entries() == entries
        assert await player.outputs() == [outputs[0].model_copy(update={"enabled": False}), *outputs[1:]]
        after = await player.status()
        assert after.model_dump(exclude={"elapsed_seconds"}) == status.model_dump(exclude={"elapsed_seconds"})
        assert after.elapsed_seconds == (19 if state == "natural" and not already_disabled else status.elapsed_seconds)
        if state not in {"empty", "stopped"}:
            assert before[3] is not None and before[4] is not None
        if state != "empty":
            assert entries[0].song_uri == entries[-1].song_uri == "a.flac"
            assert entries[0].mpd_song_id != entries[-1].mpd_song_id
        receipt.states[0].status = "ACTIVE"
        receipt.last_request.enabled = True
        if events:
            assert events[0].event_type == "output.changed"
            assert events[0].snapshot.states[0].status == "INACTIVE"
            assert events[0].snapshot.last_request.enabled is False
        assert (await manager.set_enabled(OutputMode.NAS_DAC, False)).last_request.status == "SUCCEEDED"
        assert len(commands) == int(not already_disabled)
        assert len(events) == int(not already_disabled)
        player.disconnect()
        cached = await manager.get_state()
        assert cached.states[0].status == "INACTIVE" and cached.states[0].stale is True
        assert cached.last_request.enabled is False

    asyncio.run(scenario())


@pytest.mark.parametrize("fault, error_type, code, actual, stale", [
    ("ack-no-effect", OutputError, "OUTPUT_RECONCILIATION_FAILED", "ACTIVE", False),
    ("reject", PlayerCommandError, "PLAYER_COMMAND_ERROR", "ACTIVE", False),
    ("timeout-after-effect", PlayerUnavailable, "PLAYER_UNAVAILABLE", "INACTIVE", False),
    ("readback-fails-once", PlayerUnavailable, "PLAYER_UNAVAILABLE", "INACTIVE", False),
    ("readback-offline", PlayerUnavailable, "PLAYER_UNAVAILABLE", "ACTIVE", True),
    ("cancel-after-effect", asyncio.CancelledError, "OUTPUT_CANCELLED", "INACTIVE", False),
    ("initial-offline", PlayerUnavailable, "PLAYER_UNAVAILABLE", "ACTIVE", True),
    ("after-status-fails", PlayerUnavailable, "PLAYER_UNAVAILABLE", "INACTIVE", False),
])
def test_disable_failure_keeps_truth_and_retry_is_safe(
    real_client, monkeypatch, fault, error_type, code, actual, stale,
):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        await service.pause()
        before = await authority_snapshot(service)
        facts = (await player.status(), await player.queue_entries())
        player._outputs = [
            OutputInfo(id=37, name="DAC", plugin="alsa", enabled=True),
            OutputInfo(id=0, name="Stream", plugin="httpd", enabled=True),
        ]
        events, commands, calls = [], [], []
        entered, release = asyncio.Event(), asyncio.Event()
        check = player._check

        def record(command):
            calls.append(command)
            check(command)

        class Publisher:
            async def publish(self, event):
                events.append(event)

        monkeypatch.setattr(player, "_check", record)
        manager = enable_manager(service, player, event_publisher=Publisher(), monotonic_clock=lambda: 0.0)
        assert (await manager.get_state()).states[0].status == "ACTIVE"
        original_command = player.set_output_enabled

        async def command(output_id, enabled):
            commands.append((output_id, enabled))
            preparing = (await manager.get_state()).last_request
            assert preparing.status == "PREPARING" and preparing.enabled is False
            if fault == "reject":
                raise PlayerCommandError("set_output_enabled", "command rejected")
            if fault != "ack-no-effect":
                await original_command(output_id, enabled)
            if fault == "timeout-after-effect":
                raise PlayerUnavailable("timeout after delivery")
            if fault == "readback-offline":
                player.disconnect()
            elif fault in {"readback-fails-once", "after-status-fails"}:
                method = "outputs" if fault == "readback-fails-once" else "status"
                original = getattr(player, method)
                count = 0

                async def interrupted_read():
                    nonlocal count
                    count += 1
                    if count == 1:
                        raise PlayerUnavailable("confirmation interrupted")
                    return await original()

                monkeypatch.setattr(player, method, interrupted_read)
            elif fault == "cancel-after-effect":
                entered.set()
                await release.wait()

        monkeypatch.setattr(player, "set_output_enabled", command)
        if fault == "initial-offline":
            player.disconnect()
        task = asyncio.create_task(manager.set_enabled(OutputMode.NAS_DAC, False))
        if fault == "cancel-after-effect":
            await asyncio.wait_for(entered.wait(), 3)
            task.cancel()
        with pytest.raises(error_type) as error:
            await asyncio.wait_for(task, 3)
        if isinstance(error.value, OutputError):
            assert error.value.code == code
        assert events == []
        assert await authority_snapshot(service) == before
        failure_outputs = player.outputs

        async def offline_outputs():
            raise PlayerUnavailable("later read offline")

        monkeypatch.setattr(player, "outputs", offline_outputs)
        cached = await manager.get_state()
        assert cached.states[0].status == actual and cached.states[0].stale is True
        assert cached.last_request.status == "SWITCH_FAILED"
        assert cached.last_request.error_code == code and cached.last_request.enabled is False
        monkeypatch.setattr(player, "outputs", failure_outputs)
        observed = await manager.get_state()
        assert observed.states[0].status == actual and observed.states[0].stale is stale
        assert observed.last_request.status == "SWITCH_FAILED"
        player.reconnect()
        assert (await player.status(), await player.queue_entries()) == facts
        assert (await player.outputs())[1].enabled is True
        assert commands == ([] if fault == "initial-offline" else [(37, False)])

        async def retry_command(output_id, enabled):
            commands.append((output_id, enabled))
            await original_command(output_id, enabled)

        monkeypatch.setattr(player, "set_output_enabled", retry_command)
        result = await asyncio.wait_for(asyncio.create_task(manager.set_enabled(OutputMode.NAS_DAC, False)), 3)
        assert result.states[0].status == "INACTIVE" and result.states[0].stale is False
        assert result.last_request.status == "SUCCEEDED" and result.last_request.enabled is False
        needs_write = fault in {"initial-offline", "ack-no-effect", "reject"}
        assert commands == [(37, False)] * ((0 if fault == "initial-offline" else 1) + int(needs_write))
        assert len(events) == int(needs_write)
        assert await authority_snapshot(service) == before
        assert not set(calls) - {"outputs", "status", "queue_entries", "set_output_enabled"}

    asyncio.run(scenario())


@pytest.mark.parametrize("drift", [
    "occurrence", "queue", "state", "position", "repeat", "random", "volume", "other-output", "target-id",
])
def test_disable_rejects_drift_without_playback_repair(real_client, monkeypatch, drift):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        await service.add_to_queue("a")
        await service.seek(17)
        entries = await player.queue_entries()
        before = await authority_snapshot(service)
        player._outputs = [
            OutputInfo(id=37, name="DAC", plugin="alsa", enabled=True),
            OutputInfo(id=0, name="Stream", plugin="httpd", enabled=True),
        ]
        events, calls = [], []
        original, check = player.set_output_enabled, player._check

        def record(command):
            calls.append(command)
            check(command)

        async def command(output_id, enabled):
            assert (output_id, enabled) == (37, False)
            await original(output_id, enabled)
            if drift == "occurrence":
                player._current_queue_id = entries[-1].mpd_song_id
            elif drift == "queue":
                player._queue[-1] = ("a.flac", 999)
            elif drift == "state":
                player._state = player._state.STOPPED
            elif drift == "position":
                player._elapsed = 0
            elif drift in {"repeat", "random"}:
                setattr(player, "_random_enabled" if drift == "random" else "_repeat", True)
            elif drift == "volume":
                player._volume = 23
            elif drift == "other-output":
                player._outputs[1].enabled = False
            else:
                player._outputs[0].id = 91

        class Publisher:
            async def publish(self, event):
                events.append(event)

        monkeypatch.setattr(player, "_check", record)
        monkeypatch.setattr(player, "set_output_enabled", command)
        manager = enable_manager(service, player, event_publisher=Publisher(), monotonic_clock=lambda: 0.0)
        with pytest.raises(OutputError) as error:
            await manager.set_enabled(OutputMode.NAS_DAC, False)
        assert error.value.code == "OUTPUT_RECONCILIATION_FAILED"
        snapshot = await manager.get_state()
        assert snapshot.states[0].status == "INACTIVE"
        assert snapshot.last_request.status == "SWITCH_FAILED"
        assert events == [] and calls.count("set_output_enabled") == 1
        assert not set(calls) - {"outputs", "status", "queue_entries", "set_output_enabled"}
        assert await authority_snapshot(service) == before

    asyncio.run(scenario())


@pytest.mark.parametrize("phase", ["commit", "failure", "cancel"])
def test_disable_notification_and_request_follow_outer_commit(real_client, monkeypatch, phase):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        before = await authority_snapshot(service)
        facts = (await player.status(), await player.queue_entries())
        player._outputs = [OutputInfo(id=37, name="DAC", plugin="alsa", enabled=True)]
        records = IdempotencyRepository(service.queue_manager.queue_repository.path)
        events, commands = [], []
        entered, release = asyncio.Event(), asyncio.Event()
        original = player.set_output_enabled

        async def command(output_id, enabled):
            commands.append((output_id, enabled))
            await original(output_id, enabled)

        class Publisher:
            async def publish(self, event):
                assert await asyncio.wait_for(asyncio.create_task(records.get_by_key("confirmed")), 3) is not None
                events.append(event)

        monkeypatch.setattr(player, "set_output_enabled", command)
        manager = enable_manager(service, player, event_publisher=Publisher(), monotonic_clock=lambda: 0.0)

        async def outer(_):
            receipt = await manager.set_enabled(OutputMode.NAS_DAC, False)
            assert receipt.last_request.status == "SUCCEEDED"
            await create_terminal(records)
            assert events == []
            if phase == "failure":
                raise RuntimeError("outer failure")
            if phase == "cancel":
                entered.set()
                await release.wait()
            return receipt

        task = asyncio.create_task(run_transaction(records.path, outer))
        if phase == "cancel":
            await asyncio.wait_for(entered.wait(), 3)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 3)
        elif phase == "failure":
            with pytest.raises(RuntimeError, match="outer failure"):
                await task
        else:
            await asyncio.wait_for(task, 3)
        committed = phase == "commit"
        assert (await records.get_by_key("confirmed") is not None) == committed
        assert len(events) == int(committed)
        assert (await player.outputs())[0].enabled is False
        snapshot = await manager.get_state()
        assert snapshot.states[0].status == "INACTIVE"
        assert snapshot.last_request.status == ("SUCCEEDED" if committed else "SWITCH_FAILED")
        if not committed:
            assert snapshot.last_request.error_code == "OUTPUT_TRANSACTION_FAILED"
        assert await authority_snapshot(service) == before
        assert (await player.status(), await player.queue_entries()) == facts
        assert (await manager.set_enabled(OutputMode.NAS_DAC, False)).last_request.status == "SUCCEEDED"
        assert commands == [(37, False)] and len(events) == int(committed)

    asyncio.run(scenario())


@pytest.mark.parametrize("missing", ["outputs", "set_output_enabled", "status", "queue_entries"])
def test_disable_requires_confirmation_capabilities_before_control(real_client, monkeypatch, missing):
    _, _, player, service = real_client

    async def scenario():
        player._outputs = [OutputInfo(id=37, name="DAC", plugin="alsa", enabled=True)]
        caps = enable_capabilities()
        caps = replace(caps, verified_operations=caps.verified_operations - {missing}) if missing in {
            "set_output_enabled", "queue_entries",
        } else replace(caps, commands=caps.commands - {missing})
        calls, check = [], player._check

        def record(command):
            calls.append(command)
            check(command)

        monkeypatch.setattr(player, "_check", record)
        manager = enable_manager(service, player, capabilities=caps)
        with pytest.raises(OutputError) as error:
            await manager.set_enabled(OutputMode.NAS_DAC, False)
        assert error.value.code == "OUTPUT_CAPABILITY_UNVERIFIED"
        assert not set(calls) - {"outputs"}
        assert player._outputs[0].enabled is True
        assert (await manager.get_state()).last_request.status == "SWITCH_FAILED"

    asyncio.run(scenario())


def test_disable_rebinds_current_id_and_confirms_noop_retry(real_client, monkeypatch):
    _, _, player, service = real_client

    async def scenario():
        player._outputs = [OutputInfo(id=37, name="DAC", plugin="alsa", enabled=True)]
        manager = enable_manager(service, player, monotonic_clock=lambda: 0.0)
        assert (await manager.get_state()).states[0].status == "ACTIVE"
        player._outputs[0].id = 91
        commands, original = [], player.set_output_enabled

        async def command(output_id, enabled):
            commands.append((output_id, enabled))
            await original(output_id, enabled)

        monkeypatch.setattr(player, "set_output_enabled", command)
        assert (await manager.set_enabled(OutputMode.NAS_DAC, False)).states[0].status == "INACTIVE"
        assert (await manager.set_enabled(OutputMode.NAS_DAC, False)).last_request.status == "SUCCEEDED"
        assert commands == [(91, False)]

    asyncio.run(scenario())
