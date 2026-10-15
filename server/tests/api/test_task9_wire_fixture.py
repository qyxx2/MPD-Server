"""B10 golden: real SQLite/services/MockPort -> REST receipts and resource reads.

Regenerate: .venv/bin/python -m server.tests.api.test_task9_wire_fixture
Only runtime identities and wall-clock timestamps are normalized.
"""
import json
from pathlib import Path

from server.tests.support.playback import mutate, real_client, run

FIXTURE = Path(__file__).resolve().parents[3] / 'web/tests/fixtures/task9.json'


def build_fixture(client, service):
    # Preserve the observed baseline explicitly after isolating startup tasks.
    client.portal.call(service.observe)
    client.portal.call(client.app.state.output_manager.get_state)
    response = mutate(client, 'POST', '/api/playback/collections/play',
                      {'source_type': 'SONGS', 'song_ids': ['a', 'b', 'c']})
    assert response.status_code == 200, response.text
    playlist = mutate(client, 'POST', '/api/playlists', {'name': 'B10 跨页歌单'}, key='b10-create').json()
    path = f'/api/playlists/{playlist["playlist_id"]}'
    for song_id in ('c', 'a'):
        assert mutate(client, 'POST', f'{path}/songs', {'song_id': song_id}).status_code == 200
        assert mutate(client, 'PUT', f'/api/favorites/{song_id}').status_code == 200

    def capture():
        run(service.observe())
        state = client.get('/api/state').json()
        resources = {
            '/api/library/songs': client.get('/api/library/songs').json(),
            '/api/favorites/members': client.get('/api/favorites/members').json(),
            '/api/playlists': client.get('/api/playlists').json(),
            '/api/playlists/p': client.get(path).json(),
            '/api/playlists/p/songs': client.get(f'{path}/songs').json(),
        }
        for sid in 'abc':
            resources[f'/api/library/songs/{sid}'] = client.get(f'/api/library/songs/{sid}').json()
        # These reads cannot perform control or change domain state.
        after = client.get('/api/state').json()
        for field in ('queue', 'playback', 'history', 'revisions'):
            assert state[field] == after[field]
        return {'snapshot': state, 'resources': resources}

    phases = [capture()]
    receipts = []
    response = mutate(client, 'DELETE', '/api/favorites/c')
    assert response.status_code == 204
    receipts.append(None)
    phases.append(capture())
    response = mutate(client, 'POST', f'{path}/songs', {'song_id': 'b'})
    assert response.status_code == 200, response.text
    receipts.append(response.json())
    phases.append(capture())
    response = mutate(client, 'POST', '/api/playback/songs/b/play')
    assert response.status_code == 200, response.text
    receipts.append(response.json())
    phases.append(capture())
    assert phases[0]['resources']['/api/favorites/members']['song_ids'] == ['a', 'c']
    assert phases[1]['resources']['/api/favorites/members']['song_ids'] == ['a']
    assert phases[2]['resources']['/api/playlists/p']['song_ids'] == ['c', 'a', 'b']
    assert phases[3]['snapshot']['current_song']['song_id'] == 'b'
    pending_before = [i['queue_item_id'] for i in phases[2]['snapshot']['queue']['items'] if i['position'] > 0]
    pending_after = [i['queue_item_id'] for i in phases[3]['snapshot']['queue']['items'] if i['position'] > 0]
    assert pending_after[:len(pending_before)] == pending_before
    identities = {playlist['playlist_id']: 'p'}
    identity_fields = {'epoch', 'queue_item_id', 'playback_context_id', 'session_id', 'token', 'bound_queue_item_id'}
    time_fields = {'captured_at', 'updated_at', 'created_at', 'observed_at', 'started_at', 'ended_at',
                   'last_scanned_at', 'last_seen_at', 'covered_playback_updated_at'}

    def normalize(value, field=''):
        if isinstance(value, dict):
            return {key: normalize(item, key) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item, field) for item in value]
        if isinstance(value, str):
            if field in time_fields:
                return '2026-10-11T00:00:00Z'
            if field in identity_fields and value not in identities:
                identities[value] = f'{field}-{len(identities)}'
            return identities.get(value, value)
        return value

    return normalize({'phases': phases, 'receipts': receipts})


def test_task9_server_fixture_to_resource_action_route_convergence(real_client):
    client, _, _, service = real_client
    expected = json.loads(FIXTURE.read_text())
    assert build_fixture(client, service) == expected


if __name__ == '__main__':
    from tempfile import TemporaryDirectory

    from pytest import MonkeyPatch

    from server.tests.conftest import isolate_application_observer

    with TemporaryDirectory() as directory, MonkeyPatch.context() as patch:
        isolate_application_observer.__wrapped__(patch)
        fixture = real_client.__wrapped__(Path(directory), patch)
        client, _, _, service = next(fixture)
        try:
            FIXTURE.write_text(json.dumps(build_fixture(client, service), ensure_ascii=False, indent=2) + '\n')
        finally:
            fixture.close()
