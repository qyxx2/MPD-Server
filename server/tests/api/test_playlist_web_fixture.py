"""B07: real Service/API Playlist DTO and full membership, no MPD I/O."""
from __future__ import annotations

import json
from pathlib import Path

from server.app.models.library import Song
from server.tests.support.playback import real_client, run  # noqa: F401

FIXTURE = Path(__file__).resolve().parents[3] / 'web/tests/fixtures/playlists.json'


def test_playlist_web_fixture_preserves_full_membership(real_client, monkeypatch):  # noqa: F811
    client, repository, _, _ = real_client
    monkeypatch.setattr("server.app.repositories.library_repository._now", lambda: "2026-10-11T00:00:00+00:00")
    for song_id in 'abc':
        run(repository.upsert_song(Song(
            song_id=song_id, title='长标题 / ' + song_id,
            file_uri=f'{song_id}.flac', artists=('艺术家 / 长名',),
            availability_status='MISSING' if song_id == 'c' else 'AVAILABLE',
        )))
    headers = {'Idempotency-Key': 'b07-create'}
    created = client.post('/api/playlists', json={'name': '长歌单名称'}, headers=headers)
    assert created.status_code == 201, created.text
    playlist_id = created.json()['playlist_id']
    path = f'/api/playlists/{playlist_id}'
    for song_id in ('b', 'c', 'a'):
        response = client.post(f'{path}/songs', json={'song_id': song_id}, headers={'Idempotency-Key': f'b07-add-{song_id}'})
        assert response.status_code == 200, response.text
    duplicate = client.post(f'{path}/songs', json={'song_id': 'b'}, headers={'Idempotency-Key': 'b07-duplicate'})
    assert duplicate.status_code == 409
    assert duplicate.json()['error']['code'] == 'DUPLICATE_PLAYLIST_SONG'
    actual = {'detail': client.get(path).json(), 'songs': client.get(f'{path}/songs').json()}
    assert actual['detail']['song_ids'] == ['b', 'c', 'a']
    assert [s['song_id'] for s in actual['songs']['items']] == ['b', 'c', 'a']
    assert actual['songs']['items'][1]['availability_status'] == 'MISSING'
    # Runtime identities/timestamps are not part of this stable serialization golden.
    actual['detail'].update(playlist_id='p', created_at='2026-10-11T00:00:00Z', updated_at='2026-10-11T00:00:00Z')
    assert FIXTURE.exists(), 'B07 golden fixture missing'
    assert actual == json.loads(FIXTURE.read_text())
