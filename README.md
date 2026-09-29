# MPD-Server

Music Server：`Web/PWA → FastAPI → Services → MPD Adapter → MPD`。

当前 `main` 已合入 Task 0、Task 1、Task 1R、Task 2、Task 2R、Task 3（含 corrective follow-up）以及 **Task 4**。Task 4 已完成全部 15 个 Plan Steps，覆盖 Queue、Playback Context、Played / History、AutoPlay、Queue revision/CAS 与 Playback Service；最终验收在真实 ARM64 Python virtualenv 中完成。

## 当前实现状态

| Task | 当前状态 | 说明 |
|---|---|---|
| Task 0 | 已完成 | 工程骨架、Vue/Vite、开发/生产 Docker Compose、生产静态文件托管与统一 Makefile 入口。 |
| Task 1 | 已完成 | PlayerPort、确定性的 Mock MPD、MPD TCP 协议解析、真实 MPD 0.23.5 Adapter，以及 `MPDCapabilities` / `VerifiedPlayerPort` 能力边界。 |
| Task 1R | 已完成 | 补齐 MPD Queue、Output、Stats、Database Update Status 传输契约，并已针对目标 MPD 0.23.5 完成真实运行时验证。 |
| Task 2 | 已完成 | SQLite 数据库、Library / Playlist / Favorites / History Repository，以及事务和关键写入串行化。 |
| Task 2R | 已完成 | Schema v2、Song 文件签名与可用性状态、嵌入式 Artwork 引用、Song 候选匹配和 atomic scan-batch persistence；Missing / Unreadable 不删除 Song 行，也不破坏 Playlist / Favorites / History 引用。 |
| Task 3 | 已完成 corrective follow-up | 媒体元数据、歌词、扫描器、watcher、scheduler、domain event，以及歌词持久化、LRC 增量扫描、Available Songs contract、move matching、Artwork reference lifecycle 修复均已完成最终验收。 |
| Task 4 | 已完成 | Queue、Playback Context、Played / History、AutoPlay、Queue transaction/revision-CAS、Playback Service 与 MPD/PlayerPort 一致性均已完成最终验收。 |
| Task 5 | 未开始 | Collection、Library/Playlist Service、REST API 尚未实现。 |
| Task 6 | 未开始 | WebSocket 与完整状态恢复尚未实现。 |
| Task 7 | 未开始 | Output Manager 与 MPD About 尚未实现。 |
| Task 8 | 未开始 | Web/PWA 状态层与播放器尚未实现。 |
| Task 9 | 未开始 | Web Queue、Library、Playlist、Search、Favorites、Settings 尚未实现。 |
| Task 10 | 未开始 | 配置、备份、日志、健康检查尚未实现。 |
| Task 11 | 未开始 | NAS update.sh 与生产部署流程尚未实现。 |
| Task 12 | 未开始 | 真实 NAS/MPD 最终验收与 v0.1.0 尚未开始。 |

### Task 4 最终验收

Task 4 已完成 Batch 1 → Batch 6，共 15 个 Plan Steps。

最终 ARM64 Python virtualenv 验证：

- Task 4 service aggregate：**46 passed**
- Queue + AutoPlay：**27 passed**
- Queue/History/AutoPlay：**35 passed**
- Playback Service：**11 passed**
- 其它受影响回归：**30 passed、32 passed、10 passed、34 passed**
- Health：**1 passed**
- 全局 `server/tests`：**164 passed**
- compileall：通过
- Ruff：通过
- `git diff --check`：通过
- 架构边界、changed-files、真实音乐文件只读检查：通过

核心架构约束保持不变：

- Music Server 是 Queue、AutoPlay、Playback State 与业务状态权威。
- Playback engine 只通过 `PlayerPort` 访问。
- Playback Service 不直接访问 SQLite 或具体 MPD transport。
- AutoPlay 不覆盖 MANUAL Queue items。
- Pause 保留 AutoPlay，Stop 禁用 AutoPlay，Queue exhaustion 非 terminal。
- 真实音乐文件严格只读。
- Task 4 未引入 Task 5–12 的未来实现。

Task 4 验收记录：

`docs/superpowers/plans/2026-09-29-mpd-server-task-4-batch-6-acceptance.md`

Batch 6 required commit：

`cb02824273881fcb328f20391ec99fe144ac84d9`  
`feat: implement authoritative playback model`

真实 MPD 环境：已在 Synology DS920 / DSM 7.1.1 的 MPD 0.23.5 上完成能力探针，并记录于 `docs/mpd-0.23.5-capabilities.md`。

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
