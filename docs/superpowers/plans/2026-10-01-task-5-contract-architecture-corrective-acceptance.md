# Task 5 Contract / Architecture Corrective Acceptance and Handoff

Date: 2026-10-01. Branch: `feature/task-5-library-api`.

**Latest local handoff:** A/B CLOSED; newly reproduced independent C/D OPEN.
**Batch 6 readiness remains BLOCKED.** See “Current Pre-Batch-6 A/B corrective
handoff” below. Publication was subsequently explicitly authorized by the user;
readiness remains blocked. Earlier published SHAs/results below are historical.

**Corrective implementation and local automated validation: COMPLETE.**
**Overall Task 5 / readiness to enter Batch 6: PARTIALLY COMPLETE — BLOCKED.**
Batch 6 was not executed; original Plan Steps 9–10 were not edited or checked. No main merge or PR.

## Current evidence and scope

Fresh `git fetch origin`, `git ls-remote origin refs/heads/feature/task-5-library-api refs/heads/main` and `git rev-parse HEAD origin/feature/task-5-library-api` confirmed initial local/remote Task 5 SHA `1912ea178d2ee31e92e289b937b6da5fd69b91c5`, main `43fa8999cee72c2ca7c88e2f8e3147b956d2525c`, clean workspace. Current history contains the baseline sync and Task 4 corrective work; historical acceptance counts were not substituted for tests in this run.

Sources checked: four files under `docs/superpowers/specs/`; original `2026-09-25-mpd-server-v0-1-implementation-plan.md` Task 5; Task 5 batch plan §4.7 contracts and Batches 1–5/6 boundaries; Task 5 baseline sync and Task 4 corrective plan/acceptance; current routes, domain models, services, repositories, PlayerPort and tests. Minimal design, file scope, compatibility supplement and execution rulings were recorded before production changes in [corrective plan](2026-10-01-task-5-contract-architecture-corrective-plan.md).

Actual changes:

- `services/library_service.py`: category summaries, grouping/dedup/counting/ordering, category membership over all persisted Songs, typed source-not-found error and synthetic unknown category IDs.
- `services/collection_service.py`: delegates category membership to LibraryService, retains availability split, dedup, seeded order and PlaybackContext refresh behavior. Removed the now-unused local album sorter and unreachable Library branch.
- `models/library.py`: service-owned domain summary models, independent of API schemas.
- `api/library.py`: catalog endpoints serialize service summaries; no catalog grouping or sorting remains in API.
- `api/schemas.py`: only necessary contract supplement: YearSummaryResponse gains source_id and nullable value. Known years remain integers with existing ascending order, unknown value is null/source_id `unknown`, ordered last. Clients must accept null and use source_id for category requests. Other resource fields remain unchanged.
- `main.py`: one typed source-not-found handler shared by collection reads, category song routes and collection playback; fixed 404 code/details.
- `api/playback.py` / `services/playback_service.py`: preserve Playlist 404 contract in playback, use typed Song lookup errors instead of message prefixes, and raise existing QueueItemNotFoundError for absent Queue item play. This minimal related extension was recorded with evidence before implementation; Song playback error status/code remains 404/PLAYBACK_REQUEST_INVALID, typed exceptions remain ValueError-compatible.
- `tests/api/test_task5_corrective.py`: 51 focused cases using real SQLite, actual Services and MockMPD where playback is involved; source absence, legal emptiness, all-unavailable membership, unknown/blank values, ID collisions, real invalid-date FLAC scan, unchanged metadata/media bytes and typed error mapping.
- `tests/api/test_library_api.py`: adapt only catalog service double to new service interface; existing assertions retained.
- `tests/services/test_library_service.py`: one direct summary contract test for IDs, representative album year, dedup/counts and availability.
- Related records only: corrective plan, this acceptance/handoff and a linked note in the Task 5 batch plan. No Repository schema, scanner, dependency, environment, Queue orchestration, unrelated tests or future Task implementation was changed.

