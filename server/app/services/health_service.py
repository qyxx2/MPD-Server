from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from server.app.logging_config import log_event
from server.app.models.library_sync import LibrarySyncState
from server.app.player.ports import PlayerCommandError, PlayerPort, PlayerUnavailable
from server.app.repositories.database import read_health


class MSHealth(BaseModel):
    status: Literal['ok', 'error']


class MPDHealth(BaseModel):
    status: Literal['connected', 'unavailable', 'unknown']
    observed_at: datetime


class HealthResponse(BaseModel):
    status: Literal['ok', 'error']
    ms: MSHealth
    mpd: MPDHealth
    library_sync: LibrarySyncState | None


class HealthService:
    """Independent local/Port reads; never update, scan or use an active address as proof."""

    def __init__(
        self, database_path: str, player: PlayerPort,
        library_sync: Callable[[], LibrarySyncState], *, mpd_timeout_seconds: float = 1,
    ) -> None:
        if mpd_timeout_seconds <= 0:
            raise ValueError('health observation budget must be positive')
        self.database_path, self.player = database_path, player
        self.library_sync = library_sync
        self.mpd_timeout_seconds = mpd_timeout_seconds

    async def read(self) -> HealthResponse:
        local = 'ok'
        sync = None
        try:
            await read_health(self.database_path)
        except Exception:  # noqa: BLE001 - local failures produce typed health, no private text
            local = 'error'
            log_event('health_local_unavailable', level=30)
        try:
            sync = self.library_sync()
        except Exception:  # noqa: BLE001 - unavailable local owner is required health
            local = 'error'
            log_event('health_sync_read_failed', level=30)
        mpd = 'unknown'
        try:
            await asyncio.wait_for(self.player.status(), self.mpd_timeout_seconds)
            mpd = 'connected'
        except (PlayerUnavailable, TimeoutError, OSError):
            mpd = 'unavailable'
        except PlayerCommandError:
            # An unverified or rejected read cannot prove a connection observation.
            pass
        except Exception:  # noqa: BLE001 - unexpected Port read cannot prove connected
            log_event('health_mpd_read_failed', level=30)
        return HealthResponse(
            status=local, ms=MSHealth(status=local),
            mpd=MPDHealth(status=mpd, observed_at=datetime.now(timezone.utc)),
            library_sync=sync,
        )
