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
5.  **Queue 必须明确展示已确定的业务下一首；执行器仅按 §8.10 预备 MPD 下一首，不再要求完整业务 Queue 与 MPD playlist 同步；无候选或未确认必须明确显示。**
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

AutoPlay 是全局连续播放机制。在在线正常条件下，当待播 Queue 即将耗尽时，系统生成后续歌曲、提交业务 Queue 并仅将立即需要的下一首预备到 MPD 有界执行缓冲，避免等待 STOPPED 后才补充；详见 §8.10（原 §8.9 完整同步仅属历史实现）。

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
-   Queue 按 §5 的 occurrence 点击直接播放例外执行，不先弹统一菜单；
-   播放历史；
-   收藏及其他歌曲集合。

### 3.2 必须提供的选项

除 Queue（§5）外，点击具体歌曲对象时，弹出操作选项框，至少包含：

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

**Web 合同补充（2026-10-09，产品选择已接受；后端合同见 §3.3.1）**：

- Library/Search/Playlist 等普通歌曲入口的 Play Now 创建新的 occurrence，保留已有待播 occurrence 及其相对顺序，包括同一 song 的重复项；不隐式选取、移动或去重已有 occurrence。Queue 行的 Play Now 仍精确操作该行的 queue_item_id。
- 用户明确 Stop 后，从上述普通歌曲入口执行 Play Now 表示开启新的播放会话并重新启用 AutoPlay，同时保留原待播内容；不因此退化为替换 Queue 的 Start Track。开启意图仍受 §8.9 的在线、绑定、候选与确认限制，不承诺异常情况下自动续播。
- 同一意图的传输重试必须复用既有 Idempotency-Key，不重复创建 occurrence。完整服务端原子入口、Context/History 生命周期与失败确认合同见 §3.3.1；实现能力与验证结果由 B02 验收记录证明，不以本文替代执行证据。

#### 3.3.1 普通歌曲原子 Play Now — PB-SONG-NOW-001（2026-10-10 已冻结）

用户批准方案并明确授权“冻结相关内容，再直接进行B2”。本节关闭 Task9 G9-01；只定义普通 song-id Play Now，既有 Start Track、集合播放及 queue_item_id Play Now 不变。

