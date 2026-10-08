# 第四章：项目技术栈、部署与开发维护架构规格书

- 项目：MPD-Server
- Repository：qyxx2/MPD-Server
- GitHub：https://github.com/qyxx2/MPD-Server
- 日期：2026-09-25
- 状态：设计规格
- 适用范围：Web/PWA 首期、FastAPI 服务端、SQLite、Docker Compose、群晖 DSM 7.1.1、现有独立 MPD 0.23.5
- 前置设计：Playback Model / Queue Semantics、Library / Playlist / Tag / Search、System Architecture / Playback Output

## 1. 目标与范围

本章定义 MPD-Server 的技术实现边界、代码组织、开发环境、Docker 部署、GitHub 维护、群晖生产环境、曲库同步、配置、备份、测试和发布回滚方式。

首期目标是形成一个可以长期运行在群晖上的 Music Server：

`Web/PWA → FastAPI → Music Server Services → MPD Adapter → 群晖独立 MPD → ALSA → USB DAC`

客户端不直接连接 MPD。Music Server 是业务状态和播放控制的统一入口。

本章不实现具体业务代码，也不要求在首期引入 Kubernetes、PostgreSQL、GitHub Actions CI/CD 或复杂的 Web 管理后台。

## 2. 总体技术栈

### 2.1 Web/PWA

- Vue 3
- TypeScript
- Vite
- Tailwind CSS
- 定制 CSS
- 可按需使用无默认视觉风格的 UI primitives，例如 Reka UI
- WebSocket 用于实时状态同步
- REST API 用于普通查询和控制请求

Web/PWA 首期是唯一正式客户端。Android 原生客户端后续复用相同 REST API、WebSocket 和状态模型，不重新定义业务协议。

### 2.2 服务端

- Python
- FastAPI
- REST API
- WebSocket
- SQLite
- Repository / Data Access Layer
- Service Layer
- MPD Adapter

核心业务必须位于 `services/`，API 层只负责请求解析、鉴权边界、调用 service 和响应转换，不直接操作 SQLite 或 MPD。

### 2.3 部署

- Docker
- Docker Compose
- 群晖作为首期生产环境
- 正式环境使用与 Dockerfile 对应的正式镜像
- 首期正式镜像由 NAS 根据 main 构建；未来可切换为 GitHub Container Registry 等镜像仓库拉取预构建镜像
- 开发环境使用独立 Compose 配置
- 不要求群晖宿主机安装完整 Python/Node 开发环境

## 3. 客户端职责边界

客户端负责：

- 页面展示
- 用户操作
- 播放控制请求
- Queue / History 展示和交互
- Library / Playlist 浏览
- 播放状态展示
- WebSocket 状态接收
- 断线自动重连
- 当前页面同源 API/WebSocket 地址计算

客户端不负责：

- Queue 权威状态
- AutoPlay 决策
- 曲库扫描
- Playlist 持久化业务
- History 持久化业务
- MPD 协议直接通信
- MPD 与数据库状态协调

服务端是这些状态和业务的权威来源。

## 4. Web 架构

开发环境采用：

`Browser → Vite Dev Server → Proxy → FastAPI`

Vite 开发服务器负责前端即时更新，并将：

- `/api` → FastAPI
- WebSocket → FastAPI

正式环境由 FastAPI 托管构建后的静态 Web 文件：

`Browser → FastAPI → static Web`

客户端不写死 IP、域名或端口，而是根据当前页面地址采用同源方式访问：

- API：当前 origin + `/api`
- WebSocket：当前 origin 对应的 ws/wss + WebSocket 路径

因此以下访问方式共用同一套客户端代码：

- 群晖局域网 IP + 端口
- 群晖反向代理域名
- HTTPS + WSS

正式环境必须保证群晖反向代理能够正确转发 WebSocket。

## 5. 服务端模块边界

推荐结构：

```
server/
├── app/
│   ├── api/
│   ├── services/
│   ├── repositories/
│   ├── models/
│   ├── player/
│   └── main.py
└── tests/
```

### 5.1 api

负责：

- REST endpoint
- WebSocket endpoint
- 请求参数校验
- 响应模型
- 错误映射

不直接实现复杂业务。

### 5.2 services

负责：

- Playback Service
- Queue Manager
- AutoPlay Engine
- Library Service
- Playlist Service
- History Service
- Output Manager
- 配置/备份等应用级业务

Service 通过 Repository 或 Adapter 访问外部资源。

### 5.3 repositories

负责 SQLite 持久化。

要求：

- 不把 SQL 散落在 API 层
- 事务边界明确
- 关键写操作可串行化
- 为未来 PostgreSQL 迁移保留数据访问抽象

首期仍然使用 SQLite，不为了未来迁移提前引入复杂 ORM 基础设施。

### 5.4 player

负责播放引擎抽象及 MPD Adapter。

首期：

`Music Server → MPD Adapter → MPD TCP Protocol`

MPD 是独立进程，不由 Music Server 安装、启动或管理。

## 6. MPD 集成

生产环境使用群晖宿主机已有 MPD 0.23.5。

Music Server 容器通过配置连接：

