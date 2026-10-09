# 第一章：Playback Model & Queue Semantics

> 项目：基于 MPD 0.23.5 的自建音乐播放器前端与服务层\
> 文档状态：设计规格（第一章）\
> 目标：定义播放会话、Queue、播放历史、临时播放集合、用户自定义 Playlist
> 与 AutoPlay 的统一语义，作为后续服务端
> API、数据模型和客户端交互的基础。

## 1. 设计目标与原则

本播放器以 MPD
作为现有播放引擎，在其上构建统一的音乐播放模型。客户端不直接依赖 MPD
的内部队列语义，而是通过 Music Server 操作本章定义的模型。

核心原则：

1.  **Queue 是当前播放会话的可见、可操作队列。**
2.  **任何具体歌曲对象都提供相同的三项 Playback Action。**
3.  **播放一个集合时，默认整体替换当前 Queue，而不是逐首追加。**
4.  **AutoPlay
    是全局兜底行为。在在线、已绑定、执行顺序受控且有可用候选的正常条件下，提前准备后续内容；异常限制见 §8.9。**
5.  **Queue 必须明确展示已确定的下一首；尚未同步或无候选时明确显示该状态。**
6.  **Queue、播放历史、临时播放集合与用户保存的 Playlist
    是不同概念，不得混为一体。**
7.  播放规则由 Music Server 统一执行，避免 Web、PWA、Android
    客户端出现行为分歧。

## 2. 核心对象定义

### 2.1 Queue

Queue 表示当前播放会话中的歌曲顺序，包含：

-   当前播放歌曲；
-   当前会话中已播放或被切换离开的歌曲记录；
-   尚待播放的歌曲；
-   AutoPlay 预先生成的后续歌曲。

Queue 是动态对象，可以被替换、插队、排序、删除和清空。Queue
不是永久保存的歌单。

### 2.2 Playback History

Playback History 是独立于 Queue
的播放历史记录，记录实际发生过的播放事件。建议至少记录：

-   歌曲标识；
-   开始播放时间；
-   结束时间（如可获得）；
-   结束/离开原因，例如自然播放完成、用户切歌、停止；
-   所属播放会话标识。

Queue 中展示的 Played 区域是当前会话已确认离开项的视图，不是完整听歌证明；永久 Playback History
则用于最近播放等功能。清除 Queue
中的历史展示，不应自动删除永久历史。清除永久历史也不应改变当前正在播放的歌曲或待播队列。

#### 2.2.1 History availability 与读取合同（Task 6，2026-10-03）

人工决策 G6-04 / A 定义 snapshot 的 availability；事件持久性及其与 Queue/active session 的独立性沿用本章、Task 2R 与 Task 4/5 已冻结合同。

- **Preconditions**：HistoryService 可读取持久事件与当前 runtime active/session；歌曲之后可以变为 AVAILABLE、MISSING 或 UNREADABLE。
- **Authority / Source of Truth**：History Repository 的已提交事件决定永久历史是否存在；HistoryService 拥有 active event/session；Library 拥有歌曲当前元数据及 availability。三者不互相冒充。
- **Expected State Delta**：只读生成 `history: {has_entries: boolean, active_event: HistoryEvent | null, session_id: string | null}`。has_entries 为存在至少一条持久已提交 History 的判断，不是服务健康、当前歌曲可播放性或 active 存在性。仅有 active 而无持久事件时为 false。
- **Must Remain Unchanged**：读取不结束/新建 active，不清除永久事件、不修改 Queue Played；歌曲后来不可用不删除或过滤其 History，不能把历史事件改写成当前可播放事实。
- **Transaction Boundary**：持久事件、active/session 与 Playback/Queue 在架构 Spec §12.1 的共同切面读取。未提交的 History 不能使 has_entries 提前变 true。
- **Failure / Rollback**：读取失败按 §12.1 整体失败，不能返回 false 冒充空历史。领域 mutation 回滚恢复持久和 runtime History，快照不得暴露中间状态。
- **Retry / Idempotency**：重读不产生事件；既有 mutation replay 不产生重复 History。History 顺序仍沿用既有读取合同，不从歌曲 availability 推断历史排序。
- **Revision / Ordering**：History 变化参与实时 sequence/失效通知；本节不引入 History CAS 或持久 revision。Library availability 变化影响歌曲表示，不改变 History 事件身份/结束原因或 has_entries。
- **Observable Result**：snapshot 不携带全部永久 History。既有 `/api/history` 的事件字段及返回语义保持，包含后来 unavailable 的歌曲事件；歌曲当前信息通过 Library Service/API 按 song_id 读取。MISSING/UNREADABLE Song 保留其身份和已有有效元数据，availability 明确可见；不把不可用 Song 当正常可播放项，也不凭空创建“播放当时的元数据快照”。仅展示当前可播放候选的 Collection 规则不能用于 History 读取。
- **Executable Invariant Proof**：真实 HistoryService/Repository/LibraryScanner/API/StateService 测试覆盖空历史、仅 active、已结束事件、同一歌曲多次播放、扫描后 MISSING/UNREADABLE、恢复 AVAILABLE、runtime/持久 rollback 及读取失败；比较原 history_id/song_id/times/reason/session、条数及 Queue Played 不变，证明 unavailable 事件仍可读取且 has_entries 不随 availability 改变。Task 6 Plan 分配具体 proof，当前未实现。

### 2.3 Playback Context（临时播放集合）

Playback Context 表示一次播放操作所依据的歌曲集合及其来源，例如：

-   专辑；
-   歌手；
-   年代；
-   Genre / 风格；
-   文件夹；
-   搜索结果；
-   标签筛选组合；
-   用户保存的 Playlist。

