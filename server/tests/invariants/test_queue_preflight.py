from __future__ import annotations

import pytest

from server.app.player.models import PlayerState
from server.tests.invariants.test_d6_recovery import capture_controls
from server.tests.support.playback import real_client, run, start

__all__ = ["real_client"]


@pytest.mark.parametrize("paused", [False, True])
@pytest.mark.parametrize("drift", ["extra", "missing", "unbound", "foreign-current"])

def test_user_append_repairs_full_execution_and_restores_ms_current(real_client, monkeypatch, paused, drift):
    client, _, player, service = real_client
    start(client)
    if paused:
        run(service.pause())
    run(player.seek(23))
    if drift == "extra":
        run(player.queue_add("d.flac"))
    elif drift == "missing":
        run(player.queue_delete(run(player.queue_entries())[-1].mpd_song_id))
    elif drift == "unbound":
        service._recovery.invalidate_binding()
    else:
        run(player.queue_play(run(player.queue_entries())[1].mpd_song_id))
    controls = capture_controls(monkeypatch, player)
    run(service.add_to_queue("b"))
    assert controls[0][0] == "queue_clear"
    snapshot = run(service.queue_manager.get_snapshot())
    desired = [f"{item.song_id}.flac" for item in sorted(snapshot.items, key=lambda item: item.position) if item.position >= 0]
    assert [entry.song_uri for entry in run(player.queue_entries())] == desired
    status = run(player.status())
    assert status.song_uri == "a.flac" and status.song_position == 0
    assert status.state == (PlayerState.PAUSED if paused else PlayerState.PLAYING)
    assert status.elapsed_seconds == (0 if drift == "foreign-current" else 23)
    assert run(service.get_execution_binding()) is not None



def test_matching_full_queue_does_not_clear(real_client, monkeypatch):
    client, _, player, service = real_client
    start(client)
    controls = capture_controls(monkeypatch, player)
    run(service.add_to_queue("b"))
    assert not any(name == "queue_clear" for name, _, _ in controls)


@pytest.mark.parametrize("operation", ["play_next", "reorder", "clear", "delete_pending", "delete_current", "start_track", "play_now", "play_song_now", "next", "context"])

def test_every_mutating_entry_clears_drift_before_its_first_command(real_client, monkeypatch, operation):
    from server.app.models.queue import PlaybackContext
    client, _, player, service = real_client
    start(client)
    run(player.queue_add("d.flac"))
    controls = capture_controls(monkeypatch, player)
    queue = run(service.queue_manager.get_snapshot())
    current = next(item for item in queue.items if item.position == 0)
    pending = sorted((item for item in queue.items if item.position > 0), key=lambda item: item.position)
    if operation == "play_next":
        run(service.play_next("b"))
    elif operation == "reorder":
        run(service.reorder(pending[1].queue_item_id, pending[0].queue_item_id))
    elif operation == "clear":
        run(service.clear())
    elif operation.startswith("delete"):
        run(service.delete((current if operation == "delete_current" else pending[0]).queue_item_id))
    elif operation == "start_track":
        run(service.start_track("b"))
    elif operation == "play_now":
        run(service.play_now(pending[0].queue_item_id))
    elif operation == "play_song_now":
        run(service.play_song_now("b"))
    elif operation == "next":
        run(service.next())
    else:
        run(service.play_context(PlaybackContext(context_id="new", source_type="SONGS", ordered_song_ids=("b", "c"))))
    assert controls[0][0] == "queue_clear"
    snapshot = run(service.queue_manager.get_snapshot())
    expected = [f"{item.song_id}.flac" for item in sorted(snapshot.items, key=lambda item: item.position) if item.position >= 0]
    assert [entry.song_uri for entry in run(player.queue_entries())] == expected
    assert run(service.get_execution_binding()) is not None