- MPD host
- MPD port
- MPD password（如果启用）

采用容器访问群晖 LAN IP 的方式，不使用容器内的 `localhost` 连接宿主机 MPD。

Music Server 不：

- 在容器内运行 MPD
- 自动安装 MPD
- 修改 MPD 配置文件
- 管理 MPD 生命周期

Music Server 提供常用 MPD 运行时控制，例如：

- play / pause / stop
- previous / next
- seek
- repeat
- random
- volume
- update database
- output 状态相关控制（在 MPD 0.23.5 实测能力允许的范围内）

涉及只能修改配置文件的 MPD 设置，不假定能够通过 MPD 协议修改。

### 6.1 MPD 能力验证

实现前必须以实际 MPD 0.23.5 为准验证：

- 支持的命令
- 输出设备能力
- 当前输出状态
- 播放位置
- 曲库更新
- 播放状态事件
- 错误响应

不得因为文档中存在某个新版本 MPD 命令，就假定 0.23.5 支持。

## 7. 曲库

Music Server 对音乐目录采用只读挂载。

原则：

- Music Server 可以读取音乐文件和元数据
- 不修改原始音乐文件
- 不删除原始音乐文件
- MPD 继续使用现有音乐路径
- Music Server 维护文件路径与 MPD song identifier 的映射

### 7.1 扫描机制

使用两层机制：

1. 文件系统事件监测
2. 定时完整校准扫描

文件系统事件需要 debounce / batch，避免大量文件连续变化导致重复扫描。

默认完整校准间隔：

`12 小时`

该值可配置。

同时保留手动扫描接口。

扫描完成后：

- 更新 SQLite
- 必要时触发 MPD 曲库更新
- 通过 WebSocket 通知客户端曲库发生变化

## 8. 数据库

首期使用 SQLite。

建议至少覆盖：

- songs
- albums
- artists
- tags
- playlists
- playlist_items
- favorites
- history
- queue / playback state
- 配置或必要的系统状态

实际表结构以实现阶段的详细数据模型为准，但必须保持前述三个设计章节定义的实体和状态边界。

### 8.1 SQLite 可靠性

必须：

- 使用事务
- 明确写操作边界
- 避免多个后台任务无序并发写数据库
- 对关键状态更新进行串行化
- 对数据库启动进行结构检查

SQLite 文件必须位于持久化目录，而不是容器临时层。

## 9. 开发环境

开发环境使用独立：

`deploy/docker-compose.dev.yml`

开发环境：

- 源码挂载
- FastAPI hot reload
- Vite 即时更新
- 独立开发数据库
- 独立配置
- 独立备份目录
- 默认使用 Mock MPD

开发环境的数据不得与生产环境共享。

### 9.1 Mock MPD

Mock MPD 与真实 MPD 使用同一个 Adapter 接口。

Mock MPD 用于：

- 服务端单元测试
- API 测试
- Queue 测试
- AutoPlay 测试
- 播放状态同步测试
- 前端联调

需要真实音频播放时，再切换到群晖真实 MPD。

## 10. 生产 Docker 部署

生产使用：

`deploy/docker-compose.yml`

正式容器：

- 使用预构建镜像
- 持久化挂载 SQLite
- 持久化挂载配置
- 持久化挂载备份
- 只读挂载音乐目录
- 配置 healthcheck
- 配置日志轮转

容器重建不得导致：

- 数据库丢失
- 配置丢失
- 备份丢失

音乐文件完全位于宿主机，不属于容器生命周期。

## 11. 配置

支持：

1. 配置文件
2. 环境变量

主要配置包括：

- MPD host
- MPD port
- MPD password
- 音乐目录映射
- SQLite 路径
- 备份目录
- 曲库校准间隔
- Web/API 基础配置

修改配置后按需要重启容器。

首期不开发“编辑所有服务端参数”的 Web 管理后台。

MPD 运行时控制，例如 random、repeat、volume、update database、output 等，提供 API；静态配置仍通过部署配置管理。

## 12. WebSocket 与状态恢复

WebSocket 是实时状态同步通道。

服务端在状态发生关键变化时广播，例如：

- 当前歌曲变化
- 播放/暂停/停止
- 播放进度
- Queue 变化
- History 变化
- Playlist 变化
- Output 状态变化
- 曲库扫描完成

客户端断线后自动重连。

重连成功后不能只依赖遗漏的增量事件，而必须重新获取完整当前状态，以恢复：

- 当前歌曲
- 播放状态
- 播放位置
- Queue
- History 可用状态
- Output
- 必要的 Library/Playlist 状态

### 12.1 完整快照的一致性与失败边界（Task 6，2026-10-03）

本节来自本次 Contract Gap Resolution 的明确人工决策 G6-01 / A。它规定聚合读取边界，不授权改变领域 mutation 或引入新的播放转移规则。

