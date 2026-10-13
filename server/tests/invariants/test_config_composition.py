"""FINAL-CONFIG-001: real composition, isolated DB and deterministic Ports only."""
import asyncio
import importlib
import json
from dataclasses import asdict, replace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from server.app import main
from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.mock_mpd import MockMPD
from server.app.player.models import OutputInfo
from server.app.player.ports import PlayerCommandError


def test_saved_endpoint_and_mode_are_applied_only_at_start(tmp_path, monkeypatch, caplog):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'music.db'))
    monkeypatch.setenv('MUSIC_ROOT', str(tmp_path))
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('MPD_MODE', raising=False)
    path = tmp_path / 'mpd-connection.json'
    path.write_text('{"host":"2001:db8::1","port":16600}')
    monkeypatch.setenv('MPD_HOST', 'http://invalid')
    monkeypatch.setenv('MPD_PORT', 'invalid')
    monkeypatch.setenv('MPD_PASSWORD', 'current-secret')
    created = []

    def adapter(host, *, port, password, uri_mapper):
        created.append((host, port, password))
        player = MockMPD()
        player.disconnect()
        return player

    monkeypatch.setattr(main, 'MPDAdapter', adapter)

    async def scenario():
        application = FastAPI()
        application.include_router(main.system_router)
        async with main.lifespan(application):
            assert hasattr(application.state, 'config'), 'final config is not assembled'
            config = application.state.config
            assert config.mpd_mode == 'real'
            async with AsyncClient(transport=ASGITransport(app=application),
                                   base_url='http://test') as client:
                response = await client.get('/api/system/mpd/connection')
                assert response.status_code == 200
                assert set(response.json()) == {'active', 'saved', 'restart_required'}
                assert 'current-secret' not in response.text and 'password' not in response.text
            player = application.state.playback_service.player
            assert isinstance(player, VerifiedPlayerPort)
            with pytest.raises(PlayerCommandError):
                await player.queue_clear()
            assert application.state.playback_recovery_task is None
            application.state.mpd_connection_service.save(
                main.MPDConnectionAddress(host='next.example', port=6602))
            monkeypatch.setenv('MPD_PASSWORD', 'next-secret')
            assert application.state.config is config
            assert application.state.playback_service.player is player
            assert application.state.mpd_connection_service.active.host == '2001:db8::1'
        async with main.lifespan(FastAPI()):
            pass
        assert created == [('2001:db8::1', 16600, 'current-secret'), ('next.example', 6602, 'next-secret')]
        path.write_text('broken')
        with pytest.raises(ValueError):
            async with main.lifespan(FastAPI()):
                pass
        assert len(created) == 2
        path.unlink()  # only this test's own temporary saved address
        monkeypatch.setenv('MPD_HOST', 'localhost')
        monkeypatch.setenv('MPD_PORT', '6600')
        monkeypatch.setenv('APP_ENV', 'development')
        async with main.lifespan(FastAPI()) as _:
            assert len(created) == 2
    asyncio.run(scenario())
    assert 'current-secret' not in caplog.text and 'next-secret' not in caplog.text


def evidence(tmp_path, host='mpd.example', version='0.23.5'):
    result = replace(MPDCapabilities.from_commands({'status', 'currentsong', 'playlistinfo',
                      'addid', 'deleteid', 'moveid', 'outputs', 'enableoutput', 'disableoutput'}),
                     version=version, verified_operations=frozenset({
                         'queue_entries', 'queue_add', 'queue_delete', 'queue_move', 'set_output_enabled'}))
    data = asdict(result)
    for name, value in list(data.items()):
        if isinstance(value, frozenset):
            data[name] = sorted(value)
    path = tmp_path / 'capabilities.json'
    path.write_text(json.dumps({'endpoint': {'host': host, 'port': 6600},
                               'mpd_version': version, 'result': data}))
    return path, data


