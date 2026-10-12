"""Thread preparation, safety, path reuse and atomic commit contracts."""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

from server.app.repositories.database import initialize_database, run_transaction
from server.app.repositories.library_repository import LibraryRepository
from server.app.services import library_scan_prepare as media
from server.app.services.library_scanner import (
    LibraryScanConflict,
    LibraryScanError,
    LibraryScanner,
)
from server.app.services.library_sync_service import LibrarySyncService
from server.app.services.realtime_coordinator import RealtimeCoordinator
from server.tests.invariants.test_startup_library_reconciliation import (
    IndexedPlayer,
    music_fixture,
)


def test_prepare_releases_database_lock(tmp_path, media_fixture_dir, monkeypatch):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / "lock.db")

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        entered, release = threading.Event(), threading.Event()
        prepare = media.prepare_scan

        def barrier(*args, **kwargs):
            entered.set()
            assert release.wait(3)
            return prepare(*args, **kwargs)

        monkeypatch.setattr(media, 'prepare_scan', barrier)
        sync = LibrarySyncService(LibraryScanner(repo), IndexedPlayer(root), root)
        await sync.request_scan(None, "startup")
        owner = asyncio.create_task(sync.run())
        # Created from the test task, outside the owner's transaction ContextVar.
        async def independent_select():
            return await run_transaction(db, lambda connection: connection.execute("SELECT 1").fetchone())

        readers = []
        try:
            assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 1), 1), "prepare barrier was not reached"
            readers = [asyncio.create_task(independent_select()), asyncio.create_task(repo.list_songs())]
            done, _ = await asyncio.wait(readers, timeout=1)
            assert len(done) == 2, "prepare holds shared DB lock: SELECT 1 / list_songs blocked"
            assert readers[0].result() == (1,)
            assert readers[1].result() == []
        finally:
            release.set()
            await sync.close()
            await asyncio.wait_for(owner, 1)
            await asyncio.gather(*readers, return_exceptions=True)

    asyncio.run(run())


@pytest.mark.parametrize("operation", ["parse_media_file", "_hash_file"], ids=["parse", "hash"])
def test_slow_media_io_runs_without_transaction(tmp_path, media_fixture_dir, monkeypatch, operation):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / "thread.db")
    entered, release = threading.Event(), threading.Event()
    original = getattr(media, operation)
    io_threads = []

    def slow(path):
        if not entered.is_set():
            io_threads.append(threading.get_ident())
            entered.set()
            assert release.wait(3), "test watchdog failed to release media I/O"
        return original(path)

    monkeypatch.setattr(media, operation, slow)

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        sync = LibrarySyncService(LibraryScanner(repo), IndexedPlayer(root), root)
        await sync.request_scan(None, "startup")
        loop_thread = threading.get_ident()
        # A watchdog outside the event loop bounds the test even on synchronous I/O.
        observed = []

        def watchdog():
            if entered.wait(3):
                time.sleep(1.2)
            release.set()

        guard = threading.Thread(target=watchdog)
        guard.start()
        owner = asyncio.create_task(sync.run())

        async def independent():
            while not entered.is_set():
                await asyncio.sleep(0)
            started = time.monotonic()
            value = await run_transaction(db, lambda c: c.execute("SELECT 1").fetchone())
            observed.append((value, time.monotonic() - started, release.is_set()))

        reader = asyncio.create_task(independent())
        try:
            # If the loop blocks, this await resumes only after the watchdog.
            started = time.monotonic()
            while not entered.is_set():
                await asyncio.sleep(0)
            await asyncio.wait_for(reader, 1)
            assert time.monotonic() - started < 1, "real media I/O blocked event-loop progress"
            assert observed == [((1,), observed[0][1], False)], observed
            assert observed[0][1] < 1
            assert io_threads[0] != loop_thread
        finally:
            release.set()
            await sync.close()
            await asyncio.wait_for(owner, 1)
            await asyncio.gather(reader, return_exceptions=True)
            guard.join(4)

    asyncio.run(run())


