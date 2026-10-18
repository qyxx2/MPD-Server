# MPD-Server

面向局域网和 NAS 的自托管音乐服务器。通过手机或桌面浏览器访问 Web 界面，由服务端连接 [Music Player Daemon (MPD)](https://www.musicpd.org/) 控制播放；音乐音频由 MPD 输出，而不是由浏览器解码播放。

**版本状态：v0.1 为首个基本可用版本；当前开发内容为 v0.2 增量维护。** 原主 Task 路线图及未来 Task 10–12 已退役；以现有代码为基线，按实际需求进行小范围迭代。

## 功能

- **播放器**：显示实际播放/暂停、当前曲目及进度；提供基本播放控制和歌词/音频信息展示。
- **队列**：浏览当前队列、下一首插入、排序与基本管理；Queue、Played 与执行身份以现有规格和实现为准，长队列性能问题另有专项指导。
- **资料库与搜索**：默认浏览全部歌曲，支持标题或文件修改时间正/倒序，“播放全部”沿用所选顺序；另有专辑/艺术家等分类与搜索。后端只读访问音乐文件，支持自动曲库同步和状态通知。
- **播放列表与收藏**：建立和管理播放列表、歌曲收藏。
- **设置与连接**：保存 MPD 连接目标，通过重启服务应用保存的地址；查看连接、输出及基本健康状态。
- **Web**：移动端优先的响应式界面，宽屏横向布局提供常驻播放器与右侧工作区；共享活动入口展示异常、忙碌和普通通知。HTTP API 与 WebSocket 实时同步；当前不包含完整离线 PWA 安装体验。

技术架构：`Vue 3 / Vite → FastAPI / WebSocket → Service / PlayerPort → MPD`，元数据及业务记录使用 SQLite。

## v0.2 实现与验收状态

当前分支已包含 Played occurrence 映射修复、Song 批量读取、提交后通知及完整样本复用、Observer 唤醒、后台锁外采样、最终确认交接和受控 MPD ID 播放。MPD 共享连接还启用了可回退的歌曲标签过滤；完整队列、身份和异常安全校验仍保留。

- [播放性能现状](docs/performance/README.md)：优化已有实现与阶段实测；B8 的短队列端到端无明显退化门槛仍未通过，原整体性能验收为 PARTIAL，已随计划归档，不能宣称延迟已解决。
- [横屏历史验收](docs/superpowers/archive/responsive-landscape/2026-10-16-responsive-landscape-B5-acceptance.md)：B1–B4 已有用户确认，B5 原记录保留最终 HUMAN/PWA PENDING；计划与验收现已归档，不再作为待办。后续透明样式及播放全部排序变更，以当前源码和测试为准。
- 全部实施计划、阶段验收与旧路线图已按用户要求移入[历史归档](docs/superpowers/archive/README.md)；现行目录保留规格书、重要入口和部署说明，后续只按新需求立项。历史未通过或未执行项不因归档改记为通过。

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


### 生成 `mpd-capabilities.json`

在能直接连接目标 MPD 的仓库环境中运行；`SONG_URI` 使用 MPD 曲库中真实存在的一首歌的**相对 URI**：

```sh
export MPD_HOST=192.168.3.94 MPD_PORT=6600 SONG_URI='Artist/Album/song.flac'
mkdir -p deploy/config

.venv/bin/python -m server.app.player.capabilities \
  --host "$MPD_HOST" --port "$MPD_PORT" \
  --probe-transport --probe-song-uri "$SONG_URI" \
  > /tmp/mpd-capabilities-result.json

.venv/bin/python -c 'import json,os; r=json.load(open("/tmp/mpd-capabilities-result.json")); json.dump({"endpoint":{"host":os.environ["MPD_HOST"],"port":int(os.environ["MPD_PORT"])},"mpd_version":r["version"],"result":r},open("deploy/config/mpd-capabilities.json","w"),ensure_ascii=False,indent=2)'
```

生成后将该文件挂载到容器的 `/config/mpd-capabilities.json`，并设置 `MPD_CAPABILITIES_PATH=/config/mpd-capabilities.json`。能力探测会临时执行 Queue / Output 等真实 MPD 操作并尝试恢复原状态，应在允许短暂改变播放状态时运行；不要把其他 MPD 地址生成的旧文件直接复用到当前目标。

## 开发及验证

```sh
# 使用已有虚拟环境；临时数据目录避免触及已有数据库和配置。
task_test_dir=$(mktemp -d)
mkdir -p "$task_test_dir/config" "$task_test_dir/music"
DATABASE_PATH="$task_test_dir/test.db" CONFIG_DIR="$task_test_dir/config" \
  MUSIC_ROOT="$task_test_dir/music" APP_ENV=production MPD_MODE=real \
  MPD_HOST=127.0.0.1 MPD_PORT=9 .venv/bin/python -m pytest -q server/tests
.venv/bin/python -m ruff check server/app server/tests
npm --prefix web run test -- --run --maxWorkers=1 --minWorkers=1
npm --prefix web run typecheck
npm --prefix web run build
```

CI/镜像基线：Python 3.13 / FastAPI、Node 22 / Vue 3；本地使用已有工具环境。生产镜像定义在 `deploy/Dockerfile`。运行自动测试时为 `DATABASE_PATH` 使用隔离临时目录，避免触及生产数据库。CI 在推送到 main/功能分支及版本 tag 时验证后端、前端、类型检查和生产构建，并在非 PR 事件发布 GHCR 多架构镜像。

## v0.1 边界与安全

- 局域网自用为主要场景；目前未提供对公网暴露所需的完整身份认证和安全边界，**不要直接暴露到公网**。
- 音乐根目录按只读方式挂载，业务数据和持久化配置另存。
- MPD 是实际播放状态的来源，应用编排队列和业务状态；连接断开、控制目标丢失等异常会限制部分操作。
- 离线 PWA、客户端串流、原 Task 10–12 等不再作为自动推进的既定路线图；只有新需求明确授权才单独评估。
- Task 9 的历史自动及人工 Gate 与未关闭项见 [Task 9 final acceptance](docs/superpowers/archive/task-9/2026-10-11-task-9-final-acceptance.md)。后续修复证据在 `docs/superpowers/archive/task-9/`；不要将自动测试结果误写为实机验收通过。

## 文档与源码

- `server/`：后端 API、业务服务、MPD Adapter、SQLite；`web/`：Web UI；`deploy/`：部署与配置。
- [现行文档索引](docs/superpowers/README.md)：保留必要架构、领域规格、视觉合同与环境证据。
- [v0.2 播放性能现状](docs/performance/README.md)：已实现机制、阶段实测、B8 未闭合门槛和历史依据。
- [历史归档](docs/superpowers/archive/README.md)：旧 Task 主 Plan、验收、历史研究与退役路线图，保留用于追溯，不再是开发待办。

今后的迭代从实际检出的代码、测试、部署镜像及明确需求重新立项，不自动执行旧 Task 或未关闭 Gate。