- **Preconditions**：通过 StateService 聚合已初始化的领域 Services；允许空库、无当前歌曲及 MPD 不可达。
- **Authority / Source of Truth**：本地 Playback、Queue、PlaybackContext、History 持久与 runtime 状态、Library/Playlist 数据及对应 revisions 由各领域 Service 提供；StateService 只负责聚合。MPD 实际播放与输出事实经 PlayerPort 和所属 Service 确认；数据库锁不能冻结 MPD 时间推进、自然结束或其它 MPD 客户端。
- **Expected State Delta**：生成独立、不可随源对象后续变化而改变的完整快照。本地业务字段及其版本必须对应同一已提交、可串行化切面，不得混合一次业务转移前后的 Queue、Playback 和 History。
- **Must Remain Unchanged**：读取不改变 Queue occurrence/order/revision、PlaybackContext、Playlist/Favorites membership、History active/session、MPD 播放或输出；不得调用具有业务转移副作用的 reconciliation 来完成只读快照。允许既有 Output observation cache 更新。
- **Transaction Boundary**：聚合读取必须与所有相关本地 mutation/runtime 更新遵守共同的一致性边界。不得暴露其它尚未提交的业务状态；业务数据与对应 revision 同时可见。不得将网络发送或等待客户端纳入该边界。
- **Failure / Rollback**：任一本地必需域读取失败，整个快照操作失败，不返回伪装为完整成功的部分本地状态，也不能将失败解释为空历史、空 Queue 或零 revision。外部观察失败允许保留完整结构，但必须显式表示 stale/unknown、观测时间（无成功样本时为空）和错误；没有样本不得伪造数值。快照失败不撤销此前已提交的业务操作。首次连接不能把失败结果当作成功初始快照；交付协议见后续连接合同。
- **Retry / Idempotency**：重试重新读取当前状态，不重放业务 mutation，不产生 History 或业务成功事件；不保证两次读取内容相同。
- **Revision / Ordering**：本地快照中的数据和 revisions 属于同一切面；外部观察明确标记自身时间和 freshness，不宣称与本地切面或不同 MPD 命令物理原子。具体 revision 生命周期见第二章 §7.1，observation freshness 见本章 §12.3 和第一章 §8.8。
- **Observable Result**：完整的本地状态加显式外部观察状态，或明确的整体读取失败；MPD 不可达本身不要求丢弃已成功读取的本地完整状态。
- **Executable Invariant Proof**：Task 6 必须新增真实 SQLite/Services/MockPort 的关系测试，用 barrier 强制 mutation 与 capture 交错，断言结果仅为联合提交前或后的本地状态及匹配 revisions；逐域注入本地失败证明无成功部分快照；外部失败证明 stale/unknown/error 与空值保留；深复制及读取前后业务状态比较证明无读取副作用。测试尚未实现，不能将本节当作已通过的执行证据。

### 12.2 实时失效通知、交接与背压（Task 6，2026-10-03）

本节来自当前对话人工决策 G6-03 / A。领域事件保留业务含义和既有 payload；对客户端的实时帧是失效通知，不是领域状态副本。不存在持久事件重放或 exactly-once 保证。

#### 协议与读取入口

- `GET /api/state`：通过 StateService 返回完整 `FullStateSnapshot`；本地必需域读取失败返回 HTTP 503，错误码 `STATE_SNAPSHOT_UNAVAILABLE`，不返回部分成功。外部降级本身仍可返回 200。此接口只读，不创建幂等 terminal record。
- `WS /api/realtime`：每次新连接第一条成功数据帧为 `{"type":"snapshot","protocol_version":1,"epoch":...,"sequence":...,"state":...}`；state 与 GET 返回的快照语义相同。v0.1 沿用无鉴权、同源访问范围。
- live 帧为 `{"type":"invalidate","protocol_version":1,"epoch":...,"sequence":...,"domains":[...],"revisions":{"library":...,"playlist":...}}`。domains 取 `playback / queue / history / library / playlist / output`，表示应重读的域；revisions 为该通知覆盖的同 epoch 已提交版本，不是 Queue CAS 版本。客户端不能把该帧当作 mutation 回执或按它直接改 Queue/History。
- snapshot 必须含 `epoch`、`sequence` 与 Library/Playlist revisions。收到 invalidate 后重新 GET 完整快照；Library/Playlist 资源列表根据相应版本刷新。Playlist 展示同时依赖 Library 版本。客户端以当前新连接首帧的epoch为基准；同epoch只应用比已应用sequence更新的快照，相同sequence幂等忽略。新连接跨epoch时清除旧比较基准并完整恢复，同时废弃旧连接及其未完成GET的结果；旧epoch响应不能触发再次回退。GET若发现与当前连接不同epoch，重新连接确认当前epoch后恢复。旧请求晚返回不得覆盖较新快照。

#### 操作合同

