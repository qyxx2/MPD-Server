# Task 0–4 Integration Gate Acceptance Record

Date: 2026-09-29
Branch: `test/task0-4-integration-gate`
Gate: Task 0–4 backend integration

## Scope

This gate verifies coordination between the already-completed Task 0, Task 1, Task 1R, Task 2, Task 2R, Task 3, and Task 4 implementations before starting Task 5.

The permanent regression scope is backend-only:

- Task 3 scanner/metadata → Task 2 repository/SQLite persistence.
- Task 3 scan transaction → MPD update → domain event ordering and failure semantics.
- Task 4 Playback Service → PlayerPort → MPDAdapter using a stateful local Fake MPD.
- Task 2 + Task 3 + Task 4 end-to-end flow from real media fixtures to playback state and MPD queue state.
- Full integration-suite and server-suite regression coverage.

No Task 5–12 implementation is introduced by this gate.

## Web test scope

Web/PWA build and typecheck are **not part of this permanent Task 0–4 integration regression gate**.

They were previously validated separately. No Web/PWA test files are added to this integration branch, and the gate does not require rebuilding the Web application on each backend integration regression run.

The branch diff was checked against `main`; the integration implementation adds only backend integration test/support files under `server/tests/integration/`, plus this acceptance documentation and the README update.

## Integration test files

1. `server/tests/integration/test_task3_to_task2.py`
2. `server/tests/integration/test_task3_events_and_mpd.py`
3. `server/tests/integration/test_task4_with_mpd_adapter.py`
4. `server/tests/integration/test_task2_task3_task4_e2e.py`
5. `server/tests/integration/support/stateful_fake_mpd.py`

These tests use the real SQLite/repository/scanner/service implementations and a deterministic local stateful Fake MPD. They do not connect to or mutate the production NAS/MPD.

## Acceptance results

The user executed the integration validation in the real ARM64 local environment and reported that all required validation steps passed.

The accepted coverage includes:

- Task 3 → Task 2 real fixture scan and persistence.
- Metadata, technical audio fields, lyrics, and artwork-reference persistence.
- Move/rename identity preservation.
- Missing-file reconciliation while preserving the Song row and references.
- Commit → MPD update → event publication ordering.
- MPD update failure after database commit.
- Repository transaction failure preventing MPD update and event publication.
- Playback Service ↔ MPDAdapter synchronization.
- Queue mutation and MPD queue consistency.
- Pause/Stop/AutoPlay/History coordination.
- MPD command failure without falsely advancing authoritative server state.
- Full Task 2 + Task 3 + Task 4 end-to-end playback flow.
- Full integration regression.
- Full server regression.
- Compile, Ruff, and diff checks.

The test results above are recorded from the user's local execution; they are not claimed as independently executed by this acceptance record.

## Boundary verification

Accepted:

- Server Queue remains the authoritative business queue.
- Playback engine access remains behind `PlayerPort`.
- Playback Service does not directly access SQLite or concrete MPD transport.
- Task 4 behavior does not depend on Task 5–12 implementations.
- Real music files remain read-only.
- Production NAS/MPD is not mutated by these integration tests.
- No Web/PWA test dependency is introduced into the Task 0–4 backend regression gate.

## Validation limitation

This gate is an integration coordination check for Tasks 0–4. It is not the final Task 12 production acceptance. Real NAS/MPD capability validation remains covered by the earlier MPD capability record, while final deployment/update.sh/release acceptance remains in Task 12.

## Final conclusion

**COMPLETE**

Task 0–4 integration coordination is accepted. The backend integration regression suite is suitable as a permanent regression layer before Task 5, without adding Web/PWA build or test work to each backend regression run.
