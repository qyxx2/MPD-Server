from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Protocol, TypeVar

from server.app.models.output import OutputMode, OutputSnapshot, OutputState
from server.app.player.capabilities import MPDCapabilities
from server.app.player.models import OutputInfo
from server.app.player.ports import PlayerCommandError, PlayerPort, PlayerUnavailable
from server.app.services.events import EventPublisher

T = TypeVar("T")
OutputSelector = Callable[[tuple[OutputInfo, ...]], OutputInfo | None]


class OutputOperationRunner(Protocol):
    async def __call__(self, operation: Callable[[], Awaitable[T]]) -> T: ...


class OutputError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class OutputManager:
    """Observe MPD output facts without taking ownership of playback state."""

    def __init__(
        self,
        *,
        player: PlayerPort,
        capabilities: MPDCapabilities,
        operation_runner: OutputOperationRunner,
        selector: OutputSelector | None = None,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self.player = player
        self.capabilities = capabilities
        self.operation_runner = operation_runner
        self.selector = selector
        self.event_publisher = event_publisher
        self._nas_observation: OutputState | None = None

    async def get_state(self) -> OutputSnapshot:
        return await self.operation_runner(self._observe)

    async def set_enabled(self, mode: OutputMode, enabled: bool) -> OutputSnapshot:
        if mode == OutputMode.CLIENT_STREAM:
            raise OutputError("OUTPUT_MODE_UNSUPPORTED", "Client streaming is not supported in v0.1")
        raise OutputError("OUTPUT_CONTROL_UNAVAILABLE", "NAS output control is not implemented yet")

    async def _observe(self) -> OutputSnapshot:
        now = datetime.now(timezone.utc)
        try:
            if not self.capabilities.supports_operation("outputs"):
                raise OutputError("OUTPUT_CAPABILITY_UNVERIFIED", "Output reading capability is unavailable")
            outputs = await self.player.outputs()
        except (OutputError, PlayerUnavailable, PlayerCommandError) as exc:
            code = (
                exc.code if isinstance(exc, OutputError)
                else "PLAYER_UNAVAILABLE" if isinstance(exc, PlayerUnavailable)
                else "PLAYER_COMMAND_ERROR"
            )
            nas = self._nas_observation.model_copy(deep=True) if self._nas_observation else OutputState(
                mode=OutputMode.NAS_DAC, status="UNAVAILABLE", updated_at=now,
            )
            nas.stale = True
            nas.error_code = code
            nas.error_message = str(exc)
            return self._snapshot(nas, now)

        try:
            target = self._select_target(tuple(outputs))
        except OutputError as exc:
            nas = OutputState(
                mode=OutputMode.NAS_DAC, status="UNAVAILABLE",
                error_code=exc.code, error_message=str(exc), updated_at=now,
            )
        else:
            nas = OutputState(
                mode=OutputMode.NAS_DAC,
                status="ACTIVE" if target.enabled else "INACTIVE", updated_at=now,
            )
        self._nas_observation = nas.model_copy(deep=True)
        return self._snapshot(nas, now)

    def _snapshot(self, nas: OutputState, now: datetime) -> OutputSnapshot:
        return OutputSnapshot(states=(
            nas,
            OutputState(
                mode=OutputMode.CLIENT_STREAM,
                status="UNAVAILABLE",
                error_code="OUTPUT_MODE_UNSUPPORTED",
                error_message="Client streaming is not supported in v0.1",
                updated_at=now,
            ),
        ))

    def _select_target(self, outputs: tuple[OutputInfo, ...]) -> OutputInfo:
        candidates = tuple(output for output in outputs if output.plugin == "alsa")
        if not candidates:
            raise OutputError("OUTPUT_UNAVAILABLE", "No ALSA output is available")
        if self.selector is None:
            if len(candidates) != 1:
                raise OutputError("OUTPUT_AMBIGUOUS", "Multiple ALSA outputs require a selector")
            target = candidates[0]
        else:
            try:
                target = self.selector(candidates)
            except Exception as exc:
                raise OutputError("OUTPUT_SELECTION_FAILED", "Output selector failed") from exc
            if sum(candidate is target for candidate in candidates) != 1:
                raise OutputError("OUTPUT_SELECTION_FAILED", "Selector must return one current candidate")
        if sum(output.id == target.id for output in outputs) != 1:
            raise OutputError("OUTPUT_AMBIGUOUS", "Selected output ID is not unique")
        return target
