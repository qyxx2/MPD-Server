# Task 5 Pre-Batch-6 A/B corrective plan

Branch: `feature/task-5-library-api`. Baseline: `86aedd6`.
Authority: all four specs, original Implementation Plan Task 5 Steps 1–8,
Task 5 Batch Plan §4.7 / Batches 3–5, existing corrective acceptance.
No Batch 6 Steps 9/10, Task 5 completion checkbox, merge or future Task.

## Verified review feedback / root cause

Real API + SQLite + Services + MockMPD regression reproduces four queue
synchronization failures and two Playlist resource failures before production edits.
Current deletion fixture selects the MANUAL current row (AutoPlay can repeat a Song
with a different queue_item_id); its exact case was rerun after correcting identity.
API routes bypass PlaybackService; QueueManager.delete optimistically saves PLAYING
without PlayerPort confirmation. Playlist reads use playable Collection membership.

## Minimal design and execution

1. A RED: cover reorder/pending deletion/current deletion/clear against actual
   Server Queue and MockMPD, confirmed state, History and persisted retry replay.
2. Add PlaybackService queue mutation methods. Keep QueueManager as Queue business
   authority with opt-out of optimistic state persistence, as existing play_now does.
   Serialize the new orchestration in the existing SQLite transaction (including
   idempotency's nested transaction), reserve/check revision before player commands.
   Synchronize the execution queue, excluding Played, via existing PlayerPort methods.
   Current deletion switches to the first playable successor, confirms actual playback,
   saves state, closes History with existing SWITCH_AWAY and starts the successor event.
   Skip unavailable pending members; attempt existing AutoPlay on exhaustion. If none
   exists, confirm STOPPED and close History; permit the Repository to move current to
   Played only via an explicit opt-in, preserving its default no-successor rejection.
   Clear active pending queue invokes AutoPlay under spec §6.1; stopped state does not
   restart. All new mutation DB effects rollback on failure; external MPD side effects
   cannot be rolled back by SQLite and failed requests remain retryable.
3. A GREEN and failure RED/GREEN: MPD command/unavailable/unconfirmed status, revision
   conflict, no-successor/AutoPlay/STOPPED, unavailable successor, empty sync, replay.
4. B: PlaylistResponse always uses PlaylistService persisted ordered song_ids.
   `/playlists/{id}/songs` is an ordered resource read of all persisted Songs,
   including MISSING/UNREADABLE with existing availability_status. It is not a playable
   Collection. Keep Collection availability split unchanged. Real SQLite tests cover
   list/detail/create/update/add/reorder/song-resource consistency.
5. Focused and affected Task 4/5 regressions, full server/tests, compileall, Ruff,
   diff and changed-file review. Fresh independent review of correction and full
   Task 5 Step 1–8/Batch 3–5 contract audit. Stop Batch 6 on any independent blocker.
6. Update acceptance/handoff with evidence and A/B status. Only if no blocker remains,
   commit/push feature branch and re-read remote ref and commit.

## Scope / review focus

Only queue mutation service/API paths, minimum QueueManager/QueueRepository contract
extension, Playlist read routes, directly affected doubles, regression tests and these
corrective records. No availability change in Collection, schema/dependency/environment
change, music write, realtime/output/UI/config/deployment implementation.

Review failure classes: duplicate Song queue identities, actual current and execution
queue confirmation, paused/stopped controls, transaction/revision ordering, failed retry,
History transitions, AutoPlay exhaustion, unavailable playlist resources and unchanged
Collection split. A/B share no production interfaces.

## Execution ledger / scoped rulings

- A/B initial RED: 16 failed (six original cross-layer mismatches plus missing
  service/failure/revision/exhaustion contracts); first focused GREEN: 16 passed.
- Ruling: clear active pending uses existing AutoPlay only on exhaustion (spec §6.1),
  while stopped mutations never restart. Current deletion keeps existing
  SWITCH_AWAY transition; no candidates uses confirmed STOPPED/STOP, not fabricated
  content. This changes queue rows under the existing repository primitives only.
- Additional A RED→GREEN: four final-status mismatches; explicit Stop deletion;
  two terminal-record failures restoring History active/session; wrong duplicate
  current occurrence; Mock queue identity and transport-control fidelity.
- Ruling: typed PlaybackReconciliationError maps to 502 with stable
  PLAYBACK_RECONCILIATION_FAILED/details=null. It is an upstream confirmation
  failure; unexpected Service/Repository errors remain 500. No response fields changed.
- Minimum necessary A extension after real trigger RED: database transaction rollback
  callbacks and History active/session checkpoint, registered only by the new
  delete method. This protects its own outer idempotency failure without silently
  expanding implementation into other playback operations. SQLite cannot undo MPD
  commands; an unsuccessful command sequence is observable and retryable.
- Minimum necessary A test-support extension: MockMPD tracks the execution queue
  occurrence independently of its available-song library, reports actual queue
  ID/position, and models removal of current. Standalone control behavior retained;
  next/previous keep their selected URI and queue identity coherent.
- Test fixture rulings: current queue_item_id chosen by MANUAL row rather than a
  song_id-only map that picked an AutoPlay repeat; PlayerState value is lowercase;
  reorder request requires a JSON body. These correct setup against existing contracts.
  Regression doubles assert new PlaybackService delegation and persisted membership
  service calls, retaining resource assertions and adding no-Collection-call checks.
- Independent review performed by `corrective_review` read-only agent; root repeated
  actual SQLite/MockMPD audit. Two new independent blockers are confirmed in unchanged
  next/play_now/start_track paths and unavailable-next handling. Do not fix them here.
- Final A/B focused: 32 passed; affected regression: 198 passed. Full/static results
  and exhaustive contract audit are recorded in the linked corrective acceptance.
- Initial conditional publication was withheld because of C/D. Subsequent explicit
  user instruction “先执行push” authorizes committing/pushing the reviewed correction.
  Verify fresh remote ref/commit after publication; C/D and Batch 6 block remain.
  No Task 5 completion, PR or main merge.
