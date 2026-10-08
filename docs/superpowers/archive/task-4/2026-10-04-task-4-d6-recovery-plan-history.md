# Task4 D6 corrective plan 历史与调查归档

> 本文件仅为过往记录，不是 active plan、Spec 或验收通过证明。2026-10-04 从唯一 [active plan P](../../plans/2026-10-04-task-4-d6-recovery-corrective-plan.md) 汇总迁入旧 consumer Step2.1–Step3、旧 S0/S1、已废止的剩余步骤，以及合同迁移时的详细能力调查。当前执行仅以 P 的新 S0–S12 和 F §8.9 为准。
>
> 下文旧记录中的“当前”“下一步”“需要后端扩展”和白名单均只描述当时合同；不授权执行。旧记录内部的 P §8.9 指 Playback Spec（当前简称 F），不是当前 active plan P。保留原文以维护调查过程；旧 SOURCE BLOCKED 和历史 GREEN 均不代表当前门禁。

## 合同迁移时的能力复核记录

原始 [JSON](/home/Gold/Downloads/mpd-0.23.5-probe-2026-09-26-091948.json) 已取得，SHA-256 `6c4036572314b38d822481c28fa25652bab29a26ab8ec6e74a076cbe815d0d40`。逐项核对 C：commands=105（补回 unmount），status_fields=17，outputs/stats/update/errors 一致；无 verified_operations。第二轮原始 JSON 未取得，九项 transport 仅保留 C 历史摘录。旧 S1 “当时未取得”保持原样，不改成当时已取得；没有运行新 probe。

仅用官方固定 tag，未以 stable 替代。以下是本轮只读接口/源码核查，不是目标实机行为认证：

| 官方主来源 | 对本轮决定的依据 |
|---|---|
| [v0.23.5 protocol.rst](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/doc/protocol.rst) status/queue/command lists | status 提供 current ID/position/playlist version/length 和模式；command list 错误后停止，先前命令不回滚；greeting 是协议版本，不能认证二进制补丁。 |
| [PlayerCommands.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/command/PlayerCommands.cxx) handle_status/handle_next | status 无完成 reason/结束时间；外部 next 与内部推进可到相同 current；STOP 仍可保留选中 entry，不能解释为正在播放。 |
| [Idle.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/client/Idle.cxx) IdleAdd | 变化位 OR 合并，不是有序逐事件日志；提高采样频率不补齐原因。 |
| [Playlist.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/queue/Playlist.cxx) SyncWithPlayer/ResumePlayback | 已排后继可由 MPD 自身推进；错误也可经 PlayNext，接纳当前事实不得反推自然原因。 |
| [PlaylistControl.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/queue/PlaylistControl.cxx) Stop/PlayNext/SeekSongOrder | 控制/队尾 stop/seek 路径不能从最终 current 区分发起者。 |
| [Thread.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/player/Thread.cxx) SongBorder/Run/SeekDecoder | played URI 出现在边界及通用退出清理；seek 到终点也可排空；日志不是完成认证。 |
| [IdTable.hxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/queue/IdTable.hxx) GenerateId | ID 分配回绕可重用；必须结合有效连接/映射/version，不能持久信任裸 ID。 |

不可区分性结论是上述代码的推论：A→B 自然推进、外部 Next、seek 后到 B 可以留下相同可见快照；采样间 B 可能不可见。新合同仅接纳目标，不利用这些证据产生原因。目标 NAS build/hash 未核验，模式组合/长时续播未实测。

## R1 决策过程

以下是用户答复前的原记录，仅保存决策过程：

本轮最终只检查文档diff、链接、源文件字节和未授权范围，不执行上述未来测试；不commit。**待决产品项 R1（已向用户提出，尚未收到答复）**：F8.9.2及A12.3.1中“服务/MPD重启后恢复actual显示，但业务绑定须明确接管”目前是推荐草案，不冒充用户已接受的新限制。选项A接受该限制（不影响仅刷新/换浏览器）；选项B要求重启后自动业务绑定，则该子合同保持BLOCKED并需再设计可认证的跨重启身份，不默认后端扩展。其余已授权合同/调查/步骤继续成立；依赖此选择的S3重启策略、S8重启表示验收和S9重启接管在答复前不实施。History已在用户允许范围内选定，不另设审批。

2026-10-04 后续用户明确接受建议（原选项 A）：重启后恢复实际状态显示，业务绑定由明确播放操作经确认重建；仅刷新/换浏览器不丢服务绑定。当前 F/A/P/E/B/T/M 已同步为接受，未因此宣称新实现或验收完成。


# 历史记录区：旧严格 SOURCE 合同与 consumer 实施

> 以下完整保留旧 Step2.1–Step3、旧 S0/S1 和当时证据；所有“当前/最新/下一步/白名单/需要后端扩展”均限定于当时旧合同。旧剩余 S2–S7 已废止执行，现只执行上文新 S0–S12。历史 SOURCE BLOCKED 不是当前的实现前置，历史 PASSED 也不是新合同验收。旧调查在严格因果要求下的不可行结论仍有效；产品本轮选择收窄该要求，未采用其后端扩展建议。

# 历史：Task4 D6-RECOVERY corrective plan

> 使用 superpowers:executing-plans 顺序执行；遵循 systematic-debugging、test-driven-development、verification-before-completion。consumer Step2.1–Step3 已实施并有验收记录；2026-10-04 S0 已核对基线，S1 来源调查已完成，裁定需要后端扩展，D6-SOURCE 仍 BLOCKED（见文末）。后续须先决定后端范围，再进入 S2；不重做 consumer，不提交、不启动自动恢复。唯一新增语义为 Playback Spec §8.9，本文只分解该权威合同。

**Goal:** 实施已批准的保守 D6 consumer 合同，并明确生产因果证据能力门禁；consumer GREEN 不替代完整 D6 验收。

**Architecture:** PlaybackService 编排 Queue/History/AutoPlay/PlayerPort；Repository 管理同库 outer transaction，runtime hooks 恢复 History/observation。Task6 observer/snapshot/reconnect 保持只读。

**Tech Stack:** 既有 Python `.venv`、SQLite、pytest、Mock/Fake PlayerPort。

**Spec:** Playback Spec 2026-09-24 §6–8.9/§10；Architecture Spec 2026-09-25 §12.1–12.3/§19.5；主 Implementation Plan Task4/Task6/Dependency/Relationship/Contract Matrix；active Task6 plan §3/§4/§5/Batch13；Task5 archived batch plan §3.7。

## Constraints / files