- **P / Authority**：PlaybackService 是唯一编排者，先在服务端互斥/业务版本边界校验 Song 存在且 AVAILABLE，再控制 MPD；目标 §8.10 禁止将多轮 MPD 网络 I/O 包在长期 SQLite 写事务内，按分阶段确认后短事务提交。未知歌曲及不可用歌曲沿用 404 `PLAYBACK_REQUEST_INVALID`，无 MPD 控制、Queue/History/revision/terminal 变更。Web 沿用 Architecture §4.1–4.2 baseline/writable 与 key 合同。
- **保留项 availability（同日补充已接受）**：用户明确选择沿用整次拒绝并保留队列。所选 Song 可用但任一原 pending 为 MISSING/UNREADABLE（或其 Song 缺失）时，该既有用户接受的整次拒绝规则在 §8.10 执行器迁移中暂不变更（放宽须另行用户裁决），因此操作在 MPD 控制、token失效及 Queue 修改之前返回既有404 PLAYBACK_REQUEST_INVALID；原 Queue/History/Context/revision/token不变，无成功terminal。不能静默删除、跳过或重新分配保留项；允许跳过的执行映射扩展需另行审核，不属B02。
- **Occurrence / provenance**：每个新意图创建新的 MANUAL occurrence，即使所选 song 是 current 或已在 pending 中出现多次。position=0，song_id 为目标，playback_context_id 为本次保留/新建 Context。原 position>0 项的 ID/song/source/context 及相对顺序全部保留，只规范化连续正 position；不选择、移动、去重已有同 song 项。AutoPlay 新项追加在原 pending 后。
- **Context / lifecycle**：会话内 PLAYING/PAUSED 且 PlaybackState 有非空 Context ID 时保留该 ID；现有模型没有独立 Context 表，Service 从权威 Queue 重建候选范围，不能把 MPD 绑定当 Context 是否存在的依据。首次无 Context、Context 缺失时创建 `source_type=TRACK/source_id=song_id/ordered_song_ids=(song_id,)` 单曲 Context。本服务已确认并提交的明确 Stop 后，即使旧 Context ID 尚存，也创建新单曲 Context。任何已确认的开始播放（含既有 Queue/Start Track/集合入口）消费上次 Stop provenance；Stop provenance 使用服务拥有的、随外层事务提交/回滚的运行时标记，不新增 schema；服务重启丢失标记，不能仅凭 STOPPED、AutoPlay=false 或空 session 推断用户 Stop。
- **Played / old current**：保留 Context 时保留原 Played；旧业务 current 在成功显式切换后成为最近 Played，其余 Played 顺延。创建新 Context 时删除旧 position<=0 展示，保留所有原 pending；不删除永久 History。Played 表示曾成为业务 current 后离开，不证明听完/natural；未知外部停止后的旧 current 不因此获得永久 History 结束原因。
- **History**：正常已认证 active 切换沿用 session，按 §8.9.4 记录既有 SWITCH_AWAY。旧 active 不可信时丢弃，不补原因，保留已有 session；新 active 在目标完整确认后建立，session 不存在则创建。明确 Stop 已清 session，随后产生新 session。Context 缺失但 session 尚存时创建 Context 而保留 session；服务重启/无 active 不回填历史起点。
- **STOPPED / unbound**：未知外部 STOPPED、无绑定、外部队列漂移时，本次请求是新的明确播放/接管授权；有 Context 就保留，否则创建，保留已有 session、无 session 则创建。不把该分支归类为用户 Stop，不自动恢复执行。旧执行器以完整 occurrence↔MPD 映射及 current position=0 确认；§8.10 新执行器以短缓冲中精确目标 occurrence 的 MPD ID/URI/实际 PLAYING 和有效代次确认成功，不要求其余 pending 进入 MPD。
- **AutoPlay**：保留 Context 的已有会话保留原 AutoPlay 意图；明确 Stop 后、新 Context 或没有既有 History session 的初始化启用 AutoPlay。沿用 §8.9.5 低水位5/每批最多5、候选/current fallback、模式/绑定限制；不改 MANUAL 顺序或来源。无候选不阻止所选歌曲播放，按已有 NO_CANDIDATES 表达；不扩展候选策略。真实补充独立 Queue revision，整个 endpoint 的净变化仍一次联合对外提交。
- **API / observable result**：additive `POST /api/playback/songs/{song_id}/play`，无业务请求体，必须有 Idempotency-Key；200 返回已有 QueueItemResponse，包含新 MANUAL current（position=0），不扩展 DTO。错误沿用既有 Playback typed error：404 validation、502 PLAYER_COMMAND_FAILED/PLAYBACK_RECONCILIATION_FAILED、503 PLAYER_UNAVAILABLE；同 key scope/payload 冲突409 IDEMPOTENCY_KEY_CONFLICT。客户端成功后重读 snapshot，不从单项 DTO 拼装 Queue/History/token。
- **Confirmation / transaction**：复用 §8.9.6 账本与现有 current-target 代次；Queue 切换 revision +1，真实 AutoPlay batch 另按现有规则计数。Queue/Playback/Context ID/History runtime与持久事件、terminal record 及 realtime delta 均在最外层成功提交后可见，事件覆盖实际发生变化的 queue/playback/history，提交前无成功通知。旧 token 在显式控制前失效，新 token 完整确认并提交后可供读取；rollback 不复活因外部连续性丢失而失效的 token。
- **Failure / retry / replay**：命令/确认、状态写入、History、terminal、materialization、outer commit 或提交前取消失败恢复本地业务与 runtime，无成功回执/通知；SQLite 不撤销 MPD。固定操作分配 occurrence/新 Context，保留逐命令已执行前缀，安全 retry 不重播已确认目标、不重复添加；归属/执行结果不明时 fail closed，不能按 URI 找回未知 addid 或盲目再 add。失败 key 的 runtime 请求身份固定原 operation/base business generation/Queue revision；其他 current/Queue/AutoPlay 变更使基线过期时返回既有502 PLAYBACK_RECONCILIATION_FAILED，不分配新 occurrence 或发送控制；同 key 更换 song/payload 返回409 IDEMPOTENCY_KEY_CONFLICT。成功 HTTP terminal replay 优先返回原 DTO，即使之后 current/availability 改变也不控制、不 refill、不新增 History/revision。不同新 key 是新意图；失败尚未提交的同 key 不得改成另一输入继续旧执行。跨进程不承诺未提交请求 exactly-once，沿用 PB-RECOVERY-RETRY-001。
- **Proof / downstream**：B02 的真实 SQLite/Services/MockPort API/invariant 测试证明同 song 重复 pending、MANUAL/provenance、Context/session/Stop/unknown/无 Context、token、联合版本/事件，以及全部上述失败与 retry/replay；existing wire Gate兼容。B02无独立 UI，phone N/A；真实 MPD/DAC NOT RUN。B03 Played 展开按 accepted Context ID 变化、已确认用户 Stop 或 epoch 变化复位；会话内普通 Play Now、暂停、采样不复位；2026-10-11 Queue本地展示修订后，每次重新进入Queue复位并定位current（§5.1），不能从 unknown STOPPED 推断复位。

#### 3.3.2 明确 Stop 生命周期传播 — PB-STOP-LIFECYCLE-001（2026-10-10 已冻结）

用户选择补充服务端Stop生命周期信号，并授权补充合同后直接执行B03。本节关闭G9-06的合同缺口，不新增Stop UI，不改变Stop、History、Queue或song Play Now的领域结果。

