from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HistoryEvent(BaseModel):
    history_id: int | None = None
    song_id: str
    started_at: datetime
    ended_at: datetime | None = None
    reason: str | None = None
    session_id: str | None = None
