# Task 6 Batch 1 — 本地实施验收证据

日期：2026-10-03。仅记录本轮执行证据，不定义或修改合同。

## 真实基准与范围

- 分支：`feature/task-6-realtime-state`。
- 本地 HEAD：`0cf48297e53060eed6b0596b1a85f7d65a0aa694`；开始时 working tree 干净。
- `git ls-remote` 及 fetch 后确认远端 HEAD：`e946663a2f1ab153b822b780bd1cb80c218d7f63`。
- 本地落后远端 2 次提交；差异只有 Task 7 plan 从 plans 移至 archive，生产代码、Spec、Task 6 active plan 无差异。未切换、合并、提交或推送。
- 权威：README 文档顺序、主 Implementation Plan Task 6 / 两项 Gate、Task 6 active plan §4/§5/Batch 1、架构 Spec §12.1–12.2、Library Spec §7.1。
- 本轮实现共同提交/版本/失效登记基础；没有接入领域 producer、snapshot Service/API、observer、socket 或 D6-RECOVERY。

## Contract Matrix Impact Analysis / traceability

新增或修改合同语义：无。实现已有冻结 rows 的 Batch 1 子合同。

| 分类 / Contract ID | Authority | 本轮 delta / preservation / failure / retry | Implementation → executable proof |
|---|---|---|---|
| Owned RT-REVISION-001 interface/core | Library Spec §7.1；架构 Spec §12.1–12.2；active plan §4.2/B1 | SQLite outer commit 后锁释放前登记；每实际变化域最多 +1；改后恢复/no-op/rollback/replay 不增；未变化域和业务状态保留；新 epoch 计数0；登记失败阻止可信 marker | database.py visibility hook + realtime_coordinator.py → `test_committed_data_and_revision_become_visible_together`、`test_outer_delta_is_once_per_domain_and_reverted_content_is_noop`、rollback/terminal/child-task/failure proofs |
| Owned RT-DELIVERY-001 登记隔离 | 架构 Spec §12.2；active plan §4.2/B1 | 只登记内存失效义务；不等待网络；迟到回调重申最新版本；取消不丢最后变化；登记故障使订阅失效，不撤销已提交 DB/terminal | coordinator + database failure hook → reversed-callback、post-commit-cancel、registration-failure proofs |
| Relied TX-ROLLBACK-001 | active plan §4.3；主 Plan Contract Matrix Gate | 同库 outer rollback 与 runtime restore 保持；失败 retry 可重新执行 | `test_child_task_staging_shares_outer_owner_and_does_not_interrupt_runtime_restore`；新文件 rollback/terminal proofs；R-TX |
| Relied TX-IDEMP-001 | active plan §4.3；主 Plan Contract Matrix Gate | 真实 IdempotencyService terminal 与业务同事务；成功 replay 不再调用业务，不增版本或通知 | `test_terminal_failure_and_success_replay_preserve_committed_versions`；R-TX |
| Relied EVENT-PORT-001 | 架构 Spec §12.2；active plan §4.3 | 保持 EventPublisher 异步接口、Library/Output 旧 payload；不引入 socket 依赖或将迟到 payload 当当前状态 | events.py routing + coordinator.publish；reversed-callback proof；R-O/R-ARCH |
| Regression O-EVENT-001 | Output Spec §6.3；active plan §4.3 | 原确认/深复制/outer commit/锁外通知/rollback/replay 合同保持 | `test_output_event_transactions.py`；R-O |

External Confirmation：B1 的新 delta 以真实 SQLite commit 为确认，无新增外部控制；既有 Output 确认语义由 R-O 保持。业务 Queue/History/Playlist/Favorites/playback_state 的不变性由新文件 preservation proof 和历史 invariant regression 验证。

Relationship Gate：**REQUIRED / 本 Batch PASS**。Contract Matrix Gate：**REQUIRED / 本 Batch PASS**。
RT-REVISION-001 整体仍为 PARTIAL，真实 producer final owner 是 B3；RT-DELIVERY-001 整体仍为 PARTIAL，网络交付 final owner 是 B12。没有以此验收整个 Task 6。

## RED → GREEN 与审查修复

均在 production 修改前运行相应 RED selector，读取实际失败，再运行 GREEN：