- **Authority / representation**：PlaybackService拥有进程内非负整数`explicit_stop_generation`，初始0。`FullStateSnapshot`及GET/WS完整snapshot additive字段`explicit_stop_generation`表达同一已提交切面中的计数；有PlaybackService时必须为整数，无该owner的独立聚合允许null。旧服务器缺字段由Web解码为null（未知），不猜成0，不据状态/session推断来源。字段不进入PlaybackState持久schema或mutation receipt。
- **Delta / confirmation**：每次本服务明确`stop()`完成MPD STOPPED确认并成功提交，计数恰+1，包括已停止时新的明确Stop意图；同key成功terminal replay不执行Service，计数不变。随后确认开始播放只消费原内部Stop provenance，不清除此累计计数。非用户Stop路径（unknown外部停止、current删除无后继、session结束、采样、pause、GET/WS、其它播放动作）不递增。
- **Transaction / failure**：计数与原Stop的Playback/History/provenance共用最外层串行事务及rollback hooks；命令、确认、terminal写入、outer commit失败或提交前取消不递增可见计数，SQLite不撤销MPD副作用。计数变化登记`playback`域失效，提交前读取不能导出计数；后续普通开始不抹去已提交Stop。重试成功仅计最终成功提交一次，不将外部已执行但本地失败当成功来源。
- **Epoch / propagation**：计数只在当前服务进程/epoch内比较，不持久化、不跨进程宣称exactly-once；重启的新epoch从0开始。通过Architecture §12的joint snapshot/覆盖水位传播，允许合并重读跳过中间Stop，但最新累计值仍保留已提交Stop事实；invalidate不是Stop回执，也不重放操作。服务owner不能在同epoch重建并使计数回退；正常生命周期以新epoch重建。
- **B03 consumer**：持久queueUi初始展开0；只观察accepted snapshot，Context ID或epoch变化归零，同epoch已知Stop计数增加归零，重复/旧snapshot和连接状态不归零。首次获得计数（此前null）仅建立基线；同epoch缺字段保持最后已知计数，不能用unknown推断Stop。采样、pause、会话内普通Play Now、session单独变化和unknown STOPPED不复位；2026-10-11本地展示修订：每次进入Queue展开归零并定位current，留页切歌保持滚动及已揭示历史（§5.1）。新epoch总复位，不比较旧计数。字段回退的同epochsnapshot不能被接纳为新canonical事实。
- **Proof**：真实SQLite/Services/Mock/API证明Stop确认、outer commit屏障、rollback/terminal/replay、Stop→start合并读取及non-Stop不递增；真实后端序列化fixture→shared Web decoder/store→queueUi证明source、ordering和跨route展开，手机H02验收实际显示与Context复位。真实MPD/DAC另行验收。

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

### 5.1 连续歌曲列表 — PB-QUEUE-VIEW-001（2026-10-11 用户授权修订）

服务端 Played/current/Up Next 分区与完整 occurrence 保留；Web连续列表不显示 Now Playing、Played、Up Next 分组标题，不提供“展开10条”按钮，不读取永久History拼接Played。

- 每次从任意导航页进入Queue，隐藏Played，将position=0的业务current作为首条可见歌曲并定位到它；离页再回来重新隐藏。进入时尚无有效current则等待accepted current后定位，不猜歌曲身份。
- 用户从current处向下拉动内容才逐步揭示其上方Played，最近项先出现。a,b,c,d播放到c：初始c,d，下拉先露b，再露a；最终顺序a,b,c,d。本地揭示不修改服务端Queue/History。滚动与长按拖动排序须分开，取消不误触播放。
- 已确认current且fresh匹配绑定、actual playing/paused时，在标题前显示明显播放/暂停图标；其它行无此类图标。unknown/stale/unbound不伪装已确认状态，position0本身不是确认。
- 没有MANUAL待播、只有current且AutoPlay启用：仅显示最先的一首AUTOPLAY待播候选，即使服务端生成多个。存在MANUAL待播的多曲场景：显示全部MANUAL待播，隐藏全部AUTOPLAY候选；有/无Played均适用。Played不计为待播，候选本身不使单曲场景变成多曲。AutoPlay关闭时不预览候选。
- 留在Queue期间自动/普通切歌保留用户滚动位置与已揭示历史，不因current变化强制定位或隐藏；重新进入才定位。accepted Context/epoch改变及明确Stop counter递增仍归零，继承§3.3.2，不用unknown STOPPED/session猜Stop。
- 标题和艺术家各单行省略；点击不展开多行详情。metadata读取失败/不可用仍保留occurrence及身份，按唯一顶部通知合同反馈。

### 5.2 Queue 操作

- current、已揭示Played、MANUAL待播及可见AutoPlay候选均点击即播放，精确POST `/api/playback/queue/items/{queue_item_id}/play`；不先弹播放菜单、不用普通song Play Now、不选择同song其它occurrence。
- 仅position>0待播项可以长按拖动排序，current与Played不可排序、不可作为待播区之外的放置目标。按现有PUT item及`before_queue_item_id`提交，保留完整服务端Queue及隐藏候选；隐藏项不因拖动被客户端删除或重建。
- drag只是本地草稿；已知Queue revision/current/成员、epoch/连接generation变化、断线或离页取消；已发intent留在共享owner。提交后按服务端执行时权威状态裁决，不承诺尚未送达浏览器的并发变化被expected-version守护。
- 所有mutation继承Architecture §4.1–4.2只读门禁、共享key/原key恢复、HTTP确认后权威重读；不speculative改canonical，不把invalidate当ACK。长按取消/拖动结束不触发点击播放。
- B04剩余动作由独立入口提供，整行点击合同不变。用户2026-10-11修正Queue快捷语义：仅position>0待播项提供“移为下一首/移到队尾”，以queue_item_id经现有PUT item/before_queue_item_id移动原occurrence至完整UpNext首位/末尾（含隐藏候选）；不调用song-id入队、不新增/去重/重建条目。已在目标首尾位置为本地no-op；current/Played不提供移动入口，整行播放和删除保持。此Queue例外不改变普通Song的Play Next/Add入队合同。删除精确使用queue_item_id，可作用current/Played/待播，沿用服务端后继确认、History及无后继处理；不在浏览器猜造current。
- 清空入口明确为“清空待播”，经本地确认后DELETE queue；只清Up Next，不清current/Played、不作为Stop。AutoPlay既有补充策略保持，服务端补充的候选可重新出现。

