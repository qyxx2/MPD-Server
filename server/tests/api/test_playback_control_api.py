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
