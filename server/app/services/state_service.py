from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from server.app.models.output import OutputSnapshot
from server.app.models.realtime import FullStateSnapshot, PlaybackObservation
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
    ) -> None:
        self._coordinator = coordinator
        self._queue = queue_manager
        self._history = history_service
        self._library = library_service
        # A synchronous cached Service read, never an external observation call.
        # OutputManager cache/lifecycle wiring belongs to Batch 9.
        self._output_snapshot = output_snapshot
        self._playback = playback_service

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
            output = self._output_snapshot()
            observation = (await self._playback.get_observation()
                           if self._playback is not None else PlaybackObservation())
            marker = self._coordinator.marker()
            snapshot = FullStateSnapshot(
                epoch=marker.epoch, sequence=marker.sequence,
                captured_at=datetime.now(timezone.utc),
                revisions={"library": marker.library_revision, "playlist": marker.playlist_revision},
                playback=playback, current_song=song, queue=queue, history=history, output=output,
                playback_observation=observation,
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