- **Preconditions**：领域 Service、StateService 和进程内传播协调器已注入；领域事件不依赖 socket。合法 mutation 仍遵守其原确认、outer commit 和幂等合同。
- **Authority / Source of Truth**：领域 Service/Repository/PlayerPort 拥有业务事实；协调器拥有进程 epoch、传播顺序和订阅生命周期；WebSocket 只负责交付。
- **Expected State Delta**：提交或已接受的外部观察使对应客户端表示失效；首次连接取得完整状态，随后获知尚未被该快照覆盖的变化。
- **Must Remain Unchanged**：发送、重连、重复通知、队满或断开不触发业务重做；不改变已提交 DB/runtime/terminal、Queue/History 或外部控制事实。保留 LibraryChangedEvent 的扫描结果/MPD update error 与 OutputChangedEvent 的确认快照语义。
- **Transaction Boundary**：在共同一致性边界内完成最外层提交、版本可见性和进程内待通知变化登记；登记不得早于成功提交，也不得晚到出现“可读新状态但无人知道需要通知”的窗口。登记只操作内存且不得等待 socket/外部 I/O；实际交付及领域 post-commit 回调在数据库锁外。若提交后无法可靠登记，必须使相关连接失效并关闭，协调器进入不可提供可信快照的状态：GET 返回503、新连接不得获得成功snapshot，直到重建新epoch及当前状态基线；不能携旧revision返回新数据，也不能继续连接却静默漏掉最后一次变化。此故障不得执行已提交事务的rollback hooks。提交前失败没有成功通知；提交后取消不撤提交或其失效义务。
- **Revision / Ordering**：同 epoch 的 `sequence` 从 0 开始，由协调器对已提交可观察变化和接受的外部观察串行分配，单调增加；它只用于当前进程的覆盖/先后判断，不是 durable cursor，也不与领域 revision 等同。一次联合提交产生联合 domains，不暴露中间状态；无内容变化的扫描完成可产生通知而不递增 Library revision。因 optional MPD update 而延迟的扫描完成，不能延迟该扫描提交数据的版本可见性或失效登记；原领域 completion event 仍遵守 commit → optional update → completion event。迟到领域回调只可重申失效、被已覆盖标识去重，或在协调器重新读取最新版本后登记新的通知，不能携旧状态覆盖新版本。重复通知不要求恰一次，sequence 缺号本身不代表可重放事件丢失。
- **连接交接**：订阅登记和 snapshot capture 建立共同边界。连接在 capture 前已能暂存通知；第一帧成功 snapshot 的 sequence 为覆盖水位。随后只交付未被快照覆盖的失效义务，或安全的冗余失效通知；不能在发送快照之后才注册订阅。每个交接窗口内的最后一次变化必须被初始快照覆盖，或在其后通知客户端重读；即使没有下一次 mutation 也要成立。
- **Failure / Rollback**：每连接独立有界队列和 sender；默认上限 64 个待发送帧、每帧发送超时 10 秒，均为可注入运行参数而非 Task 10 配置系统。队满或超时将连接标为失效、注销并关闭，使用关闭码 1013；无法发出关闭帧时终止发送任务/连接资源。客户端以新连接完整快照恢复，不允许持续连接静默丢弃唯一通知。初始 snapshot 本地读取失败关闭码 1011，不发送成功 snapshot；普通断开/取消清理订阅和 sender。单个失败连接不能阻塞其它连接或改变已提交 mutation 结果；失败有可定位日志。
- **Retry / Idempotency**：GET 重试重新读取；WS 重连总是重新 capture，不接受旧 cursor 恢复。失效通知可重复；幂等 mutation replay 不重复业务事件。快照请求进行中又收到更新时，必须保证所应用快照覆盖最新已知水位，否则再读；请求失败不得假装恢复成功。
- **Observable Result**：成功 initial snapshot → 单调有序失效通知 → GET 当前完整状态；故障时明确断开/读取失败，不伪报业务 rollback 或客户端已应用。无客户端 ACK 保证。
- **Executable Invariant Proof**：用真实事务/Service 与 barrier 在 register/capture/send、commit/迟到 callback、并发 GET 返回处插入最后一次 mutation，证明其被覆盖或通知且不倒退；双客户端阻塞发送/队满/取消测试证明提交与正常连接独立；断线期间跨域变化、重启 epoch、重连首帧与真实 Services 对照。使用可控队列/FakeClock，不用 sleep 猜测竞态。具体测试由 Task 6 Plan 分配，尚未实现。

### 12.3 观察生命周期与完整 DTO

继承人工决策 G6-04/G6-05 / A；History 与播放观察的领域 authority 分别为第一章 §2.2.1/§8.8，不在 gateway 重定义。Task4 D6 的保守恢复及 STOPPED/AutoPlay/session 组合只由第一章 §7/§8.9 定义；本节观察循环仍不调用恢复，完整验收依赖第一章 §8.9 修订后的绑定/当前接纳/提前执行/未知历史与只读展示联合门禁；严格自然 SOURCE 已被替换，未被证明通过。

**生命周期合同**：前提是 composition root 已注入 PlaybackService observation facade、OutputManager、传播协调器和可控时钟。每个服务进程仅启动一个观察循环，首次启动立即采样，以每轮完成后 1 秒为默认间隔，无重叠采样；单轮外部读取预算默认 5 秒，可注入以便测试，不引入 Task 10 配置系统。PlayerPort 的既有 typed timeout/error 保留。采样不依赖客户端数量；失败后按同一有界间隔重试，不忙循环。关闭应用取消并 await observer/senders、注销订阅，不把关停取消解释成 Stop 或 rollback 已提交业务。MPD 不可达不阻止服务启动。

