# 第四章：项目技术栈、部署与开发维护架构规格书

- 项目：MPD-Server
- Repository：qyxx2/MPD-Server
- GitHub：https://github.com/qyxx2/MPD-Server
- 日期：2026-09-25
- 状态：设计规格
- 适用范围：Web/PWA 首期、FastAPI 服务端、SQLite、Docker Compose、群晖 DSM 7.1.1、现有独立 MPD 0.23.5
- 前置设计：Playback Model / Queue Semantics、Library / Playlist / Tag / Search、System Architecture / Playback Output

## 1. 目标与范围

本章定义 MPD-Server 的技术实现边界、代码组织、开发环境、Docker 部署、GitHub 维护、群晖生产环境、曲库同步、配置、备份、测试和发布回滚方式。

首期目标是形成一个可以长期运行在群晖上的 Music Server：

`Web/PWA → FastAPI → Music Server Services → MPD Adapter → 群晖独立 MPD → ALSA → USB DAC`

客户端不直接连接 MPD。Music Server 是业务状态和播放控制的统一入口。

本章不实现具体业务代码，也不要求在首期引入 Kubernetes、PostgreSQL、GitHub Actions CI/CD 或复杂的 Web 管理后台。

## 2. 总体技术栈

### 2.1 Web/PWA

- Vue 3
- TypeScript
- Vite
- Tailwind CSS
- 定制 CSS
- 可按需使用无默认视觉风格的 UI primitives，例如 Reka UI
- WebSocket 用于实时状态同步
- REST API 用于普通查询和控制请求

Web/PWA 首期是唯一正式客户端。Android 原生客户端后续复用相同 REST API、WebSocket 和状态模型，不重新定义业务协议。

### 2.2 服务端

- Python
- FastAPI
- REST API
- WebSocket
- SQLite
- Repository / Data Access Layer
- Service Layer
- MPD Adapter

核心业务必须位于 `services/`，API 层只负责请求解析、鉴权边界、调用 service 和响应转换，不直接操作 SQLite 或 MPD。

### 2.3 部署

- Docker
- Docker Compose
- 群晖作为首期生产环境
- 正式环境使用与 Dockerfile 对应的正式镜像
- 首期正式镜像由 NAS 根据 main 构建；未来可切换为 GitHub Container Registry 等镜像仓库拉取预构建镜像
- 开发环境使用独立 Compose 配置
- 不要求群晖宿主机安装完整 Python/Node 开发环境

## 3. 客户端职责边界

客户端负责：

- 页面展示
- 用户操作
- 播放控制请求
- Queue / History 展示和交互
- Library / Playlist 浏览
- 播放状态展示
- WebSocket 状态接收
- 断线自动重连
- 当前页面同源 API/WebSocket 地址计算

客户端不负责：

- Queue 权威状态
- AutoPlay 决策
- 曲库扫描
- Playlist 持久化业务
- History 持久化业务
- MPD 协议直接通信
- MPD 与数据库状态协调

服务端是这些状态和业务的权威来源。

## 4. Web 架构

开发环境采用：

`Browser → Vite Dev Server → Proxy → FastAPI`

Vite 开发服务器负责前端即时更新，并将：

- `/api` → FastAPI
- WebSocket → FastAPI

正式环境由 FastAPI 托管构建后的静态 Web 文件：

`Browser → FastAPI → static Web`

客户端不写死 IP、域名或端口，而是根据当前页面地址采用同源方式访问：

- API：当前 origin + `/api`
- WebSocket：当前 origin 对应的 ws/wss + WebSocket 路径

因此以下访问方式共用同一套客户端代码：

- 群晖局域网 IP + 端口
- 群晖反向代理域名
- HTTPS + WSS

正式环境必须保证群晖反向代理能够正确转发 WebSocket。

## 5. 服务端模块边界

推荐结构：

```
server/
├── app/
│   ├── api/
│   ├── services/
│   ├── repositories/
│   ├── models/
│   ├── player/
│   └── main.py
└── tests/
```

### 5.1 api

负责：

- REST endpoint
- WebSocket endpoint
- 请求参数校验
- 响应模型
- 错误映射

不直接实现复杂业务。

### 5.2 services

负责：

- Playback Service
- Queue Manager
- AutoPlay Engine
- Library Service
- Playlist Service
- History Service
- Output Manager
- 配置/备份等应用级业务

Service 通过 Repository 或 Adapter 访问外部资源。

### 5.3 repositories

负责 SQLite 持久化。

要求：

- 不把 SQL 散落在 API 层
- 事务边界明确
- 关键写操作可串行化
- 为未来 PostgreSQL 迁移保留数据访问抽象

