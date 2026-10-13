# Task 9 B03 acceptance — T9-B03-A01

## 2026-10-11修订前置（最新状态）

用户要求连续Queue、每次进入隐藏Played/定位current、下拉揭示、确认播放/暂停图标、单曲AutoPlay只预览首候选、所有Queue类别直接occurrence点击播放及拖动。已核对实际Git、代码和入口Specs；冲突与最小计划同步audit/Batch Plan最新顶部章节。三个边界已由用户答复：仅待播可排序，多曲隐藏全部AutoPlay，留页自动切歌保留滚动与已揭示历史。

| Gate | 本轮证据/状态 |
|---|---|
| B01/B02、冻结后端合同 | 保持既有关闭；未改领域合同 |
| 新Queue合同 | FROZEN：Playback §5 PB-QUEUE-VIEW-001及Visual/Architecture引用已同步 |
| 新修订实现/行为RED与自动Gate | A03–A05当前交付范围实现/自动及用户整体验收通过；见最终关闭记录 |
| 前置基线自动验证 | npm --prefix web run test -- --run tests/invariants/queue-view.test.ts：5 passed，仅旧合同基线 |
| 本地环境 | .venv Python3.14.4、pytest9.1.1、ruff0.16.9；server/requirements.txt已读；未安装或修改依赖 |
| Git | feature/task-9-web / 14c6239；既有dirty内容保留，git diff --check通过；无commit/push/PR/merge |
| 新构建/LAN/HUMAN | T9-QUEUE-A05构建/LAN及用户HUMAN PASSED；B03 CLOSED |
| B04 | 点击/拖动子集 CLOSED；完整B04未完成；删除/清空/保存/Next/Add及后续Batch未推进 |
| 真实MPD/NAS/DAC、PWA | NOT RUN / DEFERRED |

此前Song REST含ArtworkRef序列化500仍为单独批次外发现，本轮未修复。

日期：2026-10-10，Asia/Shanghai。用户授权仅B03 Queue表示与Played；本轮完成前置核对，发现G9-06，暂停产品实施，未关闭Batch。

## 当前范围与Git

分支`feature/task-9-web`，HEAD `14c6239283f4fed079f07ab817964b23e87e793c`。开始时B01/B02、合同/计划和相关README已有未提交修改，实际生产owners及测试存在；均保留。本轮仅向两个Task9入口追加前置核对记录并创建本报告，未修改生产代码、测试、长期Spec或依赖，未启动其它Batch。没有commit/push/PR/merge。

已读取两入口、主Plan Task9、Visual WEB-UI-*、Architecture §4.1–4.3/§12/§19.5、Playback §3.3.1/§5/§8.9、Library Song/revision合同、手机验收方法及B01/B02关闭记录；以当前代码和fresh验证核对历史状态，不把旧DRAFT段落当当前合同。

## Gate

| Gate | 当前状态 |
|---|---|
| B01 / B02 | 既有关闭记录核对，实际owners及本轮前置复验通过；不重开历史手机验收 |
| PB-SONG-NOW-001 / G9-01 | FROZEN / CLOSED；不重新讨论song Play Now领域语义 |
| B03 Contract / propagation prerequisite | BLOCKED：G9-06 OPEN，明确用户Stop复位的Web可观察来源尚未定义 |
| B03实现 | NOT STARTED：QueueView/queuePresentation/queueUi/resourceWire未创建 |
| B03新表示 / 展开proof | NOT RUN：`queue-view.test.ts`尚不存在；前置测试不当B03通过证据 |
| 本地环境 | READY：既有`.venv` Python3.14.4、pytest9.1.1、ruff0.16.9；读取server/requirements.txt，无环境或依赖改动 |
| production build / LAN / phone | NOT RUN：当前没有B03产品页面，不交付旧B01 URL冒充B03；H02/M01/M02/M04待实现和自动Gate后再交付 |
| 真实MPD/NAS/DAC | NOT RUN：本轮为本地SQLite/Mock测试，无live控制 |
| PWA | DEFERRED |
| B04以后 | NOT STARTED |

## G9-06：明确用户Stop来源不能由当前状态猜测

