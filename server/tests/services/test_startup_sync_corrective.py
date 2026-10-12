"""C3 single-owner lifecycle, exact confirmation, retry and cancellation proofs."""
import asyncio

import pytest
from mutagen.flac import FLAC

from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.services.library_scanner import LibraryScanConflict, LibraryScanner
from server.app.services.library_sync_service import LibrarySyncService
from server.tests.invariants.test_startup_library_reconciliation import (
    IndexedPlayer,
    music_fixture,
    spy_media,
    wait_synced,
)


@pytest.mark.parametrize('entry', ['wrapper', 'owner'])
def test_baseline_conflict_reuses_unrelated_successful_media(tmp_path, media_fixture_dir, monkeypatch, entry):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'conflict.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        await scanner.scan_full(root)
        audio, unrelated = root / 'a.flac', root / 'sidecar.mp3'
        tags = FLAC(audio)
        tags['title'] = ['Changed Audio']
        tags.save()
        (root / 'sidecar.lrc').write_text('[00:01.00] Changed Lyrics\n')
        parsed, hashed = spy_media(monkeypatch)
        commit = scanner.commit
        raced = False
        retries, conflicts = [], []

        async def racing(prepared, **kwargs):
            nonlocal raced
            if not raced:
                raced = True
                song = await repo.find_song_by_file_uri(str(audio))
                await repo.upsert_song(song.model_copy(update={'title': 'Concurrent Writer'}))
            try:
                return await commit(prepared, **kwargs)
            except LibraryScanConflict as exc:
                conflicts.append(str(exc))
                raise

        async def sleep(seconds):
            retries.append(seconds)
            await asyncio.sleep(0)

        monkeypatch.setattr(scanner, 'commit', racing)
        if entry == 'wrapper':
            await scanner.scan_full(root)
        else:
            sync = LibrarySyncService(scanner, IndexedPlayer(root), root, sleep=sleep)
            await sync.request_scan(None, 'startup')
            task = asyncio.create_task(sync.run())
            try:
                await wait_synced(sync)
                assert sync.get_state().generation == 1
                assert retries == [2]
            finally:
                await sync.close()
                await asyncio.wait_for(task, 1)
        assert raced
        assert conflicts == ["Library baseline changed before commit"]
        assert (await repo.find_song_by_file_uri(str(audio))).title == 'Changed Audio'
        assert (await repo.find_song_by_file_uri(str(unrelated))).lyrics == '[00:01.00] Changed Lyrics\n'
        assert parsed[str(audio)] == hashed[str(audio)] == 2
        assert hashed[str(unrelated)] == 0
        assert parsed[str(unrelated)] == 1, dict(parsed)

    asyncio.run(run())


