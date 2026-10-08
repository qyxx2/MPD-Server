from __future__ import annotations

import asyncio
import importlib
import importlib.util
from types import SimpleNamespace

import pytest

from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_d6_autoplay import prepare, seed_candidates
from server.tests.invariants.test_d6_recovery import capture_controls
from server.tests.support.playback import run


def runner_type():
    name = 'server.app.services.playback_recovery_runner'
    assert importlib.util.find_spec(name) is not None, 'independent recovery runner missing'
    return importlib.import_module(name).PlaybackRecoveryRunner


async def snapshot(service):
    return (
        await service.queue_manager.queue_repository.get_snapshot(),
        await service.queue_manager.get_playback_state(),
        await service.history_service.list_history(),
        service.history_service.active_event,
        service.history_service.session_id,
    )


class FakeClock:
    def __init__(self):
        self.now = 0
        self.delays = asyncio.Queue()
        self.permits = asyncio.Queue()

    def __call__(self):
        return self.now

    async def sleep(self, delay):
        self.now += delay
        await self.delays.put(delay)
        await self.permits.get()

    async def next_delay(self):
        return await asyncio.wait_for(self.delays.get(), 2)


def test_single_runner_refills_without_clients_and_never_restarts_stop(real_client, monkeypatch):
    runner_class = runner_type()
    player, service = prepare(real_client)
    seed_candidates(player, service)
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)

    async def scenario():
        clock = FakeClock()
        active = maximum = 0
        method = service.maintain_execution
        planner = service.autoplay.plan_refill
        planning, release = asyncio.Event(), asyncio.Event()

        async def blocked(context, snapshot):
            result = await planner(context, snapshot)
            planning.set()
            await release.wait()
            return result

        async def counted(*, read_timeout=None):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            try:
                return await method(read_timeout=read_timeout)
            finally:
                active -= 1

        monkeypatch.setattr(service, 'maintain_execution', counted)
        monkeypatch.setattr(service.autoplay, 'plan_refill', blocked)
        runner = runner_class(service, sleep=clock.sleep, clock=clock)
        task = asyncio.create_task(runner.run())
        try:
            await asyncio.wait_for(planning.wait(), 2)
            with pytest.raises(RuntimeError, match='owner|running'):
                await runner.run()
            duplicate = runner_class(service, sleep=clock.sleep, clock=clock)
            with pytest.raises(RuntimeError, match='owner|running'):
                await duplicate.run()
            stop = asyncio.create_task(service.stop())
            await asyncio.sleep(0)
            assert not stop.done()
            release.set()
            assert await clock.next_delay() == 1
            await stop
            assert maximum == 1 and active == 0
            committed = await service.queue_manager.get_snapshot()
            assert committed.revision > before[0].revision
            assert len([i for i in committed.items if i.source == 'AUTOPLAY']) == 5
            prefix = list(controls)
            await service.observe()
            assert controls == prefix  # observer remains read-only
            await clock.permits.put(None)
            assert await clock.next_delay() == 1
            assert controls == prefix
            assert not any(name in {'play', 'queue_play'} for name, _, _ in controls)
        finally:
            await runner.close()
            await task
        assert task.done() and active == 0
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]

    run(scenario())


