from __future__ import annotations

import uuid
from datetime import datetime, timezone

from server.app.models.playlist import Playlist

from .database import run_transaction


class DuplicatePlaylistSongError(ValueError):
    """Raised when a song already exists in the target playlist."""


class PlaylistReorderMemberMismatchError(ValueError):
    """Raised when a reorder does not contain the current playlist members."""


class PlaylistNotFoundError(ValueError):
    """Raised when a requested Playlist does not exist."""


class SongNotFoundError(ValueError):
    """Raised when a playlist or favorite mutation references a missing Song."""


class SystemPlaylistModificationError(ValueError):
    """Raised when a protected system Playlist is renamed or deleted."""


class PlaylistRepository:
    def __init__(self, path: str) -> None:
        self.path = path

    @staticmethod
    def _playlist_from_row(row: tuple[object, ...]) -> Playlist:
        return Playlist(
            playlist_id=str(row[0]),
            name=str(row[1]),
            created_at=datetime.fromisoformat(str(row[2])),
            updated_at=datetime.fromisoformat(str(row[3])),
            is_system=bool(row[4]),
        )

    @staticmethod
    def _require_playlist(connection, playlist_id: str) -> Playlist:
        row = connection.execute(
            """
            SELECT playlist_id, name, created_at, updated_at, is_system
            FROM playlists
            WHERE playlist_id = ?
            """,
            (playlist_id,),
        ).fetchone()
        if row is None:
            raise PlaylistNotFoundError(playlist_id)
        return PlaylistRepository._playlist_from_row(row)

    @staticmethod
    def _require_song(connection, song_id: str) -> None:
        row = connection.execute(
            "SELECT 1 FROM songs WHERE song_id = ?", (song_id,)
        ).fetchone()
        if row is None:
            raise SongNotFoundError(song_id)

    async def create_playlist(self, name: str) -> Playlist:
        async def operation(connection):
            now = datetime.now(timezone.utc)
            playlist_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO playlists(
                    playlist_id, name, created_at, updated_at, is_system
                ) VALUES(?, ?, ?, ?, 0)
                """,
                (playlist_id, name, now.isoformat(), now.isoformat()),
            )
            return Playlist(
                playlist_id=playlist_id,
                name=name,
                created_at=now,
                updated_at=now,
            )

        return await run_transaction(self.path, operation)

    async def list_playlists(self) -> list[Playlist]:
        async def operation(connection):
            rows = connection.execute(
                """
                SELECT playlist_id, name, created_at, updated_at, is_system
                FROM playlists
                ORDER BY created_at ASC, playlist_id ASC
                """
            ).fetchall()
            return [self._playlist_from_row(row) for row in rows]

        return await run_transaction(self.path, operation)

    async def get_playlist(self, playlist_id: str) -> Playlist | None:
        async def operation(connection):
            row = connection.execute(
                """
                SELECT playlist_id, name, created_at, updated_at, is_system
                FROM playlists
                WHERE playlist_id = ?
                """,
                (playlist_id,),
            ).fetchone()
            return self._playlist_from_row(row) if row is not None else None

        return await run_transaction(self.path, operation)

    async def update_playlist(self, playlist_id: str, name: str) -> Playlist:
        async def operation(connection):
            playlist = self._require_playlist(connection, playlist_id)
            if playlist.is_system:
                raise SystemPlaylistModificationError(playlist_id)

            now = datetime.now(timezone.utc)
            connection.execute(
                """
                UPDATE playlists
                SET name = ?, updated_at = ?
                WHERE playlist_id = ?
                """,
                (name, now.isoformat(), playlist_id),
            )
            return Playlist(
                playlist_id=playlist.playlist_id,
                name=name,
                created_at=playlist.created_at,
                updated_at=now,
                is_system=playlist.is_system,
            )

        return await run_transaction(self.path, operation)

    async def delete_playlist(self, playlist_id: str) -> None:
        async def operation(connection):
            playlist = self._require_playlist(connection, playlist_id)
            if playlist.is_system:
                raise SystemPlaylistModificationError(playlist_id)

            connection.execute(
                "DELETE FROM playlists WHERE playlist_id = ?",
                (playlist_id,),
            )

        await run_transaction(self.path, operation)

    async def add_song(
        self, playlist_id: str, song_id: str, position: int | None = None
    ) -> None:
        async def operation(connection):
            self._require_playlist(connection, playlist_id)
            self._require_song(connection, song_id)
            duplicate = connection.execute(
                """
                SELECT 1
                FROM playlist_items
                WHERE playlist_id = ? AND song_id = ?
                """,
                (playlist_id, song_id),
            ).fetchone()
            if duplicate is not None:
                raise DuplicatePlaylistSongError(song_id)

            count = connection.execute(
                "SELECT COUNT(*) FROM playlist_items WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()[0]
            target = count if position is None else max(0, min(position, count))
            offset = count + 1
            connection.execute(
                """
                UPDATE playlist_items
                SET position = position + ?
                WHERE playlist_id = ? AND position >= ?
                """,
                (offset, playlist_id, target),
            )
            connection.execute(
                """
                UPDATE playlist_items
                SET position = position - ?
                WHERE playlist_id = ? AND position >= ?
                """,
                (offset - 1, playlist_id, target + offset),
            )
            connection.execute(
                """
                INSERT INTO playlist_items(playlist_id, song_id, position)
                VALUES(?, ?, ?)
                """,
                (playlist_id, song_id, target),
            )
            connection.execute(
                "UPDATE playlists SET updated_at = ? WHERE playlist_id = ?",
                (datetime.now(timezone.utc).isoformat(), playlist_id),
            )

        await run_transaction(self.path, operation)

    async def remove_song(self, playlist_id: str, song_id: str) -> None:
        async def operation(connection):
            self._require_playlist(connection, playlist_id)
            row = connection.execute(
                """
                SELECT position
                FROM playlist_items
                WHERE playlist_id = ? AND song_id = ?
                """,
                (playlist_id, song_id),
            ).fetchone()
            if row is not None:
                removed_position = row[0]
                connection.execute(
                    """
                    DELETE FROM playlist_items
                    WHERE playlist_id = ? AND song_id = ?
                    """,
                    (playlist_id, song_id),
                )
                connection.execute(
                    """
                    UPDATE playlist_items
                    SET position = position - 1
                    WHERE playlist_id = ? AND position > ?
                    """,
                    (playlist_id, removed_position),
                )
                connection.execute(
                    "UPDATE playlists SET updated_at = ? WHERE playlist_id = ?",
                    (datetime.now(timezone.utc).isoformat(), playlist_id),
                )

        await run_transaction(self.path, operation)

    async def reorder_playlist(
        self, playlist_id: str, ordered_song_ids: list[str]
    ) -> None:
        async def operation(connection):
            self._require_playlist(connection, playlist_id)
            current_song_ids = [
                row[0]
                for row in connection.execute(
                    """
                    SELECT song_id
                    FROM playlist_items
                    WHERE playlist_id = ?
                    ORDER BY position
                    """,
                    (playlist_id,),
                )
            ]
            if len(ordered_song_ids) != len(set(ordered_song_ids)):
                raise ValueError("ordered_song_ids contains duplicates")
            if set(ordered_song_ids) != set(current_song_ids):
                raise PlaylistReorderMemberMismatchError(
                    "ordered_song_ids must match playlist members"
                )

            connection.execute(
                """
                UPDATE playlist_items
                SET position = position + ?
                WHERE playlist_id = ?
                """,
                (len(current_song_ids), playlist_id),
            )
            for position, song_id in enumerate(ordered_song_ids):
                connection.execute(
                    """
                    UPDATE playlist_items
                    SET position = ?
                    WHERE playlist_id = ? AND song_id = ?
                    """,
                    (position, playlist_id, song_id),
                )
            if ordered_song_ids != current_song_ids:
                connection.execute(
                    "UPDATE playlists SET updated_at = ? WHERE playlist_id = ?",
                    (datetime.now(timezone.utc).isoformat(), playlist_id),
                )

        await run_transaction(self.path, operation)

    async def set_favorite(self, song_id: str, is_favorite: bool) -> None:
        async def operation(connection):
            if is_favorite:
                self._require_song(connection, song_id)
                connection.execute(
                    """
                    INSERT OR IGNORE INTO favorites(song_id, created_at)
                    VALUES(?, ?)
                    """,
                    (song_id, datetime.now(timezone.utc).isoformat()),
                )
            else:
                connection.execute(
                    "DELETE FROM favorites WHERE song_id = ?",
                    (song_id,),
                )

        await run_transaction(self.path, operation)

    async def list_favorite_song_ids(self) -> list[str]:
        async def operation(connection):
            return [
                row[0]
                for row in connection.execute(
                    """
                    SELECT song_id
                    FROM favorites
                    ORDER BY created_at DESC, song_id DESC
                    """
                )
            ]

        return await run_transaction(self.path, operation)

    async def list_song_ids(self, playlist_id: str) -> list[str]:
        async def operation(connection):
            self._require_playlist(connection, playlist_id)
            return [
                row[0]
                for row in connection.execute(
                    """
                    SELECT song_id
                    FROM playlist_items
                    WHERE playlist_id = ?
                    ORDER BY position
                    """,
                    (playlist_id,),
                )
            ]

        return await run_transaction(self.path, operation)
