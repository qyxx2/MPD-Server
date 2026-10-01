# Task 5 Pre-Batch 6 C/D Corrective Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, TDD, and a fresh independent superpowers:requesting-code-review pass.

**Goal:** Repair reproduced C (History memory surviving playback rollback) and D (Next aborting on unavailable pending). This is not Batch 6 execution.

**Architecture:** PlaybackService remains the sole player orchestrator. History-changing playback methods join the existing SQLite transaction and register the existing History active/session rollback callback. Next removes unavailable pending occurrences, records their identities/reasons in service logs, resolves the next valid occurrence, and attempts AutoPlay on exhaustion. No new API/schema or History events for unplayed songs.

**Tech Stack:** Existing ARM64 `.venv`, FastAPI, SQLite, MockMPD. No dependency changes.

**Spec:** playback-model-queue-semantics-design §§2.2, 7, 8.3; Task 5 batch plan §4.7.7; current corrective handoff and archived pre-batch6 A/B corrective plan's independent blockers C/D.

## Global Constraints

- Use the user-specified clean feature checkout and existing `.venv`; no additional worktree/environment. The preceding applicable corrective plan explicitly specifies this checkout/branch.
- Only `server/app/services/playback_service.py`, directly affected corrective tests, and this plan/current handoff/status references are in scope. History/database boundaries may change only if required by a reproduced contract defect.
- No Batch 6, original Step 9–10 checkbox changes, future features, Docker/live MPD, PR or main merge.
- User authorizes commit/push after successful validation; publish only this corrective scope.

## Review Focus

- Outer terminal-record failure restores active event and session and permits identical-key retry without phantom History.
- Direct service calls roll back Queue/state/History on post-transition player failures.
- Context/previous/stop/reconciliation share the same History transaction guarantee.
- MISSING/UNREADABLE/absent pending identities are skipped with observable reasons, never recorded as played.
- All-unavailable exhaustion attempts AutoPlay; command/confirmation failures roll back skips; replay does not repeat commands/events.

## Task 1: C — atomic History-changing playback

**Files:** `server/app/services/playback_service.py`; `server/tests/api/test_pre_batch6_corrective.py`.

**Interfaces:** Consume `run_transaction(path, operation)` and `HistoryService.preserve_active_on_rollback()`; retain all public playback signatures and HTTP contracts. Produce atomic start_track/play_context/play_now/next/previous/stop/reconcile_external_status for both direct and outer transactions.

- [x] Run existing corrective baseline: 32 passed.
- [x] Add real SQLite terminal trigger tests for next/play_now/start_track, checking snapshot/state/persisted History/active/session before same-key retry and replay.
- [x] Observe RED: all three fail at active-event restoration, with persisted rollback assertions already passing.
- [x] Join/register rollback at each History-changing playback operation before mutations; validate final player confirmation after synchronization.
- [x] Expand RED/GREEN coverage to context/previous/stop/reconciliation and direct service failure.
- [x] Run exact targeted cases, then full corrective test file and affected services/API/integration.

## Task 2: D — unavailable successor resolution

**Files:** same playback service and corrective test file.

**Interfaces:** Consume Task 1 transaction guarantee; use existing QueueManager.delete(persist_state=False), LibraryRepository lookup and AutoPlay.refill. Preserve Queue revision semantics and public response schemas.

- [x] Add real API Next MISSING/UNREADABLE successor cases; observe two RED 404 responses instead of c.
- [x] Resolve unavailable pending occurrences before selection, log song/occurrence/reason, refill when empty, synchronize and confirm successful transition.
- [x] Cover absent identity, all-unavailable with/without AutoPlay candidates, same-key replay/retry, command/unavailable/confirmation failure and concurrent revision boundary.
- [x] Run focused tests, affected regression, complete `server/tests`, compileall, Ruff and diff checks.
- [x] Request independent scope/contract review, resolve Important findings with tests, record acceptance evidence, commit and push feature branch; verify remote SHA.

## Execution ledger

Baseline: `fe043af`, clean `feature/task-5-library-api`. Python 3.14.4 / pytest 9.1.1 / Ruff 0.16.9 verified; requirements inspected.

Pre-flight: Task 2 depends on Task 1 owning/joining the transaction; existing nested `run_transaction` reuses its outer connection and outer rollback callback list. No conflict.

Ruling: skip causes are service logs, not History rows or a new public response field — spec requires recording reasons but History represents actual playback and frozen schemas must remain stable.

Reproduction command: `.venv/bin/python -m pytest -q server/tests/api/test_pre_batch6_corrective.py -k 'playback_terminal_failure or next_skips_unavailable'`: 5 failed, 32 deselected. No production code changed before this RED.


## Final corrective findings and evidence