@pytest.mark.parametrize('case', ['match', 'endpoint', 'version', 'offline', 'bare', 'invalid'])
def test_capability_evidence_requires_endpoint_and_observed_version(tmp_path, monkeypatch, case):
    loader = importlib.import_module('server.app.player.capability_loader')
    path, data = evidence(tmp_path)
    observed = []

    async def version(host, port):
        observed.append((host, port))
        return None if case == 'offline' else '0.24.0' if case == 'version' else '0.23.5'

    if case == 'bare':
        path.write_text(json.dumps(data))
    if case == 'invalid':
        path.write_text('{"endpoint":{}}')
    async def scenario():
        if case in {'bare', 'invalid'}:
            with pytest.raises(ValueError):
                await loader.load_capabilities(path, host='mpd.example', port=6600,
                                               version_reader=version)
            assert observed == []
            return
        capabilities = await loader.load_capabilities(
            path, host='other.example' if case == 'endpoint' else 'mpd.example',
            port=6600, version_reader=version)
        assert bool(capabilities.verified_operations) == (case == 'match')
        assert bool(capabilities.commands) == (case == 'match')
        if case == 'endpoint':
            assert observed == []
    asyncio.run(scenario())


def test_configured_output_selector_matches_current_name_and_rejects_ambiguity(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'music.db'))
    monkeypatch.setenv('MUSIC_ROOT', str(tmp_path))
    monkeypatch.setenv('OUTPUT_NAME', 'USB DAC')
    monkeypatch.setenv('OUTPUT_PLUGIN', 'alsa')
    application = FastAPI()
    application.state.player = MockMPD()
    application.state.mpd_capabilities = MPDCapabilities.from_commands({'outputs'})
    async def scenario():
        async with main.lifespan(application):
            manager = application.state.output_manager
            one = OutputInfo(id=74, name='USB DAC', plugin='alsa', enabled=True)
            other = OutputInfo(id=1, name='HDMI', plugin='alsa', enabled=False)
            assert manager._select_target((other, one)) is one
            from server.app.services.output_manager import OutputError
            with pytest.raises(OutputError):
                manager._select_target((one, one.model_copy(update={'id': 99})))
    asyncio.run(scenario())


@pytest.mark.parametrize('verified', [True, False])
def test_bound_capabilities_are_installed_before_background_owners(tmp_path, monkeypatch, verified):
    loader = importlib.import_module('server.app.player.capability_loader')
    path, _ = evidence(tmp_path)
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'startup.db'))
    monkeypatch.setenv('MUSIC_ROOT', str(tmp_path))
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('MPD_MODE', 'real')
    monkeypatch.setenv('MPD_HOST', 'mpd.example')
    monkeypatch.setenv('MPD_PORT', '6600')
    monkeypatch.setenv('MPD_CAPABILITIES_PATH', str(path))
    order = []
    async def version(host, port):
        order.append('version')
        return '0.23.5' if verified else None
    monkeypatch.setattr(loader, 'read_endpoint_version', version)
    monkeypatch.setattr(main, 'MPDAdapter', lambda *args, **kwargs: MockMPD())
    original = main.initialize_database
    async def initialize(path):
        order.append('database')
        return await original(path)
    monkeypatch.setattr(main, 'initialize_database', initialize)
    async def scenario():
        application = FastAPI()
        async with main.lifespan(application):
            assert order == ['version', 'database']
            assert application.state.playback_service.player.capabilities.supports_operation('queue_add') == verified
            task = application.state.playback_recovery_task
            assert (task is not None) == verified
            assert application.state.output_manager.capabilities is application.state.mpd_info_service.capabilities
        if task is not None:
            assert task.done()
        assert application.state.state_observer_task.done()
    asyncio.run(scenario())


@pytest.mark.parametrize('greeting', [b'OK MPD 0.23.5\n', b'wrong\n', b''])
def test_version_confirmation_reads_only_greeting_and_closes_transport(monkeypatch, greeting):
    loader = importlib.import_module('server.app.player.capability_loader')
    class Writer:
        closed = False
        def write(self, data):
            raise AssertionError('startup version confirmation sent an MPD command')
        def close(self):
            self.closed = True
        async def wait_closed(self):
            pass
    writer = Writer()
    async def connect(host, port):
        assert (host, port) == ('2001:db8::1', 16600)
        reader = asyncio.StreamReader()
        reader.feed_data(greeting)
        reader.feed_eof()
        return reader, writer
    monkeypatch.setattr(loader.asyncio, 'open_connection', connect)
    observed = asyncio.run(loader.read_endpoint_version('2001:db8::1', 16600))
    assert observed == ('0.23.5' if greeting.startswith(b'OK MPD ') else None)
    assert writer.closed
