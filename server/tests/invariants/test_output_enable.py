"""F5: enable changes only output facts across real playback authorities."""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import replace

import pytest

from server.app.models.output import OutputMode
from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.models import OutputInfo
from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.app.repositories import database
from server.app.repositories.database import run_transaction
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.services.output_manager import OutputError, OutputManager
from server.tests.invariants.test_output_event_transactions import create_terminal
from server.tests.invariants.test_output_serialization import authority_snapshot
from server.tests.support.playback import start


def enable_capabilities():
    return replace(
        MPDCapabilities.from_commands({
            "outputs", "enableoutput", "disableoutput", "status", "currentsong", "playlistinfo",
        }),
        verified_operations=frozenset({"set_output_enabled", "queue_entries"}),
    )


def enable_manager(service, player, **kwargs):
    caps = kwargs.pop("capabilities", enable_capabilities())
    return OutputManager(
        player=VerifiedPlayerPort(player, caps), capabilities=caps,
        operation_runner=service.run_output_operation, **kwargs,
    )


@pytest.mark.parametrize("already_enabled", [False, True])
def test_enable_receipt_cannot_corrupt_last_confirmed_fact_when_later_offline(real_client, already_enabled):
    _, _, player, service = real_client

    async def scenario():
        player._outputs = [OutputInfo(id=37, name="DAC", plugin="alsa", enabled=already_enabled)]
        manager = enable_manager(service, player, monotonic_clock=lambda: 0.0)
        receipt = await manager.set_enabled(OutputMode.NAS_DAC, True)
        assert receipt.states[0].status == "ACTIVE"
        receipt.states[0].status = "INACTIVE"
        receipt.last_request.status = "SWITCH_FAILED"
        receipt.last_request.enabled = False
        player.disconnect()
        cached = await manager.get_state()
        assert cached.states[0].status == "ACTIVE"
        assert cached.states[0].stale is True
        assert cached.states[0].error_code == "PLAYER_UNAVAILABLE"
        assert cached.last_request.status == "SUCCEEDED"
        assert cached.last_request.enabled is True
        player.reconnect()
        assert (await player.outputs())[0].enabled is True

    asyncio.run(scenario())


@pytest.mark.parametrize("state", ["playing", "paused", "stopped", "empty", "unknown", "natural"])
@pytest.mark.parametrize("already_enabled", [False, True])
def test_enable_preserves_other_outputs_and_all_playback_authorities(
    real_client, monkeypatch, state, already_enabled,
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
            OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=already_enabled),
            OutputInfo(id=8, name="Other DAC", plugin="alsa", enabled=True),
            OutputInfo(id=0, name="Stream", plugin="httpd", enabled=True),
        ]
        original_status = player.status
        if state == "unknown":
            async def unknown_status():
                return (await original_status()).model_copy(update={"elapsed_seconds": None})
            monkeypatch.setattr(player, "status", unknown_status)
        before = await authority_snapshot(service)
        before_status = await player.status()
        entries = await player.queue_entries()
        outputs = await player.outputs()
        calls, events = [], []
        check = player._check
        now = 100.0

        def record(command):
            nonlocal now
            calls.append(command)
            check(command)
            if state == "natural" and calls.count("outputs") == 2 and command == "outputs":
                player._elapsed += 2
                now += 2

        monkeypatch.setattr(player, "_check", record)

        class Publisher:
            async def publish(self, event):
                assert event.event_type == "output.changed"
                assert calls[-2:] == ["status", "queue_entries"]
                # A different task proves commit and lock release preceded delivery.
                assert await asyncio.wait_for(
                    asyncio.create_task(authority_snapshot(service)), 3,
                ) == before
                events.append(event)

        manager = enable_manager(
            service, player, selector=lambda candidates: candidates[0],
            event_publisher=Publisher(), monotonic_clock=lambda: now,
        )
        receipt = await manager.set_enabled(OutputMode.NAS_DAC, True)
        assert receipt.states[0].status == "ACTIVE"
        assert receipt.states[0].stale is False
        assert receipt.last_request.status == "SUCCEEDED"
        assert receipt.last_request.enabled is True
        assert receipt.last_request.error_code is None
        assert receipt.states[1].status == "UNAVAILABLE"
        assert calls.count("set_output_enabled") == (0 if already_enabled else 1)
        assert not set(calls) - {"outputs", "status", "queue_entries", "set_output_enabled"}
        assert len(events) == (0 if already_enabled else 1)
        assert await authority_snapshot(service) == before
        assert await player.queue_entries() == entries
        assert await player.outputs() == [outputs[0].model_copy(update={"enabled": True}), *outputs[1:]]
        after = await player.status()
        assert after.model_dump(exclude={"elapsed_seconds"}) == before_status.model_dump(
            exclude={"elapsed_seconds"},
        )
        assert after.elapsed_seconds == (19 if state == "natural" else before_status.elapsed_seconds)
        if state != "empty":
            assert entries[0].song_uri == entries[-1].song_uri == "a.flac"
            assert entries[0].mpd_song_id != entries[-1].mpd_song_id
        if events:
            receipt.states[0].status = "INACTIVE"
            receipt.last_request.status = "SWITCH_FAILED"
            assert events[0].snapshot.states[0].status == "ACTIVE"
            assert events[0].snapshot.last_request.status == "SUCCEEDED"
        assert (await manager.get_state()).last_request.status == "SUCCEEDED"

    asyncio.run(scenario())


