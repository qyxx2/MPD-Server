# Task 5 Contract / Architecture Corrective Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline, with TDD and an independent superpowers:requesting-code-review pass.

**Goal:** Close the three pre-acceptance contract/architecture gaps; do not execute Batch 6 or mark original Steps 9–10.

**Architecture:** LibraryService owns catalog aggregation and category membership. CollectionService checks source existence before splitting availability. API validates, delegates, maps typed errors and serializes domain summaries.

**Tech Stack:** Existing ARM64 `.venv`, Python 3.14.4, FastAPI/Pydantic/SQLite; no dependency or environment changes.

**Spec:** `docs/superpowers/specs/2026-09-24-library-playlist-tag-search-design-2-1.md` §§3–9; playback model §§4–8; original implementation plan Task 5; Task 5 batch plan §4.7 frozen contracts. Baseline sync and Task 4 corrective acceptance are historical evidence, not current completion proof.

## Baseline and scope

Fresh fetch / ls-remote on 2026-10-01: local HEAD and remote feature ref = `1912ea178d2ee31e92e289b937b6da5fd69b91c5`; remote main = `43fa8999cee72c2ca7c88e2f8e3147b956d2525c`. Working tree clean. Work in the user-specified checkout/branch with its existing venv.

Files: `services/{library_service,collection_service}.py`, `models/library.py`, `api/{library,playback,schemas}.py`; focused API/service tests and required adaptations of catalog service doubles; this plan and a corrective acceptance/handoff record. `services/playback_service.py` only if the directly related typed playback lookup error is confirmed. No repository schema, scanner, music-file, dependency or future Task changes.

## Minimal contract supplement (before implementation)

- Frozen 404 for absent collection source applies equally to reads, category song routes and collection playback. Preserve `PLAYLIST_NOT_FOUND`; classification sources use `COLLECTION_SOURCE_NOT_FOUND` with fixed details `{source_type, source_id}`. No exception-string classification.
- Classification existence is determined from ALL persisted members, before availability filtering. Known all-unavailable sources return 200 with empty song_ids and explicit unavailable_song_ids. Empty Playlist/Favorites/Library/Search/SONGS remain successful empty reads. Playback retains existing empty-context semantics.
- Missing/blank/unparseable normalized metadata belongs to a synthetic **view category**, not fabricated Song metadata. Album has no usable album ID/title; Artist has no usable song/album artist; Genre/Tag have no usable names; Year is null after parsing. Unknown categories exist only when corresponding persisted members exist. IDs use a dedicated UUID5 namespace name `mpd-server:unknown:<kind>` to avoid collisions with a real value named “未知”. Year source ID is `unknown`.
- Year summary `value` becomes nullable and gains `source_id` (decimal year for known values, `unknown` for unknown). Existing known integer values and ordering remain unchanged; unknown last. Clients must accept null value and use source_id for collection requests. Other summary schemas unchanged; unknown name/title is “未知”; unknown Album year/date/artwork/album_artists remain null/empty. Song metadata is untouched.
- Existing available-only catalog summaries remain available-only; source existence and Collection use all persisted members.

## Review focus

All-unavailable sources; empty vs absent source; real “未知” names vs synthetic IDs; metadata blanks vs valid multi-values; playback errors/transaction rollback and retry. Verify actual call chains, not import checks alone.

## Correction A — source existence

- [x] Add real SQLite → Service → API tests for six absent source types on reads/playback and five category song routes; check typed 404, envelope and no queue/history/idempotency mutation.
- [x] Run `.venv/bin/python -m pytest -q server/tests/api/test_task5_corrective.py -k 'absent or empty or unavailable'`; expect current 200/400 mismatches (Playlist read already 404).
- [x] Add typed classification not-found error; check pre-split membership, map Playlist and classification errors identically across HTTP paths.
- [x] Rerun exact focused tests, then CollectionService/library API/playback API tests.

## Correction B — service boundary

- [x] Add direct LibraryService summary tests asserting stable IDs, ordering, representative album metadata, dedup counts and availability; API test uses a service double exposing only catalog methods, proving no song enumeration/aggregation in API.
- [x] Run focused tests; expect absent service methods / API enumeration failure.
- [x] Move existing aggregation into domain summaries returned by LibraryService catalog methods; API only serializes these results.
- [x] Rerun exact tests and API/library service regression.

## Correction C — unknown categories