它描述"这次播放是从哪里、按什么范围发起的"，不等于永久歌单。播放集合时，将其歌曲按指定顺序或随机顺序装入
Queue。

### 2.4 Saved Playlist（用户自定义 Playlist）

Saved Playlist
是用户明确保存、可长期管理的歌曲集合。它支持创建、重命名、排序、添加歌曲、删除歌曲和删除歌单。

从专辑、歌手、年代、Genre 或搜索结果发起播放，不应自动创建永久
Playlist。用户明确执行保存操作后，临时集合或 Queue 内容才可被保存为
Saved Playlist。

### 2.5 AutoPlay

AutoPlay 是全局连续播放机制。在在线正常条件下，当待播 Queue 即将耗尽时，系统生成后续歌曲、提交业务 Queue 并提前同步到 MPD 执行队列，避免等待 STOPPED 后才补充。

AutoPlay 不属于某个专辑或 Playlist
的私有功能。它是播放会话的兜底行为。用户明确 Stop 结束接管；异常停止不改写该意图，但暂停自动控制，见 §8.9.5。

## 3. Playback Action：具体歌曲的统一操作

### 3.1 触发范围

任何界面中出现的具体歌曲对象，都必须能触发统一的 Playback Action
选项框，包括但不限于：

-   专辑曲目列表；
-   歌手页面；
-   Genre、年代、文件夹等分类页面；
-   搜索结果；
-   Playlist 详情；
-   Queue；
-   播放历史；
-   收藏及其他歌曲集合。

### 3.2 必须提供的选项

点击具体歌曲对象时，弹出操作选项框，至少包含：

1.  **Play Now（立即播放）**
2.  **Play Next（下一首播放）**
3.  **Add to Queue（添加到 Queue 末尾）**

这些操作在各页面保持一致，不允许某些分类页面采用不同的隐式语义。

### 3.3 操作语义

#### Play Now

-   将所选歌曲设为当前播放歌曲并立即开始播放。
-   按 §8.9.4 记录已确认的本服务切换事件；不为未经认证的旧 active 补造原因。
-   保留原 Queue
    中尚未播放的其他内容，并将其放在新当前歌曲之后；不得因单纯切换歌曲而无提示地丢弃原有待播内容。
-   若该操作来自一个明确的"开始独立单曲播放"入口，且产品交互将其定义为新播放上下文，则按第
    4.1 节的 Start Track 规则替换 Queue。

**Web 合同补充（2026-10-09，产品选择已接受；接口与实现待完成）**：

- Library/Search/Playlist 等普通歌曲入口的 Play Now 创建新的 occurrence，保留已有待播 occurrence 及其相对顺序，包括同一 song 的重复项；不隐式选取、移动或去重已有 occurrence。Queue 行的 Play Now 仍精确操作该行的 queue_item_id。
- 用户明确 Stop 后，从上述普通歌曲入口执行 Play Now 表示开启新的播放会话并重新启用 AutoPlay，同时保留原待播内容；不因此退化为替换 Queue 的 Start Track。开启意图仍受 §8.9 的在线、绑定、候选与确认限制，不承诺异常情况下自动续播。
- 同一意图的传输重试必须复用既有 Idempotency-Key，不重复创建 occurrence。完整服务端原子入口、Context/History 生命周期与失败确认合同由专项审计补齐；本补充不宣告现有 API 已具备该能力。

#### Play Next

-   将所选歌曲插入当前歌曲之后，成为下一首。
-   不改变当前正在播放的歌曲。
-   多次执行时，应有稳定且可理解的插入顺序；同一歌曲是否允许重复入队由后续产品规则明确，但不得静默去重。

#### Add to Queue

-   将所选歌曲添加到 Queue 待播内容末尾。
-   不改变当前播放歌曲和当前下一首歌曲。
-   不应覆盖现有 Queue。

## 4. 从歌曲或集合开始播放

### 4.1 Start Track：从单曲开始一个播放上下文

从音乐库、搜索结果或其他浏览位置明确发起单曲播放时：

1.  清除并替换原有 Queue 的待播内容；
2.  将目标歌曲设为当前歌曲并立即播放；
3.  创建对应的单曲 Playback Context；
4.  启用 AutoPlay，并预先生成可见的后续歌曲。

因此，在 §8.9.5 的在线正常条件下，AutoPlay 提前补充并同步后续内容；不承诺断线、未知停止或无可用候选时无限续播。

注意：这条规则适用于"开始播放一首独立歌曲"的入口。Queue 内对某一行执行
Play Now 时，按第 3.3 节的 Queue 内切换语义处理。

### 4.2 集合页面的固定顶部操作

专辑、歌手、年代、Genre、文件夹、标签筛选等能够形成歌曲集合的页面，顶部必须明确显示：

-   **全部播放**
-   **全部随机播放**

这两个动作不要求用户逐首添加歌曲。

#### 全部播放

-   取得当前集合中的全部符合条件歌曲；
-   按集合的默认顺序排列；
-   整体替换当前 Queue；
-   停止原歌曲并立即播放新 Queue 的第一首；
-   设置当前 Playback Context；
-   AutoPlay 保持启用。

#### 全部随机播放

-   取得当前集合中的全部符合条件歌曲；
-   对集合进行随机排列；
-   整体替换当前 Queue；
-   立即播放随机排列后的第一首；
-   设置当前 Playback Context；
-   AutoPlay 保持启用。

随机排列应在本次集合播放开始时生成并固定在 Queue
中，不能因界面刷新或状态同步而反复改变已显示的待播顺序。

