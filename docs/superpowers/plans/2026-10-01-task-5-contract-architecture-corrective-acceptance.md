# Task 5 Batch 6 Final Acceptance

Date: 2026-10-02
Branch: `feature/task-5-library-api`
Fresh starting local and remote HEAD: `94142144c00ff6f078e92313be8f9f958d32480c`

This existing file remains the sole current corrective/acceptance record. It records the latest reproducible Gate evidence, not a parallel contract source. Authority follows `docs/superpowers/README.md`. Historical A/B evidence remains in `archive/task-5/2026-10-01-task-5-contract-architecture-corrective-acceptance-full-history.md`; C/D evidence remains in `archive/task-5/2026-10-01-task-5-pre-batch6-cd-corrective-plan.md`.

## Repository and dependency audit

- Starting working tree was clean. Local branch, HEAD, history and remote branch ref were freshly checked; remote and local starting HEAD matched.
- Task 3 `f94ee65`, Task 4 `cb02824`, Batch 1 `8f35161`, Batch 2 `f962cb7`, Batch 3 `1a823a5`, Batch 4 RED/API lineage `6e0a3a3`, Batch 5 `4a4e514`, and corrective commits `a3fc1b1`, `fe043af`, `0e2c034`, `18b4026` are actual ancestors of starting HEAD. Current code/tests were inspected rather than accepting plan checkboxes. The original Task 4 checklist remains outside this bookkeeping scope.
- Task 3 Available Songs/DomainEvent/scanner and Task 4 Queue/PlaybackContext/History/AutoPlay/PlaybackService implementations exist. Directly dependent regression ran fresh.
- A/B/C/D/E and insertion confirmation safeguards exist in code and executable tests. I1–I5 foundation is under `server/tests/invariants/`, backed by actual SQLite/Services/API/MockMPD and shared persisted/session assertions.
- API delegates to Services; API has no SQLite/Repository/concrete MPDAdapter access. PlaybackService uses PlayerPort; composition-root concrete wiring stays in `main.py`. Playlist resource membership and Collection playable split remain separate. Artwork reads persisted references and source bytes without writing media.
- Branch production changes against the Task 4 baseline and current diff contain no Task 6–12 implementation. Existing skeleton/static-serving/env wiring is not new future-Task work.

## Contract Matrix Impact Analysis

Relationship Gate: **REQUIRED** (I1–I5 and architecture relationships).
Contract Matrix Gate: **REQUIRED** (all 11 existing rows).
New Contract Rows: **none**. Modified Contract Rows: **none**.

All 11 IDs are affected/relied-upon regression obligations. The correction below restores existing PB-REORDER-001/PB-DELETE-PENDING-001 semantics; no Spec or Matrix wording was changed to fit implementation. Before the Contract Gate, each row was checked for Preconditions, Authorities, Expected State Delta, Must Remain Unchanged, External Confirmation, History/Event Semantics, Transaction Boundary, Failure/Rollback, Retry/Idempotency, Observable Result and Executable Invariant Proof.

Shared mutation boundary: retriable REST business writes and successful terminal idempotency records join one SQLite transaction. History-changing paths also register active/session rollback. Failures/cancellation restore persisted/runtime authorities and leave no terminal success; SQLite cannot undo external PlayerPort effects, so retry reconciles those separately. Same-key/scope/payload replay returns original status/body without re-running business work; conflicting scope/payload returns 409. Read-only resource/Collection resolution has no playback/History transition or terminal mutation record. These shared fields apply only where the row invokes that boundary.

The operation definitions remain exclusively in the active plan §3.7. This acceptance record does not duplicate that Contract Matrix. The row-by-row traceability review below records implementation/proof/result; preserved relations were checked alongside deltas, including current occurrence/state/context/History for pending operations, Queue for Stop, all persisted/runtime authorities on rollback, and Playlist membership on Collection conversion.

## Scoped blocker and RED → GREEN

Independent review reproduced a **code gap + invariant test gap**, PB-REORDER-001/PB-DELETE-PENDING-001. With two pending `b.flac` occurrences, successful reorder swapped their retained MPD IDs; deleting the first retained the targeted ID and deleted the other. `_sync_player_queue()` chose URI matches and could not distinguish those occurrences. Instantaneous final-position bijection alone missed the defect.

New `test_same_uri_pending_mutation_preserves_occurrence_identity[reorder/delete]` uses actual SQLite/API/Services/MockMPD, independent before/after bindings, exact target deletion, unchanged current/PlaybackState/context/History/session and no-op replay. Fresh RED: **2 failed** specifically on retained MPD ID assertions. Minimal PlaybackService correction passes the pre-mutation Queue snapshot to pending reorder/delete synchronization, binds operation-local execution positions to actual MPD IDs when the player still matches that Queue, and synchronizes retained occurrences by ID. Existing URI reconciliation remains for retry after external divergence. No persisted mapping or cross-playback-switch identity guarantee was introduced.