## RED → GREEN evidence

| Correction | Executed RED | Executed GREEN |
|---|---|---|
| A: absent sources | 16 real mismatches: five categories read/play return 200, Playlist play returns 400, five category song routes return 200 | 27 passed, including six source types, five song routes, all-unavailable categories and five legal empty sources |
| B: catalog Service boundary | 2 failures: missing LibraryService catalog methods; summary-only service causes API 500 because API enumerates Songs | 2 focused passed; related combined regression 108 passed |
| C: unknown categories | 13 failures: missing/blank summaries and collision separation absent | 13 passed, including API summary → category songs → Collection → actual PlaybackService/MockMPD |
| Related playback errors | 4 failures: Queue item play 400; Song lookup errors generic; plain ValueError mapped to 404 by its message | 4 focused passed; PlaybackService + mutation API regression 43 passed |

Additional checks first passed once implementation existed: five unknown all-UNREADABLE source cases; real invalid-date parsing → persisted null year → unknown Collection, with media bytes unchanged. These are coverage, not claimed RED evidence.

Fixture corrections: Repository derives Album identity, so the unavailable Album test now reads its persisted ID. Initial MockMPD playback fixture omitted its known song URIs; seeded the documented constructor. Invalid-year integration initially scanned the shared fixture root's intentionally broken.mp3; complete traceback confirmed expected MediaMetadataError abort. Isolated a valid generated FLAC in a new subdirectory, reran the exact test (1 passed), and retained scanner code and strict assertions. Initial Ruff import failures were fixed only in scoped imports; unrelated formatter changes were removed. No environment failures or dependencies changed.

## Executed verification (repository root, existing venv)

Environment commands: `test -x .venv/bin/python`; `.venv/bin/python --version` → 3.14.4; `.venv/bin/python -m pytest --version` → 9.1.1; `.venv/bin/python -m ruff --version` → 0.16.9. Existing requirements inspected. No system Python, second venv, Docker, dependency change or live MPD was used.

| Command | Actual result |
|---|---|
| `.venv/bin/python -m pytest -q server/tests/api/test_task5_corrective.py` | 51 passed |
| `.venv/bin/python -m pytest -q server/tests/api/test_task5_corrective.py server/tests/services/test_library_service.py server/tests/services/test_collection_service.py server/tests/services/test_playlist_service.py server/tests/api/test_idempotency.py server/tests/api/test_library_api.py server/tests/api/test_mutations_playback.py` | 141 passed |
| `.venv/bin/python -m pytest -q server/tests/api` | 102 passed |
| `.venv/bin/python -m pytest -q server/tests/services` | 155 passed |
| `.venv/bin/python -m pytest -q server/tests/repositories` | 44 passed |
| `.venv/bin/python -m pytest -q server/tests/repositories/test_available_songs.py server/tests/repositories/test_library_reconciliation.py server/tests/services/test_library_scanner.py server/tests/services/test_library_watch.py server/tests/services/test_library_scheduler.py server/tests/services/test_media_metadata.py server/tests/services/test_playback_service.py server/tests/services/test_queue_manager.py server/tests/services/test_autoplay.py server/tests/services/test_history_service.py server/tests/integration` | 144 passed |
| `.venv/bin/python -m pytest -q server/tests` | 354 passed; final fresh repeat also 354 passed |
| `.venv/bin/python -m compileall -q server` | exit 0 |
| `.venv/bin/python -m ruff check server` | All checks passed |
| `git diff --check` / staged diff check | exit 0 |
| `git diff`, `git diff --stat`, `git status --short`, staged stats and changed-files review | scoped files only, no runtime/dependency/generated assets |

API/full tests report one existing Starlette TestClient/httpx deprecation warning. No test was deleted, skipped, xfailed or weakened. Broader automated PASS does not cover the independent defects reproduced below.

## Entire Task 5 contract and architecture re-audit

Independent read-only reviewer and root both inspected real call paths; root repeated defect reproductions. No assertion of compliance is based solely on imports or tests.

