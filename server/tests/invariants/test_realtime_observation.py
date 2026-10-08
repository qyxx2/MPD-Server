from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from server.app.main import app
from server.app.models.queue import PlaybackContext
from server.app.services.playback_service import PlaybackService
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_realtime_snapshot import cached_output
from server.tests.support.playback import mutate, run


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 10, 3, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def setup_observation(real_client):
    _, library, player, original = real_client
    assert hasattr(PlaybackService, 'observe'), 'PlaybackService read-only observation facade is missing'
    clock = FakeClock()
    coordinator = RealtimeCoordinator(library.path)
    playback = PlaybackService(
        queue_manager=original.queue_manager, history_service=original.history_service,
        autoplay=original.autoplay, player=player, library_repository=library,
        coordinator=coordinator, observation_clock=clock,
    )
    run(playback.play_context(PlaybackContext(
        context_id='repeated', source_type='SONGS', ordered_song_ids=('a', 'a', 'b'),
    )))
    return playback, player, library, coordinator, clock


@pytest.mark.parametrize('operation', ['next', 'pause', 'seek'])
def test_late_sample_never_becomes_new_current_progress(real_client, monkeypatch, operation):
    """Accepting a sample after a confirmed mutation attaches old progress to its successor."""
    playback, player, _, coordinator, _ = setup_observation(real_client)
    initial = run(playback.observe())
    assert initial.matches_current is True and initial.freshness == 'fresh'
    original_sample = player.read_execution_sample

    async def scenario():
        sampled, release = asyncio.Event(), asyncio.Event()
        observation_task = None

        async def held_status():
            status = await original_sample()
            if asyncio.current_task() is observation_task:
                sampled.set()
                await release.wait()
            return status

        player._elapsed = 23
        monkeypatch.setattr(player, 'read_execution_sample', held_status)
        observation_task = asyncio.create_task(playback.observe())
        await asyncio.wait_for(sampled.wait(), 1)
        if operation == 'seek':
            await asyncio.wait_for(playback.seek(7), 1)
        else:
            await asyncio.wait_for(getattr(playback, operation)(), 1)
        marker = coordinator.marker()
        release.set()
        late = await asyncio.wait_for(observation_task, 1)
        assert late.position_seconds is None, 'late sample became new-generation progress'
        assert late.freshness != 'fresh'
        assert coordinator.marker() == marker, 'discarded sample registered an invalidation'
        fresh = await playback.observe()
        assert fresh.matches_current is True and fresh.freshness == 'fresh'
        assert fresh.position_seconds == (7 if operation == 'seek' else 0 if operation == 'next' else 23)
        if operation == 'next':
            assert (await playback.queue_manager.get_playback_state()).song_id == 'a'
            assert fresh.position_seconds != 23, 'same URI concealed a different occurrence'

    run(scenario())
    before = server_snapshot(playback)
    run(playback.observe())
    assert server_snapshot(playback) == before
    assert coordinator.marker().library_revision == coordinator.marker().playlist_revision == 0


