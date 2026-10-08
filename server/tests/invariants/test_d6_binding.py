from __future__ import annotations

import pytest

from server.app.models.queue import PlaybackContext
from server.app.player.ports import PlayerUnavailable
from server.app.services.playback_service import PlaybackService
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_d6_recovery import capture_controls
from server.tests.support.playback import run, start


def test_duplicate_uri_binding_uses_confirmed_entry_ids(real_client, monkeypatch):
    _, library, player, service = real_client
    song = run(library.get_song('a'))
    run(library.upsert_song(song.model_copy(update={'file_uri': 'same.flac'})))
    player._songs.append('same.flac')
    player._durations['same.flac'] = 300

    async def no_refill(context):
        return []

    monkeypatch.setattr(service.autoplay, 'refill', no_refill)
    player._next_queue_id = 10
    run(player.queue_add("same.flac"))
    player._next_queue_id = 11
    run(service.play_context(PlaybackContext(
        context_id='duplicates', source_type='SONGS', ordered_song_ids=('a', 'a'),
    )))
    assert hasattr(service, 'get_execution_binding'), 'missing occurrence binding facade'
    binding = run(service.get_execution_binding())
    a, b = [item.queue_item_id for item in run(service.queue_manager.list_items())[:2]]
    assert binding.entries == ((a, 11, 'same.flac'), (b, 12, 'same.flac'))
    assert a != b
    assert binding.queue_revision == run(service.queue_manager.get_snapshot()).revision
    sample = run(player.read_execution_sample())
    assert binding.connection_epoch == sample.connection_epoch
    assert binding.playlist_version == sample.playlist_version
    before = server_snapshot(service)
    run(player.queue_delete(12))
    assert run(player.queue_add('same.flac')) == 13
    controls = capture_controls(monkeypatch, player)
    assert run(service.reconcile_external_status()).outcome == 'UNKNOWN'
    assert run(service.get_execution_binding()) is None
    assert server_snapshot(service) == before
    assert controls == []


@pytest.mark.parametrize('gap', [
    'disconnect', 'service-restart', 'mpd-restart', 'version-change', 'id-reuse', 'foreign-partition',
])
def test_binding_invalidates_on_gap_version_reuse_and_restart(real_client, monkeypatch, gap):
    client, _, player, service = real_client
    start(client)
    old = run(service.get_execution_binding())
    assert old is not None
    before_business = server_snapshot(service)
    if gap == 'disconnect':
        player.disconnect()
        with pytest.raises(PlayerUnavailable):
            run(service.reconcile_external_status())
        assert run(service.get_execution_binding()) is None
        player.reconnect()
    elif gap == 'service-restart':
        service = PlaybackService(
            queue_manager=service.queue_manager, history_service=service.history_service,
            autoplay=service.autoplay, player=player, library_repository=service.library_repository,
        )
    elif gap == 'mpd-restart':
        player.reconnect()
    elif gap == 'version-change':
        player._playlist_version += 1
    elif gap == 'id-reuse':
        entries = run(player.queue_entries())
        run(player.queue_delete(entries[-1].mpd_song_id))
        player._next_queue_id = entries[-1].mpd_song_id
        assert run(player.queue_add(entries[-1].song_uri)) == entries[-1].mpd_song_id
    else:
        original = player.read_execution_sample

        async def partition():
            return (await original()).model_copy(update={'partition': 'foreign'})

        monkeypatch.setattr(player, 'read_execution_sample', partition)
    controls = capture_controls(monkeypatch, player)
    result = run(service.reconcile_external_status())
    binding = run(service.get_execution_binding())
    after_business = server_snapshot(service)
    assert binding is None
    assert result.outcome == 'UNKNOWN'
    assert after_business == before_business
    assert controls == []
    run(service.observe())
    assert run(service.get_execution_binding()) is None
    assert server_snapshot(service) == before_business
    assert controls == []