Fresh GREEN: **2 passed**; affected invariant file **14 passed**; corrective/playback/Queue/invariant regression **117 passed**. Independent re-review found no further blocker and additionally exercised three identical pending URIs across PLAYING/PAUSED/STOPPED, selected occurrences and replay. All final gates below ran after the production correction.

## Final Contract traceability review

Spec aliases: **P** = `specs/2026-09-24-playback-model-queue-semantics-design.md`; **L** = `specs/2026-09-24-library-playlist-tag-search-design-2-1.md`; **A** = `specs/2026-09-25-system-and-development-architecture-design.md`. Frozen clauses refer to the sole active Task 5 plan §3. Tests below are executable cross-authority relationship proofs; existing corrective API proofs collaborate through real repositories/services/player rather than mocking away the boundary.

Evidence **B1** = complete invariant command (31 passed); **B2** = explicit Contract-focused command (172 passed); **C1** = Task 5 aggregate (213 passed); **C2** = affected prior-Task regression (157 passed). Commands are reproduced below. Each row was reviewed individually against these fresh results, not inferred solely from the full-suite count.

| Contract ID | Spec / frozen contract | Implementation owner | Executable relationship proof (under server/tests/) | Fresh result |
|---|---|---|---|---|
| PB-STOP-001 | P §2.2, §6.1, §7, §8.7; frozen §3.5–3.6 | PlaybackService.stop / HistoryService / owning transaction | invariants/test_stop_confirmation.py; test_playback_relationships.py::test_transition_history_matches_confirmed_current[stop]; transaction relationships stop cases | GREEN B1/B2 |
| PB-INSERT-001 | P §3.3, §8.6–7; frozen §3.6 | PlaybackService.play_next/add_to_queue | invariants/test_playback_relationships.py::test_insertion_rejects_actual_playback_divergence_and_can_retry; services/test_playback_service.py insertion preservation | GREEN B1/B2/C2 |
| PB-REORDER-001 | P §5.2, §8.4–7; frozen §3.6 | PlaybackService.reorder/_sync_player_queue; QueueManager/Repository | invariants/test_playback_relationships.py::test_same_uri_pending_mutation_preserves_occurrence_identity[reorder]; retained duplicate mutation; api/test_pre_batch6_corrective.py revision/failure/final-confirmation tests | GREEN B1/B2 |
| PB-DELETE-PENDING-001 | P §5.2, §6.1, §8.7; frozen §3.6 | PlaybackService.delete/_sync_player_queue; QueueManager/AutoPlay | invariants/test_playback_relationships.py::test_same_uri_pending_mutation_preserves_occurrence_identity[delete]; api/test_pre_batch6_corrective.py::test_queue_mutations_sync_real_player_and_history and failure/retry cases | GREEN B1/B2 |
| PB-DELETE-CURRENT-001 | P §5.2, §6.1, §7, §8.3/7; frozen §3.6 | PlaybackService.delete / HistoryService / AutoPlay | api/test_pre_batch6_corrective.py::test_delete_current_without_pending_uses_autoplay_or_confirmed_stop; test_current_delete_skips_unavailable_successor; test_current_deletion_after_explicit_stop_does_not_restart; test_current_delete_terminal_record_failure_restores_history | GREEN B2 |
| PB-NEXT-UNAVAILABLE-001 | P §8.1/3/7; frozen §3.6 | PlaybackService.next/_next_available_pending / AutoPlay | invariants/test_playback_relationships.py::test_transition_history_matches_confirmed_current[skip]; transaction skip cases; api/test_pre_batch6_corrective.py next unavailable/absent/exhaustion/failure/cancel tests | GREEN B1/B2 |
| PB-HISTORY-001 | P §2.2, §3.3, §7; frozen §3.5–3.6 | PlaybackService / HistoryService / HistoryRepository | invariants/test_playback_relationships.py::test_transition_history_matches_confirmed_current; test_stop_confirmation.py; test_transaction_relationships.py | GREEN B1/B2 |
| TX-ROLLBACK-001 | A §8.1, §19.5; frozen §3.5 | database.run_transaction / HistoryService.preserve_active_on_rollback / PlaybackService / IdempotencyService | invariants/test_transaction_relationships.py::test_transaction_restores_persisted_and_session_state_and_retry (next/skip/stop × terminal/outer/cancellation) | GREEN B1/B2 |
| TX-IDEMP-001 | P §8.6; A §8.1, §19.5; frozen §3.5 | IdempotencyService / IdempotencyRepository / API middleware | invariants/test_transaction_relationships.py retry/replay; api/test_idempotency.py; api/test_mutations_playback.py scope/payload conflict and replay coverage; canonical payload hashing inspected in IdempotencyService._payload_hash | GREEN B1/B2/C1 |
| PL-REP-001 | L §2, §5.1, §7, §9; frozen §3.2/3.4 | PlaylistRepository / PlaylistService / playlists API | invariants/test_playlist_relationships.py::test_persisted_membership_matches_every_representation_and_collection_split | GREEN B1/B2 |
| PL-COLLECTION-001 | L §4.2–3, §9; P §8.3; frozen §3.1–2 | CollectionService / PlaylistService / LibraryService | same Playlist relationship invariant; services/test_collection_service.py; api/test_task5_corrective.py known-empty/all-unavailable tests | GREEN B1/B2/C1 |