def test_old_missing_signatures_are_backfilled_once(tmp_path, media_fixture_dir, monkeypatch):
    import sqlite3

    from server.tests.invariants.test_startup_library_reconciliation import spy_media

    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'backfill.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        await scanner.scan_full(root)
        with sqlite3.connect(db) as c:
            c.execute('DELETE FROM library_sidecar_signatures')
        parsed, hashed = spy_media(monkeypatch)
        await scanner.scan_full(root)
        baseline = await repo.read_scan_baseline()
        assert len(baseline.sidecars) == 2, 'successful legacy signatures were not persisted'
        assert dict(parsed) == {str(root / 'sidecar.mp3'): 1}
        assert sum(hashed.values()) == 0, 'sidecar backfill must reuse audio hash'
        await scanner.scan_full(root)
        assert dict(parsed) == {str(root / 'sidecar.mp3'): 1}
        assert sum(hashed.values()) == 0

    asyncio.run(run())


def test_deep_reconciliation_detects_same_stat_content_change(tmp_path, media_fixture_dir, monkeypatch):
    import os

    from mutagen.flac import FLAC

    from server.tests.invariants.test_startup_library_reconciliation import spy_media

    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'deep.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        await scanner.scan_full(root)
        target = root / 'a.flac'
        stat = target.stat()
        tags = FLAC(target)
        tags['title'] = ['Same Size']
        tags.save()
        assert target.stat().st_size == stat.st_size
        os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        parsed, hashed = spy_media(monkeypatch)
        await scanner.scan_full(root)
        assert sum(parsed.values()) == sum(hashed.values()) == 0
        assert (await repo.find_song_by_file_uri(str(target))).title == 'Test Song'
        await scanner.commit(await scanner.prepare(root, deep=True))
        assert (await repo.find_song_by_file_uri(str(target))).title == 'Same Size'
        assert sum(parsed.values()) == sum(hashed.values()) == 2

    asyncio.run(run())


def test_media_changed_during_prepare_is_retried(tmp_path, media_fixture_dir, monkeypatch):
    from mutagen.flac import FLAC

    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'changed.db')
    original = media.parse_media_file
    calls = []

    def changing(path):
        result = original(path)
        calls.append(path.name)
        if path.name == 'a.flac' and calls.count('a.flac') == 1:
            tags = FLAC(path)
            tags['title'] = ['Changed During Prepare']
            tags.save()
        return result

    monkeypatch.setattr(media, 'parse_media_file', changing)

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        await scanner.scan_full(root)
        assert await repo.find_song_by_file_uri(str(root / 'a.flac')) is None
        assert (await repo.find_song_by_file_uri(str(root / 'sidecar.mp3'))).title
        await scanner.scan_full(root)
        assert (await repo.find_song_by_file_uri(str(root / 'a.flac'))).title == 'Changed During Prepare'
        assert calls.count('a.flac') == 2
        assert calls.count('sidecar.mp3') == 1

    asyncio.run(run())


def test_stale_baseline_cannot_overwrite_new_commit(tmp_path, media_fixture_dir):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'conflict.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        await scanner.scan_full(root)
        prepared = await scanner.prepare(root, deep=True)
        song = (await repo.list_songs())[0]
        await repo.upsert_song(song.model_copy(update={'title': 'Concurrent Writer'}))
        before = await repo.read_scan_baseline()
        with pytest.raises(LibraryScanConflict):
            await scanner.commit(prepared)
        assert (await repo.read_scan_baseline()).fingerprint == before.fingerprint

    asyncio.run(run())


