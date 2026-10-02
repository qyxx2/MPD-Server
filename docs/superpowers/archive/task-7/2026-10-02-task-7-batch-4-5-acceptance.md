# Task 7 Batch 4.5 — lifecycle capability 注入 corrective acceptance

## 实际基线与完成范围

- 分支 `feature/task-7-output-manager`；开始时 HEAD `4fb736bb30e023f032b1f1e5c76ad1e15751aeb2`，工作树干净。重新 fetch 后 `git ls-remote` 同名远端 ref 与基线一致；Task 1R `03f4de9`、Task 4 corrective `86975d6` ancestry 检查 exit 0。
- 实际读取 README、主 Plan Task 7/两个 Gate、active Task 7 Plan §3.1/相关 rows/§5/F4L/B4.5/§8、O §6.2–6.3、A §8.1/12/19.5、P §8、归档 Task 5 原 Matrix、B4 acceptance，以及真实 PlaybackService/OutputManager/database hooks、直接相关代码和测试。没有使用历史验收结论替代本轮执行。
- 使用现有 `.venv`：Python 3.14.4、pytest 9.1.1、Ruff 0.16.9；未修改依赖或环境，未使用 Docker、真实 MPD/NAS/DAC。
- 完成 B4.5 共同执行步骤：pre-flight、RED tests、最小 production 实现、focused/invariant/直接历史 regression、compile/lint、完整 diff/范围与 traceability review、独立审查。仅补 transaction owner → lifecycle capability → OutputManager 的技术桥梁。

## Contract Matrix Impact Analysis 与追溯

- Owned：**无新增业务 Contract row**；支持 **O-PRESERVE-001、O-TX-001、O-EVENT-001** 既有技术路径。
- Relied-upon unchanged：**TX-ROLLBACK-001、EVENT-PORT-001**。
- Regression：**F3/F4、R-TX、R-PLAY**；对应既有 TX-ROLLBACK-001/TX-IDEMP-001 和 playback PB-STOP/INSERT/REORDER/DELETE-PENDING/DELETE-CURRENT/NEXT-UNAVAILABLE/HISTORY-001，保持原 row，不新增 owner。
- Relationship Gate：**REQUIRED / PASS（B4.5 lifecycle bridge）**。
- Contract Matrix Gate：**REQUIRED / PASS（B4.5 lifecycle bridge）**。
- 无新增或修改业务语义 row；无 Contract Gap。逐项核对 Preconditions、Authorities、Expected Delta、Unchanged、External Confirmation、History/Event、Transaction、Failure/Rollback、Retry/Idempotency、Observable Result、Executable Proof。

| ID → 权威 | 本 Batch delta / unchanged / failure / confirmation / retry | implementation → invariant → fresh GREEN |
|---|---|---|
| O-PRESERVE-001 → O §6.2、A §8.1/19.5、P §8、active §4.2/§5/B4.5 | callback 获得 lifecycle；同 DB serialization、Queue/revision/Context/History/session、MPD occurrence/order/state/position/modes/outputs 保持；guard 漂移仍拒绝、不修复播放器；失败后新 invocation 重取基线 | PlaybackService runner + OutputManager read/guard；F4L capability/unchanged assertions + F3 的双向 barrier 和 drift proofs；14 F4L、230 focused/regression、140 invariants GREEN |
| O-TX-001 → O §6.2–6.3、A §19.5、active §3.1/4.2/5 | facade 绑定 owner 的 public hooks，不暴露 DB resource；内层返回不等于 outer commit。outer/callback failure、提交前取消 cleanup 且丢弃 notification；提交后取消保留 terminal，不反向 rollback。retry 使用新 lifecycle，旧 capability 在 invocation 外被拒绝 | Protocol-only output_operation.py；PlaybackService path-bound facade + finally 失效；F4L outer/callback/cancel/nested/postcommit/expiry/retry；14 GREEN，F4/R-TX 在230 GREEN 内 |
| O-EVENT-001 → O §6.3、A §12、active §4.2/5 | 仅注入 commit/rollback 注册，不新增 emit 决策。提交后释放锁才执行 callback，独立 task 读到 committed terminal；失败丢弃通知；已提交事实不被取消/发布器失败撤销 | lifecycle forwarding 至已有 B4 hooks；F4L notification/terminal witness、F4 exception/cancellation proofs；14 F4L + focused/regression GREEN；真实输出 emit 仍 pending B5/B6，API final proof pending B8 |
| TX-ROLLBACK-001 → 原 Task 5 Matrix、A §8.1/19.5、active §4.3 | persisted/runtime/session rollback 保持；不改 database 算法，不把 SQLite rollback 当 MPD rollback；同 key retry/replay 原合同保持 | R-TX test_transaction_relationships.py、api/test_idempotency.py、F3/F4；230 GREEN |
| EVENT-PORT-001 → A §12、主 Plan dependency rule 6、active §4.3 | 既有 EventPublisher 接口不变；无 WebSocket/outbox/exactly-once 协议；Library 原 publication 顺序保持 | F4 与全 backend 中 Task 3 event regression；230 focused / 578 backend GREEN |

