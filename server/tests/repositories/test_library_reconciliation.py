from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone

import pytest

from server.app.models.history import HistoryEvent
from server.app.models.library import ArtworkRef, ScanBatch, Song
from server.app.repositories.database import initialize_database, run_transaction
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.repositories.migrations import SCHEMA_VERSION


def run(coro):
    return asyncio.run(coro)


def test_fresh_database_is_schema_v2_with_reconciliation_and_artwork_tables(tmp_path):
    path = tmp_path / "library.db"

    run(initialize_database(str(path)))

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert SCHEMA_VERSION == 2

        song_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(songs)")
        }
        assert {
            "file_size",
            "file_mtime_ns",
            "content_hash",
            "availability_status",
            "last_seen_at",
        }.issubset(song_columns)

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "album_art_refs" in tables

        indexes = {
            row[1]
            for row in connection.execute("PRAGMA index_list(songs)")
        }
        assert "idx_songs_content_hash" in indexes
        assert "idx_songs_availability_status" in indexes
        assert "sqlite_autoindex_songs_2" not in indexes
    finally:
        connection.close()


def test_v1_to_v2_migration_preserves_song_playlist_favorite_history_data(tmp_path):
    path = tmp_path / "library.db"

    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE albums (
                album_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                identity_key TEXT NOT NULL UNIQUE,
                year INTEGER,
                date TEXT
            );
            CREATE TABLE songs (
                song_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                file_uri TEXT NOT NULL UNIQUE,
                identity_key TEXT UNIQUE,
                album_id TEXT,
                track_number INTEGER,
                disc_number INTEGER,
                year INTEGER,
                date TEXT,
                duration REAL,
                lyrics TEXT,
                lyrics_format TEXT,
                bit_depth INTEGER,
                sample_rate_hz INTEGER,
                channel_count INTEGER,
                codec TEXT,
                metadata_status TEXT,
                last_scanned_at TEXT,
                FOREIGN KEY(album_id) REFERENCES albums(album_id)
            );
            CREATE TABLE playlists (
                playlist_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_system INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE playlist_items (
                playlist_id TEXT NOT NULL,
                song_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                PRIMARY KEY(playlist_id, song_id),
                UNIQUE(playlist_id, position),
                FOREIGN KEY(playlist_id) REFERENCES playlists(playlist_id),
                FOREIGN KEY(song_id) REFERENCES songs(song_id)
            );
            CREATE TABLE favorites (
                song_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                FOREIGN KEY(song_id) REFERENCES songs(song_id)
            );
            CREATE TABLE history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                song_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                reason TEXT,
                session_id TEXT,
                FOREIGN KEY(song_id) REFERENCES songs(song_id)
            );
            INSERT INTO songs(
                song_id, title, file_uri, identity_key, metadata_status
            ) VALUES(
                'song-1', 'Legacy', 'music/legacy.flac',
                'identity-1', 'OK'
            );
            INSERT INTO playlists(
                playlist_id, name, created_at, updated_at, is_system
            ) VALUES(
                'playlist-1', 'Legacy Playlist',
                '2026-09-01T00:00:00+00:00',
                '2026-09-01T00:00:00+00:00', 0
            );
            INSERT INTO playlist_items(playlist_id, song_id, position)
            VALUES('playlist-1', 'song-1', 0);
            INSERT INTO favorites(song_id, created_at)
            VALUES('song-1', '2026-09-01T00:00:00+00:00');
            INSERT INTO history(
                song_id, started_at, ended_at, reason, session_id
            ) VALUES(
                'song-1',
                '2026-09-01T00:00:00+00:00',
                '2026-09-01T00:03:00+00:00',
                'natural_complete',
                'session-1'
            );
            PRAGMA user_version = 1;
            """
        )
        connection.commit()
    finally:
        connection.close()

    run(initialize_database(str(path)))

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute(
            "SELECT title, file_uri, identity_key, metadata_status, availability_status "
            "FROM songs WHERE song_id = 'song-1'"
        ).fetchone() == (
            "Legacy",
            "music/legacy.flac",
            "identity-1",
            "OK",
            "AVAILABLE",
        )
        assert connection.execute(
            "SELECT playlist_id, song_id, position FROM playlist_items"
        ).fetchall() == [("playlist-1", "song-1", 0)]
        assert connection.execute(
            "SELECT song_id FROM favorites"
        ).fetchall() == [("song-1",)]
        assert connection.execute(
            "SELECT song_id, reason, session_id FROM history"
        ).fetchall() == [("song-1", "natural_complete", "session-1")]

        connection.execute(
            """
            INSERT INTO songs(
                song_id, title, file_uri, identity_key, availability_status
            ) VALUES(
                'song-2', 'Second', 'music/second.flac',
                'identity-1', 'AVAILABLE'
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


def test_file_signature_fields_and_availability_are_persisted(tmp_path):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))
    repository = LibraryRepository(str(path))

    seen_at = datetime(2026, 9, 27, tzinfo=timezone.utc)
    saved = run(
        repository.upsert_song(
            Song(
                song_id="song-1",
                title="Track",
                file_uri="music/track.flac",
                file_size=1234,
                file_mtime_ns=987654321,
                content_hash="sha256:abc",
                availability_status="MISSING",
                last_seen_at=seen_at,
            )
        )
    )

    assert saved.file_size == 1234
    assert saved.file_mtime_ns == 987654321
    assert saved.content_hash == "sha256:abc"
    assert saved.availability_status == "MISSING"
    assert saved.last_seen_at == seen_at