def test_prepare_cancellation_never_commits(tmp_path, media_fixture_dir, monkeypatch):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'cancel.db')
    entered, release = threading.Event(), threading.Event()
    original = media.parse_media_file
    threads = []

    def slow(path):
        threads.append(threading.get_ident())
        entered.set()
        assert release.wait(3)
        return original(path)

    monkeypatch.setattr(media, 'parse_media_file', slow)

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        coordinator = RealtimeCoordinator(db)
        events = []

        class Publisher:
            async def publish(self, event):
                events.append(event)

        scanner = LibraryScanner(repo, Publisher(), coordinator=coordinator)
        loop_thread = threading.get_ident()
        guard = threading.Timer(1.2, release.set)
        guard.start()
        owner = asyncio.create_task(scanner.scan_full(root))
        try:
            while not entered.is_set():
                await asyncio.sleep(0)
            owner.cancel()
            with pytest.raises(asyncio.CancelledError):
                await owner
            assert threads == [threads[0]] and threads[0] != loop_thread
            assert await repo.list_songs() == []
            assert (await repo.read_scan_baseline()).sidecars == ()
            assert coordinator.marker().library_revision == 0
            assert events == []
        finally:
            release.set()
            await asyncio.gather(owner, return_exceptions=True)
            guard.join(3)

    asyncio.run(run())


def test_commit_data_revision_and_sync_are_atomic(tmp_path, media_fixture_dir, monkeypatch):
    import sqlite3

    from server.app.repositories.database import transaction_identity

    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'atomic.db')
    original = media.parse_media_file
    io_in_transaction = []

    def parsing(path):
        try:
            transaction_identity(db)
        except RuntimeError:
            io_in_transaction.append(False)
        else:
            io_in_transaction.append(True)
        return original(path)

    monkeypatch.setattr(media, 'parse_media_file', parsing)

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        coordinator = RealtimeCoordinator(db)
        player = IndexedPlayer(root)
        sync = LibrarySyncService(LibraryScanner(repo, coordinator=coordinator), player, root)
        await sync.request_scan(None, 'startup')
        job = await sync._jobs.get()
        apply = repo.apply_scan_batch

        async def failing(batch):
            await apply(batch)
            raise RuntimeError('rollback after SQL')

        monkeypatch.setattr(repo, 'apply_scan_batch', failing)
        before = sync.get_state()
        with pytest.raises(RuntimeError, match='rollback after SQL'):
            await sync._scan(job)
        assert await repo.list_songs() == []
        assert (await repo.read_scan_baseline()).sidecars == ()
        assert coordinator.marker().library_revision == 0
        assert sync.get_state() == before
        assert player.calls == []
        monkeypatch.setattr(repo, 'apply_scan_batch', apply)
        await sync._scan(job)
        with sqlite3.connect(db) as c:
            assert c.execute('SELECT count(*) FROM songs').fetchone() == (2,)
            assert c.execute('SELECT count(*) FROM library_sidecar_signatures').fetchone() == (2,)
        assert coordinator.marker().library_revision == 1
        assert sync.get_state().status == 'SYNCING'
        assert sync.get_state().pending_count == 2
        assert io_in_transaction and not any(io_in_transaction), 'media preparation ran in SQL transaction'

    asyncio.run(run())


def test_commit_has_no_music_io_and_workers_have_no_repository_access(tmp_path, media_fixture_dir, monkeypatch):
    from pathlib import Path

    from server.app.repositories.database import transaction_identity

    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'boundary.db')
    threads = []
    reads = LibraryRepository.read_scan_baseline
    applies = LibraryRepository.apply_scan_batch

    async def read(self):
        threads.append(threading.get_ident())
        return await reads(self)

    async def apply(self, batch):
        threads.append(threading.get_ident())
        return await applies(self, batch)

    monkeypatch.setattr(LibraryRepository, 'read_scan_baseline', read)
    monkeypatch.setattr(LibraryRepository, 'apply_scan_batch', apply)

    async def run():
        await initialize_database(db)
        scanner = LibraryScanner(LibraryRepository(db))
        loop_thread = threading.get_ident()
        prepared = await scanner.prepare(root)
        assert prepared.checked and prepared.inventory.complete
        assert {Path(e.file_uri).suffix for e in prepared.inventory.entries} == {'.flac', '.mp3', '.lrc'}

        def guarded(original):
            def call(path, *args, **kwargs):
                if path.is_relative_to(root):
                    try:
                        transaction_identity(db)
                    except RuntimeError:
                        pass
                    else:
                        pytest.fail('music filesystem I/O inside commit transaction')
                return original(path, *args, **kwargs)
            return call

        for name in ('stat', 'iterdir', 'open', 'resolve'):
            monkeypatch.setattr(Path, name, guarded(getattr(Path, name)))

        async def outer(_):
            with pytest.raises(LibraryScanError, match='outside an outer transaction'):
                await scanner.scan_full(root)
            result = await scanner.commit(prepared)
            assert len(result.added_song_ids) == 2

        await run_transaction(db, outer)
        assert threads and set(threads) == {loop_thread}

    asyncio.run(run())


