# MPD 0.23.5 Capability Record

## 状态

**已完成真实 NAS 验收。**

已确认的目标环境：

- Synology DS920
- DSM 7.1.1
- MPD TCP：192.168.3.94:6600
- TCP greeting：`OK MPD 0.23.5`
- `commands` 可正常返回完整命令列表并以 `OK` 结束。
- `status` 已取得真实字段样本。
- 未知命令 `__mpd_server_unsupported_probe__` 在真实 MPD 0.23.5 上会直接关闭 TCP 连接，不返回 ACK。

本文件只记录实际 NAS probe 取得的数据，不根据 MPD 文档或其它版本补填运行时结果。


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

### 运行环境与时间

- NAS：Synology DS920
- DSM：7.1.1
- MPD TCP：192.168.3.94:6600
- Probe JSON 文件：`mpd-0.23.5-probe-2026-09-26-091948.json`
- 实测时间：2026-09-26 09:19:48（按 probe 文件时间命名记录）

### MPD version

Greeting：

```text
OK MPD 0.23.5
```

实测版本：`0.23.5`。

### Commands

实际执行：

```text
commands
```

MPD 返回完整命令集合并以 `OK` 结束。

本次 probe 返回的完整命令集合为：

```text
add
addid
addtagid
albumart
binarylimit
channels
clear
clearerror
cleartagid
close
commands
config
consume
count
crossfade
currentsong
decoders
delete
deleteid
delpartition
disableoutput
enableoutput
find
findadd
getvol
idle
kill
list
listall
listallinfo
listfiles
listmounts
listpartitions
listplaylist
listplaylistinfo
listplaylists
load
lsinfo
mixrampdb
mixrampdelay
mount
move
moveid
moveoutput
newpartition
next
notcommands
outputs
outputset
partition
password
pause
ping
play
playid
playlist
playlistadd
playlistclear
playlistdelete
playlistfind
playlistid
playlistinfo
playlistmove
playlistsearch
plchanges
plchangesposid
previous
prio
prioid
random
rangeid
readcomments
readmessages
readpicture
rename
repeat
replay_gain_mode
replay_gain_status
rescan
rm
save
search
searchadd
searchaddpl
seek
seekcur
seekid
sendmessage
setvol
shuffle
single
stats
status
sticker
stop
subscribe
swap
swapid
tagtypes
toggleoutput
unsubscribe
update
urlhandlers
volume
```

共 104 个命令。

其中与当前 PlayerPort / Adapter 直接相关的命令均出现在真实 `commands` 返回中，包括：

```text
currentsong
next
outputs
pause
play
playid
playlistinfo
previous
random
seekcur
setvol
stats
status
stop
update
```

另有 `notcommands: []`，因此本次 MPD 连接用户没有被 `notcommands` 列出额外受限命令。

### Status fields

本次 probe 实际得到：

```text
audio
bitrate
consume
duration
elapsed
mixrampdb
partition
playlist
playlistlength
random
repeat
single
song
songid
state
time
volume
```

共 17 个字段。

注意：本次 capability probe 记录的是字段集合，不把字段值复制为固定能力数据；运行时值仍应通过 Adapter 的 `status` 实际读取。

### Outputs

本次实际 `outputs` 返回两个输出：

| outputid | outputname | plugin | enabled | attributes |
|---:|---|---|---|---|
| 0 | USB DAC | alsa | true | `allowed_formats=""`, `dop="0"` |
| 1 | HTTP Stream (port 6680) | httpd | false | 空 |

因此目标 NAS 当前实际暴露：

- NAS USB DAC 的 MPD ALSA 输出：已启用。
- HTTPD 输出：已配置但当前未启用。

这里只记录 MPD 返回的输出属性，不据此推断 HTTP 串流功能的完整可用性或音频格式能力。

### Stats

本次实际 `stats` 返回：

```text
albums: 344
artists: 264
db_playtime: 103730
db_update: 1786802874
playtime: 0
songs: 403
uptime: 59917
```

原始值按 MPD 返回记录，不对 `db_update` 的时间戳或其它统计值做额外解释。

### Update behavior

本次 probe 使用：

```text
update "__mpd_server_capability_probe__"
```

实际立即返回：

```text
updating_db: 2
```

因此可以确认当前 MPD 0.23.5 接受该 `update` 请求，并返回数据库更新 Job ID `2`。

Probe 只记录立即响应，没有等待该 Job 完成，因此本次结果**不能**据此宣称数据库更新已经完成，也不把它解释为完整扫描耗时或最终更新状态。

探针路径应保持为不会命中真实音乐文件的不存在 URI，以避免改变实际媒体内容；本次 probe 未对音乐文件执行写操作。

### Errors

本次实际取得两种不同错误行为。

#### 1. 未知命令导致连接关闭

发送：

```text
__mpd_server_unsupported_probe__
```

实际结果：

```text
outcome: connection_closed
error_code: null
command_list_index: null
message: MPD closed the connection
```

这确认真实 MPD 0.23.5 对该未知命令关闭 TCP 连接，而不是返回 ACK。

#### 2. 普通 ACK error

发送：

```text
playid 2147483647
```

实际结果：

```text
outcome: ack
error_code: 50
command_list_index: 0
message: No such song
```

因此当前 probe 可以同时区分：

- 正常 MPD ACK error；
- 服务端直接关闭连接。

### Step 7 验收结论

本次真实 NAS probe 已完整取得并记录：

- MPD version
- 完整 commands
- status fields
- outputs
- stats
- update immediate response
- ACK error
- unknown-command connection close

代码层也已实现与真实行为对应的隔离探测和断线恢复：未知命令不会使整个 capability probe 崩溃，后续探测可以使用新的 TCP 连接继续完成。

## 服务能力边界

后续服务层不应直接把“MPD 协议文档里存在”当成“当前环境已验证”。Task1 提供 `VerifiedPlayerPort`，由 capability probe 得到的 `MPDCapabilities` 作为服务层访问 PlayerPort 的能力边界：

- 未在目标 MPD `commands` 中验证的操作直接拒绝。
- 按歌曲 URI 播放需要同时验证 `playlistinfo` 与 `playid`。
- 状态读取同时要求 `status` 与 `currentsong`，与现有 Adapter 的实现一致。
- 更新、输出、音量、随机、重复等运行时操作分别按各自 MPD 命令验证。
- 能力拒绝转换为 typed `PlayerCommandError`，不会调用底层 PlayerPort。

这只建立能力边界，不提前实现 Task2 及后续 Service。
