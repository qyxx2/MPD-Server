# MPD-Server

Music Server：`Web/PWA → FastAPI → Services → MPD Adapter → MPD`。

当前 `main` 已合入 Task 0、Task 1、Task 1R、Task 2、Task 2R，以及 Task 3 的基础实现。Task 3 基础实现已通过原计划的 Task 3 验收并合入 `main`，但随后审计发现若干跨层契约缺口；当前 `feature/task-3-corrective-followup` 专用于这些独立修复，Task 3 corrective follow-up 已完成最终验收；Task 4 现在可以依据已冻结的 Available Songs contract 和 Task 3 dependency gate 开始。Task 4 本身尚未实现。

## 当前实现状态

| Task | 当前状态 | 说明 |
|---|---|---|
| Task 0 | 已完成 | 工程骨架、Vue/Vite、开发/生产 Docker Compose、生产静态文件托管与统一 Makefile 入口。 |
| Task 1 | 已完成 | PlayerPort、确定性的 Mock MPD、MPD TCP 协议解析、真实 MPD 0.23.5 Adapter，以及 `MPDCapabilities` / `VerifiedPlayerPort` 能力边界。 |
| Task 1R | 已完成 | 补齐 MPD Queue、Output、Stats、Database Update Status 传输契约，并已针对目标 MPD 0.23.5 完成真实运行时验证。 |
| Task 2 | 已完成 | SQLite 数据库、Library / Playlist / Favorites / History Repository，以及事务和关键写入串行化。 |
| Task 2R | 已完成 | Schema v2、Song 文件签名与可用性状态、嵌入式 Artwork 引用、Song 候选匹配和 atomic scan-batch persistence；Missing / Unreadable 不删除 Song 行，也不破坏 Playlist / Favorites / History 引用。 |
| Task 3 | 已完成 corrective follow-up | 媒体元数据、歌词、扫描器、watcher、scheduler、domain event，以及歌词持久化、LRC 增量扫描、Available Songs contract、move matching、Artwork reference lifecycle 修复均已完成最终验收。 |
| Task 4 | 未开始 | 依赖 Task 3 corrective follow-up 完成；Queue、Playback Context、AutoPlay、Playback Service 尚未实现。 |
| Task 5 | 未开始 | Collection、Library/Playlist Service、REST API 尚未实现。 |
| Task 6 | 未开始 | WebSocket 与完整状态恢复尚未实现。 |
| Task 7 | 未开始 | Output Manager 与 MPD About 尚未实现。 |
| Task 8 | 未开始 | Web/PWA 状态层与播放器尚未实现。 |
| Task 9 | 未开始 | Web Queue、Library、Playlist、Search、Favorites、Settings 尚未实现。 |
| Task 10 | 未开始 | 配置、备份、日志、健康检查尚未实现。 |
| Task 11 | 未开始 | NAS update.sh 与生产部署流程尚未实现。 |
| Task 12 | 未开始 | 真实 NAS/MPD 最终验收与 v0.1.0 尚未开始。 |

真实 MPD 环境：已在 Synology DS920 / DSM 7.1.1 的 MPD 0.23.5 上完成能力探针，并记录于 `docs/mpd-0.23.5-capabilities.md`。

### Task 3 Corrective Follow-up

Task 3 corrective follow-up 已按以下顺序完成：

`Batch 0 → Batch 1 → Batch 2 → Batch 3 → Batch 4 → Batch 5 → Batch 6`

完成条件包括：跨层契约问题全部关闭；新增测试遵循 RED → GREEN；Task 3 focused tests、Task 2R regression、全局 Python tests、compileall、Ruff 通过；diff 无越界修改；Plan 有独立 corrective 记录；以及 Task 4 所需的 Available Songs contract 已冻结。

在上述条件全部满足前，`main` 不应进入 Task 4。

## 本地检查

项目提供统一命令入口：

```text
make test
make lint
make typecheck
make build
```

前端目录：`web/`

```text
npm install
npm run dev
npm run build
npm run typecheck
```

群晖当前 Node.js 18 不满足新版 Vite 的构建要求；生产 Web 构建使用 `deploy/Dockerfile` 中的 Node 22 构建环境。

## Docker

开发环境：

```text
docker compose -f deploy/docker-compose.dev.yml up
```

生产环境首先复制 `deploy/.env.example` 为 `deploy/.env` 并填写现有 MPD、音乐目录和持久化目录，再执行：

```text
docker compose --env-file deploy/.env -f deploy/docker-compose.yml config
docker compose --env-file deploy/.env -f deploy/docker-compose.yml build
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

开发环境默认使用 Mock MPD。真实 MPD 由服务层通过已验证的 MPD Adapter 接入；Music Server 不在容器内安装、启动或管理 MPD。

生产环境只读挂载音乐目录，SQLite、配置和备份目录位于容器外。真实音乐文件在所有扫描和持久化流程中保持只读。

## 目录

```text
server/   FastAPI 服务端
web/      Vue 3 / Vite 前端
deploy/   Docker Compose、Dockerfile 和生产环境配置示例
docs/     规格、实施计划和 MPD 能力记录
```

详细实现边界和依赖顺序以 `docs/superpowers/specs/` 与 `docs/superpowers/plans/2026-09-25-mpd-server-v0-1-implementation-plan.md` 为准。
