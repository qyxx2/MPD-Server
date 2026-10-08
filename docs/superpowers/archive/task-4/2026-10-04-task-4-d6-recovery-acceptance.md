# Task4 D6-RECOVERY专项验收 — PASSED

**当前有效状态（2026-10-09）：D6 S10/S11/S12、Batch13 / Task6 functional final PASSED。最新逐Contract追溯和隔离测试记录见文末S12；原本地DB保留UNVERIFIED单独保留为审计事件，下文较早BLOCKED/NOT RUN均为各历史轮次。**

首建：2026-10-04；S11核验：2026-10-08（Asia/Shanghai）。唯一专项 acceptance。**2026-10-08历史状态：S11目标运行时功能能力PASSED（用户授权的现有NAS部署功能范围：daemon0.23.17/套件0.23.17-3/协议0.23.5，不冒称daemon0.23.5）。真实推进/身份/预同步/Stop/断线与重启/丢响应及隔离真实输入、解码、pipe输出错误均已取得本次原始证据和保护核对；临时进程/目录/SSH转发已清理并留档。S10前置已fresh确认PASSED且本轮源码hash保持；S12未执行，D6/Batch13/Task6 final仍BLOCKED，不能以S11能力通过代替最终联合门禁。真实USB DAC故障/听觉仍属Task12，未验收。**

> 最新有效状态见文末 S12；S11 目标证据见补充实测；S10 前置证据见「2026-10-08 S10 — stock Adapter 联合 proof」。下文旧记录保留当时结论，不因后续补验自动扩充证明范围。

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

## 2026-10-04 S2 一致执行样本与只读能力门禁

本节取代上文“新stock实现 S2 NOT STARTED / 新专项 NOT RUN”中仅关于 S2 的当前状态；S3–S12 仍未执行。实际开工工作树 clean，branch=`feature/task-6-realtime-state`，HEAD=`9a6d1443343e337154017731926a4fad7c2359fd`。相对旧 consumer 基线 `651aade`，`server/app` 与 `server/tests` 无差异；`9a6d144` 的冻结合同文档与当前 P/F/A/T/M/C/E/B 一致，没有发现需要改写 S0/S1 或超出 S2 冻结接口的漂移。

### execution-before baseline

使用既有 `.venv`，Python 3.14.4、pytest 9.1.1、Ruff 0.16.9；`server/requirements.txt` 已读取，未改环境或依赖。S0 要求的 fresh baseline：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history
# 1 passed, 1 warning
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py
# 98 passed, 1 warning
```

仓库内原始 probe SHA-256=`6c4036572314b38d822481c28fa25652bab29a26ab8ec6e74a076cbe815d0d40`；105 commands、17 status fields、无 `verified_operations`，与 C/S0 记录一致。没有访问 live MPD、NAS、Docker 或外部服务。

### S2 实现与 RED→GREEN

仅修改 S2 白名单中的 Player 模型、Port、Adapter、能力 wrapper、Mock 和专用测试。新增不可变深复制 `ExecutionSample`，字段为 connection epoch、partition、playlist version、完整 status/entries、single/consume/error，不含 completion/reason。`PlayerPort`、`MockMPD` 和 `VerifiedPlayerPort` 暴露同一只读入口；能力门禁只要求 `status`/`playlistinfo` 命令，不把该读取自动加入 runtime `verified_operations`。

真实 Adapter 在一次连接锁内执行 `status → playlistinfo → status`，每次读取核对 connection、partition、playlist version/length、current position/ID、完整连续 position 与唯一 MPD ID；最多两次 attempt。两次仍冲突抛 `PlayerCommandError(command="read_execution_sample", message="inconsistent execution sample")`；断线保留原 `PlayerUnavailable`，取消沿用弃连接逻辑，不返回半样本、不发送控制。连接成功 greeting/password 后生成本地 connection epoch，close/reconnect 更换代次。STOPPED 可保留 selected entry，只表示实际选择位置，不生成 reason。

`test_sample_rejects_torn_current_and_queue` 的 current/version/length/duplicate-id/position 五参数首先均因入口缺失 RED，最小一致采样实现后同 selector **5 passed**；断言两次 playlist attempt、typed error、controls=[]。`test_sample_epoch_and_modes_are_not_completion_evidence` 修正一次测试 fixture 的空队列 length 后，真实 RED 暴露 Mock/wrapper 缺入口；补齐后嵌套 status/entry 仍可变再次 RED，冻结深复制后同 selector GREEN。最终 diff 审阅又发现公开 close 可在 await 间更换连接：新增同 selector 竞态 proof 取得 playlist attempt 1≠2 的 RED，采样固定并复核 attempt epoch 后同 selector **1 passed**。该 selector 同时覆盖 epoch 变化/中途重连、single/consume/error、空 error、空 STOPPED、selected STOPPED、单次断线、Mock 与能力允许/拒绝，且 `model_dump()` 无 reason。

### fresh 验证与门禁

```text
.venv/bin/python -m pytest -q server/tests/player/test_execution_sample.py::test_sample_rejects_torn_current_and_queue
# 5 passed
.venv/bin/python -m pytest -q server/tests/player/test_execution_sample.py::test_sample_epoch_and_modes_are_not_completion_evidence
# 1 passed
.venv/bin/python -m pytest -q server/tests/player/test_execution_sample.py
# 6 passed
.venv/bin/python -m pytest -q server/tests/player/test_mpd_adapter_tcp.py
# 1 passed
.venv/bin/python -m pytest -q server/tests/player/test_mpd_adapter_errors.py
# 3 passed
.venv/bin/python -m pytest -q server/tests/player
# 40 passed
.venv/bin/python -m ruff check server/app/player/models.py server/app/player/ports.py server/app/player/mpd_adapter.py server/app/player/capabilities.py server/app/player/mock_mpd.py server/tests/player/test_execution_sample.py
# All checks passed
.venv/bin/python -m pytest -q server/tests
# 1093 passed, 1 existing Starlette/httpx deprecation warning, 62.22s
```

S2 implementation、自动测试和本地环境验证 **PASSED**。这只证明本地协议模拟和只读能力门禁；目标 MPD 的新模式/组合运行时仍 **NOT VERIFIED**，S11 未授权/未运行。没有修改 schema、数据库、依赖、业务 Queue/History、observer/GET/WS 或 runner，没有进入 S3。完整 D6 Relationship/Contract Matrix、Batch13 与 Task6 final 继续 **BLOCKED**。

## 2026-10-07 S3 occurrence 绑定与失效（当前状态：指定本地 gate 满足；完整 D6 BLOCKED）

本节取代上文关于 S3「未执行」的状态；**S3 实施及指定本地自动验收 PASS**。附加 R-PB-D6 仍有 5 项重试失败，不能宣称整体播放回归通过。S4–S12 未实施，完整 D6 / Batch13 / Task6 final 继续 BLOCKED。实际起点工作树 clean，branch=`feature/task-6-realtime-state`，HEAD=`31be1c4`；未提交、未推送。

### S2 prerequisite 的 fresh 验证

当前源码与 S2 提交、P/F §8.9.2、A §12.1–12.3.1 和本文件最新 S2 记录核对。既有 `.venv` 可执行，Python 3.14.4 / pytest 9.1.1 / Ruff 0.16.9；已读取 `server/requirements.txt`，未改环境或依赖。

```text
.venv/bin/python -m pytest -q server/tests/player
# 40 passed in 0.84s，exit0
# 包括 ExecutionSample 六项、TCP 与 adapter errors 等 S2 指定 tests。
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py::test_recovery_binding_uses_the_confirmed_execution_sample server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history
# 实施前 2 passed, 1 existing warning，exit0
```

S2 的本地只读样本 gate 本次由真实测试满足；目标 MPD 运行时能力仍未实测，不能外推为 S11 PASS。

### S3 实施边界与 proof

新增不可变 `ExecutionBinding`，由 RecoveryJournal 持有 service/connection epoch、binding generation、partition、Queue revision、playlist version 及完整有序 occurrence/MPD ID/URI 映射。Service 的 `get_execution_binding()` 遵守共同事务读取边界。同步使用旧有效映射或本次 `queue_add` 的返回 ID，删除 URI 搜索/zip 重建入口；最终完整样本确认后才建立绑定。明确 current 控制的入口接线用于登记本次控制身份，普通 pending mutation 不能以此重新接管；独立 Sample/observer/GET 不建立绑定。

同步与二次确认均验证连接/partition、完整 ID/URI/position；没有队列控制的同步必须保持原 playlist version。观察样本验证有效绑定内的完整队列版本与映射，替换 ID、复用 ID但版本改变、连接/partition 变化使绑定失效。相同 entry 的 elapsed 回退不拆 occurrence、不写 History；超过 6 秒只让缓存 stale，同连接同版本样本可以再次确认，不补遗漏历史。未知 current 转移尚未接纳，pending mutation 拒绝控制；不实现自动 current 推进。

绑定在 outer transaction 内暂存，公共读取通过既有共同边界。普通业务失败恢复旧业务绑定；外部连续性失效由独立失效标志保存，rollback 不复活。失效之后本事务重新接管形成的新绑定若未提交，也在 rollback 清除。明确 Stop 清除 current 绑定；仍由已确认控制取得的停止队列映射，仅可验证同连接/partition/version 的停止队列控制，不成为 current 的读取重绑入口。未新增执行意图、逐命令账本、receipt 类型、runner、History finalizer、自动接纳/refill 或 schema。

RED→GREEN 记录（没有把 fixture 失败或首次 GREEN 冒充 RED）：

- `test_duplicate_uri_binding_uses_confirmed_entry_ids` 首次因缺 Service facade RED，之后同 selector GREEN。冻结 refill 作为该专用 fixture 的边界，literal assertion 是完整 `binding.entries == ((a,11,"same.flac"),(b,12,"same.flac"))`，替换 12 为 13 后 UNKNOWN、绑定 None、业务相同、零控制。早期 fixture 中准备播放先分配了一个 ID，已用明确预置 entry 修正该编号假设；该 fixture 修正不是生产缺陷的 RED。
- `test_binding_invalidates_on_gap_version_reuse_and_restart` 的 disconnect/service-restart/mpd-restart/version-change/id-reuse/foreign-partition 六参数，在上述核心实现后首次 **6 GREEN**；记录为新增 proof 验证已实现行为，没有人为制造 RED。
- 显式 Stop 失效、lost binding 下 pending mutation 不重建、源错误后 reconciliation_required、未接纳 current 下 pending mutation 不重播、确认间隐藏版本变化、控制采样错误跨 rollback、辅助 status/queue_entries 读错误（6 参数）分别取得真实 RED，再以同 selector GREEN。
- 新鲜上下文只读审阅发现同步最终样本连接连续性缺口与直接读失败绕过失效两个 Important finding。前者 connection 参数 RED→GREEN；partition 参数首次 GREEN，新增最终边界检查。无队列控制的意外 version 变化另取得 RED→GREEN；后者由上述辅助读错误 6 参数 RED→GREEN 修正。
- 外部失效后本事务重新接管再 rollback 的 runtime 绑定清除：最初只检查公共 getter 时 GREEN，但不足以覆盖 runtime；补上 runtime 未提交绑定断言后取得 RED，再最小修正 rollback hook，同 selector GREEN。
- 同 entry replay/单纯 stale 间隔、所有七种 current-changing 控制、普通 rollback 与外部失效 rollback 的补充 proofs 首次 GREEN，保持业务/History 不变断言。
- 已失效绑定下读取旧 fresh 缓存的误确认另取得 RED→GREEN：缓存降为 stale、matches_current 不再 True、reconciliation_required=True，GET 不重建绑定、不控制或写业务。

原 `test_recovery_binding_uses_the_confirmed_execution_sample` 机械迁移到新 Sample：先取得确认样本，再模拟相同 URI 的晚到替换，断言绑定保留该样本完整 ID 映射及 version，而非晚读重建；下一次读取 UNKNOWN 并失效，持久数据和业务 snapshot 保持不变。legacy completion consumer 仍隔离，没有把 NATURAL_COMPLETION 当作 stock 来源。

R-OBS 的 status 故障/并发屏障注入迁移到 `read_execution_sample`， nullable 字段通过 sample.status 注入；原 rollback、只读、terminal 与传播断言保留。同进程测试中只更换 publisher/coordinator 的包装 Service 共用原已确认 journal，避免把新 wrapper 构造当作重启重绑。断线重连原来期待旧 current progress fresh 的单条断言，与 F §8.9.2 新合同冲突，已改为 UNKNOWN/无业务 progress/绑定 None；没有放松业务保全断言，独立新六参数 proof 同时验证不重绑。

### 停止后删除的授权修正

初次 R-OBS-D6 为 140 passed / 1 failed：`test_delete_after_stop_notifies_queue_without_restarting_history` 预期只有 queue 通知，实际还产生 playback 通知。用户随后明确允许「对其它方面没有影响的话就允许」。修正限于 `delete` 的已有 STOPPED 且有后继项分支，未扩展到 S4。

精确 selector 重现 RED；最初提出的单行 `song_id=state.song_id` 修正仍 RED，整文件为 45 passed / 1 failed。完整状态比较显示不仅 song_id 被清空，MPD 取消 selected entry 后 elapsed 也变为 None，导致业务 position_seconds 改变。最终在既有 `_sync_player_queue` 与 `_confirm_preserved_state` 确認 STOPPED 后，保存原业务 PlaybackState，仅更新 updated_at。actual 仍如实取消选择，不伪造 PlayerStatus、不恢复 URI fallback。精确 selector GREEN，整文件 46 passed。新增提交/outer rollback 两参数 proof 首次 2 GREEN，断言业务状态（除时间戳）/History/active/session 保全、actual 无 song ID/URI/elapsed、绑定 None、没有播放/暂停/停止/seek 控制。

该分支修正的直接验证通过；附加播放回归的 5 项失败发生于其它分支，未进入此 STOPPED 且有后继项保存分支。因此没有发现此分支修正造成的其它影响，但不能将有限测试证据表述为所有播放行为无影响。

### 最终本地验证

以下均为授权修正后的真实执行结果：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_binding.py
# 39 passed, 1 existing warning，exit0
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py::test_recovery_binding_uses_the_confirmed_execution_sample
# 1 passed, 1 existing warning，exit0
# R-ARCH-D6
.venv/bin/python -m pytest -q server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# 3 passed, 1 existing warning，exit0
# R-OBS-D6
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_transitions.py server/tests/invariants/test_output_serialization.py
# 141 passed, 1 existing warning，exit0
# scoped Ruff：四个生产文件及四个本步测试文件
.venv/bin/python -m ruff check server/app/models/recovery.py server/app/services/playback_recovery.py server/app/services/playback_service.py server/app/services/playback_observation.py server/tests/invariants/test_d6_binding.py server/tests/invariants/test_d6_recovery.py server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_transitions.py
# All checks passed，exit0
# 附加 R-PB-D6（检查用户授权修正的其它影响，不实施 S4）
.venv/bin/python -m pytest -q server/tests/services/test_queue_manager.py server/tests/services/test_autoplay.py server/tests/services/test_playback_service.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py
# 130 passed, 5 failed, 1 existing warning，exit1
```

附加回归失败 selectors（保留原 tests/assertions，未 skip/xfail）：

- `test_playback_relationships.py::test_insertion_rejects_actual_playback_divergence_and_can_retry[queue]` 与 `[play-next]`：add 已生效但业务回滚，外部恢复 play 后 queue version/完整映射已变化，重试返回 502 `MPD execution binding lost before queue sync`，旧测试预期 200。
- `test_pre_batch6_corrective.py::test_queue_player_failure_rolls_back_and_key_can_retry[delete_pending-queue_delete]` 与 `[clear-queue_delete]`：队列同步部分控制已生效而业务回滚，旧绑定无法覆盖实际完整队列，重试同样 502，旧测试预期 200/204。
- `test_pre_batch6_corrective.py::test_current_delete_terminal_record_failure_restores_history[False]`：无后继删除的外部 Stop/queue 变化不能被 SQLite terminal rollback 撤销，原业务恢复后重试返回 502，旧测试预期 204。

这些涉及 S4 定义的固定执行意图、逐命令 prefix 与受控多命令版本归属。S3 不得按 URI 猜测/读取重建旧 occurrence，也尚无 S4 receipt 证明可安全重试，因此记录为完整 D6 的待处理失败，不为使附加回归 GREEN 进入 S4 或放松 assertion。S3 指定回归的本地 gate 满足不代表这些重试合同已经满足。

环境失败：无。既有 Starlette/httpx deprecation warning 未改依赖处理。首次 scoped Ruff 仅 import 排序失败，局部手动修正后重新通过。诊断时脱离 pytest setup 手工构造 fixture 曾出现 SQLite database locked；正规 pytest 中没有该环境/setup 失败，不计为产品 RED。早期旧故障注入/绑定 fixture 入口迁移和辅助读取/显式操作接线失败已按原 selectors 重跑修复。

完整逐命令 prefix/响应丢失/受控多命令版本归属仍由 S4 负责；审阅未将该项当作 S3 已实现。S5 History、S6 current adoption、S7 refill、S8 actual DTO、S9 runner、S10–S12 联合/实机/final gates 均未进入。没有访问 live MPD、Docker、外部服务，未改依赖、虚拟环境、永久 schema 或用户数据库。完整 D6 / Batch13 / Task6 final 继续 BLOCKED。

最终实际 diff 逐文件检查（包含未跟踪的新 `test_d6_binding.py`）：四个 S3 生产文件、四个相关测试文件和本 acceptance，共九个文件；其中 stopped-delete 分支是上述用户授权的局部范围扩展。`git diff --check` exit0；stat/status 和 HEAD 核对，无环境、依赖、schema、数据库、runner、临时调试或其它文档变更。新测试文件尚未加入 index；没有 commit/push/PR。

## 当前 stock corrective S4 — 2026-10-07

状态：**S4 实施及指定本地自动化 gate 满足；完整 D6 / Batch13 / Task6 final 仍 BLOCKED。** 本轮止于 S4，不进入 S5–S12。

### prerequisite 与授权范围

