"""B08 full ordered Favorites read, independent of playable collection."""
import json
from pathlib import Path

from server.app.repositories.playlist_repository import PlaylistRepository
from server.tests.support.playback import mutate, real_client, run  # noqa: F401


def test_favorites_members_preserves_unavailable_order_and_has_no_side_effect(real_client):  # noqa: F811
    client, library, _, service = real_client
    assert client.get('/api/favorites/members').json() == {'song_ids': []}
    song = run(library.get_song('b'))
    run(library.upsert_song(song.model_copy(update={'availability_status': 'MISSING'})))
    for song_id in ('a', 'b', 'c'):
        assert mutate(client, 'PUT', f'/api/favorites/{song_id}').status_code == 200
    repository = PlaylistRepository(service.queue_manager.queue_repository.path)
    expected = run(repository.list_favorite_song_ids())
    before = client.get('/api/state').json()
    response = client.get('/api/favorites/members')
    assert response.status_code == 200, response.text
    assert response.json() == {'song_ids': expected}
    fixture = Path(__file__).resolve().parents[3] / 'web/tests/fixtures/favorites.json'
    assert response.json() == json.loads(fixture.read_text())
    assert 'b' in response.json()['song_ids']
    assert client.get('/api/favorites').json()['unavailable_song_ids'] == ['b']
    after = client.get('/api/state').json()
    for field in ('revisions', 'queue', 'history', 'playback'):
        assert after[field] == before[field]
    assert mutate(client, 'DELETE', '/api/favorites/b').status_code == 204
    assert client.get('/api/favorites/members').json()['song_ids'] == [i for i in expected if i != 'b']