### 4.3 搜索结果

搜索以用户寻找确定歌曲为主要目的：

-   点击具体歌曲时，仍弹出统一的 Playback Action；
-   搜索结果若支持"全部播放/全部随机播放"，其行为必须明确作用于当前搜索结果集合，并遵循集合替换规则；
-   不得将搜索结果中的单曲点击默认为"立即播放"而跳过操作选项框。

## 5. Queue 的显示与操作

### 5.1 必须展示的区域

Queue 页面至少包含：

1.  **Now Playing**：当前正在播放的歌曲；
2.  **Played**：当前会话中曾确认成为 current、后来离开该位置的 occurrence；不表示完整播放或自然完成（§8.9.3）；
3.  **Up Next**：按确定顺序排列的后续歌曲。

Queue 展示已确定的 Up Next 及执行同步状态。§8.9.5 正常条件成立时，AutoPlay 必须在耗尽前补充并同步到 MPD；无候选或同步失败不得虚构下一首。

### 5.2 Queue 操作

用户应能对 Queue 中的内容执行：

-   长按拖动排序；
-   插入为下一首；
-   从 Queue 删除指定歌曲；
-   清空待播内容；
-   保存当前 Queue 为自定义 Playlist。

对当前正在播放的歌曲执行删除时，必须定义清楚行为：不得造成客户端和 MPD
状态不一致。建议将"删除当前歌曲"解释为结束当前曲目并转到下一首；若没有下一首则立即触发
AutoPlay，除非用户同时明确选择停止。

### 5.3 保存 Queue 为 Playlist

"保存当前 Queue"默认保存尚待播放的内容（Up Next），不包含已经播放的
Played 历史，也不改变当前播放状态。

如未来提供"包含已播放歌曲"的保存选项，应作为明确的独立操作，不得作为默认行为。

## 6. AutoPlay 的全局规则

### 6.1 启用与持续性

-   用户主动开始播放单曲或集合时，AutoPlay 启用。
-   Pause 只暂停播放，不关闭 AutoPlay。
-   Queue 播放到最后一首，不代表播放会话结束。
-   Queue 被用户删空或即将耗尽时，AutoPlay 应补充后续歌曲。
-   用户明确执行 Stop 结束当前播放会话并停止 AutoPlay 接管；未知停止/故障暂停控制但不冒充此意图。
-   如产品以后提供"播放完当前集合后停止"等选项，该选项必须是明确、可见的用户指令，并记录为会话结束策略。

### 6.2 预生成与可见性

AutoPlay 应在 Queue
即将耗尽前预先生成后续歌曲。当前既有策略冻结为低水位5、每批最多5；§8.9.5规定基于确认剩余量触发，不在本次改为其它阈值。

已生成的 AutoPlay 歌曲必须进入 Queue 的 Up Next
并可见，不能只在后台保留一个无法预览的随机结果。

### 6.3 随机选择与避免重复

AutoPlay 的歌曲来源、随机策略和重复规避规则由后续章节细化。最低要求：

-   不应在同一批次中无故重复同一首歌曲；
-   在曲库有足够歌曲时，应避免刚播放过的歌曲立即重复；
-   用户手动加入的歌曲必须受到尊重，不得被 AutoPlay 静默覆盖；
-   AutoPlay 生成的内容与用户手动排入的内容应能在 Queue
    中区分来源，至少在内部数据模型中保留来源标记。

## 7. 播放会话状态

核心状态至少区分：

-   **PLAYING**：正在播放；
-   **PAUSED**：已暂停，播放会话仍存在；
-   **STOPPED**：已确认没有正在执行的播放。用户明确 Stop 时
    AutoPlay=false、active/session 结束；未知外部停止只进入独立未确认表示，不自动改写最后业务状态或 AutoPlay 意图。STOPPED 本身不证明用户意图，原严格自然 empty 组合不再作为 stock MPD 的生产转移（§8.9）。

Queue
耗尽不是独立的终止状态。正常情况下，系统应在耗尽前补充内容并继续播放。

Stop、Pause、切歌、自然播放完成是不同概念；只记录有确认依据的原因，无法认证的离开不制造永久 History（§8.9.4）。

### 7.1 Web 主播放按钮与 seek 意图（2026-10-09）

以下交互选择已接受；接口合同见 Architecture Spec §4.2.1，实现与验收由 Task 8 后端前置承担：

- PAUSED 下恢复播放必须原位继续，保留当前 occurrence、Queue 和 Playback Context，不能用重新 Start Track 代替 resume。此选择不授权未绑定状态自动接管。
- 用户明确 Stop 后，主播放按钮不隐式选曲；通过明确选曲/Queue Play Now 重新开始。未知外部停止仍按 §8.9 表达，不能冒充用户 Stop。
- Web seek 绑定开始操作时的 occurrence。服务端须在共同执行边界验证目标及有效代次；执行前切歌或绑定失效则拒绝，客户端放弃草稿并重读，不将旧 seek 改发到新 current。只做客户端检查不能满足此合同。
- 已提交 seek 的同 key terminal replay 沿用既有幂等合同，返回原回执而不再次执行；不能因当前歌曲已改变而把 replay 当作新的 seek。目标前置条件、typed conflict 与 API 兼容策略沿用 Architecture Spec §4.2.1。

### 7.2 Web 进度与歌词展示时钟（2026-10-09）

产品选择已接受，具体时钟校准与验收用例由 Task 8 专项合同落实：

