from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from server.app.models.hardware_volume import (
    HardwareVolumeControlSource,
    HardwareVolumeObservation,
    HardwareVolumeRequestState,
    HardwareVolumeRequestStatus,
    HardwareVolumeSnapshot,
    HardwareVolumeState,
    HardwareVolumeStatus,
)
from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.mock_mpd import MockMPD
from server.app.player.models import OutputInfo, PlayerStatus
from server.app.services.hardware_volume_manager import (
    HardwareVolumeError,
    HardwareVolumeManager,
)


class Lifecycle:
    def __init__(self):
        self.commits = []
        self.rollbacks = []

    def on_commit(self, callback):
        self.commits.append(callback)

    def on_rollback(self, callback):
        self.rollbacks.append(callback)


async def direct_runner(operation):
    return await operation(Lifecycle())


def capabilities(*, status=True, set_volume=True, outputs=True, queue=True):
    commands = set()
    if status:
        commands.update({"status", "currentsong"})
    if set_volume:
        commands.add("setvol")
    if outputs:
        commands.add("outputs")
    if queue:
        commands.add("playlistinfo")
    verified = {"queue_entries"} if queue else set()
    return replace(
        MPDCapabilities.from_commands(commands),
        verified_operations=frozenset(verified),
    )


def make_manager(
    player,
    *,
    enabled=True,
    caps=None,
    selector=None,
    clock=None,
    max_age=6,
    coordinator=None,
):
    caps = caps or capabilities()
    return HardwareVolumeManager(
        player=VerifiedPlayerPort(player, caps),
        capabilities=caps,
        enabled=enabled,
        selector=selector,
        operation_runner=direct_runner,
        coordinator=coordinator,
        observation_clock=clock,
        observation_max_age=max_age,
    )


def alsa_output(*, output_id=37, name="USB DAC", enabled=True, plugin="alsa"):
    return OutputInfo(id=output_id, name=name, plugin=plugin, enabled=enabled)


def test_hardware_volume_models_expose_the_documented_enums_and_unknown_values():
    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    state = HardwareVolumeState(
        status=HardwareVolumeStatus.UNAVAILABLE,
        volume_percent=None,
        updated_at=now,
        stale=True,
    )
    request = HardwareVolumeRequestState(
        requested_percent=80,
        status=HardwareVolumeRequestStatus.PREPARING,
        updated_at=now,
    )
    snapshot = HardwareVolumeSnapshot(state=state, last_request=request)
    observation = HardwareVolumeObservation(observed_at=None, freshness="unknown")

    assert [item.value for item in HardwareVolumeStatus] == [
        "AVAILABLE", "UNAVAILABLE", "UNSUPPORTED",
    ]
    assert [item.value for item in HardwareVolumeRequestStatus] == [
        "PREPARING", "SUCCEEDED", "FAILED",
    ]
    assert HardwareVolumeControlSource.MPD_HARDWARE_MIXER.value == "MPD_HARDWARE_MIXER"
    assert snapshot.state.volume_percent is None
    assert snapshot.state.stale is True
    assert snapshot.last_request.requested_percent == 80
    assert observation.freshness == "unknown"


@pytest.mark.parametrize("invalid", [True, False, 1.5, "50", -1, 101])
def test_hardware_volume_model_rejects_non_integer_or_out_of_range_percent(invalid):
    with pytest.raises(ValidationError):
        HardwareVolumeState(
            status="AVAILABLE",
            volume_percent=invalid,
            updated_at=datetime.now(timezone.utc),
        )


@pytest.mark.parametrize("invalid", [True, 1.5, "50", -1, 101])
def test_hardware_volume_request_rejects_non_integer_or_out_of_range_percent(invalid):
    with pytest.raises(ValidationError):
        HardwareVolumeRequestState(
            requested_percent=invalid,
            status="PREPARING",
            updated_at=datetime.now(timezone.utc),
        )