def test_retry_after_outer_rollback(real_client, monkeypatch):
    client, _, player, service = real_client
    start(client)
    run(player.queue_add('d.flac'))
    original = service._confirm_preserved_state
    controls = capture_controls(monkeypatch, player)

    async def fail():
        raise RuntimeError('business rollback after MPD confirmed')
    monkeypatch.setattr(service, '_confirm_preserved_state', fail)
    with pytest.raises(RuntimeError):
        run(service.add_to_queue('b'))
    monkeypatch.setattr(service, '_confirm_preserved_state', original)
    controls.clear()
    run(service.add_to_queue('b'))
    assert controls == []


def test_next_without_successor_keeps_elapsed(real_client):
    client, _, player, service = real_client
    start(client)
    state = run(service.queue_manager.get_playback_state())
    run(service.queue_manager.set_playback_state(state.model_copy(update={'autoplay_enabled': False})))
    run(service.clear())
    run(player.seek(23))
    run(player.queue_add('d.flac'))
    run(service.next())
    assert run(player.status()).elapsed_seconds == 23


def test_previous_without_played_repairs(real_client):
    client, _, player, service = real_client
    start(client)
    run(player.queue_add('d.flac'))
    run(service.previous())
    assert 'd.flac' not in [e.song_uri for e in run(player.queue_entries())]


def test_selection_retry_after_outer_rollback(real_client, monkeypatch):
    client, _, player, service = real_client
    start(client)
    run(player.queue_add('d.flac'))
    original = service._confirm_preserved_state
    controls = capture_controls(monkeypatch, player)

    async def fail():
        raise RuntimeError('business rollback after MPD confirmed')
    monkeypatch.setattr(service, '_confirm_preserved_state', fail)
    with pytest.raises(RuntimeError):
        run(service.start_track('b'))
    monkeypatch.setattr(service, '_confirm_preserved_state', original)
    controls.clear()
    run(service.start_track('b'))
    assert controls == []


@pytest.mark.parametrize("phase", ["sent", "ack", "confirmed"])

def test_preflight_clear_prefix_retry_never_sends_clear_twice(real_client, monkeypatch, phase):
    client, _, player, service = real_client
    start(client)
    run(player.queue_add("d.flac"))
    journal = service._recovery
    record = journal.record_command
    controls = capture_controls(monkeypatch, player)
    failed = False

    def fault(operation_id, index, receipt):
        nonlocal failed
        if operation_id.endswith("/preflight") and index == 0 and receipt.phase == phase and not failed:
            failed = True
            if phase != "sent":
                record(operation_id, index, receipt)
            raise RuntimeError("preflight fault")
        record(operation_id, index, receipt)

    monkeypatch.setattr(journal, "record_command", fault)
    with pytest.raises(RuntimeError, match="preflight fault"):
        run(service.add_to_queue("b"))
    monkeypatch.setattr(journal, "record_command", record)
    run(service.add_to_queue("b"))
    assert sum(name == "queue_clear" for name, _, _ in controls) == 1
    assert run(service.get_execution_binding()) is not None


@pytest.mark.parametrize("operation", ["next", "previous"])

def test_stopped_navigation_repairs_without_starting(real_client, monkeypatch, operation):
    client, _, player, service = real_client
    start(client)
    run(service.stop())
    run(player.queue_add("d.flac"))
    controls = capture_controls(monkeypatch, player)
    run(getattr(service, operation)())
    assert controls[0][0] == "queue_clear"
    assert not any(name in {"play", "queue_play"} for name, _, _ in controls)
    assert run(player.status()).state == PlayerState.STOPPED
    assert run(service.queue_manager.get_playback_state()).state == "STOPPED"



def test_invalid_preserved_pending_is_checked_before_clear(real_client, monkeypatch):
    from server.app.services.playback_service import PlaybackSongUnavailableError
    client, library, player, service = real_client
    start(client)
    song = run(library.get_song('c'))
    run(library.upsert_song(song.model_copy(update={'availability_status': 'MISSING'})))
    run(player.queue_add('d.flac'))
    target = next(i for i in run(service.queue_manager.get_snapshot()).items if i.song_id == 'b')
    controls = capture_controls(monkeypatch, player)
    with pytest.raises(PlaybackSongUnavailableError):
        run(service.play_now(target.queue_item_id))
    assert controls == []
