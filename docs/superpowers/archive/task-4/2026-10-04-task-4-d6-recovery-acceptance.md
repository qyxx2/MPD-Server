# Task4 D6-RECOVERY专项验收 — BLOCKED

日期：2026-10-04（Asia/Shanghai）。唯一专项 acceptance。**最新：原版 MPD 主体合同已定义，R1重启接管限制已接受；新实施/自动测试/目标运行时均未完成；D6、Batch13、Task6 final BLOCKED。**

> 最新有效状态见文末「原版 MPD 合同迁移」。下文所有旧 RED、GREEN、S0/S1、严格 SOURCE 裁定均是当时合同下的历史记录；不会因本次改合同而被追认为新合同通过。

## Actual baseline / scope

用户指定 checkout `/home/Gold/WorkSpace/MPD-Server/MPD-Server`；实际执行 status/branch/rev-parse/log-15。起始 working tree clean，branch `feature/task-6-realtime-state`，HEAD **82391fcf6bb02a8bb480e99ea5be4a93ec43746b**。结束 HEAD 相同。`git show --stat HEAD` 核实该提交已有三份 Batch13 文件，共545新增行：recovery invariant、realtime API、既有 Batch13 acceptance。不是本轮 D6 新增，也不是未提交修改。两个 Batch13 Python 文件本轮没有 diff；原 acceptance 只追加本轮状态，不改写历史执行记录。

环境实际验证：`test -x .venv/bin/python` exit0；Python3.14.4、pytest9.1.1、Ruff0.16.9；已读 server/requirements.txt；没有修改 `.venv`/dependencies/schema，未使用系统 Python、Docker、live MPD、远端命令。测试只用 tmp SQLite/真实 Services/MockMPD。

使用 Superpowers using-superpowers/systematic-debugging/writing-plans/test-driven-development/verification-before-completion。没有进入 production implementation 或需要独立 implementer/reviewer 的阶段；未派发代理。本提示词授权既有合同内修复，遇到未定义自然识别/漂移分类/终态/retry 按用户停止条件处理，不因 skill 另加审批。

读取 README；主 Plan Task4/6、Dependency/Relationship/Contract Matrix；active T6 §3/§4/§5/Batch13；P §6–8.8/§10、A §12.1–12.3/§19.5、O §6/§8.1、L availability/§9；Task4 archived corrective/acceptance 与 Task5 PB-HISTORY/Stop/successor/CD/rollback/idempotency合同；实际 PlaybackService/QueueManager/HistoryService/AutoPlay/PlayerPort/MockMPD/observation/transaction/idempotency 实现及直接相关测试。历史 GREEN 没有升级为当前证据。

## Steps / root cause / Contract Gap

新 active plan：`../../plans/2026-10-04-task-4-d6-recovery-corrective-plan.md`。未找到既有 D6专项 active plan。**仅 Step1 audit/diagnostic 已完成；Step2 implementation、Step3 D6验收、Step4 Batch13最终门禁未完成。生产修改0。**

当前 `PlaybackService.reconcile_external_status()`：读取 status；STOPPED→autoplay false→保存STOPPED→History.stop；`_save_confirmed_status()` 还有独立 STOPPED→autoplay false 分支。非STOPPED分支按 URI 查 song_id、比较 active.song_id 后启动History，没有原因确认/完整 occurrence 分类。`HistoryService.complete_naturally()` 存在及单测GREEN只证明给定原因的事件存储，不证明 PlayerPort→自然完成识别→successor 的实际能力。

真实 RED：`server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history`。先由真实API/SQLite/Services建立 a/b/c 会话，再直接改变 MockPort transport；没有 PlaybackService.stop 或用户Stop请求，也未传递原因。reconcile后实际新增 `(a, STOP)`，has_entries false→true、active/session→None、autoplay true→false；Queue occurrence/order/revision=2 与 Context 相同。selector 首次及重复运行均在禁止项断言失败，fixture与setup全部成功。完整 `-vv` traceback 已读取；是 production 行为失败，不是环境/夹具 RED。**没有 GREEN、没有 RED→GREEN 完成声明；未 skip/xfail/放宽断言。新增测试保留为未关闭 blocker，当前工作区不能被描述为测试全绿。**

权威定义的禁止项已经明确，但完整修复路径尚缺：

1. 自然完成的可信证据、接纳边界与断线/重启/重复 occurrence 的处理。
2. 外部 pause/next/stop/foreign current 等漂移的允许转移、确认与 History reason。
3. 自然完成后没有可用歌曲时 persisted state/active/session/AutoPlay 的终态组合。
4. 恢复转移的重试身份/消费边界，尤其 outer rollback 后外部已发生变化的 retry。
5. 未知原因不造History/不冒充Stop已冻结；正向返回/拒绝/恢复策略未闭合。

依据 P §7/§8.8/§10 与 A §19.5：不能从 STOPPED、elapsed/duration、URI、Mock event 名字或已有 Next/delete 分支推导上述业务语义。P §10 明列“Queue 与 MPD 原生队列的精确映射及故障恢复协议”未决。Task5手动Next无候选保留current、删除current无候选confirmed Stop，是不同操作合同，不能任意套给自然完成。Task6 G6-01–05 已闭合的只读协议不因此重开；这是本轮发现的 **Task4 D6 Contract Gap**。

原 Batch13 acceptance 的“没有新的Contract Gap”是上一轮未实施D6时的记录；本轮专项审计得到不同结论，追加最新状态而不修改历史。未改Spec、不新增平行权威解释。必须先以明确人工领域决定闭合唯一Playback Spec，再更新 active专项矩阵、继续逐行为RED→GREEN。

