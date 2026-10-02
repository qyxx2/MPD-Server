# MPD-Server Task 4 PlaybackService Contract Corrective Follow-up Plan

> Corrective follow-up for a contract gap discovered during the Task 5 Contract Audit. This plan does not replace the Specs, the original Implementation Plan, or the Task 4 Batch Execution Plan.

## 1. Problem

Task 5 REST playback APIs require the architecture:

```text
REST → Service → PlaybackService → Queue/History/AutoPlay → PlayerPort
```

The actual Task 4 implementation currently has `PlaybackService.start_track()`, `play_now()`, `play_next()`, `add_to_queue()`, `next()`, `previous()`, `pause()`, `stop()` and `reconcile_external_status()`, but no public `seek()` service method.

`PlayerPort.seek(seconds)` already exists, so this is a missing service-layer contract, not a new MPD transport requirement.

The Task 4 Batch 5 plan also explicitly requires collection-play orchestration, while the current PlaybackService has no Task-4-owned handoff accepting an already ordered `PlaybackContext`. Task 5's CollectionService must not become the playback orchestrator.

## 2. Dependency correction

Do not patch these gaps inside Task 5 Batch 4.

Create an independent corrective branch from the actual current `main` baseline:

```text
main
  ↓
feature/task-4-playback-service-corrective
```

The corrective branch must not import Task 5's `Collection` or `CollectionService`.

The bridge between Task 5 and Task 4 is the existing Task-4-owned `PlaybackContext`:

```text
Task 5 CollectionService
    ↓ convert ordered Collection to PlaybackContext
Task 4 PlaybackService
```

## 3. Scope

### Correction A — `PlaybackService.seek`

Add only the service-level orchestration around the existing PlayerPort capability:

```text
PlaybackService.seek(seconds)
    ↓
PlayerPort.seek(seconds)
    ↓
PlayerPort.status()
    ↓
confirmed PlaybackState
```

On command failure or PlayerUnavailable, service state must not be falsely advanced.

The existing `song_id`, `playback_context_id`, state and autoplay semantics must be preserved.

### Correction B — collection-play handoff

Add a Task-4-owned PlaybackService entry point whose input is `PlaybackContext` (or the minimum equivalent already frozen by the repository), containing:

- `context_id`
- `source_type`
- `source_id`
- ordered `song_ids`
- `random_seed`

PlaybackService must execute the supplied order exactly. It must not query album/artist/search semantics itself and must not randomize again.

Required behavior:

```text
PlaybackContext
  ↓
validate available songs through existing Library contract
  ↓
replace authoritative Server Queue as one queue-level operation
  ↓
play first song through PlayerPort
  ↓
confirm MPD status
  ↓
persist PlaybackState + PlaybackContext
  ↓
HistoryService.start_track()
  ↓
AutoPlay using the same PlaybackContext
  ↓
MPD queue synchronization
```

If the current QueueRepository/QueueManager lacks an atomic collection replacement contract, add only the minimum Task-4-scoped repository/service method required. Reuse the existing transaction and revision/CAS boundaries. Do not simulate collection replacement by repeatedly calling `add_to_queue()`.

## 4. TDD sequence

### Audit — no production changes

Before implementation, read and verify from the actual repository:

- `docs/superpowers/specs/`
- `docs/superpowers/plans/2026-09-25-mpd-server-v0-1-implementation-plan.md`
- `docs/superpowers/plans/2026-09-28-mpd-server-task-4-batch-plan.md`
- `docs/mpd-0.23.5-capabilities.md`
- Task 4 acceptance record
- `PlaybackService`, `QueueManager`, `QueueRepository`, `HistoryService`, `AutoPlay`, `PlayerPort`, `PlaybackContext`
- existing Task 4 tests

Confirm branch, HEAD, workspace, actual dependency ancestry and minimal changed-file set. If the repository differs from this plan, stop and reconcile against Specs + original Plan rather than guessing.

### Step 1 — seek

RED tests first:

- PLAYING seek success updates confirmed position;
- PAUSED seek success;
- PlayerCommandError leaves service state unchanged;
- PlayerUnavailable leaves service state unchanged;
- STOPPED/no-current-state follows existing service/error semantics rather than inventing a new rule.