| Contract area | Actual chain / conclusion |
|---|---|
| ALBUM/ARTIST/GENRE/YEAR/TAG | API → CollectionService → LibraryService.category_members → LibraryRepository.list_songs. Source existence before availability split; typed 404. IDs/sorts/dedup maintained. Unknown is a view category, never fabricated Song metadata. |
| SEARCH | CollectionService → LibraryService.search_library → available Songs; exact/prefix/substring rank with stable fallback; empty/no-match is valid empty. |
| PLAYLIST/FAVORITES | CollectionService → PlaylistService → persisted relations → Song resolution. Saved order / favorite created_at DESC + song_id DESC, unavailable split, independence from Queue/History retained. PlaylistResponse has blocker B below. |
| LIBRARY/SONGS | All-song enumeration and availability split / explicit first-occurrence order. Empty selection never random-fills. |
| Random / PlaybackContext | Seed shuffles once; context carries ordered_song_ids; refresh resolves those IDs and retains order; PlaybackService accepts ordered context without reshuffle. QueueRepository replacement preserves supplied order and revision/transaction rules. |
| API routes/request/response/status | Required frozen library/playlist/favorite/playback/queue/history routes registered. Schema validation precedes Service calls; stable error envelope; 200/201/204/400/404/409/422/500/502/503 mappings inspected. Year supplement explicitly documented. Same Playlist schema semantics still blocked by B. |
| Playback/History | CollectionService → PlaybackContext → PlaybackService → QueueManager/HistoryService/AutoPlay/PlayerPort. Normal controls and seek reach PlayerPort confirmation. History API delegates reason semantics to HistoryService; Queue Played and permanent History separated. Queue mutation route chain blocked by A. |
| Playlist persistence | Repository transactions enforce duplicates/member mismatch and atomically reorder/delete relations; Song/file remains independent; Up Next save excludes Played/History and rejects duplicate selections. |
| Idempotency/transactions | Middleware → IdempotencyService → SQLite Repository. Canonical JSON payload hash, global key conflict, persisted terminal replay, failure retry; ContextVar carries same SQLite transaction into Repository calls. Existing actual trigger rollback tests included in API regression. SQLite atomicity inspected; no claim that it can rollback external PlayerPort side effects. |
| Architecture | API depends on Services, not SQLite/concrete MPD. Library summaries are domain models. Composition root wires repositories/player. No additional orchestration was introduced in API. Queue→Player synchronization is an existing functional blocker, not repaired by import hygiene. |
| Artwork/music read-only | LibraryService persisted ArtworkRef/source lookup → read-only Mutagen access/hash validation → bytes/MIME; observable artwork failures retained. New categories never write music files; invalid-date test checks generated fixture bytes unchanged after production scan. |
| Future isolation | No WebSocket/StateService, Output Manager, UI/PWA, final config, deployment or physical acceptance added. |

## Remaining independent blockers (not silently implemented)

### A — Queue mutations do not synchronize PlayerPort/History (Important)

Evidence: `server/app/api/playback.py` queue reorder/delete/clear handlers call QueueManager directly; `server/app/services/queue_manager.py` reorder/delete/clear update Repository state without PlayerPort. On current deletion the DB successor is marked PLAYING, but no player command or History transition occurs. Violates playback spec §5.2 consistency and authoritative orchestration.

Root reproduction command: `.venv/bin/python /tmp/task5-contract-audit.py`, using temporary SQLite and MockMPD, no live MPD. API play SONGS `[a,b,c]` returns 200; current DELETE returns 204:

```text
delete current: 204 API song: b Player URI: a.flac History active: a
clear: 204 DB pending: [] Player queue: ['a.flac', 'b.flac', 'c.flac', 'a.flac']
```

Fix needs a separate scoped corrective plan for PlaybackService orchestration, confirmation, history transition, pending synchronization and AutoPlay, with regression/rollback semantics. Not necessary to implement missing-source/catalog/unknown fixes, so left unchanged as the user required.

