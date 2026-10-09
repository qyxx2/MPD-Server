import pytest

from server.app.repositories.database import run_transaction
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_realtime_observation import setup_observation
from server.tests.support.playback import run


def test_elapsed_does_not_rotate_target(real_client):
    playback, player, _, _, _ = setup_observation(real_client)
    before = server_snapshot(playback)
    first = run(playback.observe()).control_target
    assert first is not None
    player._elapsed = 23
    assert run(playback.observe()).control_target == first
    assert run(playback.get_observation()).control_target == first
    assert server_snapshot(playback) == before


def require(playback, target):
    async def check(_):
        return await playback._require_control_target(target)
    return run(run_transaction(playback.library_repository.path, check))


def test_old_target_rejected_after_same_item_replay(real_client):
    playback, _, _, _, _ = setup_observation(real_client)
    target = run(playback.observe()).control_target
    run(playback.play_now(target.queue_item_id))
    fresh = run(playback.observe()).control_target
    assert fresh.queue_item_id == target.queue_item_id and fresh != target
    with pytest.raises(ValueError, match='target'):
        require(playback, target)


def test_restart_and_reconnect_reject_old_target(real_client):
    from server.app.services.playback_service import PlaybackService
    playback, player, _, _, _ = setup_observation(real_client)
    target = run(playback.observe()).control_target
    restarted = PlaybackService(
        queue_manager=playback.queue_manager, history_service=playback.history_service,
        autoplay=playback.autoplay, player=player, library_repository=playback.library_repository,
    )
    with pytest.raises(ValueError, match='target'):
        require(restarted, target)
    player.disconnect()
    player.reconnect()
    with pytest.raises(ValueError, match='target'):
        require(playback, target)
    assert run(playback.observe()).control_target is None


def test_current_leaves_and_returns_rejects_old_target(real_client):
    playback, player, _, _, _ = setup_observation(real_client)
    target = run(playback.observe()).control_target
    entries = run(player.queue_entries())
    run(player.queue_play(entries[1].mpd_song_id))
    assert run(playback.observe()).control_target is None
    run(player.queue_play(entries[0].mpd_song_id))
    fresh = run(playback.observe()).control_target
    assert fresh is not None and fresh != target
    with pytest.raises(ValueError, match='target'):
        require(playback, target)


def test_rollback_never_revives_invalidated_target(real_client):
    playback, _, library, _, _ = setup_observation(real_client)
    target = run(playback.observe()).control_target
    before = server_snapshot(playback)

    async def failing(_):
        await playback.play_now(target.queue_item_id)
        raise RuntimeError('terminal failure')

    with pytest.raises(RuntimeError, match='terminal failure'):
        run(run_transaction(library.path, failing))
    assert server_snapshot(playback) == before
    with pytest.raises(ValueError, match='target'):
        require(playback, target)
    assert run(playback.get_observation()).control_target is None


def test_pending_rebind_cannot_accept_stale_target(real_client):
    playback, _, _, _, _ = setup_observation(real_client)
    target = run(playback.observe()).control_target
    run(playback.add_to_queue('c'))
    fresh = run(playback.observe()).control_target
    assert fresh is not None and fresh != target
    with pytest.raises(ValueError, match='target'):
        require(playback, target)


def test_stop_terminal_rollback_never_revives_target(real_client):
    from server.app.services.playback_control import PlaybackTargetConflictError
    playback, player, library, _, _ = setup_observation(real_client)
    target = run(playback.observe()).control_target
    before = server_snapshot(playback)

    async def failing(_):
        await playback.stop()
        raise RuntimeError('stop terminal failure')

    with pytest.raises(RuntimeError, match='stop terminal failure'):
        run(run_transaction(library.path, failing))
    assert server_snapshot(playback) == before
    assert run(playback.get_observation()).control_target is None
    # Restarting the same external entry must not make the pre-Stop token valid.
    run(player.play())
    with pytest.raises(PlaybackTargetConflictError):
        require(playback, target)