### 5.3 保存 Queue 为 Playlist

"保存当前 Queue"默认保存尚待播放的内容（Up Next），不包含已经播放的
Played 历史，也不改变当前播放状态。

Web只提交{name}，不提交song_ids、可见行或expected_revision。服务端事务内读取提交时完整Up Next（包括隐藏AutoPlay），不含current/Played、不自动去重；重复song_id整次400拒绝，写入失败回滚Playlist及成员，不能留下半成品。HTTP确认后权威state及Playlist列表重读；失败保留名称草稿，离页丢弃未发草稿，已发intent跨页由共享owner恢复。

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

已生成的 AutoPlay 歌曲必须进入服务端完整Queue的Up Next。2026-10-11 Web展示按§5.1：单曲只预览首候选、多曲隐藏候选；这只改变本地可见投影，不改变低水位、补充策略、执行映射或Queue occurrence。

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

Web 的 pending/同步/未知/错误及恢复操作入口只遵守 [全局 UI 合同](2026-10-03-web-pwa-visual-design.md) WEB-UI-NOTIFY-001；以下“显示/提示”不授权正文增加通知行。2026-10-10 用户已移除 Player Stop UI，本节保留后端 Stop 语义，不要求重新添加按钮；Player 保护基线见 WEB-UI-BASE-001。

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

### 8.9 原版 MPD 当前状态接纳与连续执行合同（2026-10-04 历史完整同步实现）

> **2026-10-12 迁移标注**：本节描述 Task4/D6 已完成的完整MPD执行列表绑定路线；其产品业务与未知因果/History安全规则保留，但 §8.9.1–3/5–7 关于「将所有pending同步MPD、完整playlist映射/playlist version、旧执行账本、自动runner同步目标」的**执行约束**由新 §8.10 取代。此处保留原文供历史验收与旧代码审计，不再作为新执行器实施指令。新合同为 FROZEN / NOT IMPLEMENTED；旧实现与新目标的验收状态不得混同。

本节在2026-10-04为当时唯一领域 authority，替换此前人工 A 的严格自然完成 SOURCE 路线；2026-10-12起执行映射/同步的权威由新 §8.10 取代，业务与 History 安全语义仍继承。用户选择保留原版 MPD 0.23.5、不采用后端扩展，授权收窄原因、实际结束时间和遗漏历史；Queue、AutoPlay、页面真实性、事务和只读边界不收窄。历史 consumer Step2.1–Step3 的定义和验收保存在 [计划历史归档](../archive/task-4/2026-10-04-task-4-d6-recovery-plan-history.md) 与专项 acceptance，不能据此声称本节已实现。合同于2026-10-04已定义，R1重启接管体验已由用户接受（§8.9.2）。**历史状态说明**：当时新实现、自动测试、目标运行时验证尚未完成，D6/Batch13/Task6 final 为 **BLOCKED**；其后2026-10-09已有专项验收，详见 [D6 acceptance](../archive/task-4/2026-10-04-task-4-d6-recovery-acceptance.md)；**§8.10的新执行器仍未实现/未验收**。

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

必须证明真实 Adapter/Port→一致采样→绑定→Service→Queue/History/AutoPlay→outer commit→snapshot/WS 的显式联合路径，再证明 runner 生命周期。协议模拟器只验证给定输入；官方 v0.23.5 静态依据与目标运行时测试分开记账。该段为2026-10-04撰写时的目标门禁说明；其后2026-10-09完成旧D6专项验收，以对应归档为准。§8.10新模式/短执行缓冲组合尚须独立授权实测；本次文档冻结不访问live MPD、不运行probe，新的重构联合/真人门禁为 NOT RUN。


### 8.10 MS 唯一业务 Queue / MPD 有界执行缓冲合同 — PB-BUF-*（2026-10-12 FROZEN）

> **变更授权与生效边界**：用户已授权在 Task9 当前分支基础上重新设计播放执行层，并要求先冻结合同；本文是新路线的**唯一长期领域权威**。冻结仅证明设计决定，不表示实现、CI、真实MPD/DAC验收成功。§8.9 仍记录已经交付的**旧完整队列同步实现及其历史证据**；凡涉及「完整业务 Queue ↔ 完整 MPD playlist 映射」「为每个 pending 维护 MPD ID」「以完整 MPD playlist version 维护所有业务 occurrence」的执行细节，**未来目标以本节取代**。§8.9 和 §3.3.1 中的业务 Queue/History/Context/AutoPlay/explicit Stop/retry 与用户交互语义仍然有效，除非本节明确指出执行实现替换。切换完成前旧系统的验收结果不能冒称本节验收。