Playback 和 Output 观察分域处理，一域失败不丢弃另一域成功事实。Output 始终通过 OutputManager 的已冻结 observation/request 分离、null/stale 合同；观察不执行输出控制，不制造 Output 控制成功事件。重复无内容变化样本只更新观测时间，freshness/error 的实际变化可触发失效。读取 snapshot 只消费受保护的本地状态和观察缓存，不启动恢复或控制；尚无样本为 unknown。默认超过 6 秒未取得成功样本时表示 stale（无样本为 unknown）；freshness 过期可机械判定，不依赖是否恰好收到下一次事件；到期由观察生命周期在共同边界登记stale及sequence，capture也必须先检查到期，不能以旧水位返回未登记的新freshness。此登记是观察时效变化，不是业务mutation或成功事件。外部调用失败立即降级。时间阈值及队列容量是明确的可注入 v0.1 运行参数，不是新领域决策。

**统一 DTO 语义**：`FullStateSnapshot` 包含 `epoch`、`sequence`、`captured_at`、`revisions {library, playlist}`、`playback`（既有已确认 PlaybackState 或 null）、`current_song`（Library 当前 Song 表示或 null）、`queue {revision, items}`（全部 occurrence/position/source/context，包含 Played/current/pending）、`history`（第一章 §2.2.1）、`output`（既有完整 OutputSnapshot）、`playback_observation`、`output_observation`。无本地 current 时 current_song 为 null；已知 Song unavailable 保留身份/元数据及 availability，不过滤 Queue occurrence。current 存在引用但本地必需数据读取异常时遵守 §12.1 失败，不悄悄删字段。按当前对话 G6-01 补充决策 A，PlaybackContext 仅通过 PlaybackState/Queue occurrence 的 playback_context_id 和当前权威 Queue 顺序恢复；本Task不承诺另一个完整Context对象或其来源/原始成员/seed跨重启恢复，不从Queue反推这些资料，不改既有Collection/开始播放合同。重连不得重排Queue或重建Context。

`playback_observation` 包含 nullable `actual_state`、nullable `matches_current`（true/false/null=未确认）、nullable `position_seconds`/`duration_seconds`（只属已验证匹配的本地 current）、nullable `observed_at`、`freshness`（fresh/stale/unknown）、`reconciliation_required`、nullable `error_code`/`error_message`。从未采样不推断外部漂移，matches_current=null、reconciliation_required=false；发现确定漂移则 false/reconciliation_required=true；绑定无法确认时 null/reconciliation_required=true。连接读取失败或样本过期时，有最后匹配样本可保留其位置，但必须stale且绑定仍属同一current；已明确state/current漂移或绑定无法确认时，position_seconds/duration_seconds为null，不在该DTO复用旧位置。Output 原 observed/request/error 字段完整保留，并在外层提供 `output_observation {observed_at, freshness, error_code, error_message}` 描述采样状态，不拿旧 request 回执作 fresh observation。

**保留、失败与证明**：生命周期只改变观察缓存/订阅资源/传播 sequence；保持持久数据、History、Queue、Library/Playlist revisions、MPD 控制事实不变。FakeClock 和受控 PlayerPort 需证明单循环、预算超时、无重叠、独立域降级、周期重试、关停资源释放和读操作无业务副作用；进程重启清空观察可信度并更换 epoch。自动恢复不得接入未通过第一章 §8.8 前置验收的 reconciliation 路径。以上新增代码及测试仍未实现。

### 12.3.1 原版 MPD 实际身份与页面恢复补充（2026-10-04，RT-ACTUAL-001）

本节仅定义表示；领域转移由第一章 §8.9 决定。服务/MPD重启后业务重新接管体验沿用 F §8.9.2 的 R1 已接受合同（2026-10-04）：自动恢复实际状态显示，明确播放操作经确认重建业务绑定；仅刷新/换浏览器不丢失有效服务绑定，实际状态/unknown 必须准确表示。当前实现 `StateService.get_full_snapshot()` 通过持久 PlaybackState.song_id 读取 `current_song`；该字段是**最后已提交业务歌曲**，不保证是 MPD 当前曲目。保留旧字段语义，不把它悄悄改为陌生曲目的 Song，也不为陌生 URI 建 Library 行。

最小 additive DTO：在 `playback_observation` 新增 `actual_current`（nullable 对象，字段 `entry_id:int|null, uri:str|null, position:int|null`）、`actual_freshness: fresh|stale|unknown`、`bound_queue_item_id:str|null`、`sync_status: CONFIRMED|UNBOUND|EXTERNAL_DRIFT|UNCONFIRMED_STOP|SYNC_FAILED|NO_CANDIDATES`。沿用 `actual_state/observed_at/error_code/error_message`；actual_current 仅是最近一致 MPD 样本，STOPPED 中有 entry 不表示仍在播放。无成功样本为 null/unknown；断线保留最后样本但 actual_freshness=stale。fresh 的未绑定 actual 可以与旧业务 current 不同。