def test_artwork_reference_is_persisted_once_per_album(tmp_path):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))
    repository = LibraryRepository(str(path))

    artwork = ArtworkRef(
        artwork_id="art-1",
        source="EMBEDDED",
        picture_index=0,
        mime_type="image/jpeg",
        width=1200,
        height=1200,
        content_sha256="art-hash",
    )
    saved = run(
        repository.upsert_song(
            Song(
                song_id="song-1",
                title="Track",
                file_uri="music/track.flac",
                album="Album",
                album_artists=("Artist",),
                artwork=artwork,
            )
        )
    )

    assert saved.artwork == artwork

    second = run(
        repository.upsert_song(
            Song(
                song_id="song-2",
                title="Second",
                file_uri="music/second.flac",
                album="Album",
                album_artists=("Artist",),
            )
        )
    )

    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(
            """
            SELECT artwork_id, song_id, picture_index, mime_type
            FROM album_art_refs
            """
        ).fetchall()
    finally:
        connection.close()

    assert rows == [("art-1", "song-1", 0, "image/jpeg")]
    assert second.artwork == artwork


def test_candidate_lookups_allow_ambiguous_identity_and_non_unique_content_hash(
    tmp_path,
):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))
    repository = LibraryRepository(str(path))

    for song_id, file_uri in (
        ("song-1", "music/one.flac"),
        ("song-2", "music/two.flac"),
    ):
        run(
            repository.upsert_song(
                Song(
                    song_id=song_id,
                    title=song_id,
                    file_uri=file_uri,
                    identity_key="same-identity",
                    content_hash="same-content",
                    availability_status="MISSING",
                )
            )
        )

    identity_candidates = run(
        repository.find_song_candidates_by_identity("same-identity")
    )
    content_candidates = run(
        repository.find_song_candidates_by_content_hash("same-content")
    )

    assert [song.song_id for song in identity_candidates] == ["song-1", "song-2"]
    assert [song.song_id for song in content_candidates] == ["song-1", "song-2"]