- 原 checkout/branch；既有环境，不修改依赖/schema，不使用 Docker/live MPD。
- 不重开全部 Task4，不扩展 Task6/Task8；不引入 loop、scheduler 或 MPD occurrence 持久映射。
- 起始三份 Batch13 文件已在 `82391fc`，不得改其测试以掩盖 D6。
- S0 生产白名单：**无**；仅同步 P/E，必要时同步 B。下列 consumer 白名单记录已有实施范围，不授权 S0 改代码，也不授权 API/observer/main/MPDAdapter 恢复接线。
- 已实施 consumer 生产白名单：`services/playback_service.py`（分类/确认/事务/传播）；新增 `models/recovery.py`（内部 evidence/result/intent 类型）、`services/playback_recovery.py`（进程 epoch、业务代次、pending intent/receipt，调用者仍为 PlaybackService）；`services/queue_manager.py` + `repositories/queue_repository.py`（唯一自然完成 Queue 转移，保留完成 occurrence，原方法合同不动）；`services/autoplay.py`（仅提取既有候选规划以固定 retry IDs，不改变来源/算法/low-watermark）；`services/playback_observation.py`（仅提供既有绑定校验及恢复提交绑定，保留只读采样）。所有路径在 `server/app/` 下。
- 无需修改 schema、PlaybackState 枚举、HistoryReason、HistoryService finalizer 或 database/idempotency/realtime coordinator；使用现有 hooks。若实际证明白名单仍不足，先修订最小依赖，不能默认扩展。
- 2026-10-04 Step2.5 实证最小依赖修订：允许 `services/history_service.py::stop` 在无 active 时清空既有 session。专项 empty selector 已证明自然完成后显式 Stop 未清 session（真实 RED）；仅修改公开 Stop 的 session 收尾，不修改 `_finish_active`、reason、schema 或持久事件。由 PlaybackService 既有 outer runtime rollback hook 保护。
- 测试白名单：专项 `server/tests/invariants/test_d6_recovery.py`；仅下文列明的三个旧 reconciliation selectors 允许按新 Spec 改写；`server/tests/invariants/assertions.py` 仅将 STOPPED 检查拆分为显式 Stop 与无候选组合，不弱化其它断言；AutoPlay/Queue 的直接 focused 测试可按新增接口补最小案例。不得改两份 Batch13 Python proof。
- 本轮 proof：`server/tests/invariants/test_d6_recovery.py`。唯一专项 acceptance：`docs/superpowers/archive/task-4/2026-10-04-task-4-d6-recovery-acceptance.md`。既有 Batch13 acceptance 仅追加本轮 blocker 状态。

## 人工决策 / Gap 审核

2026-10-04 用户明确选择方案 **A**，批准五项保守决策及 §7 STOPPED 含义修订。新增 authority 全部在 P §8.9；不创建第二份 Spec/计划。已有约束：显式 Stop 请求+实际确认、PB-HISTORY 未确认不写事件、可用 successor/AutoPlay 候选原则、DB/runtime rollback、REST scope/key replay、observer 只读。真正新增：因果证据接纳、漂移分类/返回、无候选终态组合、恢复身份/同进程 retry。

五项**领域消费合同已闭合**；自然完成**生产可信来源机制尚未确定/验证**，记为 `D6-SOURCE` 能力 blocker，不能声称整个自然识别 Gap 消失。路线 A 允许先做 consumer TDD；只有来源生产者能力 proof + consumer proof 联合 GREEN 才能通过 D6。Task6 G6-01–05 仍闭合，无重新设计 Task6。

## 内部接口与文件职责（consumer 已实现；生产来源未实现）

- `models/recovery.py`：不可变 `CompletionEvidence`，字段 `service_epoch:str, source_id:str, source_epoch:str, continuity_token:str, business_generation:int, queue_revision:int, queue_item_id:str, mpd_song_id:int, transition_id:str, ended_at:datetime`；验证来源由注入内部 evidence validator 完成，不接受 public bool/reason。`RecoveryResult` 字段 `outcome:Literal["UNKNOWN","UNCHANGED","APPLIED","REPLAYED"], playback:PlaybackState|None, transition_id:str|None, reconciliation_required:bool, diagnostic:str|None`。REPLAYED 表达读取 receipt，其 playback 是原回执，不改写为实时值。
- `PlaybackService.reconcile_external_status(self, *, evidence:CompletionEvidence|None=None) -> RecoveryResult`：无参调用仍可用，未知正常返回，typed source failure/confirmation conflict 抛异常。所有调用者已 rg 搜索：只有测试与显式方法，无生产恢复 loop/API 调用，不改 wire DTO。PlaybackService 构造器新增可选 keyword `completion_validator:CompletionValidator|None=None`，journal epoch独立于Task6协调器；证据 validator 为内部依赖，默认拒绝全部自然证据；测试提供 deterministic validator，不能标生产 GREEN。
- `models/recovery.py` 另定义 `RecoveryIdentity=tuple[str,int,str,str]`；不可变 `RecoveryBaseline(queue:QueueSnapshot, playback:PlaybackState, history:HistoryAvailability, business_generation:int, mpd_song_id:int)` 和 `RecoveryPlan(identity:RecoveryIdentity, evidence:CompletionEvidence, baseline:RecoveryBaseline, pending:tuple[QueueItem,...], successor_id:str|None)`。注入 `CompletionValidator.validate(evidence:CompletionEvidence, baseline:RecoveryBaseline) -> Awaitable[bool]`；false按UNKNOWN保留，source typed error原样抛出。测试validator只为测试来源背书；生产默认未注入 validator（None），自然证据被拒绝。
- `playback_recovery.py`：`RecoveryJournal` 保存进程 epoch、独立业务代次、pending plan、固定 execution IDs 和 receipt；当前 binding 由 PlaybackObservations 保存；`get_receipt(identity:RecoveryIdentity, evidence:CompletionEvidence) -> RecoveryResult|None`、`prepare(evidence:CompletionEvidence, baseline:RecoveryBaseline, planned_pending:tuple[QueueItem,...]) -> RecoveryPlan`、`commit(identity:RecoveryIdentity, result:RecoveryResult) -> None`，全部只由 PlaybackService 在既有事务边界使用。prepare 固定目标与新 occurrence IDs；commit 先在事务内深复制/验证结果并保留未消费槽位，outer-visible hooks只切换已提交状态，不能把结果materialization留到提交后；若提交后journal无法可靠提供receipt，隔离该journal并拒绝执行旧ID，不能再写History。rollback 恢复业务代次/绑定，pending 不丢。业务代次不可使用每次 observation 的 generation 作为持久播放身份；所有成功 current-changing 原入口须在此更新/失效，pause/seek 不制造新 occurrence。
- `AutoPlay.plan_refill(context:PlaybackContext, snapshot:QueueSnapshot) -> tuple[QueueItem,...]`：纯候选规划，复用现有候选算法/availability/5+5规则；普通 refill 沿用原行为。恢复 journal 仅首次规划，retry 不重分配 ID。
- `QueueManager.complete_current` 使用下述同一参数/返回签名，转发 → `QueueRepository.complete_current(queue_item_id:str, *, pending:tuple[QueueItem,...], successor_id:str|None, expected_revision:int) -> QueueSnapshot`：一次 CAS 业务转移；pending 是固定最终有效项+已规划 AutoPlay 项，successor 必须属于 pending 或为 None。验证旧 current、保留项身份及顺序、新项 source=AUTOPLAY；完成项移到 -1，已有 Played 顺序保留，目标0/其它pending连续，无目标无 execution；单次 +1 revision。不能作为任意覆盖 Queue 的通用接口。
- 使用 `HistoryService.complete_naturally(ended_at=...)` 与 `start_track(...)`、`preserve_active_on_rollback()`；不调用 `next()`/delete 模拟自然完成，不改变它们的 reason。