## Contract traceability / gate

Owned：PB-HISTORY-001，D6-RECOVERY阶段验收义务。
Relied：PB-STOP-001、PB-NEXT-UNAVAILABLE-001、TX-ROLLBACK-001、TX-IDEMP-001、EVENT-PORT-001。
Regression：PB-INSERT/REORDER/DELETE-PENDING/DELETE-CURRENT-001、PL-REP/PL-COLLECTION-001、O-PRESERVE/O-STATE/O-EVENT-001、RT-OBSERVE/SNAPSHOT/PLAYBACK/RECOVER-001。完整影响表/Expected Delta/U/confirmation/rollback/retry/proof见唯一active专项plan；本轮没有新增或修改frozen语义。

| Contract → authority | Implementation → executable proof | 本轮 fresh evidence / limitation |
|---|---|---|
| PB-HISTORY-001/D6 → P §7/§8.8; M Task6; T6 §3 | PlaybackService.reconcile_external_status → test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history | **1 failed**；原因缺确认、STOP错误事件；自然识别/续播未证明 |
| PB-STOP-001 → P §6.1/§7; T5 §3.7 | PlaybackService.stop → invariants/test_stop_confirmation.py::test_unconfirmed_stop_preserves_all_authorities / test_stop_transport_failure_rolls_back_and_retries | 所在57项baseline GREEN；仅显式Stop，不替代自然恢复 |
| TX-ROLLBACK-001/TX-IDEMP-001 → A §19.5; T5 §3.5/3.7 | database/history hooks/idempotency → invariants/test_transaction_relationships.py::test_transaction_restores_persisted_and_session_state_and_retry；api/test_idempotency.py；transaction commit hooks | R-TX **19 passed**；既有业务路径的rollback/retry，不是完整D6状态机证明 |
| RT-OBSERVE-001 → P §8.8; A §12.3 | PlaybackObservations → test_realtime_observation.py::test_external_drift_never_attaches_progress_or_changes_history[stop/foreign/duplicate/missing-id/queue-mismatch] | 所在57项baseline GREEN；观察只读/漂移标记，无自动恢复 |
| RT-RECOVER/SNAPSHOT-001 → A §12.1–12.3 | StateService/HTTP/WS → test_realtime_recovery.py::test_reconnect_replaces_all_domains_and_epoch；api/test_realtime.py | selector **6 passed**、两文件 **14 passed**；完整最终门禁仍未满足 |
| architecture → A Service/Repository/Port边界 | invariants/test_architecture_relationships.py；api/test_api_contracts.py::test_api_does_not_import_repositories | R-ARCH **3 passed**；无production改动 |

Relationship Gate **REQUIRED / FAILED**（目标跨模块不变量RED）。Contract Matrix Gate **REQUIRED / BLOCKED**（领域行缺authority、D6没有GREEN）。其它GREEN不得冲抵。

## User acceptance obligations

| 义务 | 本轮状态 |
|---|---|
| 自然完成与显式Stop分别处理/记录 | 未满足；unknown STOPPED错误STOP已RED |
| 自然完成后AutoPlay/successor/无可用歌曲 | 未满足；识别/终态合同缺口，未实现 |
| 未知原因不补History/不误判Stop | FAILED；新增专项RED |
| 确认后History恰一次，重复/retry/replay | D6未证明；已有REST replay回归不替代 |
| 确认失败/提交前取消/outer/terminal/materialization失败恢复persisted/runtime | D6未证明；原TX测试GREEN不外推，SQLite不撤MPD副作用 |
| 提交后取消/交付失败不撤提交 | 既有TX hooks回归GREEN；D6路径未证明 |
| Queue/Context/History/Playlist/Favorites/Output/terminal逐项保留 | 专项RED核对Queue/Context/History/AutoPlay；其余D6路径尚未逐项证明 |
| Task6 observation/snapshot/reconnect只读 | 既有observation及两恢复文件fresh GREEN；没有自动恢复/新调度 |

## Actual commands/results

