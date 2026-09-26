from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PlayerState(str, Enum):
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"


class PlayerStatus(BaseModel):
    state: PlayerState
    song_uri: str | None = None
    song_position: int | None = Field(default=None, ge=0)
    song_id: int | None = Field(default=None, ge=0)
    elapsed_seconds: float | None = Field(default=None, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    volume: int | None = Field(default=None, ge=0, le=100)
    repeat: bool = False
    random: bool = False


class OutputInfo(BaseModel):
    id: int = Field(ge=0)
    name: str
    plugin: str
    enabled: bool
    attributes: dict[str, str] = Field(default_factory=dict)


class PlayerQueueEntry(BaseModel):
    mpd_song_id: int = Field(ge=0)
    position: int = Field(ge=0)
    song_uri: str


class MPDStats(BaseModel):
    songs: int | None = Field(default=None, ge=0)
    albums: int | None = Field(default=None, ge=0)
    artists: int | None = Field(default=None, ge=0)
    db_playtime: int | None = Field(default=None, ge=0)
    db_update: int | None = Field(default=None, ge=0)
    playtime: int | None = Field(default=None, ge=0)
    uptime: int | None = Field(default=None, ge=0)


class DatabaseUpdateStatus(BaseModel):
    updating: bool | None = None
    job_id: int | None = Field(default=None, ge=0)


class PlayerEvent(BaseModel):
    kind: str
    status: PlayerStatus
