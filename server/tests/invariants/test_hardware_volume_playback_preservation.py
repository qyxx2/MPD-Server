from __future__ import annotations

import asyncio
from dataclasses import replace

from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.models import OutputInfo
from server.app.services.hardware_volume_manager import HardwareVolumeManager
from server.tests.invariants.test_output_serialization import authority_snapshot
from server.tests.support.playback import start


def test_hardware_volume_write_changes_only_volume_and_preserves_queue_history_and_playback(
    real_client, monkeypatch,
):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        await service.seek(17)
        before_authority = await authority_snapshot(service)
        before_status = await player.status()
        before_entries = await player.queue_entries()
        player._outputs = [OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=True)]
        capabilities = replace(
            MPDCapabilities.from_commands({
                "status", "currentsong", "setvol", "outputs", "playlistinfo",
            }),
            verified_operations=frozenset({"queue_entries"}),
        )
        manager = HardwareVolumeManager(
            player=VerifiedPlayerPort(player, capabilities),
            capabilities=capabilities,
            enabled=True,
            operation_runner=service.run_output_operation,
            selector=None,
        )

        result = await manager.set_volume(64)
        after_status = await player.status()
        assert result.state.volume_percent == 64
        assert after_status.volume == 64
        assert after_status.model_dump(exclude={"volume", "elapsed_seconds"}) == (
            before_status.model_dump(exclude={"volume", "elapsed_seconds"})
        )
        assert await player.queue_entries() == before_entries
        assert await authority_snapshot(service) == before_authority

    asyncio.run(scenario())


def test_hardware_volume_write_allows_natural_elapsed_progress(real_client, monkeypatch):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        await service.seek(17)
        player._outputs = [OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=True)]
        capabilities = replace(
            MPDCapabilities.from_commands({
                "status", "currentsong", "setvol", "outputs", "playlistinfo",
            }),
            verified_operations=frozenset({"queue_entries"}),
        )
        original_status = player.status
        reads = 0
        async def status_with_natural_progress():
            nonlocal reads
            reads += 1
            value = await original_status()
            if reads == 2:
                value.elapsed_seconds = (value.elapsed_seconds or 0) + 1.0
            return value
        monkeypatch.setattr(player, "status", status_with_natural_progress)
        times = iter([100.0, 101.2])
        manager = HardwareVolumeManager(
            player=VerifiedPlayerPort(player, capabilities),
            capabilities=capabilities,
            enabled=True,
            operation_runner=service.run_output_operation,
            observation_clock=None,
            monotonic_clock=lambda: next(times),
        )
        result = await manager.set_volume(55)
        assert result.state.volume_percent == 55
        assert reads == 2

    asyncio.run(scenario())


def test_hardware_volume_transaction_rollback_invalidates_success_receipt(real_client):
    from server.app.repositories.database import run_transaction

    _, _, player, service = real_client

    async def scenario():
        player._outputs = [OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=True)]
        capabilities = replace(
            MPDCapabilities.from_commands({
                "status", "currentsong", "setvol", "outputs", "playlistinfo",
            }),
            verified_operations=frozenset({"queue_entries"}),
        )
        manager = HardwareVolumeManager(
            player=VerifiedPlayerPort(player, capabilities),
            capabilities=capabilities,
            enabled=True,
            operation_runner=service.run_output_operation,
        )
        path = service.queue_manager.queue_repository.path

        async def outer(_connection):
            result = await manager.set_volume(69)
            assert result.last_request.status.value == "SUCCEEDED"
            raise RuntimeError("outer transaction rollback witness")

        try:
            await run_transaction(path, outer)
        except RuntimeError as exc:
            assert str(exc) == "outer transaction rollback witness"
        else:
            raise AssertionError("outer transaction should roll back")

        cached = manager.get_cached_state()
        assert (await player.status()).volume == 69
        assert cached.state.volume_percent == 69
        assert cached.state.stale is True
        assert cached.state.error_code == "HARDWARE_VOLUME_TRANSACTION_FAILED"
        assert cached.last_request.status.value == "FAILED"
        assert cached.last_request.error_code == "HARDWARE_VOLUME_TRANSACTION_FAILED"

    asyncio.run(scenario())


def test_hardware_volume_manager_stages_only_net_hardware_volume_invalidations(real_client):
    import pytest

    _, _, player, service = real_client

    async def scenario():
        player._outputs = [OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=True)]
        capabilities = replace(
            MPDCapabilities.from_commands({
                "status", "currentsong", "setvol", "outputs", "playlistinfo",
            }),
            verified_operations=frozenset({"queue_entries"}),
        )
        coordinator = service._coordinator
        manager = HardwareVolumeManager(
            player=VerifiedPlayerPort(player, capabilities),
            capabilities=capabilities,
            enabled=True,
            operation_runner=service.run_output_operation,
            coordinator=coordinator,
        )
        subscription = coordinator.subscribe()
        try:
            await manager.set_volume(63)
            invalidation = await asyncio.wait_for(subscription.receive(), 1)
            assert invalidation.domains == frozenset({"hardware_volume"})

            await manager.get_state()
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(subscription.receive(), 0.05)
        finally:
            coordinator.unsubscribe(subscription)

    asyncio.run(scenario())


