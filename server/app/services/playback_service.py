from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timezone
from functools import wraps
from typing import Concatenate, ParamSpec, TypeVar

from server.app.models.library import Song
from server.app.models.queue import PlaybackContext, PlaybackState, QueueItem
from server.app.models.realtime import PlaybackObservation
from server.app.models.recovery import (
    CompletionEvidence,
    CompletionValidator,
    RecoveryBaseline,
    RecoveryResult,
)
from server.app.player.models import PlayerState, PlayerStatus
from server.app.player.ports import PlayerPort
from server.app.repositories.database import (
    on_transaction_commit,
    on_transaction_rollback,
    on_transaction_visible,
    run_transaction,
    transaction_identity,
)
from server.app.repositories.library_repository import LibraryRepository
from server.app.repositories.queue_repository import QueueRevisionConflictError
from server.app.services.autoplay import AutoPlay
from server.app.services.events import EventPublisher, PlaybackChangedEvent
from server.app.services.history_service import HistoryService
from server.app.services.output_operation import OutputOperationLifecycle
from server.app.services.playback_observation import PlaybackObservations
from server.app.services.playback_recovery import RecoveryJournal
from server.app.services.queue_manager import QueueItemNotFoundError, QueueManager
from server.app.services.realtime_coordinator import RealtimeCoordinator

logger = logging.getLogger(__name__)
P = ParamSpec("P")
T = TypeVar("T")


class _OutputOperationLifecycle:
    """Bind public database hooks without exposing transaction resources."""

    __slots__ = ("_active", "_path")

    def __init__(self, path: str) -> None:
        self._path = path
        self._active = True

    def _require_active(self) -> None:
        if not self._active:
            raise RuntimeError("lifecycle registration requires an active output invocation")

    def on_commit(self, callback: Callable[[], object | Awaitable[object]]) -> None:
        self._require_active()
        on_transaction_commit(self._path, callback)

    def on_rollback(self, callback: Callable[[], None]) -> None:
        self._require_active()
        on_transaction_rollback(self._path, callback)


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


def _recovery_change(operation):
    """Track business identity only for operations that can change current."""
    @wraps(operation)
    async def wrapped(self, *args, **kwargs):
        identity = await self._recovery_current_identity()
        result = await operation(self, *args, **kwargs)
        if identity != await self._recovery_current_identity():
            self._recovery.advance()
        return result

    return wrapped


def _transport_change(operation):
    """Stage only transport producers, never the shared Output operation runner."""
    @wraps(operation)
    async def wrapped(self, *args, **kwargs):
        if self._coordinator is None and self._event_publisher is None:
            return await operation(self, *args, **kwargs)
        before = await self._transport_content()
        result = await operation(self, *args, **kwargs)
        after = await self._transport_content()
        self._stage_transport(before, after)
        return result

    return wrapped


def _queue_change(operation):
    """Capture a pending mutation inside its owning playback transaction."""
    @wraps(operation)
    async def wrapped(self, *args, **kwargs):
        before = await self._queue_content()
        result = await operation(self, *args, **kwargs)
        self._stage_transport(before, await self._queue_content())
        return result

    return wrapped