#### 8.10.1 权威边界和业务不变项 — PB-BUF-AUTH-001

- **MS SQLite Queue 是唯一的业务 Queue**：由 queue_item_id 区分每一次 occurrence；Played/current/pending、MANUAL/AUTOPLAY、Context、歌曲重复、排序、原有 Queue revision/CAS 及清空「仅清待播」行为全部保留。MPD playlist **不是**业务 Queue，不是恢复 MS Queue 的来源，不得从 MPD playlist 反向生成/删除/重排用户业务项。永久 History 与 Queue Played 分开。AutoPlay 的候选选择/低水位5/每批最多5、固定随机顺序由 MS 决定；MPD random 绝不代表 Web 随机播放。
- **MPD独占实际播放事实**：实际PLAYING/PAUSED/STOPPED、当前MPD Song ID/URI及elapsed/duration/输出和错误以最近一次**新鲜、实际、一致的MPD读取**为权威；MS上次发出的指令、操作日志、SQLite last-confirmed business current不能冒充MPD当前事实。**Web播放器的播放/暂停/停止、实际当前歌曲和该歌曲进度，只由MPD决定**；Web下一首/待播仍以MS业务Queue决定；MPD内部两个预备项只用于后端缓冲校验，参见§8.10.6–7。
- **分离三种身份**：Song ID 是 MS 媒体库身份，queue_item_id 是业务 occurrence 身份，MPD song ID 是**当前连接/受控执行缓冲内**的临时执行身份；同 URI 重复出现也不得混淆。URI mapper 必须对发出的本地 URI 与 MPD 文件 URI 做可核对的双向转换；可播放/AVAILABLE 和 MPD 找得到文件是不同前提，失败不得按文件名猜测匹配。
- **业务兼容**：Task8/9 已接受的 Start Track、集合替换/固定随机、普通 Song Play Now 新建 occurrence 并保留 pending、Queue occurrence Play Now、Next/Previous、重排、删除、Played 点击、明确 Stop 后恢复、AutoPlay、保存 Playlist、REST/WS DTO/HTTP key/sequence 与 Web 视觉合同不随执行器变更。§3.3.1 以前已接受的「任一保留 pending unavailable 则普通 Song Play Now 整次拒绝」暂时保留；取消该规则需要独立产品合同，不以旧技术原因消失而擅自修改。

#### 8.10.2 有界 MPD 执行缓冲和确认 — PB-BUF-EXEC-001

- **steady state目标**：已受控时MPD短缓冲由实际Current A、MS计划并经MPD确认的Next B、Next Next C组成，若仅1–2首可播放则相应减少。**稳定≤3项，执行插入/切换瞬态≤4项**；Stop可空。旧版本残留400首/foreign状态不是稳态，不得暗中clear；不把MS完整400首传给MPD。MPD缓冲后两项供后端实际核验，不是Web Next来源。
- MPD原生命令无标准 `play_uri` 原子捷径；目标的正常执行为 `addid <mapped-uri>` 接收 MPD ID，再 `playid <id>`，或对已经确认属于该 occurrence 的现有 ID `playid`。禁止按URI扫描MPD全表选择「第一个相同歌曲」，禁止以 `clear → addid → playid` 作为普通切歌的默认序列；已有首曲播放期间更不得默认 clear。
- 执行器拥有单实例写序列与`operation_id + business_generation + connection_epoch + execution_generation` fence；相同URI不能证明重复occurrence的身份，MPD ID不跨连接/重启有效。受控执行绑定只包含**当前及预备的后续至多两项**`(queue_item_id, mpd_song_id, mapped_uri)`和版本/连接/模式/业务代次；这些操作记录只用于控制归属/异常恢复，**不得代替MPD最新实际Current/Next/Next Next采样**。
- 每轮必须取得**一致的短缓冲样本**（前后 status + 实际条目、版本/当前 ID/连接代次核对）。MPD状态自然变化可以被接纳，但不允许通过忽略未知版本漂移来「通过测试」。每条有副作用命令记录送达阶段、ACK和可归属确认；至少最终的 `current MPD id+URI+state` 必须与目标绑定一致。不得因为 `addid` ACK 就提交业务播放成功。
- 当已有合法受控缓冲发生正常自然进位，MPD自主从 A 播B；MS**绝不能再次 playid B**。先确认 B 的执行身份，再将 A 标为 Played、B 置 current，清理 A 并补业务下一项 C；PAUSED 的 B 仍保持 PAUSED。清理导致位置变化时以 ID 重新核验，不把 `position=0` 作为自然进位的前置条件。
- MPD 写入模式需满足 `random=0, repeat=0, single=0, consume=0`。取得明确控制权时可以执行**经目标MPD能力验证的**模式预检查/必要配置，并重新核验；其余观察、runner、页面 GET/WS **不能偷偷重设模式**。未知、不支持、被外部修改或无法验证时 fail closed、展示真实状态，保留业务 Queue。MPD 的原生 `next/previous` 不是业务 Next/Previous 的权威入口；用户切歌由 MS 选择 queue_item_id 并用指定 ID 执行。

