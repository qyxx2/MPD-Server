# Task4 D6-RECOVERY corrective plan

> 使用 superpowers:executing-plans 顺序执行；遵循 systematic-debugging、test-driven-development、verification-before-completion。本次仅完成 Contract Gap Resolution；后续窗口按本文逐行为执行，不提交、不启动自动恢复。唯一新增语义为 Playback Spec §8.9，本文只分解该权威合同。

**Goal:** 实施已批准的保守 D6 consumer 合同，并明确生产因果证据能力门禁；consumer GREEN 不替代完整 D6 验收。

**Architecture:** PlaybackService 编排 Queue/History/AutoPlay/PlayerPort；Repository 管理同库 outer transaction，runtime hooks 恢复 History/observation。Task6 observer/snapshot/reconnect 保持只读。

**Tech Stack:** 既有 Python `.venv`、SQLite、pytest、Mock/Fake PlayerPort。

**Spec:** Playback Spec 2026-09-24 §6–8.9/§10；Architecture Spec 2026-09-25 §12.1–12.3/§19.5；主 Implementation Plan Task4/Task6/Dependency/Relationship/Contract Matrix；active Task6 plan §3/§4/§5/Batch13；Task5 archived batch plan §3.7。

## Constraints / files

- 原 checkout/branch；既有环境，不修改依赖/schema，不使用 Docker/live MPD。
- 不重开全部 Task4，不扩展 Task6/Task8；不引入 loop、scheduler 或 MPD occurrence 持久映射。
- 起始三份 Batch13 文件已在 `82391fc`，不得改其测试以掩盖 D6。
- 本窗口生产白名单：**无**；下列文件仅供下一窗口实施。没有 API/observer/main/MPDAdapter 接线授权。
- 下一窗口生产白名单：`services/playback_service.py`（分类/确认/事务/传播）；新增 `models/recovery.py`（内部 evidence/result/intent 类型）、`services/playback_recovery.py`（进程 epoch、业务代次、pending intent/receipt，调用者仍为 PlaybackService）；`services/queue_manager.py` + `repositories/queue_repository.py`（唯一自然完成 Queue 转移，保留完成 occurrence，原方法合同不动）；`services/autoplay.py`（仅提取既有候选规划以固定 retry IDs，不改变来源/算法/low-watermark）；`services/playback_observation.py`（仅提供既有绑定校验及恢复提交绑定，保留只读采样）。所有路径在 `server/app/` 下。
- 无需修改 schema、PlaybackState 枚举、HistoryReason、HistoryService finalizer 或 database/idempotency/realtime coordinator；使用现有 hooks。若实际证明白名单仍不足，先修订最小依赖，不能默认扩展。
- 测试白名单：专项 `server/tests/invariants/test_d6_recovery.py`；仅下文列明的三个旧 reconciliation selectors 允许按新 Spec 改写；`server/tests/invariants/assertions.py` 仅将 STOPPED 检查拆分为显式 Stop 与无候选组合，不弱化其它断言；AutoPlay/Queue 的直接 focused 测试可按新增接口补最小案例。不得改两份 Batch13 Python proof。
- 本轮 proof：`server/tests/invariants/test_d6_recovery.py`。唯一专项 acceptance：`docs/superpowers/archive/task-4/2026-10-04-task-4-d6-recovery-acceptance.md`。既有 Batch13 acceptance 仅追加本轮 blocker 状态。

## 人工决策 / Gap 审核

2026-10-04 用户明确选择方案 **A**，批准五项保守决策及 §7 STOPPED 含义修订。新增 authority 全部在 P §8.9；不创建第二份 Spec/计划。已有约束：显式 Stop 请求+实际确认、PB-HISTORY 未确认不写事件、可用 successor/AutoPlay 候选原则、DB/runtime rollback、REST scope/key replay、observer 只读。真正新增：因果证据接纳、漂移分类/返回、无候选终态组合、恢复身份/同进程 retry。

五项**领域消费合同已闭合**；自然完成**生产可信来源机制尚未确定/验证**，记为 `D6-SOURCE` 能力 blocker，不能声称整个自然识别 Gap 消失。路线 A 允许先做 consumer TDD；只有来源生产者能力 proof + consumer proof 联合 GREEN 才能通过 D6。Task6 G6-01–05 仍闭合，无重新设计 Task6。

