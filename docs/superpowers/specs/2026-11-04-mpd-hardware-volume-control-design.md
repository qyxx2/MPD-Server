# MPD 硬件音量控制与实时状态设计规格

> 状态：新需求设计规格；仅覆盖 MPD-Server 服务端。客户端适配是后续独立阶段，不属于本分支的实现范围。
> 日期：2026-11-04
> 分支：feature/hardware-volume-control

## 1. 目标与边界

在 MPD-Server 中增加独立的硬件音量领域能力，使客户端可以通过统一 REST API 查询 NAS USB DAC 的硬件 Mixer 音量、调整音量，并通过现有 WebSocket 实时状态通道获知变化。

控制链路：

Client → MPD-Server API → HardwareVolumeManager → PlayerPort → MPD setvol/status → ALSA hardware mixer → USB DAC。

Music Server 仍是客户端唯一控制入口。本规格不实现 Web / Android UI、客户端 DTO 适配或客户端验收；不改变 Queue、AutoPlay、History 或输出切换语义；不直接由 Music Server 容器打开 /dev/snd，也不实现通用 ALSA ioctl 驱动。

## 2. 已验证事实与适用前提

### 2.1 目标 NAS 实测

2026-11-04 在 Synology DS920 / DSM 7.1.1 上，MPD TCP greeting 为 OK MPD 0.23.5。MPD outputs 查询返回 USB DAC（plugin=alsa、outputenabled=1），另有一个未启用的 HTTP Stream 输出。

NAS 实际 MPD 配置中的 USB DAC 输出块为：

~~~conf
audio_output {
    type           "alsa"
    name           "USB DAC"
    device         "hw:0,0"
    mixer_type     "hardware"
    mixer_device   "hw:0"
    mixer_control  "PCM"
    mixer_index    "0"
}
~~~

MPD setvol 80 返回成功，随后 status 返回 volume: 80。直接读取 ALSA PCM Playback Volume 硬件控制项，左右声道从测试前的 125/125 变为 117/117。该实测证明目标 NAS 的 MPD 硬件 Mixer 路径能真实改变 DAC 硬件音量。

MPD status 已返回音量字段，当前 PlayerPort 的 PlayerStatus.volume 将其建模为 0–100 整数；PlayerPort 已有 set_volume(volume: int)，MPD Adapter 已将其映射为 setvol。服务端无需另建 MPD 命令实现。

### 2.2 不能从实测推断的内容

MPD status.volume 是 MPD Mixer 的逻辑音量读数，不是 ALSA 原始控制值、精确 dB 值或模拟输出电压。目标 DAC 的 ALSA 原始音量范围目前为每声道 0–127，但 MPD 协议没有返回原始左右声道值。API 不得从 MPD 百分比伪造 raw value、dB、声道平衡或 bit-perfect 信息。

MPD TCP 客户端的 config 命令被目标服务器拒绝（仅允许 local clients），所以服务端不能通过 MPD TCP 自动证明 mixer_type。必须显式配置能力开关，不得仅因 MPD 存在 setvol 命令就宣称该音量一定是硬件音量。

MPD setvol 命令不带 output ID，控制语义属于 MPD 实例的音量控制，不是可独立寻址的某一输出专属音量接口。当前 NAS 只有 USB DAC 的 ALSA 输出启用，HTTP Stream 输出禁用；部署验收必须确认其它启用输出不会造成意外联动。客户端不得把此接口宣传成支持多输出各自独立调音。

MPD status 是否能立即反映第三方程序直接写入 ALSA mixer 的变化，目前没有独立实测证据。实现验收必须单独验证这条外部变化路径；在证实之前，不承诺 Roon 或其它进程直接改写 ALSA 后一定会被 MPD 观察到。

## 3. 方案比较与采用方案

| 方案 | 做法 | 取舍 |
|---|---|---|
| A. MPD 硬件 Mixer（采用） | 经现有 PlayerPort 调用 MPD setvol，读取 status.volume；前提是管理员确认 MPD ALSA 输出使用 mixer_type hardware | 与现有 MPD→ALSA 链路一致；无需容器映射声卡设备；已有真实 NAS 写入硬件验证。不能经 MPD 协议返回 ALSA 原始通道值；第三方直接改 ALSA 的可见性需实测 |
| B. Music Server 直接 ALSA ioctl | 容器映射 /dev/snd/controlC*，服务端直接读写 Feature Unit | 能读取原始通道值，更适合观察绕过 MPD 的外部硬件改动；增加设备节点映射、权限、热插拔/声卡编号识别和内核 ABI 维护，扩大容器设备访问面 |
| C. 客户端直接控制 MPD | 客户端调用 MPD setvol / getvol | 绕过 Music Server，违反客户端只调用服务端的控制边界，也无法统一状态广播 |