全部在仓库根目录；唯一警告为既有Starlette/httpx deprecation，不安装依赖处理。

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_realtime_observation.py server/tests/services/test_history_service.py server/tests/services/test_playback_service.py
# 57 passed, 1 warning, 2.52s
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history
# 1 failed, 1 warning, 0.20s, exit1
.venv/bin/python -m pytest -q -vv server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history
# 1 failed, 1 warning, 0.16s, exit1
.venv/bin/python -m pytest -vv server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history
# 1 failed, 1 warning, 0.19s, full assertion diff, exit1
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_recovery.py::test_reconnect_replaces_all_domains_and_epoch
# 6 passed, 1 warning, 1.25s
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_recovery.py server/tests/api/test_realtime.py
# 14 passed, 1 warning, 2.45s
.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py
# R-TX 19 passed, 1 warning, 1.44s
.venv/bin/python -m pytest -q server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# R-ARCH 3 passed, 1 warning, 0.12s
.venv/bin/python -m ruff check server/tests/invariants/test_d6_recovery.py
# All checks passed, exit0
.venv/bin/python -m compileall -q server
# exit0
git diff --check
# exit0
```

D6未完成，因此“D6完成后”才执行的最终门禁未进入：全部realtime proofs、完整R-LIB/R-PL/R-PB/R-H/R-O、invariants+API、server/tests全套本轮未运行；R-TX/R-ARCH为独立审计回归，不声称已完成Batch13最终序列。上一轮251/323/711/987不算本轮fresh GREEN。

## Final state / isolation

修改：新增active专项plan、新增专项RED test、新增本acceptance；既有Batch13 acceptance追加本轮核对/阻塞结果。production及两个Batch13 Python proof没有修改。无future Task、API/observer恢复接线、依赖、环境、schema、本地DB或机器配置变更。

结束 working tree 保留上述4个可审阅文件；HEAD未变，未commit/push/PR/merge。完整tracked diff及新增文件已经审阅；diff --check通过。**不具备D6 corrective完成提交条件，不具备Task6已完成为前提进入Task8或后续Task的验收条件。**

物理MPD/NAS/DAC/reverse-proxy验证全部未执行，本轮不提供这些结论。


## Contract Gap Resolution / 人工 A（2026-10-04，最新状态）

用户在方案表后明确回复 **A**，批准五项保守决策及 STOPPED 含义修订，允许先实施 UNKNOWN/漂移/consumer，生产因果来源保持 blocker。本窗口仅写合同与计划，没有进入任何 implementation Step。

本窗口实际起始工作区为 **1 tracked modification + 3 untracked files**，不是clean：已有Batch13 acceptance修改、D6 acceptance/plan/test未跟踪，全部保留。再次执行status/branch/rev-parse；前一阶段已实际执行log-15。branch=`feature/task-6-realtime-state`，HEAD=`82391fcf6bb02a8bb480e99ea5be4a93ec43746b`，没有提交或远端操作。

### 已闭合与仍阻塞

| Gap | 已有authority / 人工新增决定 | 当前结论 |
|---|---|---|
| 自然完成可信识别/确认 | P §7/§8.8禁止推测已明确；新增P §8.9.1绑定因果证据、连续性、occurrence、完成时间、精确目标+execution确认 | consumer接纳边界CLOSED；真实生产来源机制未确定/验证，D6-SOURCE BLOCKED |
| 外部漂移 | observer只读已明确；新增P §8.9.2同occurrence pause/resume可接纳，无因果stop/next/foreign/duplicate/queue drift UNKNOWN且无控制/History | 领域策略CLOSED，未实现 |
| 无候选终态 | P §8.1不伪造歌曲已明确；新增P §7/§8.9.3 STOPPED/null/null/AutoPlay=true，active=null/session/context保留，完成occurrence Played | 组合CLOSED，未实现；显式Stop原合同保持 |
| 恢复身份/retry | REST/TX rollback已冻结；新增P §8.9.4进程epoch/业务代次/occurrence/ID固定证据和目标，pending跨业务rollback保留，receipt只在outer commit，已到目标不重播 | 同进程consumer CLOSED，未实现；无跨进程durable完成日志承诺 |
| 未知原因 | 不造History/不冒充Stop已明确；新增P §8.9.2 UNKNOWN返回与typed source error、全业务保留 | CLOSED但真实RED仍FAILED |

本次代价：外部播放器换曲不会自动改业务current；无候选等待会话不启动新调度；receipt/失效身份保留到进程退出有内存开销；断线continuity失效/重启拒绝旧完成证据，不推断遗漏事件。不能声称生产自然识别的完整Gap已消失。

### Spec → Contract → Step → executable proof 审查

唯一长期新增语义：[Playback Spec §8.9](../../specs/2026-09-24-playback-model-queue-semantics-design.md)。唯一执行分解：[D6 corrective plan](../../plans/2026-10-04-task-4-d6-recovery-corrective-plan.md)。该计划提供5个新增稳定consumer rows、PB-HISTORY扩展、共同12字段、白名单、内部接口、Step2.1–2.7精确TO CREATE selectors及literal assertions、confirmation/rollback/retry和Step3/3-SOURCE/4验收顺序。主Plan与active Task6、Architecture §12.3仅同步authority/能力门禁引用，不复制第二份产品语义。

审查发现并显式安排三个旧proof迁移（本窗口均未改）：Service外部b只凭URI推进、API corrective unknown stop/foreign→History、realtime unknown stop→成功History通知。下一窗口仅这些冲突selectors按新Spec改写，保留有业务delta分支的outer rollback、retry及提交传播断言。专项RED原样保留；通用invariant helper的STOPPED/session假设需要区分显式Stop与自然empty，不删除session断言。

可执行性结论：Step2.1可立即开始逐行为TDD，随后可以实施保守consumer；所有新增selectors均明确TO CREATE，不是当前已有证明。生产来源的Port/Adapter机制/接口/selector尚不能确定，Step3-SOURCE保持BLOCKED，不能用consumer Fake替代。完整D6状态机/自动恢复/Batch13 final未具备验收前置。

### 本窗口fresh验证

使用既有.venv，Python3.14.4/pytest9.1.1/Ruff0.16.9，requirements已读取。只有既有Starlette/httpx warning，无环境失败。

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history
# 1 failed, exit1（人工决策前重新确认）
.venv/bin/python -m pytest -q -vv server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history
# 1 failed, exit1（文档落地后）
.venv/bin/python -m pytest -vv server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history
# 1 failed, exit1；读取完整assertion diff：新增STOP/清active/session/AutoPlay=false
.venv/bin/python -m pytest -q server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_realtime_observation.py server/tests/services/test_history_service.py server/tests/services/test_playback_service.py
# 57 passed, 1 warning, 1.90s
.venv/bin/python -m ruff check server/tests/invariants/test_d6_recovery.py
# All checks passed, exit0
```

57项GREEN包含旧reconciliation行为，不证明新合同已实现。未运行新consumer tests（尚未创建）；未运行生产来源proof（机制未确定）；未进入D6/Batch13最终regression全套；物理MPD/NAS/DAC、Docker和live服务均未执行。文档无需以compileall/全套测试伪装实施验收。

### 本窗口文件与gate

