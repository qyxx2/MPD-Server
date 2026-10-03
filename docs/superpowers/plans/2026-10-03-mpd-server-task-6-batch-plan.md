# MPD-Server Task 6 Contract Audit / Batch Execution Plan

> **For agentic workers:** 后续执行使用 `superpowers:executing-plans`；本轮仅 Contract Gap Resolution / planning。所有 Batch 未执行。没有 commit/push/PR 授权；不得因下列实施白名单而在本轮修改 production code。

**Goal:** 传播已确认的权威状态，以完整快照恢复客户端，同时保持既有 Playback/Queue/History/Library/Playlist/Output 业务合同。

**Architecture:** Service 提供一致读取和只读外部观察；共同提交边界关联数据、revision、失效登记；WebSocket 只交付 initial snapshot 和 invalidation。领域恢复属于 PlaybackService / Task 4 corrective。

**Tech Stack:** 当前 FastAPI/Pydantic/SQLite/asyncio/pytest；Linux ARM64 既有 `.venv`，无新增依赖、schema migration 或 Docker 要求。

**Spec / authority aliases**（路径相对本文件）：

- A：`../specs/2026-09-25-system-and-development-architecture-design.md` §5/§7/§12.1–12.3/§19.5。
- P：`../specs/2026-09-24-playback-model-queue-semantics-design.md` §2.2.1/§6–8.8。
- L：`../specs/2026-09-24-library-playlist-tag-search-design-2-1.md` §2/§5/§7.1/§9。
- O：`../specs/2026-09-24-system-architecture-playback-output-design.md` §6.1–6.3/§8.1。
- M：`2026-09-25-mpd-server-v0-1-implementation-plan.md` Task 6、Dependency Matrix、Relationship-Test Matrix、Contract Matrix Gate。
- T5：`../archive/task-5/2026-09-29-mpd-server-task-5-batch-plan.md` §3；对应 2026-10-01 contract-architecture-corrective acceptance、pre-batch6 AB/CD corrective plans。
- T4：`../archive/task-4/2026-09-28-mpd-server-task-4-batch-plan.md`；Batch 2/4/6 acceptance、2026-09-30 playback-service corrective plan/acceptance。
- T7：`2026-10-02-mpd-server-task-7-batch-plan.md` §4；O-* 合同保持。
- T1–3：M Task 1/1R/2/2R/3；`../archive/task-3/2026-09-27-task3-corrective-followup-plan.md`；`../archive/integration/2026-09-29-mpd-server-task-0-4-integration-gate-acceptance.md`；`../../mpd-0.23.5-capabilities.md`。

## 1. 状态与范围

**CONTRACT FREEZE COMPLETE / Contract Gap = 0 / BATCH PLAN READY IN DEPENDENCY ORDER / IMPLEMENTATION NOT STARTED。**

2026-10-03 重新审计基准：分支 `feature/task-7-output-manager`，HEAD `8abc8fb`。本轮开始已有 M 的 Task 6 blocked 修改和本未跟踪审计文件；并非 clean worktree。本轮保留其审计来源，不能把原审计记录的“开始时 clean”当作本轮状态。

五个 Gap 均由当前对话明确选择 A 后写入唯一 authoritative Spec；没有从代码推定产品语义。原 contract-freeze blocked 已解除。**D6-RECOVERY 尚未验收**：自动恢复启用与最终 Batch 13 受 Task 4 自然结束/外部恢复专项验收约束；Batch 1 不依赖该能力。合同闭合不等于该 corrective 已实现，不等于 Task 6 功能完成。

- [x] 重新核对 authority、当前代码/测试、Git 与历史合同。
- [x] 完成当前对话 G6-01–05 决策并写入 Spec。
- [x] 冻结 Matrix、更新全局 relationship/dependency、重新推导 Batch。
- [x] 完整 Task-level Contract Audit：所有合同有 authority、owner、proof obligation、验收门禁。
- [ ] Batch 1–13 的实现、RED/GREEN 与 Task 6 acceptance。
- [ ] D6-RECOVERY 的独立领域能力验收（本轮不执行）。

**Global Constraints**：API→Service→Repository/PlayerPort；Service 不依赖 socket/concrete MPDAdapter；真实曲库只读；沿用 outer transaction、runtime rollback、terminal replay；网络不在 DB 锁内；不实现 Task 8–12、CLIENT_STREAM、最终配置/备份/部署；不改 frozen REST 字段或播放规则；不提交环境/DB/cache/本地 AGENTS 文件。

**Review Focus**：

1. commit 后、原异步 callback 前取消或发生第二次 mutation：版本可见且最后变化不能永久漏通知（B1/B2/B11）。
2. Library 无变化扫描仍有 completion/error，但版本不增；availability 变更保留 Playlist/History（B2/B7）。
3. 同 URI 的不同 occurrence、切歌后迟到 progress，不得串曲（B8）。
4. 初始 snapshot 发送期间最后一次 mutation，之后无事件，仍可恢复（B11）。
5. 慢连接/队满/断线不能阻塞正常连接或回滚 terminal success（B12/B13）。

Task-level Relationship Gate 与 Contract Matrix Gate 均 **REQUIRED**。每个 Batch 同样 REQUIRED，未用 full-suite 替代关系测试。

## 2. 原始 Gap 证据、判定与人工决策

| Gap | 原始 authority / 不能唯一推导的部分 | 既有 authority 唯一确定的部分 | 当前对话最终决定 / 正式 authority |
|---|---|---|---|
| G6-01 snapshot | A §12、O §8.1、M Task6 只要求完整当前状态，未定义跨域切面或本地读取失败降级 | A §5/§19.5、TX-ROLLBACK-001 禁止绕过 Service/提交边界；O §6.2 明确 DB 锁不能冻结 MPD | A：本地数据/runtime/revisions 同一已提交切面；本地必需域失败整体失败；外部明确 stale/unknown/error；补充A：Context只恢复context_id+当前Queue顺序，不新增完整对象持久化；A §12.1/§12.3 |
| G6-02 revisions | M 要求 Library/Playlist revisions，未定义持久性、no-op、重启、递增粒度；Queue revision 不能代替 | L §2/§5.2 定义 Favorites 属 Playlist；TX-IDEMP/ROLLBACK 保持回滚与 replay 无重复 mutation | A：进程 epoch + 两域实际内容计数，每 outer commit 每变化域最多 +1；no-op/rollback/replay 不增，重启新 epoch；L §7.1 |
| G6-03 delivery | A §12/O §8.1 未定义 wire、subscribe/capture race、顺序及背压 | O §6.3 规定 post-commit、失败不撤提交、无 durable/exactly-once；重连必须完整恢复 | A：initial snapshot + live invalidation + GET /api/state；共同交接边界、顺序水位、有界队列、溢出/超时断开重连；A §12.2 |
| G6-04 History | A §12 的“History 可用状态”未定义是否有记录/健康/可播放；不是 bool(list_history()) 的实现授权 | P §2.2/§7、T4 History、Task2R 保留引用要求永久 History/active/Played 独立，unavailable 不抹掉事件；T5 §3.4 冻结事件 REST | A：has_entries + active_event/session；has_entries 仅持久事件存在性，unavailable 事件仍返回，当前歌曲资料由 Library 查询；P §2.2.1 |
| G6-05 observation | A §12 的进度/状态要求、P §8.7/O §8 的恢复要求与 M 原 transport-only 存在范围张力，未指定 loop owner | MPD 实际状态经 Port 确认；PlaybackService 业务权威；P §6/§7/PB-HISTORY-001 禁止 natural=Stop | A：Task6 只读 Service observer/传播；领域恢复由 Task4 corrective，自动恢复/最终验收前满足 D6-RECOVERY；P §8.8、A §12.3、O §8.1、M |

