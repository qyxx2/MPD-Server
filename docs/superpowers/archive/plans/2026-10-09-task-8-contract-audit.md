# Task 8 Contract Audit — 实施前决策记录

状态：**2026-10-09 决策索引保留；2026-10-10 全局 UI 合同同步。本文不独立报告当前 implementation/GREEN；实际 W1–W5 产物及未关闭 Gate 以 Web Batch Plan、最新 acceptance 与代码/测试共同核对。Task 8 尚未整体验收，本轮仅文档修订。**

审计基线：`docs/web-common-contract-preflight`，`e3a15b3`。本次基于文档和代码静态核对，未运行测试，不重新宣告 Task 0–7 验收通过。用户授权启动合同审计；下列建议不等于已经接受的产品决定。

## 1. 目标与范围

为 Task 8 的共享 Web 基础和 Player 确定实施前提、接口缺口、专项合同及证明要求，再推导 Batch。Task 9 只保留依赖与增量审计清单，待 Task 8 接口落地后另行审计。当前不实现 UI、不修改后端接口、不安装依赖、不提交或推送。

本记录是 Task 8 active plan 引用的合同/证明索引，不成为第二份产品 Spec。长期规则已回写对应既有 Spec；Task scope/dependency 已回写主 Plan。实施入口为 [后端前置计划](2026-10-09-task-8-playback-control-prerequisite-plan.md) 与 [Web Batch Plan](2026-10-09-task-8-web-batch-plan.md)；本记录保留决策来源与客户端 Contract rows，不重复 Batch 指令。

## 2. 已冻结依赖：引用，不重新决定

| 来源 | 本 Task 继承的合同 |
|---|---|
| [Architecture §4.1–4.3](../specs/2026-09-25-system-and-development-architecture-design.md) | 状态三层、请求代次保护、degraded read-only、mutation/idempotency、静态壳 PWA |
| Architecture §12；[Task 6 plan](2026-10-03-mpd-server-task-6-batch-plan.md) | initial snapshot、最高失效水位、跨 epoch 恢复、actual/binding/observation 语义 |
| [Playback §3–8.9](../specs/2026-09-24-playback-model-queue-semantics-design.md) | Start Track 与 Play Now 区别、Queue occurrence、进度权威、重启后明确接管、Stop |
| [Library §3、§5–7](../specs/2026-09-24-library-playlist-tag-search-design-2-1.md) | 歌词来源与时间戳、membership 与 playable collection、Favorites、资源 revision |
| [Output §6–8](../specs/2026-09-24-system-architecture-playback-output-design.md) | observed fact/request 分离、输出切换保留关系、未知值与 About |
| [全局 UI 合同](../specs/2026-10-03-web-pwa-visual-design.md) | WEB-UI-* 唯一视觉/通知/背景/布局/四项导航合同；保护当前 Player，Task 9 共享壳前置；不重复定义 |
| [主 Plan](2026-09-25-mpd-server-v0-1-implementation-plan.md) | Task scope/dependency、Contract Matrix、Relationship Gate |

共同合同需要实现与可执行证明；不能因为未实现而重新作为产品待决策项。

## 3. 优先关闭的接口边界

### G8-01 — 暂停恢复及 STOPPED 主按钮（合同已接受，实施待执行计划审阅）

证据：`server/app/api/playback.py` 没有 resume endpoint；`PlaybackService.pause()` 调用 PlayerPort.pause，`server/app/player/mpd_adapter.py` 的 pause 固定发送 `pause 1`，不是 toggle。Adapter 存在底层 play 能力不等于已经存在保留关系经验证的业务 resume API。

用户于 2026-10-09 选择：“采用推荐：暂停原位继续；停止后明确选曲”。PAUSED 使用明确 resume，保持当前 occurrence、位置、Queue、Context；明确 Stop 后主按钮不隐式选曲，通过明确 Start/Queue Play Now 重启。此选择不授权未绑定状态自动接管，也不定义未知外部停止为用户 Stop。

