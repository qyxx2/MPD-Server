"""S10 local TCP/SQLite/ASGI harness; no causal MPD evidence or live services."""
from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI

from server.app.api.realtime import router
from server.app.models.library import Song
from server.app.models.output import (
    OutputMode,
    OutputRequestState,
    OutputSnapshot,
    OutputState,
)
from server.app.models.queue import PlaybackContext
from server.app.player.capabilities import MPDCapabilities, VerifiedPlayerPort
from server.app.player.mpd_adapter import MPDAdapter
from server.app.repositories.database import initialize_database
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.idempotency_repository import IdempotencyRepository
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playback_state_repository import PlaybackStateRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.repositories.queue_repository import QueueRepository
from server.app.services.autoplay import AutoPlay
from server.app.services.history_service import HistoryService
from server.app.services.library_service import LibraryService
from server.app.services.playback_recovery_runner import PlaybackRecoveryRunner
from server.app.services.playback_service import PlaybackService
from server.app.services.queue_manager import QueueManager
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.app.services.state_service import StateService
from server.tests.integration.support.stateful_fake_mpd import StatefulFakeMPD

READS = {'status', 'currentsong', 'playlistinfo', 'outputs'}


class StockJoint:
    def __init__(self, path):
        self.path = str(path)
        self.fake = StatefulFakeMPD()
        self.events = []

    async def publish(self, event):
        self.events.append(event)

    async def start(self, *, duplicate=False, short=False):
        await initialize_database(self.path)
        await self.fake.start()
        self.adapter = MPDAdapter(self.fake.host, port=self.fake.port)
        # Injected LOCAL protocol capabilities, never a target runtime capability claim.
        capabilities = replace(MPDCapabilities.from_commands({
            'status', 'currentsong', 'playlistinfo', 'addid', 'deleteid', 'moveid',
            'playid', 'play', 'pause', 'stop', 'next', 'seekcur', 'outputs',
        }), version='0.23.5', verified_operations=frozenset({
            'queue_entries', 'queue_add', 'queue_delete', 'queue_move', 'queue_play',
        }))
        self.player = VerifiedPlayerPort(self.adapter, capabilities)
        self.library = LibraryRepository(self.path)
        self.queue = QueueRepository(self.path)
        self.playback_state = PlaybackStateRepository(self.path)
        self.playlists = PlaylistRepository(self.path)
        self.history = HistoryRepository(self.path)
        self.manager = QueueManager(self.queue, self.playback_state, self.playlists)
        self.autoplay = AutoPlay(self.queue, self.library, self.playback_state)
        for song_id in ('abcdi' if short else 'abcdefghi'):
            await self.library.upsert_song(Song(
                song_id=song_id, title=song_id, file_uri=f'{song_id}.flac',
            ))
        playlist = await self.playlists.create_playlist('preserved')
        await self.playlists.add_song(playlist.playlist_id, 'b')
        await self.playlists.set_favorite('c', True)
        self.terminals = IdempotencyRepository(self.path)
        await self.terminals.create(operation_scope='retained', idempotency_key='old',
                                   payload_hash='fixed', response_status=200,
                                   response_body='{"ok":true}')
        now = datetime.now(timezone.utc)
        self.output = OutputSnapshot(states=(OutputState(
            mode=OutputMode.NAS_DAC, status='ACTIVE', updated_at=now,
        ),), last_request=OutputRequestState(
            mode=OutputMode.NAS_DAC, enabled=True, status='SUCCEEDED', updated_at=now,
        ))
        self.app = FastAPI()
        self.app.include_router(router)
        self.rebuild_service()
        # Seed genuine permanent history before the stock unknown-history proof.
        await self.service.start_track('i')
        await self.service.play_context(PlaybackContext(
            context_id='stock-joint', source_type='SONGS',
            ordered_song_ids=tuple('abcd' if short else 'abcdefghi') + (('a',) if duplicate else ()),
        ))
        await self.service.observe()
        self.events.clear()

    def rebuild_service(self):
        self.coordinator = RealtimeCoordinator(self.path)
        self.history_service = HistoryService(self.queue, self.history)
        self.service = PlaybackService(
            queue_manager=self.manager, history_service=self.history_service,
            autoplay=self.autoplay, player=self.player, library_repository=self.library,
            coordinator=self.coordinator, event_publisher=self,
        )
        self.state = StateService(
            coordinator=self.coordinator, queue_manager=self.manager,
            history_service=self.history_service, library_service=LibraryService(self.library),
            playback_service=self.service, output_snapshot=lambda: self.output.model_copy(deep=True),
        )
        self.app.state.state_service = self.state
        self.app.state.realtime_coordinator = self.coordinator

    async def business(self):
        return (await self.queue.get_snapshot(), await self.manager.get_playback_state(),
                await self.history.list_history(), self.history_service.active_event,
                self.history_service.session_id)

    def authorities(self):
        with sqlite3.connect(self.path) as connection:
            tables = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ) if row[0] not in {'queue_items', 'queue_state', 'playback_state', 'history'}]
            persisted = {table: connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
                         for table in tables}
        return persisted, self.output.model_copy(deep=True), self.fake.volume

    def controls(self, start=0):
        return [r for r in self.fake.received[start:] if r.split()[0] not in READS]

    async def external(self, command):
        # A distinct TCP client gives facts, never synthetic natural evidence.
        reader, writer = await asyncio.open_connection(self.fake.host, self.fake.port)
        try:
            assert (await reader.readline()).startswith(b'OK MPD 0.23.5')
            writer.write((command + '\n').encode())
            await writer.drain()
            lines = []
            while True:
                line = (await reader.readline()).decode().strip()
                assert line and not line.startswith('ACK'), line
                if line == 'OK':
                    return lines
                lines.append(line)
        finally:
            writer.close()
            await writer.wait_closed()

    async def public_state(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                                    base_url='http://local') as client:
            response = await client.get('/api/state')
            assert response.status_code == 200, response.text
            return response.json()

    @asynccontextmanager
    async def socket(self):
        incoming, outgoing = asyncio.Queue(), asyncio.Queue()
        await incoming.put({'type': 'websocket.connect'})
        scope = {'type': 'websocket', 'asgi': {'version': '3.0'}, 'scheme': 'ws',
                 'path': '/api/realtime', 'raw_path': b'/api/realtime', 'query_string': b'',
                 'root_path': '', 'headers': [], 'client': ('local', 1), 'server': ('local', 80),
                 'subprotocols': [], 'state': {}}
        task = asyncio.create_task(self.app(scope, incoming.get, outgoing.put))

        async def frame():
            message = await asyncio.wait_for(outgoing.get(), 3)
            assert message['type'] == 'websocket.send', message
            return json.loads(message['text'])

        try:
            assert (await asyncio.wait_for(outgoing.get(), 3))['type'] == 'websocket.accept'
            yield frame
        finally:
            await incoming.put({'type': 'websocket.disconnect', 'code': 1000})
            await asyncio.wait_for(task, 3)

    async def assert_reads_preserved(self):
        before, authorities = await self.business(), self.authorities()
        cutoff = len(self.fake.received)
        await self.service.observe()
        snapshot = await self.state.get_full_snapshot()
        http = await self.public_state()
        async with self.socket() as frame:
            first = await frame()
        assert first['type'] == 'snapshot' and first['protocol_version'] == 1
        ws = first['state']
        assert {k: v for k, v in ws.items() if k != 'captured_at'} == {
            k: v for k, v in http.items() if k != 'captured_at'
        }
        assert ws['queue'] == snapshot.queue.model_dump(mode='json')
        assert ws['playback'] == snapshot.playback.model_dump(mode='json')
        assert ws['output'] == self.output.model_dump(mode='json')
        assert await self.business() == before
        assert self.authorities() == authorities
        assert self.controls(cutoff) == []
        return ws

    async def one_runner_tick(self):
        sleeping = asyncio.Event()

        async def sleep(delay):
            sleeping.set()
            await asyncio.Event().wait()

        runner = PlaybackRecoveryRunner(self.service, sleep=sleep)
        task = asyncio.create_task(runner.run())
        try:
            await asyncio.wait_for(sleeping.wait(), 3)
        finally:
            await runner.close()
            await task

    async def close(self):
        await self.adapter.close()
        await self.fake.close()


@asynccontextmanager
async def stock_joint(path, **kwargs):
    joint = StockJoint(path)
    try:
        await joint.start(**kwargs)
        yield joint
    finally:
        await joint.close()
