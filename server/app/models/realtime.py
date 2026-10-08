from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from server.app.models.history import HistoryEvent
from server.app.models.library import Song
from server.app.models.output import OutputSnapshot
from server.app.models.queue import PlaybackState, QueueSnapshot
from server.app.player.models import PlayerState


class ActualCurrent(BaseModel):
    model_config = ConfigDict(frozen=True)

    entry_id: int | None = None
    uri: str | None = None
    position: int | None = Field(default=None, ge=0)


class HistoryAvailability(BaseModel):
    has_entries: bool
    active_event: HistoryEvent | None = None
    session_id: str | None = None


class PlaybackObservation(BaseModel):
    actual_state: PlayerState | None = None
    actual_current: ActualCurrent | None = None
    actual_freshness: Literal["fresh", "stale", "unknown"] = "unknown"
    bound_queue_item_id: str | None = None
    sync_status: Literal[
        "CONFIRMED",
        "UNBOUND",
        "EXTERNAL_DRIFT",
        "UNCONFIRMED_STOP",
        "SYNC_FAILED",
        "NO_CANDIDATES",
    ] = "UNBOUND"
    matches_current: bool | None = None
    position_seconds: float | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    observed_at: datetime | None = None
    freshness: Literal["fresh", "stale", "unknown"] = "unknown"
    reconciliation_required: bool = False
    error_code: str | None = None
    error_message: str | None = None


class OutputObservation(BaseModel):
    observed_at: datetime | None = None
    freshness: Literal["fresh", "stale", "unknown"] = "unknown"
    error_code: str | None = None
    error_message: str | None = None


class FullStateSnapshot(BaseModel):
    epoch: str
    sequence: int = Field(ge=0)
    captured_at: datetime
    revisions: dict[str, int]
    playback: PlaybackState | None
    current_song: Song | None
    queue: QueueSnapshot
    history: HistoryAvailability
    output: OutputSnapshot
    playback_observation: PlaybackObservation = Field(default_factory=PlaybackObservation)
    output_observation: OutputObservation = Field(default_factory=OutputObservation)


class StateMarker(BaseModel):
    model_config = ConfigDict(frozen=True)

    epoch: str
    sequence: int = Field(default=0, ge=0)
    library_revision: int = Field(default=0, ge=0)
    playlist_revision: int = Field(default=0, ge=0)


class Invalidation(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["invalidate"] = "invalidate"
    protocol_version: Literal[1] = 1
    epoch: str
    sequence: int = Field(ge=0)
    domains: frozenset[str]
    revisions: dict[str, int]