Then implement the minimum service change and run focused playback tests plus affected regression.

### Step 2 — collection playback

RED tests first:

- `(a,b,c)` becomes current `a`, Up Next `b,c`;
- every new QueueItem carries the same playback_context_id;
- PlaybackState points to `a` and the supplied context;
- supplied non-natural order `(c,a,b)` is preserved;
- fixed `ordered_song_ids` / `random_seed` is never randomized again;
- MPD failure/unavailable does not falsely commit the new playback state;
- unavailable members use the existing availability contract;
- empty collection does not start a random song and does not silently replace the queue with random data;
- History and AutoPlay use the existing services and the same PlaybackContext.

If Queue-level atomic replacement is missing, first add its smallest RED test and minimum implementation. Do not refactor Queue architecture.

### Step 3 — acceptance

Run the focused Task 4 service/repository tests actually present in the repository, the existing Task 2→Task 3→Task 4 backend integration tests, and then the appropriate full Python regression. Also run compileall, Ruff and `git diff --check` when the environment permits.

## 5. Architecture constraints

Must remain:

```text
PlaybackService
  → QueueManager / QueueRepository
  → HistoryService
  → AutoPlay
  → PlayerPort
```

Must never become:

```text
PlaybackService → SQLite directly
PlaybackService → concrete MPD adapter
Task 4 → Task 5 CollectionService
Task 4 → REST API
Task 4 → WebSocket
Task 4 → config.py / deployment
```

Real music files remain read-only.

## 6. Allowed files

Expected minimum:

- `server/app/services/playback_service.py`
- `server/tests/services/test_playback_service.py`

Only if the audit proves collection queue replacement is missing may the corrective work additionally modify:

- `server/app/services/queue_manager.py`
- `server/app/repositories/queue_repository.py`
- corresponding Task-4 tests

Any other file requires explicit dependency justification before modification.

## 7. Explicitly forbidden

Do not implement Task 5 LibraryService, PlaylistService, CollectionService, REST API, API schemas or idempotency. Do not implement Task 6 WebSocket, Task 7 Output Manager, Task 8+ Web/PWA, config, backup, logging or deployment.

Do not weaken or delete tests to manufacture GREEN. Do not bypass Repository/Service/PlayerPort boundaries. Do not introduce a second collection ordering or randomization implementation.

## 8. Git

Recommended commit:

```text
fix: complete playback service contract
```

Do not merge `main` automatically from the corrective implementation window. After commit, verify the remote branch/ref and commit SHA independently.

## 9. Corrective acceptance record

After implementation, create:

`docs/superpowers/plans/2026-09-30-task-4-playback-service-corrective-acceptance.md`

It must record:

- actual audit baseline;
- the two discovered gaps;
- RED/GREEN evidence;
- focused and regression test results;
- compile/lint/diff results;
- changed files and scope justification;
- commit SHA and remote ref;
- final corrective determination.

Do not delete or rewrite the historical Task 4 acceptance record.

## 10. Return to Task 5

Only after the corrective branch is independently accepted:

```text
corrective branch
  ↓
PR / review
  ↓
main
  ↓
update Task 5 feature branch
  ↓
re-audit Task 5 prerequisites
  ↓
resume Task 5 Batch 4
```

The existence of the corrective commit alone does not prove that Task 5 is ready. The Task 5 window must verify that the corrective commit is actually in its ancestry and that its CollectionService-to-PlaybackService bridge matches the final contract.

## 11. Stop conditions

Stop immediately if:

- collection replacement cannot be expressed safely using Task 4 contracts;
- implementation would require importing Task 5 code into Task 4;
- an unverified MPD capability is required;
- an environment failure prevents determining production semantics;
- the actual repository state contradicts this plan and the contradiction has not been reconciled against Specs and the original Implementation Plan.

Final status may only be `COMPLETE`, `PARTIALLY COMPLETE — ENVIRONMENT VALIDATION PENDING`, `PARTIALLY COMPLETE — BLOCKED`, or `BLOCKED BY DEPENDENCY`.