@pytest.mark.parametrize('case', ['backoff', 'budget', 'precommit', 'postcommit', 'postcommit-timeout'])
def test_runner_budget_backoff_and_shutdown_preserve_commit(real_client, monkeypatch, case):
    runner_class = runner_type()
    player, service = prepare(real_client)
    seed_candidates(player, service)
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)

    async def scenario():
        clock = FakeClock()
        entered = asyncio.Event()
        budgets = []
        method = service.maintain_execution
        calls = 0

        async def facade(*, read_timeout=None):
            nonlocal calls
            calls += 1
            budgets.append(read_timeout)
            if case == 'backoff':
                if calls <= 7:
                    if calls % 2:
                        raise RuntimeError('temporary failure')
                    return SimpleNamespace(reconciliation_required=True)
                return SimpleNamespace(reconciliation_required=False)
            return await method(read_timeout=read_timeout)

        monkeypatch.setattr(service, 'maintain_execution', facade)
        if case == 'budget':
            async def blocked():
                entered.set()
                await asyncio.Event().wait()
            monkeypatch.setattr(player, 'read_execution_sample', blocked)
        elif case == 'precommit':
            async_wait = asyncio.Event()
            add = player.queue_add
            async def sent(uri):
                result = await add(uri)
                entered.set()
                await async_wait.wait()
                return result
            monkeypatch.setattr(player, 'queue_add', sent)
        elif case in {'postcommit', 'postcommit-timeout'}:
            class Publisher:
                async def publish(self, event):
                    entered.set()
                    await asyncio.Event().wait()
            service._event_publisher = Publisher()
        runner = runner_class(service, budget=0.02 if case in {'budget', 'postcommit-timeout'} else 5,
                              sleep=clock.sleep, clock=clock)
        task = asyncio.create_task(runner.run())
        try:
            if case == 'backoff':
                delays = []
                for _ in range(7):
                    delays.append(await clock.next_delay())
                    await clock.permits.put(None)
                assert delays == [1, 2, 4, 8, 16, 30, 30]
                assert await clock.next_delay() == 1
                assert budgets == [5] * 8
            else:
                await asyncio.wait_for(entered.wait(), 2)
                if case == 'postcommit-timeout':
                    assert await clock.next_delay() == 1
                if case == 'budget':
                    assert await clock.next_delay() == 1
                    assert await snapshot(service) == before
                    assert budgets == [0.02]
        finally:
            await runner.close()
            await task
        prefix = list(controls)
        assert not any(name == 'stop' for name, _, _ in controls)
        assert task.done()
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        if case == 'precommit':
            assert await snapshot(service) == before
            assert not any(key.endswith('/refill') for key in service._recovery.execution_receipts)
            result = await method()
            assert result.outcome == 'UNKNOWN' and controls == prefix  # lost add response stays fenced
        elif case in {'postcommit', 'postcommit-timeout'}:
            committed = await snapshot(service)
            assert committed[0].revision == before[0].revision + 1
            assert committed[2:] == before[2:]
            key = next(key for key in service._recovery.execution_receipts if key.endswith('/refill'))
            assert service._recovery.get_execution_receipt(key).outcome == 'REPLAYED'
            assert (await method()).outcome == 'UNCHANGED'
            assert await snapshot(service) == committed and controls == prefix

    run(scenario())


