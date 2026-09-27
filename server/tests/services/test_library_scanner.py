from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from shutil import copy2

import pytest

from server.app.models.library import ScanResult, Song
from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository


def _run(coro):
    return asyncio.run(coro)


def _scanner(db_path: Path):
    from server.app.services.library_scanner import LibraryScanner

    return LibraryScanner(LibraryRepository(str(db_path)))


def test_step4_failed_parse_does_not_overwrite_known_good_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import server.app.services.media_metadata as media_metadata

    db_path = tmp_path / "library.db"
    _run(initialize_database(str(db_path)))
    repository = LibraryRepository(str(db_path))
    target = tmp_path / "track.mp3"
    target.write_bytes(b"placeholder")
    existing = _run(
        repository.upsert_song(
            Song(
                title="Known Good",
                file_uri=str(target),
                lyrics="known-good lyrics",
                metadata_status="OK",
            )
        )
    )

    def fail(_path: Path):
        raise media_metadata.MediaMetadataError("broken media")

    monkeypatch.setattr(
        "server.app.services.library_scanner.parse_media_file",
        fail,
    )

    with pytest.raises(media_metadata.MediaMetadataError):
        _run(_scanner(db_path).scan_paths([target]))

    restored = _run(repository.get_song(existing.song_id))
    assert restored is not None
    assert restored.title == "Known Good"
    assert restored.lyrics == "known-good lyrics"
    assert restored.metadata_status == "OK"


