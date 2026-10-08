from __future__ import annotations

import pytest

from server.app.models.library import Song
from server.app.models.queue import PlaybackContext
from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.app.repositories.database import run_transaction
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_d6_recovery import capture_controls
from server.tests.support.playback import run


def prepare(real_client, pending=4):
    _, library, player, service = real_client
    for song_id in 'def':
        run(library.upsert_song(Song(song_id=song_id, title=song_id, file_uri=f'{song_id}.flac')))
        if f'{song_id}.flac' not in player._songs:
            player._songs.append(f'{song_id}.flac')
            player._durations[f'{song_id}.flac'] = 180
    run(service.play_context(PlaybackContext(context_id='s7', source_type='SONGS', ordered_song_ids=tuple('abcdef'))))
    if pending == 4:
        item = next(i for i in run(service.queue_manager.list_items()) if i.song_id == 'f')
        run(service.delete(item.queue_item_id))
    run(service.add_to_queue('b'))
    # Five pending initially; removing e gives four, with duplicate MANUAL b retained.
    if pending == 4:
        item = next(i for i in run(service.queue_manager.list_items()) if i.song_id == 'e')
        run(service.delete(item.queue_item_id))
    else:
        item = next(i for i in run(service.queue_manager.list_items()) if i.song_id == 'f')
        run(service.delete(item.queue_item_id))
    return player, service


def seed_candidates(player, service):
    for song_id in 'ghijklmn':
        run(service.library_repository.upsert_song(Song(song_id=song_id, title=song_id, file_uri=f'{song_id}.flac')))
        player._songs.append(f'{song_id}.flac')
        player._durations[f'{song_id}.flac'] = 180


@pytest.mark.parametrize('remaining', [4, 5])
@pytest.mark.parametrize('advance', [False, True], ids=['same-current', 'a-to-c'])
@pytest.mark.parametrize('paused', [False, True])
def test_refill_uses_confirmed_remaining_and_preserves_manual_order(real_client, monkeypatch, remaining, advance, paused):
    player, service = prepare(real_client, remaining)
    seed_candidates(player, service)
    binding = run(service.get_execution_binding())
    if advance:
        # Adoption removes A; one extra MANUAL preserves the requested watermark.
        run(service.add_to_queue('d'))
        binding = run(service.get_execution_binding())
        run(player.queue_play(binding.entries[2][1]))
    if paused:
        run(player.pause())
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    old_entry_id = run(player.read_execution_sample()).status.song_id
    result = run(service.maintain_execution())
    assert result.outcome in {'APPLIED', 'UNCHANGED'}
    after = server_snapshot(service)
    added = tuple(i for i in after[0].items if i.queue_item_id not in {i.queue_item_id for i in before[0].items})
    assert len(added) == (5 if remaining == 4 else 0)
    assert {i.source for i in added} == ({'AUTOPLAY'} if added else set())
    assert {i.queue_item_id for i in after[0].items if i.source == 'MANUAL'} == {i.queue_item_id for i in before[0].items if i.source == 'MANUAL'}
    excluded = {binding.entries[0][0], binding.entries[2][0]} if advance else set()
    assert [i.queue_item_id for i in after[0].items if i.source == 'MANUAL' and i.queue_item_id not in excluded] == [i.queue_item_id for i in before[0].items if i.source == 'MANUAL' and i.queue_item_id not in excluded]
    confirmed = run(service.get_execution_binding())
    assert tuple(i.queue_item_id for i in sorted((i for i in after[0].items if i.position >= 0), key=lambda i: i.position)) == tuple(row[0] for row in confirmed.entries)
    assert run(player.read_execution_sample()).status.song_id == old_entry_id
    assert after[2] == before[2]
    assert after[3] is None if advance else after[3] == before[3]
    assert not any(name in {'play', 'queue_play', 'next', 'seek', 'pause'} for name, _, _ in controls)