- 在有效、已确认绑定且实际处于播放状态的 observation 样本之间，允许平滑推进展示位置；这是本地显示估算，不是新的服务端确认样本，不写回 canonical state。
- 进度条和同步歌词共用同一个展示时钟，不能各自外推成不同时间线。新 authoritative 样本到达后校准；切歌不能沿用旧 occurrence 的时钟。
- 暂停、样本过期、断线或绑定失效时停止外推；显示保留值还是 unknown/null 仍遵守 §8.8 及架构 Spec §12 的观察合同，停止外推不代表可以把失效值继续标为 fresh。
- 展示估算不能触发 next、seek、Queue/History/AutoPlay 变更，不能因估算到达结尾而认定自然完成。普通歌词仍不伪造同步时间戳。

### 7.3 Web seek 交互与确认（2026-10-09）

- 拖动只改变本地预览，松手后提交一次 seek；取消手势不发送。键盘操作以一次完成的调整意图提交，不按动画帧发送。
- 提交期间显示 pending，禁止再次拖动；不把预览位置提交到 canonical state。若操作期间收到新 occurrence/绑定失效，撤销草稿，不能向新歌曲补发。
- HTTP 成功表示 endpoint 已确认；随后重读当前 snapshot。未收到属于当前 occurrence、足够新的匹配 observation 前，不把旧样本或拖动目标冒充已确认的新实时进度。可以显示“正在同步”，切歌后立即以新的权威状态为准。
- HTTP 错误显示 typed error；网络 timeout 表示结果未知，不能显示确定失败或自动生成新 key。显式重试复用原 payload/key，并受共同断线只读门禁约束。
- 已知 duration 才开放 seek，目标限定在零到 duration 之间；duration 未知/非正数时保留可用 elapsed 的只读显示，禁用 seek，不虚构时长。

### 7.4 Web Player 常规交互选择（2026-10-09）

本节按用户授权选择非重大交互细节，继承架构共同状态、确认和幂等合同：

- 同一客户端内 pause/resume/next/previous/seek 等互斥播放意图 pending 时禁用相互冲突的控件，不排队保存一串稍后自动执行的操作。Stop 仍是明确独立意图，可在共同连接门禁允许时发起；它不是取消已经在服务端执行的请求，也不保证抢占该请求。最终以服务端串行结果和 snapshot 为准。
- timeout 的未知结果不触发自动业务重试；用户可用原 key 重试或重新读取。HTTP 已成功但读取失败表达为“操作已确认，状态未同步”，不能要求用户用新 key 再做一次。
- 页面进入后台停止展示动画；回到前台重新读取权威 snapshot，确认 observation 后重建展示时钟，不累加后台停留时间。连接不可用时继续遵守 degraded read-only。
- 展示外推使用浏览器单调时钟，不直接相减浏览器和服务器墙上时钟。相同 observed_at 的重复样本不重新开启外推有效期；已知 duration 是显示上界，到达上界不触发任何业务动作。

## 8. 边界情况与一致性要求

1.  **曲库为空或没有可用歌曲**：不能伪造下一首。显示明确的空状态，并说明
    AutoPlay 无法生成内容。
2.  **当前集合只有一首歌**：Queue 仍以该歌曲开始；AutoPlay
    根据全库策略补充后续歌曲。
3.  **集合中的文件失效或无法播放**：跳过失效项并记录可核对的可用性诊断（不是该项播放过或自然结束的 History 原因），继续处理后续有效歌曲；若无有效歌曲则尝试
    AutoPlay。
4.  **用户在 AutoPlay 补充期间操作 Queue**：以服务端串行化后的最新 Queue
    为准，不能让后台补充覆盖用户刚做的排序、删除或插队。
5.  **多客户端同时操作**：Music Server 是 Queue
    状态的权威来源；操作完成后通过实时状态同步向各客户端广播最终状态。
6.  **重复点击或网络重试**：后续 API
    设计应支持请求去重或幂等策略，避免一次用户操作意外执行多次。
7.  **MPD
    与服务层状态短暂不一致**：服务层需要检测并恢复状态，客户端显示以服务层确认的播放会话为准，并明确呈现错误或重连状态。

### 8.8 播放观察与进度权威（Task 6，2026-10-03）

本节来自人工决策 G6-05 / A。Task 6 增加观察与传播，不接管 Task 4 的自然结束/外部恢复状态机。

