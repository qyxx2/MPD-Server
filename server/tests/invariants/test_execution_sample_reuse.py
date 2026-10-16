"""B4: reuse planning data, never the executor's external authorization."""
from __future__ import annotations

import asyncio
from collections import Counter

import pytest

from server.app.services.playback_service import PlaybackReconciliationError
from server.tests.invariants.test_playback_song_read_budget import measure, seed_queue
from server.tests.support.d6_stock import stock_joint


@pytest.mark.parametrize('size', [8, 400])
@pytest.mark.parametrize('operation_to_assert', ['next', 'song', 'played'])
def test_simple_flow_saves_only_the_intermediate_planning_read(tmp_path, monkeypatch, size, operation_to_assert):
    async def scenario():
        async with stock_joint(tmp_path / 'budget.db') as j:
            await seed_queue(j, size)
            for operation, expected_samples, expected_controls in (
                ('next', 8, {'playid': 1, 'deleteid': 1}),
                ('song', 8, {'addid': 1, 'playid': 1, 'moveid': 1, 'deleteid': 1}),
                ('played', 10, {'addid': 1, 'playid': 1, 'moveid': 1, 'deleteid': 1}),
            ):
                before = await j.service.get_execution_binding()
                snapshot = await j.manager.get_snapshot()
                played = next((i for i in snapshot.items if i.position == -1), None)
                with monkeypatch.context() as patch:
                    counts = measure(j, patch)
                    cutoff = len(j.fake.received)
                    if operation == 'next':
                        await j.service.next()
                    elif operation == 'song':
                        await j.service.play_song_now('d')
                    else:
                        await j.service.play_now(played.queue_item_id)
                    commands = Counter(c.split()[0] for c in j.fake.received[cutoff:])
                    measured = dict(counts)
                after = await j.service.get_execution_binding()
                print(f'B4 {size=} {operation=} reads={measured} wire={dict(commands)}')
                assert Counter({k: v for k, v in commands.items()
                                if k not in {'status', 'playlistinfo', 'currentsong'}}) == expected_controls
                assert len(after.entries) == size - 1
                unaffected = before.entries[2:] if operation == 'next' else before.entries[1:]
                assert after.entries[1:] == unaffected
                assert measured['get_song'] == 2
                assert measured['batch'] == 3
                # One planner-only read disappears; every control still has its
                # full result read, and both execute calls retain fresh entry reads.
                if operation == operation_to_assert:
                    assert measured['sample'] == expected_samples
                    # B5 sends the verified ID directly; only move retains an
                    # independent playlistinfo outside the complete samples.
                    assert commands['playlistinfo'] == expected_samples + (operation != 'next')
                    assert commands['status'] == {'next': 20, 'song': 19, 'played': 24}[operation]
                    assert commands['currentsong'] == {'next': 4, 'song': 3, 'played': 4}[operation]
    asyncio.run(scenario())


@pytest.mark.parametrize('operation,expected_samples', [('no-command', 3), ('append', 4)])
def test_planning_reuse_retains_fresh_executor_check_without_transport(tmp_path, monkeypatch, operation, expected_samples):
    async def scenario():
        async with stock_joint(tmp_path / 'other-plans.db') as j:
            old = await seed_queue(j, 8)
            with monkeypatch.context() as patch:
                counts = measure(j, patch)
                cutoff = len(j.fake.received)
                if operation == 'no-command':
                    await j.service.reorder(old.entries[-1][0])
                else:
                    await j.service.add_to_queue('d')
                measured = dict(counts)
            controls = Counter(c.split()[0] for c in j.controls(cutoff))
            assert controls == ({} if operation == 'no-command' else {'addid': 1})
            assert measured['sample'] == expected_samples
            new = await j.service.get_execution_binding()
            assert new.entries[:8] == old.entries
            assert j.fake.current_song_id == old.entries[0][1]
            assert len(new.entries) == (8 if operation == 'no-command' else 9)
    asyncio.run(scenario())


