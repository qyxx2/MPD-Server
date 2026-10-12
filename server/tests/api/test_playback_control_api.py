import pytest

from server.app.main import app
from server.tests.api.test_realtime_state import state_client
from server.tests.invariants.assertions import server_snapshot
from server.tests.support.playback import mutate, real_client, run

__all__ = ['real_client', 'state_client']


def target_for(playback):
    target = run(playback.observe()).control_target
    assert target is not None
    return target.model_dump()


def consume_samples(player, monkeypatch, enabled):
    """Keep MockMPD execution evidence intact, varying only the external mode."""
    mode = {'consume': enabled}
    read = player.read_execution_sample

    async def sample():
        return (await read()).model_copy(update=mode)

    monkeypatch.setattr(player, 'read_execution_sample', sample)
    return mode


@pytest.mark.parametrize('consume', [True, False])
def test_pause_resume_uses_published_target_without_changing_consume(
    state_client, monkeypatch, consume,
):
    client, _, playback, player, _, _, _, _ = state_client
    consume_samples(player, monkeypatch, consume)
    player._elapsed = 37
    paused = mutate(client, 'POST', '/api/playback/pause')
    assert paused.status_code == 200, paused.text
    run(playback.observe())
    snapshot = client.get('/api/state').json()
    assert snapshot['playback']['state'] == 'PAUSED'
    assert snapshot['playback_observation']['sync_status'] == 'CONFIRMED'
    target = snapshot['playback_observation']['control_target']
    assert target is not None
    before = server_snapshot(playback)
    entries = run(player.queue_entries())
    commands = []
    play = player.play

    async def resume_only(uri=None):
        commands.append(uri)
        await play(uri)

    async def forbidden(*args):
        raise AssertionError('resume rebuilt execution or changed modes')

    monkeypatch.setattr(player, 'play', resume_only)
    for name in ('seek', 'queue_play', 'queue_clear', 'queue_add', 'queue_delete',
                 'queue_move', 'set_random', 'set_repeat'):
        monkeypatch.setattr(player, name, forbidden)
    result = mutate(client, 'POST', '/api/playback/resume', {'target': target})
    assert result.status_code == 200, result.text
    assert result.json()['state'] == 'PLAYING'
    assert result.json()['position_seconds'] == 37
    assert commands == [None]
    assert run(player.status()).state.value == 'playing'
    assert run(player.read_execution_sample()).consume is consume
    assert run(player.queue_entries()) == entries
    after = server_snapshot(playback)
    assert after[0] == before[0] and after[2:] == before[2:]
    assert after[1].song_id == before[1].song_id
    assert after[1].playback_context_id == before[1].playback_context_id
    assert after[1].autoplay_enabled == before[1].autoplay_enabled


@pytest.mark.parametrize('initial', [True, False])
def test_resume_rejects_external_consume_change_before_command(
    state_client, monkeypatch, initial,
):
    client, _, playback, player, _, _, _, _ = state_client
    mode = consume_samples(player, monkeypatch, initial)
    run(playback.pause())
    target = target_for(playback)
    before = server_snapshot(playback)
    mode['consume'] = not initial

    async def forbidden(*args):
        raise AssertionError('changed mode target sent resume')

    monkeypatch.setattr(player, 'play', forbidden)
    result = mutate(client, 'POST', '/api/playback/resume', {'target': target})
    assert result.status_code == 409, result.text
    assert result.json()['error']['code'] == 'PLAYBACK_TARGET_CONFLICT'
    assert server_snapshot(playback) == before
    assert client.get('/api/state').json()['playback_observation']['control_target'] is None
    mode['consume'] = initial
    fresh = target_for(playback)
    assert fresh != target  # Rollback and restoring the mode cannot revive this token.


@pytest.mark.parametrize('initial', [True, False])
def test_observed_consume_change_rotates_target(state_client, monkeypatch, initial):
    client, _, playback, player, _, _, _, _ = state_client
    mode = consume_samples(player, monkeypatch, initial)
    run(playback.pause())
    target = target_for(playback)
    mode['consume'] = not initial
    fresh = target_for(playback)
    assert fresh != target
    result = mutate(client, 'POST', '/api/playback/resume', {'target': target})
    assert result.status_code == 409, result.text
    result = mutate(client, 'POST', '/api/playback/resume', {'target': fresh})
    assert result.status_code == 200, result.text


@pytest.mark.parametrize('initial', [True, False])
def test_resume_does_not_confirm_external_consume_change_after_command(
    state_client, monkeypatch, initial,
):
    client, _, playback, player, _, _, _, _ = state_client
    mode = consume_samples(player, monkeypatch, initial)
    run(playback.pause())
    target = target_for(playback)
    before = server_snapshot(playback)
    play = player.play

    async def changed_mode(uri=None):
        await play(uri)
        mode['consume'] = not initial

    monkeypatch.setattr(player, 'play', changed_mode)
    result = mutate(client, 'POST', '/api/playback/resume', {'target': target})
    assert result.status_code == 502, result.text
    assert result.json()['error']['code'] == 'PLAYBACK_RECONCILIATION_FAILED'
    assert server_snapshot(playback) == before
    assert client.get('/api/state').json()['playback_observation']['control_target'] is None


