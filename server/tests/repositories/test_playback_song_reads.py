"""Minimal playback projection: chunking, identity, absence and fresh reads."""
from __future__ import annotations

import asyncio
import sqlite3

import pytest

from server.app.models.library import Song
from server.app.repositories.database import initialize_database, run_transaction
from server.app.repositories.library_repository import LibraryRepository


@pytest.mark.parametrize('size', [0, 3, 1205])
def test_batch_projection_deduplicates_and_chunks_without_song_relations(tmp_path, monkeypatch, size):
    async def scenario():
        path = str(tmp_path / 'reads.db')
        await initialize_database(path)
        repo = LibraryRepository(path)
        # Seed directly through the Repository's existing transaction implementation.
        async def seed(connection):
            for index in range(size):
                repo._upsert_song(connection, Song(
                    song_id=f'id-{index}', title='Title', file_uri=f'{index}.flac',
                    availability_status=('AVAILABLE', 'MISSING', 'UNREADABLE')[index % 3],
                    album='Album', artists=('Artist',), tag_names=('Tag',),
                ), f'id-{index}', '2026-10-14T00:00:00+00:00')
        await run_transaction(path, seed)
        statements = []
        def no_full_song(*args):
            pytest.fail('Playback projection built full Song relations')
        monkeypatch.setattr(repo, '_song_from_row', no_full_song)
        async def read(connection):
            # Force a smaller SQLite variable limit to prove actual chunk safety.
            connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 100)
            connection.set_trace_callback(statements.append)
            ids = [f'id-{i}' for i in reversed(range(size))]
            return await repo.get_playback_songs(ids + ids + (['absent'] if size else []))
        rows = await run_transaction(path, read)
        assert set(rows) == {f'id-{i}' for i in range(size)}
        for index in range(size):
            row = rows[f'id-{index}']
            assert row.song_id == f'id-{index}'
            assert row.file_uri == f'{index}.flac'
            assert row.availability_status == ('AVAILABLE', 'MISSING', 'UNREADABLE')[index % 3]
            assert not hasattr(row, 'artwork') and not hasattr(row, 'title')
        selects = [s for s in statements if s.lstrip().upper().startswith('SELECT')]
        assert len(selects) == (0 if size == 0 else (size + 1 + 99) // 100)
        assert all(s.lstrip().startswith('SELECT song_id, file_uri, availability_status FROM songs') for s in selects)
    asyncio.run(scenario())


def test_batch_rereads_writes_within_root_transaction_and_after_rollback(tmp_path):
    async def scenario():
        path = str(tmp_path / 'fresh.db')
        await initialize_database(path)
        repo = LibraryRepository(path)
        await repo.upsert_song(Song(song_id='a', title='A', file_uri='a.flac'))
        async def change(connection):
            assert (await repo.get_playback_songs(['a']))['a'].file_uri == 'a.flac'
            await repo.upsert_song(Song(song_id='a', title='A', file_uri='new.flac', availability_status='MISSING'))
            fresh = (await repo.get_playback_songs(['a']))['a']
            assert (fresh.file_uri, fresh.availability_status) == ('new.flac', 'MISSING')
            raise RuntimeError('rollback')
        with pytest.raises(RuntimeError, match='rollback'):
            await run_transaction(path, change)
        fresh = (await repo.get_playback_songs(['a']))['a']
        assert (fresh.file_uri, fresh.availability_status) == ('a.flac', 'AVAILABLE')
        async def remove(connection):
            connection.execute('DELETE FROM songs WHERE song_id = ?', ('a',))
            assert await repo.get_playback_songs(['a']) == {}
        await run_transaction(path, remove)
    asyncio.run(scenario())
