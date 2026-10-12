# MPD-Server

Music Server：`Web/PWA → FastAPI → Services → PlayerPort/Repositories → MPD/SQLite`。

当前实现已完成 Task 0–7，以及 Task 4 D6 corrective 和 Task 6 Batch13 的后端 final acceptance。Task 8 后端播放控制前置 P1–P3 已通过本地自动 Gate 并合入 main；Task 8 手机 Web W1–W6 已实现，自动 Gate 与必要手机真人验收通过，当前手机 Web 范围满足 Task 9 前置。PWA 延期、真实 MPD/NAS/DAC 尚未运行，不宣称原始 Task 8 整体验收完成。项目的长期产品/架构合同位于 `docs/superpowers/specs/`，任务依赖和范围以主 Implementation Plan 为准。

## 当前状态

| Task | 状态 | 范围 |
|---|---|---|
| 0 | 已完成 | 工程骨架、Docker Compose、统一开发入口 |
| 1 / 1R | 已完成 | PlayerPort、Mock/真实 MPD Adapter、MPD 0.23.5 能力合同 |
| 2 / 2R | 已完成 | SQLite、Library/Playlist/Favorites/History、reconciliation persistence |
| 3 | 已完成 | 元数据、歌词、扫描、watch/scheduler、artwork lifecycle |
| 4 | 已完成；D6 S10/S11/S12 已通过 | Queue、PlaybackContext、History、AutoPlay、PlaybackService |
| 5 | 已完成并合入 main | Collection、Library/Playlist Service、REST API、idempotency 与跨模块 invariant |
| 7 | 已完成并合入 main；物理 DAC 验收留待 Task 12 | Output Manager、NAS_DAC 状态/控制、MPD About |
| 6 | Batch1–13 实现与后端 final acceptance 已通过 | WebSocket、完整状态快照与重连恢复 |
| 8 | 后端控制前置已合入 main；手机 Web W1–W6 自动及必要真人验收通过 | 手机 Web 状态层与播放器；PWA 安装/SW/冷离线壳延期 |
| 9 | 部分完成；B01–B09 CLOSED / HUMAN PASSED，B10自动/关系及production/LAN预检完成，手机综合PENDING、新实机功能Gate BLOCKED/NOT RUN | Web 业务页面；B09 Settings、MPD接入配置及A02布局整改已获用户验收 |
| 10–12 修订范围 | B00–B06自动Gate已通过，B07本地准备完成；NAS实机与最终交接待验 | 最小配置、自动曲库同步、AppBar活动、基本健康日志、NAS部署及真实验收；复杂运维延期 |

全部后续Web UI工作流遵守唯一 [全局 UI 合同](docs/superpowers/specs/2026-10-03-web-pwa-visual-design.md)，保护当前Player。Task 9 B01–B09（共享壳/背景/导航、普通歌曲原子播放、Queue、Library、Search、Playlist、Favorites、Settings及MPD接入配置）已实现并通过必要验收；B06 Search（A04）已获用户手机验收，CLOSED / HUMAN PASSED；B07 Playlist已获用户验收，CLOSED / HUMAN PASSED；B08 Favorites/爱心及A02展示整改已获用户验收，CLOSED / HUMAN PASSED；B10自动/关系及production/LAN预检完成，手机综合PENDING、新实机功能Gate BLOCKED/NOT RUN，Task 9 整体未完成。

