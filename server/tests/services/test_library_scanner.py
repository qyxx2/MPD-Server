from __future__ import annotations

import asyncio
from pathlib import Path
from shutil import copy2

import pytest

from server.app.models.library import Song
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

    monkeypatch.setattr(media_metadata, "parse_media_file", fail)

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
