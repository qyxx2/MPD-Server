# Task 4 PlaybackService Corrective Acceptance Record

Date: 2026-09-30
Branch: `feature/task-4-playback-service-corrective`
Expected base: `main` at `29c7d6158c235f1070a4dc2c61cfe44261fe2458`
Corrective plan commit: `79162d11f26e106fab103a78e78d27428fc7e85f5`
Status: **COMPLETE**

## 1. Audit baseline

The remote repository was audited from the corrective branch itself before production implementation.

- Branch: `feature/task-4-playback-service-corrective`
- Base branch HEAD: `29c7d6158c235f1070a4dc2c61cfe44261fe2458`
- Merge base: `29c7d6158c235f1070a4dc2c61cfe44261fe2458`
- Initial corrective branch HEAD: `79162d11f26e106fab103a78e78d27428fc7e85f5`
- Initial ancestry: corrective plan commit was directly based on the actual current main.
- Corrective plan exists and was read.
- Specs, original v0.1 implementation plan, Task 4 Batch plan, MPD 0.23.5 capability record, README, and historical Task 4 Batch 6 acceptance record were read.

### Contract gaps confirmed

Correction A:
- `PlayerPort.seek()` exists.
- `PlaybackService.seek()` was absent.
- Existing `MPDAdapter`, `VerifiedPlayerPort`, and `MockMPD` seek transport behavior already satisfied the transport contract.

Correction B:
- `PlaybackContext` already exists with `context_id`, `source_type`, `source_id`, `ordered_song_ids`, and `random_seed`.
- `PlaybackService` had no public Task-4-owned collection playback handoff accepting an already ordered PlaybackContext.
- `QueueRepository` / `QueueManager` had no atomic collection queue replacement operation.
- Existing revision/CAS and transaction boundaries were reusable without redesign.

### Dependency gate

- Task 4 production code does not import Task 5 Collection or CollectionService.
- No Task 5 CollectionService implementation is required for the corrective change.
- The intended bridge remains Task 5 CollectionService → PlaybackContext → PlaybackService.
- No API, WebSocket, config, Output Manager, or future Task implementation was added.

## 2. Correction A — seek

### RED

Added focused tests before the production seek implementation:

- PLAYING seek confirmation.
- PAUSED seek confirmation.
- PlayerCommandError leaves PlaybackState unchanged.
- PlayerUnavailable leaves PlaybackState unchanged.
- STOPPED / no-current-state follows existing no-op behavior.

RED execution command:

```text
python -m pytest server/tests/services/test_playback_service.py -k "seek"
```

Execution result: **NOT EXECUTED** in the original blocked container.

Reason: the available container could not obtain a local repository/test runtime because outbound GitHub DNS resolution failed. No RED failure output is claimed as executed evidence.

### Implementation

Implemented only the PlaybackService service-layer seek orchestration:

```text
PlaybackService.seek()
  → PlayerPort.seek()
  → PlayerPort.status()
  → confirmed PlaybackState
```

The implementation preserves the existing song/context/autoplay fields and derives the state/position from confirmed PlayerPort status.

### GREEN

Focused GREEN command:

```text
python -m pytest server/tests/services/test_playback_service.py -k "seek"
```

Local ARM64 Python venv result: **5 passed**.

### Regression

The affected service regression was executed locally in the ARM64 Python venv.

- PlaybackService: **26 passed**.
- Queue + AutoPlay + History: **37 passed**.

Final status for Correction A: **COMPLETE**.

## 3. Correction B — collection playback

### RED

Added focused Task-4 tests before the production collection handoff implementation:

- Ordered `(a,b,c)` produces current `a` and Up Next `b,c`.
- All collection QueueItems share one PlaybackContext ID.
- Existing pending Queue entries are replaced rather than retained.
- Non-natural order `(c,a,b)` is preserved.
- Existing `random_seed` is not re-applied by PlaybackService.
- MPD command failure does not commit new PlaybackState or History success.
- PlayerUnavailable does not falsely commit new PlaybackState or History success.
- Existing availability contract is used before queue mutation.
- Empty collection is a no-op and does not choose random content.
- History is handled through HistoryService.
- AutoPlay refill uses the same PlaybackContext.
- Queue-level replacement has an atomic transaction and revision increment.
- Queue-level replacement rolls back completely when an FK constraint fails.