def test_enable_keeps_independent_output_baseline_when_port_reuses_models(real_client, monkeypatch):
    _, _, player, service = real_client

    async def scenario():
        shared = [
            OutputInfo(id=37, name="DAC", plugin="alsa", enabled=False),
            OutputInfo(id=0, name="Stream", plugin="httpd", enabled=True),
        ]

        async def outputs():
            return shared

        async def command(output_id, enabled):
            assert (output_id, enabled) == (37, True)
            shared[0].enabled = True
            shared[1].enabled = False

        monkeypatch.setattr(player, "outputs", outputs)
        monkeypatch.setattr(player, "set_output_enabled", command)
        manager = enable_manager(service, player, monotonic_clock=lambda: 0.0)
        with pytest.raises(OutputError) as error:
            await manager.set_enabled(OutputMode.NAS_DAC, True)
        assert error.value.code == "OUTPUT_RECONCILIATION_FAILED"
        assert (await manager.get_state()).last_request.status == "SWITCH_FAILED"

    asyncio.run(scenario())


@pytest.mark.parametrize("missing", ["outputs", "set_output_enabled", "status", "queue_entries"])
def test_enable_checks_every_confirmation_capability_before_control(real_client, monkeypatch, missing):
    _, _, player, service = real_client

    async def scenario():
        caps = enable_capabilities()
        if missing in {"set_output_enabled", "queue_entries"}:
            caps = replace(caps, verified_operations=caps.verified_operations - {missing})
        else:
            caps = replace(caps, commands=caps.commands - {missing})
        calls = []
        check = player._check

        def record(command):
            calls.append(command)
            check(command)

        monkeypatch.setattr(player, "_check", record)
        manager = enable_manager(service, player, capabilities=caps)
        with pytest.raises(OutputError) as error:
            await manager.set_enabled(OutputMode.NAS_DAC, True)
        assert error.value.code == "OUTPUT_CAPABILITY_UNVERIFIED"
        assert not set(calls) - {"outputs"}
        assert (await manager.get_state()).last_request.status == "SWITCH_FAILED"

    asyncio.run(scenario())