- [x] Add missing/blank/parse-failure category tests, round-trip summary ID → category songs / Collection / playback, collisions with real “未知”, unavailable unknown membership, and unchanged Song metadata.
- [x] Run focused tests; expect missing unknown summaries/membership.
- [x] Implement shared category value/ID resolution in LibraryService and use it in CollectionService; implement documented nullable Year supplement.
- [x] Rerun focused tests and all affected tests.

## Re-audit and acceptance

- [x] Independently review entire Task 5 against specs and frozen routes/schema/status/idempotency/transaction contracts, tracing API → Service → Repository/PlayerPort, Playlist/Favorites, Queue/History, ordering/random context, read-only files and future Task isolation.
- [x] Record any additional evidence/range before a necessary associated fix; independent/out-of-scope gaps block readiness and are not silently implemented.
- [x] Run focused tests, API/Service/Repository aggregates, affected Task 2R/3/4 integration and services, complete `server/tests`, compileall, Ruff, diff/check/changed-files review using `.venv/bin/python` from root. Unexecuted checks cannot PASS.
- [x] Write corrective acceptance/handoff with actual commands/results and blockers. Commit and push only corrective scope; fresh fetch, ls-remote and remote commit read confirm published SHA. No main merge; no Batch 6 final commit.

## Execution rulings / findings

- Correction A API error mapping uses the composition root's typed exception handler in `server/app/main.py` so all category/read/playback paths share one error envelope. This file is added to the allowed scope. LibraryService owns the typed classification error; CollectionService delegates membership resolution.
- RED source reproduction: 16 contract mismatches plus one fixture error (Repository derives Album ID, not the supplied ID). Fixture corrected to query persisted Album ID; no production change for that fixture assumption. GREEN: 27 passed.
- Correction B RED: LibraryService missing catalog methods and summary-only service producing API 500. GREEN: 2 focused passed; affected combined regression 108 passed.
- Correction C RED: 13 missing/blank/collision cases failed. Initial GREEN attempt reached playback but MockMPD had no known URIs; seeded its documented songs input, no production workaround. GREEN: 13 passed; library/collection/corrective aggregate 83 passed.
- Re-audit associated finding: playback API still classifies Song errors with `str(exc).startswith(...)`, and PlaybackService.play_now raises ordinary ValueError for absent Queue item, which maps to 400 instead of frozen 404. These are the same typed-error/status boundary and will be closed only after focused RED. Scope extension: PlaybackService typed lookup errors plus focused service/API tests; preserve existing Song playback status/code and ValueError compatibility.

- Associated typed playback mapping RED: 4 cases failed (absent Queue item HTTP 400; two generic Song lookup errors; plain ValueError misclassified as 404 by message). GREEN: 4 passed; PlaybackService + playback mutation API regression 43 passed.
- Additional invalid-year integration check initially scanned the shared fixture root containing intentionally broken.mp3; complete traceback confirmed the documented MediaMetadataError abort. Isolated the valid FLAC fixture in a new generated subdirectory, retained strict assertions and scanner production code. Exact test rerun: 1 passed. No dependency/environment failures.
- Final review: independent read-only reviewer audited all Task 5 actual chains and found no blocker in A–C; two independent pre-existing Important gaps were confirmed again by root's `.venv/bin/python /tmp/task5-contract-audit.py`. They are retained as blockers: inconsistent PlaylistResponse membership; Queue reorder/delete/clear fail to synchronize PlayerPort, and current deletion leaves History stale. No unrelated implementation added.
- Final fresh automated verification: corrective file 51 passed; Task 5 focused combined 141 passed; API 102 passed; services 155 passed; repositories 44 passed; affected Task 2R/3/4 + integration 144 passed; complete server/tests 354 passed. compileall/Ruff/diff-check passed. Exact commands and audit coverage belong in the corrective acceptance record.
- Ruling: original Task 5 Steps 9–10 and Batch 6 remain unexecuted/unmodified. This corrective run's full-suite verification is required by the user's repair request; it does not close the overall Task 5 acceptance gate. Cost if wrong: falsely permitting final acceptance despite reproduced state/contract inconsistencies.

- Repair publication verified: push succeeded; fresh fetch/ls-remote/remote commit read confirmed `a3fc1b1fe548652c81573204d7c214049ba921b7`; main unchanged. Final documentation publication is separately re-read in terminal handoff.