## Contract Matrix Impact Analysis

Relationship Gate **consumer PASSED / 完整 D6 NOT COMPLETE**；Contract Matrix 定义 **CLOSED for consumer / production source BLOCKED**。Step2.1–Step3 consumer 验收见 E 实施节；S0 仅复核指定三文件，不代替完整联合验收。
Owned modified：PB-HISTORY-001 的自然 consumer 扩展。新增稳定 rows：PB-RECOVERY-UNKNOWN-001、PB-RECOVERY-TRANSPORT-001、PB-NATURAL-001、PB-NATURAL-EMPTY-001、PB-RECOVERY-RETRY-001。D6-RECOVERY 仍是阶段验收 ID。Relied unchanged：PB-STOP-001、PB-NEXT-UNAVAILABLE-001、TX-ROLLBACK-001、TX-IDEMP-001、EVENT-PORT-001。Regression：PB-INSERT/REORDER/DELETE-PENDING/DELETE-CURRENT-001、PL-REP/COLLECTION-001、O-PRESERVE/STATE/EVENT-001、RT-OBSERVE/SNAPSHOT/PLAYBACK/RECOVER-001。

### 共同字段（每行组成部分）

Preconditions：真实 Services/同库 Repository/verified PlayerPort；自然行另需 P §8.9.1 evidence validator。Authorities：PlaybackService 编排，Queue/PlaybackState 持久，History 持久+active/session，MPD 外部事实，journal runtime；网络不是业务 authority。

U：除行中列出的 delta，保持 Queue occurrence/source/context/相对顺序，PlaybackContext，History 旧记录，Playlist/Favorites 全资源与 Library 内容/revisions，Output observation/request/MPD outputs，全部既有 REST terminal；无新 REST endpoint/terminal。行 F/T/I 优先于普通成功 delta。

T/F：同库 outer transaction；当前 binding、History active/session、业务代次一起回滚；未提交结果不作 success receipt。确认/写入/materialization/terminal/outer failure、提交前取消无成功事件，pending 意图保留；提交后取消/交付失败保留提交/receipt，登记传播遵守 A §12.2。MPD 副作用不撤销，retry 必须实际重读。只有实际 Queue delta 增 revision；成功联合变化 outer commit 后传播，unknown/no-op/replay 无 mutation notification。

| ID / Type / authority | Preconditions / Expected delta | U / confirmation / History | Failure / Retry / Observable | Executable proof（专项文件，selectors 已存在；S0 指定命令含全部 D6 cases） |
|---|---|---|---|---|
| PB-RECOVERY-UNKNOWN-001 / STATE_TRANSITION / P §8.9.1–2 | 无证据 STOPPED、foreign/duplicate/missing binding/Queue drift；业务零 delta | U 全保留；status不能证明原因；无控制/History | T/F；UNKNOWN+required=true；来源错误抛 typed error；重复仍不提交 | test_unclassified_external_stop_does_not_fabricate_history；test_unknown_recovery_preserves_all_authorities；test_recovery_source_failure_preserves_authorities |
| PB-RECOVERY-TRANSPORT-001 / STATE_TRANSITION / P §8.9.2 | 已绑定同 occurrence/完整 Queue；PLAYING↔PAUSED；仅state/确认位置/updated_at | active/session/autoplay/Queue/context不变；实际两次回读一致，无控制/History | T/F；同状态UNCHANGED，APPLIED后重复无通知；rollback恢复再读 | test_bound_external_pause_resume_preserves_history；test_transport_recovery_rollback_and_retry |
| PB-NATURAL-001 / STATE_TRANSITION / P §8.9.1/3 | 验证完成；首个可用pending，否则固定AutoPlay；完成项Played，目标current+新active | U；同session/context/autoplay；精确目标PLAYING与完整execution确认；仅旧active NATURAL_COMPLETION | T/F；目标已播放不重播，冲突UNKNOWN；consumer APPLIED，来源未验证不验收D6 | test_natural_completion_promotes_confirmed_successor；test_natural_completion_refills_once；test_duplicate_song_completion_uses_occurrence_identity |
| PB-NATURAL-EMPTY-001 / STATE_TRANSITION / P §7/§8.9.3 | evidence有效且无候选；STOPPED/null/null/true；旧current -1，无execution；active=null/session保留 | 旧Played、Context、U；确认STOPPED+空execution；无STOP command/reason | T/F；同ID replay无refill；重启拒绝旧证据；等待内容无新loop | test_natural_completion_without_candidates_retains_session |
| PB-RECOVERY-RETRY-001 / TRANSACTION / P §8.9.4 | epoch+generation+occurrence+ID固定证据/目标/IDs；receipt只在outer commit | U；失败无phantom/receipt；成功replay原回执，无controls/events | T/F；rollback后实际目标已到则确认，不重播；其它漂移UNKNOWN；冲突抛ReconciliationError；旧epoch UNKNOWN | test_recovery_rollback_retry_keeps_identity；test_recovery_replay_and_conflict；test_recovery_rejects_stale_evidence；test_recovery_post_commit_failure_preserves_receipt |
| PB-HISTORY-001 / STATE_TRANSITION / P §2.2/§7/§8.9；T5 §3.7 | 已确认自然离开恰一次NATURAL_COMPLETION，新确认目标新active | 原显式Stop/Next/delete/switch合同保持；无未知归因 | T/F；原REST idempotency不重做；consumer replay不重复History | 上述自然/rollback selectors + 原 playback/stop/transaction proof |
| PB-STOP/NEXT-UNAVAILABLE/TX-ROLLBACK/TX-IDEMP/EVENT-PORT / 原类型和authority | 仅各owner原合同delta | 原confirmation/History/U全部保持；STOPPED+AutoPlay=true不得套显式Stop断言 | 原key/scope/outer/failure/retry；既有receipt不受新journal影响 | active T6 §5 R-PB/R-H/R-TX；transaction hooks |
| regression IDs / 各owner原Spec、T5 §3.7、T6 §4 | 各自冻结delta，不增加读取/网络控制 | 原U，observer/snapshot/reconnect不调用恢复 | 原确认/提交/rollback/replay，无第二个编排器 | active T6 §5所有R集合；realtime observation/snapshot/transitions/recovery |

## Review Focus

1. 同URI不同occurrence/迟到代次/重启/断线证据不混淆：Step2.2 / Step2.7。
2. 无原因Stop、外部Next、foreign、Queue drift不归因：Step2.1。
3. 无候选与显式Stop的session/autoplay不同：Step2.5，不以state单字段断言。
4. rollback后MPD已到目标仍保持固定IDs，不跳歌/重播：Step2.6。
5. outer结果/receipt未提交、提交后取消与交付错误不误撤销：Step2.7。

## Ordered Steps（consumer 完成状态；RED 历史见 E）

- [x] **Step1 — Git/environment/authority审计与精确真实RED**。首次审计的真实 1 failed 保留于 E 历史节；该原 selector 已在 Step2.1 闭合，S0 fresh GREEN。人工A已写入 Playback Spec §8.9，生产来源仍BLOCKED。

