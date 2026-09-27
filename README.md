# MPD-Server

Music Server：`Web/PWA → FastAPI → Services → MPD Adapter → MPD`。

当前 `main` 已完成 Task 0、Task 1、Task 1R、Task 2 和 Task 2R 的基础能力建设。现阶段重点是服务端分层、MPD 0.23.5 传输契约以及 SQLite 曲库持久化与 Reconciliation 前置硬化；完整的播放业务、REST API、WebSocket、Web 播放器和 NAS 发布流程仍按实施计划继续推进。

## 当前实现状态

- Task 0：工程骨架、Vue/Vite、开发/生产 Docker Compose、生产静态文件托管与统一 Makefile 入口。
- Task 1：PlayerPort、确定性的 Mock MPD、MPD TCP 协议解析、真实 MPD 0.23.5 Adapter，以及 `MPDCapabilities` / `VerifiedPlayerPort` 能力边界。
- Task 1R：补齐 MPD Queue、Output、Stats、Database Update Status 传输契约，并已针对目标 MPD 0.23.5 完成真实运行时能力验证。
- Task 2：SQLite 数据库、Library / Playlist / Favorites / History Repository，以及事务和关键写入串行化。
- Task 2R：Schema v2、Song 文件签名与可用性状态、嵌入式 Artwork 引用、Song 候选匹配和 atomic scan-batch persistence；Missing / Unreadable 状态不会删除 Song 行或破坏 Playlist / Favorites / History 引用。
- 真实 MPD 环境：已在 Synology DS920 / DSM 7.1.1 的 MPD 0.23.5 上完成能力探针，并记录于 `docs/mpd-0.23.5-capabilities.md`。
- 下一阶段：Task 3 开始实现媒体元数据、歌词、曲库扫描与监听；随后按依赖顺序推进 Queue/AutoPlay/Playback Service、REST API、Output、WebSocket、Web/PWA、配置与 NAS 部署。

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
