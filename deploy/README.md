# MPD-Server：NAS / Docker 部署

本文件是当前可用部署入口。历史 v0.1 B07 部署卡保留在 [归档](../docs/superpowers/archive/deployment/2026-10-11-v0-1-nas-deploy-card.md)。

## 选择镜像及环境

`.github/workflows/container.yml` 的 `validate` 和 `image` 都成功后，GHCR 会提供 `ghcr.io/qyxx2/mpd-server:sha-<完整commit SHA>`（amd64/arm64）。选择与实际使用分支匹配的**成功**构建，核对 OCI `org.opencontainers.image.revision`，不得只因 SHA 标签存在就宣称 CI 已通过。

复制 `deploy/.env.example` 至 `deploy/.env`（若文件已存在，只补必要项，不覆盖）。填入真实 NAS 的 `MPD_HOST/MPD_PORT`、`MUSIC_DIR`、`MPD_SERVER_DATA_DIR`、`MPD_SERVER_CONFIG_DIR`、`MPD_SERVER_BACKUP_DIR`、`MPD_SERVER_PORT`、`MPD_SERVER_IMAGE`；保留持久 `/data`、`/config` 和数据库。`/music` 必须只读挂载并与 MPD 的相对 URI 对应。MPD 密码不提交 Git；在容器内 `127.0.0.1` 不等于 NAS 主机。

## MPD 硬件音量控制前置条件

`MPD_HARDWARE_VOLUME_ENABLED` 默认是 `false`。本开关仅供后续硬件音量 API 实现启用前使用；当前阶段不要提前设置为 `true`。正式启用前，必须在 NAS 本机检查实际生效的 MPD `audio_output` 配置，确认选中的 ALSA 输出使用硬件 Mixer，而非软件音量：

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

以上是目标 DS920 当前已实测的配置映射（USB DAC / ALSA / PCM）。MPD TCP 的 `config` 命令在该 NAS 上仅允许本地客户端，因此 Music Server 无法通过远程 MPD 协议自行验证 `mixer_type`；必须以 NAS 本机实际配置为准。实机已验证 MPD `setvol` 后 `status.volume` 读回变化，并且 ALSA `PCM Playback Volume` 左右声道原始值同步变化。

确认新版本服务端已包含硬件音量控制实现、选中的输出及 Mixer 配置正确后，才可在本机 `deploy/.env` 中设置 `MPD_HARDWARE_VOLUME_ENABLED=true` 并重建/重启服务。该控制映射到 MPD 实例级 `setvol`，不是按输出 ID 隔离的多输出音量控制；启用前须确认 MPD 的启用输出组合符合这一作用范围。此功能不要求给容器映射 `/dev/snd`。

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