@pytest.mark.parametrize("selection, code", [
    ("none", "OUTPUT_UNAVAILABLE"), ("ambiguous", "OUTPUT_AMBIGUOUS"),
    ("selector-none", "OUTPUT_SELECTION_FAILED"), ("selector-foreign", "OUTPUT_SELECTION_FAILED"),
    ("selector-error", "OUTPUT_SELECTION_FAILED"), ("duplicate-id", "OUTPUT_AMBIGUOUS"),
])
def test_enable_rejects_unconfirmed_output_selection_without_mutation(real_client, monkeypatch, selection, code):
    _, _, player, service = real_client

    async def scenario():
        player._outputs = [
            OutputInfo(id=37, name="DAC", plugin="alsa", enabled=False),
            OutputInfo(id=8, name="Other", plugin="alsa", enabled=True),
        ]
        if selection == "none":
            player._outputs = [OutputInfo(id=0, name="Stream", plugin="httpd", enabled=True)]
        elif selection == "duplicate-id":
            player._outputs[1].id = 37
        outputs, before = await player.outputs(), await authority_snapshot(service)
        facts = (await player.status(), await player.queue_entries())
        selector = None
        if selection.startswith("selector"):
            def selector(candidates):
                if selection == "selector-error":
                    raise ValueError("selector failed")
                return candidates[0].model_copy() if selection == "selector-foreign" else None
        elif selection == "duplicate-id":
            selector = lambda candidates: candidates[0]
        calls = []
        check = player._check

        def record(command):
            calls.append(command)
            check(command)

        monkeypatch.setattr(player, "_check", record)
        manager = enable_manager(service, player, selector=selector, monotonic_clock=lambda: 0.0)
        with pytest.raises(OutputError) as error:
            await manager.set_enabled(OutputMode.NAS_DAC, True)
        assert error.value.code == code
        assert not set(calls) - {"outputs", "status", "queue_entries"}
        state = await manager.get_state()
        assert state.last_request.status == "SWITCH_FAILED"
        assert state.last_request.error_code == code
        assert state.states[0].status == "UNAVAILABLE"
        assert await player.outputs() == outputs
        assert (await player.status(), await player.queue_entries()) == facts
        assert await authority_snapshot(service) == before

    asyncio.run(scenario())


def test_enable_rebinds_changed_id_before_control_and_retry_is_noop(real_client, monkeypatch):
    _, _, player, service = real_client

    async def scenario():
        player._outputs = [OutputInfo(id=37, name="DAC", plugin="alsa", enabled=False)]
        manager = enable_manager(service, player, monotonic_clock=lambda: 0.0)
        assert (await manager.get_state()).states[0].status == "INACTIVE"
        player._outputs[0].id = 91
        commands = []
        original = player.set_output_enabled

        async def command(output_id, enabled):
            commands.append((output_id, enabled))
            await original(output_id, enabled)

        monkeypatch.setattr(player, "set_output_enabled", command)
        assert (await manager.set_enabled(OutputMode.NAS_DAC, True)).states[0].status == "ACTIVE"
        assert (await manager.set_enabled(OutputMode.NAS_DAC, True)).last_request.status == "SUCCEEDED"
        assert commands == [(91, True)]

    asyncio.run(scenario())


@pytest.mark.parametrize("drift", ["occurrence", "queue", "state", "position", "repeat", "random", "volume", "other-output", "target-id"])
def test_enable_rejects_actual_drift_without_repair_or_notification(real_client, monkeypatch, drift):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        await service.add_to_queue("a")
        await service.pause()
        await service.seek(17)
        entries = await player.queue_entries()
        before = await authority_snapshot(service)
        player._outputs = [
            OutputInfo(id=37, name="DAC", plugin="alsa", enabled=False),
            OutputInfo(id=0, name="Stream", plugin="httpd", enabled=True),
        ]
        commands, events = [], []
        original = player.set_output_enabled

        async def command(output_id, enabled):
            commands.append((output_id, enabled))
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
            elif drift == "target-id":
                player._outputs[0].id = 91

        class Publisher:
            async def publish(self, event):
                events.append(event)

        monkeypatch.setattr(player, "set_output_enabled", command)
        manager = enable_manager(
            service, player, event_publisher=Publisher(), monotonic_clock=lambda: 0.0,
        )
        with pytest.raises(OutputError) as error:
            await manager.set_enabled(OutputMode.NAS_DAC, True)
        assert error.value.code == "OUTPUT_RECONCILIATION_FAILED"
        observation = await manager.get_state()
        assert observation.states[0].status == "ACTIVE"
        assert observation.last_request.status == "SWITCH_FAILED"
        assert commands == [(37, True)]
        assert events == []
        assert await authority_snapshot(service) == before

    asyncio.run(scenario())