@pytest.mark.parametrize('fault', ['status', 'uri', 'timeout', 'unknown'])
def test_precheck_failure_never_blindly_updates(tmp_path, media_fixture_dir, fault):
    from server.app.player.ports import PlayerUnavailable

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        db = str(tmp_path / 'unknown.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        await LibraryScanner(repo).scan_full(root)
        attempts, waits = [], []

        class Player(IndexedPlayer):
            async def database_update_status(self):
                if fault == 'status' and not attempts:
                    attempts.append('fault')
                    raise PlayerUnavailable('read unavailable')
                return await super().database_update_status()

            async def has_library_uri(self, uri):
                if fault != 'status' and not attempts:
                    attempts.append('fault')
                    if fault == 'uri':
                        raise PlayerUnavailable('read unavailable')
                    if fault == 'timeout':
                        raise TimeoutError('read timed out')
                    return None  # unknown is not False
                return await super().has_library_uri(uri)

        async def sleep(seconds):
            waits.append(seconds)
            await asyncio.sleep(0)

        player = Player(root)
        sync = LibrarySyncService(LibraryScanner(repo), player, root, sleep=sleep)
        await sync.request_scan(None, 'startup')
        task = asyncio.create_task(sync.run())
        try:
            await wait_synced(sync)
            assert attempts == ['fault']
            assert waits == [2]
            assert player.calls.count(('update',)) == 0, player.calls
        finally:
            await sync.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_accepted_update_is_not_repeated_on_confirmation_retry(tmp_path, media_fixture_dir):
    from server.app.player.ports import PlayerUnavailable

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        db = str(tmp_path / 'accepted.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        await LibraryScanner(repo).scan_full(root)
        failed, waits = [], []

        class Player(IndexedPlayer):
            async def has_library_uri(self, uri):
                if ('update',) in self.calls and not failed:
                    failed.append(uri)
                    raise PlayerUnavailable('confirmation disconnected')
                return await super().has_library_uri(uri)

        async def sleep(seconds):
            waits.append(seconds)
            await asyncio.sleep(0)

        player = Player(root, consistent=False)
        sync = LibrarySyncService(LibraryScanner(repo), player, root, sleep=sleep)
        await sync.request_scan(None, 'startup')
        task = asyncio.create_task(sync.run())
        try:
            await wait_synced(sync)
            assert failed and waits == [2]
            assert player.calls.count(('update',)) == 1, player.calls
            update = player.calls.index(('update',))
            assert player.calls[0] == ('status',)
            assert any(c[0] == 'uri' and not c[2] for c in player.calls[:update])
            assert player.calls[update + 1] == ('status',)
        finally:
            await sync.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


@pytest.mark.parametrize('outcome', ['unknown', 'rejected'])
def test_update_outcome_is_reread_before_any_retry(tmp_path, media_fixture_dir, outcome):
    from server.app.player.ports import PlayerCommandError

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        db = str(tmp_path / 'update.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        await LibraryScanner(repo).scan_full(root)
        waits = []

        class Player(IndexedPlayer):
            async def update_database(self):
                if ('update',) not in self.calls:
                    self.calls.append(('update',))
                    if outcome == 'unknown':
                        self.library_uris = set(self.expected)
                        raise OSError('reply lost after acceptance')
                    raise PlayerCommandError('update', 'explicit rejection')
                await super().update_database()

        async def sleep(seconds):
            waits.append(seconds)
            await asyncio.sleep(0)

        player = Player(root, consistent=False)
        sync = LibrarySyncService(LibraryScanner(repo), player, root, sleep=sleep)
        await sync.request_scan(None, 'startup')
        task = asyncio.create_task(sync.run())
        try:
            await wait_synced(sync)
            assert waits == [2]
            assert player.calls.count(('update',)) == (1 if outcome == 'unknown' else 2)
            first = player.calls.index(('update',))
            assert player.calls[first + 1] == ('status',), player.calls
        finally:
            await sync.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


@pytest.mark.parametrize('change', ['add', 'modify', 'delete', 'move', 'lrc'])
def test_local_delta_updates_only_audio_and_confirms_exact_targets(tmp_path, media_fixture_dir, monkeypatch, change):
    from shutil import copy2

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        db = str(tmp_path / 'delta.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        await LibraryScanner(repo).scan_full(root)
        audio = root / 'a.flac'
        old_song = await repo.find_song_by_file_uri(str(audio))
        player = IndexedPlayer(root)
        target = audio
        if change == 'add':
            target = root / 'added.flac'
            copy2(audio, target)
            player.expected.add(str(target))
            player.library_uris.add(str(target))  # URI consistent still needs audio update
        elif change == 'modify':
            tags = FLAC(audio)
            tags['title'] = ['Changed']
            tags.save()
        elif change == 'delete':
            audio.unlink()
            player.expected.remove(str(audio))
            player.library_uris.remove(str(audio))
        elif change == 'move':
            target = root / 'moved.flac'
            audio.rename(target)
            player.expected.remove(str(audio))
            player.expected.add(str(target))
            player.library_uris = set(player.expected)
        else:
            audio.with_suffix('.lrc').write_text('[00:01.00] Changed\n')
        parsed, hashed = spy_media(monkeypatch)
        sync = LibrarySyncService(LibraryScanner(repo), player, root)
        await sync.request_scan((target if change != 'lrc' else audio.with_suffix('.lrc'),), 'automatic')
        task = asyncio.create_task(sync.run())
        try:
            await wait_synced(sync)
            assert player.calls[0] == ('status',), player.calls
            assert player.calls.count(('update',)) == (0 if change == 'lrc' else 1)
            expected = {str(target)}
            if change == 'move':
                expected.add(str(audio))
                assert (await repo.find_song_by_file_uri(str(target))).song_id == old_song.song_id
            assert {c[1] for c in player.calls if c[0] == 'uri'} == expected, player.calls
            assert parsed[str(root / 'sidecar.mp3')] == hashed[str(root / 'sidecar.mp3')] == 0
            if change == 'lrc':
                assert parsed[str(audio)] == 1 and hashed[str(audio)] == 0
        finally:
            await sync.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_empty_startup_checks_status_without_update(tmp_path):
    from server.app.player.mock_mpd import MockMPD
    from server.app.player.models import DatabaseUpdateStatus

    async def run():
        root = tmp_path / 'empty'
        root.mkdir()
        db = str(tmp_path / 'empty.db')
        await initialize_database(db)
        calls = []

        class Player(MockMPD):
            async def database_update_status(self):
                calls.append('status')
                return DatabaseUpdateStatus(updating=False)

            async def update_database(self):
                calls.append('update')

        sync = LibrarySyncService(LibraryScanner(LibraryRepository(db)), Player(), root)
        await sync.request_scan(None, 'startup')
        task = asyncio.create_task(sync.run())
        try:
            await wait_synced(sync)
            assert calls == ['status']
        finally:
            await sync.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


@pytest.mark.parametrize('component', ['config', 'mapper'])
@pytest.mark.parametrize('operation', ['stat', 'resolve', 'iterdir', 'open'])
def test_config_and_mapper_construction_do_not_touch_music_root(tmp_path, monkeypatch, component, operation):
    from pathlib import Path

    from server.app.config import AppConfig
    from server.app.player.music_uri import MusicUriMapper

    root = tmp_path / 'music'
    root.mkdir()
    calls = []
    original = getattr(Path, operation)

    def observed(path, *args, **kwargs):
        if path == root or path.is_relative_to(root):
            calls.append(str(path))
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, operation, observed)
        if component == 'config':
            AppConfig(music_root=root, mpd_connection_path=tmp_path / 'connection.json')
        else:
            MusicUriMapper(root)
    assert calls == [], calls


def test_mapper_first_use_canonicalizes_root_and_rejects_symlink_escape(tmp_path, monkeypatch):
    from pathlib import Path

    from server.app.player.music_uri import MusicUriMapper

    root, alias, outside = tmp_path / 'music', tmp_path / 'alias', tmp_path / 'outside'
    root.mkdir()
    outside.mkdir()
    alias.symlink_to(root, target_is_directory=True)
    (root / 'escape').symlink_to(outside, target_is_directory=True)
    calls = []
    original = Path.resolve

    def observed(path, *args, **kwargs):
        calls.append(path)
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'resolve', observed)
        mapper = MusicUriMapper(alias, 'prefix')
        before = list(calls)
        assert mapper.to_local('prefix/ok.flac') == str(root / 'ok.flac')
        assert mapper.to_mpd(str(root / 'ok.flac')) == 'prefix/ok.flac'
        with pytest.raises(ValueError):
            mapper.to_local('prefix/escape/song.flac')
    assert before == [], before
    assert alias in calls


def test_shutdown_during_prepare_has_no_late_update(tmp_path, media_fixture_dir, monkeypatch):
    import threading

    from server.app.services import library_scan_prepare as media
    from server.app.services.events import LibraryChangedEvent
    from server.app.services.library_runtime import LibraryRuntime

    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'cancel.db')
    entered, release = threading.Event(), threading.Event()
    original = media.parse_media_file
    completions = []

    def barrier(path):
        entered.set()
        assert release.wait(3)
        return original(path)

    class Publisher:
        async def publish(self, event):
            if isinstance(event, LibraryChangedEvent):
                completions.append(event)

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        player = IndexedPlayer(root)
        sync = LibrarySyncService(LibraryScanner(repo, Publisher()), player, root)
        runtime = LibraryRuntime(sync, root)
        monkeypatch.setattr(media, 'parse_media_file', barrier)
        task = asyncio.create_task(runtime.run())
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            closing = asyncio.create_task(runtime.close())
            await asyncio.sleep(0.01)
            assert not closing.done()  # cooperative close joins the real worker
            release.set()
            await asyncio.wait_for(closing, 1)
            await asyncio.wait_for(task, 1)
            await asyncio.sleep(0.01)
            assert await repo.list_songs() == []
            assert player.calls == []
            assert completions == []
        finally:
            release.set()
            await runtime.close()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())


