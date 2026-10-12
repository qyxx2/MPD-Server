from __future__ import annotations

import asyncio
import sqlite3

import pytest

from server.app.main import app
from server.app.player.models import PlayerState
from server.app.player.ports import PlayerCommandError
from server.app.repositories import database
from server.app.repositories.database import run_transaction
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.services.playback_service import PlaybackService
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.tests.invariants.assertions import (
    assert_execution_relationship,
    server_snapshot,
)
from server.tests.invariants.test_d6_recovery import capture_controls
from server.tests.support.playback import mutate, run, start


def play(client, song='b', key='song-now'):
    response = mutate(client, 'POST', f'/api/playback/songs/{song}/play', key=key)
    assert response.status_code == 200, response.text
    return response.json()


def pending(snapshot):
    return [(i.queue_item_id, i.song_id, i.source, i.playback_context_id)
            for i in sorted(snapshot.items, key=lambda i: i.position) if i.position > 0]


def filled(real_client):
    client, _, _, service = real_client
    start(client)
    for _ in range(3):
        run(service.add_to_queue('b'))
    return server_snapshot(service)


def test_new_occurrence_preserves_pending_identity_and_joint_state(real_client):
    client, library, player, service = real_client
    before = filled(real_client)
    old_target = run(service.observe()).control_target
    events = []

    class Publisher:
        async def publish(self, event):
            # The publisher can read only the committed joint result.
            snap = await service.queue_manager.get_snapshot()
            state = await service.queue_manager.get_playback_state()
            assert next(i for i in snap.items if i.position == 0).song_id == state.song_id == 'b'
            events.append(event)

    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    service._coordinator, service._event_publisher = coordinator, Publisher()
    item = play(client)
    after = server_snapshot(service)
    assert item['queue_item_id'] not in {i.queue_item_id for i in before[0].items}
    assert item['position'] == 0 and item['source'] == 'MANUAL'
    assert pending(after[0]) == pending(before[0])
    assert after[0].revision == before[0].revision + 1
    assert after[1].playback_context_id == item['playback_context_id'] == before[1].playback_context_id
    old_current = next(i for i in before[0].items if i.position == 0)
    assert next(i for i in after[0].items if i.position == -1).queue_item_id == old_current.queue_item_id
    assert after[4] == before[4] and after[3].song_id == 'b'
    assert len(after[2]) == len(before[2]) + 1 and after[2][0].reason == 'SWITCH_AWAY'
    assert subscriber.pending.domains == frozenset({'queue', 'playback', 'history'})
    assert [e.domains for e in events] == [frozenset({'queue', 'playback', 'history'})]
    assert_execution_relationship(service, player, current_id=item['queue_item_id'])
    target = run(service.observe()).control_target
    assert target is not None and target.queue_item_id == item['queue_item_id'] and target != old_target
    assert run(IdempotencyRepository(library.path).get_by_key('song-now')) is not None


def test_explicit_stop_starts_new_context_and_session_preserving_pending(real_client):
    client, _, player, service = real_client
    filled(real_client)
    run(service.next())
    before_stop = server_snapshot(service)
    run(service.stop())
    stopped = server_snapshot(service)
    assert stopped[4] is None and not stopped[1].autoplay_enabled
    item = play(client)
    after = server_snapshot(service)
    assert after[1].playback_context_id != stopped[1].playback_context_id
    assert after[4] not in {None, before_stop[4]} and after[1].autoplay_enabled
    assert all(i.position >= 0 for i in after[0].items)
    assert pending(after[0]) == pending(stopped[0])
    assert after[2] == stopped[2]
    assert_execution_relationship(service, player, current_id=item['queue_item_id'])


