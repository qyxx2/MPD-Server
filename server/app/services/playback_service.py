from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timezone
from functools import wraps
from math import isfinite
from time import monotonic
from typing import Concatenate, ParamSpec, TypeVar
from uuid import UUID, uuid5

from server.app.models.library import Song
from server.app.models.playback_control import PlaybackControlTarget
from server.app.models.queue import PlaybackContext, PlaybackState, QueueItem
from server.app.models.realtime import PlaybackObservation
from server.app.models.recovery import (
    CompletionEvidence,
    CompletionValidator,
    ExecutionBinding,
    ExecutionCommand,
    ExecutionIntent,
    RecoveryBaseline,
    RecoveryResult,
)
from server.app.player.models import ExecutionSample, PlayerState, PlayerStatus
from server.app.player.ports import PlayerCommandError, PlayerPort, PlayerUnavailable
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
from server.app.services.playback_control import (
    PlaybackControlTargets,
    PlaybackTargetConflictError,
)
from server.app.services.playback_execution import ExecutionSynchronizer
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
            nonlocal args
            self.history_service.preserve_active_on_rollback()
            if operation.__name__ == "play_context" and kwargs.get("request_id") is not None:
                args = (self._recovery.prepare_context(kwargs["request_id"], kwargs["request_payload"], args[0]), *args[1:])
            owner = transaction_identity(self.queue_manager.queue_repository.path)
            prior = getattr(self, "_execution_owner", None)
            if prior is None or prior[0] is not owner:
                snapshot = await self.queue_manager.get_snapshot()
                key = (self._recovery.business_generation, snapshot.revision,
                       operation.__name__, repr(args), repr(sorted(kwargs.items())))
                operation_id = self._recovery.operation_id(key)
                self._execution_owner = (owner, operation_id)
            else:
                operation_id = prior[1]
            try:
                if prior is None or prior[0] is not owner:
                    with self.queue_manager.queue_repository.fixed_allocation(operation_id):
                        return await operation(self, *args, **kwargs)
                return await operation(self, *args, **kwargs)
            except (PlayerUnavailable, PlayerCommandError, TimeoutError) as error:
                if (isinstance(error, (PlayerUnavailable, TimeoutError))
                        or error.command in {"status", "queue_entries", "read_execution_sample", "playlistinfo", "currentsong"}):
                    self._recovery.invalidate_binding()
                    if (isinstance(error, (PlayerUnavailable, TimeoutError))
                            or error.command in {"read_execution_sample", "playlistinfo", "currentsong"}):
                        control_id = self._recovery.execution_attempts.get(operation_id, operation_id)
                        for intent_id in self._recovery.execution_intents:
                            if intent_id.startswith(control_id + "/") and self._recovery.get_execution_receipt(intent_id) is None:
                                self._recovery.unknown_executions.add(intent_id)
                raise
            finally:
                self._execution_owner = prior

        return await run_transaction(self.queue_manager.queue_repository.path, transition)

    return wrapped


