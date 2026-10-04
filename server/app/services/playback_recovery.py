from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

from server.app.models.queue import QueueItem
from server.app.models.recovery import (
    CompletionEvidence,
    RecoveryBaseline,
    RecoveryIdentity,
    RecoveryPlan,
    RecoveryResult,
)
from server.app.repositories.database import (
    on_transaction_rollback,
    on_transaction_visibility_failure,
    on_transaction_visible,
    transaction_identity,
)


class RecoveryJournal:
    """Process-local business identity; independent of observation sample count."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.service_epoch = str(uuid4())
        self.business_generation = 0
        self._owners: set[object] = set()
        self.pending: dict[RecoveryIdentity, RecoveryPlan] = {}
        self.receipts: dict[RecoveryIdentity, RecoveryResult | None] = {}
        self.execution: dict[RecoveryIdentity, tuple[tuple[str, int, str], ...]] = {}
        self.quarantined = False

    @staticmethod
    def identity(evidence: CompletionEvidence) -> RecoveryIdentity:
        return (evidence.service_epoch, evidence.business_generation,
                evidence.queue_item_id, evidence.transition_id)

    def get_receipt(self, identity: RecoveryIdentity, evidence: CompletionEvidence) -> RecoveryResult | None:
        plan = self.pending.get(identity)
        if plan is not None and plan.evidence != evidence:
            raise ValueError("Recovery identity has conflicting evidence")
        receipt = self.receipts.get(identity)
        return replace(deepcopy(receipt), outcome="REPLAYED") if receipt else None

    def prepare(self, evidence: CompletionEvidence, baseline: RecoveryBaseline,
                planned_pending: tuple[QueueItem, ...]) -> RecoveryPlan:
        identity = self.identity(evidence)
        existing = self.pending.get(identity)
        if existing is not None:
            if existing.evidence != evidence:
                raise ValueError("Recovery identity has conflicting evidence")
            return deepcopy(existing)
        plan = RecoveryPlan(identity, evidence, deepcopy(baseline), deepcopy(planned_pending),
                            planned_pending[0].queue_item_id if planned_pending else None)
        self.pending[identity] = plan
        return deepcopy(plan)

    def commit(self, identity: RecoveryIdentity, result: RecoveryResult) -> None:
        receipt = deepcopy(result)
        # Reserve/materialize while rollback is still possible. Visibility only
        # switches the preallocated slot; failed visibility never reexecutes it.
        self.receipts[identity] = None
        on_transaction_rollback(self.path, lambda: self.receipts.pop(identity, None))
        on_transaction_visible(self.path, lambda: self.receipts.__setitem__(identity, receipt))

        def failure():
            if self.receipts.get(identity) is None:
                self.quarantined = True

        on_transaction_visibility_failure(self.path, failure)

    def advance(self) -> None:
        owner = transaction_identity(self.path)
        if owner not in self._owners:
            generation = self.business_generation
            self._owners.add(owner)

            def rollback():
                self.business_generation = generation
                self._owners.discard(owner)

            on_transaction_rollback(self.path, rollback)
            on_transaction_visible(self.path, lambda: self._owners.discard(owner))
        self.business_generation += 1
