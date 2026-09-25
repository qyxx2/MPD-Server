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

- [ ] Step 1: Write health endpoint test.
~~~python
from fastapi.testclient import TestClient
from server.app.main import app

def test_health():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
~~~
- [ ] Step 2: Run pytest and verify it fails.
- [ ] Step 3: Add the minimal FastAPI app and health endpoint.
- [ ] Step 4: Run pytest and verify PASS.
- [ ] Step 5: Add the Vue/Vite shell, including the required `web/index.html` entry point, and verify `npm run build`.
- [ ] Step 6: Add Makefile targets and separate dev/prod Compose.
- [ ] Step 7: Validate both Compose files with `docker compose config` in a Docker-capable environment (for example, the Synology Docker environment). This validates Compose configuration only; real MPD/USB DAC testing starts at Task 1 Step 7 and Task 12.
- [ ] Step 8: Commit: chore: establish music server monorepo.

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

- [ ] Step 1: Test PlayerPort/domain models.
- [ ] Step 2: Implement deterministic Mock MPD with disconnect/fail-next injection.
- [ ] Step 3: Test Mock play/pause/stop/next/previous/seek/status/events.
- [ ] Step 4: Implement line-oriented MPD protocol parsing, including escaped values and ACK errors.
- [ ] Step 5: Implement MPDAdapter with connection/command timeouts and typed PlayerUnavailable/PlayerCommandError.
- [ ] Step 6: Test Adapter through a fake TCP server.
- [ ] Step 7: Run capability probe against actual NAS MPD 0.23.5 and record commands, outputs, status fields, update behavior and errors.
- [ ] Step 8: Restrict service features to verified capabilities.
- [ ] Step 9: Commit: feat: add mpd adapter and verified capabilities.

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

- [ ] Step 1: Test fresh database, schema version, foreign keys, transaction boundaries and integrity.
- [ ] Step 2: Define songs/albums/artists/genres/tags/playlists/playlist_items/favorites/history/queue/playback-state tables and indexes.
- [ ] Step 3: Test stable Song ID reuse, path move/rename matching, metadata update and multi-artist relations.
- [ ] Step 4: Test duplicate Playlist insertion is rejected without order changes.
- [ ] Step 5: Test Favorites persistence and independent removal.
- [ ] Step 6: Test History records start/end/reason/session independently of Queue.
- [ ] Step 7: Implement repositories with serialized critical writes.
- [ ] Step 8: Verify tests.
- [ ] Step 9: Commit: feat: add sqlite library playlist and history repositories.

---

## Task 3：媒体元数据、歌词、曲库扫描与监听

**Files**
- Create: server/app/services/media_metadata.py
- Create: server/app/services/library_scanner.py
- Create: server/app/services/library_watch.py
- Create: server/app/services/library_scheduler.py
- Create: server/tests/services/test_media_metadata.py
- Create: server/tests/services/test_library_scanner.py
- Create: server/tests/services/test_library_watch.py

**Interfaces**
~~~python
def parse_media_file(path: Path) -> ParsedSongMetadata: ...
async def scan_full(root: Path) -> ScanResult: ...
async def scan_paths(paths: list[Path]) -> ScanResult: ...
~~~

- [ ] Step 1: Add media fixtures for embedded lyrics, LRC, FLAC/MP3 metadata and technical audio properties.
- [ ] Step 2: Test title/artist/album/album artist/track/disc/year/genre/duration/codec/bit depth/sample rate/channels.
- [ ] Step 3: Test embedded lyrics vs sidecar LRC, ordinary lyrics, missing lyrics and parse failure.
- [ ] Step 4: Ensure unknown values stay null and failed scans do not erase known-good metadata.
- [ ] Step 5: Test new/changed/moved/deleted/unreadable files.
- [ ] Step 6: Implement scanner using read-only filesystem access and repository transactions.
- [ ] Step 7: Implement filesystem event debounce/batch.
- [ ] Step 8: Implement configurable full reconciliation with default 12 hours and manual scan.
- [ ] Step 9: Emit library-change domain event only after DB success; optionally trigger MPD database update.
- [ ] Step 10: Commit: feat: add library scanner and metadata pipeline.

---

## Task 4：Queue、Playback Context、History、AutoPlay、Playback Service

**Files**
- Create: server/app/models/queue.py
- Create: server/app/services/queue_manager.py
- Create: server/app/services/history_service.py
- Create: server/app/services/autoplay.py
- Create: server/app/services/playback_service.py
- Create: server/tests/services/test_queue_manager.py
- Create: server/tests/services/test_history_service.py
- Create: server/tests/services/test_autoplay.py
- Create: server/tests/services/test_playback_service.py

