from __future__ import annotations

import asyncio
import hashlib
import sqlite3
from pathlib import Path
from shutil import copy2

from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.services.library_scanner import LibraryScanner


def run(coro):
    return asyncio.run(coro)


def make_scanner(db_path: Path) -> tuple[LibraryScanner, LibraryRepository]:
    repository = LibraryRepository(str(db_path))
    return LibraryScanner(repository), repository


def prepare_library(tmp_path: Path) -> tuple[Path, Path]:
    db_path = tmp_path / "library.db"
    root = tmp_path / "library"
    root.mkdir()
    run(initialize_database(str(db_path)))
    return db_path, root


def test_task3_to_task2_scans_real_flac_and_mp3_into_get_song(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    db_path, root = prepare_library(tmp_path)
    flac_path = root / "metadata.flac"
    mp3_path = root / "sidecar.mp3"
    copy2(media_fixture_dir / "metadata.flac", flac_path)
    copy2(media_fixture_dir / "sidecar.mp3", mp3_path)
    copy2(media_fixture_dir / "sidecar.lrc", root / "sidecar.lrc")

    scanner, repository = make_scanner(db_path)
    result = run(scanner.scan_full(root))

    assert len(result.added_song_ids) == 2
    flac_id = next(
        song_id
        for song_id in result.added_song_ids
        if run(repository.get_song(song_id)).file_uri == str(flac_path)
    )
    mp3_id = next(
        song_id
        for song_id in result.added_song_ids
        if run(repository.get_song(song_id)).file_uri == str(mp3_path)
    )

    flac = run(repository.get_song(flac_id))
    assert flac is not None
    assert flac.title == "Test Song"
    assert flac.artists == ("Artist A", "Artist B")
    assert flac.album == "Test Album"
    assert flac.album_artists == ("Album Artist",)
    assert flac.track_number == 2
    assert flac.disc_number == 1
    assert flac.year == 2024
    assert flac.date == "2024-08-09"
    assert set(flac.genres) == {"Rock", "Alt"}
    assert flac.codec == "FLAC"
    assert flac.bit_depth == 16
    assert flac.sample_rate_hz == 8000
    assert flac.channel_count == 2
    assert flac.duration is not None

    mp3 = run(repository.get_song(mp3_id))
    assert mp3 is not None
    assert mp3.title == "MP3 Song"
    assert mp3.artists == ("MP3 Artist",)
    assert mp3.album == "MP3 Album"
    assert mp3.track_number == 3
    assert mp3.disc_number == 2
    assert mp3.year == 2023
    assert mp3.codec == "MP3"
    assert mp3.bit_depth is None
    assert mp3.sample_rate_hz == 8000
    assert mp3.channel_count == 2
    assert mp3.duration is not None


def test_task3_to_task2_persists_sidecar_and_embedded_lyrics(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    db_path, root = prepare_library(tmp_path)
    sidecar_audio = root / "sidecar.mp3"
    embedded_audio = root / "embedded.flac"
    copy2(media_fixture_dir / "sidecar.mp3", sidecar_audio)
    copy2(media_fixture_dir / "sidecar.lrc", root / "sidecar.lrc")
    copy2(media_fixture_dir / "metadata.flac", embedded_audio)

    scanner, repository = make_scanner(db_path)
    result = run(scanner.scan_full(root))

    assert len(result.added_song_ids) == 2
    songs = [
        run(repository.get_song(song_id))
        for song_id in result.added_song_ids
    ]
    by_path = {song.file_uri: song for song in songs if song is not None}

    sidecar = by_path[str(sidecar_audio)]
    assert sidecar.lyrics == (
        "[00:00.00] LRC line 1\n[00:01.50] LRC line 2\n"
    )
    assert sidecar.lyrics_format == "lrc"
    assert sidecar.lyrics_source == "sidecar"
    assert sidecar.lyrics_status == "available"

    embedded = by_path[str(embedded_audio)]
    assert embedded.lyrics == "Plain embedded lyric line 1\nline 2"
    assert embedded.lyrics_format == "text"
    assert embedded.lyrics_source == "embedded"
    assert embedded.lyrics_status == "available"


def test_task3_to_task2_persists_embedded_artwork_reference(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    from mutagen.flac import FLAC, Picture

    db_path, root = prepare_library(tmp_path)
    target = root / "artwork.flac"
    copy2(media_fixture_dir / "metadata.flac", target)

    image_data = b"task0-4-integration-artwork"
    audio = FLAC(target)
    picture = Picture()
    picture.type = 3
    picture.mime = "image/png"
    picture.width = 2
    picture.height = 2
    picture.depth = 8
    picture.data = image_data
    audio.add_picture(picture)
    audio.save()

    scanner, repository = make_scanner(db_path)
    result = run(scanner.scan_full(root))
    assert len(result.added_song_ids) == 1

    song_id = result.added_song_ids[0]
    song = run(repository.get_song(song_id))
    assert song is not None
    assert song.artwork is not None
    assert song.artwork.source == "EMBEDDED"
    assert song.artwork.picture_index == 0
    assert song.artwork.mime_type == "image/png"
    assert song.artwork.width == 2
    assert song.artwork.height == 2
    assert (
        song.artwork.content_sha256
        == hashlib.sha256(image_data).hexdigest()
    )

    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT artwork_id, song_id, source, picture_index,
                   mime_type, width, height, content_sha256
            FROM album_art_refs
            """
        ).fetchone()
    finally:
        connection.close()

    assert row == (
        song.artwork.artwork_id,
        song_id,
        "EMBEDDED",
        0,
        "image/png",
        2,
        2,
        hashlib.sha256(image_data).hexdigest(),
    )


def test_task3_to_task2_rename_preserves_song_id_playlist_and_favorite(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    db_path, root = prepare_library(tmp_path)
    old_path = root / "old-name.flac"
    new_path = root / "new-name.flac"
    copy2(media_fixture_dir / "metadata.flac", old_path)

    scanner, repository = make_scanner(db_path)
    first = run(scanner.scan_full(root))
    assert len(first.added_song_ids) == 1
    song_id = first.added_song_ids[0]

    playlists = PlaylistRepository(str(db_path))
    playlist = run(playlists.create_playlist("Integration"))
    run(playlists.add_song(playlist.playlist_id, song_id))
    run(playlists.set_favorite(song_id, True))

    old_path.rename(new_path)
    moved = run(scanner.scan_full(root))

    assert moved.moved_song_ids == (song_id,)
    song = run(repository.get_song(song_id))
    assert song is not None
    assert song.song_id == song_id
    assert song.file_uri == str(new_path)
    assert song.availability_status == "AVAILABLE"
    assert run(playlists.list_song_ids(playlist.playlist_id)) == [song_id]
    assert run(playlists.list_favorite_song_ids()) == [song_id]


def test_task3_to_task2_delete_preserves_song_row_as_missing(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    db_path, root = prepare_library(tmp_path)
    target = root / "delete-me.flac"
    copy2(media_fixture_dir / "metadata.flac", target)

    scanner, repository = make_scanner(db_path)
    first = run(scanner.scan_full(root))
    song_id = first.added_song_ids[0]

    target.unlink()
    result = run(scanner.scan_full(root))

    assert result.missing_song_ids == (song_id,)
    song = run(repository.get_song(song_id))
    assert song is not None
    assert song.song_id == song_id
    assert song.file_uri == str(target)
    assert song.availability_status == "MISSING"


def test_task3_to_task2_list_available_songs_returns_only_available(
    tmp_path: Path,
    media_fixture_dir: Path,
) -> None:
    db_path, root = prepare_library(tmp_path)
    available_path = root / "available.flac"
    removed_path = root / "removed.mp3"
    copy2(media_fixture_dir / "metadata.flac", available_path)
    copy2(media_fixture_dir / "sidecar.mp3", removed_path)

    scanner, repository = make_scanner(db_path)
    first = run(scanner.scan_full(root))

    assert len(first.added_song_ids) == 2
    removed_id = next(
        song_id
        for song_id in first.added_song_ids
        if run(repository.get_song(song_id)).file_uri == str(removed_path)
    )
    available_id = next(
        song_id
        for song_id in first.added_song_ids
        if run(repository.get_song(song_id)).file_uri == str(available_path)
    )

    removed_path.unlink()
    result = run(scanner.scan_full(root))

    assert result.missing_song_ids == (removed_id,)
    available = run(repository.list_available_songs())

    assert [song.song_id for song in available] == [available_id]
    assert all(song.availability_status == "AVAILABLE" for song in available)
