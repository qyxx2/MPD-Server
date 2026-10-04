from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from server.app.models.output import OutputMode
from server.app.player.capabilities import MPDCapabilities
from server.app.player.models import OutputInfo
from server.app.services.output_manager import OutputManager
from server.tests.invariants.test_output_serialization import authority_snapshot
from server.tests.invariants.test_realtime_observation import setup_observation
from server.tests.support.playback import run


def setup_output(real_client):
    playback, player, library, coordinator, clock = setup_observation(real_client)
    player._outputs = [OutputInfo(id=1, name='DAC', plugin='alsa', enabled=True)]
    assert hasattr(OutputManager, 'get_cached_state'), 'Output observation cache facade is missing'
    manager = OutputManager(
        player=player,
        capabilities=replace(MPDCapabilities.from_commands({'outputs', 'enableoutput', 'disableoutput',
                                                   'status', 'currentsong', 'playlistinfo'}), verified_operations=frozenset({'queue_entries', 'set_output_enabled'})),
        operation_runner=playback.run_output_operation,
        coordinator=coordinator, observation_clock=clock,
        event_publisher=coordinator, monotonic_clock=lambda: 0,
    )
    return playback, player, library, coordinator, clock, manager


def test_unknown_output_cache_read_does_not_invent_an_observation_change(real_client):
    _, _, _, coordinator, _, manager = setup_output(real_client)
    marker = coordinator.marker()
    observation = run(manager.get_observation())
    assert observation.observed_at is None and observation.freshness == 'unknown'
    assert coordinator.marker() == marker


def test_output_control_and_observation_share_delivery_without_history(real_client):
    """Lost observation invalidation or bypassing outer commit breaks Output/current preservation."""
    playback, player, _, coordinator, clock, manager = setup_output(real_client)

    async def scenario():
        before = await authority_snapshot(playback)
        subscription = coordinator.subscribe()
        unknown = await manager.get_observation()
        assert unknown.freshness == 'unknown' and unknown.observed_at is None
        first = await manager.get_state()
        assert first.states[0].status == 'ACTIVE'
        assert (await manager.get_observation()).freshness == 'fresh'
        assert subscription.pending.domains == {'output'}
        marker = coordinator.marker()
        clock.advance(1)
        await manager.get_state()
        assert coordinator.marker() == marker, 'timestamp-only update invalidated output'
        await manager.set_enabled(OutputMode.NAS_DAC, False)
        assert manager.get_cached_state().states[0].status == 'INACTIVE'
        assert manager.get_cached_state().last_request.status == 'SUCCEEDED'
        assert coordinator.marker().sequence > marker.sequence
        # External observation is independent of the successful control receipt.
        receipt = manager.get_cached_state().last_request.model_copy(deep=True)
        player._outputs[0].enabled = True
        await manager.get_state()
        assert manager.get_cached_state().states[0].status == 'ACTIVE'
        assert manager.get_cached_state().last_request == receipt
        assert await authority_snapshot(playback) == before
        assert coordinator.marker().library_revision == coordinator.marker().playlist_revision == 0
        detached = manager.get_cached_state()
        detached.states[0].status = 'UNAVAILABLE'
        assert manager.get_cached_state().states[0].status == 'ACTIVE'

    run(scenario())


