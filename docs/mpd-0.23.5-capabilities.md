# MPD 0.23.5 Capability Record

## 状态

**部分实测，完整 Step 7 验收仍待执行。**

已确认的目标环境：

- Synology DS920
- DSM 7.1.1
- MPD TCP：192.168.3.94:6600
- TCP greeting：`OK MPD 0.23.5`
- `commands` 可正常返回完整命令列表并以 `OK` 结束。
- `status` 已取得真实字段样本。
- 未知命令 `__mpd_server_unsupported_probe__` 在真实 MPD 0.23.5 上会直接关闭 TCP 连接，不返回 ACK。

本文件只记录已经取得的真实数据；尚未取得的数据保持未填写，不根据 MPD 文档或其它版本猜测。


目标环境按项目规格固定为 **MPD 0.23.5**。实际记录必须来自目标群晖上的 MPD 进程，而不是根据新版本文档推断。

## 探针设计

### 主连接

主连接依次获取：

```text
commands
notcommands
status
outputs
stats
update "__mpd_server_capability_probe__"
```

`commands` 表示当前用户可访问的命令集合。

`notcommands` 只表示当前用户没有权限访问的命令，不用于判断 MPD 是否实现了某个命令；探针将其独立记录为 `not_commands`。

### 负向探测连接隔离

未知命令不再使用主连接探测。真实 MPD 0.23.5 已实测会因 `__mpd_server_unsupported_probe__` 关闭 TCP，因此该测试在独立的新连接上执行。

若读取到 EOF：

- 记录 `outcome: connection_closed`
- 保留原命令
- `error_code` 和 `command_list_index` 保持 `null`
- 关闭该失效连接
- 再建立新连接继续后续探测

这样真实 connection-close 行为不会导致整个 capability probe 崩溃，也不会被伪装成 ACK。

### ACK error 探测

为覆盖正常 MPD ACK error 路径，探针在另一条新连接上发送：

```text
playid 2147483647
```

实际返回内容完全以目标 MPD 为准。若返回 ACK，记录：

- `outcome: ack`
- `error_code`
- `command_list_index`
- `message`

若目标 MPD 对该负向请求关闭连接，则同样记录真实 connection outcome。

### Error outcome

`ProbeError.outcome` 区分：

- `ack`
- `connection_closed`
- `timeout`
- `communication_error`
- `connection_error`

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

### MPD version

直接连接：

```text
OK MPD 0.23.5
```

版本按真实 greeting 记录为 `0.23.5`；不额外推断 daemon 的其它版本元数据。

### Commands

真实 NAS 已执行：

```text
commands
```

返回完整命令集合并以：

```text
OK
```

结束。

已在实测输出中确认至少包含：

```text
add
addid
albumart
currentsong
next
notcommands
outputs
pause
play
playid
playlistinfo
previous
random
seek
seekcur
setvol
stats
status
stop
update
volume
```

完整 commands 清单应以最终 capability probe JSON 为准；当前对话中未保存完整原始清单，因此不补写未实际取得的命令。

### Status fields

真实 NAS 已执行：

```text
status
```

实际样本：

```text
volume: 100
repeat: 0
random: 0
single: 0
consume: 1
partition: default
playlist: 2
playlistlength: 1
mixrampdb: 0
state: pause
song: 0
songid: 1
time: 187:240
elapsed: 187.481
bitrate: 0
duration: 240.386
audio: 44100:16:2
```

当前已直接取得的 status 字段：

```text
volume
repeat
random
single
consume
partition
playlist
playlistlength
mixrampdb
state
song
songid
time
elapsed
bitrate
duration
audio
```

### Outputs

**尚未取得最终 probe 的真实 `outputs` 返回，本文件不填充猜测值。**

待最终 probe 记录：

- `outputid`
- `outputname`
- `plugin`
- `outputenabled`
- 所有实际 `attribute` 行

### Stats

**尚未取得最终 probe 的真实 `stats` 返回，本文件不填充猜测值。**

### Update behavior

当前 probe 使用默认探针路径：

```text
__mpd_server_capability_probe__
```

该 URI 应保持不存在，以避免命中真实音乐文件或目录。

probe 只记录 `update` 的立即返回值或 ACK；不等待整个数据库更新任务完成，避免能力探针承担长时间库同步工作。

**尚未取得最终 NAS probe 的真实 `update` 返回，本文件不填充猜测值。**

### Errors

真实 NAS 已直接验证：

```text
__mpd_server_unsupported_probe__
```

实际收到：

```text
b''
```

即服务端关闭 TCP 连接，没有 ACK。

这不是网络超时，也不是普通 `MPDAckError`。

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
