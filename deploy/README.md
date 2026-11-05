# MPD-Server：NAS / Docker 部署

本文件是当前可用部署入口。历史 v0.1 B07 部署卡保留在 [归档](../docs/superpowers/archive/deployment/2026-10-11-v0-1-nas-deploy-card.md)。

## 选择镜像及环境

`.github/workflows/container.yml` 的 `validate` 和 `image` 都成功后，GHCR 会提供 `ghcr.io/qyxx2/mpd-server:sha-<完整commit SHA>`（amd64/arm64）。选择与实际使用分支匹配的**成功**构建，核对 OCI `org.opencontainers.image.revision`，不得只因 SHA 标签存在就宣称 CI 已通过。

复制 `deploy/.env.example` 至 `deploy/.env`（若文件已存在，只补必要项，不覆盖）。填入真实 NAS 的 `MPD_HOST/MPD_PORT`、`MUSIC_DIR`、`MPD_SERVER_DATA_DIR`、`MPD_SERVER_CONFIG_DIR`、`MPD_SERVER_BACKUP_DIR`、`MPD_SERVER_PORT`、`MPD_SERVER_IMAGE`；保留持久 `/data`、`/config` 和数据库。`/music` 必须只读挂载并与 MPD 的相对 URI 对应。MPD 密码不提交 Git；在容器内 `127.0.0.1` 不等于 NAS 主机。

## MPD 硬件音量控制

服务端已提供 MPD 硬件 Mixer 音量查询与控制接口：

- `GET /api/system/hardware-volume`：返回 MPD 确认的音量、目标输出、状态新鲜度及最近一次控制请求。
- `PUT /api/system/hardware-volume`：请求体为 `{"volumePercent": 0..100}`，必须携带 `Idempotency-Key`；只有 MPD 写后状态读回与请求值完全一致才返回成功。
- `/api/state` 与 WebSocket 初始快照包含硬件音量状态；WebSocket 只广播 `hardware_volume` invalidate，客户端收到后重新读取完整状态。

`MPD_HARDWARE_VOLUME_ENABLED` 默认是 `false`。只有在 NAS 本机确认当前唯一选中的 ALSA 输出使用 `mixer_type "hardware"`，且 MPD 当前启用的输出组合符合实例级 `setvol` 控制范围后，才在部署环境中明确设置 `MPD_HARDWARE_VOLUME_ENABLED=true`。不要把 `deploy/.env.example` 的默认值改成开启。

目标 DS920 已核实的 MPD 配置映射为：

```conf
audio_output {
    type           "alsa"
    name           "USB DAC"
    device         "hw:0,0"
    mixer_type     "hardware"
    mixer_device   "hw:0"
    mixer_control  "PCM"
    mixer_index    "0"
}
```

MPD TCP 的 `config` 命令在该 NAS 上仅允许本地客户端，因此服务端不能通过远程 MPD 协议自行验证 `mixer_type`；启用前必须以 NAS 本机实际配置为准。MPD `status.volume` 是 0–100 的逻辑百分比，不是 ALSA 原始声道值或 dB。当前 `setvol` 属于 MPD 实例级控制，不支持按输出 ID 分别调音。该 MPD-backed 路径不要求给容器映射 `/dev/snd`。

生产部署应使用目标分支 CI 成功后生成的 `ghcr.io/qyxx2/mpd-server:sha-<完整commit SHA>` 镜像，并核对镜像 revision 与目标 commit 一致。随后在 NAS 本地部署环境中设置开关并重建服务。不要提交 NAS 本地 `.env`、密码或其它部署凭据。服务端 API 没有在本批次新增身份认证，禁止将未受保护的服务端口直接暴露到公网。

### Compose v2（支持该版本的机器）

```sh
docker compose --env-file deploy/.env -f deploy/docker-compose.yml config
docker compose --env-file deploy/.env -f deploy/docker-compose.yml pull
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --no-build
docker compose --env-file deploy/.env -f deploy/docker-compose.yml ps
docker compose --env-file deploy/.env -f deploy/docker-compose.yml logs --tail=100 server
```

### 群晖旧版 Compose 1.28.5

仓库的 `docs/docker-compose.yml` 是旧版兼容**示例**，含有过期镜像 SHA、局域网地址、输出名称及文件映射，必须先按实际环境改好：

```sh
docker-compose -f docs/docker-compose.yml pull
docker-compose -f docs/docker-compose.yml up -d
docker-compose -f docs/docker-compose.yml ps
docker-compose -f docs/docker-compose.yml logs --tail=100
```

对于 `MPD_CAPABILITIES_PATH`、`OUTPUT_NAME` 等可选项，没有真实文件或唯一匹配的输出时请**省略**，不要赋空字符串。MPD 地址保存后需要重启服务才生效；已有 `/data/mpd-connection.json` 可能覆盖环境中的地址。获取能力证明请看 [根 README](../README.md)，其 probe 会触碰真实 MPD 控制，选择维护窗口。

部署后检查 `/api/health`、`/api/state`、Web、MPD 连接与实际 DAC 输出。**健康接口成功不等于音频播放正常**。切勿把缺乏公网身份认证的服务直接暴露到互联网。

源码构建可用 `docker compose --env-file deploy/.env -f deploy/docker-compose.yml build`，但旧群晖 Compose 可优先使用预构建镜像。不要把 `deploy/docker-compose.dev.yml` 的 Mock 卷与生产数据混用，也不要在生产 DB 上运行测试。

[现行文档索引](../docs/superpowers/README.md) · [性能现状与验收限制](../docs/performance/README.md)
