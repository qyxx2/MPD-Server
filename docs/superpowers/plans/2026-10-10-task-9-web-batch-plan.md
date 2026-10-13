# Task 9 Web Implementation Plan

> 2026-10-11后续范围：当前Task9旧Gate/验收保留；后续最小NAS交付改走[Final Batch Plan](2026-10-11-v0-1-nas-final-batch-plan.md)。旧A05成功通知撤下属于历史已验行为，新活动增量归Visual §6、Final B04；本计划不重新实施该增量，也不把新范围标为已通过。

当前进度（2026-10-11 B10交付）：B01–B09 **CLOSED / HUMAN PASSED**；B10综合proof、自动Gate与production/LAN预检完成，**OPEN / HUMAN PENDING**；用户新增实机各功能Gate因当前endpoint/音乐映射待提供及历史NAS TCP超时，**BLOCKED / NOT RUN**。Task9整体未完成。当前范围/矩阵/证据/最少手机及实机步骤见[单份final acceptance](../archive/task-9/2026-10-11-task-9-final-acceptance.md)。历史OPEN/PENDING不重开已关闭前置。

## 2026-10-11 B03历史Gate：用户验收通过

用户明确“可以了。验收通过”，当前B03展示/交互及已实施B04 occurrence点击/待播拖动子集、A04播放/手感及A05临时通知修正验收通过。**B03 CLOSED；B04已实施子集 CLOSED；完整B04剩余Next/Add、删除/清空/保存 NOT STARTED。** B01/B02保持CLOSED。此前OPEN/PENDING段落保留为历史，不再作为当前前置阻塞。

关闭依据与限制见同一[B03 acceptance最终关闭记录](../archive/task-9/2026-10-10-task-9-b03-acceptance.md)。本轮仅更新验收状态和提供后续提示词，不开始B04剩余工作；不重做已接受行为，不扩大未来Batch，不commit/push/PR/merge，保留dirty checkout。真实MPD/NAS/DAC仍NOT RUN，PWA DEFERRED，ArtworkRef单Song500仍为批次外未修复项。


## A05 通知限定修正（2026-10-11）

- [x] 用户A04两项反馈无其他问题，既有Queue/播放保持；旧成功结果常驻通知与“当前临时状态”冲突，同步Visual/audit。
- [x] global-notices行为RED→GREEN：成功通知撤下、正常同步无恢复按钮、读失败恢复后撤下、跨页/epoch不复活；保持unknown原key、离线及并发未解决错误。
- [x] 通知精确文件→受影响Queue/Player/壳关系Gate→完整Web/typecheck/build、既有后端wire读取Gate；同源LAN确认排序成功后无日志图标/条目，提供A05 label。
- [x] 用户只观察本次通知修正；不重做已接受的播放/排序手感，不推进其他Batch；无commit/push/PR/merge。


## A04 最小反馈修正计划（2026-10-11）

- [x] 自有HTTP loop复现冻结Mock位置；启用验收单调时钟，验证超过5秒持续推进、暂停稳定、target resume保持位置。产品时钟租期/服务端冻结合同不改。
- [x] 长按漂移取消/旧落点提交行为RED→GREEN；跟指浮层、稳定列表和插入标记、边缘滚动、释放坐标重判；共享通知层在浮层上方。
- [x] 精确行为→Queue文件→通知/导航关系Gate、完整Web、typecheck/build；.venv既有clock单节点→fixture文件→Queue/事务/幂等/control-target后端Gate；独立审阅及diff/LAN核对。
- [x] A04同Wi-Fi手机复测：歌曲播放>10秒，暂停后继续不归零；长按待播≡移动，前/后落点正确、浮层跟手、边缘滚动和无效落点撤销。真人反馈前B03及本轮子集OPEN，完整B04未完成；其余原验收项保持待验收状态。

详情追加同一B03 acceptance，A03结果不代替A04验证；不commit/push/PR/merge，不碰删除/清空/保存/Next/Add或其他Batch。

## 2026-10-11 B03修正 + B04点击/拖动子集最小计划

本节记录用户新的限定授权，覆盖下文旧三分区/+10/切页保留/Queue点击菜单方案。三个未定义边界见audit最新修订输入，已由用户确认；不是授权范围的再次审批。当前checkout既有修改全部保留，不commit/push/PR/merge。B03未关闭，B04仅允许本节子集，不推进删除、清空、保存、Next/Add或其它Batch。

- [x] 明确current/Played排序范围、多曲AutoPlay显示、留页自动切歌定位规则；同步唯一Playback §3.1–3.2/§5/§6.2及仅Web消费者复位说明、Visual Queue例外、Architecture本地UI投影引用、audit矩阵。冻结服务端PB-SONG-NOW-001/PB-STOP-LIFECYCLE-001领域与传播合同不变。
- [x] 更新queue-view测试，先观察行为RED：进入/返回隐藏并定位current，a,b,c,d到c初始c,d，下拉依次b,a且最终顺序a,b,c,d；无分组/按钮/details；确认播放/暂停图标及unknown/stale/unbound拒绝；单曲候选预览与多曲已确认规则；metadata错误/迟到及重复occurrence原断言保留。
- [x] 最小修改QueueView、QueueOccurrence、queuePresentation、queueUi及Queue局部CSS：连续可见投影，不删改canonical queue/永久History；复用共享Song cache及notice，不改变壳预算。进入定位等待有效current与DOM，不用song_id定位重复项。
- [x] 新queue-actions.test先RED：所有类别点击精确POST item play；拖动按before_queue_item_id PUT；只改local draft，捕获epoch/generation/revision/current/成员并在已知变化、断线、离页取消；pending互斥、unknown原key恢复及跨页回执、失败/迟到ACK不伪造canonical；成功通过共享权威read收敛。最小接入现有持久TaskActions/createIntent，无第二套key或连接。
- [x] 精确节点GREEN→两个Queue文件→resource-cache/wire/player-facts/mutation/global-notices/shell-navigation/global-artwork及受影响Player回归；后端test_realtime_queue/test_realtime_history/test_stop_lifecycle、既有Queue mutation/idempotency/service Gate（选择真实节点，不以全量代替目标）；Web typecheck/build，必要完整回归，git diff --check/stat/status与本轮diff核对。后端执行只用.venv，不访问live MPD。
- [x] 在自有SQLite/Mock验收fixture准备单曲候选、多曲含Played/无Played及重复occurrence；核实当前LAN IP、产物字节、同源API/WS，交付新label实际URL。手机最少检查进入/揭示/返回、点击各类和重复项、允许范围拖动/取消、长文本及断线顶部恢复；留页自动切歌按确认规则验收。真人反馈前B03及本轮子集Gate OPEN，完整B04仍未完成。

验收记录继续追加同一B03 acceptance，分别标示合同、实现、自动、LAN、HUMAN、真实MPD/PWA；旧A02通过与URL不当本轮新结果。

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan Batch-by-Batch after review and execution authorization. If the user explicitly selects delegation, use `superpowers:subagent-driven-development`. Steps use checkbox syntax. Do not implement a Batch whose prerequisite or required phone Gate remains open.

**Goal:** 在真实main的Task8基础上交付共享UI及Queue/Library/Playlist/Search/Favorites/Settings；保留服务端权威和已确认Player。

**Architecture:** 唯一AppShell拥有连接、全局背景、通知和已发送intent恢复上下文；路由只替换内容。复用既有API/key、canonical store及resource cache。普通song Play Now由独立后端prerequisite提供，页面不拼接请求模拟。

**Tech Stack:** 既有Vue3、Vue Router、TypeScript、Vitest/Vue Test Utils；Python/FastAPI、SQLite、PlayerPort及pytest。使用现有Node依赖和`.venv`。

