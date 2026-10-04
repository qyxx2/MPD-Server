# Task4 D6-RECOVERY专项验收 — BLOCKED

日期：2026-10-04（Asia/Shanghai）。本轮唯一专项 acceptance。**D6 未完成；Relationship Gate FAILED，Contract Matrix Gate BLOCKED；Batch13 最终 acceptance 未满足。**

> 最新结论见文末「Contract Gap Resolution / 人工 A」；前文保留首次诊断历史，不再将其未决合同状态作为当前实施指令。

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