唯一Playback Spec §3.3.1的下游合同要求：accepted Context ID变化、已确认用户Stop、epoch变化使展开归零；会话内普通Play Now、暂停、采样和切页不归零；unknown STOPPED不归零。

实际传播链中：

- `PlaybackService._set_explicit_stop`拥有随事务提交/回滚的私有标记；`stop()`确认后设置，已确认开始消费。该标记服务重启后丢失，不能从STOPPED或空session重新推断。
- `server/app/models/realtime.py`、`models/queue.py`及`StateService.get_full_snapshot`没有Stop来源或生命周期代次；Web `types/api.ts`、`services/wire.ts`只解码这些既有字段。
- `PlaybackService.delete`的current无successor路径也调用`HistoryService.stop()`清session；`_save_confirmed_status`对所有STOPPED写AutoPlay=false。这些字段不是明确用户Stop的充分证明。
- Architecture §12.2的invalidate不是操作回执，允许合并重读且不重放事件。只监听当前浏览器Stop ACK不能覆盖其它客户端及漏过的中间Stop；当前产品也无Stop UI。永久History不保证未经认证旧active的结束原因，不能拿它补来源或拼Played。

因此不选择“session变化即复位”“STOPPED即复位”等替代规则，也不擅自增加公开字段。Architecture §19.5要求先修正唯一权威Spec，再更新矩阵、建立RED proof、修改生产代码；用户本轮也明确禁止自行补定语义。

待用户选择的方向：优先单独冻结可供snapshot传播的服务端Stop生命周期信号，明确outer commit/rollback、terminal replay、epoch/reconnect/合并读取边界后评估最小后端前置；或明确修改唯一Playback Spec，取消立即Stop复位，仅按Context/epoch变化复位。两方向都属于待审阅，尚不构成合同或实施授权。G9-01及B02不因这个新的表示/传播前置重开。

## 本轮自动前置验证

所有命令从仓库根运行，均exit0：

1. `.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_queue.py server/tests/invariants/test_realtime_history.py server/tests/invariants/test_song_play_now.py::test_explicit_stop_starts_new_context_and_session_preserving_pending server/tests/invariants/test_song_play_now.py::test_lifecycle_does_not_infer_stop_or_reuse_song_occurrence` → **59 passed**。
2. `.venv/bin/python -m pytest -q server/tests/api/test_song_play_now.py server/tests/invariants/test_song_play_now.py` → **36 passed**。与上项生命周期节点有重叠，不相加冒称独立覆盖数。
3. `npm --prefix web run test -- --run tests/invariants/shell-navigation.test.ts tests/invariants/global-notices.test.ts tests/invariants/global-artwork.test.ts tests/invariants/resource-cache.test.ts tests/invariants/wire.test.ts tests/invariants/player-facts.test.ts` → **6文件76 passed**。
4. `npm --prefix web run typecheck` → **PASSED**。

Python两次运行各含1条既有Starlette/httpx弃用warning，无测试或环境失败，未修改依赖。`git diff --check`通过，实际stat/status已核对，既有未提交B01/B02保留。本轮没有新增生产实现，未声称完整后端或完整Web回归重跑。

## 剩余Gate与交付

先关闭G9-06，再按B03原清单执行行为RED→最小实现→目标及关系回归→typecheck/生产构建→核验LAN及同源API/WS→给真实URL和最少H02/M01/M02/M04操作项，等待用户手机反馈。当前没有可供B03验收的新页面，手机Gate尚未开始；不提前关闭B03，不推进B04。


## T9-B03-A02：授权补充合同后的实施结果

用户补充“补充服务费stop生命周期信号，按你推荐的补充合同并直接开始b3”，按上下文冻结服务端生命周期来源。A01为历史阻塞记录；当前G9-06 CLOSED，唯一Playback Spec §3.3.2 **PB-STOP-LIFECYCLE-001 FROZEN**，Architecture §12.3同步传播引用，audit增加T9-STOP-001矩阵。既有B01/B02保持关闭。分支及HEAD不变，沿用dirty checkout及原`.venv`，无依赖/DB schema改动，无commit/push/PR/merge。

### 实现范围和合同关系

