from __future__ import annotations

import pytest

from server.app.models.library import Song
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.tests.invariants.assertions import server_snapshot
from server.tests.invariants.test_d6_recovery import capture_controls
from server.tests.support.playback import mutate, real_client, run, start

__all__ = ['real_client']


def test_key_required_and_unavailable_validation_precedes_control(real_client, monkeypatch):
    client, library, player, service = real_client
    controls = capture_controls(monkeypatch, player)
    before = server_snapshot(service)
    missing_key = client.post('/api/playback/songs/a/play')
    assert missing_key.status_code == 422
    assert missing_key.json()['error']['code'] == 'IDEMPOTENCY_KEY_REQUIRED'
    run(library.upsert_song(Song(song_id='missing-file', title='Missing', file_uri='d.flac', availability_status='MISSING')))
    for song in ('unknown', 'missing-file'):
        response = mutate(client, 'POST', f'/api/playback/songs/{song}/play', key=song)
        assert response.status_code == 404, response.text
        assert response.json()['error']['code'] == 'PLAYBACK_REQUEST_INVALID'
        assert run(IdempotencyRepository(library.path).get_by_key(song)) is None
    assert controls == [] and server_snapshot(service) == before


def test_replay_returns_original_occurrence_after_current_changes(real_client, monkeypatch):
    client, library, player, service = real_client
    start(client)
    first = mutate(client, 'POST', '/api/playback/songs/b/play', key='first')
    assert first.status_code == 200, first.text
    assert set(first.json()) == {'queue_item_id', 'song_id', 'position', 'source', 'playback_context_id'}
    second = mutate(client, 'POST', '/api/playback/songs/b/play', key='second')
    assert second.status_code == 200
    assert first.json()['queue_item_id'] != second.json()['queue_item_id']
    # Replay is terminal lookup, independent of current target/catalog eligibility.
    song = run(library.get_song('b'))
    run(library.upsert_song(song.model_copy(update={'availability_status': 'MISSING'})))
    before = server_snapshot(service)
    controls = capture_controls(monkeypatch, player)
    replay = mutate(client, 'POST', '/api/playback/songs/b/play', key='first')
    assert replay.status_code == 200 and replay.content == first.content
    assert server_snapshot(service) == before and controls == []
    for path, body in [('/api/playback/songs/a/play', None), ('/api/playback/songs/b/play', {'unexpected': True})]:
        conflict = mutate(client, 'POST', path, body, key='first')
        assert conflict.status_code == 409
        assert conflict.json()['error']['code'] == 'IDEMPOTENCY_KEY_CONFLICT'
    assert server_snapshot(service) == before and controls == []


def test_failed_intent_cannot_change_payload_and_new_key_is_distinct(real_client, monkeypatch):
    client, library, player, service = real_client
    start(client)
    repo = IdempotencyRepository(library.path)
    create = repo.create
    async def fail(**kwargs):
        raise RuntimeError('terminal fault')
    # Patch the actual middleware repository, not an unrelated new instance.
    from server.app.main import app
    records = app.state.idempotency_service._repository
    monkeypatch.setattr(records, 'create', fail)
    before = server_snapshot(service)
    with pytest.raises(RuntimeError, match='terminal fault'):
        mutate(client, 'POST', '/api/playback/songs/b/play', key='failed')
    assert server_snapshot(service) == before
    monkeypatch.setattr(records, 'create', create)
    controls = capture_controls(monkeypatch, player)
    changed = mutate(client, 'POST', '/api/playback/songs/b/play', {'changed': True}, key='failed')
    assert changed.status_code == 409
    assert changed.json()['error']['code'] == 'IDEMPOTENCY_KEY_CONFLICT'
    assert controls == [] and server_snapshot(service) == before
    retry = mutate(client, 'POST', '/api/playback/songs/b/play', key='failed')
    assert retry.status_code == 200, retry.text
    assert controls == []
    another = mutate(client, 'POST', '/api/playback/songs/b/play', key='fresh')
    assert another.status_code == 200
    assert another.json()['queue_item_id'] != retry.json()['queue_item_id']


@pytest.mark.parametrize('availability', ['MISSING', 'UNREADABLE'])
def test_unavailable_pending_rejects_before_control_preserving_entire_queue(real_client, monkeypatch, availability):
    client, library, player, service = real_client
    start(client)
    before = server_snapshot(service)
    target = run(service.observe()).control_target
    song = run(library.get_song('b'))
    run(library.upsert_song(song.model_copy(update={'availability_status': availability})))
    controls = capture_controls(monkeypatch, player)
    response = mutate(client, 'POST', '/api/playback/songs/a/play', key='unavailable-pending')
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'PLAYBACK_REQUEST_INVALID'
    assert controls == [] and server_snapshot(service) == before
    # Catalog preflight failure has not even invalidated the current token.
    assert run(service.get_observation()).control_target == target
    assert run(IdempotencyRepository(library.path).get_by_key('unavailable-pending')) is None