**没有一个完整 Gap 能仅凭旧 authority 唯一闭合。** 上表第三列是继承部分；新增选择全部来自用户 A/A/A/A/A（G6-01 Context 补充也选 A），旧候选不再作为未批准方案存留。DTO再审计发现前置没有完整Context读取/持久模型后，已当场追加G6-01最小决策；用户选A，删除了草稿中未经确认的完整Context恢复承诺，未以代码缺少接口直接裁定产品范围。唯一文档范围张力 G6-05 已由显式选择修订 M；没有默选冲突方。当前 `reconcile_external_status()` 将 STOPPED→History.stop 的代码与自然结束区分要求不符，作为能力风险进入 D6-RECOVERY，不能把代码升级为 authority。

## 3. 当前实现证据与依赖审计

所有相对 `server/app/` 的源码位置均重新读取；当前存在不等于未来合同已实现。

| 文件/接口 | 当前事实及 Task 6 必需工作 |
|---|---|
| `services/events.py` | DomainEvent/EventPublisher.publish、LibraryChangedEvent(result/mpd_update_error)、OutputChangedEvent(深复制 snapshot) 已存在；没有订阅协调器或其他域事件 |
| `repositories/database.py` | run_transaction 同库嵌套、BaseException rollback、runtime hooks；on_transaction_commit 在释放锁/context 后执行。现有 hook 不足以独自保证新数据与内存版本共同可见；B1 增加同步可见性登记，保持原异步 hook 语义 |
| `services/idempotency_service.py` | outer unit-of-work 包含业务、响应 materialization 和 terminal；replay 不再次业务执行，必须继承 |
| `services/library_scanner.py` | scan_full/scan_paths 在 repository 返回后 _finalize；嵌套事务返回不等于 outer commit，B2 修正接线；可保持原完成事件 payload |
| `services/playlist_service.py` | CRUD/Favorites/save_queue_as_playlist 已有，无 revision/publisher；批量创建需同一 outer 边界 |
| `services/playback_service.py` | transport/Queue/transition/确认/reconcile 已有，无 publisher；不能在包含 run_output_operation 的通用装饰器无差别发播放事件 |
| `services/queue_manager.py`、`models/queue.py` | get_playback_state/list_items、Repository QueueSnapshot(revision,items) 已有；新增 Service facade，不能 gateway 直读 repository |
| `services/history_service.py`、`api/history.py` | list_history/list_played/active_event/session_id 已有；永久 API 返回事件，无歌曲内嵌副本。B7 明确 has_entries 与 unavailable 关系 |
| `services/output_manager.py` | get_state 经共同 operation runner 读取；set_enabled 已确认/commit 后 event。沿用 observed/request/null/stale，B9 新增缓存读取/观察接线，不重做控制 |
| `player/ports.py`、`player/models.py` | status/queue_entries/outputs 与 typed error 已有；PlayerStatus 带 elapsed/duration/song_id/position；没有可直接当生产 observer 的 loop，Mock event 不能证明真实 observer 已存在 |
| `main.py` | lifespan/output publisher injection 已有；LibraryScanner 尚未传统一 publisher，未有全局 realtime/observer wiring |
| 尚不存在 | state_service.py、api/realtime.py、FullStateSnapshot、realtime tests；均在 §6 分配 **TO CREATE** owner |

T1/1R verified capability record 只证明已验证命令，不证明外部自然结束可可靠分类；不调用 live MPD 重新探针。T2R identity/availability、T3 scan ordering、T4 History reasons/Queue CAS、T5 11 rows、T7 Output 合同是 regression 输入。

**Dependency Matrix 变化**：基础 Task3+4+5+7 不变；新增阶段性 D6-RECOVERY（Task4 corrective → 自动恢复启用/Task6 final acceptance）。不新增 Task8+ 依赖，不把 corrective 混入 socket Batch。若专项审计暴露尚无 authority 的领域恢复策略，必须在该领域工作中按既有合同规则处理；本 Task6 已明确只报告漂移，不能凭此擅自恢复。

D6-RECOVERY 的验收义务：真实 Services/Repository/MockPort 证明自然完成与显式 Stop 分别记录、AutoPlay/可用 successor 遵循原合同、无法确定原因不伪造 History、外部状态转移经确认且历史恰一次、失败恢复 persisted/runtime、retry/replay 无重复。验收记录必须给出实际 test 路径/函数、命令和 fresh GREEN；方法存在、历史全套 GREEN 或新计划本身不算通过。

## 4. 冻结 Contract Matrix

### 4.1 共同字段（逐 row 引用，是 row 的组成部分）

- **U / Must Remain Unchanged**：只读/传播不改变 Queue occurrence/order/revision、PlaybackContext、Playlist/Favorites、持久 History/active/session、terminal 或 MPD 控制；领域 producer 仅允许原 frozen operation 的 delta。观察缓存/epoch/传播计数是明确允许的新 runtime 状态。
- **T / Transaction Boundary**：同库 outer transaction + runtime rollback；成功后同步登记可见版本/失效义务；网络/异步领域通知在 DB 锁外。API response/terminal failure 仍可令尚未提交业务回滚。
- **F / Failure-Rollback**：提交前失败/取消不留成功版本/事件；提交后交付失败不撤提交/terminal；SQLite 不假装撤销外部作用。
- **I / Retry-Idempotency**：沿用原 key/scope/payload 合同；失败重试重新执行，成功 replay 不重做领域操作/版本；read/reconnect 不重放 mutation。
- 每个新增 row 的 **Executable Invariant Proof** 在下方指定最终 owner；所有新增 proof 均 **TO CREATE / NOT RUN**，矩阵冻结不冒充 executable GREEN。

### 4.2 新增 rows（11 个；旧 8 个稳定 ID 保留，新增 3 个）

