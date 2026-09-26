# MPD-Server v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 在群晖 DSM 7.1.1 + 独立 MPD 0.23.5 上实现由 FastAPI 统一管理播放状态、Queue、AutoPlay、Library、Playlist、History 和输出状态，并由 Vue 3/PWA 提供客户端界面的 Music Server。

**Architecture:** FastAPI + SQLite + Repository/Service 分层；MPD 通过独立 Adapter 接入，Mock MPD 与真实 MPD 使用同一接口。Web 采用 Vue 3 + TypeScript + Vite，开发环境 Vite Proxy → FastAPI，生产环境 FastAPI 托管静态文件；Docker Compose 分离 dev/prod。Music Server 是业务权威，客户端不直接连接 MPD。

**Tech Stack:** Python、FastAPI、Pydantic、SQLite、pytest、Vue 3、TypeScript、Vite、Tailwind CSS、WebSocket、Docker Compose、Git/GitHub；真实播放引擎为 MPD 0.23.5。

**Spec:**
- docs/superpowers/specs/2026-09-24-playback-model-queue-semantics-design.md
- docs/superpowers/specs/2026-09-24-library-playlist-tag-search-design-2-1.md
- docs/superpowers/specs/2026-09-24-system-architecture-playback-output-design.md
- docs/superpowers/specs/2026-09-25-system-and-development-architecture-design.md



> Plan Revision 2 (2026-09-26): dependency-safe implementation order
>
> This revision keeps the historical completion of Task 0/1/2 intact and adds explicit prerequisite hardening before continuing Task 3. It closes dependency gaps discovered during the Task 3 Step 1-5 review.
>
> Approved v0.1 decisions:
> - No username/password authentication, session credentials, authentication middleware, or WebSocket authentication.
> - The real music library is strictly read-only. The scanner, metadata parser, artwork handling, watcher, scheduler and services never modify, rename, delete, tag, generate or write sidecar files in the music directory.
> - Album artwork is represented by a persisted reference to embedded artwork and read on demand by the API. The original media file remains read-only.
> - A valid sidecar LRC has priority over embedded lyrics. If the sidecar LRC exists but cannot be read or parsed, embedded lyrics may be used as fallback while the sidecar failure remains observable.

## Global Constraints

- MPD 固定按目标环境 0.23.5 实测，不假定新版本能力。
- Music Server 不安装、启动、修改或管理 MPD。
- 容器通过群晖 LAN IP 连接 MPD，禁止用容器 localhost 连接宿主机。
- 浏览器和未来 Android 不直接连接 MPD TCP。
- Queue、History、Playback Context、Saved Playlist 独立。
- Music Server 是 Queue、AutoPlay、播放状态和业务状态权威。
- API 不直接操作 SQLite 或 MPD；业务进入 services，持久化进入 repositories，MPD 进入 player/adapter。
- 音乐目录只读挂载，不修改/删除原文件。
- SQLite、配置、备份位于容器外持久化目录。
- dev 数据、配置、备份与 prod 完全隔离。
- dev 默认 Mock MPD，真实 MPD 仅联调/验收。
- Web 使用当前页面同源 API/WebSocket 地址。
- WebSocket 重连必须重新取得完整状态快照。
- 首期不做 PostgreSQL、Kubernetes、GitHub Actions CI/CD、复杂 Web 管理后台、多用户权限和复杂浏览器 E2E。
- 首期 Web/PWA 先完成，Android 只保留边界。
- NAS 默认只部署 main，不直接编辑源码。
- 稳定版本用 Git Tag。
- 关键状态更新必须有事务/串行化边界。
- 未知音频参数和 MPD 字段保持未知。
- LRC 时间戳必须保留，普通歌词不得伪造同步时间戳。
- 同一 Playlist 默认禁止重复 song_id；重复添加拒绝且不改变顺序。
- Favorites 是固定预置 Playlist；未收藏空心星，已收藏黄色实心五角星。
- AutoPlay 在耗尽前补充可见 Up Next；Stop 才结束自动接管，Pause 不结束。
- Play Now / Play Next / Add to Queue 在所有歌曲入口一致。
- 集合播放整体替换 Queue；随机顺序在本次 Playback Context 中固定。
- 输出切换默认保留当前歌曲、Queue、Playback Context、播放位置。
- MPD 暂时不可达时服务仍应启动并报告 MPD UNAVAILABLE。
- 生产日志必须轮转。

## Review Focus

1. MPD 0.23.5 与新版本能力差异：必须有真实能力探针。
2. AutoPlay 与 Queue 并发修改：用户操作不得被后台补充覆盖。
3. 文件移动/重命名：尽可能保持 Song ID、Playlist、Favorites、History。
4. WebSocket 断线：重连必须以完整快照恢复。
5. MPD、SQLite、服务层不一致：必须回读真实状态并显式报告。


## Dependency Gates and Contract Rules

These rules apply to the entire implementation plan.

1. A Task may depend only on contracts, schemas, repositories, ports, services or utilities implemented in an earlier Task or an explicitly earlier prerequisite hardening Task.
2. A Task must not import a concrete implementation owned by a later Task to bypass a missing earlier contract.
3. API code never accesses SQLite directly and never accesses MPD directly. The required direction is API → Service → Repository/Port.
4. Service code never depends on a concrete MPD adapter. Playback-engine access goes through PlayerPort.
5. Scanner code never depends on API, WebSocket, or the final configuration module. Runtime configuration is injected at the composition root.
6. Task 3, Task 4 and Task 7 never depend on Task 6 WebSocket code. They publish domain events through the earlier event contract.
7. The Web client never accesses MPD TCP and never becomes Queue or AutoPlay authority.
8. When a required contract is missing, implementation stops and the plan or contract is corrected before continuing. Temporary architectural bypasses are prohibited.
9. Every Step follows TDD: write the smallest failing test first, run the RED test, implement the minimum change, run the Step verification, then continue.
10. A Task is complete only after behavior tests, dependency-boundary checks, diff review, and remote commit/ref verification.
11. Historical RED checkpoints are development evidence; a completed Task does not need to remain permanently failing.
12. Real music files are never used as mutable test fixtures. Tests use temporary copies or generated fixtures outside the real library root.

---

## Task 0：工程骨架与开发/生产 Compose