- **Preconditions**：通过经能力验证的 PlayerPort 读取；PlaybackService/Queue/History 已建立业务权威。允许进程重启后尚无可验证的当前 occurrence 绑定、断线、未知时长/位置以及其它 MPD 客户端变更。
- **Authority / Source of Truth**：MPD 拥有实际 transport state/current occurrence/elapsed/duration；PlaybackService 拥有确认后的业务会话和允许的转移；Repository 保存已提交的业务状态及上次确认位置，不是不断推进的时钟；API/WS 只表示这些事实。客户端不能自行改 Queue、History 或 AutoPlay，也不能把预测位置冒充服务端确认样本。
- **Expected State Delta**：只读采样由 PlaybackService 的 observation facade 接受，形成独立 `PlaybackObservation`，表达实际 state、是否匹配本地 current、采样位置/时长、观测时间、freshness 与 reconciliation_required。匹配须核对 occurrence 和当前业务代次；只匹配 URI/song_id 不足以区分重复歌曲。Task 6 不新增持久 MPD occurrence 映射；缺少可验证绑定时明确未确认，不猜测匹配。
- **Must Remain Unchanged**：采样不执行 play/seek/stop/queue control，不写 PlaybackState/Queue/Context/History/session，不关闭 AutoPlay；只有接受的观察缓存和传播水位可变化。单纯时间推进不递增 Queue/Library/Playlist revision，不产生 History。
- **Transaction Boundary**：观察与领域 mutation 共享串行验证边界；采样期间或采样后发生业务变更时，旧样本不能被标为新 current 的 fresh 位置。可串行读取，或捕获代次后校验并丢弃过期样本；不保证 MPD 多命令物理原子。样本接受/失效与 snapshot/sequence 一致，交付在边界外。
- **Failure / Rollback**：读取失败保留最近样本但标 stale/error，无样本为 unknown/null；不能将 unknown elapsed/duration 变成 0。实际 state/current 不匹配业务会话时置 reconciliation_required，并把当前业务歌曲的可展示实时进度置 null；可保留独立的最后匹配样本为 stale，不能把外部陌生歌曲的进度挂在本地 current 上。失败观察不回滚已提交业务；无成功请求事件。
- **Retry / Idempotency**：下一次采样重读实际事实，不重发业务命令；重复相同样本不产生重复 History。观察 loop 与 WebSocket 连接数量无关。
- **Revision / Ordering**：接受的 elapsed/state/current/freshness/error 变化递增传播 sequence 并失效 playback；仅观测时间刷新不制造无内容变化通知。领域 mutation 确认/提交前不得发送它的成功事件；外部观察通知与 mutation 成功通知语义分离。
- **Observable Result**：本地 `playback` 仍是最后确认业务会话，独立 `playback_observation` 提供 MPD 实际观察；fresh 表示最近一次采样成功且当前绑定通过校验，不表示冻结 MPD。旧数据库位置有 updated_at，但不得作为 fresh progress。API `/api/state` 与 WS 使用同一模型；既有 Playback REST mutation 回执仍是提交时回执，不改成动态时钟。
- **Executable Invariant Proof**：FakeClock/MockPort/真实 Services 证明 elapsed 自然推进只改变 observation/sequence；pause/seek/切歌与迟到采样交错不串曲；重复 URI occurrence 不误配；断线/unknown/stale/reconnect/restart 不伪造状态；所有只读观察前后 Queue/Context/History/terminal 不变；外部 STOPPED 不触发 History STOP。

自然结束与外部恢复的领域能力仍由 Task 4 corrective 承担：不能将 MPD STOPPED 本身当作“用户明确 Stop”，不能由采样推测或补造遗漏播放事件。必须按本章 §8.9、PB-HISTORY-001 和确认/回滚合同区分当前转移事实、显式操作原因、未知过去与重试。Task 6 只暴露 reconciliation_required，不直接调用尚未通过该验收的恢复路径。自动恢复启用及 Task 6 最终验收以该专项能力验收为前置；独立的只读观察、传播基础和 snapshot Batch 可以先执行。此实施依赖不表示本节的新观察语义待决，也不授权本轮修改 production code。

### 8.9 原版 MPD 当前状态接纳与连续执行合同（2026-10-04 修订）

本节是唯一领域 authority，替换此前人工 A 的严格自然完成 SOURCE 路线。用户选择保留原版 MPD 0.23.5、不采用后端扩展，授权收窄原因、实际结束时间和遗漏历史；Queue、AutoPlay、页面真实性、事务和只读边界不收窄。历史 consumer Step2.1–Step3 的定义和验收保存在 [计划历史归档](../archive/task-4/2026-10-04-task-4-d6-recovery-plan-history.md) 与专项 acceptance，不能据此声称本节已实现。合同已定义，R1重启接管体验已由用户接受（§8.9.2）；新实现、新自动测试、目标运行时验证均未完成，D6/Batch13/Task6 final **BLOCKED**。

#### 8.9.1 事实词汇与能力边界 — PB-CURRENT-001

- **目标 occurrence 已确认**：在本进程有效绑定内，对 MPD entry ID、URI、position、partition、完整执行队列及版本进行一致回读，确认 PLAYING/PAUSED 的精确业务 queue_item_id。它仅是采样时当前执行位置事实，不证明从开始听完，也不证明音频输出成功。
- **上一项已离开当前执行位置**：此前确认 A、现在确认不同 occurrence B/C，可以确认 A 现在不再 current；不能给该离开补上 natural/skip/stop 原因或精确 ended_at。
- **上一项自然完成**：是独立因果命题。原版协议不提供本合同所需严格证明，生产路径不产生 NATURAL_COMPLETION。
- **中间项是否播放过**：观察 A→C 不能断定 B 播放过或没有播放过，更不能断定完整播放。
- **原因未知**：是能力边界，不是用户 Stop、失败、SKIP 或自然完成的别名。

status、idle、elapsed≈duration、URI 变化、played URI 日志、未见本服务 Stop 请求、空 error 都不能证明自然完成。seek 到终点与 seek 后余段结束同样不能认证 natural。MPD entry ID 不是一次播放代次：同一 entry 重播可能不可观察；不据此分割历史。MPD ID 删除后可复用，重启也不能沿用旧 ID 绑定。Mock/协议模拟器不得自造原因能力。

#### 8.9.2 绑定、确认与失效 — PB-BINDING-001

> 产品项 R1 已接受（2026-10-04）：用户接受重启后恢复实际状态显示、业务绑定由明确播放操作经确认重建的建议。仅刷新/换浏览器不丢失有效服务绑定。以下为已定合同；接受限制不代表实现、测试或运行时验收通过。

绑定由 PlaybackService 在明确控制后的实际确认建立，含 service_epoch、connection_epoch、binding_generation、partition、业务 revision、完整 `(queue_item_id, mpd_song_id, URI)` 有序映射及 MPD playlist version。connection_epoch 是 Adapter 连接代次，不冒充 MPD daemon UUID。不可由 URI 相等或 zip 相同歌曲列表重建遗失绑定。