当前实施入口：
- [v0.1 NAS最小真实交付 Final Batch Plan](docs/superpowers/plans/2026-10-11-v0-1-nas-final-batch-plan.md)（B07 READY FOR NAS；B08/B09 未启动，实机Gate待确认）
- [主 Implementation Plan](docs/superpowers/plans/2026-09-25-mpd-server-v0-1-implementation-plan.md)
- [Task 9 Contract Audit](docs/superpowers/plans/2026-10-10-task-9-contract-audit.md)
- [Task 9 Web Batch Plan](docs/superpowers/plans/2026-10-10-task-9-web-batch-plan.md)（B01–B09 CLOSED；song Play Now 后端合同已冻结，B06 Search（A04）已获用户手机验收，CLOSED / HUMAN PASSED；B07 Playlist已获用户验收，CLOSED / HUMAN PASSED；B08 Favorites/爱心及A02展示整改已获用户验收，CLOSED / HUMAN PASSED；B10自动/关系及production/LAN预检完成，手机综合PENDING、新实机功能Gate BLOCKED/NOT RUN）
- [Task 8 Web Batch Plan](docs/superpowers/plans/2026-10-09-task-8-web-batch-plan.md)
- [Task 8 Contract Audit](docs/superpowers/plans/2026-10-09-task-8-contract-audit.md)
- [Task 8 后端控制前置验收](docs/superpowers/archive/task-8/2026-10-09-playback-control-prerequisite-acceptance.md)
- [手机 Web 真人验收方法](docs/superpowers/plans/2026-10-09-mobile-web-manual-acceptance.md)
- [D6 联合验收与逐合同追溯](docs/superpowers/archive/task-4/2026-10-04-task-4-d6-recovery-acceptance.md)
- [Task 6 Batch13 final acceptance](docs/superpowers/archive/task-6/2026-10-04-task-6-batch-13-acceptance.md)

D6 目标验证限现有 NAS 部署功能范围（daemon 0.23.17 / 协议 0.23.5）。恢复 runner 需显式启用并注入能力；最终配置加载属 Task 10。服务或 MPD 重启可恢复 actual 显示，业务 occurrence 绑定需明确播放操作经确认重建；不认证自然完成原因或补造遗漏 History。

Task 7 后端验收证据见 `docs/superpowers/archive/task-7/2026-10-03-task-7-batch-9-acceptance.md`；本地后端验收不代表已完成真实 NAS/物理 DAC 验收。

Task 8 后端已提供 snapshot `control_target`、原位 resume 和 guarded seek，保留无 target seek 的兼容行为。真实 MPD/NAS manual gate 尚未运行；后端自动通过不代表手机 Web 或完整 Task 8 验收通过。当前以手机浏览器通过 LAN HTTP 验收显示和触摸交互，PWA 延期部分不阻塞修订后的 Task 8 手机 Web 验收及 Task 9。

Task 5 的 Batch/acceptance/corrective 文档已归档到 `docs/superpowers/archive/task-5/`，作为历史证据，不再作为当前实现入口。文档读取规则见 `docs/superpowers/README.md`。

2026-10-11用户优先级：先让现有功能在NAS Docker＋真实MPD上正确运行。保留URI模型，只补音乐根映射；曲库自动及时同步并推送结果；所有活动归现有AppBar中心。用户手动重启容器，备份恢复/update.sh/restart API/PWA延期，详细记录查看Docker及浏览器诊断日志。长期规则见Architecture §22、Library §7.2和Visual §6。

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
DATABASE_PATH="$(mktemp -d)/test.db" .venv/bin/python -m pytest -q server/tests
.venv/bin/python -m compileall -q server
.venv/bin/python -m ruff check server
```

测试使用临时 `DATABASE_PATH`，避免少数 API lifespan 测试回落到本地运行数据库。

前端目录为 `web/`。群晖 Node.js 18 不满足新版 Vite 构建要求；生产 Web 构建使用 `deploy/Dockerfile` 中的 Node 22 环境。

当前B10证据与未关闭Gate：[Task9 final acceptance](docs/superpowers/archive/task-9/2026-10-11-task-9-final-acceptance.md)。真实地址请填写本轮LIVE Adapter页面（5188），旧Mock页面保存地址不会连接实机。

## Docker

B07 的部署配置、SPA 深链接与本地生产构建已准备；真实 NAS 构建、容器部署及重启持久化仍待确认。实际参数、最短操作与反馈卡见 [NAS 部署卡](deploy/README.md)。此状态不代表 B08/B09 已执行。

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
