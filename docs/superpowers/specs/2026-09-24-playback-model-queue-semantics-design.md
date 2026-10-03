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
    是全局兜底行为。只要用户没有明确停止播放，播放结束后就应继续产生后续内容。**
5.  **Queue 必须始终明确展示下一首歌曲。**
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

Queue 中展示的 Played 区域是当前会话的历史视图；永久 Playback History
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

AutoPlay 是全局连续播放机制。当待播 Queue
即将耗尽时，系统生成后续歌曲并放入 Queue，避免播放自然停止。

AutoPlay 不属于某个专辑或 Playlist
的私有功能。它是播放会话的兜底行为，除非用户明确停止播放，或执行了定义为终止会话的操作。

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
-   记录原当前歌曲离开当前播放位置的事件。
-   保留原 Queue
    中尚未播放的其他内容，并将其放在新当前歌曲之后；不得因单纯切换歌曲而无提示地丢弃原有待播内容。
-   若该操作来自一个明确的"开始独立单曲播放"入口，且产品交互将其定义为新播放上下文，则按第
    4.1 节的 Start Track 规则替换 Queue。

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

因此，单曲播放不会在该歌曲结束后停止；AutoPlay 会继续补充后续内容。

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
2.  **Played**：当前会话中已播放或被切换离开的歌曲；
3.  **Up Next**：按确定顺序排列的后续歌曲。

Queue 必须始终明确展示下一首歌曲。只要播放会话处于活动状态，系统就应保证
Up Next 中有确定的下一首；AutoPlay
生成内容时应在队列耗尽前完成补充，而不是等到播放器停止后才开始寻找歌曲。

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
-   用户明确执行 Stop，才结束当前播放会话并停止 AutoPlay 接管。
-   如产品以后提供"播放完当前集合后停止"等选项，该选项必须是明确、可见的用户指令，并记录为会话结束策略。

### 6.2 预生成与可见性

AutoPlay 应在 Queue
即将耗尽前预先生成后续歌曲。建议以可配置的低水位阈值触发补充，例如剩余
3--5 首时开始准备下一批；具体数值可在性能和用户体验测试后确定。

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
-   **STOPPED**：用户明确停止，当前会话不再由 AutoPlay 自动续播。

Queue
耗尽不是独立的终止状态。正常情况下，系统应在耗尽前补充内容并继续播放。

Stop、Pause、切歌、自然播放完成是不同事件，必须分别处理并记录，不能都归类为"播放结束"。

## 8. 边界情况与一致性要求

1.  **曲库为空或没有可用歌曲**：不能伪造下一首。显示明确的空状态，并说明
    AutoPlay 无法生成内容。
2.  **当前集合只有一首歌**：Queue 仍以该歌曲开始；AutoPlay
    根据全库策略补充后续歌曲。
3.  **集合中的文件失效或无法播放**：跳过失效项并记录原因，继续处理后续有效歌曲；若无有效歌曲则尝试
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

自然结束与外部恢复的领域能力仍由 Task 4 corrective 承担：不能将 MPD STOPPED 本身当作“用户明确 Stop”，不能由采样推测或补造遗漏播放事件。必须按本章 §6/§7、PB-HISTORY-001 和确认/回滚合同证明自然结束、显式 Stop、外部漂移及重试的区分。Task 6 只暴露 reconciliation_required，不直接调用尚未通过该验收的恢复路径。自动恢复启用及 Task 6 最终验收以该专项能力验收为前置；独立的只读观察、传播基础和 snapshot Batch 可以先执行。此实施依赖不表示本节的新观察语义待决，也不授权本轮修改 production code。

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
-   只要用户没有明确 Stop，单曲、集合或 Playlist
    播放结束后都不会自然停止；
-   Queue 始终展示确定的下一首，且用户手动操作不会被 AutoPlay 静默覆盖；
-   Pause、Stop、自然结束和用户切歌具有不同语义；
-   Web/PWA 与 Android 客户端遵循同一套服务端播放规则。

## 10. 本章暂不决定的事项

以下内容留待后续章节，不在本章擅自固化：

-   AutoPlay 的具体随机算法、权重和歌曲来源；
-   Queue 与 MPD 原生队列的精确映射及故障恢复协议；
-   歌曲重复入队、跨集合重复项的完整策略；
-   Queue 历史保留数量与永久播放历史的保留期限；
-   多用户、多播放设备或多房间播放；
-   Smart Playlist、推荐系统和复杂标签筛选；
-   Android 原生媒体会话、通知栏、锁屏及耳机按键实现细节。