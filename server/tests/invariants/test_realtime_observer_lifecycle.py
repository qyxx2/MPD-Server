from __future__ import annotations

import asyncio
import importlib
import importlib.util

import pytest

from server.app.player.ports import PlayerUnavailable
from server.tests.invariants.test_output_serialization import authority_snapshot
from server.tests.invariants.test_realtime_observation import setup_observation
from server.tests.invariants.test_realtime_output import setup_output
from server.tests.support.playback import run


def test_observation_budget_degrades_but_shutdown_cancellation_does_not(real_client, monkeypatch):
    """An outer timeout must not leave the previous sample fresh or become Stop."""
    playback, player, _, coordinator, clock = setup_observation(real_client)

    async def scenario():
        await playback.observe()
        before = await authority_snapshot(playback)
        marker = coordinator.marker()
        entered = asyncio.Event()

        async def blocked():
            entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(player, 'read_execution_sample', blocked)
        failed = await playback.observe(read_timeout=0.01)
        assert failed.freshness == 'stale'
        assert failed.error_code == 'PLAYER_TIMEOUT'
        assert failed.observed_at == clock()
        assert coordinator.marker().sequence == marker.sequence + 1
        task = asyncio.create_task(playback.observe(read_timeout=5))
        await entered.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError('shutdown cancellation was swallowed')
        assert await playback.get_observation() == failed
        # Read preservation without querying the deliberately blocked Port.
        monkeypatch.undo()
        assert await authority_snapshot(playback) == before

    run(scenario())


def test_one_domain_cache_failure_does_not_kill_retry_loop(real_client, monkeypatch):
    from server.app.services.state_observer import StateObserver

    playback, _, _, _, _, manager = setup_output(real_client)

    async def scenario():
        runner = manager.operation_runner
        sleeps, permits = asyncio.Queue(), asyncio.Queue()
        failures = 2

        async def failed_runner(operation):
            nonlocal failures
            if failures:
                failures -= 1
                raise RuntimeError('temporary output acceptance failure')
            return await runner(operation)

        async def sleep(delay):
            await sleeps.put(delay)
            await permits.get()

        monkeypatch.setattr(manager, 'operation_runner', failed_runner)
        observer = StateObserver(playback=playback, output=manager, sleep=sleep)
        task = asyncio.create_task(observer.run())
        try:
            await asyncio.wait_for(sleeps.get(), 0.2)
            assert not task.done()
            assert (await playback.get_observation()).freshness == 'fresh'
            await permits.put(None)
            await asyncio.wait_for(sleeps.get(), 0.2)
            assert (await manager.get_observation()).freshness == 'fresh'
        finally:
            await observer.close()
            await asyncio.gather(task, return_exceptions=True)

    run(scenario())


def test_round_budget_is_shared_and_output_timeout_retries_independently(real_client, monkeypatch):
    from server.app.services.state_observer import StateObserver

    playback, player, _, _, clock, manager = setup_output(real_client)

    async def scenario():
        sample, outputs = player.read_execution_sample, player.outputs
        sleeps, permits = asyncio.Queue(), asyncio.Queue()
        cancelled = asyncio.Event()
        samples = 0

        async def slow_sample():
            result = await sample()
            clock.advance(0.015)
            return result

        async def blocked_output():
            nonlocal samples
            samples += 1
            if samples == 1:
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
            return await outputs()

        async def sleep(delay):
            await sleeps.put(delay)
            await permits.get()

        monkeypatch.setattr(player, 'read_execution_sample', slow_sample)
        monkeypatch.setattr(player, 'outputs', blocked_output)
        observer = StateObserver(playback=playback, output=manager, read_budget=0.02,
                                 monotonic_clock=lambda: clock().timestamp(), sleep=sleep)
        task = asyncio.create_task(observer.run())
        try:
            await asyncio.wait_for(sleeps.get(), 0.2)
            assert cancelled.is_set()
            assert (await playback.get_observation()).freshness == 'fresh'
            output = await manager.get_observation()
            assert output.freshness == 'unknown' and output.error_code == 'PLAYER_TIMEOUT'
            assert output.observed_at is None
            await permits.put(None)
            await asyncio.wait_for(sleeps.get(), 0.2)
            assert (await manager.get_observation()).freshness == 'fresh'
            assert (await playback.get_observation()).freshness == 'fresh'
        finally:
            await observer.close()
            await asyncio.gather(task, return_exceptions=True)

    run(scenario())


def test_composition_root_starts_one_sampler_without_clients_and_awaits_shutdown(tmp_path, monkeypatch):
    from fastapi import FastAPI

    from server.app import main
    from server.app.player.capabilities import MPDCapabilities
    from server.app.player.mock_mpd import MockMPD
    from server.app.player.models import OutputInfo

    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'composition.db'))

    async def scenario():
        sampled = asyncio.Event()
        player = MockMPD(outputs=[OutputInfo(id=1, name='DAC', plugin='alsa', enabled=True)])
        outputs = player.outputs

        async def observed_outputs():
            sampled.set()
            return await outputs()

        monkeypatch.setattr(player, 'outputs', observed_outputs)
        monkeypatch.setattr(main, 'MPDAdapter', lambda *args, **kwargs: player)
        application = FastAPI()
        application.state.mpd_capabilities = MPDCapabilities.from_commands({'outputs'})
        async with main.lifespan(application):
            assert hasattr(application.state, 'state_observer'), 'composition root has no observer'
            await asyncio.wait_for(sampled.wait(), 1)
            coordinator = application.state.realtime_coordinator
            subscription = coordinator.subscribe()
            assert application.state.library_scanner.coordinator is coordinator
            assert application.state.playlist_service._coordinator is coordinator
            assert application.state.playback_service._coordinator is coordinator
            task = application.state.state_observer_task
            assert not task.done()
            snapshot = await application.state.state_service.get_full_snapshot()
            assert snapshot.output.states[0].status == 'ACTIVE'
            assert snapshot.output_observation.freshness == 'fresh'
            assert snapshot.playback is None and not snapshot.history.has_entries
        assert task.done()
        assert not subscription.valid and subscription.pending is None
        assert (await player.status()).state.value == 'stopped'

    run(scenario())


