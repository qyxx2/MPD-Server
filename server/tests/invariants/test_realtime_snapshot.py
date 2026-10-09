from __future__ import annotations

import asyncio
import importlib.util

import pytest

from server.app.main import app
from server.app.player.capabilities import MPDCapabilities
from server.app.player.mock_mpd import MockMPD
from server.app.services.library_scanner import LibraryScanner
from server.app.services.output_manager import OutputManager
from server.app.services.playlist_service import PlaylistService
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_realtime_transitions import wire
from server.tests.support.playback import mutate, run, start


def make_state(playback, library, coordinator, output):
    assert importlib.util.find_spec('server.app.services.state_service') is not None, (
        'StateService committed snapshot aggregation is missing'
    )
    from server.app.services.state_service import StateService

    return StateService(
        coordinator=coordinator,
        queue_manager=playback.queue_manager,
        history_service=playback.history_service,
        library_service=library,
        output_snapshot=lambda: output,
    )


def cached_output(playback, player):
    manager = OutputManager(
        player=player,
        capabilities=MPDCapabilities.from_commands({'outputs'}),
        operation_runner=playback.run_output_operation,
    )
    return run(manager.get_state())


def test_snapshot_is_one_committed_cut(real_client, tmp_path, monkeypatch):
    """RT-SNAPSHOT: releasing the capture boundary between reads mixes transitions."""
    client, repository, player, original = real_client
    root = tmp_path / 'empty-music'
    root.mkdir()
    for song_id in 'abc':
        song = run(repository.get_song(song_id))
        run(repository.upsert_song(song.model_copy(update={'file_uri': str(root / f'{song_id}.flac')})))
    player = MockMPD([str(root / f'{song_id}.flac') for song_id in 'abc'])
    original.player = player
    start(client)
    coordinator = RealtimeCoordinator(repository.path)
    playback = wire(original, None, coordinator)
    output = cached_output(playback, player)
    state = make_state(playback, app.state.library_service, coordinator, output)
    playlists = PlaylistService(app.state.playlist_service._repository, coordinator=coordinator)
    scanner = LibraryScanner(repository, coordinator=coordinator)
    original_read = playback.queue_manager.get_playback_state
    before = server_snapshot(playback)

    async def scenario():
        reading, release, attempted = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def held_read():
            result = await original_read()
            reading.set()
            await release.wait()
            return result

        monkeypatch.setattr(playback.queue_manager, 'get_playback_state', held_read)
        capture = asyncio.create_task(state.get_full_snapshot())
        await asyncio.wait_for(reading.wait(), 1)

        async def mutate():
            from server.app.repositories.database import run_transaction

            attempted.set()

            async def joint(_):
                await playback.next()
                await playlists.create_playlist('joint')
                await scanner.scan_full(root)

            await run_transaction(repository.path, joint)

        mutation = asyncio.create_task(mutate())
        await attempted.wait()
        await asyncio.sleep(0)
        assert not mutation.done(), 'mutation escaped the shared capture boundary'
        release.set()
        first = await asyncio.wait_for(capture, 1)
        await asyncio.wait_for(mutation, 1)
        second = await state.get_full_snapshot()
        assert first.playback == before[1]
        assert first.queue == before[0]
        assert first.history.active_event == before[3]
        assert first.history.session_id == before[4]
        assert not first.history.has_entries
        assert first.current_song.song_id == 'a'
        assert first.current_song.availability_status == 'AVAILABLE'
        assert first.sequence == 0 and first.revisions == {'library': 0, 'playlist': 0}
        assert second.playback.song_id == second.history.active_event.song_id == 'b'
        assert second.history.has_entries
        assert second.current_song.song_id == 'b'
        assert second.current_song.availability_status == 'MISSING'
        assert second.sequence == 1 and second.revisions == {'library': 1, 'playlist': 1}
        assert second.epoch == first.epoch == coordinator.marker().epoch
        assert [i.song_id for i in second.queue.items if i.position == 0] == ['b']
        assert [i.song_id for i in second.queue.items if i.position < 0] == ['a']
        assert first.output == second.output == output

    run(scenario())