@pytest.mark.parametrize('case', ['empty', 'no-candidates', 'stop', 'disconnect', 'append-failure', 'late-stop'])
def test_empty_stop_disconnect_and_refill_failure_do_not_restart(real_client, monkeypatch, case):
    player, service = prepare(real_client)
    if case in {'empty', 'no-candidates'}:
        for song in run(service.library_repository.list_available_songs()):
            run(service.library_repository.upsert_song(song.model_copy(update={'availability_status': 'MISSING'})))
    else:
        seed_candidates(player, service)
    if case == 'stop':
        run(service.stop())
        seed_candidates(player, service)
    if case == 'disconnect':
        async def disconnected():
            raise PlayerUnavailable('disconnected')
        monkeypatch.setattr(player, 'read_execution_sample', disconnected)
    if case == 'append-failure':
        async def rejected(uri):
            raise PlayerCommandError('addid', 'injected')
        monkeypatch.setattr(player, 'queue_add', rejected)
    if case == 'late-stop':
        plan = service.autoplay.plan_refill
        async def stopped(context, snapshot):
            planned = await plan(context, snapshot)
            await player.stop()
            return planned
        monkeypatch.setattr(service.autoplay, 'plan_refill', stopped)
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    try:
        result = run(service.maintain_execution())
    except (PlayerUnavailable, PlayerCommandError):
        result = None
    assert server_snapshot(service) == before
    assert not any(name in {'play', 'queue_play', 'next', 'seek'} for name, _, _ in controls)
    assert not any(event.reason == 'NATURAL_COMPLETION' for event in server_snapshot(service)[2])
    assert server_snapshot(service)[1].autoplay_enabled == (case != 'stop')
    if case in {'empty', 'no-candidates'}:
        assert result.diagnostic == 'NO_CANDIDATES'
    if case == 'late-stop':
        assert result.outcome == 'UNKNOWN' and result.reconciliation_required
        assert not any(name == 'queue_add' for name, _, _ in controls)


@pytest.mark.parametrize('advance', [False, True])
def test_refill_outer_rollback_reuses_fixed_candidates_and_prefix(real_client, monkeypatch, advance):
    player, service = prepare(real_client)
    seed_candidates(player, service)
    if advance:
        binding = run(service.get_execution_binding())
        run(player.queue_play(binding.entries[2][1]))
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    async def failed(_):
        result = await service.maintain_execution()
        assert result.outcome == 'APPLIED'
        assert service._recovery.get_execution_receipt(result.transition_id) is None
        raise RuntimeError('outer')
    with pytest.raises(RuntimeError, match='outer'):
        run(run_transaction(service.queue_manager.queue_repository.path, failed))
    assert server_snapshot(service) == before
    prefix = list(controls)
    planned = next(iter(service._recovery.refill_items.values()))
    result = run(service.maintain_execution())
    assert result.outcome == 'APPLIED' and controls == prefix
    assert {i.queue_item_id for i in planned} <= {i.queue_item_id for i in server_snapshot(service)[0].items}
    assert service._recovery.get_execution_receipt(result.transition_id).outcome == 'REPLAYED'


@pytest.mark.parametrize('pending_repeat', [False, True])
def test_single_song_fallback_keeps_existing_dedup_boundary(real_client, monkeypatch, pending_repeat):
    _, library, player, service = real_client
    for song_id in 'bc':
        song = run(library.get_song(song_id))
        run(library.upsert_song(song.model_copy(update={'availability_status': 'MISSING'})))
    run(service.start_track('a'))
    if not pending_repeat:
        pending = next(i for i in run(service.queue_manager.list_items()) if i.position > 0)
        run(service.queue_manager.delete(pending.queue_item_id, persist_state=False))
        run(service._sync_player_queue())
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    result = run(service.maintain_execution())
    after = server_snapshot(service)
    assert sum(i.position > 0 for i in after[0].items) == 1
    assert after[2:] == before[2:]
    assert not any(name in {'play', 'queue_play'} for name, _, _ in controls)
    if pending_repeat:
        assert result.diagnostic == 'NO_CANDIDATES'
        assert after == before and controls == []
    else:
        assert result.outcome == 'APPLIED'
        assert after[0].revision == before[0].revision + 1