**Files**
- Create: server/app/main.py
- Create: server/app/{api,services,repositories,models,player}/__init__.py
- Create: server/tests/conftest.py
- Create: web/index.html, web/package.json, web/vite.config.ts, web/tsconfig.json, web/src/main.ts, web/src/App.vue
- Create: deploy/docker-compose.dev.yml, deploy/docker-compose.yml, deploy/Dockerfile, deploy/.env.example
- Create: server/requirements.txt, Makefile, .gitignore
- Modify: README.md

**Interfaces**
- FastAPI app object: app
- /api/health returns {"status":"ok"}
- make test / lint / typecheck / build are stable entry points.
- Vite proxies /api and WebSocket to FastAPI.

- [x] Step 1: Write health endpoint test.
~~~python
from fastapi.testclient import TestClient
from server.app.main import app

def test_health():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
~~~
- [x] Step 2: Run pytest and verify it fails.
- [x] Step 3: Add the minimal FastAPI app and health endpoint.
- [x] Step 4: Run pytest and verify PASS.
- [x] Step 5: Add the Vue/Vite shell, including the required `web/index.html` entry point, and verify `npm run build`.
- [x] Step 6: Add Makefile targets and separate dev/prod Compose.
- [x] Step 7: Validate both Compose files with `docker compose config` in a Docker-capable environment (for example, the Synology Docker environment). This validates Compose configuration only; real MPD/USB DAC testing starts at Task 1 Step 7 and Task 12.
- [x] Step 8: Commit: chore: establish music server monorepo.

**Task 0 verification record (2026-09-25):**
- Final Task 0 source was reviewed against all four design specifications and the implementation plan.
- The production Web static-serving path is implemented by FastAPI and is included in the production image.
- Local acceptance completed for: server pytest, Node 22 typecheck/build, both Compose configuration checks, and production Compose startup/health plus root Web serving.
- Step 2 is a historical RED-phase development checkpoint; the final repository retains the resulting test and GREEN implementation rather than a reproducible failing-test state.

---

## Task 1：PlayerPort、Mock MPD、真实 MPD Adapter