#### 8.10.3 四类播放动作和前置下一首 — PB-BUF-PLAY-001 / PB-BUF-AUTO-001

- **显式 Play Now/Start/集合播放**：MS 确定或创建精确业务 occurrence，预校验目标 Song/URI 可用，规划业务变更，执行 `addid/playid` 或已绑定目标的 `playid`；确认 MPD 实际播放目标后联合提交业务 current、Context/History/Queue revision、完成回执。即使此前未绑定，用户的**明确选曲**也是唯一允许的新接管授权；但不得把此前不可信的 History 自动补成自然结束/用户跳过。若取得控制权前 MPD 残留旧实现400首或其它客户端队列，采用**单独、明确受控 takeover/清理路径**，对真实MPD状态和实际副作用记录证据；不得在启动/刷新/只读时自动清空，也不能用稳态缓冲上限掩盖迁移风险。
- **Queue/Played/Previous/Next**：目标只能按 MS queue_item_id/Played顺序裁决；重复 Song/URI 不去重、不选错 occurrence。目标若已在短缓冲中，直接用绑定 ID；否则按受控 addid→playid 引入目标，并在确认后清理不再需要的 MPD 旧条目，刷新预备 next。旧 item 的 Played/History 原因仅按已验证的显式操作提交，不把未观察的中间项视为已播放。
- **单纯改pending**：MS数据库独立保存全部待播与排序；未触及MPD预备next/next-next的项目不触发对应MPD变动。若插队、删除、排序、清空待播、AutoPlay或availability影响任一已预备项目，应基于**最新真实MPD样本**调整并确认两个预备位置；不允许用户成功删除B后仍将B作为受控下一首。与MPD自然进位并发时先采样确认，采用业务CAS/代次或保守冲突，不能假成功。旧业务Current/Played不随后台采样自动冒进。
- **AutoPlay**：原有低水位5/每批最多5候选和全量业务Queue策略不变；仅预备MPD当前后的**最多两首**可执行项。MPD从A自然进位到B后，MS按实际ID/URI确认B再清理A、预备C和D；不重复playid B，不把AutoPlay batch或400首交给MPD。未知/无候选/断线时不得静默接管或按猜测历史继续。
- **暂停/恢复/seek**：控制目标仍使用现有 current-target token、绑定代次与 MPD 实际 current 确认。暂停和恢复不得重新分配 occurrence、重排 Queue、重新起播目标；seek 不影响 Queue/History，只用对应目标的 MPD 进度回读确认。explicit Stop 仍是明确独立意图，终止 AutoPlay 接管，停止MPD并作受控缓冲清理；Stop 不隐式选择下一首。音量/输出由既有 Output Manager/MPD adapter继续管理，播放迁移不重定义输出。

#### 8.10.4 事务、重试与一致性 — PB-BUF-TX-001 / PB-BUF-RECOVERY-001

- **不允许跨MPD多轮网络I/O持有SQLite写事务**。建立单owner序列化的预检/固定计划（Queue revision、current occurrence、预期目标、connection/binding generations、request key），释放DB锁后执行外部命令；在最终短原子事务内重验 CAS、提交 Queue/Playback/History/runtime/journal terminal与 event-registration。最终 Web成功回执、Queue/History/版本通知只在 MPD确认和 SQLite成功提交后出现。若阶段实现必须变更架构的一致性锁，先提供跨服务 barrier/invariant；绝不把「事务已开且await MPD」当作最终方案。
- SQLite rollback **不撤销**已发送的MPD命令。超时、取消、通信断开、写入/提交失败、其他 owner、命令响应丢失进入明确 `UNKNOWN/SYNC_FAILED/UNBOUND`，记录**可归属的命令前缀**并失效不可信绑定；绝不能自动重发 `addid/playid`，不能按URI回猜一次未知 addid，也不能把部分MPD成功写成业务成功。能证明原意图、前缀、代次和唯一结果时，原 key可恢复或返回已提交 terminal；不能唯一证明则显式接管/只读恢复，不承诺进程崩溃前未提交操作跨重启 exactly-once。
- 多客户端/连续点击由服务端单owner序列 + Queue revision/CAS + token generation 拒绝迟到意图；收到未知终态的前端遵循现有共享 TaskActions/key 恢复，不因为新executor把所有 unknown 伪报成功或重试成功。重复提交成功 key返回原 terminal，**零新增 MPD 控制、occurrence、History、revision**。新 key 的新意图必须重新验证，不复用旧 current。
- **外部MPD客户端修改playlist/song/modes，MPD或MS重启/连接 epoch 改变，样本不一致**：不得凭URI认领 MS current，不反向覆盖 MS Queue，不自动 stop/clear/play，不补造 History；业务保留，观察实际状态单独可见，写权限按已有只读门禁受控；只有明确选择歌曲经完整再确认可以重建执行控制权。特别要证明外部播放相同 URI 但不同 MPD ID 不会误认业务 current。断线后若MPD仍自主播放短缓冲中的剩余项，重新连接也不得凭猜测重建业务历史。
- **History**：沿用 §8.9.4 的保守证据规则。有效绑定内确认 A→B 只证明离开当前，不证明自然播放完；未被确认的B/C不可计入 Played 或永久 History；不知道原因就不要写成 Stop/Skip/NATURAL_COMPLETION。§3.3.2 `explicit_stop_generation`、History active/session/事件提交时机不变。