@pytest.mark.parametrize('failure', ['after-ack', 'after-confirm', 'lost-response', 'queue-write', 'precommit-cancel'])
def test_refill_failure_preserves_fixed_ids_and_only_owned_suffix(real_client, monkeypatch, failure):
    import asyncio

    player, service = prepare(real_client)
    seed_candidates(player, service)
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    journal = service._recovery
    with monkeypatch.context() as fault:
        if failure == 'lost-response':
            add = player.queue_add
            async def lost(uri):
                await add(uri)
                raise PlayerUnavailable('lost add response')
            fault.setattr(player, 'queue_add', lost)
        elif failure in {'after-ack', 'after-confirm'}:
            record = journal.record_command
            def cancelled(operation_id, index, receipt):
                record(operation_id, index, receipt)
                if operation_id.endswith('/refill') and index == 1 and receipt.phase == ('ack' if failure == 'after-ack' else 'confirmed'):
                    raise asyncio.CancelledError()
            fault.setattr(journal, 'record_command', cancelled)
        elif failure == 'queue-write':
            async def fail(*args, **kwargs):
                raise RuntimeError('queue write')
            fault.setattr(service.queue_manager.queue_repository, 'add_autoplay_batch', fail)
        async def attempt(_):
            await service.maintain_execution()
            if failure == 'precommit-cancel':
                raise asyncio.CancelledError()
        expected = PlayerUnavailable if failure == 'lost-response' else RuntimeError if failure == 'queue-write' else asyncio.CancelledError
        with pytest.raises(expected):
            run(run_transaction(journal.path, attempt))
    assert server_snapshot(service) == before
    intent = next(i for key, i in journal.execution_intents.items() if key.endswith('/refill'))
    planned = journal.refill_items[intent.operation_id]
    assert journal.get_execution_receipt(intent.operation_id) is None
    if failure == 'lost-response':
        prefix = list(controls)
        result = run(service.maintain_execution())
        assert result.outcome == 'UNKNOWN' and controls == prefix
        assert server_snapshot(service) == before
    else:
        result = run(service.maintain_execution())
        assert result.outcome == 'APPLIED'
        added = [i for i in server_snapshot(service)[0].items if i.queue_item_id in {i.queue_item_id for i in planned}]
        assert added == list(planned)
        assert sum(name == 'queue_add' for name, _, _ in controls) == 5
        assert journal.execution_intents[intent.operation_id] == intent


@pytest.mark.parametrize('mode', ['random', 'repeat', 'single', 'consume', 'unbound', 'external-stop'])
def test_maintenance_unknown_and_nonsequential_modes_do_not_control(real_client, monkeypatch, mode):
    player, service = prepare(real_client)
    seed_candidates(player, service)
    if mode in {'random', 'repeat'}:
        run(getattr(player, f'set_{mode}')(True))
    elif mode in {'single', 'consume'}:
        read = player.read_execution_sample
        async def unsupported():
            return (await read()).model_copy(update={mode: '1' if mode == 'single' else True})
        monkeypatch.setattr(player, 'read_execution_sample', unsupported)
    elif mode == 'unbound':
        service._recovery.invalidate_binding()
    else:
        run(player.stop())
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    result = run(service.maintain_execution())
    assert result.outcome == 'UNKNOWN' and result.reconciliation_required
    assert server_snapshot(service) == before and controls == []


def test_refill_final_confirmation_rejects_stop_during_queue_write(real_client, monkeypatch):
    player, service = prepare(real_client)
    seed_candidates(player, service)
    before = server_snapshot(service)
    write = service.queue_manager.queue_repository.add_autoplay_batch
    async def progressed(*args, **kwargs):
        added = await write(*args, **kwargs)
        await player.stop()
        return added
    monkeypatch.setattr(service.queue_manager.queue_repository, 'add_autoplay_batch', progressed)
    result = run(service.maintain_execution())
    assert result.outcome == 'UNKNOWN' and result.reconciliation_required
    assert server_snapshot(service) == before