@pytest.mark.parametrize("phase", ["commit", "outer-failure", "outer-cancel", "commit-failure", "postcommit-cancel", "publisher-failure"])
def test_enable_request_and_notification_follow_outer_transaction(real_client, monkeypatch, caplog, phase):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        before = await authority_snapshot(service)
        facts = (await player.status(), await player.queue_entries())
        player._outputs = [OutputInfo(id=37, name="DAC", plugin="alsa", enabled=False)]
        records = IdempotencyRepository(service.queue_manager.queue_repository.path)
        events = []
        entered, release = asyncio.Event(), asyncio.Event()
        committed = phase in {"commit", "postcommit-cancel", "publisher-failure"}
        connect = database._connect

        class FailingCommit(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError("commit witness failure")

        if phase == "commit-failure":
            monkeypatch.setattr(database, "_connect", lambda p: sqlite3.connect(p, factory=FailingCommit))

        class Publisher:
            async def publish(self, event):
                terminal = await asyncio.wait_for(
                    asyncio.create_task(records.get_by_key("confirmed")), 3,
                )
                assert terminal is not None
                events.append(event)
                if phase == "publisher-failure":
                    raise RuntimeError("publisher witness failure")
                if phase == "postcommit-cancel":
                    entered.set()
                    await release.wait()

        manager = enable_manager(
            service, player, event_publisher=Publisher(), monotonic_clock=lambda: 0.0,
        )

        async def outer(_):
            receipt = await manager.set_enabled(OutputMode.NAS_DAC, True)
            assert receipt.last_request.status == "SUCCEEDED"
            assert events == []
            await create_terminal(records)
            assert events == []
            if phase == "outer-failure":
                raise RuntimeError("outer witness failure")
            if phase == "outer-cancel":
                entered.set()
                await release.wait()
            return receipt

        task = asyncio.create_task(run_transaction(records.path, outer))
        if phase in {"outer-cancel", "postcommit-cancel"}:
            await asyncio.wait_for(entered.wait(), 3)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 3)
        elif phase == "outer-failure":
            with pytest.raises(RuntimeError, match="outer witness failure"):
                await task
        elif phase == "commit-failure":
            with pytest.raises(sqlite3.OperationalError, match="commit witness failure"):
                await task
        else:
            await asyncio.wait_for(task, 3)
        monkeypatch.setattr(database, "_connect", connect)
        assert len(events) == int(committed)
        assert (await records.get_by_key("confirmed") is not None) == committed
        if phase == "publisher-failure":
            assert "Post-commit notification failed" in caplog.text
        assert await authority_snapshot(service) == before
        assert (await player.status(), await player.queue_entries()) == facts
        assert (await player.outputs())[0].enabled is True  # SQLite never reverses MPD.
        observation = await manager.get_state()
        assert observation.states[0].status == "ACTIVE"
        assert observation.last_request.status == ("SUCCEEDED" if committed else "SWITCH_FAILED")
        # An already effected retry confirms and emits no new change notification.
        assert (await manager.set_enabled(OutputMode.NAS_DAC, True)).last_request.status == "SUCCEEDED"
        assert len(events) == int(committed)

    asyncio.run(scenario())