def test_file_changed_before_commit_retains_other_prepared_results(tmp_path, media_fixture_dir, monkeypatch):
    from mutagen.flac import FLAC

    from server.tests.invariants.test_startup_library_reconciliation import spy_media

    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'precheck.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        parsed, hashed = spy_media(monkeypatch)
        prepared = await scanner.prepare(root)
        tags = FLAC(root / 'a.flac')
        tags['title'] = ['Changed Before Commit']
        tags.save()
        result = await scanner.commit(prepared)
        assert len(result.added_song_ids) == 1
        assert await repo.find_song_by_file_uri(str(root / 'a.flac')) is None
        assert (await repo.find_song_by_file_uri(str(root / 'sidecar.mp3'))).title
        await scanner.scan_full(root)
        assert parsed[str(root / 'sidecar.mp3')] == hashed[str(root / 'sidecar.mp3')] == 1
        assert parsed[str(root / 'a.flac')] == hashed[str(root / 'a.flac')] == 2

    asyncio.run(run())


def test_conflict_reprepare_reuses_unrelated_successful_media(tmp_path, media_fixture_dir, monkeypatch):
    from mutagen.flac import FLAC

    from server.tests.invariants.test_startup_library_reconciliation import spy_media

    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'reuse-conflict.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        await scanner.scan_full(root)
        tags = FLAC(root / 'a.flac')
        tags['title'] = ['Changed Audio']
        tags.save()
        (root / 'sidecar.lrc').write_text('[00:01.00] Changed Lyrics\n')
        parsed, hashed = spy_media(monkeypatch)
        commit = scanner.commit
        raced = False

        async def racing(prepared, **kwargs):
            nonlocal raced
            if not raced:
                raced = True
                song = await repo.find_song_by_file_uri(str(root / 'a.flac'))
                await repo.upsert_song(song.model_copy(update={'title': 'Concurrent Writer'}))
            return await commit(prepared, **kwargs)

        monkeypatch.setattr(scanner, 'commit', racing)
        await scanner.scan_full(root)
        assert raced
        assert (await repo.find_song_by_file_uri(str(root / 'a.flac'))).title == 'Changed Audio'
        assert parsed[str(root / 'a.flac')] == hashed[str(root / 'a.flac')] == 2
        assert parsed[str(root / 'sidecar.mp3')] == 1
        assert hashed[str(root / 'sidecar.mp3')] == 0
        assert (await repo.find_song_by_file_uri(str(root / 'sidecar.mp3'))).lyrics == '[00:01.00] Changed Lyrics\n'

    asyncio.run(run())