def test_snapshot_empty_and_unknown_observations_are_complete(real_client, monkeypatch):
    """Empty state cannot masquerade as zero MPD progress or confirmed output sampling."""
    _, repository, player, playback = real_client
    coordinator = RealtimeCoordinator(repository.path)
    output = cached_output(playback, player)
    state = make_state(playback, app.state.library_service, coordinator, output)
    marker = coordinator.marker()

    async def forbidden(*args, **kwargs):
        raise AssertionError('snapshot performed external I/O or domain reconciliation')

    for method in ('status', 'outputs', 'play', 'stop', 'queue_entries', 'set_output_enabled'):
        monkeypatch.setattr(player, method, forbidden)
    monkeypatch.setattr(playback, 'reconcile_external_status', forbidden)
    first = run(state.get_full_snapshot())
    second = run(state.get_full_snapshot())
    assert first.model_dump(exclude={'captured_at'}) == second.model_dump(exclude={'captured_at'})
    assert set(first.model_dump()) == {
        'epoch', 'sequence', 'captured_at', 'revisions', 'playback', 'current_song',
        'queue', 'history', 'output', 'playback_observation', 'output_observation',
    }
    assert first.captured_at.tzinfo is not None
    assert first.playback is None and first.current_song is None
    assert first.queue.model_dump() == {'revision': 0, 'items': ()}
    assert first.history.model_dump() == {'has_entries': False, 'active_event': None, 'session_id': None}
    assert first.output == output
    assert first.playback_observation.model_dump() == {
        'actual_state': None, 'actual_current': None, 'actual_freshness': 'unknown',
        'bound_queue_item_id': None, 'control_target': None, 'sync_status': 'UNBOUND',
        'matches_current': None, 'position_seconds': None,
        'duration_seconds': None, 'observed_at': None, 'freshness': 'unknown',
        'reconciliation_required': False, 'error_code': None, 'error_message': None,
    }
    assert first.output_observation.model_dump() == {
        'observed_at': None, 'freshness': 'unknown', 'error_code': None, 'error_message': None,
    }
    assert first.revisions == {'library': 0, 'playlist': 0}
    assert coordinator.marker() == marker


def test_snapshot_is_detached_and_preserves_all_business_state(real_client, monkeypatch):
    """Aliasing returned nested models corrupts runtime/history/output; reads must not write."""
    client, repository, player, playback = real_client
    assert mutate(client, 'POST', '/api/playback/collections/play', {
        'source_type': 'SONGS', 'song_ids': ['a', 'b', 'c'],
    }, key='snapshot-start').status_code == 200
    run(playback.next())
    coordinator = RealtimeCoordinator(repository.path)
    subscription = coordinator.subscribe()
    output = cached_output(playback, player)
    state = make_state(playback, app.state.library_service, coordinator, output)
    before = server_snapshot(playback)
    songs = run(app.state.library_service.list_songs())
    playlists = run(app.state.playlist_service.revision_content())
    records = app.state.idempotency_service._repository
    terminal = run(records.get_by_key('snapshot-start'))
    assert terminal is not None
    player_before = (run(player.status()), run(player.queue_entries()), run(player.outputs()))
    marker = coordinator.marker()
    first = run(state.get_full_snapshot())
    baseline = first.model_copy(deep=True)

    async def forbidden(*args, **kwargs):
        raise AssertionError('snapshot touched PlayerPort or reconciliation')

    for method in ('status', 'queue_entries', 'outputs', 'play', 'stop', 'set_output_enabled'):
        monkeypatch.setattr(player, method, forbidden)
    monkeypatch.setattr(playback, 'reconcile_external_status', forbidden)
    first.playback.song_id = 'corrupt'
    first.queue.items[0].song_id = 'corrupt'
    first.history.active_event.song_id = 'corrupt'
    first.current_song.title = 'corrupt'
    first.output.states[0].status = 'ACTIVE'
    first.revisions['library'] = 999
    second = run(state.get_full_snapshot())
    assert second.model_dump(exclude={'captured_at'}) == baseline.model_dump(exclude={'captured_at'})
    assert server_snapshot(playback) == before
    assert run(app.state.library_service.list_songs()) == songs
    assert run(app.state.playlist_service.revision_content()) == playlists
    assert coordinator.marker() == marker and subscription.pending is None
    # Later source changes cannot rewrite a snapshot already returned.
    output.states[0].error_message = 'later cache update'
    playback.history_service.active_event.song_id = 'later runtime change'
    assert second.history.active_event.song_id == 'b'
    assert second.output == baseline.output
    playback.history_service.active_event.song_id = 'b'
    monkeypatch.undo()
    assert (run(player.status()), run(player.queue_entries()), run(player.outputs())) == player_before
    assert run(records.get_by_key('snapshot-start')) == terminal


