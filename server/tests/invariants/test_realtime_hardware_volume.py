from __future__ import annotations

import asyncio
from dataclasses import replace

from server.app.main import app
from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.models import OutputInfo
from server.app.services.hardware_volume_manager import HardwareVolumeManager
from server.app.services.state_observer import StateObserver
from server.app.services.state_service import StateService
from server.tests.invariants.test_realtime_output import setup_output
from server.tests.support.playback import run


def setup_hardware_volume(real_client):
    playback, player, library, coordinator, clock, output = setup_output(real_client)
    player._outputs = [OutputInfo(id=1, name="DAC", plugin="alsa", enabled=True)]
    capabilities = replace(
        MPDCapabilities.from_commands({"status", "currentsong", "setvol", "outputs", "playlistinfo"}),
        verified_operations=frozenset({"queue_entries"}),
    )
    manager = HardwareVolumeManager(
        player=player,
        capabilities=capabilities,
        enabled=True,
        operation_runner=playback.run_output_operation,
        coordinator=coordinator,
        observation_clock=clock,
    )
    return playback, player, library, coordinator, clock, output, manager


def test_full_state_snapshot_reads_detached_hardware_volume_cache(real_client, monkeypatch):
    playback, player, library, coordinator, clock, output, hardware = setup_hardware_volume(real_client)

    async def scenario():
        await hardware.get_state()
        state = StateService(
            coordinator=coordinator,
            queue_manager=playback.queue_manager,
            history_service=playback.history_service,
            library_service=library,
            playback_service=playback,
            output_snapshot=output.get_cached_state,
            output_observation=output.get_observation,
            hardware_volume_snapshot=hardware.get_cached_state,
            hardware_volume_observation=hardware.get_observation,
        )
        expected = hardware.get_cached_state()

        async def forbidden(*args, **kwargs):
            raise AssertionError("a full snapshot must not perform MPD hardware-volume I/O")

        monkeypatch.setattr(player, "status", forbidden)
        monkeypatch.setattr(player, "outputs", forbidden)
        snapshot = await state.get_full_snapshot()
        assert snapshot.hardware_volume == expected
        assert snapshot.hardware_volume.state.volume_percent == 50
        assert snapshot.hardware_volume_observation.freshness == "fresh"
        snapshot.hardware_volume.state.volume_percent = 1
        assert hardware.get_cached_state() == expected
        clock.advance(7)
        stale = await state.get_full_snapshot()
        assert stale.hardware_volume.state.volume_percent == 50
        assert stale.hardware_volume.state.stale is True
        assert stale.hardware_volume_observation.freshness == "stale"
        assert stale.sequence == coordinator.marker().sequence
        assert stale.sequence == snapshot.sequence + 1
        assert (await state.get_full_snapshot()).sequence == stale.sequence

    run(scenario())


def test_hardware_volume_net_changes_and_freshness_transitions_publish_one_domain(real_client):
    _playback, player, _, coordinator, clock, _, hardware = setup_hardware_volume(real_client)

    async def scenario():
        subscription = coordinator.subscribe()
        first = await hardware.get_state()
        assert first.state.volume_percent == 50
        first_frame = subscription.queue.get_nowait()
        assert first_frame.domains == {"hardware_volume"}
        assert first_frame.revisions == {"library": 0, "playlist": 0}
        marker = coordinator.marker()

        # Time-only samples must not advance the sequence or enqueue a frame.
        clock.advance(1)
        await hardware.get_state()
        assert coordinator.marker() == marker
        assert subscription.queue.empty()

        # Simulate a volume change made outside the server's write endpoint.
        await player.set_volume(72)
        changed = await hardware.get_state()
        assert changed.state.volume_percent == 72
        changed_frame = subscription.queue.get_nowait()
        assert changed_frame.domains == {"hardware_volume"}
        marker = coordinator.marker()
        assert not subscription.queue.qsize()

        # Expiry and recovery are each a single net change, not repeated polls.
        clock.advance(7)
        stale = await hardware.get_observation()
        assert stale.freshness == "stale"
        stale_frame = subscription.queue.get_nowait()
        assert stale_frame.domains == {"hardware_volume"}
        marker = coordinator.marker()
        assert await hardware.get_observation() == stale
        assert coordinator.marker() == marker
        assert subscription.queue.empty()

        fresh = await hardware.get_state()
        assert fresh.state.volume_percent == 72 and fresh.state.stale is False
        fresh_frame = subscription.queue.get_nowait()
        assert fresh_frame.domains == {"hardware_volume"}
        assert coordinator.marker().sequence == marker.sequence + 1
        assert coordinator.marker().library_revision == coordinator.marker().playlist_revision == 0

    run(scenario())


