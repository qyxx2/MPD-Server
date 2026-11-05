from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from time import monotonic

from server.app.models.hardware_volume import (
    HardwareVolumeControlSource,
    HardwareVolumeObservation,
    HardwareVolumeRequestState,
    HardwareVolumeRequestStatus,
    HardwareVolumeSnapshot,
    HardwareVolumeState,
    HardwareVolumeStatus,
)
from server.app.player.capabilities import MPDCapabilities
from server.app.player.models import (
    OutputInfo,
    PlayerState,
    PlayerStatus,
)
from server.app.player.ports import PlayerCommandError, PlayerPort, PlayerUnavailable
from server.app.services.output_operation import (
    OutputOperationLifecycle,
    OutputOperationRunner,
)
from server.app.services.realtime_coordinator import RealtimeCoordinator


class HardwareVolumeError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


OutputSelector = Callable[[tuple[OutputInfo, ...]], OutputInfo | None]


class HardwareVolumeManager:
    """Own the MPD-backed hardware Mixer state and its serialized mutations."""

    def __init__(
        self,
        *,
        player: PlayerPort,
        capabilities: MPDCapabilities,
        enabled: bool,
        selector: OutputSelector | None = None,
        operation_runner: OutputOperationRunner,
        coordinator: RealtimeCoordinator | None = None,
        observation_clock: Callable[[], datetime] | None = None,
        observation_max_age: float = 6,
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self.player = player
        self.capabilities = capabilities
        self.enabled = enabled
        self.selector = selector
        self.operation_runner = operation_runner
        self._coordinator = coordinator
        self._clock = observation_clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic_clock
        self._max_age = observation_max_age
        self._observed_at: datetime | None = None
        self._sample_number = 0
        self._accepted_sample = 0
        self._generation = 0
        now = self._clock()
        self._state = HardwareVolumeState(
            status=(
                HardwareVolumeStatus.UNAVAILABLE if enabled
                else HardwareVolumeStatus.UNSUPPORTED
            ),
            updated_at=now,
            stale=False,
            error_code=None if enabled else "HARDWARE_VOLUME_NOT_CONFIGURED",
            error_message=(
                None if enabled
                else "Hardware volume is disabled by MPD_HARDWARE_VOLUME_ENABLED"
            ),
        )
        self._last_request: HardwareVolumeRequestState | None = None

    def get_cached_state(self) -> HardwareVolumeSnapshot:
        return HardwareVolumeSnapshot(
            state=self._state.model_copy(deep=True),
            last_request=self._last_request.model_copy(deep=True) if self._last_request else None,
        )

    def _observation(self) -> HardwareVolumeObservation:
        if not self.enabled:
            return HardwareVolumeObservation(
                observed_at=None,
                freshness="unknown",
                error_code="HARDWARE_VOLUME_NOT_CONFIGURED",
                error_message="Hardware volume is disabled by MPD_HARDWARE_VOLUME_ENABLED",
            )
        freshness = (
            "unknown" if self._observed_at is None
            else "stale" if self._state.stale
            else "fresh"
        )
        return HardwareVolumeObservation(
            observed_at=self._observed_at,
            freshness=freshness,
            error_code=self._state.error_code,
            error_message=self._state.error_message,
        )

    def _stage_observation(self) -> None:
        if self._coordinator is None:
            return
        snapshot = self.get_cached_state()
        observation = self._observation()
        self._coordinator.stage_observation(
            "hardware_volume",
            (
                snapshot.state.model_dump(exclude={"updated_at"}),
                (
                    snapshot.last_request.model_dump(exclude={"updated_at"})
                    if snapshot.last_request else None
                ),
                observation.model_dump(exclude={"observed_at"}),
            ),
        )

    async def get_state(self, read_timeout: float | None = None) -> HardwareVolumeSnapshot:
        if not self.enabled:
            return self.get_cached_state()

        generation = self._generation
        player = self.player
        self._sample_number += 1
        sample_number = self._sample_number
        try:
            self._require_capabilities()
            async def read():
                status = await player.status()
                outputs = tuple(await player.outputs())
                return status, outputs

            if read_timeout is None:
                status, outputs = await read()
            else:
                status, outputs = await asyncio.wait_for(read(), timeout=read_timeout)
            error: Exception | None = None
        except (HardwareVolumeError, PlayerUnavailable, PlayerCommandError, TimeoutError, ValueError) as exc:
            status, outputs, error = None, None, exc

        async def accept(_lifecycle: OutputOperationLifecycle) -> HardwareVolumeSnapshot:
            if (
                generation != self._generation
                or sample_number < self._accepted_sample
                or player is not self.player
            ):
                return self.get_cached_state()
            self._accepted_sample = sample_number
            if error is not None:
                self._mark_unavailable(*self._classify_read_error(error))
            else:
                self._accept_read(status, outputs)
            self._stage_observation()
            return self.get_cached_state()

        return await self.operation_runner(accept)

    async def get_observation(self) -> HardwareVolumeObservation:
        async def read_observation(_lifecycle: OutputOperationLifecycle) -> HardwareVolumeObservation:
            if (
                self.enabled
                and self._observed_at is not None
                and (self._clock() - self._observed_at).total_seconds() > self._max_age
                and not self._state.stale
            ):
                self._mark_unavailable(
                    "HARDWARE_VOLUME_UNAVAILABLE",
                    "The last confirmed MPD hardware-volume sample has expired",
                )
                self._stage_observation()
            return self._observation().model_copy(deep=True)

        return await self.operation_runner(read_observation)

    async def set_volume(self, volume_percent: int) -> HardwareVolumeSnapshot:
        if isinstance(volume_percent, bool) or not isinstance(volume_percent, int) or not 0 <= volume_percent <= 100:
            raise HardwareVolumeError("VALIDATION_ERROR", "volume_percent must be an integer from 0 to 100")
        if not self.enabled:
            message = "Hardware volume is disabled by MPD_HARDWARE_VOLUME_ENABLED"

            async def reject(_lifecycle: OutputOperationLifecycle) -> None:
                self._last_request = HardwareVolumeRequestState(
                    requested_percent=volume_percent,
                    status=HardwareVolumeRequestStatus.FAILED,
                    error_code="HARDWARE_VOLUME_NOT_CONFIGURED",
                    error_message=message,
                    updated_at=self._clock(),
                )
                self._stage_observation()

            # Commit the failed request fact without touching MPD. Raising
            # inside the runner would discard its after-commit invalidation.
            await self.operation_runner(reject)
            raise HardwareVolumeError("HARDWARE_VOLUME_NOT_CONFIGURED", message)

        async def mutate(lifecycle: OutputOperationLifecycle) -> HardwareVolumeSnapshot:
            self._generation += 1
            request = HardwareVolumeRequestState(
                requested_percent=volume_percent,
                status=HardwareVolumeRequestStatus.PREPARING,
                updated_at=self._clock(),
            )
            self._last_request = request

            def rollback_request() -> None:
                if self._last_request is request:
                    self._last_request = request.model_copy(update={
                        "status": HardwareVolumeRequestStatus.FAILED,
                        "error_code": "HARDWARE_VOLUME_TRANSACTION_FAILED",
                        "error_message": "The enclosing transaction did not commit",
                        "updated_at": self._clock(),
                    })
                    self._mark_unavailable(
                        "HARDWARE_VOLUME_TRANSACTION_FAILED",
                        "MPD may have applied the volume, but the enclosing transaction did not commit",
                    )

            lifecycle.on_rollback(rollback_request)
            try:
                self._require_capabilities(mutation=True)
                await self._run_preserved_volume_operation(volume_percent)
            except (Exception, asyncio.CancelledError) as exc:
                code, message = self._classify_mutation_error(exc)
                self._last_request = request.model_copy(update={
                    "status": HardwareVolumeRequestStatus.FAILED,
                    "error_code": code,
                    "error_message": message,
                    "updated_at": self._clock(),
                })
                self._mark_unavailable(code, message)
                self._stage_observation()
                if isinstance(exc, asyncio.CancelledError):
                    raise
                if isinstance(exc, HardwareVolumeError):
                    raise
                raise HardwareVolumeError(code, message) from exc
            else:
                request.status = HardwareVolumeRequestStatus.SUCCEEDED
                request.updated_at = self._clock()
                request.error_code = None
                request.error_message = None
                self._stage_observation()
                return self.get_cached_state()
            finally:
                self._generation += 1

        return await self.operation_runner(mutate)

    async def _run_preserved_volume_operation(self, volume_percent: int) -> None:
        before_start = self._monotonic()
        try:
            before = (await self.player.status()).model_copy(deep=True)
        except Exception as exc:
            raise self._as_read_error(exc) from exc
        before_end = self._monotonic()
        try:
            entries = tuple(
                entry.model_copy(deep=True) for entry in await self.player.queue_entries()
            )
            outputs = tuple(await self.player.outputs())
            target = self._select_target(outputs)
        except Exception as exc:
            if isinstance(exc, HardwareVolumeError):
                raise
            raise self._as_read_error(exc) from exc

        self._accept_read(before, outputs)
        if before.volume is None:
            raise HardwareVolumeError(
                "HARDWARE_VOLUME_UNAVAILABLE",
                "MPD status does not contain a confirmed volume value",
            )
        if not target.enabled:
            raise HardwareVolumeError(
                "HARDWARE_VOLUME_UNAVAILABLE",
                "The selected ALSA output is disabled",
            )
        if before.state != PlayerState.STOPPED and (
            not entries
            or entries[0].position != 0
            or before.song_position != 0
            or before.song_id != entries[0].mpd_song_id
            or before.song_uri != entries[0].song_uri
        ):
            raise HardwareVolumeError(
                "HARDWARE_VOLUME_RECONCILIATION_FAILED",
                "MPD current occurrence is not confirmed",
            )

        try:
            await self.player.set_volume(volume_percent)
        except (PlayerUnavailable, TimeoutError):
            raise
        except PlayerCommandError as exc:
            raise HardwareVolumeError(
                "HARDWARE_VOLUME_WRITE_FAILED",
                f"MPD rejected hardware volume write: {exc}",
            ) from exc

        after_start = self._monotonic()
        try:
            after = await self.player.status()
            after_end = self._monotonic()
            after_entries = tuple(
                entry.model_copy(deep=True) for entry in await self.player.queue_entries()
            )
            after_outputs = tuple(await self.player.outputs())
            after_target = self._select_target(after_outputs)
        except PlayerUnavailable:
            raise
        except TimeoutError:
            raise
        except Exception as exc:
            raise HardwareVolumeError(
                "HARDWARE_VOLUME_RECONCILIATION_FAILED",
                f"MPD could not confirm the hardware volume mutation: {exc}",
            ) from exc

        if after.volume != volume_percent:
            raise HardwareVolumeError(
                "HARDWARE_VOLUME_RECONCILIATION_FAILED",
                "MPD status volume did not match the requested value",
            )
        if (
            target.id != after_target.id
            or not after_target.enabled
            or (target.name, target.plugin) != (after_target.name, after_target.plugin)
        ):
            raise HardwareVolumeError(
                "HARDWARE_VOLUME_RECONCILIATION_FAILED",
                "The selected ALSA output changed during the volume operation",
            )
        # The volume itself is now confirmed even if a separate playback
        # preservation check below fails. Keep that last-known reading stale.
        self._accept_read(after, after_outputs)
        if (
            before.model_dump(exclude={"volume", "elapsed_seconds"})
            != after.model_dump(exclude={"volume", "elapsed_seconds"})
            or entries != after_entries
        ):
            raise HardwareVolumeError(
                "HARDWARE_VOLUME_RECONCILIATION_FAILED",
                "Hardware volume operation changed playback or the selected ALSA output",
            )
        if (
            before.state != PlayerState.PLAYING
            or before.elapsed_seconds is None
            or after.elapsed_seconds is None
        ) and before.elapsed_seconds != after.elapsed_seconds:
            raise HardwareVolumeError(
                "HARDWARE_VOLUME_RECONCILIATION_FAILED",
                "Hardware volume operation changed playback position",
            )
        if (
            before.state == PlayerState.PLAYING
            and before.elapsed_seconds is not None
            and after.elapsed_seconds is not None
        ):
            delta = after.elapsed_seconds - before.elapsed_seconds
            # MPD may return the same elapsed sample for two nearby status reads.
            # Require monotonic progress, not a minimum tick during this short operation.
            maximum = after_end - before_start + 0.001
            if not 0.0 <= delta <= maximum:
                raise HardwareVolumeError(
                    "HARDWARE_VOLUME_RECONCILIATION_FAILED",
                    "Playback position changed outside the volume operation window",
                )


    def _require_capabilities(self, *, mutation: bool = False) -> None:
        required = ["status", "set_volume", "outputs"]
        if mutation:
            required.append("queue_entries")
        for operation in required:
            if not self.capabilities.supports_operation(operation):
                raise HardwareVolumeError(
                    "HARDWARE_VOLUME_UNAVAILABLE",
                    f"MPD capability is not verified for {operation}",
                )

    def _select_target(self, outputs: tuple[OutputInfo, ...]) -> OutputInfo:
        candidates = tuple(output for output in outputs if output.plugin == "alsa")
        if not candidates:
            raise HardwareVolumeError(
                "HARDWARE_VOLUME_UNAVAILABLE",
                "No ALSA output is available",
            )
        if self.selector is None:
            if len(candidates) != 1:
                raise HardwareVolumeError(
                    "HARDWARE_VOLUME_OUTPUT_AMBIGUOUS",
                    "Multiple ALSA outputs require an explicit selector",
                )
            target = candidates[0]
        else:
            try:
                target = self.selector(candidates)
            except Exception as exc:
                raise HardwareVolumeError(
                    "HARDWARE_VOLUME_OUTPUT_AMBIGUOUS",
                    "The ALSA output selector failed",
                ) from exc
            if sum(candidate is target for candidate in candidates) != 1:
                raise HardwareVolumeError(
                    "HARDWARE_VOLUME_OUTPUT_AMBIGUOUS",
                    "The selector must return one current ALSA output candidate",
                )
        if sum(output.id == target.id for output in outputs) != 1:
            raise HardwareVolumeError(
                "HARDWARE_VOLUME_OUTPUT_AMBIGUOUS",
                "The selected MPD output ID is not unique",
            )
        return target

    def _accept_read(self, status: PlayerStatus, outputs: tuple[OutputInfo, ...]) -> None:
        now = self._clock()
        try:
            target = self._select_target(outputs)
        except HardwareVolumeError as exc:
            self._mark_unavailable(exc.code, str(exc))
            return
        if not target.enabled:
            self._state = HardwareVolumeState(
                status=HardwareVolumeStatus.UNAVAILABLE,
                volume_percent=self._state.volume_percent,
                output_name=target.name,
                output_plugin=target.plugin,
                output_enabled=False,
                error_code="HARDWARE_VOLUME_UNAVAILABLE",
                error_message="The selected ALSA output is disabled",
                updated_at=now,
                stale=self._state.volume_percent is not None,
            )
            return
        if status.volume is None:
            self._mark_unavailable(
                "HARDWARE_VOLUME_UNAVAILABLE",
                "MPD status does not contain a confirmed volume value",
                output=target,
            )
            return
        self._state = HardwareVolumeState(
            status=HardwareVolumeStatus.AVAILABLE,
            volume_percent=status.volume,
            output_name=target.name,
            output_plugin=target.plugin,
            output_enabled=target.enabled,
            control_source=HardwareVolumeControlSource.MPD_HARDWARE_MIXER,
            updated_at=now,
            stale=False,
        )
        self._observed_at = now

    def _mark_unavailable(
        self,
        error_code: str,
        error_message: str,
        *,
        output: OutputInfo | None = None,
    ) -> None:
        now = self._clock()
        previous = self._state
        self._state = HardwareVolumeState(
            status=HardwareVolumeStatus.UNAVAILABLE,
            volume_percent=previous.volume_percent,
            output_name=output.name if output is not None else previous.output_name,
            output_plugin=output.plugin if output is not None else previous.output_plugin,
            output_enabled=output.enabled if output is not None else previous.output_enabled,
            control_source=previous.control_source,
            error_code=error_code,
            error_message=error_message,
            updated_at=now,
            stale=previous.volume_percent is not None or self._observed_at is not None,
        )

    @staticmethod
    def _classify_read_error(exc: Exception) -> tuple[str, str]:
        if isinstance(exc, HardwareVolumeError):
            return exc.code, str(exc)
        if isinstance(exc, PlayerUnavailable):
            return "PLAYER_UNAVAILABLE", str(exc)
        if isinstance(exc, PlayerCommandError):
            return "PLAYER_COMMAND_ERROR", str(exc)
        if isinstance(exc, TimeoutError):
            return "PLAYER_TIMEOUT", str(exc)
        return "PLAYER_OBSERVATION_FAILED", str(exc)

    @staticmethod
    def _as_read_error(exc: Exception) -> HardwareVolumeError:
        code, message = HardwareVolumeManager._classify_read_error(exc)
        return HardwareVolumeError(code, message)

    @staticmethod
    def _classify_mutation_error(exc: BaseException) -> tuple[str, str]:
        if isinstance(exc, HardwareVolumeError):
            return exc.code, str(exc)
        if isinstance(exc, PlayerUnavailable):
            return "PLAYER_UNAVAILABLE", str(exc)
        if isinstance(exc, PlayerCommandError):
            if exc.command == "set_volume":
                return "HARDWARE_VOLUME_WRITE_FAILED", str(exc)
            return "PLAYER_COMMAND_ERROR", str(exc)
        if isinstance(exc, TimeoutError):
            return "PLAYER_TIMEOUT", str(exc)
        if isinstance(exc, asyncio.CancelledError):
            return "HARDWARE_VOLUME_CANCELLED", "Hardware volume mutation was cancelled"
        return "HARDWARE_VOLUME_OPERATION_FAILED", str(exc)