@pytest.mark.parametrize('mode', ['single', 'random', 'repeat', 'error'])
def test_state_does_not_publish_target_rejected_by_mode_or_error(
    state_client, monkeypatch, mode,
):
    client, _, playback, player, _, _, _, _ = state_client
    read = player.read_execution_sample
    run(playback.pause())

    async def unsupported():
        sample = await read()
        if mode in {'random', 'repeat'}:
            return sample.model_copy(update={'status': sample.status.model_copy(update={mode: True})})
        return sample.model_copy(update={mode: '1' if mode == 'single' else 'decoder error'})

    monkeypatch.setattr(player, 'read_execution_sample', unsupported)
    run(playback.observe())
    assert client.get('/api/state').json()['playback_observation']['control_target'] is None


def test_expired_consume_target_requires_fresh_execution_evidence(state_client, monkeypatch):
    client, _, playback, player, _, _, clock, _ = state_client
    mode = consume_samples(player, monkeypatch, True)
    player._elapsed = 37
    run(playback.pause())
    target = target_for(playback)
    clock.advance(6.01)
    assert client.get('/api/state').json()['playback_observation']['control_target'] is None
    # Age alone does not end the binding lifetime; resume must read actual MPD.
    result = mutate(client, 'POST', '/api/playback/resume', {'target': target}, key='fresh-check')
    assert result.status_code == 200, result.text
    run(playback.pause())
    target = target_for(playback)
    clock.advance(6.01)
    mode['consume'] = False
    result = mutate(client, 'POST', '/api/playback/resume', {'target': target}, key='expired-change')
    assert result.status_code == 409, result.text


def test_observed_consume_change_rollback_never_revives_old_target(state_client, monkeypatch):
    client, _, playback, player, _, _, _, _ = state_client
    mode = consume_samples(player, monkeypatch, True)
    run(playback.pause())
    target = target_for(playback)
    mode['consume'] = False

    set_observation = playback._observations._set

    async def rolled_back(observation):
        await set_observation(observation)
        assert observation.control_target.model_dump() != target
        raise RuntimeError('outer rollback')

    with monkeypatch.context() as patch:
        patch.setattr(playback._observations, '_set', rolled_back)
        with pytest.raises(RuntimeError, match='outer rollback'):
            run(playback.observe())
    mode['consume'] = True
    fresh = target_for(playback)
    assert fresh != target
    result = mutate(client, 'POST', '/api/playback/resume', {'target': target})
    assert result.status_code == 409, result.text


@pytest.mark.parametrize('consume', [True, False])
def test_next_previous_preserve_occurrences_with_consume(state_client, monkeypatch, consume):
    client, _, playback, player, _, _, _, _ = state_client
    consume_samples(player, monkeypatch, consume)
    original = server_snapshot(playback)[0]
    current = next(item for item in original.items if item.position == 0)
    successor = next(item for item in original.items if item.position == 1)
    result = mutate(client, 'POST', '/api/playback/next')
    assert result.status_code == 200, result.text
    assert next(item for item in run(playback.queue_manager.list_items())
                if item.position == 0).queue_item_id == successor.queue_item_id
    result = mutate(client, 'POST', '/api/playback/previous')
    assert result.status_code == 200, result.text
    assert next(item for item in run(playback.queue_manager.list_items())
                if item.position == 0).queue_item_id == current.queue_item_id
    assert result.json()['state'] == 'PLAYING'
    assert run(player.read_execution_sample()).consume is consume


@pytest.mark.parametrize('consume', [True, False])
def test_guarded_seek_uses_same_consume_condition(state_client, monkeypatch, consume):
    client, _, playback, player, _, _, _, _ = state_client
    mode = consume_samples(player, monkeypatch, consume)
    run(playback.pause())
    target = target_for(playback)
    before = server_snapshot(playback)
    result = mutate(client, 'POST', '/api/playback/seek', {'seconds': 19, 'target': target})
    assert result.status_code == 200, result.text
    assert result.json()['state'] == 'PAUSED' and result.json()['position_seconds'] == 19
    after = server_snapshot(playback)
    assert after[0] == before[0] and after[2:] == before[2:]
    assert run(player.read_execution_sample()).consume is consume
    mode['consume'] = not consume

    async def forbidden(*args):
        raise AssertionError('changed mode target sent seek')

    monkeypatch.setattr(player, 'seek', forbidden)
    result = mutate(client, 'POST', '/api/playback/seek', {'seconds': 23, 'target': target})
    assert result.status_code == 409, result.text
    assert result.json()['error']['code'] == 'PLAYBACK_TARGET_CONFLICT'
    assert server_snapshot(playback) == after