AutoPlay 意图与既有 active History 的保留、实际确认/失败/retry 边界及接口已落实至 Architecture §4.2.1 和前置计划 PB-RESUME-001；合同接受不等于后端能力已实现。

决定后归属：Playback Spec 定义状态转移与不变关系；主 Plan 明确后端 prerequisite owner。证明至少覆盖暂停原位继续、重复请求、命令/确认失败、未绑定或实际 current 漂移，不将 resume 变成重新 Start Track。

### G8-02 — 普通歌曲 Play Now 的原子入口（occurrence 选择已接受，其余合同待设计；Task 9 依赖）

证据：Playback Spec §3.3 要求普通 Play Now 保留其他待播内容；`POST /api/playback/tracks/{song_id}/play` 调用 start_track 创建上下文；保留型 `play_now` 接受 queue_item_id。缺少直接面向未入队 song 的保留型原子入口。

用户于 2026-10-09 确认方案 A：Library/Search/Playlist 等普通歌曲入口执行 Play Now 时创建新的 occurrence 并立即播放，保留原有待播项及其相对顺序，包括相同 song 的已有待播 occurrence；不按 song_id 静默去重或移动旧项。Queue 行仍精确操作其指定 occurrence。

用户同日进一步确认方案 A：明确 Stop 后，从普通歌曲入口执行 Play Now 开启新的播放会话并重新启用 AutoPlay，同时保留原待播内容。

建议保持既有产品语义，补服务端单次原子 song Play Now 能力；不得用 Start Track 替代，也不得前端拼接“入队→播放”冒充原子动作。相同用户意图的同 key retry/replay 不能重复创建 occurrence；新的明确用户意图使用新 key。空/停止会话如何建立 context、History 生命周期和不可用歌曲失败边界仍需完成设计。

已接受的产品规则归入 Playback Spec §3.3；暂停恢复与 seek 意图归入 §7.1。本记录保留2026-10-09审计状态，不替代Spec；当前接口实现与Gate须核对active计划/最新acceptance和代码，不能据此判定仍无实现。

决定后归属：Playback Spec；主 Plan 决定该 prerequisite 在 Task 8 前置范围还是 Task 9 前置范围，不默认把所有 Task 9 能力拉入 Task 8。

### G8-03 — seek 意图的曲目身份（合同已接受，实施待执行计划审阅）

证据：`server/app/api/schemas.py::SeekRequest` 只有 seconds；API 调用 `PlaybackService.seek(seconds)`。客户端拖动 A 后发生切歌，发送前检查或取消请求无法保障执行时仍是 A。

用户于 2026-10-09 选择按推荐处理：seek 绑定用户开始操作的 occurrence；服务端在共同执行边界验证目标身份，切歌/代次失效时拒绝，客户端放弃草稿并重读。不得把过期 seek 改发到新 current；重新拖动属于新的用户意图。

跨 epoch/绑定失效前置条件、typed conflict 和旧 API 兼容策略已落实至 Architecture §4.2.1 与前置计划；不能仅添加前端字段而服务端不校验。证明覆盖发送后切歌、重复 URI、重连及同 key replay。

接口设计必须区分首次执行的目标校验与已提交 terminal replay：原操作已成功后，重复相同 key 应沿用既有幂等合同返回原回执，不因 current 已改变而重新执行 seek。queue_item_id 或 song_id 单独不足以证明绑定代次未变化；前置条件也不应直接使用每次 elapsed 采样都推进的 realtime sequence，避免正常播放导致无意义冲突。具体字段和验证边界在完整合同设计时确定。

### G8-04 — 进度与歌词展示时钟（产品选择已接受，算法合同待设计）

用户于 2026-10-09 确认方案 A：有效、已绑定且实际播放的样本之间允许平滑显示估算；暂停、过期、断线、绑定失效停止外推；新样本到达后校准。歌词与进度条共用展示时钟，不以估算驱动领域操作。长期规则归入 Playback Spec §7.2。

