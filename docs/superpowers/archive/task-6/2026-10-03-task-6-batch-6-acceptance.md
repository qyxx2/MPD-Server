# Task 6 Batch 6 acceptance — Current/History 联合转移传播

日期：2026-10-03。范围：active Task 6 plan Batch 6；本文件仅保存执行证据，不新增合同或修改 authority。

## 真实基线与最小范围

- 分支：`feature/task-6-realtime-state`。
- 开始时 HEAD：`068d80491fb5c9ebefed22a171c2396cfac7deec`；working tree 干净。
- 实际读取 README、主 Plan Task 6/Dependency/Relationship/Contract gates、active Task 6 plan Batch 6/Matrix/回归命令、Playback Spec §3–8、Architecture Spec §5/§12/§19.5、T5 frozen PB/TX rows、T4 PlaybackService corrective plan/acceptance，以及真实代码/测试。历史记录只作定位；前置 proof 重新运行。
- Python 3.14.4、pytest 9.1.1、Ruff 0.16.9；仅使用既有 `.venv`，已检查 `server/requirements.txt`。无依赖/环境/schema 修改，无 Docker、live MPD 或物理 NAS/DAC 测试。
- 本批生产修改仅 `server/app/services/playback_service.py`（25 行新增）：复用现有提交登记，捕获联合 playback/queue/history 前后内容；start_track/play_context/play_now/next/previous/current delete 和既有显式 reconciliation 接线。无需修改 HistoryService。

## Contract Matrix Impact Analysis（实施前核对）

- Owned：**RT-PLAYBACK-001 final**。
- Relied-upon：**TX-ROLLBACK-001、TX-IDEMP-001**；传播消费 **EVENT-PORT-001** 的既有合同。
- Regression：**PB-STOP-001、PB-INSERT-001、PB-REORDER-001、PB-DELETE-PENDING-001、PB-DELETE-CURRENT-001、PB-NEXT-UNAVAILABLE-001、PB-HISTORY-001**。
- Relationship Gate：**REQUIRED**；Contract Matrix Gate：**REQUIRED**。新增/修改业务语义 rows：0；Contract Gap：0。

以下引用 active plan §4.1 U/T/F/I、RT-PLAYBACK row 和 §4.3/T5 §3.7，不复制另一份权威合同：

| 受影响合同 | Expected State Delta / Must Remain Unchanged | Confirmation / Failure-Rollback / Retry | 本轮 executable proof |
|---|---|---|---|
| RT-PLAYBACK-001 | confirmed current/Queue/History 联合提交后失效 changed domains；传播不新增转移，不改变原操作之外的 Library/Playlist/Favorites/Output、Queue CAS 或 History reason/session | 继承 PlayerPort status/current occurrence 确认；提交前失败/取消无成功事件，持久/runtime rollback；提交后取消/交付失败保留提交与 terminal；成功 replay 不再通知 | transitions 全文件、B4 transport、B5 queue proofs |
| TX-ROLLBACK-001 | 原领域 delta 与 terminal 同 outer owner；失败恢复全部本地持久/runtime，不能假装撤销 MPD 副作用 | terminal failure、outer exception/cancel 无 phantom History/terminal；retry 再确认实际结果 | 主 selector 六分支、failed-transition、cancel、显式 reconciliation rollback；R-TX |
| TX-IDEMP-001 | 同 key/scope/payload terminal replay 原回执，Queue/History/event/marker 不重做 | 外部或 terminal 失败无 success record；相同 key 可 retry；scope conflict 保持 | 主 selector、failed-transition、publisher-failure；R-TX |
| EVENT-PORT-001 | publisher 注入，无 socket 反向依赖，旧 payload 保留 | outer commit 后锁外异步发布；失败不撤已提交状态 | Publisher 内独立事务读取、transaction_identity 边界；B4/B5 与 publisher-failure |
| PB-STOP / INSERT / REORDER / DELETE-PENDING | 仅原 frozen operation delta；current/occurrence/context/history 或 Queue 保留关系按各 row | PlayerPort 确认、CAS conflict 在 side effect 前、rollback/retry/replay | B4/B5 proofs；R-PB 与 R-TX |
| PB-DELETE-CURRENT / NEXT-UNAVAILABLE / HISTORY | 确认可用 successor 后共同切换；unavailable 不成为 current；STOPPED deletion 不重启；无 phantom/lost/duplicate History | 实际 successor/current 确认；失败恢复本地/runtime；retry/replay exactly-once 原领域结果 | transitions 主 selector、barrier、successor selection、stopped deletion；R-PB/R-H |

## 执行顺序与 RED→GREEN

1. 读取/核对前置实现：B1/B4/B5 proof 合跑 **85 passed**，不是根据勾选或历史摘要判定。
2. 新建 `test_transition_notification_matches_committed_history`。六分支 start/context/play-now/next/previous/current delete 实际 **6 failed**：成功确认并提交后 `subscriber.pending is None`。terminal rollback 部分已通过，失败源为目标传播缺失。最小生产接线后精确 selector **6 passed**；新文件+B4/B5 **74 passed**，diff/status 检查通过。
3. 新建 `test_explicit_reconciliation_propagates_only_committed_existing_delta`。显式 paused/stopped 两分支实际 **2 failed**：失效未登记。增加同一 wrapper 后精确 selector **2 passed**；新文件+B4/B5 **77 passed**，diff/status 检查通过。未新增自动调用、未修改 natural/Stop 分类。
4. 增加关系保护：六入口确认屏障、command/status/disconnect failure/retry、unavailable/no successor、空 context/no-op、停止后删除、outer 多 producer 联合 domains、提交前/后取消、publisher failure 与 terminal replay。新 proof 全文件 **46 passed**。
5. 执行 focused/历史回归、lint/compile、完整 diff 和 future scope 审查；最后完整后端 suite GREEN。两项 REQUIRED Gate 均满足。