**Interfaces**
~~~python
async def start_track(song_id: str, context: PlaybackContext) -> QueueSnapshot: ...
async def play_now(song_id: str) -> QueueSnapshot: ...
async def play_next(song_id: str) -> QueueSnapshot: ...
async def add_to_queue(song_id: str) -> QueueSnapshot: ...
async def reorder_queue(item_id: str, before_item_id: str | None) -> QueueSnapshot: ...
async def remove_queue_item(item_id: str) -> QueueSnapshot: ...
async def clear_up_next() -> QueueSnapshot: ...
async def save_queue_as_playlist(name: str) -> Playlist: ...

async def play(song_id: str, context: PlaybackContext | None = None) -> PlaybackSnapshot: ...
async def pause() -> PlaybackSnapshot: ...
async def stop() -> PlaybackSnapshot: ...
async def next() -> PlaybackSnapshot: ...
async def previous() -> PlaybackSnapshot: ...
async def seek(seconds: float) -> PlaybackSnapshot: ...
~~~

- [ ] Step 1: Test Start Track replacing pending Queue and creating Playback Context.
- [ ] Step 2: Test Queue Play Now preserving existing pending items after the selected song.
- [ ] Step 3: Test Play Next and Add to Queue exact insertion semantics.
- [ ] Step 4: Test reorder/delete/clear/save-as-playlist and current-song deletion.
- [ ] Step 5: Test Played view vs persistent History separation.
- [ ] Step 6: Test natural completion, skip, stop and switch-away reasons.
- [ ] Step 7: Fix first-wave AutoPlay defaults: low-watermark 5, refill 5, whole-library candidate source respecting Playback Context, exclude current/Up Next/recently-played when enough candidates exist, no duplicate within a batch.
- [ ] Step 8: Mark queue items source MANUAL or AUTOPLAY; AutoPlay never overwrites MANUAL items.
- [ ] Step 9: Test empty library, one-song library, insufficient candidates and concurrent user Queue mutation.
- [ ] Step 10: Serialize Queue mutations or use revision/CAS so refill cannot overwrite newer user changes.
- [ ] Step 11: Test Pause keeps AutoPlay, Stop disables it, and Queue exhaustion is not a terminal state.
- [ ] Step 12: Implement Playback Service as the sole orchestration layer between Queue/History/AutoPlay and PlayerPort.
- [ ] Step 13: Test MPD command failure does not falsely commit service state; reconcile external MPD state.
- [ ] Step 14: Commit: feat: implement authoritative playback model.

---

## Task 5：Collection、Playlist/Search/Library REST API