具体合同仍需明确：服务端 observed_at 与浏览器单调时钟的映射、网络延迟与页面后台恢复、已知 duration 的展示上界、未知 duration 的禁用条件，以及 seek draft/pending 与 observation 校准的优先关系。不得直接用两个设备的墙上时钟差假设网络延迟，也不得后台恢复后无限补算。

证明应使用 FakeClock 和可控请求交错，覆盖暂停、stale、重复歌曲切换、后台恢复、seek 前旧样本迟到；断言只改变展示估算，canonical snapshot、Queue、History 与 AutoPlay 不变。

## 4. Task 8 专项审计队列

用户于 2026-10-09 确认松手单次 seek，并授权后续非重大选择由审计者按合适逻辑决定。已落实的交互归入 Playback Spec §7.3–7.4、Library Spec §3.1 歌词补充。下表仍跟踪证明与接口设计的剩余工作，不表示这些能力已实现。

| 议题 | 需落实的边界 | 最小证明目标 |
|---|---|---|
| Player 状态/操作矩阵 | actual 与最后业务歌曲分别表达；各 sync_status 的控件条件；WS 可写不等于 MPD 已绑定；NO_CANDIDATES 仍可能匹配 current | 未绑定不伪装实际 Now Playing；明确 Stop/接管入口符合既有合同 |
| 进度和 seek 生命周期 | 插值已选 G8-04；待落实有效期、后台恢复、unknown duration、drag draft、发送频率、pending 结束、成功但未同步与未知结果 | 旧 observation 不串曲；HTTP receipt 不成为动态时钟；失败不伪造位置 |
| LRC 同步 | 支持语法、offset/多时间戳/异常行；手动滚动及恢复跟随；切歌清理 | 同一展示时钟；plain text 不伪造同步；迟到歌词不串曲 |
| mutation 交互 | 连点、并发意图、timeout、同 key retry、HTTP 成功后 read 失败 | 已失败/结果未知/已成功待同步可区分；不重复执行业务 |
| Output | 既有合同/独立实现保留；Player卡片/启停入口已移除，设置接入归Task9；confirmed fact 与 last_request 分层 | 失败请求不覆盖已确认输出；CLIENT_STREAM 不冒充已支持 |
| Web harness / 手机人工验收 | 测试目录、依赖选择、精确命令、DTO 一致性、LAN 手机触摸及报告边界；PWA 延期 | REST/WS→store→UI；恢复 PWA 时静态缓存不得处理 API/业务 replay |

以上工具缺口是2026-10-09审计基线；当前工作区已存在 Vitest、tests/invariants 与相关 scripts。各 Batch 的实际验证入口见 Web Batch Plan，本轮不安装依赖或将历史 GREEN 当作 fresh 证明。

## 5. Task 9 留待后续的增量

- Queue：snapshot occurrence/position 驱动三分区；Played 不替代永久 History；展开数量、顺序、context/Stop/epoch 重置条件。
- 并发拖动：current/AutoPlay/其他客户端变化时取消或重定位草稿；现有 QueueReorderRequest 无客户端 expected_revision，内部 CAS 不等于用户所见版本保护。
- SongRow：普通 song 与 Queue occurrence 的三项操作映射、unavailable 状态；继承 G8-02 决定。
- Save as Playlist：既有 Up Next 范围不重定；核对重复 occurrence 到禁止重复 membership 的规则，明确提交时最新内容与用户预览的关系。
- Playlist/Favorites：完整排序请求与并发成员变化、draft 冲突、跨页 pending/确认；星形“立即切换”不得覆盖 Architecture 禁止 speculative commit 的规定。
- Library/Search：Collection IDs 到 Song 表示、空查询、迟到结果、不可用项、集合操作范围；不把 playable collection 当完整 membership。
- navigation/Settings：继承 WEB-UI-NAV/SHELL/NOTIFY/BG 已冻结映射，先交付共享壳/背景/导航再扩展内容；只审计详情返回、草稿/跨页pending生命周期及证明，不重定导航项。不提前实现 Task 10 管理或 CLIENT_STREAM。

