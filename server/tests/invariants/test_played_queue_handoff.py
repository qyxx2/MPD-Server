"""Batch 1: confirmed occurrence handoff, command budgets and failure fences."""
from __future__ import annotations

import asyncio
from collections import Counter

import pytest

from server.app.models.queue import PlaybackContext
from server.tests.support.d6_stock import stock_joint


async def seed(j, size, *, duplicate=False):
    # After next there are exactly size MPD entries and a recent Played a.
    pending = ('a',) * (size - 1) if duplicate else ('c',) * (size - 1)
    await j.service.play_context(PlaybackContext(
        context_id='batch-1', source_type='SONGS',
        ordered_song_ids=('a', 'b', *pending),
    ))
    await j.service.next()
    binding = await j.service.get_execution_binding()
    assert len(binding.entries) == size
    queue = await j.manager.get_snapshot()
    played = next(i for i in queue.items if i.position == -1)
    j.events.clear()
    return binding, queue, played


@pytest.mark.parametrize('size', [8, 400])
@pytest.mark.parametrize('operation', ['played', 'previous'])
def test_played_retains_pending_ids_with_constant_command_budget(tmp_path, monkeypatch, size, operation):
    async def scenario():
        async with stock_joint(tmp_path / 'budget.db') as j:
            old, queue, played = await seed(j, size)
            cutoff = len(j.fake.received)
            samples = 0
            read = j.player.read_execution_sample

            async def count_sample():
                nonlocal samples
                samples += 1
                return await read()

            monkeypatch.setattr(j.player, 'read_execution_sample', count_sample)
            if operation == 'played':
                await j.service.play_now(played.queue_item_id)
            else:
                await j.service.previous()
            counts = Counter(c.split()[0] for c in j.controls(cutoff))
            print(f'BATCH1 size={size} operation={operation} commands={dict(counts)} samples={samples}')
            assert counts == {'addid': 1, 'playid': 1, 'moveid': 1, 'deleteid': 1}
            assert samples <= 14
            binding = await j.service.get_execution_binding()
            assert binding.entries[0][0] == played.queue_item_id
            assert binding.entries[1:] == old.entries[1:]
            assert binding.entries[0][1] not in {row[1] for row in old.entries}
            actual = await j.player.read_execution_sample()
            assert tuple(e.mpd_song_id for e in actual.entries) == tuple(row[1] for row in binding.entries)
            assert actual.status.song_id == binding.entries[0][1]
            assert actual.status.song_position == 0
            after = await j.manager.get_snapshot()
            assert [(i.queue_item_id, i.position) for i in after.items] == [
                (old.entries[0][0], -1),
                *((i.queue_item_id, -pos) for pos, i in enumerate(
                    (i for i in queue.items if i.position < 0 and i.queue_item_id != played.queue_item_id), 2
                )),
                (played.queue_item_id, 0),
                *((row[0], pos) for pos, row in enumerate(old.entries[1:], 1)),
            ]
            assert j.history_service.active_event.song_id == 'a'
            assert j.history_service.session_id is not None
    asyncio.run(scenario())


@pytest.mark.parametrize('paused', [False, True])
@pytest.mark.parametrize('operation', ['played', 'previous'])
def test_duplicate_played_uses_new_occurrence_and_preserves_elapsed(tmp_path, monkeypatch, paused, operation):
    async def scenario():
        async with stock_joint(tmp_path / 'duplicate.db') as j:
            old, _, played = await seed(j, 8, duplicate=True)
            if paused:
                await j.service.pause()
            prepare = j.service._prepare_play

            async def advance_after_confirmation(*args, **kwargs):
                status = await prepare(*args, **kwargs)
                # Simulate time passing after confirmed playback, without a control.
                j.fake.elapsed = 17
                return status

            monkeypatch.setattr(j.service, '_prepare_play', advance_after_confirmation)
            cutoff = len(j.fake.received)
            if operation == 'previous':
                await j.service.previous()
            else:
                await j.service.play_now(played.queue_item_id)
            binding = await j.service.get_execution_binding()
            assert binding.entries[1:] == old.entries[1:]
            assert binding.entries[0][0] == played.queue_item_id
            assert binding.entries[0][1] not in {row[1] for row in old.entries}
            actual = await j.player.read_execution_sample()
            assert actual.status.song_id == binding.entries[0][1]
            assert actual.status.elapsed_seconds == 17
            assert actual.status.state.value == 'playing'
            assert Counter(c.split()[0] for c in j.controls(cutoff)) == {
                'addid': 1, 'playid': 1, 'moveid': 1, 'deleteid': 1,
            }
    asyncio.run(scenario())