def test_state_observer_samples_volume_once_with_shared_budget_and_cancels_cleanly():
    async def scenario():
        now = [0.0]
        calls = []
        sleeps = asyncio.Queue()
        permits = asyncio.Queue()
        second_volume_sample = asyncio.Event()
        volume_cancelled = asyncio.Event()

        class PlaybackProbe:
            async def observe(self, *, read_timeout):
                calls.append(("playback", read_timeout))
                now[0] += 0.5

            async def get_observation(self):
                calls.append(("playback_cache", None))

        class OutputProbe:
            async def get_state(self, *, read_timeout):
                calls.append(("output", read_timeout))
                now[0] += 1.5

            async def get_observation(self):
                calls.append(("output_cache", None))

        class VolumeProbe:
            samples = 0

            async def get_state(self, *, read_timeout):
                self.samples += 1
                calls.append(("hardware_volume", read_timeout))
                if self.samples == 1:
                    raise RuntimeError("temporary hardware-volume read failure")
                second_volume_sample.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    volume_cancelled.set()

            async def get_observation(self):
                calls.append(("hardware_volume_cache", None))

        async def sleep(delay):
            await sleeps.put(delay)
            await permits.get()

        playback, output, volume = PlaybackProbe(), OutputProbe(), VolumeProbe()
        observer = StateObserver(
            playback=playback,
            output=output,
            hardware_volume=volume,
            interval=1,
            read_budget=5,
            sleep=sleep,
            monotonic_clock=lambda: now[0],
        )
        task = asyncio.create_task(observer.run())
        try:
            assert await asyncio.wait_for(sleeps.get(), 1) == 1
            assert calls[:3] == [
                ("playback", 5),
                ("output", 4.5),
                ("hardware_volume", 3),
            ]
            assert calls[3:] == [
                ("playback_cache", None),
                ("output_cache", None),
                ("hardware_volume_cache", None),
            ]
            # Hardware failure was isolated: playback and output completed.
            assert volume.samples == 1
            await permits.put(None)
            await asyncio.wait_for(second_volume_sample.wait(), 1)
            await asyncio.wait_for(observer.close(), 1)
            assert task.done() and volume_cancelled.is_set()
        finally:
            await observer.close()
            await asyncio.gather(task, return_exceptions=True)

    run(scenario())


def test_state_observer_marks_hardware_volume_stale_after_failed_sample(real_client):
    playback, player, _, coordinator, _, output, hardware = setup_hardware_volume(real_client)

    async def scenario():
        await hardware.get_state()
        assert (await hardware.get_observation()).freshness == "fresh"
        player.disconnect()
        sleeps = asyncio.Queue()
        never_release = asyncio.Event()

        async def sleep(delay):
            await sleeps.put(delay)
            await never_release.wait()

        observer = StateObserver(
            playback=playback,
            output=output,
            hardware_volume=hardware,
            sleep=sleep,
        )
        task = asyncio.create_task(observer.run())
        try:
            await asyncio.wait_for(sleeps.get(), 1)
            observation = await hardware.get_observation()
            assert observation.freshness == "stale"
            assert observation.error_code == "PLAYER_UNAVAILABLE"
            assert hardware.get_cached_state().state.stale is True
            assert coordinator.marker().sequence >= 1
        finally:
            await observer.close()
            await asyncio.gather(task, return_exceptions=True)

    run(scenario())


def test_websocket_volume_change_emits_v1_invalidation_without_hardware_payload(real_client, monkeypatch):
    client, _, player, playback = real_client
    player._outputs = [OutputInfo(id=37, name="USB DAC", plugin="alsa", enabled=True)]
    capabilities = replace(
        MPDCapabilities.from_commands(
            {"status", "currentsong", "setvol", "outputs", "playlistinfo"}
        ),
        verified_operations=frozenset({"queue_entries"}),
    )
    coordinator = app.state.realtime_coordinator
    manager = HardwareVolumeManager(
        player=VerifiedPlayerPort(player, capabilities),
        capabilities=capabilities,
        enabled=True,
        operation_runner=playback.run_output_operation,
        coordinator=coordinator,
    )
    monkeypatch.setattr(app.state.state_service, "_hardware_volume_snapshot", manager.get_cached_state)
    monkeypatch.setattr(app.state.state_service, "_hardware_volume_observation", manager.get_observation)

    with client.websocket_connect("/api/realtime") as socket:
        snapshot = socket.receive_json()
        assert snapshot["type"] == "snapshot"
        result = run(manager.set_volume(63))
        assert result.state.volume_percent == 63
        frame = socket.receive_json()

    assert frame["type"] == "invalidate"
    assert frame["protocol_version"] == 1
    assert frame["domains"] == ["hardware_volume"]
    assert frame["sequence"] > snapshot["sequence"]
    assert frame["revisions"] == snapshot["state"]["revisions"]
    assert "state" not in frame and "hardware_volume" not in frame