- PlaybackService运行时`explicit_stop_generation`只在成功显式Stop提交时+1，含已停止后的新Stop意图；后续start不清零。失败、outer rollback/commit失败、precommit取消不泄露代次；terminal replay不重复递增，postcommit取消保留。未知外部停止、删除current无successor/session结束不冒认Stop。计数通过共享事务快照及staged playback invalidation传播，epoch重启清零，不新增持久表。
- domain/public FullStateSnapshot additive nullable字段、StateService joint cut、Web decoder与accepted player owner接线；缺字段/null为未知，首次known只设基线，同epoch已知倒退拒绝，暂时null不丢已知上界。
- AppShell持有queueUi及共享Song Library cache；QueueView读canonical queue，按occurrence ID保留重复song，Played按-1开始、current0、UpNext正序。只有匹配fresh observation与写权限的playing/paused标记实际确认，否则业务当前。Played默认0，每次+10；切页/暂停/普通采样/History session变化不复位，accepted Context/epoch变化或已知Stop代次增加才复位。
- typed Song/SongList解码复用既有Song validator，Song请求路径与响应ID一致；可见ID去重读取、library marker保护，失败/unknown/不可用仍保留条目、顶部notice反馈。长标题有固定槽和省略，原生details可读完整标题/艺术家/专辑/occurrence ID，无新增mutation或B04控件。

### 自动/关系Gate（实际fresh结果）

| Gate / command | 结果与边界 |
|---|---|
| `.venv/bin/python -m pytest -q server/tests/invariants/test_stop_lifecycle.py` | 9 passed；真实SQLite/Services/Mock/API及事务故障/取消，不使用live MPD |
| `npm --prefix web run test -- --run tests/invariants/queue-view.test.ts` | 5 passed；表示、复位、资源失败/迟到/身份错误、legacy-null来源关系 |
| 后端B03指定10文件：stop_lifecycle、realtime_queue/history/snapshot/playback_transport、invariants/api song_play_now、api mutations_playback/idempotency/web_wire_fixture | 153 passed；含B02生命周期合同回归，不以完整suite代替；日志`b03-backend-targets-final.log` |
| `npm --prefix web run test -- --run tests/invariants/queue-view.test.ts tests/invariants/shell-navigation.test.ts tests/invariants/global-notices.test.ts tests/invariants/global-artwork.test.ts tests/invariants/resource-cache.test.ts tests/invariants/wire.test.ts tests/invariants/player-facts.test.ts` | 7文件83 passed，`b03-web-targets-final.log` |
| `.venv/bin/python -m pytest -q server/tests` | 1443 passed，116.62秒；1条既有Starlette/httpx warning，`b03-full-server.log` |
| `npm --prefix web run test -- --run` | 18文件194 passed，`b03-full-web.log` |
| `npm --prefix web run typecheck` / `VITE_ACCEPTANCE_LABEL=T9-B03-A02 npm --prefix web run build` | PASSED；CSS修正后再次typecheck/build，82模块，`b03-build-final.log` |
| 定向Ruff（本轮8个Python生产/测试文件） | All checks passed；未用fix、未扩大到全仓 |
| `.venv/bin/python -m server.tests.api.test_web_wire_fixture` + wire25 | public Pydantic真实序列化Song/SongList/snapshot counter fixture，无手写第二份公共合同 |
| `git diff --check`、stat/status及实际scope diff | PASSED；保留既有B01/B02和untracked documents，新runtime/DB/dist在ignored区域；HEAD未变 |

测试数有覆盖重叠，不相加为独立总数。原测试中snapshot精确字段集、显式重复Stop的transport no-op假设按新增合同调整，pause/seek no-op及原事务断言保留。共享壳fixture增设真实API Song GET读取分支，单独记录songRequests；原mutation/key/payload/epoch/unknown assertions及默认fixture路径保留。初始setup修正不作为生产行为RED证据；主行为RED分别为snapshot缺字段与Queue placeholder。

### 独立审阅及裁决