def _recovery_change(operation):
    """Track business identity only for operations that can change current."""
    @wraps(operation)
    async def wrapped(self, *args, **kwargs):
        identity = await self._recovery_current_identity()
        explicit = operation.__name__ in {"start_track", "play_context", "play_now", "next", "previous", "delete"}
        old_owner = getattr(self, "_binding_control_owner", None)
        old_origin = getattr(self, "_binding_origin_id", None)
        if explicit:
            self._binding_control_owner = transaction_identity(self.queue_manager.queue_repository.path)
            self._binding_origin_id = identity[0] if operation.__name__ in {"next", "previous", "delete"} else None
        try:
            result = await operation(self, *args, **kwargs)
        finally:
            self._binding_control_owner, self._binding_origin_id = old_owner, old_origin
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
        self._control_targets = PlaybackControlTargets(queue_manager.queue_repository.path)
        self._recovery = RecoveryJournal(
            queue_manager.queue_repository.path, invalidate_targets=self._control_targets.invalidate,
        )
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

    async def get_execution_binding(self) -> ExecutionBinding | None:
        async def read(_):
            binding = self._recovery.binding
            if (binding is not None and self._observations._confirmed_identity is not None
                    and self._observations._confirmed_identity[0] is not self.player):
                self._recovery.invalidate_binding()
                binding = None
            if binding is not None:
                queue = await self.queue_manager.get_snapshot()
                ids = tuple(item.queue_item_id for item in sorted(
                    (item for item in queue.items if item.position >= 0),
                    key=lambda item: item.position,
                ))
                if (binding.queue_revision != queue.revision
                        or ids != tuple(item_id for item_id, _, _ in binding.entries)):
                    self._recovery.invalidate_binding()
            return self._recovery.binding

        return await run_transaction(self.queue_manager.queue_repository.path, read)

    def _control_identity(self) -> tuple[object, ...] | None:
        binding = self._recovery.binding
        if binding is None or not binding.entries:
            return None
        return (binding.service_epoch, binding.connection_epoch, binding.partition,
                binding.binding_generation, binding.entries[0][0], self._control_targets.generation)

    async def _require_control_target(self, target: PlaybackControlTarget) -> ExecutionSample:
        await self.get_execution_binding()
        if self._control_identity() != self._control_targets.identity:
            self._control_targets.invalidate()
        self._control_targets.require(target)
        sample = await self._read_bound_sample()
        binding = await self.get_execution_binding()
        status = sample.status
        if (binding is None or not binding.entries
                or self._control_identity() != self._control_targets.identity
                or status.state not in {PlayerState.PLAYING, PlayerState.PAUSED}
                or status.song_id != binding.entries[0][1]
                or status.song_uri != binding.entries[0][2] or status.song_position != 0
                or sample.single != "0" or sample.consume or status.random or status.repeat
                or sample.error is not None):
            self._control_targets.invalidate()
            raise PlaybackTargetConflictError("Playback control target no longer matches actual current")
        self._control_targets.require(target)
        return sample

    async def _read_execution_sample(self) -> ExecutionSample:
        try:
            sample = await self.player.read_execution_sample()
        except BaseException:
            self._recovery.invalidate_binding()
            raise
        return sample

    async def _read_bound_sample(self) -> ExecutionSample:
        sample = await self._read_execution_sample()
        self._recovery.accepts(sample)
        return sample

    async def _validate_history_active(self, sample: ExecutionSample) -> bool:
        active = self.history_service.active_event
        binding = self._recovery.binding
        if active is None or binding is None or not self._recovery.accepts(sample):
            return False
        current = next(
            (item for item in await self.queue_manager.list_items() if item.position == 0),
            None,
        )
        if current is None or active.song_id != current.song_id:
            return False
        try:
            position = next(
                index
                for index, (item_id, _, _) in enumerate(binding.entries)
                if item_id == current.queue_item_id
            )
        except StopIteration:
            return False
        _, mpd_song_id, song_uri = binding.entries[position]
        status = sample.status
        return (
            status.state in {PlayerState.PLAYING, PlayerState.PAUSED}
            and status.song_position == position
            and status.song_id == mpd_song_id
            and status.song_uri == song_uri
        )

    async def _history_active_identity(self) -> tuple[object, ...] | None:
        active = self.history_service.active_event
        current = next(
            (item for item in await self.queue_manager.list_items() if item.position == 0),
            None,
        )
        if active is None or current is None:
            return None
        return (
            current.queue_item_id,
            active.song_id,
            active.started_at,
            active.session_id,
        )

    async def _discard_unconfirmed_history_active(self) -> None:
        identity = await self._history_active_identity()
        if identity is None:
            return
        operation_id = self._execution_owner[1]
        if self._recovery.prepare_history_active(operation_id, identity):
            return
        sample = await self._read_execution_sample()
        if not await self._validate_history_active(sample):
            await self.history_service.discard_unconfirmed_active()

    async def _confirm_history_active(self) -> None:
        operation_id = self._execution_owner[1]
        qualification = self._recovery.history_active_qualifications.get(operation_id)
        active = self.history_service.active_event
        if qualification is None or active is None:
            return
        identity = qualification[0]
        if identity[1:] != (active.song_id, active.started_at, active.session_id):
            raise PlaybackReconciliationError("History active identity conflict")
        self._recovery.confirm_history_active(operation_id, identity)

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
        await self._discard_unconfirmed_history_active()
        await self._prepare_play(song)

        context = await self.queue_manager.start_track(
            song_id,
            persist_state=False,
            context_id=str(uuid5(UUID(self._execution_owner[1]), "context")),
        )
        status = await self.player.status()
        await self._save_confirmed_playing(
            song_id,
            context_id=context.context_id,
            status=status,
        )
        await self._confirm_history_active()
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
        *,
        request_id: str | None = None,
        request_payload: str | None = None,
    ) -> PlaybackState | None:
        if not context.ordered_song_ids:
            return await self.queue_manager.get_playback_state()

        songs = [
            await self._require_available_song(song_id)
            for song_id in context.ordered_song_ids
        ]

        await self._discard_unconfirmed_history_active()

        await self.queue_manager.replace_with_context(context)

        status = await self._prepare_play(songs[0])
        state = await self._save_confirmed_playing(
            context.ordered_song_ids[0],
            context_id=context.context_id,
            status=status,
        )
        await self._confirm_history_active()
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
        await self._discard_unconfirmed_history_active()
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
        await self._confirm_history_active()
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

    @_atomic_history_transition
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

    @_atomic_history_transition
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

            await self._discard_unconfirmed_history_active()

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
                await self._confirm_history_active()
                await self.history_service.stop()
            elif state is not None and state.state == "STOPPED":
                await self._sync_player_queue()
                await self._confirm_preserved_state()
                # Deselection changes actual identity, not the last Stop business state.
                await self.queue_manager.set_playback_state(state.model_copy(update={
                    "updated_at": datetime.now(timezone.utc),
                }))
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
                await self._confirm_history_active()
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
        sample = await self._read_execution_sample()
        mapping = self._recovery.synced_entries
        controlled_sample = self._recovery.sync_sample
        queue = await self.queue_manager.get_snapshot()
        ids = tuple(item.queue_item_id for item in sorted(
            (item for item in queue.items if item.position >= 0), key=lambda item: item.position,
        ))
        if (mapping is None or controlled_sample is None
                or sample.connection_epoch != controlled_sample.connection_epoch
                or sample.partition != controlled_sample.partition
                or sample.playlist_version != controlled_sample.playlist_version
                or ids != tuple(item_id for item_id, _, _ in mapping)
                or not sample.entries or sample.status.song_position != 0
                or sample.status.song_id != mapping[0][1]
                or sample.status.song_uri != mapping[0][2]
                or (status.state, status.song_id, status.song_uri, status.song_position)
                != (sample.status.state, sample.status.song_id,
                    sample.status.song_uri, sample.status.song_position)
                or tuple((entry.mpd_song_id, entry.song_uri, entry.position)
                         for entry in sample.entries)
                != tuple((mpd_id, uri, index)
                         for index, (_, mpd_id, uri) in enumerate(mapping))):
            self._recovery.invalidate_binding()
            raise PlaybackReconciliationError("MPD current occurrence differs from Server Queue")
        self._recovery.bind(sample, item_ids=ids, queue_revision=queue.revision)

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

        await self._discard_unconfirmed_history_active()

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
        await self._confirm_history_active()
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

        await self._discard_unconfirmed_history_active()

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
        await self._confirm_history_active()
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

    async def _confirm_control_transport(
        self, target: PlaybackControlTarget, *, expected_state: PlayerState,
        position: float | None, started: float,
    ) -> PlayerStatus:
        try:
            sample = await self._require_control_target(target)
        except PlaybackTargetConflictError as error:
            raise PlaybackReconciliationError("MPD control target changed after command") from error
        status = sample.status
        elapsed = status.elapsed_seconds
        allowance = monotonic() - started + 1 if expected_state == PlayerState.PLAYING else 0.05
        if (status.state != expected_state or (position is not None and (
                elapsed is None or elapsed < position - 0.05 or elapsed > position + allowance))):
            self._control_targets.invalidate()
            raise PlaybackReconciliationError("MPD did not confirm transport state and position")
        return status

    @_atomic_history_transition
    @_transport_change
    async def resume(self, target: PlaybackControlTarget) -> PlaybackState:
        sample = await self._require_control_target(target)
        state = await self.queue_manager.get_playback_state()
        if state is None or state.state == "STOPPED":
            raise PlaybackTargetConflictError("Playback control target has no active session")
        started = monotonic()
        if sample.status.state == PlayerState.PAUSED:
            if sample.status.elapsed_seconds is None or not isfinite(sample.status.elapsed_seconds):
                raise PlaybackReconciliationError("MPD resume position is unknown")
            # Never select/rebuild execution or seek: parameterless play resumes MPD.
            on_transaction_rollback(self._recovery.path, self._control_targets.invalidate)
            await self.player.play()
        status = await self._confirm_control_transport(
            target, expected_state=PlayerState.PLAYING,
            position=sample.status.elapsed_seconds, started=started,
        )
        if sample.status.state == PlayerState.PLAYING and state.state == "PLAYING":
            return state
        return await self._save_confirmed_status(
            status, song_id=state.song_id, context_id=state.playback_context_id,
            autoplay_enabled=state.autoplay_enabled,
        )

    @_atomic_history_transition
    @_transport_change
    async def seek(
        self, seconds: float, *, target: PlaybackControlTarget | None = None,
    ) -> PlaybackState | None:
        state = await self.queue_manager.get_playback_state()
        if state is None or state.state == "STOPPED":
            if target is not None:
                self._control_targets.invalidate()
                raise PlaybackTargetConflictError("Playback control target has no active session")
            return state

        if target is not None:
            sample = await self._require_control_target(target)
            started = monotonic()
            on_transaction_rollback(self._recovery.path, self._control_targets.invalidate)
            await self.player.seek(seconds)
            status = await self._confirm_control_transport(
                target, expected_state=sample.status.state, position=seconds, started=started,
            )
        else:
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

        await self._discard_unconfirmed_history_active()

        self._control_targets.invalidate()
        await self.player.stop()
        status = await self.player.status()
        if status.state != PlayerState.STOPPED:
            raise PlaybackReconciliationError("MPD did not confirm stopped state")
        confirmed = await self._save_confirmed_status(
            status,
            context_id=state.playback_context_id if state else None,
            autoplay_enabled=False,
        )
        await self._confirm_history_active()
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
        if evidence is not None:
            status = await self.player.status()
            entries = await self.player.queue_entries()
            previous = await self.queue_manager.get_playback_state()
            return await self._reconcile_completion(evidence, previous, status, entries)
        journal = self._recovery
        operation_id = self._execution_owner[1] + "/adopt"
        receipt = journal.get_execution_receipt(operation_id)
        if receipt is not None:
            return receipt
        previous = await self.queue_manager.get_playback_state()
        unknown = RecoveryResult("UNKNOWN", previous, reconciliation_required=True)
        if journal.quarantined or operation_id in journal.unknown_executions:
            return unknown
        queue = await self.queue_manager.get_snapshot()
        generation = journal.business_generation
        intent = journal.execution_intents.get(operation_id)
        if intent is None:
            binding = await self.get_execution_binding()
            sample = await self._read_bound_sample()
            status, entries = sample.status, sample.entries
            if (binding is None or journal.binding != binding
                    or generation != journal.business_generation
                    or previous is None or previous.state not in {"PLAYING", "PAUSED"}
                    or status.state not in {PlayerState.PLAYING, PlayerState.PAUSED}
                    or (sample.single, sample.consume, status.random, status.repeat)
                    != ("0", False, False, False)):
                return unknown
            target = next((item_id for index, (item_id, mpd_id, uri) in enumerate(binding.entries)
                           if (mpd_id, uri, index) == (status.song_id, status.song_uri, status.song_position)), None)
            current = next((item for item in queue.items if item.position == 0), None)
            if current is None or not binding.entries or current.queue_item_id != binding.entries[0][0] or target is None:
                return unknown
            if target != current.queue_item_id:
                pending = sorted((item for item in queue.items if item.position > 0), key=lambda item: item.position)
                target_item = next((item for item in pending if item.queue_item_id == target), None)
                if target_item is None:
                    return unknown
                ordered = (target_item, *(item for item in pending if item != target_item))
                uris = {item_id: uri for item_id, _, uri in binding.entries}
                intent = ExecutionIntent(
                    service_epoch=journal.service_epoch, binding_generation=binding.binding_generation,
                    operation_id=operation_id, queue_revision=queue.revision,
                    baseline=sample, entries=binding.entries,
                    items=tuple((item.queue_item_id, uris[item.queue_item_id]) for item in ordered),
                    commands=ExecutionSynchronizer.adoption_commands(binding.entries, target),
                    target_item_id=target, target_state=status.state.value.upper(),
                )
                journal.prepare_execution(intent)
        if intent is not None:
            if queue.revision != intent.queue_revision:
                journal.unknown_executions.add(operation_id)
                journal.invalidate_binding()
                return unknown
            executor = ExecutionSynchronizer(self.player, journal)
            try:
                final = await executor.execute(intent)
            except PlaybackReconciliationError:
                journal.unknown_executions.add(operation_id)
                journal.invalidate_binding()
                return unknown
            # CAS is a second fence: an external prefix never licenses a stale business write.
            try:
                adopted = await self.queue_manager.adopt_current(
                    intent.entries[0][0], intent.target_item_id,
                    expected_revision=intent.queue_revision,
                )
            except QueueRevisionConflictError:
                journal.unknown_executions.add(operation_id)
                journal.invalidate_binding()
                raise
            await self.history_service.discard_unconfirmed_active()
            target_item = next(item for item in adopted.items if item.position == 0)
            saved = await self._save_confirmed_status(
                final.status, song_id=target_item.song_id,
                context_id=previous.playback_context_id,
                autoplay_enabled=previous.autoplay_enabled,
            )
            journal.bind(final, item_ids=tuple(item_id for item_id, _ in intent.items),
                         queue_revision=adopted.revision)
            await self._observations.confirmed(final.status, entries=final.entries)
            result = RecoveryResult("APPLIED", saved, operation_id)
            journal.commit_execution(operation_id, result)
            return result
        matched = (
            previous is not None and previous.state in {"PLAYING", "PAUSED"}
            and binding is not None and bool(binding.entries)
            and status.state in {PlayerState.PLAYING, PlayerState.PAUSED}
            and status.song_id == binding.entries[0][1]
            and status.song_uri == binding.entries[0][2]
            and status.song_position == 0
        )
        if not matched:
            return RecoveryResult("UNKNOWN", previous, reconciliation_required=True)
        if status.state.value == previous.state.lower():
            return RecoveryResult("UNCHANGED", previous)
        confirmed_sample = await self._read_bound_sample()
        confirmation, confirmed_entries = confirmed_sample.status, confirmed_sample.entries
        if (
            self._recovery.binding is None
            or generation != journal.business_generation
            or self._recovery.binding != binding
            or (confirmation.state, confirmation.song_id, confirmation.song_uri, confirmation.song_position)
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

    async def maintain_execution(self, *, read_timeout: float | None = None) -> RecoveryResult:
        """Confirm current and append a fixed refill within one rollback boundary."""
        diagnostic_number = self._observations.begin_diagnostic()

        def publish_diagnostic(operation):
            @wraps(operation)
            async def wrapped(service):
                result = await operation(service)
                await service._observations.diagnose(
                    result.diagnostic,
                    service._recovery.business_generation,
                    diagnostic_number,
                )
                return result

            return wrapped

        @_atomic_history_transition
        @publish_diagnostic
        @_queue_change
        async def maintain(self):
            journal = self._recovery
            operation_id = self._execution_owner[1] + "/refill"
            receipt = journal.get_execution_receipt(operation_id)
            if receipt is not None:
                return receipt
            previous = await self.queue_manager.get_playback_state()
            unknown = RecoveryResult("UNKNOWN", previous, reconciliation_required=True,
                                     diagnostic="SYNC_FAILED")
            if journal.quarantined or operation_id in journal.unknown_executions:
                return unknown
            intent = journal.execution_intents.get(operation_id)
            if intent is None:
                reconciled = await self.reconcile_external_status()
                if reconciled.reconciliation_required:
                    return reconciled
                previous = await self.queue_manager.get_playback_state()
                unknown = RecoveryResult("UNKNOWN", previous, reconciliation_required=True,
                                         diagnostic="SYNC_FAILED")
                if previous is None or not previous.autoplay_enabled:
                    return RecoveryResult("UNCHANGED", previous)
                binding = await self.get_execution_binding()
                sample = await self._read_bound_sample()
                if (binding is None or journal.binding != binding
                        or sample.status.state not in {PlayerState.PLAYING, PlayerState.PAUSED}
                        or sample.error
                        or sample.status.song_position != 0
                        or sample.status.song_id != binding.entries[0][1]
                        or (sample.single, sample.consume, sample.status.random, sample.status.repeat)
                        != ("0", False, False, False)):
                    return unknown
                queue = await self.queue_manager.get_snapshot()
                if sum(item.position > 0 for item in queue.items) >= self.autoplay.LOW_WATERMARK:
                    return reconciled
                planned = await self.autoplay.plan_refill(await self._queue_playback_context(previous), queue)
                if not planned:
                    return RecoveryResult(reconciled.outcome, previous, reconciled.transition_id,
                                          diagnostic="NO_CANDIDATES")
                additions = tuple([(item.queue_item_id, (await self._require_available_song(item.song_id)).file_uri)
                                   for item in planned])
                intent = ExecutionIntent(
                    journal.service_epoch, binding.binding_generation, operation_id,
                    queue.revision, sample, binding.entries,
                    tuple((item_id, uri) for item_id, _, uri in binding.entries) + additions,
                    ExecutionSynchronizer.append_commands(additions), binding.entries[0][0],
                    sample.status.state.value.upper(),
                )
                journal.prepare_execution(intent)
                journal.refill_items[operation_id] = planned
                journal.refill_bindings[operation_id] = binding
            else:
                # An outer rollback may have undone adoption and refill together.
                # Recreate only that fixed business projection; the executor below
                # must still prove ownership of the entire external command prefix.
                queue = await self.queue_manager.get_snapshot()
                adoption_id = self._execution_owner[1] + "/adopt"
                adoption = journal.execution_intents.get(adoption_id)
                if (queue.revision != intent.queue_revision and adoption is not None
                        and queue.revision == adoption.queue_revision
                        and adoption_id in journal.execution_samples):
                    final = journal.execution_samples[adoption_id]
                    adopted = await self.queue_manager.adopt_current(
                        adoption.entries[0][0], adoption.target_item_id,
                        expected_revision=adoption.queue_revision,
                    )
                    await self.history_service.discard_unconfirmed_active()
                    target = next(item for item in adopted.items if item.position == 0)
                    previous = await self._save_confirmed_status(
                        final.status, song_id=target.song_id,
                        context_id=previous.playback_context_id,
                        autoplay_enabled=previous.autoplay_enabled,
                    )
                    journal.advance()
                    journal.preserve_binding()
                    journal.binding = journal.refill_bindings[operation_id]
                    journal.synced_entries = journal.binding.entries
                    journal.sync_sample = intent.baseline
                    journal.commit_execution(adoption_id, RecoveryResult("APPLIED", previous, adoption_id))
            queue = await self.queue_manager.get_snapshot()
            if queue.revision != intent.queue_revision or previous is None or not previous.autoplay_enabled:
                journal.unknown_executions.add(operation_id)
                journal.invalidate_binding()
                raise PlaybackReconciliationError("UNKNOWN stale refill business baseline")
            # Execute first inside the same outer transaction. Fixed Queue IDs are
            # persisted only after all append responses and current facts confirm.
            executor = ExecutionSynchronizer(self.player, journal)
            cleanup_owner_id = self._execution_owner[1] + "/refill-current"
            cleanup_id = cleanup_owner_id + "/adopt"
            cleanup = journal.execution_intents.get(cleanup_id)
            try:
                final = (journal.execution_samples[operation_id] if cleanup is not None
                         else await executor.execute_append(intent))
            except PlaybackReconciliationError:
                journal.unknown_executions.add(operation_id)
                journal.invalidate_binding()
                # Roll back any staged adoption too; UNKNOWN is materialized outside.
                raise
            planned = journal.refill_items[operation_id]
            current = next(item for item in queue.items if item.position == 0)
            added = await self.queue_manager.queue_repository.add_autoplay_batch(
                [item.song_id for item in planned],
                playback_context_id=planned[0].playback_context_id,
                max_items=self.autoplay.REFILL_COUNT,
                allow_current_repeat=planned[0].song_id == current.song_id,
                expected_revision=intent.queue_revision, planned_items=planned,
            )
            if tuple(added) != planned:
                raise PlaybackReconciliationError("Fixed AutoPlay occurrences were not persisted")
            if cleanup is None:
                final = await executor.execute_append(intent)
            committed_queue = await self.queue_manager.get_snapshot()
            if cleanup is None:
                confirmed_binding = journal.bind(
                    final, item_ids=tuple(item_id for item_id, _ in intent.items),
                    queue_revision=committed_queue.revision,
                )
            else:
                journal.preserve_binding()
                confirmed_binding = journal.refill_cleanup_bindings[operation_id]
                journal.binding = confirmed_binding
                journal.synced_entries = confirmed_binding.entries
                journal.sync_sample = final
            if cleanup is not None or final.status.song_id != confirmed_binding.entries[0][1]:
                journal.refill_cleanup_bindings[operation_id] = confirmed_binding
                owner = self._execution_owner
                self._execution_owner = (owner[0], cleanup_owner_id)
                try:
                    adopted = await self.reconcile_external_status()
                    if adopted.reconciliation_required:
                        raise PlaybackReconciliationError("UNKNOWN refill current cleanup")
                    previous = adopted.playback
                finally:
                    self._execution_owner = owner
            else:
                await self._observations.confirmed(final.status, entries=final.entries)
            result = RecoveryResult("APPLIED", previous, operation_id)
            journal.commit_execution(operation_id, result)
            return result

        async with asyncio.timeout(read_timeout):
            try:
                return await maintain(self)
            except PlaybackReconciliationError as error:
                if not str(error).startswith("UNKNOWN"):
                    raise
                try:
                    transaction_identity(self.queue_manager.queue_repository.path)
                except RuntimeError:
                    # Our own outer boundary has already rolled back. An existing
                    # caller's outer boundary must instead receive the failure.
                    result = RecoveryResult(
                        "UNKNOWN", await self.queue_manager.get_playback_state(),
                        reconciliation_required=True, diagnostic="SYNC_FAILED",
                    )
                    generation = self._recovery.business_generation
                    await self._observations.diagnose(
                        result.diagnostic, generation, diagnostic_number,
                    )
                    return result
                raise

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
        confirmed_sample = await self._read_execution_sample()
        confirmed, confirmed_entries = confirmed_sample.status, confirmed_sample.entries
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
            self._recovery.bind(
                confirmed_sample, item_ids=tuple(item_id for item_id, _, _ in planned_execution),
                queue_revision=(await self.queue_manager.get_snapshot()).revision,
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
        self._control_targets.invalidate()
        journal = self._recovery
        operation_id = self._execution_owner[1]
        allocation_id = operation_id
        operation_id = journal.execution_attempts.get(allocation_id, allocation_id)
        executor = ExecutionSynchronizer(self.player, journal)
        async def read_retry_sample(intent_id: str) -> ExecutionSample:
            try:
                return await self._read_execution_sample()
            except BaseException:
                journal.unknown_executions.add(intent_id)
                raise

        queue_intent = journal.execution_intents.get(operation_id + "/queue")
        if queue_intent is not None:
            baseline = await read_retry_sample(queue_intent.operation_id)
            if baseline.connection_epoch != queue_intent.baseline.connection_epoch:
                receipts = journal.command_receipts[queue_intent.operation_id]
                if (queue_intent.operation_id in journal.unknown_executions
                        or any(receipt.phase == "sent" for receipt in receipts.values())):
                    raise PlaybackReconciliationError("UNKNOWN lost response cannot be taken over by retry")
                journal.unknown_executions.add(queue_intent.operation_id)
                operation_id = allocation_id + "/takeover/" + baseline.connection_epoch
                journal.execution_attempts[allocation_id] = operation_id
                queue_intent = None
        if queue_intent is not None:
            if not queue_intent.items or queue_intent.items[0][1] != song.file_uri:
                raise PlaybackReconciliationError("Execution identity conflict: requested song changed")
            sample = await executor.execute(queue_intent)
        else:
            prepare_id = journal.execution_preparations.get(operation_id, operation_id + "/prepare")
            intent = journal.execution_intents.get(prepare_id)
            baseline = None
            if intent is not None:
                if prepare_id in journal.unknown_executions:
                    raise PlaybackReconciliationError("UNKNOWN explicit execution requires handling")
                baseline = await read_retry_sample(prepare_id)
                if baseline.connection_epoch != intent.baseline.connection_epoch:
                    receipts = journal.command_receipts[prepare_id]
                    if any(receipt.phase == "sent" for receipt in receipts.values()):
                        raise PlaybackReconciliationError("UNKNOWN lost explicit response")
                    # This is a fresh, explicit takeover after a known ACK or
                    # rejection, never recovery replay of an uncertain command.
                    journal.unknown_executions.add(prepare_id)
                    prepare_id = operation_id + "/prepare/" + baseline.connection_epoch
                    intent = None
            if intent is None:
                baseline = baseline or await self._read_execution_sample()
                # An explicit request may select an existing execution entry.
                # This temporary control identity never binds a business occurrence.
                mapping = tuple((f"prepare:{entry.mpd_song_id}", entry.mpd_song_id, entry.song_uri)
                                for entry in baseline.entries)
                target = next((item_id for item_id, _, uri in mapping if uri == song.file_uri), None)
                items = tuple((item_id, uri) for item_id, _, uri in mapping)
                commands = []
                if target is None:
                    target = "prepare:new"
                    items += ((target, song.file_uri),)
                    commands.append(ExecutionCommand("add", target, uri=song.file_uri))
                commands.append(ExecutionCommand("play", target, uri=song.file_uri))
                intent = ExecutionIntent(
                    journal.service_epoch, journal.binding.binding_generation if journal.binding else journal._binding_generation,
                    prepare_id, (await self.queue_manager.get_snapshot()).revision,
                    baseline, mapping, items, tuple(commands), target, "PLAYING", True,
                )
                journal.execution_preparations[operation_id] = prepare_id
            sample = await executor.execute(intent)
            journal.commit_execution(prepare_id, RecoveryResult("APPLIED", None, prepare_id))
        status = await self.player.status()
        if (
            status.state != PlayerState.PLAYING
            or status.song_uri != song.file_uri
            or status.song_id != sample.status.song_id
            or status.song_position != sample.status.song_position
        ):
            raise PlaybackReconciliationError(
                "MPD did not confirm the requested current track"
            )
        return status

    @_atomic_history_transition
    async def _sync_player_queue(
        self, *, previous_items: Sequence[QueueItem] | None = None,
    ) -> None:
        desired = await self._desired_song_uris()
        queue = await self.queue_manager.get_snapshot()
        execution = sorted((item for item in queue.items if item.position >= 0), key=lambda item: item.position)
        items = tuple((item.queue_item_id, uri) for item, uri in zip(execution, desired, strict=True))
        journal = self._recovery
        allocation_id = self._execution_owner[1]
        operation_id = journal.execution_attempts.get(allocation_id, allocation_id) + "/queue"
        intent = journal.execution_intents.get(operation_id)
        executor = ExecutionSynchronizer(self.player, journal)
        if intent is not None:
            if intent.items != items or intent.queue_revision != queue.revision:
                raise PlaybackReconciliationError("Execution identity conflict: fixed Queue changed")
        else:
            sample = await self._read_execution_sample()
            binding = journal.binding
            state = await self.queue_manager.get_playback_state()
            explicit = (
                getattr(self, "_binding_control_owner", None) is transaction_identity(journal.path)
                and (getattr(self, "_binding_origin_id", None) is None
                     or (bool(execution) and execution[0].queue_item_id != self._binding_origin_id))
            )
            if binding is not None and not journal.accepts(sample):
                if not explicit:
                    raise PlaybackReconciliationError("MPD execution binding lost before queue sync")
                binding = None
            stopped_sample = journal.sync_sample
            stopped_owned = (
                state is not None and state.state == "STOPPED" and stopped_sample is not None
                and sample.connection_epoch == stopped_sample.connection_epoch
                and sample.partition == stopped_sample.partition
                and sample.playlist_version == stopped_sample.playlist_version
                and sample.entries == stopped_sample.entries
            )
            if binding is None and not explicit and not stopped_owned and state is not None:
                journal.invalidate_binding()
                raise PlaybackReconciliationError("Queue mutation requires an execution binding")
            mapping = binding.entries if binding else journal.synced_entries if stopped_owned else ()
            if (binding is not None and execution and binding.entries
                    and execution[0].queue_item_id == binding.entries[0][0] and not explicit
                    and state is not None and state.state != "STOPPED"
                    and (sample.status.song_id != binding.entries[0][1]
                         or sample.status.song_position != 0
                         or sample.status.state.value != state.state.lower())):
                raise PlaybackReconciliationError("Queue mutation requires the confirmed current")
            ids = {item_id: mpd_id for item_id, mpd_id, _ in mapping}
            names = {mpd_id: item_id for item_id, mpd_id, _ in mapping}
            simulated = [(entry.mpd_song_id, names.get(entry.mpd_song_id)) for entry in sample.entries]
            commands = []
            for position, (item_id, uri) in enumerate(items):
                if item_id not in ids:
                    commands.append(ExecutionCommand("add", item_id, uri=uri))
                    simulated.append((None, item_id))
                index = next(i for i, row in enumerate(simulated) if row[1] == item_id)
                if index != position:
                    before_id, before_item = simulated[position]
                    commands.append(ExecutionCommand("move", item_id, before_item_id=before_item,
                                                     before_mpd_song_id=before_id if before_item is None else None))
                    row = simulated.pop(index)
                    simulated.insert(position, row)
            wanted = {item_id for item_id, _ in items}
            for mpd_id, item_id in reversed(simulated):
                if item_id not in wanted:
                    commands.append(ExecutionCommand("delete", mpd_song_id=mpd_id))
            target = items[0][0] if items and state is not None and state.state != "STOPPED" else None
            if target is not None and (ids.get(target) != sample.status.song_id
                                       or sample.status.state == PlayerState.STOPPED):
                if not explicit:
                    raise PlaybackReconciliationError("UNKNOWN execution cannot restart current")
                commands.append(ExecutionCommand("play", target))
                if state.state == "PAUSED":
                    commands.append(ExecutionCommand("pause"))
            target_state = state.state if state else "STOPPED"
            if (explicit and target is not None
                    and ids.get(target) == sample.status.song_id
                    and sample.status.state == PlayerState.PLAYING):
                # Explicit successor playback was already confirmed by _prepare_play.
                target_state = "PLAYING"
            intent = ExecutionIntent(
                journal.service_epoch, binding.binding_generation if binding else journal._binding_generation,
                operation_id, queue.revision, sample, tuple(mapping), items, tuple(commands),
                target, target_state, explicit,
            )
        journal.preserve_binding()
        final = await executor.execute(intent)
        status = await self.player.status()
        if (status.state, status.song_id, status.song_position) != (
                final.status.state, final.status.song_id, final.status.song_position):
            raise PlaybackReconciliationError("UNKNOWN current changed after queue confirmation")
        planned = executor.mapping(intent)
        journal.synced_entries, journal.sync_sample = planned, final
        if (planned and final.status.state in {PlayerState.PLAYING, PlayerState.PAUSED}
                and final.status.song_id == planned[0][1] and final.status.song_position == 0):
            journal.bind(final, item_ids=tuple(item_id for item_id, _, _ in planned), queue_revision=queue.revision)
        journal.commit_execution(operation_id, RecoveryResult(
            "APPLIED", await self.queue_manager.get_playback_state(), operation_id,
        ))

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
        await self._observations.changed(status)
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