原 `freshness/matches_current/position_seconds/duration_seconds` 保持原绑定进度合同。bound_queue_item_id 只在当前有效绑定被验证时非 null；丢绑定、样本过期或当前漂移时为 null。`CONFIRMED` 需实际与业务 current/transport/完整执行一致；空候选但仍播放时允许 `NO_CANDIDATES` 且 matches_current=true。诊断优先级：无样本/绑定失效 UNBOUND → 可确认未知停止 UNCONFIRMED_STOP → 意外执行漂移 EXTERNAL_DRIFT → 已归属计划失败 SYNC_FAILED → 无候选 NO_CANDIDATES → CONFIRMED。Stop 的已确认业务终态可 CONFIRMED，不套未知停止规则。

authority：MPD 提供实际 identity/state，PlaybackService 提供绑定及同步诊断，Library 提供本地 Song 元数据，StateService 只聚合。queue.items 的 position=0 与 current_song 在不同步时是最后业务 current，客户端不得把它渲染为已确认实际 Now Playing。实际陌生项可显示 URI/entry 与“未绑定”；没有观测则显示未知，不能以旧歌曲代填。实际 progress 不另增字段，未匹配时保持 null；本轮不扩展任意外部 metadata/完整 Context/History active 重建。

兼容：保留 protocol_version=1、所有原字段与 REST mutation 回执；只新增上述观察字段，旧消费者可忽略未知字段。新消费者缺字段时按 actual unknown、绑定未确认处理，不因服务降级回旧版本而误认 current。GET 与 WS 首帧必须用同一扩展模型；Task4 corrective 拥有 Service 数据，Task6 表示 owner 修改 domain/public realtime DTO 和聚合映射；Task8 将来实现展示，此计划不实现前端。

| 验收场景 | 必须得到 | 不能声称恢复 |
|---|---|---|
| 浏览器刷新/全新浏览器（服务未重启） | 无旧内存的 initial full snapshot，与 GET/Service 全字段相同；有效绑定时已确认 actual 与业务一致 | 不依赖旧消息补出状态 |
| WebSocket 重连 | 新完整快照，订阅/capture 无缝交接，epoch/sequence 水位及迟到 GET 拒绝仍成立 | 不重放业务/History，不以 socket ACK 当播放确认 |
| 服务进程重启 | 新 realtime epoch；持久 Queue/History/Playback 保留；actual 经新只读采样可 fresh，绑定 UNBOUND、runtime active/session 不虚构 | 不把旧 Queue ID/URI 自动认回 MPD ID；业务接管须明确动作 |
| MPD 重启/断线重连 | 实际先 stale/unknown，成功一致采样后恢复 actual；旧 connection binding 失效，显示不同步 | 不沿用复用 ID、不追补断线期间原因 |

有效绑定情况下 runner 的成功领域提交最终使业务 current 与 actual 一致，联合失效通知在 outer commit 后传播；失效绑定情况下按第一章 §8.9.2 明确接管。读路径始终不控制、不丢弃 active、不同步执行队列。所有新表示的序列变化与 snapshot 同一可见性边界；旧样本不能覆盖新绑定，fresh actual 的变化也不得静默漏通知。新增字段和上述验收均未实现/未执行；不改变历史 Task6 只读 proof 的意义，不解除 final gate。

## 13. Output Manager

首期定义：

- `NAS_DAC`
- `CLIENT_STREAM`

输出状态至少支持：

- `UNAVAILABLE`
- `INACTIVE`
- `PREPARING`
- `ACTIVE`
- `SWITCH_FAILED`

切换输出模式默认保留：

- 当前歌曲
- Queue
- Playback Context
- 尽可能准确的播放位置

Output Manager 不直接暴露 MPD 内部细节给 Web 客户端。

## 14. 关于页与 MPD 信息

服务端可以提供 MPD 信息 API。

内容参照现有 myMPD 的信息维度：

- MPD 版本
- 运行时间
- 歌曲数量
- 专辑数量
- 艺术家数量
- 曲库总时长
- 曲库更新时间
- 累计播放时长
- MPD 连接状态

不首期实现 NAS CPU、内存、磁盘等复杂系统监控。

## 15. SQLite 备份与恢复

自动备份：

- 每日一次
- 保留最近 7 份

同时提供：

- 手动备份
- 手动恢复

恢复前必须：

1. 校验备份文件可读取
2. 校验 SQLite 完整性
3. 校验数据库结构
4. 停止或隔离正在写入数据库的业务
5. 执行恢复
6. 重新启动服务
7. 进行健康检查

备份目录与当前数据库目录分离。

备份内容：

- SQLite 数据库
- 服务端配置文件

不备份音乐文件。

配置可能包含 MPD 密码，因此备份文件必须限制访问权限。

## 16. GitHub 代码管理

GitHub 仓库：

`qyxx2/MPD-Server`

GitHub 是唯一正式代码源。

手机是主要开发环境；群晖主要承担：

- 拉取正式代码
- 构建/部署
- 真实 MPD 联调
- USB DAC 实机验收

群晖不作为源码的主要编辑环境。

### 16.1 分支策略

```
main
├── feature/*
├── fix/*
└── refactor/*
```