Focused RED commands:

```text
python -m pytest server/tests/services/test_queue_manager.py -k "replace_with_context"
python -m pytest server/tests/services/test_playback_service.py -k "play_context"
```

Execution result at the original RED stage: **NOT EXECUTED in the blocked container**. No RED failure output is claimed as executed evidence.

### Queue contract hardening

Added the minimum missing queue contract:

```text
QueueManager.replace_with_context(PlaybackContext)
        ↓
QueueRepository.replace_with_context(PlaybackContext)
        ↓
one run_transaction() + existing revision/CAS
```

The repository operation:

- preserves the Played region;
- removes existing Up Next entries;
- creates the supplied collection at positions 0..N-1;
- assigns the same `playback_context_id` to every new collection QueueItem;
- leaves ordering exactly as supplied;
- uses MANUAL source for the supplied collection items;
- rolls back the whole transaction, including revision, on failure.

No repeated `add_to_queue()` calls are used for collection replacement.

### Implementation

Added `PlaybackService.play_context(PlaybackContext)`.

Execution boundary:

```text
PlaybackContext
  → existing availability contract
  → QueueManager.replace_with_context()
  → existing PlayerPort play/confirmation path
  → confirmed PlaybackState
  → HistoryService.start_track()
  → AutoPlay.refill(context)
  → existing MPD queue synchronization
```

PlaybackService does not query or calculate collection membership, sorting, or randomization.

### GREEN

Focused GREEN commands:

```text
python -m pytest server/tests/services/test_queue_manager.py -k "replace_with_context"
python -m pytest server/tests/services/test_playback_service.py -k "play_context"
```

Local ARM64 Python venv results:

- `replace_with_context`: **2 passed** after commit `9d8442e5565489566e1c7afd65e304044460e104`.
- `play_context`: **10 passed** after commit `d670229c4c6bac8bad787f5a62c84b92a737df97`.

Final status for Correction B: **COMPLETE**.

## 4. Focused and integration regression

Executed locally in the ARM64 Python virtual environment:

```text
python -m pytest server/tests/services/test_playback_service.py
python -m pytest server/tests/services/test_queue_manager.py server/tests/services/test_autoplay.py server/tests/services/test_history_service.py
python -m pytest server/tests/integration/test_task2_task3_task4_e2e.py server/tests/integration/test_task4_with_mpd_adapter.py
```

Results:

- PlaybackService: **26 passed**.
- Queue + AutoPlay + History: **37 passed**.
- Both integration groups together: **9 passed**.
- Combined corrective-core regression: **72 passed**.

No skipped, failed, or error tests were reported in the supplied acceptance results.

## 5. Full regression

Required:

```text
python -m pytest server/tests -q
```

Local ARM64 Python venv result: **199 passed**.

## 6. Compile / lint / diff

Required:

```text
python -m compileall -q server
python -m ruff check server
git diff --check
```

Local ARM64 Python venv results:

- `compileall`: **PASS**.
- Ruff: **PASS**.
- `git diff --check`: **PASS**.

Static source inspection performed remotely found:

- zero lines longer than 88 characters in the five changed Python source/test files;
- no direct SQLite access in PlaybackService;
- no concrete MPDAdapter / MPD protocol dependency in PlaybackService;
- no REST / WebSocket dependency;
- no Task 5 Collection / CollectionService dependency.

## 7. Changed files

Allowed scope after audit:

1. `server/app/services/playback_service.py`
   - Add `seek()`.
   - Add Task-4-owned `play_context()`.

2. `server/app/services/queue_manager.py`
   - Add minimum queue-manager handoff for atomic collection replacement.

3. `server/app/repositories/queue_repository.py`
   - Add minimum transactional collection replacement operation reusing revision/CAS.

4. `server/tests/services/test_playback_service.py`
   - Add RED tests for seek and collection playback.

5. `server/tests/services/test_queue_manager.py`
   - Add RED tests for collection queue replacement and atomic rollback.

6. `docs/superpowers/plans/2026-09-30-task-4-playback-service-corrective-acceptance.md`
   - Required corrective acceptance record.

No other production/test file is in the corrective diff.

## 8. Architecture review

