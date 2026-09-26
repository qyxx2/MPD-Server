from __future__ import annotations

import uuid
from datetime import datetime, timezone

from server.app.models.library import Song

from .database import run_transaction


SONGS_SELECT = """
SELECT song_id, title, file_uri, identity_key, album_id, track_number,
       disc_number, year, date, duration, lyrics, lyrics_format, bit_depth,
       sample_rate_hz, channel_count, codec, metadata_status, last_scanned_at
FROM songs
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entity_id(kind: str, name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"mpd-server:{kind}:{name.casefold()}"))


class LibraryRepository:
    def __init__(self, path: str) -> None:
        self.path = path

    async def upsert_song(self, song: Song) -> Song:
        async def operation(connection):
            existing_id = None
            if song.song_id is not None:
                row = connection.execute(
                    "SELECT song_id FROM songs WHERE song_id = ?", (song.song_id,)
                ).fetchone()
                existing_id = row[0] if row else None
            if existing_id is None and song.identity_key is not None:
                row = connection.execute(
                    "SELECT song_id FROM songs WHERE identity_key = ?",
                    (song.identity_key,),
                ).fetchone()
                existing_id = row[0] if row else None
            if existing_id is None:
                row = connection.execute(
                    "SELECT song_id FROM songs WHERE file_uri = ?", (song.file_uri,)
                ).fetchone()
                existing_id = row[0] if row else None

            song_id = existing_id or song.song_id or str(uuid.uuid4())
            if song.song_id is not None and existing_id is not None:
                if existing_id != song.song_id:
                    raise ValueError(
                        "song_id resolves to a different existing song"
                    )

            if song.identity_key is not None:
                conflict = connection.execute(
                    "SELECT song_id FROM songs WHERE identity_key = ?",
                    (song.identity_key,),
                ).fetchone()
                if conflict is not None and conflict[0] != song_id:
                    raise ValueError("identity_key belongs to a different song")

            album_id = None
            if song.album:
                album_artists = sorted(
                    {
                        value.strip().casefold()
                        for value in song.album_artists
                        if value.strip()
                    }
                )
                album_identity = "|".join(
                    [song.album.strip().casefold(), *album_artists]
                )
                row = connection.execute(
                    "SELECT album_id FROM albums WHERE identity_key = ?",
                    (album_identity,),
                ).fetchone()
                album_id = row[0] if row else str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO albums(album_id, title, identity_key, year, date)
                    VALUES(?, ?, ?, ?, ?)
                    ON CONFLICT(identity_key) DO UPDATE SET
                        title = excluded.title,
                        year = excluded.year,
                        date = excluded.date
                    """,
                    (
                        album_id,
                        song.album,
                        album_identity,
                        song.year,
                        song.date,
                    ),
                )
                album_id = connection.execute(
                    "SELECT album_id FROM albums WHERE identity_key = ?",
                    (album_identity,),
                ).fetchone()[0]

            scanned = (
                song.last_scanned_at.isoformat()
                if song.last_scanned_at
                else _now()
            )
            connection.execute(
                """
                INSERT INTO songs(
                    song_id, title, file_uri, identity_key, album_id,
                    track_number, disc_number, year, date, duration, lyrics,
                    lyrics_format, bit_depth, sample_rate_hz, channel_count,
                    codec, metadata_status, last_scanned_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(song_id) DO UPDATE SET
                    title = excluded.title,
                    file_uri = excluded.file_uri,
                    identity_key = excluded.identity_key,
                    album_id = excluded.album_id,
                    track_number = excluded.track_number,
                    disc_number = excluded.disc_number,
                    year = excluded.year,
                    date = excluded.date,
                    duration = excluded.duration,
                    lyrics = excluded.lyrics,
                    lyrics_format = excluded.lyrics_format,
                    bit_depth = excluded.bit_depth,
                    sample_rate_hz = excluded.sample_rate_hz,
                    channel_count = excluded.channel_count,
                    codec = excluded.codec,
                    metadata_status = excluded.metadata_status,
                    last_scanned_at = excluded.last_scanned_at
                """,
                (
                    song_id,
                    song.title,
                    song.file_uri,
                    song.identity_key,
                    album_id,
                    song.track_number,
                    song.disc_number,
                    song.year,
                    song.date,
                    song.duration,
                    song.lyrics,
                    song.lyrics_format,
                    song.bit_depth,
                    song.sample_rate_hz,
                    song.channel_count,
                    song.codec,
                    song.metadata_status,
                    scanned,
                ),
            )

            relations = (
                ("artists", "artist_id", "song_artists", song.artists),
                ("artists", "artist_id", "song_album_artists", song.album_artists),
                ("genres", "genre_id", "song_genres", song.genres),
                ("tags", "tag_id", "song_tags", song.tag_names),
            )
            for table, key, join_table, names in relations:
                connection.execute(
                    f"DELETE FROM {join_table} WHERE song_id = ?", (song_id,)
                )
                for name in names:
                    value = name.strip()
                    if not value:
                        continue
                    entity_id = _entity_id(table, value)
                    connection.execute(
                        f"INSERT OR IGNORE INTO {table}({key}, name) VALUES(?, ?)",
                        (entity_id, value),
                    )
                    connection.execute(
                        f"INSERT INTO {join_table}(song_id, {key}) VALUES(?, ?)",
                        (song_id, entity_id),
                    )
            return song_id

        song_id = await run_transaction(self.path, operation)
        return await self.get_song(song_id)  # type: ignore[return-value]

    async def get_song(self, song_id: str) -> Song | None:
        async def operation(connection):
            row = connection.execute(
                f"{SONGS_SELECT} WHERE song_id = ?", (song_id,)
            ).fetchone()
            if row is None:
                return None
            artists = tuple(
                item[0]
                for item in connection.execute(
                    """
                    SELECT a.name
                    FROM artists AS a
                    JOIN song_artists AS sa ON sa.artist_id = a.artist_id
                    WHERE sa.song_id = ?
                    ORDER BY a.name
                    """,
                    (song_id,),
                )
            )
            album_artists = tuple(
                item[0]
                for item in connection.execute(
                    """
                    SELECT a.name
                    FROM artists AS a
                    JOIN song_album_artists AS sa ON sa.artist_id = a.artist_id
                    WHERE sa.song_id = ?
                    ORDER BY a.name
                    """,
                    (song_id,),
                )
            )
            genres = tuple(
                item[0]
                for item in connection.execute(
                    """
                    SELECT g.name
                    FROM genres AS g
                    JOIN song_genres AS sg ON sg.genre_id = g.genre_id
                    WHERE sg.song_id = ?
                    ORDER BY g.name
                    """,
                    (song_id,),
                )
            )
            tags = tuple(
                item[0]
                for item in connection.execute(
                    """
                    SELECT t.name
                    FROM tags AS t
                    JOIN song_tags AS st ON st.tag_id = t.tag_id
                    WHERE st.song_id = ?
                    ORDER BY t.name
                    """,
                    (song_id,),
                )
            )
            album = connection.execute(
                "SELECT title FROM albums WHERE album_id = ?", (row[4],)
            ).fetchone()
            return Song(
                song_id=row[0],
                title=row[1],
                file_uri=row[2],
                identity_key=row[3],
                album=album[0] if album else None,
                artists=artists,
                album_artists=album_artists,
                genres=genres,
                tag_names=tags,
                track_number=row[5],
                disc_number=row[6],
                year=row[7],
                date=row[8],
                duration=row[9],
                lyrics=row[10],
                lyrics_format=row[11],
                bit_depth=row[12],
                sample_rate_hz=row[13],
                channel_count=row[14],
                codec=row[15],
                metadata_status=row[16],
                last_scanned_at=(
                    datetime.fromisoformat(row[17]) if row[17] else None
                ),
            )

        return await run_transaction(self.path, operation)

    async def find_song_by_file_uri(self, file_uri: str) -> Song | None:
        async def operation(connection):
            row = connection.execute(
                "SELECT song_id FROM songs WHERE file_uri = ?", (file_uri,)
            ).fetchone()
            return row[0] if row else None

        song_id = await run_transaction(self.path, operation)
        return await self.get_song(song_id) if song_id else None