### B — PlaylistResponse membership differs across endpoints (Important)

Evidence: `server/app/api/playlists.py` list and mutation response paths use PlaylistService.list_song_ids (persisted all members); detail uses available-only Collection.song_ids. Violates library spec §5.1 persistent membership and frozen §4.7.6 same authoritative resource semantics.

Same executed root reproduction: persist MISSING Song, create Playlist, add Song; response/list/detail respectively:

```text
playlist mutation/list/detail: ['missing'] ['missing'] []
```

Fix needs consistent persisted membership in PlaylistResponse, keeping availability in Collection/playable views. Independent from the three scoped corrections; do not silently implement it here.

No Critical finding or deferred Minor finding. Reviewer declined real MPD/NAS/DAC and future UI/realtime/output/config/deployment validation: these are explicitly outside Task 5; ruling is to retain their original later acceptance gates. No PASS for these unexecuted checks.

## Handoff / Git

Repair commit: `a3fc1b1fe548652c81573204d7c214049ba921b7` (`fix(task-5): close collection contracts and catalog boundaries`). Verified locally with `git rev-parse HEAD`, `git log -3 --oneline`, `git show --stat --oneline HEAD` and clean status.

Publication verification is recorded after the push below; this document's final SHA is obtained with `git log -1 --format=%H -- docs/superpowers/plans/2026-10-01-task-5-contract-architecture-corrective-acceptance.md`. Final HEAD/remote equality is verified again after the documentation push and reported in the terminal handoff.

Next stage: resolve independent blockers A/B under a separately authorized scope before Batch 6. This repair does not close overall Task 5, original Steps 9–10, the Batch 6 final commit, or main integration. Required local environment validation for this corrective scope is complete; overall acceptance remains blocked by the reproduced contracts/architecture, not by the environment.

Repair publication actually verified: `git push origin HEAD:refs/heads/feature/task-5-library-api` succeeded; fresh `git fetch origin` / `git ls-remote` and `git show --format=fuller --stat origin/feature/task-5-library-api` confirmed repair SHA `a3fc1b1fe548652c81573204d7c214049ba921b7` exists remotely. At this repair publication checkpoint HEAD = remote feature ref; remote main remained `43fa8999cee72c2ca7c88e2f8e3147b956d2525c`. Workspace was clean before this documentation-only update.

## Current Pre-Batch-6 A/B corrective handoff (2026-10-01)

This section supersedes the earlier A/B **OPEN** handoff above. Earlier evidence and
published SHAs remain historical records, not the current readiness determination.

- **A — Queue mutation orchestration: CLOSED in current local implementation.**
- **B — Playlist persisted membership: CLOSED in current local implementation.**
- **Readiness to enter Batch 6: PARTIALLY COMPLETE — BLOCKED.**
- Two newly confirmed independent blockers remain; neither was implemented here.
- No Batch 6 Step 9/10, Task 5 completion checkbox, PR or main merge was performed.

### Actual baseline, reproduction and changes

Current branch was `feature/task-5-library-api`, clean at start, HEAD `86aedd6`
(`docs(task-5): record corrective verification and acceptance blockers`). All four
specs, original Task 5 Steps 1–8, Batch Plan Contract Audit/Batches 3–5, existing
corrective acceptance, actual Task 4 Playback/Queue/History/AutoPlay contracts,
Repository and PlayerPort implementations were inspected. The [A/B corrective plan](2026-10-01-task-5-pre-batch6-ab-corrective-plan.md)
was written before production edits. No assumption of historical test completion was
substituted for reproduction.

A/B were reproduced through actual API → Service → SQLite and MockMPD: reorder,
pending/current deletion, clear execution queues differed; Playlist detail and song
resources hid MISSING/UNREADABLE persisted members. Initial six original mismatches
and ten additional failure/contract cases were RED (16 failed). After first GREEN,
further RED→GREEN cases verified final status, explicit STOP preservation, outer
idempotency failure rollback of in-memory History, and duplicate URI occurrence.
Fixture corrections are recorded in the plan ledger; none weakened a business assertion.