**RT-SNAPSHOT-001 — REPRESENTATION / capture，A §12.1/§12.3**
- Preconditions：前置 Services 存在，允许空态/外部断线。Authorities：领域 Services + 持久/runtime；StateService 只聚合。
- Expected Delta：完整深复制 DTO，本地联合切面、外部显式 freshness。Unchanged：U。
- External Confirmation：仅消费 Service 已确认观察，不宣称物理原子。History/Event：读取无业务成功事件。
- Transaction：T 的读取切面；Failure：本地必需读取失败整体失败，外部可降级；Rollback：读取不撤业务。
- Retry：I 的重读；Revision/Ordering：同切面 marker，旧 snapshot 不覆盖新水位。
- Observable：A §12.3 完整字段、unknown/null 保留。Proof：B7 `test_snapshot_is_one_committed_cut`、B10 HTTP 503、B13 综合 final proof。

**RT-REVISION-001 — TRANSACTION / version visibility，L §7.1**
- Preconditions：初始化后进程 epoch 已生成、合法领域写。Authorities：domain semantic before/after、outer commit、coordinator。
- Delta：每 outer commit 每实际变化域 +1，sequence 对失效义务排序。Unchanged：U，未变化域及 Queue CAS 不变。
- Confirmation：持久 commit；History/Event：no-op 可有 scan completion，但不能伪造内容变化。
- Transaction：T；Failure/Rollback：F；Retry：I。Revision：新 epoch、两域从0，跨 epoch 不比较，改后恢复 no-op。
- Observable：snapshot/event 携匹配版本。Proof：B1 `test_committed_data_and_revision_become_visible_together`，B2/B3 real producer commit/no-op/rollback/restart；final owner B3，B13 regression。

**RT-LIBRARY-001 — STATE_PROPAGATION / scan，A §7/§12.2、L §7.1**
- Preconditions：direct 或 HTTP outer scan。Authorities：只读文件源、Library Repository/scanner、outer owner。
- Delta：已提交内容失效 + completion 结果/MPD update error。Unchanged：U、Song/Playlist/Favorites/History 引用及源文件。
- Confirmation：DB commit；optional MPD update 不等于扫描事务。History/Event：保留原 LibraryChangedEvent；completion 必须 commit→optional update→event。
- Transaction：T，内容登记不能等待 optional update。Failure/Rollback：F，update 失败保留提交/可见错误。Retry：I。
- Revision：实际内容变化才 +1；延迟 completion 不使版本倒退。Observable：新数据匹配版本、原结果事件。Proof/final owner：B2 `test_outer_scan_waits_for_commit_and_keeps_completion_order`。

**RT-PLAYLIST-001 — STATE_PROPAGATION / CRUD/Favorites/save，L §5/§7.1**
- Preconditions：合法 mutation；Favorites 固定 Playlist。Authorities：PlaylistService/Repository/outer owner。
- Delta：完整提交资源的联合失效。Unchanged：U、unavailable membership/order、Library Song 内容。
- Confirmation：独立读取能见提交；无 MPD。History/Event：新 PlaylistChangedEvent 仅已提交变化。
- Transaction：T，save_queue 一次变化不暴露逐成员。Failure/Rollback：F，包括校验/terminal；Retry：I。
- Revision：L §7.1；Library 元数据不算 Playlist 成员 delta。Observable：最新资源+版本。Proof/final owner：B3 `test_playlist_versions_follow_outer_delta_and_replay`。

**RT-PLAYBACK-001 — STATE_PROPAGATION / committed playback/queue/history，P §3–8、A §12.2**
- Preconditions：原操作已确认并 outer commit。Authorities：PlaybackService/Queue/History/PlayerPort。
- Delta：联合 changed domains 的失效；不增加播放转移。Unchanged：每个 PB-* 原保留关系与 U。
- Confirmation：继承原 PlayerPort 确认；ACK 非确认。History/Event：传播不再产生 History，联合转移不发半成品。
- Transaction：T；Failure/Rollback：F；Retry：I。Revision：业务 Queue CAS 不变，传播 sequence 独立。
- Observable：pause/seek/stop、queue-only、current transition 各有变化通知。Proof：B4 transport、B5 queue-only、B6 current/history；final owner B6 `test_transition_notification_matches_committed_history`；之前不得 COMPLETE。

**RT-OUTPUT-001 — STATE_PROPAGATION / Output bridge，O §6.1–6.3、A §12.3**
- Preconditions：已确认并提交控制事件，或只读 Output observation。Authorities：OutputManager/PlayerPort，网络非事实源。
- Delta：output 失效/缓存同步。Unchanged：O-PRESERVE-001/U，旧 terminal 回执。
- Confirmation：既有回读；observer 不发控制命令。History/Event：控制成功与 observation 分离，不制造歌曲事件。
- Transaction：T 用于控制；观察接受受同一 capture 边界保护。Failure：F、stale/null 保留；Retry：I/重新读取。
- Revision：sequence 变化不 bump Library/Playlist/Queue。Observable：observed/request 分离及 freshness。Proof/final owner：B9 `test_output_control_and_observation_share_delivery_without_history`。

**RT-HISTORY-001 — REPRESENTATION / availability，P §2.2.1**
- Preconditions：空/active/持久事件及歌曲 availability 变化。Authorities：History persisted/runtime、Library current Song。
- Delta：has_entries/active/session 只读表示。Unchanged：U、永久事件身份与 reason、不按 playable 过滤。
- Confirmation：已提交历史事实；无 MPD。History/Event：仅 active 时 has_entries=false；scan 不制造播放事件。
- Transaction：T 一致读取；Failure：读取失败整体失败，rollback 无暂态泄露；Retry：I read。
- Revision：没有新 History revision；Library availability 使用 Library revision。Observable：原 REST 事件仍返回 unavailable 歌曲，资料由 Library 查询。
- Proof/final owner：B7 `test_history_unavailability_preserves_events_and_has_entries`，对照真实 scanner/API/Service。

**RT-OBSERVE-001 — LIFECYCLE / read-only playback/output observation，P §8.8、A §12.3**
- Preconditions：注入 verified PlayerPort/Service/clock；不假定已有 observer 或可信 occurrence binding。Authorities：MPD 实际 transport，PlaybackService 业务会话，OutputManager 输出事实。
- Delta：确认匹配样本或 stale/unknown/reconciliation_required；单进程 loop。Unchanged：U，尤其不因 STOPPED 调 History.stop。
- Confirmation：actual occurrence/业务代次校验，无法确认则 unknown，不凭 URI。History/Event：观察失效不是业务成功。
- Transaction：采样接受与 mutation/capture 串行校验；不新增领域事务 delta。Failure：保留 stale/未知；取消关停释放，不停止播放。
- Retry：每轮完成后1秒，预算5秒，无重叠；age>6秒 stale。Revision：只观察内容变化推 sequence，非单纯时间戳刷新。
- Observable：独立 observation DTO、断线错误、匹配进度；领域恢复由 D6-RECOVERY。Proof：B8 occurrence/进度，B9 lifecycle；final owner B9，最终验收仍受 D6 gate。