def test_enabled_manager_starts_unknown_until_a_valid_volume_sample_is_accepted():
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        manager = make_manager(player)
        cached = manager.get_cached_state()
        observation = await manager.get_observation()
        assert cached.state.status == HardwareVolumeStatus.UNAVAILABLE
        assert cached.state.volume_percent is None
        assert cached.state.stale is False
        assert observation.freshness == "unknown"

    asyncio.run(scenario())


def test_disabled_gate_returns_unsupported_without_reading_or_writing_mpd(monkeypatch):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        calls = []

        async def forbidden_status():
            calls.append("status")
            raise AssertionError("disabled hardware volume must not read MPD")

        async def forbidden_outputs():
            calls.append("outputs")
            raise AssertionError("disabled hardware volume must not read MPD")

        async def forbidden_set_volume(_):
            calls.append("set_volume")
            raise AssertionError("disabled hardware volume must not write MPD")

        monkeypatch.setattr(player, "status", forbidden_status)
        monkeypatch.setattr(player, "outputs", forbidden_outputs)
        monkeypatch.setattr(player, "set_volume", forbidden_set_volume)
        manager = make_manager(player, enabled=False)

        result = await manager.get_state()
        assert result.state.status == HardwareVolumeStatus.UNSUPPORTED
        assert result.state.volume_percent is None
        assert result.state.error_code == "HARDWARE_VOLUME_NOT_CONFIGURED"
        assert result.last_request is None
        with pytest.raises(HardwareVolumeError) as error:
            await manager.set_volume(42)
        assert error.value.code == "HARDWARE_VOLUME_NOT_CONFIGURED"
        failed = manager.get_cached_state().last_request
        assert failed.status == HardwareVolumeRequestStatus.FAILED
        assert failed.error_code == "HARDWARE_VOLUME_NOT_CONFIGURED"
        assert calls == []

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "caps, expected",
    [
        (capabilities(set_volume=False), "HARDWARE_VOLUME_UNAVAILABLE"),
        (capabilities(status=False), "HARDWARE_VOLUME_UNAVAILABLE"),
        (capabilities(outputs=False), "HARDWARE_VOLUME_UNAVAILABLE"),
    ],
)
def test_missing_mpd_capabilities_report_unavailable_without_fabricating_volume(caps, expected):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        manager = make_manager(player, caps=caps)
        result = await manager.get_state()
        assert result.state.status == HardwareVolumeStatus.UNAVAILABLE
        assert result.state.volume_percent is None
        assert result.state.error_code == expected

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "outputs, selector, expected",
    [
        ([], None, "HARDWARE_VOLUME_UNAVAILABLE"),
        ([alsa_output(), alsa_output(output_id=38, name="Second DAC")], None,
         "HARDWARE_VOLUME_OUTPUT_AMBIGUOUS"),
        ([alsa_output(enabled=False)], None, "HARDWARE_VOLUME_UNAVAILABLE"),
    ],
)
def test_no_ambiguous_or_disabled_alsa_target_is_available(outputs, selector, expected):
    async def scenario():
        player = MockMPD(outputs=outputs)
        manager = make_manager(player, selector=selector)
        result = await manager.get_state()
        assert result.state.status == HardwareVolumeStatus.UNAVAILABLE
        assert result.state.volume_percent is None
        assert result.state.error_code == expected
        if outputs and outputs[0].enabled is False:
            assert (await manager.get_observation()).freshness == "unknown"

    asyncio.run(scenario())


def test_selector_must_return_the_current_unique_alsa_candidate():
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        manager = make_manager(
            player,
            selector=lambda candidates: alsa_output(output_id=candidates[0].id),
        )
        result = await manager.get_state()
        assert result.state.status == HardwareVolumeStatus.UNAVAILABLE
        assert result.state.error_code == "HARDWARE_VOLUME_OUTPUT_AMBIGUOUS"

    asyncio.run(scenario())