正常读使用 status → playlistinfo → status 的有界一致性检查；currentsong 如用于身份也须与该 ID/position 一致。前后 connection/partition/version/length/current ID/state 一致、队列 ID 唯一且位置连续、current 指向其中正确项才形成可信样本；elapsed 可推进。不一致重读最多一次，仍冲突返回 UNKNOWN；这不是跨客户端物理锁，也不能排除采样间不可见重播。

无本服务执行计划时，playlist version 必须与已绑定版本相同，完整映射不得增删/重排。意外版本变化即使最终列表看似相同也失效，不按 URI 修复。有限版本回绕、读取间瞬时变化无法提供数学上无条件的连续性证明；连接断开、读取超时或协议错误使绑定失效；单纯采样间隔只使观察stale，新的完整同连接/同版本样本可重新确认当前位置，不因此声称补齐过去。受控多命令变化按 §8.9.6 的逐命令账本核验，不能将未知版本直接认领。

浏览器刷新/换浏览器不影响服务绑定。服务重启丢弃 runtime 绑定/journal/active；MPD 重启或断线更换连接代次并失效旧绑定。重新连通可以自动恢复**实际状态显示**，不能自动按旧 ID/URI 恢复业务 occurrence。既有明确 Start Track/Play Context/Queue Play Now 经完整确认重建绑定，才恢复接管；显式 Stop 始终可停止实际播放并结束本地意图。此版本不新增持久映射或 schema，不承诺重启后无用户动作地恢复业务绑定。若将来需要该体验，必须另立跨重启身份合同，不能伪称本轮已提供。

#### 8.9.3 Queue 当前转移与执行清理 — PB-QUEUE-ADOPT-001

有效绑定内 A→B 或 A→C 可按实际当前项接纳，无需证明 A natural；PAUSED 目标也可接纳但绝不强行 resume。相同 current 的 pause/resume 沿用 PB-RECOVERY-TRANSPORT-001。陌生曲目、无绑定、意外队列修改、已离开/清理项被外部重新选中一律 UNKNOWN；保留业务 Queue，不以 MPD 列表覆盖它。

接纳当前转移时，只把**此前确认的 A**移入 Played（position=-1，原 Played 顺延）；目标 C 为0。其余待播 occurrence 包括未观察到的 B 全部保留，按原相对顺序放在 C 后，身份/source/context 不变。例：A0/B1/C2/D3 → A-1/C0/B1/D2；不会说 B 已播放，不默删手动 B，代价是 B 若曾在采样间播放，稍后可能再播放。该保守规则使无 schema 的 Played 仍可准确解释；Played 不等于永久 History，不包含未确认经过项。

执行计划删除已确认离开的 A 的 MPD entry，保留目标的 MPD ID，不重播目标、不 seek；必要时把其余 pending 排到目标后。清理/移动会改变 MPD current position：最终确认要求目标 position=0、完整执行映射与业务目标一致。若清理期间 MPD 又前进，放弃本次提交并按已执行命令账本重新核验；不得宣布旧目标成功。MPD 自动前进时 position 可先为1/2，不能因为旧实现只接受0而误认 foreign。

整个业务 current/Played/pending 调整一次 CAS、Queue revision 恰 +1；仅 MPD position 随清理变化、同态采样或 retry/replay 不额外增加 revision。后续独立 AutoPlay batch 的真实 Queue 变更另 +1。pending 手动动作保持原 revision 合同、MANUAL 相对顺序和来源；先处理/拒绝未接纳当前转移，再执行用户队列操作，禁止用旧 position=0 误删实际 current。外部漂移下普通 pending mutation 失败且业务不变；用户显式 Start/Play Now 的重新接管不属于偷偷修复漂移。

#### 8.9.4 History 决定 — PB-HISTORY-001 / PB-HISTORY-UNCERTIFIED-001

采用**不记录未经认证离开的永久 History**。比较另一方案：新增 UNKNOWN/OBSERVED_DEPARTURE reason 可保留更多最近播放，但必须同时区分观测时间/实际结束时间、未知开始时间及 API/schema 兼容；仅加 reason 仍会把旧 started_at/ended_at 冒充事实。当前推荐前者，零 HistoryReason/schema/永久 DTO 扩展，代价是自动转移不会形成完整的永久最近播放列表。

本服务明确 Start/Next/Stop/Play Now/delete 的既有确认及原因合同保留；原因只属于本服务操作已确认作用于的 active occurrence。未知 STOPPED、外部切歌、错误或绑定丢失，不能借下次显式 Stop/Next 为旧 active 补原因。

接纳 A→C 的同一事务中，用新内部 `discard_unconfirmed_active()` 清除 A 的 runtime active，不写结束事件、保留 session；C 不凭 observed_at 创建 History active，因为实际起点未知。后续显式操作若无可信 active，操作可成功但无旧歌曲 History。若显式操作建立新 active，仍按既有确认开始时间合同创建；在任何 finalizer 前须核对绑定/当前身份，失配则丢弃未经认证 active 而不写 reason。只读 observer 不执行这些修改。

未知 STOPPED 的 UNKNOWN 结果保留最后业务状态与 runtime active（作为最后业务资料），页面以 reconciliation_required 标明其未获实际确认；后续 Service 显式操作先做上述 active 资格检查。采样 observed_at 只作观察时间，不是 ended_at，也不以 duration 倒推 started_at。永久旧记录不改写、不删除；has_entries 仍只由持久记录决定。

#### 8.9.5 AutoPlay 提前准备与异常终态 — PB-AUTOPLAY-EXEC-001