**RT-CONNECT-001 — LIFECYCLE / initial handoff，A §12.2**
- Preconditions：StateService/coordinator 注入，v0.1 无鉴权。Authorities：Service state、订阅生命周期。
- Delta：注册、capture、首帧完整 snapshot，随后 live。Unchanged：U。
- Confirmation：消费 snapshot；不从 socket 查 MPD。History/Event：连接无业务事件。
- Transaction：订阅先于capture且共同边界；网络锁外。Failure：本地 capture 失败1011，无成功首帧，清理资源；不撤业务。
- Retry：新连接全量；Revision：水位覆盖，最后变化不丢，迟到callback不倒退。
- Observable：首帧 snapshot 后 invalidate。Proof/final owner：B11 `test_last_mutation_during_initial_send_is_not_lost`。

**RT-DELIVERY-001 — TRANSACTION / delivery isolation，A §12.2**
- Preconditions：正常与阻塞/断开连接并存。Authorities：commit owner、独立 client sender。
- Delta：交付或失效连接清理。Unchanged：U/已提交 terminal/其它连接。
- Confirmation：send非应用ACK。History/Event：失败不可重做业务补偿。
- Transaction：网络锁外且不被业务await；Failure：64帧上限/10秒timeout，1013关闭恢复，记录错误；不rollback。
- Retry：重新连接完整snapshot，无遗漏重放；Revision：通知顺序/重复覆盖规则。
- Observable：正常连接继续、mutation成功独立。Proof：B1登记隔离基础；final owner B12 `test_overflow_and_timeout_isolate_clients_and_preserve_commit`。

**RT-RECOVER-001 — STATE_PROPAGATION / reconnect，A §12.1–12.3**
- Preconditions：断线期间各域合法变化，允许活跃播放/进程重启。Authorities：当前 Services 与新 snapshot。
- Delta：完整替换旧表示。Unchanged：U，无业务重放。
- Confirmation：fresh/stale来自Service样本；无旧事件推断。History/Event：遗漏增量不作为恢复机制。
- Transaction：继承 snapshot/connect；Failure：读取失败不是恢复成功，断开可重连，不发旧缓存伪全量。
- Retry：I；Revision：同epoch单调、跨epoch清基准。Observable：全部 A §12.3 字段恢复。
- Proof/final owner：B13 `test_reconnect_replaces_all_domains_and_epoch`；不实施 Task8 client store。

### 4.3 继承/修改/回归分类

**新增**：上列11 rows（原审计8 + RT-REVISION/HISTORY/OBSERVE-001）。**修改既有 frozen 业务语义 rows：无**。EVENT-PORT-001、O-EVENT-001 的实现接线扩展，不改变原 payload/确认/提交语义。

| 继承 ID | Authorities / precondition / allowed delta | Preservation / confirmation / History-event | Transaction / failure / retry / observable / existing proof |
|---|---|---|---|
| EVENT-PORT-001 | Service 发布 DomainEvent，经注入 publisher | 无 socket 反向依赖；原 Library/Output payload 保留 | producer outer boundary；非 durable；失败不伪成功；`integration/test_task3_events_and_mpd.py`、`invariants/test_output_event_transactions.py` |
| TX-ROLLBACK-001 | DB/runtime History/terminal 同库 unit-of-work | 无 phantom History/terminal；外部副作用不被假装撤销 | outer BaseException rollback/runtime restore；retry reconciliation；`invariants/test_transaction_relationships.py` |
| TX-IDEMP-001 | key+scope+canonical payload 首次提交/replay | replay不重复业务/History/event；需先确认成功 | terminal与业务同事务；失败无success，冲突409；`api/test_idempotency.py`及 transaction invariant |
| O-EVENT-001 | OutputManager 确认后发布深复制态 | O-PRESERVE 不变，不造 History | outer commit锁外，rollback丢通知，publish失败日志，replay不重发；`invariants/test_output_event_transactions.py` |
| O-STATE-001 | MPD observation / request 分离 | 不拿目标/旧回执作fresh；null/stale保留 | read不控制、失败stale；`invariants/test_output_observation.py` |
| PL-REP-001 | persisted membership/order →全部资源表示 | AVAILABLE/MISSING/UNREADABLE均保留；非Collection过滤 | 原mutation事务/失败/replay；`invariants/test_playlist_relationships.py` |

Regression-only：PB-STOP/INSERT/REORDER/DELETE-PENDING/DELETE-CURRENT/NEXT-UNAVAILABLE/HISTORY-001、PL-COLLECTION-001、O-PRESERVE-001。逐字段 authority 仍为 T5 §3.7/T7 §4；本计划的 U/T/F/I 不覆盖其业务 delta。精确 regression 命令在 §5，各 Batch 指定集合，不能只跑全套代替。

## 5. 可复用验证命令与实施纪律

以下全部从仓库根目录执行；`T(file)` 是记法，执行时展开为 `.venv/bin/python -m pytest -q server/tests/<file>`；`T(file::test)` 为同一命令的精确选择器。不存在的测试在相应 Batch 明确 **TO CREATE**，不能把命令存在当作测试已实现。

| 集合 | 精确命令 |
|---|---|
| R-TX | `.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py` |
| R-LIB | `.venv/bin/python -m pytest -q server/tests/integration/test_task3_events_and_mpd.py server/tests/repositories/test_library_reconciliation.py server/tests/services/test_library_scanner.py server/tests/api/test_library_api.py` |
| R-PL | `.venv/bin/python -m pytest -q server/tests/invariants/test_playlist_relationships.py server/tests/services/test_playlist_service.py server/tests/api/test_playlist_reads.py` |
| R-PB | `.venv/bin/python -m pytest -q server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_playback_service.py` |
| R-H | `.venv/bin/python -m pytest -q server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/repositories/test_task2_steps_5_7.py` |
| R-O | `.venv/bin/python -m pytest -q server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_lifecycle_injection.py` |
| R-ARCH | `.venv/bin/python -m pytest -q server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories` |

每个 Batch 下列步骤独立执行；不能把一次全套测试当作所有 RED/GREEN：