def test_same_entry_replay_and_sample_gap_preserve_binding(real_client, monkeypatch):
    from server.tests.invariants.test_realtime_observation import setup_observation

    service, player, _, _, clock = setup_observation(real_client)
    binding = run(service.get_execution_binding())
    before = server_snapshot(service)
    generation = service._recovery.business_generation
    player._elapsed = 23
    assert run(service.observe()).position_seconds == 23
    clock.advance(7)
    assert run(service.get_observation()).freshness == 'stale'
    assert run(service.get_execution_binding()) == binding
    player._elapsed = 0
    controls = capture_controls(monkeypatch, player)
    observed = run(service.observe())
    assert observed.matches_current is True and observed.position_seconds == 0
    assert run(service.get_execution_binding()) == binding
    assert service._recovery.business_generation == generation
    assert server_snapshot(service) == before
    assert controls == []


def test_explicit_stop_invalidates_binding(real_client):
    client, _, _, service = real_client
    start(client)
    assert run(service.get_execution_binding()) is not None
    run(service.stop())
    assert run(service.get_execution_binding()) is None

@pytest.mark.parametrize('operation', ['start', 'context', 'play-now', 'next', 'previous', 'delete', 'stop'])
def test_current_controls_update_or_invalidate_binding(real_client, operation):
    client, _, player, service = real_client
    start(client)
    if operation == 'previous':
        run(service.next())
    before = run(service.get_execution_binding())
    items = run(service.queue_manager.list_items())
    if operation == 'start':
        run(service.start_track('b'))
    elif operation == 'context':
        run(service.play_context(PlaybackContext(
            context_id='new', source_type='SONGS', ordered_song_ids=('b', 'a'),
        )))
    elif operation == 'play-now':
        run(service.play_now(next(item.queue_item_id for item in items if item.position == 1)))
    elif operation == 'delete':
        run(service.delete(next(item.queue_item_id for item in items if item.position == 0)))
    else:
        run(getattr(service, operation)())
    after = run(service.get_execution_binding())
    if operation == 'stop':
        assert after is None
    else:
        queue = run(service.queue_manager.get_snapshot())
        current = next(item for item in queue.items if item.position == 0)
        sample = run(player.read_execution_sample())
        assert after.entries[0][0] == current.queue_item_id
        assert after.entries[0][1] == sample.status.song_id
        assert after.queue_revision == queue.revision
        assert after.binding_generation > before.binding_generation
        assert run(service.observe()).matches_current is True

@pytest.mark.parametrize('loss', [False, True])
def test_binding_rollback_restores_business_but_never_external_continuity(real_client, loss):
    from server.app.repositories.database import run_transaction

    client, library, player, service = real_client
    start(client)
    binding = run(service.get_execution_binding())
    before = server_snapshot(service)

    async def failing(_):
        await service.next()
        if loss:
            player._playlist_version += 1
            assert (await service.reconcile_external_status()).outcome == 'UNKNOWN'
        raise RuntimeError('outer failure')

    with pytest.raises(RuntimeError, match='outer failure'):
        run(run_transaction(library.path, failing))
    assert server_snapshot(service) == before
    assert run(service.get_execution_binding()) == (None if loss else binding)

@pytest.mark.parametrize('failure', ['timeout', 'protocol', 'disconnect'])
def test_sample_failure_invalidates_binding_without_business_change(real_client, monkeypatch, failure):
    from server.app.player.ports import PlayerCommandError

    client, _, player, service = real_client
    start(client)
    before = server_snapshot(service)
    errors = {
        'timeout': TimeoutError('read budget'),
        'protocol': PlayerCommandError('read_execution_sample', 'invalid protocol'),
        'disconnect': PlayerUnavailable('disconnected'),
    }

    async def failed():
        raise errors[failure]

    monkeypatch.setattr(player, 'read_execution_sample', failed)
    controls = capture_controls(monkeypatch, player)
    observed = run(service.observe())
    assert observed.error_code is not None and observed.reconciliation_required
    assert run(service.get_execution_binding()) is None
    assert server_snapshot(service) == before
    assert controls == []