@pytest.mark.parametrize('drift', [
    'extra', 'missing', 'reorder', 'current', 'stop', 'pause', 'epoch', 'generation',
    'single', 'random', 'repeat', 'consume', 'version', 'partition', 'invalidation',
])
def test_handoff_rejects_drift_after_confirmed_prepare(tmp_path, monkeypatch, drift):
    from server.app.services.playback_service import PlaybackReconciliationError

    async def scenario():
        async with stock_joint(tmp_path / 'drift.db') as j:
            old, _, played = await seed(j, 8)
            before, authorities = await j.business(), j.authorities()
            prepare = j.service._prepare_play
            cutoff = 0

            async def change_after_prepare(*args, **kwargs):
                nonlocal cutoff
                status = await prepare(*args, **kwargs)
                if drift == 'extra':
                    await j.external('addid "d.flac"')
                elif drift == 'missing':
                    await j.external(f'deleteid {old.entries[-1][1]}')
                elif drift == 'reorder':
                    await j.external(f'moveid {old.entries[-1][1]} 0')
                elif drift == 'current':
                    await j.external(f'playid {old.entries[1][1]}')
                elif drift == 'stop':
                    await j.external('stop')
                elif drift == 'pause':
                    await j.external('pause 1')
                elif drift == 'epoch':
                    await j.adapter.close()
                elif drift == 'generation':
                    j.service._recovery.business_generation += 1
                elif drift == 'version':
                    j.fake.playlist_version += 1
                elif drift == 'partition':
                    read = j.player.read_execution_sample

                    async def foreign_partition():
                        return (await read()).model_copy(update={'partition': 'foreign'})

                    monkeypatch.setattr(j.player, 'read_execution_sample', foreign_partition)
                elif drift == 'invalidation':
                    j.service._recovery.invalidate_binding()
                else:
                    setattr(j.fake, drift, '1' if drift == 'single' else True)
                cutoff = len(j.fake.received)
                return status

            monkeypatch.setattr(j.service, '_prepare_play', change_after_prepare)
            message = 'confirmed playing state' if drift in {'stop', 'pause'} else 'UNKNOWN'
            with pytest.raises(PlaybackReconciliationError, match=message):
                await j.service.play_now(played.queue_item_id)
            assert await j.business() == before
            assert j.authorities() == authorities
            assert j.controls(cutoff) == []
            assert not j.events
    asyncio.run(scenario())


@pytest.mark.parametrize('drift', ['extra', 'missing', 'reorder'])
def test_played_preflight_repairs_foreign_baseline_before_selection(tmp_path, drift):
    async def scenario():
        async with stock_joint(tmp_path / 'preflight.db') as j:
            old, _, played = await seed(j, 8)
            if drift == 'extra':
                await j.external('addid "d.flac"')
            elif drift == 'missing':
                await j.external(f'deleteid {old.entries[-1][1]}')
            else:
                await j.external(f'moveid {old.entries[-1][1]} 0')
            cutoff = len(j.fake.received)
            await j.service.play_now(played.queue_item_id)
            assert j.controls(cutoff)[0] == 'clear'
            binding = await j.service.get_execution_binding()
            assert binding.entries[0][0] == played.queue_item_id
            assert [row[0] for row in binding.entries[1:]] == [row[0] for row in old.entries[1:]]
            assert not {row[1] for row in old.entries} & {row[1] for row in binding.entries}
    asyncio.run(scenario())


@pytest.mark.parametrize('command', ['addid', 'playid'])
def test_played_lost_response_never_retries_unknown_after_reconnect(tmp_path, command):
    from server.app.player.ports import PlayerUnavailable
    from server.app.services.playback_service import PlaybackReconciliationError

    async def scenario():
        async with stock_joint(tmp_path / 'lost.db') as j:
            _, _, played = await seed(j, 8)
            before = await j.business()
            j.fake.drop_response = command
            with pytest.raises(PlayerUnavailable):
                await j.service.play_now(played.queue_item_id)
            assert await j.business() == before
            await j.adapter.close()
            cutoff = len(j.fake.received)
            with pytest.raises(PlaybackReconciliationError, match='UNKNOWN'):
                await j.service.play_now(played.queue_item_id)
            assert j.controls(cutoff) == []
            assert await j.business() == before
    asyncio.run(scenario())


