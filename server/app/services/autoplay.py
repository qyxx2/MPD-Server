from __future__ import annotations

from uuid import uuid4

from server.app.models.queue import PlaybackContext, QueueItem, QueueSnapshot
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.playback_state_repository import PlaybackStateRepository
from server.app.repositories.queue_repository import (
    QueueRepository,
    QueueRevisionConflictError,
)


class AutoPlay:
    LOW_WATERMARK = 5
    REFILL_COUNT = 5
    MAX_CAS_RETRIES = 1

    def __init__(
        self,
        queue_repository: QueueRepository,
        library_repository: LibraryRepository,
        playback_state_repository: PlaybackStateRepository | None = None,
    ) -> None:
        self.queue_repository = queue_repository
        self.library_repository = library_repository
        self.playback_state_repository = playback_state_repository

    async def _autoplay_is_enabled(self) -> bool:
        if self.playback_state_repository is None:
            return True
        state = await self.playback_state_repository.get_state()
        return state is None or state.autoplay_enabled

    @staticmethod
    def _current_item(items: tuple[QueueItem, ...]):
        return next((item for item in items if item.position == 0), None)

    def _candidate_ids(
        self,
        snapshot_items: tuple[QueueItem, ...],
        playback_context: PlaybackContext,
        available_ids: list[str],
    ) -> tuple[list[str], bool]:
        queued_song_ids = {item.song_id for item in snapshot_items}
        available_set = set(available_ids)
        candidates: list[str] = []
        seen: set[str] = set()

        for song_id in playback_context.ordered_song_ids:
            if song_id in available_set and song_id not in queued_song_ids:
                candidates.append(song_id)
                seen.add(song_id)

        for song_id in available_ids:
            if song_id in seen or song_id in queued_song_ids:
                continue
            candidates.append(song_id)
            seen.add(song_id)

        current = self._current_item(snapshot_items)
        current_song_id = current.song_id if current is not None else None
        if (
            not candidates
            and current_song_id is not None
            and current_song_id in available_set
        ):
            candidates.append(current_song_id)

        allow_current_repeat = bool(
            current_song_id is not None
            and candidates
            and candidates[0] == current_song_id
        )
        return candidates, allow_current_repeat

    async def refill(self, playback_context: PlaybackContext) -> list[QueueItem]:
        if not await self._autoplay_is_enabled():
            return []

        available_songs = await self.library_repository.list_available_songs()
        available_ids = [song.song_id for song in available_songs if song.song_id]

        for attempt in range(self.MAX_CAS_RETRIES + 1):
            if not await self._autoplay_is_enabled():
                return []

            snapshot = await self.queue_repository.get_snapshot()
            up_next = [
                item for item in snapshot.items if item.position > 0
            ]
            if len(up_next) >= self.LOW_WATERMARK:
                return []

            current = self._current_item(snapshot.items)
            if (
                current is not None
                and current.playback_context_id is not None
                and current.playback_context_id != playback_context.context_id
            ):
                return []

            candidates, allow_current_repeat = self._candidate_ids(
                snapshot.items,
                playback_context,
                available_ids,
            )
            try:
                return await self.queue_repository.add_autoplay_batch(
                    candidates,
                    playback_context_id=playback_context.context_id,
                    max_items=self.REFILL_COUNT,
                    allow_current_repeat=allow_current_repeat,
                    expected_revision=snapshot.revision,
                )
            except QueueRevisionConflictError:
                if attempt >= self.MAX_CAS_RETRIES:
                    return []

        return []

    async def plan_refill(self, context: PlaybackContext, snapshot: QueueSnapshot) -> tuple[QueueItem, ...]:
        """Plan the existing candidate policy without persisting new occurrences."""
        if not await self._autoplay_is_enabled():
            return ()
        pending = [i for i in snapshot.items if i.position > 0]
        current = self._current_item(snapshot.items)
        if len(pending) >= self.LOW_WATERMARK or (
            current is not None and current.playback_context_id is not None
            and current.playback_context_id != context.context_id
        ):
            return ()
        available = await self.library_repository.list_available_songs()
        candidates, _ = self._candidate_ids(snapshot.items, context, [s.song_id for s in available if s.song_id])
        start = max((i.position for i in pending), default=0) + 1
        return tuple(QueueItem(
            queue_item_id=str(uuid4()), song_id=song_id, position=start + index,
            source="AUTOPLAY", playback_context_id=context.context_id,
        ) for index, song_id in enumerate(list(dict.fromkeys(candidates))[:self.REFILL_COUNT]))