采用 A。若后续实测证明 MPD 无法观察外部 ALSA 写入，应另行评估 B 作为只读硬件状态探针或完整硬件控制后端；不得悄悄把 MPD 百分比当作外部硬件原始值。

## 4. 配置与能力门禁

新增配置项：

- Python 字段：AppConfig.mpd_hardware_volume_enabled，默认 false。
- 环境变量：MPD_HARDWARE_VOLUME_ENABLED。
- 生产 Compose 将该变量传入容器；.env.example 默认关闭。

该开关是运维人员对 MPD 配置的显式确认：OutputManager 选中的唯一 NAS ALSA 输出必须配置 mixer_type "hardware"，Mixer 指向目标 DAC 的硬件音量控制项。目标 NAS 当前确认值为 mixer_device "hw:0"、mixer_control "PCM"、mixer_index "0"。服务端不能从远程 MPD config 命令独立验证这些静态设置。该控制 API 的作用范围是当前 MPD 实例的 Mixer 音量；选择目标 ALSA 输出用于确认硬件音量路径，不意味着 MPD setvol 可以按 output ID 隔离控制。启用前须确认当前启用输出组合与该实例级音量语义相符。

门禁规则：

1. 开关默认关闭；关闭时 API/state 明确返回 UNSUPPORTED / HARDWARE_VOLUME_NOT_CONFIGURED，不调用 setvol。
2. 开关开启时，运行时仍必须验证 MPD 连接、status 音量字段、setvol 能力，以及当前唯一选中的 ALSA 输出。
3. 输出未能唯一识别、目标输出不存在或当前输出不可用时，不执行写入。
4. 不保存 MPD 输出数字 ID 作为设备身份；复用 OutputManager 当前输出选择合同（配置名称/plugin，或仅在只有一个 ALSA 候选时使用唯一候选）。
5. MPD status 音量为 null / -1、MPD 断线、命令拒绝或读取超时均不能当作 0。
6. 配置开关仅是静态配置声明，不是运行时可用证明；只有最近一次有效读取成功后才可报告新鲜可用。

## 5. 领域模型

新增 server/app/models/hardware_volume.py，与 OutputSnapshot 分离，避免把音量误作输出启停状态。

### 5.1 HardwareVolumeState

| 字段 | 类型 | 语义 |
|---|---|---|
| status | AVAILABLE / UNAVAILABLE / UNSUPPORTED | 控制能力状态 |
| volume_percent | int 0..100 或 null | 最近一次 MPD 确认的 Mixer 音量；未知时为 null |
| output_name | string 或 null | 当前被选中的 MPD 输出名称 |
| output_plugin | string 或 null | 例如 alsa |
| output_enabled | bool 或 null | 最近一次 MPD outputs 读取结果 |
| control_source | MPD_HARDWARE_MIXER 或 null | 仅在运维配置开启且能力确认后返回 |
| error_code / error_message | nullable string | 当前不可用原因 |
| updated_at | datetime | 最近一次接受的状态更新时间 |
| stale | bool | 是否为旧样本；旧值可保留展示但不能当作当前确认 |

volume_percent 表示 MPD 0–100 的硬件 Mixer 逻辑级别，不代表声压百分比或线性 dB。不得额外生成 raw_left、raw_right、decibels 等没有可靠读取来源的字段。

### 5.2 HardwareVolumeRequestState

字段：requested_percent: int、status: PREPARING | SUCCEEDED | FAILED、nullable error_code / error_message、updated_at。

它仅记录最近一次服务端控制请求，不是当前音量事实。第三方更改音量或 MPD 状态发生变化时，不能把 last_request 当作最新读数。

### 5.3 HardwareVolumeSnapshot 与 observation

HardwareVolumeSnapshot 包含 state 和 nullable last_request。

HardwareVolumeObservation 沿用现有 output observation 模式，字段为 observed_at、freshness: fresh | stale | unknown、nullable error_code / error_message。从未成功采样为 unknown；曾成功但超过 6 秒未刷新或读取失败为 stale；读取成功且样本不超过 6 秒为 fresh。

读取失败时可以保留最后一次已确认的 volume_percent，但必须将 stale=true 并写明错误；从未取得有效值时保持 null。禁止将未知值回填为 0。

## 6. HTTP API 合同

客户端只调用 Music Server，不得连接 MPD TCP。API 沿用现有系统控制接口的网络信任边界；Idempotency-Key 只保证重试语义，不是身份认证。当前部署不得将无认证的服务端口直接暴露到公网。

### 6.1 查询硬件音量

GET /api/system/hardware-volume

返回 HardwareVolumeSnapshotResponse，至少包含 state、observation 和 lastRequest：