实施前重新读取 corrective plan、Playback spec §8.9 和 Architecture spec §12/§19.5，并核对源码/Git。S3 新鲜 gate 为 binding 文件及 confirmed sample selector **40 passed**，R-OBS/R-ARCH **144 passed**；没有仅依赖旧 checklist。既有 `.venv` 保持，沿用含未提交 S3 的 `feature/task-6-realtime-state` / `31be1c4`，保留已有改动。

用户两次明确允许最小白名单补充，已写入计划 S4：固定 occurrence 分配先于 Queue 写入（Service allocation scope、Repository 既有分配点、QueueManager 固定 context）；显式 `_prepare_play` add/play 委托同一账本；集合 API 传递请求身份/内容，journal 复用首次 context/随机顺序。只改变分配与执行委托，不改变候选算法、响应合同、schema 或后续步骤。

### 实施与故障语义

新增不可变 `ExecutionIntent/ExecutionCommand/CommandReceipt` 和 `ExecutionSynchronizer`。intent 固定最终 occurrence IDs、Queue revision、基线样本、目标与命令顺序；同 identity 内容冲突拒绝。每条控制先登记 sent，返回后立即登记 ACK/返回 ID，完整一致样本验证成功后确认 prefix。重试仅续执行未发送后缀，不能重新分配 ID、重做已确认命令或重新规划。

ownership 同时检查连接/partition、playlist version 的逐命令变化、完整 MPD ID/URI/position、模式及 current。add 必须使用返回 ID；丢失 add/play/pause 响应封存 UNKNOWN，不能按 URI 猜测或盲重发。丢失 delete/move 响应仅在连续版本及完整样本能唯一证明一个不同结果时确认；no-op 或外部漂移拒绝。current 离开再返回也不能清除已发现的不确定性。协议读取失效跨 rollback/reconnect 保持封锁。

初次显式播放可选择采样中已有 URI 对应的控制 entry，但该临时控制身份不建立业务 occurrence 绑定，不用于认领 lost-add。仅已知 ACK/明确拒绝、无 sent/UNKNOWN 的显式请求，允许依原重试例外建立独立 reconnect takeover 意图；不会续用跨连接的旧 ownership。辅助最终 status 的明确 ACK 拒绝使绑定失效；协议样本错误、断连/timeout 则封存意图，二者分别处理。

outer rollback 恢复 Queue/PlaybackState/History 与 runtime active，保留已执行 prefix；只读观察遇到严格匹配的已知 rollback prefix 时清除未同步业务绑定，不销毁独立 retry 证据，也不控制播放器。receipt 在提交前预物化且不可见，visible 后 replay 零读源/零控制，即使 generation 已改变；发布或 postcommit cancellation 不撤销已提交业务。visibility 故障隔离，GET 503，不能重执行。

### RED/GREEN 与新增 proof

- `test_each_command_prefix_is_retried_only_when_owned`：add/delete/move/play × before-send/after-ack/after-confirm，最初因缺执行器 RED，最小实现后同 selector 12 GREEN。断言固定 intent/IDs、无重复 add、提交后零控制与 revision 不变。
- `test_lost_add_response_never_guesses_or_resends`：实现核心后首次 GREEN，记录为新增 proof，没有虚构 RED。实际执行 add 后 EOF，业务不变、无 receipt，再次调用不 add。
- `test_execution_outer_failures_and_post_commit_receipt`：10 个边界；9 个首次 GREEN，visibility 首次 fixture 接线错误修正后 GREEN，不计产品 RED。terminal 在真实 idempotency INSERT 通过 SQLite trigger 拒绝；materialization 在 journal 的真实 deepcopy 入口故障；另覆盖 Queue、state、runtime、outer commit、提交前/后 cancellation、publisher、visibility。提交前完整业务保全且无成功事件/receipt；提交后 replay 不控制，visibility GET 503。
- 审阅与补充测试取得真实 RED→GREEN：lost play 不能以自然前进结果认领；current 离开再返回；显式播放 outer rollback 重试零控制且 IDs 固定；子 task 不继承 allocation writer；辅助协议读错误后重连不能绕过 UNKNOWN；只读 observation 不销毁已证明 rollback prefix。其它 drift、多命令后缀、集合随机计划/terminal rollback、已提交 receipt 优先于新 generation/源读取等首次 GREEN，按新增 proof 记录。
- 最后辅助 status 的过严 UNKNOWN 分类使既有实时重试 6 项 RED；区分明确拒绝与协议失效后，同 selector 的全部参数加协议封锁 proof **19 passed**。未放松原断言或 skip/xfail。

### 最终 fresh 验证

全部使用现有 `.venv/bin/python`，以下 exit0：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_execution.py server/tests/invariants/test_d6_binding.py server/tests/invariants/test_d6_recovery.py::test_recovery_binding_uses_the_confirmed_execution_sample
# 94 passed = S4 54 + S3 gate 40
.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py
# R-TX-D6: 19 passed
.venv/bin/python -m pytest -q server/tests/services/test_queue_manager.py server/tests/services/test_autoplay.py server/tests/services/test_playback_service.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py
# R-PB-D6: 135 passed（实施前 130 passed / 5 failed）
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_delivery.py server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_transitions.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# delivery + R-OBS-D6 + R-ARCH-D6: 154 passed
.venv/bin/python -m ruff check server/app/api/playback.py server/app/models/recovery.py server/app/repositories/queue_repository.py server/app/services/playback_recovery.py server/app/services/playback_execution.py server/app/services/playback_service.py server/app/services/queue_manager.py server/tests/invariants/test_d6_execution.py
# All checks passed
```

仅既有 Starlette/httpx warning；环境/依赖失败无。两次独立只读审阅指出的 ownership/显式重试缺口均修复，最后边界审阅未发现新 Important 问题；审阅结论不代替上述测试。

### 隔离 legacy 回归与限制

额外整文件 `test_d6_recovery.py` 为 **84 passed / 14 failed，exit1**，不能称整文件 GREEN。其中 legacy completion rollback 非 confirmation 的 21 个参数通过；confirmation 的三个故障注入仍针对旧 status 入口。为核对来源，用实施前保存的 S3 五个模块源码在独立进程 overlay，显式替换 main 的 Service/Manager/Repository，并逐 fixture 断言同步方法来自 baseline；仅以 wrapper 兼容新增集合请求参数。该比较同样 **84 passed / 相同 14 failed**，未改工作区源码。比较进程额外有 pytest already-imported warning；它是诊断证据，不能当普通验收 PASS。

保留失败 selectors：`test_unknown_recovery_preserves_all_authorities[duplicate/missing-id/queue-mismatch/pending-duplicate]`；`test_recovery_source_failure_preserves_authorities[unavailable/status/queue_entries/validator-unavailable]`；`test_natural_completion_promotes_confirmed_successor[confirmation-fails]`；`test_recovery_business_generation_follows_committed_current[delete]`；`test_bound_external_pause_resume_preserves_history[confirmation-conflict]`；`test_recovery_rollback_retry_keeps_identity[confirmation-successor/confirmation-autoplay/confirmation-empty]`。它们涉及旧 runtime binding 保留期待、旧 status 故障注入或无有效绑定 fixture；没有借 S4 扩范围修改旧 consumer assertions。新 S4 stock 故障 proof 不由这些 legacy consumer 替代。

最终实际 diff 对照实施前 S3 文件逐项核对，S4 增量仅七个白名单生产文件（含上述授权补充）、新执行测试、计划授权说明与本 acceptance；已有 S3 observation/测试改动保留。`git diff --check`、scoped Ruff、stat/status 检查通过；新执行器及测试的 untracked 内容也已检查。未修改依赖、环境、永久 schema/数据库或后续步骤文件，未访问 live MPD/Docker/外部服务，未 commit/push/PR。S4 本地 gate 满足不意味着旧 D6 整文件、目标 MPD 能力、联合/实机或 final gate 通过。

## 当前 stock corrective S5 — 2026-10-07

状态：**S5 指定实现、RED→GREEN 与本地 gate 满足；完整 D6 / Batch13 / Task6 final 仍 BLOCKED。** 本轮止于 S5，未进入 S6–S12。

### prerequisite、范围与语义

沿用含未提交 S3/S4 的 `feature/task-6-realtime-state` / `31be1c4`，保留既有改动且未创建或修改 `.venv`。实施前 fresh gate：S3/S4 专项 **94 passed**、R-TX **19 passed**、R-PB **135 passed**、delivery/R-OBS/R-ARCH **154 passed**；只有既有 Starlette/httpx deprecation warning。由此确认 S3/S4 指定前置满足，不以 acceptance checklist 代替实际运行。

实现严格限于 S5：`HistoryService.discard_unconfirmed_active()` 只清 runtime active、保留 session，不写 History；PlaybackService 在 start_track/play_context/play_now/next/previous/current-delete/stop 控制前，以有效 `ExecutionBinding`、完整 MPD entry ID/position/URI 和业务 Queue occurrence 校验 active，不凭 URI 或观测时间认领。失配 active 在领域事务中 discard；Stop 仍清 session 并关闭 AutoPlay，next/play_now 只按原合同创建新 active。

outer/terminal rollback 已确认作用于旧 active 的显式操作，需要在 retry 时保留该事实，否则 rollback 恢复的 active 会被错误当成未经认证离开。RecoveryJournal 因此按固定 operation_id 保存 active identity 的 pending/confirmed 资格：只有控制及最终状态已确认后才标 confirmed；业务 rollback 保留这份外部事实，commit visible 清除；未发送、未确认、binding/identity 冲突不能升级。未增加 History reason、schema、公开 DTO/事件字段或 S6 current adoption。

### RED→GREEN 与授权迁移

- `test_unknown_departure_then_explicit_stop_does_not_relabel_old_active`：stop/next/play_now 最初均写出旧 A 的 STOP/SWITCH_AWAY，**3 failed**；最小 active 资格校验与 discard 后同 selector **3 passed**。
- `test_discard_preserves_session_and_rolls_back_without_event`：最初因接口不存在 **1 failed**；实现后确认 commit 时 active=None/session 保留/永久 History 不变，outer failure 时 active/session 恢复且无事件，**1 passed**。
- 首次事务回归揭示已确认外部动作的资格在 outer rollback 后丢失：相关 transaction selector **9 failed**，R-PB terminal/delete/skip selectors 同类失败。增加 operation-scoped confirmed 资格后，精确复跑分别 **9 passed**、**10 passed**，未用 pending/transport failure 冒充确认。
- 旧 `test_stop_transport_failure_rolls_back_and_retries` 每个参数在失败后强制 `reconnect()` 更换 connection epoch，却仍期待旧 A/STOP；这与 F §8.9.2/§8.9.4 冲突。用户明确授权只迁移该 selector：重连后的成功 Stop 清 active/session，但不写永久 History；同 selector **3 passed**。没有扩大到其它测试或生产合同。

### 最终 fresh 指定验证

全部使用既有 `.venv/bin/python`；下列均 exit0：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_history.py
# 4 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_stop_confirmation.py
# 5 passed
.venv/bin/python -m pytest -q server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/invariants/test_realtime_history.py
# R-H-D6: 13 passed
.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py
# R-TX-D6: 19 passed
.venv/bin/python -m pytest -q server/tests/services/test_queue_manager.py server/tests/services/test_autoplay.py server/tests/services/test_playback_service.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py
# R-PB-D6: 135 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_execution.py server/tests/invariants/test_d6_binding.py server/tests/invariants/test_d6_recovery.py::test_recovery_binding_uses_the_confirmed_execution_sample
# S3/S4 regression: 94 passed
.venv/bin/python -m ruff check server/app/services/history_service.py server/app/services/playback_service.py server/app/services/playback_recovery.py server/tests/invariants/test_d6_history.py server/tests/invariants/test_stop_confirmation.py
# All checks passed
```

### Broad-suite limitation与剩余 gate

额外运行 `.venv/bin/python -m pytest -q server/tests` 得到 **1136 passed / 54 failed / 1 existing warning**，因此不能声称 repository-wide suite GREEN。失败包含 S4 已记录的14项 legacy D6，以及未在 S2–S5 白名单完成迁移的旧 Fake/API、真实 Adapter fixture、observer/queue/realtime tests。精确复跑 `test_realtime_playback_transport.py` 为15 passed/5 failed：失败的 Stop cases 重新构造 PlaybackService、丢失 binding 却复用旧 History active，仍期待旧 STOP；按 F §8.9.2/§8.9.4 新 Service 无资格写该原因。本轮未获授权修改这些 S5 白名单外 tests，也未以生产 fallback 让它们变绿。system-read 2项和 observer lifecycle 2项精确复跑同样仍失败，属于当前未完成迁移/既有路线范围，不作为 S5 指定 gate 的 GREEN。

独立只读 S5 审查为 **Critical 0 / Important 0 / Minor 1**，审查者独立复跑 S5+Stop **9 passed**；未发现 reason/schema 扩展、错误 History 写入或 S6 current adoption。延期 Minor：discard 分支登记的 pending active qualification 因 active 已清除而不会进入 confirmed/visible cleanup；operation_id 隔离防止普通复用或错误 History，但进程内 stale bookkeeping 可能随此类操作增长。本轮按计划不为 Minor 扩大修复范围。

S5 的 implementation、指定 automated tests 和本地环境验证 **PASSED**；repository-wide regression、目标 MPD runtime、S6 current adoption、S7–S12、完整 D6 Relationship/Contract Matrix、Batch13 与 Task6 final 均仍 **BLOCKED/NOT RUN**。未运行 live MPD/Docker/外部服务，未改依赖、永久 schema、数据库或后续步骤；未 commit/push/PR。

## 当前 stock corrective S6 — 2026-10-07

状态：**S6 implementation、全部 selectors、旧 D6 冲突迁移及规定本地回归 gate PASSED。完整 D6 / Batch13 / Task6 final 仍 BLOCKED。** 用户已授权最小 PAUSED current-delete 补充并完成修复；未进入 S7。

### 前置与实施边界

沿用含未提交 S3–S5 的 `feature/task-6-realtime-state` / `31be1c4`，保留既有工作，使用现有 `.venv`，未新建环境或 checkout。先读取 P/F，核对实际源码与 Git；fresh S4/S5/Stop 文件 **63 passed**，binding/confirmed-sample/TX/PB/H/delivery/OBS/ARCH 集合 **356 passed**，确认 S4/S5 指定前置满足。Python 3.14.4、pytest 9.1.1、Ruff 0.16.9；没有环境失败。

S6 增量共四个生产文件：`PlaybackService.reconcile_external_status` 的 stock 分支、QueueManager/Repository 的 `adopt_current`、ExecutionSynchronizer 的清理/移动计划与 await 后 fence 校验。复用已有不可变 ExecutionIntent，不改 models/schema/依赖。新增 `test_d6_current.py`；迁移计划指定的旧 D6、PlaybackService 与 outer reconciliation rollback 冲突用例。S6 前源码副本保存在本地 ignored SDD workspace 中，用于逐项核对增量；既有 S3–S5 修改不当成本次新增。用户随后授权 `_sync_player_queue` 已确认显式后继的目标状态修正，补充范围已写入 P 的 S6，仍在同一个 Service 文件内；未扩展其它 helper。

### 当前事实、Queue 与故障语义

有效完整映射中的 A→B/C 以精确 entry ID/URI/position 接纳，目标必须是原 pending。Queue CAS 仅将 A 置 -1、旧 Played 各减1，目标置0，其余 pending 按原相对顺序保留，revision 恰 +1；IDs/song/source/context 均保持。A→C 的 B 保留待播，不能声称 B 曾播放或没有播放，稍后可能再播放。

固定 intent 只删除 A、必要时移动目标到执行队首，保留目标 MPD ID，不 add/play/seek/next。PAUSED 保持 PAUSED。逐命令 ACK/confirmed prefix 与完整样本核验后，目标最终0及全映射正确才同 outer 提交 Queue/state/discard active/binding/receipt/通知。自动接纳不新建 History active、不写永久 History、不认证 natural、原因或实际 ended_at；session/AutoPlay/context 保留。同 entry 重播不分割业务或 History。

陌生项/队列编辑/ID 复用/不支持模式/STOPPED/迟到样本/代次漂移均 fail closed。清理期间再次切歌返回 UNKNOWN，保留已执行 MPD prefix，不伪装物理回滚；CAS conflict 使用原 typed error，旧 intent 封锁。业务失败恢复 Queue/state/active/session/binding/generation、零成功 receipt/通知；归属可证明的 retry 仅执行未发送后缀。后续同态调用零控制、零 revision 增长。TRANSPORT 双读确认同时校验 business/binding generation，不能采纳迟到确认。

### RED/GREEN、迁移与审阅证据

- 三个规定 selector 首次完整有效输入：**25 failed / 8 passed**。16 个 adoption 变体与9个不同原因标签的合法目标样本因缺当前接纳而真实 RED；same-entry 与7个负向参数首次 GREEN，记录为新增 proof。早期 duplicate fixture 错方法名、foreign fixture URI 未载入、error sample 使用 dataclass replace 的 setup 错误修正后才计算此 RED，不计产品失败。
- 最小实现后同三个 selector **33 passed**；覆盖 B/C × existing Played × PLAYING/PAUSED × duplicate URI。追加同 URI 的 A→另一个 A occurrence，确认按不同 MPD/business ID 接纳，不依赖 song/URI 变化。
- 新增真实 asyncio barriers：清理后外部 MPD 再选 D，旧目标不提交/后续 move 不发送；另一 writer 提交 D 后迟到旧样本，业务保留该 writer 的新提交，恢复零控制。
- 追加 Queue 真 CAS/非法目标、outer rollback、Queue/state/materialization/discard 失败、提交前 cancellation、publisher 失败、delete/move × ACK/confirmed/lost-response cancellation 的固定后缀 retry。它们在现有事务/执行账本上首次 GREEN，不虚构 RED。新增测试早期误要求 journal 中没有任何历史 receipt，修正为没有本次 `/adopt` 成功 receipt；不删除既有成功 receipt。
- TRANSPORT confirmation 中代次改变的精确 selector 真实 RED（仍保存 PAUSED），增加确认 fence 后同 selector GREEN。
- 旧 foreign 实际是已绑定 B 的冲突：保留真正新 foreign entry 的 UNKNOWN case；新 stock/service/API proof 确认 B 接纳。旧 status 故障注入机械迁移到 ExecutionSample；漂移/读取断连时 binding 必须失效，仍完整断言 durable/business/History 不变。legacy natural assertions 保留；externally stopped A 后显式接管不再补 SWITCH_AWAY，符合 S5。没有 skip/xfail、弱化 natural reason 或生产 validator 注入。
- 一次独立只读审阅 **Critical 0 / Important 0 / Minor 0**；建议的同 URI 目标及 discard/publisher 集成覆盖已补。审阅未运行 pytest；下列 fresh 实测是自动化证据，不以审阅代替运行。

