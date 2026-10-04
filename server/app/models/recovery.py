from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from server.app.models.queue import PlaybackState, QueueItem, QueueSnapshot
from server.app.models.realtime import HistoryAvailability


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
