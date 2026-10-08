from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from server.app.models.queue import PlaybackState, QueueItem, QueueSnapshot
from server.app.models.realtime import HistoryAvailability
from server.app.player.models import ExecutionSample


@dataclass(frozen=True)
class CompletionEvidence:
    service_epoch: str
    source_id: str
    source_epoch: str
    continuity_token: str
    business_generation: int
    queue_revision: int
    queue_item_id: str
    mpd_song_id: int
    transition_id: str
    ended_at: datetime


@dataclass(frozen=True)
class RecoveryResult:
    outcome: Literal["UNKNOWN", "UNCHANGED", "APPLIED", "REPLAYED"]
    playback: PlaybackState | None
    transition_id: str | None = None
    reconciliation_required: bool = False
    diagnostic: str | None = None


RecoveryIdentity = tuple[str, int, str, str]


@dataclass(frozen=True)
class RecoveryBaseline:
    queue: QueueSnapshot
    playback: PlaybackState
    history: HistoryAvailability
    business_generation: int
    mpd_song_id: int


@dataclass(frozen=True)
class RecoveryPlan:
    identity: RecoveryIdentity
    evidence: CompletionEvidence
    baseline: RecoveryBaseline
    pending: tuple[QueueItem, ...]
    successor_id: str | None


class CompletionValidator(Protocol):
    async def validate(self, evidence: CompletionEvidence, baseline: RecoveryBaseline) -> bool: ...


@dataclass(frozen=True)
class ExecutionBinding:
    service_epoch: str
    connection_epoch: str
    binding_generation: int
    partition: str
    queue_revision: int
    playlist_version: int
    entries: tuple[tuple[str, int, str], ...]


@dataclass(frozen=True)
class ExecutionCommand:
    kind: Literal["add", "delete", "move", "play", "pause"]
    item_id: str | None = None
    mpd_song_id: int | None = None
    before_item_id: str | None = None
    before_mpd_song_id: int | None = None
    uri: str | None = None


@dataclass(frozen=True)
class ExecutionIntent:
    service_epoch: str
    binding_generation: int
    operation_id: str
    queue_revision: int
    baseline: ExecutionSample
    entries: tuple[tuple[str, int, str], ...]
    items: tuple[tuple[str, str], ...]
    commands: tuple[ExecutionCommand, ...]
    target_item_id: str | None
    target_state: str
    allow_start: bool = False


@dataclass(frozen=True)
class CommandReceipt:
    phase: Literal["sent", "ack", "confirmed", "rejected"]
    returned_id: int | None = None
    sample: ExecutionSample | None = None