### 最终 fresh 验证

以下为用户授权补充完成后的最终 fresh 结果，全部使用既有 `.venv/bin/python`，均 exit0，仅既有 Starlette/httpx deprecation warning：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_current.py
# 58 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_current.py server/tests/invariants/test_d6_execution.py server/tests/invariants/test_d6_history.py server/tests/invariants/test_d6_binding.py
# 155 passed = S6 58 + S4 54 + S5 4 + S3 39
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py
# 98 passed
.venv/bin/python -m pytest -q server/tests/services/test_queue_manager.py server/tests/services/test_autoplay.py server/tests/services/test_playback_service.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py
# R-PB-D6: 135 passed
.venv/bin/python -m pytest -q server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/invariants/test_realtime_history.py
# R-H-D6: 13 passed
.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py
# R-TX-D6: 19 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_transitions.py server/tests/invariants/test_output_serialization.py
# R-OBS-D6: 141 passed
.venv/bin/python -m ruff check server/app/services/playback_service.py server/app/services/queue_manager.py server/app/repositories/queue_repository.py server/app/services/playback_execution.py server/tests/invariants/test_d6_current.py server/tests/invariants/test_d6_recovery.py server/tests/services/test_playback_service.py server/tests/api/test_pre_batch6_corrective.py
# All checks passed
```

### 授权补充、已关闭失败与 diff

初次 S6 验证中旧 D6 为 **97 passed / 1 failed**；唯一失败 `test_recovery_business_generation_follows_committed_current[delete]` 是 S4/S5 已记录的遗留生产缺陷：已确认 PAUSED 时 current-delete 的 `_prepare_play` 明确播放后继，但 `_sync_player_queue` 用旧业务 PAUSED 构造最终目标，执行器拒绝实际 PLAYING。未用修改旧断言或将 PAUSED 自动接纳改为 resume 解决该问题。

2026-10-07 用户明确授权最小补充。只在已有 `explicit` 归属、目标非空、精确 MPD ID 匹配及 sample 为 PLAYING 时，固定意图的目标状态取已确认 PLAYING；其余路径仍取原业务状态，完整执行与最终确认检查保留。旧失败 selector fresh **1 RED → 1 GREEN**；新增 `test_paused_current_delete_confirms_explicit_successor[commit/rollback-retry]` 因同一目标状态缺陷 **2 RED → 2 GREEN**，连同原 selector **3 passed**。新测试曾误以为 current-delete 删除 A 的业务记录；核对现有 Repository/Manager 的 A→Played 合同后仅纠正新测试，旧 D6 原断言不变。精确 proof 同时确认后继 B 的原 MPD ID、Queue +1、已认证显式 SWITCH_AWAY、active/session，以及 outer rollback 后全部恢复、retry 不重播/不重复 History。

授权修正后依次通过 S6 整文件58、旧 D6 整文件98及所有规定回归；没有剩余 S6 阻塞项。此前独立审阅的 S6 主体无 Critical/Important/Minor；本次最小授权修正按 RED→GREEN、原断言与最终回归/diff复核完成，未重复派发审阅。

已检查 S6 增量 diff 与本次 untracked 测试/既有执行器内容；scoped Ruff、`git diff --check`、stat/status 检查通过。授权补充仅 Service 目标状态、新增精确测试、P 的授权说明及本 acceptance；未修改其它 helper、模型、其它测试、依赖、环境、永久 schema、数据库或 runtime 文件。没有 live MPD/Docker/外部服务、commit/push/PR。implementation、automated tests、本地环境验证及 S6 指定 acceptance gate **PASSED**；repository-wide regression、目标 runtime、S7–S12/联合验收未执行，不能声称全仓或目标运行时通过。原因认证与中间项历史恢复不在本合同能力内。D6/Batch13/Task6 final 保持 BLOCKED。

## 2026-10-07 S7 — confirmed-remaining AutoPlay 预同步

**本次只实施 S7；S7 本地 gate PASSED，S8 未进入。D6 / Batch13 / Task6 final 仍 BLOCKED。**

### 输入、S6 gate 与本次边界

读取唯一 active corrective plan 的 S7/共同 U/T/F/I/O、固定回归命令及 Playback Spec §6/§8.9.1–6，核对既有 S6 acceptance、源码、Git。实际 branch `feature/task-6-realtime-state`，HEAD `31be1c4`；起始保留 S2–S6 的既有未提交内容，未把旧 checklist/历史 GREEN 当作 fresh 证据。继续使用当前 checkout 和原 `.venv`，不迁走这些未提交前置实现。

执行前 fresh：S6 `test_d6_current.py` **58 passed**；AutoPlay12 + Execution54 + 旧 D6 98 **164 passed**；R-PB135/R-H13/R-TX19/R-OBS141 合并执行 **308 passed**。S6 没有剩余 gate 阻塞。环境验证 `test -x .venv/bin/python` exit0，Python3.14.4、pytest9.1.1、Ruff0.16.9。没有依赖安装/版本调整或环境修改。

本次生产增量仅：

- `PlaybackService.maintain_execution()`：先独立核验/接纳 current，再按清理后确认 pending 数量规划。剩余4补最多5；剩余5不补。整个维护调用加入同库 outer transaction，最终确认才提交，refill 不调用 play/seek/next/pause，不制造 History/active。
- `ExecutionSynchronizer` 的 add-only append 路径：固定候选及 IDs，逐命令 ACK/完整前缀确认；绑定内 current 在规划/add/Queue写入期间前进时重新采样当前位置，并由既有 S6 在独立固定 cleanup 身份下接纳，不重复候选/add。不改变普通 S4 `execute()` 默认严格目标确认。连接/partition/version/完整队列/mode 漂移、STOPPED、player error 均停止控制。
- `RecoveryJournal` 保存本进程固定 refill items/绑定及 cleanup 绑定，业务 rollback 不抹除已确认外部前缀；原 current 接纳与 refill 同时 outer rollback 时，可重建同一业务投影并再次验证固定执行前缀，最终 receipt 只在 visible 后出现。
- `QueueRepository.add_autoplay_batch(..., planned_items=...)` 可接受固定 occurrence IDs，验证原候选过滤结果、source/context/position/ID唯一性及 CAS，不能覆盖其它 Queue 项。不传该参数的既有行为保留。
- `AutoPlay.plan_refill` 仅补齐与既有 repository 一致的 current fallback 边界：已有 pending current 时不再规划重复 current。保持5/5、Context优先、全库 AVAILABLE、同批去重、含 Played 的 Queue排除与既有单曲 fallback；不扩大循环策略、不按 song/URI 去重 MANUAL。

新增测试仅 `server/tests/invariants/test_d6_autoplay.py`；文档仅追加本 acceptance。P、models、API、History/observer/DTO/runner、既有测试均没有本次新增修改。既有 S2–S6 未提交改动保留；不以整个 working-tree diff 冒充 S7 增量。

### RED → GREEN、故障与审阅记录

1. 规定 `test_refill_uses_confirmed_remaining_and_preserves_manual_order` 全8参数因缺 `maintain_execution` **8 RED → 8 GREEN**；覆盖剩余4/5、同current/A→C、PLAYING/PAUSED、MANUAL重复 occurrence。A→C 先把未观察 B 同步到 C 后再计数，精确 MPD current ID 保留，无服务重播。
2. 规定 `test_empty_stop_disconnect_and_refill_failure_do_not_restart` 全6参数同样 **6 RED → 6 GREEN**。无 AVAILABLE/无候选、显式 Stop 后 Library 变化、断线、append故障与规划后外部 Stop 均不重启；未知停止不改用户 AutoPlay 意图。无候选以 `RecoveryResult.diagnostic="NO_CANDIDATES"` 表示，保留现有 outcome 集合。
3. 独立只读 reviewer 报告 **Critical0 / Important1 / Minor0**：原初实现将普通 current 前进永久标 UNKNOWN/失效，无法继续接纳。新增 `test_current_advance_resamples_owned_prefix_without_duplicate_candidates` 六参数真实 **6 RED → 6 GREEN**，覆盖 planner/second-add/queue-write × commit/outer rollback；随后再次 maintenance 为 UNCHANGED、零新增控制/Queue delta。修正后保留固定候选，完整校验 add-only prefix，再用 S6 接纳 current。审阅不是 pytest 证据；修正由作者按 TDD、回归和增量 diff 复核，未重新派发第二次审阅。
4. 单曲 pending fallback 暴露 planner/repository 分歧：pending current case 真实 **1 RED → GREEN**；无 pending 的 fallback proof 首次 GREEN。planner 现在不会在 repository 拒绝的重复 current 上发送 add。最终 Queue/完整 execution IDs 一致。
5. `test_player_error_pauses_refill_without_changing_user_intent` 规划前/during-add **2 RED → 2 GREEN**；player error 不继续 add、不改变业务/用户意图。`test_refill_confirmation_failure_propagates_to_outer_owner` **1 RED → 1 GREEN**：确认失败时若调用者已有 outer，必须抛给 outer owner，不能吞异常后把暂存 Queue 提交；独立调用在自己的 outer rollback 后返回 UNKNOWN。
6. 最终回执一致性复核 `test_refill_diagnostic_returns_the_committed_adopted_playback` **1 RED → 1 GREEN**：合法 current 已由 S6 接纳、随后 refill 因 player error 暂停时，UNKNOWN诊断返回该已确认提交的 playback，不返回旧A。
7. 追加 proof 首次 GREEN：固定 IDs与source/context/position/CAS验证、ACK/confirmed后取消、lost add响应不猜测/不重发、Queue写失败、precommit取消、outer rollback固定 retry、mode/unbound/external-stop、Queue写入后STOPPED最终确认、真实 asyncio并发Stop串行 barrier、receipt materialization失败、publisher失败及提交后可见性/通知。所有失败前业务恢复，提交后publisher故障保留receipt/提交，无 natural event。

新测试编写期间纠正了实现调试及 fixture/断言错误，分别记录：初次实现的 await generator TypeError 改为具体候选列表；MANUAL比较不能禁止 S6 已授权 current C 到0/A到Played，只比较未操作 pending 的相对顺序与所有原 IDs；单曲 setup 的 Service.delete 会立即既有refill，改用受控 Repository/同步准备真实空pending。queue-write progression 注入由每次retry重复外部play改为单次外部前进；否则“retry零控制”会把测试自己重发的外部命令误算为Service控制。没有修改旧用例、放宽自然原因断言、skip/xfail 或改写既有产品策略。原初把合法 current 前进预期 UNKNOWN 的新测试已按 S7 authority 改为上述独立成功 proof；最终失败确认 proof 使用实际 STOPPED。

### 最终 fresh 结果

均从根目录用 `.venv/bin/python` 执行，exit0；仅既有 Starlette/httpx deprecation warning：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_autoplay.py::test_refill_uses_confirmed_remaining_and_preserves_manual_order
# 8 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_autoplay.py::test_empty_stop_disconnect_and_refill_failure_do_not_restart
# 6 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_autoplay.py
# 49 passed
.venv/bin/python -m pytest -q server/tests/services/test_autoplay.py
# 12 passed（Context优先、5/5、单曲、同批去重、手动并发/Context变化/Stop原tests保留）
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_execution.py
# 54 passed
.venv/bin/python -m pytest -q server/tests/services/test_queue_manager.py server/tests/services/test_autoplay.py server/tests/services/test_playback_service.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py
# R-PB-D6: 135 passed
.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py
# R-TX-D6: 19 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_current.py server/tests/invariants/test_d6_binding.py server/tests/invariants/test_d6_history.py server/tests/invariants/test_d6_recovery.py
# 199 passed = 58 + 39 + 4 + 98（S7执行路径/重新采样修正后）
.venv/bin/python -m ruff check server/app/services/autoplay.py server/app/services/playback_service.py server/app/services/playback_execution.py server/app/services/playback_recovery.py server/app/repositories/queue_repository.py server/tests/invariants/test_d6_autoplay.py
# All checks passed
```

已对本次起始源码副本逐文件检查 S7 增量，并检查实际 working-tree diff/stat/status、`git diff --check` 和新增 untracked 测试/执行器。无其它文件新增修改、临时debug、generated/env/database/dependency变更；不删除原 runtime 文件，无 commit/push/PR/live MPD/Docker/外部服务。

**implementation completed / automated tests completed / local environment validation completed / S7 acceptance satisfied。** 未进入 S8/DTO、S9 runner或 S10–S12。全仓 regression、目标 MPD 运行时能力、联合 final gate 本次未执行；短歌曲/预算不足、未知停止/断线/错误不承诺无限续播，原因与实际 ended_at/遗漏History仍不认证。D6、Batch13、Task6 final 保持 **BLOCKED**。

## 2026-10-08 S8 — actual-state DTO、完整快照与只读传播

**本次只实施 S8；S8 本地 gate PASSED，未进入 S9。D6 / Batch13 / Task6 final 仍 BLOCKED。**

### 前置 gate、边界与实现

读取 active corrective plan、Architecture A §12.3.1 与 Task6 batch plan，核对实际 branch `feature/task-6-realtime-state`、HEAD `31be1c4` 及源码/Git。保留当前 checkout 的 S2–S7 未提交实现并继续使用原 `.venv`；执行前 fresh S6/S7 gate：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_current.py server/tests/invariants/test_d6_autoplay.py server/tests/invariants/test_d6_history.py server/tests/invariants/test_d6_recovery.py
# 209 passed, 1 existing Starlette/httpx deprecation warning
```

本次 additive 公共表示新增 `actual_current {entry_id, uri, position}`、`actual_freshness`、`bound_queue_item_id` 与 `sync_status` 六值枚举；旧构造默认仍为 null/unknown/UNBOUND。`current_song` 和 `playback.song_id` 继续来自已提交业务状态与 Library，绝不以实际 MPD identity 覆盖。实际 identity 只来自 S2 的单次 `ExecutionSample`；无样本为 unknown，断线保留最后成功样本并转 stale，foreign/unbound 实际 identity 可以 fresh，而旧绑定 progress 必须 null/unknown。

`StateService.get_full_snapshot()`、GET `/api/state` 与 WS `/api/realtime` 原本已共享同一 domain snapshot/public encoder，因此无需分别增设实现；协议版本保持1，coordinator 原 content-diff 已能登记新增字段变化。读取链只调用 observation/cache/local repositories：测试把 MPD controls、`reconcile_external_status` 和 `maintain_execution` 全部替换为 forbidden，仍能获得快照；Queue、History、terminal business snapshot 前后相等。

S7 的 `NO_CANDIDATES`/`SYNC_FAILED` 原来只存在 `RecoveryResult`，只改 `get_observation` 无法向后续 snapshot 传播。因此在既有 `maintain_execution()` 结果点增加一个窄的表示诊断发布：成功结果在同一事务内 staged，回滚后的 UNKNOWN 以单调 operation number 防止迟到结果覆盖新结果；它不发控制、不执行恢复、不写 Queue/History。此为 S8 对白名单中“同步诊断 facade”的必要落点，代价是触及既有 S7 方法，但没有改变 S7 控制语义。

显式 Stop 的 `CONFIRMED` 证明同时固定 player、connection epoch、playlist version、完整 Queue occurrence↔MPD 映射及 Stop 时 current identity；service/MPD restart 或同连接外部 add/play/stop 均清除连续性并报告 UNBOUND，不能用 persisted STOPPED 冒充实际确认。

计划要求的两个同名 `test_d6_state.py` 在原非 package test 目录下会触发 pytest import-file mismatch。仅新增 `server/tests/api/__init__.py` 使规定 API 路径具有唯一模块名；未改 pytest 全局配置、未重命名计划 selector、未改变生产 package。

### RED → GREEN 与独立审阅

规定 invariant 首次有效运行因缺 `actual_current` RED，最小 domain/observation 实现后 GREEN；API 五种 recovery 首次有效运行均因缺 public `actual_current` RED，public schema 后 GREEN。后续真实 RED 分别覆盖：维护诊断不可见、空实际样本断线未 stale、unbound freshness 不过期、诊断被 observe 错误清除/保留、旧 public constructor 缺默认值、service restart 的 stopped 样本被误确认、同连接 foreign identity 漂移及迟到旧维护覆盖新 refill。

独立只读审阅最终报告 **Critical0 / Important2 / Minor0，assessment: ready with fixes**。两项 Important 均建立确定性失败测试后修正：

- 旧 `NO_CANDIDATES` 在 post-commit callback 阻塞时，可晚于新的 APPLIED refill 发布并覆盖 CONFIRMED；现在诊断在所属事务内 staged，回滚发布另有调用顺序 fence。
- Stop proof 仅检查连接时，外部 `d.flac` add/play/stop 会把业务 A + 实际 D 错报 CONFIRMED；现在完整执行身份/playlist/current 任一漂移即失效。

修正后的精确 Stop/并发 selectors **6 passed**，S8 两文件 **17 passed**。没有修改旧断言、skip、xfail 或通过读取触发恢复。

### 最终 fresh 验证与限制

均从 repository root 使用 `.venv/bin/python`，exit0；pytest 仅同一个既存 Starlette/httpx deprecation warning：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_state.py server/tests/api/test_d6_state.py
# 17 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_recovery.py::test_reconnect_replaces_all_domains_and_epoch
# 6 passed
.venv/bin/python -m pytest -q server/tests/api/test_realtime.py
# 7 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_transitions.py server/tests/invariants/test_output_serialization.py
# R-OBS-D6: 141 passed
.venv/bin/python -m pytest -q server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/invariants/test_realtime_history.py
# R-H-D6: 13 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# R-ARCH-D6: 3 passed
.venv/bin/python -m ruff check server/app/models/realtime.py server/app/api/realtime_schemas.py server/app/services/playback_observation.py server/app/services/playback_service.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_d6_state.py server/tests/api/test_d6_state.py server/tests/api/__init__.py
# All checks passed
.venv/bin/python -m compileall -q server
# exit 0
git diff --check
# exit 0
```

