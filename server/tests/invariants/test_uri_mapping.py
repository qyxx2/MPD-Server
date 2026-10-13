"""FINAL-URI: real Adapter protocol boundary + existing Service/SQLite owners."""
import asyncio
import importlib
import shlex

import pytest

from server.app.models.queue import PlaybackContext
from server.app.player.mock_mpd import MockMPD
from server.app.player.mpd_adapter import MPDAdapter
from server.app.player.ports import PlayerCommandError
from server.app.repositories.database import run_transaction
from server.tests.support.playback import run


class ProtocolMusic:
    """Deterministic protocol peer; receives only MPD-relative paths."""
    def __init__(self, raw_uri):
        self.player = MockMPD([raw_uri])
        self.received = []

    async def handle(self, reader, writer):
        writer.write(b'OK MPD 0.23.5\n')
        await writer.drain()
        try:
            while raw := await reader.readline():
                line = raw.decode().rstrip('\r\n')
                self.received.append(line)
                verb, *args = shlex.split(line)
                output = ''
                if verb == 'status':
                    sample = await self.player.read_execution_sample()
                    s = sample.status
                    state = {'playing': 'play', 'paused': 'pause', 'stopped': 'stop'}[s.state.value]
                    output = (f'partition: default\nplaylist: {sample.playlist_version}\n'
                              f'playlistlength: {len(sample.entries)}\nstate: {state}\n'
                              'single: 0\nconsume: 0\nrepeat: 0\nrandom: 0\n'
                              f'elapsed: {s.elapsed_seconds or 0}\nduration: 300\n')
                    if s.song_id is not None:
                        output += f'song: {s.song_position}\nsongid: {s.song_id}\n'
                elif verb == 'playlistinfo':
                    output = ''.join(f'file: {e.song_uri}\nPos: {e.position}\nId: {e.mpd_song_id}\n'
                                     for e in await self.player.queue_entries())
                elif verb == 'currentsong':
                    s = await self.player.status()
                    if s.song_uri:
                        output = f'file: {s.song_uri}\n'
                elif verb == 'addid':
                    output = f'Id: {await self.player.queue_add(args[0])}\n'
                elif verb == 'clear':
                    await self.player.queue_clear()
                elif verb == 'moveid':
                    source, position = map(int, args)
                    entries = [e for e in await self.player.queue_entries() if e.mpd_song_id != source]
                    before = entries[position].mpd_song_id if position < len(entries) else None
                    await self.player.queue_move(source, before)
                elif verb == 'deleteid':
                    await self.player.queue_delete(int(args[0]))
                elif verb == 'playid':
                    await self.player.queue_play(int(args[0]))
                elif verb == 'play':
                    await self.player.play()
                elif verb == 'stop':
                    await self.player.stop()
                elif verb in {'repeat', 'random'}:
                    await getattr(self.player, 'set_' + verb)(args[0] == '1')
                else:
                    raise AssertionError(f'unexpected protocol command: {line}')
                writer.write((output + 'OK\n').encode())
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