## 内部接口与文件职责（TO CREATE，不是当前实现）

- `models/recovery.py`：不可变 `CompletionEvidence`，字段 `service_epoch:str, source_id:str, source_epoch:str, continuity_token:str, business_generation:int, queue_revision:int, queue_item_id:str, mpd_song_id:int, transition_id:str, ended_at:datetime`；验证来源由注入内部 evidence validator 完成，不接受 public bool/reason。`RecoveryResult` 字段 `outcome:Literal["UNKNOWN","UNCHANGED","APPLIED","REPLAYED"], playback:PlaybackState|None, transition_id:str|None, reconciliation_required:bool, diagnostic:str|None`。REPLAYED 表达读取 receipt，其 playback 是原回执，不改写为实时值。
- `PlaybackService.reconcile_external_status(self, *, evidence:CompletionEvidence|None=None) -> RecoveryResult`：无参调用仍可用，未知正常返回，typed source failure/confirmation conflict 抛异常。所有调用者已 rg 搜索：只有测试与显式方法，无生产恢复 loop/API 调用，不改 wire DTO。PlaybackService 构造器新增可选 keyword `completion_validator:CompletionValidator|None=None`，journal epoch独立于Task6协调器；证据 validator 为内部依赖，默认拒绝全部自然证据；测试提供 deterministic validator，不能标生产 GREEN。
- `models/recovery.py` 另定义 `RecoveryIdentity=tuple[str,int,str,str]`；不可变 `RecoveryBaseline(queue:QueueSnapshot, playback:PlaybackState, history:HistoryAvailability, business_generation:int, mpd_song_id:int)` 和 `RecoveryPlan(identity:RecoveryIdentity, evidence:CompletionEvidence, baseline:RecoveryBaseline, pending:tuple[QueueItem,...], successor_id:str|None)`。注入 `CompletionValidator.validate(evidence:CompletionEvidence, baseline:RecoveryBaseline) -> Awaitable[bool]`；false按UNKNOWN保留，source typed error原样抛出。测试validator只为测试来源背书，默认生产validator始终false。
- `playback_recovery.py`：`RecoveryJournal` 保存独立业务代次、当前绑定、pending plan 和 receipt；`get_receipt(identity:RecoveryIdentity, evidence:CompletionEvidence) -> RecoveryResult|None`、`prepare(evidence:CompletionEvidence, baseline:RecoveryBaseline, planned_pending:tuple[QueueItem,...]) -> RecoveryPlan`、`commit(identity:RecoveryIdentity, result:RecoveryResult) -> None`，全部只由 PlaybackService 在既有事务边界使用。prepare 固定目标与新 occurrence IDs；commit 先在事务内深复制/验证结果并保留未消费槽位，outer-visible hooks只切换已提交状态，不能把结果materialization留到提交后；若提交后journal无法可靠提供receipt，隔离该journal并拒绝执行旧ID，不能再写History。rollback 恢复业务代次/绑定，pending 不丢。业务代次不可使用每次 observation 的 generation 作为持久播放身份；所有成功 current-changing 原入口须在此更新/失效，pause/seek 不制造新 occurrence。
- `AutoPlay.plan_refill(context:PlaybackContext, snapshot:QueueSnapshot) -> tuple[QueueItem,...]`：纯候选规划，复用现有候选算法/availability/5+5规则；普通 refill 沿用原行为。恢复 journal 仅首次规划，retry 不重分配 ID。
- `QueueManager.complete_current` 使用下述同一参数/返回签名，转发 → `QueueRepository.complete_current(queue_item_id:str, *, pending:tuple[QueueItem,...], successor_id:str|None, expected_revision:int) -> QueueSnapshot`：一次 CAS 业务转移；pending 是固定最终有效项+已规划 AutoPlay 项，successor 必须属于 pending 或为 None。验证旧 current、保留项身份及顺序、新项 source=AUTOPLAY；完成项移到 -1，已有 Played 顺序保留，目标0/其它pending连续，无目标无 execution；单次 +1 revision。不能作为任意覆盖 Queue 的通用接口。
- 使用 `HistoryService.complete_naturally(ended_at=...)` 与 `start_track(...)`、`preserve_active_on_rollback()`；不调用 `next()`/delete 模拟自然完成，不改变它们的 reason。