@pytest.mark.parametrize("fault, error_type, code, actual, stale", [
    ("ack-no-effect", OutputError, "OUTPUT_RECONCILIATION_FAILED", "INACTIVE", False),
    ("reject", PlayerCommandError, "PLAYER_COMMAND_ERROR", "INACTIVE", False),
    ("timeout-after-effect", PlayerUnavailable, "PLAYER_UNAVAILABLE", "ACTIVE", False),
    ("readback-fails-once", PlayerUnavailable, "PLAYER_UNAVAILABLE", "ACTIVE", False),
    ("readback-offline", PlayerUnavailable, "PLAYER_UNAVAILABLE", "INACTIVE", True),
    ("cancel-after-effect", asyncio.CancelledError, "OUTPUT_CANCELLED", "ACTIVE", False),
    ("initial-offline", PlayerUnavailable, "PLAYER_UNAVAILABLE", "INACTIVE", True),
    ("after-status-fails", PlayerUnavailable, "PLAYER_UNAVAILABLE", "ACTIVE", False),
])
def test_enable_failure_reconciles_actual_output_without_false_success(
    real_client, monkeypatch, fault, error_type, code, actual, stale,
):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        await service.pause()
        before = await authority_snapshot(service)
        facts = (await player.status(), await player.queue_entries())
        player._outputs = [
            OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=False),
            OutputInfo(id=0, name="Stream", plugin="httpd", enabled=True),
        ]
        events, commands = [], []
        entered, release = asyncio.Event(), asyncio.Event()

        class Publisher:
            async def publish(self, event):
                events.append(event)

        manager = enable_manager(
            service, player, event_publisher=Publisher(), monotonic_clock=lambda: 0.0,
        )
        assert (await manager.get_state()).states[0].status == "INACTIVE"
        original_command = player.set_output_enabled

        async def command(output_id, enabled):
            commands.append((output_id, enabled))
            assert (await manager.get_state()).last_request.status == "PREPARING"
            if fault == "reject":
                raise PlayerCommandError("set_output_enabled", "command rejected")
            if fault != "ack-no-effect":
                await original_command(output_id, enabled)
            if fault == "timeout-after-effect":
                raise PlayerUnavailable("timeout after delivery")
            if fault == "readback-offline":
                player.disconnect()
            elif fault == "readback-fails-once":
                original_outputs = player.outputs
                count = 0

                async def outputs():
                    nonlocal count
                    count += 1
                    if count == 1:
                        raise PlayerUnavailable("readback interrupted")
                    return await original_outputs()

                monkeypatch.setattr(player, "outputs", outputs)
            elif fault == "after-status-fails":
                original_status = player.status
                count = 0

                async def status():
                    nonlocal count
                    count += 1
                    if count == 1:
                        raise PlayerUnavailable("preservation read interrupted")
                    return await original_status()

                monkeypatch.setattr(player, "status", status)
            elif fault == "cancel-after-effect":
                entered.set()
                await release.wait()

        monkeypatch.setattr(player, "set_output_enabled", command)
        if fault == "initial-offline":
            player.disconnect()
        task = asyncio.create_task(manager.set_enabled(OutputMode.NAS_DAC, True))
        if fault == "cancel-after-effect":
            await asyncio.wait_for(entered.wait(), 3)
            task.cancel()
        with pytest.raises(error_type):
            await asyncio.wait_for(task, 3)
        assert events == []
        assert await authority_snapshot(service) == before
        # Block subsequent reads: the failed command itself must have reconciled
        # the actual effect, rather than relying on the caller's next GET.
        failure_outputs = player.outputs

        async def offline_outputs():
            raise PlayerUnavailable("later read offline")

        monkeypatch.setattr(player, "outputs", offline_outputs)
        cached = await manager.get_state()
        assert cached.states[0].status == actual
        assert cached.states[0].stale is True
        assert cached.last_request.status == "SWITCH_FAILED"
        assert cached.last_request.error_code == code
        monkeypatch.setattr(player, "outputs", failure_outputs)
        observation = await manager.get_state()
        assert observation.last_request.status == "SWITCH_FAILED"
        assert observation.last_request.error_code == code
        assert observation.states[0].status == actual
        assert observation.states[0].stale is stale
        player.reconnect()
        assert (await player.status(), await player.queue_entries()) == facts
        assert (await player.outputs())[1].enabled is True
        assert commands == ([] if fault == "initial-offline" else [(37, True)])

        # Remove fault, then a new task proves rollback released the common lock.
        async def retry_command(output_id, enabled):
            commands.append((output_id, enabled))
            await original_command(output_id, enabled)

        monkeypatch.setattr(player, "set_output_enabled", retry_command)
        result = await asyncio.wait_for(
            asyncio.create_task(manager.set_enabled(OutputMode.NAS_DAC, True)), 3,
        )
        assert result.states[0].status == "ACTIVE"
        assert result.last_request.status == "SUCCEEDED"
        needs_write = fault in {"initial-offline", "ack-no-effect", "reject"}
        assert len(commands) == (0 if fault == "initial-offline" else 1) + int(needs_write)
        assert len(events) == int(needs_write)
        assert await authority_snapshot(service) == before

    asyncio.run(scenario())
