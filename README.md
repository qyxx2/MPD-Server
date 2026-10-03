# MPD-Server

Music Server：`Web/PWA → FastAPI → Services → PlayerPort/Repositories → MPD/SQLite`。

当前 `main` 已完成 Task 0–5；`feature/task-7-output-manager` 已完成 Task 7 实现及后端 final acceptance，尚未合入 main。按照主 Implementation Plan 的依赖顺序，Task 7 先于 Task 6。项目的长期产品/架构合同位于 `docs/superpowers/specs/`，任务依赖和范围以主 Implementation Plan 为准。

## 当前状态

| Task | 状态 | 范围 |
|---|---|---|
| 0 | 已完成 | 工程骨架、Docker Compose、统一开发入口 |
| 1 / 1R | 已完成 | PlayerPort、Mock/真实 MPD Adapter、MPD 0.23.5 能力合同 |
| 2 / 2R | 已完成 | SQLite、Library/Playlist/Favorites/History、reconciliation persistence |
| 3 | 已完成 | 元数据、歌词、扫描、watch/scheduler、artwork lifecycle |
| 4 | 已完成 | Queue、PlaybackContext、History、AutoPlay、PlaybackService |
| 5 | 已完成并合入 main | Collection、Library/Playlist Service、REST API、idempotency 与跨模块 invariant |
| 7 | 分支实现及后端验收完成，未合入 main；物理 DAC 验收留待 Task 12 | Output Manager、NAS_DAC 状态/控制、MPD About |
| 6 | 未开始；可进行独立 pre-flight | WebSocket、完整状态快照与重连恢复 |
| 8–12 | 未开始 | Web/PWA、配置、部署及最终实机验收 |

当前实施入口：
- `docs/superpowers/plans/2026-10-02-mpd-server-task-7-batch-plan.md`
- `docs/superpowers/plans/2026-09-25-mpd-server-v0-1-implementation-plan.md`

Task 5 的 Batch/acceptance/corrective 文档已归档到 `docs/superpowers/archive/task-5/`，作为历史证据，不再作为当前实现入口。文档读取规则见 `docs/superpowers/README.md`。

## 核心架构约束

- API 只做 request validation、Service 调用、error mapping 和 response model。
- API 不直接访问 SQLite，也不直接访问 concrete MPD adapter。
- PlaybackService 是播放编排权威；PlayerPort 是播放引擎边界。
- Queue、Playback History、Playlist/Favorites、Collection/PlaybackContext 保持各自语义，不互相代替。
- Library/scan/artwork 流程对真实音乐文件只读。
- 后续 Task 不得被当前 Task 提前实现。

## 本地检查

```text
make test
make lint
make typecheck
make build
```

后端可直接在现有 virtualenv 中运行：

```text
python -m pytest -q server/tests
python -m compileall -q server
python -m ruff check server
```

前端目录为 `web/`。群晖 Node.js 18 不满足新版 Vite 构建要求；生产 Web 构建使用 `deploy/Dockerfile` 中的 Node 22 环境。

## Docker

开发环境：

```text
docker compose -f deploy/docker-compose.dev.yml up
```

生产环境先复制 `deploy/.env.example` 为 `deploy/.env`，再执行：

```text
docker compose --env-file deploy/.env -f deploy/docker-compose.yml config
docker compose --env-file deploy/.env -f deploy/docker-compose.yml build
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

真实 MPD 的目标能力记录：`docs/mpd-0.23.5-capabilities.md`。

## 目录

```text
server/                    FastAPI 服务端
web/                       Vue 3 / Vite 前端
deploy/                    Docker/生产配置
docs/superpowers/specs/    长期产品与架构合同
docs/superpowers/plans/    当前仍会指导实施的计划/Gate
docs/superpowers/archive/  已完成阶段的历史证据
```

开始任何 Task 前，先阅读 `docs/superpowers/README.md`，再按其中的最小文档集加载上下文。