## Contract Matrix Impact Analysis

Relationship Gate **REQUIRED / FAILED**；Contract Matrix 定义 **CLOSED for consumer / production source BLOCKED**，实现验收仍未通过。
Owned modified：PB-HISTORY-001 的自然 consumer 扩展。新增稳定 rows：PB-RECOVERY-UNKNOWN-001、PB-RECOVERY-TRANSPORT-001、PB-NATURAL-001、PB-NATURAL-EMPTY-001、PB-RECOVERY-RETRY-001。D6-RECOVERY 仍是阶段验收 ID。Relied unchanged：PB-STOP-001、PB-NEXT-UNAVAILABLE-001、TX-ROLLBACK-001、TX-IDEMP-001、EVENT-PORT-001。Regression：PB-INSERT/REORDER/DELETE-PENDING/DELETE-CURRENT-001、PL-REP/COLLECTION-001、O-PRESERVE/STATE/EVENT-001、RT-OBSERVE/SNAPSHOT/PLAYBACK/RECOVER-001。

### 共同字段（每行组成部分）

Preconditions：真实 Services/同库 Repository/verified PlayerPort；自然行另需 P §8.9.1 evidence validator。Authorities：PlaybackService 编排，Queue/PlaybackState 持久，History 持久+active/session，MPD 外部事实，journal runtime；网络不是业务 authority。

U：除行中列出的 delta，保持 Queue occurrence/source/context/相对顺序，PlaybackContext，History 旧记录，Playlist/Favorites 全资源与 Library 内容/revisions，Output observation/request/MPD outputs，全部既有 REST terminal；无新 REST endpoint/terminal。行 F/T/I 优先于普通成功 delta。

T/F：同库 outer transaction；当前 binding、History active/session、业务代次一起回滚；未提交结果不作 success receipt。确认/写入/materialization/terminal/outer failure、提交前取消无成功事件，pending 意图保留；提交后取消/交付失败保留提交/receipt，登记传播遵守 A §12.2。MPD 副作用不撤销，retry 必须实际重读。只有实际 Queue delta 增 revision；成功联合变化 outer commit 后传播，unknown/no-op/replay 无 mutation notification。

| ID / Type / authority | Preconditions / Expected delta | U / confirmation / History | Failure / Retry / Observable | Executable proof（专项文件，TO CREATE 除首个） |
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

## Ordered Steps（本窗口不执行）

- [x] **Step1 — Git/environment/authority审计与精确真实RED**。既有专项测试保留不变；本轮重新运行仍1 failed。人工A已写入P §8.9，生产来源仍BLOCKED。

- [ ] Step2.1 UNKNOWN / 原专项RED闭合。
- [ ] Step2.2 身份与证据拒绝。
- [ ] Step2.3 bound transport。
- [ ] Step2.4 natural successor consumer。
- [ ] Step2.5 natural empty consumer。
- [ ] Step2.6 rollback/retry。
- [ ] Step2.7 replay/commit边界。

每个 Step2 行必须依序：①写该行最小 test/literal assertions；②精确 selector RED（fixture/setup失败不算）；③最小白名单实现；④相同selector GREEN；⑤专项文件及列明直接回归 GREEN；⑥diff/isolation。命令统一展开 `.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py::<下表函数>`。TO CREATE selector 尚不存在，不得声称可直接执行或已GREEN。每行完成这六个检查才进入下一行，先闭合Step2.1原RED。