#### 8.10.5 状态展示、性能界限和过渡 — PB-BUF-STATE-001 / PB-BUF-PERF-001 / PB-BUF-MIGRATION-001

- 服务端业务`QueueSnapshot`继续返回完整MS SQLite Queue，但**Web播放/暂停/停止、当前歌曲、进度只选MPD实际采样**。实际URI经精确URI Mapper反查MS Library的Song元数据（标题/艺人/封面/歌词），即使尚未绑定业务queue_item_id，也可显示该实际媒体事实和进度，**不能据URI认领业务occurrence、History或控制令牌**；无法反查则显示真实URI/未知歌曲并提示。**Web下一首、再下一首、待播Queue、Played、AutoPlay始终仅依MS业务Queue**；异常时标业务尚未与执行缓冲同步，不取MPD下一首作Web替代。MPD实际样本stale/unknown时标明最后观察，停止进度外推、不填0；GET/WS只消费缓存无控制。
- Web保留现有 Task8/9 API、路由、Player/Queue视觉与点击语义。若旧DTO观察字段不足，可以**向后兼容 additive 扩展**运行诊断，但不更换现有字段含义、响应成功语义或旧键，且先冻结wire增量和consumer proof。400首 Queue 的 Web 元数据读取/虚拟化可单独优化，不借执行器重构改变业务展示或已验收布局。
- **复杂度门禁**：当N≥400 pending时，MPD只容纳当前和至多两首预备歌曲（稳态≤3、瞬态≤4），普通操作涉及至多4个MPD条目；MPD控制及局部读取规模不随MS业务Queue数量增长。不得每添一首重新读取逐渐增长的全MPD playlist；MS SQLite/HTTP和Web元数据成本须单独监测、不能在状态lease发送时每秒盲目重传400首。
- **部署迁移**：Task9当前镜像及持久数据库是改造基线，不直接在其上实验播放；不删除、重建或批量重写现有SQLite/音乐。可新增执行器所需 schema，但须正向迁移/rollback策略和老数据兼容；不保留跨进程旧完整映射作为新可信绑定。需要清理历史大MPD队列时仅在明确播放接管授权下执行；真实NAS验收在自有验证环境、原队列备份/可恢复预案后进行。旧Task9、Final NAS验收不得替代新执行器的真实 MPD/DAC 门禁。
- 新合同的实现依赖、Contract Matrix、逐Batch RED→GREEN、真实MPD门禁及未关闭风险，唯一由 [Bounded Execution Refactor Plan](../plans/2026-10-12-mpd-bounded-execution-refactor-plan.md)分配。本次只冻结文档，不修改production/test，不声称任何测试或实机结果。

#### 8.10.6 MPD实际状态单一观察源 — PB-BUF-ACTUAL-001 / PB-BUF-OBSERVE-001

- **事实源**：后端维护唯一`ActualStateOwner`（具体类名不强制），持有最新、可验证的`connection_epoch/sample_generation/observed_at/actual_state/actual_current(songid,URI,position)/elapsed/duration/playlist_version/length/modes/actual_next/actual_next_next/freshness/error`。Current及物理后两首必须来自**MPD当下真实回读**，不允许从上一次addid/playid成功、恢复账本或MS预定列表直接推导为实际事实。实际next/next-next只供后端校验执行缓冲和安排下一条命令，**不作为Web下一首权威或Web展示字段**。
- **监听与兜底**：MPD协议监听使用独立TCP连接执行`idle player playlist options`；通知仅是变更信号，不包含当前事实，触发尽快重新采样。正常约每轮完成后1秒调用`status`读取真实状态/进度作漏事件兜底，状态变更/重连/控制确认立即做有界一致采样。idle与查询连接分离；idle断线重连/退避期间仍保留轮询，轮询失败显示unknown/stale，不忙循环。一个服务进程只拥有一个actual事实缓存与单个播放写owner，不允许StateObserver与RecoveryRunner各自建立可冲突的实际当前。
- **MPD小缓冲回读**：当已受控且实际MPD playlistlength≤4时，使用`status → playlistinfo 0:4 → status`（或目标MPD验证通过的等价命令）核对connection/partition/playlist版本/长度/current ID/position/播放模式。elapsed自然推进允许；不稳定样本有界重读后UNKNOWN，不拼接两个时间点。计算实际Next/Next Next从**实际Current position之后**找，不默认current在位置0：例如A尚未清理、B已在position1播放时，B才是实际Current。旧大队列>4/foreign/越界样本不认领为短缓冲；可以额外只读`currentsong`或`playlistid <id>`取得actual current用于Web真实显示，但不得因局部读取猜测完整队列/自行清空。旧MPD能力探针仅证实命令存在，具体组合在B6真实验证。
- **任何播放控制强制实态前置及事后确认**：用户Play Now/Queue/Played/Next/Previous、pause/resume/seek及改变物理预备后两首的Queue/AutoPlay操作，均须在串行控制fence内获得**新的MPD实际样本**，核对真实Current、缓冲、代次、模式及业务Queue CAS，再制定实际命令。发送后重新采样，确认精确目标MPD ID/URI/state才提交MS成功。命令记录/ACK仅证明已尝试/被接受，不证明「现在正在播放什么」。MPD自然进位可能发生在两次读取之间，出现竞态需重新规划或fail closed，不承诺跨SQLite/MPD原子。
- **MS History与业务状态不受推测污染**：MPD新样本能够证实采样时A或B是current，不能证明中间漏看的歌曲是否播放/自然完成。只有可信的当前转移或已验证显式操作才可按既有规则更新Played/History；不能凭MPD下一首或日志补造History，不能从MPD物理playlist回写/覆盖完整MS业务Queue。