def test_apply_scan_batch_performs_atomic_insert_update_move_missing_and_unreadable(
    tmp_path,
):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))
    repository = LibraryRepository(str(path))

    run(
        repository.upsert_song(
            Song(
                song_id="song-1",
                title="Moved",
                file_uri="music/old.flac",
                identity_key="identity-1",
                availability_status="AVAILABLE",
            )
        )
    )
    run(
        repository.upsert_song(
            Song(
                song_id="song-2",
                title="Missing",
                file_uri="music/missing.flac",
                identity_key="identity-2",
                availability_status="AVAILABLE",
            )
        )
    )
    run(
        repository.upsert_song(
            Song(
                song_id="song-3",
                title="Unreadable",
                file_uri="music/bad.flac",
                identity_key="identity-3",
                availability_status="AVAILABLE",
            )
        )
    )

    result = run(
        repository.apply_scan_batch(
            ScanBatch(
                songs=(
                    Song(
                        title="Moved Updated",
                        file_uri="music/new.flac",
                        identity_key="identity-1",
                        content_hash="hash-1",
                    ),
                    Song(
                        title="Added",
                        file_uri="music/added.flac",
                        identity_key="identity-4",
                        content_hash="hash-4",
                    ),
                ),
                unreadable_file_uris=("music/bad.flac",),
                reconciled_root_uri_prefix="music/",
            )
        )
    )

    assert "song-1" in result.updated_song_ids
    assert "song-1" in result.moved_song_ids
    assert result.added_song_ids == ("song-4",)
    assert result.missing_song_ids == ("song-2",)
    assert result.unreadable_song_ids == ("song-3",)

    moved = run(repository.get_song("song-1"))
    missing = run(repository.get_song("song-2"))
    unreadable = run(repository.get_song("song-3"))
    added = run(repository.get_song("song-4"))

    assert moved is not None
    assert moved.title == "Moved Updated"
    assert moved.file_uri == "music/new.flac"
    assert moved.availability_status == "AVAILABLE"
    assert missing is not None and missing.availability_status == "MISSING"
    assert unreadable is not None and unreadable.availability_status == "UNREADABLE"
    assert added is not None and added.availability_status == "AVAILABLE"


def test_apply_scan_batch_rolls_back_all_changes_on_error(tmp_path):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))
    repository = LibraryRepository(str(path))

    run(
        repository.upsert_song(
            Song(
                song_id="song-1",
                title="Existing",
                file_uri="music/existing.flac",
            )
        )
    )

    batch = ScanBatch(
        songs=(
            Song(
                title="Added",
                file_uri="music/added.flac",
            ),
            Song(
                title="Conflicting",
                file_uri="music/existing.flac",
            ),
        ),
        reconciled_root_uri_prefix="music/",
    )

    with pytest.raises(Exception):
        run(repository.apply_scan_batch(batch))

    assert run(repository.get_song("song-1")).title == "Existing"
    assert run(repository.find_song_by_file_uri("music/added.flac")) is None


def test_missing_or_unreadable_song_rows_keep_playlist_favorite_history_references(
    tmp_path,
):
    path = tmp_path / "library.db"
    run(initialize_database(str(path)))
    library = LibraryRepository(str(path))
    playlists = PlaylistRepository(str(path))
    history = HistoryRepository(str(path))

    run(
        library.upsert_song(
            Song(
                song_id="song-1",
                title="Keep References",
                file_uri="music/keep.flac",
            )
        )
    )
    run(
        library.upsert_song(
            Song(
                song_id="song-2",
                title="Unreadable",
                file_uri="music/bad.flac",
            )
        )
    )
    playlist = run(playlists.create_playlist("Keep"))
    run(playlists.add_song(playlist.playlist_id, "song-1"))
    run(playlists.add_song(playlist.playlist_id, "song-2"))
    run(playlists.set_favorite("song-1", True))
    run(playlists.set_favorite("song-2", True))
    run(
        history.record_history(
            HistoryEvent(
                song_id="song-1",
                started_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
                session_id="session-1",
            )
        )
    )

    run(
        library.apply_scan_batch(
            ScanBatch(
                songs=(),
                unreadable_file_uris=("music/bad.flac",),
                reconciled_root_uri_prefix="music/",
            )
        )
    )

    assert run(library.get_song("song-1")).availability_status == "MISSING"
    assert run(library.get_song("song-2")).availability_status == "UNREADABLE"
    assert run(playlists.list_song_ids(playlist.playlist_id)) == ["song-1", "song-2"]
    assert run(playlists.list_favorite_song_ids()) == ["song-2", "song-1"]
    assert len(run(history.list_history())) == 1
