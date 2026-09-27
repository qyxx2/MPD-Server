from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from server.app.models.library import ScanResult


class DomainEvent(BaseModel):
    event_type: str


class LibraryChangedEvent(DomainEvent):
    event_type: str = "library.changed"
    result: ScanResult
    mpd_update_error: str | None = None


class EventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...


class MPDDatabaseUpdater(Protocol):
    async def update_database(self) -> None: ...