独立审阅完成：无未关闭Critical/Important。1项Minor延期：当前QueueOccurrence缺key，current从A变B时原生details的open可能沿用；数据已经是B，无错误occurrence或控制目标。仅影响本地详情展开状态，依执行技能Minor延期规则未额外修复。窄屏实际浏览器另发现Grid implicit列min-content撑至814px，来源/按钮被裁切；限制`grid-template-columns:minmax(0,1fr)`后本轮复验clientWidth=scrollWidth=277（浏览器实际innerWidth323），展开按钮277，无水平内容裁切；独立聚焦CSS复核无新发现。

审阅未代替真人Gate、live MPD/NAS/DAC、PWA、B04+或Git整合；这些排除项分别为HUMAN PENDING、NOT RUN、DEFERRED、未授权。全量测试/Ruff/typecheck/build/LAN由主agent实际执行。

### LAN / 浏览器证据与手机最少操作

当前地址 **http://192.168.3.18:5175/queue**，同Wi-Fi访问，页面标记T9-B03-A02。wlan0当前IP核实为192.168.3.18，未沿用旧B01地址。preview监听0.0.0.0:5175、代理到127.0.0.1:8003；backend只用自有新SQLite和MockPort，未控制live MPD/用户DB，未变更其它既有验收进程。

HTML、`index-Csdxbckd.js`与`index-CEG31Zbi.css`LAN响应逐字节等于本轮dist；JS SHA256 `16e4bb2d289ac1e569685c97f48895e59013c11a6bc817a9955d8815936152c5`，CSS `e842be52633f38382bd2f46c77ece0c7abc24411869b67d716a73fc86a4f41bd`。同源/api/state及4个Song GET200；实际/api/realtime首snapshot成功（protocol1），epoch `c6b5906b-9daf-4125-8019-64d50078b326`、stop generation1。本轮owned场景：Played26/current1 paused/UpNext8，重复MANUAL/AutoPlay、长标题及MISSING；LAN原始证据和运行命令留在ignored `.superpowers/sdd/2026-10-10-task-9-web-batch-plan/b03-runtime/`，不作为待提交文件。

浏览器确认0→10→20展开，去Library返回仍20；长标题详情完整、条目ID可读，窄屏最终queue client=scroll，无overflow。浏览器viewport override已撤销。这不代替手机触控、字体缩放/对比度及框架真人验收。

1. 手机查看三分区、重复曲的手动/AutoPlay来源；连续展开Played至10、20，去其它页再回来应保持20。
2. 点长标题读完整内容和条目ID，查看不可用行仍存在、原因在顶部；检查手机窄屏/字体放大时内容和底部导航可达。

先等用户反馈以上H02/M01/M02/M04适用项；随后agent切换自有Mock Stop/Context场景，用户留在Queue观察Played归零，再切unknown-stop观察不归零。没有B03 Stop/Context产品按钮，不要求用户操作未来Batch控件，不提前变场景破坏当前验收。HUMAN未反馈，B03仍OPEN。

### 批次外发现（未修复）

已有`server/app/api/schemas.py::ArtworkResponse`未启用from_attributes；`library.py::_song_response`将含领域ArtworkRef的Song交给SongResponse.model_validate时抛Pydantic model_type ValidationError，GET单Song返回500。实际浏览器及完整trace稳定复现，仅无封面fixture的现有后端测试通过不能覆盖这个问题。按用户批次范围约束，不修改既有公共REST schemas，不隐藏问题或将无封面场景当封面通过。B03资源失败已按合同保留occurrence/顶部错误；当前手机fixture撤去ArtworkRef，仍读取真实Song API200。修复该既有后端缺陷需单独范围，后续Library批次应核对。

### 剩余Gate

B03手机H02/M01/M02/M04、Stop/Context/unknown-stop分阶段真人反馈 **PENDING**；独立审阅Minor **DEFERRED**。无未冻结B03合同或未关闭实施前置；Batch不能仅凭自动验证关闭。真实MPD/NAS/DAC NOT RUN，PWA DEFERRED；B04以后未推进。没有commit/push/PR/merge。


## T9-QUEUE-A03：2026-10-11合同修订与限定实现结果

### 合同与实现

用户确认：仅待播可排序，多曲场景不展示任何AutoPlay候选，留页自动切歌保持滚动/已揭示历史。唯一Playback §5 **PB-QUEUE-VIEW-001 FROZEN**，§3菜单Queue例外、§6.2候选可见规则及§3.3下游/消费者展示说明同步；PB-SONG-NOW-001和PB-STOP-LIFECYCLE-001服务端领域/事务/传播不改。Visual、Architecture本地UI投影引用、audit T9-QUEUE-001/002和Batch B03/B04子集已同步。

