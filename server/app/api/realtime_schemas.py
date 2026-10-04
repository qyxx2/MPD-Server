from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .schemas import (
    HistoryEventResponse,
    PlaybackStateResponse,
    QueueItemResponse,
    SongResponse,
)


class StateRevisionsResponse(BaseModel):
    library: int = Field(ge=0)
    playlist: int = Field(ge=0)


class StateQueueResponse(BaseModel):
    revision: int = Field(ge=0)
    items: list[QueueItemResponse]


class HistoryAvailabilityResponse(BaseModel):
    has_entries: bool
    active_event: HistoryEventResponse | None
    session_id: str | None


class PlaybackObservationResponse(BaseModel):
    actual_state: Literal["playing", "paused", "stopped"] | None
    matches_current: bool | None
    position_seconds: float | None = Field(ge=0)
    duration_seconds: float | None = Field(ge=0)
    observed_at: datetime | None
    freshness: Literal["fresh", "stale", "unknown"]
    reconciliation_required: bool
    error_code: str | None
    error_message: str | None


class OutputObservationResponse(BaseModel):
    observed_at: datetime | None
    freshness: Literal["fresh", "stale", "unknown"]
    error_code: str | None
    error_message: str | None


class StateOutputResponse(BaseModel):
    mode: Literal["NAS_DAC", "CLIENT_STREAM"]
    status: Literal["UNAVAILABLE", "INACTIVE", "ACTIVE"]
    target_client_id: str | None
    stream_url: str | None
    format: str | None
    sample_rate: int | None
    bit_depth: int | None
    channels: int | None
    error_code: str | None
    error_message: str | None
    updated_at: datetime
    stale: bool


class StateOutputRequestResponse(BaseModel):
    mode: Literal["NAS_DAC", "CLIENT_STREAM"]
    enabled: bool
    status: Literal["PREPARING", "SUCCEEDED", "SWITCH_FAILED"]
    error_code: str | None
    error_message: str | None
    updated_at: datetime


class StateOutputSnapshotResponse(BaseModel):
    states: list[StateOutputResponse]
    last_request: StateOutputRequestResponse | None


class FullStateSnapshotResponse(BaseModel):
    epoch: str
    sequence: int = Field(ge=0)
    captured_at: datetime
    revisions: StateRevisionsResponse
    playback: PlaybackStateResponse | None
    current_song: SongResponse | None
    queue: StateQueueResponse
    history: HistoryAvailabilityResponse
    output: StateOutputSnapshotResponse
    playback_observation: PlaybackObservationResponse
    output_observation: OutputObservationResponse