Changes and why they belong to this correction:

- `api/playback.py`: reorder/delete/clear enter PlaybackService. Typed confirmation
  failure gets 502/PLAYBACK_RECONCILIATION_FAILED/details=null; existing command,
  availability, revision and unexpected-error mappings remain.
- `services/playback_service.py`: new serialized mutations coordinate QueueManager,
  AutoPlay, PlayerPort and History. Execution queue excludes Played. Current deletion
  skips unavailable successors, attempts existing AutoPlay when empty, switches and
  confirms actual URI/state/MPD occurrence before saving state/History; no candidates
  confirms STOPPED and closes History. Explicit Stop never restarts. Sync handles empty
  desired execution queues and checks actual results. Partial external MPD effects are
  observable failures, not falsely reported database success, and can be retried.
- `services/queue_manager.py` / `repositories/queue_repository.py`: opt out of speculative
  state persistence and opt in to moving current to Played without a successor after
  application resolution. Defaults retain existing Task 4 QueueManager/Repository
  contracts; neither becomes a PlayerPort orchestrator.
- `repositories/database.py` / `services/history_service.py`: minimal outer-transaction
  rollback callback and History active/session checkpoint. Only new delete registers;
  real SQLite terminal-record triggers prove both successor and STOP rollback/retry.
  The unchanged playback paths are explicitly left as blocker C below.
- `player/mock_mpd.py`: queue-backed status reports MPD occurrence identity/position
  rather than library index; removing the active queue entry stops it. Required to
  make duplicate/current cross-layer tests observe actual execution behavior. Existing
  standalone controls and injection tests pass.
- `api/playlists.py`: list/detail/mutation PlaylistResponse always represents persisted
  ordered members. `/playlists/{id}/songs` reads every member in persisted order and
  exposes AVAILABLE/MISSING/UNREADABLE via existing SongResponse.availability_status.
  Impossible dangling relations report failure rather than silently omitting a member.
  Collection continues to expose playable song_ids and unavailable_song_ids separately.
- `tests/api/test_pre_batch6_corrective.py`: 32 actual SQLite/Services/MockMPD cases,
  including replay, failure rollback/retry, revision, availability, session controls,
  History transitions, execution identity and all requested Playlist response paths.
- `tests/api/test_mutations_playback.py` / `tests/api/test_library_api.py`: only directly
  affected service doubles/delegation assertions. Original response/error assertions
  retained; persisted membership read additionally asserts no Collection call.
- Corrective plan, this handoff and linked Batch Plan note only. No dependency/schema,
  environment, music-file, unrelated feature, runtime artifact or future Task change.

### Fresh mandatory re-audit

Independent reviewer inspected the actual code/diff, and root repeated reproductions.
Automated PASS does not override the independent failures below.

| Required contract | Actual result |
|---|---|
| Original Task 5 Steps 1–5 | All Collection sources, stable Song IDs/dedup/default order, fixed seeded PlaybackContext, empty handling, Library/Playlist/Collection Service boundaries retained. |
| Original Steps 6–8 / Batch 3–5 | Required REST resources and stable schema envelopes present; A/B repaired. Step 7–8 playback idempotency/History has blocker C; unavailable playback has blocker D. |
| API → Service → Repository/PlayerPort | API imports no Repository/SQLite/concrete MPD. Queue mutation orchestration is in PlaybackService; composition root still wires resources. |
| Sole playback authority | PlaybackService owns player commands, confirmation, History and AutoPlay. QueueManager owns business mutation only; no second orchestrator added. |
| Queue/History/Playlist/Collection/Context independence | Played is excluded from execution queue and default Queue-save Playlist. Persistent History survives Queue mutation; Playlist persisted order differs intentionally from Collection playable split. C remains in unrelated playback transitions. |
| Unavailable membership | Playlist resource includes MISSING/UNREADABLE; Collection playable split unchanged. Current deletion skips unavailable successors. Existing Next does not: blocker D. |
| Idempotency/errors/transactions/revision | Canonical persisted replay/conflict and validation/command/unavailable mappings retained. New A operations serialize inside original SQLite/idempotency transaction; stale revision precedes player commands; new delete restores History memory after outer rollback. Existing playback operations lack that safeguard: C. |
| Artwork read-only | LibraryService still reads persisted ArtworkRef/source without writes; prior artwork/source/error/read-only regression passes. No Artwork or scanner production edits. |
| Future Task isolation | No WebSocket/StateService, Output Manager, Web/PWA, config, backup/deployment or physical acceptance implementation. Original Task 5 checkboxes untouched. |
| Search for independent blockers | Two Important findings C/D below. No other confirmed blocker from this audit; no Critical or deferred Minor finding. |