F4L 使用真实 SQLite、PlaybackService、OutputManager guard、VerifiedPlayerPort/MockMPD；不使用 mock DB path、bound-method `__self__` 或私有 transaction ContextVar。测试 terminal 是 lifecycle witness，不冒充 NAS 启停或 REST 集成证明。

## RED → GREEN 与 Step 检查

1. capability 注入：新测试明确断言 `output callback lacks lifecycle capability`，**1 failed**，不是导入或环境错误。最小 Protocol/facade/runner/read/guard 适配后 **1 passed**；历史 read/guard callback 仅改签名，断言保持，直接回归 **94 passed**；diff check/status 已检查。
2. invocation 生命周期：commit/rollback 各自覆盖 still-active outer 和 next invocation，旧 capability 注册未被拒绝，**4 failed、2 passed**。增加 invocation active 检查及 `finally` 失效后 **7 passed**；F3/F4/hooks/R-TX/R-PLAY **99 passed**；diff check/status 已检查。
3. 对继承 hook 语义补充 outer commit/failure、callback failure、取消发生在 callback/outer、嵌套归属、commit 后取消、retry/unchanged 证明，F4L **14 passed**。这些是已存在 B4 行为的补充 GREEN 关系证明，不声称额外 production RED 周期。
4. lint 首次发现 import formatting、slots ordering、冗余 real_client 导入。按 systematic debugging 核对 traceback、真实 diff 和 invariants/conftest.py 后，仅整理当前 imports/slots、移除已由 conftest 提供的重复 fixture 导入；未 suppress 检查。复跑 scoped Ruff PASS、F4L **14 passed**。

## 本轮实际命令与结果

所有命令从 repo root 使用 `.venv/bin/python`。

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_output_lifecycle_injection.py
# 14 passed

.venv/bin/python -m pytest -q server/tests/invariants/test_output_lifecycle_injection.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_event_transactions.py server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/services/test_playback_service.py server/tests/services/test_output_manager.py server/tests/invariants/test_output_observation.py server/tests/api/test_idempotency.py server/tests/api/test_pre_batch6_corrective.py
# 230 passed

.venv/bin/python -m pytest -q server/tests/invariants
# 140 passed; includes architecture relationships

.venv/bin/python -m pytest -q server/tests
# 578 passed

.venv/bin/python -m compileall -q server
# exit 0

.venv/bin/python -m ruff check server/app/services/output_operation.py server/app/services/playback_service.py server/app/services/output_manager.py server/tests/invariants/test_output_lifecycle_injection.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_observation.py server/tests/services/test_output_manager.py
# All checks passed

git diff --check
# exit 0
```

无 skip/xfail；pytest 各次只有现有 FastAPI/Starlette httpx 弃用警告，没有依赖/环境或测试失败残留。完整 suite 不替代显式 F4L/F3/F4 关系 Gate。

独立 read-only reviewer：无 Critical/Important/Minor findings；独立 F4L **14 passed**，直接相关回归 **126 passed**，scoped Ruff/diff check 通过。其未复建历史 RED 状态；本轮 RED 来自作者实际输出。其排除的 B5/B6 mutation、B8 API、真实硬件行为均保留为未来验收，不以本轮结果外推完成。

## Changed-files / future isolation / acceptance

- Production：新增 `server/app/services/output_operation.py`（仅 Protocol）；修改 `playback_service.py`（facade/runner）、`output_manager.py`（read/guard callbacks）。数据库、事件、Repository schema、幂等协议、PlayerPort 未改。
- Tests：新增 `server/tests/invariants/test_output_lifecycle_injection.py`；`test_output_serialization.py`、`test_output_observation.py`、`services/test_output_manager.py` 仅适配冻结 callback 签名，不弱化断言。
- Docs：active Task 7 Plan 只更新 B4.5 实际接口/局部状态并引用本归档；本文件保存验收证据，不建立并行权威合同。
- 无 enable/disable、request state transition、emit 决策、System API、Task 6/8/10、无关格式化/重构或 runtime/env artifact。
- **B4.5 本地 acceptance 满足，无 blocker/Contract Gap，可进入 B5 独立 pre-flight。** O-PRESERVE-001 实际 mutation proof 仍 pending B5/B6；O-TX-001/O-EVENT-001 最终 integration proof 仍 pending B8；Task 7 未完成。真实 DAC 物理验收不属于本 Batch。
- 本文记录预提交验收；提交 SHA/HEAD/changed files/clean tree 与远端 ref 的二次确认在本轮最终报告及忽略的执行 ledger 中记录。用户授权本 Batch commit；active plan 未明确要求 push，本轮不 push、不创建 PR、不合并 main。
