from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from functools import wraps
from typing import Concatenate, ParamSpec, TypeVar

from server.app.models.library import Song
from server.app.models.queue import PlaybackContext, PlaybackState, QueueItem
from server.app.player.models import PlayerState, PlayerStatus
from server.app.player.ports import PlayerPort
from server.app.repositories.database import run_transaction
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.queue_repository import QueueRevisionConflictError
from server.app.services.autoplay import AutoPlay
from server.app.services.history_service import HistoryService
from server.app.services.queue_manager import QueueItemNotFoundError, QueueManager

logger = logging.getLogger(__name__)
P = ParamSpec("P")
T = TypeVar("T")


def _atomic_history_transition(
    operation: Callable[Concatenate[PlaybackService, P], Awaitable[T]],
) -> Callable[Concatenate[PlaybackService, P], Awaitable[T]]:
    """Join the owning transaction, including its in-memory History rollback."""
    @wraps(operation)
    async def wrapped(self: PlaybackService, *args: P.args, **kwargs: P.kwargs) -> T:
        async def transition(_connection):
            self.history_service.preserve_active_on_rollback()
            return await operation(self, *args, **kwargs)

        return await run_transaction(self.queue_manager.queue_repository.path, transition)

    return wrapped


class PlaybackSongNotFoundError(ValueError):
    """A requested Song identity is absent from the library."""


class PlaybackSongUnavailableError(ValueError):
    """A known requested Song currently cannot be played."""


class PlaybackReconciliationError(RuntimeError):
    """Raised when MPD reports a different state than the requested action."""