- [x] Step2.1 UNKNOWN / 原专项RED闭合。
- [x] Step2.2 身份与证据拒绝。
- [x] Step2.3 bound transport。
- [x] Step2.4 natural successor consumer。
- [x] Step2.5 natural empty consumer。
- [x] Step2.6 rollback/retry。
- [x] Step2.7 replay/commit边界。

每个 Step2 行必须依序：①写该行最小 test/literal assertions；②精确 selector RED（fixture/setup失败不算）；③最小白名单实现；④相同selector GREEN；⑤专项文件及列明直接回归 GREEN；⑥diff/isolation。命令统一展开 `.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py::<下表函数>`。这是原逐行实施纪律；下表 consumer selectors 现在均存在，Step2.1–Step3 的逐行结果见 E 实施节。S0 不重复创建或人为制造 RED；SOURCE 新测试仍在文末标为 TO CREATE。

| Step | selector / literal assertions及实现动作 | 直接回归 |
|---|---|---|
| 2.1 UNKNOWN | 既有 test_unclassified_external_stop_does_not_fabricate_history 原样先RED→GREEN；新增 test_unknown_recovery_preserves_all_authorities 参数stop/foreign/duplicate/missing-id/queue-mismatch/unbound及elapsed-at-end：`outcome=="UNKNOWN"; reconciliation_required is True; before==after; controls==[]; receipt is None`。新增 test_recovery_source_failure_preserves_authorities 对不可达/命令错误断言原typed exception、全部保留。最小修改reconcile入口与result，不隐含修复_save_confirmed_status其它operation | 三个冲突selectors按下节改写；R-PB，observation |
| 2.2 identity/evidence拒绝 | test_recovery_rejects_stale_evidence 参数epoch/generation/occurrence/source-continuity/restart/missing-active/invalid-time：UNKNOWN、全部保留、零控制。引入journal和validator默认拒绝；内部验证Fake可固定valid token，旧业务成功current入口更新journal代次。不要把unknown测试升级为可信natural | R-PB/R-TX/R-ARCH |
| 2.3 transport | test_bound_external_pause_resume_preserves_history 参数pause/resume/no-op：APPLIED/UNCHANGED、同queue/context/session/active/autoplay、无事件reason/控制。test_transport_recovery_rollback_and_retry 用outer failure及precommit cancellation，回滚before；retry后唯一playback通知、无History | stop、observation、realtime transitions、Output serialization |
| 2.4 natural successor | test_natural_completion_promotes_confirmed_successor 参数pending/missing/unreadable/absent/already-playing/confirmation-fails；test_natural_completion_refills_once 参数autoplay/one-song；test_duplicate_song_completion_uses_occurrence_identity 参数正确/错误同URI occurrence。`events==[(old,"NATURAL_COMPLETION")]; active.song_id==target; session==old_session; context==old_context; autoplay is True`；完成ID -1、目标ID0、其它身份保持，实际目标id/state/Queue全匹配，confirmation失败before==after/no receipt。先测试再提取AutoPlay plan/Queue complete_current/自然编排；已到目标controls无play | Queue/AutoPlay focused、R-PB/R-H/R-TX、realtime transitions |
| 2.5 natural empty | test_natural_completion_without_candidates_retains_session：空可用库+无效pending，valid completion；`(state,song,position,autoplay)==("STOPPED",None,None,True); active is None; session==old_session; context==old_context; no position>=0; old_id.position==-1; events==[(old,"NATURAL_COMPLETION")]`。实际STOPPED/空execution、无stop command；后续显式Stop才session=None/autoplay=False。修订helper仅按两种STOPPED组合检查 | R-PB/R-H、Queue/AutoPlay focused、snapshot |
| 2.6 rollback retry | test_recovery_rollback_retry_keeps_identity 参数target=successor/autoplay/empty × failure=confirmation/history-write/queue-write/state-write/outer/materialization/terminal/precommit-cancel。失败后完整业务snapshot==before、无receipt/成功通知，intent固定且MPD副作用单独记录；retry同ID不重分配/重播/Next，History恰一次。人为外部漂移retry UNKNOWN；合法新current后旧intent拒绝。terminal case通过真实IdempotencyService outer test harness，不新增API；纯Service receipt case独立验证 | R-TX/R-PB/R-H |
| 2.7 replay/commit边界 | test_recovery_replay_and_conflict：同ID结果playback等于原receipt，outcome=REPLAYED，零History/controls/revision/event；改内容抛ReconciliationError。test_recovery_post_commit_failure_preserves_receipt 参数cancel/publisher/visibility-registration：成功提交保留；registration失败按现有A §12.2使snapshot不可用，不执行rollback hooks。重复业务后重放旧receipt仍不改变新current；restart旧epoch UNKNOWN。outer hook/barrier证明receipt消费及通知不早于commit | commit hooks、realtime delivery/transitions、R-TX/R-ARCH |

### 旧证明冲突的最小迁移（Step2.1/2.3 已实施；S0 只读核对）

- `server/tests/services/test_playback_service.py::test_reconcile_external_status_updates_service_state_but_not_server_queue`：改为外部b UNKNOWN，全业务状态不变。不能继续允许Playback/active=b但Queue current=a。
- `server/tests/api/test_pre_batch6_corrective.py::test_reconciliation_outer_rollback_restores_history`：stop/foreign分支按UNKNOWN无delta，保留outer失败全状态恢复；额外bound pause分支验证有delta时outer rollback与retry。未知retry绝不产生STOP/SWITCH_AWAY。
- `server/tests/invariants/test_realtime_transitions.py::test_explicit_reconciliation_propagates_only_committed_existing_delta`：stopped分支UNKNOWN、零producer sequence/event；pause分支保留outer rollback、提交后唯一playback notification与重复no-op，History/session不变。其它三个测试文件中的无关selectors不改。
- `invariants/assertions.py::assert_execution_relationship`：显式Stop继续active/session=None；自然empty分支要求无current+autoplay=true+active=None+session保留，不能删除session断言。专项测试必须另外固定期待的旧session值，helper不能自行“猜”状态正确。

- [x] **Step3 — consumer专项验收（既有实施节已 PASSED，S0 仅三文件复核）**：Step2全部GREEN后，专项文件→Queue/AutoPlay/三项迁移文件→R-PB/R-H/R-TX/R-O/R-ARCH→scoped Ruff/compile/diff。逐行U包括真实Library/Playlist/Favorites/Output内容、全部旧REST terminals和revisions，不仅server_snapshot五元组。用barrier证明并发mutation/晚证据不会覆盖新current。记为consumer PASSED仍不是D6 PASSED。
- [ ] **Step3-SOURCE — production能力门禁，当前BLOCKED**：需明确真实因果证据来源、Port/Adapter能力验证、断线/重启continuity与重复occurrence proof，修订本计划白名单后才实现该producer。不接受只注入Fake、扩展status reason或旧单元GREEN作为解除证据。本窗口不虚构selector；这里因能力接口尚不存在不能建立生产proof，明确是剩余可执行性缺口。
- [ ] **Step4 — 完整D6与Batch13最终门禁**：Step3+SOURCE联合fresh GREEN后才进入active T6 §5/Batch13最终序列。仍不启用自动恢复loop；更新唯一acceptance，另行授权才可执行后续接线或提交。