### New independent blocker C — playback History memory survives failed transaction

Code evidence: existing `PlaybackService.start_track`, `play_now`, `next` call
`HistoryService.start_track()` inside the API's outer idempotency transaction without
registering History rollback; `HistoryService.start_track()` changes `_active`, while
`IdempotencyService.execute()` creates its terminal record only after the route returns
(`services/idempotency_service.py:46–66`). These playback method bodies are unchanged
from baseline `86aedd6`; new delete's checkpoint does not conceal the broader defect.

Root repeated `.venv` audit using temporary SQLite, real Services and MockMPD:

```text
next HTTP 500 Queue rollback True DB song a History active b History persisted []
retry 200 History persisted [('b', 'SWITCH_AWAY')]
play_now HTTP 500 Queue rollback True DB song a History active b History persisted []
retry 200 History persisted [('b', 'SWITCH_AWAY')]
start_track HTTP 500 Queue rollback True DB song a History active b History persisted []
retry 200 History persisted [('b', 'SWITCH_AWAY')]
```

Deterministic reproduction: seed AVAILABLE a/b/c and play SONGS [a,b,c]. In the
same temporary database install:

```sql
CREATE TRIGGER fail_terminal BEFORE INSERT ON idempotency_records
WHEN NEW.idempotency_key='failure'
BEGIN SELECT RAISE(ABORT, 'forced terminal failure'); END;
```

POST `/api/playback/next`, `/api/playback/queue/items/{b_queue_item_id}/play`, or
`/api/playback/tracks/b/play` with `Idempotency-Key: failure` (separate fixture per route).
Read Queue snapshot/PlaybackState/persisted History/HistoryService.active_event.
DROP only that temporary trigger, retry the identical request/key, then read History.
The failed request loses a's actual transition and retry records a phantom b transition.

Contract: original Task 5 Steps 7–8; Batch Plan §4.7.7 / Batch 5 business+terminal atomic
boundary; playback spec §2.2 and §7 distinct actual History events. Minimal next scope:
make existing History-changing playback paths preserve active/session through their
own/outer transaction failures, with real SQLite trigger rollback and same-key retry
regression for start/play-now/next and affected previous/stop/context/reconciliation.
Do not add realtime/state/config features or attempt to treat SQLite as MPD rollback.

### New independent blocker D — Next aborts instead of skipping unavailable pending

Code evidence: unchanged `PlaybackService.next()` selects `up_next[0]` and immediately
calls `_require_available_song(target.song_id)` (`services/playback_service.py:308–309`).
A pending b marked MISSING with later c AVAILABLE causes 404/PLAYBACK_REQUEST_INVALID,
leaves a playing and never reaches c. Root's fresh reproduction:

```text
unavailable_next HTTP 404 Queue rollback True DB song a History active a History persisted []
```

Setup: fresh temporary SQLite fixture, AVAILABLE a/b/c, play SONGS [a,b,c], persist b
as MISSING, POST `/api/playback/next` with a fresh idempotency key. No external service.

