# MPD-Server

Music Server：`Web/PWA → FastAPI → Services → MPD Adapter → MPD`。

当前 `main` 已完成 Task 0 工程骨架与 Task 1 MPD 播放引擎适配层。服务端提供 `/api/health` 健康端点，并已具备 PlayerPort、确定性的 Mock MPD、MPD TCP 协议解析、真实 MPD 0.23.5 Adapter，以及基于目标 NAS 实测结果的能力边界校验。

## 当前实现状态

- Task 0：工程骨架、Vue/Vite、开发/生产 Docker Compose、生产静态文件托管。
- Task 1：PlayerPort、Mock MPD、MPDAdapter、MPD 协议解析、`MPDCapabilities` / `VerifiedPlayerPort`。
- 真实环境：已在 Synology DS920 / DSM 7.1.1 的 MPD 0.23.5 上完成能力探针，并记录于 `docs/mpd-0.23.5-capabilities.md`。
- 后续 Task：SQLite、Library、Queue/AutoPlay、REST/WebSocket、Web 播放器、备份/部署及最终 NAS 验收仍按实施计划推进。

## 本地检查

项目提供统一命令入口：

```text
make test
make lint
make typecheck
make build
```

也可直接执行对应命令。群晖当前 Node.js 18 不满足新版 Vite 的构建要求；生产 Web 构建应使用 `deploy/Dockerfile` 提供的 Node 22 构建环境。

前端目录：`web/`

```text
npm install
npm run dev
npm run build
npm run typecheck
```

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

开发环境默认使用 `MPD_MODE=mock`。真实 MPD 由后续服务层通过已验证的 MPD Adapter 接入，Music Server 不在容器内安装、启动或管理 MPD。

生产环境只读挂载音乐目录，SQLite、配置和备份目录位于容器外。

## 目录

```text
server/   FastAPI 服务端
web/      Vue 3 / Vite 前端
deploy/   Docker Compose、Dockerfile 和生产环境配置示例
docs/     规格、实施计划和 MPD 能力记录
```