修改7份现有文档：Playback Spec、Architecture Spec引用、主Implementation Plan引用、active Task6 plan引用、唯一D6 corrective plan、唯一D6 acceptance、既有Batch13 acceptance。没有创建平行文件。专项Python test与全部production保持本窗口起始内容，原三份未跟踪文件仍未跟踪。

**合同定义：consumer CLOSED；D6-SOURCE能力/完整可执行性 BLOCKED。Relationship Gate FAILED，D6 implementation/acceptance NOT COMPLETE；Batch13与Task6 final acceptance继续BLOCKED。** 下一窗口可以从Step2.1开始D6逐行为TDD，不能以合同落地或Fake GREEN关闭完整D6。


本轮文档检查：既有3个冲突selectors经AST核对存在；计划引用的直接测试文件均存在；新增selectors明确TO CREATE。相对文档链接与未跟踪文档逐行whitespace检查通过，tracked `git diff --check` exit0；实际tracked diff及未跟踪plan/acceptance/test内容均审阅。`git diff --exit-code -- server/app server/tests` exit0（tracked production/tests零delta；专项untracked test另行核对原有内容）。结束status为5份tracked文档M + 3份原有untracked（D6 plan/acceptance/test），HEAD仍82391fcf6bb02a8bb480e99ea5be4a93ec43746b。`git diff --stat`不包含untracked文件，不能将其5-file统计当作全部工作区范围。


## 2026-10-04 Step2.1–Step3 consumer 实施（最新验收状态）

本节取代上文“consumer 未实施 / UNKNOWN RED 未修复”的当前状态；上文保留为历史证据。实际开工先执行 `git status --short`、`git branch --show-current`、`git rev-parse HEAD`、`git log -5 --oneline`：工作区 clean，branch=`feature/task-6-realtime-state`，HEAD=`6b05d7f434024488a736db5be83ada82bb0abf91`。人工 A 已生效，没有重复决策。重读 Playback Spec §7/§8.8–8.9/§10、corrective plan、既有 acceptance、冻结架构/事务/Task6 合同及当前实现和 tests。

### 实现及逐行为证据

自然完成 consumer 只能接收明确证据；生产 `completion_validator` 默认拒绝，测试 validator 仅模拟可信输入。STOPPED、elapsed、URI、Mock 事件都不提供完成因果性。UNKNOWN 不写业务、不控制播放器、不创建 receipt；typed 来源失败继续抛出。绑定同 occurrence 且完整 execution 一致的 pause/resume 经二次确认才保存 transport；重复同态是 no-op。

journal 的 epoch/业务代次独立于 observation 样本；完整 baseline、完成身份、固定 pending 及精确 MPD ID 在同进程 retry 保持。自然完成使用一次 Queue CAS，保留已完成 Played occurrence，选择首个可用 pending 或一次纯 AutoPlay plan；只有目标和完整 execution 确认后才写 NATURAL_COMPLETION/new active。无候选保持 STOPPED/null/null/AutoPlay=true、原 session/context，后续显式 Stop 才结束 session。receipt 在 outer commit 可见；旧 receipt 可离线返回原结果而不覆盖新 current；visibility 故障无可信 receipt 时隔离 journal。

下列 selector 均位于 `server/tests/invariants/test_d6_recovery.py`，除另注文件。每次真实 production RED 后先最小修改、同 selector GREEN，再直接回归和 diff 检查；没有用全套替代 targeted gate。

| Step / row | 实际 RED → 同 selector GREEN → 直接回归 |
|---|---|
| 2.1 UNKNOWN / SOURCE | 原样 `test_unclassified_external_stop_does_not_fabricate_history` **1 failed → 1 passed**；unknown/source 参数 **8 failed / 2 已 GREEN → 10 passed**；专项11、R-PB+observation+transitions169 passed |
| 2.2 identity / evidence | `test_recovery_rejects_stale_evidence` **7 failed / restart 已 GREEN → 8 passed**；`test_recovery_business_generation_follows_committed_current` **7 failed → 7 passed**；专项26、R-PB/R-TX/R-ARCH127 passed |
| 2.3 TRANSPORT | `test_bound_external_pause_resume_preserves_history` 与 pending duplicate **7 failed → 7 passed**；专项33、Stop/observation/transitions/Output serialization130 passed |
| 2.4 NATURAL / HISTORY | successor/refill/duplicate **9 failed / invalid occurrence 已 GREEN → 10 passed**；专项43、Queue/AutoPlay/R-PB/R-H/R-TX/transitions214 passed |
| 2.5 EMPTY / STOP | `test_natural_completion_without_candidates_retains_session` **UNKNOWN RED → empty 实现后 explicit Stop session RED → 1 passed**；专项44、R-PB/R-H/Queue/AutoPlay/snapshot165 passed |
| 2.6 RETRY / TX | `test_recovery_rollback_retry_keeps_identity` successor/autoplay/empty × 8 failures：**21 首次 GREEN，3 terminal fixture str/bytes 失败**；修正 harness bytes 后同3及完整24 GREEN。drift retry3 GREEN；专项71、R-TX/R-PB/R-H139 passed |
| 2.7 receipt / commit | replay/postcommit **2 production RED / 5 已 GREEN → 7 passed**；专项78、hooks/delivery/transitions/R-TX/R-ARCH78 passed |
| 3 additional proofs | unbound local pending **1 RED → 1 GREEN**；纯 planner duplicate-context golden test（`services/test_autoplay.py`）**1 RED → 1 GREEN**；source failures/CAS invalid plans/retained Played12 GREEN；完整 U、真实 commit fault、concurrent barriers GREEN |