连续播放由 MPD 已同步的后续执行项承担，不能等虚构 NATURAL_COMPLETION 才 Next/play。区分四步：纯候选生成 → 业务 Queue 事务提交 → MPD 执行同步及实际确认 → MPD 当前项变化后的独立接纳。实现中 Queue 写入可在 outer transaction 内暂存，只有执行确认后提交可见；候选或 addid ACK 本身不是同步成功。

保留现有策略：LOW_WATERMARK=5、REFILL_COUNT=5；先 PlaybackContext 中可用且未入队的歌曲，再全库 AVAILABLE；同批 song 去重、已有 Queue（含 Played）排除，候选不足时只允许既有单曲/current fallback，不扩大循环策略。手动 occurrence 不按 song/URI 去重；不删/重排 MANUAL 以迁就 AutoPlay，用户指定位置优先。当前确认后按**实际 current 后剩余可执行 pending**判断低水位，不能把已越过的 MPD 前缀当库存。A→C 中 B 只有经 §8.9.3 重新同步到 C 后才计入剩余量。

正常保证前提：在线且绑定有效、顺序执行模式 random=false/repeat=false/single=0/consume=false、候选可播放、服务调度/同步在已排入歌曲耗尽前完成、无外部漂移或输出/解码故障。读取并核验这些模式；不偷偷覆盖外部模式。用户要随机集合时仍在业务侧固定随机 Queue。其他模式表示需要处理并暂停接管，已有模式控制 API 合同不改。命令存在不证明这些组合已在目标运行时验收。

| 条件 | 终态 / 可见表示 | 恢复条件 |
|---|---|---|
| 正常 PLAYING，剩余不足5 | 规划最多5项并预同步；不重播 current | 下一周期或 Queue 提交后唤醒，成功确认/提交后对外可见 |
| PAUSED | 保留意图，可同步 pending；不主动 play | 明确 resume 或确认外部 resume 后继续 |
| 空库/无可用候选 | `NO_CANDIDATES`，不伪造下一首；已有执行项可继续 | Library 变化/下一有界周期重新查询；若已 STOPPED 仍不自动启动 |
| 未知外部 STOPPED（含队尾） | `UNCONFIRMED_STOP`，reconciliation_required=true；不判用户Stop/natural、不自动重新启动、不改 AutoPlay 意图 | 显式 Start/Play Now；Stop 可结束意图 |
| 断线/重启/无绑定/foreign/外部改队列 | `UNBOUND` 或 `EXTERNAL_DRIFT`，实际状态 stale/unknown/独立显示；停止控制 | 只读重新采样恢复实际显示；业务接管须明确控制后重新绑定 |
| 补充/清理失败 | `SYNC_FAILED`；无业务伪提交，已执行前缀保留账本 | 仅能证明归属的同进程固定意图安全 retry；否则需要明确处理 |
| 本服务明确 Stop 并确认 | AutoPlay=false，active/session结束 | 仅新的明确开始播放操作；迟到 refill/runner 不重启 |

状态标签是恢复诊断，不新增 PlaybackState 枚举。尚无可信候选、播放极短导致调度追不上、服务停机等不承诺永不停播。未知停止后即使新候选出现也不得由 runner 启动；这明确替换旧“没有 Stop 就永不自然停止”的绝对承诺。

#### 8.9.6 事务、部分执行、retry 与幂等 — PB-RECOVERY-RETRY-001

恢复身份改为 `(service_epoch, binding_generation, operation_id)`，operation_id 是 Service 生成的固定意图 ID，不冒充 MPD 完成事件 ID。固定输入含 queue revision、原 current、目标 occurrence、完整映射、计划候选 IDs；相同 ID 不同内容抛 PlaybackReconciliationError。准备与确认处校验代次/CAS，采样只读不能更新业务代次。

Service 是唯一编排者；Queue/Playback/History runtime/绑定/receipt 在同库 outer transaction 与可见性边界协同。确认失败、写入失败、terminal/materialization失败、提交前取消、outer commit失败恢复 persisted/runtime、零成功通知；SQLite 无法撤销 MPD 副作用。journal 的固定意图及逐命令已知执行前缀独立于业务回滚保存。

每条 add/delete/move/play 都记录尝试和已确认响应，再回读核验完整中间态；尚未发送的命令才可继续。addid 响应丢失不能按 URI 寻找新 ID，也不能盲目再次 add。delete/move/play 的响应丢失不等于未执行：只有原绑定持续有效且实际状态与唯一计划结果相符才可免重发确认；存在其它可达解释则 UNKNOWN。连接失效后不自动延续控制。不能宣称 MPD command list 是原子事务，不能把半执行伪装成 rollback。

目标已确认 PLAYING/PAUSED 时不重播；unknown STOPPED 不靠 retry 启动，明确用户播放请求的既有 retry 合同另行保留。receipt 仅 outer commit 后可见；同 ID/同内容返回原回执、无控制/无 refill/无 Queue revision/无 History/无重复通知。先查 receipt 再检查旧代次。提交后取消或 publisher/send失败保留提交和receipt；可见性登记失败沿用 A §12.2 fail-closed，不能执行 rollback hooks。进程重启旧 intent/receipt 不重放，不承诺跨进程 exactly-once；REST key/scope/payload 持久 replay 合同不变。

#### 8.9.7 只读页面恢复与调度边界 — PB-RECOVERY-RUNNER-001