当前歌曲删除、AutoPlay、Playlist 禁止重复等已有历史合同，应继承并核对实际代码/测试，不把它们重新标为未定义。

## 6. 审计退出与实施 Gate

Contract Matrix：**REQUIRED**。Relationship / Invariant Gate：**REQUIRED**。

- [x] 核对分支、最新共同 preflight、实际 API/Service/Adapter 关键边界。
- [x] 区分共同冻结合同、Task 8 新增决策、Task 9 后续增量。
- [x] G8-01 / G8-03 接口与 owner 方案获接受；G8-02 原子入口留待 Task 9，不虚构 Task 8 完成该能力。
- [x] Task 8 专项行为选择与已接受公共接口回写既有权威 Spec。
- [x] 用户接受书面接口方案，建立 Task 8 Contract rows 与两个执行计划供下一步审阅。
- [x] row 通过共同字段和专项表明确 Preconditions、Authorities、Expected Delta、Must Remain Unchanged、External Confirmation、History/Event、Transaction、Failure/Rollback、Retry/Idempotency、Observable Result、Executable Proof。
- [x] 两个执行计划列明新建/继承 Contract IDs 与 Task 5/6/7、D6 相关回归。
- [x] Web 测试工具、拟创建 script/命令、自动/人工验收边界已写入执行计划；工具兼容版本在 W1 实施时核验，当前无 GREEN 声明。

当前结果为决策登记与专项合同草案；Task 8 Steps、Task 9 Steps 和验收状态均未改变。

## 7. 后端前置方案：2026-10-09 已接受

### 7.1 接受的 additive 方案

推荐最小 additive 扩展：新增显式 resume endpoint；既有 seek body 增加可选 target，Web 必须发送 target；snapshot 增加 nullable control target。旧调用方的无 target seek 保持原合同，但不具备 Web 所要求的防串曲保证。Web 收到不支持 target 的旧服务器状态时禁用 resume/seek，不能降级到无保护调用。

用户已接受本节 additive 方案与 owner 划分。权威 wire 合同归入 Architecture Spec §4.2.1；不采用 breaking 必填 target 或另建 seek endpoint 的替代路线。

已接受、待实现的 wire surface：

- `playback_observation.control_target: {queue_item_id: string, token: string} | null`，GET/WS 相同表示。token 是服务端不透明的条件令牌，不是认证凭据，不持久化到浏览器。
- `POST /api/playback/resume` body `{target: {queue_item_id, token}}`，沿用 Idempotency-Key，成功返回已确认 PlaybackState。
- `POST /api/playback/seek` body `{seconds, target?: {queue_item_id, token}}`；只有有 target 的请求承担此处新增防串曲合同。
- 首次执行时目标不匹配返回 typed 409 `PLAYBACK_TARGET_CONFLICT`，业务无变更；格式错误仍为 422，MPD 错误沿用现有错误边界。terminal replay 在校验前按既有 middleware 返回原结果。

### 7.2 target 必须提供的保证

由 PlaybackService 持有，不允许 API 自己拼装 binding：token 绑定服务进程、有效 MPD 连接/绑定生命周期以及 current occurrence 的控制代次。正常 elapsed 样本不能让它变化；current 离开再回来、同 occurrence 显式重播、连接/绑定失效或服务重启必须使旧 token 失效。不能直接暴露 realtime sequence，也不能仅依赖 queue_item_id。

对首次执行，Service 在既有共同事务/串行边界内校验 token，并在命令前重新核验实际 current 与完整受控执行关系；不能只相信缓存 fresh。snapshot capture 只导出已有 target，不进行 MPD I/O 或恢复操作。stale/unknown/未绑定 observation 导出 null，不能凭 URI 生成 target。

