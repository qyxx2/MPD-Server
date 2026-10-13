"""Observed-only reconciliation must preserve committed facts and references."""
from __future__ import annotations

import asyncio

import pytest

from server.app.models.library import ScanBatch, SidecarSignature
from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.services.library_scanner import LibraryScanError, LibraryScanner
from server.app.services.library_sync_service import LibrarySyncService
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.tests.invariants.test_startup_library_reconciliation import (
    IndexedPlayer,
    music_fixture,
)


def test_observed_unchanged_uri_is_not_missing(tmp_path, media_fixture_dir):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / "observed.db")

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        coordinator = RealtimeCoordinator(db)
        scanner = LibraryScanner(repo, coordinator=coordinator)
        await scanner.scan_full(root)
        before, revision = await repo.list_songs(), coordinator.marker().library_revision
        batch = ScanBatch(
            reconciled_root_uri_prefix=str(root) + "/",
            observed_file_uris=tuple(song.file_uri for song in before),
        )
        result = await scanner._apply_batch(batch)
        assert await repo.list_songs() == before, result
        assert coordinator.marker().library_revision == revision

    asyncio.run(run())


@pytest.mark.parametrize("boundary", ["during_prepare", "before_scanner_commit"])
def test_mount_replacement_never_commits_mass_missing(tmp_path, media_fixture_dir, monkeypatch, boundary):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / "mount.db")

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        coordinator = RealtimeCoordinator(db)
        scanner = LibraryScanner(repo, coordinator=coordinator)
        await scanner.scan_full(root)
        before = await repo.list_songs()
        revision = coordinator.marker().library_revision
        playlists = PlaylistRepository(db)
        playlist = await playlists.create_playlist("Keep")
        for song in before:
            await playlists.add_song(playlist.playlist_id, song.song_id)
        player = IndexedPlayer(root)
        sync = LibrarySyncService(scanner, player, root)
        # Empty inventory under the original mount; then replace that mount at
        # the selected boundary. Every source belongs to this temporary fixture.
        for file in root.iterdir():
            file.unlink()
        replaced = False

        def replace_mount():
            nonlocal replaced
            if not replaced:
                root.rename(tmp_path / "old-mount")
                root.mkdir()
                replaced = True

        if boundary == "during_prepare":
            scan_files = scanner.prepare

            async def prepare(*args, **kwargs):
                batch = await scan_files(*args, **kwargs)
                replace_mount()
                return batch

            monkeypatch.setattr(scanner, "prepare", prepare)
        else:
            apply = scanner.commit

            async def commit(batch, **kwargs):
                # Full inventory/prepare is complete, but commit has not begun.
                # Today's public scan_full wrapper never checks root identity
                # across this boundary. C2 must retain this safety for wrappers.
                replace_mount()
                return await apply(batch, **kwargs)

            monkeypatch.setattr(scanner, "commit", commit)
        try:
            if boundary == "during_prepare":
                await sync.request_scan(None, "startup")
                await sync._scan(await sync._jobs.get())
            else:
                await scanner.scan_full(root)
        except (OSError, LibraryScanError):
            pass
        assert replaced, "mount fault injection was not reached"
        assert await repo.list_songs() == before
        assert coordinator.marker().library_revision == revision
        assert await playlists.list_song_ids(playlist.playlist_id) == [song.song_id for song in before]
        assert player.calls == []

    asyncio.run(run())


def signature(lrc_uri, size=None, mtime=None):
    return SidecarSignature(lrc_uri=lrc_uri, file_size=size, file_mtime_ns=mtime)


def delta_batch(*, songs=(), observed=(), sidecars=None, unreadable=()):
    return ScanBatch(
        songs=songs, unreadable_file_uris=unreadable,
        observed_file_uris=observed, sidecar_signatures=sidecars or {},
    )


def sidecar_rows(connection):
    # Absence of the auxiliary index means no signature persisted, not a SQL
    # setup exception. RED assertions below compare actual stored facts.
    if not connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'library_sidecar_signatures'").fetchone():
        return []
    return connection.execute('SELECT song_id, lrc_uri, file_size, file_mtime_ns FROM library_sidecar_signatures ORDER BY song_id').fetchall()