def test_full_prepare_artwork_fallback_revisits_only_related_observed_song(tmp_path, media_fixture_dir, monkeypatch):
    from server.tests.invariants.test_startup_library_reconciliation import spy_media
    from server.tests.services.test_library_scanner import (
        _prepare_artwork_track,
        _set_flac_pictures,
    )

    root = tmp_path / 'artwork'
    root.mkdir()
    fallback, source, unrelated = root / 'a.flac', root / 'z.flac', root / 'other.mp3'
    from shutil import copy2

    copy2(media_fixture_dir / 'sidecar.mp3', unrelated)
    for path, title, number, payload in [(source, 'Source', 1, b'source'), (fallback, 'Fallback', 2, b'fallback')]:
        _prepare_artwork_track(media_fixture_dir / 'metadata.flac', path, title=title, track_number=number, image_payloads=(payload,))
    db = str(tmp_path / 'fallback.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        await scanner.scan_paths([source])
        await scanner.scan_full(root)
        before = await repo.find_song_by_file_uri(str(source))
        fallback_song = await repo.find_song_by_file_uri(str(fallback))
        _set_flac_pictures(source)
        parsed, hashed = spy_media(monkeypatch)
        await scanner.scan_full(root)
        after = await repo.read_scan_baseline()
        assert dict(after.artwork_sources)[before.album_id] == fallback_song.song_id
        assert parsed[str(source)] == parsed[str(fallback)] == 1
        assert hashed[str(source)] == 1 and hashed[str(fallback)] == 0
        assert parsed[str(unrelated)] == hashed[str(unrelated)] == 0

    asyncio.run(run())


def test_single_file_stat_failure_keeps_other_prepared_media(tmp_path, media_fixture_dir, monkeypatch):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'stat-failure.db')
    signature = media._signature
    failures = []

    def denied(path):
        if path == root / 'a.flac':
            failures.append(path)
            raise PermissionError('fixture audio stat denied')
        return signature(path)

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        with monkeypatch.context() as patch:
            patch.setattr(media, '_signature', denied)
            prepared = await scanner.prepare(root)
            assert prepared.failed_paths == (root / 'a.flac',)
            await scanner.commit(prepared)
        assert failures, 'fault injection did not reach inventory'
        assert await repo.find_song_by_file_uri(str(root / 'a.flac')) is None
        assert (await repo.find_song_by_file_uri(str(root / 'sidecar.mp3'))).title
        await scanner.scan_full(root)
        assert (await repo.find_song_by_file_uri(str(root / 'a.flac'))).availability_status == 'AVAILABLE'

    asyncio.run(run())


