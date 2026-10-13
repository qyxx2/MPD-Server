from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LibrarySyncState(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["IDLE", "SYNCING", "SYNCED", "FAILED"] = "IDLE"
    generation: int = 0
    activity_id: str | None = None
    trigger: str | None = None
    pending_count: int = 0
    confirmed_count: int = 0
    failed_count: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_code: str | None = None
    reason: str | None = None
