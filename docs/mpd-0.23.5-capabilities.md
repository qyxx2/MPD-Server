# MPD 0.23.5 Capability Record

## 状态

**历史基础 probe 已完成真实 NAS 验收；D6 S11目标功能与S12联合门禁已通过（2026-10-09）。最新范围为现有NAS daemon0.23.17 / 套件0.23.17-3 / 协议0.23.5；不冒称精确daemon0.23.5或源码原版认证。最新结论见文末S11/S12，Task12物理DAC等另行验收。**

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
- Probe JSON 文件：[原始记录](/home/Gold/Downloads/mpd-0.23.5-probe-2026-09-26-091948.json)（机器本地来源，不复制进仓库）。
- 2026-10-04 只读核对 SHA-256：`6c4036572314b38d822481c28fa25652bab29a26ab8ec6e74a076cbe815d0d40`；105 commands、17 status_fields，与下列数据逐项核对。此 JSON **没有 verified_operations 字段**，不能用作第二轮 transport 原始证据。
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
unmount
unsubscribe
update
urlhandlers
volume
```

共 105 个命令（2026-10-04 对照原始 JSON 纠正，旧摘录遗漏 `unmount`）。

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

### Task1R 运行时 Transport 验证（2026-09-27）

> 以下为既有第二轮验收摘录，保留其历史结论；2026-10-04 未取得该轮原始 JSON。新取得的 2026-09-26 JSON 不支持复核这里的九项 verified_operations。本次没有重新运行 probe，也不新增运行时结论。

本次在真实 NAS 环境重新执行：

```text
docker run --rm --network host mpd-server:latest \
  python -m server.app.player.capabilities \
  --host 192.168.3.94 \
  --port 6600 \
  --probe-transport