QueueView/QueueOccurrence移除分组、+10按钮和details，标题/艺术家各单行省略。每次进入隐藏Played并定位current，下拉按最近到更早逐条揭示（触摸/滚轮），最终position升序；leave/reentry重置，留页current变化保留最早已揭示occurrence及滚动。仅fresh匹配绑定confirmed actual playing/paused的current显示图标。无MANUAL pending且AutoPlay启用只预览第一候选；有MANUAL pending显示全部手动待播、隐藏全部候选；Played不计pending，未改服务端队列或补充策略。

queueActions复用持久TaskActions与共享key，点击所有可见类别按occurrence API；仅pending有长按手柄，350ms激活、local preview、PUT before item。已知revision/current/成员/epoch/generation、断线、离页/取消终止draft，确认后权威重读；未知跨页原key恢复。保留G9-02未送达并发窗口，未增加expected_revision字段。必要共享runtime锁使Queue pending/unknown与Player控制互斥；不更改Player歌词/状态合同或壳预算。未实施Next/Add、删除、清空、保存及其它Batch。

### fresh自动验证（本轮实际执行）

| 范围 | 结果 |
|---|---|
| 新表示RED | 原实现5行为失败：分组、进入未定位、候选全显示、没有下拉揭示、留页历史；最小修正GREEN，metadata原身份/迟到/失败断言保留 |
| 点击/拖动RED | 精确POST/PUT及unknown恢复7行为失败；未绑定控制导致无请求，不是import失败 |
| 审阅修正RED→GREEN | 拖动吞下一次明确鼠标点击、跨页Player未互斥2项；作者另复现排序触摸冒泡同时揭示历史，隔离后GREEN |
| Queue两文件最终 | **25 passed**（queue-view8、queue-actions17），queue-final.log |
| 初次Web目标关系9文件 | 106 passed；修正后受影响Player/Queue/通知/导航6文件74 passed；最终完整Web包含全部关系Gate |
| 后端最窄节点 | reorder仅UpNext、Queue play保留pending、mutation delegates、revision conflict：4 passed |
| 后端指定9文件 | **135 passed**：realtime_queue/history、stop_lifecycle、invariant/API song_play_now、API mutations_playback/idempotency、queue_manager、web_wire_fixture；backend-targets.log |
| 完整后端 | **1443 passed**，118.56秒，full-backend.log；1条既有Starlette/httpx弃用warning，无环境/测试失败，未更改依赖 |
| 完整Web最终 | **214 passed / 19 files**，full-web-final.log；不是复用旧194结果 |
| typecheck / production build | PASSED，T9-QUEUE-A03；83 modules；typecheck-final.log / build-final.log |
| 定向Ruff | 8个既有相关Python owners/proof All checks passed；本轮无Python产品修改，无全仓fix |
| Git | diff --check通过；stat/status与本轮baseline差异已检查，prior B01–B03 dirty保留，无DB/env/依赖进入交付；HEAD14c6239不变，无commit/push/PR/merge |

上述测试有覆盖重叠，不相加称独立总数。日志、开始前Web文件副本和本轮implementation.diff留在ignored `.superpowers/sdd/2026-10-10-task-9-web-batch-plan/queue-revision/`。

### 独立审阅

requesting-code-review/executing-plans要求的独立审阅完成，两项Important已各自行为RED→GREEN并跑受影响回归及最终完整Web；无遗留Critical/Important或本轮deferred Minor。首次审阅调用因额度限制未产生审阅，随后独立审阅成功；不把失败调用当通过。A02遗留details沿用Minor随移除details自然消除，未改其它历史问题。

### LAN与浏览器证据

实际同Wi-Fi手机URL：**http://192.168.3.18:5176/queue**，页面title **MPD-Server · T9-QUEUE-A03**。wlan0当前192.168.3.18；新preview0.0.0.0:5176代理自有127.0.0.1:8004后端，真实Services/新SQLite/MockPort，无live MPD/用户DB。原5175/8003验收进程和数据库保留；本轮自有后端为完善Mock自动前进场景重启一次，旧自有DB亦保留，前端接收新epoch。