1. PlaybackService remains the playback orchestration layer: **YES**.
2. seek goes through PlayerPort: **YES**.
3. collection playback goes through PlaybackService: **YES**.
4. Task 4 has no Task 5 implementation dependency: **YES**.
5. Collection membership and order remain external to PlaybackService and are supplied through PlaybackContext: **YES**.
6. PlaybackService does not re-randomize the supplied context: **YES**.
7. Queue replacement is one repository transaction using existing revision/CAS: **YES**.
8. History remains owned by HistoryService: **YES**.
9. AutoPlay remains owned by AutoPlay: **YES**.
10. MPD access remains behind PlayerPort: **YES**.
11. SQLite access remains behind Repository abstractions: **YES**.
12. No Task 6+ implementation was introduced: **YES**.

## 9. Environment / physical validation

- Local execution environment: **ARM64 / aarch64 Python virtual environment**.
- Local Python test/lint/compile execution: **VALIDATED**.
- Physical NAS / real MPD / USB DAC validation: **NONE** (not required for this corrective contract; MPD transport contract was unchanged).
- The corrective work did not change the MPD transport contract, so no new MPD capability probe was required.

## 10. Git

The corrective branch is remote and remains separate from main.

- Branch: `feature/task-4-playback-service-corrective`
- Base: `main`
- Base SHA: `29c7d6158c235f1070a4dc2c61cfe44261fe2458`
- Corrective plan commit: `79162d11f26e106fab103a78e78d27428fc7e85f5`
- Latest production implementation commit recorded for the corrective: `f2cf8868976a74b4a98675450d0b9b39e3b7e281` (`fix: import playback context in queue repository`).
- Subsequent acceptance-test commits verified on the same branch: `9d8442e5565489566e1c7afd65e304044460e104`, `e4a6c968e17284dbfb341eb977617c745285a4c0`, `d670229c4c6bac8bad787f5a62c84b92a737df97`.
- Branch HEAD immediately before this documentation update: `d670229c4c6bac8bad787f5a62c84b92a737df97`.
- This document update is the acceptance-record finalization commit on the same branch.

No merge to main was performed.

## 11. Documentation

- Corrective plan preserved: **YES**.
- Acceptance record finalized: **YES**.
- Original Task 4 Batch 6 acceptance preserved: **YES**.
- Original file was not deleted or rewritten.
- README was intentionally not modified because this corrective is not yet merged and the user prohibited unrelated changes.
- Plan consistency: **YES**. The corrective implementation matches the two identified gaps and the allowed file scope.

## 12. Task 5 resume gate

- Corrective merged to main: **NO**.
- `feature/task-5-library-api` updated: **NO**.
- Corrective ancestry verified on Task 5 branch: **NO — not applicable until after merge/update**.
- Task 5 prerequisite re-audited after merge: **NO**.
- Task 5 Batch 4 allowed to resume: **NO**.

Task 4 corrective acceptance itself is now complete; the remaining Task 5 gate is intentionally a separate PR/merge and prerequisite re-audit step.

Required sequence after this corrective branch is independently validated:

```text
feature/task-4-playback-service-corrective
        ↓
PR / review
        ↓
main
        ↓
update feature/task-5-library-api
        ↓
verify corrective ancestry
        ↓
re-run Task 5 prerequisite / Contract Audit
        ↓
only then resume Task 5 Batch 4
```

## 13. Final determination

**COMPLETE**

### Final local acceptance evidence

- ARM64 venv focused seek: **5 passed**.
- Queue replacement: **2 passed**.
- PlaybackContext / collection playback: **10 passed**.
- PlaybackService regression: **26 passed**.
- Queue + AutoPlay + History regression: **37 passed**.
- Task2→Task3→Task4 E2E + MPD Adapter integration: **9 passed**.
- Corrective core regression: **72 passed**.
- Full backend Python suite: **199 passed**.
- `compileall`: **PASS**.
- Ruff: **PASS**.
- `git diff --check`: **PASS**.

The corrective implementation is accepted on the basis of the specified contract tests, regression suite, static checks, and ARM64 local verification. Physical NAS / real MPD / USB DAC validation remains outside this corrective acceptance because the MPD transport contract was unchanged. No merge to `main` is performed by this acceptance-record update.