- [ ] 重读其最小 authority/依赖与生产白名单，确认前置 Batch 验收。
- [ ] 创建指定最小 RED test，运行精确 selector，确认因目标合同缺失而失败。
- [ ] 在白名单内最小实现接口与行为；遇到 scope/合同变化停止扩展并修订相应 authority。
- [ ] 重跑该 selector GREEN，再跑该测试文件、列明的其它 proof 文件与 R-*。
- [ ] `.venv/bin/python -m ruff check <本Batch实际修改的Python文件>`；`git diff --check`、实际 diff/stat/status 核对无无关/依赖/环境/DB变更。
- [ ] 逐 Owned/Relied/Regression ID 验收；跨 Batch row 到 final owner 前保持 PARTIAL。提交须用户另行授权。

## 6. 重新推导的 Batch Execution Plan

顺序来自最终合同：共同提交/顺序基础 → 各 producer → 本地聚合 → 只读观察及生命周期 → API → 交接 → 网络故障 → 全恢复验收。这里未沿用原审计 §6 的 Step 类别作为现成边界。

新文件统一在首次 owner 标记 **TO CREATE**；后续 Batch 修改它们。下列生产白名单只授权未来相应 Batch；任何额外文件须重新核对范围。所有 Backend proof 放 `server/tests/invariants/`，endpoint proof 放 `server/tests/api/`。

### Batch 1 — 提交与版本/失效登记的共同基础

依赖：现有 TX hooks，不依赖 D6-RECOVERY。原 Step2 的先决基础。读取 A §12.1–12.2/L §7.1、database/idempotency、现有 commit tests。

Owned：RT-REVISION-001 interface/core；RT-DELIVERY-001登记隔离子合同。Relied：TX-ROLLBACK/TX-IDEMP/EVENT-PORT-001。Regression：O-EVENT-001。

生产白名单：修改 `server/app/repositories/database.py`、`server/app/services/events.py`；**TO CREATE** `server/app/services/realtime_coordinator.py`、`server/app/models/realtime.py`。不接 socket/observer/所有业务 producer。

Interfaces：保留 `on_transaction_commit(path, callback)` 锁外异步语义；新增 `on_transaction_visible(path: str, callback: Callable[[], None]) -> None`，在 commit 成功后/锁释放前同步登记，不执行网络；callback异常不能撤提交/调用rollback hooks，必须记录、使订阅失效且将coordinator标为不可提供可信snapshot，按A §12.2重新建立epoch前不能返回旧marker配新数据。`RealtimeCoordinator.stage_change(domains: frozenset[str], before: object, after: object) -> None` 仅在活动事务内暂存第一 before/最后 after；`marker() -> StateMarker` 返回 epoch/sequence/revisions 深复制；`publish(event: DomainEvent) -> None` 消费旧领域事件，不把迟到payload当当前状态。StateMarker/Invalidation 在 models/realtime.py 定义；注入 DB path，不让 gateway 持有 repository。实现使用现有同库边界，不引入另一把可能反序的业务锁。

**TO CREATE** `invariants/test_realtime_commit_visibility.py`；最小 RED：`test_committed_data_and_revision_become_visible_together`。barrier 暂停原异步 callback，另一事务读新业务数据时必须同时见新revision；失败/outer cancel无增量；改后恢复no-op；两个事务回调倒序不能倒退；commit后取消仍登记最后变化；登记失败使订阅失效且snapshot失败、terminal保留，新epoch初始化后才能恢复可信marker。

验证：`T(invariants/test_realtime_commit_visibility.py::test_committed_data_and_revision_become_visible_together)` → 全文件 → R-TX/R-O/R-ARCH。验收：真实SQLite而非仅 fake publisher；旧异步hooks测试保持GREEN。RT-REVISION在真实producer B3前不 COMPLETE。

Complexity：2关联rows/DB→coordinator→event 3边界/commit-rollback 2状态转换；persistence+runtime，无外部/API；4生产文件、约180–300新增实质LOC；单窗口可审阅，反馈定位在commit-visible，不混入domain mutation。

### Batch 2 — Library 内容版本与扫描完成传播

依赖B1；原Step2。读取 L §7/§7.1、A §7/§12.2、T3 scan ordering、scanner/repository/scan API。

Owned RT-LIBRARY-001、RT-REVISION-001 Library部分；Relied EVENT-PORT/TX-*；Regression Task2R references/PL-REP-001。

白名单：`services/library_scanner.py`、`services/library_service.py`、`repositories/library_repository.py`、`services/events.py`（均 server/app/）。仅增加内容before/after读取与outer finalize接线，不改parser身份匹配/歌词/原文件。新增 `LibraryService.revision_content() -> tuple[object, ...]` 的Service语义比较视图，排除内部扫描/审计时间；Repository提供对应读取，不在API做diff。scanner注入B1 coordinator/publisher；变化在outer commit登记，原 _finalize completion 作为outer commit后工作。

**TO CREATE** `invariants/test_realtime_library.py`；RED `test_outer_scan_waits_for_commit_and_keeps_completion_order`：HTTP外层终端失败不update/event，成功时DB→update→completion；hold optional update期间新数据/版本已共同可见且可通知。扩展无变化扫描、metadata-only、availability、move、publisher failure、cancel/replay、同事务改后恢复。

验证：该精确selector → 全文件 → R-LIB/R-TX/R-PL。验收：无变化completion保留result/error，revision不增；真实文件临时fixture/真实Repository，无源码目录写入。

Complexity：2rows/scan→DB→publisher 3边界/commit与update失败2转换；persistence/runtime/optional external/API外层；4生产文件约120–240LOC。可独立RED，禁止与Playlist打包。

### Batch 3 — Playlist/Favorites 联合版本

依赖B1；执行顺序在B2之后。原Step2。读取 L §5/§7.1、T5 PL-REP/COLLECTION/TX。

Owned RT-PLAYLIST-001、RT-REVISION-001 final；Relied TX-*；Regression PL-REP/PL-COLLECTION-001。

白名单：`services/playlist_service.py`、`repositories/playlist_repository.py`、`services/events.py`；用户于2026-10-03批准最小扩展 `services/queue_manager.py`，仅限既有 `save_as_playlist` 的 outer transaction 接线，覆盖直接Service调用，不改保存范围、Queue播放规则或API。新增 `PlaylistService.revision_content() -> tuple[object, ...]`，以存在性/名称/成员/顺序比较；注入coordinator/publisher；新增 `PlaylistChangedEvent`。所有直接Service mutation与API outer事务加入同一unit-of-work，save_queue一次提交；不改变CRUD错误或REST schema。

**TO CREATE** `invariants/test_realtime_playlist.py`；RED `test_playlist_versions_follow_outer_delta_and_replay`：真实CRUD/Favorites/save queue、同名/同收藏no-op、重复添加错误、rollback/replay；两个域同outer事务各增一次，重启新coordinator epoch不同计数0、持久数据不丢；Library变更不增Playlist但保留成员。`test_direct_queue_save_never_exposes_partial_playlist` 覆盖既有 QueueManager 直接保存入口：一次提交/完整成员/单次版本，以及发布后取消仍保留完整已提交资源。

