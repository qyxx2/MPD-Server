from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from server.app.models.library import ScanBatch, Song
from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def repository(tmp_path):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))
    return LibraryRepository(str(path))


def test_batch4_repository_does_not_reclassify_live_identity_candidate_as_move(
    repository,
):
    run(
        repository.upsert_song(
            Song(
                song_id="song-live",
                title="Live Copy",
                file_uri="music/old.flac",
                identity_key="identity-x",
                availability_status="AVAILABLE",
            )
        )
    )

    result = run(
        repository.apply_scan_batch(
            ScanBatch(
                songs=(
                    Song(
                        title="Live Copy",
                        file_uri="music/new.flac",
                        identity_key="identity-x",
                    ),
                )
            )
        )
    )

    assert result.updated_song_ids == ()
    assert result.moved_song_ids == ()
    assert len(result.added_song_ids) == 1
    assert result.added_song_ids[0] != "song-live"
    assert run(repository.get_song("song-live")).file_uri == "music/old.flac"


def test_batch4_repository_reuses_unique_missing_identity_candidate(repository):
    run(
        repository.upsert_song(
            Song(
                song_id="song-missing",
                title="Moved",
                file_uri="music/old.flac",
                identity_key="identity-x",
                availability_status="MISSING",
            )
        )
    )

    result = run(
        repository.apply_scan_batch(
            ScanBatch(
                songs=(
                    Song(
                        title="Moved",
                        file_uri="music/new.flac",
                        identity_key="identity-x",
                    ),
                )
            )
        )
    )

    assert result.updated_song_ids == ("song-missing",)
    assert result.moved_song_ids == ("song-missing",)


def test_batch4_repository_persists_explicit_safe_move_identity(repository):
    run(
        repository.upsert_song(
            Song(
                song_id="song-missing",
                title="Moved",
                file_uri="music/old.flac",
                identity_key="identity-x",
                availability_status="MISSING",
            )
        )
    )

    result = run(
        repository.apply_scan_batch(
            ScanBatch(
                songs=(
                    Song(
                        song_id="song-missing",
                        title="Moved",
                        file_uri="music/new.flac",
                        identity_key="identity-x",
                    ),
                )
            )
        )
    )

    assert result.updated_song_ids == ("song-missing",)
    assert result.moved_song_ids == ("song-missing",)
    restored = run(repository.get_song("song-missing"))
    assert restored is not None
    assert restored.file_uri == "music/new.flac"
    assert restored.availability_status == "AVAILABLE"


def test_batch4_repository_ambiguous_identity_creates_new_song(repository):
    for song_id, file_uri in (
        ("song-a", "music/a.flac"),
        ("song-b", "music/b.flac"),
    ):
        run(
            repository.upsert_song(
                Song(
                    song_id=song_id,
                    title="Same",
                    file_uri=file_uri,
                    identity_key="identity-x",
                    availability_status="AVAILABLE",
                )
            )
        )

    result = run(
        repository.apply_scan_batch(
            ScanBatch(
                songs=(
                    Song(
                        title="Same",
                        file_uri="music/new.flac",
                        identity_key="identity-x",
                    ),
                )
            )
        )
    )

    assert len(result.added_song_ids) == 1
    assert result.updated_song_ids == ()
    assert result.moved_song_ids == ()
    assert result.added_song_ids[0] not in {"song-a", "song-b"}


def test_batch4_repository_identity_ambiguity_is_not_hidden_by_missing_status(
    repository,
):
    for song_id, file_uri, status in (
        ("song-available", "music/available.flac", "AVAILABLE"),
        ("song-missing", "music/missing.flac", "MISSING"),
    ):
        run(
            repository.upsert_song(
                Song(
                    song_id=song_id,
                    title="Same",
                    file_uri=file_uri,
                    identity_key="identity-x",
                    availability_status=status,
                )
            )
        )

    result = run(
        repository.apply_scan_batch(
            ScanBatch(
                songs=(
                    Song(
                        title="Same",
                        file_uri="music/new.flac",
                        identity_key="identity-x",
                    ),
                )
            )
        )
    )

    assert len(result.added_song_ids) == 1
    assert result.added_song_ids[0] not in {"song-available", "song-missing"}
    assert result.updated_song_ids == ()
    assert result.moved_song_ids == ()


def test_batch4_repository_ambiguous_content_hash_creates_new_song(repository):
    for song_id, file_uri in (
        ("song-a", "music/a.flac"),
        ("song-b", "music/b.flac"),
    ):
        run(
            repository.upsert_song(
                Song(
                    song_id=song_id,
                    title=song_id,
                    file_uri=file_uri,
                    content_hash="hash-x",
                    availability_status="MISSING",
                )
            )
        )

    result = run(
        repository.apply_scan_batch(
            ScanBatch(
                songs=(
                    Song(
                        title="New",
                        file_uri="music/new.flac",
                        content_hash="hash-x",
                    ),
                )
            )
        )
    )

    assert len(result.added_song_ids) == 1
    assert result.added_song_ids[0] not in {"song-a", "song-b"}
    assert result.updated_song_ids == ()
    assert result.moved_song_ids == ()


