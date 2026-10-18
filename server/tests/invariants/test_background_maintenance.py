from __future__ import annotations

import asyncio

import pytest

from server.app.main import app
from server.app.models.queue import PlaybackContext
from server.app.player.ports import PlayerUnavailable
from server.app.repositories.database import run_transaction, transaction_identity
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_d6_autoplay import prepare
from server.tests.invariants.test_d6_recovery import capture_controls
from server.tests.support.playback import run


@pytest.mark.parametrize("size", [8, 400])
def test_background_sample_releases_database_for_local_snapshot(real_client, monkeypatch, size):
    player, service = prepare(real_client, pending=5)
    run(service.play_context(PlaybackContext(
        context_id="background", source_type="SONGS",
        ordered_song_ids=tuple("abcdef"[i % 6] for i in range(size)),
    )))
    before = server_snapshot(service)
    read = player.read_execution_sample
    controls = capture_controls(monkeypatch, player)

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        calls = 0

        async def blocked():
            nonlocal calls
            calls += 1
            sample = await read()
            entered.set()
            await release.wait()
            return sample

        monkeypatch.setattr(player, 'read_execution_sample', blocked)
        maintenance = asyncio.create_task(service.maintain_execution())
        try:
            await asyncio.wait_for(entered.wait(), 1)

            snapshot = await asyncio.wait_for(app.state.state_service.get_full_snapshot(), 1)
            assert snapshot.queue == before[0]
            assert snapshot.playback == before[1]
        finally:
            release.set()
            result = await maintenance
        assert result.outcome == 'UNCHANGED'
        assert calls == 1

    run(scenario())
    assert server_snapshot(service) == before
    assert controls == []


@pytest.mark.parametrize('change', ['queue', 'current', 'stop', 'binding'])
def test_background_discards_sample_after_business_change(real_client, monkeypatch, change):
    player, service = prepare(real_client, pending=5)
    read = player.read_execution_sample
    controls = capture_controls(monkeypatch, player)

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        task = None
        calls = 0

        async def blocked():
            nonlocal calls
            sample = await read()
            if asyncio.current_task() is task:
                calls += 1
                entered.set()
                await release.wait()
            return sample

        monkeypatch.setattr(player, 'read_execution_sample', blocked)
        task = asyncio.create_task(service.maintain_execution())
        try:
            await asyncio.wait_for(entered.wait(), 1)
            if change == 'queue':
                await asyncio.wait_for(service.add_to_queue('b'), 1)
            elif change == 'current':
                await asyncio.wait_for(service.next(), 1)
            elif change == 'stop':
                await asyncio.wait_for(service.stop(), 1)
            else:
                async def invalidate(_):
                    service._recovery.invalidate_binding()
                await asyncio.wait_for(run_transaction(service._recovery.path, invalidate), 1)
            expected_queue = await service.queue_manager.get_snapshot()
            expected_state = await service.queue_manager.get_playback_state()
            expected_observation = await service.get_observation()
            prefix = list(controls)
        finally:
            release.set()
            result = await task
        assert not result.reconciliation_required
        assert calls == 1
        assert await service.queue_manager.get_snapshot() == expected_queue
        assert await service.queue_manager.get_playback_state() == expected_state
        assert await service.get_observation() == expected_observation
        assert controls == prefix

    run(scenario())


@pytest.mark.parametrize('failure', ['disconnect', 'cancel', 'timeout'])
def test_background_read_failure_retires_binding_without_control(real_client, monkeypatch, failure):
    player, service = prepare(real_client, pending=5)
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)

    async def scenario():
        entered = asyncio.Event()

        async def failed():
            entered.set()
            if failure == 'disconnect':
                raise PlayerUnavailable('lost connection')
            await asyncio.Event().wait()

        monkeypatch.setattr(player, 'read_execution_sample', failed)
        task = asyncio.create_task(service.maintain_execution(
            read_timeout=0.05 if failure == 'timeout' else None,
        ))
        await asyncio.wait_for(entered.wait(), 1)
        if failure == 'cancel':
            task.cancel()
        with pytest.raises(PlayerUnavailable if failure == 'disconnect' else
                           TimeoutError if failure == 'timeout' else asyncio.CancelledError):
            await task
        assert await service.get_execution_binding() is None

    run(scenario())
    assert server_snapshot(service) == before
    assert controls == []


