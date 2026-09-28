from __future__ import annotations

from datetime import datetime

from server.app.models.queue import PlaybackState

from .database import run_transaction


class PlaybackStateRepository:
    def __init__(self, path: str) -> None:
        self.path = path

    async def get_state(self) -> PlaybackState | None:
        async def operation(connection):
            row = connection.execute(
                """
                SELECT song_id, state, playback_context_id,
                       position_seconds, autoplay_enabled, updated_at
                FROM playback_state
                WHERE id = 1
                """
            ).fetchone()
            if row is None:
                return None
            return PlaybackState(
                song_id=row[0],
                state=str(row[1]),
                playback_context_id=row[2],
                position_seconds=row[3],
                autoplay_enabled=bool(row[4]),
                updated_at=datetime.fromisoformat(row[5]),
            )

        return await run_transaction(self.path, operation)

    async def save(self, state: PlaybackState) -> PlaybackState:
        async def operation(connection):
            connection.execute(
                """
                INSERT INTO playback_state(
                    id, song_id, state, playback_context_id,
                    position_seconds, autoplay_enabled, updated_at
                ) VALUES(1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    song_id = excluded.song_id,
                    state = excluded.state,
                    playback_context_id = excluded.playback_context_id,
                    position_seconds = excluded.position_seconds,
                    autoplay_enabled = excluded.autoplay_enabled,
                    updated_at = excluded.updated_at
                """,
                (
                    state.song_id,
                    state.state,
                    state.playback_context_id,
                    state.position_seconds,
                    int(state.autoplay_enabled),
                    state.updated_at.isoformat(),
                ),
            )
            return state

        return await run_transaction(self.path, operation)