@pytest.mark.parametrize('domain', ['playback', 'queue', 'history', 'library', 'marker', 'output'])
def test_required_read_failure_never_returns_partial_success(real_client, monkeypatch, domain):
    """A swallowed local/cache failure must not become an empty/zero successful snapshot."""
    client, repository, player, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(repository.path)
    state = make_state(playback, app.state.library_service, coordinator, cached_output(playback, player))
    before = server_snapshot(playback)
    marker = coordinator.marker()

    async def failed_read(*args, **kwargs):
        raise RuntimeError(f'{domain} read unavailable')

    def failed_sync():
        raise RuntimeError(f'{domain} read unavailable')

    targets = {
        'playback': (playback.queue_manager, 'get_playback_state'),
        'queue': (playback.queue_manager, 'get_snapshot'),
        'history': (playback.history_service.history_repository, 'list_history'),
        'library': (app.state.library_service, 'get_song'),
    }
    with monkeypatch.context() as patch:
        if domain in targets:
            patch.setattr(*targets[domain], failed_read)
        elif domain == 'marker':
            patch.setattr(coordinator, 'marker', failed_sync)
        else:
            patch.setattr(state, '_output_snapshot', failed_sync)
        with pytest.raises(RuntimeError, match=f'{domain} read unavailable'):
            run(state.get_full_snapshot())
    assert server_snapshot(playback) == before
    assert coordinator.marker() == marker
    assert run(state.get_full_snapshot()).playback == before[1]


def test_current_reference_missing_from_library_fails_snapshot(real_client, monkeypatch):
    """A missing required current Song cannot silently become null."""
    client, repository, player, playback = real_client
    start(client)
    state = make_state(playback, app.state.library_service, RealtimeCoordinator(repository.path), cached_output(playback, player))

    async def missing(_):
        return None

    monkeypatch.setattr(app.state.library_service, 'get_song', missing)
    with pytest.raises(LookupError, match='Current Song'):
        run(state.get_full_snapshot())


@pytest.mark.parametrize('outcome', ['commit', 'rollback', 'cancel'])
def test_capture_waits_for_mutation_and_never_leaks_uncommitted_runtime(
    real_client, outcome,
):
    """A runtime History update ahead of SQLite commit must not leak into reads."""
    client, repository, player, original = real_client
    start(client)
    coordinator = RealtimeCoordinator(repository.path)
    playback = wire(original, None, coordinator)
    state = make_state(playback, app.state.library_service, coordinator, cached_output(playback, player))
    before = server_snapshot(playback)

    async def scenario():
        from server.app.repositories.database import run_transaction

        updated, release, attempted, history_attempted = (
            asyncio.Event(), asyncio.Event(), asyncio.Event(), asyncio.Event(),
        )

        async def joint(_):
            await playback.next()
            assert playback.history_service.active_event.song_id == 'b'
            updated.set()
            await release.wait()
            if outcome == 'rollback':
                raise RuntimeError('outer rollback')
            if outcome == 'cancel':
                raise asyncio.CancelledError

        mutation = asyncio.create_task(run_transaction(repository.path, joint))
        await asyncio.wait_for(updated.wait(), 1)

        async def capture():
            attempted.set()
            return await state.get_full_snapshot()

        reading = asyncio.create_task(capture())
        await attempted.wait()

        async def availability():
            history_attempted.set()
            return await playback.history_service.get_availability()

        history_reading = asyncio.create_task(availability())
        await history_attempted.wait()
        await asyncio.sleep(0)
        assert not reading.done(), 'uncommitted runtime leaked through capture'
        assert not history_reading.done(), 'uncommitted runtime leaked through availability'
        release.set()
        if outcome == 'commit':
            await asyncio.wait_for(mutation, 1)
        else:
            with pytest.raises(RuntimeError if outcome == 'rollback' else asyncio.CancelledError):
                await mutation
        snapshot = await asyncio.wait_for(reading, 1)
        assert await asyncio.wait_for(history_reading, 1) == snapshot.history
        if outcome == 'commit':
            assert snapshot.playback.song_id == snapshot.history.active_event.song_id == 'b'
            assert snapshot.history.has_entries and snapshot.sequence == 1
            assert [i.song_id for i in snapshot.queue.items if i.position == 0] == ['b']
        else:
            assert snapshot.playback == before[1] and snapshot.queue == before[0]
            assert snapshot.history.active_event == before[3]
            assert snapshot.history.session_id == before[4]
            assert not snapshot.history.has_entries and snapshot.sequence == 0
            assert await playback.history_service.list_history() == []
        assert snapshot.revisions == {'library': 0, 'playlist': 0}

    run(scenario())


