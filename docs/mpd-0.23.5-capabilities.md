# MPD 0.23.5 Capability Record

## 状态

**待实际 NAS 实测。**

当前实现环境没有到用户群晖 LAN 内 MPD TCP 端口的网络通道，因此本文件不伪造实际 NAS 的探针结果。仓库已加入可重复执行的 capability probe，并用 fake TCP MPD 对探针流程进行了自动测试。

目标环境按项目规格固定为 **MPD 0.23.5**。实际记录必须来自目标群晖上的 MPD 进程，而不是根据新版本文档推断。

## 探针内容

探针连接目标 MPD TCP 服务后记录：

| 项目 | 记录内容 |
|---|---|
| MPD version | greeting 中的版本 |
| Commands | `commands` 返回的命令集合 |
| Status fields | `status` 实际返回的字段名 |
| Outputs | `outputs` 返回的 OutputID、名称、插件、启用状态及属性 |
| Stats | `stats` 返回的曲库/更新/播放统计字段 |
| Update behavior | 使用指定的探针路径调用 `update`，记录立即返回内容或 ACK 错误 |
| Errors | 额外发送一个不存在的命令，记录 MPD ACK 错误格式 |

探针路径默认：

`__mpd_server_capability_probe__`

建议实际执行时保持该路径不存在，以避免扫描真实音乐目录。该调用仍可能触发 MPD 的数据库更新调度，因此应在可接受的维护窗口执行。

## 执行命令

在能够访问群晖 MPD 6600/TCP 的环境执行：

```text
PYTHONPATH=. python -m server.app.player.capabilities \
  --host <NAS_LAN_IP> \
  --port 6600 \
  [--password <MPD_PASSWORD>]
```

将命令输出的 JSON 作为实际验收记录保存到本文件的“实测结果”章节。

## 实测结果

当前没有可验证的 NAS 实测数据，因此这里保持空白，不填写猜测值。

待拿到真实结果后至少补充：

- 实际 MPD version。
- `commands` 中与 PlayerPort 对应的命令。
- `status` 字段。
- 实际输出设备及其属性。
- `update` 的返回形式、更新状态行为及错误。
- 代表性的 MPD ACK 错误。

## 服务能力边界

后续服务层不应直接把“MPD 协议文档里存在”当成“当前环境已验证”。Task1 提供 `VerifiedPlayerPort`，由 capability probe 得到的 `MPDCapabilities` 作为服务层访问 PlayerPort 的能力边界：

- 未在目标 MPD `commands` 中验证的操作直接拒绝。
- 按歌曲 URI 播放需要同时验证 `playlistinfo` 与 `playid`。
- 状态读取同时要求 `status` 与 `currentsong`，与现有 Adapter 的实现一致。
- 更新、输出、音量、随机、重复等运行时操作分别按各自 MPD 命令验证。
- 能力拒绝转换为 typed `PlayerCommandError`，不会调用底层 PlayerPort。

这只建立能力边界，不提前实现 Task2 及后续 Service。