Step2.6 的 rollback/intent 行为已随前面 natural RED→GREEN 实现，新增故障注入首先验证了已有行为。terminal bytes、History DESC 顺序及测试 service 绑定接线错误都是 test/fixture 修正，不能计作 production RED。本轮不声称每个参数都有独立 RED，不人为破坏实现制造 RED。完整 U 测试检查真实 Library/Playlist/Favorites SQL、revision、Output runtime/physical outputs、所有旧 REST terminals；barrier 证明 receipt 不提前可见、合法新 current 优先、晚证据不能覆盖新 current。

三个旧冲突 selectors 已按 Spec 最小迁移：外部 foreign→UNKNOWN；stop/foreign 的 outer rollback/retry 保留；pause 的 outer rollback、唯一提交通知、重复 no-op 保留。通用 helper 只拆分显式 Stop 与自然 empty 的 session 断言。两个 Batch13 Python proofs 未修改。

白名单仅扩展 `HistoryService.stop` 的等待 session 清理：上表 empty→后续显式 Stop 的实际 RED 证明原 public Stop 在 active=None 时漏清 session；实施前在 corrective plan 增补许可，未修改 `_finish_active`/reason/finalizer。代价是一份必要依赖文件。

### 独立审查及本轮发现的回归

独立 reviewer 初审 **Critical 0 / Important 1 / Minor 0**，独立专项 **97 passed**。Important：自然完成已确认 execution 后 binding 又无校验重读 MPD Queue，可能把同 URI 新 MPD ID 错绑旧 occurrence。新增 `test_recovery_binding_uses_the_confirmed_execution_sample` 真实 **1 failed**（binding ID 与 journal execution ID 不同），改为使用已确认样本。

首次全套 **2 failed / 1084 passed**：`test_system_read_relationships.py::test_system_composition_uses_injected_capabilities_without_probe[False/True]`。根因是本轮通用事务 wrapper 的代次追踪读取 Queue，导致只读 Output 请求惰性创建 queue_state；精确重跑仍2 failed。将追踪限于可变 current 入口，不改只读测试。上述两个 selectors 与新 binding selector 同次 **3 passed**；随后专项+只读系统文件 **112 passed**、计划直接 union **355 passed**。两项修复在最终 review 后的一次修复回合完成，没有再扩展审查范围。

审查未实施项裁定：生产 causal source、真实 MPD continuity/重复 occurrence conformance 归 D6-SOURCE（代价：生产自然完成仍未验收）；跨进程 durable receipt/恢复日志不在本合同（代价：进程重启不能重放旧证据）；loop/API/Task6/Task8/Batch13 final 未授权且前置未满足（代价：自动恢复与最终阶段继续阻塞）；物理 MPD 多命令不可宣称原子，本轮仅承诺确认失败时业务 rollback、同进程固定目标 retry。按用户要求使用原 checkout，代价是无额外 worktree 隔离；没有 deferred minor。

### 最终 fresh 验证命令

既有 `.venv`：Python3.14.4 / pytest9.1.1 / Ruff0.16.9；`server/requirements.txt` 已读取，未改依赖/环境。测试只见既有 Starlette/httpx deprecation warning，无环境失败。下方属于 consumer/direct 与额外本地 regression，不是 Step4 最终序列。

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py::test_recovery_binding_uses_the_confirmed_execution_sample server/tests/invariants/test_system_read_relationships.py::test_system_composition_uses_injected_capabilities_without_probe
# 3 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py server/tests/invariants/test_system_read_relationships.py
# 112 passed, 1 warning（D6 98 cases + system read 14 cases）
.venv/bin/python -m pytest -q server/tests/services/test_queue_manager.py server/tests/repositories/test_task2_steps_5_7.py server/tests/services/test_autoplay.py server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_transitions.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_playback_service.py server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_output_lifecycle_injection.py server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# Step3 focused + R-PB/R-H/R-TX/R-O/R-ARCH union: 355 passed, 1 warning
.venv/bin/python -m ruff check server/app/models/recovery.py server/app/services/playback_recovery.py server/app/repositories/queue_repository.py server/app/services/autoplay.py server/app/services/history_service.py server/app/services/playback_observation.py server/app/services/playback_service.py server/app/services/queue_manager.py server/tests/api/test_pre_batch6_corrective.py server/tests/invariants/assertions.py server/tests/invariants/test_d6_recovery.py server/tests/invariants/test_realtime_transitions.py server/tests/services/test_autoplay.py server/tests/services/test_playback_service.py
# All checks passed
.venv/bin/python -m compileall -q server
# exit0
git diff --exit-code -- server/tests/invariants/test_realtime_recovery.py server/tests/api/test_realtime.py
# exit0, Batch13 proofs unchanged
.venv/bin/python -m pytest -q server/tests
# 1087 passed, 1 warning, 55.82s（两项本轮回归修复后的 fresh 全套）
git diff --check
# exit0
```

### Gate / scope / 剩余阻塞

**Step2.1 CLOSED；Step2.2–2.7 实现与可执行 consumer proofs GREEN；Step3 consumer acceptance PASSED。PB-RECOVERY-UNKNOWN/TRANSPORT、PB-NATURAL/EMPTY、PB-RECOVERY-RETRY 与 PB-HISTORY consumer 扩展已验证。D6-SOURCE BLOCKED；完整 D6 Relationship/Contract Matrix 验收 NOT COMPLETE，Step4、Batch13、Task6 final acceptance 继续 BLOCKED。** Fake validator GREEN 不等于生产来源 GREEN。

剩余前置：明确真实因果 producer/Port/Adapter 能力；验证断线/重启 continuity 与重复 occurrence；按计划修改白名单及建立真实生产来源 proof。当前没有可运行的 SOURCE selector，不虚构通过或用 status reason 替代。未实施来源 producer、未启用恢复 loop/API 接线、未扩展 Task6/Task8；物理 MPD/NAS/DAC/reverse proxy、Docker/live MPD 全未执行。

范围为8份 production（含2份新文件）、6份 tests、3份文档（唯一 acceptance、必要 Batch13 blocker、plan 白名单一行）。无 schema、依赖、环境、本地数据库或机器配置变更；起始无用户修改。保留工作区供审阅，未 commit/push/PR/merge。

最终实际 diff（包含2份新增源码）、whitespace/stat/status 已检查，未发现无关格式化、调试代码、生成文件、数据库/环境/依赖修改；结束 HEAD 与 branch 保持上述起始值。`git diff --stat` 不包含2份 untracked 源码，不能将其15-file统计当作完整17-file范围。


## 2026-10-04 S0 基线核对与文档同步（最新状态）

仅执行 P 的 S0。实际 branch=`feature/task-6-realtime-state`，HEAD=`6b05d7f434024488a736db5be83ada82bb0abf91`；起始即有 15 tracked modifications + 2 untracked recovery 源码，全部保留。已读 P/E/B 最新节、T §3/§5/Batch13 及 F §8.9/A §12.3/M 的 D6 依赖/C 原始能力记录；核对 consumer 源码、未提交 diff、专项 selectors 与三项旧 proof 迁移。当前实现范围为 UNKNOWN/typed error、绑定 transport、身份/代次拒绝、natural successor/refill/empty、同进程固定意图 retry、outer receipt/replay/commit 边界；不能把这些解释为生产来源能力。

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py server/tests/invariants/test_realtime_recovery.py server/tests/api/test_realtime.py
# 112 passed, 1 warning in 11.61s, exit0（D6 98 + Batch13 14）
```

