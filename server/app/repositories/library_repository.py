from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from server.app.models.library import ArtworkRef, ScanBatch, ScanResult, Song

from .database import run_transaction

SONGS_SELECT = """
SELECT song_id, title, file_uri, identity_key, album_id, track_number,
       disc_number, year, date, duration, lyrics, lyrics_format, lyrics_source,
       lyrics_status, bit_depth,
       sample_rate_hz, channel_count, codec, metadata_status, last_scanned_at,
       file_size, file_mtime_ns, content_hash, availability_status, last_seen_at
FROM songs
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entity_id(kind: str, name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"mpd-server:{kind}:{name.casefold()}"))


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class LibraryRepository:
    def __init__(self, path: str) -> None:
        self.path = path

    def _song_from_row(self, connection, row: tuple[Any, ...]) -> Song:
        artwork_row = (
            connection.execute(
                """
                SELECT artwork_id, source, picture_index, mime_type,
                       width, height, content_sha256
                FROM album_art_refs
                WHERE album_id = ?
                """,
                (row[4],),
            ).fetchone()
            if row[4] is not None
            else None
        )
        artwork = (
            ArtworkRef(
                artwork_id=artwork_row[0],
                source=artwork_row[1],
                picture_index=artwork_row[2],
                mime_type=artwork_row[3],
                width=artwork_row[4],
                height=artwork_row[5],
                content_sha256=artwork_row[6],
            )
            if artwork_row
            else None
        )

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
                (row[0],),
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
                (row[0],),
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
                (row[0],),
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
                (row[0],),
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
            lyrics_source=row[12],
            lyrics_status=row[13],
            bit_depth=row[14],
            sample_rate_hz=row[15],
            channel_count=row[16],
            codec=row[17],
            metadata_status=row[18],
            last_scanned_at=_parse_dt(row[19]),
            file_size=row[20],
            file_mtime_ns=row[21],
            content_hash=row[22],
            availability_status=row[23],
            last_seen_at=_parse_dt(row[24]),
            artwork=artwork,
        )

    def _upsert_song(
        self,
        connection,
        song: Song,
        song_id: str,
        scanned_at: str,
    ) -> None:
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
                (album_id, song.album, album_identity, song.year, song.date),
            )
            album_id = connection.execute(
                "SELECT album_id FROM albums WHERE identity_key = ?",
                (album_identity,),
            ).fetchone()[0]

        seen_at = (
            song.last_seen_at or datetime.fromisoformat(scanned_at)
        ).isoformat()
        connection.execute(
            """
            INSERT INTO songs(
                song_id, title, file_uri, identity_key, album_id,
                track_number, disc_number, year, date, duration, lyrics,
                lyrics_format, lyrics_source, lyrics_status, bit_depth,
                sample_rate_hz, channel_count,
                codec, metadata_status, last_scanned_at, file_size,
                file_mtime_ns, content_hash, availability_status, last_seen_at
            ) VALUES(
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
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
                lyrics_source = excluded.lyrics_source,
                lyrics_status = excluded.lyrics_status,
                bit_depth = excluded.bit_depth,
                sample_rate_hz = excluded.sample_rate_hz,
                channel_count = excluded.channel_count,
                codec = excluded.codec,
                metadata_status = excluded.metadata_status,
                last_scanned_at = excluded.last_scanned_at,
                file_size = excluded.file_size,
                file_mtime_ns = excluded.file_mtime_ns,
                content_hash = excluded.content_hash,
                availability_status = excluded.availability_status,
                last_seen_at = excluded.last_seen_at
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
                song.lyrics_source,
                song.lyrics_status,
                song.bit_depth,
                song.sample_rate_hz,
                song.channel_count,
                song.codec,
                song.metadata_status,
                (
                    song.last_scanned_at.isoformat()
                    if song.last_scanned_at
                    else scanned_at
                ),
                song.file_size,
                song.file_mtime_ns,
                song.content_hash,
                song.availability_status,
                seen_at,
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
                f"DELETE FROM {join_table} WHERE song_id = ?",
                (song_id,),
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

        if song.artwork is not None and album_id is not None:
            connection.execute(
                """
                INSERT INTO album_art_refs(
                    artwork_id, album_id, song_id, source, picture_index,
                    mime_type, width, height, content_sha256
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(album_id) DO UPDATE SET
                    artwork_id = excluded.artwork_id,
                    song_id = excluded.song_id,
                    source = excluded.source,
                    picture_index = excluded.picture_index,
                    mime_type = excluded.mime_type,
                    width = excluded.width,
                    height = excluded.height,
                    content_sha256 = excluded.content_sha256
                """,
                (
                    song.artwork.artwork_id,
                    album_id,
                    song_id,
                    song.artwork.source,
                    song.artwork.picture_index,
                    song.artwork.mime_type,
                    song.artwork.width,
                    song.artwork.height,
                    song.artwork.content_sha256,
                ),
            )

    async def upsert_song(self, song: Song) -> Song:
        async def operation(connection):
            existing_id = None
            if song.song_id is not None:
                row = connection.execute(
                    "SELECT song_id FROM songs WHERE song_id = ?",
                    (song.song_id,),
                ).fetchone()
                existing_id = row[0] if row else None
            if existing_id is None:
                row = connection.execute(
                    "SELECT song_id FROM songs WHERE file_uri = ?",
                    (song.file_uri,),
                ).fetchone()
                existing_id = row[0] if row else None
            if (
                existing_id is None
                and song.song_id is None
                and song.identity_key is not None
            ):
                candidates = connection.execute(
                    """
                    SELECT song_id
                    FROM songs
                    WHERE identity_key = ?
                    ORDER BY song_id
                    """,
                    (song.identity_key,),
                ).fetchall()
                if len(candidates) == 1:
                    existing_id = candidates[0][0]

            song_id = existing_id or song.song_id or str(uuid.uuid4())
            if (
                song.song_id is not None
                and existing_id is not None
                and existing_id != song.song_id
            ):
                raise ValueError(
                    "song_id resolves to a different existing song"
                )
            self._upsert_song(connection, song, song_id, _now())
            return song_id

        song_id = await run_transaction(self.path, operation)
        return await self.get_song(song_id)  # type: ignore[return-value]

    async def get_song(self, song_id: str) -> Song | None:
        async def operation(connection):
            row = connection.execute(
                f"{SONGS_SELECT} WHERE song_id = ?", (song_id,)
            ).fetchone()
            return self._song_from_row(connection, row) if row else None

        return await run_transaction(self.path, operation)

    async def find_song_by_file_uri(self, file_uri: str) -> Song | None:
        async def operation(connection):
            row = connection.execute(
                f"{SONGS_SELECT} WHERE file_uri = ?", (file_uri,)
            ).fetchone()
            return self._song_from_row(connection, row) if row else None

        return await run_transaction(self.path, operation)

    async def list_songs_in_root(self, root_uri_prefix: str) -> list[Song]:
        async def operation(connection):
            rows = connection.execute(
                f"{SONGS_SELECT} ORDER BY file_uri"
            ).fetchall()
            return [
                self._song_from_row(connection, row)
                for row in rows
                if row[2].startswith(root_uri_prefix)
            ]

        return await run_transaction(self.path, operation)

    async def list_available_songs(self) -> list[Song]:
        async def operation(connection):
            rows = connection.execute(
                f"{SONGS_SELECT} WHERE availability_status = 'AVAILABLE' "
                "ORDER BY file_uri"
            ).fetchall()
            return [self._song_from_row(connection, row) for row in rows]

        return await run_transaction(self.path, operation)

    async def find_song_candidates_by_identity(
        self, identity_key: str
    ) -> list[Song]:
        async def operation(connection):
            rows = connection.execute(
                f"{SONGS_SELECT} WHERE identity_key = ? ORDER BY song_id",
                (identity_key,),
            ).fetchall()
            return [self._song_from_row(connection, row) for row in rows]

        return await run_transaction(self.path, operation)

    async def find_song_candidates_by_content_hash(
        self, content_hash: str
    ) -> list[Song]:
        async def operation(connection):
            rows = connection.execute(
                f"{SONGS_SELECT} WHERE content_hash = ? ORDER BY song_id",
                (content_hash,),
            ).fetchall()
            return [self._song_from_row(connection, row) for row in rows]

        return await run_transaction(self.path, operation)

    async def apply_scan_batch(self, batch: ScanBatch) -> ScanResult:
        async def operation(connection):
            now = _now()
            added: list[str] = []
            updated: list[str] = []
            moved: list[str] = []
            missing: list[str] = []
            unreadable: list[str] = []
            reserved_ids: set[str] = set()

            for song in batch.songs:
                exact = connection.execute(
                    "SELECT song_id, file_uri FROM songs WHERE file_uri = ?",
                    (song.file_uri,),
                ).fetchone()
                if exact is not None:
                    if song.song_id is not None and exact[0] != song.song_id:
                        raise ValueError(
                            "file_uri belongs to a different song_id"
                        )
                    song_id = exact[0]
                    old_uri = exact[1]
                elif song.song_id is not None:
                    explicit = connection.execute(
                        """
                        SELECT song_id, file_uri
                        FROM songs
                        WHERE song_id = ?
                        """,
                        (song.song_id,),
                    ).fetchone()
                    if explicit is not None:
                        song_id, old_uri = explicit
                    else:
                        song_id, old_uri = song.song_id, None
                else:
                    song_id = None
                    old_uri = None
                    if song.identity_key is not None:
                        candidates = connection.execute(
                            """
                            SELECT song_id, file_uri, availability_status
                            FROM songs
                            WHERE identity_key = ?
                            ORDER BY song_id
                            """,
                            (song.identity_key,),
                        ).fetchall()
                        candidates = [
                            row
                            for row in candidates
                            if row[0] not in reserved_ids
                        ]
                        if len(candidates) == 1:
                            song_id, old_uri = candidates[0][0], candidates[0][1]

                    if song_id is None and song.content_hash is not None:
                        candidates = connection.execute(
                            """
                            SELECT song_id, file_uri
                            FROM songs
                            WHERE content_hash = ?
                              AND availability_status = 'MISSING'
                            ORDER BY song_id
                            """,
                            (song.content_hash,),
                        ).fetchall()
                        candidates = [
                            row
                            for row in candidates
                            if row[0] not in reserved_ids
                        ]
                        if len(candidates) == 1:
                            song_id, old_uri = candidates[0]

                    if song_id is None:
                        song_id = str(uuid.uuid4())

                is_existing = (
                    connection.execute(
                        "SELECT 1 FROM songs WHERE song_id = ?",
                        (song_id,),
                    ).fetchone()
                    is not None
                )
                if is_existing:
                    updated.append(song_id)
                    if old_uri != song.file_uri:
                        moved.append(song_id)
                else:
                    added.append(song_id)

                if song_id in reserved_ids:
                    raise ValueError("duplicate song match in scan batch")
                reserved_ids.add(song_id)
                observed = song.model_copy(
                    update={
                        "song_id": song_id,
                        "availability_status": "AVAILABLE",
                        "last_scanned_at": (
                            song.last_scanned_at
                            or datetime.fromisoformat(now)
                        ),
                        "last_seen_at": (
                            song.last_seen_at
                            or datetime.fromisoformat(now)
                        ),
                    }
                )
                self._upsert_song(connection, observed, song_id, now)

            if batch.reconciled_root_uri_prefix is not None:
                observed_uris = {song.file_uri for song in batch.songs}
                unreadable_uris = set(batch.unreadable_file_uris)
                rows = connection.execute(
                    """
                    SELECT song_id, file_uri, availability_status
                    FROM songs
                    ORDER BY file_uri
                    """
                ).fetchall()
                for row in rows:
                    if not row[1].startswith(
                        batch.reconciled_root_uri_prefix
                    ):
                        continue
                    if row[1] in observed_uris or row[1] in unreadable_uris:
                        continue
                    if row[2] == "UNREADABLE":
                        continue
                    connection.execute(
                        """
                        UPDATE songs
                        SET availability_status = 'MISSING',
                            last_seen_at = ?
                        WHERE song_id = ?
                        """,
                        (now, row[0]),
                    )
                    missing.append(row[0])

            for uri in batch.unreadable_file_uris:
                row = connection.execute(
                    "SELECT song_id FROM songs WHERE file_uri = ?",
                    (uri,),
                ).fetchone()
                if row is not None:
                    connection.execute(
                        """
                        UPDATE songs
                        SET availability_status = 'UNREADABLE',
                            last_seen_at = ?
                        WHERE song_id = ?
                        """,
                        (now, row[0]),
                    )
                    unreadable.append(row[0])

            return ScanResult(
                added_song_ids=tuple(added),
                updated_song_ids=tuple(updated),
                moved_song_ids=tuple(moved),
                missing_song_ids=tuple(missing),
                unreadable_song_ids=tuple(unreadable),
            )

        return await run_transaction(self.path, operation)
