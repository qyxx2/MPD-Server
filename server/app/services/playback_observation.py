from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from server.app.models.realtime import PlaybackObservation
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
        self.binding: tuple[object, ...] | None = None
        self.generation = 0
        self._sample_number = 0
        self._accepted_sample = 0
        self._owners: set[object] = set()

    def _preserve(self) -> None:
        owner = transaction_identity(self.path)
        if owner in self._owners:
            return
        cache, binding, generation, accepted = (
            self.cache, self.binding, self.generation, self._accepted_sample,
        )
        self._owners.add(owner)

        def rollback():
            self.cache, self.binding, self.generation = cache, binding, generation
            self._accepted_sample = accepted
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

    async def changed(self) -> None:
        self._preserve()
        self.generation += 1
        identity = await self._identity()
        if self.binding is not None and self.binding[:4] != identity:
            self.binding = None
        await self._set(PlaybackObservation())

    async def confirmed(
        self, status: PlayerStatus, *, entries: Sequence[PlayerQueueEntry] | None = None,
    ) -> None:
        self._preserve()
        if entries is None:
            entries = await self.service.player.queue_entries()
        execution = sorted(
            (i for i in await self.service.queue_manager.list_items() if i.position >= 0),
            key=lambda i: i.position,
        )
        self.binding = (
            *await self._identity(), status.song_id, status.song_uri,
            tuple((i.queue_item_id, e.mpd_song_id, e.song_uri)
                  for i, e in zip(execution, entries, strict=True)),
        )

    async def get(self) -> PlaybackObservation:
        async def read(_):
            if self.binding is not None and self.binding[:4] != await self._identity():
                self._preserve()
                self.binding = None
                await self._set(PlaybackObservation())
            if (self.cache.freshness == 'fresh' and self.cache.observed_at is not None
                    and (self.clock() - self.cache.observed_at).total_seconds() > self.max_age):
                await self._set(self.cache.model_copy(update={'freshness': 'stale'}, deep=True))
            return self.cache.model_copy(deep=True)

        return await run_transaction(self.path, read)

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
            return (self.generation, await self._identity(), self.binding)

        before = await run_transaction(self.path, token)
        self._sample_number += 1
        sample_number = self._sample_number
        player = self.service.player
        failure = None
        try:
            async def sample():
                return await player.status(), await player.queue_entries()

            status, entries = await asyncio.wait_for(sample(), read_timeout)
        except (PlayerUnavailable, PlayerCommandError, TimeoutError, ValueError) as error:
            failure = error

        async def accept(_):
            if before != await token(None) or sample_number < self._accepted_sample:
                return await self.get()
            self._preserve()
            self._accepted_sample = sample_number
            if failure is not None:
                code = ('PLAYER_UNAVAILABLE' if isinstance(failure, PlayerUnavailable)
                        else 'PLAYER_TIMEOUT' if isinstance(failure, TimeoutError)
                        else 'PLAYER_COMMAND_ERROR' if isinstance(failure, PlayerCommandError)
                        else 'PLAYER_OBSERVATION_FAILED')
                await self._set(self.cache.model_copy(update={
                    'freshness': 'stale' if self.cache.matches_current is True else 'unknown',
                    'error_code': code, 'error_message': str(failure),
                }, deep=True))
                return await self.get()
            state = await self.service.queue_manager.get_playback_state()
            binding = self.binding
            matched = (
                binding is not None and state is not None
                and status.state.value == state.state.lower()
                and status.song_id == binding[4] and status.song_uri == binding[5]
                and status.song_position == 0 and bool(entries)
                and entries[0].position == 0 and entries[0].mpd_song_id == binding[4]
                and entries[0].song_uri == binding[5]
            )
            await self._set(PlaybackObservation(
                actual_state=status.state,
                matches_current=(True if matched else False if (
                    binding is not None and status.song_id is not None
                ) else None),
                position_seconds=status.elapsed_seconds if matched else None,
                duration_seconds=status.duration_seconds if matched else None,
                observed_at=self.clock(), freshness='fresh' if matched else 'unknown',
                reconciliation_required=not matched,
            ))
            return self.cache.model_copy(deep=True)

        return await run_transaction(self.path, accept)
