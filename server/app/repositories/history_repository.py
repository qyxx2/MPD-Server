from __future__ import annotations

from datetime import datetime

from server.app.models.history import HistoryEvent

from .database import run_transaction


class HistoryRepository:
    def __init__(self, path: str) -> None:
        self.path = path

    async def record_history(self, event: HistoryEvent) -> None:
        async def operation(connection):
            connection.execute(
                """
                INSERT INTO history(
                    song_id, started_at, ended_at, reason, session_id
                ) VALUES(?, ?, ?, ?, ?)
                """,
                (
                    event.song_id,
                    event.started_at.isoformat(),
                    event.ended_at.isoformat() if event.ended_at else None,
                    event.reason,
                    event.session_id,
                ),
            )

        await run_transaction(self.path, operation)

    async def list_history(self, limit: int | None = None) -> list[HistoryEvent]:
        async def operation(connection):
            query = """
                SELECT history_id, song_id, started_at, ended_at, reason, session_id
                FROM history
                ORDER BY started_at DESC, history_id DESC
            """
            params: tuple[int, ...] = ()
            if limit is not None:
                if limit <= 0:
                    return []
                query += " LIMIT ?"
                params = (limit,)
            rows = connection.execute(query, params).fetchall()
            return [
                HistoryEvent(
                    history_id=row[0],
                    song_id=row[1],
                    started_at=datetime.fromisoformat(row[2]),
                    ended_at=datetime.fromisoformat(row[3]) if row[3] else None,
                    reason=row[4],
                    session_id=row[5],
                )
                for row in rows
            ]

        return await run_transaction(self.path, operation)