def test_progress_snapshot_and_clock_expiry_preserve_business_authorities(real_client, monkeypatch):
    """DB timestamps or an unregistered expired cache cannot represent fresh current progress."""
    playback, player, library, coordinator, clock = setup_observation(real_client)
    from server.app.services.state_service import StateService

    output = cached_output(playback, player)
    client = real_client[0]
    monkeypatch.setattr(app.state, 'playback_service', playback)
    response = mutate(client, 'POST', '/api/playback/seek', {'seconds': 0}, key='observation-existing')
    assert response.status_code == 200, response.text
    playlist = run(app.state.playlist_service.create_playlist('preserved'))
    run(app.state.playlist_service.add_song(playlist.playlist_id, 'a'))
    run(app.state.playlist_service.set_favorite('a', True))
    before = server_snapshot(playback)
    songs = run(library.list_songs())
    playlists = run(app.state.playlist_service.revision_content())
    terminals = app.state.idempotency_service._repository
    terminal = run(terminals.get_by_key('observation-existing'))
    assert terminal is not None
    entries, outputs = run(player.queue_entries()), run(player.outputs())

    async def no_control(*args, **kwargs):
        raise AssertionError('read-only observation performed player control or recovery')

    for name in ('play', 'pause', 'stop', 'next', 'previous', 'seek', 'queue_add',
                 'queue_delete', 'queue_move', 'queue_clear', 'queue_play', 'set_output_enabled',
                 'set_volume', 'set_repeat', 'set_random', 'update_database'):
        monkeypatch.setattr(player, name, no_control)
    monkeypatch.setattr(playback, 'reconcile_external_status', no_control)
    run(playback.observe())
    marker = coordinator.marker()
    player._elapsed = 11
    clock.advance(1)
    observation = run(playback.observe())
    assert observation.position_seconds == 11 and observation.observed_at == clock.now
    assert coordinator.marker().sequence == marker.sequence + 1
    state = StateService(
        coordinator=coordinator, queue_manager=playback.queue_manager,
        history_service=playback.history_service, library_service=app.state.library_service,
        output_snapshot=lambda: output, playback_service=playback,
    )
    first = run(state.get_full_snapshot())
    assert first.playback_observation == observation
    assert first.playback.position_seconds == before[1].position_seconds == 0
    marker = coordinator.marker()
    clock.advance(1)
    run(playback.observe())
    assert coordinator.marker() == marker, 'timestamp alone generated an invalidation'
    clock.advance(6)
    assert run(state.get_full_snapshot()).playback_observation.freshness == 'fresh'
    assert coordinator.marker() == marker

    async def forbidden(*args, **kwargs):
        raise AssertionError('cached snapshot performed player control or external I/O')

    for name in ('status', 'queue_entries', 'play', 'seek', 'stop', 'queue_add'):
        monkeypatch.setattr(player, name, forbidden)
    monkeypatch.setattr(playback, 'reconcile_external_status', forbidden)
    clock.advance(.01)
    expired = run(state.get_full_snapshot())
    assert expired.playback_observation.freshness == 'stale'
    assert expired.playback_observation.position_seconds == 11
    assert expired.sequence == marker.sequence + 1 == coordinator.marker().sequence
    assert expired.revisions == {'library': 0, 'playlist': 0}
    assert run(state.get_full_snapshot()).sequence == expired.sequence
    observation.position_seconds = 999
    assert run(playback.get_observation()).position_seconds == 11
    assert first.playback_observation.freshness == 'fresh'
    assert server_snapshot(playback) == before
    assert run(library.list_songs()) == songs
    assert run(app.state.playlist_service.revision_content()) == playlists
    assert run(terminals.get_by_key('observation-existing')) == terminal
    # The saved execution and output facts are unchanged by observation.
    monkeypatch.undo()
    assert run(player.queue_entries()) == entries and run(player.outputs()) == outputs


@pytest.mark.parametrize('drift', ['stop', 'foreign', 'duplicate', 'missing-id', 'queue-mismatch'])
def test_external_drift_never_attaches_progress_or_changes_history(real_client, monkeypatch, drift):
    """URI equality or MPD STOPPED cannot authorize current progress or History STOP."""
    playback, player, _, coordinator, _ = setup_observation(real_client)
    run(playback.observe())
    before = server_snapshot(playback)
    if drift == 'stop':
        run(player.stop())
    elif drift == 'foreign':
        run(player.play('d.flac'))
    elif drift == 'duplicate':
        entries = run(player.queue_entries())
        run(player.queue_play(entries[1].mpd_song_id))
        player._elapsed = 42
    elif drift == 'missing-id':
        original_sample = player.read_execution_sample

        async def without_id():
            sample = await original_sample()
            return sample.model_copy(update={'status': sample.status.model_copy(update={'song_id': None})})

        monkeypatch.setattr(player, 'read_execution_sample', without_id)
    else:
        entries = run(player.queue_entries())
        run(player.queue_move(entries[1].mpd_song_id, entries[0].mpd_song_id))
    marker = coordinator.marker()
    result = run(playback.observe())
    assert result.matches_current is (None if drift == 'missing-id' else False)
    assert result.reconciliation_required
    assert result.position_seconds is result.duration_seconds is None
    assert coordinator.marker().sequence == marker.sequence + 1
    assert coordinator.marker().library_revision == coordinator.marker().playlist_revision == 0
    assert server_snapshot(playback) == before
    assert run(playback.history_service.list_history()) == []