@pytest.mark.parametrize('phase', ['prepare-confirmed', 'move-ack', 'delete-confirmed', 'outer-sqlite'])
def test_played_rollback_retry_preserves_confirmed_ids_and_prefix(tmp_path, monkeypatch, phase):
    import sqlite3

    from server.app.repositories.database import run_transaction

    async def scenario():
        async with stock_joint(tmp_path / 'rollback.db') as j:
            old, _, played = await seed(j, 8)
            before, authorities = await j.business(), j.authorities()
            journal = j.service._recovery
            record = journal.record_command
            failed = False
            cutoff = len(j.fake.received)

            def fault(operation_id, index, receipt):
                nonlocal failed
                record(operation_id, index, receipt)
                intent = journal.execution_intents[operation_id]
                command = intent.commands[index].kind
                trigger = (
                    phase == 'prepare-confirmed' and operation_id.endswith('/prepare')
                    and command == 'play' and receipt.phase == 'confirmed'
                    or phase == 'move-ack' and command == 'move' and receipt.phase == 'ack'
                    or phase == 'delete-confirmed' and command == 'delete' and receipt.phase == 'confirmed'
                )
                if trigger and not failed:
                    failed = True
                    raise RuntimeError('prefix rollback')

            monkeypatch.setattr(journal, 'record_command', fault)
            if phase == 'outer-sqlite':
                async def fail_outer(connection):
                    await j.service.play_now(played.queue_item_id)
                    connection.execute('INSERT INTO nonexistent_batch1_table VALUES (1)')
                with pytest.raises(sqlite3.OperationalError):
                    await run_transaction(j.path, fail_outer)
            else:
                with pytest.raises(RuntimeError, match='prefix rollback'):
                    await j.service.play_now(played.queue_item_id)
            assert await j.business() == before
            assert j.authorities() == authorities
            assert not j.events
            monkeypatch.setattr(journal, 'record_command', record)
            await j.service.play_now(played.queue_item_id)
            binding = await j.service.get_execution_binding()
            assert binding.entries[1:] == old.entries[1:]
            assert Counter(c.split()[0] for c in j.controls(cutoff)) == {
                'addid': 1, 'playid': 1, 'moveid': 1, 'deleteid': 1,
            }
            queue_id = next(key for key, intent in journal.execution_intents.items()
                            if intent.target_item_id == played.queue_item_id and key.endswith('/queue'))
            assert journal.get_execution_receipt(queue_id).outcome == 'REPLAYED'
            from server.app.services.playback_execution import ExecutionSynchronizer
            controls = len(j.fake.received)
            await ExecutionSynchronizer(j.player, journal).execute(journal.execution_intents[queue_id])
            assert j.controls(controls) == []
    asyncio.run(scenario())