def test_missing_status_volume_is_unknown_and_not_coerced_to_zero(monkeypatch):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        original_status = player.status

        async def status_without_volume():
            return (await original_status()).model_copy(update={"volume": None})

        monkeypatch.setattr(player, "status", status_without_volume)
        manager = make_manager(player)
        result = await manager.get_state()
        assert result.state.status == HardwareVolumeStatus.UNAVAILABLE
        assert result.state.volume_percent is None
        assert result.state.error_code == "HARDWARE_VOLUME_UNAVAILABLE"

    asyncio.run(scenario())


def test_fresh_read_returns_confirmed_mpd_volume_and_selected_output():
    async def scenario():
        player = MockMPD(outputs=[alsa_output(), alsa_output(
            output_id=0, name="HTTP Stream", plugin="httpd",
        )])
        await player.set_volume(61)
        manager = make_manager(player)
        result = await manager.get_state()

        assert result.state.status == HardwareVolumeStatus.AVAILABLE
        assert result.state.volume_percent == 61
        assert result.state.output_name == "USB DAC"
        assert result.state.output_plugin == "alsa"
        assert result.state.output_enabled is True
        assert result.state.control_source == HardwareVolumeControlSource.MPD_HARDWARE_MIXER
        assert result.state.stale is False
        assert result.state.error_code is None
        observation = await manager.get_observation()
        assert observation.freshness == "fresh"
        assert observation.error_code is None

    asyncio.run(scenario())


def test_stale_expiry_preserves_last_confirmed_value_with_stale_metadata():
    async def scenario():
        now = [datetime(2026, 11, 4, tzinfo=timezone.utc)]
        player = MockMPD(outputs=[alsa_output()])
        await player.set_volume(37)
        manager = make_manager(player, clock=lambda: now[0], max_age=6)
        fresh = await manager.get_state()
        assert fresh.state.volume_percent == 37

        now[0] += timedelta(seconds=6, milliseconds=1)
        observation = await manager.get_observation()
        cached = manager.get_cached_state()
        assert observation.freshness == "stale"
        assert cached.state.volume_percent == 37
        assert cached.state.stale is True
        assert cached.state.error_code == "HARDWARE_VOLUME_UNAVAILABLE"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "failure, expected",
    [
        ("disconnect", "PLAYER_UNAVAILABLE"),
        ("status", "PLAYER_COMMAND_ERROR"),
        ("outputs", "PLAYER_COMMAND_ERROR"),
    ],
)
def test_mpd_read_failures_preserve_last_value_but_mark_it_stale(failure, expected):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        await player.set_volume(47)
        manager = make_manager(player)
        assert (await manager.get_state()).state.volume_percent == 47
        if failure == "disconnect":
            player.disconnect()
        else:
            player.fail_next(failure)
        result = await manager.get_state()
        assert result.state.volume_percent == 47
        assert result.state.stale is True
        assert result.state.error_code == expected
        observation = await manager.get_observation()
        assert observation.freshness == "stale"
        assert observation.error_code == expected

    asyncio.run(scenario())


@pytest.mark.parametrize("volume", [0, 100])
def test_set_volume_confirms_exact_mpd_readback_at_boundaries(volume):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        manager = make_manager(player)
        result = await manager.set_volume(volume)
        assert (await player.status()).volume == volume
        assert result.state.status == HardwareVolumeStatus.AVAILABLE
        assert result.state.volume_percent == volume
        assert result.state.stale is False
        assert result.last_request.requested_percent == volume
        assert result.last_request.status == HardwareVolumeRequestStatus.SUCCEEDED

    asyncio.run(scenario())


def test_set_volume_does_not_report_success_when_mpd_readback_mismatches(monkeypatch):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        original_set_volume = player.set_volume

        async def acknowledge_without_change(_volume):
            return await original_set_volume(50)

        monkeypatch.setattr(player, "set_volume", acknowledge_without_change)
        manager = make_manager(player)
        with pytest.raises(HardwareVolumeError) as error:
            await manager.set_volume(72)
        result = manager.get_cached_state()
        assert error.value.code == "HARDWARE_VOLUME_RECONCILIATION_FAILED"
        assert result.state.stale is True
        assert result.last_request.status == HardwareVolumeRequestStatus.FAILED
        assert result.last_request.error_code == "HARDWARE_VOLUME_RECONCILIATION_FAILED"

    asyncio.run(scenario())