在最终审阅修正前另做的 exploratory `server/tests` 为 **1267 passed / 39 failed / 1 existing warning**；失败集中于 S8 外的旧 API fake 尚未接受 S4 request 参数、旧 Adapter fake 未提供一致 S2 sample、旧 realtime Queue/transport fixture 缺 S3 binding，以及已知 system read lazy queue-state 问题。未在 S8 越界迁移这些旧测试，因此不能声称 repository-wide green；该 exploratory run 也不替代上述 S8 指定 gate。

已检查 actual working-tree status/stat/diff、S8 文件内容与 `git diff --check`；既有 S2–S7 diff 保留，没有临时调试、generated、数据库、依赖或环境文件新增修改。未运行 live MPD、NAS、Docker 或外部服务；没有 commit/push/PR。Task8 UI、S9 runner、S10–S12 与最终联合验收均未实施。

**implementation completed / targeted automated tests completed / local environment validation completed / S8 acceptance satisfied。** 四种恢复边界只声明上述本地服务/API proof，不冒充完整 Context/未知 History/目标运行时恢复。D6、Batch13、Task6 final 保持 **BLOCKED**。

## 2026-10-08 S9 — 独立 recovery runner 与生命周期装配

**本次只实施 S9；S9 本地 gate PASSED，未进入 S10。D6 / Batch13 / Task6 final 仍 BLOCKED。**

### 前置 gate、实施边界与装配

读取 active corrective plan、Playback Spec（尤其 §8.9.2/6/7）和 Architecture Spec（尤其 §12.1–12.3.1），核对实际 branch `feature/task-6-realtime-state`、HEAD `31be1c4` 与源码/Git。当前 checkout 已有 S2–S8 未提交实现；保留这些前置内容，在原 feature checkout 和原 `.venv` 内续作，不创建遗漏前置实现的新 worktree，不安装或修改依赖。环境 fresh：Python 3.14.4、pytest 9.1.1、Ruff 0.16.9。

前置 fresh 核验：S2 execution sample / S3 binding / S4 execution / S5 history / S6 current / S7 autoplay / S8 两份 state proof 合计 **227 passed**。另执行 player 全集、旧 D6、realtime delivery、R-PB/R-H/R-TX/R-OBS/R-ARCH、reconnect 指定 selector、realtime API，合计 **472 passed**。S2–S8 的规定本地 proof 与直接回归均满足；不把历史 checklist 当作本次证据。

本次生产增量仅：

- 新增 `PlaybackRecoveryRunner(playback, *, interval=1, budget=5, sleep, clock)`，只调用 `PlaybackService.maintain_execution(read_timeout=...)` 和 UNKNOWN 时的只读 `observe(read_timeout=...)` facade。每轮完成后再 sleep；无重叠；异常或 UNKNOWN 按 1/2/4/8/16/30/30 秒退避，成功重置为 interval。maintenance 与只读复核共享整轮预算；同一 asyncio task 的 timeout 不另开事务 owner，不在 sleep 中持 DB 锁。
- `PlaybackService.maintain_execution` 仅新增可选预算参数及覆盖原事务调用/UNKNOWN materialization 的 timeout。未改变 S6/S7 规划、控制、绑定或 receipt 语义。提交前取消使用原 S4 outer rollback/逐命令前缀；提交后取消或超时保留已提交事实与 receipt。
- `main.lifespan` 支持明确注入 `app.state.player` 本地 Port；仅 `recovery_enabled` 为 true 且存在注入 capabilities 时启用，缺 capabilities/default 不启用，也不运行 probe。明确启用但缺 runner 依赖的已验证读取/add/delete/move 能力时启动失败；启用路径使用 `VerifiedPlayerPort`。进程装配 owner 在首个 await 前取得，第二个已启用 lifespan 启动失败；startup failure/关闭均释放。runner 另阻止同一 Service 的重复 run/第二个 runner。此为进程内排他，绝不宣称跨进程 MPD 协调能力；目标自动启用仍须 S11/S12。
- 关闭先取消并 await runner，再关闭/await 既有 observer，最后关闭 coordinator；没有 Stop，没有遗留 asyncio task。observer 生产代码和 GET/WS/snapshot 控制边界未修改。

新增测试仅 `test_d6_runner.py`；另只迁移 S9 计划明确指定的 `test_realtime_observer_lifecycle.py` 采样 fixture/对应表示断言。文档仅追加本 acceptance。既有 S2–S8 working-tree diff 保留，不能把全体未提交变更当作 S9 增量；S10 joint/support 文件未创建。

### RED → GREEN、生命周期回归迁移与审阅

1. 规定两个 runner selector 全参数首次有效执行因缺独立 runner **5 RED → 5 GREEN**。无人浏览页面也提交5个 AutoPlay occurrence；FakeClock/barrier 确认最大并发 tick 为1、重复 owner 拒绝、Stop 排队串行且下一 tick 零控制/零重播，observation 零控制。
2. 生命周期注入/默认禁用/无 capabilities/能力不足/明确启用/第二 owner/startup failure/立即关闭 **7 RED → 7 GREEN**；RED 为已有装配忽略注入本地 Port。使用 forbidden Adapter 构造证明本地测试不接触 live MPD；关闭后下一 lifespan 能取得 owner。
3. UNKNOWN 只读复核及剩余预算 **1 RED → 1 GREEN**，FakeClock maintenance 消耗2秒后 observation 只收到3秒。失败/UNKNOWN 混合验证完整退避序列，成功恢复1秒。
4. 提交前已发送但未 ACK 的 add 取消后业务 rollback，sent 未知前缀不猜测/不重发；ACK、confirmed、Queue 暂存后关闭的三个补充 proof 首次 **GREEN**，retry 仅完成受归属的后缀，共5次 add，零重复 occurrence。提交后 publisher 阻塞期间关闭、以及提交后整轮预算超时均保留 Queue +1、History/session、REPLAYED receipt，后续 maintenance 零控制。预算阻塞采样会取消并回滚，关闭无 Stop、无 pending tasks。
5. 规定 lifecycle 回归初次 **2 failed / 4 passed**：两项旧测试仍 monkeypatch 已不被 observation 调用的 `status()`。按当前 S2/S8 接口仅把故障/时钟 hook 改到 `read_execution_sample()`，read-command allowlist 仅增加该只读命令；未修改 observer，也未删除/跳过/放宽超时、取消、最大并发和全部业务/Library/Playlist/terminal 保持断言。有效断线后旧“progress fresh”预期另暴露新合同冲突：F §8.9.2/A §12.3.1 要求只恢复 actual facts，不能由读恢复 occurrence 绑定。该断言精确迁移为 `actual_freshness == 'fresh'`、旧 progress `freshness == 'unknown'`、`bound_queue_item_id is None`、`reconciliation_required is True`。精确 selector **GREEN**，随后整文件 **6 passed**。另一个原来 vacuous GREEN 的共享预算 clock hook 一并机械迁移并重跑。
6. 新测试编写时把 async scenario 内的同步 `server_snapshot` helper 换为等价 await helper，避免 nested asyncio.run fixture 错误；没有以该错误冒充 feature RED。
7. 独立只读审阅覆盖 runner/lifespan/Service budget 与上述 lifecycle 迁移，报告 **Critical0 / Important0 / Minor0**；独立运行当时 runner16及规定回归37均通过。审阅后增加提交后 budget-timeout proof，首次 GREEN；最终 runner17通过。审阅不替代作者实际测试和 diff 检查，不重复派发审阅。

### 最终 fresh 验证

以下均从 repository root 使用 `.venv/bin/python`，exit0；仅既有 Starlette/httpx deprecation warning，无环境失败：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_runner.py::test_single_runner_refills_without_clients_and_never_restarts_stop
# 1 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_runner.py::test_runner_budget_backoff_and_shutdown_preserve_commit
# 5 passed（原4参数 + 提交后预算超时）
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_runner.py
# 17 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_observer_lifecycle.py
# 6 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_output.py
# 9 passed
.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py
# R-TX-D6: 19 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# R-ARCH-D6: 3 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_execution.py server/tests/invariants/test_d6_autoplay.py server/tests/invariants/test_d6_current.py server/tests/invariants/test_d6_state.py server/tests/api/test_d6_state.py
# 178 passed（预算变更后的事务/current/refill/表示直接回归）
.venv/bin/python -m ruff check server/app/main.py server/app/services/playback_service.py server/app/services/playback_recovery_runner.py server/tests/invariants/test_d6_runner.py server/tests/invariants/test_realtime_observer_lifecycle.py
# All checks passed
git diff --check
# exit 0
```

已检查本次起始源码副本对照的 main/Service 增量、全部新增 runner/test、lifecycle 实际 diff、working-tree stat/status。scoped Ruff 仅修正 main 新 import 排序。无其它本次新增生产/测试变更、临时debug/generated、数据库、依赖、环境文件变化；没有 commit/push/PR/live MPD/Docker/外部服务。

**implementation completed / targeted automated tests completed / local environment validation completed / S9 local acceptance satisfied。** 此次未执行 repository-wide regression；S8 已记录的全仓旧 fixture/其它失败不由 S9 越界修复，不能宣称全仓 GREEN。S10 本地 stock joint、S11 目标运行时及 S12 final gate 未执行；无目标自动启用授权。服务/MPD restart 后业务绑定仍需明确用户控制接管，未知停止不重启，遗漏 History/原因/实际 ended_at 不补造。D6 / Batch13 / Task6 final 保持 **BLOCKED**。

## 2026-10-08 S10 — stock Adapter 联合 proof

**仅执行 S10；本地联合及规定回归 PASSED。S11 / S12 NOT RUN；D6 / Batch13 / Task6 final 仍 BLOCKED。**

### 前置、范围与真实联合装配

读取 active corrective plan P、唯一 acceptance E、F §8.9 与 A §12.3.1，核对实际源码/Git、branch `feature/task-6-realtime-state`、HEAD `31be1c4`。保留 checkout 既有 S2–S9 未提交实现；不创建遗漏这些前置实现的新 checkout。原 `.venv` fresh 环境：Python 3.14.4、pytest 9.1.1、Ruff 0.16.9。执行前 S2 sample、S3 binding、S4 execution、S5 history、S6 current、S7 autoplay、S8 两份 state、S9 runner 全部 focused 文件合计 **244 passed**；实现与 proof 的前置由当前源码及本次运行确认，未将文档 checklist 或历史 GREEN 当作 fresh evidence。

本次新增 `server/tests/invariants/test_d6_stock_joint.py` 与专用 `server/tests/support/d6_stock.py`，扩展既有 `server/tests/integration/support/stateful_fake_mpd.py`，仅更新 E；没有修改 production、计划 P、其它测试、依赖、schema 或 `.venv`。Shared TCP fake 新增真实协议-shaped status 的 playlist version/length/partition/single/consume/error、逐命令日志、ACK/EOF/屏障/迟到 wire facts、seek 和 outputs 响应。没有 natural/completed/reason 能力。

实际链路为本地 TCP → **MPDAdapter → VerifiedPlayerPort → PlaybackService / QueueManager / HistoryService / AutoPlay → tmp SQLite → RealtimeCoordinator / StateService → 真实 FastAPI HTTP 与 WebSocket ASGI 路由**。HTTP 使用 ASGITransport；WebSocket harness 只承载 ASGI messages，不替换 route、encoder 或 RealtimeConnections。未 monkeypatch Adapter/Port/Service 的样本或业务实现，没有 TestCompletionValidator。capabilities 为明确注入的本地协议事实，不是目标运行时能力验收；Output 使用非空 cached observed/request fixture，并通过真实 Adapter 读取 MPD outputs 进行保持核验，不声称物理 DAC 验证。

### 场景、事务与只读证据

- 规定 current selector 的 **9 参数**覆盖 A→B、A→C、同 URI 不同 occurrence、seek endpoint/remaining-segment 后的后来目标、error、外部 Next/playid/seekid。每次精确 MPD ID 接纳，Queue revision 只 +1；仅旧 current Played，未观察 B 和其它 pending 保持 ID/source/context 与相对顺序并同步到 current 后；已有 Played 不丢失，永久 History 保持非空历史基线，active 清空但 session 保留；不 play 目标、不制造 natural event 或起止时间。
- `seek-end/seek-remainder` 先在 A seek 180/20 并确认 A identity/elapsed 与业务保持，再输入后来 B 的协议事实。后续 `next` 只是本地 later-current 输入，不证明自然原因或真实时间流逝。`seekid` 直接从 A 指向已绑定 B，没有预先 playid；实际 elapsed=20。目标 MPD 的 seek 行为仍须 S11。
- A→B 显式 proof 完成后断开所有客户端，由独立 runner 在**无 HTTP/WS 客户端**时提交 B→C；新客户端获得 C 完整状态。关闭 runner 不 Stop、不 play 目标。
- 规定 failure selector 原 **10 参数**全部执行，额外 `torn-sample` 共 **11 参数**：lost add response、partial-add、delete/move ACK failure 的已归属后缀 retry、service restart、MPD restart、unknown stop、foreign、Queue writer 真实 barrier、迟到样本。add 的 EOF 或未知前缀保留 MPD 副作用，业务 rollback、无成功 receipt、不按 URI 猜 ID、不重发；delete/move retry 不重复成功前缀，最终只有一次业务 revision。
- MPD restart 模拟关闭连接后 URI 队列恢复、playlist version 归零、ID 分配器重置并复用 ID；新 connection epoch 与旧不同，旧绑定失效，业务 current A 保持。它只证明给定重启后的协议事实，不证明目标 daemon 的持久化配置或队列恢复能力。service restart 更换 realtime epoch，持久业务保持，runtime active/session 不虚构。
- 所有 failure/restart 场景经成功采样后正向断言 `actual_freshness == fresh`、actual entry/URI/state；foreign 显示 `outside.flac`，旧业务 current/Queue 仍 A，binding 不复活。unknown stop 保留 AutoPlay 意图且实际 stopped，标签 `UNCONFIRMED_STOP`，零自动启动。
- `late-sample` 在合法 writer 已提交 D 后，通过 TCP 提供之前 C 的完整一致旧 wire facts；拒绝该样本，保留新的 D 业务基线、零控制/事件。`torn-sample` 在两次有界 sample attempt 的 playlistinfo 后由独立 TCP writer 改版本，实际 Adapter typed rejection；不以 fixture exception 代替一致性失败。
- 补充 **4 参数**联合 proof：正常 refill、outer rollback、提交前 CancelledError、提交后 publisher failure。受控4候选全部以固定 AUTOPLAY IDs/source/context 提交，revision +1、current/History/session保持；outer 内成功 receipt/sequence/通知均未可见，rollback 恢复全部业务/runtime/binding，retry 不重复4条 add。提交后 publisher exception 不撤提交和 REPLAYED receipt；真实已连接 WebSocket 只在提交后收到单调 invalidate。
- observation、domain snapshot、GET、WS 首帧均保持完整业务快照与全部独立 authority；`reads_control_count == 0`。HTTP/WS 除 captured_at 外全字段相等，protocol_version=1。旧 terminal、Library 含相关表、Playlist/Favorites、Output observed/request/volume 与 Adapter MPD outputs 前后保持；没有由读修复 Queue/History/绑定。

### 失败分类、裁定与独立审阅

S10 是 proof 新增，**有效场景首次 GREEN 不伪造 RED→GREEN**。未发现 S2–S9 production 缺陷，因此没有越界生产修补，也没有虚报 owner RED。

测试建立期间初次9失败来自新 outputs fixture 缺必需 plugin；补齐 `plugin: alsa` 后消除，属于 fixture failure。后续 error 参数原断言 APPLIED 错误：F8.9.5/S7 已规定 error 暂停维护，S6 合法 current 已接纳仍可提交；纠正为 UNKNOWN/SYNC_FAILED，同时保留 current/Queue +1/History严格断言，精确 selector GREEN。补强 seek 时误用 `PlayerStatus.elapsed` 导致3个 AttributeError，改为既有 `elapsed_seconds` 后同3 selectors **3 passed**；这些测试错误均不算 production RED。

**Ruling：error 下 current 已接纳而维护 UNKNOWN/SYNC_FAILED，以 F8.9.5 及既有 S7 diagnostic proof 为准；不将 P S10 的 current literal 误扩展成“有 error 仍保证完整维护成功”。** 成本/限制是不能把该行算作 error 下连续执行保证；目标 error 行为与可用性仍待 S11，current、History 和原因合同没有收窄。

Superpowers 独立只读审阅实际运行当时联合文件 **24 passed**，报告 Critical0 / Important2 / Minor1。两项 Important 是 proof 缺口：seek 被前置 playid 掩盖；restart/foreign 只有失效负向而缺 actual 恢复正向。均在测试内补齐上述协议输入/精确断言，没有 production 修改。minor“MPD restart 仅为 disconnect”按本次明确 restart proof 义务升为必须补齐的覆盖项，扩展 reset-version/ID-reuse 事实后解决。最终上述24项与全部规定回归重新执行 GREEN；新增/加强 proof 仍记 GREEN 验证既有实现，不人为破坏 production 制造 RED。无 deferred minor，无重新派发审阅。

### 最终 fresh 命令与结果

以下从 repository root 使用原 `.venv/bin/python`，全部 exit0；除 player/integration 外，pytest 仅既有同一个 Starlette/httpx deprecation warning，无环境失败：

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_stock_joint.py::test_stock_adapter_current_queue_history_and_snapshot_joint
# 9 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_stock_joint.py::test_stock_joint_failure_restart_and_read_only_boundaries
# 11 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_stock_joint.py
# 24 passed = 9 + 11 + 4
.venv/bin/python -m pytest -q server/tests/player
# 40 passed
.venv/bin/python -m pytest -q server/tests/player/test_execution_sample.py server/tests/invariants/test_d6_binding.py server/tests/invariants/test_d6_execution.py server/tests/invariants/test_d6_history.py server/tests/invariants/test_d6_current.py server/tests/invariants/test_d6_autoplay.py server/tests/invariants/test_d6_state.py server/tests/api/test_d6_state.py server/tests/invariants/test_d6_runner.py server/tests/invariants/test_d6_stock_joint.py
# 268 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py
# 98 passed（仅隔离旧 consumer 回归，不替代 stock proof）
.venv/bin/python -m pytest -q server/tests/services/test_queue_manager.py server/tests/services/test_autoplay.py server/tests/services/test_playback_service.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py
# R-PB-D6: 135 passed
.venv/bin/python -m pytest -q server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/invariants/test_realtime_history.py
# R-H-D6: 13 passed
.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py
# R-TX-D6: 19 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_transitions.py server/tests/invariants/test_output_serialization.py
# R-OBS-D6: 141 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# R-ARCH-D6: 3 passed
.venv/bin/python -m pytest -q server/tests/integration/test_task4_with_mpd_adapter.py server/tests/integration/test_task2_task3_task4_e2e.py
# 9 passed（shared TCP fake 的全部既有 consumer 直接回归）
.venv/bin/python -m ruff check server/tests/invariants/test_d6_stock_joint.py server/tests/support/d6_stock.py server/tests/integration/support/stateful_fake_mpd.py
# All checks passed
git diff --check
# exit0
```