def test_snapshot_preserves_cached_output_request_and_stale_nulls(real_client):
    """A terminal request receipt must survive, without being relabeled fresh observation."""
    from server.app.models.output import OutputMode
    from server.app.player.models import OutputInfo
    from server.tests.invariants.test_output_enable import enable_manager

    _, repository, player, playback = real_client
    player._outputs = [OutputInfo(id=37, name='DAC', plugin='alsa', enabled=False)]
    manager = enable_manager(playback, player)
    receipt = run(manager.set_enabled(OutputMode.NAS_DAC, True))
    player.disconnect()
    output = run(manager.get_state())
    assert output.states[0].stale and output.states[0].error_code == 'PLAYER_UNAVAILABLE'
    assert output.last_request == receipt.last_request
    state = make_state(playback, app.state.library_service, RealtimeCoordinator(repository.path), output)
    snapshot = run(state.get_full_snapshot())
    assert snapshot.output == output
    assert snapshot.output.last_request.status == 'SUCCEEDED'
    assert snapshot.output_observation.freshness == 'unknown'
    assert snapshot.output_observation.observed_at is None
    assert all(getattr(snapshot.output.states[0], field) is None for field in (
        'target_client_id', 'stream_url', 'format', 'sample_rate', 'bit_depth', 'channels',
    ))
    snapshot.output.last_request.status = 'SWITCH_FAILED'
    assert output.last_request.status == 'SUCCEEDED'
    assert run(state.get_full_snapshot()).output == output


def test_cancelled_capture_releases_boundary_without_business_delta(real_client, monkeypatch):
    """Cancelled readers must release the shared lock without touching History or revision."""
    client, repository, player, playback = real_client
    start(client)
    coordinator = RealtimeCoordinator(repository.path)
    state = make_state(playback, app.state.library_service, coordinator, cached_output(playback, player))
    before = server_snapshot(playback)
    original_read = playback.queue_manager.get_playback_state

    async def scenario():
        reading = asyncio.Event()

        async def held_read():
            reading.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(playback.queue_manager, 'get_playback_state', held_read)
        task = asyncio.create_task(state.get_full_snapshot())
        await asyncio.wait_for(reading.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        monkeypatch.setattr(playback.queue_manager, 'get_playback_state', original_read)
        snapshot = await asyncio.wait_for(state.get_full_snapshot(), 1)
        assert snapshot.playback == before[1] and snapshot.queue == before[0]
        assert snapshot.history.active_event == before[3] and not snapshot.history.has_entries
        assert snapshot.sequence == 0 and snapshot.revisions == {'library': 0, 'playlist': 0}

    run(scenario())
    assert server_snapshot(playback) == before


def test_snapshot_rejects_an_uncommitted_owner_instead_of_exposing_phantom_success(real_client):
    """Nested reads must not export uncommitted data with the last committed marker."""
    client, repository, player, original = real_client
    start(client)
    coordinator = RealtimeCoordinator(repository.path)
    playback = wire(original, None, coordinator)
    state = make_state(playback, app.state.library_service, coordinator, cached_output(playback, player))
    before = run(state.get_full_snapshot())

    async def scenario():
        from server.app.repositories.database import run_transaction

        async def pending(_):
            await playback.next()
            assert playback.history_service.active_event.song_id == 'b'
            assert coordinator.marker().sequence == 0
            with pytest.raises(RuntimeError, match='committed'):
                await state.get_full_snapshot()
            raise RuntimeError('owner rollback')

        with pytest.raises(RuntimeError, match='owner rollback'):
            await run_transaction(repository.path, pending)
        after = await state.get_full_snapshot()
        assert after.model_dump(exclude={'captured_at'}) == before.model_dump(exclude={'captured_at'})

    run(scenario())