def test_next_generation_keeps_failed_paths_and_move_absence(tmp_path, media_fixture_dir, monkeypatch):
    from shutil import copy2

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        db = str(tmp_path / 'generation.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        await LibraryScanner(repo).scan_full(root)
        audio, moved, bad, new = (root / n for n in ('a.flac', 'moved.flac', 'bad.mp3', 'new.flac'))
        original = await repo.find_song_by_file_uri(str(audio))
        audio.rename(moved)
        bad.write_bytes(b'invalid media')
        player = IndexedPlayer(root)
        player.library_uris.add(str(audio))
        failed = asyncio.Event()
        waits, states = [], []
        parsed, hashed = spy_media(monkeypatch)
        sync = None

        async def sleep(seconds):
            waits.append(seconds)
            states.append(sync.get_state())
            failed.set()
            await asyncio.Event().wait()

        sync = LibrarySyncService(LibraryScanner(repo), player, root, sleep=sleep)
        first = await sync.request_scan(None, 'startup')
        task = asyncio.create_task(sync.run())
        try:
            await asyncio.wait_for(failed.wait(), 1)
            assert sync.get_state().status == 'FAILED'
            copy2(media_fixture_dir / 'sidecar.mp3', bad)
            copy2(media_fixture_dir / 'metadata.flac', new)
            player.expected.add(str(new))
            second = await sync.request_scan((new,), 'manual')
            await wait_synced(sync)
            assert sync.get_state().generation == 2 and sync.get_state().activity_id == second
            assert states[0].activity_id == first and waits == [2]
            assert (await repo.find_song_by_file_uri(str(moved))).song_id == original.song_id
            assert (await repo.find_song_by_file_uri(str(bad))).availability_status == 'AVAILABLE'
            assert any(c == ('uri', str(audio), False) for c in player.calls)
            assert parsed[str(bad)] == 2 and hashed[str(bad)] == 1
            assert parsed[str(moved)] == hashed[str(moved)] == 1
            assert parsed[str(root / 'sidecar.mp3')] == hashed[str(root / 'sidecar.mp3')] == 0
        finally:
            await sync.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_startup_seeds_same_inventory_in_memory_outside_lock(tmp_path, media_fixture_dir, monkeypatch):
    import threading

    from server.app.repositories.database import transaction_identity
    from server.app.services import library_scan_prepare as media
    from server.app.services.library_change_detector import LibraryChangeDetector
    from server.app.services.library_runtime import LibraryRuntime

    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'seed.db')
    prepared, seeds, walks, worker_threads = [], [], [], []
    prepare, walk = media.prepare_scan, media._walk
    seed = getattr(LibraryChangeDetector, 'seed', None)

    def preparing(*args, **kwargs):
        worker_threads.append(threading.get_ident())
        with pytest.raises(RuntimeError):
            transaction_identity(db)
        result = prepare(*args, **kwargs)
        prepared.append(result)
        return result

    def walking(*args):
        walks.append(args[0])
        return walk(*args)

    def seeding(self, inventory):
        seeds.append(inventory)
        with pytest.raises(RuntimeError):
            transaction_identity(db)
        from pathlib import Path
        with monkeypatch.context() as patch:
            def forbidden(*args, **kwargs):
                pytest.fail('seed performed music filesystem I/O')
            for operation in ('stat', 'resolve', 'iterdir', 'open'):
                patch.setattr(Path, operation, forbidden)
            if seed is not None:
                seed(self, inventory)

    monkeypatch.setattr(media, 'prepare_scan', preparing)
    monkeypatch.setattr(media, '_walk', walking)
    monkeypatch.setattr(LibraryChangeDetector, 'seed', seeding, raising=False)

    async def run():
        await initialize_database(db)
        sync = LibrarySyncService(LibraryScanner(LibraryRepository(db)), IndexedPlayer(root), root)
        runtime = LibraryRuntime(sync, root)
        task = asyncio.create_task(runtime.run())
        try:
            await wait_synced(sync)
            await asyncio.sleep(0)
            assert len(prepared) == len(walks) == 1
            assert seeds == [prepared[0].inventory]
            assert seeds[0] is prepared[0].inventory
            assert worker_threads[0] != threading.get_ident()
        finally:
            await runtime.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