@pytest.mark.parametrize('mode', ['initial', 'no-context', 'unknown-stop', 'unbound', 'paused', 'same-song', 'disabled', 'restart', 'restart-stopped'])
def test_lifecycle_does_not_infer_stop_or_reuse_song_occurrence(real_client, monkeypatch, mode):
    client, _, player, service = real_client
    if mode != 'initial':
        filled(real_client)
    if mode == 'no-context':
        state = run(service.queue_manager.get_playback_state())
        run(service.queue_manager.set_playback_state(state.model_copy(update={'playback_context_id': None})))
    elif mode == 'unknown-stop':
        run(player.stop())
        run(service.observe())
    elif mode == 'unbound':
        player.disconnect()
        player.reconnect()
    elif mode == 'paused':
        run(service.pause())
    elif mode == 'disabled':
        state = run(service.queue_manager.get_playback_state())
        run(service.queue_manager.set_playback_state(state.model_copy(update={'autoplay_enabled': False})))
    elif mode in {'restart', 'restart-stopped'}:
        if mode == 'restart-stopped':
            run(service.stop())
        # Restart loses runtime active/session/binding; persisted Context is not a Stop marker.
        from server.app.services.history_service import HistoryService
        service = PlaybackService(queue_manager=service.queue_manager,
                                  history_service=HistoryService(service.queue_manager.queue_repository, service.history_service.history_repository),
                                  autoplay=service.autoplay, player=player,
                                  library_repository=service.library_repository)
        monkeypatch.setattr(app.state, 'playback_service', service)
    before = server_snapshot(service)
    song = 'a' if mode == 'same-song' else 'b'
    item = play(client, song)
    after = server_snapshot(service)
    assert item['queue_item_id'] not in {i.queue_item_id for i in before[0].items}
    assert pending(after[0])[:len(pending(before[0]))] == pending(before[0])
    if before[1] and before[1].playback_context_id:
        assert after[1].playback_context_id == before[1].playback_context_id
    else:
        assert after[1].playback_context_id and all(i.position >= 0 for i in after[0].items)
    if before[4]:
        assert after[4] == before[4]
    else:
        assert after[4] is not None
    assert after[1].autoplay_enabled == (mode != 'disabled')
    if mode in {'unknown-stop', 'unbound', 'restart', 'restart-stopped'}:
        assert after[2] == before[2]  # No invented reason for the untrusted active.
    assert run(player.status()).state == PlayerState.PLAYING
    assert_execution_relationship(service, player, current_id=item['queue_item_id'])


@pytest.mark.parametrize('failure', ['command', 'confirmation', 'terminal', 'outer-commit', 'materialization', 'cancel'])
def test_failures_restore_joint_state_without_success_notification(real_client, monkeypatch, failure):
    client, library, player, service = real_client
    before = filled(real_client)
    old_target = run(service.observe()).control_target
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    service._coordinator = coordinator
    records = IdempotencyRepository(library.path)
    connect = database._connect
    if failure == 'command':
        async def reject(*args):
            raise PlayerCommandError('playid', 'song command rejected')
        monkeypatch.setattr(player, 'queue_play', reject)
    elif failure == 'confirmation':
        original = player.status
        async def mismatch():
            status = await original()
            if status.song_uri == 'b.flac':
                return status.model_copy(update={'state': PlayerState.PAUSED})
            return status
        monkeypatch.setattr(player, 'status', mismatch)
    elif failure == 'terminal':
        run(run_transaction(library.path, lambda c: c.execute("""
            CREATE TRIGGER fail_song_terminal BEFORE INSERT ON idempotency_records
            BEGIN SELECT RAISE(ABORT, 'song terminal'); END
        """)))
    elif failure == 'outer-commit':
        class RejectCommit(sqlite3.Connection):
            def commit(self):
                raise sqlite3.OperationalError('song commit')
        monkeypatch.setattr(database, '_connect', lambda p: sqlite3.connect(p, factory=RejectCommit))
    elif failure == 'materialization':
        from server.app.models.recovery import RecoveryResult
        from server.app.services import playback_recovery
        original = playback_recovery.deepcopy
        def reject_copy(value):
            if isinstance(value, RecoveryResult):
                raise TypeError('song materialization')
            return original(value)
        monkeypatch.setattr(playback_recovery, 'deepcopy', reject_copy)
    else:
        original = service._confirm_preserved_state
        async def cancel():
            await original()
            raise asyncio.CancelledError()
        monkeypatch.setattr(service, '_confirm_preserved_state', cancel)
    if failure in {'command', 'confirmation'}:
        response = mutate(client, 'POST', '/api/playback/songs/b/play', key='fault')
        assert response.status_code == 502, response.text
    elif failure == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            run(service.play_song_now('b'))
    else:
        with pytest.raises((sqlite3.Error, TypeError)):
            mutate(client, 'POST', '/api/playback/songs/b/play', key='fault')
    if failure == 'outer-commit':
        monkeypatch.setattr(database, '_connect', connect)
    assert server_snapshot(service) == before
    assert coordinator.marker().sequence == 0 and subscriber.pending is None
    assert run(records.get_by_key('fault')) is None
    assert run(service.get_observation()).control_target is None
    assert old_target is not None


