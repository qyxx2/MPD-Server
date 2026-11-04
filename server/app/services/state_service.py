from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from server.app.models.hardware_volume import (
    HardwareVolumeObservation,
    HardwareVolumeSnapshot,
    HardwareVolumeState,
    HardwareVolumeStatus,
)
from server.app.models.output import OutputSnapshot
from server.app.models.realtime import (
    FullStateSnapshot,
    OutputObservation,
    PlaybackObservation,
)
from server.app.repositories.database import (
    on_transaction_visible,
    run_transaction,
    transaction_identity,
)
from server.app.services.history_service import HistoryService
from server.app.services.library_service import LibraryService
from server.app.services.playback_service import PlaybackService
from server.app.services.queue_manager import QueueManager
from server.app.services.realtime_coordinator import RealtimeCoordinator


class StateService:
    """Capture local Service state and revisions under the shared commit boundary."""

    def __init__(
        self,
        *,
        coordinator: RealtimeCoordinator,
        queue_manager: QueueManager,
        history_service: HistoryService,
        library_service: LibraryService,
        output_snapshot: Callable[[], OutputSnapshot],
        playback_service: PlaybackService | None = None,
        output_observation: Callable[[], Awaitable[OutputObservation]] | None = None,
        hardware_volume_snapshot: Callable[[], HardwareVolumeSnapshot] | None = None,
        hardware_volume_observation: Callable[[], Awaitable[HardwareVolumeObservation]] | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._queue = queue_manager
        self._history = history_service
        self._library = library_service
        # A synchronous cached Service read, never an external observation call.
        self._output_snapshot = output_snapshot
        self._playback = playback_service
        self._output_observation = output_observation
        # Test and partial-composition callers without a hardware manager get
        # an explicit unsupported/unknown value, never an invented zero.
        unavailable_message = "Hardware volume manager is not configured"
        self._default_hardware_volume = HardwareVolumeSnapshot(
            state=HardwareVolumeState(
                status=HardwareVolumeStatus.UNSUPPORTED,
                error_code="HARDWARE_VOLUME_NOT_CONFIGURED",
                error_message=unavailable_message,
                updated_at=datetime.now(timezone.utc),
            ),
        )
        self._hardware_volume_snapshot = hardware_volume_snapshot or (
            lambda: self._default_hardware_volume.model_copy(deep=True)
        )
        async def default_hardware_volume_observation() -> HardwareVolumeObservation:
            return HardwareVolumeObservation(
                freshness="unknown",
                error_code="HARDWARE_VOLUME_NOT_CONFIGURED",
                error_message=unavailable_message,
            )

        self._hardware_volume_observation = (
            hardware_volume_observation or default_hardware_volume_observation
        )

    async def get_full_snapshot(self) -> FullStateSnapshot:
        # Joining a caller's owner can export pending data with a committed marker.
        # Capture owns a fresh read boundary; only its internal Service reads nest.
        try:
            transaction_identity(self._coordinator.path)
        except RuntimeError:
            pass
        else:
            raise RuntimeError("Full snapshot requires a committed read boundary")

        async def capture(_):
            playback = await self._queue.get_playback_state()
            queue = await self._queue.get_snapshot()
            history = await self._history.get_availability()
            song = None
            if playback is not None and playback.song_id is not None:
                song = await self._library.get_song(playback.song_id)
                if song is None:
                    raise LookupError(f"Current Song is missing from Library: {playback.song_id}")
            output_observation = (await self._output_observation()
                                  if self._output_observation else OutputObservation())
            output = self._output_snapshot()
            hardware_volume_observation = await self._hardware_volume_observation()
            hardware_volume = self._hardware_volume_snapshot()
            observation = (await self._playback.get_observation()
                           if self._playback is not None else PlaybackObservation())
            marker = self._coordinator.marker()
            snapshot = FullStateSnapshot(
                epoch=marker.epoch, sequence=marker.sequence,
                explicit_stop_generation=(self._playback.explicit_stop_generation
                                          if self._playback is not None else None),
                captured_at=datetime.now(timezone.utc),
                revisions={"library": marker.library_revision, "playlist": marker.playlist_revision},
                playback=playback, current_song=song, queue=queue, history=history, output=output,
                playback_observation=observation,
                output_observation=output_observation,
                hardware_volume=hardware_volume,
                hardware_volume_observation=hardware_volume_observation,
                library_sync=self._coordinator.get_library_sync(),
            ).model_copy(deep=True)

            def committed_marker():
                # Cache expiry may stage a change in this capture. Attach its
                # visible waterline after registration, before releasing the lock.
                marker = self._coordinator.marker()
                snapshot.sequence = marker.sequence
                snapshot.revisions = {
                    'library': marker.library_revision, 'playlist': marker.playlist_revision,
                }

            on_transaction_visible(self._coordinator.path, committed_marker)
            return snapshot

        snapshot = await run_transaction(self._coordinator.path, capture)
        self._coordinator.marker()  # Fail closed if visibility registration failed.
        return snapshot