| Step | selector / literal assertions及实现动作 | 直接回归 |
|---|---|---|
| 2.1 UNKNOWN | 既有 test_unclassified_external_stop_does_not_fabricate_history 原样先RED→GREEN；新增 test_unknown_recovery_preserves_all_authorities 参数stop/foreign/duplicate/missing-id/queue-mismatch/unbound及elapsed-at-end：`outcome=="UNKNOWN"; reconciliation_required is True; before==after; controls==[]; receipt is None`。新增 test_recovery_source_failure_preserves_authorities 对不可达/命令错误断言原typed exception、全部保留。最小修改reconcile入口与result，不隐含修复_save_confirmed_status其它operation | 三个冲突selectors按下节改写；R-PB，observation |
| 2.2 identity/evidence拒绝 | test_recovery_rejects_stale_evidence 参数epoch/generation/occurrence/source-continuity/restart/missing-active/invalid-time：UNKNOWN、全部保留、零控制。引入journal和validator默认拒绝；内部验证Fake可固定valid token，旧业务成功current入口更新journal代次。不要把unknown测试升级为可信natural | R-PB/R-TX/R-ARCH |
| 2.3 transport | test_bound_external_pause_resume_preserves_history 参数pause/resume/no-op：APPLIED/UNCHANGED、同queue/context/session/active/autoplay、无事件reason/控制。test_transport_recovery_rollback_and_retry 用outer failure及precommit cancellation，回滚before；retry后唯一playback通知、无History | stop、observation、realtime transitions、Output serialization |
| 2.4 natural successor | test_natural_completion_promotes_confirmed_successor 参数pending/missing/unreadable/absent/already-playing/confirmation-fails；test_natural_completion_refills_once 参数autoplay/one-song；test_duplicate_song_completion_uses_occurrence_identity 参数正确/错误同URI occurrence。`events==[(old,"NATURAL_COMPLETION")]; active.song_id==target; session==old_session; context==old_context; autoplay is True`；完成ID -1、目标ID0、其它身份保持，实际目标id/state/Queue全匹配，confirmation失败before==after/no receipt。先测试再提取AutoPlay plan/Queue complete_current/自然编排；已到目标controls无play | Queue/AutoPlay focused、R-PB/R-H/R-TX、realtime transitions |
| 2.5 natural empty | test_natural_completion_without_candidates_retains_session：空可用库+无效pending，valid completion；`(state,song,position,autoplay)==("STOPPED",None,None,True); active is None; session==old_session; context==old_context; no position>=0; old_id.position==-1; events==[(old,"NATURAL_COMPLETION")]`。实际STOPPED/空execution、无stop command；后续显式Stop才session=None/autoplay=False。修订helper仅按两种STOPPED组合检查 | R-PB/R-H、Queue/AutoPlay focused、snapshot |
| 2.6 rollback retry | test_recovery_rollback_retry_keeps_identity 参数target=successor/autoplay/empty × failure=confirmation/history-write/queue-write/state-write/outer/materialization/terminal/precommit-cancel。失败后完整业务snapshot==before、无receipt/成功通知，intent固定且MPD副作用单独记录；retry同ID不重分配/重播/Next，History恰一次。人为外部漂移retry UNKNOWN；合法新current后旧intent拒绝。terminal case通过真实IdempotencyService outer test harness，不新增API；纯Service receipt case独立验证 | R-TX/R-PB/R-H |
| 2.7 replay/commit边界 | test_recovery_replay_and_conflict：同ID结果playback等于原receipt，outcome=REPLAYED，零History/controls/revision/event；改内容抛ReconciliationError。test_recovery_post_commit_failure_preserves_receipt 参数cancel/publisher/visibility-registration：成功提交保留；registration失败按现有A §12.2使snapshot不可用，不执行rollback hooks。重复业务后重放旧receipt仍不改变新current；restart旧epoch UNKNOWN。outer hook/barrier证明receipt消费及通知不早于commit | commit hooks、realtime delivery/transitions、R-TX/R-ARCH |

### 旧证明冲突的最小迁移（Step2.1/2.3，不在本窗口改测试）