```

实测结果：

- MPD version：`0.23.5`
- `verified_operations`：

```text
database_update_status
queue_add
queue_clear
queue_delete
queue_entries
queue_move
queue_play
set_output_enabled
stats
```

以上 9 项全部进入真实 probe 的 `verified_operations`，因此 Task1R Step3 要求的 Queue、Output、Stats、Database Update Status runtime behavior 均已在目标 MPD 0.23.5 上得到验证。

#### Error 结果判定

本次 JSON 中仍有两个 `errors`，但两者均属于本探针设计明确允许并要求记录的负向行为：

1. `__mpd_server_unsupported_probe__`

```text
outcome: connection_closed
error_code: null
message: MPD closed the connection
```

这是独立连接上的未知命令探测。真实 MPD 0.23.5 实测会关闭 TCP 连接；探针将其记录后断开该失效连接并继续后续验证。这正是当前 capability record 所定义的预期行为，不代表 Queue/Output/Stats capability 验证失败。

2. `playid 2147483647`

```text
outcome: ack
error_code: 50
command_list_index: 0
message: No such song
```

这是独立连接上的 ACK error 负向探测。目标 MPD 返回标准 ACK，错误码和消息被原样记录。这同样是探针预期的错误响应覆盖，不代表 `queue_play` capability 验证失败；`queue_play` 已进入 `verified_operations`。

本次 probe 没有报告 `transport_restore` 错误；探针的 Queue/output 修改路径仍按实现中的 cleanup 逻辑执行恢复。

因此，本次真实验证结果与 Task1R Step3 的设计边界一致，Step3 可标记完成。

## 服务能力边界

后续服务层不应直接把“MPD 协议文档里存在”当成“当前环境已验证”。Task1 提供 `VerifiedPlayerPort`，由 capability probe 得到的 `MPDCapabilities` 作为服务层访问 PlayerPort 的能力边界：

- 未在目标 MPD `commands` 中验证的操作直接拒绝。
- 按歌曲 URI 播放需要同时验证 `playlistinfo` 与 `playid`。
- 状态读取同时要求 `status` 与 `currentsong`，与现有 Adapter 的实现一致。
- 更新、输出、音量、随机、重复等运行时操作分别按各自 MPD 命令验证。
- 能力拒绝转换为 typed `PlayerCommandError`，不会调用底层 PlayerPort。

这只建立能力边界，不提前实现 Task2 及后续 Service。

## D6 S11 目标运行时验收尝试（2026-10-08）

本节只记录本次新事实，不改写 2026-09-26 基础 probe 或 2026-09-27 Task1R 历史范围。本次计划验证顺序模式、current ID/position/version、受控预同步及运行时错误边界；这些能力不能由旧 commands、旧九项摘录或本地协议模拟推出。

执行主机尝试以 Python socket 连接本文权威目标 `192.168.3.94:6600`。实际在 TCP greeting 前得到：

```text
OSError: [Errno 101] Network is unreachable
```

因此本次没有目标 greeting、版本/build、`status`、`playlistinfo`、`outputs` 或其它原始 MPD 响应，也没有发送任何 MPD application command。由于无法先取得并核对原队列、模式、状态和输出备份，没有安全进入队列/播放/seek/Stop/断线/重启故障场景；没有目标 mutation，也没有恢复动作。

以下 D6 S11 能力全部 **NOT VERIFIED**：

- 重复 URI 不同 MPD ID 及 current `songid`/position/version 对应关系；
- 正常 A→B、单次 A→C 与预同步 B 的目标事实；
- 已离开 entry 的 move/delete 后 ID 保留和 position 变化；
- Stop 后不重启；
- service/MPD disconnect/restart 后旧绑定失效；
- error/响应丢失边界及不盲重发；
- 原队列、模式、状态、输出的备份与恢复核对。

结论：历史基础 probe 结论不变，但 D6 S11 目标运行时能力门禁仍 **BLOCKED**。需要从能访问 NAS LAN 的执行环境重新取得本次原始响应后，才能更新这些能力状态。

### D6 S11 网络恢复后的目标实测（2026-10-08）

更换网络环境后，目标 `192.168.3.94:6600` 可达。每条 raw TCP 连接均返回：

```text
OK MPD 0.23.5
```

机器本地完整 evidence：

```text
.superpowers/sdd/2026-10-04-task-4-d6-recovery-corrective-plan/s11-live-result.json
SHA-256: 1a3cd797102ae1d350119075f2ed02a6b30bca44fde903f5ede5b28fc678fb4f
```

本次目标原始事实确认：

- 顺序模式 `repeat=0/random=0/single=0/consume=0` 下，重复 URI occurrence 分配不同 ID；正式样本为 A=`Id51/Pos0`、B=`Id52/Pos1`、C=`Id53/Pos2`、playlist version=`133`。
- raw `next` 后 current 从 `Id51/Pos0` 变 `Id52/Pos1`，playlist version 不变；Service 接纳目标且没有发送 `playid B`，但不据此判断离开原因或 natural completion。
- A→C 样本使用 `Id55/56/57`；C current 后 B=`Id56` 保留 pending，永久 History 不增加。
- B=`Id60` 在已离开 A 后从 Pos1 移到 Pos0且 ID 保持；删除 A=`Id59` 后 B/C ID 保持。
- raw Stop 后 runner 不发送播放控制，actual 为 fresh `UNCONFIRMED_STOP`；TCP reconnect 与 Service restart 都清除旧业务 binding、保持业务 Queue/History，并恢复 fresh `UNBOUND` actual。
- `playid 2147483647` 返回 `ACK [50@0] {playid} No such song`，队列前后不变。
- 原始队列/模式/音量/stopped/outputs 已备份并在最终核对恢复；outputs raw 响应不变。MPD clear/add 必然重新分配 ID/version，最终为 `Id71/version186`，不冒充原 `Id18/version49` 已恢复。

本次未修改媒体、曲库、schema 或输出；临时业务数据库随执行删除。USB DAC 虽保持 enabled，但没有做听觉验收。

以下仍 **NOT VERIFIED**：

- NAS package / MPD build hash（greeting 只证明协议版本）；
- 真实 MPD daemon 重启后的队列/ID/version与绑定失效行为；
- 目标链路在命令已发送后丢失响应时的不盲重发行为；
- decoder/输入/物理输出故障下的 `error` 字段与恢复边界。

因此 D6 S11 只能标为 **PARTIALLY VERIFIED / BLOCKED**；旧 commands、旧九项 transport、S10 fake 或本次已通过场景都不能抵扣上述未验证义务。

### D6 S11 补充实测与范围校正（2026-10-08）

上述网络重试的 `next` 是显式外部控制，只证明后来目标接纳。补充轮重新使用真实 NAS、Adapter/VerifiedPort/Service、临时 SQLite 与透明 TCP proxy，取得以下新原始事实（完整记录及逐场景 snapshot 见唯一 D6 acceptance 文末）：

- 完整等待240.386秒歌曲的推进：重复 URI A/B=`Id74/75`，C=`76`；49个 sample 从 A Pos0/elapsed0.842 到 B Pos1/elapsed1.479，playlist version 恒197。准备后至 B 被读取前只有 status/playlistinfo，无 next/playid/seek。只确认无人追加控制时 B 成为 current，不认证自然原因。
- 纯接纳后仅 deleteid74；Queue revision2→3、History0→0；observe 后 actual Id75/Pos0，fresh/CONFIRMED/matches_current=true，精确绑定 B occurrence，无 playid B。
- seekcur237.386 后 A84→B85，version221；seekcur240.386 后 A87→B88，version230。之后只读等待；两例接纳均 revision2→3/History0→0，observe 后分别 Id85/88、Pos0、fresh/CONFIRMED。seek 与 elapsed/duration 不充当原因证据。
- 真 NAS 执行 addid 后返回 `Id: 80`/`OK`，仅此成功响应被测试 proxy 丢弃并关闭测试连接；队列确有 Id80。客户端报连接关闭，业务 Queue/Playback/History/active/session 回滚保留；retry=UNKNOWN/SYNC_FAILED，未产生新控制命令。这只验证本次 addid 丢响应路径，不外推所有命令或声称 SQLite 撤回 MPD 副作用。

新证据都位于本 plan 的 ignored `.superpowers/sdd/2026-10-04-task-4-d6-recovery-corrective-plan/`：

```text
s11-supplement-20261008T142322Z.json
SHA256 4fa32fce43a12256204b3c35477c71ba3eae8fc62870a8b131fc312fc08f0af2
s11-seek-20261008T142746Z.json
SHA256 5114cb64e3c938344a92b9ecf21a5a396760f8a6679a31a15f2659a49b926043
```

两轮均 exit0/finally恢复核对成功；最终原单曲内容/order、modes（consume1，其余0）、volume100、stopped 和 outputs 保持。新分配 Id90/version233，不称恢复原 ID/version；没有修改媒体、曲库、schema 或输出，没有 DAC 听觉验收。

用户提供 DSM 套件名 `mpd`，但尚未取得 NAS 运行 binary 的 --version/features/hash 或套件 build，也没有执行真实 daemon restart。**build 与 daemon restart 仍 NOT VERIFIED**，不因 greeting=0.23.5 即宣称未修改原版。decoder/input/output error 下 D6 暂停控制/保留状态仍 **NOT VERIFIED**；Task12 物理 DAC/发布验收另外处理，不混入已验证项、不删除 D6 错误义务。因此 S11 能力门禁依旧 **PARTIALLY VERIFIED / BLOCKED**，S12 未执行。

### NAS binary 与 endpoint greeting 不一致（2026-10-08，最新身份限制）

用户在 NAS SSH 中执行只读检查，回传 PID2823，exe=`/volume1/@appstore/mpd/bin/mpd`，`--version`=`Music Player Daemon 0.23.17 (699d8b3)`，SHA256=`ff9df851bda831c368bead85aa30e2717f96d057180d405e5c7bfc74367f7ae6`。这属于用户侧原始证据，尚无 6600 监听 PID 的映射。本机于22:48:03（Asia/Shanghai）重新只读连接 `192.168.3.94:6600`，greeting仍为 `OK MPD 0.23.5`。

不推断版本差异原因、不推断存在代理或另一 daemon，不以 hash 宣称未修改原版。上述 S11 新行为实测仅对实际 TCP endpoint 成立；**归属原版 MPD0.23.5 的目标适用性 NOT VERIFIED**，不能升级为原版0.23.5 capability PASS。先确认监听 socket→PID→binary；在身份问题解决前不执行 daemon restart 或故障注入，也不变更目标版本。S11 继续 **BLOCKED**。

### 校正：greeting 是协议版本，部署 daemon 为0.23.17（2026-10-08）

用户补充 NAS 原始 INFO 与 netstat：package=mpd、version=0.23.17-3，`0.0.0.0:6600 LISTEN 2823/mpd`。结合此前 `/proc/2823/exe --version`，当前监听进程识别为daemon0.23.17(699d8b3)。[官方协议文档](https://mpd.readthedocs.io/en/stable/protocol.html#protocol-overview) 说明 greeting 的 version 是协议版本，而非 daemon 实际版本；greeting0.23.5 与 binary0.23.17 并不矛盾。此前把 greeting 当 daemon版本核验的表述予以校正。

实际部署/套件身份已有用户侧证据；hash不证明未修改原版，当前映射也不证明此前时刻未换进程。已有 endpoint 行为记录保留，不能作为daemon0.23.5实测PASS。原版0.23.5目标仍未满足；未经用户决定不自动改目标版本或降级NAS。真实daemon重启和错误边界仍未验证，S11继续BLOCKED。

### 用户决定：现有部署按功能验收（2026-10-08，最新门禁）

用户明确版本号不是关键，关键是实现和验收所需功能。因此S11改为验收现有NAS部署的实际所需能力，不以daemon精确0.23.5匹配或源码原版溯源单独阻塞；无需降级/更换套件。实际身份仍记录daemon0.23.17(699d8b3)、DSM package0.23.17-3、协议greeting0.23.5。本文件历史标题和旧probe不据此冒充当前daemon版本或新证据。

用户决定不改变功能合同/证明要求：保留已取得endpoint原始事实，真实daemon重启和decoder/input/output error边界仍NOT VERIFIED，S11保持BLOCKED。只有实际安全执行、核对业务状态与实际身份、确认恢复后，才能逐项更新能力状态。未修改production/test/schema，未执行套件重启或危险故障注入。

### 真实DSM mpd停止/启动后的功能补验（2026-10-08，最新）

用户在场，harness先备份stopped基线并建立A93/B94/C95绑定（version244，A/B重复URI），用户停止DSM mpd，程序记录连接关闭及6600连接拒绝后才通知用户启动。用户确认已启动，stats uptime1145895→0、epoch改变、队列ID重新分配1/2/3、version2。旧binding清除，Queue/Playback/History/active/session保持；maintain=UNKNOWN，实际sample/observe恢复fresh/UNBOUND/Id1/Pos0，Service重启观察阶段控制调用=[]。实际playing如实记录，不推断恢复原因，不称业务重新绑定。

因此现有部署的**daemon重启→停止自动控制/失效旧绑定/恢复actual功能VERIFIED**。用户启动后的新PID/binary未再次读取，不能伪造此标识；该功能证据由用户停止/启动回报、真实端点失效、uptime重置和前后样本支持，不是本机Adapter.close替代。

```text
.superpowers/sdd/2026-10-04-task-4-d6-recovery-corrective-plan/s11-daemon-20261008T145937Z.json
SHA256 b0fdbdee16e0a484ea3a1b436ac7e031e0b925f0fc11bae132dcb701da5cbc69
exit0; failure=null; restore_failure=null; restore_verified=true
```

最终queue内容/order、modes、volume100、stopped及outputs恢复核对一致；新分配Id4/version4，不称原Id90/version233恢复。没有修改媒体/schema/输出，临时harness/Service已关闭。decoder/input/output error边界仍NOT VERIFIED，不能用停机连接失败或ACK50抵扣。因此S11功能门禁仍PARTIALLY VERIFIED/BLOCKED，S12未执行。

### S11 隔离真实错误与最终功能能力门禁（2026-10-08，当前有效）

用户授权独立目录/端口/进程夹具，随后用户在本机终端完成密码认证。本机确认SSH master、NAS loopback16608、夹具PID20050和实际binary后才执行新验收：同现有套件binary0.23.17(699d8b3)，SHA256=`ff9df851bda831c368bead85aa30e2717f96d057180d405e5c7bfc74367f7ae6`；独立配置降权nobody、仅null+pipe输出，无ALSA/DAC、真实曲库或套件控制。

| 新真实场景 | 原始事实 | 功能裁定 |
|---|---|---|
| 无效生成WAV | IDs28/29/30/31、version84，next ACK5 decode bad.wav，随后sample STOPPED/current=null/error=`Failed to decode good.wav` | UNKNOWN、五业务域不变、History0、AutoPlay意图保留，retry/runner零控制，actual fresh/UNCONFIRMED_STOP：VERIFIED |
| 已扫描生成文件被移走 | IDs32/33/34/35、version97，ACK/sample明确Failed to open临时路径/No such file，STOPPED/current=null | 同上，未自动重启、未伪造Stop/natural原因：VERIFIED |
| pipe sink /bin/false退出 | IDs36/37/38/39、version110，真实sample PAUSED/Id36/Pos0/elapsed96.384，error=`Failed to open audio output` | 同current PAUSED按F8.9.3/PB-RECOVERY-TRANSPORT实际确认；业务Queue/History/active/session、song/context/AutoPlay保持，UNKNOWN/SYNC_FAILED、零控制、retry/runner不再改变：VERIFIED |

原始记录与失败边界：

```text
s11-faults-20261008T153607Z.json
SHA256 4d9b3871ebee7cd1c5f3d7e8b75ae8f68851e53bf42b948f77025ed3d0c22550
exit0; decoder/input/output=VERIFIED; production_unchanged=true
fixture_restore_verified=true; restore_failure=null
```

以上位于本plan ignored workspace。两次先前探索exit1也留存E及JSON：一次ACK提前退出/错误要求PAUSED保持PLAYING；一次输入/解码ACK后MPD转到已预排健康fallback，后续status.error为空（未误认为无故障）。最终仅改自建夹具/harness：保留真实ACK，所有已排入测试URI均不可播放以验证保守停止；golden生成文件在music_directory外用于恢复。允许PAUSED delta有明确合同依据，其余保留与retry断言未删减。不得把探索失败回填成PASS或把空error推断自然原因。

三个最终sample error非空；snapshot实际诊断为UNCONFIRMED_STOP/SYNC_FAILED，error_code/error_message仍null，不声称页面显示原始错误字符串。代表性WAV/本地文件/pipe错误不外推每一codec、ALSA/USB设备故障或声学成功。

生产6600本轮仅只读；完整前后响应相等。实际用户基线是两曲、version5、PAUSED/current Id5/Pos1/elapsed12.620，不覆盖为前轮stopped单曲。所有fixture恢复只作用16608。临时Service/SQLite/runner已关闭；验证归属后停止PID20050，完整夹具/log/config/生成媒体先归档，再白名单逐文件删除并rmdir仅 `/tmp/mpd-s11-fault.8pHKv9`；关闭本次SSH master，确认临时socket与端口关闭。归档可恢复测试材料：

```text
s11-fault-nas-20261008T153839Z.tar.gz
SHA256 0216b8bdaa7cf0abaeb5a8731ad83cdf209367c6da1ba7008ebc3bcb0aa0f2ce
s11-fault-cleanup-20261008.json
```

结合此前S11各真实场景与保护恢复记录，**S11目标运行时功能能力PASSED（用户授权的现有NAS部署功能范围）**。不是daemon精确0.23.5或源码原版证明；真实DAC听觉/设备故障仍不宣称通过，另属Task12。没有自动抵扣未测关键功能，没有production/test/schema或依赖变化。**S12未执行，D6/Batch13/Task6 final仍BLOCKED**，不能以此替代联合门禁。


### 2026-10-09 S12联合门禁状态

S11能力证据仍限已授权现有NAS部署功能范围；本轮未取得新目标响应或改变目标。S12本地联合、全部规定回归及Ruff已通过；D6/Batch13/Task6 functional final PASSED，原本地DB保留审计UNVERIFIED独立记录，见[唯一D6 acceptance](superpowers/archive/task-4/2026-10-04-task-4-d6-recovery-acceptance.md)文末S12。main仅提前完成现有本地Queue初始化，目标harness的Adapter/Service/runner路径未变；不把本地GREEN改写为daemon精确0.23.5、源码溯源或物理DAC通过。默认运行配置未更改，Task10/12仍独立。
