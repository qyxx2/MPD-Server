"""B8: connection setup must preserve identities, duration and the send fence."""
import asyncio

import pytest

from server.app.player.mpd_adapter import MPDAdapter
from server.app.player.ports import PlayerUnavailable


class TagServer:
    def __init__(self, failure=None, entry_count=2):
        self.entry_count = entry_count
        self.failure = failure
        self.commands = []
        self.connections = 0
        self.bytes = 0
        self.ready = asyncio.Event()
        self.release = asyncio.Event()

    async def start(self):
        self.server = await asyncio.start_server(self.handle, '127.0.0.1', 0)
        return self.server.sockets[0].getsockname()[1]

    async def handle(self, reader, writer):
        self.connections += 1
        identity = self.connections
        filtered = False
        writer.write(b'OK MPD 0.23.5\n')
        await writer.drain()
        try:
            while raw := await reader.readline():
                command = raw.decode().strip()
                self.commands.append((identity, command))
                response = ''
                if command == 'tagtypes clear':
                    if self.failure == 'disconnect':
                        return
                    if self.failure == 'ack':
                        writer.write(b'ACK [5@0] {tagtypes} unsupported\n')
                        await writer.drain()
                        continue
                    if self.failure in {'cancel', 'timeout'}:
                        self.ready.set()
                        await self.release.wait()
                        return
                    filtered = self.failure != 'ignored'
                elif command == 'tagtypes':
                    response = '' if filtered else 'tagtype: Artist\n'
                    if self.failure == 'verify-ack':
                        writer.write(b'ACK [4@0] {tagtypes} denied\n')
                        await writer.drain()
                        continue
                elif command == 'status':
                    response = (f'partition: default\nplaylist: 100\nplaylistlength: {self.entry_count}\n'
                                'state: pause\nsingle: 0\nconsume: 0\nrepeat: 0\nrandom: 0\n'
                                'song: 0\nsongid: 10\nelapsed: 12.5\nduration: 180.25\n')
                elif command in {'playlistinfo', 'currentsong', 'find file one.flac'}:
                    count = self.entry_count if command == 'playlistinfo' else 1
                    for pos in range(count):
                        response += f'file: one.flac\nPos: {pos}\nId: {10+pos}\nTime: 180\nduration: 180.25\n'
                        if not filtered:
                            response += 'Artist: artist\nTitle: title\n'
                elif command == 'outputs':
                    response = 'outputid: 0\noutputname: USB\nplugin: alsa\noutputenabled: 1\n'
                payload = (response + 'OK\n').encode()
                self.bytes += len(payload)
                writer.write(payload)
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async def close(self):
        self.release.set()
        self.server.close()
        await self.server.wait_closed()


def test_filter_preserves_all_occurrences_status_duration_and_other_consumers():
    async def run():
        server = TagServer()
        port = await server.start()
        adapter = MPDAdapter('127.0.0.1', port, omit_song_tags=True, password='secret')
        try:
            sample = await adapter.read_execution_sample()
            assert [(e.mpd_song_id, e.position, e.song_uri) for e in sample.entries] == [
                (10, 0, 'one.flac'), (11, 1, 'one.flac'),
            ]
            assert sample.status.duration_seconds == 180.25
            assert sample.status.song_id == 10
            assert sample.status.song_uri == 'one.flac'
            assert sample.partition == 'default' and sample.playlist_version == 100
            assert (await adapter.status()).duration_seconds == 180.25
            assert len(await adapter.queue_entries()) == 2
            assert await adapter.has_library_uri('one.flac')
            assert (await adapter.outputs())[0].name == 'USB'
            assert server.commands[:3] == [
                (1, 'password secret'), (1, 'tagtypes clear'), (1, 'tagtypes'),
            ]
            assert sum(c == 'tagtypes clear' for _, c in server.commands) == 1
            assert not (await adapter._command('playlistinfo')).as_dict().get('Artist')
            old_epoch = sample.connection_epoch
            await adapter.close()
            new = await adapter.read_execution_sample()
            assert new.connection_epoch != old_epoch
            assert (2, 'tagtypes clear') in server.commands
            with pytest.raises(PlayerUnavailable):
                await adapter.queue_play(10, expected_connection_epoch=old_epoch)
            assert not any(c.startswith('playid') for _, c in server.commands)
        finally:
            await adapter.close()
            await server.close()
    asyncio.run(run())


@pytest.mark.parametrize('failure', ['ack', 'disconnect', 'ignored', 'verify-ack', 'timeout'])
def test_unsupported_or_unverified_filter_reconnects_with_full_metadata(failure):
    async def run():
        server = TagServer(failure)
        port = await server.start()
        adapter = MPDAdapter('127.0.0.1', port, omit_song_tags=True, command_timeout=0.1)
        try:
            sample = await adapter.read_execution_sample()
            assert len(sample.entries) == 2
            assert sample.status.duration_seconds == 180.25
            assert server.connections == 2
            assert (await adapter._command('playlistinfo')).as_dict()['Artist'] == ['artist', 'artist']
            assert not any(c.startswith('playid') for _, c in server.commands)
            assert sum(c == 'tagtypes clear' for _, c in server.commands) == 1
        finally:
            await adapter.close()
            await server.close()
    asyncio.run(run())


def test_cancelled_filter_setup_discards_transport_without_control():
    async def run():
        server = TagServer('cancel')
        port = await server.start()
        adapter = MPDAdapter('127.0.0.1', port, omit_song_tags=True)
        try:
            task = asyncio.create_task(adapter.read_execution_sample())
            await asyncio.wait_for(server.ready.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert adapter._connection_epoch is None
            assert adapter._writer is None
            assert not any(c.startswith('playid') for _, c in server.commands)
        finally:
            await adapter.close()
            await server.close()
    asyncio.run(run())


@pytest.mark.parametrize('entry_count', [8, 400])
def test_filter_reduces_payload_without_changing_complete_sample(entry_count):
    async def run():
        server = TagServer(entry_count=entry_count)
        port = await server.start()
        full = MPDAdapter('127.0.0.1', port)
        compact = MPDAdapter('127.0.0.1', port, omit_song_tags=True)
        try:
            old = await full.read_execution_sample()
            full_bytes = server.bytes
            new = await compact.read_execution_sample()
            compact_bytes = server.bytes - full_bytes
            assert len(new.entries) == entry_count
            assert new.model_dump(exclude={'connection_epoch'}) == old.model_dump(
                exclude={'connection_epoch'},
            )
            assert compact_bytes < full_bytes
            assert sum(c == 'playlistinfo' for _, c in server.commands) == 2
            assert sum(c == 'status' for _, c in server.commands) == 4
        finally:
            await full.close()
            await compact.close()
            await server.close()
    asyncio.run(run())


def test_filter_fallback_cannot_send_old_epoch_id_after_reconnect():
    async def run():
        server = TagServer()
        port = await server.start()
        adapter = MPDAdapter('127.0.0.1', port, omit_song_tags=True)
        try:
            old = await adapter.read_execution_sample()
            server.failure = 'ack'
            await adapter.close()
            with pytest.raises(PlayerUnavailable):
                await adapter.queue_play(10, expected_connection_epoch=old.connection_epoch)
            assert server.connections == 3
            assert not any(c.startswith('playid') for _, c in server.commands)
            assert (await adapter._command('playlistinfo')).as_dict()['Artist'] == ['artist', 'artist']
        finally:
            await adapter.close()
            await server.close()
    asyncio.run(run())
