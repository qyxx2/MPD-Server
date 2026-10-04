from __future__ import annotations

import uuid

from server.app.models.queue import (
    PlaybackContext,
    QueueItem,
    QueueItemSource,
    QueueSnapshot,
)

from .database import run_transaction


class QueueItemNotFoundError(ValueError):
    """Raised when a requested Queue item does not exist."""


class CurrentTrackDeletionError(ValueError):
    """Raised when the current track cannot be deleted safely."""


class QueueRevisionConflictError(ValueError):
    """Raised when a Queue mutation is based on a stale revision."""

    def __init__(self, expected_revision: int, actual_revision: int) -> None:
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision
        super().__init__(
            "Queue revision conflict: "
            f"expected {expected_revision}, actual {actual_revision}"
        )


class QueueRepository:
    """Persistent authoritative Queue storage."""

    _QUEUE_STATE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS queue_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            revision INTEGER NOT NULL CHECK(revision >= 0)
        )
    """

    def __init__(self, path: str) -> None:
        self.path = path

    @classmethod
    def _ensure_queue_state(cls, connection) -> None:
        connection.execute(cls._QUEUE_STATE_SCHEMA)
        connection.execute(
            """
            INSERT OR IGNORE INTO queue_state(id, revision)
            VALUES(1, 0)
            """
        )

    @classmethod
    def _current_revision(cls, connection) -> int:
        cls._ensure_queue_state(connection)
        row = connection.execute(
            "SELECT revision FROM queue_state WHERE id = 1"
        ).fetchone()
        assert row is not None
        return int(row[0])

    @classmethod
    def _reserve_mutation(
        cls,
        connection,
        expected_revision: int | None,
    ) -> int:
        cls._ensure_queue_state(connection)
        if expected_revision is None:
            connection.execute(
                """
                UPDATE queue_state
                SET revision = revision + 1
                WHERE id = 1
                """
            )
        else:
            result = connection.execute(
                """
                UPDATE queue_state
                SET revision = revision + 1
                WHERE id = 1 AND revision = ?
                """,
                (expected_revision,),
            )
            if result.rowcount != 1:
                actual_revision = cls._current_revision(connection)
                raise QueueRevisionConflictError(
                    expected_revision,
                    actual_revision,
                )
        return cls._current_revision(connection)

    @staticmethod
    def _item_from_row(row: tuple[object, ...]) -> QueueItem:
        return QueueItem(
            queue_item_id=str(row[0]),
            song_id=str(row[1]),
            position=int(row[2]),
            source=str(row[3]),
            playback_context_id=(
                str(row[4]) if row[4] is not None else None
            ),
        )

    @staticmethod
    def _list_from_connection(connection) -> list[QueueItem]:
        rows = connection.execute(
            """
            SELECT queue_item_id, song_id, position, source,
                   playback_context_id
            FROM queue_items
            ORDER BY
                CASE
                    WHEN position < 0 THEN 0
                    WHEN position = 0 THEN 1
                    ELSE 2
                END,
                CASE
                    WHEN position < 0 THEN -position
                    ELSE position
                END,
                queue_item_id
            """
        ).fetchall()
        return [QueueRepository._item_from_row(row) for row in rows]

    async def get_revision(self) -> int:
        async def operation(connection):
            return self._current_revision(connection)

        return await run_transaction(self.path, operation)

    async def get_snapshot(self) -> QueueSnapshot:
        async def operation(connection):
            revision = self._current_revision(connection)
            return QueueSnapshot(
                revision=revision,
                items=tuple(self._list_from_connection(connection)),
            )

        return await run_transaction(self.path, operation)

    async def list_items(self) -> list[QueueItem]:
        async def operation(connection):
            self._ensure_queue_state(connection)
            return self._list_from_connection(connection)

        return await run_transaction(self.path, operation)

    async def get_item(self, queue_item_id: str) -> QueueItem | None:
        async def operation(connection):
            self._ensure_queue_state(connection)
            row = connection.execute(
                """
                SELECT queue_item_id, song_id, position, source,
                       playback_context_id
                FROM queue_items
                WHERE queue_item_id = ?
                """,
                (queue_item_id,),
            ).fetchone()
            return self._item_from_row(row) if row else None

        return await run_transaction(self.path, operation)

    async def start_track(
        self,
        song_id: str,
        playback_context_id: str,
        *,
        expected_revision: int | None = None,
    ) -> QueueItem:
        async def operation(connection):
            self._reserve_mutation(connection, expected_revision)
            connection.execute(
                """
                UPDATE queue_items
                SET position = position - 1
                WHERE position < 0
                """
            )
            current = connection.execute(
                """
                SELECT queue_item_id
                FROM queue_items
                WHERE position = 0
                """
            ).fetchone()
            if current is not None:
                connection.execute(
                    """
                    UPDATE queue_items
                    SET position = -1
                    WHERE queue_item_id = ?
                    """,
                    (current[0],),
                )
            connection.execute("DELETE FROM queue_items WHERE position > 0")

            queue_item_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO queue_items(
                    queue_item_id, song_id, position, source,
                    playback_context_id
                ) VALUES(?, ?, 0, 'MANUAL', ?)
                """,
                (queue_item_id, song_id, playback_context_id),
            )
            return QueueItem(
                queue_item_id=queue_item_id,
                song_id=song_id,
                position=0,
                source="MANUAL",
                playback_context_id=playback_context_id,
            )

        return await run_transaction(self.path, operation)

    async def replace_with_context(
        self,
        playback_context: PlaybackContext,
        *,
        expected_revision: int | None = None,
    ) -> list[QueueItem]:
        async def operation(connection):
            self._reserve_mutation(connection, expected_revision)

            connection.execute(
                """
                UPDATE queue_items
                SET position = position - 1
                WHERE position < 0
                """
            )

            current = connection.execute(
                """
                SELECT queue_item_id
                FROM queue_items
                WHERE position = 0
                """
            ).fetchone()
            if current is not None:
                connection.execute(
                    """
                    UPDATE queue_items
                    SET position = -1
                    WHERE queue_item_id = ?
                    """,
                    (current[0],),
                )

            connection.execute("DELETE FROM queue_items WHERE position > 0")

            for position, song_id in enumerate(
                playback_context.ordered_song_ids
            ):
                queue_item_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO queue_items(
                        queue_item_id, song_id, position, source,
                        playback_context_id
                    ) VALUES(?, ?, ?, 'MANUAL', ?)
                    """,
                    (
                        queue_item_id,
                        song_id,
                        position,
                        playback_context.context_id,
                    ),
                )

            return self._list_from_connection(connection)

        return await run_transaction(self.path, operation)

    async def play_now(
        self,
        queue_item_id: str,
        *,
        expected_revision: int | None = None,
    ) -> QueueItem:
        async def operation(connection):
            self._reserve_mutation(connection, expected_revision)
            row = connection.execute(
                """
                SELECT queue_item_id, song_id, position, source,
                       playback_context_id
                FROM queue_items
                WHERE queue_item_id = ?
                """,
                (queue_item_id,),
            ).fetchone()
            if row is None:
                raise QueueItemNotFoundError(queue_item_id)

            selected_position = int(row[2])
            if selected_position == 0:
                return self._item_from_row(row)

            current = connection.execute(
                """
                SELECT queue_item_id
                FROM queue_items
                WHERE position = 0
                """
            ).fetchone()
            current_id = str(current[0]) if current is not None else None

            played_ids = [
                str(item[0])
                for item in connection.execute(
                    """
                    SELECT queue_item_id
                    FROM queue_items
                    WHERE position < 0
                    ORDER BY position DESC, queue_item_id
                    """
                ).fetchall()
                if str(item[0]) != queue_item_id
            ]
            if (
                current_id is not None
                and current_id != queue_item_id
                and current_id not in played_ids
            ):
                played_ids.insert(0, current_id)

            up_next_ids = [
                str(item[0])
                for item in connection.execute(
                    """
                    SELECT queue_item_id
                    FROM queue_items
                    WHERE position > 0
                    ORDER BY position, queue_item_id
                    """
                ).fetchall()
                if str(item[0]) != queue_item_id
            ]

            connection.execute(
                """
                UPDATE queue_items
                SET position =
                    CASE
                        WHEN position < 0 THEN position - 1000000
                        ELSE position + 1000000
                    END
                """
            )

            for position, item_id in enumerate(played_ids, start=1):
                connection.execute(
                    """
                    UPDATE queue_items
                    SET position = ?
                    WHERE queue_item_id = ?
                    """,
                    (-position, item_id),
                )

            connection.execute(
                """
                UPDATE queue_items
                SET position = 0
                WHERE queue_item_id = ?
                """,
                (queue_item_id,),
            )

            for position, item_id in enumerate(up_next_ids, start=1):
                connection.execute(
                    """
                    UPDATE queue_items
                    SET position = ?
                    WHERE queue_item_id = ?
                    """,
                    (position, item_id),
                )

            final = connection.execute(
                """
                SELECT queue_item_id, song_id, position, source,
                       playback_context_id
                FROM queue_items
                WHERE queue_item_id = ?
                """,
                (queue_item_id,),
            ).fetchone()
            return self._item_from_row(final)

        return await run_transaction(self.path, operation)

    async def play_next(
        self,
        song_id: str,
        *,
        playback_context_id: str | None = None,
        source: QueueItemSource = "MANUAL",
        expected_revision: int | None = None,
    ) -> QueueItem:
        async def operation(connection):
            self._reserve_mutation(connection, expected_revision)
            connection.execute(
                """
                UPDATE queue_items
                SET position = position + 1
                WHERE position > 0
                """
            )
            queue_item_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO queue_items(
                    queue_item_id, song_id, position, source,
                    playback_context_id
                ) VALUES(?, ?, 1, ?, ?)
                """,
                (queue_item_id, song_id, source, playback_context_id),
            )
            return QueueItem(
                queue_item_id=queue_item_id,
                song_id=song_id,
                position=1,
                source=source,
                playback_context_id=playback_context_id,
            )

        return await run_transaction(self.path, operation)

    async def add_to_queue(
        self,
        song_id: str,
        *,
        playback_context_id: str | None = None,
        source: QueueItemSource = "MANUAL",
        expected_revision: int | None = None,
    ) -> QueueItem:
        async def operation(connection):
            self._reserve_mutation(connection, expected_revision)
            row = connection.execute(
                """
                SELECT COALESCE(MAX(position), 0)
                FROM queue_items
                WHERE position > 0
                """
            ).fetchone()
            position = int(row[0] or 0) + 1
            queue_item_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO queue_items(
                    queue_item_id, song_id, position, source,
                    playback_context_id
                ) VALUES(?, ?, ?, ?, ?)
                """,
                (queue_item_id, song_id, position, source, playback_context_id),
            )
            return QueueItem(
                queue_item_id=queue_item_id,
                song_id=song_id,
                position=position,
                source=source,
                playback_context_id=playback_context_id,
            )

        return await run_transaction(self.path, operation)

    async def reorder(
        self,
        queue_item_id: str,
        before_queue_item_id: str | None = None,
        *,
        expected_revision: int | None = None,
    ) -> list[QueueItem]:
        async def operation(connection):
            self._reserve_mutation(connection, expected_revision)
            row = connection.execute(
                """
                SELECT position
                FROM queue_items
                WHERE queue_item_id = ?
                """,
                (queue_item_id,),
            ).fetchone()
            if row is None:
                raise QueueItemNotFoundError(queue_item_id)
            if int(row[0]) <= 0:
                raise ValueError("only Up Next items can be reordered")

            pending = [
                str(item[0])
                for item in connection.execute(
                    """
                    SELECT queue_item_id
                    FROM queue_items
                    WHERE position > 0
                    ORDER BY position, queue_item_id
                    """
                ).fetchall()
            ]
            if before_queue_item_id == queue_item_id:
                return self._list_from_connection(connection)
            if (
                before_queue_item_id is not None
                and before_queue_item_id not in pending
            ):
                raise QueueItemNotFoundError(before_queue_item_id)

            pending.remove(queue_item_id)
            if before_queue_item_id is None:
                pending.append(queue_item_id)
            else:
                pending.insert(pending.index(before_queue_item_id), queue_item_id)

            connection.execute(
                """
                UPDATE queue_items
                SET position = position + 1000000
                WHERE position > 0
                """
            )
            for position, item_id in enumerate(pending, start=1):
                connection.execute(
                    """
                    UPDATE queue_items
                    SET position = ?
                    WHERE queue_item_id = ?
                    """,
                    (position, item_id),
                )
            return self._list_from_connection(connection)

        return await run_transaction(self.path, operation)

    async def delete_item(
        self,
        queue_item_id: str,
        *,
        expected_revision: int | None = None,
        allow_no_successor: bool = False,
    ) -> QueueItem | None:
        async def operation(connection):
            self._reserve_mutation(connection, expected_revision)
            row = connection.execute(
                """
                SELECT queue_item_id, song_id, position, source,
                       playback_context_id
                FROM queue_items
                WHERE queue_item_id = ?
                """,
                (queue_item_id,),
            ).fetchone()
            if row is None:
                raise QueueItemNotFoundError(queue_item_id)

            position = int(row[2])
            if position == 0:
                next_row = connection.execute(
                    """
                    SELECT queue_item_id, song_id, position, source,
                           playback_context_id
                    FROM queue_items
                    WHERE position > 0
                    ORDER BY position, queue_item_id
                    LIMIT 1
                    """
                ).fetchone()
                if next_row is None and not allow_no_successor:
                    raise CurrentTrackDeletionError(
                        "cannot delete current track without a successor"
                    )
                connection.execute(
                    """
                    UPDATE queue_items
                    SET position = position - 1
                    WHERE position < 0
                    """
                )
                connection.execute(
                    """
                    UPDATE queue_items
                    SET position = -1
                    WHERE queue_item_id = ?
                    """,
                    (queue_item_id,),
                )
                if next_row is None:
                    return None
                connection.execute(
                    """
                    UPDATE queue_items
                    SET position = position - 1
                    WHERE position > 0
                    """
                )
                connection.execute(
                    """
                    UPDATE queue_items
                    SET position = 0
                    WHERE queue_item_id = ?
                    """,
                    (next_row[0],),
                )
                return self._item_from_row(
                    connection.execute(
                        """
                        SELECT queue_item_id, song_id, position, source,
                               playback_context_id
                        FROM queue_items
                        WHERE queue_item_id = ?
                        """,
                        (next_row[0],),
                    ).fetchone()
                )

            connection.execute(
                "DELETE FROM queue_items WHERE queue_item_id = ?",
                (queue_item_id,),
            )
            if position > 0:
                connection.execute(
                    """
                    UPDATE queue_items
                    SET position = position - 1
                    WHERE position > ?
                    """,
                    (position,),
                )
            else:
                played = connection.execute(
                    """
                    SELECT queue_item_id
                    FROM queue_items
                    WHERE position < 0
                    ORDER BY position DESC, queue_item_id
                    """
                ).fetchall()
                for index, item in enumerate(played, start=1):
                    connection.execute(
                        """
                        UPDATE queue_items
                        SET position = ?
                        WHERE queue_item_id = ?
                        """,
                        (-index, item[0]),
                    )
            return None

        return await run_transaction(self.path, operation)

    async def clear_pending(
        self,
        *,
        expected_revision: int | None = None,
    ) -> None:
        async def operation(connection):
            self._reserve_mutation(connection, expected_revision)
            connection.execute("DELETE FROM queue_items WHERE position > 0")

        await run_transaction(self.path, operation)

    async def add_autoplay_batch(
        self,
        song_ids: list[str],
        *,
        playback_context_id: str | None = None,
        max_items: int = 5,
        allow_current_repeat: bool = False,
        expected_revision: int | None = None,
    ) -> list[QueueItem]:
        if max_items <= 0 or not song_ids:
            return []

        async def operation(connection):
            rows = connection.execute(
                """
                SELECT queue_item_id, song_id, position, source,
                       playback_context_id
                FROM queue_items
                ORDER BY position, queue_item_id
                """
            ).fetchall()
            current_song_id = next(
                (str(row[1]) for row in rows if int(row[2]) == 0),
                None,
            )
            current_context_id = next(
                (
                    str(row[4])
                    for row in rows
                    if int(row[2]) == 0 and row[4] is not None
                ),
                None,
            )
            if (
                playback_context_id is not None
                and current_context_id is not None
                and current_context_id != playback_context_id
            ):
                if expected_revision is not None:
                    actual_revision = self._current_revision(connection)
                    if actual_revision != expected_revision:
                        raise QueueRevisionConflictError(
                            expected_revision,
                            actual_revision,
                        )
                return []

            self._reserve_mutation(connection, expected_revision)
            queued_song_ids = {str(row[1]) for row in rows}
            pending_candidates: list[str] = []
            seen_candidates: set[str] = set()
            for song_id in song_ids:
                if song_id in seen_candidates:
                    continue
                seen_candidates.add(song_id)
                if song_id in queued_song_ids and not (
                    allow_current_repeat
                    and song_id == current_song_id
                    and not any(
                        int(row[2]) > 0 and str(row[1]) == song_id
                        for row in rows
                    )
                ):
                    continue
                pending_candidates.append(song_id)
                if len(pending_candidates) >= max_items:
                    break

            if not pending_candidates:
                return []

            row = connection.execute(
                """
                SELECT COALESCE(MAX(position), 0)
                FROM queue_items
                WHERE position > 0
                """
            ).fetchone()
            start_position = int(row[0] or 0) + 1

            created: list[QueueItem] = []
            for offset, song_id in enumerate(
                pending_candidates,
                start=start_position,
            ):
                queue_item_id = str(uuid.uuid4())
                connection.execute(
                    """
                    INSERT INTO queue_items(
                        queue_item_id, song_id, position, source,
                        playback_context_id
                    ) VALUES(?, ?, ?, 'AUTOPLAY', ?)
                    """,
                    (
                        queue_item_id,
                        song_id,
                        offset,
                        playback_context_id,
                    ),
                )
                created.append(
                    QueueItem(
                        queue_item_id=queue_item_id,
                        song_id=song_id,
                        position=offset,
                        source="AUTOPLAY",
                        playback_context_id=playback_context_id,
                    )
                )
            return created

        return await run_transaction(self.path, operation)

    async def list_up_next(self) -> list[QueueItem]:
        async def operation(connection):
            self._ensure_queue_state(connection)
            rows = connection.execute(
                """
                SELECT queue_item_id, song_id, position, source,
                       playback_context_id
                FROM queue_items
                WHERE position > 0
                ORDER BY position, queue_item_id
                """
            ).fetchall()
            return [self._item_from_row(row) for row in rows]

        return await run_transaction(self.path, operation)

    async def complete_current(
        self, queue_item_id: str, *, pending: tuple[QueueItem, ...],
        successor_id: str | None, expected_revision: int,
    ) -> QueueSnapshot:
        """Complete exactly one current, retaining Played and pending identities."""
        async def operation(connection):
            items = self._list_from_connection(connection)
            current = next((i for i in items if i.position == 0), None)
            if current is None or current.queue_item_id != queue_item_id:
                raise ValueError("Completion does not identify the current occurrence")
            ids = [i.queue_item_id for i in pending]
            if len(set(ids)) != len(ids) or successor_id != (ids[0] if ids else None):
                raise ValueError("Completion successor must be the first planned pending item")
            existing = {i.queue_item_id: i for i in items}
            retained = []
            for item in pending:
                old = existing.get(item.queue_item_id)
                if old is not None:
                    if old.position <= 0 or old != item:
                        raise ValueError("Completion cannot overwrite an existing occurrence")
                    retained.append(item.queue_item_id)
                elif item.source != "AUTOPLAY" or item.position <= 0:
                    raise ValueError("New completion candidates must be AutoPlay pending")
            if retained != [i.queue_item_id for i in items if i.position > 0 and i.queue_item_id in retained]:
                raise ValueError("Completion cannot reorder retained pending")
            self._reserve_mutation(connection, expected_revision)
            connection.execute("DELETE FROM queue_items WHERE position > 0")
            connection.execute("UPDATE queue_items SET position = position - 1 WHERE position < 0")
            connection.execute("UPDATE queue_items SET position = -1 WHERE queue_item_id = ?", (queue_item_id,))
            for position, item in enumerate(pending):
                connection.execute(
                    "INSERT INTO queue_items(queue_item_id,song_id,position,source,playback_context_id) VALUES(?,?,?,?,?)",
                    (item.queue_item_id, item.song_id, position, item.source, item.playback_context_id),
                )
            return QueueSnapshot(revision=self._current_revision(connection), items=tuple(self._list_from_connection(connection)))
        return await run_transaction(self.path, operation)
