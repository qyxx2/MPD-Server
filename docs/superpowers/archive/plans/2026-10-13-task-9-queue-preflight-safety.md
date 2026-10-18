# Task 9 Queue Preflight Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Explicit user queue operations repair a mismatched MPD execution before sending the requested mutation.

**Architecture:** PlaybackService captures the full MS current/pending baseline inside the root transaction. Before the first MPD command it compares ordered occurrence IDs, URIs, partition, connection, playlist version and actual current/state. A mismatch creates a fixed, receipted clear/rebuild execution; retries validate their owned prefix rather than comparing the partially built execution to rolled-back MS state. Reads and background recovery remain passive.

**Tech Stack:** Python, SQLite, existing PlayerPort/ExecutionSynchronizer, pytest, GitHub Actions.

## Task 1: Full queue preflight and explicit repair

- [x] Add failing tests for extra/missing entries, unbound execution and foreign current, including playing/paused restoration and same-song elapsed.
- [x] Capture the pre-mutation queue and state in `_atomic_history_transition` without contacting MPD before request validation.
- [x] Apply preflight to selection preparation, queue synchronization and direct stop in current deletion.
- [x] Execute clear first on mismatch. For preserving actions rebuild the post-action full target, restore MS playing/paused state and seek only when the fresh actual sample confirms the same URI and has elapsed evidence. For selection actions clear before their existing preparation.
- [x] Preserve command receipts and fixed IDs across rollback; never resend an uncertain seek/add/play response.
- [x] Test all mutation entry points, rollback retries and invalid requests; run affected invariants/API/TCP tests and full backend regression.
- [x] Independent code review, fix actionable findings, inspect diff and update acceptance evidence.
- [ ] Commit and push the authorized branch, wait for CI and report verified image manifest SHA.
