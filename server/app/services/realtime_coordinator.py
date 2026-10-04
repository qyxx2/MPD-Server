from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from uuid import uuid4

from server.app.models.realtime import Invalidation, StateMarker
from server.app.repositories.database import (
    on_transaction_rollback,
    on_transaction_visibility_failure,
    on_transaction_visible,
    run_transaction,
    transaction_identity,
)
from server.app.services.events import DomainEvent, EventPublisher, invalidation_domains


@dataclass(eq=False)
class RealtimeSubscription:
    """In-memory invalidation obligation; network delivery belongs to later Batches."""

    pending: Invalidation | None = None
    valid: bool = True


class RealtimeCoordinator:
    def __init__(self, path: str, event_publisher: EventPublisher | None = None) -> None:
        self.path = path
        self._marker = StateMarker(epoch=str(uuid4()))
        self._trusted = True
        self._subscriptions: set[RealtimeSubscription] = set()
        self._staged: dict[object, dict[str, tuple[object, object]]] = {}
        self._observations: dict[str, object] = {}
        self._event_publisher = event_publisher

    def stage_observation(self, domain: str, content: object) -> None:
        """Compare accepted runtime facts with the last visible committed content."""
        self.stage_change(frozenset({domain}), self._observations.get(domain), content)
        on_transaction_visible(
            self.path, lambda: self._observations.__setitem__(domain, deepcopy(content)),
        )

    def marker(self) -> StateMarker:
        if not self._trusted:
            raise RuntimeError("realtime snapshot marker unavailable; initialize a new epoch")
        return self._marker.model_copy(deep=True)

    def subscribe(self) -> RealtimeSubscription:
        self.marker()
        subscription = RealtimeSubscription()
        self._subscriptions.add(subscription)
        return subscription

    def stage_change(
        self, domains: frozenset[str], before: object, after: object,
    ) -> None:
        owner = transaction_identity(self.path)
        staged = self._staged.get(owner)
        if staged is None:
            staged = {}

            def committed():
                try:
                    changed = frozenset(
                        domain for domain, (first, last) in staged.items() if first != last
                    )
                    if changed:
                        self._register(changed)
                finally:
                    self._staged.pop(owner, None)

            on_transaction_visible(self.path, committed)
            on_transaction_visibility_failure(self.path, self._fail_closed)
            self._staged[owner] = staged
            on_transaction_rollback(self.path, lambda: self._staged.pop(owner, None))
        for domain in domains:
            first = staged[domain][0] if domain in staged else deepcopy(before)
            staged[domain] = first, deepcopy(after)

    async def publish(self, event: DomainEvent) -> None:
        domains = invalidation_domains(event)
        if domains:
            def register(_):
                on_transaction_visible(
                    self.path, lambda: self._register(domains, revise=False)
                )
                on_transaction_visibility_failure(self.path, self._fail_closed)

            await run_transaction(
                self.path, register,
            )
        if self._event_publisher is not None:
            await self._event_publisher.publish(event)

    def _fail_closed(self) -> None:
        self._trusted = False
        for subscription in self._subscriptions:
            subscription.valid = False
            subscription.pending = None
        self._subscriptions.clear()

    def close(self) -> None:
        self._fail_closed()

    def _register(self, domains: frozenset[str], *, revise: bool = True) -> None:
        self.marker()
        self._marker = StateMarker(
            epoch=self._marker.epoch,
            sequence=self._marker.sequence + 1,
            library_revision=self._marker.library_revision + (revise and "library" in domains),
            playlist_revision=self._marker.playlist_revision + (revise and "playlist" in domains),
        )
        notification = Invalidation(
            epoch=self._marker.epoch,
            sequence=self._marker.sequence,
            domains=domains,
            revisions={
                "library": self._marker.library_revision,
                "playlist": self._marker.playlist_revision,
            },
        )
        for subscription in self._subscriptions:
            pending_domains = subscription.pending.domains if subscription.pending else frozenset()
            subscription.pending = notification.model_copy(
                update={"domains": domains | pending_domains}, deep=True,
            )