本次无测试失败/环境失败；只有既有 Starlette/httpx warning。既有 .venv 环境 Python3.14.4/pytest9.1.1/Ruff0.16.9 与 requirements 已核对。前次 355/1087 GREEN、Ruff/compileall 及逐行 RED→GREEN 属上一实施节，本次未重跑；本次 112 并非上一节 D6+system-read 的同名计数，而是用户指定 D6+recovery/API 三文件。不重写首次 RED，也不伪造新的 RED→GREEN。

SOURCE blocker 按实际源码保留：main 未注入 completion_validator，默认 None 拒绝自然证据；生产代码尚无 CompletionEvidence producer 或 reconcile 调用，Port/Adapter/目标 MPD0.23.5 的 9 项 verified_operations 无因果完成能力。测试 validator 仅认可 test-only 来源/固定 continuity，不能证明真实 EOF 原因、连续性、重复 occurrence、实际 ended_at 或来源 ACK。S1 来源可行性、S2 来源合同、S3–S6 proof/联合门禁均未执行；部分 MPD 多命令执行边界仍待 S4 补证，自动 runner 接线仍属 S7。

P 的旧“TO CREATE/未实施/从 Step2.1 开始”已同步为 consumer 已实现状态，Step2.1–Step3 与 S0 checklist 更新；SOURCE 新 selectors 继续 TO CREATE。B 仅追加本次 fresh 基线及 blocker。历史诊断和逐行实施证据均保留。

**S0 COMPLETE；consumer 已实施/验收，指定范围 fresh GREEN；完整 D6 Relationship/Contract Matrix 验收 NOT COMPLETE，D6-SOURCE BLOCKED；Step4/Batch13/Task6 final 继续 BLOCKED。** 本步仅修改 P/E/B；production/tests（含两个 untracked recovery 文件）字节比对保持一致，两份 Batch13 Python proof 无 diff，git diff --check/stat/status 已核对。未改环境/依赖/schema/本地数据库，未用 Docker/live MPD/外部服务，未 commit/push/PR/merge。S1 及后续工作未执行。

文档辅助核对曾因正则把 test_*.py 文件名当作函数而触发 AssertionError；完整缺失列表均为文件名/通配符，是核对脚本假设错误，不是 pytest、环境或 consumer 失败。收窄到 consumer selector 区域并排除文件 stem 后精确重验 exit0：16 个引用函数均存在，P/E/B 本地链接有效，148 个 production/test Python 文件与 S0 编辑前 SHA256 全部一致。未因此修改生产或测试。

## 2026-10-04 S1 生产来源可行性调查（最新验收状态）

**S1 调查与裁定 COMPLETE；裁定为「需要后端扩展」。当前原版 MPD 0.23.5 + Port/Adapter 无法满足严格 SOURCE 合同；D6-SOURCE BLOCKED，完整 D6/Step4、Batch13/Task6 final acceptance 继续 BLOCKED。** S1 完成不表示来源能力通过或 producer 已可实施；S2–S7 未执行。

