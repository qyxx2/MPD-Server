# Task 5 Current Pre-Batch-6 Corrective Handoff

Date: 2026-10-01
Branch: `feature/task-5-library-api`
Verified starting HEAD: `2ec59cdd02380055475a4ab6bd8a875d6a00cce7`

This file is the sole active corrective Gate record. Archived A/B evidence:
`docs/superpowers/archive/task-5/2026-10-01-task-5-contract-architecture-corrective-acceptance-full-history.md`.
C/D evidence:
`docs/superpowers/archive/task-5/2026-10-01-task-5-pre-batch6-cd-corrective-plan.md`.

## Current ruling

- Batch 1–5: COMPLETE.
- A/B/C/D/E: CLOSED.
- Relationship gate: REQUIRED; I1–I5 invariant foundation: COMPLETE.
- Independent audit insertion-confirmation finding: CLOSED (I1/I2 scope).
- No known remaining blocking finding in this corrective/foundation scope.
- Batch 6: NOT EXECUTED. Its entry prerequisites have evidence; its acceptance has not been performed.
- Original Task 5 Step 9–10 remain unchecked. No Task 5 final acceptance, PR or main merge.

## E — confirmed Stop

Two RED cases used temporary SQLite, actual Services/API and MockMPD, replacing Stop with a no-op and reporting PLAYING/PAUSED. Both returned HTTP 200, committed changed PlaybackState and successful idempotency terminal results, persisted a / STOP and cleared History active/session. Queue snapshot stayed unchanged; the persisted and runtime History relationship was broken.

`PlaybackService.stop()` now requires `PlayerState.STOPPED` after Stop/status and before state save or History finalization. Nonconfirmation raises existing `PlaybackReconciliationError`, mapped to 502 `PLAYBACK_RECONCILIATION_FAILED`; the existing owning transaction restores server state and History memory and discards terminal success. No second playback orchestrator was introduced.

Command failure, unavailable player, status failure, terminal INSERT failure, outer failure/cancellation, same-key retry and replay are mechanical regressions. SQLite rollback cannot undo external PlayerPort effects; tests recover/reconcile those separately before asserting final successful relationships.

## I1–I5 mechanical Gate

Shared fixture/helper is extracted from existing corrective tests into `server/tests/support/playback.py`; existing assertions/tests were preserved. `server/tests/invariants/assertions.py` relates independent SQLite Queue/PlaybackState, actual PlayerPort execution occurrences and in-memory History, and captures persisted/session snapshots.

| Invariant | Executable protection under `server/tests/invariants/` |
|---|---|
| I1 | `test_playback_relationships.py::test_duplicate_execution_occurrences_survive_mutation` and `test_pending_duplicate_mutation_preserves_retained_occurrence_ids`: ordered execution bijection, separate occurrence IDs, Played exclusion, reorder/delete/clear, no extra occurrences and retained engine IDs across pending-only duplicate mutation. |
| I2 | Shared execution/current assertion checks PLAYING/PAUSED/STOPPED against actual PlayerPort state/current position/MPD ID. `test_wrong_duplicate_current_is_reconciliation_failure` checks wrong duplicate MPD ID with both position 0 and 1. `test_insertion_rejects_actual_playback_divergence_and_can_retry` covers add/play-next confirmation. |
| I3 | `test_transition_history_matches_confirmed_current`: A→B, A→unavailable skip→C, A→STOP; exact once-only persisted events, active/current relationship and replay. `test_stop_confirmation.py` and reconciliation rejection protect against phantom/lost History. |
| I4 | `test_transaction_relationships.py::test_transaction_restores_persisted_and_session_state_and_retry`: next/skip/stop × real SQLite terminal-trigger failure, outer failure after terminal INSERT, task cancellation; Queue snapshot, PlaybackState, persisted History, active/session and terminal record rollback, then same-key retry/replay. |
| I5 | `test_playlist_relationships.py::test_persisted_membership_matches_every_representation_and_collection_split`: Repository persisted order agrees with list/detail/mutation/songs through create/add/reorder/rename, including AVAILABLE/MISSING/UNREADABLE; Collection splits playable/unavailable without changing Playlist membership. |

`test_architecture_relationships.py` additionally checks current API/Service import direction against repositories/SQLite/concrete MPDAdapter. These are static boundary checks, not a substitute for runtime relationship tests.

## Independent audit and scoped corrective ruling

Fresh read-only review found a separate pre-existing I2 code/guard gap: `play_next` and `add_to_queue` synchronized execution Queue without confirming retained playback state. Real MockMPD queue_add followed by actual pause produced HTTP 200 with server PLAYING/player PAUSED.

Ruling: this falls within the explicitly authorized I1–I5 correction scope. Two new invariant RED cases reproduced it; both paths now reuse `_confirm_preserved_state()` after queue synchronization. GREEN proves typed rejection, outer API transaction rollback, no terminal success, recovered-player retry/replay and final consistency. Production change is limited to these two confirmation calls and the E STOPPED guard.

Changed-files review, API → Service → Repository/PlayerPort review and Task 4/5 relationship re-audit found no other scoped blocker. Existing AutoPlay concurrency tests prove SQLite/Queue revision authority; exhaustive PlayerPort refill-race coverage remains outside this first foundation's evidence. Occurrence bindings use the documented execution-position relation; no new persisted stable QueueItem→MPD-ID mapping contract is assumed across playback switches. Pending-only retained identities are checked explicitly.

## Fresh verification

All commands ran from repository root using the unchanged existing `.venv`:

- `.venv/bin/python -m pytest -q server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_transaction_relationships.py -k stop`: 8 passed, 6 deselected.
- `.venv/bin/python -m pytest -q server/tests/invariants`: 29 passed (27 runtime relationship cases + 2 architecture cases).
- Existing E/C/D/A/B corrective files: 110 passed.
- Corrective files plus directly affected playback/history/queue/autoplay, idempotency, playback/mutation, playlist/library/contract API and all repository tests: 264 passed.
- `.venv/bin/python -m pytest -q server/tests`: 442 passed.
- `.venv/bin/python -m compileall -q server`: passed.
- `.venv/bin/python -m ruff check server`: passed.
- `git diff --check`: passed.

Pytest reported the existing Starlette TestClient/httpx deprecation warning; no dependencies/environment were changed. All tests are deterministic local validation. Live MPD/NAS/DAC/manual physical acceptance remains outside scope.

Only PlaybackService, shared test fixture extraction, invariant tests and the two current status documents changed. No formal spec/main Implementation Plan edits or future Task implementation. Commit/push and remote branch/SHA/message/changed-file verification are reported with actual Git results at completion; this corrective commit does not complete Task 5 Step 10.
