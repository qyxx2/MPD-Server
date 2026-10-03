from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, field_validator

from server.app.models.library import ScanResult
from server.app.models.output import OutputSnapshot


class DomainEvent(BaseModel):
    event_type: str


class LibraryChangedEvent(DomainEvent):
    event_type: str = "library.changed"
    result: ScanResult
    mpd_update_error: str | None = None


class PlaylistChangedEvent(DomainEvent):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["playlist.changed"] = "playlist.changed"


class OutputChangedEvent(DomainEvent):
    model_config = ConfigDict(frozen=True)

    event_type: Literal["output.changed"] = "output.changed"
    snapshot: OutputSnapshot

    @field_validator("snapshot")
    @classmethod
    def own_snapshot(cls, snapshot: OutputSnapshot) -> OutputSnapshot:
        return snapshot.model_copy(deep=True)


def invalidation_domains(event: DomainEvent) -> frozenset[str]:
    """Route existing events without treating their possibly delayed payload as state."""
    if isinstance(event, LibraryChangedEvent):
        return frozenset({"library"})
    if isinstance(event, PlaylistChangedEvent):
        return frozenset({"playlist"})
    if isinstance(event, OutputChangedEvent):
        return frozenset({"output"})
    return frozenset()


class EventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...


class MPDDatabaseUpdater(Protocol):
    async def update_database(self) -> None: ...
