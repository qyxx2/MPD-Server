from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class HardwareVolumeStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNSUPPORTED = "UNSUPPORTED"


class HardwareVolumeRequestStatus(str, Enum):
    PREPARING = "PREPARING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class HardwareVolumeControlSource(str, Enum):
    MPD_HARDWARE_MIXER = "MPD_HARDWARE_MIXER"


class HardwareVolumeState(BaseModel):
    status: HardwareVolumeStatus
    volume_percent: int | None = Field(default=None, strict=True, ge=0, le=100)
    output_name: str | None = None
    output_plugin: str | None = None
    output_enabled: bool | None = None
    control_source: HardwareVolumeControlSource | None = None
    error_code: str | None = None
    error_message: str | None = None
    updated_at: datetime
    stale: bool = False


class HardwareVolumeRequestState(BaseModel):
    requested_percent: int = Field(strict=True, ge=0, le=100)
    status: HardwareVolumeRequestStatus
    error_code: str | None = None
    error_message: str | None = None
    updated_at: datetime


class HardwareVolumeSnapshot(BaseModel):
    state: HardwareVolumeState
    last_request: HardwareVolumeRequestState | None = None


class HardwareVolumeObservation(BaseModel):
    observed_at: datetime | None = None
    freshness: Literal["fresh", "stale", "unknown"] = "unknown"
    error_code: str | None = None
    error_message: str | None = None