规则：

- `main` = 可部署稳定分支
- 新功能在 `feature/*`
- Bug 修复在 `fix/*`
- 必要的内部重构在 `refactor/*`
- NAS 默认只部署 `main`
- 不直接在 NAS 修改源码

手机开发完成后：

`修改 → 本地测试 → commit → push → 合并 main`

然后 NAS：

`git pull → 构建 → compose up -d → healthcheck → 实机验收`

### 16.2 Commit

Commit 应保持小而明确，例如：

- `feat: add queue reorder API`
- `fix: restore playback state after websocket reconnect`
- `refactor: isolate mpd adapter`
- `docs: update deployment specification`

不要把多个互不相关的修改压成一个巨大 commit。

### 16.3 Tag

稳定版本使用 Git Tag：

- `v0.1.0`
- `v0.1.1`
- `v0.2.0`

Tag 表示可复现的稳定版本。

正式发布后，Docker 镜像可以使用对应版本 Tag。

Tag 是回滚的主要依据之一。

## 17. NAS 一键更新

生产环境提供：

`deploy/update.sh`

目标是把 NAS 上的部署过程固定成：

```
检查工作区
↓
git fetch
↓
确认目标 main
↓
git pull
↓
构建镜像
↓
docker compose up -d
↓
healthcheck
↓
输出部署结果
```

脚本必须在以下情况下停止，而不是继续部署：

- 本地工作区存在未提交修改
- Git pull 失败
- Docker build 失败
- Compose 启动失败
- healthcheck 失败

部署脚本不允许自动覆盖 NAS 上的本地源码修改。

回滚优先使用 Git Tag 或已知稳定 commit：

```
git checkout <stable-tag>
docker compose build
docker compose up -d
```

生产部署与代码编辑严格分离。

## 18. 发布流程

首期采用人工发布：

### 开发

```
手机
→ feature/*
→ 本地测试
→ commit
→ push
```

### 合并

```
feature/*
→ main
```

### NAS

```
git pull main
→ docker build
→ docker compose up -d
→ healthcheck
→ 真实 MPD / USB DAC 验收
```

### 稳定版本

```
main
→ Git Tag
→ 稳定版本
```

首期不启用 GitHub Actions 自动部署。

未来如果项目稳定，可增加：

- GitHub Actions
- 自动测试
- Docker 镜像构建
- GitHub Container Registry
- Tag 自动发布

这些不属于首期实现范围。

## 19. 测试体系

首期测试分四层。

### 19.1 Server Unit Tests

覆盖：

- Queue
- AutoPlay
- Playlist
- Favorites
- History
- Library
- Output Manager
- Repository
- 状态转换

### 19.2 API Tests

验证：

- REST API
- 参数校验
- 错误响应
- WebSocket
- 状态广播
- 重连后的完整状态恢复

### 19.3 Mock MPD Integration Tests

使用 Mock MPD 验证：

- Music Server 与播放 Adapter 的协议边界
- play/pause/stop
- next/previous
- seek
- Queue 同步
- 播放状态同步
- MPD 异常处理

### 19.4 Real MPD Acceptance

真实 MPD 0.23.5 只做手动验收：

- 实际播放
- DAC 输出
- 输出切换
- 曲库更新
- 长时间运行
- WebSocket 重连
- NAS 重启后的恢复

首期不做复杂浏览器 E2E。

### 19.5 Cross-Authority Contract Matrix

跨模块 relationship/invariant test 负责证明“多个模块或权威之间的关系仍成立”；**Contract Matrix** 负责在实现前把这种关系写成可执行的操作合同。两者职责不同，但必须可追溯。

Contract Matrix 不是新的并列规格源，也不得覆盖本目录中既有业务规格。长期业务语义仍由相关 Spec 定义；当前 Task 的 active plan 只把这些语义整理为可实施、可审计的 Contract rows，并映射到 executable invariant tests。

合同分为五类：

- **STATE_TRANSITION**：一个操作使两个或更多权威状态共同变化，例如 PlaybackState / PlayerPort / History。
- **REPRESENTATION**：同一资源跨 Repository、Service、REST、WebSocket 或客户端表示时必须保持的语义。
- **STATE_PROPAGATION**：权威状态经 event、WebSocket、client store、UI 等链路传播和恢复时必须保持的关系。
- **TRANSACTION**：持久化状态、运行时状态、幂等记录和外部副作用在 commit / rollback / retry 中的关系。
- **LIFECYCLE**：backup/restore、build/deploy/healthcheck 等多阶段流程允许的状态推进和失败恢复。

当一个 Task/Batch/corrective 新增、修改或依赖上述任一跨模块关系时，必须在当前 Task active plan 中建立或引用稳定的 Contract ID。单纯局部计算、无共享状态/表示/事务/外部副作用的实现可以标记 Contract Matrix N/A + 原因。

每个 Contract row 至少定义：