@pytest.mark.parametrize('drift', ['random', 'repeat', 'single', 'consume', 'error', 'epoch', 'partition', 'version', 'pause', 'advance'])
def test_background_drift_uses_protected_fallback(real_client, monkeypatch, drift):
    player, service = prepare(real_client, pending=5)
    binding = run(service.get_execution_binding())
    if drift in {'random', 'repeat'}:
        run(getattr(player, f'set_{drift}')(True))
    elif drift == 'pause':
        run(player.pause())
    elif drift == 'advance':
        run(player.queue_play(binding.entries[1][1]))
    read = player.read_execution_sample
    calls = 0
    held = []

    async def changed():
        nonlocal calls
        calls += 1
        try:
            transaction_identity(service._recovery.path)
        except RuntimeError:
            held.append(False)
        else:
            held.append(True)
        sample = await read()
        updates = {
            'single': {'single': '1'}, 'consume': {'consume': True},
            'error': {'error': 'decoder error'}, 'epoch': {'connection_epoch': 'other'},
            'partition': {'partition': 'other'}, 'version': {'playlist_version': sample.playlist_version + 1},
        }
        return sample.model_copy(update=updates.get(drift, {}))

    monkeypatch.setattr(player, 'read_execution_sample', changed)
    controls = capture_controls(monkeypatch, player)
    before = server_snapshot(service)
    result = run(service.maintain_execution())
    assert calls > 1  # the external check cannot authorize a control or transport write
    assert held == [False] + [True] * (calls - 1)
    if drift in {'pause', 'advance'}:
        assert result.outcome == 'APPLIED'
        assert run(service.queue_manager.get_playback_state()).state == ('PAUSED' if drift == 'pause' else 'PLAYING')
        assert run(service.queue_manager.get_playback_state()).song_id == ('a' if drift == 'pause' else 'b')
        assert not any(name in {'play', 'queue_play', 'pause', 'seek'} for name, _, _ in controls)
    else:
        assert result.outcome == 'UNKNOWN' and result.reconciliation_required
        assert server_snapshot(service) == before
        assert controls == []


@pytest.mark.parametrize("change", ["pause", "next"])
def test_failed_background_read_fences_binding_not_transport_state(real_client, monkeypatch, change):
    player, service = prepare(real_client, pending=5)
    read = player.read_execution_sample

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        task = None

        async def blocked():
            if asyncio.current_task() is task:
                entered.set()
                await release.wait()
                raise PlayerUnavailable('old read failed')
            return await read()

        monkeypatch.setattr(player, 'read_execution_sample', blocked)
        task = asyncio.create_task(service.maintain_execution())
        try:
            await asyncio.wait_for(entered.wait(), 1)
            await asyncio.wait_for(getattr(service, change)(), 1)
            expected = await service.get_execution_binding()
            assert expected is not None
        finally:
            release.set()
            with pytest.raises(PlayerUnavailable):
                await task
        if change == 'pause':
            assert await service.get_execution_binding() is None
        else:
            assert await service.get_execution_binding() == expected

    run(scenario())


def test_background_sample_before_rolled_back_pause_cannot_clear_diagnostic(real_client, monkeypatch):
    player, service = prepare(real_client, pending=5)
    run(service.observe())
    number = service._observations.begin_diagnostic()
    run(service._observations.diagnose('SYNC_FAILED', service._recovery.business_generation, number))
    read = player.read_execution_sample

    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        task = None

        async def blocked():
            sample = await read()
            if asyncio.current_task() is task:
                entered.set()
                await release.wait()
            return sample

        monkeypatch.setattr(player, 'read_execution_sample', blocked)
        task = asyncio.create_task(service.maintain_execution())
        try:
            await asyncio.wait_for(entered.wait(), 1)

            async def abort(_):
                await service.pause()
                raise RuntimeError('outer rollback')

            with pytest.raises(RuntimeError, match='outer rollback'):
                await asyncio.wait_for(run_transaction(service._recovery.path, abort), 1)
            before = await service.get_observation()
            assert before.sync_status == 'SYNC_FAILED'
        finally:
            release.set()
            await task
        assert await service.get_observation() == before

    run(scenario())


def test_obsolete_unknown_intent_does_not_disable_background_check(real_client, monkeypatch):
    player, service = prepare(real_client, pending=5)
    add = player.queue_add

    async def lost(uri):
        await add(uri)
        raise PlayerUnavailable('lost add response')

    with monkeypatch.context() as fault:
        fault.setattr(player, 'queue_add', lost)
        with pytest.raises(PlayerUnavailable):
            run(service.add_to_queue('b'))
    assert service._recovery.unknown_executions
    run(service.play_context(PlaybackContext(
        context_id='new-takeover', source_type='SONGS', ordered_song_ids=tuple('abcdef'),
    )))
    read = player.read_execution_sample
    calls = 0

    async def counted():
        nonlocal calls
        calls += 1
        return await read()

    monkeypatch.setattr(player, 'read_execution_sample', counted)
    assert run(service.maintain_execution()).outcome == 'UNCHANGED'
    assert calls == 1