@pytest.mark.parametrize('drift_on_retry', [False, True])
def test_rollback_does_not_reuse_the_previous_planning_candidate(tmp_path, monkeypatch, drift_on_retry):
    from server.app.repositories.database import run_transaction

    async def scenario():
        async with stock_joint(tmp_path / 'retry.db') as j:
            await seed_queue(j, 8)
            before = await j.business()
            verify = j.service._verify_user_queue_baseline
            candidates = []

            async def capture(*, selecting=False):
                sample = await verify(selecting=selecting)
                candidates.append(sample)
                return sample

            monkeypatch.setattr(j.service, '_verify_user_queue_baseline', capture)
            async def rollback(_):
                await j.service.play_song_now('d', request_id='fixed', request_payload='d')
                raise RuntimeError('outer rollback')
            with pytest.raises(RuntimeError, match='outer rollback'):
                await run_transaction(j.path, rollback)
            assert await j.business() == before
            assert candidates[0] is not None
            candidates.clear()
            if drift_on_retry:
                await j.external('addid "i.flac"')
            cutoff = len(j.fake.received)
            if drift_on_retry:
                with pytest.raises(PlaybackReconciliationError):
                    await j.service.play_song_now('d', request_id='fixed', request_payload='d')
                assert await j.business() == before
                assert not j.events
            else:
                await j.service.play_song_now('d', request_id='fixed', request_payload='d')
                assert j.history_service.active_event.song_id == 'd'
            assert candidates and all(sample is None for sample in candidates)
            assert j.controls(cutoff) == []  # Confirmed prefix is never replayed.
            assert 'playlistinfo' in j.fake.received[cutoff:]  # Retry verifies actual MPD.
    asyncio.run(scenario())


@pytest.mark.parametrize('drift', [
    'add', 'delete', 'move', 'same-uri-new-id', 'restored-list',
    'current', 'pause', 'stop', 'single', 'consume', 'random', 'repeat', 'epoch',
])
@pytest.mark.parametrize('operation', ['next', 'song', 'played'])
def test_planning_sample_cannot_authorize_control_after_external_drift(tmp_path, monkeypatch, drift, operation):
    async def scenario():
        async with stock_joint(tmp_path / 'drift.db') as j:
            binding = await seed_queue(j, 8)
            if operation == 'played':
                await j.service.next()
                binding = await j.service.get_execution_binding()
            j.events.clear()
            queue = await j.manager.get_snapshot()
            played = next((i for i in queue.items if i.position == -1), None)
            before, authorities = await j.business(), j.authorities()
            verify = j.service._verify_user_queue_baseline
            cutoff = None

            async def change_after_preflight(*, selecting=False):
                nonlocal cutoff
                candidate = await verify(selecting=selecting)
                if cutoff is None:
                    if drift == 'add':
                        await j.external('addid "d.flac"')
                    elif drift == 'delete':
                        await j.external(f'deleteid {binding.entries[-1][1]}')
                    elif drift == 'move':
                        await j.external(f'moveid {binding.entries[-1][1]} 1')
                    elif drift == 'same-uri-new-id':
                        await j.external(f'deleteid {binding.entries[-1][1]}')
                        await j.external('addid "c.flac"')
                    elif drift == 'restored-list':
                        added = await j.external('addid "d.flac"')
                        await j.external(f'deleteid {added[0].split(": ")[1]}')
                    elif drift == 'current':
                        await j.external(f'playid {binding.entries[2][1]}')
                    elif drift == 'pause':
                        await j.external('pause 1')
                    elif drift == 'stop':
                        await j.external('stop')
                    elif drift == 'epoch':
                        await j.adapter.close()
                    elif drift in {'single', 'consume'}:
                        # This Fake exposes mode fields in real status responses,
                        # but has no protocol setter for these two commands.
                        setattr(j.fake, drift, '1' if drift == 'single' else True)
                    else:
                        await j.external(f'{drift} 1')
                    cutoff = len(j.fake.received)
                return candidate

            monkeypatch.setattr(j.service, '_verify_user_queue_baseline', change_after_preflight)
            with pytest.raises(PlaybackReconciliationError):
                if operation == 'next':
                    await j.service.next()
                elif operation == 'song':
                    await j.service.play_song_now('d')
                else:
                    await j.service.play_now(played.queue_item_id)
            assert j.controls(cutoff) == []
            assert await j.business() == before
            assert j.authorities() == authorities
            assert not j.events
    asyncio.run(scenario())
