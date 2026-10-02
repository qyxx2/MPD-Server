# Task 7 Batch 8 — Output mutation REST / outer transaction acceptance

## 实际范围和基线

真实 branch `feature/task-7-output-manager`，开始 HEAD `114785ceacdd22e08b74d10d85a299579f7bb46d`，working tree 干净。重新 fetch、history、ls-remote；远端同名 ref 为该 SHA。Task 1R `03f4de9`、Task 4 `86975d6` ancestry exit 0。没有沿用历史 checklist/GREEN。

读取 README、主 Plan Task 7/global constraints/Relationship 与 Contract gates、active Plan §4–8、O 输出 Spec（尤其 §6.1–6.3）、A 模块边界/§8.1/13/19.5、P §8、Task 5 归档 Matrix、B7 acceptance；核对真实 API/Service/PlayerPort/capabilities/transaction/idempotency 与直接测试。B7 遗留的 schema 排期只纠正到 B8；采用冻结名称 `OutputSetRequest`，没有更改业务合同。

按 B8 执行：pre-flight → 成功 PUT 最小行为 → validation/typed errors → outer failure/retry/replay proof → focused/历史/显式 invariant/compile/lint/范围与 traceability 审查。完成原 Step 5 API 剩余、Step 3/4/8 的 B8 integration。**不执行 B9 Task final gate，不勾选整个 Task 7**。

沿用指定 checkout 与 `.venv`（Python 3.14.4、pytest 9.1.1、Ruff 0.16.9），无依赖/环境修改，无 Docker/live NAS/物理 DAC 验收。临时 SQLite 只由 pytest fixtures 创建。

## Contract Impact / traceability

Owned：**SYS-WRITE-001、O-TX-001、O-EVENT-001**。
Relied：**O-ENABLE-001、O-DISABLE-001、O-FAIL-001、O-PRESERVE-001、O-RESERVED-001、TX-ROLLBACK-001、TX-IDEMP-001、EVENT-PORT-001**。
Regression：**PB-STOP-001、PB-INSERT-001、PB-REORDER-001、PB-DELETE-PENDING-001、PB-DELETE-CURRENT-001、PB-NEXT-UNAVAILABLE-001、PB-HISTORY-001、PL-REP-001、PL-COLLECTION-001**，以及 F1–F7/F4L。

Relationship **REQUIRED / GREEN**；Contract Matrix **REQUIRED / GREEN（B8 scope）**。Existing frozen rows only，New rows/modified business semantics = none。每个受影响 row 的 Preconditions、Authorities、Delta、Unchanged、Confirmation、History/Event、Transaction、Failure/Rollback、Retry、Observable Result、Executable Proof 均在实现前按 active §4.2–4.4 核对；没有 Contract Gap 或未关闭 blocker。