@pytest.mark.parametrize('phase', ['terminal', 'after-add', 'after-play', 'lost-add-response'])
def test_retry_keeps_fixed_occurrence_and_owned_execution_prefix(real_client, monkeypatch, phase):
    client, _, player, service = real_client
    before = filled(real_client)
    planned = []
    original_sync = service._sync_player_queue
    async def capture(**kwargs):
        planned.append(await service.queue_manager.get_snapshot())
        return await original_sync(**kwargs)
    monkeypatch.setattr(service, '_sync_player_queue', capture)
    if phase == 'terminal':
        records = app.state.idempotency_service._repository
        original = records.create
        async def fault(**kwargs):
            raise RuntimeError('song fault')
        monkeypatch.setattr(records, 'create', fault)
    elif phase in {'after-add', 'after-play'}:
        journal = service._recovery
        original = journal.record_command
        failed = False
        def fault(operation_id, index, receipt):
            nonlocal failed
            original(operation_id, index, receipt)
            if (operation_id.endswith('/queue') and receipt.phase == 'confirmed' and not failed
                    and journal.execution_intents[operation_id].commands[index].kind
                    == ('add' if phase == 'after-add' else 'play')):
                failed = True
                raise RuntimeError('song fault')
        monkeypatch.setattr(journal, 'record_command', fault)
    else:
        original = player.queue_add
        async def fault(uri):
            await original(uri)
            raise TimeoutError('lost add response')
        monkeypatch.setattr(player, 'queue_add', fault)
    if phase == 'lost-add-response':
        response = mutate(client, 'POST', '/api/playback/songs/b/play', key='prefix')
        assert response.status_code == 503, response.text
        monkeypatch.setattr(player, 'queue_add', original)
    else:
        with pytest.raises(RuntimeError, match='song fault'):
            mutate(client, 'POST', '/api/playback/songs/b/play', key='prefix')
        if phase == 'terminal':
            monkeypatch.setattr(records, 'create', original)
        else:
            monkeypatch.setattr(journal, 'record_command', original)
    assert server_snapshot(service) == before
    entries = run(player.queue_entries())
    controls = capture_controls(monkeypatch, player)
    response = mutate(client, 'POST', '/api/playback/songs/b/play', key='prefix')
    if phase == 'lost-add-response':
        assert response.status_code == 502
        assert server_snapshot(service) == before and run(player.queue_entries()) == entries
        assert controls == []
    else:
        assert response.status_code == 200, response.text
        assert planned[-1] == planned[0]
        completed = 'queue_add' if phase == 'after-add' else 'queue_play'
        assert not any(name == completed for name, *_ in controls)
        assert_execution_relationship(service, player, current_id=response.json()['queue_item_id'])
        final = server_snapshot(service)
        controls.clear()
        replay = mutate(client, 'POST', '/api/playback/songs/b/play', key='prefix')
        assert replay.content == response.content and replay.status_code == 200
        assert controls == [] and server_snapshot(service) == final


def test_new_target_and_joint_state_are_hidden_until_outer_commit(real_client):
    _, library, _, service = real_client
    before = filled(real_client)
    old_target = run(service.observe()).control_target
    coordinator = RealtimeCoordinator(library.path)
    subscriber = coordinator.subscribe()
    service._coordinator = coordinator
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def outer(_):
            item = await service.play_song_now('b')
            assert coordinator.marker().sequence == 0 and subscriber.pending is None
            entered.set()
            await release.wait()
            return item
        task = asyncio.create_task(run_transaction(library.path, outer))
        await asyncio.wait_for(entered.wait(), 2)
        # A different transaction cannot observe the staged new occurrence/token.
        reader = asyncio.create_task(service.queue_manager.get_snapshot())
        await asyncio.sleep(0)
        assert not reader.done()
        release.set()
        item = await task
        snapshot = await reader
        assert next(i for i in snapshot.items if i.position == 0).queue_item_id == item.queue_item_id
        assert coordinator.marker().sequence == 1
        assert (await service.observe()).control_target.queue_item_id == item.queue_item_id
    run(scenario())
    assert coordinator.marker().sequence >= 1
    assert subscriber.pending.domains == frozenset({'queue', 'playback', 'history'})
    assert old_target is not None and server_snapshot(service) != before