def test_injected_playback_freshness_age_expires_in_shared_boundary(real_client):
    from server.app.services.playback_service import PlaybackService

    original, player, library, coordinator, clock = setup_observation(real_client)
    playback = PlaybackService(
        queue_manager=original.queue_manager, history_service=original.history_service,
        autoplay=original.autoplay, player=player, library_repository=library,
        coordinator=coordinator, observation_clock=clock, observation_max_age=2,
    )

    async def scenario():
        await playback.start_track('a')
        await playback.observe()
        marker = coordinator.marker()
        before = await authority_snapshot(playback)
        clock.advance(2)
        assert (await playback.get_observation()).freshness == 'fresh'
        assert coordinator.marker() == marker
        clock.advance(0.1)
        assert (await playback.get_observation()).freshness == 'stale'
        assert coordinator.marker().sequence == marker.sequence + 1
        assert await authority_snapshot(playback) == before

    run(scenario())


def test_single_observer_retries_and_shutdown_preserves_playback(real_client, monkeypatch):
    """One-domain failure, duplicate loop or shutdown Stop would corrupt observed/business state."""
    from server.app.main import app
    from server.app.repositories.idempotency_repository import IdempotencyRepository
    from server.tests.invariants.test_output_event_transactions import create_terminal

    playback, player, library, coordinator, clock, manager = setup_output(real_client)
    module_name = 'server.app.services.state_observer'
    assert importlib.util.find_spec(module_name) is not None, 'single process StateObserver is missing'
    observer_type = importlib.import_module(module_name).StateObserver

    async def scenario():
        playlist = await app.state.playlist_service.create_playlist('observer-preserve')
        await app.state.playlist_service.add_song(playlist.playlist_id, 'a')
        await app.state.playlist_service.set_favorite('a', True)
        songs = await library.list_songs()
        playlists = await app.state.playlist_service.revision_content()
        records = IdempotencyRepository(library.path)
        terminal = await create_terminal(records)
        before = await authority_snapshot(playback)
        facts = await player.status(), await player.queue_entries()
        original_sample = player.read_execution_sample
        commands = []
        check = player._check

        def read_only_commands(command):
            commands.append(command)
            return check(command)

        monkeypatch.setattr(player, '_check', read_only_commands)
        sleeps, permits = asyncio.Queue(), asyncio.Queue()
        entered, cancelled = asyncio.Event(), asyncio.Event()
        calls = 0
        active = 0
        maximum = 0

        async def sample():
            nonlocal calls, active, maximum
            calls += 1
            active += 1
            maximum = max(maximum, active)
            try:
                if calls == 1:
                    raise PlayerUnavailable('offline')
                if calls == 3:
                    entered.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        cancelled.set()
                return await original_sample()
            finally:
                active -= 1

        async def sleep(delay):
            await sleeps.put(delay)
            await permits.get()
            clock.advance(delay)

        monkeypatch.setattr(player, 'read_execution_sample', sample)
        observer = observer_type(playback=playback, output=manager, sleep=sleep,
                                 monotonic_clock=lambda: clock().timestamp())
        task = asyncio.create_task(observer.run())
        try:
            assert await asyncio.wait_for(sleeps.get(), 1) == 1
            assert (await playback.get_observation()).error_code == 'PLAYER_UNAVAILABLE'
            assert (await manager.get_observation()).freshness == 'fresh'
            with pytest.raises(RuntimeError, match='running'):
                await observer.run()
            await permits.put(None)
            assert await asyncio.wait_for(sleeps.get(), 1) == 1
            recovered = await playback.get_observation()
            assert recovered.actual_freshness == 'fresh'
            # A read after a connection gap restores facts, never the occurrence
            # binding or its progress (Playback §8.9.2 / Architecture §12.3.1).
            assert recovered.freshness == 'unknown'
            assert recovered.bound_queue_item_id is None
            assert recovered.reconciliation_required is True
            await permits.put(None)
            await asyncio.wait_for(entered.wait(), 1)
            await asyncio.wait_for(observer.close(), 1)
            assert task.done() and cancelled.is_set() and active == 0 and maximum == 1
            assert await authority_snapshot(playback) == before
            assert await library.list_songs() == songs
            assert await app.state.playlist_service.revision_content() == playlists
            assert await records.get_by_key('confirmed') == terminal
            assert set(commands) <= {'status', 'read_execution_sample', 'outputs', 'queue_entries'}
            monkeypatch.undo()
            assert (await player.status(), await player.queue_entries()) == facts
            assert coordinator.marker().library_revision == coordinator.marker().playlist_revision == 0
            await observer.close()
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    run(scenario())
