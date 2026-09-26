from __future__ import annotations

import asyncio
from pathlib import Path
from shutil import copy2

import pytest


def _run(coro):
    return asyncio.run(coro)


def test_step5_new_file_is_added_and_changed_file_is_reconciled(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    from server.app.services.library_scanner import scan_full, scan_paths

    root = tmp_path / "library"
    root.mkdir()
    target = root / "track.mp3"
    copy2(media_fixture_dir / "sidecar.mp3", target)

    first = _run(scan_full(root))
    assert first.added == [target]

    copy2(media_fixture_dir / "no_lyrics.mp3", target)
    second = _run(scan_paths([target]))
    assert second.changed == [target]


def test_step5_move_preserves_song_identity(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    from server.app.services.library_scanner import scan_full

    root = tmp_path / "library"
    root.mkdir()
    old_path = root / "old-name.flac"
    new_path = root / "new-name.flac"
    copy2(media_fixture_dir / "metadata.flac", old_path)

    first = _run(scan_full(root))
    song_id = first.added[0].song_id

    old_path.rename(new_path)
    moved = _run(scan_full(root))

    assert moved.moved == [(song_id, old_path, new_path)]


def test_step5_deleted_file_is_removed_from_current_library(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    from server.app.services.library_scanner import scan_full

    root = tmp_path / "library"
    root.mkdir()
    target = root / "metadata.flac"
    copy2(media_fixture_dir / "metadata.flac", target)

    _run(scan_full(root))
    target.unlink()

    result = _run(scan_full(root))
    assert result.deleted == [target]


def test_step5_unreadable_file_is_reported_without_becoming_a_song(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import server.app.services.library_scanner as scanner

    root = tmp_path / "library"
    root.mkdir()
    target = root / "unreadable.mp3"
    target.write_bytes(b"placeholder")

    original_parser = scanner.parse_media_file

    def raise_permission_error(path: Path):
        if path == target:
            raise PermissionError("unreadable test fixture")
        return original_parser(path)

    monkeypatch.setattr(scanner, "parse_media_file", raise_permission_error)

    result = _run(scanner.scan_full(root))

    assert result.failed == [target]
    assert result.added == []
