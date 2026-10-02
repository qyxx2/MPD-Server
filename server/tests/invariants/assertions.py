from server.app.player.models import PlayerState
from server.tests.support.playback import run


def server_snapshot(service):
    """Persisted authorities and the independent in-memory History session."""
    return (
        run(service.queue_manager.queue_repository.get_snapshot()),
        run(service.queue_manager.get_playback_state()),
        run(service.history_service.list_history()),
        service.history_service.active_event,
        service.history_service.session_id,
    )


def assert_execution_relationship(service, player, *, current_id=None):
    """I1/I2: ordered occurrence bijection, actual status and current identity.

    QueueItem IDs and MPD IDs are different namespaces. The execution position
    relates them; Song/URI alone cannot identify a repeated occurrence.
    """
    items = run(service.queue_manager.list_items())
    execution = sorted((i for i in items if i.position >= 0), key=lambda i: i.position)
    entries = run(player.queue_entries())
    assert len(entries) == len(execution)
    assert len({i.queue_item_id for i in execution}) == len(execution)
    assert len({e.mpd_song_id for e in entries}) == len(entries)
    assert [e.position for e in entries] == list(range(len(entries)))
    bindings = {}
    for item, entry in zip(execution, entries, strict=True):
        song = run(service.library_repository.get_song(item.song_id))
        assert entry.song_uri == song.file_uri
        bindings[item.queue_item_id] = entry
    assert not {i.queue_item_id for i in items if i.position < 0} & bindings.keys()
    state = run(service.queue_manager.get_playback_state())
    status = run(player.status())
    assert status.state == PlayerState(state.state.lower())
    current = next((i for i in execution if i.position == 0), None)
    if current_id is not None:
        assert current.queue_item_id == current_id
    if current is not None:
        entry = bindings[current.queue_item_id]
        assert state.song_id == current.song_id
        assert status.song_id == entry.mpd_song_id
        assert status.song_position == entry.position
        assert status.song_uri == entry.song_uri
    if state.state == "STOPPED":
        assert service.history_service.active_event is None
        assert service.history_service.session_id is None
    else:
        assert service.history_service.active_event.song_id == current.song_id
    return bindings