**Files**
- Create: server/app/player/ports.py
- Create: server/app/player/models.py
- Create: server/app/player/mock_mpd.py
- Create: server/app/player/mpd_protocol.py
- Create: server/app/player/mpd_adapter.py
- Create: server/app/player/capabilities.py
- Create: server/tests/player/*
- Create: docs/mpd-0.23.5-capabilities.md

**Interfaces**
~~~python
class PlayerPort(Protocol):
    async def status(self) -> PlayerStatus: ...
    async def play(self, song_uri: str | None = None) -> None: ...
    async def pause(self) -> None: ...
    async def stop(self) -> None: ...
    async def next(self) -> None: ...
    async def previous(self) -> None: ...
    async def seek(self, seconds: float) -> None: ...
    async def set_repeat(self, enabled: bool) -> None: ...
    async def set_random(self, enabled: bool) -> None: ...
    async def set_volume(self, volume: int) -> None: ...
    async def update_database(self) -> None: ...
    async def outputs(self) -> list[OutputInfo]: ...
~~~

- [x] Step 1: Test PlayerPort/domain models.
- [x] Step 2: Implement deterministic Mock MPD with disconnect/fail-next injection.
- [x] Step 3: Test Mock play/pause/stop/next/previous/seek/status/events.
- [x] Step 4: Implement line-oriented MPD protocol parsing, including escaped values and ACK errors.
- [x] Step 5: Implement MPDAdapter with connection/command timeouts and typed PlayerUnavailable/PlayerCommandError.

**Task 1 verification record (2026-09-25, Steps 1-5):**
- Step 1 RED tests were created and verified before the PlayerPort/domain model implementation; the resulting model and interface tests pass.
- Step 2 injection tests were created before Mock MPD implementation; disconnect/reconnect and one-shot fail-next behavior pass.
- Step 3 control/event tests were created before Mock MPD implementation; play/pause/stop/next/previous/seek/status/events plus repeat/random/volume are covered, with seeded randomness deterministic.
- Step 4 protocol tests were created before parser implementation; escaped values, repeated keys, malformed responses, completion markers, quoting and ACK errors are covered.
- Step 5 adapter tests were created before adapter implementation; typed ACK mapping and connection/command timeout handling are covered, and command timeout closes the unusable connection.
- [x] Step 6: Test Adapter through a fake TCP server.
- [x] Step 7: Run capability probe against actual NAS MPD 0.23.5 and record commands, outputs, status fields, update behavior and errors.
- [x] Step 8: Restrict service features to verified capabilities.
- [x] Step 9: Commit: feat: add mpd adapter and verified capabilities.
**Task 1 verification record (2026-09-25, Steps 6-9):**
- Step 6: Added a real localhost TCP server test covering MPD greeting, command exchange, status/current-song parsing, song URI to MPD song ID lookup, playback controls, seek, volume, repeat/random, update and outputs. The test passes.
- Step 7: Completed against the real Synology DS920 MPD 0.23.5 endpoint on 2026-09-26. Recorded the full `commands` list (104 commands), 17 `status_fields`, two real outputs (USB DAC/ALSA enabled and HTTPD disabled), seven `stats` fields, `update_response: {"updating_db":"2"}`, and two error outcomes. The unknown-command probe produced a real connection close; the ACK probe returned error code 50 / "No such song". The probe result was saved on NAS as `mpd-0.23.5-probe-2026-09-26-091948.json`.
- Step 8: Added MPDCapabilities and VerifiedPlayerPort; operations whose required MPD commands were not verified are rejected before reaching the underlying PlayerPort. Song-URI playback additionally requires playlistinfo and playid; status requires status and currentsong.
- Step 9: This branch is committed with message feat: add mpd adapter and verified capabilities.

---

## Task 2：SQLite、Library、Playlist、Favorites、History Repository

**Files**
- Create: server/app/repositories/database.py
- Create: server/app/repositories/migrations.py
- Create: server/app/repositories/library_repository.py
- Create: server/app/repositories/playlist_repository.py
- Create: server/app/repositories/history_repository.py
- Create: server/app/models/library.py, playlist.py, history.py
- Create: server/tests/repositories/*

**Interfaces**
~~~python
async def initialize_database(path: str) -> None: ...
async def check_integrity(path: str) -> bool: ...
async def upsert_song(song: Song) -> Song: ...
async def get_song(song_id: str) -> Song | None: ...
async def find_song_by_file_uri(file_uri: str) -> Song | None: ...
async def create_playlist(name: str) -> Playlist: ...
async def add_song(playlist_id: str, song_id: str, position: int | None = None) -> None: ...
async def remove_song(playlist_id: str, song_id: str) -> None: ...
async def reorder_playlist(playlist_id: str, ordered_song_ids: list[str]) -> None: ...
async def set_favorite(song_id: str, is_favorite: bool) -> None: ...
async def record_history(event: HistoryEvent) -> None: ...
~~~

- [x] Step 1: Test fresh database, schema version, foreign keys, transaction boundaries and integrity.
- [x] Step 2: Define songs/albums/artists/genres/tags/playlists/playlist_items/favorites/history/queue/playback-state tables and indexes.
- [x] Step 3: Test stable Song ID reuse, path move/rename matching, metadata update and multi-artist relations.
- [x] Step 4: Test duplicate Playlist insertion is rejected without order changes.
- [x] Step 5: Test Favorites persistence and independent removal.
- [x] Step 6: Test History records start/end/reason/session independently of Queue.
- [x] Step 7: Implement repositories with serialized critical writes.
- [x] Step 8: Verify tests.
- [x] Step 9: Commit: feat: add sqlite library playlist and history repositories.

**Task 2 partial verification record (2026-09-26, Steps 1-4):**
- Step 1 RED tests were created before the repository implementation and committed on the Task2 feature branch; transaction commit/rollback, schema version, foreign-key enforcement and SQLite integrity checks pass.
- Step 2 defines the required Library/Playlist/Favorites/History/Queue/Playback-State tables and supporting indexes without implementing later service behavior.
- Step 3 tests stable Song ID reuse across file moves, metadata updates, and multi-artist relation replacement; the implementation matches by stable `identity_key` rather than treating file path as business identity.
- Step 4 tests duplicate Playlist insertion rejection without order changes and covers insertion at a non-terminal position under the unique playlist-position constraint.
- Focused verification passes: `PYTHONPATH=. python3 -m pytest server/tests/repositories/test_task2_steps_1_4.py -q` (6 passed); `python3 -m compileall -q server` (pass).
- The available execution environment could not clone the GitHub repository because outbound DNS/network access was unavailable, so the complete existing main-branch test suite was not independently executed here.


---


**Task 2 follow-up correction record (2026-09-26):**
- Rechecked the implemented repository interfaces against the Task 2 plan before final acceptance.
- Added RED-phase regression tests for `PlaylistRepository.remove_song()` and `PlaylistRepository.reorder_playlist()`, including removal without deleting the Song, order preservation after removal, exact-member validation, duplicate rejection, and atomic failure behavior.
- Implemented `remove_song()` with transactional position compaction and `reorder_playlist()` with exact-member validation and transactional position replacement.
- Fixed only Task 2-scoped Ruff findings in `database.py`, `library_repository.py`, and the Task 2 repository test import. The pre-existing Task 0 `server/tests/test_health.py` Ruff finding was intentionally left untouched to avoid unrelated changes.
- The implementation commits were pushed to `feature/task-2-sqlite-repositories`. The final Python test/lint rerun was not executed in this environment because outbound GitHub DNS/network access was unavailable; no unverified PASS claim is recorded here.
- Task 2 is not considered finally accepted until the branch is tested in the user's Docker-capable environment and the resulting test/lint/diff checks pass.


## Task 1R：MPD 播放传输契约补齐（Task 3/4/7 前置硬化）

Purpose: Task 1 established the MPD protocol and basic PlayerPort, but later authoritative Queue and Output Manager require MPD Queue transport, output enable/disable, statistics and update-state contracts. This hardening must be completed before Task 3 continuation.

Files:
- Modify: server/app/player/models.py
- Modify: server/app/player/ports.py
- Modify: server/app/player/mock_mpd.py
- Modify: server/app/player/mpd_adapter.py
- Modify: server/app/player/capabilities.py
- Modify: server/tests/player/*
- Modify: docs/mpd-0.23.5-capabilities.md

New models:
~~~python
class PlayerQueueEntry(BaseModel):
    mpd_song_id: int
    position: int
    song_uri: str

class MPDStats(BaseModel):
    songs: int | None = None
    albums: int | None = None
    artists: int | None = None
    db_playtime: int | None = None
    db_update: int | None = None
    playtime: int | None = None
    uptime: int | None = None

class DatabaseUpdateStatus(BaseModel):
    updating: bool | None = None
    job_id: int | None = None
~~~

Extend PlayerPort:
~~~python
async def queue_entries() -> list[PlayerQueueEntry]: ...
async def queue_clear() -> None: ...
async def queue_add(song_uri: str) -> int: ...
async def queue_delete(mpd_song_id: int) -> None: ...
async def queue_move(
    mpd_song_id: int,
    before_mpd_song_id: int | None,
) -> None: ...
async def queue_play(mpd_song_id: int) -> None: ...
async def set_output_enabled(output_id: int, enabled: bool) -> None: ...
async def stats() -> MPDStats: ...
async def database_update_status() -> DatabaseUpdateStatus: ...
~~~

- [x] Step 1: RED tests for the new domain models and PlayerPort contract.
- [ ] Step 2: Extend capability-probe tests for MPD Queue commands, output enable/disable commands, stats fields and update-status behavior.
- [ ] Step 3: Run a controlled real MPD 0.23.5 probe. Queue mutation tests must restore the original MPD queue/state. Output tests must prefer the disabled HTTPD output; never toggle the active USB DAC merely for probing. Unverified behavior remains unavailable.
- [ ] Step 4: Implement MockMPD Queue, output control, stats and update-status behavior.
- [ ] Step 5: Implement MPDAdapter support using only verified commands.
- [ ] Step 6: Extend MPDCapabilities/VerifiedPlayerPort so every new operation is capability-gated.
- [ ] Step 7: Extend fake-TCP integration coverage for all new operations and failures.
- [ ] Step 8: Run focused tests, compile/lint, inspect diff and verify no unrelated modules changed.
- [ ] Step 9: Commit: feat: complete mpd transport contract.

Boundary:
- No Queue Manager, Playback Service, Output Manager, API or Web behavior is implemented here.
- PlayerQueueEntry.mpd_song_id is an external MPD identifier and never becomes server queue_item_id.
- Command-list presence alone is not enough to claim runtime behavior support.



## Task 2R：Library Reconciliation Persistence 前置硬化

Purpose: Task 2 established SQLite and repository transactions, but Task 3 needs durable file availability, reconciliation and safe move detection without deleting Song rows referenced by Playlist/Favorites/History.

Files:
- Modify: server/app/models/library.py
- Modify: server/app/repositories/migrations.py
- Modify: server/app/repositories/library_repository.py
- Create: server/tests/repositories/test_library_reconciliation.py

Schema:
- Increase schema version from 1 to 2.
- Test both fresh v2 creation and v1 → v2 migration.
- Migration is transactional and preserves existing Song, Playlist, Favorites and History data.

Songs additions:
~~~text
file_size
file_mtime_ns
content_hash
availability_status
last_seen_at
~~~

availability_status values:
~~~text
AVAILABLE
MISSING
UNREADABLE
~~~

metadata_status remains separate and describes metadata parsing, for example OK or PARSE_FAILED.

Artwork reference table:
~~~text
album_art_refs
    artwork_id
    album_id
    song_id
    source = EMBEDDED
    picture_index
    mime_type
    width
    height
    content_sha256
~~~

Store one preferred artwork reference per album. Do not store image bytes in SQLite. The API later reads the referenced embedded picture directly from the read-only source media file.

Repository contracts:
~~~python
async def list_songs_in_root(root_uri_prefix: str) -> list[Song]: ...
async def find_song_candidates_by_identity(
    identity_key: str,
) -> list[Song]: ...
async def find_song_candidates_by_content_hash(
    content_hash: str,
) -> list[Song]: ...
async def apply_scan_batch(batch: ScanBatch) -> ScanResult: ...
~~~

apply_scan_batch() is the atomic persistence boundary for one successful reconciliation. It may insert new Songs, update known Songs, preserve Song ID for an unambiguous move, mark observed files AVAILABLE, mark safely reconciled-but-not-observed files MISSING, mark explicitly unreadable files UNREADABLE, update entity relations and artwork references.

It must never physically delete a Song row during normal library reconciliation.

Move matching order:
1. Exact file_uri match.
2. Unique strong identity_key match.
3. Unique content_hash match among eligible MISSING candidates.
4. Ambiguous candidates are never auto-matched.
5. Otherwise create a new Song.

- [ ] Step 1: RED tests for schema migration, availability status, file signature fields, artwork reference persistence, candidate lookup and atomic scan-batch semantics.
- [ ] Step 2: Implement schema v2 migration.
- [ ] Step 3: Implement Repository methods and atomic scan-batch persistence.
- [ ] Step 4: Verify old Playlist/Favorites/History references survive a Song becoming MISSING or UNREADABLE.
- [ ] Step 5: Run repository-focused tests, compile/lint and inspect diff.
- [ ] Step 6: Commit: feat: add library reconciliation persistence.

Boundary:
- No filesystem watcher, scheduler, metadata parser, API, WebSocket or MPD update trigger is implemented here.
- content_hash is not unique.
- identity_key remains a logical identity key and is not replaced by content_hash.



## Task 3：媒体元数据、歌词、曲库扫描与监听

Dependencies:
- Task 1R completed.
- Task 2R completed.
- Existing Task 3 RED tests may be refined only to match the frozen contracts below.

Files:
- Create: server/app/services/media_metadata.py
- Create: server/app/services/library_scanner.py
- Create: server/app/services/library_watch.py
- Create: server/app/services/library_scheduler.py
- Create: server/app/services/events.py
- Create: server/tests/services/test_media_metadata.py
- Create: server/tests/services/test_library_scanner.py
- Create: server/tests/services/test_library_watch.py
- Create: server/tests/services/test_library_scheduler.py

Interfaces:
~~~python
def parse_media_file(path: Path) -> ParsedSongMetadata: ...

class LibraryScanner:
    async def scan_full(self, root: Path) -> ScanResult: ...
    async def scan_paths(self, paths: list[Path]) -> ScanResult: ...
~~~

ParsedSongMetadata contains at least:
~~~text
title
artists
album
album_artists
track_number
disc_number
year
date
genres
duration
codec
bit_depth
sample_rate_hz
channel_count
lyrics
lyrics_format
lyrics_source
lyrics_status
artwork
metadata_status
~~~

lyrics_format = lrc | text | null
lyrics_source = sidecar | embedded | null
lyrics_status = available | missing | read_error

Media dependency:
- Add mutagen with an explicit compatible version range.
- FLAC and MP3 are the required v0.1 tested formats.
- The parser is pure media/filesystem logic and does not access SQLite, MPD, API, WebSocket or global configuration.

Metadata rules:
- Unknown values remain null or empty collections.
- No synthetic metadata.
- Technical audio fields describe the file, not the DAC/output chain.
- Multi-value artist/genre fields remain multi-value data.
- Date and year are retained separately when both are available.
- Parse failures raise a typed metadata exception and never fabricate a Song.

Lyrics rules:
- A valid sidecar .lrc has priority over embedded lyrics.
- LRC text is stored with its timestamp syntax preserved.
- Plain embedded lyrics remain plain text and never receive synthetic timestamps.
- If sidecar LRC exists but cannot be read/parsed, embedded lyrics may be used as fallback while the sidecar failure remains observable.
- Missing lyrics and lyric read failure are distinct states.

Artwork rules:
- Embedded artwork is represented by a reference candidate, not copied into the music directory.
- The reference records source song and picture index plus basic MIME/dimension/hash metadata.
- No artwork file is generated in the music library.

Strict read-only rules:
- Only read/stat operations are allowed on the music root.
- No rename, delete, tag update, file generation, sidecar generation or artwork extraction into the music directory.
- Scanner writes only to SQLite and injected non-filesystem abstractions.

Full-scan semantics:
- scan_full first performs a successful root traversal. Only after complete successful traversal may it mark previously reconciled files no longer observed as MISSING.
- Permission failure for a directory means that subtree was not safely reconciled; existing Songs in that subtree remain unchanged.
- scan_paths never marks unrelated files missing.
- Unsupported files are ignored and do not affect reconciliation.
- Changed audio is reparsed; sidecar LRC changes are independently detected.
- Move matching follows Task 2R rules.
- Failed parsing never overwrites known-good metadata with null.
- One successful reconciliation uses one atomic Repository transaction.

Domain event contract:
Create LibraryChangedEvent and a minimal EventPublisher Protocol in services/events.py. Task 6 will subscribe later; Task 3 does not implement WebSocket.

~~~python
class EventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None: ...
~~~

Publish strictly after successful DB commit.

Optional MPD update:
- Inject an MPDDatabaseUpdater Protocol rather than importing MPDAdapter.
- If enabled and verified, trigger MPD database update after DB success.
- MPD update failure never rolls back a successful SQLite scan.
- Report update failure explicitly in ScanResult/event state.

Current Step status:
- [x] Step 1: Media fixtures established.
- [x] Step 2: Metadata RED coverage established.
- [x] Step 3: Lyrics RED coverage established.
- [ ] Step 4: Complete persistence-safety coverage after Task 2R contract exists.
- [x] Step 5: File lifecycle RED coverage established.

- [ ] Step 6: Implement ParsedSongMetadata and parse_media_file() using read-only access and tested FLAC/MP3 parsing.
- [ ] Step 7: Implement LibraryScanner with injected Repository, content hashing, move matching, atomic reconciliation and typed failure handling.
- [ ] Step 8: Implement filesystem event debounce/batch with an injected callback to scan_paths(). Default debounce is 500 ms.
- [ ] Step 9: Implement scheduler with an injected interval; default is 12 hours. It must not import Task 10 configuration.
- [ ] Step 10: Implement post-commit LibraryChangedEvent publication and optional MPD database update through injected protocols.
- [ ] Step 11: Run complete Task 3 tests, relevant repository tests, global Python tests, compile/lint and diff review.
- [ ] Step 12: Commit: feat: add library scanner and metadata pipeline.

Acceptance:
- Music directory remains strictly read-only.
- Unknown values stay unknown.
- Failed parsing cannot erase known-good metadata.
- Song ID is preserved only for an unambiguous move match.
- Missing/unreadable Songs remain as rows for Playlist/Favorites/History continuity.
- Events occur only after DB success.
- No WebSocket implementation and no Task 10 configuration dependency.



## Task 4：Queue、Playback Context、History、AutoPlay、Playback Service

Dependencies:
- Task 1R and Task 2R completed.
- Task 3 completed, including available-library queries and the DomainEvent contract.
- Task 5, Task 6, Task 7, Task 8, Task 9, Task 10, Task 11, Task 12 are not dependencies.

Files:
- Create: server/app/models/queue.py
- Create: server/app/repositories/queue_repository.py
- Create: server/app/repositories/playback_state_repository.py
- Create: server/app/services/queue_manager.py
- Create: server/app/services/history_service.py
- Create: server/app/services/autoplay.py
- Create: server/app/services/playback_service.py
- Create: server/tests/services/test_queue_manager.py
- Create: server/tests/services/test_history_service.py
- Create: server/tests/services/test_autoplay.py
- Create: server/tests/services/test_playback_service.py

Core models:
~~~python
class PlaybackContext(BaseModel):
    context_id: str
    source_type: str
    source_id: str | None = None
    ordered_song_ids: tuple[str, ...]
    random_seed: int | None = None

class QueueItem(BaseModel):
    queue_item_id: str
    song_id: str
    position: int
    source: Literal["MANUAL", "AUTOPLAY"]
    playback_context_id: str | None = None
~~~

MPD Queue mapping:
- Server queue_item_id and MPD mpd_song_id are separate identifiers.
- Server Queue is authoritative business state.
- Queue mutation is persisted through QueueRepository, then synchronized to MPD through PlayerPort Queue methods.
- MPD unavailability does not erase or silently replace the server Queue; synchronization state is explicit and can be reconciled later.
- Playback state advances only after MPD command success and status reconciliation.

- [ ] Step 1: RED tests for Start Track replacing pending Up Next and creating PlaybackContext.
- [ ] Step 2: RED tests for Queue Play Now preserving prior pending items after the selected song.
- [ ] Step 3: RED tests for Play Next and Add to Queue insertion order.
- [ ] Step 4: RED tests for reorder/delete/clear/save-as-playlist and current-song deletion.
- [ ] Step 5: RED tests for Played view versus persistent History.
- [ ] Step 6: RED tests for natural completion, skip, stop and switch-away reasons.
- [ ] Step 7: Implement AutoPlay low-watermark 5/refill 5 using Task 3 available Songs while respecting PlaybackContext.
- [ ] Step 8: Prevent AutoPlay from overwriting MANUAL items and mark every generated item source.
- [ ] Step 9: Test empty library, one-song library, insufficient candidates and concurrent Queue mutation.
- [ ] Step 10: Serialize Queue mutations using Repository transaction boundaries plus Queue revision/CAS.
- [ ] Step 11: Test Pause keeps AutoPlay, Stop disables it, and Queue exhaustion is not terminal.
- [ ] Step 12: Implement Playback Service as the sole orchestration layer between Queue/History/AutoPlay and PlayerPort.
- [ ] Step 13: Test MPD failures do not falsely advance current-track service state and reconcile external status.
- [ ] Step 14: Verify Queue/Playback persistence, MPD synchronization, compile/lint and diff.
- [ ] Step 15: Commit: feat: implement authoritative playback model.



## Task 5：Collection、Library/Playlist Service 与 REST API

Dependencies:
- Task 3 completed.
- Task 4 completed.
- Task 6, Task 7, Task 8, Task 9, Task 10, Task 11 and Task 12 are not dependencies.

Files:
- Create: server/app/services/library_service.py
- Create: server/app/services/playlist_service.py
- Create: server/app/services/collection_service.py
- Create: server/app/api/schemas.py
- Create: server/app/api/library.py
- Create: server/app/api/playback.py
- Create: server/app/api/playlists.py
- Create: server/app/api/history.py
- Create: server/tests/api/*
- Create: server/tests/services/test_library_service.py
- Create: server/tests/services/test_playlist_service.py
- Create: server/tests/services/test_collection_service.py

Service boundary:
- LibraryService uses LibraryRepository and Scanner data contracts.
- PlaylistService uses PlaylistRepository and Favorites persistence.
- CollectionService composes Library/Playlist services and PlaybackContext data.
- API validates requests, calls Services, maps errors and returns response models.
- No API handler imports SQLite or a concrete MPD adapter.

API scope:
- Song/album/artist/tag/year/search/collection read endpoints.
- Manual library scan endpoint.
- Album artwork read endpoint using the persisted artwork reference and the read-only source file.
- Playback actions and controls.
- Playlist CRUD/reorder/Favorites/Queue save.

Authentication:
- v0.1 intentionally has no application authentication, sessions or auth middleware.

Idempotency:
- Mutating API operations that may be retried carry a request ID.
- Idempotency storage and lookup are implemented within this Task; no later Task is required.

- [ ] Step 1: RED tests for every Collection source.
- [ ] Step 2: RED tests for default ordering and fixed random order within PlaybackContext.
- [ ] Step 3: RED tests for explicit empty-collection behavior.
- [ ] Step 4: RED tests for Service/Repository boundaries.
- [ ] Step 5: Implement LibraryService, PlaylistService and CollectionService.
- [ ] Step 6: Implement REST schemas and endpoints.
- [ ] Step 7: Implement request-ID/idempotency handling.
- [ ] Step 8: Test validation, error mapping, artwork read failures and stable response schemas.
- [ ] Step 9: Run full API/service tests and diff review.
- [ ] Step 10: Commit: feat: expose library and playback api.



## Task 6：WebSocket 与完整状态恢复

Dependencies:
- Task 3 completed and provides DomainEvent contract.
- Task 4 completed.
- Task 5 completed.
- Task 7 completed.
- Task 6 implements realtime transport only and does not redefine domain business rules.

Files:
- Create: server/app/services/state_service.py
- Create: server/app/api/realtime.py
- Create: server/tests/api/test_realtime.py

Interfaces:
~~~python
async def get_full_snapshot() -> FullStateSnapshot: ...
async def publish(event: DomainEvent) -> None: ...
~~~

Rules:
- StateService aggregates authoritative Service states, not raw SQLite rows.
- Initial WebSocket connection receives a complete snapshot.
- Events are delivered only after the underlying successful state mutation.
- Disconnected clients cannot fail or roll back mutations.
- Reconnect always obtains a complete snapshot; missed incremental events are not the consistency mechanism.
- Snapshot includes Playback, Queue, History availability, Output and necessary Library/Playlist revisions.
- WebSocket code never accesses MPD directly.

- [ ] Step 1: Define and test FullStateSnapshot.
- [ ] Step 2: Test post-commit event semantics for Library/Playlist/Playback/Output mutations.
- [ ] Step 3: Implement WebSocket connection manager and initial snapshot.
- [ ] Step 4: Test disconnected clients.
- [ ] Step 5: Test reconnect/full snapshot restoration.
- [ ] Step 6: Run realtime tests and diff review.
- [ ] Step 7: Commit: feat: add realtime state synchronization.



## Task 7：Output Manager 与 MPD About

Dependencies:
- Task 1R completed.
- Task 4 completed.
- Task 5 and Task 6 are not dependencies.

Files:
- Create: server/app/services/output_manager.py
- Create: server/app/services/mpd_info_service.py
- Create: server/app/api/system.py
- Create: server/tests/services/test_output_manager.py
- Create: server/tests/services/test_mpd_info_service.py

Rules:
- Identify NAS_DAC by verified MPD output characteristics, never a fixed MPD output ID. When multiple ALSA outputs exist, use an injected selector; do not guess.
- CLIENT_STREAM is reserved and unavailable in v0.1.
- Output Manager uses PlayerPort only.
- NAS_DAC states: UNAVAILABLE, INACTIVE, PREPARING, ACTIVE, SWITCH_FAILED.
- Failed switch preserves the previous usable output.
- Output state is reconciled from MPD before publishing final service state.
- Switching output preserves current Song, Queue, PlaybackContext and best-effort position.
- About values come from verified capability/stat contracts. Unsupported/unavailable values stay null and are never fabricated as zero.

- [ ] Step 1: RED tests for NAS_DAC states.
- [ ] Step 2: RED tests for CLIENT_STREAM reserved/unavailable behavior.
- [ ] Step 3: RED tests for failed switch preserving the old usable output.
- [ ] Step 4: RED tests for preserving playback context, Queue and position.
- [ ] Step 5: Implement capability-gated output management.
- [ ] Step 6: Implement MPD About using MPDCapabilities version and runtime stats/status.
- [ ] Step 7: Test unknown-field behavior.
- [ ] Step 8: Run focused tests, compile/lint and diff review.
- [ ] Step 9: Commit: feat: add output manager and mpd info api.



## Task 8：Web/PWA 状态层与播放器

Dependencies:
- Task 5 completed.
- Task 6 completed.
- Task 7 completed.

Rules:
- Web uses REST/WebSocket contracts only.
- No direct MPD access.
- No local Queue or AutoPlay authority.
- Album artwork comes only from the Task 5 artwork API.
- Lyrics come only from server/API state and retain LRC timestamps.
- Same-origin URL construction is mandatory.

Files:
- Create: web/src/services/api.ts
- Create: web/src/services/realtime.ts
- Create: web/src/types/api.ts
- Create: web/src/stores/player.ts
- Create: web/src/stores/library.ts
- Create: web/src/stores/playlists.ts
- Create: web/src/views/PlayerView.vue
- Create: web/src/components/player/*
- Create: web/src/components/layout/*
- Create: web/src/styles/*
- Create: web/src/router/index.ts

- [ ] Step 1: Test same-origin HTTP/HTTPS/ws/wss URL construction.
- [ ] Step 2: Test reconnect triggers full snapshot refresh.
- [ ] Step 3: Implement typed REST/WebSocket clients.
- [ ] Step 4: Implement authoritative server-state stores.
- [ ] Step 5: Build the confirmed dark glassmorphism player UI with reduced-motion fallback.
- [ ] Step 6: Implement album art and player metadata display.
- [ ] Step 7: Implement playback controls and progress/seek.
- [ ] Step 8: Implement album-art ↔ lyrics toggle and timestamp-synchronized LRC scrolling.
- [ ] Step 9: Test UI state transitions and seek behavior.
- [ ] Step 10: Run typecheck/component tests/build and diff review.
- [ ] Step 11: Commit: feat: add web player and state layer.



## Task 9：Web Queue、Library、Playlist、Search、Favorites、Settings

Dependencies:
- Task 5 completed.
- Task 6 completed.
- Task 8 completed.

Files:
- Create: web/src/views/QueueView.vue
- Create: web/src/views/LibraryView.vue
- Create: web/src/views/PlaylistView.vue
- Create: web/src/views/SearchView.vue
- Create: web/src/views/SettingsView.vue
- Create: web/src/components/queue/*
- Create: web/src/components/library/*
- Create: web/src/components/settings/*

- [ ] Step 1: Test Queue Now Playing / Played / Up Next and MANUAL/AUTOPLAY markers.
- [ ] Step 2: Test drag reorder, Play Next, delete, clear and Save as Playlist.
- [ ] Step 3: Implement history collapsed by default and progressive expansion.
- [ ] Step 4: Reset Queue-history expansion state according to playback context rules.
- [ ] Step 5: Test every SongRow has the same Playback Action menu.
- [ ] Step 6: Implement FavoriteStar independently from SongRow playback action.
- [ ] Step 7: Implement Library collection pages with Play All and Shuffle All.
- [ ] Step 8: Implement Playlist CRUD/reorder and duplicate rejection.
- [ ] Step 9: Implement Favorites and synchronized star state.
- [ ] Step 10: Implement search by title, artist, album, album artist, genre and year.
- [ ] Step 11: Implement Settings → About using MPD info API.
- [ ] Step 12: Implement responsive bottom navigation and Player as default view.
- [ ] Step 13: Run typecheck, component tests and production build.
- [ ] Step 14: Commit: feat: add library queue playlists search and settings.



## Task 10：配置、备份、日志、健康检查

Dependencies:
- Task 3, Task 4, Task 5, Task 6 and Task 7 are complete.
- Task 10 is the first Task allowed to import the final configuration module.
- Earlier Tasks remain usable without importing config.py.

Files:
- Create: server/app/config.py
- Create: server/app/services/backup_service.py
- Create: server/app/api/backup.py
- Create: server/app/logging_config.py
- Create: server/tests/test_config.py
- Create: server/tests/services/test_backup_service.py
- Create: server/tests/test_health.py
- Modify: server/app/main.py
- Modify: deploy/docker-compose.yml
- Modify: deploy/.env.example

Config:
- Full-reconciliation interval default = 12 hours.
- Watcher debounce default = 500 ms.
- MPD host/port/password, music root mapping, SQLite path, backup path and web settings live here.
- No authentication settings exist in v0.1.

Database coordination:
- Introduce an application-level write gate around backup/restore so restore cannot race repository writes.

Backup:
- Daily, retain 7 copies.
- Backup SQLite and service configuration.
- Never back up music files.

Health:
- Preserve /api/health compatibility with {"status":"ok"} while allowing subsystem fields.
- Report FastAPI, SQLite and MPD states independently.
- MPD UNAVAILABLE does not prevent service startup.

Logging:
- Categories: API, WebSocket, Library Scan, Playback, MPD Adapter, Output, Database, Backup.
- Configure Docker log rotation.

- [ ] Step 1: RED tests for configuration defaults, validation and file/env precedence.
- [ ] Step 2: Test MPD password never enters API responses/logs.
- [ ] Step 3: Test backup integrity/schema validation and seven-copy retention.
- [ ] Step 4: Test restore rejection for corrupt/incompatible backup and write isolation.
- [ ] Step 5: Implement config loading and composition-root injection.
- [ ] Step 6: Implement daily/manual backup/restore.
- [ ] Step 7: Test health independently reports FastAPI/SQLite/MPD.
- [ ] Step 8: Implement logging configuration and Docker rotation.
- [ ] Step 9: Run config/backup/health tests and diff review.
- [ ] Step 10: Commit: feat: add config backup health and logging.



## Task 11：NAS update.sh 与生产部署

Dependencies:
- Task 10 completed.
- No source code is edited directly on NAS.

Files:
- Create: deploy/update.sh
- Create: deploy/README.md
- Create: server/tests/test_update_script.py

- [ ] Step 1: RED tests for dirty-worktree, fetch/pull, build, Compose and healthcheck guards.
- [ ] Step 2: Implement strict shell mode and explicit main-branch verification.
- [ ] Step 3: Implement fetch → fast-forward pull → Docker build → compose up → healthcheck.
- [ ] Step 4: Never use destructive reset/checkout to overwrite NAS-local changes.
- [ ] Step 5: Document stable-tag rollback.
- [ ] Step 6: Run ShellCheck and disposable Git repository tests.
- [ ] Step 7: Run deployment tests and diff review.
- [ ] Step 8: Commit: feat: add safe nas deployment updater.



## Task 12：真实 NAS/MPD 验收与 v0.1.0

Dependencies:
- Tasks 0–11 completed and accepted.

Files:
- Create: docs/acceptance/nas-mpd-0.23.5.md
- Create: docs/acceptance/web-reverse-proxy.md
- Modify: README.md
- Modify: docs/CHANGELOG.md

- [ ] Step 1: Verify container → NAS LAN IP → MPD 0.23.5.
- [ ] Step 2: Verify play/pause/stop/previous/next/seek/repeat/random/volume.
- [ ] Step 3: Verify USB DAC output and output state.
- [ ] Step 4: Verify library scan, strict read-only behavior, move/rename identity preservation, missing/unreadable handling, event debounce and 12-hour reconciliation.
- [ ] Step 5: Verify WebSocket reconnect and complete state restoration.
- [ ] Step 6: Verify NAS reboot/container rebuild preserves SQLite/config/backup.
- [ ] Step 7: Verify Synology reverse proxy HTTPS/WSS.
- [ ] Step 8: Run complete local suite:
~~~text
make test
make lint
make typecheck
make build
~~~
- [ ] Step 9: Deploy with update.sh and complete real-device acceptance.
- [ ] Step 10: Fix all discovered discrepancies through tests before release.
- [ ] Step 11: Create annotated Git tag v0.1.0 only after verification.
- [ ] Step 12: Verify controlled rollback to previous stable commit/tag.



## Spec Coverage Self-Review

- Chapter 1 Playback/Queue/AutoPlay/History/Context → Task 4, Task 5, Task 6, Task 8, Task 9.
- Chapter 2-1 Song/Album/Artist/Genre/Year/Lyrics/Audio metadata/Collection/Playlist/Favorites/Search/Scan → Task 2R, Task 3, Task 5, Task 8, Task 9.
- Chapter 3 Music Server authority/MPD Adapter/USB DAC/CLIENT_STREAM/Output/About/status/error → Task 1/1R, Task 4, Task 6, Task 7, Task 12.
- Chapter 4 Vue/FastAPI/SQLite/Docker/dev-prod/same-origin/WSS/Mock MPD/read-only music/12h scan/backup/GitHub/NAS update/test/health/logging → Tasks 0, 1, 1R, 2, 2R, 3, 6, 8, 10, 11, 12.
- Authentication is explicitly outside v0.1 scope.
- The real music directory is strictly read-only in every Task.
- Album artwork uses persisted embedded-reference + on-demand-read semantics.
- Valid sidecar LRC has explicit precedence and failure-fallback semantics.

## Type/Interface Review

- PlayerPort is the only playback-engine dependency.
- Queue/Output/Stats transport contracts exist before later Services consume them.
- Repositories return domain models, not SQLite rows.
- Library reconciliation uses one transactional Repository boundary.
- Services own business rules.
- API schemas are separate from domain models and never access SQLite or MPD.
- Domain event contract exists before WebSocket.
- Web consumes API/WebSocket state, never MPD state.
- Mock MPD and real MPD implement the same PlayerPort.
- Queue identifiers and MPD identifiers are separate.
- FullStateSnapshot is the reconnect authority.
- Final configuration is injected at the composition root and is not a dependency of early Tasks.
- Song move matching never relies on an ambiguous content hash.
- Song rows are preserved for missing/unreadable files so Playlist/Favorites/History remain valid.

## Pre-Task Acceptance Gate

Before starting any Task:
1. Confirm every listed dependency is complete and its commit is reachable.
2. Confirm every imported contract exists on the current branch.
3. Confirm required schema version/features exist.
4. Confirm RED tests cover newly introduced behavior.
5. Confirm the Task does not import a later Task.
6. Confirm intended files are within the Task's allowed file list.
7. Run the smallest relevant existing regression suite before modifications.

After each Step:
1. Run focused verification.
2. Record RED/GREEN outcome when the Step is TDD implementation.
3. Inspect git diff --check and changed-file list.
4. Do not proceed if a dependency or boundary is violated.

Before Task completion:
1. Run Task-focused tests.
2. Run relevant prior-Task regression tests.
3. Run applicable global tests/lint/typecheck/build.
4. Review diff for unrelated changes.
5. Verify branch name.
6. Verify the commit exists on the remote ref after the write.
7. Only then check the Task in the plan.

## Five Highest-Risk Tests

1. MPD 0.23.5 Queue/Output behavior mismatch → Task 1R.
2. Move/rename identity preservation and ambiguous matching → Task 2R/3.
3. Queue mutation during AutoPlay refill → Task 4.
4. WebSocket reconnect during active playback → Task 6.
5. MPD unavailable at startup and independent subsystem health → Task 10.

## Dependency Matrix

| Task | Required completed dependencies |
|---|---|
| Task 0 | none |
| Task 1 | Task 0 |
| Task 2 | Task 0 |
| Task 1R | Task 1 |
| Task 2R | Task 2 |
| Task 3 | Task 1R + Task 2R |
| Task 4 | Task 1R + Task 2R + Task 3 |
| Task 5 | Task 3 + Task 4 |
| Task 7 | Task 1R + Task 4 |
| Task 6 | Task 3 + Task 4 + Task 5 + Task 7 |
| Task 8 | Task 5 + Task 6 + Task 7 |
| Task 9 | Task 5 + Task 6 + Task 8 |
| Task 10 | Task 3 + Task 4 + Task 5 + Task 6 + Task 7 |
| Task 11 | Task 10 |
| Task 12 | Tasks 0–11 |

Task numbers are historical identifiers. Execution order is defined by the dependency matrix, not numeric order.

## Execution Order

~~~text
0
→ 1
→ 2
→ 1R
→ 2R
→ 3
→ 4
→ 5
→ 7
→ 6
→ 8
→ 9
→ 10
→ 11
→ 12
~~~

Why Task 7 precedes Task 6:
- FullStateSnapshot contains Output state, so Output Manager must exist before the final realtime snapshot is assembled.
- Task 6 consumes the Output Service contract; it does not create it.

Why Task 10 is late:
- Earlier Tasks use constructor injection and explicit defaults.
- Only Task 10 introduces final configuration and composition-root wiring.

Why Task 1R and Task 2R exist:
- They are prerequisite hardening layers discovered after Tasks 1 and 2 were already completed.
- They do not invalidate historical completion; they make the already-completed lower layers sufficient for later contracts.

Every Task remains independently tested and independently committed. Failures use systematic debugging. Major Task completion uses verification-before-completion and code review. No Task may be checked until its dependency and diff gates pass.


**Task 2 verification record (2026-09-26, Steps 5-9):**
- Step 5 RED coverage verifies Favorites persistence across repository instances and independent removal without changing the Song or Playlist membership. The Favorites table remains separate from playlist_items, so Queue/Playlist changes cannot implicitly clear Favorites.
- Step 6 RED coverage verifies History stores song ID, start/end timestamps, reason and session ID independently of Queue; recording a HistoryEvent does not create Queue entries.
- Step 7 adds per-database serialization for critical async transactions, scoped to each running event loop to avoid cross-event-loop asyncio.Lock reuse. Existing transaction commit/rollback semantics remain unchanged.
- Step 8 focused verification passes: `PYTHONPATH=. python3 -m pytest server/tests/repositories/test_task2_steps_1_4.py server/tests/repositories/test_task2_steps_5_7.py -q` (9 passed) and `python3 -m compileall -q server`. Ruff was not executable in the available verification environment because the Ruff module was not installed; no Ruff PASS is claimed for this turn.
- Step 9 final branch state is committed with message `feat: add sqlite library playlist and history repositories`; the branch ref and commit history were re-checked after the write. No merge into `main` was performed.