| Contract ID → authoritative Spec | implementation → executable proof → fresh GREEN；delta/unchanged/failure/confirmation/retry obligation |
|---|---|
| SYS-WRITE-001 → O §6 / P §8.6 / A §19.5 | `api/system.py` + `system_schemas.py` → mutation API tests + F8/F9（38 passed）。200 只对应 Service 确认；422 key/schema、409 payload/scope、400 unsupported/selection、503 unavailable/capability、502 command/reconciliation。API 无资源访问/事件/播放 policy；失败不保存成功 terminal。 |
| O-TX-001 → O §6.2–6.3 / A §19.5 | existing `IdempotencyService` / database / OutputManager lifecycle → F9 两个目标 × 五类故障 + committed replay（13 passed）。实际 MPD 可已变；terminal/schema/outer/commit/cancel-before-commit 均无 terminal/event，请求成功标记失效；GET 呈现真实事实；retry 重新观察且不重复控制，commit 后 replay 断线也无 reads/writes。 |
| O-EVENT-001 → O §6.3 | existing manager / `OutputChangedEvent` / outer commit hooks → API publisher/F8/F9（38 passed）+ F4/F4L。publisher 在独立 task 读到 committed terminal；事件对应 confirmed snapshot；无变化/replay 不通知。发布异常日志可观测；commit 后取消保留 terminal/request success。无 History，非 durable delivery。 |
| O-ENABLE-001 → O §6.1–6.3 | existing manager bool ensure → F8 enable/change/no-op + F5；确认目标 enabled 后 ACTIVE，其它 outputs 与 playback 不变；不只凭 ACK，无盲目 retry。 |
| O-DISABLE-001 → O §4.2/6.1–6.3 | same manager bool ensure → F8 disable/change/no-op + F6；INACTIVE 与 Stop 无关，无 play/stop/seek/queue mutation、History/session 变化。 |
| O-FAIL-001 → O §6/8.2 | existing manager + API error boundary → F8 ACK无效果/timeout-after-effect/guard drift + F5/F6/F9；失败与实际输出独立，错误不改判200；不补偿其它输出/播放，重新读事实。 |
| O-PRESERVE-001 → O §6.2 / A §8.1/19.5 / P §8 | existing shared runner/guard → F8/F9 before-after Queue/state/Context/persisted+active History/session/current occurrence/position + F3/F5/F6。输出只改变获准字段，无 History transition；所有播放态/并发/未知位置 proof 继续由历史 F3/F5/F6 明确回归。 |
| O-RESERVED-001 → O §5/6.1 | existing manager rejection + API mapping → mutation API enable/disable + F8 unsupported + F1。400 OUTPUT_MODE_UNSUPPORTED；无 port calls、History/event/terminal，旧输出不变。 |
| TX-ROLLBACK-001 → Task 5 Matrix / A §19.5 | existing UoW/lifecycle → F9/F4L/R-TX；失败/取消恢复持久与 runtime 权威、无 phantom History；不将 SQLite rollback 说成 MPD rollback。 |
| TX-IDEMP-001 → Task 5 Matrix / P §8.6 | existing middleware/service/repository → mutation API missing-key/payload+scope conflicts、F9 retry/replay + R-TX/API idempotency；failed key 不消费，成功 terminal 与回执一致，重放无副作用。 |
| EVENT-PORT-001 → A §12 / 主 Plan event rule | existing publisher interface/hooks → F4/F9 + R-EVENT；无 WebSocket dependency，不改变旧 Library event ordering；不声称 exactly-once。 |
| 全部九个 §4.4 regression IDs → Task 5 原 Matrix §3.7 / P | existing playback/Queue/History/Playlist owners → R-STOP/R-PLAY/R-TX/R-PL/pre-batch6 API、architecture 与全 invariants（283 passed），组合历史 gate（420 passed）。原 delta/unchanged/confirmation/rollback/retry 语义未变，无历史 production 改动。 |

## RED / GREEN 与故障调查

- 成功 PUT：**1 failed**（405，缺 mutation 路由）→最小 schema/route 调用 manager→**1 passed**；success/no-op F8 四个 cases 后 **5 passed**。
- Reserved error：**2 failed**（OutputError 未映射）；F8 十种 error cases **10 failed**（Service/Port 异常透出）→只添加 typed HTTP mapping→API/F8 **25 passed**。
- Boolean validation：对普通 `bool` 明确观测 **2 failed / 5 passed**（字符串/数字被转换后200）→`StrictBool`→exact **7 passed**，无输出副作用或 terminal。
- F9 是对已经实现的前置生命周期/事务合同新增最终 API proof，首次 **10 passed**，补 committed publisher/cancellation proof 后 **13 passed**；不伪称前置 production 在本轮有 RED→GREEN 修改。
- Schema fault 最后加强为真实 manager 操作后只损坏独立 receipt 的 status，让真实 REST schema 抛出 `ValidationError`；检查错误位置 `states[0].status`，没有 mock schema 来代替最终 proof。最终 focused **38 passed**、显式全 invariants **283 passed**。
- 非预期历史失败：F7 两个 composition cases 仍断言 GET-only。按 systematic debugging 查完整 diff/traceback 与批准 B8 route scope，唯一改动为精确集合 `{get}`→`{get, put}`；GET、无 startup probe、SQLite/port/event 不变断言全部保留。Exact **2 passed**、read API/F7 **19 passed**。不是放宽合同或删除断言。
- Ruff 初次四个 findings 仅涉及新 import formatting/unused test bindings；最小修正，最终 targeted Ruff 全 GREEN。没有为测试修改既有通用事务或幂等代码。