验证：selector → 全文件+B1/B2新proof文件 → R-PL/R-TX。验收：RT-REVISION生产级proof闭环，不能只验证计数器单测。

Complexity：2rows/Service→DB→publisher 3边界/有效delta/no-op/rollback3转换；persistence/runtime/API；4生产文件约100–220LOC（含已批准的保存事务接线）；可独立审阅。

### Batch 4 — Playback transport 提交传播

依赖B1；原Step2。读取 P §7/§8、T5 PB-STOP/HISTORY/TX、现有pause/seek/stop。

Owned RT-PLAYBACK-001 transport部分；Relied TX-*/EVENT-PORT；Regression PB-STOP/PB-HISTORY-001。

白名单：`services/playback_service.py`、`services/events.py`。新增 `PlaybackChangedEvent`（changed domains，领域状态仍由Service读取）；pause/seek/stop通过coordinator暂存原操作前后变化，仅成功outer commit登记。保持原方法签名/PlayerPort确认，不在通用装饰器对Output操作广播playback。

**TO CREATE** `invariants/test_realtime_playback_transport.py`；RED `test_transport_event_waits_for_confirmation_and_outer_commit`：pause/seek/stop参数化；未确认/terminal failure无通知，Stop History确认顺序不变，replay无新event，output runner不发playback。

验证selector → 全文件 → R-PB/R-TX/R-O。验收：该row仍PARTIAL到B6。

Complexity：1row/Playback→Port→History→commit4边界/3操作但共用一个传播转换；persistence/runtime/external/API；2文件约60–140LOC；不重写状态机。

### Batch 5 — Queue-only 传播与保留关系

依赖B4；原Step2。读取 T5 PB-INSERT/REORDER/DELETE-PENDING、Queue CAS；复用B4事件。

Owned RT-PLAYBACK-001 queue-only部分；Relied TX-*；Regression PB-INSERT/REORDER/DELETE-PENDING-001。

白名单：`services/playback_service.py`、`services/queue_manager.py`。接 play_next/add_to_queue/reorder/clear/pending delete；pending变化仅失效相关域，不结束active。不修改已有Queue revision递增策略。

**TO CREATE** `invariants/test_realtime_queue.py`；RED `test_queue_only_notification_preserves_current_occurrence_and_history`：重复URI occurrence、reorder/delete/clear、available变化与确认失败；比较DB/PlayerPort current、context、History，检查joint commit通知/replay。

验证selector → 全文件 → R-PB/R-TX。验收：无以URI合并occurrence，无改原Queue动作；row仍PARTIAL。

Complexity：1row/Queue→Playback→Port→History4边界/一个pending变更类别；4维；2文件约60–140LOC；独立保留关系审查。

### Batch 6 — Current/History 联合转移传播

依赖B5；原Step2。读取 P §3–8、T5 PB-HISTORY/NEXT-UNAVAILABLE/DELETE-CURRENT、T4 corrective。

Owned RT-PLAYBACK-001 final；Relied TX-*；Regression 全部PB-*。

白名单：`services/playback_service.py`、`services/history_service.py`。接 start_track/play_context/play_now/next/previous/current delete 的已确认联合delta；已有reconciliation仅在原显式调用路径遵循原提交传播，不从本Batch新建自动调用。禁止修订natural/Stop判断。

**TO CREATE** `invariants/test_realtime_transitions.py`；RED `test_transition_notification_matches_committed_history`：真实服务确认后新current/旧history/active一起可见，terminal失败恢复且无通知；no successor、unavailable、retry/replay、停止后删除不重启；联合domains没有中间帧。

验证selector → 全文件+B4/B5新proof → R-PB/R-TX/R-H。验收：RT-PLAYBACK三个类别都有真实proof才能COMPLETE；D6-RECOVERY不被该GREEN替代。

Complexity：1row/Playback→Queue→Port→History→commit5边界/同一confirmed current transition类别；4维；2文件约80–180LOC。超过此范围或需恢复状态机即不合并扩写。

### Batch 7 — 本地完整快照与 History availability

依赖B2/B3/B6；原Step1。读取 A §12.1/§12.3、P §2.2.1、L §7.1。

Owned RT-SNAPSHOT-001 local/RT-HISTORY-001 final；Relied RT-REVISION、PL-REP、TX-*；Regression PB-HISTORY/PL-COLLECTION。

白名单：**TO CREATE** `services/state_service.py`；修改 `models/realtime.py`、`services/queue_manager.py`、`services/history_service.py`、`services/library_service.py`（server/app/）。在models/realtime.py定义 **TO CREATE** 的FullStateSnapshot、HistoryAvailability、PlaybackObservation、OutputObservation DTO（字段严格按A §12.3）；新增 `QueueManager.get_snapshot() -> QueueSnapshot`、`HistoryService.get_availability() -> HistoryAvailability`、`StateService.get_full_snapshot() -> FullStateSnapshot`；Context仅传递既有playback_context_id和Queue顺序，不假定存在完整Context读取接口。coordinator marker与这些Service读取加入共同只读事务。观察初值为unknown DTO，不伪造MPD数据；后续B8/B9提供真实观察。

**TO CREATE** `invariants/test_realtime_snapshot.py` 与 `invariants/test_realtime_history.py`。RED分别 `test_snapshot_is_one_committed_cut`、`test_history_unavailability_preserves_events_and_has_entries`。barrier在多域读取中插入mutations；逐本地域失败、深复制、空态/active-only、Song MISSING/UNREADABLE后History REST仍返回；current unavailable保留身份/Queue occurrence。

验证两个selector各自RED/GREEN → 两个全文件 → R-H/R-PL/R-TX/R-ARCH。验收：无API直读SQL，无read触发reconcile；RT-SNAPSHOT外部/API端仍待B8–10/13。

Complexity：2rows/Service→snapshot→持久+runtime 4边界/一个capture、一个availability表示；persistence/runtime；5生产文件约160–300LOC；不加入socket/observer loop，能单独审阅。

### Batch 8 — Playback 只读观察与进度绑定

依赖B7；原Step1/2的明确scope补充。读取 P §8.8、A §12.3、PlayerPort/status/Queue identity及D6边界。

Owned RT-OBSERVE-001采样、RT-SNAPSHOT外部播放部分；Relied RT-REVISION/RT-PLAYBACK；Regression PB-*/TX-*。

白名单：**TO CREATE** `services/playback_observation.py`；修改 `services/playback_service.py`、`services/state_service.py`、`models/realtime.py`。新增 `PlaybackService.observe() -> PlaybackObservation`，由独立模块实现读取/代次校验和cache；`PlaybackService.get_observation() -> PlaybackObservation` 只读cache。复用现有Port.status/queue_entries，通过共同边界验证当前occurrence；未确认绑定一律unknown/reconciliation_required，不新增持久映射、不auto reconcile。进度与DB PlaybackState分开。