已检查新增 joint/support 内容、shared fake 实际 diff、working-tree stat/status 与 `git diff --check`。S2–S9 原有变更保留；本次只有上述3份测试/support及 E 增量，无临时 debug/generated/env/database/dependency 文件新增修改，无 commit/push/PR/merge/live MPD/probe/Docker/外部服务。

**S10 proof implementation completed / prescribed automated tests completed / local environment validation completed / S10 local acceptance satisfied。** S11 目标原版 MPD 运行时模式/执行组合 NOT RUN，S12 最终门禁 NOT RUN；本次未跑 repository-wide suite，也没有复验/关闭 S8 已记录的旧全仓 fixture/其它失败。不宣称全仓 GREEN、目标自动启用或 D6/Batch13/Task6 final通过。服务/MPD重启后业务绑定仍须明确控制接管，A→C 未观察 B 保留可再次播放，未知停止不自动重启；原因、实际 ended_at、遗漏 History 不认证。

## 2026-10-08 S11 — 目标原版 MPD 运行时能力验收（NOT VERIFIED）

**本次只进入 S11；S10 前置 fresh PASSED。目标 TCP 连接在 greeting 前失败，因此没有目标原始响应，所有真实 MPD 场景均为 NOT VERIFIED。D6 / Batch13 / Task6 final 保持 BLOCKED，未进入 S12。**

### S10 前置 fresh 确认

从 repository root 使用既有 `.venv/bin/python`，按 S10 规定顺序重新执行联合文件、player、新旧 D6 及直接回归，全部 exit0：joint **24 passed**、player **40 passed**、新 D6 集合 **268 passed**、旧 consumer **98 passed**、R-PB **135 passed**、R-H **13 passed**、R-TX **19 passed**、R-OBS **141 passed**、R-ARCH **3 passed**、shared TCP integration **9 passed**。只有既有 Starlette/httpx deprecation warning。该结果只确认 S10 本地协议模拟 gate，不代替 S11。

### 目标连接原始事实与停止裁定

执行时间 `2026-10-08T16:43:21+08:00` 前后，本次只读探针拟连接 C 中的权威目标 `192.168.3.94:6600`，连接成功后原计划依次读取 greeting、`status`、`playlistinfo`、`outputs`，再审查备份和恢复是否足够安全。实际在 Python `socket.create_connection(("192.168.3.94", 6600), timeout=5)` 阶段即失败：

```text
OSError: [Errno 101] Network is unreachable
```

失败发生在 TCP 建连和 MPD greeting 之前，因此本次：

- 未向目标发送任何 MPD application command；没有本次 `status`、`playlistinfo`、`outputs`、版本或 build 原始响应；
- 未取得可核对的原执行队列、模式、状态、输出备份，因而按 P S11 停止条件拒绝发送任何队列、播放、seek、Stop、断线或重启控制；
- 未启动生产 lifespan、observer 或 recovery runner，未打开/修改 `music-server.db`，没有业务 snapshot 可作为目标运行时证据；
- 未修改目标媒体、曲库、schema、输出或物理播放状态；没有发生需要恢复的目标 mutation；
- 未尝试 Docker、替代 IP、旧 probe、S10 fake 或旧九项 `verified_operations` 来绕过目标环境不可达。

只读网络核查的原始事实：执行环境接口为 `eth0 172.28.185.65/16`（另有 docker0），默认路由 `via 172.28.0.1 dev eth0`；`ip route get 192.168.3.94` 解析为经该默认路由，但 socket 仍返回上述 network-unreachable。未修改路由、VPN、防火墙或机器网络配置。

### S11 场景逐项状态

| S11 义务 | 本次原始事实 | 状态 |
|---|---|---|
| 当前 greeting/version/build 与命令/错误边界 | greeting 前 `Errno 101`；没有 MPD 响应 | **NOT VERIFIED** |
| 原队列、模式、status、outputs 与业务 snapshot 备份 | 无法连接，未取得；因此未进入 mutation | **NOT VERIFIED** |
| A/B/C 受控队列；重复 URI 不同 ID；`songid == entry.Id` 与 position/version | 未创建队列、未读 status/playlistinfo | **NOT VERIFIED** |
| 正常 A→B 只确认目标、不判断离开原因 | 未执行 | **NOT VERIFIED** |
| 预排 B 可推进，且服务不发送 `playid B` | 未执行；没有启动服务/runner | **NOT VERIFIED** |
| A→C 时 B 保留且不补 History | 未执行；没有目标业务 snapshot | **NOT VERIFIED** |
| 已离开 entry 后 move/delete；目标 ID 保留、position 改变 | 未执行 | **NOT VERIFIED** |
| Stop 后 runner 不重启 | 未执行 Stop，runner 未启动 | **NOT VERIFIED** |
| 断线与 MPD/service restart 后旧 binding 失效、actual 可恢复 | 未制造断线/重启 | **NOT VERIFIED** |
| 运行时 error/响应丢失边界与不盲重发 | 无安全隔离和可核对备份，未触发故障 | **NOT VERIFIED** |
| 恢复原队列/模式/状态/输出并核对 | 没有 mutation；但初始事实也未取得，不能宣称目标状态已核对 | **NOT VERIFIED** |

本次没有从状态跳变推断自然完成、没有记录自然原因或补 History。旧 2026-09-26 probe 与 2026-09-27 九项摘录仍只保留其历史范围，不升级为上述场景的本次证据。

### Gate 与修改范围

S11 target-runtime acceptance **NOT VERIFIED / BLOCKED**。关键能力全部未验证，故 D6-RECOVERY 能力子门禁不通过，D6 Relationship/Contract Matrix、Batch13 与 Task6 final 均继续 **BLOCKED**；S12 的前置不满足，本次未执行 S12。

本次只更新 E/C 和 ignored SDD 记录；没有修改 production、test、schema、依赖、`.venv`、数据库或运行配置，没有 commit/push/PR/merge。S11 只读辅助脚本保存在该 plan 的 git-ignored SDD workspace，不能当作产品或测试实现。

## 2026-10-08 S11 网络重试 — 目标 MPD 部分能力 VERIFIED，总门禁 BLOCKED

**更换网络后目标连接成功。可安全执行的 S11 场景均已用目标原版 MPD `0.23.5`、真实 TCP Adapter/VerifiedPort/Service 和临时 SQLite 逐项执行并恢复；仍有关键故障场景 NOT VERIFIED，因此 S11 不标 PASSED，D6 / Batch13 / Task6 final 继续 BLOCKED，未进入 S12。**

### 原始记录、目标与保护基线

本次 first read-only 于 `2026-10-08T22:10:04+08:00` 成功取得：

```text
greeting: OK MPD 0.23.5
status: volume=100 repeat=0 random=0 single=0 consume=1
        partition=default playlist=49 playlistlength=1 state=stop
playlistinfo: file="一样的月光 - 徐佳莹.flac" Pos=0 Id=18
outputs: 0 USB DAC/alsa/enabled; 1 HTTP Stream/httpd/disabled
```

`currentsong` 为空，符合 stopped 原始状态。目标 build/package hash 未由 MPD 协议提供，本次也未取得 NAS package build，明确为 **NOT VERIFIED**，不从 greeting 推断。

最终完整 live evidence 位于机器本地 git-ignored 文件：

```text
.superpowers/sdd/2026-10-04-task-4-d6-recovery-corrective-plan/s11-live-result.json
SHA-256: 1a3cd797102ae1d350119075f2ed02a6b30bca44fde903f5ede5b28fc678fb4f
UTC: 2026-10-08T14:14:23.583895+00:00 .. 2026-10-08T14:14:26.333885+00:00
```

使用临时目录中的 SQLite 数据库，只写入 A/B/C 受控业务切面；临时目录随执行结束删除。未打开或修改工作区 `music-server.db`。A/B 为同一 Library song 的两个 Queue occurrence，URI 均为 `一样的月光 - 徐佳莹.flac`；C 为 `小情歌 - 苏打绿.flac`。这避免伪造相同 URI 的两个 Library song，同时真实覆盖 duplicate occurrence。

两次准备阶段问题均如实保留，不能算产品失败或正式场景 PASS：第一次临时库错误地为同 URI 指定两个 song_id，被 Library identity 约束拒绝，发生在 Service/MPD 播放命令前；第二次 A→B 已执行，但 evidence serializer 错把 dataclass 当作 Pydantic model。两次 `finally` 都恢复队列内容/模式/音量/stopped/outputs。MPD entry ID 与 playlist version 在 clear/add 后不可恢复，分别经历 `18→21→28`；最终完整执行从恢复后的 `Id=48/version=122` 开始，结束恢复为 `Id=71/version=186`。这些变化不被描述为原 ID/version 恢复。

### 逐场景目标原始事实

| S11 义务 | 本次目标事实 | 状态 |
|---|---|---|
| greeting/version/build | 每条 raw 连接 greeting=`OK MPD 0.23.5`；build/package hash 未取得 | version **VERIFIED**；build **NOT VERIFIED** |
| 原队列、模式、status、outputs 与恢复保护 | 原始 queue/modes/state/output 已备份；最终 queue URI/order、volume、repeat/random/single/consume、stopped 与 outputs 原始响应核对一致 | **VERIFIED**，但原 MPD ID/version/物理瞬间不承诺恢复 |
| A/B/C 重复 URI、ID、position/version | 正式 normal binding：A=`Id51/Pos0`、B=`Id52/Pos1`，相同 URI；C=`Id53/Pos2`；status playlist version=`133` | **VERIFIED** |
| 正常 A→B 只确认目标、不判断原因 | 外部 raw `next` 后 status 从 `songid51/song0` 到 `songid52/song1`，version 保持133；Service outcome=APPLIED，永久 History `0→0` | **VERIFIED**；`next` 只提供后来目标事实，不称 natural |
| 外部推进后 Service 不发送 `playid B` | A/B/C 已预同步；raw `next` 推进后的 Service 调用只有 `queue_delete(51)` 与 AutoPlay `queue_add(...)`，没有 `queue_play/play/next/seek` | **VERIFIED**；此轮不证明无人控制推进，见后续补验 |
| A→C 时 B 保留且不补 History | A/B/C ID=`55/56/57`；raw `playid 57` 后 C current，A Played，B occurrence 保留 `position=1/MANUAL`；History `0→0` | **VERIFIED**；不判断 B 是否曾播放 |
| 已离开 entry 后 move/delete | B=`Id60` 从 `Pos1` 变 `Pos0` 且 ID 保留；A=`Id59` 移到 Pos2 后删除；C=`Id61` 保留 | **VERIFIED** |
| Stop 后不重启 | raw Stop 后 status stopped/selected `Id62/Pos0`；真实 runner 一轮 player control calls=`[]`；Queue/History 不变；snapshot=`UNCONFIRMED_STOP` | **VERIFIED** |
| TCP 断线旧绑定失效并恢复 actual | Adapter close/reconnect 后 connection epoch `621d...→f7da...`；outcome UNKNOWN，binding=None，Queue/History 不变，actual fresh/UNBOUND | **VERIFIED** |
| Service 重启旧绑定失效并恢复 actual | 同一临时 DB/目标 player 重建 Service；player controls=`[]`，binding=None，Queue/History 保持，actual `Id68` fresh/UNBOUND | **VERIFIED** |
| MPD daemon 重启 | 无获授权且安全的 daemon/package 控制路径，没有伪装成 TCP reconnect | **NOT VERIFIED** |
| MPD ACK error 边界 | `playid 2147483647` 返回 `ACK [50@0] {playid} No such song`；前后 playlistinfo 一致 | **VERIFIED** |
| 响应丢失与不盲重发 | 目标路径没有隔离 proxy/fault injector，本次未人为切断已发送命令响应 | **NOT VERIFIED** |
| decoder/output error | 不对真实媒体/USB DAC 注入故障；没有从空 error 推断可用 | **NOT VERIFIED** |

正常 A→B 中，业务 Queue revision 由2到4，因为同一 `maintain_execution()` 在接纳 B 后又按既有 AutoPlay 低水位追加一个 occurrence；本次不把它误写成纯接纳只 +1。关键约束仍由原始证据满足：B 精确 ID 接纳、旧 A Played、无永久 History、无 `playid B`。A→C 同样保留 B 的 occurrence ID/source/context，并按实际计划追加 AutoPlay occurrence；没有声称遗漏 B 的播放原因或 History。

snapshot 中的实际身份只由真实 sample/observe 提供。Stop 是 fresh `UNCONFIRMED_STOP`，TCP/Service restart 后是 fresh `UNBOUND`；没有因 actual fresh 自动重建业务 binding。所有临时 Service/runner 都在场景结束关闭，没有生产 lifespan 或持久 runner 留存。

### 恢复与最终 gate

最终恢复原始 queue 内容与顺序（单曲 `一样的月光 - 徐佳莹.flac` Pos0）、`volume=100 repeat=0 random=0 single=0 consume=1 partition=default state=stop`；outputs 完整 raw 响应与最初相等。最终重新分配 `Id=71`、playlist version=`186`，不能恢复或声称恢复原 `Id=18/version=49`。原始状态本来为 stopped，因此没有声称恢复某一物理播放瞬间；未进行 DAC 听觉验收。

S11 目标运行时能力为 **PARTIALLY VERIFIED / BLOCKED**。MPD daemon restart、响应丢失、不盲重发的目标故障路径、decoder/物理输出 error 及 build 标识仍是关键 `NOT VERIFIED` 项；依用户要求，任何关键能力未验证即保持 BLOCKED。S12 前置不满足，本次未执行 S12；D6 Relationship/Contract Matrix、Batch13、Task6 final 均继续 **BLOCKED**。

本次没有修改 production、test、schema、依赖、`.venv`、工作区数据库或运行配置。只更新 E/C 与 ignored SDD evidence/harness；没有 commit/push/PR/merge。

## 2026-10-08 S11 补充实测 — 不改合同，仍 BLOCKED

用户授权按审计建议继续执行。本轮只补 S11；S10 fresh 前置结果不变，未执行 S12。此前 raw `next` 只证明后来目标可接纳，并不证明无人控制推进；旧记录未 observe 的成功 snapshot 也不当作 CONFIRMED actual 证据。本轮重新执行并记录实际 sample、接纳和 observe 后 snapshot。目标 greeting 为 `OK MPD 0.23.5`，不据此声称 binary 为未修改原版；build 仍待识别。

### 原始证据与执行方法

在仓库根目录使用 `.venv/bin/python`，临时 SQLite、现有真实 MPDAdapter/VerifiedPort/PlaybackService。仅测试 Adapter 经 localhost 透明 TCP proxy 连接真实 NAS；proxy 不生成协议样本，保存真实 upstream 响应及 delivered 标志。命令与结果：

```text
PYTHONPATH=. .venv/bin/python .superpowers/sdd/2026-10-04-task-4-d6-recovery-corrective-plan/s11_supplement.py
# exit0; restore_verified=true; failure=null; restore_failure=null
# UTC 2026-10-08T14:23:22.035909+00:00 .. 14:27:24.293590+00:00
# s11-supplement-20261008T142322Z.json
# SHA256 4fa32fce43a12256204b3c35477c71ba3eae8fc62870a8b131fc312fc08f0af2
PYTHONPATH=. .venv/bin/python .superpowers/sdd/2026-10-04-task-4-d6-recovery-corrective-plan/s11_seek_supplement.py
# exit0; restore_verified=true; failure=null; restore_failure=null
# UTC 2026-10-08T14:27:46.258267+00:00 .. 14:27:50.491931+00:00
# s11-seek-20261008T142746Z.json
# SHA256 5114cb64e3c938344a92b9ecf21a5a396760f8a6679a31a15f2659a49b926043
```

两份完整 JSON 均在本 plan 的 git-ignored `.superpowers/sdd/2026-10-04-task-4-d6-recovery-corrective-plan/`，包含 raw_command_log/proxy_wire_log、业务前后 snapshot、status/playlistinfo/outputs 与恢复记录；不是旧 probe。时间对应本地 22:23–22:27。`unattended_A_B.waiting_wire_log` 保存至接纳之后，包含末尾 `deleteid 74`；不要把整个该字段误称为等待期零控制。等待期结束前只含 status/playlistinfo，接纳后的控制另见 service_controls。

### 逐项事实及证明边界

