from __future__ import annotations

import uuid
from datetime import datetime, timezone

from server.app.models.playlist import Playlist

from .database import run_transaction


class DuplicatePlaylistSongError(ValueError):
    """Raised when a song already exists in the target playlist."""


class PlaylistRepository:
    def __init__(self, path: str) -> None:
        self.path = path

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

    async def add_song(
        self, playlist_id: str, song_id: str, position: int | None = None
    ) -> None:
        async def operation(connection):
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

    async def list_song_ids(self, playlist_id: str) -> list[str]:
        async def operation(connection):
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