~~~json
{
  "state": {
    "status": "AVAILABLE",
    "volumePercent": 80,
    "outputName": "USB DAC",
    "outputPlugin": "alsa",
    "outputEnabled": true,
    "controlSource": "MPD_HARDWARE_MIXER",
    "errorCode": null,
    "errorMessage": null,
    "updatedAt": "2026-11-04T00:00:00Z",
    "stale": false
  },
  "observation": {
    "observedAt": "2026-11-04T00:00:00Z",
    "freshness": "fresh",
    "errorCode": null,
    "errorMessage": null
  },
  "lastRequest": {
    "requestedPercent": 80,
    "status": "SUCCEEDED",
    "errorCode": null,
    "errorMessage": null,
    "updatedAt": "2026-11-04T00:00:00Z"
  }
}
~~~

示例时间仅展示结构，不是默认值。当前从未发出服务端控制请求时，lastRequest 为 null。GET 执行一次受超时预算限制的新鲜读取；若读取失败，仍返回可表达 UNAVAILABLE / stale / unknown 的 snapshot，不伪造正常值。

### 6.2 设置硬件音量

PUT /api/system/hardware-volume

请求体：

~~~json
{ "volumePercent": 80 }
~~~

- volumePercent 是严格整数，范围 0–100；拒绝 boolean、float、字符串和越界值。
- 继承项目全局 mutation middleware，必须提供 Idempotency-Key。相同操作传输重试复用原 key；新用户操作使用新 key。
- 服务端调用 PlayerPort.set_volume(volume_percent)，即 MPD setvol；随后必须读取 MPD status 并验证 status.volume == requested_percent。
- 成功响应返回确认后的完整 HardwareVolumeSnapshotResponse，不能只返回请求值或 ACK。
- 写入后读回缺失、错误或不相等时，返回错误并将状态设为 stale/unconfirmed；不得按命令 ACK 宣称硬件音量已成功改变。

### 6.3 HTTP 状态码与错误码

| HTTP | 错误码 | 条件 |
|---|---|---|
| 400 | HARDWARE_VOLUME_NOT_CONFIGURED | 管理员未启用硬件 Mixer 能力 |
| 400 | HARDWARE_VOLUME_OUTPUT_AMBIGUOUS | ALSA 输出无法唯一选定 |
| 422 | VALIDATION_ERROR | 请求值不是严格 0–100 整数 |
| 502 | HARDWARE_VOLUME_WRITE_FAILED | MPD 拒绝 setvol |
| 502 | HARDWARE_VOLUME_RECONCILIATION_FAILED | 写后读回不能确认目标值或播放保护检查失败 |
| 503 | PLAYER_UNAVAILABLE | MPD 不可达 |
| 503 | HARDWARE_VOLUME_UNAVAILABLE | 目标输出 / Mixer 当前不可用或读数未知 |

GET 以 snapshot 表达运行状态；只有请求本身无法构造完整快照等本地必需错误才使用 503，遵守现有 /api/state 与系统读取合同。

## 7. 播放保护、并发与事务语义

1. 音量变化不得修改 Queue occurrence / 顺序 / revision、PlaybackState、current Song、播放/暂停/停止状态、repeat/random、History active session 或 AutoPlay。音量命令的作用域是 MPD 实例；本期仅在已确认的 NAS DAC 输出配置与启用输出组合下开放，不承诺多个输出各自独立音量。
2. 复用 OutputManager 使用的 PlaybackService 操作串行化边界，但音量操作的保持态比较必须明确允许 volume 字段发生目标变化；其它播放字段与 Queue entries 必须保持，播放中的 elapsed 只允许自然推进。
3. 同时存在播放控制或输出启停时，音量操作必须经过同一操作边界，不得并行交错发送 MPD 命令并把混合结果伪装成确认成功。
4. 每次写入前确认能力与目标输出；写入后读取 MPD status 和 outputs，确认音量目标及输出身份未漂移。
5. PREPARING 不代表成功；外层事务 rollback / commit 失败后不得保留成功回执。若 MPD 已执行但外层提交失败，标记状态 stale，下一次读取重新确认事实，不自动反向改回旧音量。
6. 状态是实时运行事实，不写入 SQLite 持久化业务表；重启后为 unknown，等待 observer 重新采样。
7. 多个并发客户端的不同音量写入按共享操作边界串行执行；本阶段不承诺滑块事件去抖或客户端最后写胜出策略，只保证每个已确认 mutation 的顺序与回执一致。

## 8. 状态快照与 WebSocket 广播

### 8.1 FullStateSnapshot

在现有 FullStateSnapshot 顶层增加：

- hardware_volume: HardwareVolumeSnapshot
- hardware_volume_observation: HardwareVolumeObservation