@pytest.mark.parametrize('stage', ['planner', 'second-add', 'queue-write'])
@pytest.mark.parametrize('outer_failure', [False, True])
def test_current_advance_resamples_owned_prefix_without_duplicate_candidates(real_client, monkeypatch, stage, outer_failure):
    player, service = prepare(real_client)
    seed_candidates(player, service)
    binding = run(service.get_execution_binding())
    before = server_snapshot(service)
    if stage == 'planner':
        method = service.autoplay.plan_refill
        async def progressed(context, snapshot):
            planned = await method(context, snapshot)
            await player.queue_play(binding.entries[2][1])
            return planned
        monkeypatch.setattr(service.autoplay, 'plan_refill', progressed)
    elif stage == 'second-add':
        method = player.queue_add
        calls = 0
        async def progressed(uri):
            nonlocal calls
            result = await method(uri)
            calls += 1
            if calls == 2:
                await player.queue_play(binding.entries[2][1])
            return result
        monkeypatch.setattr(player, 'queue_add', progressed)
    else:
        method = service.queue_manager.queue_repository.add_autoplay_batch
        advanced = False
        async def progressed(*args, **kwargs):
            nonlocal advanced
            result = await method(*args, **kwargs)
            if not advanced:
                await player.queue_play(binding.entries[2][1])
                advanced = True
            return result
        monkeypatch.setattr(service.queue_manager.queue_repository, 'add_autoplay_batch', progressed)
    controls = capture_controls(monkeypatch, player)
    if outer_failure:
        async def fail(_):
            result = await service.maintain_execution()
            assert result.outcome == 'APPLIED'
            raise RuntimeError('outer progression')
        with pytest.raises(RuntimeError, match='outer progression'):
            run(run_transaction(service.queue_manager.queue_repository.path, fail))
        assert server_snapshot(service) == before
        prefix = list(controls)
    result = run(service.maintain_execution())
    assert result.outcome == 'APPLIED' and not result.reconciliation_required
    if outer_failure:
        assert controls == prefix
    after = server_snapshot(service)
    assert after[1].song_id == 'c' and after[2] == before[2] and after[3] is None
    added = [i for i in after[0].items if i.queue_item_id not in {i.queue_item_id for i in before[0].items}]
    assert len(added) == 5 and len({i.song_id for i in added}) == 5
    assert sum(name == 'queue_add' for name, _, _ in controls) == 5
    new_binding = run(service.get_execution_binding())
    assert new_binding.entries[0][1] == binding.entries[2][1]
    assert binding.entries[1][0] in {i.queue_item_id for i in after[0].items if i.position > 0}
    committed = server_snapshot(service)
    prefix = list(controls)
    assert run(service.maintain_execution()).outcome == 'UNCHANGED'
    assert server_snapshot(service) == committed and controls == prefix


def test_concurrent_stop_fences_following_maintenance(real_client, monkeypatch):
    import asyncio

    player, service = prepare(real_client)
    seed_candidates(player, service)
    method = service.autoplay.plan_refill
    controls = capture_controls(monkeypatch, player)
    async def scenario():
        planning, stop_queued, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def blocked(context, snapshot):
            result = await method(context, snapshot)
            planning.set()
            await release.wait()
            return result
        monkeypatch.setattr(service.autoplay, 'plan_refill', blocked)
        async def stop():
            await planning.wait()
            stop_queued.set()
            return await service.stop()
        first = asyncio.create_task(service.maintain_execution())
        second = asyncio.create_task(stop())
        await stop_queued.wait()
        assert not second.done()
        release.set()
        result = await first
        stopped = await second
        assert result.outcome == 'APPLIED' and not stopped.autoplay_enabled
    run(scenario())
    before = server_snapshot(service)
    prefix = list(controls)
    seed_candidates(player, service)
    run(service.maintain_execution())
    assert server_snapshot(service) == before and controls == prefix
    assert not any(name in {'play', 'queue_play'} for name, _, _ in controls)


@pytest.mark.parametrize('malformed', ['song', 'source', 'context', 'position', 'duplicate-id', 'cas'])
def test_fixed_autoplay_occurrences_validate_before_persistence(real_client, malformed):
    from server.app.repositories.queue_repository import QueueRevisionConflictError

    player, service = prepare(real_client)
    seed_candidates(player, service)
    repository = service.queue_manager.queue_repository
    before = run(repository.get_snapshot())
    state = run(service.queue_manager.get_playback_state())
    planned = run(service.autoplay.plan_refill(run(service._queue_playback_context(state)), before))
    fields = {'song': {'song_id': 'wrong'}, 'source': {'source': 'MANUAL'},
              'context': {'playback_context_id': 'wrong'}, 'position': {'position': 100},
              'duplicate-id': {'queue_item_id': planned[1].queue_item_id}}
    if malformed != 'cas':
        planned = (planned[0].model_copy(update=fields[malformed]), *planned[1:])
    with pytest.raises(QueueRevisionConflictError if malformed == 'cas' else ValueError):
        run(repository.add_autoplay_batch([i.song_id for i in planned] if malformed != 'song' else ['e', *[i.song_id for i in planned[1:]]],
            playback_context_id=state.playback_context_id,
            expected_revision=before.revision - (malformed == 'cas'), planned_items=planned))
    assert run(repository.get_snapshot()) == before


