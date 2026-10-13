# MPD-Server

面向局域网和 NAS 的自托管音乐服务器。通过手机或桌面浏览器访问 Web 界面，由服务端连接 [Music Player Daemon (MPD)](https://www.musicpd.org/) 控制播放；音乐音频由 MPD 输出，而不是由浏览器解码播放。

**当前版本：v0.1 — 首个基本可用版本。** 已实现基本播放、曲库浏览与搜索、播放队列、播放列表、收藏、设置与 MPD 连接配置，可用于 NAS + 真实 MPD 的基本使用。v0.1 是初始可用版本，不表示所有原始 Task 8–12 长期需求及全部真实设备验收都已完成。

## 功能

- **播放器**：显示实际播放/暂停、当前曲目及进度；提供基本播放控制和歌词/音频信息展示。
- **队列**：浏览当前队列、下一首插入、排序与基本管理；部分队列执行语义仍在后续重构范围内。
- **资料库与搜索**：浏览歌曲/专辑/艺术家及搜索，后端只读访问现有音乐文件；自动曲库同步和状态通知。
- **播放列表与收藏**：建立和管理播放列表、歌曲收藏。
- **设置与连接**：保存 MPD 连接目标，通过重启服务应用保存的地址；查看连接、输出及基本健康状态。
- **Web**：移动端优先的响应式界面，HTTP API 与 WebSocket 实时状态；当前不包含完整离线 PWA 安装体验。

技术架构：`Vue 3 / Vite → FastAPI / WebSocket → Service / PlayerPort → MPD`，元数据及业务记录使用 SQLite。

## 快速部署（NAS）

推荐直接使用 GitHub Actions 已验证、在 GHCR 发布的 **linux/amd64 + linux/arm64** 镜像，无需在 NAS 编译源码。镜像标签为 `ghcr.io/qyxx2/mpd-server:sha-<完整提交 SHA>`；请从 [Actions](https://github.com/qyxx2/MPD-Server/actions/workflows/container.yml) 中选取**成功**的 image 作业所对应 SHA（不要只依据运行序号或较新但失败的提交），并核对镜像拉取权限。

仓库提供 [旧版 Docker Compose 可用示例](docs/docker-compose.yml)，以及完整的 [部署与环境变量说明](deploy/README.md)、[生产 Compose](deploy/docker-compose.yml) 和 [环境模板](deploy/.env.example)。在 NAS 上：

1. 创建持久化的 `data`、`config` 目录，并让容器内 `/data`、`/config` 分别映射至上述目录。
2. 将实际音乐根目录只读挂载为 `/music:ro`，确保 MPD URI 与容器中的相对音乐路径对应。
3. 设置 MPD 地址/端口（容器里 `127.0.0.1` 不是 NAS 主机）、数据库和配置路径；已有配置和数据库不要覆盖。
4. 使用确认成功的多架构镜像部署，开放 Web 端口，访问 `http://NAS-IP:18000`（采用示例映射时）。
5. 核对 `/api/health`、Web 页面、`/api/state`、WebSocket、实际曲库与 MPD 播放。服务端健康不等于 MPD 已连接或 DAC 已出声。

旧版 Compose 1.28.5 可使用：

```sh
docker-compose -f docs/docker-compose.yml pull
docker-compose -f docs/docker-compose.yml up -d
docker-compose -f docs/docker-compose.yml ps
docker-compose -f docs/docker-compose.yml logs --tail=100
```

**部署前必须编辑示例中的镜像 SHA、NAS IP、MPD 地址、音乐路径和输出设备名。** 仓库中的 `docs/docker-compose.yml` 是用于指定环境的参考示例，不应直接照搬其中的私有局域网地址或硬件名称。保存 MPD 地址并不会立即切换活跃连接，需要手动重启容器。

## 开发及验证

```sh
make test
make lint
make typecheck
make build
```

后端：Python 3.13 / FastAPI；前端：Node 22 / Vue 3。生产镜像定义在 `deploy/Dockerfile`。运行自动测试时为 `DATABASE_PATH` 使用隔离临时目录，避免触及生产数据库。CI 在推送到 main/功能分支及版本 tag 时验证后端、前端、类型检查和生产构建，并在非 PR 事件发布 GHCR 多架构镜像。

## v0.1 边界与安全

- 局域网自用为主要场景；目前未提供对公网暴露所需的完整身份认证和安全边界，**不要直接暴露到公网**。
- 音乐根目录按只读方式挂载，业务数据和持久化配置另存。
- MPD 是实际播放状态的来源，应用编排队列和业务状态；连接断开、控制目标丢失等异常会限制部分操作。
- PWA 离线能力、复杂运维/备份恢复自动化、完整实机 DAC 验收与队列执行重构均不属于本次 v0.1 基本可用范围。
- Task 9 的历史自动及人工 Gate 与未关闭项见 [Task 9 final acceptance](docs/superpowers/archive/task-9/2026-10-11-task-9-final-acceptance.md)。后续修复证据在 `docs/superpowers/archive/task-9/`；不要将自动测试结果误写为实机验收通过。

## 文档与源码

- `server/`：服务端 API、服务、MPD Adapter、SQLite
- `web/`：Web UI
- `deploy/`：Docker / Compose / 配置
- `docs/superpowers/specs/`：长期合同
- `docs/superpowers/plans/`：计划和未关闭 Gate
- `docs/superpowers/archive/`：已完成批次的验收记录

开发与后续工作入口：[文档索引](docs/superpowers/README.md) · [主实施计划](docs/superpowers/plans/2026-09-25-mpd-server-v0-1-implementation-plan.md) · [Task 9 批次计划](docs/superpowers/plans/2026-10-10-task-9-web-batch-plan.md)。
