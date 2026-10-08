from __future__ import annotations

import uuid
from datetime import datetime, timezone

from server.app.models.queue import (
    PlaybackContext,
    PlaybackState,
    QueueItem,
    QueueSnapshot,
)
from server.app.repositories.database import run_transaction
from server.app.repositories.playback_state_repository import PlaybackStateRepository
from server.app.repositories.playlist_repository import PlaylistRepository
from server.app.repositories.queue_repository import (
    CurrentTrackDeletionError,
    QueueItemNotFoundError,
    QueueRepository,
    QueueRevisionConflictError,
)

__all__ = [
    "CurrentTrackDeletionError",
    "QueueItemNotFoundError",
    "QueueManager",
    "QueueRevisionConflictError",
]


class QueueManager:
    """Owns Queue business semantics without becoming the MPD orchestrator."""

    def __init__(
        self,
        queue_repository: QueueRepository,
        playback_state_repository: PlaybackStateRepository,
        playlist_repository: PlaylistRepository,
    ) -> None:
        self.queue_repository = queue_repository
        self.playback_state_repository = playback_state_repository
        self.playlist_repository = playlist_repository

    async def adopt_current(
        self, previous_id: str, target_id: str, *, expected_revision: int,
    ) -> QueueSnapshot:
        return await self.queue_repository.adopt_current(
            previous_id, target_id, expected_revision=expected_revision,
        )

    async def complete_current(
        self, queue_item_id: str, *, pending: tuple[QueueItem, ...],
        successor_id: str | None, expected_revision: int,
    ) -> QueueSnapshot:
        return await self.queue_repository.complete_current(
            queue_item_id, pending=pending, successor_id=successor_id,
            expected_revision=expected_revision,
        )

    async def start_track(
        self,
        song_id: str,
        *,
        expected_revision: int | None = None,
        persist_state: bool = True,
        context_id: str | None = None,
    ) -> PlaybackContext:
        context = PlaybackContext(
            context_id=context_id or str(uuid.uuid4()),
            source_type="TRACK",
            source_id=song_id,
            ordered_song_ids=(song_id,),
        )
        await self.queue_repository.start_track(
            song_id=song_id,
            playback_context_id=context.context_id,
            expected_revision=expected_revision,
        )
        if persist_state:
            await self.playback_state_repository.save(
                PlaybackState(
                    song_id=song_id,
                    state="PLAYING",
                    playback_context_id=context.context_id,
                    autoplay_enabled=True,
                    position_seconds=0.0,
                    updated_at=datetime.now(timezone.utc),
                )
            )
        return context


    async def replace_with_context(
        self,
        context: PlaybackContext,
        *,
        expected_revision: int | None = None,
    ) -> list[QueueItem]:
        return await self.queue_repository.replace_with_context(
            context,
            expected_revision=expected_revision,
        )

    async def play_now(
        self,
        queue_item_id: str,
        *,
        expected_revision: int | None = None,
        persist_state: bool = True,
    ) -> QueueItem:
        current_state = await self.playback_state_repository.get_state()
        item = await self.queue_repository.play_now(
            queue_item_id,
            expected_revision=expected_revision,
        )
        if persist_state:
            await self.playback_state_repository.save(
                PlaybackState(
                    song_id=item.song_id,
                    state="PLAYING",
                    playback_context_id=item.playback_context_id
                    or (
                        current_state.playback_context_id
                        if current_state is not None
                        else None
                    ),
                    autoplay_enabled=(
                        current_state.autoplay_enabled
                        if current_state is not None
                        else True
                    ),
                    position_seconds=0.0,
                    updated_at=datetime.now(timezone.utc),
                )
            )
        return item

    async def play_next(
        self,
        song_id: str,
        *,
        expected_revision: int | None = None,
    ) -> QueueItem:
        state = await self.playback_state_repository.get_state()
        return await self.queue_repository.play_next(
            song_id,
            playback_context_id=(
                state.playback_context_id if state is not None else None
            ),
            expected_revision=expected_revision,
        )

    async def add_to_queue(
        self,
        song_id: str,
        *,
        expected_revision: int | None = None,
    ) -> QueueItem:
        state = await self.playback_state_repository.get_state()
        return await self.queue_repository.add_to_queue(
            song_id,
            playback_context_id=(
                state.playback_context_id if state is not None else None
            ),
            expected_revision=expected_revision,
        )

    async def reorder(
        self,
        queue_item_id: str,
        before_queue_item_id: str | None = None,
        *,
        expected_revision: int | None = None,
    ) -> list[QueueItem]:
        return await self.queue_repository.reorder(
            queue_item_id,
            before_queue_item_id,
            expected_revision=expected_revision,
        )

    async def delete(
        self,
        queue_item_id: str,
        *,
        expected_revision: int | None = None,
        persist_state: bool = True,
        allow_no_successor: bool = False,
    ) -> QueueItem | None:
        state = await self.playback_state_repository.get_state()
        selected = await self.queue_repository.get_item(queue_item_id)
        if selected is None:
            raise QueueItemNotFoundError(queue_item_id)

        promoted = await self.queue_repository.delete_item(
            queue_item_id,
            expected_revision=expected_revision,
            allow_no_successor=allow_no_successor,
        )
        if persist_state and selected.position == 0 and promoted is not None:
            await self.playback_state_repository.save(
                PlaybackState(
                    song_id=promoted.song_id,
                    state="PLAYING",
                    playback_context_id=(
                        state.playback_context_id
                        if state is not None
                        else promoted.playback_context_id
                    ),
                    autoplay_enabled=(
                        state.autoplay_enabled if state is not None else True
                    ),
                    position_seconds=0.0,
                    updated_at=datetime.now(timezone.utc),
                )
            )
        return promoted

    async def clear(
        self,
        *,
        expected_revision: int | None = None,
    ) -> None:
        await self.queue_repository.clear_pending(
            expected_revision=expected_revision,
        )

    async def pause(self) -> PlaybackState | None:
        state = await self.playback_state_repository.get_state()
        if state is None or state.state == "STOPPED":
            return state
        return await self.playback_state_repository.save(
            state.model_copy(
                update={
                    "state": "PAUSED",
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        )

    async def stop(self) -> PlaybackState | None:
        state = await self.playback_state_repository.get_state()
        if state is None or state.state == "STOPPED":
            return state
        return await self.playback_state_repository.save(
            state.model_copy(
                update={
                    "state": "STOPPED",
                    "autoplay_enabled": False,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        )

    async def get_playback_state(self) -> PlaybackState | None:
        return await self.playback_state_repository.get_state()

    async def set_playback_state(self, state: PlaybackState) -> PlaybackState:
        return await self.playback_state_repository.save(state)

    async def list_items(self) -> list[QueueItem]:
        return await self.queue_repository.list_items()

    async def get_snapshot(self) -> QueueSnapshot:
        return await self.queue_repository.get_snapshot()

    async def get_item(self, queue_item_id: str) -> QueueItem | None:
        return await self.queue_repository.get_item(queue_item_id)

    async def save_as_playlist(self, name: str):
        async def operation(_):
            up_next = await self.queue_repository.list_up_next()
            song_ids = [item.song_id for item in up_next]
            if len(song_ids) != len(set(song_ids)):
                raise ValueError("Queue Up Next contains duplicate songs")

            playlist = await self.playlist_repository.create_playlist(name)
            for position, song_id in enumerate(song_ids):
                await self.playlist_repository.add_song(
                    playlist.playlist_id,
                    song_id,
                    position=position,
                )
            return playlist

        return await run_transaction(self.queue_repository.path, operation)