@pytest.mark.parametrize('prior', [False, True])
def test_disconnect_retry_and_restart_never_invent_binding(real_client, prior):
    """Disconnect loses freshness, retry rereads, restart cannot infer occurrence from URI."""
    playback, player, _, coordinator, clock = setup_observation(real_client)
    player._elapsed = 9
    if prior:
        run(playback.observe())
    before = server_snapshot(playback)
    player.disconnect()
    marker = coordinator.marker()
    failed = run(playback.observe())
    assert failed.freshness == ('stale' if prior else 'unknown')
    assert failed.position_seconds == (9 if prior else None)
    assert failed.error_code == 'PLAYER_UNAVAILABLE'
    assert failed.observed_at == (clock.now if prior else None)
    assert coordinator.marker().sequence == marker.sequence + 1
    player.reconnect()
    clock.advance(1)
    recovered = run(playback.observe())
    assert recovered.freshness == 'unknown' and recovered.position_seconds is None
    assert recovered.matches_current is None and recovered.reconciliation_required
    assert run(playback.get_execution_binding()) is None
    assert recovered.error_code is None
    restarted = PlaybackService(
        queue_manager=playback.queue_manager, history_service=playback.history_service,
        autoplay=playback.autoplay, player=player, library_repository=playback.library_repository,
        coordinator=RealtimeCoordinator(coordinator.path), observation_clock=clock,
    )
    unknown = run(restarted.get_observation())
    assert unknown.observed_at is None and unknown.matches_current is None
    assert not unknown.reconciliation_required
    sampled = run(restarted.observe())
    assert sampled.matches_current is None and sampled.reconciliation_required
    assert sampled.freshness == 'unknown' and sampled.position_seconds is None
    assert restarted._coordinator.marker().epoch != coordinator.marker().epoch
    assert server_snapshot(playback) == before


def test_older_overlapping_sample_cannot_replace_newer_accepted_progress(real_client, monkeypatch):
    """Out-of-order external reads cannot overwrite the newer accepted transport sample."""
    playback, player, _, coordinator, _ = setup_observation(real_client)
    original_sample = player.read_execution_sample

    async def scenario():
        sampled, release = asyncio.Event(), asyncio.Event()
        old_task = None

        async def held_status():
            value = await original_sample()
            if asyncio.current_task() is old_task:
                sampled.set()
                await release.wait()
            return value

        monkeypatch.setattr(player, 'read_execution_sample', held_status)
        player._elapsed = 3
        old_task = asyncio.create_task(playback.observe())
        await asyncio.wait_for(sampled.wait(), 1)
        player._elapsed = 12
        latest = await playback.observe()
        assert latest.position_seconds == 12
        marker = coordinator.marker()
        release.set()
        assert (await old_task).position_seconds == 12
        assert (await playback.get_observation()).position_seconds == 12
        assert coordinator.marker() == marker

    run(scenario())


def test_observation_runtime_rolls_back_with_terminal_and_cancels_without_controls(real_client, monkeypatch):
    """Rolling back only SQLite leaves a false occurrence proof or leaked observation cache."""
    from server.app.repositories.database import run_transaction

    playback, player, library, coordinator, _ = setup_observation(real_client)
    baseline = run(playback.observe())
    before = server_snapshot(playback)
    marker = coordinator.marker()

    async def outer(_):
        await playback.next()
        await playback.next()
        with pytest.raises(RuntimeError, match='committed'):
            await playback.observe()
        raise RuntimeError('terminal failure')

    with pytest.raises(RuntimeError, match='terminal failure'):
        run(run_transaction(library.path, outer))
    assert server_snapshot(playback) == before
    assert run(playback.get_observation()) == baseline
    assert coordinator.marker() == marker
    # SQLite cannot undo the external play of b. The old a occurrence proof
    # and cache must be restored, so observation reports this external drift.
    drift = run(playback.observe())
    assert drift.matches_current is False and drift.position_seconds is None
    before = server_snapshot(playback)
    marker = coordinator.marker()
    cache = run(playback.get_observation())

    async def scenario():
        sampled = asyncio.Event()

        async def hung_status():
            sampled.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(player, 'read_execution_sample', hung_status)
        task = asyncio.create_task(playback.observe())
        await asyncio.wait_for(sampled.wait(), 1)
        # No external wait holds the business boundary.
        assert (await asyncio.wait_for(playback.get_observation(), 1)) == cache
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await playback.get_observation() == cache

    run(scenario())
    assert server_snapshot(playback) == before and coordinator.marker() == marker