## Acceptance / Spec→Contract→Step→proof 审查

| authority | row → Step → consumer proof | 审查结论 |
|---|---|---|
| P §8.9.1–2禁止推测/漂移接纳 | UNKNOWN/TRANSPORT → 2.1–3 → 精确selectors | consumer 已实施；原 unknown RED 已闭合，三项旧 proof 已迁移；S0 D6 98 cases GREEN |
| P §8.9.3 successor/empty | NATURAL/EMPTY/HISTORY → 2.4–5 → 精确selectors | consumer 已实施并 fresh GREEN；evidence 只用明确 Fake validator，不能外推生产 |
| P §8.9.4 identity/rollback/retry | RETRY/TX-* → 2.2/6/7 → 精确selectors及真实outer harness | 同进程 consumer 已实施并 fresh GREEN；真实来源 continuity 尚待证明，重启拒绝旧证据，不承诺持久 replay |
| P §8.9.5生产可信来源 | D6-RECOVERY → 3-SOURCE | BLOCKED；缺少producer机制/接口/可执行selector，未掩盖为合同全闭合 |
| A §12.1–3/§19.5；T6 Batch13 | regression/RT-* → 3/4 → active §5命令 | 原语义不重开；完整D6未PASS不能close Batch13 |

consumer Step2.1–Step3 已完成，不从 Step2.1 重做。S0/S1 调查已完成；剩余顺序以文末 S2–S7 为准。人工决策 A 的 consumer 合同保持，SOURCE 已裁定需要后端扩展，扩展范围尚待决定；完整 D6/Batch13 最终验收与自动恢复未完成。

## Exact verification commands

Step1 baseline：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_realtime_observation.py server/tests/services/test_history_service.py server/tests/services/test_playback_service.py
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history
```

Step2/3直接focused文件：`server/tests/services/test_queue_manager.py server/tests/repositories/test_task2_steps_5_7.py server/tests/services/test_autoplay.py server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_transitions.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_output_serialization.py`。每行只运行表中对应文件，末尾Step3运行其union。

Step3 consumer 的既有结果见 E 实施节；Step4 尚未进入。后续联合验收命令：R-TX/R-LIB/R-PL/R-PB/R-H/R-O/R-ARCH 使用 active Task6 §5 的精确命令（单一来源）。其它命令：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_recovery.py::test_reconnect_replaces_all_domains_and_epoch
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_recovery.py server/tests/api/test_realtime.py
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_*.py server/tests/api/test_realtime*.py
.venv/bin/python -m pytest -q server/tests/invariants server/tests/api
.venv/bin/python -m pytest -q server/tests
.venv/bin/python -m ruff check server/tests/invariants/test_d6_recovery.py
.venv/bin/python -m compileall -q server
git diff --check
git diff --stat
git status --short
```

Ruff 若有 production 修改须添加实际文件。Acceptance criteria 以 P §8.9 和 T6 §3 D6 义务为准；consumer 已验收并在 S0 指定范围复核；生产自然完成来源未验收，完整 D6 门禁仍 BLOCKED。物理 NAS/MPD/DAC/reverse-proxy 留 Task12。不得 commit/push/PR/merge。

## 2026-10-04 当前 checkout 审计与剩余实施顺序

本节为分析及实施建议，不新增领域authority、不批准来源技术路线或自动恢复接线。上文 consumer checklist/接口/selector 已按 S0 实证同步；E 中首次 RED 与逐行实施记录保留为历史，不能据此重做已有实现。领域 authority 仍为 Playback Spec §8.9，验收事实仍以唯一 D6 acceptance 最新节为准。

### S0 前的核对记录（保留历史结果；最新结果见文末）

- branch=`feature/task-6-realtime-state`、HEAD=`6b05d7f`。consumer在未提交工作区：15份tracked修改、2份untracked recovery源码；不能仅检查HEAD判断实现状态。
- 已核对当前evidence/validator、journal、PlaybackService、Queue complete_current、observation binding、PlayerPort/MPDAdapter/capabilities/main及专项测试。五项consumer定义已闭合，不重新列为未决领域选择。
- 本次实际执行 `.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py server/tests/invariants/test_realtime_recovery.py server/tests/api/test_realtime.py`：**112 passed，8.20s**（D6 98、Batch13两文件14）；仅既有Starlette/httpx warning。Python3.14.4/pytest9.1.1/Ruff0.16.9，`git diff --check`通过。此前355/1087 GREEN是上一实施窗口记录，本次未重跑完整集合。
- 生产代码没有构造CompletionEvidence或调用reconcile_external_status；main未注入completion_validator，默认None拒绝自然证据。现有测试通过不能证明来源或自动恢复可用。
- `docs/mpd-0.23.5-capabilities.md`固定目标0.23.5，9项verified_operations不含完成因果来源。main直接装配MPDAdapter，能力加载留Task10，不能假设生产已使用VerifiedPlayerPort。

### 剩余定义与接线缺口

| 项目 | 已冻结 | 仍须确定/实现 |
|---|---|---|
| 完成原因 | 真实来源验证，不能从STOPPED/时间/URI/未见Stop推导 | 哪个目标引擎事件证明自然完成；0.23.5是否支持，是否必须扩展引擎 |
| 身份与绑定 | service epoch、业务代次、server occurrence、transition ID | source epoch/sequence/连续性、MPD ID复用、事件产生时绑定；不能在迟到事件到达时倒填当前身份 |
| ended_at | 实际完成且不早于active.started_at | 来源时钟、时区、精度；接收时间不能未经定义冒充实际完成时间 |
| 消费确认 | outer commit后receipt，同ID重放 | 来源事件保留/ACK/重投接口；service嵌套返回APPLIED不能提前ACK |
| 断线/重启 | 连续性不可验证则UNKNOWN，不补History | 哪些连接故障失效证据、缺口/溢出规则、未来绑定重新建立方式 |
| 外部命令失败 | DB不撤销MPD，固定意图retry | 多条add/delete执行到一半、命令执行但响应丢失的分类与可恢复范围 |
| 接线 | PlaybackService是唯一业务编排者，observer/read/reconnect只读 | 生产来源+validator显式组合proof；自动runner/lifespan属于后续独立启用范围 |