@pytest.mark.parametrize('selection', ['current', 'pending-duplicate', 'older-played'])
def test_selection_keeps_exact_occurrence_and_queue_history_order(tmp_path, monkeypatch, selection):
    async def scenario():
        async with stock_joint(tmp_path / 'positions.db') as j:
            await seed(j, 8, duplicate=True)
            if selection == 'older-played':
                await j.service.next()
            queue = await j.manager.get_snapshot()
            old = await j.service.get_execution_binding()
            if selection == 'current':
                target = next(i for i in queue.items if i.position == 0)
            elif selection == 'pending-duplicate':
                target = next(i for i in queue.items if i.position == 5)
            else:
                target = next(i for i in queue.items if i.position == -2)
            old_current = next(i for i in queue.items if i.position == 0)
            played_ids = [i.queue_item_id for i in queue.items if i.position < 0
                          and i.queue_item_id != target.queue_item_id]
            pending = [i.queue_item_id for i in queue.items if i.position > 0
                       and i.queue_item_id != target.queue_item_id]
            if target.queue_item_id != old_current.queue_item_id:
                played_ids.insert(0, old_current.queue_item_id)
            old_history = await j.history.list_history()
            session = j.history_service.session_id
            prepare = j.service._prepare_play

            async def advance(*args, **kwargs):
                status = await prepare(*args, **kwargs)
                j.fake.elapsed = 13
                return status

            monkeypatch.setattr(j.service, '_prepare_play', advance)
            await j.external('seekcur 179')
            cutoff = len(j.fake.received)
            await j.service.play_now(target.queue_item_id)
            after = await j.manager.get_snapshot()
            assert [(i.queue_item_id, i.position) for i in after.items] == [
                *((key, -pos) for pos, key in enumerate(played_ids, 1)),
                (target.queue_item_id, 0),
                *((key, pos) for pos, key in enumerate(pending, 1)),
            ]
            binding = await j.service.get_execution_binding()
            old_ids = {key: mpd_id for key, mpd_id, _ in old.entries}
            assert {key: mpd_id for key, mpd_id, _ in binding.entries if key in pending} == {
                key: old_ids[key] for key in pending
            }
            if selection != 'older-played':
                assert binding.entries[0][1] == old_ids[target.queue_item_id]
            actual = await j.player.read_execution_sample()
            assert actual.status.song_id == binding.entries[0][1]
            assert actual.status.elapsed_seconds == 13
            controls = Counter(c.split()[0] for c in j.controls(cutoff))
            assert controls['playid'] == 1
            assert controls['addid'] == int(selection == 'older-played')
            assert controls['deleteid'] == int(selection != 'current')
            history = await j.history.list_history()
            assert j.history_service.session_id == session
            assert j.history_service.active_event.song_id == target.song_id
            # StockJoint observe during seeding relinquishes its original active;
            # each subsequent explicit switch records only certified SWITCH_AWAY.
            assert len(history) == len(old_history) + 1
            assert history[0].song_id == old_current.song_id
            assert history[0].reason == 'SWITCH_AWAY'
            assert {event.history_id for event in old_history} <= {event.history_id for event in history}
            assert all(event.reason != 'NATURAL_COMPLETION' for event in history)
    asyncio.run(scenario())


def test_played_terminal_failure_retry_and_replay_keep_one_external_execution(real_client, monkeypatch):
    import sqlite3

    from server.app.repositories.database import run_transaction
    from server.tests.invariants.assertions import server_snapshot
    from server.tests.invariants.test_d6_recovery import capture_controls
    from server.tests.support.playback import mutate, run, start

    client, library, player, service = real_client
    start(client)
    run(service.next())
    before = server_snapshot(service)
    old = run(service.get_execution_binding())
    played = next(i for i in before[0].items if i.position == -1)
    route = f'/api/playback/queue/items/{played.queue_item_id}/play'
    run(run_transaction(library.path, lambda c: c.execute("""
        CREATE TRIGGER fail_batch1_terminal BEFORE INSERT ON idempotency_records
        WHEN NEW.idempotency_key = 'batch1-played'
        BEGIN SELECT RAISE(ABORT, 'batch1 terminal'); END
    """)))
    controls = capture_controls(monkeypatch, player)
    with pytest.raises(sqlite3.IntegrityError, match='batch1 terminal'):
        mutate(client, 'POST', route, key='batch1-played')
    assert server_snapshot(service) == before
    fixed_ids = tuple(e.mpd_song_id for e in run(player.queue_entries()))
    first_controls = list(controls)
    run(run_transaction(library.path, lambda c: c.execute('DROP TRIGGER fail_batch1_terminal')))
    controls.clear()
    result = mutate(client, 'POST', route, key='batch1-played')
    assert result.status_code == 200, result.text
    assert result.json()['queue_item_id'] == played.queue_item_id
    assert controls == []
    assert tuple(e.mpd_song_id for e in run(player.queue_entries())) == fixed_ids
    binding = run(service.get_execution_binding())
    assert binding.entries[1:] == old.entries[1:]
    committed = server_snapshot(service)
    replay = mutate(client, 'POST', route, key='batch1-played')
    assert replay.json() == result.json() and replay.status_code == 200
    assert server_snapshot(service) == committed
    assert controls == []
    assert sum(name in {'play', 'queue_play'} for name, _, _ in first_controls) == 1