def test_v4_migration_preserves_library_and_references(tmp_path, media_fixture_dir):
    import sqlite3
    from datetime import datetime, timezone

    from server.app.models.history import HistoryEvent
    from server.app.repositories.history_repository import HistoryRepository

    db = str(tmp_path / 'v4.db')
    root = music_fixture(tmp_path, media_fixture_dir)

    async def seed():
        await initialize_database(db)
        repo = LibraryRepository(db)
        await LibraryScanner(repo).scan_full(root)
        song = (await repo.list_songs())[0]
        playlists = PlaylistRepository(db)
        playlist = await playlists.create_playlist('保留引用')
        await playlists.add_song(playlist.playlist_id, song.song_id)
        await playlists.set_favorite(song.song_id, True)
        await HistoryRepository(db).record_history(HistoryEvent(song_id=song.song_id, started_at=datetime.now(timezone.utc), session_id='migration'))
        return song

    song = asyncio.run(seed())
    with sqlite3.connect(db) as c:
        # Build an actual v4 fixture in this test-owned DB, even after C1 makes
        # initialize_database create v5. Only the new empty index is removed.
        c.execute('DROP TABLE IF EXISTS library_sidecar_signatures')
        c.execute('PRAGMA user_version = 4')
        c.execute("INSERT INTO queue_items VALUES ('queue', ?, 0, 'USER', 'context')", (song.song_id,))
        c.execute("INSERT INTO playback_state VALUES (1, ?, 'PAUSED', 'context', 2, 0, 'now')", (song.song_id,))
        c.execute("INSERT INTO idempotency_records VALUES ('scope', 'key', 'hash', 200, '{}', 'now')")
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        before = {t: c.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tables}
    asyncio.run(initialize_database(db))
    with sqlite3.connect(db) as c:
        assert {t: c.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tables} == before
        assert c.execute('PRAGMA foreign_key_check').fetchall() == []
        assert c.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert c.execute("SELECT name FROM sqlite_master WHERE name = 'library_sidecar_signatures'").fetchone() == ('library_sidecar_signatures',)
        assert c.execute('PRAGMA user_version').fetchone() == (5,)
        assert sidecar_rows(c) == []  # Old signatures remain unknown.
    asyncio.run(initialize_database(db))  # Reopening is idempotent.
    with sqlite3.connect(db) as c:
        assert {t: c.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tables} == before


