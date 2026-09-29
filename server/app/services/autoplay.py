from __future__ import annotations

from server.app.models.queue import PlaybackContext, QueueItem
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.queue_repository import QueueRepository


class AutoPlay:
    LOW_WATERMARK = 5
    REFILL_COUNT = 5

    def __init__(
        self,
        queue_repository: QueueRepository,
        library_repository: LibraryRepository,
    ) -> None:
        self.queue_repository = queue_repository
        self.library_repository = library_repository

    async def refill(self, playback_context: PlaybackContext) -> list[QueueItem]:
        up_next = await self.queue_repository.list_up_next()
        if len(up_next) >= self.LOW_WATERMARK:
            return []

        queue_items = await self.queue_repository.list_items()
        current_context_id = next(
            (
                item.playback_context_id
                for item in queue_items
                if item.position == 0
            ),
            None,
        )
        queued_song_ids = {item.song_id for item in queue_items}
        available_songs = await self.library_repository.list_available_songs()
        available_ids = [song.song_id for song in available_songs if song.song_id]

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

        current_song_id = next(
            (item.song_id for item in queue_items if item.position == 0),
            None,
        )
        if (
            not candidates
            and current_song_id is not None
            and current_song_id in available_set
        ):
            candidates.append(current_song_id)

        return await self.queue_repository.add_autoplay_batch(
            candidates,
            playback_context_id=playback_context.context_id,
            expected_current_context_id=current_context_id,
            max_items=self.REFILL_COUNT,
            allow_current_repeat=bool(
                current_song_id is not None
                and candidates
                and candidates[0] == current_song_id
            ),
        )
