from uuid import uuid4

from server.app.models.playback_control import PlaybackControlTarget
from server.app.repositories.database import (
    on_transaction_rollback,
    on_transaction_visible,
    transaction_identity,
)


class PlaybackTargetConflictError(ValueError):
    """The requested occurrence or control lifetime is no longer confirmed."""


class PlaybackControlTargets:
    """Runtime target owner; irreversible invalidation outlives DB rollback."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.identity: tuple[object, ...] | None = None
        self.target: PlaybackControlTarget | None = None
        self.generation = 0
        self._owners: set[object] = set()

    def publish(self, identity: tuple[object, ...], queue_item_id: str) -> PlaybackControlTarget:
        if self.identity == identity and self.target is not None:
            return self.target
        owner = transaction_identity(self.path)
        if owner not in self._owners:
            prior_identity, prior_target, generation = self.identity, self.target, self.generation
            self._owners.add(owner)

            def rollback():
                if self.generation == generation:
                    self.identity, self.target = prior_identity, prior_target
                else:
                    self.identity, self.target = None, None
                self._owners.discard(owner)

            on_transaction_rollback(self.path, rollback)
            on_transaction_visible(self.path, lambda: self._owners.discard(owner))
        self.identity = identity
        self.target = PlaybackControlTarget(queue_item_id=queue_item_id, token=str(uuid4()))
        return self.target

    def invalidate(self) -> None:
        self.generation += 1
        self.identity, self.target = None, None

    def read(self, queue_item_id: str) -> PlaybackControlTarget | None:
        return self.target if self.target and self.target.queue_item_id == queue_item_id else None

    def require(self, target: PlaybackControlTarget) -> None:
        if self.target is None or target != self.target:
            raise PlaybackTargetConflictError("Playback control target is no longer valid")