HTML及JS/CSS LAN响应逐字节等于本轮dist；JS index-C4xoTOEy.js SHA256 bfa374c1b85d0bf8934f538bff1271d527528321768cf59010806dda24bf14eb；CSS index-DBdJO4nC.css SHA256 2b4038f067be5334723d42dbd0e88a247003ef21437eeda1bfd629c21b0538bb。同源/api/state、所用Song GET200，WS/api/realtime首完整snapshot/protocol1成功。

实际窄屏innerWidth341、Queue clientWidth=scrollWidth309，无横向溢出；标题/艺术家单行，候选/手柄/底部导航可见。浏览器核验进入current首位、滚轮揭示、去Library返回隐藏/scrollTop0、第二重复occurrence精确切换。三场景：single服务端两个AutoPlay候选但UI仅一项；multi-fresh与multi-played UI均隐藏候选。Mock.next后显式调用既有reconcile_external_status采纳已绑定执行前进，UI最早已揭示ID不变、scrollTop203.13479614257812不变，visible15→16，未重定位；这不是live MPD自然结束验收。raw未采纳外部前进曾显示未知/不一致且无确认图标，符合fail-closed。

viewport override已撤销；手机尺寸截图runtime/queue-a03-phone.jpg保留。长按/touch事件自动proof不代替真人手机手感。

### 手机最少操作与剩余Gate

当前场景：confirmed PAUSED current、重复MANUAL pending、Played隐藏，供第一阶段验收；不在用户观察期间自动换场景。

1. 从Library/Settings/Player进入Queue：current首条且有暂停图标、下方待播；从current处向下拉，最近Played先露，再露更早；去Library再回来历史重新隐藏。检查长标题/艺术家单行、无分组/+10/详情，M01/M02/M04。
2. 点current、揭示后点Played、分别点两条同名待播：直接播放目标occurrence，无详情/菜单；播放图标只跟确认current。可去Player暂停再返回观察暂停图标。
3. 长按待播右侧≡后拖到另一待播前/后，松手后服务端结果收敛；current/Played没有排序手柄。未移动松手、拖动途中取消/离页不得误播放；离页再回看结果。
4. 断网观察只读/无确认图标、无排队补发，恢复完整snapshot后可操作；如果遇未知回执，顶部原操作恢复入口可达，H10/M05。结果可按编号简短反馈。

第一阶段反馈后，由agent切single、multi-fresh、Mock已确认执行前进，以及Stop/Context/unknown-stop场景，用户只观察同一URL，无需终端/DB/devtools或未来Batch删除/清空按钮。全部适用H02/M01/M02/M04/M05/H10及生命周期真人反馈前 **B03和本轮B04子集OPEN / HUMAN PENDING**。完整B04未关闭，后续Batch未推进。真实MPD/NAS/DAC NOT RUN，PWA DEFERRED。

已有Song REST含ArtworkRef的500仍单独记录未修复，本轮无封面Mock不当作该缺陷已消除。

## T9-QUEUE-A04：手机反馈后的修正（2026-10-11）

**A03真人反馈未通过**：用户报告播放停在第五秒、暂停继续归零；长按排序不跟手、很难正确拖放。本节取代A03的当前手机交付状态，历史自动证据保留；B03及本轮B04点击/拖动子集仍OPEN / HUMAN PENDING，完整B04未完成。

### 原因与限定修正

手机自有runtime/serve.py误用 `configure_acceptance(... advance_clock=False, w5=True)`，Mock执行位置冻结；前端按有效样本租期停止外推，暂停读取冻结位置。仅启动配置改为 `advance_clock=True`，重启自有8004进程并新建自有SQLite，旧DB/原5175及8003均保留。产品PlayerClock租期、PB-SONG-NOW-001/PB-STOP-LIFECYCLE-001及服务器领域实现未修改。真实MPD/NAS/DAC未测试，不能将fixture修复称为真实设备故障已排除。

