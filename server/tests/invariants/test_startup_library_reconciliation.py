"""C0 behavioral proofs through the existing single-owner runtime.

Parser/hash spies delegate to real media I/O. C2 must move these seams to the
prepare module, without changing the externally observable assertions.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from shutil import copy2

import pytest
from mutagen.flac import FLAC

from server.app.models.history import HistoryEvent
from server.app.player.mock_mpd import MockMPD
from server.app.player.models import DatabaseUpdateStatus
from server.app.repositories.database import initialize_database
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.services import library_scan_prepare as media
from server.app.services.events import LibraryChangedEvent
from server.app.services.library_runtime import LibraryRuntime
from server.app.services.library_scanner import LibraryScanner
from server.app.services.library_sync_service import LibrarySyncService


def music_fixture(tmp_path, media_fixture_dir):
    root = tmp_path / "music"
    root.mkdir()
    copy2(media_fixture_dir / "metadata.flac", root / "a.flac")
    copy2(media_fixture_dir / "sidecar.mp3", root / "sidecar.mp3")
    copy2(media_fixture_dir / "sidecar.lrc", root / "sidecar.lrc")
    return root


class IndexedPlayer(MockMPD):
    def __init__(self, root, *, consistent=True):
        self.expected = {str(p) for p in root.iterdir() if p.suffix in {".flac", ".mp3"}}
        super().__init__(library_uris=self.expected if consistent else ())
        self.calls = []

    async def update_database(self):
        self.calls.append(("update",))
        self.library_uris = set(self.expected)

    async def database_update_status(self):
        self.calls.append(("status",))
        return DatabaseUpdateStatus(updating=False)

    async def has_library_uri(self, uri):
        found = uri in self.library_uris
        self.calls.append(("uri", uri, found))
        return found


async def wait_synced(sync):
    async with asyncio.timeout(3):
        while sync.get_state().status != "SYNCED":
            await asyncio.sleep(0.001)


async def start_once(repo, root, player=None):
    player = player or IndexedPlayer(root)
    completed = asyncio.Event()

    class Publisher:
        async def publish(self, event):
            if isinstance(event, LibraryChangedEvent):
                completed.set()

    sync = LibrarySyncService(LibraryScanner(repo, event_publisher=Publisher()), player, root)
    runtime = LibraryRuntime(sync, root)
    task = asyncio.create_task(runtime.run())
    try:
        await wait_synced(sync)
        await asyncio.wait_for(completed.wait(), 1)
        assert sync.get_state().trigger == "startup"
    finally:
        await runtime.close()
        await asyncio.wait_for(task, 1)
    return player


def spy_media(monkeypatch):
    parsed, hashed = Counter(), Counter()
    parse, hash_file = media.parse_media_file, media._hash_file

    def parsing(path):
        parsed[str(path)] += 1
        return parse(path)

    def hashing(path):
        hashed[str(path)] += 1
        return hash_file(path)

    monkeypatch.setattr(media, "parse_media_file", parsing)
    monkeypatch.setattr(media, "_hash_file", hashing)
    return parsed, hashed


def test_persisted_second_start_skips_parse_and_hash(tmp_path, media_fixture_dir, monkeypatch):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / "restart.db")

    async def run():
        await initialize_database(db)
        await start_once(LibraryRepository(db), root)
        before = await LibraryRepository(db).list_songs()
        parsed, hashed = spy_media(monkeypatch)
        # Fresh Repository, Scanner, Sync and Runtime; keep SQLite and sources.
        await start_once(LibraryRepository(db), root)
        assert (sum(parsed.values()), sum(hashed.values())) == (0, 0)
        after = await LibraryRepository(db).list_songs()
        assert [s.model_dump(exclude={"last_seen_at"}) for s in after] == [s.model_dump(exclude={"last_seen_at"}) for s in before]

    asyncio.run(run())


def check_startup_confirmation(tmp_path, media_fixture_dir, consistent):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / "confirm.db")

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        await start_once(repo, root)
        player = IndexedPlayer(root, consistent=consistent)
        await player.queue_add("business-only.flac")
        queue, status = await player.queue_entries(), await player.status()
        await start_once(repo, root, player)
        assert await player.queue_entries() == queue
        assert await player.status() == status
        uris = [call for call in player.calls if call[0] == "uri"]
        assert {call[1] for call in uris} == player.expected
        if consistent:
            assert player.calls.count(("update",)) == 0
            assert uris and all(call[2] for call in uris)
        else:
            assert player.calls.count(("update",)) == 1
            update = player.calls.index(("update",))
            assert any(call[0] == "uri" and not call[2] for call in player.calls[:update]), player.calls
            assert all(call[2] for call in player.calls[update + 1:] if call[0] == "uri")
            assert player.calls[update + 1][0] == "status"

    asyncio.run(run())


def test_unchanged_consistent_startup_does_not_update(tmp_path, media_fixture_dir):
    check_startup_confirmation(tmp_path, media_fixture_dir, True)


def test_inconsistent_startup_updates_once_then_confirms(tmp_path, media_fixture_dir):
    check_startup_confirmation(tmp_path, media_fixture_dir, False)


@pytest.mark.parametrize("change", ["add", "modify", "delete", "move", "lrc_add", "lrc_modify", "lrc_delete"])
def test_reconcile_only_related_paths(tmp_path, media_fixture_dir, monkeypatch, change):
    root = music_fixture(tmp_path, media_fixture_dir)
    audio, sidecar = root / "a.flac", root / "sidecar.mp3"
    db = str(tmp_path / "delta.db")

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        await start_once(repo, root)
        song = await repo.find_song_by_file_uri(str(audio))
        playlists = PlaylistRepository(db)
        playlist = await playlists.create_playlist("Kept")
        await playlists.add_song(playlist.playlist_id, song.song_id)
        await playlists.set_favorite(song.song_id, True)
        history = HistoryRepository(db)
        await history.record_history(HistoryEvent(song_id=song.song_id, started_at=datetime.now(timezone.utc), reason="USER_NEXT", session_id="c0"))
        old_history = await history.list_history()
        target = audio
        if change == "add":
            target = root / "new.flac"
            copy2(audio, target)
        elif change == "modify":
            tags = FLAC(audio)
            tags["title"] = ["Changed"]
            tags.save()
        elif change == "delete":
            audio.unlink()
        elif change == "move":
            target = root / "moved.flac"
            audio.rename(target)
        elif change == "lrc_add":
            target = audio
            audio.with_suffix(".lrc").write_text("[00:01.00] Added\n")
        else:
            target = sidecar
            if change == "lrc_modify":
                sidecar.with_suffix(".lrc").write_text("[00:01.00] Changed\n")
            else:
                sidecar.with_suffix(".lrc").unlink()
        parsed, hashed = spy_media(monkeypatch)
        await start_once(LibraryRepository(db), root)
        assert await playlists.list_song_ids(playlist.playlist_id) == [song.song_id]
        assert await playlists.list_favorite_song_ids() == [song.song_id]
        assert await history.list_history() == old_history
        if change == "move":
            assert (await repo.find_song_by_file_uri(str(target))).song_id == song.song_id
        if change == "delete":
            assert (await repo.get_song(song.song_id)).availability_status == "MISSING"
        if change.startswith("lrc"):
            changed = await repo.find_song_by_file_uri(str(target))
            assert changed.lyrics_source == ("embedded" if change == "lrc_delete" else "sidecar")
        expected_parse = Counter() if change == "delete" else Counter({str(target): 1})
        expected_hash = Counter() if change == "delete" or change.startswith("lrc") else Counter({str(target): 1})
        assert (parsed, hashed) == (expected_parse, expected_hash)

    asyncio.run(run())


@pytest.mark.parametrize("known", [False, True], ids=["new", "known"])
def test_corrupt_path_retry_does_not_repeat_good_media(tmp_path, media_fixture_dir, monkeypatch, known):
    root = music_fixture(tmp_path, media_fixture_dir)
    # Isolate one good path and one new bad path.
    (root / "sidecar.mp3").unlink()
    bad = root / "b.mp3"
    bad.write_bytes(b"invalid media")
    db = str(tmp_path / "retry.db")
    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        old_bad = None
        if known:
            copy2(media_fixture_dir / "sidecar.mp3", bad)
            await LibraryScanner(repo).scan_paths([bad])
            old_bad = await repo.find_song_by_file_uri(str(bad))
            bad.write_bytes(b"invalid media")
        parsed, hashed = spy_media(monkeypatch)
        waits, states, snapshots = [], [], []
        sync = None

        async def sleep(seconds):
            waits.append(seconds)
            states.append(sync.get_state())
            # Observe the committed good result between retries.
            snapshots.append(await repo.list_songs())
            if len(waits) == 2:
                copy2(media_fixture_dir / "sidecar.mp3", bad)
            await asyncio.sleep(0)

        sync = LibrarySyncService(LibraryScanner(repo), IndexedPlayer(root), root, sleep=sleep)
        runtime = LibraryRuntime(sync, root)
        task = asyncio.create_task(runtime.run())
        try:
            await wait_synced(sync)
        finally:
            await runtime.close()
            await asyncio.wait_for(task, 1)
        assert waits == [2, 5]
        for songs in snapshots:
            saved_bad = next((s for s in songs if s.file_uri == str(bad)), None)
            if known:
                assert saved_bad is not None
                assert (saved_bad.song_id, saved_bad.title, saved_bad.lyrics, saved_bad.artwork) == (old_bad.song_id, old_bad.title, old_bad.lyrics, old_bad.artwork)
            else:
                assert saved_bad is None
        assert all(state.status == "FAILED" for state in states)
        assert len({state.activity_id for state in states}) == 1
        good_committed = all(any(s.file_uri == str(root / "a.flac") for s in songs) for songs in snapshots)
        assert (good_committed, parsed[str(root / "a.flac")], hashed[str(root / "a.flac")]) == (True, 1, 1)
        if known:
            assert all(next(s for s in songs if s.file_uri == str(bad)).availability_status == "UNREADABLE" for songs in snapshots)
        assert (parsed[str(bad)], hashed[str(bad)]) == (3, 1)
        assert (await repo.find_song_by_file_uri(str(bad))).availability_status == "AVAILABLE"

    asyncio.run(run())


@pytest.mark.parametrize("operation", ["resolve", "stat", "iterdir", "open"])
def test_constructor_has_no_filesystem_io(tmp_path, monkeypatch, operation):
    calls = []
    original = getattr(Path, operation)

    def observed(path, *args, **kwargs):
        calls.append(str(path))
        return original(path, *args, **kwargs)

    # Record real calls instead of raising an assembly exception.
    with monkeypatch.context() as patch:
        patch.setattr(Path, operation, observed)
        sync = LibrarySyncService(LibraryScanner(LibraryRepository(str(tmp_path / "db"))), MockMPD(), tmp_path)
        LibraryRuntime(sync, tmp_path)
    assert calls == [], f"constructor performed Path.{operation}: {calls}"


def test_startup_inventory_seed_does_not_immediately_walk(tmp_path, media_fixture_dir, monkeypatch):
    from server.app.services import library_change_detector as detector_module

    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / "inventory.db")
    walks = []
    read, walk = detector_module.read_signatures, media._walk

    def inventory(*args):
        walks.append("inventory")
        return read(*args)

    def audio_walk(*args):
        walks.append("audio")
        return walk(*args)

    monkeypatch.setattr(detector_module, "read_signatures", inventory)
    monkeypatch.setattr(media, "_walk", audio_walk)

    async def run():
        await initialize_database(db)
        sync = LibrarySyncService(LibraryScanner(LibraryRepository(db)), IndexedPlayer(root), root)
        runtime = LibraryRuntime(sync, root)
        sleep_entered, release = asyncio.Event(), asyncio.Event()
        now = [0.0]

        async def sleep(seconds):
            sleep_entered.set()
            await release.wait()
            now[0] += seconds

        runtime.detector._sleep = sleep
        runtime.detector._clock = lambda: now[0]
        task = asyncio.create_task(runtime.run())
        try:
            await wait_synced(sync)
            await asyncio.wait_for(sleep_entered.wait(), 1)
            assert now[0] == 0
            assert len(walks) == 1, walks
        finally:
            release.set()
            await runtime.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())


def test_failed_startup_has_no_competing_detector_walk(tmp_path, media_fixture_dir, monkeypatch):
    from server.app.services import library_change_detector as detector_module

    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / "failed-inventory.db")
    walks = []
    read = detector_module.read_signatures

    prepare = media.prepare_scan

    def unavailable(*args, **kwargs):
        walks.append("startup")
        prepare(*args, **kwargs)
        raise PermissionError("fixture root temporarily unreadable")

    def detecting(*args):
        walks.append("detector")
        return read(*args)

    async def run():
        await initialize_database(db)
        retry_entered, release = asyncio.Event(), asyncio.Event()

        async def retry_sleep(_):
            retry_entered.set()
            await release.wait()

        sync = LibrarySyncService(LibraryScanner(LibraryRepository(db)), IndexedPlayer(root), root, sleep=retry_sleep)
        runtime = LibraryRuntime(sync, root)
        monkeypatch.setattr(media, "prepare_scan", unavailable)
        monkeypatch.setattr(detector_module, "read_signatures", detecting)
        task = asyncio.create_task(runtime.run())
        try:
            await asyncio.wait_for(retry_entered.wait(), 1)
            assert sync.get_state().status == "FAILED"
            # Let the independently scheduled detector reach its first check;
            # observing only the retry event can race its to_thread dispatch.
            await asyncio.sleep(0.1)
            assert walks == ["startup"], walks
        finally:
            release.set()
            await runtime.close()
            await asyncio.wait_for(task, 1)

    asyncio.run(run())