@pytest.mark.parametrize('operation', ['stat', 'access'])
def test_config_construction_has_no_os_root_probe(tmp_path, monkeypatch, operation):
    import os
    from pathlib import Path

    from server.app.config import AppConfig

    root = tmp_path / 'music'
    root.mkdir()
    original = getattr(os, operation)
    calls = []

    def observed(path, *args, **kwargs):
        if Path(path) == root:
            calls.append(str(path))
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(os, operation, observed)
        AppConfig(music_root=root, mpd_connection_path=tmp_path / 'connection.json')
    assert calls == [], calls


def test_accepted_update_timeout_retry_preserves_single_update(tmp_path, media_fixture_dir):
    from server.app.player.models import DatabaseUpdateStatus

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        db = str(tmp_path / 'timeout.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        await LibraryScanner(repo).scan_full(root)
        now, sleeps = [0.0], []
        busy = [False]

        class Player(IndexedPlayer):
            async def update_database(self):
                await super().update_database()
                busy[0] = True

            async def database_update_status(self):
                self.calls.append(('status',))
                return DatabaseUpdateStatus(updating=busy[0])

        async def sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds
            if seconds == 2:
                assert sync.get_state().error_code == 'MPD_SYNC_TIMEOUT'
                busy[0] = False
            await asyncio.sleep(0)

        player = Player(root, consistent=False)
        sync = LibrarySyncService(LibraryScanner(repo), player, root, sleep=sleep, clock=lambda: now[0])
        await sync.request_scan(None, 'startup')
        task = asyncio.create_task(sync.run())
        try:
            await wait_synced(sync)
            assert sleeps == [1] * 60 + [2]
            assert player.calls.count(('update',)) == 1
        finally:
            await sync.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_shutdown_after_commit_keeps_facts_without_success_or_late_update(tmp_path, media_fixture_dir):
    from server.app.services.events import LibraryChangedEvent, LibrarySyncChangedEvent

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        db = str(tmp_path / 'committed-shutdown.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        entered = asyncio.Event()
        completions, updates = [], []

        class Publisher:
            async def publish(self, event):
                if isinstance(event, LibraryChangedEvent) or (isinstance(event, LibrarySyncChangedEvent) and event.state.status == 'SYNCED'):
                    completions.append(event)

        class Player(IndexedPlayer):
            async def update_database(self):
                updates.append('update')
                entered.set()
                await asyncio.Event().wait()

        sync = LibrarySyncService(LibraryScanner(repo, Publisher()), Player(root), root, event_publisher=Publisher())
        await sync.request_scan(None, 'startup')
        task = asyncio.create_task(sync.run())
        try:
            await asyncio.wait_for(entered.wait(), 1)
            before = await repo.list_songs()
            assert len(before) == 2
            await sync.close()
            await asyncio.wait_for(task, 1)
            assert await repo.list_songs() == before
            assert updates == ['update'] and completions == []
        finally:
            await sync.close()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())


def test_partial_scan_rollback_does_not_drop_good_uncommitted_paths(tmp_path, media_fixture_dir, monkeypatch):
    from shutil import copy2

    from server.app.services.realtime_coordinator import RealtimeCoordinator

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        (root / 'sidecar.mp3').unlink()
        bad = root / 'bad.mp3'
        bad.write_bytes(b'invalid media')
        db = str(tmp_path / 'rollback-paths.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        coordinator = RealtimeCoordinator(db)
        stage = coordinator.stage_library_sync
        attempts, waits = [], []

        def fail_once(state):
            attempts.append(state)
            if len(attempts) == 1:
                raise RuntimeError('rollback after batch observer')
            return stage(state)

        async def sleep(seconds):
            waits.append(seconds)
            if len(waits) == 1:
                assert await repo.list_songs() == []
            if len(waits) == 2:
                copy2(media_fixture_dir / 'sidecar.mp3', bad)
            await asyncio.sleep(0)

        monkeypatch.setattr(coordinator, 'stage_library_sync', fail_once)
        sync = LibrarySyncService(LibraryScanner(repo, coordinator=coordinator), IndexedPlayer(root), root, sleep=sleep)
        await sync.request_scan(None, 'startup')
        task = asyncio.create_task(sync.run())
        try:
            await wait_synced(sync)
            assert waits == [2, 5]
            assert (await repo.find_song_by_file_uri(str(root / 'a.flac'))) is not None
            assert (await repo.find_song_by_file_uri(str(bad))).availability_status == 'AVAILABLE'
        finally:
            await sync.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_root_readability_validation_is_deferred_to_worker(tmp_path, media_fixture_dir, monkeypatch):
    import os
    import threading

    from server.app.config import AppConfig
    from server.app.repositories.database import transaction_identity
    from server.app.services.library_scanner import LibraryScanError

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        db = str(tmp_path / 'root-validation.db')
        await initialize_database(db)
        calls = []
        access = os.access
        loop_thread = threading.get_ident()

        def unreadable(path, *args, **kwargs):
            if path == root:
                calls.append(threading.get_ident())
                with pytest.raises(RuntimeError):
                    transaction_identity(db)
                return False
            return access(path, *args, **kwargs)

        monkeypatch.setattr(os, 'access', unreadable)
        config = AppConfig(music_root=root, mpd_connection_path=tmp_path / 'connection.json')
        assert calls == []
        repo = LibraryRepository(db)
        with pytest.raises(LibraryScanError):
            await LibraryScanner(repo).prepare(config.music_root)
        assert calls == [calls[0]] and calls[0] != loop_thread
        assert await repo.list_songs() == []

    asyncio.run(run())


@pytest.mark.parametrize('next_work', ['new_generation', 'new_generation_directory', 'changed_media', 'changed_stable_media'])
def test_conflict_retry_reuses_stable_success_and_prepares_new_facts(tmp_path, media_fixture_dir, monkeypatch, next_work):
    from shutil import copy2

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        db = str(tmp_path / 'conflict-new-facts.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        await scanner.scan_full(root)
        audio, stable, new = root / 'a.flac', root / 'sidecar.mp3', root / 'new.flac'
        tags = FLAC(audio)
        tags['title'] = ['First Version']
        tags.save()
        (root / 'sidecar.lrc').write_text('[00:01.00] Prepared Stable Lyrics\n')
        parsed, hashed = spy_media(monkeypatch)
        commit = scanner.commit
        raced = []
        player = IndexedPlayer(root)
        retry = asyncio.Event()

        async def racing(prepared, **kwargs):
            if not raced:
                raced.append(prepared)
                song = await repo.find_song_by_file_uri(str(audio))
                await repo.upsert_song(song.model_copy(update={'title': 'Concurrent Writer'}))
            return await commit(prepared, **kwargs)

        async def sleep(seconds):
            assert seconds == 2
            if next_work.startswith('new_generation'):
                retry.set()
                await asyncio.Event().wait()
            elif next_work == 'changed_stable_media':
                from mutagen.id3 import ID3, TIT2

                tags = ID3(stable)
                tags.add(TIT2(encoding=3, text=['Changed During Conflict Wait']))
                tags.save(stable)
                await asyncio.sleep(0)
            else:
                # Stable good result changes after the failed commit. The
                # rebase inventory must not validate its old metadata/hash
                # against a newly captured signature.
                copy2(media_fixture_dir / 'metadata.flac', stable.with_suffix('.flac'))
                player.expected.add(str(stable.with_suffix('.flac')))
                await asyncio.sleep(0)

        monkeypatch.setattr(scanner, 'commit', racing)
        sync = LibrarySyncService(scanner, player, root, sleep=sleep)
        await sync.request_scan(None, 'startup')
        task = asyncio.create_task(sync.run())
        try:
            if next_work.startswith('new_generation'):
                await asyncio.wait_for(retry.wait(), 1)
                copy2(media_fixture_dir / 'metadata.flac', new)
                player.expected.add(str(new))
                await sync.request_scan((root if next_work == 'new_generation_directory' else new,), 'manual')
            await wait_synced(sync)
            if next_work == 'changed_stable_media':
                assert (await repo.find_song_by_file_uri(str(stable))).title == 'Changed During Conflict Wait'
                assert parsed[str(stable)] == 2 and hashed[str(stable)] == 1
                return
            target = new if next_work.startswith('new_generation') else stable.with_suffix('.flac')
            assert await repo.find_song_by_file_uri(str(target)) is not None
            assert parsed[str(stable)] == 1 and hashed[str(stable)] == 0
            assert parsed[str(target)] == hashed[str(target)] == 1
        finally:
            await sync.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_startup_path_retry_does_not_seed_unprocessed_new_media_as_accepted(tmp_path, media_fixture_dir):
    from shutil import copy2

    from server.app.services.library_runtime import LibraryRuntime

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        bad, new = root / 'bad.mp3', root / 'new.flac'
        bad.write_bytes(b'broken')
        db = str(tmp_path / 'retry-inventory.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        failed, retry_release, detector_release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        player = IndexedPlayer(root)

        async def retry(seconds):
            assert seconds == 2
            failed.set()
            await retry_release.wait()

        async def detector_sleep(seconds):
            assert seconds == 2
            await detector_release.wait()

        sync = LibrarySyncService(LibraryScanner(repo), player, root, sleep=retry)
        runtime = LibraryRuntime(sync, root)
        runtime.detector._sleep = detector_sleep
        now = [0.0]
        runtime.detector._clock = lambda: now[0]
        task = asyncio.create_task(runtime.run())
        try:
            await asyncio.wait_for(failed.wait(), 1)
            copy2(media_fixture_dir / 'sidecar.mp3', bad)
            copy2(media_fixture_dir / 'metadata.flac', new)
            player.expected.add(str(new))
            retry_release.set()
            await wait_synced(sync)
            await asyncio.sleep(0)
            now[0] = 2
            await runtime.detector.check_once()
            now[0] = 4
            await runtime.detector.check_once()
            async with asyncio.timeout(1):
                while await repo.find_song_by_file_uri(str(new)) is None:
                    await asyncio.sleep(0.001)
            assert sync.get_state().generation == 2
        finally:
            retry_release.set()
            detector_release.set()
            await runtime.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_rebased_prepared_audio_delta_uses_real_database_baseline(tmp_path, media_fixture_dir):
    from shutil import copy2

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        db = str(tmp_path / 'rebase-audio-delta.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        await scanner.scan_full(root)
        new = root / 'new.flac'
        copy2(media_fixture_dir / 'metadata.flac', new)
        prepared = await scanner.prepare(root)
        old = await repo.find_song_by_file_uri(str(root / 'a.flac'))
        await repo.upsert_song(old.model_copy(update={'title': 'Concurrent Writer'}))
        rebased = await scanner.rebase(prepared, root)
        assert rebased.baseline.fingerprint == (await repo.read_scan_baseline()).fingerprint
        assert any(s.file_uri == str(new) for s in rebased.batch.songs)
        assert rebased.audio_index_changed is True

    asyncio.run(run())


def test_prepared_unreadable_availability_delta_requires_audio_update(tmp_path, media_fixture_dir, monkeypatch):
    from server.app.services import library_scan_prepare as media

    async def run():
        root = music_fixture(tmp_path, media_fixture_dir)
        db = str(tmp_path / 'unreadable-audio-delta.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        await scanner.scan_full(root)
        audio = root / 'a.flac'
        audio.write_bytes(b'now invalid media')
        prepared = await scanner.prepare(root)
        assert prepared.failed_paths == (audio,)
        assert prepared.batch.unreadable_file_uris == (str(audio),)
        assert media._audio_changed(prepared.batch, prepared.baseline) is True
        assert prepared.audio_index_changed is True

    asyncio.run(run())
