from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from server.app.models.mpd_info import MPDInfo, MPDInfoError
from server.app.player.capabilities import MPDCapabilities
from server.app.player.models import DatabaseUpdateStatus, MPDStats
from server.app.player.ports import PlayerCommandError, PlayerPort, PlayerUnavailable


class MPDInfoService:
    """Read MPD About facts without treating historical probe samples as live data."""

    def __init__(self, *, player: PlayerPort, capabilities: MPDCapabilities) -> None:
        self.player = player
        self.capabilities = capabilities

    async def get_info(self) -> MPDInfo:
        errors: dict[str, MPDInfoError] = {}
        stats = await self._read("stats", self.player.stats, errors)
        update = await self._read(
            "database_update_status", self.player.database_update_status, errors,
        )
        status = await self._read("status", self.player.status, errors)
        connected = None
        if status is not None:
            connected = True
        elif errors["status"].code == "PLAYER_UNAVAILABLE":
            connected = False
        return MPDInfo(
            version=self.capabilities.version,
            version_source="verified_capability" if self.capabilities.version else None,
            stats=stats if stats is not None else MPDStats(),
            database_update_status=update if update is not None else DatabaseUpdateStatus(),
            connected=connected,
            errors=errors,
            observed_at=datetime.now(timezone.utc),
        )

    async def _read[T](
        self, source: str, read: Callable[[], Awaitable[T]],
        errors: dict[str, MPDInfoError],
    ) -> T | None:
        if not self.capabilities.supports_operation(source):
            errors[source] = MPDInfoError(
                code="CAPABILITY_UNVERIFIED", message=f"MPD capability not verified for {source}",
            )
            return None
        try:
            return await read()
        except PlayerUnavailable as exc:
            errors[source] = MPDInfoError(code="PLAYER_UNAVAILABLE", message=str(exc))
        except PlayerCommandError as exc:
            errors[source] = MPDInfoError(code="PLAYER_COMMAND_ERROR", message=str(exc))
        return None
