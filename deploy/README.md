# v0.1 NAS 部署卡（B07）

本卡只覆盖生产构建、同源路由、挂载与手动重启；功能联合验收属于 B08。
本地自动验证不能证明 NAS 容器部署成功。实际目标尚待用户确认。

## 部署前填写

| 项目 | 本轮实际值 |
|---|---|
| NAS 型号 / `uname -m` / Docker Compose 版本 | 待填写 |
| NAS 音乐目录 MUSIC_DIR | 待填写；示例 `/volume1/music` 不是确认值 |
| MPD music_directory 与 MPD_URI_PREFIX | 待填写；同一相对路径必须对应同一文件 |
| MPD_HOST / MPD_PORT / 是否需要密码 | 待填写；不反馈密码 |
| data / config / backups 持久目录 | 待填写；保留已有目录和文件 |
| NAS 对外 HTTP 端口 MPD_SERVER_PORT | 默认 8000；冲突时填写空闲端口 |
| 当前 endpoint/version 对应能力文件 / ALSA output name | 待填写；无证明时控制受限 |

历史能力记录不能代替本次地址、版本、挂载与网络确认。NAS 可以是 x86_64
或 aarch64；在 NAS 原生构建匹配架构的镜像，外部预构建镜像需核对平台。
本机 ARM64 不作为目标 NAS 架构证明。

## 配置与构建

把**包含当前未提交成果**的完整源文件带到 NAS 的独立源码目录；不要仅从
HEAD 克隆并假定包含本轮功能。保留已有生产 data/config/backups，避免覆盖
NAS 现有配置或数据库。普通部署不改动宿主 MPD，也不挂载宿主 `.venv`。

首次部署且 `deploy/.env` 不存在时，复制 `deploy/.env.example` 为
`deploy/.env`，限制文件权限，然后填写真实值。已有 `.env` 只逐项补齐。
密码仅设 MPD_PASSWORD，勿写 JSON、提交 Git 或反馈配置全文。
`compose config` 可能展开密码，只在本机查看，不粘贴完整输出。

生产环境固定 real、单 worker、容器 HTTP `0.0.0.0:8000`；对外端口由
MPD_SERVER_PORT 控制。配置文件是 `/config/config.json`，saved 地址仍为
`/data/mpd-connection.json`，优先于 env/JSON 地址；不迁移或删除旧 saved 文件。
MPD_CAPABILITIES_PATH 是**容器内**文件路径，例如
`/config/mpd-capabilities.json`；OUTPUT_NAME 必须唯一匹配当前 ALSA name/plugin。
两项未使用时在 `.env` 与 shell 中均省略，不能填写空值。Compose 的无值
键透传已设置值，未设置时省略；其实际展开在 NAS `config` 阶段确认。
能力文件需要 endpoint/mpd_version/result envelope 和真实操作证据；不能把
commands 列表、历史裸 JSON 或 Mock 测试变成 verified_operations。
没有证据可启动并如实限制控制，实际能力验证留待 B08，不自动运行副作用探针。

MPD_HOST 用 NAS 在容器网络中可达的地址，IPv6 填裸地址，不加 `[]`。
容器 `127.0.0.1` 指向容器自身，不能代替 NAS MPD；MPD bind、IPv6路由与
防火墙必须从目标容器验证。不自动改 network_mode 或宿主网络设置。
MUSIC_DIR 挂载为 `/music:ro`，MS 和 MPD 使用同一文件树。

在 NAS 仓库根目录依次执行（本轮 agent 未执行）：

```sh
docker compose --env-file deploy/.env -f deploy/docker-compose.yml config
docker compose --env-file deploy/.env -f deploy/docker-compose.yml build
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs --tail=100 server
```

镜像内 Node 22 使用现有 lockfile 执行 npm ci；只 COPY Web 源码与构建配置，
不复制本机 node_modules/dist。镜像内依赖安装是构建步骤，不修改本机依赖。
Web 构建产物 `/web/dist` COPY 到 `/app/web/dist`；FastAPI 从该目录同源提供。
开发 Compose 使用单独 named data/config/music/backups volumes 和 Mock，
不得绑定生产目录；开发和生产是不同 Compose 文件，不叠加使用。

## GitHub CI 镜像部署

`.github/workflows/container.yml` 在 main、feature/**、codex/** 推送与 v* tag
时先运行后端/Web完整回归、Ruff、typecheck与生产build，再发布双架构镜像。
PR只验证，不发布；支持手动触发。使用GitHub自动GITHUB_TOKEN发布到GHCR，
不需要将NAS MPD密码交给CI；Actions固定到具体commit。

镜像引用为 `ghcr.io/qyxx2/mpd-server:sha-<完整commit SHA>`，CI summary还提供
内容digest。CI构建通过后可替代上节NAS本地build；确认拉取权限和平台，然后
把deploy/.env中的MPD_SERVER_IMAGE填成该次成功运行的镜像引用，执行：

```sh
docker compose --env-file deploy/.env -f deploy/docker-compose.yml pull server
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --no-build server
```

GHCR新包可能默认private；若未开放匿名拉取，在NAS本机用具备read:packages
权限的凭据登录ghcr.io，不向agent或日志粘贴凭据。不自动更改包可见性。
CI成功只证明对应commit的验证与amd64/arm64镜像构建发布，不证明NAS路由、
挂载、MPD能力或实机功能；仍需完成下方验收卡。镜像不含本地运行DB/config。

## 最短实机验收 / 反馈卡

1. `ps` 显示运行且 healthy；查看 `/api/health` 为 HTTP 200/status=ok，
   分别记录 ms、mpd、library_sync。MPD unavailable 仍可能 healthy，
   不能把容器健康当成 MPD 控制可用。
2. 手机打开 `http://NAS:端口/library` 并刷新，返回应用 HTML；首页 JS/CSS
   都是当前镜像产物，无 404。未知 `/api/not-a-route` 为 404 JSON，
   `/assets/missing.js` 为 404，不能返回应用 HTML。
3. `/api/state` 为 JSON；浏览器 Network 中同源 `/api/realtime` 完成
   WebSocket 握手且收到真实 snapshot。IPv6 URL 用 `[地址]` 包裹地址，
   与 MPD_HOST 的裸地址表示区分。记录容器内文件可读及对应相对 URI。
4. 在设置页保存用户确认的目标地址，记录 connection 的 active/saved/
   restart_required；保存不热切换。由用户手动执行下方 restart，然后确认
   active 等于 saved、restart_required=false；DB 原歌曲/集合身份仍在，
   config 与 saved 文件仍在持久目录。若不适合切换地址，标 NOT RUN。

```sh
docker compose --env-file deploy/.env -f deploy/docker-compose.yml restart server
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs --tail=100 server
```

反馈：架构/构建 → 容器健康 → REST/WS/深链接/静态资产 → music映射 →
手动重启与 saved/DB/config 持久化，各项填 PASSED / FAILED / NOT RUN。
失败只提供阶段、错误码和脱敏短日志。浏览器独有异常查 console，后端查
Docker logs（json-file 10m×3）。IPv6 切网期间可离线照卡操作，恢复网络后反馈。
物理声音与完整业务验收属于 B08，B07 不据此宣布最终交付完成。
