from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from server.app.player.models import DatabaseUpdateStatus, MPDStats


class MPDInfoError(BaseModel):
    code: Literal["CAPABILITY_UNVERIFIED", "PLAYER_UNAVAILABLE", "PLAYER_COMMAND_ERROR"]
    message: str


class MPDInfo(BaseModel):
    version: str | None = None
    version_source: Literal["verified_capability"] | None = None
    stats: MPDStats = Field(default_factory=MPDStats)
    database_update_status: DatabaseUpdateStatus = Field(default_factory=DatabaseUpdateStatus)
    connected: bool | None = None
    errors: dict[str, MPDInfoError] = Field(default_factory=dict)
    observed_at: datetime
