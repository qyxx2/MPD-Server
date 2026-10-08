from __future__ import annotations

import pytest

from server.app.repositories.database import run_transaction
from server.tests.support.playback import run, start


@pytest.mark.parametrize(
    ("action", "expected_active_song"),
    [("stop", None), ("next", "b"), ("play_now", "c")],
)
def test_unknown_departure_then_explicit_stop_does_not_relabel_old_active(
    real_client,
    action,
    expected_active_song,
):
    client, _, player, service = real_client
    start(client)
    history = service.history_service
    history_before = run(history.list_history())
    old_session = history.session_id
    queue = run(service.queue_manager.list_items())
    entries = run(player.queue_entries())

    # MPD has already left the History active occurrence without a certified cause.
    run(player.queue_play(entries[1].mpd_song_id))

    if action == "stop":
        run(service.stop())
    elif action == "next":
        run(service.next())
    else:
        target = next(item for item in queue if item.song_id == "c")
        run(service.play_now(target.queue_item_id))

    assert run(history.list_history()) == history_before
    if action == "stop":
        state = run(service.queue_manager.get_playback_state())
        assert history.active_event is None
        assert history.session_id is None
        assert state is not None and state.autoplay_enabled is False
    else:
        assert history.active_event is not None
        assert history.active_event.song_id == expected_active_song
        assert history.session_id == old_session


def test_discard_preserves_session_and_rolls_back_without_event(real_client):
    client, _, _, service = real_client
    start(client)
    history = service.history_service
    persisted = run(history.list_history())
    old_active = history.active_event
    old_session = history.session_id

    async def discard(_connection):
        history.preserve_active_on_rollback()
        await history.discard_unconfirmed_active()
        assert history.active_event is None
        assert history.session_id == old_session

    run(run_transaction(history.history_repository.path, discard))
    assert run(history.list_history()) == persisted
    assert history.active_event is None
    assert history.session_id == old_session

    run(history.start_track("a", session_id=old_session))
    restored_active = history.active_event

    async def discard_then_fail(_connection):
        history.preserve_active_on_rollback()
        await history.discard_unconfirmed_active()
        assert history.active_event is None
        assert history.session_id == old_session
        raise RuntimeError("outer failure")

    with pytest.raises(RuntimeError, match="outer failure"):
        run(run_transaction(history.history_repository.path, discard_then_fail))

    assert history.active_event == restored_active
    assert history.session_id == old_session
    assert run(history.list_history()) == persisted
    assert old_active is not None
