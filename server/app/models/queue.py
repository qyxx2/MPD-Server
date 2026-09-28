from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

QueueItemSource = Literal["MANUAL", "AUTOPLAY"]
PlaybackStateValue = Literal["PLAYING", "PAUSED", "STOPPED"]


class PlaybackContext(BaseModel):
    context_id: str
    source_type: str
    source_id: str | None = None
    ordered_song_ids: tuple[str, ...]
    random_seed: int | None = None


class QueueItem(BaseModel):
    queue_item_id: str
    song_id: str
    position: int
    source: QueueItemSource
    playback_context_id: str | None = None


class PlaybackState(BaseModel):
    song_id: str | None = None
    state: PlaybackStateValue
    playback_context_id: str | None = None
    position_seconds: float | None = Field(default=None, ge=0)
    autoplay_enabled: bool = False
    updated_at: datetime