def test_write_is_rejected_before_setvol_when_current_mpd_volume_is_unknown(monkeypatch):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        calls = []
        original_set_volume = player.set_volume

        async def counted_set_volume(volume):
            calls.append(volume)
            await original_set_volume(volume)

        async def unknown_status():
            return PlayerStatus(state="stopped", volume=None)

        monkeypatch.setattr(player, "status", unknown_status)
        monkeypatch.setattr(player, "set_volume", counted_set_volume)
        manager = make_manager(player)
        with pytest.raises(HardwareVolumeError) as error:
            await manager.set_volume(19)
        assert error.value.code == "HARDWARE_VOLUME_UNAVAILABLE"
        assert calls == []
        assert manager.get_cached_state().last_request.status == HardwareVolumeRequestStatus.FAILED

    asyncio.run(scenario())


def test_mpd_setvol_failure_never_leaves_a_successful_request():
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        manager = make_manager(player)
        player.fail_next("set_volume", "MPD rejected setvol")
        with pytest.raises(HardwareVolumeError) as error:
            await manager.set_volume(23)
        result = manager.get_cached_state()
        assert error.value.code == "HARDWARE_VOLUME_WRITE_FAILED"
        assert result.last_request.status == HardwareVolumeRequestStatus.FAILED
        assert result.state.stale is True

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "outputs, expected",
    [
        ([], "HARDWARE_VOLUME_UNAVAILABLE"),
        ([alsa_output(), alsa_output(output_id=38, name="Second DAC")],
         "HARDWARE_VOLUME_OUTPUT_AMBIGUOUS"),
        ([alsa_output(enabled=False)], "HARDWARE_VOLUME_UNAVAILABLE"),
    ],
)
def test_set_volume_rejects_unavailable_target_before_calling_setvol(
    monkeypatch, outputs, expected,
):
    async def scenario():
        player = MockMPD(outputs=outputs)
        calls = []
        original = player.set_volume

        async def counted(volume):
            calls.append(volume)
            await original(volume)

        monkeypatch.setattr(player, "set_volume", counted)
        manager = make_manager(player)
        with pytest.raises(HardwareVolumeError) as error:
            await manager.set_volume(33)
        assert error.value.code == expected
        assert calls == []

    asyncio.run(scenario())


def test_set_volume_requires_runtime_verified_queue_capability():
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        manager = make_manager(player, caps=capabilities(queue=False))
        with pytest.raises(HardwareVolumeError) as error:
            await manager.set_volume(33)
        assert error.value.code == "HARDWARE_VOLUME_UNAVAILABLE"
        failed = manager.get_cached_state().last_request
        assert failed.status == HardwareVolumeRequestStatus.FAILED
        assert failed.error_code == "HARDWARE_VOLUME_UNAVAILABLE"
        assert (await player.status()).volume == 50

    asyncio.run(scenario())


def test_set_volume_does_not_swallow_process_exit(monkeypatch):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])

        async def stop_process(_volume):
            raise SystemExit(17)

        monkeypatch.setattr(player, "set_volume", stop_process)
        manager = make_manager(player)
        with pytest.raises(SystemExit) as error:
            await manager.set_volume(39)
        assert error.value.code == 17

    asyncio.run(scenario())