命令后回读确认实际 identity/state；resume 保留位置（播放后的正常时间推进允许）、Queue membership/order、Context、AutoPlay 意图及 History active/session，不产生新播放事件。已经 PLAYING 且目标仍匹配的 resume 为确认后的 no-op，不重新开始。seek 保留相同关系，仅允许确认后的位置变化及相应传播。

原版 MPD 的命令并非跨客户端物理事务：请求目标保护约束本服务可验证的身份和执行边界，不能宣称消除任意外部客户端在多条 MPD 命令间插入操作。确认失败须按现有 reconciliation/部分执行合同报告，不伪装业务成功；新测试必须包含这种失败。

后端target的mint/失效/rollback与recovery journal接线归prerequisite plan；“API尚不存在”是原审计基线，当前接口已存在，证明/运行时限制读取后端前置acceptance并核对代码，不由本文重新认证。

### 7.3 owner 与 Task 范围

- Task 8 必需 prerequisite：resume 与 guarded seek，以及完整 snapshot 的 target 表示。建议以独立后端前置计划交付，证明通过后 Task 8 Web 使用；不把它塞进 Player 组件实现。
- 普通 song Play Now 是 Task 9 SongRow prerequisite：产品选择已记录；Context/History 精确生命周期和原子接口在 Task 9 审计关闭。Task 8 不展示一个尚无实现的通用歌曲菜单，也不宣称完成该能力。
- Architecture/Playback Spec 和主 Plan 已同步本次接受的接口与依赖，未勾选任何实施 Step。

## 8. Task 8 专项 Contract rows 与状态矩阵

本节 rows 的诊断/错误/无候选/未知等可见说明统一引用 WEB-UI-NOTIFY-001；业务事实保持原位，不能用下表的“提示”措辞建立第二个通知位置。本文 DRAFT 是原审计设计标记，实际交付/Gate 见 active Batch Plan，不据此断言代码尚不存在。

以下新 ID 只覆盖 Task-8-specific 消费行为，不复制共同 Web authority/cache/reconnect/idempotency rows。六行消费语义已确定；表中DRAFT保留原审计设计标记，不表示当前proof尚未实现或公共接口仍待决定；实际状态只读取active计划/最新acceptance并核对代码。

### 8.1 共同 row 字段

每行由本节共同字段与下表专项字段共同组成：

- **Preconditions**：当前连接成功接受完整 snapshot；mutation 另需连接可写及该操作的前置条件，不能用 UI enable 替代 Service 校验。
- **Authorities**：Architecture §4.1 的 canonical snapshot/resource cache；UI draft/clock/pending 仅是本地交互。
- **Must Remain Unchanged**：客户端读、显示、重连不修改服务端 Queue/Context/History/AutoPlay/Output；mutation 继承其领域保留关系。
- **External Confirmation**：mutation HTTP 为 endpoint 回执，WS invalidate 不作 ACK；snapshot/resource read 收敛，旧请求结果按共同合同丢弃。
- **History/Event**：前端不能合成业务 History 或完成事件；服务端操作沿用各领域确认与 outer commit。
- **Transaction Boundary**：服务端既有 Service/Repository 原子边界；浏览器不声称跨请求事务，接受一个 snapshot 时完整替换相应 canonical cut。
- **Failure/Rollback**：失败保留最后确认事实；外部实际副作用可能已发生，按 typed error/unknown/reconciliation 表达，不能伪报完全回滚。
- **Retry/Idempotency**：Architecture §4.2；同 payload/method/path/key retry，已提交 replay 不重新执行。GET 可重读；重连不自动重放 mutation。