- Independent review found C also on asyncio cancellation. Root reproduced two RED failures with actual task cancellation: own Next cancelled after History mutation; outer transaction cancelled after Stop. SQLite rolled back but active/session did not. Minimal permitted dependency fix: `run_transaction` handles `BaseException` during operation/commit failure, rolls back and invokes callbacks, then re-raises. No schema/connection/lock/idempotency changes. Exact tests GREEN; repository aggregate 44 passed.
- Ruling: preserve the known current URI if catalog availability changes during active playback; this supports Next's reproduced no-candidate fallback without starting an unavailable track. All pending availability remains strict. Skip invalid pending across the execution list, including after the selected valid successor, because queue synchronization otherwise aborts on later unavailable entries.
- Ruling: on no available AutoPlay candidate, retain the confirmed existing current state/active History and expose empty pending Queue. Do not fabricate a successor or an unconfirmed Stop. Stopped requests retain existing no-op semantics.
- The previous-path test setup already records a's transition and History reads newest first. Capture the baseline and assert newest-first b/a after retry. New candidate d is supplied through MockMPD's constructor, which initializes its durations. These fixture corrections do not modify production behavior or suppress failures.
- Scope extension: one existing service test previously expected a partially replaced Queue after failed collection play. Updated to assert the entire original Queue snapshot/revision, preserving its original state/History checks and enforcing the frozen transaction contract.
- Remote advanced from `fe043af` to `0ea3210` during work, with documentation reorganization only. Fetched, inspected and fast-forwarded; original remote work preserved. This plan is archived on completion to follow the new documentation map; current status belongs in the existing active handoff and Task 5 plan.

### Verification commands

All run from repository root with existing `.venv`. No dependencies/environment modified, Docker/live MPD used, or local databases deleted.

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q server/tests/api/test_pre_batch6_corrective.py -k 'playback_terminal_failure or next_skips_unavailable'` before production edits | 5 failed, confirming C/D |
| `.venv/bin/python -m pytest -q server/tests/api/test_pre_batch6_corrective.py::test_cancelled_playback_restores_history_and_database` before/after database fix | 2 failed → 2 passed |
| `.venv/bin/python -m pytest -q server/tests/api/test_pre_batch6_corrective.py` | 59 passed |
| `.venv/bin/python -m pytest -q server/tests/repositories` | 44 passed |
| `.venv/bin/python -m pytest -q server/tests/services/test_playback_service.py server/tests/services/test_history_service.py` | 34 passed before cancellation dependency fix; final affected aggregate covers both |
| `.venv/bin/python -m pytest -q server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_playback_service.py server/tests/services/test_queue_manager.py server/tests/services/test_autoplay.py server/tests/services/test_history_service.py server/tests/api/test_mutations_playback.py server/tests/api/test_playlist_reads.py server/tests/api/test_idempotency.py server/tests/api/test_library_api.py server/tests/services/test_collection_service.py server/tests/services/test_playlist_service.py server/tests/repositories/test_playlist_repository_task5.py server/tests/integration server/tests/player/test_mock_mpd.py server/tests/player/test_mock_mpd_injection.py` | 225 passed |
| `.venv/bin/python -m pytest -q server/tests` | Final fresh run: 413 passed |
| `.venv/bin/python -m compileall -q server` | exit 0 |
| `.venv/bin/python -m ruff check server` | All checks passed |
| `git diff --check` | exit 0 |

Only the existing TestClient/httpx deprecation warning was reported. Original Task 5 implementation-plan diff remains empty. No environment failure occurred.

### Independent review and remaining Gate

The independent read-only reviewer verified the cancellation fix with its own temporary SQLite/real Service/MockMPD reproductions: direct Next and outer Stop restore Queue/state/persisted History/active/session. Reviewer ran 129 affected/repository tests and 59 Collection/Playlist/Library/idempotency tests, all passing. No remaining Critical/Important defect in C/D itself.

Gate matrix: API → Service → Repository/PlayerPort, Collection availability/order, persisted Playlist membership, execution Queue excluding Played, Next unavailable resolution, transactional History/retry/cancellation, idempotency/errors, Artwork read-only and future isolation preserved in inspected paths.

Separate Important pre-existing code/contract guard gap E: `PlaybackService.stop()` accepts non-STOPPED status and finalizes History anyway. Reviewer reproduced with temporary database/real Services/MockMPD after starting a, substituting an async no-op player.stop. POST `/api/playback/stop` with a new key returns 200/PLAYING, actual player stays PLAYING, persisted History contains `(a, STOP)`, active/session become None. No production change made for this independent issue. The next corrective should first add a RED real-Service/API confirmation test, require confirmed STOPPED before state/History commit, and cover rollback/same-key retry. C/D publication is ready; overall Batch 6 eligibility remains blocked by E.

Manual live MPD/NAS/DAC/physical acceptance was neither required nor run. SQLite rollback restores server authority and memory; it does not undo already sent player commands. Batch 6 and original Task 5 Step 9–10 remain unexecuted.

Root independently repeated E with `PYTHONPATH=. .venv/bin/python /tmp/mpd-cd-stop-audit.py`: `HTTP 200 state PLAYING actual playing history [('a', 'STOP')] active None session None`. Only the temporary fixture player.stop was replaced; no failing out-of-scope test or production workaround was committed.