| Test selector（均位于 test_realtime_commit_visibility.py） | 实际 RED | 最终 GREEN |
|---|---|---|
| `test_committed_data_and_revision_become_visible_together` | 缺少 coordinator 的明确 assertion | 1 passed |
| `test_outer_delta_is_once_per_domain_and_reverted_content_is_noop` | 实际 `(3,2,1)`，期望 `(1,1,1)` | 1 passed |
| `test_staging_owns_content_and_marker_and_notifications_are_independent` | 调用者修改 after 导致 revision 为0 | 1 passed |
| `test_registration_failure_invalidates_subscriptions_and_marker_without_rollback` | 普通异常仍留下 valid 订阅；CancelledError 进入 rollback 并重复 reset token | 2 passed |
| `test_reversed_callbacks_reassert_latest_marker_and_keep_all_pending_domains` | 缺少 event bridge 的明确 assertion | 1 passed |
| `test_any_visibility_registration_failure_blocks_trusted_state` | shared hook / 内容比较故障仍留下 valid 订阅 | 3 passed |
| `test_child_task_staging_shares_outer_owner_and_does_not_interrupt_runtime_restore` | 子 task token 在父 task reset 触发 ValueError；commit marker失效，rollback阻断 runtime restore | 2 passed |

其它新增测试为直接 regression / preservation / retry / cancellation proof；未声称它们首次运行是 RED。

独立只读 reviewer 发现 1 个 Important/P1：子 task ContextVar token cleanup 跨 context；无 Critical、Minor 或 Contract Gap。已按 systematic-debugging 定位到 transaction owner/callback 的任务边界，并通过上述最后一行 RED→GREEN 修复。暂存状态现绑定共享 outer transaction 的 opaque identity，无新业务锁。

附加 database helpers `transaction_identity` 和 `on_transaction_visibility_failure` 仅用于冻结合同所需的共同 owner 与 fail-closed 机制，没有修改既有异步 commit-hook 接口。

审查明确留给后续 owner 的范围：真实 producer delta（B2–6）、完整 snapshot（B7）、observation/lifecycle（B8–9/D6）、HTTP（B10）、订阅 capture/退出（B11）、网络背压/关闭（B12）、重连（B13）。本轮没有发现这些范围内的新 defect，也没有实现它们。

## 修复后的 fresh 验证

所有命令从仓库根目录使用现有 `.venv`，无依赖/环境修改。

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_commit_visibility.py
# 17 passed

.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_lifecycle_injection.py server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# R-TX + R-O + R-ARCH: 125 passed

.venv/bin/python -m pytest -q server/tests
# 753 passed

.venv/bin/python -m compileall -q server
# exit 0

.venv/bin/python -m ruff check server/app/repositories/database.py server/app/services/events.py server/app/services/realtime_coordinator.py server/app/models/realtime.py server/tests/invariants/test_realtime_commit_visibility.py
# All checks passed

git diff --check
# exit 0
```

pytest 有 1 个既有 Starlette/httpx deprecation warning；基线也存在，未修改依赖。期间一次新增 preservation test 用了错误表名；检查 migrations 后仅修正测试表名，再运行精确 selector GREEN，未修改生产逻辑来迁就错误测试。

## Changed-files / isolation / acceptance

- 修改：`server/app/repositories/database.py`、`server/app/services/events.py`。
- 新增：`server/app/models/realtime.py`、`server/app/services/realtime_coordinator.py`、`server/tests/invariants/test_realtime_commit_visibility.py`、本验收证据文件。
- 完整 tracked diff 与新增文件均审查；无额外 production 文件、未来 Batch 功能、合同修改、无关格式化、依赖、环境或数据库文件。
- 本 Batch 实施和本地 automated / relationship / Contract Matrix acceptance 满足；无未关闭 blocker / Contract Gap；没有物理 MPD/Docker/manual gate 属于 B1。
- 初次验收时 active plan §5 要求提交另行授权：当时没有新 commit SHA，也没有 push/PR/merge，本地 HEAD 为上述基准，工作区保留六个预期文件修改。
- B2 的本地 B1 技术前置具备。D6-RECOVERY 仍是原来的后续专项 gate，不被本轮 GREEN 替代。

## 后续提交授权与提交前复核

同日用户明确要求“提交并push”。重新 fetch 后确认远端仍为 `e946663a2f1ab153b822b780bd1cb80c218d7f63`，仅包含上述 Task 7 文档归档变更；本地通过 fast-forward 同步到该提交，保留 B1 六个预期文件修改，没有创建 merge commit。

提交前重新运行 B1 invariant + R-TX/R-O/R-ARCH：**142 passed**；目标 Ruff 与 compileall 再次通过。未修改生产代码，初次验收全套 **753 passed** 的证据保留。最终提交 SHA、working tree 和远端 HEAD 以 Git 二次核对及本次提交报告为准。