## Fresh final Gate commands

All commands ran from repository root with the existing unchanged `.venv`. Verified Python **3.14.4**, pytest **9.1.1**, Ruff **0.16.9**; no dependency/environment changes. Direct commands are equivalent to `make test/lint` with `.venv/bin/python` and satisfy the local instructions.

| Gate | Actual command | Result |
|---|---|---|
| Corrective RED → GREEN | `.venv/bin/python -m pytest -q server/tests/invariants/test_playback_relationships.py::test_same_uri_pending_mutation_preserves_occurrence_identity` | 2 failed before fix → 2 passed after fix |
| Corrective file | `.venv/bin/python -m pytest -q server/tests/invariants/test_playback_relationships.py` | 14 passed, 0 failed |
| Corrective regression | `.venv/bin/python -m pytest -q server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_playback_service.py server/tests/services/test_queue_manager.py server/tests/invariants/test_playback_relationships.py` | 117 passed, 0 failed |
| B1 I1–I5 | `.venv/bin/python -m pytest -q server/tests/invariants` | 31 passed, 0 failed |
| B2 Contract-focused | `.venv/bin/python -m pytest -q server/tests/api/test_pre_batch6_corrective.py server/tests/api/test_task5_corrective.py server/tests/api/test_idempotency.py server/tests/services/test_collection_service.py server/tests/invariants` | 172 passed, 0 failed |
| C1 Task 5 API/service/repository | `.venv/bin/python -m pytest -q server/tests/api server/tests/services/test_library_service.py server/tests/services/test_playlist_service.py server/tests/services/test_collection_service.py server/tests/repositories/test_playlist_repository_task5.py` | 213 passed, 0 failed |
| C2 Task 2R/3/4 dependencies | `.venv/bin/python -m pytest -q server/tests/repositories/test_library_reconciliation.py server/tests/repositories/test_available_songs.py server/tests/repositories/test_task3_batch4.py server/tests/repositories/test_task2_steps_5_7.py server/tests/services/test_media_metadata.py server/tests/services/test_library_scanner.py server/tests/services/test_library_watch.py server/tests/services/test_library_scheduler.py server/tests/services/test_queue_manager.py server/tests/services/test_playback_service.py server/tests/services/test_history_service.py server/tests/services/test_autoplay.py server/tests/integration` | 157 passed, 0 failed |
| Full server | `.venv/bin/python -m pytest -q server/tests` | 444 passed, 0 failed |
| Architecture | `.venv/bin/python -m pytest -q server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories` | 3 passed, 0 failed |
| Compile | `.venv/bin/python -m compileall -q server` | exit 0 |
| Lint | `.venv/bin/python -m ruff check server` | All checks passed, exit 0 |
| Diff | `git diff --check`; actual diff/status/stat inspection | clean, scoped |

C2 maps to the Relationship-Test Matrix: Task 2R migration/reconciliation preserves availability and Playlist/Favorites/History references; Task 3 parser/scanner atomic persistence and post-commit event/MPD ordering feed Task 5 scan/artwork/library contracts; Task 4 Queue/state/player/History/AutoPlay relationships feed Task 5 REST mutations. Watch/scheduler and prior integration tests protect the same scanner/playback authorities. No unrelated legacy adapter/output test range was added to the focused dependency gate; those run only in the required full server suite.

Known non-blocking warning: existing Starlette TestClient/httpx deprecation, one warning in API/invariant/full runs. No environment limitation prevented a required local Gate. Tests use temporary SQLite and Mock/fake/local protocol infrastructure; no live MPD/NAS/DAC or Docker invocation. Physical acceptance and exhaustive AutoPlay refill-race coverage remain outside this Task 5 Gate.

## Completion and integration boundary

- Relationship/Contract Matrix/I1–I5/11-row traceability/focused/dependency/full/compile/lint/architecture/diff/future-isolation Gates: **GREEN**.
- Scoped duplicate corrective: **CLOSED**. No known remaining Task 5 blocker.
- Task 5 Step 9: **COMPLETE**. Task 5 Steps 1–8 are reconciled to the reachable Batch 1–5 implementations and fresh focused/full evidence.
- Step 10: Task 5 final acceptance commit uses the original Plan message `feat: expose library and playback api`. This bookkeeping becomes final with that commit; SHA, push and second remote verification are checked from Git and reported at execution completion rather than assuming an embedded self-referential SHA.
- Final changed-file scope: PlaybackService; one occurrence-identity invariant file; main Implementation Plan Task 5 checklist; active Task 5 status; this existing sole acceptance record; README high-level status. No new completion-summary/contract document, Spec change, unrelated formatting/refactor, dependency/runtime artifact or Task 6–12 code.
- Ready for **PR/main merge review** after final commit/remote verification. No PR creation or merge into main is part of this Batch. Real deployment/physical acceptance remains a separate later Gate.
