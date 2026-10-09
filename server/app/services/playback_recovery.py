from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

from server.app.models.queue import PlaybackContext, QueueItem
from server.app.models.recovery import (
    CommandReceipt,
    CompletionEvidence,
    ExecutionBinding,
    ExecutionIntent,
    RecoveryBaseline,
    RecoveryIdentity,
    RecoveryPlan,
    RecoveryResult,
)
from server.app.player.models import ExecutionSample
from server.app.repositories.database import (
    on_transaction_rollback,
    on_transaction_visibility_failure,
    on_transaction_visible,
    transaction_identity,
)


class RecoveryJournal:
    """Process-local business identity; independent of observation sample count."""

    def __init__(self, path: str, *, invalidate_targets=None) -> None:
        self.path = path
        self._invalidate_targets = invalidate_targets
        self.service_epoch = str(uuid4())
        self.business_generation = 0
        self._owners: set[object] = set()
        self.pending: dict[RecoveryIdentity, RecoveryPlan] = {}
        self.receipts: dict[RecoveryIdentity, RecoveryResult | None] = {}
        self.execution: dict[RecoveryIdentity, tuple[tuple[str, int, str], ...]] = {}
        self.quarantined = False
        self.binding: ExecutionBinding | None = None
        self.synced_entries: tuple[tuple[str, int, str], ...] | None = None
        self.sync_sample: ExecutionSample | None = None
        self._binding_generation = 0
        self._invalidation = 0
        self._binding_owners: set[object] = set()
        self.execution_intents: dict[str, ExecutionIntent] = {}
        self.refill_items: dict[str, tuple[QueueItem, ...]] = {}
        self.refill_bindings: dict[str, ExecutionBinding] = {}
        self.refill_cleanup_bindings: dict[str, ExecutionBinding] = {}
        self.command_receipts: dict[str, dict[int, CommandReceipt]] = {}
        self.execution_receipts: dict[str, RecoveryResult | None] = {}
        self.execution_samples: dict[str, ExecutionSample] = {}
        self.execution_fences: dict[str, tuple[int, int]] = {}
        self.unknown_executions: set[str] = set()
        self.operation_ids: dict[tuple, str] = {}
        self.execution_contexts: dict[str, tuple[str, PlaybackContext]] = {}
        self.execution_preparations: dict[str, str] = {}
        self.execution_attempts: dict[str, str] = {}
        self.history_active_qualifications: dict[str, tuple[tuple[object, ...], bool]] = {}

    def prepare_context(self, request_id: str, payload: str, context: PlaybackContext) -> PlaybackContext:
        prior = self.execution_contexts.get(request_id)
        if prior is not None:
            if prior[0] != payload:
                raise self.conflict("Execution context identity conflict")
            return prior[1].model_copy(deep=True)
        self.execution_contexts[request_id] = (payload, context.model_copy(deep=True))
        return context

    def operation_id(self, key: tuple) -> str:
        return self.operation_ids.setdefault(key, str(uuid4()))

    def prepare_history_active(
        self, operation_id: str, identity: tuple[object, ...],
    ) -> bool:
        prior = self.history_active_qualifications.get(operation_id)
        if prior is not None:
            if prior[0] != identity:
                raise self.conflict("History active identity conflict")
            return prior[1]
        self.history_active_qualifications[operation_id] = (identity, False)
        return False

    def confirm_history_active(
        self, operation_id: str, identity: tuple[object, ...],
    ) -> None:
        prior = self.history_active_qualifications.get(operation_id)
        if prior is None or prior[0] != identity:
            raise self.conflict("History active was not qualified")
        self.history_active_qualifications[operation_id] = (identity, True)
        on_transaction_visible(
            self.path,
            lambda: self.history_active_qualifications.pop(operation_id, None),
        )

    @staticmethod
    def conflict(message: str):
        # Keep the public Service error without a module import cycle.
        from server.app.services.playback_service import PlaybackReconciliationError
        return PlaybackReconciliationError(message)

    def prepare_execution(self, intent: ExecutionIntent) -> ExecutionIntent:
        old = self.execution_intents.get(intent.operation_id)
        if old is not None:
            if old != intent:
                raise self.conflict("Execution identity conflict")
            return old
        if (intent.service_epoch != self.service_epoch
                or intent.binding_generation != (self.binding.binding_generation if self.binding else self._binding_generation)):
            raise self.conflict("UNKNOWN execution generation")
        self.execution_intents[intent.operation_id] = intent
        self.command_receipts[intent.operation_id] = {}
        self.execution_fences[intent.operation_id] = (self._invalidation, self.business_generation)
        return intent

    def record_command(self, operation_id: str, index: int, receipt: CommandReceipt) -> None:
        intent = self.execution_intents[operation_id]
        if not 0 <= index < len(intent.commands):
            raise self.conflict("Command index conflict")
        receipts = self.command_receipts[operation_id]
        if any(receipts.get(i, CommandReceipt("sent")).phase != "confirmed" for i in range(index)):
            raise self.conflict("Unconfirmed command prefix")
        old = receipts.get(index)
        allowed = {None: {"sent"}, "sent": {"ack", "rejected", "confirmed"},
                   "ack": {"confirmed"}, "rejected": {"sent"}, "confirmed": set()}
        if receipt == old:
            return
        if receipt.phase not in allowed[old.phase if old else None]:
            raise self.conflict("Command receipt conflict")
        receipts[index] = receipt

    def get_execution_receipt(self, operation_id: str) -> RecoveryResult | None:
        receipt = self.execution_receipts.get(operation_id)
        return replace(deepcopy(receipt), outcome="REPLAYED") if receipt else None

    def commit_execution(self, operation_id: str, result: RecoveryResult) -> None:
        receipt = deepcopy(result)
        self.execution_receipts[operation_id] = None
        on_transaction_rollback(self.path, lambda: self.execution_receipts.pop(operation_id, None))
        on_transaction_visible(self.path, lambda: self.execution_receipts.__setitem__(operation_id, receipt))
        on_transaction_visibility_failure(self.path, lambda: setattr(self, "quarantined", True))

    def preserve_binding(self) -> None:
        owner = transaction_identity(self.path)
        if owner in self._binding_owners:
            return
        binding, synced, sample, invalidation = (
            self.binding, self.synced_entries, self.sync_sample, self._invalidation,
        )
        self._binding_owners.add(owner)

        def rollback():
            # A business rollback cannot restore lost external continuity.
            if self._invalidation == invalidation:
                self.binding, self.synced_entries, self.sync_sample = binding, synced, sample
            else:
                self.invalidate_binding()
            self._binding_owners.discard(owner)

        on_transaction_rollback(self.path, rollback)
        on_transaction_visible(self.path, lambda: self._binding_owners.discard(owner))

    def bind(self, sample: ExecutionSample, *, item_ids: tuple[str, ...],
             queue_revision: int) -> ExecutionBinding:
        if (len(item_ids) != len(sample.entries) or len(set(item_ids)) != len(item_ids)
                or len({entry.mpd_song_id for entry in sample.entries}) != len(item_ids)
                or tuple(entry.position for entry in sample.entries) != tuple(range(len(item_ids)))):
            raise ValueError("Invalid confirmed occurrence mapping")
        self.preserve_binding()
        self._binding_generation += 1
        self.binding = ExecutionBinding(
            self.service_epoch, sample.connection_epoch, self._binding_generation,
            sample.partition, queue_revision, sample.playlist_version,
            tuple((item_id, entry.mpd_song_id, entry.song_uri)
                  for item_id, entry in zip(item_ids, sample.entries, strict=True)),
        )
        self.synced_entries = self.binding.entries
        self.sync_sample = sample
        return self.binding

    def invalidate_binding(self) -> None:
        if self._invalidate_targets is not None:
            self._invalidate_targets()
        self._invalidation += 1
        self.binding = None
        self.synced_entries = None
        self.sync_sample = None

    def accepts(self, sample: ExecutionSample) -> bool:
        binding = self.binding
        matched = (
            binding is not None and binding.service_epoch == self.service_epoch
            and binding.connection_epoch == sample.connection_epoch
            and binding.partition == sample.partition
            and binding.playlist_version == sample.playlist_version
            and tuple((entry.mpd_song_id, entry.song_uri, entry.position)
                      for entry in sample.entries)
            == tuple((mpd_id, uri, position)
                     for position, (_, mpd_id, uri) in enumerate(binding.entries))
        )
        if not matched:
            if self.owns_execution_prefix(sample):
                # The old business mapping is unconfirmed, but a read must not
                # destroy the separately owned external prefix after rollback.
                self.binding = None
                self.synced_entries = None
                self.sync_sample = None
            else:
                self.invalidate_binding()
        return matched

    def owns_execution_prefix(self, sample: ExecutionSample) -> bool:
        from server.app.services.playback_execution import ExecutionSynchronizer

        for operation_id, intent in self.execution_intents.items():
            receipts = self.command_receipts[operation_id]
            if (self.execution_receipts.get(operation_id) is not None
                    or operation_id in self.unknown_executions
                    or self.execution_fences[operation_id] != (self._invalidation, self.business_generation)
                    or (self.binding is not None and self.binding.binding_generation != intent.binding_generation)
                    or not receipts or any(receipt.phase == "sent" for receipt in receipts.values())):
                continue
            expected = intent.baseline
            for index, command in enumerate(intent.commands):
                receipt = receipts.get(index)
                if receipt is None or receipt.phase == "rejected":
                    break
                if receipt.phase == "confirmed":
                    expected = receipt.sample
                elif receipt.phase == "ack":
                    expected = ExecutionSynchronizer(None, self)._expected(intent, command, expected, receipt)
                    break
            if (sample.connection_epoch, sample.partition, sample.playlist_version, sample.entries,
                    sample.status.song_id, sample.status.song_position, sample.single, sample.consume,
                    sample.status.random, sample.status.repeat) == (
                    expected.connection_epoch, expected.partition, expected.playlist_version, expected.entries,
                    expected.status.song_id, expected.status.song_position, expected.single, expected.consume,
                    expected.status.random, expected.status.repeat):
                return True
        return False

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
