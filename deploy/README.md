# MPD-Server：NAS / Docker 部署

本文件是当前可用部署入口。历史 v0.1 B07 部署卡保留在 [归档](../docs/superpowers/archive/deployment/2026-10-11-v0-1-nas-deploy-card.md)。

## 选择镜像及环境

`.github/workflows/container.yml` 的 `validate` 和 `image` 都成功后，GHCR 会提供 `ghcr.io/qyxx2/mpd-server:sha-<完整commit SHA>`（amd64/arm64）。选择与实际使用分支匹配的**成功**构建，核对 OCI `org.opencontainers.image.revision`，不得只因 SHA 标签存在就宣称 CI 已通过。

复制 `deploy/.env.example` 至 `deploy/.env`（若文件已存在，只补必要项，不覆盖）。填入真实 NAS 的 `MPD_HOST/MPD_PORT`、`MUSIC_DIR`、`MPD_SERVER_DATA_DIR`、`MPD_SERVER_CONFIG_DIR`、`MPD_SERVER_BACKUP_DIR`、`MPD_SERVER_PORT`、`MPD_SERVER_IMAGE`；保留持久 `/data`、`/config` 和数据库。`/music` 必须只读挂载并与 MPD 的相对 URI 对应。MPD 密码不提交 Git；在容器内 `127.0.0.1` 不等于 NAS 主机。

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

[现行文档索引](../docs/superpowers/README.md) · [性能优化指南](../docs/performance/2026-10-14-v0.2-playback-latency-optimization-guide.md)
