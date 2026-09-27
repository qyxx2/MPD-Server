from __future__ import annotations

import sqlite3


SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS albums (
    album_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    identity_key TEXT NOT NULL UNIQUE,
    year INTEGER,
    date TEXT
);
CREATE TABLE IF NOT EXISTS songs (
    song_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    file_uri TEXT NOT NULL UNIQUE,
    identity_key TEXT,
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
    file_size INTEGER,
    file_mtime_ns INTEGER,
    content_hash TEXT,
    availability_status TEXT NOT NULL DEFAULT 'AVAILABLE'
        CHECK(availability_status IN ('AVAILABLE', 'MISSING', 'UNREADABLE')),
    last_seen_at TEXT,
    FOREIGN KEY(album_id) REFERENCES albums(album_id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS artists (
    artist_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS genres (
    genre_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS tags (
    tag_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS song_artists (
    song_id TEXT NOT NULL,
    artist_id TEXT NOT NULL,
    PRIMARY KEY(song_id, artist_id),
    FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE CASCADE,
    FOREIGN KEY(artist_id) REFERENCES artists(artist_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS song_album_artists (
    song_id TEXT NOT NULL,
    artist_id TEXT NOT NULL,
    PRIMARY KEY(song_id, artist_id),
    FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE CASCADE,
    FOREIGN KEY(artist_id) REFERENCES artists(artist_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS song_genres (
    song_id TEXT NOT NULL,
    genre_id TEXT NOT NULL,
    PRIMARY KEY(song_id, genre_id),
    FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE CASCADE,
    FOREIGN KEY(genre_id) REFERENCES genres(genre_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS song_tags (
    song_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    PRIMARY KEY(song_id, tag_id),
    FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE CASCADE,
    FOREIGN KEY(tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS playlists (
    playlist_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_system INTEGER NOT NULL DEFAULT 0 CHECK(is_system IN (0, 1))
);
CREATE TABLE IF NOT EXISTS playlist_items (
    playlist_id TEXT NOT NULL,
    song_id TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position >= 0),
    PRIMARY KEY(playlist_id, song_id),
    UNIQUE(playlist_id, position),
    FOREIGN KEY(playlist_id) REFERENCES playlists(playlist_id) ON DELETE CASCADE,
    FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS favorites (
    song_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    reason TEXT,
    session_id TEXT,
    FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS queue_items (
    queue_item_id TEXT PRIMARY KEY,
    song_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    source TEXT NOT NULL,
    playback_context_id TEXT,
    FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS playback_state (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    song_id TEXT,
    state TEXT NOT NULL,
    playback_context_id TEXT,
    position_seconds REAL,
    autoplay_enabled INTEGER NOT NULL DEFAULT 0 CHECK(autoplay_enabled IN (0, 1)),
    updated_at TEXT NOT NULL,
    FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS album_art_refs (
    artwork_id TEXT PRIMARY KEY,
    album_id TEXT NOT NULL UNIQUE,
    song_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK(source = 'EMBEDDED'),
    picture_index INTEGER NOT NULL CHECK(picture_index >= 0),
    mime_type TEXT,
    width INTEGER,
    height INTEGER,
    content_sha256 TEXT,
    FOREIGN KEY(album_id) REFERENCES albums(album_id) ON DELETE CASCADE,
    FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_songs_file_uri ON songs(file_uri);
CREATE INDEX IF NOT EXISTS idx_songs_identity_key ON songs(identity_key);
CREATE INDEX IF NOT EXISTS idx_songs_content_hash ON songs(content_hash);
CREATE INDEX IF NOT EXISTS idx_songs_availability_status ON songs(availability_status);
CREATE INDEX IF NOT EXISTS idx_song_artists_artist_id ON song_artists(artist_id);
CREATE INDEX IF NOT EXISTS idx_song_album_artists_artist_id ON song_album_artists(artist_id);
CREATE INDEX IF NOT EXISTS idx_song_genres_genre_id ON song_genres(genre_id);
CREATE INDEX IF NOT EXISTS idx_song_tags_tag_id ON song_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_playlist_items_song_id ON playlist_items(song_id);
CREATE INDEX IF NOT EXISTS idx_playlist_items_playlist_position ON playlist_items(playlist_id, position);
CREATE INDEX IF NOT EXISTS idx_history_song_started_at ON history(song_id, started_at);
"""


def _migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN")
        connection.execute("DROP INDEX IF EXISTS idx_songs_file_uri")
        connection.execute("DROP INDEX IF EXISTS idx_songs_identity_key")
        connection.execute(
            """
            CREATE TABLE songs_v2 (
                song_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                file_uri TEXT NOT NULL UNIQUE,
                identity_key TEXT,
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
                file_size INTEGER,
                file_mtime_ns INTEGER,
                content_hash TEXT,
                availability_status TEXT NOT NULL DEFAULT 'AVAILABLE'
                    CHECK(availability_status IN ('AVAILABLE', 'MISSING', 'UNREADABLE')),
                last_seen_at TEXT,
                FOREIGN KEY(album_id) REFERENCES albums(album_id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO songs_v2(
                song_id, title, file_uri, identity_key, album_id,
                track_number, disc_number, year, date, duration, lyrics,
                lyrics_format, bit_depth, sample_rate_hz, channel_count,
                codec, metadata_status, last_scanned_at,
                availability_status, last_seen_at
            )
            SELECT
                song_id, title, file_uri, identity_key, album_id,
                track_number, disc_number, year, date, duration, lyrics,
                lyrics_format, bit_depth, sample_rate_hz, channel_count,
                codec, metadata_status, last_scanned_at,
                'AVAILABLE', last_scanned_at
            FROM songs
            """
        )
        connection.execute("DROP TABLE songs")
        connection.execute("ALTER TABLE songs_v2 RENAME TO songs")

        statements = [
            "CREATE INDEX IF NOT EXISTS idx_songs_file_uri ON songs(file_uri)",
            "CREATE INDEX IF NOT EXISTS idx_songs_identity_key ON songs(identity_key)",
            "CREATE INDEX IF NOT EXISTS idx_songs_content_hash ON songs(content_hash)",
            "CREATE INDEX IF NOT EXISTS idx_songs_availability_status ON songs(availability_status)",
            """
            CREATE TABLE IF NOT EXISTS album_art_refs (
                artwork_id TEXT PRIMARY KEY,
                album_id TEXT NOT NULL UNIQUE,
                song_id TEXT NOT NULL,
                source TEXT NOT NULL CHECK(source = 'EMBEDDED'),
                picture_index INTEGER NOT NULL CHECK(picture_index >= 0),
                mime_type TEXT,
                width INTEGER,
                height INTEGER,
                content_sha256 TEXT,
                FOREIGN KEY(album_id) REFERENCES albums(album_id) ON DELETE CASCADE,
                FOREIGN KEY(song_id) REFERENCES songs(song_id) ON DELETE RESTRICT
            )
            """,
        ]
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        optional_indexes = {
            "song_artists": (
                "CREATE INDEX IF NOT EXISTS idx_song_artists_artist_id "
                "ON song_artists(artist_id)"
            ),
            "song_album_artists": (
                "CREATE INDEX IF NOT EXISTS idx_song_album_artists_artist_id "
                "ON song_album_artists(artist_id)"
            ),
            "song_genres": (
                "CREATE INDEX IF NOT EXISTS idx_song_genres_genre_id "
                "ON song_genres(genre_id)"
            ),
            "song_tags": (
                "CREATE INDEX IF NOT EXISTS idx_song_tags_tag_id "
                "ON song_tags(tag_id)"
            ),
            "playlist_items": (
                "CREATE INDEX IF NOT EXISTS idx_playlist_items_song_id "
                "ON playlist_items(song_id)"
            ),
            "history": (
                "CREATE INDEX IF NOT EXISTS idx_history_song_started_at "
                "ON history(song_id, started_at)"
            ),
        }
        if "playlist_items" in existing_tables:
            statements.append(
                "CREATE INDEX IF NOT EXISTS idx_playlist_items_playlist_position "
                "ON playlist_items(playlist_id, position)"
            )
        for table, statement in optional_indexes.items():
            if table in existing_tables:
                statements.append(statement)
        for statement in statements:
            connection.execute(statement)

        connection.execute("PRAGMA user_version = 2")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def apply_migrations(connection: sqlite3.Connection) -> None:
    current = connection.execute("PRAGMA user_version").fetchone()[0]
    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"database schema {current} is newer than supported {SCHEMA_VERSION}"
        )
    if current == 0:
        connection.executescript(
            f"BEGIN;\n{SCHEMA_SQL}\nPRAGMA user_version = {SCHEMA_VERSION};\nCOMMIT;"
        )
        return
    if current == 1:
        _migrate_v1_to_v2(connection)
