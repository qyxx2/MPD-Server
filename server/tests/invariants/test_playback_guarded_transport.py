import pytest

from server.app.player.models import PlayerState
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_realtime_observation import setup_observation
from server.tests.support.playback import run


def paused(real_client):
    playback, player, _, _, _ = setup_observation(real_client)
    player._elapsed = 37
    run(playback.pause())
    target = run(playback.observe()).control_target
    assert target is not None
    return playback, player, target


def test_resume_preserves_occurrence_position_and_history(real_client, monkeypatch):
    playback, player, target = paused(real_client)
    before = server_snapshot(playback)
    entries = run(player.queue_entries())
    original_play = player.play
    commands = []

    async def play(uri=None):
        commands.append(uri)
        await original_play(uri)

    monkeypatch.setattr(player, 'play', play)
    result = run(playback.resume(target))
    assert commands == [None]
    assert result.state == 'PLAYING' and result.position_seconds == 37
    assert run(player.status()).state == PlayerState.PLAYING
    after = server_snapshot(playback)
    assert after[0] == before[0] and after[2:] == before[2:]
    assert after[1].song_id == before[1].song_id
    assert after[1].playback_context_id == before[1].playback_context_id
    assert after[1].autoplay_enabled == before[1].autoplay_enabled
    assert run(player.queue_entries()) == entries


def test_seek_target_conflict_sends_no_command(real_client, monkeypatch):
    from server.app.services.playback_control import PlaybackTargetConflictError
    playback, player, target = paused(real_client)
    run(playback.next())
    before = server_snapshot(playback)

    async def forbidden(*args):
        raise AssertionError('stale seek sent a command')

    monkeypatch.setattr(player, 'seek', forbidden)
    with pytest.raises(PlaybackTargetConflictError):
        run(playback.seek(9, target=target))
    assert server_snapshot(playback) == before


def test_same_uri_is_not_same_target(real_client, monkeypatch):
    from server.app.services.playback_control import PlaybackTargetConflictError
    playback, player, target = paused(real_client)
    entries = run(player.queue_entries())
    run(player.queue_play(entries[1].mpd_song_id))  # Same URI, different occurrence.
    before = server_snapshot(playback)

    async def forbidden(*args):
        raise AssertionError('foreign occurrence received seek')

    monkeypatch.setattr(player, 'seek', forbidden)
    with pytest.raises(PlaybackTargetConflictError):
        run(playback.seek(9, target=target))
    assert server_snapshot(playback) == before


@pytest.mark.parametrize('operation', ['seek', 'resume'])
def test_external_drift_after_command_is_not_success(real_client, monkeypatch, operation):
    from server.app.services.playback_service import PlaybackReconciliationError
    playback, player, target = paused(real_client)
    before = server_snapshot(playback)
    original = getattr(player, 'play' if operation == 'resume' else 'seek')
    entries = run(player.queue_entries())
    commands = []

    async def drift(*args):
        commands.append(args)
        await original(*args)
        await player.queue_play(entries[1].mpd_song_id)

    monkeypatch.setattr(player, 'play' if operation == 'resume' else 'seek', drift)
    with pytest.raises(PlaybackReconciliationError):
        run(playback.resume(target) if operation == 'resume' else playback.seek(9, target=target))
    assert len(commands) == 1  # No compensating command to the successor.
    assert server_snapshot(playback) == before
    assert run(playback.get_observation()).control_target is None


@pytest.mark.parametrize('operation', ['seek', 'resume'])
def test_confirmation_failure_preserves_business_state(real_client, monkeypatch, operation):
    from server.app.player.ports import PlayerCommandError
    playback, player, target = paused(real_client)
    before = server_snapshot(playback)
    original = getattr(player, 'play' if operation == 'resume' else 'seek')

    async def fail_confirmation(*args):
        await original(*args)
        player.fail_next('read_execution_sample')

    monkeypatch.setattr(player, 'play' if operation == 'resume' else 'seek', fail_confirmation)
    with pytest.raises(PlayerCommandError):
        run(playback.resume(target) if operation == 'resume' else playback.seek(9, target=target))
    assert server_snapshot(playback) == before
    assert run(playback.get_observation()).control_target is None


def test_legacy_seek_stays_compatible(real_client):
    playback, player, _ = paused(real_client)
    before = server_snapshot(playback)
    assert run(playback.seek(9)).position_seconds == 9
    assert run(player.status()).elapsed_seconds == 9
    after = server_snapshot(playback)
    assert after[0] == before[0] and after[2:] == before[2:]


def test_resume_noop_does_not_create_history(real_client, monkeypatch):
    playback, player, _, _, _ = setup_observation(real_client)
    target = run(playback.observe()).control_target
    before = server_snapshot(playback)

    async def forbidden(*args):
        raise AssertionError('PLAYING resume replayed track')

    monkeypatch.setattr(player, 'play', forbidden)
    result = run(playback.resume(target))
    assert result == before[1]
    assert server_snapshot(playback) == before


@pytest.mark.parametrize('missing', ['before', 'after', 'nonfinite'])
def test_resume_missing_position_evidence_is_not_success(real_client, monkeypatch, missing):
    from server.app.services.playback_service import PlaybackReconciliationError
    playback, player, target = paused(real_client)
    before = server_snapshot(playback)
    read = player.read_execution_sample
    play = player.play
    commands = []

    async def incomplete():
        sample = await read()
        if missing in {'before', 'nonfinite'} or commands:
            return sample.model_copy(update={'status': sample.status.model_copy(update={
                'elapsed_seconds': float('inf') if missing == 'nonfinite' else None,
            })})
        return sample

    async def replay_instead_of_resume(uri=None):
        commands.append(uri)
        await play(uri)
        player._elapsed = 0

    monkeypatch.setattr(player, 'read_execution_sample', incomplete)
    monkeypatch.setattr(player, 'play', replay_instead_of_resume)
    with pytest.raises(PlaybackReconciliationError):
        run(playback.resume(target))
    assert commands == ([None] if missing == 'after' else [])
    assert server_snapshot(playback) == before
    if missing == 'after':
        assert run(playback.get_observation()).control_target is None
