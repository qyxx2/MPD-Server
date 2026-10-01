# MPD-Server

Music Server：`Web/PWA → FastAPI → Services → PlayerPort/Repositories → MPD/SQLite`。

当前 `main` 已完成 Task 0–4；`feature/task-5-library-api` 正在实施 Task 5。项目的长期产品/架构合同位于 `docs/superpowers/specs/`，任务依赖和范围以主 Implementation Plan 为准。

## 当前状态

| Task | 状态 | 范围 |
|---|---|---|
| 0 | 已完成 | 工程骨架、Docker Compose、统一开发入口 |
| 1 / 1R | 已完成 | PlayerPort、Mock/真实 MPD Adapter、MPD 0.23.5 能力合同 |
| 2 / 2R | 已完成 | SQLite、Library/Playlist/Favorites/History、reconciliation persistence |
| 3 | 已完成 | 元数据、歌词、扫描、watch/scheduler、artwork lifecycle |
| 4 | 已完成 | Queue、PlaybackContext、History、AutoPlay、PlaybackService |
| 5 | 进行中 | Collection、Library/Playlist Service、REST API；Batch 1–5 已完成，进入 Batch 6 前仍有 C/D corrective blocker |
| 6–12 | 未开始 | Realtime、Output、Web/PWA、配置/部署及最终实机验收 |

Task 5 当前 Gate 只看：
- `docs/superpowers/plans/2026-09-29-mpd-server-task-5-batch-plan.md`
- `docs/superpowers/plans/2026-10-01-task-5-contract-architecture-corrective-acceptance.md`

已完成 Task 的长篇 Batch/acceptance/corrective 记录已归档到 `docs/superpowers/archive/`，作为历史证据，不作为新实现的默认输入。文档读取规则见 `docs/superpowers/README.md`。

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