首期仍然使用 SQLite，不为了未来迁移提前引入复杂 ORM 基础设施。

### 5.4 player

负责播放引擎抽象及 MPD Adapter。

首期：

`Music Server → MPD Adapter → MPD TCP Protocol`

MPD 是独立进程，不由 Music Server 安装、启动或管理。

## 6. MPD 集成

生产环境使用群晖宿主机已有 MPD 0.23.5。

Music Server 容器通过配置连接：

- MPD host
- MPD port
- MPD password（如果启用）

采用容器访问群晖 LAN IP 的方式，不使用容器内的 `localhost` 连接宿主机 MPD。

Music Server 不：

- 在容器内运行 MPD
- 自动安装 MPD
- 修改 MPD 配置文件
- 管理 MPD 生命周期

Music Server 提供常用 MPD 运行时控制，例如：

- play / pause / stop
- previous / next
- seek
- repeat
- random
- volume
- update database
- output 状态相关控制（在 MPD 0.23.5 实测能力允许的范围内）

涉及只能修改配置文件的 MPD 设置，不假定能够通过 MPD 协议修改。

### 6.1 MPD 能力验证

实现前必须以实际 MPD 0.23.5 为准验证：

- 支持的命令
- 输出设备能力
- 当前输出状态
- 播放位置
- 曲库更新
- 播放状态事件
- 错误响应

不得因为文档中存在某个新版本 MPD 命令，就假定 0.23.5 支持。

## 7. 曲库

Music Server 对音乐目录采用只读挂载。

原则：

- Music Server 可以读取音乐文件和元数据
- 不修改原始音乐文件
- 不删除原始音乐文件
- MPD 继续使用现有音乐路径
- Music Server 维护文件路径与 MPD song identifier 的映射

### 7.1 扫描机制

使用两层机制：

1. 文件系统事件监测
2. 定时完整校准扫描

文件系统事件需要 debounce / batch，避免大量文件连续变化导致重复扫描。

默认完整校准间隔：

`12 小时`

该值可配置。

同时保留手动扫描接口。

扫描完成后：

- 更新 SQLite
- 必要时触发 MPD 曲库更新
- 通过 WebSocket 通知客户端曲库发生变化

## 8. 数据库

首期使用 SQLite。

建议至少覆盖：

- songs
- albums
- artists
- tags
- playlists
- playlist_items
- favorites
- history
- queue / playback state
- 配置或必要的系统状态

实际表结构以实现阶段的详细数据模型为准，但必须保持前述三个设计章节定义的实体和状态边界。

### 8.1 SQLite 可靠性

必须：

- 使用事务
- 明确写操作边界
- 避免多个后台任务无序并发写数据库
- 对关键状态更新进行串行化
- 对数据库启动进行结构检查

SQLite 文件必须位于持久化目录，而不是容器临时层。

## 9. 开发环境

开发环境使用独立：

`deploy/docker-compose.dev.yml`

开发环境：

- 源码挂载
- FastAPI hot reload
- Vite 即时更新
- 独立开发数据库
- 独立配置
- 独立备份目录
- 默认使用 Mock MPD

开发环境的数据不得与生产环境共享。

### 9.1 Mock MPD

Mock MPD 与真实 MPD 使用同一个 Adapter 接口。

Mock MPD 用于：

- 服务端单元测试
- API 测试
- Queue 测试
- AutoPlay 测试
- 播放状态同步测试
- 前端联调

需要真实音频播放时，再切换到群晖真实 MPD。

## 10. 生产 Docker 部署

生产使用：

`deploy/docker-compose.yml`

正式容器：

- 使用预构建镜像
- 持久化挂载 SQLite
- 持久化挂载配置
- 持久化挂载备份
- 只读挂载音乐目录
- 配置 healthcheck
- 配置日志轮转

容器重建不得导致：

- 数据库丢失
- 配置丢失
- 备份丢失

音乐文件完全位于宿主机，不属于容器生命周期。

## 11. 配置

支持：

1. 配置文件
2. 环境变量

主要配置包括：

- MPD host
- MPD port
- MPD password
- 音乐目录映射
- SQLite 路径
- 备份目录
- 曲库校准间隔
- Web/API 基础配置

修改配置后按需要重启容器。

首期不开发“编辑所有服务端参数”的 Web 管理后台。

MPD 运行时控制，例如 random、repeat、volume、update database、output 等，提供 API；静态配置仍通过部署配置管理。

## 12. WebSocket 与状态恢复

WebSocket 是实时状态同步通道。

服务端在状态发生关键变化时广播，例如：

