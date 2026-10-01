# Task 5 Current Pre-Batch-6 Corrective Handoff

Date: 2026-10-01  
Branch: `feature/task-5-library-api`

This file is the sole active corrective Gate record. Archived A/B evidence:
`docs/superpowers/archive/task-5/2026-10-01-task-5-contract-architecture-corrective-acceptance-full-history.md`.
C/D reproduction, implementation rulings and verification:
`docs/superpowers/archive/task-5/2026-10-01-task-5-pre-batch6-cd-corrective-plan.md`.

## Current ruling

- Batch 1–5: COMPLETE.
- A — Queue mutation orchestration: CLOSED.
- B — Playlist persisted membership visibility: CLOSED.
- C — History memory restoration after playback transaction failure: CLOSED.
- D — Next unavailable successor resolution: CLOSED.
- E — Stop finalizes History without confirmed STOPPED player status: OPEN / BLOCKING.
- Batch 6 / original Task 5 Step 9–10: BLOCKED; not executed.

## Preserved C/D invariants

History-changing start/context/play-now/next/previous/stop/reconciliation operations join the owning SQLite transaction and restore active/session on failure, including cancellation. Real terminal-record triggers prove rollback and same-key retry/replay without phantom events.

Next skips unavailable pending occurrences with song/Queue identity and reason logs, continues a valid successor, and attempts existing AutoPlay when exhausted. Unavailable Songs/Playlist members remain persisted. With no candidates it preserves the confirmed current playback and leaves pending empty; it invents neither a successor nor an unconfirmed Stop. Final synchronization confirms the current occurrence. Command/unavailable/reconciliation/terminal failures restore server state and permit retry.

Fresh root validation: corrective 59 passed; affected aggregate 225 passed; repository aggregate 44 passed; full `server/tests` 413 passed; compileall, Ruff and diff check passed. Independent review repeated direct/outer cancellation rollback and found no remaining C/D blocker. These results do not establish that all playback contracts or Batch 6 are complete.

## Blocker E — Stop requires actual confirmation

Classification: independent pre-existing code gap and contract guard gap.

`PlaybackService.stop()` currently calls PlayerPort.stop/status and saves whatever status is returned, then calls HistoryService.stop without requiring STOPPED.

Independent deterministic reproduction uses a temporary SQLite database, real Services/API and MockMPD. Start song a; replace only player.stop with an async no-op; POST `/api/playback/stop` with a fresh Idempotency-Key. Actual result:

- HTTP 200 with state PLAYING;
- Player remains PLAYING;
- persisted History records a / STOP;
- active event and session become None.

Contract: playback spec §7 and active Task 5 plan §§3.6/5 require actual confirmed playback/History transitions. C/D did not introduce this defect and this correction does not silently repair it.

Minimum next corrective scope:

1. Reproduce with a failing real-Service/API Stop confirmation test.
2. Require confirmed STOPPED before committing state or finalizing History; use existing typed reconciliation error.
3. Verify snapshot/state/History active/session rollback, no successful terminal record, identical-key retry and replay, Player command/unavailable errors.
4. Run targeted and affected regression, full server/static/diff validation, then repeat the contract/architecture Gate audit.

Do not execute Batch 6 or mark original Steps 9–10 until E is closed and the audit has no remaining blocking violation. SQLite rollback does not imply player side-effect rollback. Live MPD/NAS/DAC/manual physical acceptance remains outside this corrective scope.