def test_seek_replay_after_current_change_returns_original_receipt(state_client, monkeypatch):
    client, _, playback, player, _, coordinator, _, _ = state_client
    target = target_for(playback)
    body = {'seconds': 19, 'target': target}
    first = mutate(client, 'POST', '/api/playback/seek', body, key='guarded-replay')
    assert first.status_code == 200, first.text
    run(playback.next())
    before, marker = server_snapshot(playback), coordinator.marker()

    async def forbidden(*args):
        raise AssertionError('terminal replay validated or controlled MPD')

    for name in ('read_execution_sample', 'seek', 'play', 'queue_play', 'status'):
        monkeypatch.setattr(player, name, forbidden)
    replay = mutate(client, 'POST', '/api/playback/seek', body, key='guarded-replay')
    assert replay.status_code == first.status_code and replay.content == first.content
    assert server_snapshot(playback) == before and coordinator.marker() == marker


@pytest.mark.parametrize('body', [{}, {'target': None}, {'target': {'queue_item_id': '', 'token': 't'}},
                                  {'target': {'queue_item_id': 'q', 'token': ''}}])
def test_resume_requires_target(state_client, body):
    client, _, playback, _, _, _, _, _ = state_client
    before = server_snapshot(playback)
    result = mutate(client, 'POST', '/api/playback/resume', body)
    assert result.status_code == 422, result.text
    assert server_snapshot(playback) == before


def test_explicit_null_seek_target_is_rejected(state_client):
    result = mutate(state_client[0], 'POST', '/api/playback/seek', {'seconds': 9, 'target': None})
    assert result.status_code == 422, result.text


def test_legacy_seek_without_target_is_accepted(state_client):
    result = mutate(state_client[0], 'POST', '/api/playback/seek', {'seconds': 9})
    assert result.status_code == 200 and result.json()['position_seconds'] == 9


@pytest.mark.parametrize('operation', ['seek', 'resume'])
def test_token_conflict_is_typed_409(state_client, operation):
    client, _, playback, _, _, _, _, _ = state_client
    target = target_for(playback)
    run(playback.play_now(target['queue_item_id']))
    before = server_snapshot(playback)
    body = {'target': target}
    if operation == 'seek':
        body['seconds'] = 9
    result = mutate(client, 'POST', f'/api/playback/{operation}', body)
    assert result.status_code == 409, result.text
    assert result.json()['error']['code'] == 'PLAYBACK_TARGET_CONFLICT'
    assert server_snapshot(playback) == before


@pytest.mark.parametrize('operation', ['seek', 'resume'])
def test_terminal_failure_does_not_commit_transport_state(state_client, monkeypatch, operation):
    client, _, playback, player, _, coordinator, _, _ = state_client
    player._elapsed = 37
    run(playback.pause())
    target = target_for(playback)
    before, marker = server_snapshot(playback), coordinator.marker()
    repository = app.state.idempotency_service._repository

    async def failed_terminal(**kwargs):
        raise RuntimeError('terminal write failed')

    monkeypatch.setattr(repository, 'create', failed_terminal)
    body = {'target': target}
    if operation == 'seek':
        body['seconds'] = 9
    with pytest.raises(RuntimeError, match='terminal write failed'):
        mutate(client, 'POST', f'/api/playback/{operation}', body, key='failed-terminal')
    assert server_snapshot(playback) == before and coordinator.marker() == marker
    assert run(repository.get_by_key('failed-terminal')) is None
    assert run(playback.get_observation()).control_target is None


def test_resume_success_replay_and_key_requirement(state_client, monkeypatch):
    client, _, playback, player, _, _, _, _ = state_client
    player._elapsed = 37
    run(playback.pause())
    body = {'target': target_for(playback)}
    before = server_snapshot(playback)
    missing_key = client.post('/api/playback/resume', json=body)
    assert missing_key.status_code == 422
    assert missing_key.json()['error']['code'] == 'IDEMPOTENCY_KEY_REQUIRED'
    first = mutate(client, 'POST', '/api/playback/resume', body, key='resume-replay')
    assert first.status_code == 200 and first.json()['position_seconds'] == 37
    after = server_snapshot(playback)
    assert after[0] == before[0] and after[2:] == before[2:]
    run(playback.next())

    async def forbidden(*args):
        raise AssertionError('resume replay touched MPD')

    monkeypatch.setattr(player, 'read_execution_sample', forbidden)
    monkeypatch.setattr(player, 'play', forbidden)
    replay = mutate(client, 'POST', '/api/playback/resume', body, key='resume-replay')
    assert replay.status_code == 200 and replay.content == first.content