1. **Contract ID / Type / Operation**；
2. **Preconditions**；
3. **Authorities**：哪些模块、持久化状态或外部系统拥有独立事实；
4. **Expected State Delta**：成功后允许且必须发生的变化；
5. **Must Remain Unchanged**：成功操作不得意外改变的关键状态；
6. **External Confirmation**：存在 PlayerPort、文件系统、部署环境等外部权威时，什么事实必须被实际确认；
7. **History/Event Semantics**；
8. **Transaction Boundary**；
9. **Failure/Rollback**；
10. **Retry/Idempotency**；
11. **Observable Result**；
12. **Executable Invariant Proof**。

强制规则：

- 对有副作用的跨权威操作，Must Remain Unchanged 与 Expected State Delta 同等重要，不能只描述“要改什么”。
- 外部权威存在确认步骤时，服务端不得在确认前把目标状态、History/Event 或 terminal idempotency result 当作成功提交。
- SQLite rollback 不能回滚外部系统副作用；这类路径必须显式定义 reconciliation / retry 行为。
- 如果实施过程中发现 Contract row 需要一种 Spec 尚未定义的新业务语义，先修正唯一权威 Spec，再更新 Contract Matrix、建立 RED invariant proof，最后修改 production code；不得从现有实现反推并固化未批准语义。
- 已完成历史 Task 不因本规则自动重开；后续工作一旦触及其 Contract row，该 row 即成为 regression obligation。
- 当前 Task 的 active plan 保存仍在执行的 Task-specific Contract Matrix；完成证据和历史命令进入 archive，不把同一合同复制成多份长期权威。
- Task/Batch 完成前必须能建立 Contract ID → authoritative Spec → implementation owner → executable invariant test → fresh verification 的追溯链。


## 20. 统一开发检查命令

项目最终应提供统一命令入口，例如：

```
make test
make lint
make typecheck
make build
```

或提供等价的脚本命令。

至少覆盖：

- Python 单元测试
- API 测试
- Mock MPD 集成测试
- TypeScript 类型检查
- Web 生产构建

首期不要求 GitHub Actions，但命令结构必须适合未来直接接入 CI。

## 21. 日志与健康检查

服务端必须输出可定位问题的日志，至少区分：

- API
- WebSocket
- Library Scan
- Playback
- MPD Adapter
- Output
- Database
- Backup

生产 Docker 配置需要日志轮转，避免长期运行导致磁盘被日志占满。

Healthcheck 至少能够确认：

1. FastAPI 进程可响应
2. SQLite 可访问
3. 必要情况下 MPD 连接状态可获得

MPD 本身不可用时，Music Server 容器不应因为单纯 MPD 暂时不可达而陷入无法恢复的启动循环；应能够启动并明确报告 MPD `UNAVAILABLE`。

## 22. 安全边界

首期重点：

- Music 目录只读
- SQLite/配置/备份使用持久化目录
- MPD 密码不写入前端
- MPD 只由服务端访问
- 浏览器不直接访问 MPD TCP 端口
- 反向代理 HTTPS 由群晖承担
- WebSocket 使用 HTTPS 环境下的 WSS
- 配置和备份文件限制权限

首期不设计复杂多用户权限系统，除非后续需求明确增加。

## 23. 目录最终形态

```
music-player/
├── server/
│   ├── app/
│   │   ├── api/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── models/
│   │   ├── player/
│   │   └── main.py
│   ├── tests/
│   └── Dockerfile
├── web/
│   ├── src/
│   │   ├── components/
│   │   ├── views/
│   │   ├── services/
│   │   ├── stores/
│   │   ├── styles/
│   │   └── router/
│   ├── public/
│   └── package.json
├── android/
├── deploy/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── .env.example
│   ├── update.sh
│   └── README.md
├── docs/
│   └── superpowers/
│       └── specs/
└── README.md
```

Android 目录首期只保留项目边界，不要求与 Web 同期开发。

## 24. 首期明确不做

以下内容不进入首期实现：

- Kubernetes
- PostgreSQL
- GitHub Actions CI/CD
- GitHub Container Registry 自动发布
- 复杂 Web 管理后台
- 多用户权限体系
- NAS 系统资源监控平台
- Music Server 内嵌 MPD
- Music Server 自动管理 MPD 进程
- 浏览器直接连接 MPD
- 修改/删除原始音乐文件
- 复杂浏览器 E2E
- Android 客户端与 Web 同期实现

这些能力以后可以在不破坏当前接口边界的情况下增加。

## 25. 架构原则

1. **Music Server 是业务权威。**
2. **MPD 是首期播放引擎，而不是整个 Music Server。**
3. **客户端不直接访问 MPD。**
4. **Queue、History、Playlist、Playback Context 保持独立。**
5. **数据库访问必须经过 Repository。**
6. **MPD 访问必须经过 Adapter。**
7. **真实 MPD 与 Mock MPD 使用同一接口。**
8. **开发环境和生产环境数据完全隔离。**
9. **NAS 负责部署和实机验收，不负责日常源码编辑。**
10. **GitHub 保存正式代码历史，main 是默认生产部署来源。**
11. **稳定版本使用 Git Tag 标记。**
12. **所有生产数据必须位于容器之外的持久化目录。**
13. **首期优先保证接口稳定，再增加自动化基础设施。**