非预期失败处理：新增 stopped-deletion 测试最初 **1 failed、41 passed**。systematic-debugging 查明原 confirmed-save 会刷新 `updated_at`；合同不冻结该确认时间。只将新测试的 PlaybackState 比较改为全部业务字段，History/runtime 仍逐项完全比较，未修改生产行为。精确失败测试重跑 **1 passed**。Ruff 首次发现新测试 import 格式及 unused 返回值，局部修正后通过；未自动格式化全库。

## 本轮 fresh 验证

所有命令从仓库根目录运行，均使用 `.venv/bin/python`：

| 命令 | 实际结果 |
|---|---|
| `-m pytest -q server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_realtime_playback_transport.py server/tests/invariants/test_realtime_queue.py` | 85 passed（前置基线） |
| `-m pytest -q server/tests/invariants/test_realtime_transitions.py::test_transition_notification_matches_committed_history` | RED 6 failed → GREEN 6 passed |
| `-m pytest -q server/tests/invariants/test_realtime_transitions.py::test_explicit_reconciliation_propagates_only_committed_existing_delta` | RED 2 failed → GREEN 2 passed |
| `-m pytest -q server/tests/invariants/test_realtime_transitions.py` | 46 passed |
| `-m pytest -q server/tests/invariants/test_realtime_transitions.py server/tests/invariants/test_realtime_playback_transport.py server/tests/invariants/test_realtime_queue.py` | 114 passed |
| R-PB：`-m pytest -q server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_playback_service.py` | 104 passed |
| R-TX：`-m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py` | 19 passed |
| R-H：`-m pytest -q server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/repositories/test_task2_steps_5_7.py` | 15 passed |
| R-ARCH：`-m pytest -q server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories` | 3 passed |
| `-m pytest -q server/tests` | 888 passed，35.69s |
| `-m ruff check server/app/services/playback_service.py server/tests/invariants/test_realtime_transitions.py` | All checks passed |
| `-m compileall -q server` | exit 0 |
| `git diff --check` | exit 0 |

各 pytest run 有 1 条既有 Starlette TestClient/httpx deprecation warning；无环境失败、skip、xfail 或未报告的最终测试失败。完整 suite 不替代前面的 invariant/Contract gates。

## Traceability / changed-files review

RT-PLAYBACK-001 → P §3–8 / A §12.2 → PlaybackService `_current_change` / current-delete staging / 既有 transport+queue staging → `test_transition_notification_matches_committed_history` 及 transitions 全文件、B4/B5 proof → 本轮 46/114 GREEN。transport、queue-only、current/history 三类别真实 proof 已闭环，该 row 的 B6 final owner 门禁满足。

TX-ROLLBACK/IDEMP → A §5/§19.5、主 Plan、T5 §3.5/§3.7 → 既有 database/idempotency 与 runtime hooks（未改语义）→ terminal rollback/retry/replay/cancel proofs、R-TX → 本轮 19 GREEN。

PB-STOP/INSERT/REORDER/DELETE-PENDING/DELETE-CURRENT/NEXT-UNAVAILABLE/HISTORY → P §3–8 与 T5 §3.7 → 原 Playback/Queue/History/Port 操作（未改规则）→ B4/B5/transitions 与历史 playback/stop/pre_batch6 corrective proof → 本轮 114 + R-PB 104 + R-H 15 GREEN。

完整实际 diff（含未跟踪文件）已审查。实际三文件：

- `server/app/services/playback_service.py`：25 行最小生产接线。
- `server/tests/invariants/test_realtime_transitions.py`：新增 445 行、46 个运行用例；均保护当前合同，不修改历史测试。
- 本 archive acceptance：执行记录，不新增 parallel authority。

无无关格式化/refactor、无未来 Batch/Task 代码、无 dependency/schema/environment/DB/runtime artifacts。独立只读 reviewer 未发现 Critical/Important/Minor。

Reviewer 列出的 deferred scope 已逐项判定：既有显式 reconcile 的 STOPPED/领域恢复属于 D6；snapshot/observer/WS/production lifecycle wiring 属未来 Batches；whole-branch/历史领域合同验收不属于本批。维持这些边界，不将本批 GREEN 当作其验收，否则会遗漏后续门禁。Deferred minor：无。

## 实施验收时状态与 Git

- 本批 implementation、automated tests、本地环境验证、changed-files/isolation review、两项 REQUIRED Gate 与 Batch acceptance 满足；当前 blocker/Contract Gap：无。
- 未提交、未推送、未建 PR、未合并。active plan §5 明确“提交须用户另行授权”；本轮按 plan 执行，未收到另行 commit/push 授权。
- 本地 HEAD 与只读 `git ls-remote origin refs/heads/feature/task-6-realtime-state` 均实际返回 `068d80491fb5c9ebefed22a171c2396cfac7deec`。这是既有提交，不是本批新 commit。
- 本批三文件保留在 working tree；本地忽略的 ledger 不提交。
- B7 技术前置已具备，本轮未开始 B7。D6-RECOVERY 的专项 fresh proof 仍是自动恢复/Task 6 最终 acceptance 的独立前置，本批不宣称整个 Task 6 COMPLETE。

后续用户明确指令“提交push”，授权提交并推送本批三文件。提交前重新执行 B4/B5/B6 proof：114 passed；targeted Ruff 与 `git diff --check` 通过。实际 commit SHA 和本地/远端 HEAD 二次核对结果由后续 Git 操作及对话记录提供，不在创建提交前预填。