@pytest.mark.parametrize('command', ['read_execution_sample', 'queue_entries'])
def test_unknown_numbers_and_port_error_stay_nullable(real_client, monkeypatch, command):
    """Missing MPD fields must not turn into zero, and read failures cannot run recovery."""
    playback, player, _, coordinator, _ = setup_observation(real_client)
    original_sample = player.read_execution_sample

    async def unknown_numbers():
        sample = await original_sample()
        return sample.model_copy(update={'status': sample.status.model_copy(update={
            'elapsed_seconds': None, 'duration_seconds': None,
        })})

    monkeypatch.setattr(player, 'read_execution_sample', unknown_numbers)
    before = server_snapshot(playback)
    sample = run(playback.observe())
    assert sample.freshness == 'fresh' and sample.matches_current is True
    assert sample.position_seconds is sample.duration_seconds is None
    player.fail_next(command)
    failed = run(playback.observe())
    assert failed.freshness == 'stale' and failed.error_code == 'PLAYER_COMMAND_ERROR'
    assert failed.position_seconds is failed.duration_seconds is None
    assert server_snapshot(playback) == before
    assert coordinator.marker().library_revision == coordinator.marker().playlist_revision == 0


def test_replaced_port_with_reused_ids_cannot_reuse_old_occurrence_proof(real_client):
    """MPD IDs and URI on a different Port instance do not prove the old occurrence."""
    from server.app.player.mock_mpd import MockMPD

    playback, player, _, coordinator, _ = setup_observation(real_client)
    player._elapsed = 8
    run(playback.observe())
    before = server_snapshot(playback)
    replacement = MockMPD(['a.flac', 'b.flac', 'c.flac'])
    for entry in run(player.queue_entries()):
        run(replacement.queue_add(entry.song_uri))
    run(replacement.play('a.flac'))
    replacement._elapsed = 37
    playback.player = replacement
    result = run(playback.observe())
    assert result.matches_current is None and result.reconciliation_required
    assert result.position_seconds is None and result.freshness == 'unknown'
    assert server_snapshot(playback) == before
    assert coordinator.marker().library_revision == coordinator.marker().playlist_revision == 0


def test_delete_current_binds_confirmed_different_song_successor(real_client):
    """Binding before successor state is saved permanently loses its confirmed progress."""
    playback, player, _, coordinator, _ = setup_observation(real_client)
    run(playback.observe())
    for expected in ('a', 'b'):
        current = next(i for i in run(playback.queue_manager.list_items()) if i.position == 0)
        run(playback.delete(current.queue_item_id))
        before = server_snapshot(playback)
        player._elapsed = 17
        sample = run(playback.observe())
        assert before[1].song_id == before[3].song_id == expected
        assert sample.matches_current is True and sample.freshness == 'fresh'
        assert sample.position_seconds == 17 and not sample.reconciliation_required
        assert server_snapshot(playback) == before
        assert coordinator.marker().library_revision == coordinator.marker().playlist_revision == 0


def test_unparseable_port_sample_degrades_without_swallowing_cancellation(real_client, monkeypatch):
    """Adapter parsing errors are failed external samples, not successful or lost cache reads."""
    playback, player, _, coordinator, _ = setup_observation(real_client)
    player._elapsed = 4
    sample = run(playback.observe())
    before, marker = server_snapshot(playback), coordinator.marker()

    async def malformed():
        raise ValueError('unparseable external status')

    monkeypatch.setattr(player, 'read_execution_sample', malformed)
    failed = run(playback.observe())
    assert failed.freshness == 'stale' and failed.position_seconds == 4
    assert failed.observed_at == sample.observed_at
    assert failed.error_code == 'PLAYER_OBSERVATION_FAILED'
    assert failed.error_message == 'unparseable external status'
    assert server_snapshot(playback) == before
    assert coordinator.marker().sequence == marker.sequence + 1