@pytest.mark.parametrize('case', ['disabled', 'no-capabilities', 'incomplete', 'enabled', 'duplicate', 'startup-failure', 'immediate-shutdown'])
def test_lifespan_injection_single_owner_and_cleanup(tmp_path, monkeypatch, case):
    from dataclasses import replace

    from fastapi import FastAPI

    from server.app import main
    from server.app.player.capabilities import MPDCapabilities
    from server.app.player.mock_mpd import MockMPD
    from server.app.player.models import OutputInfo

    runner_type()
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 's9-lifecycle.db'))

    async def scenario():
        player = MockMPD(outputs=[OutputInfo(id=1, name='DAC', plugin='alsa', enabled=True)])
        controls = capture_controls(monkeypatch, player)
        def forbidden(*args, **kwargs):
            raise AssertionError('injected local Port ignored')
        monkeypatch.setattr(main, 'MPDAdapter', forbidden)
        capabilities = replace(
            MPDCapabilities.from_commands({'status', 'currentsong', 'playlistinfo', 'addid', 'deleteid', 'moveid', 'playid', 'outputs'}),
            verified_operations=frozenset({'queue_entries', 'queue_add', 'queue_delete', 'queue_move', 'queue_play'}),
        )
        def application():
            app = FastAPI()
            app.state.player = player
            app.state.recovery_enabled = case != 'disabled'
            if case != 'no-capabilities':
                app.state.mpd_capabilities = (MPDCapabilities.from_commands({'status'}) if case == 'incomplete' else capabilities)
            return app
        app = application()
        if case == 'incomplete':
            with pytest.raises(RuntimeError, match='capabilit|verified'):
                async with main.lifespan(app):
                    raise AssertionError('invalid capabilities accepted')
            return
        if case == 'startup-failure':
            initialize = main.initialize_database
            async def fail(path):
                raise RuntimeError('startup failed')
            with monkeypatch.context() as fault:
                fault.setattr(main, 'initialize_database', fail)
                with pytest.raises(RuntimeError, match='startup failed'):
                    async with main.lifespan(app):
                        pass
            monkeypatch.setattr(main, 'initialize_database', initialize)
        async with main.lifespan(app):
            observer = app.state.state_observer_task
            task = app.state.playback_recovery_task
            runner = app.state.playback_recovery_runner
            if case in {'disabled', 'no-capabilities'}:
                assert task is None and runner is None
            else:
                assert task is not None and runner is not None
                if case != 'immediate-shutdown':
                    await asyncio.sleep(0)
                    assert not task.done()
                if case == 'duplicate':
                    with pytest.raises(RuntimeError, match='owner'):
                        async with main.lifespan(application()):
                            raise AssertionError('second control owner accepted')
            assert controls == []
        assert observer.done()
        if task is not None:
            assert task.done()
        assert controls == []  # closing never sends Stop
        # A released owner can be acquired by the next lifespan.
        async with main.lifespan(application()):
            pass
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]

    run(scenario())


def test_unknown_tick_only_rechecks_observation_with_remaining_budget():
    runner_class = runner_type()

    async def scenario():
        clock = FakeClock()
        budgets = []
        class Facade:
            async def maintain_execution(self, *, read_timeout):
                budgets.append(('maintain', read_timeout))
                clock.now += 2
                return SimpleNamespace(reconciliation_required=True)

            async def observe(self, *, read_timeout):
                budgets.append(('observe', read_timeout))
        runner = runner_class(Facade(), clock=clock, sleep=clock.sleep)
        task = asyncio.create_task(runner.run())
        try:
            assert await clock.next_delay() == 1
            assert budgets == [('maintain', 5), ('observe', 3)]
        finally:
            await runner.close()
            await task

    run(scenario())


@pytest.mark.parametrize('phase', ['ack', 'confirmed', 'queue-write'])
def test_shutdown_preserves_owned_prefix_for_retry(real_client, monkeypatch, phase):
    runner_class = runner_type()
    player, service = prepare(real_client)
    seed_candidates(player, service)
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)

    async def scenario():
        entered = asyncio.Event()
        with monkeypatch.context() as fault:
            if phase == 'queue-write':
                write = service.queue_manager.queue_repository.add_autoplay_batch
                async def blocked(*args, **kwargs):
                    result = await write(*args, **kwargs)
                    entered.set()
                    await asyncio.Event().wait()
                    return result
                fault.setattr(service.queue_manager.queue_repository, 'add_autoplay_batch', blocked)
            else:
                read = player.read_execution_sample
                async def blocked():
                    result = await read()
                    receipts = service._recovery.command_receipts
                    matched = [r for key, rows in receipts.items() if key.endswith('/refill') for r in rows.values() if r.phase == phase]
                    if matched:
                        entered.set()
                        await asyncio.Event().wait()
                    return result
                fault.setattr(player, 'read_execution_sample', blocked)
            runner = runner_class(service)
            task = asyncio.create_task(runner.run())
            await asyncio.wait_for(entered.wait(), 2)
            await runner.close()
            await task
        assert await snapshot(service) == before
        assert not any(key.endswith('/refill') for key in service._recovery.execution_receipts)
        assert not any(name == 'stop' for name, _, _ in controls)
        result = await service.maintain_execution()
        assert result.outcome == 'APPLIED'
        assert sum(name == 'queue_add' for name, _, _ in controls) == 5
        assert (await snapshot(service))[0].revision == before[0].revision + 1

    run(scenario())
