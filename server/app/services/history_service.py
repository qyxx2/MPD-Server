from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from server.app.models.history import HistoryEvent
from server.app.models.queue import QueueItem
from server.app.repositories.history_repository import HistoryRepository
from server.app.repositories.queue_repository import QueueRepository

HistoryReason = Literal[
    "NATURAL_COMPLETION",
    "SKIP",
    "STOP",
    "SWITCH_AWAY",
]


class HistoryService:
    """Keeps current-session Played view separate from persistent History."""

    NATURAL_COMPLETION = "NATURAL_COMPLETION"
    SKIP = "SKIP"
    STOP = "STOP"
    SWITCH_AWAY = "SWITCH_AWAY"

    def __init__(
        self,
        queue_repository: QueueRepository,
        history_repository: HistoryRepository,
    ) -> None:
        self.queue_repository = queue_repository
        self.history_repository = history_repository
        self._active: HistoryEvent | None = None
        self._session_id: str | None = None

    async def list_played(self) -> list[QueueItem]:
        items = await self.queue_repository.list_items()
        return [item for item in items if item.position < 0]

    async def list_history(self, limit: int | None = None) -> list[HistoryEvent]:
        return await self.history_repository.list_history(limit=limit)

    async def start_track(
        self,
        song_id: str,
        *,
        started_at: datetime | None = None,
        session_id: str | None = None,
    ) -> HistoryEvent:
        started_at = started_at or datetime.now(timezone.utc)

        if self._active is not None:
            await self._finish_active(
                reason=self.SWITCH_AWAY,
                ended_at=started_at,
            )

        if session_id is not None:
            self._session_id = session_id
        elif self._session_id is None:
            self._session_id = str(uuid.uuid4())

        self._active = HistoryEvent(
            song_id=song_id,
            started_at=started_at,
            session_id=self._session_id,
        )
        return self._active

    async def complete_naturally(
        self,
        *,
        ended_at: datetime | None = None,
    ) -> HistoryEvent | None:
        return await self._finish_active(
            reason=self.NATURAL_COMPLETION,
            ended_at=ended_at,
        )

    async def skip(
        self,
        *,
        ended_at: datetime | None = None,
    ) -> HistoryEvent | None:
        return await self._finish_active(
            reason=self.SKIP,
            ended_at=ended_at,
        )

    async def stop(
        self,
        *,
        ended_at: datetime | None = None,
    ) -> HistoryEvent | None:
        return await self._finish_active(
            reason=self.STOP,
            ended_at=ended_at,
        )

    async def switch_away(
        self,
        *,
        ended_at: datetime | None = None,
    ) -> HistoryEvent | None:
        return await self._finish_active(
            reason=self.SWITCH_AWAY,
            ended_at=ended_at,
        )

    @property
    def active_event(self) -> HistoryEvent | None:
        return self._active

    @property
    def session_id(self) -> str | None:
        return self._session_id

    async def _finish_active(
        self,
        *,
        reason: HistoryReason,
        ended_at: datetime | None,
    ) -> HistoryEvent | None:
        active = self._active
        if active is None:
            return None

        ended_at = ended_at or datetime.now(timezone.utc)
        completed = active.model_copy(
            update={
                "ended_at": ended_at,
                "reason": reason,
            }
        )
        await self.history_repository.record_history(completed)
        self._active = None

        if reason == self.STOP:
            self._session_id = None

        return completed