def _current_change(operation):
    """Stage the complete confirmed transition inside the existing outer owner."""
    @wraps(operation)
    async def wrapped(self, *args, **kwargs):
        before = await self._current_content()
        result = await operation(self, *args, **kwargs)
        self._stage_transport(before, await self._current_content())
        return result

    return _recovery_change(wrapped)


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
        event_publisher: EventPublisher | None = None,
        coordinator: RealtimeCoordinator | None = None,
        observation_clock: Callable[[], datetime] | None = None,
        observation_max_age: float = 6,
        completion_validator: CompletionValidator | None = None,
    ) -> None:
        self.queue_manager = queue_manager
        self.history_service = history_service
        self.autoplay = autoplay
        self.player = player
        self.library_repository = library_repository
        self._event_publisher = event_publisher
        self._coordinator = coordinator
        self._observations = PlaybackObservations(self, observation_clock, observation_max_age)
        self._recovery = RecoveryJournal(queue_manager.queue_repository.path)
        self._completion_validator = completion_validator
        self._transport_changes: dict[object, list[dict[str, object]]] = {}

    async def _recovery_current_identity(self):
        state = await self.queue_manager.get_playback_state()
        current = next((i for i in await self.queue_manager.list_items() if i.position == 0), None)
        active = self.history_service.active_event
        return (
            current.queue_item_id if current else None,
            state.song_id if state else None,
            state.playback_context_id if state else None,
            active.started_at if active else None,
            self.history_service.session_id,
        )

    async def observe(self, read_timeout: float | None = None) -> PlaybackObservation:
        return await self._observations.observe(read_timeout=read_timeout)

    async def get_observation(self) -> PlaybackObservation:
        return await self._observations.get()

    async def _transport_content(self) -> dict[str, object]:
        state = await self.queue_manager.get_playback_state()
        return {
            "playback": (
                state.model_dump(exclude={"updated_at"}) if state else None,
                self._observations.cache.model_dump(exclude={"observed_at"}),
            ),
            "history": (
                await self.history_service.list_history(),
                self.history_service.active_event,
                self.history_service.session_id,
            ),
        }

    async def _queue_content(self) -> dict[str, object]:
        if self._coordinator is None and self._event_publisher is None:
            return {}
        return {"queue": await self.queue_manager.queue_repository.get_snapshot()}

    async def _current_content(self) -> dict[str, object]:
        if self._coordinator is None and self._event_publisher is None:
            return {}
        return {**await self._transport_content(), **await self._queue_content()}

    def _stage_transport(self, before: dict[str, object], after: dict[str, object]) -> None:
        path = self.queue_manager.queue_repository.path
        if self._coordinator is not None:
            for domain, content in before.items():
                self._coordinator.stage_change(
                    frozenset({domain}), content, after[domain],
                )
        if self._event_publisher is None:
            return
        owner = transaction_identity(path)
        delta = self._transport_changes.get(owner)
        if delta is None:
            delta = [before, after]
            self._transport_changes[owner] = delta

            async def committed():
                first, last = delta
                domains = frozenset(domain for domain in first if first[domain] != last[domain])
                if domains:
                    await self._event_publisher.publish(PlaybackChangedEvent(domains=domains))

            on_transaction_commit(path, committed)
            on_transaction_visible(path, lambda: self._transport_changes.pop(owner, None))
            on_transaction_rollback(path, lambda: self._transport_changes.pop(owner, None))
        for domain, content in before.items():
            delta[0].setdefault(domain, content)
        delta[1].update(after)

    @_atomic_history_transition
    async def run_output_operation(
        self, operation: Callable[[OutputOperationLifecycle], Awaitable[T]],
    ) -> T:
        """Serialize output work with playback in the owning database transaction."""
        lifecycle = _OutputOperationLifecycle(self.queue_manager.queue_repository.path)
        try:
            return await operation(lifecycle)
        finally:
            lifecycle._active = False

    @_atomic_history_transition
    @_current_change
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
    @_current_change
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
    @_current_change
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

    @_atomic_history_transition
    @_queue_change
    async def play_next(self, song_id: str) -> QueueItem:
        song = await self._require_available_song(song_id)
        item = await self.queue_manager.play_next(song.song_id)
        await self._sync_player_queue()
        await self._confirm_preserved_state()
        return item

    @_atomic_history_transition
    @_queue_change
    async def add_to_queue(self, song_id: str) -> QueueItem:
        song = await self._require_available_song(song_id)
        item = await self.queue_manager.add_to_queue(song.song_id)
        await self._sync_player_queue()
        await self._confirm_preserved_state()
        return item

    async def reorder(
        self,
        queue_item_id: str,
        before_queue_item_id: str | None = None,
        *,
        expected_revision: int | None = None,
    ) -> list[QueueItem]:
        async def operation(_connection):
            before = await self._queue_content()
            previous_items = await self.queue_manager.list_items()
            items = await self.queue_manager.reorder(
                queue_item_id,
                before_queue_item_id,
                expected_revision=expected_revision,
            )
            await self._sync_player_queue(previous_items=previous_items)
            await self._confirm_preserved_state()
            self._stage_transport(before, await self._queue_content())
            return items

        return await run_transaction(
            self.queue_manager.queue_repository.path, operation,
        )

    async def clear(self, *, expected_revision: int | None = None) -> None:
        async def operation(_connection):
            before = await self._queue_content()
            await self.queue_manager.clear(expected_revision=expected_revision)
            await self._refill_empty_pending()
            await self._sync_player_queue()
            await self._confirm_preserved_state()
            self._stage_transport(before, await self._queue_content())

        await run_transaction(self.queue_manager.queue_repository.path, operation)

    @_atomic_history_transition
    @_recovery_change
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
                before = await self._queue_content() if selected.position > 0 else None
                await self.queue_manager.delete(
                    queue_item_id,
                    expected_revision=expected_revision,
                    persist_state=False,
                )
                await self._refill_empty_pending()
                await self._sync_player_queue(previous_items=snapshot.items)
                await self._confirm_preserved_state()
                if before is not None:
                    self._stage_transport(before, await self._queue_content())
                return None

            # Resolve availability before promoting a successor. Played is independent.
            before = await self._current_content()
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
                await self._observations.confirmed(status)
                await self.history_service.start_track(promoted.song_id)
            self._stage_transport(before, await self._current_content())
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
            await self._observations.confirmed(status)

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
    @_current_change
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
    @_current_change
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

    @_atomic_history_transition
    @_transport_change
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

    @_atomic_history_transition
    @_transport_change
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
    @_recovery_change
    @_transport_change
    async def stop(self) -> PlaybackState | None:
        state = await self.queue_manager.get_playback_state()

        await self.player.stop()
        status = await self.player.status()
        if status.state != PlayerState.STOPPED:
            raise PlaybackReconciliationError("MPD did not confirm stopped state")
        confirmed = await self._save_confirmed_status(
            status,
            context_id=state.playback_context_id if state else None,
            autoplay_enabled=False,
        )
        await self.history_service.stop()
        return confirmed

    @_atomic_history_transition
    @_current_change
    async def reconcile_external_status(
        self, *, evidence: CompletionEvidence | None = None,
    ) -> RecoveryResult:
        if evidence is not None:
            try:
                receipt = self._recovery.get_receipt(self._recovery.identity(evidence), evidence)
            except ValueError as error:
                raise PlaybackReconciliationError(str(error)) from error
            if receipt is not None:
                return receipt
            if self._recovery.quarantined or evidence.service_epoch != self._recovery.service_epoch:
                return RecoveryResult(
                    "UNKNOWN", await self.queue_manager.get_playback_state(),
                    reconciliation_required=True,
                )
        status = await self.player.status()
        entries = await self.player.queue_entries()
        previous = await self.queue_manager.get_playback_state()
        if evidence is not None:
            return await self._reconcile_completion(evidence, previous, status, entries)
        binding = self._observations.binding
        execution = sorted(
            (item for item in await self.queue_manager.list_items() if item.position >= 0),
            key=lambda item: item.position,
        )
        songs = [await self.library_repository.get_song(item.song_id) for item in execution]
        matched = (
            previous is not None and previous.state in {"PLAYING", "PAUSED"}
            and binding is not None
            and binding[:4] == await self._observations._identity()
            and status.state in {PlayerState.PLAYING, PlayerState.PAUSED}
            and status.song_id == binding[4] and status.song_uri == binding[5]
            and status.song_position == 0 and bool(entries)
            and entries[0].mpd_song_id == binding[4]
            and len(binding) == 7
            and tuple((item.queue_item_id, entry.mpd_song_id, entry.song_uri)
                      for item, entry in zip(execution, entries)) == binding[6]
            and [entry.position for entry in entries] == list(range(len(execution)))
            and [entry.song_uri for entry in entries] == [song.file_uri if song else None for song in songs]
        )
        if not matched:
            return RecoveryResult("UNKNOWN", previous, reconciliation_required=True)
        if status.state.value == previous.state.lower():
            return RecoveryResult("UNCHANGED", previous)
        confirmation = await self.player.status()
        confirmed_entries = await self.player.queue_entries()
        if (
            (confirmation.state, confirmation.song_id, confirmation.song_uri, confirmation.song_position)
            != (status.state, status.song_id, status.song_uri, status.song_position)
            or confirmed_entries != entries
        ):
            raise PlaybackReconciliationError("External transport changed during confirmation")
        confirmed = await self._save_confirmed_status(
            confirmation, song_id=previous.song_id,
            context_id=previous.playback_context_id,
            autoplay_enabled=previous.autoplay_enabled,
        )
        return RecoveryResult("APPLIED", confirmed)

    async def _reconcile_completion(self, evidence, previous, status, entries) -> RecoveryResult:
        unknown = RecoveryResult("UNKNOWN", previous, reconciliation_required=True)
        journal = self._recovery
        identity = journal.identity(evidence)
        try:
            receipt = journal.get_receipt(identity, evidence)
        except ValueError as error:
            raise PlaybackReconciliationError(str(error)) from error
        if receipt is not None:
            return receipt
        binding = self._observations.binding
        queue = await self.queue_manager.get_snapshot()
        history = await self.history_service.get_availability()
        current = next((i for i in queue.items if i.position == 0), None)
        active = history.active_event
        if (
            previous is None or current is None or active is None or history.session_id is None
            or binding is None or len(binding) != 7
            or binding[:4] != await self._observations._identity()
            or tuple(i.queue_item_id for i in queue.items if i.position >= 0)
            != tuple(item_id for item_id, _, _ in binding[6])
            or evidence.service_epoch != journal.service_epoch
            or evidence.business_generation != journal.business_generation
            or evidence.queue_revision != queue.revision
            or evidence.queue_item_id != current.queue_item_id
            or evidence.mpd_song_id != binding[4]
            or active.song_id != current.song_id or previous.song_id != current.song_id
            or not evidence.transition_id
        ):
            return unknown
        try:
            valid_time = evidence.ended_at >= active.started_at
        except TypeError:
            valid_time = False
        if not valid_time or self._completion_validator is None:
            return unknown
        baseline = RecoveryBaseline(queue, previous, history, journal.business_generation, binding[4])
        if not await self._completion_validator.validate(evidence, baseline):
            return unknown
        plan = journal.pending.get(identity)
        if plan is not None and plan.baseline != baseline:
            return unknown
        if plan is None:
            available = []
            for item in queue.items:
                if item.position <= 0:
                    continue
                song = await self.library_repository.get_song(item.song_id)
                if song is not None and song.availability_status == "AVAILABLE":
                    available.append(item)
                else:
                    logger.warning("Skipping unavailable completion candidate %s", item.queue_item_id)
            pending = tuple(available)
            if not pending:
                filtered = queue.model_copy(update={"items": tuple(i for i in queue.items if i.position <= 0)})
                pending = await self.autoplay.plan_refill(await self._queue_playback_context(previous), filtered)
            plan = journal.prepare(evidence, baseline, pending)
        actual = tuple((e.mpd_song_id, e.song_uri) for e in entries)
        original = tuple((mpd_id, uri) for _, mpd_id, uri in binding[6])
        planned_execution = journal.execution.get(identity)
        final = tuple((mpd_id, uri) for _, mpd_id, uri in planned_execution) if planned_execution is not None else None
        target_id = next((mpd_id for item_id, mpd_id, _ in (planned_execution or binding[6]) if item_id == plan.successor_id), None)
        if actual != original and actual != final:
            return unknown
        if status.state != PlayerState.STOPPED and not (
            status.state == PlayerState.PLAYING and status.song_id == target_id
            and status.song_position == next((e.position for e in entries if e.mpd_song_id == target_id), None)
            and status.song_uri == next((e.song_uri for e in entries if e.mpd_song_id == target_id), None)
        ):
            return unknown
        if planned_execution is None:
            old_ids = {item_id: mpd_id for item_id, mpd_id, _ in binding[6]}
            planned = []
            for item in plan.pending:
                song = await self._require_available_song(item.song_id)
                mpd_id = old_ids.get(item.queue_item_id)
                if mpd_id is None:
                    mpd_id = await self.player.queue_add(song.file_uri)
                planned.append((item.queue_item_id, mpd_id, song.file_uri))
            planned_execution = tuple(planned)
            journal.execution[identity] = planned_execution
        retained_ids = {mpd_id for _, mpd_id, _ in planned_execution}
        for entry in entries:
            if entry.mpd_song_id not in retained_ids:
                await self.player.queue_delete(entry.mpd_song_id)
        target_id = planned_execution[0][1] if planned_execution else None
        if target_id is not None and status.state == PlayerState.STOPPED:
            await self.player.queue_play(target_id)
        confirmed = await self.player.status()
        confirmed_entries = await self.player.queue_entries()
        if (
            (target_id is not None and (
                confirmed.state != PlayerState.PLAYING or confirmed.song_id != target_id
                or confirmed.song_position != 0 or confirmed.song_uri != planned_execution[0][2]
            ))
            or (target_id is None and confirmed.state != PlayerState.STOPPED)
            or [(e.mpd_song_id, e.song_uri, e.position) for e in confirmed_entries]
            != [(mpd_id, uri, index) for index, (_, mpd_id, uri) in enumerate(planned_execution)]
        ):
            raise PlaybackReconciliationError("MPD did not confirm the fixed completion target and Queue")
        await self.queue_manager.complete_current(
            evidence.queue_item_id, pending=plan.pending, successor_id=plan.successor_id,
            expected_revision=queue.revision,
        )
        await self.history_service.complete_naturally(ended_at=evidence.ended_at)
        if plan.pending:
            target = plan.pending[0]
            await self.history_service.start_track(target.song_id, started_at=max(datetime.now(timezone.utc), evidence.ended_at))
            saved = await self._save_confirmed_playing(
                target.song_id, context_id=previous.playback_context_id, status=confirmed,
                autoplay_enabled=previous.autoplay_enabled,
            )
            await self._observations.confirmed(confirmed, entries=confirmed_entries)
        else:
            saved = await self.queue_manager.set_playback_state(PlaybackState(
                state="STOPPED", song_id=None, position_seconds=None, autoplay_enabled=True,
                playback_context_id=previous.playback_context_id, updated_at=datetime.now(timezone.utc),
            ))
            await self._observations.changed()
        result = RecoveryResult("APPLIED", saved, evidence.transition_id)
        journal.commit(identity, result)
        return result

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

    async def _sync_player_queue(
        self, *, previous_items: Sequence[QueueItem] | None = None,
    ) -> None:
        desired = await self._desired_song_uris()
        current = await self.player.queue_entries()
        retained_ids: dict[str, int] | None = None
        if previous_items is not None:
            previous_execution = sorted(
                (item for item in previous_items if item.position >= 0),
                key=lambda item: item.position,
            )
            previous_uris = []
            for item in previous_execution:
                song = await self.library_repository.get_song(item.song_id)
                previous_uris.append(song.file_uri if song else None)
            # Bind before mutation only when the player still executes that Queue.
            # A failed earlier command may require URI reconciliation on retry.
            if previous_uris == [entry.song_uri for entry in current]:
                retained_ids = {
                    item.queue_item_id: entry.mpd_song_id
                    for item, entry in zip(previous_execution, current, strict=True)
                }
        execution = sorted(
            (item for item in await self.queue_manager.list_items() if item.position >= 0),
            key=lambda item: item.position,
        )
        for position, song_uri in enumerate(desired):
            retained_id = (
                retained_ids.get(execution[position].queue_item_id)
                if retained_ids is not None else None
            )
            if position < len(current) and (
                current[position].mpd_song_id == retained_id
                if retained_ids is not None
                else current[position].song_uri == song_uri
            ):
                continue

            source_index = next(
                (
                    index
                    for index in range(position, len(current))
                    if (
                        current[index].mpd_song_id == retained_id
                        if retained_ids is not None
                        else current[index].song_uri == song_uri
                    )
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
        await self._observations.changed()
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