| 场景 | 新原始事实 | 裁定 |
|---|---|---|
| 完整无人控制 A→B | A/B/C=`74/75/76`，A/B 相同 URI；duration=240.386。准备后49个 sample，A=`Id74/Pos0/elapsed0.842` 至 B=`Id75/Pos1/elapsed1.479`，version 恒197；等待期间仅读取，没有 next/playid/seek | 预同步 B 在无后续控制时成为 current **VERIFIED**；不认证离开 A 的自然原因 |
| 纯接纳及成功 actual | `reconcile_external_status`=APPLIED；只 `queue_delete(74)`，无 playid B/补曲；Queue revision2→3、A Played、B 业务 Pos0、History0→0；observe 后 actual=`Id75/Pos0`，fresh/CONFIRMED/matches_current=true，绑定 B occurrence | **VERIFIED**；与此前 maintain/refill revision2→4 区分 |
| seek 剩余段 | `seekcur 237.386`；A/B/C=`84/85/86`。之后6个只读 sample，从 A elapsed237.841 到 B elapsed0.455/Pos1，version 恒221 | 后来 B 身份 **VERIFIED**；seek 不提供 natural reason |
| seek 终点 | `seekcur 240.386`；A/B/C=`87/88/89`。2个只读 sample 从 A elapsed240.386 到 B elapsed1.343/Pos1，version 恒230 | 后来 B 身份 **VERIFIED**；不把 duration 相等当作原因证据 |
| 两个 seek 的接纳/actual | 均 APPLIED，Queue revision2→3、History0→0；observe 后分别 actual=`Id85/Pos0`、`Id88/Pos0`，fresh/CONFIRMED/matches_current=true，绑定对应 B | **VERIFIED**；没有在接纳后重发 playid B |
| 真实 addid 成功后丢响应 | NAS 已执行 `deleteid 77`，随后 `addid "一样的月光 - 徐佳莹.flac"` 真实响应 `Id: 80`/`OK`；proxy 仅丢弃这次下行响应并关闭测试连接。NAS 队列确有 Id80；Service 报 `MPD communication failed: MPD closed the connection` | 已发送且外部成功、客户端未获响应的边界 **VERIFIED**；不是伪造 ACK/Mock |
| 不盲重发/业务 rollback | 丢响应后 Queue/Playback/History/active/session 与业务基线相同；Queue revision仍2、History仍0；随后 maintain 返回 UNKNOWN/SYNC_FAILED/reconciliation_required=true，proxy 未收到新控制命令（该重试也未产生新 wire 命令），receipt_count=2 | 此次 addid 故障路径 **VERIFIED**；不声称 MPD 副作用已回滚，也不外推所有命令/重启组合 |

本轮每个 harness 均先检查原状态 stopped，备份 queue/modes/volume/outputs，结束执行 finally 恢复核对。首轮基线 `Id71/version186`，恢复 `Id81/version210`；seek 轮从该恢复状态开始，最终 `Id90/version233`。最终单曲 URI/order、volume100、repeat/random/single0、consume1、partition default、stopped 及 outputs raw 响应一致；USB DAC enabled、HTTP Stream disabled。原 ID/version不可恢复，未声称恢复物理播放瞬间/听觉表现。媒体/曲库/schema/输出未改动；proxy、临时 Service 与临时 DB 已关闭，不留生产 runner。

### 未验证项与下一步条件

- 用户已确认 DSM 套件名称 **mpd**；这不是 binary version/build/hash 的原始核验。已准备只读 `s11_nas_identify.sh`（本 plan ignored workspace），本机 `sh -n` 成功，但没有在 NAS 执行，因此 build **NOT VERIFIED**。
- 本机有 ssh，未配置 NAS SSH alias，尚无用户名/现有可用认证入口；未尝试猜用户名、扫描管理口、启用 SSH 或修改套件。真实 daemon restart **NOT VERIFIED**，不得用已验证 TCP reconnect/Service reconstruction 顶替。
- F §8.9.5 的 observed decoder/input/output error 下暂停自动控制、保留业务状态仍需真实安全故障条件；没有注入媒体/DAC 故障，也没有从 error=null 推断通过，记 **NOT VERIFIED**。S11 明确不包含 Task12 DAC 听觉/物理发布验收；这一区分不删除 D6 错误边界义务。
- 继续前需要 NAS 只读运行 binary 识别，以及可协调的维护窗口/套件控制入口。不能仅在已恢复的空闲状态重启套件并据此宣称“旧业务绑定失效”：须先有受控绑定与原状态保护，再观察 daemon 断开/启动和后续 actual，最后恢复核对。

结论：新增证据补齐 unattended/seek 和 addid 丢响应范围；build、真实 daemon restart、真实错误边界仍未验证，S11/D6/Batch13/Task6 final **BLOCKED**。未修改 production/test/schema，未提交或推送。

### NAS SSH 入口确认与主机身份阻塞（2026-10-08）

用户确认入口为 `root@192.168.3.94:22`。使用现有认证、`BatchMode=yes/StrictHostKeyChecking=yes/ConnectTimeout=8/ConnectionAttempts=1` 尝试只读连接，exit255：

```text
No ED25519 host key is known for 192.168.3.94 and you have requested strict checking.
Host key verification failed.
```

阻塞发生在远端命令执行之前，尚未验证 root 认证可用；没有执行 NAS build 检查或 daemon 操作，没有修改 known_hosts 或绕过主机身份检查。需通过可信渠道核对 NAS SSH host key 后再继续。build/daemon restart 仍 NOT VERIFIED，S11 保持 BLOCKED。

### NAS 用户侧 binary 识别 — 版本不一致（2026-10-08）

用户随后报告已 SSH 登录但需要密码，由用户在 NAS 执行只读检查并回传以下原始输出（非本机直接 SSH 核验）：

```text
PID=2823
/volume1/@appstore/mpd/bin/mpd
ff9df851bda831c368bead85aa30e2717f96d057180d405e5c7bfc74367f7ae6  /proc/2823/exe
Music Player Daemon 0.23.17 (699d8b3)
```

用户还回传 decoder/output/input/features 列表，包括 flac、alsa/httpd 和 tcp/un；未回传 package/version/arch 的 INFO 字段，不能填补套件 metadata。本机在 `2026-10-08T14:48:03.605319+00:00`（22:48:03 Asia/Shanghai）仅重新连接 `192.168.3.94:6600` 读取 greeting，仍为 `OK MPD 0.23.5`；未发送控制命令。

两个版本字符串不同，但目前没有 PID2823 与 6600 监听 socket 的映射。不能推断另一 daemon、代理或 greeting/binary 版本字符串为何不同，也不能认定 binary hash 证明“未修改原版”。此前队列/恢复等实测保留为该 TCP endpoint 的行为事实，其 **原版 MPD0.23.5 目标适用性 NOT VERIFIED**。需先只读确认 6600 监听 PID/进程；暂停 daemon 重启/故障注入，不升级、降级或改配置。S11 继续 BLOCKED。

### 监听映射已取得；协议版本与 daemon 版本区分（2026-10-08）

用户回传附件 `/home/Gold/.codex/attachments/446790a7-6cb5-4146-987b-9f9899b81caf/已粘贴的文本.txt` 包含以下原始字段：

```text
package="mpd"
version="0.23.17-3"
arch="apollolake avoton braswell broadwell broadwellnk broadwellnkv2 broadwellntbap bromolow cedarview denverton epyc7002 geminilake geminilakenk grantley kvmx64 purley r1000 r1000nk v1000 v1000nk"
tcp  0  0  0.0.0.0:6600  0.0.0.0:*  LISTEN  2823/mpd
```