@pytest.mark.parametrize('stage', ['before-plan', 'during-add'])
def test_player_error_pauses_refill_without_changing_user_intent(real_client, monkeypatch, stage):
    player, service = prepare(real_client)
    seed_candidates(player, service)
    read = player.read_execution_sample
    error = stage == 'before-plan'
    async def errored():
        sample = await read()
        return sample.model_copy(update={'error': 'decoder error'}) if error else sample
    monkeypatch.setattr(player, 'read_execution_sample', errored)
    if stage == 'during-add':
        add = player.queue_add
        async def failed(uri):
            nonlocal error
            mpd_id = await add(uri)
            error = True
            return mpd_id
        monkeypatch.setattr(player, 'queue_add', failed)
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    result = run(service.maintain_execution())
    assert result.outcome == 'UNKNOWN' and result.reconciliation_required
    assert server_snapshot(service) == before
    assert sum(name == 'queue_add' for name, _, _ in controls) == (0 if stage == 'before-plan' else 1)
    assert not any(name in {'play', 'queue_play'} for name, _, _ in controls)


def test_refill_confirmation_failure_propagates_to_outer_owner(real_client, monkeypatch):
    from server.app.services.playback_service import PlaybackReconciliationError

    player, service = prepare(real_client)
    seed_candidates(player, service)
    before = server_snapshot(service)
    write = service.queue_manager.queue_repository.add_autoplay_batch
    async def stopped(*args, **kwargs):
        added = await write(*args, **kwargs)
        await player.stop()
        return added
    monkeypatch.setattr(service.queue_manager.queue_repository, 'add_autoplay_batch', stopped)
    async def outer(_):
        return await service.maintain_execution()
    with pytest.raises(PlaybackReconciliationError, match='UNKNOWN'):
        run(run_transaction(service.queue_manager.queue_repository.path, outer))
    assert server_snapshot(service) == before
    assert not any(key.endswith('/refill') for key in service._recovery.execution_receipts)


@pytest.mark.parametrize('failure', ['materialization', 'publisher'])
def test_refill_receipt_and_notifications_follow_outer_commit(real_client, monkeypatch, failure):
    from server.app.models.recovery import RecoveryResult
    from server.app.services import playback_recovery
    from server.app.services.realtime_coordinator import RealtimeCoordinator

    player, service = prepare(real_client)
    seed_candidates(player, service)
    before = server_snapshot(service)
    events = []
    class Publisher:
        async def publish(self, event):
            if failure == 'publisher':
                raise RuntimeError('publisher failed')
            events.append(event)
    service._event_publisher = Publisher()
    service._coordinator = RealtimeCoordinator(service.queue_manager.queue_repository.path)
    subscriber = service._coordinator.subscribe()
    controls = capture_controls(monkeypatch, player)
    if failure == 'materialization':
        copy = playback_recovery.deepcopy
        def failed(value):
            if isinstance(value, RecoveryResult):
                raise TypeError('materialization')
            return copy(value)
        with monkeypatch.context() as fault:
            fault.setattr(playback_recovery, 'deepcopy', failed)
            with pytest.raises(TypeError, match='materialization'):
                run(service.maintain_execution())
        assert server_snapshot(service) == before and events == [] and subscriber.pending is None
        assert not any(key.endswith('/refill') for key in service._recovery.execution_receipts)
        prefix = list(controls)
    result = run(service.maintain_execution())
    assert result.outcome == 'APPLIED'
    if failure == 'materialization':
        assert controls == prefix and len(events) == 1
    assert subscriber.pending is not None
    assert service._recovery.get_execution_receipt(result.transition_id).outcome == 'REPLAYED'
    committed = server_snapshot(service)
    prefix = list(controls)
    assert run(service.maintain_execution()).outcome == 'UNCHANGED'
    assert server_snapshot(service) == committed and controls == prefix


def test_refill_diagnostic_returns_the_committed_adopted_playback(real_client, monkeypatch):
    player, service = prepare(real_client)
    seed_candidates(player, service)
    binding = run(service.get_execution_binding())
    run(player.queue_play(binding.entries[2][1]))
    read = player.read_execution_sample
    async def errored():
        return (await read()).model_copy(update={'error': 'decoder error'})
    monkeypatch.setattr(player, 'read_execution_sample', errored)
    result = run(service.maintain_execution())
    state = run(service.queue_manager.get_playback_state())
    assert result.outcome == 'UNKNOWN' and result.reconciliation_required
    assert result.playback == state and state.song_id == 'c'
