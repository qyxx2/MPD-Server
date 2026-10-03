from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class OutputMode(str, Enum):
    NAS_DAC = "NAS_DAC"
    CLIENT_STREAM = "CLIENT_STREAM"


class OutputState(BaseModel):
    mode: OutputMode
    status: Literal["UNAVAILABLE", "INACTIVE", "ACTIVE"]
    target_client_id: str | None = None
    stream_url: str | None = None
    format: str | None = None
    sample_rate: int | None = None
    bit_depth: int | None = None
    channels: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    updated_at: datetime
    stale: bool = False


class OutputRequestState(BaseModel):
    mode: OutputMode
    enabled: bool
    status: Literal["PREPARING", "SUCCEEDED", "SWITCH_FAILED"]
    error_code: str | None = None
    error_message: str | None = None
    updated_at: datetime


class OutputSnapshot(BaseModel):
    states: tuple[OutputState, ...]
    last_request: OutputRequestState | None = None