原拖动350ms激活、漂移超过8px取消，加上每次move重排DOM改变手指下的目标行。修正为230ms长按容忍自然漂移、浮层随指针移动、原列表几何稳定、插入提示不占行高、内容边缘自动滚动。无效落点清除上一次有效目标；释放前按pointerup实际坐标重新hit-test；浮层位于共享通知层下方、pointer-events:none。仅pending可拖、精确queue_item_id/before_queue_item_id、隐藏候选不变、权威确认/重读、原key恢复及断线/离页/revision取消均保留。

### fresh自动及本地验证

| 范围 | 本轮实际结果 |
|---|---|
| 行为RED→GREEN | 长按漂移取消、有效move后无效目标误提交；独立复核另发现release坐标旧目标，精确新增测试RED→GREEN |
| Queue两文件 | 30 passed（queue-view8 / queue-actions22）；新增5项含跟指/稳定列表、无效落点、边缘滚动停止、隐藏候选邻接提示、释放坐标 |
| Queue/通知/导航关系4文件 | 39 passed；移除body Teleport、浮层留在shell内z10 / AppBar z20后重跑通过；测试DOM定位随浮层owner调整，保留存在/移动/清除断言 |
| 完整Web最终 | 219 passed / 19 files，a04-full-web.log；不是沿用A03/旧194结果 |
| .venv环境 | Python3.14.4 / pytest9.1.1 / ruff0.16.9可执行；无环境/依赖修改 |
| 验收时钟 | 既有test_w4_fixture_advances_only_playing_and_preserves_pause_resume_seek_target单节点1 passed，随后test_web_acceptance.py整文件3 passed |
| 后端指定关系Gate | 142 passed，a04-backend-targets.log：A03指定9文件再加test_playback_control_target.py；仅既有Starlette/httpx弃用warning。本轮未改Python产品代码，未重跑完整1443，不称旧全量为新结果 |
| HTTP实际时钟loop | 播放样本0.099→7.405秒；暂停8.175保持稳定，resume target后9.116；PASS超过5秒/暂停不走/继续不归零。loop等待实际timed sample，不将mutation后的短暂None当成零 |
| Web typecheck / build | PASSED；83 modules；最终JS index-DVSCWN3A.js / CSS index-DQbD2oky.css |
| 独立复核 | release坐标问题已修正，复核精确节点1 passed，未发现剩余明确Critical/Important；真人手感未冒充通过 |

### LAN与浏览器

实际URL **http://192.168.3.18:5176/queue**，title **MPD-Server · T9-QUEUE-A04**。同Wi-Fi刷新后检查label；preview同源8004自有Services/SQLite/Mock，无真实音频输出。LAN HTML/JS/CSS逐字节等于最终dist：JS SHA256 `da6f01593be9e1e24118de27bdc31e8068fa6fdc024c59dfa5d5d35bb1d93e9b`，CSS `1d57a73eb5b0866ed78e0426011db13b424646a7286216f5816f6b0ddddf0005`。

浏览器Player显示51→65秒，暂停保留约65秒，继续后91秒。最终窄屏375px，Queue clientWidth/scrollWidth均343，无横向溢出。浏览器实际拖动第二个同名长曲occurrence `cefb638b-d9fb-58f5-bea5-bdccc7786724` 到待播首位，操作确认；同源/api/state验证MANUAL顺序精确改变、四个隐藏AUTOPLAY候选仍存在。浏览器指针拖动不替代真实手机触摸手感验收。截图runtime/queue-a04-phone.jpg，临时viewport已撤销。

### 最少手机复测

1. 在A04刷新页面，点歌曲播放，去Player看进度持续超过10秒；暂停等两秒再继续，应接着原进度走。反馈是否仍停5秒/归零。
2. 长按待播右侧≡约四分之一秒，观察浮层跟随手指；拖到另一待播前/后，松手确认目标；移到current/列表外松手应撤销。有长列表时在内容边缘检查滚动；反馈跟手与落点是否可用。

这两项反馈前不关闭Gate；其余A03未完真人项仍须完成。未实施删除、清空、保存、Next/Add或其他Batch，未commit/push/PR/merge。批次外ArtworkRef单Song500保持单独未修复记录。

## T9-QUEUE-A05：顶部通知限定修正（2026-10-11）