- `server/tests/services/test_playback_service.py::test_reconcile_external_status_updates_service_state_but_not_server_queue`：改为外部b UNKNOWN，全业务状态不变。不能继续允许Playback/active=b但Queue current=a。
- `server/tests/api/test_pre_batch6_corrective.py::test_reconciliation_outer_rollback_restores_history`：stop/foreign分支按UNKNOWN无delta，保留outer失败全状态恢复；额外bound pause分支验证有delta时outer rollback与retry。未知retry绝不产生STOP/SWITCH_AWAY。
- `server/tests/invariants/test_realtime_transitions.py::test_explicit_reconciliation_propagates_only_committed_existing_delta`：stopped分支UNKNOWN、零producer sequence/event；pause分支保留outer rollback、提交后唯一playback notification与重复no-op，History/session不变。其它三个测试文件中的无关selectors不改。
- `invariants/assertions.py::assert_execution_relationship`：显式Stop继续active/session=None；自然empty分支要求无current+autoplay=true+active=None+session保留，不能删除session断言。专项测试必须另外固定期待的旧session值，helper不能自行“猜”状态正确。

- [ ] **Step3 — consumer专项验收**：Step2全部GREEN后，专项文件→Queue/AutoPlay/三项迁移文件→R-PB/R-H/R-TX/R-O/R-ARCH→scoped Ruff/compile/diff。逐行U包括真实Library/Playlist/Favorites/Output内容、全部旧REST terminals和revisions，不仅server_snapshot五元组。用barrier证明并发mutation/晚证据不会覆盖新current。记为consumer PASSED仍不是D6 PASSED。
- [ ] **Step3-SOURCE — production能力门禁，当前BLOCKED**：需明确真实因果证据来源、Port/Adapter能力验证、断线/重启continuity与重复occurrence proof，修订本计划白名单后才实现该producer。不接受只注入Fake、扩展status reason或旧单元GREEN作为解除证据。本窗口不虚构selector；这里因能力接口尚不存在不能建立生产proof，明确是剩余可执行性缺口。
- [ ] **Step4 — 完整D6与Batch13最终门禁**：Step3+SOURCE联合fresh GREEN后才进入active T6 §5/Batch13最终序列。仍不启用自动恢复loop；更新唯一acceptance，另行授权才可执行后续接线或提交。

## Acceptance / Spec→Contract→Step→proof 审查

| authority | row → Step → consumer proof | 审查结论 |
|---|---|---|
| P §8.9.1–2禁止推测/漂移接纳 | UNKNOWN/TRANSPORT → 2.1–3 → 精确selectors | 可开始；现有unknown真实RED尚未修复；旧三项proof冲突已显式安排 |
| P §8.9.3 successor/empty | NATURAL/EMPTY/HISTORY → 2.4–5 → 精确selectors | consumer可实施；evidence只用明确Fake validator，不能外推生产 |
| P §8.9.4 identity/rollback/retry | RETRY/TX-* → 2.2/6/7 → 精确selectors及真实outer harness | 同进程可实施；断线continuity失效/重启拒绝旧证据，不承诺持久replay |
| P §8.9.5生产可信来源 | D6-RECOVERY → 3-SOURCE | BLOCKED；缺少producer机制/接口/可执行selector，未掩盖为合同全闭合 |
| A §12.1–3/§19.5；T6 Batch13 | regression/RT-* → 3/4 → active §5命令 | 原语义不重开；完整D6未PASS不能close Batch13 |

下一窗口可以**从Step2.1逐行为TDD开始**，其后仅实施consumer。不能开始SOURCE、完整D6 acceptance或Task6自动恢复。人工决策A已确认，不再要求重复授权；实施前重读Spec与本plan，不在本窗口进入任何Step2代码动作。

## Exact verification commands

Step1 baseline：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_realtime_observation.py server/tests/services/test_history_service.py server/tests/services/test_playback_service.py
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history
```

Step2/3直接focused文件：`server/tests/services/test_queue_manager.py server/tests/repositories/test_task2_steps_5_7.py server/tests/services/test_autoplay.py server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_transitions.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_output_serialization.py`。每行只运行表中对应文件，末尾Step3运行其union。

Step3/4（本窗口未执行）：R-TX/R-LIB/R-PL/R-PB/R-H/R-O/R-ARCH 使用 active Task6 §5 的精确命令（单一来源）。其它命令：

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

Ruff 若有 production 修改须添加实际文件。Acceptance criteria 以 P §8.9 和 T6 §3 D6 义务为准；当前仅合同决策与诊断证据，不具备consumer或生产自然完成验收。物理 NAS/MPD/DAC/reverse-proxy 留 Task12。不得 commit/push/PR/merge。