def test_output_outer_rollback_preserves_external_fact_and_retry_does_not_repeat_control(real_client, monkeypatch):
    from server.app.repositories.database import run_transaction
    from server.app.repositories.idempotency_repository import IdempotencyRepository
    from server.tests.invariants.test_output_event_transactions import create_terminal

    playback, player, library, coordinator, _, manager = setup_output(real_client)

    async def scenario():
        await manager.get_state()
        before = await authority_snapshot(playback)
        marker = coordinator.marker()
        records = IdempotencyRepository(library.path)
        controls = []
        control = player.set_output_enabled

        async def recorded_control(output_id, enabled):
            controls.append((output_id, enabled))
            await control(output_id, enabled)

        monkeypatch.setattr(player, 'set_output_enabled', recorded_control)

        async def rejected(_):
            await manager.set_enabled(OutputMode.NAS_DAC, False)
            await create_terminal(records)
            assert coordinator.marker() == marker
            raise RuntimeError('outer rejected')

        with pytest.raises(RuntimeError, match='outer rejected'):
            await run_transaction(library.path, rejected)
        assert coordinator.marker() == marker
        assert await records.get_by_key('confirmed') is None
        assert manager.get_cached_state().last_request.status == 'SWITCH_FAILED'
        assert manager.get_cached_state().states[0].stale
        assert (await player.outputs())[0].enabled is False
        await manager.get_state()
        assert (await manager.get_observation()).freshness == 'fresh'
        assert manager.get_cached_state().last_request.status == 'SWITCH_FAILED'
        receipt = await manager.set_enabled(OutputMode.NAS_DAC, False)
        assert receipt.last_request.status == 'SUCCEEDED'
        assert controls == [(1, False)]
        assert await authority_snapshot(playback) == before

    run(scenario())


def test_output_publisher_failure_and_terminal_replay_preserve_committed_receipt(real_client, monkeypatch, caplog):
    from server.app.main import app
    from server.tests.support.playback import mutate

    playback, player, _, coordinator, _, manager = setup_output(real_client)
    monkeypatch.setattr(app.state, 'output_manager', manager)

    class FailingPublisher:
        async def publish(self, event):
            raise RuntimeError('downstream offline')

    coordinator._event_publisher = FailingPublisher()
    before = run(authority_snapshot(playback))
    response = mutate(real_client[0], 'PUT', '/api/system/output',
                      {'mode': 'NAS_DAC', 'enabled': False}, key='b9-output')
    assert response.status_code == 200, response.text
    assert 'downstream offline' in caplog.text
    marker = coordinator.marker()

    async def unexpected(*args, **kwargs):
        raise AssertionError('terminal replay performed external I/O')

    for method in ('outputs', 'status', 'queue_entries', 'set_output_enabled'):
        monkeypatch.setattr(player, method, unexpected)
    replay = mutate(real_client[0], 'PUT', '/api/system/output',
                    {'mode': 'NAS_DAC', 'enabled': False}, key='b9-output')
    assert replay.status_code == 200 and replay.json() == response.json()
    assert coordinator.marker() == marker
    assert run(authority_snapshot(playback)) == before


def test_blocked_output_sample_releases_business_boundary_and_rejects_late_control_fact(real_client, monkeypatch):
    _playback, player, _, coordinator, _, manager = setup_output(real_client)

    async def scenario():
        sampled, release = asyncio.Event(), asyncio.Event()
        outputs = player.outputs
        task = None

        async def blocked():
            result = await outputs()
            if not sampled.is_set():
                sampled.set()
                await release.wait()
            return result

        monkeypatch.setattr(player, 'outputs', blocked)
        task = asyncio.create_task(manager.get_state())
        try:
            await asyncio.wait_for(sampled.wait(), 1)
            await asyncio.wait_for(manager.set_enabled(OutputMode.NAS_DAC, False), 0.2)
            marker = coordinator.marker()
            release.set()
            await asyncio.wait_for(task, 1)
            assert manager.get_cached_state().states[0].status == 'INACTIVE'
            assert coordinator.marker() == marker, 'late pre-control output was accepted'
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)

    run(scenario())


def test_output_sample_started_during_control_cannot_overwrite_confirmed_result(real_client, monkeypatch):
    _, player, _, _, _, manager = setup_output(real_client)

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        attempted = asyncio.Event()
        outputs = player.outputs
        runner = manager.operation_runner
        first = True
        control = None
        observation = None

        async def held_control_read():
            nonlocal first
            result = await outputs()
            if asyncio.current_task() is control and first:
                first = False
                entered.set()
                await release.wait()
            return result

        async def attempted_boundary(operation):
            if asyncio.current_task() is observation:
                attempted.set()
            return await runner(operation)

        monkeypatch.setattr(player, 'outputs', held_control_read)
        monkeypatch.setattr(manager, 'operation_runner', attempted_boundary)
        control = asyncio.create_task(manager.set_enabled(OutputMode.NAS_DAC, False))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            observation = asyncio.create_task(manager.get_state())
            await asyncio.wait_for(attempted.wait(), 1)
            release.set()
            await asyncio.wait_for(control, 1)
            await asyncio.wait_for(observation, 1)
            assert manager.get_cached_state().states[0].status == 'INACTIVE'
            assert (await player.outputs())[0].enabled is False
            assert (await manager.get_observation()).freshness == 'fresh'
        finally:
            release.set()
            await asyncio.gather(control, *([observation] if observation else []), return_exceptions=True)

    run(scenario())