GET /api/state 和 WebSocket 首帧 snapshot 都包含这两个字段。WebSocket snapshot 使用现有序列化规则；当前 REST /api/state 使用 snake_case 字段，不改变既有 wire contract。系统硬件音量 REST 响应沿用 system_schemas 的 camelCase alias 规则。

新增 realtime schema DTO。若 /api/state 字段只是 additive，协议版本保持 1；旧客户端忽略未知字段即可。客户端后续适配必须确认其 decoder 对新增字段的缺省兼容。

### 8.2 Invalidation 广播

复用现有 RealtimeCoordinator.stage_observation，新增域名：

hardware_volume

当最近接受的音量百分比、输出可用状态、相关错误事实或 last_request 的状态/目标发生净变化时，提交后发出既有帧；比较内容排除 updated_at、observed_at 等纯时间戳，避免相同音量的周期采样引发无效广播：

~~~json
{
  "type": "invalidate",
  "protocol_version": 1,
  "epoch": "...",
  "sequence": 123,
  "domains": ["hardware_volume"],
  "revisions": { "library": 0, "playlist": 0 }
}
~~~

hardware_volume 是对现有系统架构规格 §12.2 invalidate domain 集合的显式 additive extension；不移除或重命名现有 domain。该帧是重新读取义务，不是音量 payload、控制 ACK 或持久事件。客户端收到后重新读取 GET /api/state，按现有 epoch/sequence waterline 合同接受完整快照。重复 invalidate 可合并；相同音量的轮询不应每秒触发广播；队列背压、断线重连和 fail-closed 继续使用现有机制。

现有 revisions 仍只包含 Library / Playlist revision；硬件音量依靠全局 sequence 和 domain 名，不新增业务 revision 计数。

### 8.3 Observer

扩展进程唯一 StateObserver，每轮读取 playback、output、hardware volume，并复用既有每秒轮询、请求唤醒、5 秒 round budget 和 6 秒 stale threshold。不得为每个 WebSocket 连接启动独立 MPD 轮询。音量观察失败不能阻断播放和输出观察；部分外部状态失败继续以对应 observation 表达。

## 9. 实现验收标准

- [ ] 默认关闭时，状态明确不可用，PUT 不产生 MPD setvol 副作用。
- [ ] 开启能力开关且目标 MPD 硬件 Mixer 配置正确时，GET 能读取当前 MPD Mixer 音量。
- [ ] PUT 0、1、目标中值、99、100 都严格验证并在 MPD status 回读相符后成功；无效输入在执行命令前被拒绝。
- [ ] 真实 NAS 实测确认 API 写入会改变 ALSA PCM Playback Volume；测试不得只验证 Mock 或 MPD ACK。
- [ ] 实测第三方直接改变 ALSA mixer 后，MPD status 是否跟随；若不能跟随，明确记录并阻断“外部硬件变更可广播”的验收，不得误报已支持。
- [ ] 音量变更不改变歌曲、Queue、播放状态、自然进度、repeat/random 或 History。
- [ ] WebSocket 在净变化后发送 domains=["hardware_volume"] invalidate；无变化轮询不发送；断线重连首帧包含完整硬件音量状态。
- [ ] MPD 断线、输出丢失、能力未配置、读写失败、readback 不一致时，保留 null/last-known + freshness/error 语义，不伪造 0 或成功。
- [ ] mutation 幂等重放不重复执行 setvol；相同 key 不同 payload 冲突。
- [ ] /api/state 和 /api/system/hardware-volume OpenAPI DTO 与 wire fixture 一致。

## 10. 不在本阶段的工作

- Web / Android DTO、状态仓库、页面、滑块、音量按钮、UI 和客户端验收。
- 客户端 debounce、拖动体验、显示 dB 曲线。
- 直接 ALSA ioctl 控制器、容器 /dev/snd 映射、原始左右声道值和 dB TLV 读取。
- 多 DAC 选择 UI、输出切换策略或音频格式能力矩阵。
- NAS 模拟音量控制、静音开关、音量限幅策略和硬件音量持久化。

## 11. 相关现有实现入口

- server/app/player/ports.py：PlayerPort.set_volume。
- server/app/player/models.py：PlayerStatus.volume。
- server/app/player/mpd_adapter.py：MPD status 解析与 setvol。
- server/app/player/capabilities.py：status / set_volume capability。
- server/app/services/output_manager.py：输出选择、操作边界、观察缓存。
- server/app/services/state_observer.py：进程唯一观察器。
- server/app/services/realtime_coordinator.py：观察变化和 invalidate 提交。
- server/app/services/state_service.py、server/app/models/realtime.py、server/app/api/realtime_schemas.py：完整状态快照。
- server/app/api/system.py、server/app/api/system_schemas.py、server/app/api/dependencies.py：系统 REST API。
- deploy/docker-compose.yml、deploy/.env.example、deploy/README.md：生产开关和安装前置条件。
