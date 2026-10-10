"""The phone fixture must use the real app/Services, never a synthetic state API."""
from fastapi.testclient import TestClient

from server.app.main import app
from server.tools.web_acceptance import configure_acceptance


def test_phone_fixture_switches_real_service_facts_without_a_public_control_api(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'phone.db'))
    original = app.router.lifespan_context
    configure_acceptance(app, tmp_path)
    try:
        with TestClient(app) as client:
            state = client.get('/api/state').json()
            assert state['current_song']['title'] == '夜航 · 本地验收曲'
            assert state['playback_observation']['matches_current'] is True
            assert state['playback_observation']['actual_freshness'] == 'fresh'
            client.portal.call(app.state.acceptance_scene, 'long')
            state = client.get('/api/state').json()
            assert 'Long' in state['current_song']['title']
            assert state['current_song']['artwork'] is None
            client.portal.call(app.state.acceptance_scene, 'unknown')
            state = client.get('/api/state').json()
            assert state['playback_observation']['duration_seconds'] is None
            assert state['current_song']['sample_rate_hz'] is None
            client.portal.call(app.state.acceptance_scene, 'unbound')
            state = client.get('/api/state').json()
            assert state['current_song']['title'] == '夜航 · 本地验收曲'
            assert state['playback_observation']['sync_status'] == 'UNBOUND'
            assert state['playback_observation']['actual_current']['uri'].endswith('external.wav')
            assert state['playback_observation']['matches_current'] is not True
            with client.websocket_connect('/api/realtime') as socket:
                assert socket.receive_json()['state']['playback_observation']['sync_status'] == 'UNBOUND'
            assert client.get('/api/acceptance/scene').status_code == 404
    finally:
        app.router.lifespan_context = original
        del app.state.player
        del app.state.acceptance_scene


def test_w4_fixture_advances_only_playing_and_preserves_pause_resume_seek_target(tmp_path, monkeypatch):
    from server.app.player.models import PlayerState
    from server.tools.web_acceptance import AcceptancePlayer

    stamp = [10.0]
    player = AcceptancePlayer(['fixture.wav'], monotonic=lambda: stamp[0])

    import asyncio

    async def scenario():
        entry = await player.queue_add('fixture.wav')
        await player.queue_play(entry)
        stamp[0] += 2
        assert (await player.read_execution_sample()).status.elapsed_seconds == 2
        await player.pause()
        stamp[0] += 20
        assert (await player.status()).elapsed_seconds == 2
        await player.play()
        stamp[0] += 1
        assert (await player.status()).elapsed_seconds == 3
        await player.seek(37)
        stamp[0] += 2
        sample = await player.read_execution_sample()
        assert sample.status.elapsed_seconds == 39
        assert sample.status.song_id == entry
        assert sample.status.state == PlayerState.PLAYING
        await player.stop()
        stamp[0] += 20
        assert (await player.status()).elapsed_seconds == 0

    asyncio.run(scenario())


def test_w5_fixture_has_selectable_lyrics_and_real_output_controls_without_playback_changes(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'phone.db'))
    original = app.router.lifespan_context
    configure_acceptance(app, tmp_path, advance_clock=True, w5=True)
    try:
        with TestClient(app) as client:
            before = client.get('/api/state').json()
            assert before['current_song']['lyrics'].count('\n') >= 30
            assert before['current_song']['lyrics_format'] == 'lrc'
            assert before['output']['states'][0]['status'] == 'ACTIVE'
            response = client.put('/api/system/output', json={'mode': 'NAS_DAC', 'enabled': False}, headers={'Idempotency-Key': 'w5-disable'})
            assert response.status_code == 200
            assert response.json()['last_request']['status'] == 'SUCCEEDED'
            assert response.json()['states'][0]['status'] == 'INACTIVE'
            after = client.get('/api/state').json()
            for field in ('queue', 'history', 'playback'):
                assert after[field] == before[field]
            assert after['playback_observation']['control_target'] == before['playback_observation']['control_target']
            assert after['output']['states'][0]['sample_rate'] is None
            assert after['current_song']['sample_rate_hz'] == 44100
            client.portal.call(app.state.acceptance_scene, 'long')
            assert client.get('/api/state').json()['current_song']['lyrics_format'] == 'text'
            client.portal.call(app.state.acceptance_scene, 'lyrics-error')
            song = client.get('/api/state').json()['current_song']
            assert song['lyrics_status'] == 'read_error'
            assert song['lyrics'] and song['lyrics_format'] == 'text'
            client.portal.call(app.state.acceptance_scene, 'unknown')
            assert client.get('/api/state').json()['current_song']['lyrics_status'] == 'missing'
    finally:
        app.router.lifespan_context = original
        del app.state.player
        if hasattr(app.state, 'acceptance_scene'):
            del app.state.acceptance_scene