@pytest.mark.parametrize('failure', ['disconnect', 'timeout'])
def test_output_failure_and_expiry_register_matching_snapshot_waterline(real_client, monkeypatch, failure):
    playback, player, library, coordinator, clock, manager = setup_output(real_client)

    async def scenario():
        from server.app.services.library_service import LibraryService
        from server.app.services.state_service import StateService

        await manager.get_state()
        marker = coordinator.marker()
        clock.advance(7)
        state = StateService(
            coordinator=coordinator, queue_manager=playback.queue_manager,
            history_service=playback.history_service, library_service=LibraryService(library),
            output_snapshot=manager.get_cached_state, output_observation=manager.get_observation,
            playback_service=playback,
        )
        snapshot = await state.get_full_snapshot()
        assert snapshot.output_observation.freshness == 'stale'
        assert snapshot.output.states[0].stale is True
        assert snapshot.sequence == marker.sequence + 1 == coordinator.marker().sequence
        before = await authority_snapshot(playback)
        if failure == 'disconnect':
            player.disconnect()
        else:
            async def blocked():
                await asyncio.Event().wait()
            monkeypatch.setattr(player, 'outputs', blocked)
        await manager.get_state(read_timeout=0.01)
        observation = await manager.get_observation()
        assert observation.freshness == 'stale' and observation.error_code is not None
        assert observation.observed_at == snapshot.output_observation.observed_at
        assert manager.get_cached_state().states[0].status == 'ACTIVE'
        assert await authority_snapshot(playback) == before
        marker = coordinator.marker()
        await manager.get_observation()
        assert coordinator.marker() == marker

    run(scenario())


def test_observer_timeout_cannot_reuse_an_abandoned_mpd_response():
    """Cancelled MPD reads must abandon the stream before the next fact is accepted."""
    from server.app.player.mpd_adapter import MPDAdapter

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        handlers = set()
        commands = []

        async def handle(reader, writer):
            task = asyncio.current_task()
            handlers.add(task)
            try:
                writer.write(b'OK MPD 0.23.5\n')
                await writer.drain()
                while line := await reader.readline():
                    commands.append(line)
                    first = len(commands) == 1
                    if first:
                        entered.set()
                        await release.wait()
                    enabled = 1 if first else 0
                    writer.write(('outputid: 1\noutputname: DAC\nplugin: alsa\n'
                                  f'outputenabled: {enabled}\nOK\n').encode())
                    await writer.drain()
            except (ConnectionError, OSError):
                pass
            finally:
                writer.close()
                await writer.wait_closed()
                handlers.discard(task)

        async def runner(operation):
            return await operation(None)

        server = await asyncio.start_server(handle, '127.0.0.1', 0)
        adapter = MPDAdapter('127.0.0.1', port=server.sockets[0].getsockname()[1])
        manager = OutputManager(player=adapter, capabilities=MPDCapabilities.from_commands({'outputs'}),
                                operation_runner=runner)
        try:
            failed = await manager.get_state(read_timeout=0.05)
            assert entered.is_set() and failed.states[0].error_code == 'PLAYER_TIMEOUT'
            release.set()
            fresh = await asyncio.wait_for(manager.get_state(read_timeout=1), 2)
            assert fresh.states[0].status == 'INACTIVE', 'previous timed-out ACTIVE response was reused'
            assert (await manager.get_observation()).freshness == 'fresh'
            assert commands == [b'outputs\n', b'outputs\n']
        finally:
            release.set()
            await adapter.close()
            server.close()
            await server.wait_closed()
            await asyncio.gather(*handlers, return_exceptions=True)

    run(scenario())