Contract: playback spec §8.3 (skip invalid items, record cause, continue valid successor,
otherwise AutoPlay) and library spec §9. Minimal next scope: existing Next successor
resolution/observable unavailable reason/AutoPlay fallback and confirmed transition,
with MISSING/UNREADABLE, all-unavailable and failure/revision/idempotency regressions.
This is distinct from A current deletion and was not silently implemented.

### Verification and Git ruling

Environment verified: Python 3.14.4, pytest 9.1.1, Ruff 0.16.9 in existing `.venv`;
`server/requirements.txt` inspected. No environment failure, dependency change, system
Python, Docker or live MPD. Tests report only existing TestClient/httpx deprecation.

Final command results are listed below. Earlier full run found the directly affected
old Playlist-detail delegation expectation; replaced it with explicit persisted-service
calls and no Collection call, then exact test/file/regressions reran GREEN. No test was
deleted, skipped, xfailed or weakened.

The initial conditional publication gate was unmet because C/D remain. The user
subsequently explicitly instructed “先执行push”, authorizing commit and publication
of this reviewed correction while retaining both blockers. Commit/push does not close
C/D or authorize Batch 6. The correction SHA is obtained from Git history, and fresh
remote ref/commit equality is verified and reported after push. No PR, Batch 6 final
acceptance/commit, Task 5 checkbox or main merge is authorized or performed.

Final executed commands (repository root, existing venv):

| Command | Result |
|---|---|
| `.venv/bin/python -m pytest -q server/tests/api/test_pre_batch6_corrective.py` | 32 passed |
| `.venv/bin/python -m pytest -q server/tests/api/test_library_api.py::test_playlist_read_uses_persisted_membership_service` | 1 passed |
| `.venv/bin/python -m pytest -q server/tests/api/test_library_api.py` | 21 passed |
| `.venv/bin/python -m pytest -q server/tests/player/test_mock_mpd.py server/tests/player/test_mock_mpd_injection.py` | 4 passed |
| `.venv/bin/python -m pytest -q server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_playback_service.py server/tests/services/test_queue_manager.py server/tests/services/test_autoplay.py server/tests/services/test_history_service.py server/tests/api/test_mutations_playback.py server/tests/api/test_playlist_reads.py server/tests/api/test_idempotency.py server/tests/api/test_library_api.py server/tests/services/test_collection_service.py server/tests/services/test_playlist_service.py server/tests/repositories/test_playlist_repository_task5.py server/tests/integration server/tests/player/test_mock_mpd.py server/tests/player/test_mock_mpd_injection.py` | 198 passed |
| `.venv/bin/python -m pytest -q server/tests` | Final fresh run: 386 passed |
| `.venv/bin/python -m compileall -q server` | exit 0 |
| `.venv/bin/python -m ruff check server` | All checks passed |
| `git diff --check` | exit 0 |
| `PYTHONPATH=. .venv/bin/python /tmp/prebatch6-independent-audit.py` | Root reproduced C on next/play_now/start_track and D on Next; exact fixture/trigger/routes/output above |
| `git diff`, `git diff --stat`, `git status --short`, direct inspection of two untracked files | 14 intended files only (12 tracked changes plus new plan/test); no runtime/environment/dependency/artwork/future Task files |
| `git diff -- docs/superpowers/plans/2026-09-25-mpd-server-v0-1-implementation-plan.md` | empty; original Task 5 checkboxes untouched |
| `git branch --show-current` / `git rev-parse HEAD` | feature/task-5-library-api / 86aedd646a2355363978f34f68741400aa6fce24 |

Local automated/environment validation and A/B implementation are complete. Overall
contract acceptance remains blocked by reproduced C/D. Real MPD/NAS/DAC/manual future
acceptance remains outside this scope and has not been claimed PASS. Next action is a
separately scoped C/D corrective with RED and the minimum ranges above, followed by
another full contract re-audit; it is not Batch 6 authorization.