@pytest.mark.parametrize('competition', ['current', 'pending'])
def test_failed_key_retry_cannot_become_new_intent_after_competing_mutation(real_client, monkeypatch, competition):
    client, _, player, service = real_client
    filled(real_client)
    allocated = []
    sync = service._sync_player_queue
    async def capture(**kwargs):
        allocated.append(next(i.queue_item_id for i in (await service.queue_manager.get_snapshot()).items if i.position == 0))
        return await sync(**kwargs)
    monkeypatch.setattr(service, '_sync_player_queue', capture)
    records = app.state.idempotency_service._repository
    create = records.create
    async def fault(**kwargs):
        raise RuntimeError('terminal stale fault')
    monkeypatch.setattr(records, 'create', fault)
    with pytest.raises(RuntimeError, match='terminal stale fault'):
        mutate(client, 'POST', '/api/playback/songs/b/play', key='stale-key')
    monkeypatch.setattr(records, 'create', create)
    if competition == 'current':
        play(client, 'c', key='competing')
    else:
        # An authoritative Queue-only writer advances revision independently
        # of current. The failed execution still has no committed binding.
        run(service.queue_manager.add_to_queue('c'))
    before = server_snapshot(service)
    entries = run(player.queue_entries())
    controls = capture_controls(monkeypatch, player)
    count = len(allocated)
    retry = mutate(client, 'POST', '/api/playback/songs/b/play', key='stale-key')
    assert retry.status_code == 502, retry.text
    assert retry.json()['error']['code'] == 'PLAYBACK_RECONCILIATION_FAILED'
    assert controls == [] and server_snapshot(service) == before
    assert run(player.queue_entries()) == entries and len(allocated) == count


@pytest.mark.parametrize('start_kind', ['song', 'queue', 'track', 'collection'])
def test_confirmed_start_consumes_prior_stop_provenance(real_client, start_kind):
    client, _, player, service = real_client
    filled(real_client)
    run(service.stop())
    if start_kind == 'song':
        play(client, 'b', key='restart')
    elif start_kind == 'queue':
        item = next(i for i in run(service.queue_manager.list_items()) if i.position > 0)
        run(service.play_now(item.queue_item_id))
    elif start_kind == 'track':
        run(service.start_track('b'))
    else:
        from server.app.models.queue import PlaybackContext
        run(service.play_context(PlaybackContext(context_id='after-stop', source_type='SONGS', ordered_song_ids=('b', 'a'))))
    # A later business STOPPED value is not the earlier Stop operation. Build
    # this boundary explicitly; do not claim the external stop produced it.
    state = run(service.queue_manager.get_playback_state())
    run(service.queue_manager.set_playback_state(state.model_copy(update={'state': 'STOPPED'})))
    run(player.stop())
    before = server_snapshot(service)
    item = play(client, 'a', key='after-unknown')
    after = server_snapshot(service)
    assert item['playback_context_id'] == before[1].playback_context_id
    assert after[4] == before[4]
    assert after[2] == before[2]


@pytest.mark.parametrize('lifecycle', ['initial', 'stop'])
def test_new_context_and_autoplay_allocations_survive_terminal_retry(real_client, monkeypatch, lifecycle):
    client, _, player, service = real_client
    if lifecycle == 'stop':
        start(client)
        run(service.stop())
    before = server_snapshot(service)
    planned = []
    sync = service._sync_player_queue
    async def capture(**kwargs):
        planned.append(await service.queue_manager.get_snapshot())
        return await sync(**kwargs)
    monkeypatch.setattr(service, '_sync_player_queue', capture)
    records = app.state.idempotency_service._repository
    create = records.create
    async def fault(**kwargs):
        raise RuntimeError('new context terminal fault')
    monkeypatch.setattr(records, 'create', fault)
    with pytest.raises(RuntimeError, match='new context terminal fault'):
        mutate(client, 'POST', '/api/playback/songs/b/play', key='new-context')
    assert server_snapshot(service) == before
    monkeypatch.setattr(records, 'create', create)
    controls = capture_controls(monkeypatch, player)
    result = play(client, 'b', key='new-context')
    assert planned[1] == planned[0] and controls == []
    assert_execution_relationship(service, player, current_id=result['queue_item_id'])
    if before[1]:
        assert result['playback_context_id'] != before[1].playback_context_id


def test_keyword_service_retry_preserves_fixed_request_identity(real_client):
    _, library, _, service = real_client
    filled(real_client)
    before = server_snapshot(service)
    planned = []
    async def attempt(_):
        item = await service.play_song_now(song_id='b', request_id='keyword', request_payload='fixed')
        planned.append(item)
        raise RuntimeError('keyword terminal fault')
    with pytest.raises(RuntimeError, match='keyword terminal fault'):
        run(run_transaction(library.path, attempt))
    assert server_snapshot(service) == before
    item = run(service.play_song_now(song_id='b', request_id='keyword', request_payload='fixed'))
    assert item == planned[0]