- 当前歌曲变化
- 播放/暂停/停止
- 播放进度
- Queue 变化
- History 变化
- Playlist 变化
- Output 状态变化
- 曲库扫描完成

客户端断线后自动重连。

重连成功后不能只依赖遗漏的增量事件，而必须重新获取完整当前状态，以恢复：

- 当前歌曲
- 播放状态
- 播放位置
- Queue
- History 可用状态
- Output
- 必要的 Library/Playlist 状态

## 13. Output Manager

首期定义：

- `NAS_DAC`
- `CLIENT_STREAM`

输出状态至少支持：

- `UNAVAILABLE`
- `INACTIVE`
- `PREPARING`
- `ACTIVE`
- `SWITCH_FAILED`

切换输出模式默认保留：

- 当前歌曲
- Queue
- Playback Context
- 尽可能准确的播放位置

Output Manager 不直接暴露 MPD 内部细节给 Web 客户端。

## 14. 关于页与 MPD 信息

服务端可以提供 MPD 信息 API。

内容参照现有 myMPD 的信息维度：

- MPD 版本
- 运行时间
- 歌曲数量
- 专辑数量
- 艺术家数量
- 曲库总时长
- 曲库更新时间
- 累计播放时长
- MPD 连接状态

不首期实现 NAS CPU、内存、磁盘等复杂系统监控。

## 15. SQLite 备份与恢复

自动备份：

- 每日一次
- 保留最近 7 份

同时提供：

- 手动备份
- 手动恢复

恢复前必须：

1. 校验备份文件可读取
2. 校验 SQLite 完整性
3. 校验数据库结构
4. 停止或隔离正在写入数据库的业务
5. 执行恢复
6. 重新启动服务
7. 进行健康检查

备份目录与当前数据库目录分离。

备份内容：

- SQLite 数据库
- 服务端配置文件

不备份音乐文件。

配置可能包含 MPD 密码，因此备份文件必须限制访问权限。

## 16. GitHub 代码管理

GitHub 仓库：

`qyxx2/MPD-Server`

GitHub 是唯一正式代码源。

手机是主要开发环境；群晖主要承担：

- 拉取正式代码
- 构建/部署
- 真实 MPD 联调
- USB DAC 实机验收

群晖不作为源码的主要编辑环境。

### 16.1 分支策略

```
main
├── feature/*
├── fix/*
└── refactor/*
```

规则：

- `main` = 可部署稳定分支
- 新功能在 `feature/*`
- Bug 修复在 `fix/*`
- 必要的内部重构在 `refactor/*`
- NAS 默认只部署 `main`
- 不直接在 NAS 修改源码

手机开发完成后：

`修改 → 本地测试 → commit → push → 合并 main`

然后 NAS：

`git pull → 构建 → compose up -d → healthcheck → 实机验收`

### 16.2 Commit

Commit 应保持小而明确，例如：

- `feat: add queue reorder API`
- `fix: restore playback state after websocket reconnect`
- `refactor: isolate mpd adapter`
- `docs: update deployment specification`

不要把多个互不相关的修改压成一个巨大 commit。

### 16.3 Tag

稳定版本使用 Git Tag：

- `v0.1.0`
- `v0.1.1`
- `v0.2.0`

Tag 表示可复现的稳定版本。

正式发布后，Docker 镜像可以使用对应版本 Tag。

Tag 是回滚的主要依据之一。

## 17. NAS 一键更新

生产环境提供：

`deploy/update.sh`

目标是把 NAS 上的部署过程固定成：

```
检查工作区
↓
git fetch
↓
确认目标 main
↓
git pull
↓
构建镜像
↓
docker compose up -d
↓
healthcheck
↓
输出部署结果
```

脚本必须在以下情况下停止，而不是继续部署：

- 本地工作区存在未提交修改
- Git pull 失败
- Docker build 失败
- Compose 启动失败
- healthcheck 失败

部署脚本不允许自动覆盖 NAS 上的本地源码修改。

回滚优先使用 Git Tag 或已知稳定 commit：

```
git checkout <stable-tag>
docker compose build
docker compose up -d
```

生产部署与代码编辑严格分离。

## 18. 发布流程

首期采用人工发布：

### 开发

```
手机
→ feature/*
→ 本地测试
→ commit
→ push
```

### 合并

```
feature/*
→ main
```

### NAS

```
git pull main
→ docker build
→ docker compose up -d
→ healthcheck
→ 真实 MPD / USB DAC 验收
```

### 稳定版本

```
main
→ Git Tag
→ 稳定版本
```

首期不启用 GitHub Actions 自动部署。