@pytest.mark.parametrize('known', [False, True], ids=['new', 'known'])
def test_inventory_entry_stat_failure_is_isolated(
    tmp_path, media_fixture_dir, monkeypatch, known,
):
    from pathlib import Path

    from server.app.repositories.playlist_repository import PlaylistRepository
    from server.tests.invariants.test_startup_library_reconciliation import spy_media

    root = music_fixture(tmp_path, media_fixture_dir)
    failed = root / 'a.flac'
    good = root / 'sidecar.mp3'
    original = Path.stat
    injected = []

    def denied(path, *args, **kwargs):
        if path == failed:
            injected.append(path)
            raise PermissionError('fixture entry stat unavailable')
        return original(path, *args, **kwargs)

    async def run():
        db = str(tmp_path / 'entry-stat.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        old = None
        playlists = PlaylistRepository(db)
        playlist = await playlists.create_playlist('Kept')
        if known:
            await scanner.scan_full(root)
            old = await repo.find_song_by_file_uri(str(failed))
            await playlists.add_song(playlist.playlist_id, old.song_id)
            await playlists.set_favorite(old.song_id, True)
            # A real independent change must commit despite the failed entry.
            good.with_suffix('.lrc').write_text('[00:01.00] Changed during failure\n')
        parsed, hashed = spy_media(monkeypatch)
        with monkeypatch.context() as patch:
            patch.setattr(Path, 'stat', denied)
            prepared = await scanner.prepare(root)
            assert injected, 'fault did not reach inventory stat'
            assert prepared.failed_paths == (failed,)
            assert prepared.batch.unreadable_file_uris == (str(failed),)
            assert str(failed) not in prepared.batch.sidecar_signatures
            result = await scanner.commit(prepared)
        saved_good = await repo.find_song_by_file_uri(str(good))
        assert saved_good is not None and saved_good.availability_status == 'AVAILABLE'
        if known:
            assert 'Changed during failure' in saved_good.lyrics
        bad = await repo.find_song_by_file_uri(str(failed))
        if known:
            assert result.unreadable_song_ids == (old.song_id,)
            assert bad.availability_status == 'UNREADABLE'
            assert (bad.song_id, bad.title, bad.lyrics, bad.artwork, bad.content_hash) == (
                old.song_id, old.title, old.lyrics, old.artwork, old.content_hash,
            )
            assert await playlists.list_song_ids(playlist.playlist_id) == [old.song_id]
            assert await playlists.list_favorite_song_ids() == [old.song_id]
        else:
            assert bad is None
        assert parsed[str(failed)] == hashed[str(failed)] == 0
        assert parsed[str(good)] == 1
        assert hashed[str(good)] == (0 if known else 1)
        # Recovery records the failed media without rereading the good result.
        await scanner.scan_full(root)
        recovered = await repo.find_song_by_file_uri(str(failed))
        assert recovered.availability_status == 'AVAILABLE'
        if known:
            assert recovered.song_id == old.song_id
        assert parsed[str(failed)] == hashed[str(failed)] == 1
        assert parsed[str(good)] == 1
        assert hashed[str(good)] == (0 if known else 1)

    asyncio.run(run())


def test_directory_inventory_failure_preserves_old_library(
    tmp_path, media_fixture_dir, monkeypatch,
):
    import os

    root = music_fixture(tmp_path, media_fixture_dir)
    nested = root / 'nested.flac'
    nested.mkdir()
    (root / 'a.flac').rename(nested / 'a.flac')
    original = os.scandir
    injected = []

    def denied(path):
        if str(path) == str(nested):
            injected.append(path)
            raise PermissionError('fixture directory enumeration unavailable')
        return original(path)

    async def run():
        db = str(tmp_path / 'directory-failure.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        coordinator = RealtimeCoordinator(db)
        scanner = LibraryScanner(repo, coordinator=coordinator)
        await scanner.scan_full(root)
        before = await repo.list_songs()
        revision = coordinator.marker().library_revision
        with monkeypatch.context() as patch:
            patch.setattr(os, 'scandir', denied)
            with pytest.raises(LibraryScanError, match='incomplete'):
                await scanner.prepare(root)
        assert injected
        assert await repo.list_songs() == before
        assert coordinator.marker().library_revision == revision

    asyncio.run(run())


def test_manual_deep_retry_does_not_repeat_good_media(tmp_path, media_fixture_dir, monkeypatch):
    from shutil import copy2

    from server.tests.invariants.test_startup_library_reconciliation import spy_media

    root = music_fixture(tmp_path, media_fixture_dir)
    bad = root / 'bad.mp3'
    bad.write_bytes(b'broken media')
    db = str(tmp_path / 'manual-retry.db')

    async def run():
        await initialize_database(db)
        parsed, hashed = spy_media(monkeypatch)
        sync = LibrarySyncService(LibraryScanner(LibraryRepository(db)), IndexedPlayer(root), root)
        await sync.request_scan(None, 'manual')
        job = await sync._jobs.get()
        for _ in range(2):
            with pytest.raises(OSError, match='unreadable media'):
                await sync._scan(job)
        copy2(media_fixture_dir / 'sidecar.mp3', bad)
        await sync._scan(job)
        for path in [root / 'a.flac', root / 'sidecar.mp3']:
            assert parsed[str(path)] == hashed[str(path)] == 1
        assert parsed[str(bad)] == 3 and hashed[str(bad)] == 1

    asyncio.run(run())


def test_observed_signature_backfill_survives_new_metadata_failure(tmp_path, media_fixture_dir, monkeypatch):
    import sqlite3

    from server.app.services.media_metadata import MediaMetadataError
    from server.tests.invariants.test_startup_library_reconciliation import spy_media

    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'observed-failure.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        await scanner.scan_full(root)
        song = await repo.find_song_by_file_uri(str(root / 'a.flac'))
        with sqlite3.connect(db) as c:
            c.execute('DELETE FROM library_sidecar_signatures WHERE song_id=?', (song.song_id,))
        (root / 'bad.mp3').write_bytes(b'broken media')
        parsed, hashed = spy_media(monkeypatch)
        with pytest.raises(MediaMetadataError):
            await scanner.scan_full(root)
        assert song.song_id in dict((await repo.read_scan_baseline()).sidecars)
        assert parsed[str(root / 'a.flac')] == hashed[str(root / 'a.flac')] == 0
        assert parsed[str(root / 'sidecar.mp3')] == hashed[str(root / 'sidecar.mp3')] == 0
        assert await repo.find_song_by_file_uri(str(root / 'bad.mp3')) is None

    asyncio.run(run())
