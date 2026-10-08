from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from server.app.models.realtime import ActualCurrent, PlaybackObservation
from server.app.player.ports import PlayerCommandError, PlayerUnavailable
from server.app.repositories.database import (
    on_transaction_rollback,
    on_transaction_visible,
    run_transaction,
    transaction_identity,
)

if TYPE_CHECKING:
    from server.app.player.models import PlayerQueueEntry, PlayerStatus
    from server.app.services.playback_service import PlaybackService


class PlaybackObservations:
    """Runtime occurrence proof and observation cache; never controls the player."""

    def __init__(
        self, service: PlaybackService, clock: Callable[[], datetime] | None, max_age: float = 6,
    ) -> None:
        self.service = service
        self.path = service.queue_manager.queue_repository.path
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.max_age = max_age
        self.cache = PlaybackObservation()
        self._confirmed_identity: tuple[object, ...] | None = None
        self.generation = 0
        self._sample_number = 0
        self._accepted_sample = 0
        self._owners: set[object] = set()
        self._sample_sync_status = 'UNBOUND'
        self._sync_diagnostic: str | None = None
        self._confirmed_stop: tuple[object, ...] | None = None
        self._diagnostic_number = 0
        self._accepted_diagnostic = 0

    def _effective_sync_status(self) -> str:
        if (self._sample_sync_status == 'CONFIRMED'
                and self._sync_diagnostic in {'SYNC_FAILED', 'NO_CANDIDATES'}):
            return self._sync_diagnostic
        return self._sample_sync_status

    def _preserve(self) -> None:
        owner = transaction_identity(self.path)
        if owner in self._owners:
            return
        (
            cache, identity, generation, accepted, sample_status, diagnostic,
            confirmed_stop, accepted_diagnostic,
        ) = (
            self.cache, self._confirmed_identity, self.generation, self._accepted_sample,
            self._sample_sync_status, self._sync_diagnostic, self._confirmed_stop,
            self._accepted_diagnostic,
        )
        self._owners.add(owner)

        def rollback():
            self.cache, self._confirmed_identity, self.generation = cache, identity, generation
            self._accepted_sample = accepted
            self._sample_sync_status, self._sync_diagnostic = sample_status, diagnostic
            self._confirmed_stop = confirmed_stop
            self._accepted_diagnostic = accepted_diagnostic
            self._owners.discard(owner)

        on_transaction_rollback(self.path, rollback)
        on_transaction_visible(self.path, lambda: self._owners.discard(owner))

    async def _set(self, observation: PlaybackObservation) -> None:
        self._preserve()
        before = await self.service._transport_content()
        self.cache = observation
        if self.service._coordinator is not None:
            after = await self.service._transport_content()
            self.service._coordinator.stage_change(
                frozenset({'playback'}), before['playback'], after['playback'],
            )

    async def _identity(self) -> tuple[object, ...]:
        state = await self.service.queue_manager.get_playback_state()
        current = next((i for i in await self.service.queue_manager.list_items() if i.position == 0), None)
        return (self.service.player, current.queue_item_id if current else None,
                state.song_id if state else None, state.playback_context_id if state else None)

    @property
    def binding(self):
        """Compatibility view for the isolated legacy completion consumer."""
        binding = self.service._recovery.binding
        if binding is None or not binding.entries or self._confirmed_identity is None:
            return None
        return (*self._confirmed_identity, binding.entries[0][1],
                binding.entries[0][2], binding.entries)

    @binding.setter
    def binding(self, value):
        if value is not None:
            raise ValueError("Binding requires explicitly confirmed control IDs")
        self.service._recovery.invalidate_binding()

    async def changed(self, status: PlayerStatus | None = None) -> None:
        self._preserve()
        self.generation += 1
        self._sample_sync_status = 'UNBOUND'
        self._sync_diagnostic = None
        if status is not None and status.state.value == 'stopped':
            journal = self.service._recovery
            binding = journal.binding
            self._confirmed_stop = (
                (
                    self.service.player,
                    binding.connection_epoch,
                    binding.playlist_version,
                    binding.entries,
                    (status.song_id, status.song_uri, status.song_position),
                )
                if binding is not None else None
            )
            journal.preserve_binding()
            journal.binding = None
        else:
            self._confirmed_stop = None
        await self._set(PlaybackObservation())

    async def confirmed(
        self, status: PlayerStatus, *, entries: Sequence[PlayerQueueEntry] | None = None,
    ) -> None:
        # Confirmation is owned by Service. This cache cannot create a mapping.
        self._preserve()
        self._confirmed_identity = await self._identity()

    async def get(self) -> PlaybackObservation:
        async def read(_):
            binding = await self.service.get_execution_binding()
            if binding is None and self.cache.matches_current is True:
                self._preserve()
                self._sample_sync_status = 'UNBOUND'
                await self._set(self.cache.model_copy(update={
                    'matches_current': None, 'freshness': 'stale',
                    'actual_freshness': (
                        'stale' if self.cache.observed_at is not None else 'unknown'
                    ),
                    'bound_queue_item_id': None,
                    'sync_status': self._effective_sync_status(),
                    'reconciliation_required': True,
                }, deep=True))
            if ((self.cache.freshness == 'fresh' or self.cache.actual_freshness == 'fresh')
                    and self.cache.observed_at is not None
                    and (self.clock() - self.cache.observed_at).total_seconds() > self.max_age):
                self._preserve()
                self._sample_sync_status = 'UNBOUND'
                await self._set(self.cache.model_copy(update={
                    'freshness': (
                        'stale' if self.cache.freshness == 'fresh' else self.cache.freshness
                    ),
                    'actual_freshness': 'stale',
                    'bound_queue_item_id': None,
                    'sync_status': self._effective_sync_status(),
                }, deep=True))
            return self.cache.model_copy(deep=True)

        return await run_transaction(self.path, read)

    def begin_diagnostic(self) -> int:
        """Order maintenance diagnostics before any asynchronous execution starts."""
        self._diagnostic_number += 1
        return self._diagnostic_number

    async def diagnose(
        self, diagnostic: str | None, business_generation: int, operation_number: int,
    ) -> None:
        if diagnostic not in {None, 'SYNC_FAILED', 'NO_CANDIDATES'}:
            return

        async def accept(_):
            if (self.service._recovery.business_generation != business_generation
                    or operation_number < self._accepted_diagnostic):
                return
            self._preserve()
            self._accepted_diagnostic = operation_number
            self._sync_diagnostic = diagnostic
            status = self._effective_sync_status()
            await self._set(self.cache.model_copy(update={
                'sync_status': status,
                'reconciliation_required': (
                    status == 'SYNC_FAILED'
                    if self._sample_sync_status == 'CONFIRMED'
                    else self.cache.reconciliation_required
                ),
            }, deep=True))

        await run_transaction(self.path, accept)

    async def observe(self, read_timeout: float | None = None) -> PlaybackObservation:
        # A caller's pending owner cannot authorize an external sample as committed.
        try:
            transaction_identity(self.path)
        except RuntimeError:
            pass
        else:
            raise RuntimeError('Playback observation requires a committed boundary')

        async def token(_):
            await self.get()
            return (self.generation, await self._identity(), await self.service.get_execution_binding())

        before = await run_transaction(self.path, token)
        self._sample_number += 1
        sample_number = self._sample_number
        player = self.service.player
        failure = None
        try:
            sample = await asyncio.wait_for(player.read_execution_sample(), read_timeout)
            status, entries = sample.status, sample.entries
        except (PlayerUnavailable, PlayerCommandError, TimeoutError, ValueError) as error:
            failure = error

        async def accept(_):
            if before != await token(None) or sample_number < self._accepted_sample:
                return await self.get()
            self._preserve()
            self._accepted_sample = sample_number
            if failure is not None:
                self.service._recovery.invalidate_binding()
                self._sample_sync_status = 'UNBOUND'
                code = ('PLAYER_UNAVAILABLE' if isinstance(failure, PlayerUnavailable)
                        else 'PLAYER_TIMEOUT' if isinstance(failure, TimeoutError)
                        else 'PLAYER_COMMAND_ERROR' if isinstance(failure, PlayerCommandError)
                        else 'PLAYER_OBSERVATION_FAILED')
                await self._set(self.cache.model_copy(update={
                    'freshness': 'stale' if self.cache.matches_current is True else 'unknown',
                    'actual_freshness': (
                        'stale' if self.cache.observed_at is not None else 'unknown'
                    ),
                    'bound_queue_item_id': None,
                    'sync_status': self._effective_sync_status(),
                    'error_code': code, 'error_message': str(failure),
                    'reconciliation_required': True,
                }, deep=True))
                return await self.get()
            state = await self.service.queue_manager.get_playback_state()
            had_binding = await self.service.get_execution_binding() is not None
            self.service._recovery.accepts(sample)
            binding = await self.service.get_execution_binding()
            matched = (
                binding is not None and bool(binding.entries) and state is not None
                and status.state.value == state.state.lower()
                and status.song_id == binding.entries[0][1] and status.song_uri == binding.entries[0][2]
                and status.song_position == 0 and bool(entries)
                and entries[0].position == 0 and entries[0].mpd_song_id == binding.entries[0][1]
                and entries[0].song_uri == binding.entries[0][2]
            )
            actual_current = None
            if any(value is not None for value in (
                status.song_id, status.song_uri, status.song_position,
            )):
                actual_current = ActualCurrent(
                    entry_id=status.song_id,
                    uri=status.song_uri,
                    position=status.song_position,
                )
            confirmed_stop = False
            if self._confirmed_stop is not None:
                stop_player, stop_epoch, stop_version, stop_entries, stop_status = (
                    self._confirmed_stop
                )
                confirmed_stop = (
                    state is not None and state.state == 'STOPPED'
                    and status.state.value == 'stopped'
                    and stop_player is self.service.player
                    and stop_epoch == sample.connection_epoch
                    and stop_version == sample.playlist_version
                    and tuple(
                        (entry.mpd_song_id, entry.song_uri, entry.position)
                        for entry in entries
                    ) == tuple(
                        (mpd_song_id, uri, position)
                        for position, (_, mpd_song_id, uri) in enumerate(stop_entries)
                    )
                    and stop_status == (status.song_id, status.song_uri, status.song_position)
                )
            if status.state.value != 'stopped' or not confirmed_stop:
                self._confirmed_stop = None
            sample_sync_status = (
                'CONFIRMED' if matched or confirmed_stop
                else 'UNCONFIRMED_STOP' if had_binding and status.state.value == 'stopped'
                else 'EXTERNAL_DRIFT' if had_binding
                else 'UNBOUND'
            )
            self._sample_sync_status = sample_sync_status
            sync_status = self._effective_sync_status()
            await self._set(PlaybackObservation(
                actual_state=status.state,
                actual_current=actual_current,
                actual_freshness='fresh',
                bound_queue_item_id=(binding.entries[0][0] if matched else None),
                sync_status=sync_status,
                matches_current=(True if matched else False if (
                    had_binding and status.song_id is not None
                ) else None),
                position_seconds=status.elapsed_seconds if matched else None,
                duration_seconds=status.duration_seconds if matched else None,
                observed_at=self.clock(), freshness='fresh' if matched else 'unknown',
                reconciliation_required=(
                    sync_status == 'SYNC_FAILED'
                    or sample_sync_status != 'CONFIRMED'
                ),
            ))
            return self.cache.model_copy(deep=True)

        return await run_transaction(self.path, accept)
