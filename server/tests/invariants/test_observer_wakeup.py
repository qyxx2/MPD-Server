"""B6-A: committed changes wake the single, generation-safe observer."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from server.app.repositories.database import on_transaction_commit, run_transaction
from server.app.services.state_observer import StateObserver
from server.tests.invariants.test_realtime_observation import setup_observation
from server.tests.support.playback import run


def test_requests_interrupt_idle_and_coalesce_during_sampling():
    async def scenario():
        entered, permits, sleeps = asyncio.Queue(), asyncio.Queue(), asyncio.Queue()
        active = maximum = count = 0

        async def observe(**kwargs):
            nonlocal active, maximum, count
            active += 1
            maximum = max(maximum, active)
            count += 1
            await entered.put(count)
            try:
                await permits.get()
            finally:
                active -= 1

        async def cached(**kwargs):
            pass

        async def sleep(delay):
            await sleeps.put(delay)
            await asyncio.Event().wait()

        observer = StateObserver(
            playback=SimpleNamespace(observe=observe, get_observation=cached),
            output=SimpleNamespace(get_state=cached, get_observation=cached), sleep=sleep,
        )
        task = asyncio.create_task(observer.run())
        try:
            assert await asyncio.wait_for(entered.get(), 1) == 1
            await permits.put(None)
            await asyncio.wait_for(sleeps.get(), 1)
            observer.request_observation()
            assert await asyncio.wait_for(entered.get(), 1) == 2
            for _ in range(100):
                observer.request_observation()
            await permits.put(None)
            assert await asyncio.wait_for(entered.get(), 1) == 3
            await permits.put(None)
            await asyncio.wait_for(sleeps.get(), 1)
            assert count == 3 and maximum == 1
            # A request at the next idle boundary is not consumed by round 3.
            observer.request_observation()
            assert await asyncio.wait_for(entered.get(), 1) == 4
        finally:
            await observer.close()
            await asyncio.gather(task, return_exceptions=True)
        observer.request_observation()  # Shutdown cannot resurrect sampling.
        await observer.run()
        assert count == 4
    run(scenario())


@pytest.mark.parametrize('operation', ['pause', 'next', 'append'])
@pytest.mark.parametrize('rollback', [False, True])
def test_wakeup_belongs_to_outer_commit(real_client, operation, rollback):
    playback, _, _, _, _ = setup_observation(real_client)

    async def scenario():
        wakes = []
        playback.set_observation_request(lambda: wakes.append(True))
        path = playback.queue_manager.queue_repository.path

        async def outer(_):
            if operation == 'append':
                await playback.add_to_queue('b')  # Binding changes without status save.
            else:
                await getattr(playback, operation)()
            assert wakes == []
            if rollback:
                raise RuntimeError('outer rejected')
        if rollback:
            with pytest.raises(RuntimeError, match='outer rejected'):
                await run_transaction(path, outer)
        else:
            await run_transaction(path, outer)
        expected = [] if rollback or operation != 'pause' else [True]
        assert wakes == expected
        # Read-only sampling and snapshots do not cause a wake feedback loop.
        await playback.observe()
        await playback.get_observation()
        assert wakes == expected
    run(scenario())


def test_wakeup_does_not_wait_for_async_delivery_or_survive_rollback(real_client):
    playback, _, _, _, _ = setup_observation(real_client)

    async def scenario():
        wakes = []
        playback.set_observation_request(lambda: wakes.append(True))
        path = playback.queue_manager.queue_repository.path
        entered, release = asyncio.Event(), asyncio.Event()

        async def delivery():
            entered.set()
            await release.wait()

        async def outer(_):
            on_transaction_commit(path, delivery)
            await playback.pause()
            await playback.seek(2)
            assert not wakes
        writer = asyncio.create_task(run_transaction(path, outer))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            assert wakes == [True]  # Coalesced across nested operations.
        finally:
            release.set()
            await writer
        playback.set_observation_request(None)
        await playback.seek(3)
        assert wakes == [True]
    run(scenario())


@pytest.mark.parametrize('operation', ['pause', 'resume', 'next'])
def test_inflight_old_sample_is_rejected_and_followed_without_polling(real_client, monkeypatch, operation):
    from server.tests.invariants.test_realtime_output import setup_output

    playback, player, _, _, _, output = setup_output(real_client)

    async def scenario():
        if operation == 'resume':
            await playback.pause()
        target = (await playback.observe()).control_target
        sampled, release, sleeps = asyncio.Event(), asyncio.Event(), asyncio.Queue()
        sample = player.read_execution_sample
        calls = 0
        first_result = []
        original_observe = playback.observe

        async def held_sample():
            nonlocal calls
            result = await sample()
            if asyncio.current_task().get_name() == 'b6a-observer':
                calls += 1
                if calls == 1:
                    sampled.set()
                    await release.wait()
            return result

        async def observe(**kwargs):
            result = await original_observe(**kwargs)
            if not first_result:
                first_result.append(result)
            return result

        async def sleep(delay):
            await sleeps.put(delay)
            await asyncio.Event().wait()

        monkeypatch.setattr(player, 'read_execution_sample', held_sample)
        monkeypatch.setattr(playback, 'observe', observe)
        observer = StateObserver(playback=playback, output=output, sleep=sleep)
        playback.set_observation_request(observer.request_observation)
        task = asyncio.create_task(observer.run(), name='b6a-observer')
        try:
            await asyncio.wait_for(sampled.wait(), 1)
            if operation == 'resume':
                await playback.resume(target)
            else:
                await getattr(playback, operation)()
            assert not first_result
            release.set()
            await asyncio.wait_for(sleeps.get(), 1)
            if operation == 'pause':
                assert first_result[0].freshness != 'fresh'
            else:
                assert first_result[0] == await playback.get_observation()
            observed = await playback.get_observation()
            assert observed.freshness == observed.actual_freshness == 'fresh'
            assert observed.matches_current is True and observed.sync_status == 'CONFIRMED'
            assert observed.control_target is not None
            assert observed.actual_state.value == ('paused' if operation == 'pause' else 'playing')
            assert calls == (2 if operation == 'pause' else 1)
        finally:
            await observer.close()
            await asyncio.gather(task, return_exceptions=True)
    run(scenario())


@pytest.mark.parametrize('size', [8, 400])
@pytest.mark.parametrize('operation,budget', [('next', 8), ('song', 8), ('append', 4)])
def test_wakeup_reads_are_separate_from_mutation_budget(tmp_path, monkeypatch, size, operation, budget):
    from collections import Counter

    from server.tests.invariants.test_playback_song_read_budget import seed_queue
    from server.tests.support.d6_stock import stock_joint

    async def scenario():
        async with stock_joint(tmp_path / 'wake-budget.db') as j:
            await seed_queue(j, size)
            sleeps = asyncio.Queue()
            counts = Counter()
            sample = j.player.read_execution_sample
            observer_task = None

            async def counted():
                counts['observer' if asyncio.current_task() is observer_task else 'mutation'] += 1
                return await sample()

            async def cached(**kwargs):
                pass

            async def sleep(delay):
                await sleeps.put(delay)
                await asyncio.Event().wait()

            monkeypatch.setattr(j.player, 'read_execution_sample', counted)
            observer = StateObserver(
                playback=j.service,
                output=SimpleNamespace(get_state=cached, get_observation=cached), sleep=sleep,
            )
            wakes = []

            def request():
                wakes.append(True)
                observer.request_observation()

            j.service.set_observation_request(request)
            observer_task = asyncio.create_task(observer.run())
            try:
                await asyncio.wait_for(sleeps.get(), 5)
                counts.clear()
                cutoff = len(j.fake.received)
                if operation == 'song':
                    await j.service.play_song_now('d')
                elif operation == 'append':
                    await j.service.add_to_queue('d')
                else:
                    await j.service.next()
                # The observer remains in its blocked periodic wait: the final
                # complete mutation sample has already satisfied this demand.
                assert wakes == []
                assert sleeps.empty()
                assert counts == {'mutation': budget}
                controls = Counter(command.split()[0] for command in j.controls(cutoff))
                assert controls == {
                    'next': {'playid': 1, 'deleteid': 1},
                    'song': {'addid': 1, 'playid': 1, 'moveid': 1, 'deleteid': 1},
                    'append': {'addid': 1},
                }[operation]
                snapshot = await j.state.get_full_snapshot()
                assert snapshot.playback_observation.sync_status == 'CONFIRMED'
                assert snapshot.playback_observation.matches_current is True
                print(f'B6-B size={size} operation={operation} samples={dict(counts)} controls={dict(controls)}')
            finally:
                await observer.close()
                await asyncio.gather(observer_task, return_exceptions=True)
    run(scenario())


@pytest.mark.parametrize('failure', ['commit', 'cancel'])
def test_failed_commit_and_precommit_cancellation_do_not_wake(real_client, monkeypatch, failure):
    import sqlite3

    from server.app.repositories import database

    playback, _, _, _, _ = setup_observation(real_client)

    async def scenario():
        wakes = []
        playback.set_observation_request(lambda: wakes.append(True))
        generation = playback._observations.generation
        path = playback.queue_manager.queue_repository.path

        class RejectCommit(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError('B6-A rejected commit')

        async def outer(_):
            await playback.pause()
            if failure == 'cancel':
                raise asyncio.CancelledError()

        with monkeypatch.context() as patch:
            if failure == 'commit':
                patch.setattr(database, '_connect', lambda p: sqlite3.connect(p, factory=RejectCommit))
            with pytest.raises(sqlite3.OperationalError if failure == 'commit' else asyncio.CancelledError):
                await run_transaction(path, outer)
        assert wakes == []
        assert playback._observations.generation == generation
        assert not playback._observation_request_owners
        await playback.pause()
        assert wakes == [True]  # Failed owner did not leak into the retry.
    run(scenario())