**TO CREATE** `invariants/test_realtime_observation.py`；RED `test_late_sample_never_becomes_new_current_progress`；FakeClock/屏障覆盖elapsed推进、pause/seek、重复URI、切歌、外部STOPPED/陌生current、断线/恢复、restart无可信绑定；assert全体U与Library/Playlist/Queue revision不变，只样本/sequence允许变化。

验证selector → 全文件+B7snapshot proof → R-PB/R-TX/R-O/R-ARCH。验收：数据库updated_at不冒充实时进度；明确未知比错误绑定优先；无domain recovery代码。

Complexity：2rows/Port→Playback observation→snapshot3边界/accept-stale-mismatch3转换；runtime/external；4文件约160–300LOC，单独于调度生命周期。

### Batch 9 — Observer 生命周期与 Output 接入

依赖B8；原Step2加lifecycle。读取 A §12.3、O §6、T7 O-STATE/EVENT/PRESERVE。

Owned RT-OBSERVE-001 final、RT-OUTPUT-001 final；Relied RT-DELIVERY core；Regression O-*、TX-*。

白名单：**TO CREATE** `services/state_observer.py`；修改 `services/output_manager.py`、`services/state_service.py`、`services/realtime_coordinator.py`、`main.py`。新增 `StateObserver.run() -> None` 与 `close() -> None`；OutputManager新增 `get_cached_state() -> OutputSnapshot`，复用既有get_state实际观察。composition root注入共享coordinator/publisher到各producer，启停一个observer，不因连接数增loop；输出控制原event bridge保留，非控制观察只失效。初始化未知Output结构沿用原空值/不支持合同。

**TO CREATE** `invariants/test_realtime_observer_lifecycle.py` 与 `invariants/test_realtime_output.py`。RED `test_single_observer_retries_and_shutdown_preserves_playback`、`test_output_control_and_observation_share_delivery_without_history`。FakeClock验证1秒间隔/5秒预算/6秒freshness、无重叠、单域故障不抹另一域、无客户端也采样、shutdown取消清理；控制outerrollback/replay/发布失败不影响旧terminal。

验证两个selector → 两文件+B8proof → R-O/R-TX/R-ARCH。验收：不在observer调用reconcile_external_status；没有自动恢复启用，D6未通过仍允许本只读Batch验收。

Complexity：2rows/生命周期→Services→Port→publisher4边界/start-sample-error-stop4转换；runtime/external/装配；5生产文件约180–320LOC。若扩大为新的恢复状态机则拆回D6，不可借loop引入。

### Batch 10 — 只读 snapshot API

依赖B9；原Step1/3的API边界。读取 A §12.1–12.3，现有API schemas/dependencies与router wiring。

Owned RT-SNAPSHOT-001 HTTP部分；Relied RT-HISTORY/OBSERVE/REVISION；Regression API architecture。

白名单：**TO CREATE** `api/realtime.py`、`api/realtime_schemas.py`；修改 `api/dependencies.py`、`main.py`。新增 `get_state_service() -> StateService` dependency、`GET /api/state` handler调用get_full_snapshot；API DTO与domain分离。snapshot本地失败503/STATE_SNAPSHOT_UNAVAILABLE，外部降级200，不创建terminal。不提前开WS。

**TO CREATE** `api/test_realtime_state.py`；RED `test_state_api_fails_whole_local_snapshot_but_keeps_external_degradation`。验证完整DTO/current/context_id/Queue所有occurrences/History/Output/read-only/cache freshness/版本；REST旧schema不变。

验证selector → 全文件+B7/B8snapshot/observation proofs → R-ARCH/R-H。验收：真实Service endpoint测试；不能只mock所有边界。

Complexity：1row/Service→schema→HTTP3边界/成功或本地失败2结果；runtime/API；4文件约80–160LOC；小窗口。

### Batch 11 — WebSocket initial → live 无缝交接

依赖B10；原Step3/5。读取 A §12.2、coordinator/snapshot接口。

Owned RT-CONNECT-001 final；Relied RT-SNAPSHOT/REVISION/DELIVERY；Regression EVENT-PORT/TX-*。

白名单：**TO CREATE** `services/realtime_connections.py`；修改 `api/realtime.py`、`services/realtime_coordinator.py`、`api/realtime_schemas.py`。新增 `RealtimeConnections.connect(socket: WebSocket) -> None`、`disconnect(connection_id: str) -> None`；coordinator提供 `subscribe() -> Subscription`、`unsubscribe(subscription: Subscription) -> None`，与capture共同边界建立先订阅/首帧水位/待通知交接。使用A固定路由/envelope；此Batch已使用有界队列，不引入无界临时实现，B12补全异常生命周期proof。

**TO CREATE** `invariants/test_realtime_handoff.py`、`api/test_realtime.py`。RED `test_last_mutation_during_initial_send_is_not_lost`：register前/后、capture内/后、send阻塞各屏障注入最后一次变更，之后不再mutation；它被首帧覆盖或随后invalidate，迟到callback无回退。首帧读取失败1011，清理订阅无成功snapshot。

验证selector → 两文件+B1proof → R-TX/R-ARCH。验收：无先send后subscribe；socket不持业务锁/不读MPD。

Complexity：1row/subscribe→capture→send3边界/register-initial-live3阶段；runtime/API；4文件约150–260LOC；独立race gate。

### Batch 12 — 背压、取消与隔离

依赖B11；原Step4。读取 A §12.2、既有O post-commit cancellation证明。

Owned RT-DELIVERY-001 final；Relied RT-CONNECT/REVISION；Regression TX-IDEMP/ROLLBACK/O-EVENT。

白名单：`services/realtime_connections.py`、`services/realtime_coordinator.py`、`api/realtime.py`。每连接独立sender，默认64帧/10秒；overflow/timeout1013、注销且取消并await资源；close也受有界退出约束，不能等坏socket拖死业务。提交可见hook仅enqueue或使连接失效，不await网络。

**TO CREATE** `invariants/test_realtime_delivery.py`；RED `test_overflow_and_timeout_isolate_clients_and_preserve_commit`：正常/blocked双连接，容量注入小值和FakeClock；数据库独立读/terminal replay证明已提交结果不变，关闭失败也清理，取消不遗留task，正常连接最后更新可达。

验证selector → 全文件+B11proof → R-TX/R-O/R-ARCH。验收：无silent drop、无socket异常改判业务失败；该row到此才COMPLETE。

Complexity：1row/commit→queue→sender3边界/overflow-timeout-cancel3失败转换；runtime/API；3文件约80–180LOC，可独立审查。

### Batch 13 — 重连恢复与最终 Task-level acceptance