class PlaybackService:
    """Orchestrates authoritative Queue/History/AutoPlay state with PlayerPort."""

    def __init__(
        self,
        *,
        queue_manager: QueueManager,
        history_service: HistoryService,
        autoplay: AutoPlay,
        player: PlayerPort,
        library_repository: LibraryRepository,
    ) -> None:
        self.queue_manager = queue_manager
        self.history_service = history_service
        self.autoplay = autoplay
        self.player = player
        self.library_repository = library_repository

    @_atomic_history_transition
    async def start_track(self, song_id: str) -> PlaybackContext:
        song = await self._require_available_song(song_id)
        await self._prepare_play(song)

        context = await self.queue_manager.start_track(
            song_id,
            persist_state=False,
        )
        status = await self.player.status()
        await self._save_confirmed_playing(
            song_id,
            context_id=context.context_id,
            status=status,
        )
        await self.history_service.start_track(song_id)
        await self.autoplay.refill(context)
        await self._sync_player_queue()
        await self._confirm_preserved_state()
        return context

    @_atomic_history_transition
    async def play_context(
        self,
        context: PlaybackContext,
    ) -> PlaybackState | None:
        if not context.ordered_song_ids:
            return await self.queue_manager.get_playback_state()

        songs = [
            await self._require_available_song(song_id)
            for song_id in context.ordered_song_ids
        ]

        await self.queue_manager.replace_with_context(context)

        status = await self._prepare_play(songs[0])
        state = await self._save_confirmed_playing(
            context.ordered_song_ids[0],
            context_id=context.context_id,
            status=status,
        )
        await self.history_service.start_track(songs[0].song_id)
        await self.autoplay.refill(context)
        await self._sync_player_queue()
        await self._confirm_preserved_state()
        return state

    @_atomic_history_transition
    async def play_now(self, queue_item_id: str) -> QueueItem:
        item = await self.queue_manager.get_item(queue_item_id)
        if item is None:
            raise QueueItemNotFoundError(queue_item_id)
        song = await self._require_available_song(item.song_id)
        await self._prepare_play(song)

        current_state = await self.queue_manager.get_playback_state()
        selected = await self.queue_manager.play_now(
            queue_item_id,
            persist_state=False,
        )
        status = await self.player.status()
        await self._save_confirmed_playing(
            selected.song_id,
            context_id=(
                selected.playback_context_id
                or (
                    current_state.playback_context_id
                    if current_state is not None
                    else None
                )
            ),
            status=status,
            autoplay_enabled=(
                current_state.autoplay_enabled
                if current_state is not None
                else True
            ),
        )
        await self.history_service.start_track(selected.song_id)
        await self._sync_player_queue()
        await self._confirm_preserved_state()
        return selected

    async def play_next(self, song_id: str) -> QueueItem:
        song = await self._require_available_song(song_id)
        item = await self.queue_manager.play_next(song.song_id)
        await self._sync_player_queue()
        return item

    async def add_to_queue(self, song_id: str) -> QueueItem:
        song = await self._require_available_song(song_id)
        item = await self.queue_manager.add_to_queue(song.song_id)
        await self._sync_player_queue()
        return item

    async def reorder(
        self,
        queue_item_id: str,
        before_queue_item_id: str | None = None,
        *,
        expected_revision: int | None = None,
    ) -> list[QueueItem]:
        async def operation(_connection):
            items = await self.queue_manager.reorder(
                queue_item_id,
                before_queue_item_id,
                expected_revision=expected_revision,
            )
            await self._sync_player_queue()
            await self._confirm_preserved_state()
            return items

        return await run_transaction(
            self.queue_manager.queue_repository.path, operation,
        )

    async def clear(self, *, expected_revision: int | None = None) -> None:
        async def operation(_connection):
            await self.queue_manager.clear(expected_revision=expected_revision)
            await self._refill_empty_pending()
            await self._sync_player_queue()
            await self._confirm_preserved_state()

        await run_transaction(self.queue_manager.queue_repository.path, operation)

    async def delete(
        self,
        queue_item_id: str,
        *,
        expected_revision: int | None = None,
    ) -> QueueItem | None:
        async def operation(_connection):
            snapshot = await self.queue_manager.queue_repository.get_snapshot()
            if expected_revision is not None and snapshot.revision != expected_revision:
                raise QueueRevisionConflictError(expected_revision, snapshot.revision)
            selected = await self.queue_manager.get_item(queue_item_id)
            if selected is None:
                raise QueueItemNotFoundError(queue_item_id)
            state = await self.queue_manager.get_playback_state()
            self.history_service.preserve_active_on_rollback()
            if selected.position != 0:
                await self.queue_manager.delete(
                    queue_item_id,
                    expected_revision=expected_revision,
                    persist_state=False,
                )
                await self._refill_empty_pending()
                await self._sync_player_queue()
                await self._confirm_preserved_state()
                return None

            # Resolve availability before promoting a successor. Played is independent.
            for item in snapshot.items:
                if item.position > 0:
                    song = await self.library_repository.get_song(item.song_id)
                    if song is None or song.availability_status != "AVAILABLE":
                        await self.queue_manager.delete(
                            item.queue_item_id, persist_state=False,
                        )
            await self._refill_empty_pending()
            promoted = await self.queue_manager.delete(
                queue_item_id,
                persist_state=False,
                allow_no_successor=True,
            )
            context_id = (
                state.playback_context_id if state else selected.playback_context_id
            )
            if promoted is None:
                await self.player.stop()
                status = await self.player.status()
                if status.state != PlayerState.STOPPED:
                    raise PlaybackReconciliationError("MPD did not confirm stopped state")
                await self._sync_player_queue()
                status = await self.player.status()
                if status.state != PlayerState.STOPPED:
                    raise PlaybackReconciliationError("MPD did not remain stopped")
                await self._save_confirmed_status(status, context_id=context_id)
                await self.history_service.stop()
            elif state is not None and state.state == "STOPPED":
                await self._sync_player_queue()
                await self._confirm_preserved_state()
                await self._save_confirmed_status(
                    await self.player.status(), context_id=context_id,
                    autoplay_enabled=False,
                )
            else:
                song = await self._require_available_song(promoted.song_id)
                await self._prepare_play(song)
                await self._sync_player_queue()
                status = await self.player.status()
                if (
                    status.state != PlayerState.PLAYING
                    or status.song_uri != song.file_uri
                ):
                    raise PlaybackReconciliationError("MPD did not retain the successor")
                await self._confirm_current_occurrence(status)
                await self._save_confirmed_playing(
                    promoted.song_id,
                    context_id=promoted.playback_context_id or context_id,
                    status=status,
                    autoplay_enabled=state.autoplay_enabled if state else True,
                )
                await self.history_service.start_track(promoted.song_id)
            return promoted

        return await run_transaction(
            self.queue_manager.queue_repository.path, operation,
        )

    async def _confirm_preserved_state(self) -> None:
        state = await self.queue_manager.get_playback_state()
        status = await self.player.status()
        if state is None:
            return
        expected = PlayerState(state.state.lower())
        song = (
            await self.library_repository.get_song(state.song_id) if state.song_id else None
        )
        if status.state != expected or (
            expected != PlayerState.STOPPED
            and (song is None or status.song_uri != song.file_uri)
        ):
            raise PlaybackReconciliationError("Queue mutation changed actual playback state")
        if expected != PlayerState.STOPPED:
            await self._confirm_current_occurrence(status)

    async def _confirm_current_occurrence(self, status: PlayerStatus) -> None:
        entries = await self.player.queue_entries()
        if (
            not entries
            or status.song_position != 0
            or status.song_id != entries[0].mpd_song_id
        ):
            raise PlaybackReconciliationError("MPD current occurrence differs from Server Queue")

    async def _refill_empty_pending(self) -> None:
        state = await self.queue_manager.get_playback_state()
        if state is None or state.state == "STOPPED" or not state.autoplay_enabled:
            return
        if any(item.position > 0 for item in await self.queue_manager.list_items()):
            return
        await self.autoplay.refill(await self._queue_playback_context(state))

    @_atomic_history_transition
    async def next(self) -> PlaybackState | None:
        state = await self.queue_manager.get_playback_state()
        if state is None or state.state == "STOPPED":
            return state

        target = await self._next_available_pending()
        if target is None:
            context = await self._queue_playback_context(state)
            await self.autoplay.refill(context)
            target = await self._next_available_pending()
        if target is None:
            await self._sync_player_queue()
            await self._confirm_preserved_state()
            return state

        song = await self._require_available_song(target.song_id)
        await self._prepare_play(song)
        selected = await self.queue_manager.play_now(
            target.queue_item_id,
            persist_state=False,
        )
        status = await self.player.status()
        await self._save_confirmed_playing(
            selected.song_id,
            context_id=selected.playback_context_id or state.playback_context_id,
            status=status,
            autoplay_enabled=state.autoplay_enabled,
        )
        await self.history_service.start_track(selected.song_id)
        await self._sync_player_queue()
        await self._confirm_preserved_state()
        return await self.queue_manager.get_playback_state()

    async def _next_available_pending(self) -> QueueItem | None:
        target = None
        for item in await self.queue_manager.list_items():
            if item.position <= 0:
                continue
            song = await self.library_repository.get_song(item.song_id)
            if song is not None and song.availability_status == "AVAILABLE":
                if target is None:
                    target = item
                continue
            reason = song.availability_status if song is not None else "SONG_NOT_FOUND"
            logger.warning(
                "Skipping unavailable Queue item %s (song %s): %s",
                item.queue_item_id, item.song_id, reason,
            )
            await self.queue_manager.delete(item.queue_item_id, persist_state=False)
        return target

    @_atomic_history_transition
    async def previous(self) -> PlaybackState | None:
        state = await self.queue_manager.get_playback_state()
        if state is None or state.state == "STOPPED":
            return state

        played = [
            item
            for item in await self.queue_manager.list_items()
            if item.position < 0
        ]
        if not played:
            return state

        target = played[0]
        song = await self._require_available_song(target.song_id)
        await self._prepare_play(song)
        selected = await self.queue_manager.play_now(
            target.queue_item_id,
            persist_state=False,
        )
        status = await self.player.status()
        await self._save_confirmed_playing(
            selected.song_id,
            context_id=selected.playback_context_id or state.playback_context_id,
            status=status,
            autoplay_enabled=state.autoplay_enabled,
        )
        await self.history_service.start_track(selected.song_id)
        await self._sync_player_queue()
        await self._confirm_preserved_state()
        return await self.queue_manager.get_playback_state()

    async def pause(self) -> PlaybackState | None:
        state = await self.queue_manager.get_playback_state()
        if state is None or state.state == "STOPPED":
            return state

        await self.player.pause()
        status = await self.player.status()
        return await self._save_confirmed_status(
            status,
            context_id=state.playback_context_id,
            autoplay_enabled=state.autoplay_enabled,
        )

    async def seek(self, seconds: float) -> PlaybackState | None:
        state = await self.queue_manager.get_playback_state()
        if state is None or state.state == "STOPPED":
            return state

        await self.player.seek(seconds)
        status = await self.player.status()
        return await self._save_confirmed_status(
            status,
            song_id=state.song_id,
            context_id=state.playback_context_id,
            autoplay_enabled=state.autoplay_enabled,
        )

    @_atomic_history_transition
    async def stop(self) -> PlaybackState | None:
        state = await self.queue_manager.get_playback_state()

        await self.player.stop()
        status = await self.player.status()
        confirmed = await self._save_confirmed_status(
            status,
            context_id=state.playback_context_id if state else None,
            autoplay_enabled=False,
        )
        await self.history_service.stop()
        return confirmed

    @_atomic_history_transition
    async def reconcile_external_status(self) -> PlaybackState:
        status = await self.player.status()
        previous = await self.queue_manager.get_playback_state()
        queue_items = await self.queue_manager.list_items()
        current_item = next(
            (item for item in queue_items if item.position == 0),
            None,
        )

        song_id = await self._song_id_for_uri(status.song_uri)
        context_id = None
        if (
            current_item is not None
            and song_id is not None
            and current_item.song_id == song_id
        ):
            context_id = current_item.playback_context_id
        elif previous is not None and song_id == previous.song_id:
            context_id = previous.playback_context_id

        autoplay_enabled = (
            False
            if status.state == PlayerState.STOPPED
            else (
                previous.autoplay_enabled
                if previous is not None
                else True
            )
        )
        confirmed = await self._save_confirmed_status(
            status,
            song_id=song_id,
            context_id=context_id,
            autoplay_enabled=autoplay_enabled,
        )

        if status.state == PlayerState.STOPPED:
            await self.history_service.stop()
        elif song_id is not None:
            active = self.history_service.active_event
            if active is None or active.song_id != song_id:
                await self.history_service.start_track(song_id)

        return confirmed

    async def _prepare_play(self, song: Song) -> PlayerStatus:
        entries = await self.player.queue_entries()
        if not any(entry.song_uri == song.file_uri for entry in entries):
            await self.player.queue_add(song.file_uri)

        await self.player.play(song.file_uri)
        status = await self.player.status()
        if (
            status.state != PlayerState.PLAYING
            or status.song_uri != song.file_uri
        ):
            raise PlaybackReconciliationError(
                "MPD did not confirm the requested current track"
            )
        return status

    async def _sync_player_queue(self) -> None:
        desired = await self._desired_song_uris()
        current = await self.player.queue_entries()
        for position, song_uri in enumerate(desired):
            if position < len(current) and current[position].song_uri == song_uri:
                continue

            source_index = next(
                (
                    index
                    for index in range(position, len(current))
                    if current[index].song_uri == song_uri
                ),
                None,
            )
            if source_index is not None:
                await self.player.queue_move(
                    current[source_index].mpd_song_id,
                    current[position].mpd_song_id,
                )
            else:
                mpd_song_id = await self.player.queue_add(song_uri)
                if position < len(current):
                    await self.player.queue_move(
                        mpd_song_id,
                        current[position].mpd_song_id,
                    )
            current = await self.player.queue_entries()

        current = await self.player.queue_entries()
        for entry in reversed(current[len(desired):]):
            await self.player.queue_delete(entry.mpd_song_id)
        if [entry.song_uri for entry in await self.player.queue_entries()] != desired:
            raise PlaybackReconciliationError("MPD did not confirm the Server Queue")

    async def _desired_song_uris(self) -> list[str]:
        items = await self.queue_manager.list_items()
        ordered = sorted(
            (
                item
                for item in items
                if item.position == 0 or item.position > 0
            ),
            key=lambda item: item.position,
        )
        uris: list[str] = []
        for item in ordered:
            if item.position == 0:
                # Catalog availability may change while this occurrence still plays.
                # Retain it until a successor is confirmed; never start it anew here.
                song = await self.library_repository.get_song(item.song_id)
                if song is None:
                    raise PlaybackSongNotFoundError(f"song not found: {item.song_id}")
            else:
                song = await self._require_available_song(item.song_id)
            uris.append(song.file_uri)
        return uris

    async def _queue_playback_context(
        self,
        state: PlaybackState,
    ) -> PlaybackContext:
        items = await self.queue_manager.list_items()
        ordered_song_ids = tuple(
            item.song_id
            for item in sorted(
                (
                    item
                    for item in items
                    if item.position == 0 or item.position > 0
                ),
                key=lambda item: item.position,
            )
        )
        context_id = state.playback_context_id or "queue-context"
        return PlaybackContext(
            context_id=context_id,
            source_type="QUEUE",
            ordered_song_ids=ordered_song_ids,
        )

    async def _save_confirmed_playing(
        self,
        song_id: str,
        *,
        context_id: str | None,
        status: PlayerStatus,
        autoplay_enabled: bool = True,
    ) -> PlaybackState:
        if (
            status.state != PlayerState.PLAYING
            or status.song_uri is None
        ):
            raise PlaybackReconciliationError(
                "MPD status is not a confirmed playing state"
            )
        return await self._save_confirmed_status(
            status,
            song_id=song_id,
            context_id=context_id,
            autoplay_enabled=autoplay_enabled,
        )

    async def _save_confirmed_status(
        self,
        status: PlayerStatus,
        *,
        song_id: str | None = None,
        context_id: str | None = None,
        autoplay_enabled: bool = True,
    ) -> PlaybackState:
        resolved_song_id = song_id
        if resolved_song_id is None:
            resolved_song_id = await self._song_id_for_uri(status.song_uri)

        state = (
            "PLAYING"
            if status.state == PlayerState.PLAYING
            else "PAUSED"
            if status.state == PlayerState.PAUSED
            else "STOPPED"
        )
        if state == "STOPPED":
            autoplay_enabled = False

        saved = PlaybackState(
            song_id=resolved_song_id,
            state=state,
            playback_context_id=context_id,
            position_seconds=status.elapsed_seconds,
            autoplay_enabled=autoplay_enabled,
            updated_at=datetime.now(timezone.utc),
        )
        return await self.queue_manager.set_playback_state(saved)

    async def _song_id_for_uri(self, song_uri: str | None) -> str | None:
        if song_uri is None:
            return None
        song = await self.library_repository.find_song_by_file_uri(song_uri)
        return song.song_id if song is not None else None

    async def _require_available_song(self, song_id: str) -> Song:
        song = await self.library_repository.get_song(song_id)
        if song is None:
            raise PlaybackSongNotFoundError(f"song not found: {song_id}")
        if song.availability_status != "AVAILABLE":
            raise PlaybackSongUnavailableError(f"song is not available: {song_id}")
        return song