| 新 ID / 状态 | 操作与额外前置条件 | Expected Delta / Observable Result | 专项确认与保留 | Executable Invariant Proof（拟新增，不是已存在测试） |
|---|---|---|---|---|
| WEB-PLAYER-FACT-001 / DRAFT | 接受 actual 与业务 current 表示 | actual 未绑定时显示 URI/未知及诊断；最后业务歌曲明确分层 | position=0/current_song 不单独证明实际 Now Playing；不从 Queue 推断原 Context 名称 | `web/tests/invariants/player-facts.test.ts`：fresh actual≠业务 current、字段缺失、NO_CANDIDATES 且匹配、UNCONFIRMED_STOP |
| WEB-PLAYER-CONTROL-001 / DRAFT | 各状态下显式按钮操作；resume 依赖 prerequisite | pending→HTTP receipt→权威重读；明确 Stop 后不隐式 resume | resume 保留 occurrence/position；冲突不重播；Stop 不冒充取消旧请求 | `web/tests/invariants/player-controls.test.ts`：按钮→真实 client/store→模拟 HTTP/WS；重复操作、timeout、断线禁用、旧响应迟到 |
| WEB-SEEK-001 / DRAFT | 有效 target、已知正 duration；松手提交 | draft 与 canonical 分离；一次请求；冲突撤销草稿 | 仅目标 occurrence；同 key replay；成功但 observation 未更新不伪造位置 | `web/tests/invariants/player-seek.test.ts`：拖动期间/发送后切歌、重复 URI、unknown duration、失败、成功旧样本 |
| WEB-PROGRESS-001 / DRAFT | fresh、matches_current、bound current、actual playing | 单调时钟有限外推，新样本校准；暂停/stale/后台停止 | UI clock 不提交 position、不触发 next/history | `web/tests/invariants/player-clock.test.ts`：FakeClock、重复样本、后台恢复、duration 上界、跨 epoch |
| WEB-LYRICS-001 / DRAFT | 当前 Song 的 API lyrics 与有效显示进度 | 同时 cue 高亮、继承 Library §3.1 已冻结的3秒恢复跟随/cue seek、缺失/失败在顶部详情区分 | 源文本不改写；无时间文本不伪造同步；迟到歌词不串曲 | `web/tests/invariants/player-lyrics.test.ts`：clock/store→歌词、切歌、offset、同时间 cue、fallback read_error |
| WEB-OUTPUT-001 / DRAFT | NAS_DAC 独立合同实现保留；Player仅confirmed摘要，设置入口归Task9；共同门禁 | confirmed fact 与 pending/last_request 分开；通知位置引用WEB-UI-NOTIFY | 输出操作不改播放意图；未知参数不补值；CLIENT_STREAM 显示预留不可用 | `web/tests/invariants/player-output.test.ts`：失败保留事实、camelCase REST→snake_case realtime 显式映射、迟到回执 |

### 8.2 Player 控件矩阵（界面限制，不改变服务端权限）

| 状态 | 表示 | 控件 |
|---|---|---|
| 没有可信 initial snapshot / WS degraded | stale 或 disconnected | 所有服务端 mutation 禁用；本地切换/只读浏览可用 |
| fresh 匹配 current，actual PLAYING | 已确认当前歌曲及进度 | pause、next、具有 Played 候选的 previous；正 duration 且有 target 时 seek；Stop |
| fresh 匹配 current，actual PAUSED | 已暂停，进度不外推 | 有 target 时 resume/seek；next/previous 按已有候选规则；Stop |
| NO_CANDIDATES 且仍匹配 current | 当前播放 + 无候选提示 | 保留 pause/resume/seek/Stop 的对应条件；不虚构下一首，next 无可见候选时禁用 |
| UNBOUND/EXTERNAL_DRIFT/UNCONFIRMED_STOP/SYNC_FAILED 或 observation stale | actual 与最后业务状态分层，未知进度不补零 | 保留显式 Stop；禁用依赖可信 current 的 resume/seek/next/previous/pause；明确选曲接管由既有播放入口提供 |
| 已确认用户 STOPPED | 已停止，旧歌曲仅为最后业务歌曲 | 主播放按钮不自动选曲；明确歌曲/Queue Play Now 入口在 Task 9 提供 |

controls 的禁用不改变已冻结后端 API；恢复 Web writable baseline 也不自动满足 current-specific 前置条件。Output 独立使用自身事实和错误，不把 playback 未绑定简单映射为 Output 不可用。

