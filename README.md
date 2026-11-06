# MPD-Server

MPD-Server 是一套面向 NAS 和局域网环境的自托管音乐服务器。它以 [Music Player Daemon（MPD）](https://github.com/MusicPlayerDaemon/MPD) 作为实际播放引擎，并提供浏览器端音乐管理与播放控制界面。用户可以通过手机或桌面浏览器访问服务；音频解码和输出由 MPD 完成，而不是由浏览器播放。

## 项目功能

- **音乐播放**：查看当前播放状态、曲目信息和进度，执行播放、暂停、切歌及进度控制，并展示歌词和音频输出信息。
- **播放队列与历史**：管理待播队列、调整曲目顺序、查看播放历史，并支持自动播放。
- **音乐资料库**：浏览歌曲、专辑和艺术家，搜索曲目；服务端扫描音乐目录并同步曲库信息。
- **歌单与收藏**：创建和管理播放列表，收藏常听歌曲。
- **实时同步**：通过 HTTP API 和 WebSocket 同步播放状态、队列及资料库变更。
- **音量与输出状态**：查看 MPD 输出信息；在 MPD 输出设备和 Mixer 配置满足条件时，可启用硬件音量控制。该功能默认关闭。

Web 界面采用 Vue 3 和 Vite 构建，后端使用 Python、FastAPI 和 WebSocket，业务数据与曲库索引存储在 SQLite 中。

## 系统结构

```text
浏览器 / Android 遥控端
          │
          ▼
      MPD-Server
  FastAPI · WebSocket · SQLite
          │
          ▼
         MPD
          │
          ▼
     DAC / 音频设备

音乐文件目录 ──► MPD
       └──────► MPD-Server（只读扫描）
```

MPD-Server 负责曲库索引、队列及播放相关业务和客户端通信；MPD 负责读取音乐文件、解码和音频输出。部署时，MPD 与 MPD-Server 必须能够访问对应的音乐目录，并确保服务端音乐路径与 MPD 曲库 URI 相互对应。

## Android 遥控客户端

[MPD-Server Remote for Android](https://github.com/qyxx2/MPD-Server_remote_for_Android) 是本项目的原生 Android 遥控端，使用 Kotlin 和 Jetpack Compose 构建，不依赖 WebView。

客户端连接 MPD-Server 后，可进行播放控制、查看专辑封面和歌词、管理队列、浏览曲库、搜索歌曲，以及管理歌单和收藏；同时支持 Android 媒体会话、系统通知控制，并可观察和控制符合条件的 MPD 硬件音量。

Android 客户端主要负责交互与状态展示。播放状态、队列、曲库和歌单等业务数据由 MPD-Server 统一管理。

## 部署方式

推荐在 NAS 或 Linux 主机上使用 Docker Compose 部署预构建镜像。GitHub Actions 会构建并发布适用于 `linux/amd64` 和 `linux/arm64` 的 GHCR 镜像。

### 1. 准备配置

克隆仓库后复制环境变量模板：

```sh
cp deploy/.env.example deploy/.env
```

编辑 `deploy/.env`，至少配置以下项目：

| 配置项 | 说明 |
| --- | --- |
| `MPD_SERVER_IMAGE` | GHCR 镜像及提交 SHA 标签 |
| `MPD_HOST`、`MPD_PORT` | MPD 服务的可访问地址和端口 |
| `MUSIC_DIR` | NAS 主机上的音乐目录 |
| `MPD_SERVER_DATA_DIR` | 数据库及持久化数据目录 |
| `MPD_SERVER_CONFIG_DIR` | 服务配置目录 |
| `MPD_SERVER_BACKUP_DIR` | 数据库备份目录 |
| `MPD_SERVER_PORT` | NAS 对外提供 Web 服务的端口 |

镜像使用 `ghcr.io/qyxx2/mpd-server:sha-<完整提交 SHA>`。请从 [容器构建工作流](https://github.com/qyxx2/MPD-Server/actions/workflows/container.yml) 中选择 `validate` 和 `image` 均成功的提交，并使用其完整 SHA。不要仅凭镜像标签存在就认定该提交已通过构建验证。

### 2. 启动服务

在支持 Docker Compose v2 的环境中执行：

```sh
docker compose --env-file deploy/.env -f deploy/docker-compose.yml config
docker compose --env-file deploy/.env -f deploy/docker-compose.yml pull
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --no-build
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs --tail=100 server
```

群晖等仍使用 Docker Compose 1.28.5 的环境，可使用仓库中的 [旧版 Compose 示例](docs/docker-compose.yml)。该文件是需要按实际环境修改的示例，使用前请更新镜像 SHA、MPD 地址、音乐目录、持久化目录和端口映射，再执行：

```sh
docker-compose -f docs/docker-compose.yml pull
docker-compose -f docs/docker-compose.yml up -d
docker-compose -f docs/docker-compose.yml ps
docker-compose -f docs/docker-compose.yml logs --tail=100
```

### 3. 部署检查

- 将 NAS 数据目录分别持久化挂载到容器的 `/data`、`/config` 和 `/backups`。
- 音乐目录挂载到容器的 `/music`，并保持只读（`/music:ro`）。
- 确保 MPD 与容器都能访问同一音乐目录；`MPD_HOST` 必须是容器实际可访问的地址。容器内的 `127.0.0.1` 指向容器自身，并不代表 NAS 主机。
- 启动后访问 `http://NAS-IP:MPD_SERVER_PORT`，并检查 `/api/health`、`/api/state`、曲库读取和实际 MPD 播放输出。

当前服务主要面向可信任的局域网环境，尚未提供适合直接公网开放的完整身份认证与安全边界。请勿将服务端口直接暴露到互联网。

完整的环境变量、硬件音量配置及部署说明见 [部署文档](deploy/README.md)，配置项模板见 [deploy/.env.example](deploy/.env.example)。

## 相关项目

- **上游播放引擎：** [Music Player Daemon（MPD）](https://github.com/MusicPlayerDaemon/MPD)
- **下游 Android 遥控端：** [MPD-Server Remote for Android](https://github.com/qyxx2/MPD-Server_remote_for_Android)
