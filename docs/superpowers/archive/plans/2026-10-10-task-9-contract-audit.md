# Task 9 Contract Audit

> 2026-10-11最终交付增量：此audit保留Task9领域合同和历史验收；新活动展示按Visual §6，旧成功撤下的证明仅属旧版本。后续配置/同步/AppBar/部署执行入口为[Final Batch Plan](2026-10-11-v0-1-nas-final-batch-plan.md)，不在本audit新增第二份矩阵。

当前进度（2026-10-11 B10交付）：B01–B09 **CLOSED / HUMAN PASSED**；B10综合proof、自动Gate与production/LAN预检完成，**OPEN / HUMAN PENDING**；用户新增实机各功能Gate因当前endpoint/音乐映射待提供及历史NAS TCP超时，**BLOCKED / NOT RUN**。Task9整体未完成。当前范围/矩阵/证据/最少手机及实机步骤见[单份final acceptance](../task-9/2026-10-11-task-9-final-acceptance.md)。历史OPEN/PENDING不重开已关闭前置。

## 2026-10-11 B03历史Gate：用户验收通过

用户明确“可以了。验收通过”，当前B03展示/交互及已实施B04 occurrence点击/待播拖动子集、A04播放/手感及A05临时通知修正验收通过。**B03 CLOSED；B04已实施子集 CLOSED；完整B04剩余Next/Add、删除/清空/保存 NOT STARTED。** B01/B02保持CLOSED。此前OPEN/PENDING段落保留为历史，不再作为当前前置阻塞。

关闭依据与限制见同一[B03 acceptance最终关闭记录](../task-9/2026-10-10-task-9-b03-acceptance.md)。本轮仅更新验收状态和提供后续提示词，不开始B04剩余工作；不重做已接受行为，不扩大未来Batch，不commit/push/PR/merge，保留dirty checkout。真实MPD/NAS/DAC仍NOT RUN，PWA DEFERRED，ArtworkRef单Song500仍为批次外未修复项。


## 2026-10-11 A05：通知生命周期限定修正

用户确认A04播放/拖动无其他问题，要求保持已通过行为，只修正顶部图标被成功拖动记录占据的问题。旧Visual“已完成结果图标”与当前诉求冲突；按WEB-UI-NOTIFY-001同步为当前事项入口：进行中临时spinner，无恢复按钮；已确认且状态/资源同步成功撤下；未解决失败/unknown/确认后read失败保留原key及既有恢复，不吞并发异常。成功通知不因切页/epoch复活，不自行设定“长久”秒数，不改变Queue操作/播放/服务端领域。AppShell投影与taskActions成功记录epoch处理为最小代码范围，internal intent/key保留既有防重复与互斥语义；不新建日志UI。

## 2026-10-11 A04：真人反馈修正输入

用户报告 A03 手机播放卡第五秒、暂停再播归零，以及长按排序不灵敏。检查自有验收启动脚本发现 `advance_clock=False`，Mock样本位置不前进；前端有效样本租期届满正确停止外推。修正自有fixture为真实单调时钟，保留PlayerClock租期、实际/业务分离及冻结服务端合同，不能通过无限外推掩盖验收错误。播放时钟loop和已有fixture pause/resume测试负责验证。

Queue手柄原350ms、移动8px取消及移动时重排DOM导致漂移取消与不稳定落点。B03/B04子集内改为230ms容忍漂移、跟指浮层、稳定行/插入标记、边缘滚动；失效/取消/释放时重新hit-test，不保留无效旧目标。仅待播排序、精确occurrence、共享事务/幂等/断线合同均不变。同步Visual及Batch/原acceptance；不推进其他Batch。A03自动证据保留为历史，用户本次反馈意味着真人Gate仍OPEN，不能据旧通过关闭。

## 2026-10-11 Queue修订输入（优先于旧B03表示方案；边界已确认）

用户授权在当前dirty checkout修订B03并实施必要B04点击播放/拖动子集。B01/B02保持CLOSED，B03手机Gate仍OPEN；不得据此前1443/194通过关闭新修订Gate。PB-SONG-NOW-001、PB-STOP-LIFECYCLE-001服务端合同冻结不变。

已核对冲突：

| 当前合同/实现 | 本轮已授权修订 |
|---|---|
| Playback §5.1、Visual导航表、QueueView三个分区标题 | 连续歌曲列表，不显示Now Playing/Played/Up Next标题 |
| Playback §3.3.1 downstream / §3.3.2 consumer、audit §5、queueUi：每次+10，切页保留 | 每次进入Queue隐藏Played并定位current；从current向下拉内容，先揭示最近Played，再揭示更早Played；离页返回重新隐藏 |
| Playback §6.2、deriveQueue.next：全部AutoPlay可见 | 单曲且AutoPlay启用时只预览最先候选；隐藏其余仅为本地展示，不改Queue或补充策略 |
| Playback §3.1–3.2统一菜单、Visual密集行详情、QueueOccurrence details | Queue独立点击合同：current/Played/pending/AutoPlay均直接按queue_item_id播放，不打开详情或先弹菜单；标题/艺术家各单行省略 |
| position0圆点/文字标签 | 仅fresh、匹配绑定、已确认playing/paused的current在标题前显示明确播放/暂停图标；unknown/stale/unbound不显示这类确认图标 |

用户已确认三个实施边界：仅待播可排序，多曲隐藏全部AutoPlay，留页自动切歌保留滚动与已揭示历史；以下问题列表为修订前的历史输入：current/Played是否可排序（旧B04仅pending）；多曲场景是否显示全部AutoPlay；留在Queue期间自动切歌是否重新隐藏并定位。本轮已按用户答案同步Playback §5 PB-QUEUE-VIEW-001，合同FROZEN。已有Context/epoch/明确Stop reset仍继承，服务端计数传播与事务/replay不改。

T9-QUEUE-001将覆盖本地可见投影、进入复位/下拉揭示、候选预览、确认图标；T9-QUEUE-002本轮仅覆盖精确occurrence点击和已确认范围内drag，继承G9-02未送达并发窗口限制。T9-SAVE-001及删除/清空/Next/Add不属本轮实施。

实际前置：分支feature/task-9-web，HEAD14c6239；根目录无AGENTS.md，读取AGENTS.override.md（与用户提供本地规则一致）。现有queue-view5项fresh通过，仅证明旧合同基线；Python3.14.4/pytest9.1.1/ruff0.16.9可用，requirements已读，未改环境。

日期：2026-10-10（Asia/Shanghai）。原始范围：按真实 main 审计 Task 9 文档、接口、Web 实现和测试，形成增量合同矩阵及 Batch 输入。

当前合同更新：G9-01 已按用户批准冻结为 Playback Spec §3.3.1 PB-SONG-NOW-001（含不可用 pending 整次拒绝边界）；原始审计结论保留时态，当前B02验证/关闭记录见文末及单份B02 acceptance。

## 1. 基线与结论

