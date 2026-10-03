from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from time import monotonic
from typing import TypeVar

from server.app.models.output import (
    OutputMode,
    OutputRequestState,
    OutputSnapshot,
    OutputState,
)
from server.app.player.capabilities import MPDCapabilities
from server.app.player.models import OutputInfo, PlayerState
from server.app.player.ports import PlayerCommandError, PlayerPort, PlayerUnavailable
from server.app.services.events import EventPublisher, OutputChangedEvent
from server.app.services.output_operation import (
    OutputOperationLifecycle,
    OutputOperationRunner,
)

T = TypeVar("T")
OutputSelector = Callable[[tuple[OutputInfo, ...]], OutputInfo | None]


class OutputError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class OutputManager:
    """Coordinate selected MPD output facts while preserving playback ownership."""

    def __init__(
        self,
        *,
        player: PlayerPort,
        capabilities: MPDCapabilities,
        operation_runner: OutputOperationRunner,
        selector: OutputSelector | None = None,
        event_publisher: EventPublisher | None = None,
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self.player = player
        self.capabilities = capabilities
        self.operation_runner = operation_runner
        self.selector = selector
        self.event_publisher = event_publisher
        self.monotonic_clock = monotonic_clock
        self._nas_observation: OutputState | None = None
        self._last_request: OutputRequestState | None = None

    async def get_state(self) -> OutputSnapshot:
        async def observe(_lifecycle: OutputOperationLifecycle) -> OutputSnapshot:
            return await self._observe()

        return await self.operation_runner(observe)

    async def _run_preserved_operation(
        self, operation: Callable[[OutputOperationLifecycle], Awaitable[T]],
    ) -> T:
        """Confirm playback preservation within the injected shared operation runner."""
        async def guarded(lifecycle: OutputOperationLifecycle) -> T:
            before_start = self.monotonic_clock()
            before = (await self.player.status()).model_copy(deep=True)
            before_end = self.monotonic_clock()
            entries = [entry.model_copy(deep=True) for entry in await self.player.queue_entries()]
            if before.state != PlayerState.STOPPED and (
                not entries
                or entries[0].position != 0
                or before.song_position != 0
                or before.song_id != entries[0].mpd_song_id
                or before.song_uri != entries[0].song_uri
            ):
                raise OutputError(
                    "OUTPUT_RECONCILIATION_FAILED", "MPD current occurrence is unconfirmed",
                )
            result = await operation(lifecycle)
            after_start = self.monotonic_clock()
            after = await self.player.status()
            after_end = self.monotonic_clock()
            after_entries = await self.player.queue_entries()
            if (
                before.model_dump(exclude={"elapsed_seconds"})
                != after.model_dump(exclude={"elapsed_seconds"})
                or entries != after_entries
            ):
                raise OutputError("OUTPUT_RECONCILIATION_FAILED", "Output operation changed playback")
            if (
                before.state != PlayerState.PLAYING
                or before.elapsed_seconds is None
                or after.elapsed_seconds is None
            ) and before.elapsed_seconds != after.elapsed_seconds:
                raise OutputError("OUTPUT_RECONCILIATION_FAILED", "Output operation changed position")
            if (
                before.state == PlayerState.PLAYING
                and before.elapsed_seconds is not None
                and after.elapsed_seconds is not None
            ):
                delta = after.elapsed_seconds - before.elapsed_seconds
                # MPD elapsed has millisecond precision. Bracket each status read
                # to include transport latency; never allow a backwards reset.
                minimum = max(0.0, after_start - before_end - 0.001)
                maximum = after_end - before_start + 0.001
                if not minimum <= delta <= maximum:
                    raise OutputError(
                        "OUTPUT_RECONCILIATION_FAILED", "Playback position did not advance naturally",
                    )
            return result

        return await self.operation_runner(guarded)

    async def set_enabled(self, mode: OutputMode, enabled: bool) -> OutputSnapshot:
        if mode == OutputMode.CLIENT_STREAM:
            raise OutputError("OUTPUT_MODE_UNSUPPORTED", "Client streaming is not supported in v0.1")
        async def execute(lifecycle: OutputOperationLifecycle) -> OutputSnapshot:
            self._last_request = OutputRequestState(
                mode=mode, enabled=enabled, status="PREPARING", updated_at=datetime.now(timezone.utc),
            )
            request = self._last_request

            def rollback_request() -> None:
                if self._last_request is request:
                    self._fail_request(OutputError(
                        "OUTPUT_TRANSACTION_FAILED", "Output request transaction did not commit",
                    ))
                    if self._nas_observation is not None:
                        self._nas_observation.stale = True

            lifecycle.on_rollback(rollback_request)
            try:
                return await self._ensure_enabled(lifecycle, enabled)
            except (Exception, asyncio.CancelledError) as exc:
                self._fail_request(exc)
                await self._observe()
                raise

        return await self.operation_runner(execute)

    def _fail_request(self, exc: BaseException) -> None:
        code = (
            exc.code if isinstance(exc, OutputError)
            else "OUTPUT_CANCELLED" if isinstance(exc, asyncio.CancelledError)
            else "PLAYER_UNAVAILABLE" if isinstance(exc, PlayerUnavailable)
            else "PLAYER_COMMAND_ERROR" if isinstance(exc, PlayerCommandError)
            else "OUTPUT_OPERATION_FAILED"
        )
        self._last_request = self._last_request.model_copy(update={
            "status": "SWITCH_FAILED", "error_code": code, "error_message": str(exc),
            "updated_at": datetime.now(timezone.utc),
        })

    async def _ensure_enabled(
        self, lifecycle: OutputOperationLifecycle, enabled: bool,
    ) -> OutputSnapshot:
        for operation in ("outputs", "set_output_enabled", "status", "queue_entries"):
            if not self.capabilities.supports_operation(operation):
                raise OutputError(
                    "OUTPUT_CAPABILITY_UNVERIFIED", f"Output operation requires {operation}",
                )
        changed = False

        async def ensure(_lifecycle: OutputOperationLifecycle) -> OutputSnapshot:
            nonlocal changed
            outputs = tuple(output.model_copy(deep=True) for output in await self.player.outputs())
            self._observe_outputs(outputs, datetime.now(timezone.utc))
            target = self._select_target(outputs)
            changed = target.enabled != enabled
            if changed:
                await self.player.set_output_enabled(target.id, enabled)
            confirmed = tuple(await self.player.outputs())
            self._observe_outputs(confirmed, datetime.now(timezone.utc))
            actual = self._select_target(confirmed)
            expected = tuple(
                output.model_copy(update={"enabled": enabled}) if output.id == target.id else output
                for output in outputs
            )
            if actual.id != target.id or actual.enabled != enabled or confirmed != expected:
                raise OutputError(
                    "OUTPUT_RECONCILIATION_FAILED", "MPD output state did not confirm requested state",
                )
            return self._snapshot(self._nas_observation, datetime.now(timezone.utc))

        snapshot = await self._run_preserved_operation(ensure)
        self._last_request.status = "SUCCEEDED"
        self._last_request.updated_at = datetime.now(timezone.utc)
        snapshot.last_request = self._last_request.model_copy(deep=True)
        if changed and self.event_publisher is not None:
            event = OutputChangedEvent(snapshot=snapshot)
            lifecycle.on_commit(lambda: self.event_publisher.publish(event))
        return snapshot

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

        return self._observe_outputs(tuple(outputs), now)

    def _observe_outputs(self, outputs: tuple[OutputInfo, ...], now: datetime) -> OutputSnapshot:
        try:
            target = self._select_target(outputs)
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
            nas.model_copy(deep=True),
            OutputState(
                mode=OutputMode.CLIENT_STREAM,
                status="UNAVAILABLE",
                error_code="OUTPUT_MODE_UNSUPPORTED",
                error_message="Client streaming is not supported in v0.1",
                updated_at=now,
            ),
        ), last_request=self._last_request.model_copy(deep=True) if self._last_request else None)

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