def test_pending_mutation_cannot_rebuild_lost_binding(real_client, monkeypatch):
    from server.app.services.playback_service import PlaybackReconciliationError

    client, _, player, service = real_client
    start(client)
    player.reconnect()
    assert run(service.reconcile_external_status()).outcome == 'UNKNOWN'
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    with pytest.raises(PlaybackReconciliationError):
        run(service.add_to_queue('b'))
    assert run(service.get_execution_binding()) is None
    assert server_snapshot(service) == before
    assert controls == []


def test_pending_mutation_does_not_replay_unaccepted_current(real_client, monkeypatch):
    from server.app.services.playback_service import PlaybackReconciliationError

    client, _, player, service = real_client
    start(client)
    entries = run(player.queue_entries())
    run(player.queue_play(entries[1].mpd_song_id))
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    with pytest.raises(PlaybackReconciliationError):
        run(service.add_to_queue('c'))
    assert server_snapshot(service) == before
    assert run(player.status()).song_id == entries[1].mpd_song_id
    assert controls == []


def test_confirmation_never_rebinds_a_changed_version(real_client, monkeypatch):
    from server.app.services.playback_service import PlaybackReconciliationError

    client, _, player, service = real_client
    start(client)
    before = server_snapshot(service)
    original = service._confirm_current_occurrence

    async def gap(status):
        player._playlist_version += 1
        await original(status)

    monkeypatch.setattr(service, '_confirm_current_occurrence', gap)
    with pytest.raises(PlaybackReconciliationError):
        run(service.play_next('b'))
    assert server_snapshot(service) == before
    assert run(service.get_execution_binding()) is None

@pytest.mark.parametrize('read_number', [1, 3])
def test_control_read_failure_cannot_restore_old_binding(real_client, monkeypatch, read_number):
    client, _, player, service = real_client
    start(client)
    before = server_snapshot(service)
    original = player.read_execution_sample
    reads = 0

    async def failing_sample():
        nonlocal reads
        reads += 1
        if reads == read_number:
            raise PlayerUnavailable('connection lost during confirmation')
        return await original()

    monkeypatch.setattr(player, 'read_execution_sample', failing_sample)
    with pytest.raises(PlayerUnavailable):
        run(service.add_to_queue('b'))
    assert server_snapshot(service) == before
    assert run(service.get_execution_binding()) is None

@pytest.mark.parametrize('gap', ['connection', 'partition'])
def test_queue_confirmation_rejects_continuity_gap(real_client, monkeypatch, gap):
    from server.app.services.playback_service import PlaybackReconciliationError

    client, _, player, service = real_client
    start(client)
    before = server_snapshot(service)
    original = player.read_execution_sample
    reads = 0

    async def changed_sample():
        nonlocal reads
        reads += 1
        if reads == 2 and gap == 'connection':
            player.reconnect()
        sample = await original()
        if reads == 2 and gap == 'partition':
            return sample.model_copy(update={'partition': 'foreign'})
        return sample

    monkeypatch.setattr(player, 'read_execution_sample', changed_sample)
    with pytest.raises(PlaybackReconciliationError):
        run(service.add_to_queue('b'))
    assert server_snapshot(service) == before
    assert run(service.get_execution_binding()) is None

@pytest.mark.parametrize('command, read_number', [('status', 1), ('status', 2), ('queue_entries', 2)])
@pytest.mark.parametrize('error_kind', ['disconnect', 'protocol'])
def test_control_auxiliary_read_failure_invalidates_binding(
    real_client, monkeypatch, command, read_number, error_kind,
):
    from server.app.player.ports import PlayerCommandError

    client, _, player, service = real_client
    start(client)
    before = server_snapshot(service)
    original = getattr(player, command)
    reads = 0
    error = (PlayerUnavailable('connection lost') if error_kind == 'disconnect'
             else PlayerCommandError(command, 'read protocol failure'))

    async def failing_read():
        nonlocal reads
        reads += 1
        if reads == read_number:
            raise error
        return await original()

    monkeypatch.setattr(player, command, failing_read)
    with pytest.raises(type(error)):
        run(service.add_to_queue('b'))
    assert server_snapshot(service) == before
    assert run(service.get_execution_binding()) is None