def test_set_volume_rejects_a_changed_output_target_after_write(monkeypatch):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        original_outputs = player.outputs
        output_reads = 0

        async def changing_outputs():
            nonlocal output_reads
            output_reads += 1
            if output_reads == 1:
                return await original_outputs()
            return [alsa_output(output_id=41, name="Replacement DAC")]

        monkeypatch.setattr(player, "outputs", changing_outputs)
        manager = make_manager(player)
        with pytest.raises(HardwareVolumeError) as error:
            await manager.set_volume(44)
        result = manager.get_cached_state()
        assert error.value.code == "HARDWARE_VOLUME_RECONCILIATION_FAILED"
        assert (await player.status()).volume == 44
        assert result.state.stale is True
        assert result.last_request.status == HardwareVolumeRequestStatus.FAILED

    asyncio.run(scenario())


def test_configured_selector_selects_its_current_alsa_candidate():
    async def scenario():
        player = MockMPD(outputs=[
            alsa_output(output_id=37, name="USB DAC A"),
            alsa_output(output_id=38, name="USB DAC B"),
            alsa_output(output_id=0, name="Stream", plugin="httpd"),
        ])
        manager = make_manager(
            player,
            selector=lambda candidates: next(
                output for output in candidates if output.name == "USB DAC B"
            ),
        )
        result = await manager.get_state()
        assert result.state.status == HardwareVolumeStatus.AVAILABLE
        assert result.state.output_name == "USB DAC B"
        assert result.state.output_plugin == "alsa"
        assert "output_id" not in HardwareVolumeState.model_fields

    asyncio.run(scenario())


def test_get_state_timeout_returns_unknown_or_last_known_stale_state(monkeypatch):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        manager = make_manager(player)

        async def blocked_status():
            await asyncio.Event().wait()

        monkeypatch.setattr(player, "status", blocked_status)
        result = await manager.get_state(read_timeout=0.001)
        observation = await manager.get_observation()
        assert result.state.volume_percent is None
        assert result.state.error_code == "PLAYER_TIMEOUT"
        assert result.state.stale is False
        assert observation.freshness == "unknown"
        assert observation.error_code == "PLAYER_TIMEOUT"

    asyncio.run(scenario())


def test_post_readback_playback_drift_fails_request_but_retains_the_confirmed_volume(monkeypatch):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        original_set_volume = player.set_volume

        async def set_volume_and_drift(volume):
            await original_set_volume(volume)
            await player.set_repeat(True)

        monkeypatch.setattr(player, "set_volume", set_volume_and_drift)
        manager = make_manager(player)
        with pytest.raises(HardwareVolumeError) as error:
            await manager.set_volume(52)
        cached = manager.get_cached_state()
        assert error.value.code == "HARDWARE_VOLUME_RECONCILIATION_FAILED"
        assert cached.state.volume_percent == 52
        assert cached.state.stale is True
        assert cached.last_request.status == HardwareVolumeRequestStatus.FAILED

    asyncio.run(scenario())


def test_newer_accepted_read_cannot_be_overwritten_by_an_older_slow_sample(monkeypatch):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        original_status = player.status
        first_started = asyncio.Event()
        release_first = asyncio.Event()
        calls = 0

        async def ordered_status():
            nonlocal calls
            calls += 1
            current = calls
            if current == 1:
                first_started.set()
                await release_first.wait()
            status = await original_status()
            return status.model_copy(update={"volume": 41 if current == 1 else 73})

        monkeypatch.setattr(player, "status", ordered_status)
        manager = make_manager(player)
        older_read = asyncio.create_task(manager.get_state())
        await asyncio.wait_for(first_started.wait(), 1)
        newer = await manager.get_state()
        release_first.set()
        older = await older_read

        assert newer.state.volume_percent == 73
        assert older.state.volume_percent == 73
        assert manager.get_cached_state().state.volume_percent == 73

    asyncio.run(scenario())