## 本轮命令与实际结果

所有命令从 root 使用 `.venv/bin/python`：

```bash
.venv/bin/python -m pytest -q server/tests/api/test_system_reads.py server/tests/invariants/test_output_lifecycle_injection.py server/tests/invariants/test_output_enable.py server/tests/invariants/test_output_disable.py server/tests/api/test_idempotency.py
# baseline: 120 passed
.venv/bin/python -m pytest -q server/tests/api/test_system_output_mutations.py server/tests/invariants/test_system_output_relationships.py server/tests/invariants/test_output_idempotency.py
# final focused: 38 passed
.venv/bin/python -m pytest -q server/tests/invariants server/tests/services/test_output_manager.py server/tests/services/test_mpd_info_service.py server/tests/services/test_playback_service.py server/tests/api/test_system_output_mutations.py server/tests/api/test_system_reads.py server/tests/api/test_idempotency.py server/tests/api/test_pre_batch6_corrective.py server/tests/repositories/test_transaction_commit_hooks.py server/tests/player/test_task1r_step4.py server/tests/player/test_task1r_step5.py server/tests/player/test_task1r_step6.py server/tests/player/test_task1r_step7.py server/tests/integration/test_task3_events_and_mpd.py
# historical + required gates: 420 passed
.venv/bin/python -m pytest -q server/tests
# final unchanged code/test tree regression: 736 passed (46.64s)
.venv/bin/python -m pytest -q server/tests/invariants
# independent final relationship gate: 283 passed
.venv/bin/python -m compileall -q server
# exit 0
.venv/bin/python -m ruff check server/app/api/system.py server/app/api/system_schemas.py server/tests/api/test_system_output_mutations.py server/tests/invariants/test_system_output_relationships.py server/tests/invariants/test_output_idempotency.py server/tests/invariants/test_system_read_relationships.py
# All checks passed
```

上述最终验证无 failed/error/skip/xfail；pytest 唯一 warning 为既有 Starlette TestClient/httpx deprecation。未更改环境解决 warning。每个最小单元 GREEN 后均执行 diff check/status；最终完整 diff/changed files 审查无越界。

## 独立审查 / 文件范围 / 剩余边界

独立只读 reviewer 审查真实 working diff 和直接依赖；独立执行 focused **38 passed**、加强的 F9 **13 passed**、diff check clean。无 Critical/Important/Minor finding。schema proof 加强建议已落实，无 production defect 或 deferred issue。

实际 production 两文件：`server/app/api/system.py`、`system_schemas.py`（薄 PUT/请求 validation/error mapping）。新增 tests：`server/tests/api/test_system_output_mutations.py`、`server/tests/invariants/test_system_output_relationships.py`、`test_output_idempotency.py`。已有 F7 文件仅更新批准 route-set。文档仅 active Plan 当前事实/schema排期与本 acceptance archive。

无无关格式化/refactor、合同语义改写、平行权威、schema/dependency/runtime artifact、Task 6/10 imports。OutputManager、通用 middleware/idempotency/database 均未改动。Review set-aside：durable event delivery 不在合同内；物理 DAC/NAS 未执行；B9 Task final gate 未执行；Spec 缺失语义不自行实施。上述不是 B8 未关闭 blocker。

**B8 本地 acceptance 满足，可进入 B9 独立 pre-flight；Task 7 未完成。** Active B8 未明确要求 push；本轮只本地 commit，提交后由最终报告给出真实 SHA、HEAD、完整 changed-files、clean tree 和远端 ref 二次核对。未 push/PR/merge main。