def test_noop_sync_never_claims_an_unexpected_version(real_client, monkeypatch):
    from server.app.services.playback_service import PlaybackReconciliationError

    client, _, player, service = real_client
    start(client)
    before = server_snapshot(service)
    item = next(item for item in before[0].items if item.position == 1)
    original = player.read_execution_sample
    reads = 0

    async def changed_version():
        nonlocal reads
        reads += 1
        if reads == 2:
            player._playlist_version += 1
        return await original()

    monkeypatch.setattr(player, 'read_execution_sample', changed_version)
    controls = capture_controls(monkeypatch, player)
    with pytest.raises(PlaybackReconciliationError):
        run(service.reorder(item.queue_item_id, item.queue_item_id))
    assert server_snapshot(service) == before
    assert run(service.get_execution_binding()) is None
    assert controls == []


def test_rollback_after_rebind_does_not_publish_staged_binding(real_client):
    from server.app.repositories.database import run_transaction

    client, library, player, service = real_client
    start(client)
    before = server_snapshot(service)

    async def failing(_):
        await service.next()
        player._playlist_version += 1
        assert (await service.reconcile_external_status()).outcome == 'UNKNOWN'
        await service.start_track('c')
        assert await service.get_execution_binding() is not None
        raise RuntimeError('outer failure after rebind')

    with pytest.raises(RuntimeError, match='outer failure after rebind'):
        run(run_transaction(library.path, failing))
    assert server_snapshot(service) == before
    assert service._recovery.binding is None
    assert run(service.get_execution_binding()) is None


def test_cached_observation_cannot_confirm_an_invalidated_binding(real_client, monkeypatch):
    client, _, player, service = real_client
    start(client)
    assert run(service.observe()).freshness == 'fresh'
    before = server_snapshot(service)

    async def disconnected():
        raise PlayerUnavailable('connection lost')

    monkeypatch.setattr(player, 'read_execution_sample', disconnected)
    with pytest.raises(PlayerUnavailable):
        run(service.add_to_queue('b'))
    observation = run(service.get_observation())
    assert observation.freshness != 'fresh'
    assert observation.matches_current is not True
    assert observation.reconciliation_required
    assert run(service.get_execution_binding()) is None
    assert server_snapshot(service) == before


@pytest.mark.parametrize('rollback', [False, True])
def test_stopped_delete_preserves_business_and_actual_deselection(real_client, monkeypatch, rollback):
    from server.app.repositories.database import run_transaction

    client, library, player, service = real_client
    start(client)
    run(service.stop())
    before = server_snapshot(service)
    current = next(item for item in before[0].items if item.position == 0)
    controls = capture_controls(monkeypatch, player)

    async def operation(_):
        await service.delete(current.queue_item_id)
        if rollback:
            raise RuntimeError('stopped delete outer failure')

    if rollback:
        with pytest.raises(RuntimeError, match='stopped delete outer failure'):
            run(run_transaction(library.path, operation))
        assert server_snapshot(service) == before
    else:
        run(run_transaction(library.path, operation))
        after = server_snapshot(service)
        assert after[1].model_dump(exclude={'updated_at'}) == before[1].model_dump(exclude={'updated_at'})
        assert after[2:] == before[2:]
        assert after[0].revision == before[0].revision + 1
    actual = run(player.read_execution_sample()).status
    assert actual.state.value == 'stopped'
    assert actual.song_id is None and actual.song_uri is None and actual.elapsed_seconds is None
    assert run(service.get_execution_binding()) is None
    assert all(name not in {'play', 'queue_play', 'pause', 'stop', 'next', 'previous', 'seek'}
               for name, _, _ in controls)