- 审计开始工作区干净，当前分支 `main`；HEAD、local main、已存在的 `origin/main` 均为 `14c6239283f4fed079f07ab817964b23e87e793c`。未 fetch；这证明本机三者一致，不宣称服务器此刻无更新。
- Task 8 手机 Web 前置成立：实际 Player/shared client 代码与测试存在；[W6 acceptance 最新关闭及合并核验](../task-8/2026-10-10-task-8-web-w6-acceptance.md)记录必要手机 HUMAN PASSED。本轮未重跑手机验收。
- Task 9 产品实现尚未开始。`web/src/router/index.ts:3` 只有 Player 与 fallback；不存在 Queue/Library/Playlist/Search/Settings views、通用 SongRow 或 Favorites UI。
- 可以先实施共享 UI 基础。依赖普通歌曲 Play Now 的内容必须等待独立后端 prerequisite；不能用 Start Track 或两次请求拼接实现。
- **审计及 Batch 拆分已形成；整个 Task 9 的业务合同关闭和实施验收尚未完成。** G9-01 后端新增合同仍待审核；其余本地交互方案见 §5，不作为长期 Spec 的替代。
- PWA DEFERRED，真实 MPD/NAS/DAC NOT RUN；Task 10 配置/备份/日志及 CLIENT_STREAM 不在范围内。

## 2. 权威与文档时态

