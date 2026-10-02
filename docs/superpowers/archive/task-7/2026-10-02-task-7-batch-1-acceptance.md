# Task 7 Batch 1 execution evidence

Date: 2026-10-02. Scope authority: active Task 7 plan §7 B1; this file is
execution evidence, not a new specification or Contract Matrix.

## Baseline and pre-flight

- Branch: `feature/task-7-output-manager`.
- Start HEAD: `345d50cef0b866298d596f34faa085ab702e48c0`; working tree clean.
- `git fetch origin` completed; prerequisite commits `03f4de9` and `86975d6`
  verified reachable with `git merge-base --is-ancestor`.
- Existing `.venv`: Python 3.14.4, pytest 9.1.1, Ruff 0.16.9. No dependency,
  environment, Docker, live MPD or runtime database changes.
- Initial R-PORT step4/6 run: **4 passed**.
- Approved design executed in the specified checkout/branch; no redesign or
  additional worktree/environment.

## Contract Matrix Impact Analysis

Owned: **O-DISC-001**, **O-STATE-001 (read phase only)**,
**O-RESERVED-001**. Relied: **PORT-OUTPUT-001**, unchanged.
Regression Contract IDs: **none** per B1; R-PORT is the direct regression.
Relationship Gate: **REQUIRED**. Contract Matrix Gate: **REQUIRED**.
No new or modified Contract rows and no Contract Gap.

| ID | Authoritative Spec / active row | Delta and confirmation | Unchanged / failure / retry | Implementation / executable proof |
|---|---|---|---|---|
| O-DISC-001 | Chapter 3 §4.2/6.1; active §4.2 | Current ALSA candidate/fact from `outputs()`; refreshed identity after ID drift | Outputs and playback unchanged; absent/ambiguous/foreign/throwing selector fails closed; every refresh rereads | `output_manager.py` `_observe`/`_select_target`; F1 `test_output_identity_and_observation_follow_current_port` |
| O-STATE-001 (read) | Chapter 3 §5.2/6.1; active §4.2/5 | ACTIVE/INACTIVE only from a fresh read; stream fields null; request dimension separate | Failed reads keep last confirmed fact/time with stale, or unknown UNAVAILABLE without cache; retry refreshes; no playback/DB writes | `models/output.py`, manager observation/cache; F1 identity and `test_output_read_failure_marks_last_confirmed_fact_stale_and_retry_refreshes` |
| O-RESERVED-001 | Chapter 3 §5/6.1; active §4.2 | Enable and disable refuse with OUTPUT_MODE_UNSUPPORTED | No player call, runner entry or success event, including enabled HTTPD/disconnected/repeated requests; NAS observation unchanged | manager `set_enabled`; F1 `test_reserved_mode_has_no_external_side_effect` |
| PORT-OUTPUT-001 (relied) | Chapter 3 §4/10; main Task 1R; active §4.3 | Existing capability gate and typed output transport consumed | No transport implementation changes; no output control in B1 | Existing VerifiedPlayerPort/MockMPD; R-PORT step4/5/6/7 |

F1 crosses OutputManager → VerifiedPlayerPort → MockMPD, with a recording
subclass retaining real Mock behavior. Read tests compare actual outputs,
execution queue occurrences and full PlayerStatus (including position,
repeat/random/volume); call recording proves no mutation/other player access.
The service has no Repository, SQLite or playback authority dependency.
Reads enter the injected operation runner; its real PlaybackService integration
and preservation guard remain B3. Read/rejection paths create no History or
success event. Cache snapshots are copied, not retroactively rewritten.

## RED → GREEN and Step checks

The B1 shared execution checklist was followed in order: dependency/impact
pre-flight, test-first behaviors, minimal implementation with focused/F1 gates,
regression/compile/lint/diff checks, evidence and review.

| Minimum behavior | Observed RED | Observed GREEN |
|---|---|---|
| Single ALSA ACTIVE/INACTIVE, reserved representation | 2 assertion failures: observation module absent (tests collected, environment operational) | 2 passed |
| No/multiple ALSA, selector acceptance/refusal, ID refresh | 7 failed / 1 passed: absent target handling and selector behavior | 8 invariant cases passed; cumulative focused 10 passed |
| Read capability/transport failure, cached and uncached stale/retry | 8 failed: typed errors escaped or capability failure fabricated fresh data | Exact 8 passed; cumulative focused 18 passed |
| CLIENT_STREAM refusal / unopened NAS control | 6 failed: set_enabled missing | Exact 6 passed; cumulative focused 24 passed |

After each GREEN round the affected F1/focused tests and `git diff --check` /
`git status --short` were inspected before continuing. Initial import discovery
assertion was replaced with ordinary production imports after the feature existed.
No RED was caused by missing environment dependencies or test collection errors.

## Final automated evidence

All commands ran from repository root using `.venv/bin/python`:

- `-m pytest -q server/tests/services/test_output_manager.py server/tests/invariants/test_output_observation.py`: **24 passed**.
- `-m pytest -q server/tests/invariants/test_output_observation.py`: **20 passed**, explicit F1 gate.
- `-m pytest -q server/tests/player/test_task1r_step4.py server/tests/player/test_task1r_step6.py`: **4 passed**.
- Extended R-PORT step4/5/6/7 plus `server/tests/invariants/test_architecture_relationships.py`: **8 passed**.
- `-m pytest -q server/tests`: **468 passed**; no failures/errors/skips/xfails.
- `-m compileall -q server`: exit 0.
- `-m ruff check` on the four changed Python files: **All checks passed**.
  First run found two I001 import-order violations; only those imports were
  reordered, and the exact check rerun successfully.
- Invariant/full test runs emit one existing Starlette/httpx deprecation warning.
  Dependencies were not changed to suppress it.

## Scope, review and acceptance

Production files: `server/app/models/output.py`,
`server/app/services/output_manager.py`. Test files:
`server/tests/services/test_output_manager.py`,
`server/tests/invariants/test_output_observation.py`.
Only active-plan factual progress and this archived evidence are documentation
changes. No API/router/main, database, events implementation, playback changes,
MPD About, NAS enable/disable success, WebSocket, configuration or future Task
implementation. NAS mutation entry explicitly refuses until its owner Batches.

Independent review and final acceptance disposition are recorded below after
review completion. Task 7 as a whole and request-transition rows remain open;
physical NAS/DAC and HTTP acceptance belong to later owner Batches/Tasks.

Final disposition:

- `-m pytest -q server/tests/invariants`: **51 passed**, explicit broader
  invariant regression; unit/full-suite GREEN did not substitute for F1.
- Fresh independent read-only reviewer: no Critical/Important/Minor findings;
  independently ran focused/F1 + step4/6 + architecture: **30 passed**.
- Reviewer deferred NAS control success, playback runner/guard, request
  transitions, commit/event lifecycle, HTTP/idempotency, About and physical
  NAS/DAC checks as later-owner scope. These boundaries agree with active B1;
  implementing them now would breach Batch isolation. No review fix required.
- Changed-file review: only the four B1 Python files, active-plan factual
  progress and this archival evidence. No contract semantics changed.
- Relationship Gate **PASS** and Contract Matrix Gate **PASS for B1**:
  each owned read/rejection obligation traces to the Spec, implementation and
  fresh F1 evidence above. O-STATE-001 transitions and REST proof remain pending;
  O-DISC-001 ID-drift mutation proof still belongs to B5, reserved HTTP to B8.
- B1 acceptance satisfied; no blocker/Contract Gap. Ready for B2 pre-flight,
  without declaring any later Batch accepted. Final commit/ref verification is
  reported after the actual Git operation, not predicted in this document.