GET/WS/snapshot/StateObserver 只读；浏览器重连不是恢复命令。独立、单实例 recovery runner 调用 PlaybackService 的一次 reconcile/refill facade；它是正常无人打开页面时持续补充所必需的 Task4 corrective 步骤，不藏进 observer。默认每轮完成后1秒、单次外部预算5秒，失败退避1/2/4/8/16/30秒，成功重置；无重叠，UNKNOWN 只重读不发控制，Stop 使迟到意图失效；shutdown取消并 await，不发 Stop。不提供多进程共享同一 MPD 的协调保证，装配必须限定一个控制 owner。

页面当前业务歌只在匹配确认时作为已确认 Now Playing；外部陌生/未绑定曲目通过独立实际身份展示，本地 Queue/current 保留并标不同步。完整 DTO、authority/兼容与刷新/重启验收见 A §12.3.1。最终同步在有效绑定的下一次 runner 成功确认/提交完成；失去绑定时实际显示可恢复，业务同步等待明确用户操作，不隐瞒这一限制。

#### 8.9.8 场景验收矩阵

| 场景 | 接纳/控制 | History 与身份限制 |
|---|---|---|
| 正常 A→B | 完整绑定确认后推进 B，清理 A，无 play B | A Played，无 natural 事件，B 无伪造起点 |
| 单次观察 A→C | C current；B 保留待播并同步到 C 后 | 不断言 B 播放过；仅 A Played |
| 同 URI 不同 occurrence | 按映射 ID 分辨，不按 URI 合并 | 仅被确认 occurrence 可推进 |
| 同 MPD entry 重播 | 当前位置事实不变，可更新实际进度 | 不产生新播放次数/自然完成；不可见重播不补史 |
| ID 删除复用/意外版本变化 | 失效绑定，UNKNOWN，即使 URI/ID 看似相同 | 零推测历史 |
| seek 到终点/seek 后余段结束 | 可确认后来目标，未知停止则不启动 | 不生成 NATURAL_COMPLETION |
| 解码/输入/输出错误 | 有 error 明示；空 error 不免责；已确认目标可接纳，停止则保守 | 原因未知不写成自然/Stop/Skip |
| 外部 Next/playid/seekid | 仅目标在完整有效映射内且可确认才接纳 | 接纳目标不认证发起者或旧项原因 |
| 外部改队列/陌生曲目 | UNKNOWN，保留业务Queue，展示实际身份 | 无自动覆盖/URI猜绑定 |
| 断线/服务重启/MPD重启 | 恢复实际观察；业务绑定失效，待明确接管 | 不恢复未知过去、完整Context或runtime active |
| Queue修改/采样/恢复并发 | 共同代次/CAS，迟到样本及旧意图拒绝 | 一次提交一个完整切面 |
| 多命令部分成功/响应丢失 | 固定意图/逐命令账本/唯一可归属才retry，否则UNKNOWN | 无重复History/revision/成功事件 |

#### 8.9.9 门禁替换

旧 `D6-SOURCE` 严格因果 producer 不再是本路线实施前置，状态为 **SUPERSEDED（合同替换，不是 capability PASSED）**。`PB-NATURAL-001` / `PB-NATURAL-EMPTY-001` 退为历史 consumer 合同，不可转写成“原版自然识别已通过”。取代它们的新义务为 PB-BINDING/CURRENT/QUEUE-ADOPT/HISTORY-UNCERTIFIED/AUTOPLAY-EXEC/RECOVERY-RUNNER-001，以及修订的 PB-RECOVERY-UNKNOWN/RETRY-001、RT-ACTUAL-001。

必须证明真实 Adapter/Port→一致采样→绑定→Service→Queue/History/AutoPlay→outer commit→snapshot/WS 的显式联合路径，再证明 runner 生命周期。协议模拟器只验证给定输入；官方 v0.23.5 静态依据与目标运行时测试分开记账。新目标模式/执行组合必须单列待授权实测；本轮不访问 live MPD、不运行 probe。全部实现、专项及直接回归、D6 联合验收和 Batch13/Task6 gate 复验未满足前，最终门禁保持 BLOCKED。

## 9. 本章验收标准

本章对应的实现只有满足以下条件，才可视为核心播放模型完成：

-   任意具体歌曲对象都能打开含 Play Now、Play Next、Add to Queue
    的统一操作框；
-   集合页面顶部提供全部播放和全部随机播放，并整体替换
    Queue、立即播放第一首；
-   Queue 明确区分 Now Playing、Played 和 Up Next；
-   Queue 中的歌曲支持拖动排序、插队、删除和保存为 Playlist；
-   播放历史与 Queue 历史分离，清理其中一者不会意外清除另一者；
-   Queue 接近耗尽时 AutoPlay 提前补充内容；
-   在 §8.9.5 在线正常条件下，单曲、集合或 Playlist 的后续项在耗尽前同步；未知停止不自动启动；
-   Queue 明确展示已确定下一首或无候选/不同步状态，且用户手动操作不会被 AutoPlay 静默覆盖；
-   Pause、Stop、自然结束和用户切歌具有不同语义；
-   Web/PWA 与 Android 客户端遵循同一套服务端播放规则。

## 10. 本章暂不决定的事项

以下内容留待后续章节，不在本章擅自固化：

-   AutoPlay 超出 §8.9.5 既有候选顺序/去重边界的推荐算法与权重；
-   Queue 与 MPD 原生队列的跨进程持久映射（§8.9 已定义当前绑定、接纳、进程内 retry 和失效策略；未承诺跨重启自动业务绑定）；
-   歌曲重复入队、跨集合重复项的完整策略；
-   Queue 历史保留数量与永久播放历史的保留期限；
-   多用户、多播放设备或多房间播放；
-   Smart Playlist、推荐系统和复杂标签筛选；
-   Android 原生媒体会话、通知栏、锁屏及耳机按键实现细节。