def test_read_started_before_a_volume_write_is_discarded_after_the_write(monkeypatch):
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        original_outputs = player.outputs
        first_outputs_started = asyncio.Event()
        release_first_outputs = asyncio.Event()
        output_calls = 0

        async def ordered_outputs():
            nonlocal output_calls
            output_calls += 1
            if output_calls == 1:
                first_outputs_started.set()
                await release_first_outputs.wait()
            return await original_outputs()

        monkeypatch.setattr(player, "outputs", ordered_outputs)
        manager = make_manager(player)
        older_read = asyncio.create_task(manager.get_state())
        await asyncio.wait_for(first_outputs_started.wait(), 1)
        written = await manager.set_volume(73)
        release_first_outputs.set()
        old_result = await older_read

        assert written.state.volume_percent == 73
        assert old_result.state.volume_percent == 73
        assert manager.get_cached_state().state.volume_percent == 73

    asyncio.run(scenario())


def test_set_volume_rejects_replaced_output_even_when_name_and_plugin_match(monkeypatch):
    async def scenario():
        player = MockMPD(outputs=[alsa_output(output_id=37)])
        original_outputs = player.outputs
        output_reads = 0

        async def replacement_with_same_name():
            nonlocal output_reads
            output_reads += 1
            if output_reads == 1:
                return await original_outputs()
            return [alsa_output(output_id=41)]

        monkeypatch.setattr(player, "outputs", replacement_with_same_name)
        manager = make_manager(player)
        with pytest.raises(HardwareVolumeError) as error:
            await manager.set_volume(46)
        cached = manager.get_cached_state()
        assert error.value.code == "HARDWARE_VOLUME_RECONCILIATION_FAILED"
        assert cached.state.volume_percent == 50
        assert cached.state.stale is True
        assert cached.last_request.status == HardwareVolumeRequestStatus.FAILED

    asyncio.run(scenario())


def test_stale_disconnect_preserves_the_last_confirmed_control_source():
    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        manager = make_manager(player)
        fresh = await manager.get_state()
        assert fresh.state.control_source == HardwareVolumeControlSource.MPD_HARDWARE_MIXER
        player.disconnect()
        stale = await manager.get_state()
        assert stale.state.control_source == HardwareVolumeControlSource.MPD_HARDWARE_MIXER
        assert stale.state.volume_percent == 50
        assert stale.state.stale is True

    asyncio.run(scenario())


def test_mpd_disconnect_during_setvol_is_not_misreported_as_an_ack_rejection(monkeypatch):
    from server.app.player.ports import PlayerUnavailable

    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        manager = make_manager(player)

        async def unavailable(_volume):
            raise PlayerUnavailable("MPD connection was lost during setvol")

        monkeypatch.setattr(player, "set_volume", unavailable)
        with pytest.raises(HardwareVolumeError) as error:
            await manager.set_volume(48)
        cached = manager.get_cached_state()
        assert error.value.code == "PLAYER_UNAVAILABLE"
        assert cached.last_request.status == HardwareVolumeRequestStatus.FAILED
        assert cached.last_request.error_code == "PLAYER_UNAVAILABLE"
        assert cached.state.volume_percent == 50
        assert cached.state.stale is True

    asyncio.run(scenario())


def test_mpd_disconnect_after_setvol_is_not_misreported_as_readback_drift(monkeypatch):
    from server.app.player.ports import PlayerUnavailable

    async def scenario():
        player = MockMPD(outputs=[alsa_output()])
        manager = make_manager(player)
        original_status = player.status
        reads = 0

        async def disconnect_on_readback():
            nonlocal reads
            reads += 1
            if reads == 2:
                raise PlayerUnavailable("MPD connection was lost before readback")
            return await original_status()

        monkeypatch.setattr(player, "status", disconnect_on_readback)
        with pytest.raises(HardwareVolumeError) as error:
            await manager.set_volume(48)
        cached = manager.get_cached_state()
        assert error.value.code == "PLAYER_UNAVAILABLE"
        assert cached.last_request.status == HardwareVolumeRequestStatus.FAILED
        assert cached.last_request.error_code == "PLAYER_UNAVAILABLE"
        assert cached.state.volume_percent == 50
        assert cached.state.stale is True

    asyncio.run(scenario())