def test_application_composes_hardware_volume_with_existing_output_selection_and_runner(real_client):
    from server.app.main import app

    _, _, _, service = real_client
    manager = app.state.hardware_volume_manager
    output_manager = app.state.output_manager
    assert manager.enabled is False
    assert manager.player is output_manager.player
    assert manager.capabilities is output_manager.capabilities
    assert manager.selector is output_manager.selector
    assert manager.operation_runner.__self__ is service
    assert manager.operation_runner.__func__ is service.run_output_operation.__func__


def test_hardware_volume_write_serializes_with_concurrent_playback_mutation(
    real_client, monkeypatch,
):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        player._outputs = [OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=True)]
        capabilities = replace(
            MPDCapabilities.from_commands({
                "status", "currentsong", "setvol", "outputs", "playlistinfo",
            }),
            verified_operations=frozenset({"queue_entries"}),
        )
        manager = HardwareVolumeManager(
            player=VerifiedPlayerPort(player, capabilities),
            capabilities=capabilities,
            enabled=True,
            operation_runner=service.run_output_operation,
        )
        entered = asyncio.Event()
        release = asyncio.Event()
        pause_entered = asyncio.Event()
        original_set = player.set_volume
        original_pause = player.pause

        async def blocked_set_volume(volume):
            entered.set()
            await release.wait()
            await original_set(volume)

        async def tracked_pause():
            pause_entered.set()
            await original_pause()

        monkeypatch.setattr(player, "set_volume", blocked_set_volume)
        monkeypatch.setattr(player, "pause", tracked_pause)
        volume_task = asyncio.create_task(manager.set_volume(71))
        playback_task = None
        try:
            await asyncio.wait_for(entered.wait(), 1)

            async def pause():
                return await service.pause()

            playback_task = asyncio.create_task(pause())
            await asyncio.sleep(0)
            assert not playback_task.done()
            assert not pause_entered.is_set()
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(
                volume_task, *([playback_task] if playback_task else []),
            ), 3)

        assert pause_entered.is_set()
        assert (await player.status()).volume == 71
        assert (await player.status()).state.value == "paused"

    asyncio.run(scenario())


def test_disabled_hardware_volume_request_commits_unsupported_request_invalidation(
    real_client, monkeypatch,
):
    from server.app.services.hardware_volume_manager import HardwareVolumeError

    _, _, player, service = real_client

    async def scenario():
        capabilities = replace(
            MPDCapabilities.from_commands({
                "status", "currentsong", "setvol", "outputs", "playlistinfo",
            }),
            verified_operations=frozenset({"queue_entries"}),
        )
        calls = []

        async def forbidden_status():
            calls.append("status")
            raise AssertionError("disabled mode must not read MPD")

        async def forbidden_outputs():
            calls.append("outputs")
            raise AssertionError("disabled mode must not read MPD")

        async def forbidden_set_volume(_volume):
            calls.append("set_volume")
            raise AssertionError("disabled mode must not write MPD")

        monkeypatch.setattr(player, "status", forbidden_status)
        monkeypatch.setattr(player, "outputs", forbidden_outputs)
        monkeypatch.setattr(player, "set_volume", forbidden_set_volume)
        manager = HardwareVolumeManager(
            player=VerifiedPlayerPort(player, capabilities),
            capabilities=capabilities,
            enabled=False,
            operation_runner=service.run_output_operation,
            coordinator=service._coordinator,
        )
        subscription = service._coordinator.subscribe()
        try:
            try:
                await manager.set_volume(57)
            except HardwareVolumeError as exc:
                assert exc.code == "HARDWARE_VOLUME_NOT_CONFIGURED"
            else:
                raise AssertionError("disabled hardware volume request must fail")
            invalidation = await asyncio.wait_for(subscription.receive(), 1)
            assert invalidation.domains == frozenset({"hardware_volume"})
            cached = manager.get_cached_state()
            assert cached.state.status.value == "UNSUPPORTED"
            assert cached.last_request.status.value == "FAILED"
            assert cached.last_request.error_code == "HARDWARE_VOLUME_NOT_CONFIGURED"
            assert calls == []
        finally:
            service._coordinator.unsubscribe(subscription)

    asyncio.run(scenario())


def test_hardware_volume_write_accepts_unchanged_elapsed_from_coarse_mpd_status(
    real_client, monkeypatch,
):
    client, _, player, service = real_client
    start(client)

    async def scenario():
        await service.seek(17)
        player._outputs = [OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=True)]
        capabilities = replace(
            MPDCapabilities.from_commands({
                "status", "currentsong", "setvol", "outputs", "playlistinfo",
            }),
            verified_operations=frozenset({"queue_entries"}),
        )
        original_status = player.status
        status_reads = 0
        first_elapsed = None

        async def status_with_coarse_elapsed():
            nonlocal status_reads, first_elapsed
            value = await original_status()
            status_reads += 1
            if status_reads == 1:
                first_elapsed = value.elapsed_seconds
            else:
                value.elapsed_seconds = first_elapsed
            return value

        monkeypatch.setattr(player, "status", status_with_coarse_elapsed)
        times = iter([100.0, 100.3])
        manager = HardwareVolumeManager(
            player=VerifiedPlayerPort(player, capabilities),
            capabilities=capabilities,
            enabled=True,
            operation_runner=service.run_output_operation,
            monotonic_clock=lambda: next(times),
        )

        result = await manager.set_volume(55)

        assert result.state.volume_percent == 55
        assert status_reads == 2
        after_status = await original_status()
        assert after_status.state.value == "playing"
        assert after_status.volume == 55

    asyncio.run(scenario())