| 来源 | 本次用途 |
|---|---|
| [主 Plan Task 9](2026-09-25-mpd-server-v0-1-implementation-plan.md#task-9web-queuelibraryplaylistsearchfavoritessettings) | Scope、依赖、原 Steps；Step12 前移且仅实施一次 |
| [Visual Spec](../../specs/2026-10-03-web-pwa-visual-design.md) WEB-UI-* / §8–9 | 唯一 UI 合同；共享壳→通知→背景→四项导航，保护 Player |
| [Architecture](../../specs/2026-09-25-system-and-development-architecture-design.md) §4.1–4.3 / §12 / §19.5 | canonical/cache/UI 三层、只读门禁、key/replay、完整矩阵与关系测试 |
| [Playback](../../specs/2026-09-24-playback-model-queue-semantics-design.md) §3–5 / §8.9 | Song/occurrence 动作、Queue 分区、保存范围、确认/History/部分执行 |
| [Library](../../specs/2026-09-24-library-playlist-tag-search-design-2-1.md) §4–7 | collection 与 membership、收藏/搜索、revision |
| [手机方法](2026-10-09-mobile-web-manual-acceptance.md) | M01–M07、T9-H01–H10；真人交付与每 Batch 关闭条件 |

Visual Spec §2/§8、旧 audit 及 W5/W6 acceptance 前段保留修订当时 dirty/HUMAN PENDING 描述。不能据这些历史段落重开已关闭 Task8；最新 W6 关闭记录、main 实际文件和本轮验证才是当前状态证据。反之，新共享壳/背景/导航从未被 Task8 验收，不得用旧通过抵扣。

## 3. 实际可复用基础及缺口

| 实际文件/入口 | 已存在 | Task 9 差距及 owner |
|---|---|---|
| `web/src/App.vue:8`、`components/layout/AppShell.vue:7` | app 级 store/api/realtime、单 start/stop 生命周期及 injection | Shell 只有 slot；持久 bar/背景/nav 不存在，B01接入 |
| `views/PlayerView.vue:15`、`:33` | Player actions、clock、presentation；通知已包含 connection/selection/read/file/artwork/lyrics | actions/watchers 及通知仍是页面 owner；unmount dispose，跨页恢复上下文需提升到持久 owner；不重写冻结歌词 |
| `components/player/PlaybackStatus.vue:40` | 顶部中心入口/详情、原key retry/read | 32px 点击区低于 Visual 44px 要求；不是新共享壳已完成证据 |
| `components/player/ArtworkStage.vue:17` | 同源 artwork、generation/abort、object URL 回收及旧资源拒绝 | page-local 请求/DOM load；无跨页共享 decoded 背景；B01须共用资源并证明不重复读取 |
| `components/player/OutputPanel.vue:25`、`:78` | NAS_DAC confirmed/request 分离，REST alias decoder | Player 已不引用；不可原样粘到设置：unmount retire、行内通知、厚卡片须按唯一 UI 合同接入，B09负责 |
| `services/api.ts:42` | `createIntent(method,path,payload)`、`send(intent,decode)`、`get(path,decode)` | 这是共享 key/transport，不是现成跨页 action registry；B01增加 intent 恢复 owner，不造第二套 key |
| `stores/player.ts`、`services/realtime.ts` | accepted snapshot、marker、writable 门禁 | 所有新动作消费同一实例；route/resource GET 不能恢复写权限 |
| `stores/resourceCache.ts:5` | `read(key)`、`entry(key)`、`invalidate(marker,{force?})` | 无 fresh epoch baseline 不读；generation/revision迟到保护可复用，不另造缓存 |
| `stores/library.ts:6`、`stores/playlists.ts:6` | typed decoder 注入、marker watch、`stop()` | 目前只是泛型薄包装；新增 DTO decoder、路径装配及主动读取义务由新页面负责 |
| `types/api.ts`、`services/wire.ts` | realtime/Song/Output DTO/decoder | Collection/Playlist/list/MPDInfo typed decoder 尚需新增并用真实后端序列化样本证明 |

实际接口清单：

| 领域 | main 可用 REST（除注明外均已有） | 注意 |
|---|---|---|
| Queue | GET `/api/state`；POST `/api/playback/queue/items/{id}/play`；PUT `/api/playback/queue/items/{id}` `{before_queue_item_id}`；DELETE 同项；DELETE `/api/playback/queue` | snapshot 含 revision，独立 GET queue 不含 revision；全部按 occurrence id 操作 |
| Song | POST `/api/playback/songs/{id}/play-next`、`/queue` | 普通 song-id Play Now **缺失**；`/tracks/{id}/play` 替换 Queue，不能代用 |
| Collection | POST `/api/library/collections`、POST `/api/playback/collections/play` | collection build 是只读例外；执行集合播放由服务端解析/排序/随机，不提交浏览器猜造成员 |
| Library | GET `/api/library/songs`、`/songs/{id}`、`/albums`、`/artists`、`/genres`、`/years`、`/tags` 及对应 `/{id}/songs` | 分类歌曲入口过滤 unavailable；不能宣称它返回完整原始 membership |
| Search | GET `/api/library/search?q=...` | 返回 Collection；不是 SongList，不把 song_ids 当完整 Song |
| Playlist | GET/POST `/api/playlists`；GET/PATCH/DELETE `/api/playlists/{id}`；GET/POST `/{id}/songs`；DELETE `/{id}/songs/{song_id}`；PUT `/{id}/songs/order` | PlaylistResponse 含完整 song_ids；songs GET 保留 unavailable；完整 reorder 成员不匹配为409 |
| Favorites | GET `/api/favorites`；PUT/DELETE `/api/favorites/{song_id}` | GET是可播放 Collection，另有 unavailable_song_ids；完整星标 membership 应用系统 Playlist 的完整 song_ids，不能只读 playable ids |
| 保存 Queue | POST `/api/playback/queue/save-as-playlist` `{name}` | 提交时读取最新 Up Next；重复 song_id 400拒绝，事务不残留半个 Playlist；不静默去重 |
| Settings | GET `/api/system/mpd`、GET/PUT `/api/system/output` | MPDInfo 与 Output 单独 DTO，嵌套 camelCase REST 和 snake_case realtime 不混用 |

证据 owner：`server/app/api/{library,playlists,playback,system}.py`、`api/schemas.py:268`、`services/{collection_service,library_service,playlist_service,queue_manager,playback_service}.py`。`main.py:178`统一 mutation key middleware；collection build 明确 exempt。新增公开字段/路径不能仅由前端定义。后端精确行证据及现有测试节点见[后端研究输入](2026-10-10-task-9-backend-research.md)，它不另拥有合同或Batch状态。

## 4. 增量发现与影响

### G9-01 / BLOCKER：普通歌曲 Play Now

`PlaybackService.play_now(queue_item_id)`（`playback_service.py:495`）选择现有 occurrence；`start_track`替换 Queue；song Play Next/Add只入队。因此“入队→Queue Play Now”不是原子 song 动作，可能留下中间项/通知、被其他客户端穿插且不能满足一次意图的 key/terminal/rollback。

用户在本轮选择“采用建议，写入待审核方案”：

- 正常 PLAYING/PAUSED、已有有效 Context 时，保留 Context 和 Played，新 MANUAL occurrence 成为 current；原 Up Next（含同 song 重复项）及相对顺序保留。
- 明确用户 Stop 后，新单曲 Context、新 History session，清除旧 Played、保留原 Up Next，并启用 AutoPlay。
- 以上是**待审核方案，不是已冻结后端合同**。首次无会话、业务 STOPPED 与 unknown external STOPPED、无有效 Context、保留项 context_id 的归属、原 current 的移动、Queue revision/AutoPlay refill、terminal DTO 和部分执行 retry 必须在唯一 Playback Spec 中补齐并确认。未知外部停止不能由客户端推断为用户 Stop。
- History继承PB-HISTORY既有规则：正常已确认切换沿用session；明确Stop清session，随后开始生成新session；未知外部切歌丢弃不可信active但保留session，不作为新产品选择重开。
- 推荐 additive `POST /api/playback/songs/{song_id}/play`，由 `PlaybackService.play_song_now(song_id: str)`编排，返回新 QueueItemResponse；这是候选接口。B02 的接口/测试以审核后的 Spec 为准，当前不得据此写生产代码。

B01纯壳不受此 blocker；B05普通歌曲完整菜单依赖 B02。

### G9-02 / KNOWN LIMIT：拖动并发

`QueueReorderRequest`无 expected_revision（`schemas.py:268`）；Service虽然支持参数，API未传入。Playlist reorder只有完整ordered_song_ids，无版本条件。**内部CAS不证明浏览器所见版本被守护**。

建议保持现有 API：本地草稿捕获epoch/generation/Queue revision或Playlist revision及完整成员；已收到变更、current转移、断线、路由离开立即取消，重新读取后由用户重新拖动；提交后服务端以执行时权威状态裁决。无法消除“尚未送达浏览器的并发变化”；计划不承诺严格 expected-version。若要求严格防过时覆盖，应先批准 additive API/Spec，再调整 B04/B07，不能暗加字段。

### G9-03 / INHERIT：保存重复与预览

`QueueManager.save_as_playlist`（`queue_manager.py:268`）读最新 Up Next，重复song拒绝。继承拒绝，顶部显示原因；name草稿可保留，本地预览不当提交快照。不新增包含Played、去重选项、client song_ids或expected revision。

### G9-04 / INHERIT：membership 不等于可播放集合

Collection分离song_ids/unavailable_song_ids；分类/song search目前只返回可用歌曲；Playlist songs保留不可用。Favorites星标必须基于完整系统Playlist membership，包括不可用项。收藏请求失败不能先提交星标；pending可立即显示但confirmed必须等待HTTP+authoritative read。Playlist duplicate rejection/系统playlist禁止改名删除沿用已有合同，不重开产品决策。

### G9-05 / INHERIT：通知与跨页操作

Player通知迁移在W6已完成其页面范围，但不是持久shell通知完成。B01保留原action/key/retry owner；B09将Output行内反馈迁入同一中心，保留confirmed输出事实。多个操作/资源异常以稳定id并存，不以“最后一条消息”吞掉之前未解决错误。

## 5. 本地交互方案（供 Batch 审阅，不新增领域权威）

- 路径：`/` Player、`/queue`、`/library`、`/settings`；Library内 `/library/:kind/:id`（kind仅albums/artists/genres/years/tags）、`/library/search`、`/library/playlists`、`/library/playlists/:id`、`/library/favorites`。参数URL编码；静态子路径优先，非法路径回到`/`。Library所有子路径的顶级选中仍为音乐库。
- Queue按Playback §5 PB-QUEUE-VIEW-001：每次进入隐藏Played并定位current；下拉从最近Played逐步向更早揭示，连续列表按position升序；留页普通/自动切歌不强制定位，保留已揭示历史与滚动。accepted Context/epoch或明确Stop counter增加仍归零，unknown STOPPED不冒认Stop，不拼永久History。
- 本地搜索q保留在route query，刷新/返回重读该查询；空白q为空结果且不触发播放。请求generation与当前query双重拒绝迟到结果；搜索不新增全结果播放入口。
- Playlist名称草稿离开route丢弃；拖动草稿离开route取消；确认发送的intent与结果未知恢复上下文仍由持久shell owner保留，切页不补发请求。epoch变化退役旧恢复动作，保留不确定记录供读取，不用旧key创建新epoch业务。
- 普通SongRow三个菜单操作一致；Queue例外点击直接Play Now按queue_item_id，不先弹菜单/详情；普通song按song_id。Play Next/Add to Queue沿用song-id接口，创建新occurrence，未来如提供Queue额外菜单须另行实现；本轮不接入Next/Add。移动已有pending行属于拖动reorder。若需要另一个“移为下一首”快捷动作，应先明确命名/合同，当前计划不暗加。FavoriteStar独立点击不播放；本地确认态不做speculative commit。

## 6. Contract Matrix（REQUIRED）

以下共同字段D0 + 各行增量合成完整合同；不是长期Spec副本。字段缩写：P前置、A权威、Δ状态变化、U不变、X外部确认、H历史/事件、T事务、F失败、R重试、O可见结果、E证明。所有拟新增测试文件在当前main均**未实现/未运行**。

**D0（每行适用）**：P当前连接完整baseline，写动作另需writable；A后端Services/Repositories/MPD拥有业务，snapshot/cache只表达；Δ仅操作定义域；U音乐文件、其他资源及未授权业务不变；X播放/输出成功按既有PlayerPort确认，UI/资源GET不发控制；H沿用领域事件，读取不产History；T服务端最外层事务及revision/terminal提交，UI草稿与通知无DB事务；F无optimistic canonical/cache，保留最后事实、typed error、重读；R同intent/key/payload传输重试，HTTP确认后只读，不自动补发；O唯一顶部结果/恢复，禁用/availability原位；E真实DTO→client→action/view关系测试，配对应历史回归。

| ID / Type / Operation | P / A | Δ / U | X / H / T | F / R / O | E / Batch |
|---|---|---|---|---|---|
| T9-SHELL-001 / UI relationship / 跨页共享壳通知 | D0；唯一AppShell/API/store | 仅route/local UI；连接、confirmed事实不变 | 无控制；切页无History或mutation；持久runtime | pending/unknown跨页可恢复；不自动retry；唯一bar/detail/nav | `shell-navigation.test.ts`、`global-notices.test.ts`；B01，WEB-UI-SHELL/NAV/NOTIFY |
| T9-BG-001 / representation / 共享背景 | confirmed实际身份及library资源代次 | decoded资源替换；不改layout/播放 | GET artwork+decode成功；handoff不是新确认；无事件/事务 | 404/default、失败顶部、旧解码拒绝、路由不重读 | `global-artwork.test.ts`；B01，WEB-UI-BG/BASE/STYLE |
| T9-SONG-001 / cross-authority / song Play Now | PB-SONG-NOW-001；PlaybackService唯一编排 | 新occurrence与已冻结生命周期；UpNext相对序保留 | MPD occurrence/state确认；History/revision/terminal联合提交 | 部分执行按PB-RECOVERY；同key不重复项；HTTP ACK不装配canonical | `test_song_play_now.py`（API/invariants）、`song-actions.test.ts`；B02/B05；PB-SONG-NOW-001 FROZEN |
| T9-QUEUE-001 / representation / 连续列表/可见投影 | canonical完整Queue + metadata | 进入隐藏Played/定位current，下拉最近→更早；单曲首AutoPlay/多曲隐藏；不删Queue/History | 仅fresh匹配的confirmed current图标；留页切歌保留滚动/已揭示历史 | metadata失败不丢occurrence；旧生命周期reset继承；只读可揭示 | `queue-view.test.ts`；B03修订，PB-QUEUE-VIEW-001 |
| T9-QUEUE-002 / mutation / 移动/播放/删/清空 | writable、精确item id；drag为pending项 | 仅既有动作delta，手动操作source按服务端；不猜current | PlaybackService确认；现有联合事务/History | 取消已知过期draft；typed conflict重读；原keyretry | `queue-actions.test.ts`；B04点击/待播drag子集已关闭；剩余Next/Add/delete/clear已实施，完整真人Gate待反馈，G9-02限制明确 |
| T9-SAVE-001 / transaction / UpNext保存 | name合法、服务端执行时UpNext | 新Playlist/revision；Queue/Playback/History不变 | 无MPD动作；Playlist提交后事件 | 重复400、无半成品；不自动去重；HTTP回执+列表重读 | `queue-save.test.ts`及现有playlist invariant；B04 |
| T9-LIB-001 / resource/action / collection列表/播放 | library cache；source_type/source_id合法 | 浏览只读；PlayAll/Shuffle交服务端替换Queue | 确认后的context/queue/history；资源read不发控制 | 空/不可用不伪造曲目；unknown原key；shuffle只生成一次 | `library-collections.test.ts`、`song-actions.test.ts`；B05 |
| T9-SEARCH-001 / resource / LIB-SEARCH-VIEW-001 | route q + library marker | SVG归类置顶/默认单列表去重/进入对应详情并返回；不动Queue | GET results→逐song表示；原Collection保留；无History | 服务端catalog/Collection排序；空查询/无匹配；旧query/epoch/revision不倒灌 | SearchView/CollectionView/同Library cache为owner；真实API groups与golden；A02后端关系77/完整1451；A04 Search6/关系46/Web完整261/typecheck/build及独立审阅通过；用户验收认可，CLOSED / HUMAN PASSED（详见B06最终关闭记录） |
| T9-PLAYLIST-001 / mutation/resource / CRUD/reorder | full membership；系统Playlist保护 | 仅名称/成员/顺序+revision；文件/播放/收藏其他资源不变 | 无MPD；existing playlist事务/事件 | duplicate/member mismatch保持事实；取消已知旧draft；204重读 | `playlists.test.ts`；B07 CLOSED / HUMAN PASSED，proof见B07 acceptance |
| T9-FAV-001 / mutation/resource / 爱心/Favorites | LIB-FAV-MEMBERS-001：GET /api/favorites/members完整有序membership | 仅目标membership/revision；不播放/重建Queue | 无MPD；无播放History；同域事务 | 请求失败保留confirmed星标；同song pending锁；跨页读同步 | `favorites.test.ts`；B08 |
| T9-SETTINGS-001 / external representation / About+Output | writable只用于Output；独立MPDInfo/Output DTO | confirmed与request分层；仅既有NAS_DAC控制 | 按Output Spec外部确认，About读取无控制 | unknown不补零，失败不改confirmed；retry归持久owner | `settings.test.ts`、现有output tests；B09 |

## 7. 本轮验证与审计退出

Fresh验证（当前main代码）：`npm --prefix web run test -- --run`：14 files / 173 passed；`npm --prefix web run typecheck`：exit0；`.venv/bin/python -m pytest -q server/tests/api/test_web_wire_fixture.py`：3 passed。既有Starlette/httpx deprecation warning，未更改依赖。

环境：既有`.venv`，Python3.14.4、pytest9.1.1、ruff0.16.9。无依赖安装、Docker、live MPD请求、构建或新手机测量；后端全量1398的历史结果仅见W6合并核验，不冒称本轮重跑。

- [x] 核对本机main/Git、Task9权威文档、Task8最新交接及实际Web/backend边界。
- [x] 分开已实现基础、继承合同、待实现UI、待审核业务新增与并发能力限制。
- [x] 建立增量矩阵、proof owners、原Step→Batch及手机卡映射。
- [ ] G9-01唯一Playback Spec/接口/生命周期审核关闭（B02进入实现前）。
- [ ] Batch计划审阅并获实施授权；当前各Batch NOT STARTED。

下一入口：[Task 9 Batch Plan](2026-10-10-task-9-web-batch-plan.md)。先B01共享基础；全Task不能因本报告或既有173测试宣称通过。

## G9-01 冻结更新（2026-10-10）

用户批准建议并授权冻结及直接执行B02。唯一合同现为 Playback Spec §3.3.1 PB-SONG-NOW-001；上文 DRAFT/待审核为审计时历史状态。G9-01 Contract CLOSED，T9-SONG-001 正式引用 PB-SONG-NOW-001。API 为 POST /api/playback/songs/{song_id}/play → QueueItemResponse，Service 为 play_song_now(song_id:str)，完整生命周期/失败/重试以唯一 Spec 为准。实现/自动/关系Gate 尚待本轮证明；不因合同关闭称B02完成。

## B02验证关闭更新（2026-10-10）

T9-SONG-001后端owner已实现，G9-01与B02自动/关系Gate CLOSED：新增36、指定回归209、完整后端1434、后端wire3/Web wire23、typecheck、定向Ruff及diff check通过。用户批准不可用pending整次拒绝并保留原Queue；唯一合同、owner与精确proof见[单份B02验收报告](../task-9/2026-10-10-task-9-b02-acceptance.md)。phone N/A、真实设备NOT RUN、PWA DEFERRED；B03以后未启动，不宣称Task9整体完成。

## B03前置核对 / G9-06（2026-10-10）

用户授权仅执行B03；已重新读取入口、权威Specs、B01/B02关闭记录并核对当前`feature/task-9-web`、HEAD `14c6239`及未提交实现。B01/B02关闭不重开；本轮共享壳及相关Web6文件76项、后端Queue/History和B02生命周期59项、B02两文件36项、Web typecheck均通过。完整命令及当前状态见[单份B03报告](../task-9/2026-10-10-task-9-b03-acceptance.md)。这些是前置复验，不能抵扣尚不存在的B03表示/展开proof。

**G9-06 / OPEN：T9-QUEUE-001的明确Stop复位来源缺少Web可观察合同。** PB-SONG-NOW-001已冻结，明确要求B03按accepted Context ID变化、已确认用户Stop、epoch变化复位，unknown STOPPED不复位；但`PlaybackService._explicit_stop`仅为服务内部可回滚标记。`StateService`、`FullStateSnapshot`、HistoryAvailability、PlaybackState及Web decoder未暴露该来源/代次。WS只交付失效义务，不重放操作；浏览器可能只看到合并后的最新状态。仅绑定本客户端Stop HTTP回执不能覆盖其它客户端Stop及中间状态未送达的情况，且当前Player无Stop UI。

现有`PlaybackService.delete`在current无successor时也调用`history_service.stop()`；`_save_confirmed_status`对STOPPED统一设置AutoPlay=false。这说明空session或STOPPED/AutoPlay=false不是明确用户Stop的来源证明，不能擅自用它们或session变化扩大复位规则。永久History既不包含所有未经认证的结束原因，也不属于Played展示数据来源，不以读History补洞。

B03的领域规则已冻结；缺的是满足该规则的传播合同及实现前置。可审阅方向：单独冻结服务端Stop生命周期信号（需定义提交/回滚、replay、epoch、重连及合并读取边界）；或由用户明确修改唯一Playback Spec，取消立即Stop复位要求，仅保留Context/epoch复位。两者均未获本轮选择，不定义字段或默认新语义，不自动扩大B03后端范围。G9-06关闭前暂停B03产品实现；B04以后不推进。

## G9-06合同关闭 / B03继续授权（2026-10-10）

用户选择“补充服务端Stop生命周期信号，补充合同并直接开始B3”。唯一Playback Spec §3.3.2 **PB-STOP-LIFECYCLE-001 FROZEN**，Architecture §12.3引用该传播合同；上节待选择为历史状态。G9-06 Contract CLOSED，实现/自动传播Gate待证明，未关闭B03。

`T9-STOP-001 / STATE_PROPAGATION`：P已有Service/epoch/完整baseline；A PlaybackService累计计数；Δ成功提交明确Stop+1，snapshot additive explicit_stop_generation；U Queue/History既有领域结果及其它动作不变；X继承Stop MPD确认；H仅playback失效义务，不造History；T最外层joint commit/rollback；F失败不可见；Rterminal replay不递增；O合并读取、跨route仍可识别已提交Stop，旧服务器null未知；E `test_stop_lifecycle.py`真实Service/API/SQLite→DTO、`queue-view.test.ts` shared decoder/store→queueUi/route。完整边界以唯一Spec为准。


## 2026-10-11 T9-QUEUE-A03当前交付状态

PB-QUEUE-VIEW-001按用户确认冻结；B03连续列表/进入定位/下拉揭示/候选投影及必要B04 occurrence点击/待播拖动子集实现、自动Gate完成。fresh Queue25、完整Web214、指定后端135、完整后端1443通过；typecheck/build/定向Ruff及diff check通过。独立审阅两项Important已RED→GREEN并回归，排序触摸/揭示隔离proof亦通过。当前新LAN http://192.168.3.18:5176/queue（T9-QUEUE-A03）构建字节、同源API/WS及窄屏/三场景浏览器核验通过。

B03与本轮B04子集仍OPEN / HUMAN PENDING，完整B04未完成；用户第一阶段反馈后再由agent切其它必要观察场景，不提前关闭Gate。B01/B02保持CLOSED；PB-SONG-NOW-001/PB-STOP-LIFECYCLE-001服务端冻结不变。删除/清空/保存/Next/Add及其它Batch未实施；未commit/push/PR/merge。详见[同一B03 acceptance的T9-QUEUE-A03记录](../task-9/2026-10-10-task-9-b03-acceptance.md)。ArtworkRef单Song500仍为批次外未修复项。

## 2026-10-11 B04剩余续作：合同裁决与最小计划

用户授权当前dirty checkout继续B04剩余范围；feature/task-9-web / HEAD14c6239已重新核验，既有修改保留。B01/B02/B03及B04点击/拖动、A04/A05维持CLOSED，旧OPEN/PENDING及“本轮不实施”仅指历史轮次。完整B04 IN PROGRESS / HUMAN PENDING。

| 冲突/共享接口 | 裁决（既有Spec/API为准） |
|---|---|
| Queue默认整行播放 vs Next/Add菜单 | 独立更多按钮；整行精确queue_item_id播放不变。Next/Add按song_id创建新MANUAL occurrence，不移动/去重旧项，不抽取B05 SongRow。 |
| “清空”可能误作Stop/全部Queue | DELETE item按queue_item_id，可作用current/Played/pending；DELETE queue只清UpNext，服务端AutoPlay补充、current删除后继/停止及History规则原样保留。 |
| 可见候选子集 vs 保存完整UpNext | POST save-as-playlist仅{name}，服务端在事务内读取提交时完整UpNext；不含current/Played、不去重、重复拒绝零半成品。HTTP确认后state及Playlist列表重读。 |
| 页面草稿 vs 跨页恢复 | 菜单/名称/确认草稿离页丢弃；已发intent交持久TaskActions，unknown原key/payload重试；confirmed/read失败只读；epoch退役、断线禁写。 |

执行清单：
- [ ] 新Queue Next/Add/delete/clear独立入口行为测试RED，保存{name}/名称草稿/unknown/读失败/重复失败关系测试RED；真实Playlist DTO序列化及完整UpNext/重复/写入回滚后端proof。
- [ ] 最小QueueActions + Queue局部菜单/清空确认/保存输入；共享壳/唯一通知及冻结展示/排序不变；PB-SONG-NOW-001、PB-STOP-LIFECYCLE-001不改。
- [ ] 精确节点→Queue动作/保存文件→Queue表示、wire/resource-cache/mutation/player/global-notices/shell/global-artwork；后端QueueManager/save节点→文件→mutations_playback/idempotency/realtime_queue/realtime_history/playlist_relationships/realtime_playlist/stop_lifecycle/song_play_now/control_target；完整Web、typecheck/build，定向Ruff及diff检查。
- [ ] 独立审阅；新的自有SQLite/Mock手机URL及版本，LAN产物/同源API/WS核验，窄屏/键盘/入口/操作收敛辅助验证。
- [ ] 用户手机H03/H04/H10、M01/02/03/05反馈后才关闭完整B04。

G9-02未送达并发窗口保留，无expected_revision或新公开字段。ArtworkRef单Song500批次外未修复；真实MPD/NAS/DAC NOT RUN、PWA DEFERRED。不commit/push/PR/merge，不推进B05。自动、Mock、真人证据分开记录于B04 acceptance。

## 2026-10-11 B04剩余实现/自动完成，等待真人Gate

Next/Add独立入口、精确delete、仅待播clear及服务端完整UpNext save已实施；此前B01–03/已接受子集不变。本轮fresh完整Web237、指定后端关系157、新save/wire6、完整后端1446、typecheck/build/定向Ruff通过；独立审阅4个边界精确RED→GREEN并最终回归。完整B04 OPEN / HUMAN PENDING，手机URL http://192.168.3.18:5177/queue，T9-B04-A01。唯一证据及最少手机步骤见[本轮B04 acceptance](../task-9/2026-10-11-task-9-b04-acceptance.md)。G9-02保留、PB-SONG-NOW/STOP及冻结展示不改，ArtworkRef批次外；真实设备NOT RUN，PWA DEFERRED，无Git整合，不推进B05。

## 2026-10-11 A01用户纠正：Queue Next/Add是移动原条目

用户接受其它B04交付，仅Next/Add新建重复项未通过。Queue快捷入口改按queue_item_id移动，完整UpNext首位/末尾含隐藏候选，不能用song-id复制；普通Song动作保持原入队语义。现有reorder只支持pending；current/Played入口边界询问中，不擅改冻结生命周期。完整B04仍OPEN，新语义须fresh测试与手机复测。实现/自动/手机记录继续追加同一[B04 acceptance](../task-9/2026-10-11-task-9-b04-acceptance.md)。

### A02移动边界已确认

用户选择仅待播项提供移动入口。最小实现为move(id,next|add,title)经PUT原item，不发POST song、不改server；完整pending首位/末尾包含隐藏候选，边界no-op，原key恢复。current/Played仅删除；原availability门禁属于A01“新入队”的历史语义，移动与已接受drag一致按queue权威判断pending，metadata仅展示，不以缓存availability定义reorder。G9-02保持，不加expected_revision。精确测试已RED→GREEN，完整Gate仍待A02本轮回归及手机复测。

### A02最新交付：移动实现/自动完成，等待两项手机复测

用户已确认仅pending移动。Queue快捷移动实现已修正，原ID/总数保留、含hidden首尾、边界no-op，current/Played仅删除。fresh Web关系99/完整242、后端关系104、typecheck/build/定向Ruff通过，独立审阅无遗留问题。新URL http://192.168.3.18:5178/queue（T9-B04-A02）；Mock真实REST逐项验证position1→7且全量身份/current/Played不变。其它B04已获用户“别的都可以”反馈接受，只等两个移动入口复测，完整B04仍OPEN。完整证据见同一B04 acceptance末尾。A01复制语义不再当前合同，不改普通song Next/Add；G9-02及冻结展示/lifecycle保持。

## 2026-10-11 完整B04最终关闭：用户验收通过

用户明确“验收通过，记录一下。不需要额外的复测”。A02仅待播原occurrence移动获真人接受，结合此前其它B04范围已接受，完整B04 **CLOSED / HUMAN PASSED**；B01–03及既有子集保持CLOSED。最终Queue快捷操作是移动queue_item_id，不是song-id复制；current/Played不提供移动入口。此前OPEN/PENDING及A01复制方案保留为历史。

关闭依据见[B04 acceptance最终关闭记录](../task-9/2026-10-11-task-9-b04-acceptance.md)。本轮仅同步记录，不跑额外测试、不改产品/环境/依赖/Mock场景，不编造新自动或逐场景真人证据。A02 Web242/后端关系104及A01完整后端1446均属于各自实施轮次。feature/task-9-web / HEAD14c6239重新核验，dirty保留，无commit/push/PR/merge。G9-02保留，真实设备NOT RUN、PWA DEFERRED、ArtworkRef单Song500批次外未修复；B05及其它Batch未启动，Task9整体未完成。

## 2026-10-11 B05实施/自动交付，等待手机Gate

最终状态（2026-10-11）：用户明确A02“可以了。通过验收”，结合此前功能认可，完整B05 **CLOSED / HUMAN PASSED**，必要手机Gate关闭。按用户要求仅同步文档，不重复测试；A02 Web255及A01后端1448保留各轮证据归属，不编造逐项真人日志。B06–10未启动；真实设备NOT RUN、PWA DEFERRED、G9-02与ArtworkRef批次外限制保持，无commit/push/PR/merge。以下交付时OPEN描述为历史。

后续A02仅按用户六项要求调整B05界面，公开动作合同不变；fresh Web255/typecheck/build及窄屏验证通过，封面版本身份审阅问题已修正复核。用户认可功能，新界面手机反馈仍待收，B05 OPEN；最新URL版本T9-B05-A02与范围见[B05 acceptance A02](../task-9/2026-10-11-task-9-b05-acceptance.md)。不推进B06，不作Git整合。

用户授权本批次，核对当前feature/task-9-web / HEAD14c6239及dirty成果、最新B04用户关闭、唯一Specs和实际接口后执行。Library分类/详情/全歌曲、普通SongRow三个动作、服务端PlayAll/Shuffle、统一Library cache和顶部通知已接入；Queue原occurrence点击/快捷移动不改，真实Favorites及其它未来Batch未实施。fresh B05 Web11、指定关系108/完整253、后端指定86/完整1448，typecheck/build/定向Ruff通过；独立审阅唯一Important菜单遮挡顶部已浏览器RED→GREEN修正，无遗留Critical/Important。

当前实际URL http://10.104.60.177:5179/library（T9-B05-A01），空集合 http://10.104.60.177:5179/library/years/unknown；LAN产物字节/同源REST/WS及窄屏验证通过。B05 **OPEN / HUMAN PENDING**，必要H04/H05/H10/M01/M02/M04/M05待用户反馈，不推进B06。矩阵T9-SONG-001/T9-LIB-001的owner/proof/fresh结果、最少手机卡及限制见[单份B05 acceptance](../task-9/2026-10-11-task-9-b05-acceptance.md)。真实设备NOT RUN，PWA DEFERRED，既有ArtworkRef REST500批次外保持；没有commit/push/PR/merge。

## 2026-10-11 B06 Search实施与交付

A02更新：用户否定跳页对象分组，明确归类集中置顶、内容在同页下方一起展示，顺序跟随归类。唯一Library §6.1 LIB-SEARCH-VIEW-001已按此次边界冻结，T9-SEARCH-001引用该合同；additive results读取仅B06必要增量，原Collection API保持。A01自动/LAN仅证明旧Song表示，不关闭新表示Gate；当前B06 IN PROGRESS / HUMAN PENDING。

已核对B05最新用户关闭、feature/task-9-web / HEAD14c6239及实际前置代码；本批次查询生命周期按现行T9-SEARCH-001实施，无新业务合同决策或未关闭前置。Library入口/Search route q、空白/快速改词/清空、返回与刷新重读、Collection→有序Song、epoch/revision迟到拒绝、顶部读取恢复及共享SongRow动作完成。新proof先RED→GREEN；fresh Web4/指定关系44/完整259，后端精确search11/指定API-service+fixture36，typecheck/build/定向Ruff通过。独立审阅无Critical/Important，LAN同源REST/WS及320px窄屏预检通过。

当前手机URL http://10.104.60.177:5180/library/search（T9-B06-A01），必要H08/H04及M01/M02/M03/M04待用户反馈，**B06 OPEN / HUMAN PENDING**。最少三项手机卡、合同追溯及限制见[单份B06 acceptance](../task-9/2026-10-11-task-9-b06-acceptance.md)。B01–05保持CLOSED，B07–10不推进；真实MPD/NAS/DAC NOT RUN、PWA DEFERRED，G9-02/ArtworkRef批次外限制保持。未commit/push/PR/merge，既有dirty成果保留。

### B06 A02 当前验收版本

LIB-SEARCH-VIEW-001实现与自动/关系/独立审阅完成，无未关闭Critical/Important；A02 URL http://10.104.60.177:5181/library/search，同源REST/WS与窄屏已验证。新归类顶部及下方内容顺序待两项手机反馈，B06 OPEN / HUMAN PENDING；旧A01证明保留历史，B07–10不推进。fresh后端关系77/Web完整260，详见同一B06 acceptance末尾。

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

B07 **OPEN / HUMAN PENDING**，必要H06/H04/H10及M01/M02/M03/M05等待反馈；B01–06保持CLOSED，B08–10不推进。范围/合同追溯、命令及最少四项手机卡见[单份B07 acceptance](../task-9/2026-10-11-task-9-b07-acceptance.md)。现有.venv未改，无依赖/DB schema/生产后端改动，无commit/push/PR/merge。真实MPD/NAS/DAC NOT RUN，PWA DEFERRED；ArtworkRef单Song500批次外保持。


## 2026-10-11 B07最终关闭：用户验收通过

用户在T9-B07-A01交付后明确“验收通过。更正相关文档。不需要额外测试。”；B07 **CLOSED / HUMAN PASSED**，必要H06/H04/H10及M01/M02/M03/M05手机Gate按本次整体认可关闭，不编造逐项操作日志。B01–B07保持CLOSED，B08–B10未启动，Task9整体未完成。关闭依据见[单份B07 acceptance最终关闭记录](../task-9/2026-10-11-task-9-b07-acceptance.md)。

本轮只更新必要验收状态/入口并检查文档差异及diff check；没有重跑测试、构建、环境或LAN验证。B07 Playlist9/指定Web36/完整Web270、指定后端25及独立审阅/LAN证据保留实施轮次归属。feature/task-9-web / HEAD14c6239重新核对，原dirty保留；产品/测试/依赖/Mock及运行文件不改，无commit/push/PR/merge。G9-02、真实MPD/NAS/DAC NOT RUN、PWA DEFERRED及ArtworkRef批次外限制保持。


## 2026-10-11 B08前置核对与用户裁决

feature/task-9-web / HEAD14c6239与既有dirty成果已核对，B01–07最新用户关闭有效。实际Favorites独立表且无自动系统Playlist实体；现有GET /api/favorites拆分playable/unavailable，无法还原跨availability完整排序，旧§3/G9-04/B08系统Playlist读取假设不成立。用户明确批准最小只读GET /api/favorites/members → {song_ids}，由既有PlaylistService/Repository按收藏时间倒序（song_id稳定tie-break）提供完整成员；Library §5.4 LIB-FAV-MEMBERS-001 FROZEN。无DB/schema/依赖或收藏写接口变更，现有revision传播继承。

用户确认Player艺术家同行右侧直接收藏入口、其它Song位置仅已收藏展示、既有单曲菜单一个可操作当前状态收藏项；Queue整行occurrence播放保持、更多菜单收藏。随后要求统一爱心SVG而非五角星，实心复用主题accent。Library §5.3 LIB-FAV-UI-001为本批次现行合同，覆盖旧全位置直接互动/未收藏星标设计。T9-FAV-001 membership owner消费同一playlists cache；HTTP+权威read/原key/断线/epoch/双revision合同保持。

B08实施与验证中，HUMAN PENDING，不推进B09/B10；具体结果写单份B08 acceptance，不以自动通过关闭手机Gate。未commit/push/PR/merge，.venv保持。


## 2026-10-11 B08当前交付

LIB-FAV-UI-001（用户爱心设计）/LIB-FAV-MEMBERS-001（获准最小只读完整成员接口）冻结并实施；复用同一cache/TaskActions/通知，完整不可用成员、服务端顺序、全位置爱心和单曲菜单接线完成。Fresh Favorites9、指定Web124/完整279，最后低影响占位显示补充定向26；后端指定23、typecheck/build/Ruff/diff通过。独立审阅/自查问题均精确RED→GREEN修复，无遗留finding。LAN http://10.104.60.177:5185/（T9-B08-A01）最终产物字节/同源REST/WS及窄屏预检通过。

B08 **OPEN / HUMAN PENDING**，仅等H07/H04/H10、M01/02/05手机反馈；B09/B10不推进。各轮结果、最少操作及限制见[B08 acceptance](../task-9/2026-10-11-task-9-b08-acceptance.md)。现有dirty和.venv保留，无commit/push/PR/merge，无依赖/DB模型变更；真实设备NOT RUN、PWA DEFERRED、ArtworkRef REST500批次外保持。


## 2026-10-11 B08最终关闭：用户验收通过

用户在T9-B08-A02整改交付后明确：“验收通过。无需重复测试。更正需要的文档即可”。据此将B08记为 **CLOSED / HUMAN PASSED**，必要H07/H04/H10及M01/M02/M05手机Gate按本次整体验收认可关闭，不编造逐项手机操作日志。现行实现包含Player空心/实心爱心与位置修正、其它位置仅已收藏展示、菜单纯文字、Queue单曲菜单与Library共享样式，以及获准的最小只读完整收藏成员接口。

自动证据沿用所属轮次：A01指定Web124/完整279、后端指定23；A02展示整改定向58、typecheck/build、产物字节/REST/WS与辅助DOM核对。此次仅更新必要文档并检查文档差异及diff check，未重跑测试、构建或运行环境验证，不宣称新增自动证据。

B01–B08 CLOSED，B09/B10未启动，Task9整体未完成。真实MPD/NAS/DAC NOT RUN、PWA DEFERRED、G9-02及既有ArtworkRef REST500批次外限制保持。原dirty成果保留，无commit/push/PR/merge。关闭依据见[B08 acceptance最终关闭记录](../task-9/2026-10-11-task-9-b08-acceptance.md)。此前OPEN/PENDING保留历史。


## 2026-10-11 B09当前交付：实现/自动完成，等待手机Gate

Settings About/NAS_DAC及持久顶部恢复、音乐库播放列表/收藏唯一标签入口、用户选择的MPD地址保存后重启生效完成。SYS-MPD-CONNECTION-001已冻结，最小文件/API例外不授权其它Task10功能。fresh指定Web103/完整284、指定后端57/完整1466，新配置文件13（最终排版后）、typecheck/build/定向Ruff/diff通过；独立审阅两项Important已RED→GREEN，当前无遗留finding。

新LAN http://10.104.60.177:5186/settings（T9-B09-A01），同源产物字节/REST/WS及320px预检通过。B09 **OPEN / HUMAN PENDING**，H09/H10、新增入口及M01/02/03/04/05待用户反馈；B01–B08保持CLOSED，B10不推进。完整范围/合同追溯/最少手机步骤见[B09 acceptance](../task-9/2026-10-11-task-9-b09-acceptance.md)。真实设备NOT RUN、PWA DEFERRED、G9-02/ArtworkRef批次外限制保持，原dirty/.venv保留，无commit/push/PR/merge。


### 2026-10-11 B09 A02用户反馈输入

用户“A01测试项没问题”接受原功能验证；本轮仅标签顺序、DAC同行开关、地址同行固定宽度及IPv6组合表示修订。用户澄清仍是MPD域名/IP+端口，不使用HTTP前缀，后端原生TCP合同不扩展。真实设置页重启入口登记主Plan Task11待办，不在B09加入假实现；SYS-MPD-CONNECTION-001仍为保存后重启生效。原A01已接受范围不重复要求真人复测；本轮新表示手机Gate仍OPEN，不推进B10。

A02步骤：新开关canonical/显式enabled关系及标签顺序RED→GREEN；IPv6组合表示RED→GREEN、后端保存/读取/下次启动IPv6定向proof；设置/输出文件与受影响关系回归、typecheck/build；LAN同源和320px固定宽度/开关同行辅助验证；手机仅复核本轮布局/开关手感。


### B09 A02最新交付：等待局部手机复核

用户认可A01测试；A02标签艺术家→收藏→播放列表、DAC同行confirmed开关、同行固定宽地址输入已交付。用户澄清MPD原生TCP无HTTP前缀；IPv6裸host保存/读取/启动及组合[IPv6]:port补充验证通过。真实restart按钮及监管后端登记Task11，本批次不实施。

Fresh设置/输出16、指定Web105/完整286、IPv6 API精确1/配置文件14，typecheck/build/Ruff/diff及聚焦独立审阅通过；LAN同源产物/REST/WS、320px长地址与五位端口固定尺寸、开关同行及标签选择核验通过。地址仍 http://10.104.60.177:5186/settings，title T9-B09-A02。B09 OPEN / HUMAN PENDING，只复核新增三类表示，原A01已认可功能不重复要求；B10未推进。证据追加同一B09 acceptance；真实设备/IPv6连通NOT RUN、PWA DEFERRED，既有批次外限制不改，无Git整合。


## 2026-10-11 B09最终关闭：CLOSED / HUMAN PASSED

用户最终反馈：“验收通过。无需重复测试。记录更正需要的文档。”结合此前“A01测试项没问题”，接受B09原功能及A02标签顺序、DAC同行开关、同行地址输入与IPv6组合表示。H09/H10、M01/M02/M03/M04/M05及A02局部手机Gate按用户整体验收关闭，不编造逐项操作日志。

自动验证及LAN证据沿用[B09验收记录](../task-9/2026-10-11-task-9-b09-acceptance.md)的A01、A02所属轮次；本次仅更新必要文档并检查文档差异，未重复测试、构建、环境或网络验证，不新增自动证据。B01–B09 **CLOSED / HUMAN PASSED**；B10未启动，Task9整体未完成。此前OPEN/PENDING为历史状态，以本次最终关闭为准。

真实MPD/NAS/DAC及IPv6网络连通仍NOT RUN，PWA DEFERRED；设置页真实立即重启入口及监管后端仍为Task11待办，G9-02与既有ArtworkRef单Song REST500批次外限制保持。未改产品代码，无commit/push/PR/merge。


## 2026-10-11 B10：综合自动交付，手机与实机Gate待关闭

本批次只增加真实SQLite/Services/MockPort四阶段golden及跨route action/cache/ACK-read综合proof，未改产品功能或合同。负向校验能捕获缺少snapshot refresh，原文件按字节恢复后GREEN。fresh Web新1/指定114/完整287、后端新1/指定1114/完整1468、typecheck/build/Ruff/diff及独立审阅通过。非空ArtworkRef后端综合链未证明，既有单Song500继续单列，不吞作通过。

本机production产物字节及两个origin REST/WS核验通过：Mock综合http://10.104.60.177:5187/；真实MPDAdapter地址入口http://10.104.60.177:5188/settings，无Mock/虚构能力、独立DB。历史NAS192.168.3.94:6600本轮TCP超时；等待用户保存当前实机地址及提供只读音乐根/URI映射。保存仅下次启动生效，由agent重启自有live服务；不实现Task11按钮或Task10通用配置。完整矩阵、独立审阅Minor边界、各轮命令及手机/实机方案见[单份final acceptance](../task-9/2026-10-11-task-9-final-acceptance.md)。

B01–09保持CLOSED；B10 OPEN/HUMAN PENDING，实机功能Gate BLOCKED/NOT RUN，Task9整体未完成。PWA DEFERRED、G9-02限制保留；现有dirty/.venv/DB保留，无Git整合。此前B10未启动段落保留为历史，不作为当前状态。


### B10 A02：用户独立IPv6实机验收

用户只能在启用IPv6后访问MPD，届时Codex不可用；agent事先准备/启动，用户独立测试后恢复网络反馈，不能要求agent实时设备验证。远程NAS音乐仅MPD可读尚不足以建立本机Web音乐库；当前LibraryScanner需后端可读文件根，MPDAdapter不提供曲库导入/根映射。等待IPv6 endpoint及NAS部署/只读挂载/有限连接先行的选择，不扩展合同。LIVE入口5188已独立启动、配置GET200，仍未配置实机，不记设备通过。详情见[同一final acceptance A02](../task-9/2026-10-11-task-9-final-acceptance.md)。本轮仅启动核验/文档同步，无重复suite或Git整合。