结合此前 PID2823 的 exe/--version/hash，用户侧证据已建立当前 NAS 6600→PID2823→套件 binary0.23.17 的映射。官方 [MPD protocol overview](https://mpd.readthedocs.io/en/stable/protocol.html#protocol-overview) 明确 greeting 的 version 是协议版本，不是 daemon 实际版本；不能通过该连接获取实际 daemon 版本。因此 greeting0.23.5 与 binary0.23.17 并不构成版本异常。此前将 greeting 用作 daemon 版本核验的表述错误，本节予以校正，历史 raw 响应保留。

当前部署识别为 DSM package mpd0.23.17-3、daemon0.23.17(699d8b3)、协议greeting0.23.5；hash是标识而非未修改原版的证明。不能将此前 endpoint 实测升级为 daemon0.23.5 的通过证据，也不能仅凭当前映射证明此前时刻进程未变化。用户原要求是原版 MPD0.23.5；未经用户决定不改目标/Spec/Plan，不降级套件。真实daemon重启/错误边界仍未验证，S11保持BLOCKED。下一步需决定维持精确0.23.5验收目标，或正式调整为现有0.23.17部署目标；决定前不执行重启/故障注入。

### 用户决定：功能合同为门禁，不拘泥 daemon 精确版本（2026-10-08，当前有效）

用户明确：“不用过分纠结这个，版本号不是真正重要的。重要的是实现需要的功能，验收需要的功能”。据此本次目标是现有NAS部署对S11所需功能的真实能力，不再把daemon必须精确0.23.5/原版源码溯源当作独立阻塞项；仍如实区分daemon0.23.17、套件0.23.17-3和协议0.23.5，不把实际部署重命名为daemon0.23.5。此决定仅调整验收目标身份要求，不更改业务合同、功能断言、未知原因规则或任何production/test/schema。

现有endpoint实测逐项保留原始证明范围，不以版本兼容性推断任何未执行场景。当前功能缺口仍是真实daemon重启时绑定失效/停止控制/actual恢复，以及安全条件下真实error边界的暂停控制/状态保留；两项NOT VERIFIED，S11继续BLOCKED。不得因用户淡化版本要求而自动视为功能通过。下一步协调DSM套件mpd维护窗口：先备份并建立临时库受控绑定，再由用户停止套件，观察实际连接失败和业务保留；随后用户启动套件，观察新连接epoch/无旧绑定/fresh actual及零自动控制，最后恢复原状态。先建立观察再操作，不用空闲重启或TCP close代替。

SSH需要密码，密码留在用户终端；不索取密码、不配置免密或更改SSH认证。维护时需用户在场执行停止/启动；尚未启动这项测试或改变当前队列。错误注入无安全条件时继续标NOT VERIFIED，不损坏媒体、不切换输出或人为断开USB DAC。

## 2026-10-08 S11 真实 daemon 停止/启动补验 — 功能 VERIFIED，专项仍 BLOCKED

用户确认维护“就绪”，由用户在DSM套件中心停止/启动mpd；分别回报“已停止”“已启动”。程序先建立受控绑定，观察到transport失效和业务保留后才通知用户启动，不把Adapter.close或Service重建伪装为daemon重启。本机不执行SSH密码认证或套件管理命令，不更改SSH/套件配置。使用现有真实Adapter/VerifiedPort/Service和临时SQLite，无production runner留存。

```text
PYTHONPATH=. .venv/bin/python .superpowers/sdd/2026-10-04-task-4-d6-recovery-corrective-plan/s11_daemon_restart.py
# exit0; failure=null; restore_failure=null; restore_verified=true
# artifact: .superpowers/sdd/2026-10-04-task-4-d6-recovery-corrective-plan/s11-daemon-20261008T145937Z.json
# SHA256 b0fdbdee16e0a484ea3a1b436ac7e031e0b925f0fc11bae132dcb701da5cbc69
# UTC 2026-10-08T14:59:37 .. 15:01:24.115133+00:00 (Asia/Shanghai 22:59–23:01)
```

该机器本地ignored完整JSON保存baseline、raw_command_log、old/new sample与业务前后snapshot、down错误与恢复事实。`daemon_identity_after`字段仍说明未取得用户侧启动后新PID/binary识别；不伪造该项。但本次真实daemon停止/启动的功能验收有用户操作回报、端点关闭/拒绝连接、stats uptime重置及完整运行时样本共同支持，不仅是一次TCP重连。

| 义务 | 本次原始事实 | 状态/边界 |
|---|---|---|
| 原状态保护与绑定 | baseline stopped，原单曲Id90/Pos0/version233，volume100、repeat/random/single0、consume1。受控A/B同URI不同ID=93/94，C95，version244；业务snapshot fresh/CONFIRMED，revision2/History0 | 已备份并真实建立受控绑定 |
| daemon停机 | 首次错误 `MPD communication failed: MPD closed the connection`；maintain报 `MPD connection failed: [Errno 111] Connect call failed ('192.168.3.94', 6600)` | 实际端点失效，不由harness主动close注入 |
| 旧绑定与业务 | down_binding=None；Queue/Playback/History/active/session与before一致；actual旧样本stale、UNBOUND，reconciliation_required=true、PLAYER_UNAVAILABLE | **VERIFIED**；旧显示不冒充fresh，不清业务意图 |
| daemon重新上线 | stats uptime=1145895→0；连接epoch=`9ca3c1b47d36432abf1e481247d82f06`→`65a4837630564055b6c83eeb1b8d6c24`；playlist version244→2；A/B/C ID93/94/95→1/2/3 | **VERIFIED**；当前版本/build不从greeting推导，不承诺ID可跨重启使用 |
| actual恢复与控制边界 | new_sample实际playing，Id1/Pos0/elapsed55.185；maintain=UNKNOWN/reconciliation_required=true，new_binding=None；observe后actual fresh/UNBOUND、bound_queue_item_id=None，业务五域仍不变；post_restart_controls=[] | **VERIFIED**；不自动重建业务绑定，不把MPD重连后playing归因于Service控制或自然原因 |
| 恢复核对 | 最终单曲URI/order、volume100、repeat/random/single0、consume1、default partition、stopped及outputs完整raw响应与baseline一致；最终Id4/version4 | **VERIFIED**；不承诺恢复Id90/version233或物理瞬间 |

outputs全程USB DAC/alsa enabled、HTTP Stream/httpd disabled；没有enable/disable output或媒体/schema改动。临时Service关闭、临时库清理，维护harness已exit0，不再等待用户操作。本次只有恢复阶段按保护方案发送stop/clear/add/modes/setvol，不能把这些恢复命令混为重启观察阶段自动控制；post_restart_controls记录的是恢复前的Service控制。

**当前门禁**：真实daemon重启功能项已VERIFIED。decoder/input/output error下暂停控制/保留业务状态尚无安全真实故障样本，继续NOT VERIFIED，不以停机PLAYER_UNAVAILABLE或ACK50代替decoder/output错误。S11/D6/Batch13/Task6 final仍BLOCKED，S12未执行。精确daemon版本匹配已按用户决定不再单独阻塞；没有更改功能合同、production/test/schema、依赖、工作区数据库或输出配置，没有commit/push。

### 授权隔离故障验收 — 启动向导准备，尚未运行（2026-10-08）

用户没有现成失败曲目，随后明确授权同binary/独立临时目录、配置、端口和MPD进程的隔离故障验收。不改现有套件配置/曲库/DAC或production/test/schema；不制造真实媒体损坏。使用wizard技能为需要用户输入SSH密码的启动步骤制作向导，未由agent端到端执行。

本plan ignored workspace新增 `s11_fault_wizard.sh`（未修改wizard模板库）、`s11_fault_nas_setup.sh`、`s11_fault_nas_control.sh`。向导3阶段：用户在本机建立临时root SSH master与loopback端口转发（密码仅ssh从用户终端读取，agent后续只复用连接执行本次夹具操作）→NAS只读检查后创建全新 `/tmp/mpd-s11-fault.XXXXXX`→保存公开连接/夹具位置并交给验收观察。临时MPD使用 `/volume1/@appstore/mpd/bin/mpd`，独立16608端口，NAS仅绑定127.0.0.1，降权nobody，20分钟进程运行上限，只有null和初始disabled的pipe输出，无ALSA/真实设备。生成180秒静音WAV夹具和独立database/log/config，没有复制或改写原歌曲。

待执行场景分别是仅临时夹具中的无效WAV、已扫描文件被移走、pipe sink提前退出；对应真实输入/解码/输出错误事实必须由实际raw响应判定，不承诺每种注入都一定产生status.error，不把“脚本执行成功”当能力PASS。参考官方 [v0.23.17示例配置](https://raw.githubusercontent.com/MusicPlayerDaemon/MPD/v0.23.17/doc/mpdconf.example) 及 [pipe output实现](https://raw.githubusercontent.com/MusicPlayerDaemon/MPD/v0.23.17/src/output/plugins/PipeOutputPlugin.cxx)，pipe错误不外推真实USB DAC故障。采样后核验Service控制、业务五域和snapshot，再保存日志、校验PID/exe/config归属后停止夹具，核对生产端点未被修改；临时文件清理仅限本次明确目录，不作广泛递归删除。

本机 `bash -n wizard`、两份 `sh -n` exit0，模板库一致性检查通过，已chmod+x；shellcheck本机未安装，明确NOT RUN且未安装依赖。162份production/test源码保存hash核对exit0。**尚未在NAS创建/启动夹具，错误能力仍NOT VERIFIED；S11 BLOCKED，S12未执行。** 启动或依赖检查失败应停下报告，不重跑覆盖、不安装/升级、不切换生产输出。

### 向导SSH密码提示失败及最小修正（2026-10-08）

用户执行向导在stage1认证阶段失败，原始错误包括 `ssh_askpass: exec(/usr/bin/ksshaskpass): No such file or directory`，最后 `Permission denied (publickey,password)`，没有进入stage2。只读本机环境确认 `SSH_ASKPASS_REQUIRE=prefer`、`SSH_ASKPASS=/usr/bin/ksshaskpass`；公开state文件未生成，本次 `/tmp/mpd-s11-ssh.fGnAvN` 是空目录，无control socket。没有密码输入成功的证据，不能断言用户密码错误；NAS夹具未创建，所有故障能力仍NOT VERIFIED。

按 [OpenSSH环境变量文档](https://man.openbsd.org/ssh#ENVIRONMENT)，prefer优先使用askpass，never禁止askpass。ignored向导仅stage1 SSH命令增加 `SSH_ASKPASS_REQUIRE=never`，并先校验交互TTY及公开state文件不存在；不修改用户环境/SSH全局配置，不安装ksshaskpass，不改变密钥检查，不关闭加密警告。静态guard selector先exit1（缺少terminal-only要求），修改后exit0；bash-n与wizard模板库一致性exit0。这仅证明脚本修正及静态安全，不是实际SSH认证GREEN。原post-quantum告警另记为连接安全告警，不据此推断本次认证失败原因，也没有自动升级NAS或调整算法。

用户可以在普通本机交互终端重新执行修正向导；若非交互环境则应提前停止，不获取/保存密码。S11保持BLOCKED，待实际认证/夹具启动与真实错误验收。

## 2026-10-08 S11 隔离真实错误补验与能力门禁 — PASSED（现有部署功能范围）

用户认证完成后授权就绪则直接继续。本机实际检查master可用、loopback16608 greeting/status及NAS夹具身份，才执行验收。NAS夹具 `/tmp/mpd-s11-fault.8pHKv9`，独立PID20050，使用现有套件binary：`Music Player Daemon 0.23.17 (699d8b3)`，SHA256=`ff9df851bda831c368bead85aa30e2717f96d057180d405e5c7bfc74367f7ae6`。MPD降权nobody、仅loopback16608、null+pipe输出，无ALSA、无真实媒体；通过用户建立的临时SSH master/端口转发访问，未读取密码。真实TCP Adapter/VerifiedPort/Services与临时SQLite进行新实测，非Mock/旧probe或仅静态源码推断。

### 执行、失败事实与合同校准

```text
PYTHONPATH=. .venv/bin/python .superpowers/sdd/2026-10-04-task-4-d6-recovery-corrective-plan/s11_fault_acceptance.py
# 最终正式执行exit0：decoder/input/output全部VERIFIED
# production_unchanged=true; fixture_restore_verified=true; restore_failure=null
# UTC 2026-10-08T15:36:07.427960+00:00 .. 15:36:10.158381+00:00
# Asia/Shanghai 23:36:07 .. 23:36:10
# s11-faults-20261008T153607Z.json
# SHA256 4d9b3871ebee7cd1c5f3d7e8b75ae8f68851e53bf42b948f77025ed3d0c22550
```

最终完整JSON含所有raw响应、SSH夹具动作、业务before/after/retry/runner snapshot、ID/version、真实ExecutionSample.error、控制调用和保护事实。以下两次探索失败原样保留，不能回填PASS：

- `s11-faults-20261008T153223Z.json`，SHA256=`62366c44d7ab07439c376d0d822d3367d19d19d17c65739f95fe2b9849b996de`，exit1：输入/解码触发next的真实ACK被harness异常处理提前中断，未做Service验收；输出实际PAUSED导致harness错误要求五域完全不变。这不是已确认production失败。
- `s11-faults-20261008T153429Z.json`，SHA256=`08cd5ac254844516d7af734477ee12f55a6136f69080257306ba26af3323b850`，exit1：pipe输出功能VERIFIED；输入/解码虽然真实ACK失败，但MPD后来current是健康fallback的独立good.wav occurrence，10秒样本status.error为空，所以“必然持续status.error”假设不成立。没有从空error断言没有故障或判断自然原因，两个保守停止场景仍NOT VERIFIED。

只修改ignored验收harness/自建夹具，未改production/test/schema：触发阶段允许并记录真实ACK，后续仍须真实status.error；把不可播放条件覆盖所有已排入夹具URI（包括AutoPlay预排的同URI独立fallback），确保测试的是“没有健康后续项”的故障停止。备份golden.wav在music_directory外，reset只恢复本次生成的文件，没有动真实媒体。最终三例仍有A/B/C及预排fallback，共4个occurrence；实际初始Queue revision为2，不假定为3项或把fallback误认重复执行。

**合同校准（非放宽功能）**：F §8.9.3 / P relied PB-RECOVERY-TRANSPORT-001明确允许同绑定current的PLAYING↔PAUSED实际回读确认。输出错误后PAUSED接纳是允许的transport delta，不要求把它冻结为旧PLAYING。harness精确允许state/确认position/updated_at三字段变化，且必须与同一current实际PAUSED样本一致；song/context/AutoPlay、Queue、History、active/session不变，retry/runner不得再次变化。没有通过修改Spec或删除断言迁就产品；保守STOPPED仍要求业务五域完全保留。

### 三类最终原始事实

| 场景 | 身份/version与真实错误 | Service / 状态 / 保留 |
|---|---|---|
| 解码失败 | A/B/C/fallback IDs=28/29/30/31，version84；临时WAV改为无效内容，外部next返回 `ACK [5@0] {next} Failed to decode bad.wav`；随后真实sample STOPPED，current=null，error=`Failed to decode good.wav` | maintain与retry均UNKNOWN/reconciliation_required=true；runner一轮零控制；Queue/Playback/History/active/session完全保留，revision2/History0；actual fresh/UNCONFIRMED_STOP，非伪造业务Stop |
| 输入打开失败 | IDs32/33/34/35，version97；仅临时文件移到parked；ACK与sample明确 `Failed to open '/tmp/mpd-s11-fault.8pHKv9/music/good.wav': No such file or directory`（ACK指bad.wav，sample指good.wav）；真实STOPPED/current=null | maintain与retry均UNKNOWN；runner零控制；业务五域完全保留，revision2/History0；actual fresh/UNCONFIRMED_STOP，不关闭AutoPlay意图、不写自然/Stop/Skip原因 |
| 输出失败 | IDs36/37/38/39，version110；只在隔离端点enable pipe `/bin/false`、disable null；真实error=`Failed to open audio output`，实际PAUSED/Id36/Pos0/elapsed96.384 | 同current实际PAUSED按合同确认；maintain/retry=UNKNOWN/SYNC_FAILED，Queue/History/active/session与song/context/AutoPlay不变，revision2/History0；observe fresh/SYNC_FAILED/matches_current=true；retry/runner无再次delta、零控制、无resume/补曲 |

不把pause归因于用户，也不根据elapsed增量推断播放时间或音频成功。snapshot诊断如上，error_code/error_message实际仍为null；本轮没有宣称页面显示原始MPD错误字符串，真实错误文本由raw status/ExecutionSample与NAS log保留。pipe路径验证的是通用输出错误处理，不外推ALSA/USB DAC/每一codec或全部设备异常。

### 生产保护与清理

本轮6600仅发送status/playlistinfo/outputs。其基线已不是前轮单曲stopped，而是用户当前两项队列：Id4 `一样的月光 - 徐佳莹.flac`、Id5 `雨下一整晚 - 周杰伦.flac`，version5、PAUSED、current Id5/Pos1/elapsed12.620、volume100、consume1、其它模式0；USB DAC enabled/HTTP Stream disabled。三次harness均核对本轮生产前后完整raw响应相等，**没有为恢复旧基线而覆盖用户新状态**；fixture restore仅作用16608，恢复空队列/stopped/null enabled/pipe disabled。没有对6600发play/stop/clear/add/模式/输出控制。

停止前确认fixture PID/exe/config归属，发送TERM仅PID20050，/proc确认该配置进程已退出。完整NAS夹具（生成WAV、配置、database、binary标识、全部launch.log）留存到本机ignored归档：

```text
s11-fault-nas-20261008T153839Z.tar.gz (29703 bytes)
SHA256 0216b8bdaa7cf0abaeb5a8731ad83cdf209367c6da1ba7008ebc3bcb0aa0f2ce
s11-fault-cleanup-20261008.json
```

先验证归档成员只含普通文件/目录且无越界路径，再删除明确白名单生成文件、rmdir仅本次 `/tmp/mpd-s11-fault.8pHKv9`；没有递归删除。随后仅关闭本次SSH master，确认socket已不存在、本机16608已拒绝连接；清理两个本次空SSH目录（成功连接与此前askpass失败的空目录）。临时库/Services/runner均关闭。NAS临时内容可从该归档恢复，真实媒体、DSM套件及其配置未删改。

独立重新核对JSON：三例真实error非空、严格允许delta、零Service控制、retry保留、生产只读allowlist与前后相等、fixture恢复均通过。162份production/test源码hash核对exit0；music-server.db hash仍`57fe90fe852d4a481c57122c39e4014024a48ad6582fc69372832012fb9caba2`；git diff --check通过，无依赖/venv/schema改动，无commit/push。

### S11 最终能力矩阵与边界

| S11功能义务 | 本次有效证据 | 门禁 |
|---|---|---|
| 目标身份/版本/build记录 | 用户NAS监听PID/exe/package，之后SSH夹具实际binary --version/hash；greeting只记协议；用户决定验现有部署功能 | 满足授权范围，不冒称daemon0.23.5或源码原版溯源 |
| 顺序模式、重复URI、ID/position/version | s11-live-result + unattended/seek新原始样本 | VERIFIED |
| 预同步无人控制推进、无Service playid B | 完整240秒无人控制样本；纯接纳后actual CONFIRMED | VERIFIED，不认证natural |
| A→C保留B/不补History、已离开entry move/delete | live-result的真实Service/MPD/业务snapshot | VERIFIED |
| Stop不重启，TCP/Service/daemon restart绑定失效与actual恢复 | live-result与真实用户DSM停止/启动daemon JSON | VERIFIED |
| ACK及响应丢失不盲重发 | ACK50与透明proxy丢真实addid成功响应的UNKNOWN/零重发 | VERIFIED（所执行addid故障范围，不外推全部故障组合） |
| 真实decoder/input/output错误的保守处理 | 最终独立同binary故障JSON，STOPPED与PAUSED分支、retry、runner | VERIFIED（本地WAV/文件打开/pipe场景） |
| 原状态保护与恢复/隔离清理 | 每轮finally恢复核对；本轮生产完全只读不变、归档后精确清理 | VERIFIED |

**S11目标运行时功能能力PASSED，限用户授权的现有NAS部署与上述场景范围**。没有任何被列为本门禁关键功能的NOT VERIFIED项被自动抵扣；未执行的USB DAC听觉/真实设备故障仍不宣称通过，属于Task12，不是S11范围。S10前置已核验、源码未变；本步骤不是pytest联合门禁GREEN，**S12未执行，D6/Batch13/Task6 final继续BLOCKED**。没有实施未来Task/Batch或修改production/test/schema。

## 2026-10-09 S12 — D6 联合验收 / Batch13 / Task6 final PASSED

日期跨 2026-10-08/09（Asia/Shanghai）。实际 checkout `feature/task-6-realtime-state`、HEAD `31be1c4`；保留已有 S2–S10 未提交变更。本次使用既有 .venv：Python3.14.4、pytest9.1.1、Ruff0.16.9。S12自动测试及功能合同验收通过；原本地DB保留UNVERIFIED单列审计；S12不新增功能；发现失败实际回 owner 最小修复后从首项重新验收，无skip/xfail/删减断言。

### S10/S11 前置与证据适用性

本轮 S10 两个完整selector及文件 fresh通过9/11/24；新D6集合包括S9 runner，全部执行。S11不是重新连接目标或复制旧probe：逐项读取现存live/supplement/seek/daemon/fault JSON，核对原始response、Service snapshot、保护恢复及哈希；独立review复核最终三类错误JSON、生产前后相等、清理与归档。最终故障JSON SHA256仍 `4d9b3871ebee7cd1c5f3d7e8b75ae8f68851e53bf42b948f77025ed3d0c22550`，归档仍 `0216b8bdaa7cf0abaeb5a8731ad83cdf209367c6da1ba7008ebc3bcb0aa0f2ce`。

S11门禁沿最新用户功能范围：daemon0.23.17/DSM0.23.17-3/greeting0.23.5；不是daemon精确0.23.5或源码原版溯源PASS。旧NOT VERIFIED义务由分别取得的lost-response、真实daemon restart及最终isolated faults证据补齐，不删除义务。USB DAC听觉/真实设备故障仍属Task12，Task8实际浏览器UI仍未执行。

S11保存的162份源码manifest与本轮起始一致；owner修正后仅main.py和下述3份测试不同。目标harness直接构造Services/runner而不经过main.lifespan；唯一生产增量提前初始化现有本地Queue状态，没有改变目标Adapter/Service/runner算法，故原S11能力证据保持适用。本轮没有live MPD、NAS控制、Docker、依赖/venv变更。

### 失败回 owner、修复与重新验证

1. 首轮realtime为27 failed/224 passed；根因是B4/B5 wire重新构造Service，却丢失开始播放已确认journal。回Task6 Batch4/5 fixture owner，只在test_realtime_playback_transport.py和test_realtime_queue.py复用原RecoveryJournal，沿现有transitions helper模式。两代表selector2 failed→2 passed；原27个失败selector全部27 passed；两整文件68 passed。Queue/History/commit/retry/cancel所有原断言保留，不通过URI造绑定。
2. 第二轮invariants/API为3 failed/1069 passed。回S4/API fixture，将test_mutations_playback.py的fake play_context签名机械接纳已存在request_id/request_payload；原call recording/断言不变。回S9 main启动owner，在observer/runner启动前await现有queue_repository.get_snapshot，完成既有lazy queue_state初始化；没有新增表定义、schema migration、MPD调用或业务revision。两system只读断言与API selector3 failed→3 passed；整文件及S4 execution/S9 runner/lifecycle/output/TX/ARCH回归144 passed。
3. 第三轮invariants/API1072 passed后，发现少数旧API tests的lifespan没有临时DATABASE_PATH，会使用仓库music-server.db。完整server run在765 passed时人为SIGINT中断（exit2），不是GREEN、不计入最终gate。此前本地DB的mtime/哈希与S11记录不同；本窗口没有初始DB字节副本，不能声称原状态未变或已恢复，未删除/覆盖该DB。
4. 回验证环境owner，最终每条原pytest命令均注入独立tmp fallback DATABASE_PATH；具体tests的tmp_path仍优先。没有改通用conftest或生产配置。最终从S10第一selector重新跑全部17段；本地DB最终前后SHA256均 `d52491a2a8e493b36ba7d2ff51a11c68c41d14d373fc3def6ec849e2c277de52`，仅证明最终隔离轮未再改动该DB。此前隔离缺失及中断原始记录全部保留，不回填为通过。

独立只读review两轮均无Critical/Important；确认两类owner修正合理、断言未弱化与S11证据适用性。最终完整门禁结果来自本轮root实测，不称reviewer重复了全套。

### 最终按序 fresh 命令与结果

以下均repository root、原.venv，环境DATABASE_PATH只指向每段独立临时目录；退出均0。每段只有同一既有Starlette/httpx deprecation warning，没有依赖/环境失败。完整stdout、时间戳及exit保存在本plan ignored workspace的s12-isolated-results.json和对应log；旧RED、中断与owner记录分别保留。G编号用于下面追溯表，R集合逐条执行T5原命令，没有union替代。

```text
# G01: 9 passed, 1 warning in 1.32s; exit0
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_stock_joint.py::test_stock_adapter_current_queue_history_and_snapshot_joint
# G02: 11 passed, 1 warning in 1.41s; exit0
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_stock_joint.py::test_stock_joint_failure_restart_and_read_only_boundaries
# G03: 24 passed, 1 warning in 3.19s; exit0
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_stock_joint.py
# G04: 268 passed, 1 warning in 24.03s; exit0
.venv/bin/python -m pytest -q server/tests/player/test_execution_sample.py server/tests/invariants/test_d6_binding.py server/tests/invariants/test_d6_execution.py server/tests/invariants/test_d6_history.py server/tests/invariants/test_d6_current.py server/tests/invariants/test_d6_autoplay.py server/tests/invariants/test_d6_state.py server/tests/api/test_d6_state.py server/tests/invariants/test_d6_runner.py server/tests/invariants/test_d6_stock_joint.py
# G05: 98 passed, 1 warning in 9.35s; exit0
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py
# R-TX: 19 passed, 1 warning in 1.38s; exit0
.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py
# R-LIB: 69 passed, 1 warning in 1.91s; exit0
.venv/bin/python -m pytest -q server/tests/integration/test_task3_events_and_mpd.py server/tests/repositories/test_library_reconciliation.py server/tests/services/test_library_scanner.py server/tests/api/test_library_api.py
# R-PL: 10 passed, 1 warning in 0.66s; exit0
.venv/bin/python -m pytest -q server/tests/invariants/test_playlist_relationships.py server/tests/services/test_playlist_service.py server/tests/api/test_playlist_reads.py
# R-PB: 105 passed, 1 warning in 9.80s; exit0
.venv/bin/python -m pytest -q server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_playback_service.py
# R-H: 15 passed, 1 warning in 0.95s; exit0
.venv/bin/python -m pytest -q server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/repositories/test_task2_steps_5_7.py
# R-O: 103 passed, 1 warning in 5.88s; exit0
.venv/bin/python -m pytest -q server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_lifecycle_injection.py
# R-ARCH: 3 passed, 1 warning in 0.14s; exit0
.venv/bin/python -m pytest -q server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# G13: 6 passed, 1 warning in 1.46s; exit0
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_recovery.py::test_reconnect_replaces_all_domains_and_epoch
# G14: 14 passed, 1 warning in 2.57s; exit0
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_recovery.py server/tests/api/test_realtime.py
# G15: 251 passed, 1 warning in 23.73s; exit0
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_*.py server/tests/api/test_realtime*.py
# G16: 1072 passed, 1 warning in 96.79s (0:01:36); exit0
.venv/bin/python -m pytest -q server/tests/invariants server/tests/api
# G17: 1355 passed, 1 warning in 99.49s (0:01:39); exit0
.venv/bin/python -m pytest -q server/tests
```

### Contract ID → Spec → implementation → executable proof → fresh result

F/A/T/M 缩写沿用 active P。下表 proof 路径均以 `server/tests/` 为根；implementation 路径以 `server/app/` 为根。G04 是新 D6 全参数集合，G05 是旧 consumer（其中 natural 用例仅历史隔离路径），G15 是 realtime 全集；R-* 是 T §5 原命令，不能由全量替代。表中的局部 proof GREEN 不能单独关闭最终 gate，最终结论取决于下面全部命令、S11、Ruff 与范围审查。

| Contract ID | Spec | implementation owner | executable proof | fresh result 集合 |
|---|---|---|---|---|
| PB-BINDING-001 | F8.9.2 | player/mpd_adapter.py::read_execution_sample；services/playback_recovery.py::bind/accepts；PlaybackService确认 | player/test_execution_sample.py::test_sample_rejects_torn_current_and_queue；invariants/test_d6_binding.py::test_duplicate_uri_binding_uses_confirmed_entry_ids、test_binding_invalidates_on_gap_version_reuse_and_restart | G04；S11 ID/模式/连接原始证据 |
| PB-CURRENT-001 | F8.9.1–3 | services/playback_service.py::reconcile_external_status | invariants/test_d6_current.py::test_current_fact_never_claims_cause、test_same_uri_target_is_adopted_by_distinct_occurrence_id | G04；G03联合；S11 later-current/seek |
| PB-QUEUE-ADOPT-001 | F8.9.3 | repositories/queue_repository.py::adopt_current；services/queue_manager.py::adopt_current；ExecutionSynchronizer | invariants/test_d6_current.py::test_current_adoption_preserves_unobserved_manual_occurrences、test_queue_adoption_cas_and_invalid_targets_are_atomic、test_cleanup_barrier_rejects_a_new_mpd_current | G04；G03；S11 A→C/move/delete |
| PB-HISTORY-UNCERTIFIED-001 | F8.9.4 | services/history_service.py::discard_unconfirmed_active；PlaybackService active资格核验 | invariants/test_d6_history.py::test_unknown_departure_then_explicit_stop_does_not_relabel_old_active、test_discard_preserves_session_and_rolls_back_without_event | G04；G03；S11零伪史 |
| PB-HISTORY-001 | F7/8.9.4 | HistoryService；PlaybackService已确认显式操作/finalizer | invariants/test_stop_confirmation.py；invariants/test_playback_relationships.py；invariants/test_d6_history.py | G04/R-PB/R-H；旧原因断言保留 |
| PB-AUTOPLAY-EXEC-001 | F8.9.5 | services/autoplay.py::plan_refill；PlaybackService::maintain_execution；QueueRepository固定planned_items | invariants/test_d6_autoplay.py::test_refill_uses_confirmed_remaining_and_preserves_manual_order、test_empty_stop_disconnect_and_refill_failure_do_not_restart、test_refill_outer_rollback_reuses_fixed_candidates_and_prefix | G04；G03 refill/outer；S11无人推进 |
| PB-RECOVERY-UNKNOWN-001 | F8.9.1/2/5 | RecoveryJournal失效；PlaybackService stock fail-closed；PlaybackObservations | invariants/test_d6_current.py::test_stop_foreign_drift_and_concurrent_mutation_fail_closed；invariants/test_d6_binding.py::test_sample_failure_invalidates_binding_without_business_change | G04；G03；S11故障/重启 |
| PB-RECOVERY-TRANSPORT-001 | F8.9.3 | PlaybackService同binding transport确认 | invariants/test_d6_recovery.py::test_bound_external_pause_resume_preserves_history、test_transport_recovery_rollback_and_retry；invariants/test_d6_current.py::test_transport_confirmation_rejects_a_changed_business_generation | G05/G04；S11 PAUSED error允许delta |
| PB-RECOVERY-RETRY-001 | F8.9.6 | services/playback_execution.py::execute；RecoveryJournal前缀/receipt；outer hooks | invariants/test_d6_execution.py::test_each_command_prefix_is_retried_only_when_owned、test_lost_add_response_never_guesses_or_resends、test_execution_outer_failures_and_post_commit_receipt | G04；G03；S11真实addid丢响应范围 |
| PB-RECOVERY-RUNNER-001 | F8.9.7 | services/playback_recovery_runner.py::run/close；main.py::lifespan | invariants/test_d6_runner.py::test_single_runner_refills_without_clients_and_never_restarts_stop、test_runner_budget_backoff_and_shutdown_preserve_commit、test_lifespan_injection_single_owner_and_cleanup | G04；G03无客户端；owner S9回归 |
| RT-ACTUAL-001 | A12.3.1 | models/realtime.py；api/realtime_schemas.py；PlaybackObservations::observe/get；StateService | invariants/test_d6_state.py::test_actual_identity_is_separate_from_persisted_current；api/test_d6_state.py::test_fresh_browser_reconnect_and_restart_show_truthful_full_state | G04；G03 HTTP/WS；S11实际样本 |
| D6-RECOVERY | F8.9.8–9/A19.5/M依赖 | Adapter/VerifiedPort→Service/SQLite→DTO；独立runner | invariants/test_d6_stock_joint.py的两个规定selector与refill/outer/receipt联合proof；本节完整S12命令；S11原始运行证据 | G01–G17与质量gate合取；不以Fake原因替代 |
| RT-SNAPSHOT-001 | A12.1/12.3 | services/state_service.py::get_full_snapshot；API统一encoder | invariants/test_realtime_snapshot.py::test_snapshot_is_one_committed_cut、test_required_read_failure_never_returns_partial_success；api/test_realtime.py；G13重连selector | G13/G14/G15 |
| RT-REVISION-001 | Library Spec7.1 | repositories/database.py visibility hooks；services/realtime_coordinator.py | invariants/test_realtime_commit_visibility.py::test_committed_data_and_revision_become_visible_together；invariants/test_realtime_playlist.py::test_playlist_versions_follow_outer_delta_and_replay | G15/R-TX |
| RT-LIBRARY-001 | A7/12.2；Library Spec7.1 | LibraryScanner/Repository/LibraryService→RealtimeCoordinator | invariants/test_realtime_library.py::test_outer_scan_waits_for_commit_and_keeps_completion_order | G15/R-LIB/G13 |
| RT-PLAYLIST-001 | Library Spec5/7.1 | PlaylistService/Repository→RealtimeCoordinator | invariants/test_realtime_playlist.py::test_playlist_versions_follow_outer_delta_and_replay | G15/R-PL/G13 |
| RT-PLAYBACK-001 | F3–8/8.9；A12.2 | PlaybackService producer outer wrappers→RealtimeCoordinator | invariants/test_realtime_playback_transport.py::test_transport_event_waits_for_confirmation_and_outer_commit；invariants/test_realtime_queue.py::test_queue_only_notification_preserves_current_occurrence_and_history；invariants/test_realtime_transitions.py::test_transition_notification_matches_committed_history | G15/R-PB/R-TX；B4/B5 owner修正后 |
| RT-OUTPUT-001 | Output Spec6.1–6.3；A12.3 | OutputManager observation/control bridge | invariants/test_realtime_output.py::test_output_control_and_observation_share_delivery_without_history | G15/R-O |
| RT-HISTORY-001 | F2.2.1/8.9.4 | HistoryService::get_availability；Library当前metadata | invariants/test_realtime_history.py::test_history_unavailability_preserves_events_and_has_entries | G15/R-H/G13 |
| RT-OBSERVE-001 | F8.8/8.9；A12.3 | PlaybackObservations；OutputManager；StateObserver | invariants/test_realtime_observation.py；invariants/test_realtime_observer_lifecycle.py::test_single_observer_retries_and_shutdown_preserves_playback | G15；G04新增表示；owner S9只读回归 |
| RT-CONNECT-001 | A12.2 | services/realtime_connections.py::connect；coordinator subscribe_committed | invariants/test_realtime_handoff.py::test_last_mutation_during_initial_send_is_not_lost | G15/R-TX |
| RT-DELIVERY-001 | A12.2 | RealtimeConnections独立sender/失效清理；coordinator有界订阅 | invariants/test_realtime_delivery.py::test_overflow_and_timeout_isolate_clients_and_preserve_commit | G15/R-TX/R-O |
| RT-RECOVER-001 | A12.1–12.3.1 | StateService；api/realtime.py；RealtimeConnections | invariants/test_realtime_recovery.py::test_reconnect_replaces_all_domains_and_epoch；api/test_realtime.py（乱序GET/服务重启/失败恢复） | G13/G14/G15；G04 actual恢复 |

继承与 regression ID 逐项追溯（原权威条款沿 T4.3、Task5 T3.7、Task7 T4；无合同语义改写）：

| ID | Spec / implementation | executable proof | fresh result |
|---|---|---|---|
| EVENT-PORT-001 | A领域event边界；services/events.py及Library/Output producer | integration/test_task3_events_and_mpd.py；invariants/test_output_event_transactions.py | R-LIB/R-O |
| TX-ROLLBACK-001 | A事务边界；repositories/database.py/runtime hooks | invariants/test_transaction_relationships.py；repositories/test_transaction_commit_hooks.py | R-TX/G04/G03 |
| TX-IDEMP-001 | API Spec幂等；services/idempotency_service.py/terminal Repository | api/test_idempotency.py；invariants/test_transaction_relationships.py | R-TX |
| O-EVENT-001 | Output Spec6.1–6.3；OutputManager outer通知 | invariants/test_output_event_transactions.py | R-O |
| O-STATE-001 | Output Spec6.1–6.3；OutputManager cache/observation | invariants/test_output_observation.py | R-O |
| O-PRESERVE-001 | Output Spec6.1–6.3；OutputManager/PlaybackService共享串行边界 | invariants/test_output_serialization.py | R-O |
| PL-REP-001 | Library Spec5；PlaylistService/Repository | invariants/test_playlist_relationships.py；api/test_playlist_reads.py | R-PL |
| PL-COLLECTION-001 | Library Spec集合语义；CollectionService/PlaylistService | invariants/test_playlist_relationships.py；services/test_playlist_service.py | R-PL |
| PB-STOP-001 | F显式Stop/8.9.4–5；PlaybackService/History | invariants/test_stop_confirmation.py | R-PB/G04 |
| PB-INSERT-001 | F Queue插入；PlaybackService/QueueManager | invariants/test_playback_relationships.py；api/test_pre_batch6_corrective.py | R-PB/G15 |
| PB-REORDER-001 | F Queue重排；PlaybackService/QueueRepository | invariants/test_playback_relationships.py；api/test_pre_batch6_corrective.py | R-PB/G15 |
| PB-DELETE-PENDING-001 | F Queue删除pending；PlaybackService/QueueRepository | invariants/test_playback_relationships.py；api/test_pre_batch6_corrective.py | R-PB/G15 |
| PB-DELETE-CURRENT-001 | F当前删除/8.9.4；PlaybackService/History/Queue | invariants/test_playback_relationships.py；invariants/test_d6_current.py::test_paused_current_delete_confirms_explicit_successor | R-PB/G04 |
| PB-NEXT-UNAVAILABLE-001 | F Next不可用跳过；PlaybackService/Library | services/test_playback_service.py；invariants/test_playback_relationships.py | R-PB |

PB-NATURAL-001/PB-NATURAL-EMPTY-001 的 G05 GREEN 仅旧 consumer 隔离证明；D6-SOURCE 保持 SUPERSEDED，不填写生产原因能力 PASSED。原因、真实 ended_at、未观察 B History、重启自动业务绑定、完整Context均不在本合同的成功声明中。U/T/F/I/O 由以上negative/barrier/outer/replay/读路径proof及G03真实TCP联合证明，不以方法存在或checked checklist替代。


```text
.venv/bin/python -m ruff check server/app/api/playback.py server/app/api/realtime_schemas.py server/app/main.py server/app/models/realtime.py server/app/models/recovery.py server/app/repositories/queue_repository.py server/app/services/autoplay.py server/app/services/history_service.py server/app/services/playback_execution.py server/app/services/playback_observation.py server/app/services/playback_recovery.py server/app/services/playback_recovery_runner.py server/app/services/playback_service.py server/app/services/queue_manager.py server/tests/api/__init__.py server/tests/api/test_d6_state.py server/tests/api/test_mutations_playback.py server/tests/api/test_pre_batch6_corrective.py server/tests/integration/support/stateful_fake_mpd.py server/tests/invariants/test_d6_autoplay.py server/tests/invariants/test_d6_binding.py server/tests/invariants/test_d6_current.py server/tests/invariants/test_d6_execution.py server/tests/invariants/test_d6_history.py server/tests/invariants/test_d6_recovery.py server/tests/invariants/test_d6_runner.py server/tests/invariants/test_d6_state.py server/tests/invariants/test_d6_stock_joint.py server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_observer_lifecycle.py server/tests/invariants/test_realtime_playback_transport.py server/tests/invariants/test_realtime_queue.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_transitions.py server/tests/invariants/test_stop_confirmation.py server/tests/services/test_playback_service.py server/tests/support/d6_stock.py
# All checks passed; exit0
```


### 质量、范围与最终裁定

实际改动Python范围（tracked diff + untracked源码/测试）完整scoped Ruff通过；精确命令与文件清单保存s12-quality.json。git diff --check通过，实际diff/stat/status与本轮source manifest核对；当前增量仅main.py两行初始化、3份owner测试夹具及P/E/B/T/M/C状态记录。既有S2–S10生产/测试变更全部保留，不能把全体dirty diff当本轮新增。无临时debug、生成文件、依赖/环境文件进入Git；本地runtime DB保留，隔离问题事实如上，不能称整个窗口没有DB副作用。文档relative link及显式proof selector存在性检查完成；未commit/push/PR/merge，未更改目标运行配置或默认自动启用。

implementation：S2–S10已实现；本轮仅上述owner修复。automated/local-environment：所有规定focused/relationship/realtime/invariants+API/server与Ruff gate完成。target-runtime：S11现有部署功能范围已验，证据适用性核对完成，本轮未重复live。acceptance：自动Relationship proofs GREEN；完整D6 Contract Matrix、Batch13、Task6 functional final PASSED。原本地DB保留UNVERIFIED独立记录；用户已另行授权提交、push、PR和合规合并，Git操作完成后核对其实际结果。Task8 UI、Task10最终配置/部署启用、Task12真实DAC/HTTPS/发布仍未执行，不作为本gate声称的能力。

验收归类复核：最终自动测试没有RED/NOT RUN遗留，S11已定义目标功能均有有效证据；P S12的阻塞项是产品合同、必跑proof及目标能力。原本地DB保留未验证属于本次测试隔离审计事件，不能据此将已完成的产品gate继续标BLOCKED。D6/S12、Batch13和Task6 functional final因此PASSED；这是纠正验收分类，不放宽合同、不删减测试、不把UNVERIFIED改写为通过。原DB事件独立保持UNVERIFIED，不声称已恢复或无副作用；没有可信原副本，不自动覆盖。历史SOURCE仍SUPERSEDED，不外推无限续播、完整History或重启后自动业务接管。

最终文档写入后再次执行 `git diff --check`、`git diff --stat`、`git status --short`；diff检查exit0，status保持既有dirty实现及本轮4份owner源文件/6份状态文档，无新增tracked运行数据库或环境文件。40个相对文档链接存在，逐条显式test selector AST核对均存在。原本地DB保留审计仍UNVERIFIED；功能final已按上述产品合同与可执行证据归类为PASSED。

### 2026-10-09 合并前 S2 owner修复与 corrected-tree 最终复验

合并前review发现PB-BINDING-001的双status采样未比较state。回S2，在Adapter稳定字段增加state；专用TCP fixture加入PLAYING→PAUSED冲突参数。精确selector `test_sample_rejects_torn_current_and_queue[state]` 先RED（DID NOT RAISE）后GREEN1；整文件7、TCP1、errors3、Player目录41均通过，原重试两次/typed error/零控制断言完整保留。无新增产品能力或弱化合同。

独立复审Critical/Important/Minor均0，并复跑selector和整文件。S11 supplement/seek的141个完整wire采样窗口state前后一致；等待和丢响应日志同样一致。初始独立RawMPD日志中跨业务操作的变化已被旧version/ID核验拒绝，不能当作accepted样本。该修复仅增加不一致拒收，不改变已成功稳定样本或目标控制行为，S11证据仍适用。

修复后从G01重新按原顺序执行全部17段，命令与上节相同。以下为合并树的最新fresh结果，覆盖上节首轮结果用于逐Contract表G编号追溯；R集合仍分别执行。完整命令/时间戳/stdout/exit保存release-isolated-results.json及release日志，原S12结果和RED日志不覆盖。

| Gate | 最新结果 | Exit |
|---|---|---|
| 01-stock-current | 9 passed, 1 warning in 1.26s | 0 |
| 02-stock-failure | 11 passed, 1 warning in 1.44s | 0 |
| 03-stock-file | 24 passed, 1 warning in 3.25s | 0 |
| 04-new-d6 | 269 passed, 1 warning in 24.74s | 0 |
| 05-old-d6 | 98 passed, 1 warning in 9.86s | 0 |
| R-TX | 19 passed, 1 warning in 1.41s | 0 |
| R-LIB | 69 passed, 1 warning in 2.05s | 0 |
| R-PL | 10 passed, 1 warning in 0.63s | 0 |
| R-PB | 105 passed, 1 warning in 9.75s | 0 |
| R-H | 15 passed, 1 warning in 1.00s | 0 |
| R-O | 103 passed, 1 warning in 6.39s | 0 |
| R-ARCH | 3 passed, 1 warning in 0.16s | 0 |
| 13-batch13-selector | 6 passed, 1 warning in 1.42s | 0 |
| 14-batch13-files | 14 passed, 1 warning in 2.53s | 0 |
| 15-realtime | 251 passed, 1 warning in 23.76s | 0 |
| 16-invariants-api | 1072 passed, 1 warning in 91.37s (0:01:31) | 0 |
| 17-server | 1356 passed, 1 warning in 97.86s (0:01:37) | 0 |

质量：本分支相对origin/main所有70份实际Python文件scoped Ruff通过（release-quality.json）；compileall、diff检查和40个相对文档链接检查通过。最新隔离轮本地DB前后SHA256均 `d52491a2a8e493b36ba7d2ff51a11c68c41d14d373fc3def6ec849e2c277de52`；早期原状态保留仍UNVERIFIED独立记录，未删除/恢复/覆盖。

因此D6/S12、Batch13、Task6 functional final PASSED；所有关键proof和目标功能有适用证据，没有被豁免的RED/NOT RUN或目标能力。Task4/Task6已满足实现与测试步骤，用户另行授权的提交/push/PR/合并由Git记录验证，不声称本验收替代Task8/10/12。