依赖B1–12；**最终验收另需 D6-RECOVERY 的 fresh proof**。原Step5/6；Step7提交仍须用户授权。读取所有11 rows及D6验收记录，不能拿旧全套结果代替。

Owned RT-RECOVER-001 final、RT-SNAPSHOT-001 final；Relied全部Task6 rows；Regression所有§4.3 IDs。

生产白名单：无计划中的新生产功能；发现缺陷只回到其owner范围修正并重跑对应RED/GREEN，不能在final gate新增恢复状态机。**TO CREATE** `invariants/test_realtime_recovery.py`；扩展 `api/test_realtime.py`。

RED `test_reconnect_replaces_all_domains_and_epoch`：断线期间真实Library扫描/Playlist/Favorites/Queue/Playback/History/Output变化，重连与当前Service逐字段比较；活跃播放/空态/unavailable/stale/本地失败/overflow重连/restart都覆盖；并发snapshot请求用协议测试客户端证明旧响应不覆盖新水位、旧epoch晚返回不覆盖新连接基准、相同sequence幂等忽略，不写Task8 store。

验证selector → 文件 → `.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_*.py server/tests/api/test_realtime*.py` → R-TX/R-LIB/R-PL/R-PB/R-H/R-O/R-ARCH → `.venv/bin/python -m pytest -q server/tests/invariants server/tests/api` → `.venv/bin/python -m pytest -q server/tests`。最后两项为本Task显式回归范围，不能替代前面的targeted gates。Ruff仅实际改动Python文件；必要compile使用 `.venv/bin/python -m compileall -q server`。

验收：D6证据真实存在且测试通过；全11 rows implementation→proof→fresh GREEN闭环，无未来功能、环境/schema/dependency漂移；完整diff/status/stat检查。物理NAS/MPD/DAC与reverse proxy仍属Task12，不冒充本地proof。

Complexity：2rows/Service→HTTP/WS→客户端表示3边界/reconnect-restart2类别；4维，仅新增测试0生产LOC。若D6未通过，只能报告恢复proof已做/最终验收未通过，不能宣称Task6 COMPLETE。

## 7. Ownership 与重新划分依据

| Contract | Interface freeze | Behavior owner | Final executable proof / acceptance owner |
|---|---|---|---|
| RT-SNAPSHOT-001 | B7 | B7/B8/B9/B10 | B13（含B7/B10proof） |
| RT-REVISION-001 | B1 | B1/B2/B3 | B3，B13回归 |
| RT-LIBRARY-001 | B2 | B2 | B2 |
| RT-PLAYLIST-001 | B3 | B3 | B3 |
| RT-PLAYBACK-001 | B4 | B4/B5/B6 | B6 |
| RT-OUTPUT-001 | B9 | B9 | B9 |
| RT-HISTORY-001 | B7 | B7 | B7 |
| RT-OBSERVE-001 | B7 DTO / B8 Service | B8/B9 | B9；领域恢复仍D6专项 |
| RT-CONNECT-001 | B11 | B11 | B11 |
| RT-DELIVERY-001 | B1/B11 | B1/B11/B12 | B12 |
| RT-RECOVER-001 | B11 | B11–13 | B13，依赖D6 |

B1的提交可见性必须先于producer；Library完成事件有optional update独立失败边界，不能与Playlist合并。Playback transport、pending保留、current/History联合转移各能独立RED，故拆3批。聚合读取先证明本地切面，观察样本再证明外部权威，loop又独立于采样；网络交接与慢连接故障可分别拒收，因此不打包。没有500–800行多个状态机的大Batch；LOC估计只用于Complexity Gate，实际超过范围必须重新拆分，不能以估计作为扩范围许可。

## 8. 本轮验证与最终 Task-level Contract Audit

本轮仅文档落地、源码/测试读取和既有基线验证。环境确认：Python3.14.4、pytest9.1.1、ruff0.16.9；已读取server/requirements.txt，无环境/依赖修改。未运行新Task6测试（均未创建），未执行Batch、D6 corrective、live MPD、Docker或远端操作。

实际基线命令：

```bash
.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/integration/test_task3_events_and_mpd.py server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_transaction_relationships.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_playlist_relationships.py server/tests/invariants/test_architecture_relationships.py server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/repositories/test_library_reconciliation.py server/tests/invariants/test_output_observation.py
```

**89 passed，6.17s，1条既有Starlette TestClient/httpx deprecation warning**。无环境失败；该GREEN不证明新snapshot/handoff/revisions/observer或D6已实现。

| 再审计项 | 结论 |
|---|---|
| 原5 Gap各有证据、authority判定、人工选择 | 完整，§2；5项及G6-01 Context补充全部选择A，非代码推导 |
| Spec正式落地 | A §12.1–12.3、L §7.1、P §2.2.1/§8.8，O §8.1消歧引用 |
| Snapshot/mutation/event race | 同切面+同步提交可见登记+subscribe/capture交接；B1/B7/B11barrier proof |
| Revision success/no-op/failure/rollback/restart | L §7.1逐项定义；B1–3 proof |
| Initial→live / overflow recovery | A §12.2定义水位、顺序、关闭及重连；B11–13 proof |
| History unavailable语义 | P §2.2.1保留事件，当前Library信息独立；B7 proof |
| MPD/PlaybackService/DB/API/WS authority | P §8.8/A §12.3明确分离；observer只读，D6保留领域恢复所有权 |
| Matrix fields与分类 | 11新增rows含共同U/T/F/I和逐row字段；6继承rows；原业务语义修改0 |
| Matrix→Batch→file/interface→proof→acceptance | §6/7每row有owner和精确TO CREATE proof；现有回归文件已核实 |
| Relationship-Test Matrix | M Task6 row扩展到切面/版本/History/observation/handoff/overflow；Task4 row明确D6专项关系证明，原历史验收不整体重开 |
| Dependency Matrix | 仅新增D6阶段性验收依赖；基础顺序与Task8+边界不变 |
| Contract Gap count | **0**；不是实现缺口数量 |
| Plan可执行性 | 依赖顺序可执行，B1具备前置合同；final acceptance需D6证据，不能跳过 |
| 完成声明 | 合同/计划审计完成；Task6 implementation、proof GREEN及最终验收均未完成 |

文档结构校验已核对11个唯一row、Batch 1–13连续编号、各Batch必要字段及现有regression路径。首次全文件空白检查碰到Library Spec既有表格行尾空格；确认它与HEAD一致后改为检查本轮新增行，未顺手格式化旧内容。`git diff --check`通过。

本轮最终diff检查还包括未跟踪的本文件（普通git diff不会显示其全文）；只允许本文件、M及4份直接authority Spec。没有改测试或production code，没有提交。用户检查本轮结果后，才另行决定执行/提交。
