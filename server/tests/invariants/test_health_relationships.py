"""FINAL-HEALTH-001: real local reads, independent bounded Port observation."""

import asyncio
import hashlib
import sqlite3

from fastapi.testclient import TestClient

from server.app.main import app
from server.app.player.mock_mpd import MockMPD
from server.app.player.ports import PlayerUnavailable


def test_mpd_failure_is_independent_and_health_has_no_control_side_effects(tmp_path, monkeypatch):
    path = tmp_path / 'health.db'
    calls = []

    class Player(MockMPD):
        async def update_database(self):
            calls.append('update')
            raise AssertionError('health must not update')

        async def play(self, song_uri=None):
            calls.append('play')
            raise AssertionError('health must not play')

        async def status(self):
            calls.append('status')
            raise PlayerUnavailable('private connection error')

    player = Player()
    monkeypatch.setenv('DATABASE_PATH', str(path))
    monkeypatch.setattr(app.state, 'player', player, raising=False)
    with TestClient(app) as client:
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        sync = app.state.realtime_coordinator.get_library_sync().model_dump(mode='json')
        response = client.get('/api/health')
        assert response.status_code == 200
        body = response.json()
        assert body['status'] == body['ms']['status'] == 'ok'
        assert body['mpd']['status'] == 'unavailable'
        assert body['mpd']['observed_at']
        assert body['library_sync'] == sync
        assert calls == ['status']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
        assert asyncio.run(player.queue_entries()) == []
        # Break this test's schema only; healthy MPD must not mask local failure.
        with sqlite3.connect(path) as connection:
            connection.execute('DROP TABLE songs')
        response = client.get('/api/health')
        assert response.status_code == 503
        assert response.json()['status'] == response.json()['ms']['status'] == 'error'
        assert response.json()['mpd']['status'] == 'unavailable'
        assert response.json()['library_sync'] == sync
        assert 'private' not in response.text


def test_health_budget_unknown_and_sync_owner(tmp_path, monkeypatch):
    from server.app.models.library_sync import LibrarySyncState
    from server.app.services.health_service import HealthService

    async def run():
        from server.app.repositories.database import initialize_database
        path = str(tmp_path / 'budget.db')
        await initialize_database(path)
        cancelled = asyncio.Event()

        class SlowPlayer(MockMPD):
            async def status(self):
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

        sync = LibrarySyncState(status='FAILED', generation=7, error_code='MPD_SYNC_TIMEOUT')
        health = HealthService(path, SlowPlayer(), lambda: sync, mpd_timeout_seconds=0.01)
        result = await asyncio.wait_for(health.read(), 0.5)
        assert result.status == 'ok'
        assert result.mpd.status == 'unavailable'
        assert cancelled.is_set()
        assert result.library_sync == sync
        # Unverified capabilities mean unknown without contacting the delegate.
        from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
        port = VerifiedPlayerPort(SlowPlayer(), MPDCapabilities.from_commands(set()))
        result = await HealthService(path, port, lambda: sync).read()
        assert result.mpd.status == 'unknown'
        missing = tmp_path / 'absent.db'
        result = await HealthService(str(missing), MockMPD(), lambda: sync).read()
        assert result.status == 'error'
        assert result.mpd.status == 'connected'
        assert not missing.exists()

    asyncio.run(run())
