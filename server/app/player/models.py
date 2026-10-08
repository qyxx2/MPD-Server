from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    mpd_song_id: int
    position: int
    song_uri: str


class _ExecutionPlayerStatus(PlayerStatus):
    model_config = ConfigDict(frozen=True)


class _ExecutionQueueEntry(PlayerQueueEntry):
    model_config = ConfigDict(frozen=True)


class ExecutionSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    connection_epoch: str
    partition: str
    playlist_version: int = Field(ge=0)
    status: PlayerStatus
    entries: tuple[PlayerQueueEntry, ...]
    single: str
    consume: bool
    error: str | None = None

    @model_validator(mode="after")
    def _copy_nested_models(self) -> ExecutionSample:
        object.__setattr__(
            self,
            "status",
            _ExecutionPlayerStatus.model_validate(self.status.model_dump()),
        )
        object.__setattr__(
            self,
            "entries",
            tuple(
                _ExecutionQueueEntry.model_validate(entry.model_dump())
                for entry in self.entries
            ),
        )
        return self


class MPDStats(BaseModel):
    songs: int | None = None
    albums: int | None = None
    artists: int | None = None
    db_playtime: int | None = None
    db_update: int | None = None
    playtime: int | None = None
    uptime: int | None = None


class DatabaseUpdateStatus(BaseModel):
    updating: bool | None = None
    job_id: int | None = None


class PlayerEvent(BaseModel):
    kind: str
    status: PlayerStatus