用户反馈A04播放/排序“别的没有问题，也不要改动了”；这两项手机修正已获反馈通过。用户另指出appbar蓝色感叹号累积每次拖动成功结果，要求当前临时通知、同步成功消失、未解决异常才有恢复操作。只修正此通知生命周期，不重新实现或调整Queue、Player、服务端与其它Batch。

原Visual“已完成结果图标”及AppShell对所有task records生成notice的做法与新要求冲突；已同步WEB-UI-NOTIFY-001/audit/Batch Plan。AppShell只投影busy与未解决记录：正常处理中/同步spinner，不附恢复按钮；confirmed且重读成功撤下notice；unknown/failed/readFailed仍保留身份与适用的原key retry/只重读。taskActions不会在epoch切换时把已同步成功记录变为retired通知；内部完成intent身份仍保留既有防重复语义，不用于展示日志。不新增错误超时秒数，不吞并发未解决事项。

fresh行为RED为四项：成功常驻/正常同步附重读/读失败恢复后不清/旧成功可复活；global-notices新合同10项GREEN，受影响Queue/Player/壳五文件69 passed，完整Web **221 passed / 19 files**（a05-full-web.log），typecheck/build83 modules通过。中间notice自读写watchEffect引发的递归被测试捕获，已改为仅监听task entries的watch，重跑文件/关系/完整Web均零未处理错误。独立只读复核10项通过，无遗留明确问题。后端未改，既有web_wire_fixture **3 passed**，仅既有Starlette/httpx弃用warning；未把历史1443/142结果当本轮新验证。

LAN **http://192.168.3.18:5176/queue**，title **MPD-Server · T9-QUEUE-A05**，同源HTML/JS/CSS与dist逐字节一致：JS index-JHD-HYCS.js SHA256 `d9709bda1c8fd39f133d36cc9c41c90be701ba061fb0cde5a07eb45e2210c566`；CSS index-DQbD2oky.css SHA256 `1d57a73eb5b0866ed78e0426011db13b424646a7286216f5816f6b0ddddf0005`（与A04相同）。浏览器实际拖动一次后确认排序生效，观察收敛后 `.status-toggle`不存在、notice-entry=0、status-description为空；去Library再回Queue仍无成功记录。手机截图runtime/queue-a05-notice.jpg，viewport已撤销；未重启自有Mock/删DB/修改环境，未使用live MPD。

本轮最少真人项只有：刷新A05，拖动成功并同步收敛后顶部图标应消失，点击不再看到历史成功操作；当前未解决异常仍应有对应恢复。其他已接受行为保持，不要求重测播放/拖动手感。A05 HUMAN PENDING；未提前关闭完整B03/B04 Gate，不将未实施B04范围记为完成。所有既有dirty保留，diff check通过，HEAD14c6239不变；无commit/push/PR/merge。批次外ArtworkRef问题仍未顺带修复。

## 2026-10-11 最终用户验收关闭记录

用户明确反馈：“可以了。验收通过。总结一下把b4的提示词给我”。结合此前A04“别的没有问题”反馈，当前交付范围的真人验收已接受：B03 Queue展示与交互修正、必要B04精确occurrence点击播放/待播拖动子集、A04验收时钟与手感修正、A05顶部临时通知修正。**B03 CLOSED；B04点击/拖动子集 CLOSED；A05 HUMAN PASSED。完整B04未完成，剩余Next/Add、删除、清空、保存未开始。**

关闭依据是既有fresh自动证据及用户本次明确整体验收，不额外编造逐场景真人日志或新的测试结果。最新Web221/typecheck/build、后端wire3与独立通知10证据见A05；A04关系142/fixture3及A03完整后端1443分别属于其原轮次。真实MPD/NAS/DAC NOT RUN，PWA DEFERRED，批次外ArtworkRef缺陷仍单独未修复。

用户本轮仅要求总结与下一批提示词，不授权在本轮执行B04剩余实现。现有未提交修改全部保留，feature/task-9-web / HEAD14c6239；无commit/push/PR/merge。后续B04以此最新关闭记录为前置，不重做已接受的Queue/播放/拖动/通知，也不把子集关闭当完整B04完成。