def test_step5_new_file_is_added(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    db_path = tmp_path / "library.db"
    _run(initialize_database(str(db_path)))
    root = tmp_path / "library"
    root.mkdir()
    target = root / "track.mp3"
    copy2(media_fixture_dir / "sidecar.mp3", target)

    result = _run(_scanner(db_path).scan_full(root))

    assert len(result.added_song_ids) == 1


def test_step5_changed_file_is_reconciled(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    db_path = tmp_path / "library.db"
    _run(initialize_database(str(db_path)))
    root = tmp_path / "library"
    root.mkdir()
    target = root / "track.mp3"
    copy2(media_fixture_dir / "sidecar.mp3", target)

    scanner = _scanner(db_path)
    first = _run(scanner.scan_full(root))
    copy2(media_fixture_dir / "no_lyrics.mp3", target)
    second = _run(scanner.scan_paths([target]))

    assert second.updated_song_ids == first.added_song_ids
    song = _run(
        LibraryRepository(str(db_path)).get_song(first.added_song_ids[0])
    )
    assert song is not None
    assert song.title == "MP3 Song"
    assert song.lyrics is None


def test_step5_move_preserves_song_identity(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    db_path = tmp_path / "library.db"
    _run(initialize_database(str(db_path)))
    root = tmp_path / "library"
    root.mkdir()
    old_path = root / "old-name.flac"
    new_path = root / "new-name.flac"
    copy2(media_fixture_dir / "metadata.flac", old_path)

    scanner = _scanner(db_path)
    first = _run(scanner.scan_full(root))
    old_song_id = first.added_song_ids[0]

    old_path.rename(new_path)
    moved = _run(scanner.scan_full(root))
    repository = LibraryRepository(str(db_path))
    song = _run(repository.get_song(old_song_id))

    assert moved.moved_song_ids == (old_song_id,)
    assert song is not None
    assert song.file_uri == str(new_path)


def test_step5_deleted_file_becomes_missing_without_deleting_song_row(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    db_path = tmp_path / "library.db"
    _run(initialize_database(str(db_path)))
    root = tmp_path / "library"
    root.mkdir()
    target = root / "metadata.flac"
    copy2(media_fixture_dir / "metadata.flac", target)

    scanner = _scanner(db_path)
    first = _run(scanner.scan_full(root))
    song_id = first.added_song_ids[0]
    target.unlink()

    result = _run(scanner.scan_full(root))
    song = _run(LibraryRepository(str(db_path)).get_song(song_id))

    assert result.missing_song_ids == (song_id,)
    assert song is not None
    assert song.availability_status == "MISSING"


def test_step5_unreadable_file_is_marked_unreadable(
    tmp_path: Path,
    media_fixture_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "library.db"
    _run(initialize_database(str(db_path)))
    root = tmp_path / "library"
    root.mkdir()
    target = root / "metadata.flac"
    copy2(media_fixture_dir / "metadata.flac", target)

    scanner = _scanner(db_path)
    first = _run(scanner.scan_full(root))
    song_id = first.added_song_ids[0]

    import server.app.services.library_scanner as scanner_module

    real_parser = scanner_module.parse_media_file

    def fail_only_target(path: Path):
        if path == target:
            raise PermissionError("test unreadable")
        return real_parser(path)

    monkeypatch.setattr(scanner_module, "parse_media_file", fail_only_target)
    result = _run(scanner.scan_full(root))
    song = _run(LibraryRepository(str(db_path)).get_song(song_id))

    assert result.unreadable_song_ids == (song_id,)
    assert song is not None
    assert song.availability_status == "UNREADABLE"


def test_step7_scanner_hashes_content_and_uses_unique_identity_for_move(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.library_scanner import LibraryScanner, _identity_key
    from server.app.services.media_metadata import ParsedSongMetadata

    target = tmp_path / "new.mp3"
    target.write_bytes(b"scanner-bytes")
    old = tmp_path / "old.mp3"
    metadata = ParsedSongMetadata(
        title="Moved",
        artists=("Artist",),
        album="Album",
        codec="MP3",
    )
    identity = _identity_key(metadata)
    repository = _ScannerFakeRepository([
        Song(
            song_id="song-old",
            title="Moved",
            file_uri=str(old),
            identity_key=identity,
            availability_status="AVAILABLE",
        )
    ])
    monkeypatch.setattr(
        "server.app.services.library_scanner.parse_media_file",
        lambda _path: metadata,
    )

    result = _run(LibraryScanner(repository).scan_paths([target]))

    scanned = repository.applied[0].songs[0]
    assert result.added_song_ids == ("new",)
    assert scanned.song_id == "song-old"
    assert scanned.file_size == len(b"scanner-bytes")
    assert scanned.content_hash == hashlib.sha256(
        b"scanner-bytes"
    ).hexdigest()


def test_step7_live_copy_and_ambiguous_identity_do_not_match_existing_song(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.library_scanner import LibraryScanner, _identity_key
    from server.app.services.media_metadata import ParsedSongMetadata

    existing_file = tmp_path / "existing.mp3"
    existing_file.write_bytes(b"same")
    copy = tmp_path / "copy.mp3"
    copy.write_bytes(b"same")
    metadata = ParsedSongMetadata(title="Same", artists=("Artist",))
    identity = _identity_key(metadata)
    repository = _ScannerFakeRepository([
        Song(
            song_id="song-live",
            title="Same",
            file_uri=str(existing_file),
            identity_key=identity,
        ),
    ])
    monkeypatch.setattr(
        "server.app.services.library_scanner.parse_media_file",
        lambda _path: metadata,
    )

    _run(LibraryScanner(repository).scan_paths([copy]))
    assert repository.applied[0].songs[0].song_id != "song-live"

    ambiguous = _ScannerFakeRepository([
        Song(
            song_id="song-1",
            title="Same",
            file_uri=str(tmp_path / "one.mp3"),
            identity_key=identity,
        ),
        Song(
            song_id="song-2",
            title="Same",
            file_uri=str(tmp_path / "two.mp3"),
            identity_key=identity,
        ),
    ])
    another = tmp_path / "another.mp3"
    another.write_bytes(b"another")
    _run(LibraryScanner(ambiguous).scan_paths([another]))
    assert ambiguous.applied[0].songs[0].song_id not in {
        "song-1",
        "song-2",
    }


def test_step7_unique_missing_content_hash_is_reused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.library_scanner import LibraryScanner
    from server.app.services.media_metadata import ParsedSongMetadata

    target = tmp_path / "new.mp3"
    target.write_bytes(b"same-content")
    content_hash = hashlib.sha256(b"same-content").hexdigest()
    repository = _ScannerFakeRepository([
        Song(
            song_id="song-missing",
            title="Old",
            file_uri=str(tmp_path / "old.mp3"),
            content_hash=content_hash,
            availability_status="MISSING",
        )
    ])
    monkeypatch.setattr(
        "server.app.services.library_scanner.parse_media_file",
        lambda _path: ParsedSongMetadata(title="New"),
    )

    _run(LibraryScanner(repository).scan_paths([target]))
    assert repository.applied[0].songs[0].song_id == "song-missing"


def test_step7_parse_failure_never_applies_partial_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.library_scanner import LibraryScanner
    from server.app.services.media_metadata import (
        MediaMetadataError,
        ParsedSongMetadata,
    )

    first = tmp_path / "a.mp3"
    second = tmp_path / "b.mp3"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    repository = _ScannerFakeRepository()

    def parser(path: Path):
        if path.name == "b.mp3":
            raise MediaMetadataError("broken")
        return ParsedSongMetadata(title="A")

    monkeypatch.setattr(
        "server.app.services.library_scanner.parse_media_file",
        parser,
    )

    with pytest.raises(MediaMetadataError):
        _run(LibraryScanner(repository).scan_full(tmp_path))
    assert repository.applied == []


def test_step7_unknown_title_is_not_fabricated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.library_scanner import LibraryScanner
    from server.app.services.media_metadata import (
        MediaMetadataError,
        ParsedSongMetadata,
    )

    target = tmp_path / "file-name.mp3"
    target.write_bytes(b"data")
    repository = _ScannerFakeRepository()
    monkeypatch.setattr(
        "server.app.services.library_scanner.parse_media_file",
        lambda _path: ParsedSongMetadata(title=None),
    )

    with pytest.raises(MediaMetadataError, match="title is missing"):
        _run(LibraryScanner(repository).scan_paths([target]))
    assert repository.applied == []


def test_step7_full_scan_does_not_follow_symlinked_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.library_scanner import LibraryScanner

    root = tmp_path / "music"
    external = tmp_path / "external"
    root.mkdir()
    external.mkdir()
    (external / "outside.mp3").write_bytes(b"outside")
    link = root / "external-link"
    try:
        link.symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")

    repository = _ScannerFakeRepository()
    monkeypatch.setattr(
        "server.app.services.library_scanner.parse_media_file",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("symlinked file was scanned")
        ),
    )

    _run(LibraryScanner(repository).scan_full(root))
    assert repository.applied[0].songs == ()


def test_step7_traversal_error_disables_missing_reconciliation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.library_scanner import LibraryScanner

    root = tmp_path / "music"
    root.mkdir()
    target = root / "track.mp3"
    target.write_bytes(b"data")
    repository = _ScannerFakeRepository()
    monkeypatch.setattr(
        "server.app.services.library_scanner._walk",
        lambda _root: ([target], False),
    )

    from server.app.services.media_metadata import ParsedSongMetadata

    monkeypatch.setattr(
        "server.app.services.library_scanner.parse_media_file",
        lambda _path: ParsedSongMetadata(title="Track"),
    )

    _run(LibraryScanner(repository).scan_full(root))
    assert repository.applied[0].reconciled_root_uri_prefix is None


class _ScannerFakeRepository:
    def __init__(self, songs=None):
        self.songs = {
            song.song_id: song
            for song in (songs or [])
            if song.song_id is not None
        }
        self.applied = []

    async def find_song_by_file_uri(self, file_uri: str):
        return next(
            (
                song
                for song in self.songs.values()
                if song.file_uri == file_uri
            ),
            None,
        )

    async def find_song_candidates_by_identity(self, identity_key: str):
        return [
            song
            for song in self.songs.values()
            if song.identity_key == identity_key
        ]

    async def find_song_candidates_by_content_hash(self, content_hash: str):
        return [
            song
            for song in self.songs.values()
            if song.content_hash == content_hash
        ]

    async def list_songs_in_root(self, root_uri_prefix: str):
        return [
            song
            for song in self.songs.values()
            if song.file_uri.startswith(root_uri_prefix)
        ]

    async def apply_scan_batch(self, batch):
        self.applied.append(batch)
        return ScanResult(added_song_ids=("new",))


def _run(coro):
    return asyncio.run(coro)


def test_step10_event_contract_and_post_commit_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.events import (
        DomainEvent,
        EventPublisher,
        LibraryChangedEvent,
        MPDDatabaseUpdater,
    )
    from server.app.services.library_scanner import LibraryScanner
    from server.app.services.media_metadata import ParsedSongMetadata

    event = LibraryChangedEvent(result=ScanResult())
    assert isinstance(event, DomainEvent)
    assert event.event_type == "library.changed"
    assert EventPublisher is not None
    assert MPDDatabaseUpdater is not None

    target = tmp_path / "track.mp3"
    target.write_bytes(b"data")
    result = ScanResult(added_song_ids=("song-1",))
    repository = _ScannerFakeRepository()
    order: list[str] = []

    async def apply(_batch):
        order.append("commit")
        return result

    repository.apply_scan_batch = apply

    class Publisher:
        async def publish(self, published):
            order.append("publish")
            assert isinstance(published, LibraryChangedEvent)
            assert published.result == result

    class Updater:
        async def update_database(self):
            order.append("update")

    monkeypatch.setattr(
        "server.app.services.library_scanner.parse_media_file",
        lambda _path: ParsedSongMetadata(title="Track"),
    )

    returned = _run(
        LibraryScanner(
            repository,
            event_publisher=Publisher(),
            mpd_updater=Updater(),
        ).scan_paths([target])
    )
    assert returned == result
    assert order == ["commit", "update", "publish"]


def test_step10_mpd_update_failure_is_reported_without_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.library_scanner import LibraryScanner
    from server.app.services.media_metadata import ParsedSongMetadata

    target = tmp_path / "track.mp3"
    target.write_bytes(b"data")
    repository = _ScannerFakeRepository()
    received = []

    class Publisher:
        async def publish(self, event):
            received.append(event)

    class Updater:
        async def update_database(self):
            raise RuntimeError("MPD unavailable")

    monkeypatch.setattr(
        "server.app.services.library_scanner.parse_media_file",
        lambda _path: ParsedSongMetadata(title="Track"),
    )

    result = _run(
        LibraryScanner(
            repository,
            event_publisher=Publisher(),
            mpd_updater=Updater(),
        ).scan_paths([target])
    )

    assert result.added_song_ids == ("new",)
    assert len(received) == 1
    assert received[0].mpd_update_error == "MPD unavailable"


def test_step10_repository_failure_never_publishes_or_updates_mpd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.library_scanner import LibraryScanner
    from server.app.services.media_metadata import ParsedSongMetadata

    target = tmp_path / "track.mp3"
    target.write_bytes(b"data")

    class FailingRepository(_ScannerFakeRepository):
        async def apply_scan_batch(self, _batch):
            raise RuntimeError("db failed")

    repository = FailingRepository()
    published = []
    updated = []

    class Publisher:
        async def publish(self, event):
            published.append(event)

    class Updater:
        async def update_database(self):
            updated.append(True)

    monkeypatch.setattr(
        "server.app.services.library_scanner.parse_media_file",
        lambda _path: ParsedSongMetadata(title="Track"),
    )

    with pytest.raises(RuntimeError, match="db failed"):
        _run(
            LibraryScanner(
                repository,
                event_publisher=Publisher(),
                mpd_updater=Updater(),
            ).scan_paths([target])
        )

    assert published == []
    assert updated == []