def test_mapped_execution_and_current_confirmation_preserve_occurrences(real_client, tmp_path, monkeypatch, caplog):
    _, library, _, service = real_client
    root = tmp_path / 'music'
    root.mkdir()
    local = str(root / 'A/中文 空格.flac')
    raw = 'shared/A/中文 空格.flac'
    song = run(library.get_song('a'))
    run(library.upsert_song(song.model_copy(update={'file_uri': local})))

    async def no_refill(context):
        return []
    monkeypatch.setattr(service.autoplay, 'refill', no_refill)

    async def scenario():
        mapper = importlib.import_module('server.app.player.music_uri').MusicUriMapper(root, 'shared')
        peer = ProtocolMusic(raw)
        server = await asyncio.start_server(peer.handle, '127.0.0.1', 0)
        adapter = MPDAdapter('127.0.0.1', server.sockets[0].getsockname()[1], uri_mapper=mapper)
        service.player = adapter
        try:
            await service.play_context(PlaybackContext(
                context_id='mapped-duplicates', source_type='SONGS', ordered_song_ids=('a', 'a')))
            items = (await service.queue_manager.get_snapshot()).items
            first, second = items[:2]
            assert first.queue_item_id != second.queue_item_id
            binding = await service.get_execution_binding()
            assert binding.entries == ((first.queue_item_id, 1, local), (second.queue_item_id, 2, local))
            sample = await adapter.read_execution_sample()
            assert tuple(e.song_uri for e in sample.entries) == (local, local)
            assert sample.status.song_uri == local
            assert (await adapter.status()).song_uri == local
            assert tuple(e.song_uri for e in await adapter.queue_entries()) == (local, local)
            assert (await service.observe()).matches_current is True
            assert service.history_service.active_event.song_id == 'a'
            assert await service.history_service.list_history() == []
            await service.play_now(second.queue_item_id)
            state = await service.queue_manager.get_playback_state()
            assert state.song_id == 'a'
            current = next(i for i in await service.queue_manager.list_items() if i.position == 0)
            assert current.queue_item_id == second.queue_item_id
            assert (await adapter.read_execution_sample()).status.song_id == 2
            history = await service.history_service.list_history()
            assert len(history) == 1 and history[0].song_id == 'a'
            assert service.history_service.active_event.song_id == 'a'
            await adapter.play(local)
            assert peer.received[-1] == 'playid 2'
            assert [c for c in peer.received if c.startswith('addid')] == [
                'addid "shared/A/中文 空格.flac"'] * 2
            assert (await library.get_song('a')).file_uri == local
            # A same-URI replacement is still a different occurrence: no repair controls.
            async def business_snapshot():
                return (await service.queue_manager.get_snapshot(),
                        await service.queue_manager.get_playback_state(),
                        await service.history_service.list_history(),
                        service.history_service.active_event)
            # External ACK survives an outer rollback; retry uses the same planned occurrence.
            before_retry = await business_snapshot()
            planned = []
            async def rollback(_):
                await service.add_to_queue('a')
                planned.append(await service.queue_manager.get_snapshot())
                raise RuntimeError('owned outer rollback')
            with pytest.raises(RuntimeError, match='owned outer rollback'):
                await run_transaction(library.path, rollback)
            assert await business_snapshot() == before_retry
            before = len(peer.received)
            await service.add_to_queue('a')
            assert await service.queue_manager.get_snapshot() == planned[0]
            assert all(c in {'status', 'playlistinfo', 'currentsong'} for c in peer.received[before:])
            assert all(e.song_uri == local for e in await adapter.queue_entries())
            business = await business_snapshot()
            await peer.player.queue_delete(2)
            await peer.player.queue_add(raw)
            before = len(peer.received)
            assert (await service.reconcile_external_status()).outcome == 'UNKNOWN'
            assert await service.get_execution_binding() is None
            assert await business_snapshot() == business
            assert all(c in {'status', 'playlistinfo'} for c in peer.received[before:])
            # Invalid outbound path is rejected before any protocol command.
            before = len(peer.received)
            with pytest.raises(PlayerCommandError):
                await adapter.queue_add(str(tmp_path / 'outside.flac'))
            assert len(peer.received) == before
            # Foreign raw path fails closed; no rebuild/clear to hide the mismatch.
            peer.player._queue[0] = ('../outside.flac', 1)
            before = len(peer.received)
            with pytest.raises(PlayerCommandError):
                await adapter.read_execution_sample()
            assert all(c in {'status', 'playlistinfo'} for c in peer.received[before:])
            assert 'direction=local_to_mpd' in caplog.text
            assert 'direction=mpd_to_local' in caplog.text
            assert local not in caplog.text and raw not in caplog.text
        finally:
            await adapter.close()
            server.close()
            await server.wait_closed()
    run(scenario())


def test_real_startup_injects_configured_mapper(tmp_path, monkeypatch):
    from fastapi import FastAPI

    from server.app import main
    from server.app.player.capabilities import VerifiedPlayerPort

    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('MPD_MODE', 'real')
    monkeypatch.setenv('MUSIC_ROOT', str(tmp_path))
    monkeypatch.setenv('MPD_URI_PREFIX', 'nas/music')
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'startup.db'))
    monkeypatch.setenv('MPD_CONNECTION_PATH', str(tmp_path / 'saved.json'))
    created = []

    async def no_network(*args):
        raise AssertionError('startup mapping test must not open a connection')

    def adapter(*args, **kwargs):
        result = MPDAdapter(*args, connection_factory=no_network, **kwargs)
        created.append(result)
        return result
    monkeypatch.setattr(main, 'MPDAdapter', adapter)

    async def scenario():
        application = FastAPI()
        async with main.lifespan(application):
            await application.state.state_observer.close()
            await asyncio.gather(application.state.state_observer_task, return_exceptions=True)
            assert isinstance(application.state.playback_service.player, VerifiedPlayerPort)
            assert created[0].uri_mapper is not None
            assert created[0].uri_mapper.to_mpd(str(tmp_path / 'A/曲目.flac')) == 'nas/music/A/曲目.flac'
            assert created[0].uri_mapper.to_local('nas/music/A/曲目.flac') == str(tmp_path / 'A/曲目.flac')
    run(scenario())