未来如果项目稳定，可增加：

- GitHub Actions
- 自动测试
- Docker 镜像构建
- GitHub Container Registry
- Tag 自动发布

这些不属于首期实现范围。

## 19. 测试体系

首期测试分四层。

### 19.1 Server Unit Tests

覆盖：

- Queue
- AutoPlay
- Playlist
- Favorites
- History
- Library
- Output Manager
- Repository
- 状态转换

### 19.2 API Tests

验证：

- REST API
- 参数校验
- 错误响应
- WebSocket
- 状态广播
- 重连后的完整状态恢复

### 19.3 Mock MPD Integration Tests

使用 Mock MPD 验证：

- Music Server 与播放 Adapter 的协议边界
- play/pause/stop
- next/previous
- seek
- Queue 同步
- 播放状态同步
- MPD 异常处理

### 19.4 Real MPD Acceptance

真实 MPD 0.23.5 只做手动验收：

- 实际播放
- DAC 输出
- 输出切换
- 曲库更新
- 长时间运行
- WebSocket 重连
- NAS 重启后的恢复

首期不做复杂浏览器 E2E。

## 20. 统一开发检查命令

项目最终应提供统一命令入口，例如：

```
make test
make lint
make typecheck
make build
```

或提供等价的脚本命令。

至少覆盖：

- Python 单元测试
- API 测试
- Mock MPD 集成测试
- TypeScript 类型检查
- Web 生产构建

首期不要求 GitHub Actions，但命令结构必须适合未来直接接入 CI。

## 21. 日志与健康检查

服务端必须输出可定位问题的日志，至少区分：

- API
- WebSocket
- Library Scan
- Playback
- MPD Adapter
- Output
- Database
- Backup

生产 Docker 配置需要日志轮转，避免长期运行导致磁盘被日志占满。

Healthcheck 至少能够确认：

1. FastAPI 进程可响应
2. SQLite 可访问
3. 必要情况下 MPD 连接状态可获得

MPD 本身不可用时，Music Server 容器不应因为单纯 MPD 暂时不可达而陷入无法恢复的启动循环；应能够启动并明确报告 MPD `UNAVAILABLE`。

## 22. 安全边界

首期重点：

- Music 目录只读
- SQLite/配置/备份使用持久化目录
- MPD 密码不写入前端
- MPD 只由服务端访问
- 浏览器不直接访问 MPD TCP 端口
- 反向代理 HTTPS 由群晖承担
- WebSocket 使用 HTTPS 环境下的 WSS
- 配置和备份文件限制权限

首期不设计复杂多用户权限系统，除非后续需求明确增加。

## 23. 目录最终形态

```
music-player/
├── server/
│   ├── app/
│   │   ├── api/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── models/
│   │   ├── player/
│   │   └── main.py
│   ├── tests/
│   └── Dockerfile
├── web/
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   ├── services/
│   │   ├── stores/
│   │   ├── styles/
│   │   └── router/
│   ├── public/
│   └── package.json
├── android/
├── deploy/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── .env.example
│   ├── update.sh
│   └── README.md
├── docs/
│   └── superpowers/
│       └── specs/
└── README.md
```

Android 目录首期只保留项目边界，不要求与 Web 同期开发。

## 24. 首期明确不做

以下内容不进入首期实现：

- Kubernetes
- PostgreSQL
- GitHub Actions CI/CD
- GitHub Container Registry 自动发布
- 复杂 Web 管理后台
- 多用户权限体系
- NAS 系统资源监控平台
- Music Server 内嵌 MPD
- Music Server 自动管理 MPD 进程
- 浏览器直接连接 MPD
- 修改/删除原始音乐文件
- 复杂浏览器 E2E
- Android 客户端与 Web 同期实现

这些能力以后可以在不破坏当前接口边界的情况下增加。

## 25. 架构原则

1. **Music Server 是业务权威。**
2. **MPD 是首期播放引擎，而不是整个 Music Server。**
3. **客户端不直接访问 MPD。**
4. **Queue、History、Playlist、Playback Context 保持独立。**
5. **数据库访问必须经过 Repository。**
6. **MPD 访问必须经过 Adapter。**
7. **真实 MPD 与 Mock MPD 使用同一接口。**
8. **开发环境和生产环境数据完全隔离。**
9. **NAS 负责部署和实机验收，不负责日常源码编辑。**
10. **GitHub 保存正式代码历史，main 是默认生产部署来源。**
11. **稳定版本使用 Git Tag 标记。**
12. **所有生产数据必须位于容器之外的持久化目录。**
13. **首期优先保证接口稳定，再增加自动化基础设施。**