**Files**
- Create: server/app/services/collection_service.py
- Create: server/app/api/schemas.py
- Create: server/app/api/library.py
- Create: server/app/api/playback.py
- Create: server/app/api/playlists.py
- Create: server/app/api/history.py
- Create: server/tests/api/*
- Create: server/tests/services/test_collection_service.py

**Interfaces**
~~~python
async def get_collection(source: CollectionSource, filters: CollectionFilters, order: CollectionOrder) -> Collection: ...
async def play_collection(collection_id: str, mode: PlayMode) -> PlaybackSnapshot: ...
~~~

- [ ] Step 1: Test Album, Artist, Genre, Year, Folder, Search, Playlist, Favorites, whole-library and explicit-song collections.
- [ ] Step 2: Test default ordering and fixed random order within one Playback Context.
- [ ] Step 3: Test empty collection does not silently substitute random songs.
- [ ] Step 4: Expose song/album/artist/tag/search/collection endpoints.
- [ ] Step 5: Expose Play Now, Play Next, Add to Queue, collection play, pause, stop, next, previous and seek.
- [ ] Step 6: Expose Playlist CRUD/reorder/Favorites/Queue-save.
- [ ] Step 7: Add request IDs/idempotency for mutating playback requests that may be retried.
- [ ] Step 8: Test validation, error mapping and stable response schemas.
- [ ] Step 9: Commit: feat: expose library and playback api.

---

## Task 6：WebSocket 与完整状态恢复

**Files**
- Create: server/app/services/state_service.py
- Create: server/app/api/realtime.py
- Create: server/tests/api/test_realtime.py

**Interfaces**
~~~python
async def get_full_snapshot() -> FullStateSnapshot: ...
async def publish(event: DomainEvent) -> None: ...
~~~

- [ ] Step 1: Define FullStateSnapshot containing playback, Queue, History availability, Output and necessary Library/Playlist revisions.
- [ ] Step 2: Test every persisted domain mutation emits a logical event only after successful persistence.
- [ ] Step 3: Implement WebSocket connection manager and initial snapshot.
- [ ] Step 4: Test disconnected clients cannot break mutations.
- [ ] Step 5: Test reconnect always requests a complete snapshot rather than replaying missed events.
- [ ] Step 6: Commit: feat: add realtime state synchronization.

---

## Task 7：Output Manager 与 MPD About

**Files**
- Create: server/app/services/output_manager.py
- Create: server/app/services/mpd_info_service.py
- Create: server/app/api/system.py
- Create: server/tests/services/test_output_manager.py
- Create: server/tests/services/test_mpd_info_service.py

- [ ] Step 1: Test NAS_DAC states UNAVAILABLE/INACTIVE/PREPARING/ACTIVE/SWITCH_FAILED.
- [ ] Step 2: Keep CLIENT_STREAM reserved but unavailable until its real implementation exists.
- [ ] Step 3: Test failed output switch preserves old usable output.
- [ ] Step 4: Test output switch preserves current song, Queue, Playback Context and best-effort position.
- [ ] Step 5: Implement only capabilities verified by the MPD probe.
- [ ] Step 6: Expose MPD version, uptime, song/album/artist counts, total library duration, update state, cumulative playtime and connection state.
- [ ] Step 7: Test unsupported/unavailable fields remain unknown, never fabricated as zero.
- [ ] Step 8: Commit: feat: add output manager and mpd info api.

---

## Task 8：Web/PWA 状态层与播放器

**Files**
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
- [ ] Step 3: Implement typed REST and WebSocket clients.
- [ ] Step 4: Implement authoritative server-state stores; no local Queue/AutoPlay authority.
- [ ] Step 5: Build the confirmed dark glassmorphism player UI with reduced-motion fallback.
- [ ] Step 6: Implement album art, title/artist/album/total-song display and previous/next/play-pause/stop/play-mode controls.
- [ ] Step 7: Implement progress display and drag-to-seek.
- [ ] Step 8: Implement album-art ↔ lyrics toggle and timestamp-synchronized LRC scrolling.
- [ ] Step 9: Test player state transitions and seek behavior.
- [ ] Step 10: Commit: feat: add web player and state layer.

---

## Task 9：Web Queue、Library、Playlist、Search、Favorites、Settings

**Files**
- Create: web/src/views/QueueView.vue
- Create: web/src/views/LibraryView.vue
- Create: web/src/views/PlaylistView.vue
- Create: web/src/views/SearchView.vue
- Create: web/src/views/SettingsView.vue
- Create: web/src/components/queue/*
- Create: web/src/components/library/*
- Create: web/src/components/settings/*

- [ ] Step 1: Test Queue Now Playing / Played / Up Next and manual/autoplay source markers.
- [ ] Step 2: Test drag reorder, Play Next, delete, clear and Save as Playlist.
- [ ] Step 3: Implement history collapsed by default and progressive expansion by downward scroll/gesture.
- [ ] Step 4: Reset Queue-history expansion state when the current song returns to the Queue context as specified.
- [ ] Step 5: Test every SongRow has the same Playback Action menu.
- [ ] Step 6: Implement FavoriteStar independently from SongRow playback action.
- [ ] Step 7: Implement Library collection pages with Play All and Shuffle All.
- [ ] Step 8: Implement Playlist create/rename/delete/reorder and duplicate rejection.
- [ ] Step 9: Implement Favorites and synchronized star state.
- [ ] Step 10: Implement search by title, artist, album, album artist, genre and year.
- [ ] Step 11: Implement Settings → About using MPD info API.
- [ ] Step 12: Implement responsive bottom navigation and Player as default view.
- [ ] Step 13: Run typecheck, component tests and production build.
- [ ] Step 14: Commit: feat: add library queue playlists search and settings.

---

## Task 10：配置、备份、日志、健康检查

**Files**
- Create: server/app/config.py
- Create: server/app/services/backup_service.py
- Create: server/app/api/backup.py
- Create: server/app/logging_config.py
- Create: server/tests/test_config.py
- Create: server/tests/services/test_backup_service.py
- Create: server/tests/test_health.py
- Modify: server/app/main.py, deploy/docker-compose.yml, deploy/.env.example

- [ ] Step 1: Test config defaults, invalid values and environment/file precedence.
- [ ] Step 2: Ensure MPD password never appears in API responses/logs.
- [ ] Step 3: Test SQLite backup integrity/schema validation and seven-copy retention.
- [ ] Step 4: Test restore refuses corrupt/incompatible backups and isolates active writes.
- [ ] Step 5: Implement daily backup plus manual backup/restore.
- [ ] Step 6: Test health separately reports FastAPI, SQLite and MPD status.
- [ ] Step 7: Ensure MPD-unavailable startup remains recoverable.
- [ ] Step 8: Add log categories API/WebSocket/Library Scan/Playback/MPD Adapter/Output/Database/Backup and Docker rotation.
- [ ] Step 9: Commit: feat: add config backup health and logging.

---

## Task 11：NAS update.sh 与生产部署

**Files**
- Create: deploy/update.sh
- Create: deploy/README.md
- Create: server/tests/test_update_script.py

- [ ] Step 1: Test dirty-worktree, fetch/pull failure, build failure, Compose failure and healthcheck failure guards.
- [ ] Step 2: Implement strict shell mode and explicit main-branch verification.
- [ ] Step 3: Implement fetch → fast-forward pull → Docker build → compose up → healthcheck.
- [ ] Step 4: Never use destructive reset/checkout to overwrite NAS-local changes.
- [ ] Step 5: Document stable-tag rollback.
- [ ] Step 6: Run ShellCheck and a disposable Git repository test.
- [ ] Step 7: Commit: feat: add safe nas deployment updater.

---

## Task 12：真实 NAS/MPD 验收与 v0.1.0

**Files**
- Create: docs/acceptance/nas-mpd-0.23.5.md
- Create: docs/acceptance/web-reverse-proxy.md
- Modify: README.md, docs/CHANGELOG.md

- [ ] Step 1: Verify container → NAS LAN IP → MPD 0.23.5.
- [ ] Step 2: Verify play/pause/stop/previous/next/seek/repeat/random/volume.
- [ ] Step 3: Verify USB DAC output and output state.
- [ ] Step 4: Verify library update, event debounce and 12-hour reconciliation.
- [ ] Step 5: Verify WebSocket reconnect after browser network interruption.
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

---

## Spec Coverage Self-Review

- Chapter 1 Playback/Queue/AutoPlay/History/Context → Tasks 4, 5, 6, 8, 9.
- Chapter 2-1 Song/Album/Artist/Genre/Year/Lyrics/Audio metadata/Collection/Playlist/Favorites/Search/Scan → Tasks 2, 3, 5, 8, 9.
- Chapter 3 Music Server authority/MPD Adapter/USB DAC/CLIENT_STREAM/Output/About/status/error → Tasks 1, 4, 6, 7, 12.
- Chapter 4 Vue/FastAPI/SQLite/Docker/dev-prod/same-origin/WSS/Mock MPD/read-only music/12h scan/backup/GitHub/NAS update/test/health/logging/security → Tasks 0, 1, 3, 6, 8, 10, 11, 12.
- Android remains outside v0.1 implementation but reuses the stable REST/WebSocket/state model later.

## Type/Interface Review

- PlayerPort is the only playback-engine dependency.
- Repositories return domain models, not SQLite rows.
- Services own business rules.
- API schemas are separate from domain models.
- Web consumes API/WebSocket state, never MPD state.
- Mock MPD and real MPD implement the same PlayerPort.
- FullStateSnapshot is the reconnect authority.

## Five Highest-Risk Tests

1. Unsupported MPD 0.23.5 command → Task 1.
2. Queue mutation during AutoPlay refill → Task 4.
3. File move/rename and Song ID preservation → Tasks 2/3.
4. WebSocket reconnect during active playback → Task 6.
5. MPD unavailable during startup → Task 10.

## Execution Order

0 工程骨架
→ 1 MPD Adapter/Mock/能力探针
→ 2 SQLite/Repository
→ 3 Scanner/Metadata/Lyrics
→ 4 Queue/History/AutoPlay/Playback
→ 5 Collection/REST
→ 6 WebSocket/State
→ 7 Output/MPD About
→ 8 Web/PWA
→ 9 Queue/Library/Playlist/Search UI
→ 10 Backup/Health/Logging
→ 11 NAS update.sh
→ 12 Real NAS/MPD acceptance/v0.1.0

每个 Task 独立测试、独立提交。遇到失败先使用 superpowers:systematic-debugging；完成主要阶段后使用 code-review/verification-before-completion。