**Spec:** [主 Plan Task9](2026-09-25-mpd-server-v0-1-implementation-plan.md#task-9web-queuelibraryplaylistsearchfavoritessettings)、[Visual Spec WEB-UI-*](../specs/2026-10-03-web-pwa-visual-design.md)、[Architecture §4.1–4.3/§12/§19.5](../specs/2026-09-25-system-and-development-architecture-design.md)、[Playback](../specs/2026-09-24-playback-model-queue-semantics-design.md)、[Library](../specs/2026-09-24-library-playlist-tag-search-design-2-1.md)。输入：[Task9 Contract Audit](2026-10-10-task-9-contract-audit.md)。本计划不取代唯一长期Specs。

## Global Constraints

- 基线 `main / 14c6239283f4fed079f07ab817964b23e87e793c`；执行时重新核对Git，不把审计时基线当未来checkout事实。
- UI长期规则只引用WEB-UI-*；保护已冻结歌词、Player facts/clock/controls/seek/比例，无Stop UI、无Player Output卡片。
- Architecture三层、degraded read-only、原key传输retry、禁止speculative canonical/cache commit全部继承；HTTP ACK后权威重读，WS invalidate不当ACK。
- 所有新增mutation使用已有`createIntent/send`；路由离开不丢已发intent，不补发离线请求，不建立第二个canonical store/连接/cache。
- 不改schema/依赖、不安装PWA、HTTP串流、认证、Task10配置/备份/日志，不做桌面专用布局。
- Python只用已有`.venv/bin/python`，先检查requirements，不修改环境。验证从精确节点→文件→受影响关系Gate；全量不能代替显式目标测试。
- G9-01当前已冻结为Playback Spec §3.3.1 PB-SONG-NOW-001，用户批准并授权直接B02实施；原审计时DRAFT描述保留历史时态，不能代替本节当前合同。B01不依赖它。
- G9-02采用现有API+已知变化取消草稿方案；不承诺HTTP expected-version冲突防护。若要求严格版本保护，先单独审核公开API扩展。
- 本轮仅形成审计/计划，所有Batch **NOT STARTED**；没有产品验收通过。当前请求不授权执行、commit/push/PR/merge。

## Review Focus

- 同URI重复occurrence：所有Queue操作按item id，普通song动作不会错误选中旧项；B02/B04/B05机械证明。
- pending/未知回执跨页、断网与epoch切换：intent不丢、不自动补发，不让HTTP GET恢复写权限；B01/B04/B09证明。
- Favorites不可用成员、Playlist完整成员与可播放集合不同：星标不丢，不能按playable ids重建编辑顺序；B07/B08证明。
- current转移/AutoPlay及其他客户端更新碰到拖动：已知过期草稿取消；未送达并发窗口按服务端实际执行裁决并报告限制；B04/B07证明。
- 迟到封面/搜索/metadata及长文本：旧资源不串身份，唯一背景/bar/nav保持几何，缺字段不伪装0；B01/B03/B06/B09证明。

## 1. Batch 顺序、依赖与原 Step 映射

| Batch | 交付 | 前置 | 主Plan Steps | 合同 / 手机卡 |
|---|---|---|---|---|
| B01 | 持久壳/唯一通知→共享背景→四项导航；空内容占位 | Task8修订手机Gate | 12前移、13受影响部分 | SHELL/BG、WEB-UI-*；H01/H10，M01/02/04/05/06/07 |
| B02 | 原子song Play Now后端prerequisite | B01关闭，G9-01合同审核关闭 | Task9增量prerequisite | SONG；后端自动，无独立UI HUMAN |
| B03 | 连续Queue、metadata、进入定位与下拉揭示Played | B02；最终生命周期明确 | 1、3、4 | QUEUE-001；H02（显示/展开），M01/02/04 |
| B04 | Queue播放/Next/Add、拖动、删除/清空/保存 | B03 | 2、5的Queue适用部分 | QUEUE-002/SAVE；H02（排序）/H03/H04/H10，M01/02/03/05 |
| B05 | 通用SongRow与Library分类/详情/PlayAll/Shuffle | B04、B02 | 5、7 | SONG/LIB；H04/H05/H10，M01/02/04/05 |
| B06 | 六字段Search及查询生命周期 | B05 | 10 | SEARCH；H08/H04，M01/02/03/04 |
| B07 | Playlist CRUD、完整成员、reorder | B06 | 8 | PLAYLIST；H06/H04/H10，M01/02/03/05 |
| B08 | 全局FavoriteStar与Favorites | B07 | 6、9及所有SongRow星标接线 | FAV；H07/H04/H10，M01/02/05 |
| B09 | Settings About及既有NAS_DAC输出 | B08 | 11 | SETTINGS；H09/H10，M01/02/04/05 |
| B10 | 综合关系Gate、生产构建及手机关闭 | B01–09关闭 | 13、14（另行授权commit） | 全矩阵；仅跨页综合/尚未验证或受影响真人项 |

纯壳独立先行，B02不绑入B01。B03的Played复位依赖最终生命周期，避免按草案写死再推倒。顺序是默认执行顺序；未经用户调整不跳过必要真人Gate，不因为后端只读API可用而先交付缺少统一动作的页面。

## 2. 文件与接口边界

以下新增路径为计划，当前main并不存在；既有factory/类型以实际导出为准，不重命名全仓库。

| Owner / 文件 | 职责和接口 |
|---|---|
| B01 `web/src/runtime/playerSession.ts`（新） | 提升既有`createPlayerActions`实例及其恢复上下文至AppShell生命周期；复用clock/presentation，保留mediaMode。`createPlayerSession(store: PlayerStore,runtime: PlayerRuntime)`返回既有actions/clock/presentation及`dispose():void`；仅壳卸载dispose，页面不dispose持久owner |
| B01 `web/src/runtime/taskActions.ts`（新） | `createTaskActions({api,player,refresh})`；`run(intent:MutationIntent,decode,read,description?:string):Promise<void>`、`retry(key:string):Promise<void>`、`dispose():void`。按key保留pending/unknown/confirmed及原intent；description仅为可辨认的动作/资源展示名，不参与请求/key或恢复语义；确认后只read，retry只允许unknown且writable；epoch退役恢复动作 |
| B01 `web/src/stores/notices.ts`（新） | `createNoticeStore()`、`set(notice)`、`remove(id)`、只读`entries`；notice `{id,scope,message,busy,level?:'warning'|'info',retry?,read?}`（level仅表达Visual通知优先级），恢复closure引用原owner；不拥有业务事实/key生成 |
| B01 `web/src/stores/artwork.ts`（新） | `createArtworkStore({fetch})`、`read(song:Song,scope:string)`、只读decoded URL/status、`dispose()`；同identity共享单flight；generation+解码检查，object URL只在无消费者/退役后回收 |
| B01 layout `AppBar.vue`、`AppBackground.vue`、`BottomNavigation.vue`（新） | 唯一UI入口；AppShell持久装配，不页级复制；nav路由见audit §5 |
| B01修改 `App.vue`、`AppShell.vue`、`router/index.ts`、`PlayerView.vue`、`PlaybackStatus.vue`、`ArtworkStage.vue`、`styles/app.css`/`tokens.css` | 迁移owner/预算；保持Player正文和歌词行为；top routes先稳定空占位，不宣称页面完成 |
| B02 `server/app/services/playback_service.py`、`services/queue_manager.py`、`repositories/queue_repository.py`、`api/playback.py`、`api/schemas.py`（按最终Spec实际需要） | `play_song_now(song_id:str, *, request_id:str|None=None, request_payload:str|None=None)` + additive`POST /api/playback/songs/{id}/play`→QueueItemResponse；一个Service外层事务/确认/terminal/realtime联合delta，既有Queue Play Now不改义 |
| B03–09 `web/src/types/resources.ts`、`services/resourceWire.ts`（新） | Collection/List/Playlist/MPDInfo DTO及runtime decoder，逐域在所属Batch增加；`parseCollection`、`parseSongList`、`parsePlaylist`、`parsePlaylistList`、分类list decoder、`parseMPDInfo`；禁止decoder用类型断言冒充校验 |
| B03 `views/QueueView.vue`、`components/queue/queuePresentation.ts`（新） | `deriveQueue(snapshot:FullStateSnapshot,writable?:boolean)`保留业务分区，输出确认图标与候选可见投影，identity为queue_item_id；Song metadata通过既有Library缓存读取 |
| B03 `web/src/stores/queueUi.ts`（新） | `createQueueUi(player:PlayerStore)`返回响应式`expandedCount`、`enter():void`、`reveal():void`、`dispose():void`；逐条揭示，按accepted生命周期reset。AppShell拥有实例，每次路由进入Queue归零；留页current变化按最早已揭示occurrence保留可见历史；不缓存或写回Queue业务事实 |
| B04 `components/queue/queueActions.ts`（新） | 捕获item id/草稿基线；装配真实API intents；保存name和提交时最新UpNext语义分层 |
| B05 `components/library/SongRow.vue`、`SongActionMenu.vue`、`songActions.ts`、`views/LibraryView.vue`、`CollectionView.vue`（新） | `SongTarget={song_id:string;queue_item_id?:string}`；`playNow(target)`按目标类型dispatch、`playNext(songId)`/`add(songId)`沿用现有接口；Collection source描述直接交后端 |
| B06 `views/SearchView.vue`（新） | route q/query-generation、Collection→Song资源，使用同一SongRow及library store |
| B07 `views/PlaylistView.vue`、`components/library/playlistActions.ts`（新） | 同一组件承载list/detail；完整成员CRUD/reorder；名称/drag草稿与已发intent分层 |
| B08 `components/library/FavoriteIcon.vue`、`views/FavoritesView.vue`、`stores/favorites.ts`（新） | 从共享playlists cache的GET /api/favorites/members取得完整有序membership；`isFavorite(songId)`、`setFavorite(songId,enabled)`，不用第二套resource cache |
| B09 `views/SettingsView.vue`（新）、修改`components/player/OutputPanel.vue` | 复用输出控制，动作状态owner移至持久runtime；所有结果/异常进唯一顶部，About独立读取；不把Player文件位置误解为Player仍显示Output |

若实施发现命名/边界需要改动，先更新本表与测试引用；不能在后续Batch消费尚未定义的接口。通用SongRow从B05抽取B04临时Queue行的共有菜单接线，B04只实现Queue适用目标，不提前实现Library/Favorites功能。

## 3. 统一自动/真人Gate

每Batch Contract Matrix **REQUIRED**，Relationship / Invariant **REQUIRED**，引用audit §6稳定ID。下面新测试名及文件均为待建立的proof，不是当前通过记录。

自动验证顺序：新增精确test RED（真实合同缺口；不是import失败作为行为证明）→最小实现→精确test GREEN→该文件→本Batch列明受影响回归→typecheck。纯视觉最小调整不造镜像测试；状态/身份/事务问题必须机械证明。Web命令：`npm --prefix web run test -- --run tests/invariants/<file>.test.ts -t '<name>'`，再去掉`-t`跑文件。

真人：自动GREEN并准备本机可用构建/同源API/WS后给一个实际LAN URL，不抄历史IP。M01/M02各可见Batch必验，其他适用卡见下；同一报告追加轮次，存`docs/superpowers/archive/task-9/2026-10-10-task-9-bNN-acceptance.md`（实际执行日更新文件日期），记录implementation/automated/Contract/Relationship/LAN/phone HUMAN/真实MPD/PWA分别状态。用户无需终端/DB/devtools，场景由AI最小夹具准备。必要HUMAN PENDING时只在当前Batch定位修复，不进入下一Batch。

旧Player受影响回归组P：`player-facts`、`player-controls`、`player-seek`、`player-clock`、`player-lyrics`、`player-notices`、`player-output`、`wire`，均在`web/tests/invariants/`。B01修改单路由相关旧assertion时只改Task9已授权导航预期，保留原facts/lifecycle断言。

## 4. Batch实施及验收步骤

### B01：共享UI基础（先做，独立可验收）

**Files/Interfaces:** §2 B01 owners；消费既有store/api/realtime/actions；产出持久session/actions/notices/artwork和四顶级路由，供后续页面接入。

- [x] 建立`global-notices.test.ts::pending_and_unknown_intent_survive_route_change`：发出请求→切Queue占位→unknown→从顶部原keyretry；断线不发送，确认后仅重读，并发两个异常均保留。
- [x] 建立`global-artwork.test.ts::confirmed_identity_decode_and_route_lifetime`：同资源跨四页仅一请求，迟到A解码不能盖B；404/无图/default、error、stale保留与身份明确失效清除分开；背景不取lastSong/handoff作为新身份。
- [x] 建立`shell-navigation.test.ts::one_shell_one_connection_four_routes`：默认`/`、四项与内部Library选中、返回/刷新、一次start/最终一次stop、一个通知入口；Player只一份底部预算。记录基线几何/最小44px触摸范围及亮/杂乱图片对比度证据。
- [x] 按顺序最小接入：持久壳/通知owner→decoded背景→四项导航；保留空占位，不在此实现页面动作。迁移Player通知/原actions而非新建；修改Artwork消费者共用资源，不改歌词正文/解析/跟随/选择/cue。
- [x] 跑三个新文件、回归组P、`realtime/client/mutation/resource-cache`文件、typecheck与build；未触后端只需既有wire fixture读取Gate。生产构建通过再给LAN页面。
- [x] 手机H01：四页切换/返回/刷新只变中间内容；Player比例与封面↔歌词/3秒跟随仍正常，背景跨页连续，bar/nav不跳动。H10：断网与多个异常只在顶部，原retry/read可达且无离线补发。M04/M07覆盖长中文、缩放、亮/缺图、no-blur/reduced-motion；M06后台返回不假计时。全部必要项用户通过后关闭。

### B02：song Play Now后端prerequisite

**Files/Interfaces:** §2 B02 owners；接口FROZEN（PB-SONG-NOW-001），消费既有History/recovery/transaction/idempotency，产出原子song入口。

- [x] 先关闭G9-01：把audit待审核方案及所有边界补到唯一Playback Spec，确定首次/无Context/unknown external STOPPED、旧current/Played/pending provenance、确认/失败/replay/返回DTO；用户审核通过才建立实施RED，不能直接复制Start Track。
- [x] 新`server/tests/invariants/test_song_play_now.py::test_new_occurrence_preserves_pending_identity_and_joint_state`：真实SQLite/Services/MockPort，重复song pending ID/相对序不变、新current MANUAL、新token确认后可用、History/session按最终Spec、联合revision/事件；确认为根本功能缺失的RED。
- [x] 新API文件`server/tests/api/test_song_play_now.py`证明合法请求/key必需、404/unavailable先于控制、同key同内容replay无第二occurrence、payload冲突；同invariant文件覆盖明确Stop后新session/AutoPlay/Played、未知active不补原因、命令/确认/terminal/outer commit失败及部分执行retry。Queue原入口语义原样保留。
- [x] 最小实现最终Spec的单Service编排及additive API；复用middleware、恢复账本和current target代次，不新增schema或前端编排。
- [x] 跑精确节点→两个新文件；回归`server/tests/services/test_playback_service.py`、`test_queue_manager.py`、`server/tests/api/test_idempotency.py`、`test_mutations_playback.py`及`server/tests/invariants/test_realtime_queue.py`、`test_realtime_playback_transport.py`、`test_playback_control_target.py`、`test_playback_guarded_transport.py`、`test_d6_history.py`、`test_d6_execution.py`；新文件与改动生产文件定向Ruff。另验证公开DTO与existing wire Gate兼容。
- [x] 归档Contract→Spec→code→proof→fresh结果；无独立UI，phone N/A（普通song真实菜单交B05）。Mock确认不当真实MPD/DAC验收；B02自动和合同关闭后才进入B03。

### B03：Queue表示与Played（2026-10-11修订）

**Files/Interfaces:** QueueView/QueueOccurrence/queuePresentation/queueUi、既有resourceWire；消费snapshot canonical Queue与Library cache。按Playback §5 PB-QUEUE-VIEW-001输出连续可见投影，服务端分区/完整Queue不变。

- [x] `queue-view.test.ts::continuous_occurrences_confirm_icons_without_claiming_actual`：无标题/+10/details，重复ID保留，Played下拉最近先揭示、最终position升序；仅fresh bound confirmed playing/paused current有图标，stale/unknown/unbound/stopped无图标。
- [x] `entry_hides_played_pull_reveals_and_lifecycle_resets_without_inventing_stop`及`on_page_current_transition_keeps_revealed_history_and_scroll`：每次进入隐藏/定位、返回重置；留页切歌保留滚动/已揭示最早occurrence；Context/epoch/明确Stop counter仍复位，unknown/session/连接状态不假Stop。
- [x] `single_track_previews_first_candidate_multi_track_hides_all_candidates_without_mutation`：MANUAL pending存在为多曲、隐藏所有候选；无MANUAL pending且AutoPlay启用只首候选；canonical完整Queue不变，Played不计待播；metadata失败/身份错误/迟到原proof保留。
- [x] 最小实现上述可见投影、触摸下拉/滚轮揭示、单行标题艺术家；排序手柄触摸与历史揭示隔离，正文无详情或新通知系统。
- [x] 新修订所有目标/关系回归、typecheck/build/LAN证据见T9-QUEUE-A03；手机待反馈，旧A02自动结果不抵扣。
- [x] 手机H02/M01/M02/M04：进入current首位，逐步揭示、离页返回隐藏；单/多曲候选；确认/未知图标、窄屏长文本；留页切歌位置保持。用户反馈前B03 OPEN。

### B04：Queue动作及保存（点击/拖动已关闭；剩余续作见文末）

**Files/Interfaces:** `createQueueActions(player,runtime,tasks,playbackLocked)`输出`draft/locked/play/begin/target/cancel/drop/dispose`；QueueView长按handle与local preview，复用持久TaskActions、共享API/key及原snapshot读取。普通SongRow菜单不作为Queue默认点击入口。

- [x] `queue-actions.test.ts`：current/Played/待播/AutoPlay按occurrence精确POST，重复song不选错；pending互斥、跨页unknown原key恢复、offline拒绝、typed conflict重读、malformed回执不伪确认。
- [x] pending长按drag及before item PUT，只读本地draft；current/Played无拖动handle/放置目标。已知revision/current/成员、断线/离页/pointercancel取消。隐藏候选不删改，HTTP后权威读取；未送达并发窗口G9-02限制保留。
- [x] 独立审阅两项Important修复RED→GREEN：拖动后新鼠标按下不能吞掉明确播放；Queue pending/unknown跨页阻止Player冲突控制。只增加共享runtime lock，不改Player播放领域规则。排序触摸不同时揭示历史。
- [x] 手机H02（点击/排序）/H10（只读与原key恢复）及M01/M02/M05由用户整体接受；仅已实施子集关闭，完整B04未完成。
- [x] **B04剩余实施/自动验证**：Next/Add独立菜单、删除/清空/保存及`queue-save.test.ts`已实施，fresh证据见文末。
- [x] **完整B04真人Gate**：A01其它范围已接受；A02待播原occurrence首尾移动获用户明确验收通过。完整B04 CLOSED，最终依据见文末及B04 acceptance。

### B05：Library及统一SongRow

2026-10-11 A02：用户认可功能后授权直接修改六处界面。分类图标导航/顺序/单行、独立返回、专辑左图右文/占位、居中播放按钮和窄菜单已实施；该轮Web255/typecheck/build通过，320/390px浏览器验证及独立复核完成。用户随后明确“可以了。通过验收”，完整B05 **CLOSED / HUMAN PASSED**；本次仅更新文档，不重复测试。证据见[B05 acceptance最终关闭记录](../archive/task-9/2026-10-11-task-9-b05-acceptance.md)。B06未启动。

**Files/Interfaces:** §2 SongRow/SongActionMenu/songActions/LibraryView/CollectionView，resourceWire分类DTO；消费B02入口与既有CollectionRequest，产出所有普通歌曲共享菜单。

- [x] `song-actions.test.ts::ordinary_play_now_is_one_atomic_intent`：普通song一次POST到B02入口，无StartTrack/入队后play组合；Queue目标仍item id；三个菜单一致，unavailable不发播放、重试原key、confirmed后重读；favorite点击插槽不触发菜单/播放（真实收藏B08接入）。
- [x] `library-collections.test.ts::category_identity_and_server_collection_play`：albums/artists/genres/years/tags及全songs读取真实DTO，source id不由标题猜；PlayAll/Shuffle交source_type/source_id/randomize，空collection不假播放，随机序不由刷新重排。
- [x] 实现Library及内部详情路由；复用B04共有菜单接线到SongRow，保持Queue实际目标；完整membership与playable范围标注在正确业务槽，原因通知顶部。
- [x] 跑新文件及Queue两个动作/表示文件、`wire/resource-cache/global-notices`；Python `server/tests/api/test_library_api.py`、`server/tests/services/test_collection_service.py`、B02两个文件；typecheck。
- [x] 手机H04各歌曲菜单可用且同义，PlayNow保留原pending；H05类别/详情/返回、PlayAll/Shuffle所选collection正确，空/长名称/不可用可辨；断网只读及H10回页pending恢复。M01/02/04/05按用户整体功能认可及A02最终验收通过关闭，不追加复测或编造逐项真人日志。


### B06：Search

2026-10-11 当前B06 CLOSED / HUMAN PASSED。Library §6.1 LIB-SEARCH-VIEW-001按A03/A04反馈冻结：顶部SVG图标＋归类名称，默认内容无分组且全局去重，顺序继承归类与Collection；入口可进入对应归类详情并返回原搜索。A01/A02表示及A03仅定位为历史。限定增量执行清单：
- [x] 后端真实关系RED：新只读results入口与分类稳定身份/原顺序、artist含album-artist、tags、多归类上下文、直接歌曲去重复及空白/无匹配；原search接口保持，读不改Queue/History/revision。
- [x] 最小Service/DTO/API、Web同cache decoder和Search表示；真实wire fixture证明，不新增依赖/schema/客户端搜索算法或Search PlayAll。
- [x] 精确RED→GREEN→新增文件及原Search/cache/Song/Library/notice/shell关系回归；backend Library API/service/fixture与realtime-library关系，Ruff/typecheck/build/diff，独立审阅。
- [x] A02 LAN同源REST/WS/窄屏与A03/A04必要增量辅助核验已记录；用户认可A04最终表示及归类进入/返回，B06手机Gate关闭，各轮验证范围仍以acceptance记录为准。

**Files/Interfaces:** SearchView、resourceWire.parseCollection；消费route q和library cache；不新增Search业务算法。

- [x] `search.test.ts::six_fields_empty_and_latest_query_only`：title/artist/album/album_artist/genre/year真实fixture命中；空白为空，快速A→B迟到A不覆B；清空不保留旧命中；epoch/library revision推进拒绝旧DTO。
- [x] 实现`/library/search?q=...`、返回/刷新保留q并重读；Collection IDs读Song资源且保持服务端排序，不浏览器自建搜索索引、不补unavailable搜索项、不新增Search PlayAll。
- [x] 跑新文件及`song-actions/resource-cache/library-collections`；后端`test_library_api.py`搜索节点、`server/tests/services/test_library_service.py`搜索节点；typecheck。
- [x] 手机H08/H04与M01/02/03/04：沿用此前既有操作认可及本次A04整体验收认可关闭；不编造逐项手机日志，不重复要求验收或重跑自动测试。

### B07：Playlist

**Files/Interfaces:** PlaylistView/playlistActions、parsePlaylist/parsePlaylistList/SongList；消费playlists cache/full membership，产出CRUD/reorder。

- [x] `playlists.test.ts::full_membership_includes_unavailable_and_duplicate_is_rejected`：显示成员含unavailable；排序完整ordered_song_ids；重复409无乐观加歌；system Favorites不能改名删除；空Playlist不是读取失败。
- [x] `playlists.test.ts::draft_and_confirmed_mutation_have_distinct_lifetimes`：成员/playlist marker变化或离页取消drag，名称draft离页丢弃；已发intent跨页保留，204只重读；409成员不匹配后重读并提示重拖，同epoch迟到资源不回退。
- [x] 实现list/detail、create/rename/add/remove/delete/reorder；加歌选择复用既有Library，只负责成员管理不偷偷播放；服务端confirmed结果收敛列表与详情。
- [x] 跑新文件、`song-actions/resource-cache/global-notices`；Python `server/tests/api/test_playlist_reads.py`、`server/tests/services/test_playlist_service.py`、`server/tests/invariants/test_playlist_relationships.py`、`test_realtime_playlist.py`、`server/tests/api/test_idempotency.py`；typecheck。
- [x] 手机H06从空表创建→输入长名→加歌/重复拒绝→拖动→移除→改名→删除，页面结果与回页一致；H04点行不默认播放，H10已发操作跨页/断网仅原key恢复；M01/02/03/05通过。


最终状态：用户对T9-B07-A01整体验收通过，B07 CLOSED / HUMAN PASSED；必要手机Gate关闭，证据见[B07最终关闭记录](../archive/task-9/2026-10-11-task-9-b07-acceptance.md)。本轮不额外测试，不推进B08。

### B08：Favorites与独立爱心（2026-10-11用户补充优先）

**Files/Interfaces:** FavoriteIcon/FavoritesView/favorites store薄包装；复用playlists cache，消费完整`/api/favorites/members`及library+playlist marker。Library §5.3 LIB-FAV-UI-001 / §5.4 LIB-FAV-MEMBERS-001 FROZEN：Player艺术家同行靠右唯一直接可互动爱心；其它Song位置仅已收藏实心展示；既有单曲菜单提供一个当前状态纯文字收藏项，Queue更多菜单接入、整行播放不变。用户后续明确爱心而非五角星，实心复用主题accent。

- [x] 核对当前Git、B07用户关闭和实际代码；发现无系统Favorites Playlist投影，用户批准最小只读GET完整有序song_ids；不迁移模型/schema，现有收藏写接口不变。后端404 RED→GREEN。
- [x] `favorites.test.ts::unavailable_membership_and_cross_view_stars`及跨页关系：不可用收藏仍可取消；Library/Search/Playlist/Queue/Favorites/Player共用完整membership；直接爱心/菜单收藏不请求播放；两revision重读，完整顺序与真实后端fixture解码。
- [x] `favorites.test.ts::failure_and_unknown_do_not_speculate_membership`：same song pending互斥、确认前事实不改；失败保留confirmed，unknown原keyretry；回页不补发，DELETE204/read-failure只读恢复，epoch退役、迟到响应拒绝。
- [x] 共享membership owner及各页接线；Favorites按服务端完整顺序（含不可用），metadata失败保留身份/菜单取消，原因进顶部；PlayAll/Shuffle交FAVORITES source由服务端解析，播放门禁不用于收藏。
- [x] 新文件及`playlists/song-actions/queue-actions/search/resource-cache/global-notices`；Python完整成员fixture与`test_playlist_relationships.py`、`test_realtime_playlist.py`及`test_playlist_service.py`收藏节点；受影响Player/全Web、typecheck/build、Ruff/diff、独立审阅最终Gate。
- [x] LAN同源API/WS、产物及窄屏预检已通过（见B08 acceptance）。
- [x] 手机H07/H04/H10及M01/02/05：用户在A02交付后整体验收通过，关闭依据见B08 acceptance最终关闭记录；不编造逐项操作日志。

当前B08 实现/自动Gate完成，CLOSED / HUMAN PASSED，B09/B10未启动。独立只读补充授权与用户爱心设计取代旧系统Playlist读取及全列表互动星标假设。

### B09：Settings About/Output

**Files/Interfaces:** SettingsView、OutputPanel及持久输出action owner、parseMPDInfo；消费system API与canonical output，复用原NAS_DAC控制。

- [x] `settings.test.ts::about_and_output_are_distinct_authorities`：真实MPD version/source/stats/update/errors，未知不补0；REST aliases映射正确；CLIENT_STREAM disabled；无Task10控件；Player只有DAC confirmed摘要。
- [x] `settings.test.ts::output_unknown_survives_navigation_without_inline_notice`：pending/unknown/失败均顶部，输出confirmed不被last_request覆盖；离页不retire已发intent，原keyretry、HTTP确认后read，不重放已确认切换。
- [x] 最小迁移旧OutputPanel行内反馈到notice owner、动作到持久owner；Settings显示事实和合法控制，不能原封不动复制旧卡片/说明区。
- [x] 跑新文件、`player-output/global-notices/player-facts/wire`；Python `server/tests/api/test_system_reads.py`、`test_system_output_mutations.py`、`server/tests/invariants/test_system_read_relationships.py`、`test_system_output_relationships.py`；typecheck。
- [x] 手机H09：About事实/unknown、NAS_DAC启停结果及Player摘要一致，HTTP串流不可用；H10切页pending/异常顶部可恢复，断线只读；M01/02/04/05通过。Mock启停不当物理DAC通过。新增M03与A02局部表示亦获用户整体验收，见文末最终关闭记录。


### B10：Task9综合验收

**Files/Interfaces:** 仅必要集成证明与同一Task9 final acceptance；不扩大功能范围。

- [x] 新`web/tests/invariants/task9-relationships.test.ts::server_fixture_to_resource_action_route_convergence`：实际后端序列化资源fixture→shared decoder/cache→跨route action→ACK/read，证明Queue/Favorites/Playlist/当前背景及顶部通知关系；新`server/tests/api/test_task9_wire_fixture.py`从真实test SQLite/Services/MockPort生成同形DTO证明，不能只前端手写fixture自证。
- [x] 跑精确新增关系测试及Task9所有新invariant文件，然后`npm --prefix web run test -- --run`、typecheck、build；backend先所有本计划指定invariant/新API文件，再按实际改动与主计划需要运行`.venv/bin/python -m pytest -q server/tests`。全量不能代替前面的目标Gate。
- [x] Contract Matrix每行补实际owner/test节点/本轮结果；执行`git diff --check`、`git diff --stat`、`git status --short`并读实际diff，排除DB/dist/env/dependency/本机配置和无关重构。
- [ ] 核验当前production build与实际LAN响应/同源API/WS，再做H01/H10跨页综合：Player→Queue→Library/Search/Playlist/Favorites→Settings返回，背景/框架/通知/写权限和已发intent保持。H02–09已有通过且未触及不重复全量手机复核；未验证/受影响项明确列出，不能用自动测试代替。
- [ ] 用户必要项通过后按主Plan关闭Task9 Steps，单份final acceptance区分implementation/automated/Contract/Relationship/LAN/phone HUMAN/真实MPD NOT RUN/PWA DEFERRED，更新根README/文档地图的Task9状态。
- [ ] 如用户另行请求commit，完成检查后提交并核实`git log/show/status`；本计划不授权push/PR/merge。当前制定计划阶段不执行主Plan Step14。

当前B10自动/关系Gate完成：Web定向114/完整287，后端定向1114/完整1468，typecheck/build/Ruff/diff、独立审阅及LAN同源REST/WS通过。手机H01/H10综合PENDING；新实机范围BLOCKED/NOT RUN，详见[final acceptance](../archive/task-9/2026-10-11-task-9-final-acceptance.md)。未关闭Task9 Steps；不commit/push/PR/merge。

## 5. 自审与交接状态

- [x] 主Plan Step1–14及增量prerequisite都有Batch owner，Step12只一次且优先。
- [x] matrix→唯一Spec→拟owner→拟proof→手机卡可追溯；旧测试和新待实现proof分开。
- [x] 每个Review Focus有所属Batch测试；资源完整membership/播放集合、song/occurrence、unknown/用户Stop均显式分层。
- [x] PWA/Task10/串流/物理实机未混入Task9；没有隐式依赖安装或自动Git远程动作。
- [ ] 用户审阅Batch边界及本地交互方案；G9-01后端方案专项审核仍待完成。

本次已完成文档审计及批次划分；产品实施未开始。可供下一次授权执行的首批是B01，不能直接把B02候选接口当已批准Spec。

## B01执行状态（2026-10-10）

B01实现、自动/关系Gate及手机H01/H10和适用M项已通过；用户A02后确认“测试都可以通过”，B01当前范围已关闭。播放控件响应慢依用户意见暂缓，未修复。详见[单份验收报告](../archive/task-9/2026-10-10-task-9-b01-acceptance.md)。B02–B10未启动，G9-01仍DRAFT；未执行commit/push/PR/merge。

## B02实施补充（2026-10-10，用户授权冻结并直接执行）

PB-SONG-NOW-001 是当前唯一合同，覆盖上文 G9-01 DRAFT/候选接口的历史描述。B01已关闭；本轮核对真实代码及共享壳14项通过。沿用当前 feature/task-9-web checkout/既有 .venv，不复制未提交B01到另一个 checkout，不安装依赖，不提交。

- [x] 精确行为RED：新增 invariants/test_song_play_now.py::test_new_occurrence_preserves_pending_identity_and_joint_state，以实际API返回200、新ID和重复pending保留、joint state为断言；Expected：缺少原子入口导致HTTP405（现有路径匹配）而非import失败。
- [x] 最小实现：QueueRepository.play_song_now(song_id, playback_context_id, *, reset_played, expected_revision=None)一次revision转移；QueueManager转发；PlaybackService.play_song_now(song_id:str)负责Context/History/Stop provenance、确认/refill/账本；API additive路由返回既有DTO。Stop runtime provenance参与rollback，不改变现有Stop结果。
- [x] 同文件生命周期/故障精确节点：首次、无Context保留session、明确Stop清Played且保留pending来源、unknown不写旧History、PAUSED/same-song/disabled intent/restart、token提交屏障；命令/确认/terminal/materialization/outer commit/取消失败，固定ID和部分执行重试。Expected：逐节点通过且无本地半提交/重复控制。
- [x] 新 api/test_song_play_now.py：key必需、not-found/unavailable先于MPD、DTO、同keyreplay跨current变化、payload/path冲突、不同key新occurrence、failed intent payload变化拒绝；Expected：全部通过。
- [x] 运行原B02列明精确节点→两个新文件→指定回归文件→wire fixture→定向Ruff，Web wire test/typecheck；必要时按实际测试布局跑server/tests完整回归。Expected：全部GREEN；环境失败单列。
- [x] 自审最终本轮diff并按执行技能进行独立审阅，归档T9-SONG-001→Spec→owner→proof→fresh结果；phone N/A，真实设备NOT RUN，B03不启动。

## B02关闭记录（2026-10-10）

G9-01 / PB-SONG-NOW-001 已冻结，B02实现、自动及关系Gate CLOSED。最终代码新API/invariants36项、指定回归209项、完整后端1434项、后端wire3项/Web wire23项、typecheck及定向Ruff通过；git diff --check通过。独立审阅3个Important均已修复并精确RED→GREEN，无未关闭Critical/Important或deferred Minor。完整范围、裁决及proof见[单份B02验收报告](../archive/task-9/2026-10-10-task-9-b02-acceptance.md)。B02无独立UI，phone N/A；真实MPD/NAS/DAC NOT RUN，PWA DEFERRED。B03–B10 NOT STARTED；原审计/ B01段落中DRAFT和未启动措辞为历史状态。本轮没有commit/push/PR/merge。

## B03前置检查状态（2026-10-10）

用户授权B03，本轮已核对Specs、Git、实际owners及B01/B02前置，执行fresh前置复验。B01/B02仍CLOSED；B03产品实现NOT STARTED、Contract/传播前置BLOCKED：audit **G9-06**记录明确用户Stop的复位要求在现行Web快照中缺少可认证来源，不能从STOPPED、AutoPlay=false或空/变化session补定。等待用户选择单独冻结生命周期传播合同或修改唯一Playback Spec的复位要求；未自行扩展DTO、后端范围或复位语义。

当前B03表示/展开新proof、生产构建/LAN及手机H02/M01/M02/M04仍NOT RUN，Batch未关闭。仅有前置自动复验通过，不勾选B03实施清单，不进入B04。证据、命令及缺口见[单份B03报告](../archive/task-9/2026-10-10-task-9-b03-acceptance.md)。没有commit/push/PR/merge。

## B03继续执行补充（2026-10-10）

用户选择服务端Stop生命周期信号并授权补充合同后直接B03。G9-06合同关闭，PB-STOP-LIFECYCLE-001冻结；不使用STOPPED/session替代来源。

- [x] 前置RED：真实SQLite/Services/Mock/API `test_stop_lifecycle.py`证明counter成功Stop+1、start后保留、未知停止不递增、outer commit/rollback/terminal replay；预期真实snapshot缺counter导致断言失败。
- [x] 最小additive传播：PlaybackService runtime counter/rollback/staged playback domain、domain/public snapshot及StateService字段；Web nullable additive decoder+已知同epoch回退拒绝；无DB schema改动。更新真实public wire fixture，旧服务器缺字段未知。
- [x] B03原清单按只读范围执行，新Queue关系proof覆盖nullable counter/Context/epoch/route与metadata marker；后端补`test_realtime_snapshot.py`、`test_realtime_playback_transport.py`、`test_mutations_playback.py`、`test_idempotency.py`及wire fixture回归，定向Ruff。
- [ ] 自动/独立审阅通过后生产构建与LAN同源API/WS核验，交付H02/M01/M02/M04手机卡，必要真人反馈前保持B03未关闭。

本补充是B03必要传播前置，不授权B04动作或其它Batch；最终证据追加单份B03 acceptance。

## B03实施与自动Gate状态（T9-B03-A02）

G9-06 / PB-STOP-LIFECYCLE-001 FROZEN/CLOSED；B03只读Queue/Played及必要Stop传播实现完成，精确RED→GREEN、定向后端153/Web83、完整后端1443/Web194、Ruff/typecheck/production build通过。独立审阅无未关闭Critical/Important，1项current详情展开沿用的Minor延期；实际窄屏发现并修复Grid列最小宽度，独立聚焦复核无新问题。当前LAN `http://192.168.3.18:5175/queue`（T9-B03-A02）已核验产物字节一致、同源API/WS，phone HUMAN PENDING，B03未关闭。继续执行补充最后一项待真人反馈后勾选；只读阶段无Stop/Context UI，由agent在自有Mock验收场景分阶段切换，等待用户观察反馈。

另行记录已有Song REST带ArtworkRef时DTO序列化500，未修改批次外接口；B03保留occurrence并顶部反馈，手机场景使用无封面metadata。详见[单份B03报告](../archive/task-9/2026-10-10-task-9-b03-acceptance.md)。B04以后未推进，没有commit/push/PR/merge。


## 2026-10-11 T9-QUEUE-A03当前交付状态

PB-QUEUE-VIEW-001按用户确认冻结；B03连续列表/进入定位/下拉揭示/候选投影及必要B04 occurrence点击/待播拖动子集实现、自动Gate完成。fresh Queue25、完整Web214、指定后端135、完整后端1443通过；typecheck/build/定向Ruff及diff check通过。独立审阅两项Important已RED→GREEN并回归，排序触摸/揭示隔离proof亦通过。当前新LAN http://192.168.3.18:5176/queue（T9-QUEUE-A03）构建字节、同源API/WS及窄屏/三场景浏览器核验通过。

B03与本轮B04子集仍OPEN / HUMAN PENDING，完整B04未完成；用户第一阶段反馈后再由agent切其它必要观察场景，不提前关闭Gate。B01/B02保持CLOSED；PB-SONG-NOW-001/PB-STOP-LIFECYCLE-001服务端冻结不变。删除/清空/保存/Next/Add及其它Batch未实施；未commit/push/PR/merge。详见[同一B03 acceptance的T9-QUEUE-A03记录](../archive/task-9/2026-10-10-task-9-b03-acceptance.md)。ArtworkRef单Song500仍为批次外未修复项。

## 2026-10-11 B04剩余续作：合同裁决与最小计划

用户授权当前dirty checkout继续B04剩余范围；feature/task-9-web / HEAD14c6239已重新核验，既有修改保留。B01/B02/B03及B04点击/拖动、A04/A05维持CLOSED，旧OPEN/PENDING及“本轮不实施”仅指历史轮次。完整B04 IN PROGRESS / HUMAN PENDING。

| 冲突/共享接口 | 裁决（既有Spec/API为准） |
|---|---|
| Queue默认整行播放 vs Next/Add菜单 | 独立更多按钮；整行精确queue_item_id播放不变。Next/Add按song_id创建新MANUAL occurrence，不移动/去重旧项，不抽取B05 SongRow。 |
| “清空”可能误作Stop/全部Queue | DELETE item按queue_item_id，可作用current/Played/pending；DELETE queue只清UpNext，服务端AutoPlay补充、current删除后继/停止及History规则原样保留。 |
| 可见候选子集 vs 保存完整UpNext | POST save-as-playlist仅{name}，服务端在事务内读取提交时完整UpNext；不含current/Played、不去重、重复拒绝零半成品。HTTP确认后state及Playlist列表重读。 |
| 页面草稿 vs 跨页恢复 | 菜单/名称/确认草稿离页丢弃；已发intent交持久TaskActions，unknown原key/payload重试；confirmed/read失败只读；epoch退役、断线禁写。 |

执行清单：
- [x] 新Queue Next/Add/delete/clear独立入口行为测试RED，保存{name}/名称草稿/unknown/读失败/重复失败关系测试RED；真实Playlist DTO序列化及完整UpNext/重复/写入回滚后端proof。
- [x] 最小QueueActions + Queue局部菜单/清空确认/保存输入；共享壳/唯一通知及冻结展示/排序不变；PB-SONG-NOW-001、PB-STOP-LIFECYCLE-001不改。
- [x] 精确节点→Queue动作/保存文件→Queue表示、wire/resource-cache/mutation/player/global-notices/shell/global-artwork；后端QueueManager/save节点→文件→mutations_playback/idempotency/realtime_queue/realtime_history/playlist_relationships/realtime_playlist/stop_lifecycle/song_play_now/control_target；完整Web、typecheck/build，定向Ruff及diff检查。
- [x] 独立审阅；新的自有SQLite/Mock手机URL及版本，LAN产物/同源API/WS核验，窄屏/键盘/入口/操作收敛辅助验证。
- [x] 用户整体反馈及A02修正验收通过，完整B04关闭；不追加复测或编造逐卡日志。

G9-02未送达并发窗口保留，无expected_revision或新公开字段。ArtworkRef单Song500批次外未修复；真实MPD/NAS/DAC NOT RUN、PWA DEFERRED。不commit/push/PR/merge，不推进B05。自动、Mock、真人证据分开记录于B04 acceptance。

## 2026-10-11 B04剩余实现/自动完成，等待真人Gate

Next/Add独立入口、精确delete、仅待播clear及服务端完整UpNext save已实施；此前B01–03/已接受子集不变。本轮fresh完整Web237、指定后端关系157、新save/wire6、完整后端1446、typecheck/build/定向Ruff通过；独立审阅4个边界精确RED→GREEN并最终回归。完整B04 OPEN / HUMAN PENDING，手机URL http://192.168.3.18:5177/queue，T9-B04-A01。唯一证据及最少手机步骤见[本轮B04 acceptance](../archive/task-9/2026-10-11-task-9-b04-acceptance.md)。G9-02保留、PB-SONG-NOW/STOP及冻结展示不改，ArtworkRef批次外；真实设备NOT RUN，PWA DEFERRED，无Git整合，不推进B05。

## 2026-10-11 A01用户纠正：Queue Next/Add是移动原条目

用户接受其它B04交付，仅Next/Add新建重复项未通过。Queue快捷入口改按queue_item_id移动，完整UpNext首位/末尾含隐藏候选，不能用song-id复制；普通Song动作保持原入队语义。现有reorder只支持pending；current/Played入口边界询问中，不擅改冻结生命周期。完整B04仍OPEN，新语义须fresh测试与手机复测。实现/自动/手机记录继续追加同一[B04 acceptance](../archive/task-9/2026-10-11-task-9-b04-acceptance.md)。

### A02移动边界已确认

用户选择仅待播项提供移动入口。最小实现为move(id,next|add,title)经PUT原item，不发POST song、不改server；完整pending首位/末尾包含隐藏候选，边界no-op，原key恢复。current/Played仅删除；原availability门禁属于A01“新入队”的历史语义，移动与已接受drag一致按queue权威判断pending，metadata仅展示，不以缓存availability定义reorder。G9-02保持，不加expected_revision。精确测试已RED→GREEN，完整Gate仍待A02本轮回归及手机复测。

### A02最新交付：移动实现/自动完成，等待两项手机复测

用户已确认仅pending移动。Queue快捷移动实现已修正，原ID/总数保留、含hidden首尾、边界no-op，current/Played仅删除。fresh Web关系99/完整242、后端关系104、typecheck/build/定向Ruff通过，独立审阅无遗留问题。新URL http://192.168.3.18:5178/queue（T9-B04-A02）；Mock真实REST逐项验证position1→7且全量身份/current/Played不变。其它B04已获用户“别的都可以”反馈接受，只等两个移动入口复测，完整B04仍OPEN。完整证据见同一B04 acceptance末尾。A01复制语义不再当前合同，不改普通song Next/Add；G9-02及冻结展示/lifecycle保持。

## 2026-10-11 完整B04最终关闭：用户验收通过

用户明确“验收通过，记录一下。不需要额外的复测”。A02仅待播原occurrence移动获真人接受，结合此前其它B04范围已接受，完整B04 **CLOSED / HUMAN PASSED**；B01–03及既有子集保持CLOSED。最终Queue快捷操作是移动queue_item_id，不是song-id复制；current/Played不提供移动入口。此前OPEN/PENDING及A01复制方案保留为历史。

关闭依据见[B04 acceptance最终关闭记录](../archive/task-9/2026-10-11-task-9-b04-acceptance.md)。本轮仅同步记录，不跑额外测试、不改产品/环境/依赖/Mock场景，不编造新自动或逐场景真人证据。A02 Web242/后端关系104及A01完整后端1446均属于各自实施轮次。feature/task-9-web / HEAD14c6239重新核验，dirty保留，无commit/push/PR/merge。G9-02保留，真实设备NOT RUN、PWA DEFERRED、ArtworkRef单Song500批次外未修复；B05及其它Batch未启动，Task9整体未完成。

## 2026-10-11 B05实施/自动交付，等待手机Gate

用户授权本批次，核对当前feature/task-9-web / HEAD14c6239及dirty成果、最新B04用户关闭、唯一Specs和实际接口后执行。Library分类/详情/全歌曲、普通SongRow三个动作、服务端PlayAll/Shuffle、统一Library cache和顶部通知已接入；Queue原occurrence点击/快捷移动不改，真实Favorites及其它未来Batch未实施。fresh B05 Web11、指定关系108/完整253、后端指定86/完整1448，typecheck/build/定向Ruff通过；独立审阅唯一Important菜单遮挡顶部已浏览器RED→GREEN修正，无遗留Critical/Important。

当前实际URL http://10.104.60.177:5179/library（T9-B05-A01），空集合 http://10.104.60.177:5179/library/years/unknown；LAN产物字节/同源REST/WS及窄屏验证通过。B05 **OPEN / HUMAN PENDING**，必要H04/H05/H10/M01/M02/M04/M05待用户反馈，不推进B06。矩阵T9-SONG-001/T9-LIB-001的owner/proof/fresh结果、最少手机卡及限制见[单份B05 acceptance](../archive/task-9/2026-10-11-task-9-b05-acceptance.md)。真实设备NOT RUN，PWA DEFERRED，既有ArtworkRef REST500批次外保持；没有commit/push/PR/merge。

## 2026-10-11 B06 Search实施与交付

已核对B05最新用户关闭、feature/task-9-web / HEAD14c6239及实际前置代码；本批次查询生命周期按现行T9-SEARCH-001实施，无新业务合同决策或未关闭前置。Library入口/Search route q、空白/快速改词/清空、返回与刷新重读、Collection→有序Song、epoch/revision迟到拒绝、顶部读取恢复及共享SongRow动作完成。新proof先RED→GREEN；fresh Web4/指定关系44/完整259，后端精确search11/指定API-service+fixture36，typecheck/build/定向Ruff通过。独立审阅无Critical/Important，LAN同源REST/WS及320px窄屏预检通过。

当前手机URL http://10.104.60.177:5180/library/search（T9-B06-A01），必要H08/H04及M01/M02/M03/M04待用户反馈，**B06 OPEN / HUMAN PENDING**。最少三项手机卡、合同追溯及限制见[单份B06 acceptance](../archive/task-9/2026-10-11-task-9-b06-acceptance.md)。B01–05保持CLOSED，B07–10不推进；真实MPD/NAS/DAC NOT RUN、PWA DEFERRED，G9-02/ArtworkRef批次外限制保持。未commit/push/PR/merge，既有dirty成果保留。

### B06 A02当前交付

LIB-SEARCH-VIEW-001已冻结；归类顶部集中、全部组内内容下方连续展示实现及自动/独立审阅通过。fresh后端关系77、完整Web260、typecheck/build/Ruff/diff通过；当前LAN http://10.104.60.177:5181/library/search（T9-B06-A02），同源REST/WS和320px预检完成，手机仅复核新归类表示两项。B06 OPEN / HUMAN PENDING，B07–10不推进。完整证据见同一B06 acceptance末尾；A01的5180为历史版本。

A02最终fresh完整后端：`.venv/bin/python -m pytest -q server/tests` **1451 passed**，119.53s，仅既有Starlette/httpx弃用warning；不能替代上述77项定向Gate。最终diff check通过。


### 2026-10-11 B06 A03表示修订

用户要求顶部类型改为对应SVG图标＋名称；下方仅一个连续歌曲列表，无分类标题、无重复Song。Library §6.1 LIB-SEARCH-VIEW-001已按此反馈同步：沿服务端归类/组内顺序保留首次出现，直接歌曲追加，顶部入口定位首首歌曲（重复成员定位已有行）。仅SearchView、Search CSS与Search关系测试调整，后端API/DTO保持。旧A02跨组重复展示为历史。当前手机URL http://10.104.60.177:5182/library/search（T9-B06-A03）；fresh Search5/关系45/完整Web260、typecheck/build通过；详细证据见B06 acceptance末尾。B06 OPEN / HUMAN PENDING，B01–05保持CLOSED，B07–10未推进。


### 2026-10-11 B06 A04归类入口可进入

用户明确要求搜索命中的专辑、艺术家、标签等入口点击进入后只展示对应内容，原默认完整去重无分组列表保留。此前A03入口仅定位为历史。Library §6.1 LIB-SEARCH-VIEW-001已同步：复用既有CollectionView和分类成员API，按稳定kind/source_id跳转，原搜索词通过详情query search保留；详情“返回搜索”恢复q并重读原列表，普通Library入口返回合同保持。空归类也可进入空详情；默认搜索无PlayAll，详情沿用已存在的菜单与集合动作。后端/API/依赖及B07–10未改。

Fresh Search6、相关7文件46、完整Web23文件261（单worker，39.55s）、typecheck/build/diff通过；独立只读审阅无Critical/Important/Minor。手机当前地址 http://10.104.60.177:5183/library/search（T9-B06-A04），本轮同源LAN归类进入与返回已辅助验证，B06 OPEN / HUMAN PENDING。详细证据见B06 acceptance末尾；不关闭手机Gate，原dirty保留，无commit/push/PR/merge。


## 2026-10-11 B06最终关闭：用户验收认可

用户在T9-B06-A04交付后明确“可以验收了，更正相关必要文档。规避没必要的重复跑测试”，本轮按对当前版本的验收认可记录，**B06 CLOSED / HUMAN PASSED**。当前合同为Library §6.1 LIB-SEARCH-VIEW-001：顶部SVG图标＋归类名称，默认下方无分组且按首次出现去重；点击归类进入对应内容，返回恢复原搜索词与结果。此前“别的正常”的既有操作认可保留，必要H08/H04及M01/M02/M03/M04手机Gate按本次整体认可关闭，不编造逐项手机操作日志。

B01–B06 CLOSED，B07–B10未启动，Task9整体未完成。自动证据沿用所属轮次：A04 Search6/关系46/完整Web261、typecheck/build及独立审阅；A02后端定向77/完整1451。A03并发超时与单worker通过记录继续保留。本轮只改必要状态/入口文档并检查文档差异与diff check，没有重跑测试、构建或运行环境验证，不宣称新增自动验证结果。原dirty保留，无commit/push/PR/merge；真实MPD/NAS/DAC NOT RUN、PWA DEFERRED，G9-02与ArtworkRef批次外限制保持。


## 2026-10-11 B07 Playlist交付，等待手机Gate

本轮核对feature/task-9-web / HEAD14c6239、既有dirty前置成果及B06最终用户关闭，按T9-PLAYLIST-001现行合同实施列表/详情、CRUD、Library加歌、完整成员含不可用项、完整reorder与系统歌单保护。草稿离页/已知版本变化取消，已发intent由持久TaskActions原key恢复，HTTP/204通过同一playlists cache重读；不改公开API，不加入B08星标。G9-02未送达并发窗口继承。

Fresh Playlist9、指定Web36/完整Web270、后端精确golden1/指定关系25、typecheck/build/定向Ruff/diff通过；独立审阅唯一Important回原行松手仍提交旧目标已RED→GREEN修正并回归，无遗留Critical/Important或deferred Minor。实际LAN http://10.104.60.177:5184/library/playlists（T9-B07-A01），产物字节/同源REST/WS及320px辅助验证通过。

B07 **OPEN / HUMAN PENDING**，必要H06/H04/H10及M01/M02/M03/M05等待反馈；B01–06保持CLOSED，B08–10不推进。范围/合同追溯、命令及最少四项手机卡见[单份B07 acceptance](../archive/task-9/2026-10-11-task-9-b07-acceptance.md)。现有.venv未改，无依赖/DB schema/生产后端改动，无commit/push/PR/merge。真实MPD/NAS/DAC NOT RUN，PWA DEFERRED；ArtworkRef单Song500批次外保持。


## 2026-10-11 B07最终关闭：用户验收通过

用户在T9-B07-A01交付后明确“验收通过。更正相关文档。不需要额外测试。”；B07 **CLOSED / HUMAN PASSED**，必要H06/H04/H10及M01/M02/M03/M05手机Gate按本次整体认可关闭，不编造逐项操作日志。B01–B07保持CLOSED，B08–B10未启动，Task9整体未完成。关闭依据见[单份B07 acceptance最终关闭记录](../archive/task-9/2026-10-11-task-9-b07-acceptance.md)。

本轮只更新必要验收状态/入口并检查文档差异及diff check；没有重跑测试、构建、环境或LAN验证。B07 Playlist9/指定Web36/完整Web270、指定后端25及独立审阅/LAN证据保留实施轮次归属。feature/task-9-web / HEAD14c6239重新核对，原dirty保留；产品/测试/依赖/Mock及运行文件不改，无commit/push/PR/merge。G9-02、真实MPD/NAS/DAC NOT RUN、PWA DEFERRED及ArtworkRef批次外限制保持。


## 2026-10-11 B08当前交付

LIB-FAV-UI-001（用户爱心设计）/LIB-FAV-MEMBERS-001（获准最小只读完整成员接口）冻结并实施；复用同一cache/TaskActions/通知，完整不可用成员、服务端顺序、全位置爱心和单曲菜单接线完成。Fresh Favorites9、指定Web124/完整279，最后低影响占位显示补充定向26；后端指定23、typecheck/build/Ruff/diff通过。独立审阅/自查问题均精确RED→GREEN修复，无遗留finding。LAN http://10.104.60.177:5185/（T9-B08-A01）最终产物字节/同源REST/WS及窄屏预检通过。

B08 **OPEN / HUMAN PENDING**，仅等H07/H04/H10、M01/02/05手机反馈；B09/B10不推进。各轮结果、最少操作及限制见[B08 acceptance](../archive/task-9/2026-10-11-task-9-b08-acceptance.md)。现有dirty和.venv保留，无commit/push/PR/merge，无依赖/DB模型变更；真实设备NOT RUN、PWA DEFERRED、ArtworkRef REST500批次外保持。


### 2026-10-11 B08 A02展示修正（用户反馈优先）

Player爱心保持艺术家同行，向左8px/向上3px微调，SVG从22px放大到26px；未收藏明确使用--text-primary描边，已收藏仍用--accent。所有单曲菜单收藏/取消收藏仅纯文字，不显示爱心、不使用蓝色，字体颜色/对齐沿用其它菜单项；按用户最新反馈，Queue单曲菜单与Library共用样式：无按钮边框、文字左对齐、相同尺寸/间距/歌曲信息排版；清空和保存弹窗保持原样。其它位置已收藏展示爱心及所有状态/写权限/请求/恢复功能不改。只复验这两类展示，不重开已认可功能；B08手机Gate仍待本轮反馈。

A02最终fresh定向4文件58通过、typecheck/build、LAN产物字节/REST/WS和实际DOM样式比对通过。当前地址http://10.104.60.177:5185/（T9-B08-A02），手机最少复核Player爱心、Queue与Library菜单一致两项；B08仍OPEN/HUMAN PENDING，原轮次结果见同份acceptance。


## 2026-10-11 B08最终关闭：用户验收通过

用户在T9-B08-A02整改交付后明确：“验收通过。无需重复测试。更正需要的文档即可”。据此将B08记为 **CLOSED / HUMAN PASSED**，必要H07/H04/H10及M01/M02/M05手机Gate按本次整体验收认可关闭，不编造逐项手机操作日志。现行实现包含Player空心/实心爱心与位置修正、其它位置仅已收藏展示、菜单纯文字、Queue单曲菜单与Library共享样式，以及获准的最小只读完整收藏成员接口。

自动证据沿用所属轮次：A01指定Web124/完整279、后端指定23；A02展示整改定向58、typecheck/build、产物字节/REST/WS与辅助DOM核对。此次仅更新必要文档并检查文档差异及diff check，未重跑测试、构建或运行环境验证，不宣称新增自动证据。

B01–B08 CLOSED，B09/B10未启动，Task9整体未完成。真实MPD/NAS/DAC NOT RUN、PWA DEFERRED、G9-02及既有ArtworkRef REST500批次外限制保持。原dirty成果保留，无commit/push/PR/merge。关闭依据见[B08 acceptance最终关闭记录](../archive/task-9/2026-10-11-task-9-b08-acceptance.md)。此前OPEN/PENDING保留历史。

## 2026-10-11 B09执行输入与有限扩展

B01–B08最新用户Gate已关闭；feature/task-9-web / HEAD14c6239及dirty实际前置已核对。用户补充优先：标签条扩展播放列表/收藏且成为唯一列表入口；MPD地址保存后服务重启生效。SYS-MPD-CONNECTION-001已按用户选项冻结，允许独立最小接入配置owner/API，不引入通用Task10模块。旧“无Task10控件”对本获准host/port例外调整，其它范围不变。B09 IN PROGRESS，B10不推进。

| Contract | P/A/Δ/U/X/H/T/F/R/O/E |
|---|---|
| T9-SETTINGS-001 | 继承audit D0及Output §6/About §7；About与canonical Output独立；持久output action复用TaskActions；confirmed不取last_request；错误顶部；settings/player-output及指定四份PythonGate |
| T9-MPD-CONNECTION-001 | SYS-MPD-CONNECTION-001；writable及合法host/port；文件owner；Δ仅saved文件；U当前Player/播放/Queue/History/Output/epoch；X原子落盘；H无History；T文件原子替换、非SQLite事务；F保留旧文件；R原key/target重试与确认后GET；O顶部重启说明/typed error；E文件→startup/API与Settings关系测试 |
| T9-LIB-NAV-001 | 本轮Visual补充；Δ本地route/选中标签；U领域/cache/动作/共享壳；无外部/事务/History；沿用读取失败恢复；settings导航及Library/Playlist/Favorites回归 |

清单：
- [x] 新Settings/About/跨页Output恢复及标签入口行为RED→GREEN；真实MPDInfo序列化golden。
- [x] 接入设置API/文件/启动优先级与失败、Web保存/重读/重启事实分离RED→GREEN。
- [x] 新文件→指定Web与Python关系Gate；完整Web/typecheck/build、定向Ruff/diff；独立审阅。
- [x] 新Mock/LAN产物/REST/WS及窄屏预检；交付H09/H10、M01/02/03/04/05最少手机操作；A01及A02已获用户验收，B09 CLOSED / HUMAN PASSED。


## 2026-10-11 B09当前交付：实现/自动完成，等待手机Gate

Settings About/NAS_DAC及持久顶部恢复、音乐库播放列表/收藏唯一标签入口、用户选择的MPD地址保存后重启生效完成。SYS-MPD-CONNECTION-001已冻结，最小文件/API例外不授权其它Task10功能。fresh指定Web103/完整284、指定后端57/完整1466，新配置文件13（最终排版后）、typecheck/build/定向Ruff/diff通过；独立审阅两项Important已RED→GREEN，当前无遗留finding。

新LAN http://10.104.60.177:5186/settings（T9-B09-A01），同源产物字节/REST/WS及320px预检通过。B09 **OPEN / HUMAN PENDING**，H09/H10、新增入口及M01/02/03/04/05待用户反馈；B01–B08保持CLOSED，B10不推进。完整范围/合同追溯/最少手机步骤见[B09 acceptance](../archive/task-9/2026-10-11-task-9-b09-acceptance.md)。真实设备NOT RUN、PWA DEFERRED、G9-02/ArtworkRef批次外限制保持，原dirty/.venv保留，无commit/push/PR/merge。


### 2026-10-11 B09 A02用户反馈输入

用户“A01测试项没问题”接受原功能验证；本轮仅标签顺序、DAC同行开关、地址同行固定宽度及IPv6组合表示修订。用户澄清仍是MPD域名/IP+端口，不使用HTTP前缀，后端原生TCP合同不扩展。真实设置页重启入口登记主Plan Task11待办，不在B09加入假实现；SYS-MPD-CONNECTION-001仍为保存后重启生效。原A01已接受范围不重复要求真人复测；本轮新表示手机Gate仍OPEN，不推进B10。

A02步骤：新开关canonical/显式enabled关系及标签顺序RED→GREEN；IPv6组合表示RED→GREEN、后端保存/读取/下次启动IPv6定向proof；设置/输出文件与受影响关系回归、typecheck/build；LAN同源和320px固定宽度/开关同行辅助验证；手机仅复核本轮布局/开关手感。


### B09 A02最新交付：等待局部手机复核

用户认可A01测试；A02标签艺术家→收藏→播放列表、DAC同行confirmed开关、同行固定宽地址输入已交付。用户澄清MPD原生TCP无HTTP前缀；IPv6裸host保存/读取/启动及组合[IPv6]:port补充验证通过。真实restart按钮及监管后端登记Task11，本批次不实施。

Fresh设置/输出16、指定Web105/完整286、IPv6 API精确1/配置文件14，typecheck/build/Ruff/diff及聚焦独立审阅通过；LAN同源产物/REST/WS、320px长地址与五位端口固定尺寸、开关同行及标签选择核验通过。地址仍 http://10.104.60.177:5186/settings，title T9-B09-A02。B09 OPEN / HUMAN PENDING，只复核新增三类表示，原A01已认可功能不重复要求；B10未推进。证据追加同一B09 acceptance；真实设备/IPv6连通NOT RUN、PWA DEFERRED，既有批次外限制不改，无Git整合。


## 2026-10-11 B09最终关闭：CLOSED / HUMAN PASSED

用户最终反馈：“验收通过。无需重复测试。记录更正需要的文档。”结合此前“A01测试项没问题”，接受B09原功能及A02标签顺序、DAC同行开关、同行地址输入与IPv6组合表示。H09/H10、M01/M02/M03/M04/M05及A02局部手机Gate按用户整体验收关闭，不编造逐项操作日志。

自动验证及LAN证据沿用[B09验收记录](../archive/task-9/2026-10-11-task-9-b09-acceptance.md)的A01、A02所属轮次；本次仅更新必要文档并检查文档差异，未重复测试、构建、环境或网络验证，不新增自动证据。B01–B09 **CLOSED / HUMAN PASSED**；B10未启动，Task9整体未完成。此前OPEN/PENDING为历史状态，以本次最终关闭为准。

真实MPD/NAS/DAC及IPv6网络连通仍NOT RUN，PWA DEFERRED；设置页真实立即重启入口及监管后端仍为Task11待办，G9-02与既有ArtworkRef单Song REST500批次外限制保持。未改产品代码，无commit/push/PR/merge。


## 2026-10-11 B10：综合自动交付，手机与实机Gate待关闭

本批次只增加真实SQLite/Services/MockPort四阶段golden及跨route action/cache/ACK-read综合proof，未改产品功能或合同。负向校验能捕获缺少snapshot refresh，原文件按字节恢复后GREEN。fresh Web新1/指定114/完整287、后端新1/指定1114/完整1468、typecheck/build/Ruff/diff及独立审阅通过。非空ArtworkRef后端综合链未证明，既有单Song500继续单列，不吞作通过。

本机production产物字节及两个origin REST/WS核验通过：Mock综合http://10.104.60.177:5187/；真实MPDAdapter地址入口http://10.104.60.177:5188/settings，无Mock/虚构能力、独立DB。历史NAS192.168.3.94:6600本轮TCP超时；等待用户保存当前实机地址及提供只读音乐根/URI映射。保存仅下次启动生效，由agent重启自有live服务；不实现Task11按钮或Task10通用配置。完整矩阵、独立审阅Minor边界、各轮命令及手机/实机方案见[单份final acceptance](../archive/task-9/2026-10-11-task-9-final-acceptance.md)。

B01–09保持CLOSED；B10 OPEN/HUMAN PENDING，实机功能Gate BLOCKED/NOT RUN，Task9整体未完成。PWA DEFERRED、G9-02限制保留；现有dirty/.venv/DB保留，无Git整合。此前B10未启动段落保留为历史，不作为当前状态。


### B10 A02：用户独立IPv6实机验收

用户只能在启用IPv6后访问MPD，届时Codex不可用；agent事先准备/启动，用户独立测试后恢复网络反馈，不能要求agent实时设备验证。远程NAS音乐仅MPD可读尚不足以建立本机Web音乐库；当前LibraryScanner需后端可读文件根，MPDAdapter不提供曲库导入/根映射。等待IPv6 endpoint及NAS部署/只读挂载/有限连接先行的选择，不扩展合同。LIVE入口5188已独立启动、配置GET200，仍未配置实机，不记设备通过。详情见[同一final acceptance A02](../archive/task-9/2026-10-11-task-9-final-acceptance.md)。本轮仅启动核验/文档同步，无重复suite或Git整合。