## 9. 常规技术选择与验证清单

### 9.1 展示时钟

以服务端 `captured_at - observed_at` 的非负差计算样本在 capture 时的年龄，再加本次 HTTP round-trip 的保守上界；全程不相减两台设备的时钟。应用样本后仅用浏览器 monotonic clock 计时。无法得出可靠年龄、服务端时间倒退或首帧 WS 长时间延迟时，先显示服务端值但不开启外推，启动可计时 GET 取得基线。

v0.1 Web 最多外推 6 秒减已知样本年龄，与服务端默认观察 stale 上限一致；服务端更早报告 stale 时立即停止。此客户端上限为保守展示限制，不改变服务端可注入 max_age。elapsed 取服务端值作为锚，不为估计网络延迟预加进度；新样本直接校准。键盘 seek 在 keyup/blur 结束一次编辑提交；Escape 撤销且不提交；pointercancel 同样撤销。

### 9.2 测试基础与 typed client

建议 Vitest + Vue Test Utils + jsdom，复用 Vite 配置；原生 Vue reactive/composable store，路由使用 Vue Router。只在获准实施相应基础 Batch 时添加依赖和 lockfile，不修改 Python .venv。具体兼容版本需依据届时 Node/package lock 验证，不在当前文档猜测版本。

建议入口：`npm --prefix web run test -- --run`、`npm --prefix web run test:invariants -- --run`、现有 typecheck/build。这些scripts当前工作区已存在；具体执行选择按active Batch Plan，此处不是本轮运行结果。

relationship tests 使用真实 Web API client/realtime adapter/store/composable/component，替换的是网络和时间边界；不能把 store 和 client 全部 mock 后称为跨层证明。DTO 对齐使用后端实际 Pydantic 序列化的固定场景 fixture，明确 nullable、unknown enum、snake/camel alias、WS envelope 校验；TypeScript 编译不能替代 wire 校验。新协议主版本未知或首帧损坏时 fail closed，显示连接错误，不恢复 mutation。

共同合同另需证明：旧连接/epoch/sequence/resource generation 不倒灌、刷新覆盖最高失效水位、同 key retry、断线只读→initial snapshot 恢复；这些是继承 proof，不另建冲突业务规则。2026-10-09 用户调整后，PWA manifest、同源 standalone shell 与 SW proof 延期；恢复该范围时仍须证明 API network-only/无 replay，不阻塞当前手机 Web Gate。

自动验证范围：各 row 的窄测试→对应文件→相关 invariants→typecheck/build；若补后端，按 .venv 运行所影响的 Task 5/6/7 与 D6 suites。精确后端测试选择由 prerequisite plan 根据实际改动列出，不用全套 GREEN 替代 targeted gate。

人工验收：手机浏览器显示/触摸为主，通过实际 LAN 地址/端口实测，断线与后台恢复按对应 Batch 执行；Ubuntu 浏览器仅辅助窄屏、放大文字、键盘、reduced-motion、无 backdrop-filter 检查。不要求桌面专用显示；安装与冷离线壳 DEFERRED，不新增验收场景控制台。具体方法/报告见 [手机 Web 真人验收方法](2026-10-09-mobile-web-manual-acceptance.md)，必验编号以 Web Batch Plan 为准。真实 MPD/NAS 的 resume 原位继续与 seek 确认需单列运行时验收；不由浏览器 mock 测试替代，也不在本次文档审计联系外部设备。

## 10. 本轮输出与下一步

2026-10-10文档同步：全局UI表达只引用唯一Visual Spec，当前Player与已冻结歌词保留；设置/导航及背景接入先于Task9内容扩展。Task8仍按active Web Batch Plan完成未关闭真人Gate与W6，不由本次审计关闭。

原P1–P3/W1–W6设计与历史决策保留；当前实际产物、测试入口、未关闭Gate须核对代码/测试及最新acceptance。本文不声称本轮执行了测试，也不再以原“尚未实施”结论覆盖工作区成果。