def test_sidecar_absence_is_distinct_from_unknown(tmp_path):
    import sqlite3

    from server.app.models.library import Song
    db = str(tmp_path / 'absence.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        for song_id in ('known', 'unknown', 'present'):
            await repo.upsert_song(Song(song_id=song_id, title=song_id, file_uri=f'music/{song_id}.flac'))
        before = await repo.list_songs()
        scanner = LibraryScanner(repo, coordinator=RealtimeCoordinator(db))
        await scanner._apply_batch(delta_batch(
            observed=('music/known.flac', 'music/present.flac'),
            sidecars={'music/known.flac': signature('music/known.lrc'), 'music/present.flac': signature('music/present.lrc', 12, 34)},
        ))
        with sqlite3.connect(db) as c:
            assert sidecar_rows(c) == [('known', 'music/known.lrc', None, None), ('present', 'music/present.lrc', 12, 34)]
        baseline = await repo.read_scan_baseline()
        assert tuple(s.model_dump() for s in baseline.songs) == tuple(s.model_dump() for s in before)
        assert tuple((sid, s.lrc_uri, s.file_size, s.file_mtime_ns) for sid, s in baseline.sidecars) == (('known', 'music/known.lrc', None, None), ('present', 'music/present.lrc', 12, 34))
        assert 'unknown' not in dict(baseline.sidecars)
        assert scanner.coordinator.marker().library_revision == 0
        await scanner._apply_batch(delta_batch(observed=('music/present.flac',), sidecars={'music/present.flac': signature('music/present.lrc')}))
        assert dict((await repo.read_scan_baseline()).sidecars)['present'].file_size is None
        assert await repo.list_songs() == before
        assert scanner.coordinator.marker().library_revision == 0

    asyncio.run(run())


@pytest.mark.parametrize('outcome', ['commit', 'rollback', 'cancel'])
def test_signature_delta_rolls_back_with_song_batch(tmp_path, outcome):
    import sqlite3

    from server.app.models.library import Song
    from server.app.repositories.database import run_transaction
    db = str(tmp_path / 'atomic.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        saved = await repo.upsert_song(Song(song_id='kept', title='Before', file_uri='music/a.flac'))
        scanner = LibraryScanner(repo, coordinator=RealtimeCoordinator(db))
        await scanner._apply_batch(delta_batch(observed=(saved.file_uri,), sidecars={saved.file_uri: signature('music/a.lrc', 1, 2)}))
        with sqlite3.connect(db) as c:
            assert sidecar_rows(c) == [('kept', 'music/a.lrc', 1, 2)]
        before = await repo.read_scan_baseline()
        marker = scanner.coordinator.marker()

        async def transaction(c):
            await scanner._apply_batch(delta_batch(songs=(saved.model_copy(update={'title': 'After'}), Song(song_id='new', title='New', file_uri='music/new.flac')), sidecars={saved.file_uri: signature('music/a.lrc', 3, 4), 'music/new.flac': signature('music/new.lrc')}))
            assert sidecar_rows(c) == [('kept', 'music/a.lrc', 3, 4), ('new', 'music/new.lrc', None, None)]
            assert (await repo.get_song('kept')).title == 'After'
            assert (await repo.read_scan_baseline()).fingerprint != before.fingerprint
            # Independent connection sees neither Song nor signature before the
            # outer owner commits; revision is equally unchanged.
            with sqlite3.connect(db) as reader:
                assert sidecar_rows(reader) == [('kept', 'music/a.lrc', 1, 2)]
                assert reader.execute('SELECT title FROM songs ORDER BY song_id').fetchall() == [('Before',)]
            assert scanner.coordinator.marker() == marker
            if outcome == 'rollback':
                raise RuntimeError('rollback batch')
            if outcome == 'cancel':
                raise asyncio.CancelledError

        if outcome == 'commit':
            await run_transaction(db, transaction)
            assert (await repo.get_song('kept')).title == 'After'
            assert scanner.coordinator.marker().library_revision == marker.library_revision + 1
            with sqlite3.connect(db) as c:
                assert sidecar_rows(c) == [('kept', 'music/a.lrc', 3, 4), ('new', 'music/new.lrc', None, None)]
        else:
            with pytest.raises(RuntimeError if outcome == 'rollback' else asyncio.CancelledError):
                await run_transaction(db, transaction)
            assert await repo.read_scan_baseline() == before
            assert scanner.coordinator.marker() == marker
            with sqlite3.connect(db) as c:
                assert sidecar_rows(c) == [('kept', 'music/a.lrc', 1, 2)]

    asyncio.run(run())


@pytest.mark.parametrize('failure', ['read_error', 'unreadable', 'new_unreadable'])
def test_failed_sidecar_delta_is_never_recorded_as_success(tmp_path, failure):
    import sqlite3

    from server.app.models.library import Song
    db = str(tmp_path / 'failure.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        song = await repo.upsert_song(Song(song_id='known', title='Keep', file_uri='music/a.flac', lyrics='embedded fallback', lyrics_source='embedded', lyrics_status='available'))
        await repo.apply_scan_batch(delta_batch(observed=(song.file_uri,), sidecars={song.file_uri: signature('music/a.lrc', 1, 2)}))
        with sqlite3.connect(db) as c:
            assert sidecar_rows(c) == [('known', 'music/a.lrc', 1, 2)]
        if failure == 'read_error':
            batch = delta_batch(songs=(song.model_copy(update={'lyrics_status': 'read_error'}),), sidecars={song.file_uri: signature('music/a.lrc', 9, 10)})
        else:
            uri = 'music/new.flac' if failure == 'new_unreadable' else song.file_uri
            batch = delta_batch(observed=(uri,), unreadable=(uri,), sidecars={uri: signature('music/error.lrc', 9, 10)})
        await repo.apply_scan_batch(batch)
        with sqlite3.connect(db) as c:
            assert sidecar_rows(c) == [('known', 'music/a.lrc', 1, 2)]
        kept = await repo.get_song('known')
        assert kept.lyrics == 'embedded fallback'
        assert kept.song_id == song.song_id
        assert await repo.find_song_by_file_uri('music/new.flac') is None

    asyncio.run(run())


def test_scan_baseline_tracks_content_and_signatures_but_not_audit_time(tmp_path):
    import sqlite3
    from dataclasses import FrozenInstanceError

    from pydantic import ValidationError

    from server.app.models.library import ArtworkRef, Song
    from server.app.repositories.database import run_transaction
    db = str(tmp_path / 'baseline.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        song = await repo.upsert_song(Song(song_id='a', title='Before', file_uri='music/曲.flac', album='Album', artists=('Artist',), genres=('Genre',), tag_names=('Tag',), artwork=ArtworkRef(artwork_id='art', source='EMBEDDED', picture_index=0)))
        await repo.apply_scan_batch(delta_batch(observed=(song.file_uri,), sidecars={song.file_uri: signature('music/曲.lrc')}))
        with sqlite3.connect(db) as c:
            assert sidecar_rows(c) == [('a', 'music/曲.lrc', None, None)]
        baseline = await repo.read_scan_baseline()
        assert tuple(s.model_dump() for s in baseline.songs) == (song.model_dump(),)
        assert baseline.songs[0].artwork.model_dump() == song.artwork.model_dump()
        with pytest.raises(FrozenInstanceError):
            baseline.fingerprint = 'overwrite'
        with pytest.raises(ValidationError):
            baseline.songs[0].title = 'overwrite'
        with pytest.raises(ValidationError):
            baseline.songs[0].artwork.picture_index = 3
        with pytest.raises(ValidationError):
            baseline.sidecars[0][1].file_size = 2
        await run_transaction(db, lambda c: c.execute("UPDATE songs SET last_scanned_at = '2026-10-12T00:00:00+00:00', last_seen_at = '2026-10-12T01:00:00+00:00'"))
        assert (await repo.read_scan_baseline()).fingerprint == baseline.fingerprint
        await repo.apply_scan_batch(delta_batch(observed=(song.file_uri,), sidecars={song.file_uri: signature('music/曲.lrc', 0, 0)}))
        signatures = await repo.read_scan_baseline()
        assert signatures.fingerprint != baseline.fingerprint
        assert baseline.sidecars[0][1].file_size is None
        await repo.upsert_song(song.model_copy(update={'title': 'After'}))
        assert (await repo.read_scan_baseline()).fingerprint != signatures.fingerprint
        assert baseline.songs[0].title == 'Before'

    asyncio.run(run())


@pytest.mark.parametrize(('size', 'mtime'), [(None, 1), (1, None), (-1, 0), (0, -1)])
def test_sidecar_signature_rejects_partial_or_negative_stats(size, mtime):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        signature('music/a.lrc', size, mtime)


def test_sidecar_table_enforces_signature_pairs_and_song_reference(tmp_path):
    import sqlite3

    from server.app.models.library import Song
    db = str(tmp_path / 'constraints.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        await repo.upsert_song(Song(song_id='a', title='A', file_uri='music/a.flac'))
        await repo.apply_scan_batch(delta_batch(observed=('music/a.flac',), sidecars={'music/a.flac': signature('music/a.lrc')}))
    asyncio.run(run())
    with sqlite3.connect(db) as c:
        c.execute('PRAGMA foreign_keys = ON')
        assert sidecar_rows(c) == [('a', 'music/a.lrc', None, None)]
        for size, mtime in ((None, 1), (1, None), (-1, 0), (0, -1), (1.5, 2), ('bad', 2)):
            with pytest.raises(sqlite3.IntegrityError):
                c.execute('UPDATE library_sidecar_signatures SET file_size = ?, file_mtime_ns = ?', (size, mtime))
            assert sidecar_rows(c) == [('a', 'music/a.lrc', None, None)]
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO library_sidecar_signatures VALUES ('orphan', 'music/a.lrc', 1, 2)")
        c.execute("DELETE FROM songs WHERE song_id = 'a'")
        assert sidecar_rows(c) == []


def test_sidecar_delta_follows_song_identity_on_move(tmp_path):
    import sqlite3

    from server.app.models.library import Song
    db = str(tmp_path / 'move-signature.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        song = await repo.upsert_song(Song(song_id='kept', title='Move', file_uri='music/旧.flac'))
        playlists = PlaylistRepository(db)
        playlist = await playlists.create_playlist('Keep')
        await playlists.add_song(playlist.playlist_id, song.song_id)
        await repo.apply_scan_batch(delta_batch(observed=(song.file_uri,), sidecars={song.file_uri: signature('music/旧.lrc')}))
        with sqlite3.connect(db) as c:
            assert sidecar_rows(c) == [('kept', 'music/旧.lrc', None, None)]
        result = await repo.apply_scan_batch(delta_batch(songs=(song.model_copy(update={'file_uri': 'music/新.flac'}),), sidecars={'music/新.flac': signature('music/新.lrc', 5, 6)}))
        assert result.moved_song_ids == ('kept',)
        assert result.added_song_ids == ()
        assert await playlists.list_song_ids(playlist.playlist_id) == ['kept']
        with sqlite3.connect(db) as c:
            assert sidecar_rows(c) == [('kept', 'music/新.lrc', 5, 6)]
        assert dict((await repo.read_scan_baseline()).sidecars)['kept'].lrc_uri == 'music/新.lrc'

    asyncio.run(run())