#### 8.10.7 Web实际播放权威与过期合同 — PB-BUF-WEB-001

- **唯一MPD权威显示范围**：Web Player的「正在播放/暂停/停止」、「实际当前曲目」、「曲目实际elapsed/duration」是MPD实际采样的表示；实际媒体标题/艺人/封面/歌词/音频参数只从MS Library按已核实MPD URI取得。**Web下一首/再下一首、Queue/Played、AutoPlay与下一首按钮目标完全使用MS业务Queue**，即使MPD物理缓冲下一首不同也不静默替换。真正发生实际进位时Web先反映MPD实际Current，MS再完成可信业务Queue推进；未推进期间标记「业务Queue未确认」。
- **脱离业务occurrence也须如实显示**：fresh、有效的MPD current即使业务绑定失败，也应以独立actual身份显示其真实state/当前曲目/进度；URI→Library匹配只用于展示，不形成Queue ID绑定、控制令牌或History证明。实际STOPPED但playlist还保留曲目时，不能称其「正在播放」；缺少可信媒体映射时显示「实际歌曲未识别」及URI诊断，而非错拿业务Current标题。现有绑定专用`position_seconds/duration_seconds`语义不变，不能将其偷换为所有actual进度。
- **兼容DTO**：保留现有`GET /api/state`、WS`snapshot/invalidate`、`epoch/sequence`、业务`playback/current_song/queue`及旧Web合同；仅作向后兼容additive字段：`playback_observation.actual_elapsed_seconds/actual_duration_seconds`（与MPD actual ID/URI同一采样）、必要的实际采样代次/观察时刻与可空`FullStateSnapshot.actual_song`（经URI精确唯一映射的MS Song）。Web播放器读actual字段；未提供字段时明确降级，不能借业务进度/标题伪装实态。MPD的物理next/next-next不增加Web展示DTO。必须以真实后端fixture→旧/新Web decoder + Player proof冻结增量。
- **推送与过期时间**：后端idle驱动变化、约1秒状态采样；MPD播放进度的真实变化经已有playback invalidation→GET刷新。针对PAUSED/STOPPED等值不变但确有**新成功采样**的情况，在有Web订阅时允许至多每3秒一次仅用于保持实际观测租约的`playback`限频invalidate（使用原有WS帧和读取链，业务Queue revision不得因lease增加），作为Architecture §12.2「观测时间单独不发通知」的唯一新执行路线例外。不得以重发旧样本延长租约，不得为1秒status轮询每秒无差异地全量GET 400首。性能专项必须验证这项限频传播不使大Queue页面阻塞；必要的轻量传输优化需另先冻结兼容合同，不擅自改WS协议。
- **显性反馈**：连续>3秒没有新的可信MPD样本，Web以自身单调时钟显示「实际状态同步延迟」；>6秒或明确断线/观测失败时显示「已过期/未知」并冻结进度外推。旧`fresh`字段、不断重复的旧snapshot或新到达但observed_at未更新的消息都不能刷新实际事实租约。按MPD断线、Web↔MS断线、实际MPD正常但业务Queue未绑定分别告知；复用WEB-UI-NOTIFY-001唯一AppBar活动/通知，禁止增加Player正文新状态栏或修改已通过的UI布局。MPD断线时无法知道当前即时事实，只能显示最后观察并明确stale，不能承诺断网也实时同步。
- **顺序/只读**：相同epoch内只有更新的sample_generation/真实observed_at可覆盖旧MPD事实；迟到采样、旧WS/HTTP及控制执行前的样本不能覆盖已确认的新current。GET/WS/idle/status轮询不得触发MPD播放、Queue/History变化或自动创建occurrence，按§8.10.4继续执行外部控制的确认/幂等规则。Web只收到MS的业务Next，不根据MPD物理next移动业务Queue。

**专项RED proof（均未实施）**：真实Adapter/MockMPD/FakeClock/SQLite/API/WS/Web分别验证：A→B且MPD实际current处于position1、A→C、重复URI不同MPD ID、三首稳态/四首短暂过渡、旧400首只读退化、漏idle通知1秒轮询兜底、PAUSED>6秒但持续真实采样仍显示fresh、MPD断线/Web单独断线、3秒延迟与6秒超时、同旧样本不能续租、业务绑定失效时仍显示正确实际标题/进度而不认领occurrence、Web Next只由MS业务Queue决定、MPD控制前后实采样和无业务读副作用。真实MPD/DAC验收单列，不用Mock绿色冒充。

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
