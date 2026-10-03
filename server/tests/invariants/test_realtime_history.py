from __future__ import annotations

from shutil import copy2

from server.app.main import app
from server.app.player.mock_mpd import MockMPD
from server.app.services import library_scanner as scanner_module
from server.app.services.library_scanner import LibraryScanner
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.tests.invariants.test_realtime_snapshot import cached_output, make_state
from server.tests.invariants.test_realtime_transitions import wire
from server.tests.support.playback import run


def test_history_unavailability_preserves_events_and_has_entries(
    real_client, tmp_path, media_fixture_dir, monkeypatch,
):
    """RT-HISTORY: playable filtering or active-as-persisted loses history meaning."""
    client, repository, player, original = real_client
    history = original.history_service
    assert hasattr(history, 'get_availability'), 'History availability facade is missing'
    empty = run(history.get_availability())
    assert empty.model_dump() == {'has_entries': False, 'active_event': None, 'session_id': None}
    root = tmp_path / 'music'
    root.mkdir()
    target = root / 'track.flac'
    copy2(media_fixture_dir / 'metadata.flac', target)
    coordinator = RealtimeCoordinator(repository.path)
    scanner = LibraryScanner(repository, coordinator=coordinator)
    song_id = run(scanner.scan_paths([target])).added_song_ids[0]
    player = MockMPD([str(target)])
    original.player = player
    playback = wire(original, None, coordinator)
    run(playback.start_track(song_id))
    active = run(history.get_availability())
    assert not active.has_entries and active.active_event.song_id == song_id
    session = active.session_id
    run(playback.start_track(song_id))
    # Repeated plays of one Song are independent occurrences and permanent events.
    run(playback.start_track(song_id))
    state = make_state(playback, app.state.library_service, coordinator, cached_output(playback, player))
    saved = client.get('/api/history').json()
    assert saved['count'] == 2
    assert len({e['history_id'] for e in saved['items']}) == 2
    played = client.get('/api/history/played').json()
    queue = run(playback.queue_manager.get_snapshot())
    source = run(app.state.library_service.get_song(song_id))
    baseline = run(state.get_full_snapshot())
    assert baseline.history.has_entries and baseline.history.session_id == session
    assert all(e['reason'] == 'SWITCH_AWAY' and e['session_id'] == session
               and e['started_at'] and e['ended_at'] for e in saved['items'])
    playlists = app.state.playlist_service
    playlist = run(playlists.create_playlist('preserved history song'))
    run(playlists.add_song(playlist.playlist_id, song_id))
    run(playlists.set_favorite(song_id, True))
    memberships = run(playlists.revision_content())

    def preserved(status):
        snapshot = run(state.get_full_snapshot())
        assert snapshot.history == baseline.history
        assert snapshot.queue == queue
        assert snapshot.playback == baseline.playback
        assert snapshot.current_song.song_id == song_id
        assert snapshot.current_song.title == source.title
        assert snapshot.current_song.availability_status == status
        assert snapshot.revisions['playlist'] == 0
        assert client.get('/api/history').json() == saved
        assert client.get('/api/history/played').json() == played
        assert run(playlists.revision_content()) == memberships
        return snapshot

    with monkeypatch.context() as patch:
        def unreadable(_):
            raise PermissionError('unreadable fixture')

        patch.setattr(scanner_module, 'parse_media_file', unreadable)
        run(scanner.scan_paths([target]))
    unreadable = preserved('UNREADABLE')
    run(scanner.scan_paths([target]))
    restored = preserved('AVAILABLE')
    moved = tmp_path / 'saved-track.flac'
    target.rename(moved)
    run(scanner.scan_full(root))
    missing = preserved('MISSING')
    moved.rename(target)
    run(scanner.scan_full(root))
    available = preserved('AVAILABLE')
    assert [s.revisions['library'] for s in (baseline, unreadable, restored, missing, available)] == [1, 2, 3, 4, 5]