官方协议的idle player是子系统变化通知，status是当前状态，不能直接作为本文要求的带原因/事件ID/实际结束时间的完成记录。参考[官方协议](https://mpd.readthedocs.io/en/stable/protocol.html)。该stable页面为0.24系列，仅作语义背景，不替代目标0.23.5源码/运行时验证。添加idle、single或consume开关本身不能解除SOURCE。

### 剩余执行步骤

- [x] **S0：同步实施基线。** 已保留全部未提交 consumer 修改，核对源码/diff/现有 selectors、E/B 最新节及 T §3/§5/Batch13；指定三文件 fresh **112 passed，1 warning，11.61s**。仅同步 P/E/B，未改 production/tests；原 RED 保留在 E 历史节。详见文末 S0 记录。
- [x] **S1：来源可行性裁定，调查完成 / 能力 BLOCKED。** 2026-10-04 已核查官方 v0.23.5 协议、player/decoder/queue 源码、C/可找到的记录及当前 Port/Adapter；逐项证据和裁定见文末。当前能力不可用，保持合同需要后端扩展；不是 producer 可行性 proof GREEN。若固定原版 NAS MPD 且不接受扩展，当前组合无法满足严格 SOURCE。S2–S7 未获本步实施授权。
- [ ] **S2：冻结来源合同与白名单。** S1证实可行后，在P §8.9定义原因/时间、source epoch/sequence、occurrence绑定、事件重复/缺口、连接连续性、ACK与outer commit、UNKNOWN处理。明确pending队列变更期间的旧事件与revision规则。然后更新本plan；候选修改为player/models.py、ports.py、mpd_adapter.py、capabilities.py、新来源实现、PlaybackService。main仅在后续启用阶段涉及。不得直接替换测试test-only/continuous常量冒充生产协议。
- [ ] **S3：来源与业务绑定TDD。** 建议新增player/completion_source.py，解析真实引擎事件并保留连续性/原始记录。由PlaybackService在已提交绑定上生成现有CompletionEvidence；validator核对原始来源事件与baseline。新增窄Service facade传递绑定，禁止仿照测试直接读取_recovery/_observations私有字段；Port不依赖Repository/History。未支持、未验证的来源默认拒绝。能力记录必须绑定目标版本与来源实现，不能只检查命令存在。
- [ ] **S4：补证MPD部分执行边界。** 当前actual既非original又非final即UNKNOWN，且新增MPD IDs在全部queue_add完成后整体登记；部分add/delete成功后的retry存在静态可见覆盖缺口，本次未新增故障复现。先对每条add/delete/play前后注入失败，取得实际RED/行为证据，再按S2确定的边界修复。可证明属于本意图的已确认前缀若允许继续，journal须逐命令保留结果和固定IDs；响应丢失/断线/外部漂移导致不可归属时必须UNKNOWN，不能按URI猜ID或盲重发add。不得承诺所有MPD失败均可自动恢复。
- [ ] **S5：显式端到端能力证明，不开loop。** 使用生产来源实现/validator/Adapter与真实Services/SQLite，显式驱动读取→绑定→reconcile→outer commit→来源消费确认。覆盖successor/autoplay/empty、重复occurrence、错误原因拒绝、断线/重启、提交前后故障、同ID retry/replay。协议模拟器只证明实现符合输入协议，另需S1的目标因果语义证据，不能让模拟器凭空生成natural来替代。需要目标运行时试验时单列授权/环境，不擅自联系NAS，物理DAC仍留Task12。
- [ ] **S6：联合验收，再关闭Batch13门禁。** 新增精确selector→source/adapter/专项文件→原直接focused→active T6 §5全部R集合→指定reconnect selector→两份Batch13文件→realtime全集→invariants+API→server/tests→scoped Ruff/compile/diff/status。唯一D6 acceptance记录来源proof及局限；Batch13引用结果。S1/S5未通过，不因全套GREEN关闭D6。
- [ ] **S7：自动恢复另列后续启用。** 若需要自动恢复，另行定义单实例runner、生命周期、超时/退避、UNKNOWN暂停、提交后ACK、关停取消和重新绑定，在main/lifespan装配，仅调用PlaybackService。不在StateObserver/GET/WS/reconnect中执行恢复。S6能力验收与自动启用分开，不给Batch13增加未要求的loop实现。

### 新增测试目标（全部TO CREATE / 本次未执行）

以下在S1/S2冻结后落地；名称不代表来源已经存在。

| 文件/selector | 必须证明 |
|---|---|
| server/tests/player/test_completion_source.py::test_source_distinguishes_eof_from_controls_and_errors | natural与stop/next/seek/error不混淆 |
| 同文件::test_source_invalidates_continuity_on_gap_disconnect_restart | 缺口/断线/重启拒绝旧证据 |
| 同文件::test_source_binds_duplicate_uri_to_committed_occurrence | 重复URI、ID复用、迟到事件不误绑定 |
| server/tests/invariants/test_d6_recovery.py::test_recovery_partial_player_mutation_retry | 已确认前缀或不可归属中间态分别恢复/UNKNOWN，零重复History |
| server/tests/invariants/test_d6_source_recovery.py::test_production_source_drives_explicit_recovery | 真实生产来源实现与consumer联合路径，不用TestCompletionValidator替代 |
| 同文件::test_source_ack_waits_for_outer_commit | outer失败不ACK，提交后交付失败保留receipt，重投REPLAYED无重复通知 |
| 同文件::test_source_unavailable_keeps_observer_and_reads_read_only | 来源不可用不使GET/WS/observer执行恢复控制 |

每项先创建测试，再用 `.venv/bin/python -m pytest -q <完整文件>::<selector>`验证真实RED，最小实现后重跑同selector与直接回归。本节给出有明确能力停止条件的顺序；S1 已裁定需要后端扩展、能力仍 BLOCKED，不能将尚不存在的引擎能力包装为无条件可执行的最终代码方案。


## 2026-10-04 S0 基线核对与文档同步（已完成）

实际 checkout 为用户指定目录；branch=`feature/task-6-realtime-state`，HEAD=`6b05d7f434024488a736db5be83ada82bb0abf91`。起始已有 15 份 tracked 修改及 2 份 untracked recovery 源码：8 份 production、6 份 tests、P/E/B 三份文档；并非 clean，也不是仅 HEAD 中的实现。全部保留，S0 仅编辑 P/E/B。

核对了 recovery 类型/validator、journal、PlaybackService 分类/确认/outer receipt、Queue CAS、AutoPlay planner、History Stop session 收尾、observation execution binding，以及未提交 production/test diff。矩阵所列 consumer selectors 均已存在；现有专项另含业务代次、完整 U/旧 terminals、commit fault、并发 barrier、Queue CAS 与确认样本绑定 proofs。三个旧冲突 selectors 已迁移；两份 Batch13 Python proof 无 diff。源码/测试存在与本次 GREEN 支持 consumer 当前基线，不将 E 的历史 RED 或上一窗口完整回归冒充本次结果。

本次唯一测试命令（仓库根目录，既有 .venv）：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py server/tests/invariants/test_realtime_recovery.py server/tests/api/test_realtime.py
# 112 passed, 1 warning in 11.61s, exit0（D6 98 + Batch13 14）
```

环境核对：Python3.14.4、pytest9.1.1、Ruff0.16.9，已读 server/requirements.txt；无环境或测试失败，仅既有 Starlette/httpx warning。未重跑 355/1087、全部 R 集合、Ruff 或 compileall；这些仅保留 E 的前次记录。未联网、未访问 live MPD/NAS，未用 Docker，未改依赖/环境/本地数据库。

SOURCE 实证边界：`server/app` 没有构造 CompletionEvidence 或调用 reconcile_external_status 的生产路径；main 直接装配 MPDAdapter/PlaybackService，未注入 completion_validator，默认 None 拒绝自然证据。PlayerPort/Adapter/capability record 尚无因果完成来源；目标 0.23.5 的 9 项 verified_operations 不含该能力。测试 TestCompletionValidator 的 test-only/continuous 输入只证明 consumer。部分 add/delete 的中间态仍为 S4 待补证范围，本步不复现、不修复、不宣称已闭合。

**结论：S0 COMPLETE；Step2.1–Step3 consumer 已实施/验收，且指定范围 fresh GREEN；D6-SOURCE BLOCKED，完整 D6/Step4/Batch13/Task6 final NOT COMPLETE。** S1–S7 未执行；不存在的 SOURCE selectors 继续明确 TO CREATE。生产/tests 字节比对、Batch13 proof diff、git diff --check/stat/status 均完成；未 commit/push/PR/merge。

## 2026-10-04 S1 生产来源可行性裁定（调查完成，能力 BLOCKED）

**裁定：需要后端扩展。当前 PlayerPort/MPDAdapter + 原版 MPD 0.23.5 无法满足 F §8.9.1 的严格因果证据合同；不能仅扩展 Python Adapter 或添加推断 validator。** 若固定未扩展的 NAS MPD、不允许更换后端，则在该约束下无法满足。这里完成的是 S1 调查与裁定，不是 SOURCE capability proof；S2–S7、Step3-SOURCE/Step4、完整 D6、Batch13/Task6 final 继续 BLOCKED。

### 基线、权威与实测材料边界

- 起始 checkout clean；branch=`feature/task-6-realtime-state`，HEAD=`651aade83d0df52601f4555e0a682c9f16afd25e`。consumer 已在该提交，不能沿用 S0 的未提交基线。只修改 P/E，不修改 C/B/F/A/T/M、production/tests。
- 已读 P/E/B、F §7/§8.8–8.9/§10、A §12.1–12.3、T §3/§5/Batch13、M Task4/Task6 与 Dependency/Relationship gate、C；独立核对当前 Port、models、Adapter、capability probe、main 和 consumer。
- M 的依赖仍为 Task4 ← Task1R/Task2R/Task3；Task6 ← Task3/Task4/Task5/Task7，自动恢复/最终验收另需 D6。Task4 不能依赖 Task6/Task8 客户端或 WS 补出原因；Task10 能力装配、Task12 物理验证也不能提前视为已完成。
- C 的 2026-09-26 probe：104 commands、17 status fields、ACK 与未知命令关闭连接；2026-09-27 transport：9 个 verified_operations。均不含自然完成因果、事件连续性、重复 occurrence 完成或 ended_at 验证。C 未实测的内容本步不补填。
- `git ls-files '*probe*'`、`git log --all -- '*probe*.json'`、本地 `/home/Gold/WorkSpace` 和 `/home/Gold` 可读文件名搜索均未找到 C 引用的 `mpd-0.23.5-probe-2026-09-26-091948.json` 或第二次原始 JSON；M Task1 Step7 明确首份保存在 NAS。`85a24f6`、`4453eb1` 的记录提交可找到，但不包含原始 JSON。原始 probe **未取得**，没有连接 NAS 重取或运行新 probe；只能引用 C 既有摘录，不能宣称重新核验全部原始响应。
- 下面核查的是官方 **v0.23.5 tag**，不使用 stable/0.24 推导目标能力。[该 tag 协议说明](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/doc/protocol.rst#L23)指出 greeting 标识协议版本；C 记录 `OK MPD 0.23.5` 是已有事实，不能仅据此认证 NAS 二进制与上游 tag 完全相同。本次没有取得 NAS build/hash/补丁清单，静态结论与目标运行时验收分开。

### 官方接口与源码证据索引

| 来源（均固定 v0.23.5） | 核查事实及限制 |
|---|---|
| [协议 doc/protocol.rst](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/doc/protocol.rst) / clearerror、idle、status、queue IDs | status 是当前快照，不含离开原因、事件身份或结束时间；idle 返回变化子系统。error 可以被 clearerror/开始播放清除。重复 URI 入队有不同 ID，但 ID 不是播放代次。 |
| [client/Idle.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/client/Idle.cxx#L31) / WriteIdleResponse、IdleAdd | 位集 OR 合并变化，仅输出 changed；连接内保留变化标志不等于逐事件保留。没有原因、序号、cursor、ACK 或重连事件补取。 |
| [command/PlayerCommands.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/command/PlayerCommands.cxx#L110) / handle_status、stop/next/seek handlers | 完整 status 打印无 completed/reason；STOP 时不打印 elapsed/duration。各控制命令进入 Partition，没有向旁观客户端输出命令发起者/原因事件。 |
| [queue/PlaylistControl.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/queue/PlaylistControl.cxx#L32) / Stop、PlayNext、SeekSongOrder | 显式 Next 在队尾也 Stop，consume 下 Next 也能删除旧项；seek 可改变曲目并清除 error。single/consume 不是独有自然完成标记。 |
| [queue/Playlist.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/queue/Playlist.cxx#L191) / SyncWithPlayer、ResumePlayback | STOP 后按 error/队列决定 Stop 或 PlayNext；无完成原因记录。内部自动与显式控制可抵达相同目标。 |
| [player/Thread.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/player/Thread.cxx#L697) / ProcessCommand、SeekDecoder、SongBorder、Run | STOP/EXIT/CLOSE_AUDIO 退出；seek 超过时长会截到终点。尾部排空与其它退出统一清理并设 STOP。SongBorder 与统一清理都写 played URI；Stop/error 也可写该日志。 |
| [decoder/Control.hxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/decoder/Control.hxx#L227)、[decoder/Thread.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/decoder/Thread.cxx#L439)、[DecoderAPI.hxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/decoder/DecoderAPI.hxx#L47) | IsIdle 包括 STOP/ERROR；StopDecoder 被捕获后返回 true，普通 success 归 STOP；read=0 可表示 EOF、error、SEEK 或 STOP。decoder idle/普通返回本身不足以证明 EOF。 |
| [FlacDecoderPlugin.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/decoder/plugins/FlacDecoderPlugin.cxx#L168) / flac_decoder_loop | 正常 END_OF_STREAM 与 fatal/seek flush 失败均可 return；process_single 失败也可日志后 break。此静态反例说明 error 缺席不证明正常 EOF；不是 NAS 故障实测。 |
| [queue/IdTable.hxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/queue/IdTable.hxx#L64)、[QueueSave.cxx](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/queue/QueueSave.cxx#L97) | ID 分配回绕可复用删除槽；队列载入 Append 重建项。需区分 daemon epoch、entry 身份和同 entry 的每次播放，不承诺 MPD ID 跨重启稳定。 |

### 场景判别矩阵

此表把“当前能观察什么”和“扩展必须补什么”分开；引擎内部控制点不是已经可用的生产来源。

| 场景 | 当前证据 / 来源 | 能否区分原因；所需可信证据 |
|---|---|---|
| 自然 EOF（有 successor / 队尾） | player Run 尾部 drain 或 SongBorder；对外当前 songid/state、idle player、played URI | **不能**。必须保留 decoder 正常 EOF 与该播放代次的输出边界完成，排除命令、seek 和错误后输出事件；解码读完时间不是实际播放完成时间。 |
| Stop | 本连接 stop 的 OK/实际回读；外部 Stop 仅最终状态。ProcessCommand 退出也走统一清理 | 本服务显式请求+确认支持原 Stop 合同；旁观状态不证明发起者。扩展须记录全客户端生效控制与代次。未见 Stop 请求不证明 natural。 |
| Next（含队尾） | PlayNext→PlayOrder 或 Stop；consume 可删除旧项；最终目标可能与自然推进一致 | **不能**凭 nextsong/current/队列删除区分。需独立 command/control 原因，并关联旧、新播放代次，不能复用 PlayNext 方法名当 natural。 |
| seek 到终点 | SeekDecoder clamp + decoder/pipe 后续排空；idle 不带 seek 目标/因果链 | **不能**凭 elapsed=duration/排空区分。须保留 seek 生效位置、代次和终止原因；终点 seek 不能包装为自然证据。seek 后播放剩余段的接纳规则另待 S2 冻结。 |
| 播放错误（解码/输入/输出） | 部分进入 status.error；ResumePlayback 可能跳过；FLAC 某些失败普通返回 | error 可提示错误，不能仅以空 error 判 natural。扩展须贯通插件显式 EOF/error/cancel 分类与输出失败；不能保留原版的原因丢失后再推断。 |
| 外部换曲（playid/seekid/Next、离开后返回同项） | songid/URI/queue 快照变化；没有外部客户端来源记录 | **不能**与自然换曲可靠区分；同项重新播放可能在采样间不可见。需全客户端控制序列与每次播放 generation；迟到证据不能倒填当前业务绑定。 |
| 重复 URI / 同 entry 重播 | playlistinfo/songid 可区别同时存在的队列项；played 日志只有 URI | 能区分槽位，**不能证明完成原因/播放代次**。需 epoch+entry ID+playback generation 在事件产生时绑定已提交 queue_item_id/业务代次；包含 ID 复用、迟到和重复事件 proof。 |
| 断线 / MPD 重启 / 服务重启 | EOF/timeout、重连 greeting/status/stats；idle 无补取；queue ID 可重建 | **不能**证明遗漏转移或连续性。须事件序号、source epoch、缺口/溢出检测；按 F 当前合同失效 continuity、旧证据 UNKNOWN，不补 History。来源留存仅服务同进程 retry/ACK，不新增跨重启恢复承诺。 |

不可区分性的具体对照：正常 A→B、外部 next A→B、seek A 到尾后 A→B 均可能只留下当前 B、同一队列与一个 player 变化标志；错误字段还可被后续播放清除。断线窗口内更无法还原完整命令序列。因此提高采样频率、独占本服务连接、记录本服务全部命令、single/consume、解析 played 日志或 sendmessage 传自报原因，都不能补齐所有客户端/decoder 的因果证明。这里是源码可达性分析，不是伪造 NAS 对照实验。

### 当前 Port/Adapter 与 consumer 接线核查

`server/app/player/ports.py::PlayerPort` 只有读取/控制，无因果事件读取、source epoch/sequence、绑定或 ACK。`models.py::PlayerStatus` 不含 error/终止原因；`PlayerEvent(kind,status)` 没有生产来源实现。`mpd_adapter.py::status` 顺序读 status/currentsong，锁仅保护本连接，不隔离其它 MPD 客户端；`_status_from_response` 未保留 status.error。Adapter 断线会丢弃连接并重建，但没有 daemon epoch 或事件连续性。

`capabilities.py::_probe_transport_runtime` 的 queue_play 以 playid 命令成功记 verified，不等待 EOF；既有九项不能用于 SOURCE 背书。`main.py` 直接装配 MPDAdapter/PlaybackService，completion_validator 未注入；`PlaybackService` 默认拒绝自然证据。rg 核查无生产 CompletionEvidence 构造或 reconcile 调用；测试 validator 不进入此裁定。单加 idle/error 读取只能改善观察/诊断，不能解锁自然消费。

### 推荐路线与必要决策（建议，不是新增 authority 或实施授权）

推荐保持 F 合同，先定义一个**受控、可核验的 MPD 后端扩展前置工作**，再执行 S2–S6；不写基于 stock status 的 producer。

1. **部署范围**：是否允许维护/部署 NAS 上版本固定的扩展 MPD，并取得 daemon build/hash、补丁来源和目标 conformance；只修改本仓库 Python 不够。若拒绝，保留 BLOCKED；其它选择需明确批准提供等价因果能力的后端，或由用户修订 F/阶段门禁，本步不降低合同。
2. **原因产生与媒体范围**：decoder/plugin 显式传递 EOF/error/cancel，player 按准确输出边界完成确认，控制/seek 与边界串行化并保留 generation。不能只在 Run drain 分支增加 natural；覆盖预解码、gapless/crossfade、子曲目/范围以及插件错误普通返回。先限定可验证 decoder/媒体；未验证格式、直播流或不明确 EOF 均 fail closed。支持列表不能由 C 的 commands 推出。
3. **seek 和时间**：终点 seek 与正常 EOF 分开；seek 后余段完成及 crossfade 的结束边界、UTC/单调时钟关系、精度和 started_at 校验须在 S2 冻结。接收时间不冒充 ended_at；不承诺物理 DAC 听觉时间。
4. **事件与业务绑定**：来源记录建议含 source epoch、单调序号/transition ID、partition、entry ID、playback generation、明确原因、完成时间/时钟信息及控制因果。来源只保存引擎事实，Service 在事件产生所对应的已提交绑定上关联业务；Port 不访问 Repository。需解决绑定注册/播放确认与外部命令交错、pending revision 变化，不在迟到时填写最新 current。
5. **留存与提交**：提供可验证事件读取/重投/ACK、有限留存和 gap/overflow 标志；ACK 必须在 outer commit 后。同进程 rollback 不丢原事件；提交后交付失败重投走 receipt。断线/重启按 F 失效旧 continuity 并 UNKNOWN，重新显式建可信绑定；若要跨断线接纳旧证据，必须先修订 F，不能由来源日志暗中扩大范围。

可行性层次：源码表明原因可在插件/控制/播放边界丢失前捕获，支持提出上述扩展路线；**尚无实现、构建/部署 proof、NAS二进制核验或目标对照实测，不声称扩展已可用或所有 decoder 均能满足**。若后端范围未决定，S2 只能等待该决策；SOURCE 新 selectors 仍 TO CREATE，不以协议模拟器人为 natural 替代目标语义。

本步使用 research/执行计划/完成前验证技能，只读官方网络材料与本地文件；未运行 pytest/Ruff/compileall 或新 probe，未改生产、tests、环境、依赖/schema/数据库，未用 Docker/live MPD，未 commit/push/PR/merge。文档检查和源码/tests 字节保全结果见 E 的 S1 最新验收节。
