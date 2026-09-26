from __future__ import annotations

import asyncio
import sqlite3

import pytest

from server.app.models.library import Song
from server.app.repositories.database import (
    SCHEMA_VERSION,
    check_integrity,
    initialize_database,
    run_transaction,
)
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playlist_repository import (
    DuplicatePlaylistSongError,
    PlaylistRepository,
)


def run(coro):
    return asyncio.run(coro)


def test_fresh_database_has_version_integrity_and_enforced_foreign_keys(tmp_path):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    finally:
        connection.close()

    assert run(check_integrity(str(path))) is True

    async def insert_orphan(connection):
        connection.execute(
            "INSERT INTO song_artists(song_id, artist_id) VALUES('missing', 'missing')"
        )

    with pytest.raises(sqlite3.IntegrityError):
        run(run_transaction(str(path), insert_orphan))


def test_transaction_commits_and_rolls_back_as_one_boundary(tmp_path):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))

    async def insert_artist(connection):
        connection.execute(
            "INSERT INTO artists(artist_id, name) VALUES('artist-1', 'Artist')"
        )

    run(run_transaction(str(path), insert_artist))

    async def fail_after_insert(connection):
        connection.execute(
            "INSERT INTO artists(artist_id, name) VALUES('artist-2', 'Rollback')"
        )
        raise RuntimeError("force rollback")

    with pytest.raises(RuntimeError):
        run(run_transaction(str(path), fail_after_insert))

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT name FROM artists").fetchall() == [
            ("Artist",)
        ]
    finally:
        connection.close()


def test_schema_contains_required_tables_and_indexes(tmp_path):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))

    connection = sqlite3.connect(path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    finally:
        connection.close()

    assert {
        "songs",
        "albums",
        "artists",
        "genres",
        "tags",
        "song_artists",
        "song_album_artists",
        "song_genres",
        "song_tags",
        "playlists",
        "playlist_items",
        "favorites",
        "history",
        "queue_items",
        "playback_state",
    }.issubset(tables)
    assert {
        "idx_songs_file_uri",
        "idx_songs_identity_key",
        "idx_playlist_items_song_id",
    }.issubset(indexes)


def test_song_id_is_reused_when_file_moves_and_metadata_updates(tmp_path):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))
    repository = LibraryRepository(str(path))

    original = Song(
        song_id="song-1",
        title="Original Title",
        file_uri="music/old-name.flac",
        identity_key="fingerprint-1",
        artists=("Artist A", "Artist B"),
        genres=("Rock",),
        bit_depth=24,
        sample_rate_hz=96000,
    )
    saved = run(repository.upsert_song(original))

    moved = Song(
        title="Updated Title",
        file_uri="music/new-name.flac",
        identity_key="fingerprint-1",
        artists=("Artist A", "Artist C"),
        genres=("Rock", "Hi-Res"),
        bit_depth=24,
        sample_rate_hz=96000,
    )
    updated = run(repository.upsert_song(moved))

    assert saved.song_id == "song-1"
    assert updated.song_id == "song-1"
    assert updated.title == "Updated Title"
    assert updated.file_uri == "music/new-name.flac"
    assert updated.artists == ("Artist A", "Artist C")
    assert set(updated.genres) == {"Rock", "Hi-Res"}

    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT song_id, title, file_uri FROM songs"
        ).fetchall() == [
            ("song-1", "Updated Title", "music/new-name.flac")
        ]
        artist_rows = connection.execute(
            """
            SELECT a.name
            FROM artists AS a
            JOIN song_artists AS sa ON sa.artist_id = a.artist_id
            WHERE sa.song_id = ?
            ORDER BY a.name
            """,
            ("song-1",),
        ).fetchall()
    finally:
        connection.close()

    assert [row[0] for row in artist_rows] == ["Artist A", "Artist C"]


def test_duplicate_playlist_song_is_rejected_without_order_change(tmp_path):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))
    library = LibraryRepository(str(path))
    playlists = PlaylistRepository(str(path))

    run(
        library.upsert_song(
            Song(song_id="song-1", title="One", file_uri="music/one.flac")
        )
    )
    run(
        library.upsert_song(
            Song(song_id="song-2", title="Two", file_uri="music/two.flac")
        )
    )

    playlist = run(playlists.create_playlist("My Playlist"))
    run(playlists.add_song(playlist.playlist_id, "song-1"))
    run(playlists.add_song(playlist.playlist_id, "song-2"))
    before = run(playlists.list_song_ids(playlist.playlist_id))

    with pytest.raises(DuplicatePlaylistSongError):
        run(playlists.add_song(playlist.playlist_id, "song-1", position=0))

    after = run(playlists.list_song_ids(playlist.playlist_id))
    assert after == before == ["song-1", "song-2"]