实际起始工作区 clean，branch=`feature/task-6-realtime-state`，HEAD=`651aade83d0df52601f4555e0a682c9f16afd25e`；consumer 已提交在此基线。本步只更新 P/E，未重做 consumer，不沿用 S0 未提交文件状态。已读用户指定全部八份文档及当前 PlayerPort/models/Adapter/capabilities/main/consumer；研究记录、逐场景矩阵、官方 tag 链接及五项必要决策均写入 [原 P 的 S1 裁定（现归档）](2026-10-04-task-4-d6-recovery-plan-history.md#2026-10-04-s1-生产来源可行性裁定调查完成能力-blocked)，不建立平行计划/Spec/验收。

### 来源证据与拒绝边界

- 官方版本限定 **v0.23.5**。[协议](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/doc/protocol.rst)与 [idle 位集合并实现](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/client/Idle.cxx)仅支持当前快照/子系统变化；没有终止原因、唯一完成 ID、实际结束时间或可重放事件序列。协议 greeting 也不足以认证 NAS daemon build；未取得目标 build/hash/补丁清单。
- 已区分 EOF、Stop、Next/队尾、seek 终点、播放错误、外部换曲、重复 URI、断线/重启：status/idle/elapsed/URI/没有本服务 Stop 请求均不作为自然完成证据。当前 songid 可以区分同时入队槽位，不能区分同项重播、迟到/复用/重启。UNKNOWN 原则保持 F §8.9。
- [player Thread](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/player/Thread.cxx)的排空、命令退出及错误路径最终可合流；played URI 日志也出现在统一清理路径。[decoder Thread](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/decoder/Thread.cxx)的普通返回与 [FLAC plugin](https://github.com/MusicPlayerDaemon/MPD/blob/v0.23.5/src/decoder/plugins/FlacDecoderPlugin.cxx)的 EOF/错误返回不是唯一自然原因。不能以 Drain 或空 status.error 新造可信 source。
- C 的两轮记录及提交 `85a24f6`/`4453eb1` 已核对；原始 JSON 未在仓库 tracked/history、本地 WorkSpace/home 文件名搜索找到。M 记首份保存在 NAS；本步未连接 NAS，因此原始 probe **未取得**。不新增 C 实测结果，不把官方源码静态反例写成 NAS 实测；既有九项 verified_operations 无 SOURCE 能力。
- 生产 Port 无事件/连续性/ACK；Adapter 未保留 error，无完成来源；main 不注入 validator，consumer 默认拒绝。M 的 Task4/Task6 依赖和 A/T 的 observer/read/reconnect 只读边界保持，不能借 Task6/Task8 生成原因。

### 推荐与待决项

推荐受控 MPD 扩展：在 decoder/plugin 原因丢失前保留 EOF/error/cancel，在控制/seek/播放输出边界保留每次播放代次，再提供带 source epoch、序号/transition ID、entry ID、时间与缺口标志的来源记录。Service 关联事件对应的已提交业务绑定；ACK 在 outer commit 后。同进程失败保留事件，重复走 receipt；断线/重启仍按 F 拒绝旧 continuity，不新增跨进程恢复承诺。仅改 Python Adapter 或 player drain 分支不足。

必要决策：①能否部署维护可核验的 NAS 后端扩展；②decoder/媒体与 gapless/crossfade/范围支持边界；③seek 后余段及实际完成时间定义；④全客户端控制、来源 generation 与业务绑定/Queue revision 竞态；⑤留存/ACK/缺口与重新绑定规则。细项见 P。本次只是建议，未批准后端白名单、未冻结 S2 来源合同。若拒绝后端扩展且固定当前后端，则当前约束下无法满足；保持 BLOCKED，或由用户另行批准换后端/修订 F 与阶段门禁。不得自动降低为启发式自然识别。

### 本步验证与局限

本步为只读能力调查及文档更新，没有生产实现、SOURCE 自动测试或运行时能力验收。未运行 pytest/Ruff/compileall、未制造 RED→GREEN；旧 consumer GREEN 仍为前节历史证据。官方源码已读取并由主执行者核对关键控制/decoder 分支，研究子代理只读协助，不修改仓库。未运行新 capability probe、未访问 live MPD/NAS/DAC、未用 Docker，未改环境/依赖/schema/本地数据库。

fresh 检查：`git diff --check` exit0；`.venv/bin/python` 辅助校验 **148 份 production/test 文件起止 SHA256 相同、P/E 3 个本地链接有效**；`git diff --exit-code --` C/B/F/A/T/M 与 server/app、server/tests exit0。已读取实际 diff，stat/status 仅 P/E 两份文档修改，无生成文件/环境/数据库变更。这些是文档及范围验证，不代替 SOURCE proof。未 commit/push/PR/merge。**consumer 实施/验收状态保持；来源能力验收未满足，手工目标部署/对照验证也未执行，完整联合验收仍 BLOCKED。**

## 2026-10-04 原版 MPD 合同迁移（最新有效状态）

用户明确保留原版 MPD 0.23.5，不采用后端扩展，授权收窄自然原因/精确结束时间/采样间及断线重启历史完整性，要求保留 Queue occurrence、手动顺序、AutoPlay核心、真实页面恢复、事务/确认/幂等与读取只读。本轮只编辑文档；没有把这些授权解释为新实现或验收通过。

### 真实起点、原始材料与能力结论

branch=`feature/task-6-realtime-state`，HEAD=`651aade83d0df52601f4555e0a682c9f16afd25e`；开始 P/E 已有未提交 S1 调查（2文件），完整保留。核对 `651aade` consumer 与 `6b05d7f` 合同提交、`82391fc` Batch13 proof、当前Port/Adapter/capabilities/PlaybackService/journal/Queue/AutoPlay/History/observation/StateService/完整snapshot/WS/main及关联测试。当前源码支持旧consumer存在，不支持新stock路线已完成；默认completion_validator=None，没有生产natural source或恢复runner。

本轮取得 [2026-09-26 原始JSON](/home/Gold/Downloads/mpd-0.23.5-probe-2026-09-26-091948.json)，SHA-256=`6c4036572314b38d822481c28fa25652bab29a26ab8ec6e74a076cbe815d0d40`。commands=105，C旧摘录漏unmount；status_fields=17；outputs/stats/update/errors核对一致；没有verified_operations字段。只最小纠正C并补来源。第二轮JSON未取得，九项transport仍是历史摘录，未重跑实机probe。上文“当时未取得”是当时事实，不抹去。

重新读取官方固定v0.23.5的protocol、PlayerCommands、Idle、Playlist/PlaylistControl、player Thread、IdTable；索引和逐条限制在[P的S0审计表](../../plans/2026-10-04-task-4-d6-recovery-corrective-plan.md)。静态结论：可读当前entry/完整执行队列，不能认证上一项自然原因、准确ended_at或遗漏项播放；既有SOURCE调查的不可行结论对旧严格合同仍成立。没有认证NAS build/hash或新运行时组合。

### 决定与门禁替换

唯一authority [F §8.9](../../specs/2026-09-24-playback-model-queue-semantics-design.md)改为当前目标接纳与预同步；[A §12.3.1](../../specs/2026-09-25-system-and-development-architecture-design.md)定义最小actual identity/同步状态DTO。候选→业务提交→执行同步→当前接纳分开，顺序和提交确认不弱化。未知STOPPED不自动启动、不改AutoPlay意图、不造reason。

History推荐并采用不记录未经认证离开的永久事件，保留现有reason/schema；新目标不凭观测时间创建active。A→C只把已确认A放Played，B留pending保留身份和手动顺序；代价是B可能再次播放。刷新/新浏览器通过完整快照恢复，服务/MPD重启先恢复actual显示，失效绑定需明确操作重建；不承诺未知过去/完整Context/runtime active还原。

严格 `D6-SOURCE` 标记 **SUPERSEDED / NOT PROVEN**，不是删除阻塞后PASS。新增PB-BINDING/CURRENT/QUEUE-ADOPT/HISTORY-UNCERTIFIED/AUTOPLAY-EXEC/RECOVERY-RUNNER、RT-ACTUAL及修订UNKNOWN/RETRY义务全部待实施。旧natural/empty测试仅证明历史consumer；原UNKNOWN/Stop/TX/只读/水位proof仍适用或按P表精确迁移，历史112/355/1087不外推。

| 层次 | 最新状态 |
|---|---|
| 新合同与执行计划 | DEFINED；唯一 P 保留当前 S0–S12；R1 重启后明确接管限制已由用户接受 |
| 旧consumer Step2.1–Step3 | 当前代码存在，历史验收保留；本轮未重跑 |
| 新stock实现（S2–S9） | NOT STARTED；含独立runner，非observer恢复 |
| 新专项/联合自动proof | TO CREATE / NOT RUN；无新RED/GREEN声明 |
| 当前本地Python | 既有.venv可执行，Python3.14.4；只用于文档/JSON校验，没有改环境 |
| 目标MPD模式/预同步/新绑定运行时验收 | S11 NOT RUN；需另行授权；本轮禁止live/Docker |
| D6 Relationship/Contract Matrix验收 | REQUIRED / BLOCKED（历史consumer PASSED不能抵扣） |
| Batch13 / Task6 final | BLOCKED；S12最终复验未执行 |
| Task8实际UI、Task12 DAC/反向代理 | 未实施/未验收，不包含于文档完成声明 |

### 本轮验证边界

没有运行pytest/Ruff/compileall、新probe或任何生产入口；没有写测试、schema、数据库、依赖或环境。文档事实验证：JSON解析/计数/摘要，当前源码与selector只读检查，实际diff、git diff --check、stat/status、相对链接检查及起始tracked文件SHA-256保全。最终检查结果记录在下方，不把文档校验冒充实现GREEN。未commit/push/PR/merge，HEAD保持651aade。

### 最终文档核验结果

`git diff --check` exit0；当前diff仅指定P/E/B/F/A/T/M/C八份Markdown。辅助脚本验证：相对/绝对本地Markdown链接31个（含1个heading anchor）均可解析；C完整commands/status_fields数组与原始JSON逐项一致（105/17）；新S0–S12编号连续；当前计划已有selector经AST核对存在，新21个test函数名称均为TO CREATE。148个tracked production/test文件与本轮起始SHA-256一致，全部其它非授权tracked文件也一致，无untracked新增。起始P/E调查保留在历史区；没有将旧SOURCE“需要扩展”意见作为当前行动指令。

当次文档核验结束时 R1 尚待用户答复；该状态仅为历史记录，后续决定见下节。

### R1 接受与 active plan 归档整理（2026-10-04 后续）

用户已接受建议：服务/MPD 重启后恢复准确 actual 显示，明确播放操作经确认重建业务绑定；仅刷新/换浏览器不丢失有效服务绑定。F/A/P/B/T/M 已同步。P 中旧 consumer、旧 S0/S1、废止步骤和详细能力调查移入 [计划历史归档](2026-10-04-task-4-d6-recovery-plan-history.md)，保留原记录；P 保留当前源码基线、proof 迁移、S0–S12 与文档简称索引。上一节核验数字属于归档整理前的文档版本，不作为本次核验结果。合同已接受；新实现、新自动测试和目标运行时仍未完成，D6/Batch13/Task6 final 继续 BLOCKED。

本次整理核验：active plan 从 587 行缩至 300 行，新增 321 行历史归档；脚本确认迁出的旧历史正文和详细能力复核逐字保留，当前 S0–S12 连续。九份工作区变更文档的 37 个本地 Markdown 链接（含锚点）可解析；已检查实际 diff、stat/status 和 git diff --check。相对本次整理起点只改七份 tracked 文档并新增上述归档；C、全部 production/tests 及其它 tracked 文件字节未变。未运行自动测试、未访问 live MPD、未修改环境、未提交。