def test_batch4_repository_exact_uri_reuses_existing_song(repository):
    run(
        repository.upsert_song(
            Song(
                song_id="song-existing",
                title="Existing",
                file_uri="music/exact.flac",
                identity_key="identity-x",
            )
        )
    )

    result = run(
        repository.apply_scan_batch(
            ScanBatch(
                songs=(
                    Song(
                        title="Updated",
                        file_uri="music/exact.flac",
                        identity_key="identity-y",
                    ),
                )
            )
        )
    )

    assert result.added_song_ids == ()
    assert result.updated_song_ids == ("song-existing",)
    assert result.moved_song_ids == ()
    restored = run(repository.get_song("song-existing"))
    assert restored is not None
    assert restored.title == "Updated"


def test_batch4_scanner_reuses_unique_missing_identity_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.library_scanner import LibraryScanner
    from server.app.services.media_metadata import ParsedSongMetadata

    db_path = tmp_path / "library.db"
    run(initialize_database(str(db_path)))
    repository = LibraryRepository(str(db_path))

    old_path = tmp_path / "old.mp3"
    target = tmp_path / "new.mp3"
    target.write_bytes(b"identity-move")
    identity_metadata = ParsedSongMetadata(
        title="Moved",
        artists=("Artist",),
        album="Album",
    )

    run(
        repository.upsert_song(
            Song(
                song_id="song-identity-move",
                title="Moved",
                file_uri=str(old_path),
                identity_key="pending",
                availability_status="MISSING",
            )
        )
    )

    from server.app.services import library_scanner as scanner_module

    identity_key = scanner_module._identity_key(identity_metadata)
    run(
        repository.upsert_song(
            Song(
                song_id="song-identity-move",
                title="Moved",
                file_uri=str(old_path),
                identity_key=identity_key,
                availability_status="MISSING",
            )
        )
    )

    monkeypatch.setattr(
        scanner_module, "parse_media_file", lambda _path: identity_metadata
    )

    result = run(LibraryScanner(repository).scan_paths([target]))

    assert result.updated_song_ids == ("song-identity-move",)
    assert result.moved_song_ids == ("song-identity-move",)
    restored = run(repository.get_song("song-identity-move"))
    assert restored is not None
    assert restored.file_uri == str(target)


def test_batch4_scanner_reuses_unique_missing_content_hash_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.library_scanner import LibraryScanner
    from server.app.services.media_metadata import ParsedSongMetadata

    db_path = tmp_path / "library.db"
    run(initialize_database(str(db_path)))
    repository = LibraryRepository(str(db_path))

    target = tmp_path / "new.mp3"
    payload = b"content-hash-move"
    target.write_bytes(payload)
    content_hash = hashlib.sha256(payload).hexdigest()

    run(
        repository.upsert_song(
            Song(
                song_id="song-hash-move",
                title="Old",
                file_uri=str(tmp_path / "old.mp3"),
                identity_key="old-identity",
                content_hash=content_hash,
                availability_status="MISSING",
            )
        )
    )

    from server.app.services import library_scanner as scanner_module

    metadata = ParsedSongMetadata(title="New", artists=("Artist",))
    monkeypatch.setattr(
        scanner_module, "parse_media_file", lambda _path: metadata
    )

    result = run(LibraryScanner(repository).scan_paths([target]))

    assert result.updated_song_ids == ("song-hash-move",)
    assert result.moved_song_ids == ("song-hash-move",)
    restored = run(repository.get_song("song-hash-move"))
    assert restored is not None
    assert restored.file_uri == str(target)


def test_batch4_scanner_live_copy_stays_a_new_song_through_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from server.app.services.library_scanner import LibraryScanner
    from server.app.services.media_metadata import ParsedSongMetadata

    db_path = tmp_path / "library.db"
    run(initialize_database(str(db_path)))
    repository = LibraryRepository(str(db_path))

    old_path = tmp_path / "old.mp3"
    copy_path = tmp_path / "copy.mp3"
    payload = b"live-copy"
    old_path.write_bytes(payload)
    copy_path.write_bytes(payload)

    metadata = ParsedSongMetadata(title="Same", artists=("Artist",))
    import server.app.services.library_scanner as scanner_module

    monkeypatch.setattr(
        scanner_module, "parse_media_file", lambda _path: metadata
    )

    first = run(LibraryScanner(repository).scan_paths([old_path]))
    live_id = first.added_song_ids[0]

    second = run(LibraryScanner(repository).scan_paths([copy_path]))

    assert second.added_song_ids
    assert second.added_song_ids[0] != live_id
    assert second.updated_song_ids == ()
    assert second.moved_song_ids == ()
