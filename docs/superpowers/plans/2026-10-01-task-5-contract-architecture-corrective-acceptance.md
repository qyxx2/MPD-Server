# Task 5 Contract / Architecture Corrective Acceptance and Handoff

Date: 2026-10-01. Branch: `feature/task-5-library-api`.

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
