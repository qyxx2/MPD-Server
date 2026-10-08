# Task 6 Batch 4 — 本地实施验收证据

日期：2026-10-03。执行证据，不新增或修改权威合同。

## 实际基准与范围

- 分支 `feature/task-6-realtime-state`；本轮基准及结束 HEAD 均为 `546afe008c45cb07b587fea4ef7bb4a7d2b8339d`；开始时工作树干净。
- `git ls-remote origin refs/heads/feature/task-6-realtime-state` 实际返回同一 SHA。没有 fetch/merge/push/PR。
- README、主 Implementation Plan Task 6 / Relationship / Contract Matrix Gate、active Task 6 plan §4/§5/Batch 4、P §7–8、A §12.1–12.3/§19.5、T5 PB-STOP/HISTORY/TX rows 及实际代码/测试已核对。
- `.venv` 为现有 Python 3.14.4 / pytest 9.1.1 / Ruff 0.16.9；未修改环境、依赖或数据库。
- B1/B2/B3 proof 和 R-PB 基线实际运行：142 passed。未根据旧验收或 checklist 推定前置实现存在。
- 仅新增 pause/seek/stop 的提交传播；没有 Queue-only、current transition、observer、snapshot/API、socket 或 D6 recovery 实现。

## Contract Matrix Impact Analysis / traceability

新增/修改合同语义：无。Relationship Gate 和 Contract Matrix Gate 均 **REQUIRED / 本 Batch PASS**。

| 分类 / Contract ID | Authority | Delta / preservation / failure / confirmation / retry | Implementation → executable invariant → fresh GREEN |
|---|---|---|---|
| Owned RT-PLAYBACK-001 transport | A §12.2；P §7–8；active plan §4.2/B4 | 原操作经 PlayerPort 读取确认，outer commit 才联合登记 playback/history；不改变原领域操作；Queue occurrence/order/revision、Context、Library/Playlist/Favorites 保留；未确认/transport/terminal/取消失败无成功通知；replay 不重复 | playback_service.py 三个 transport 包装、events.py PlaybackChangedEvent / routing → test_transport_event_waits_for_confirmation_and_outer_commit（3 cases）、confirmation_and_commit_barriers（3）、failed_transport（9）、unconfirmed_stop、outer_delta/output_isolation、cancellation（2）、publisher_failure → 文件20 passed |
| Relied TX-ROLLBACK-001 | active plan §4.3；T5 §3.7 | 同库 owning transaction、History active/session rollback；不假装撤销外部作用；失败重试仍沿原合同 | transport terminal/transport/cancel proofs；test_transaction_relationships.py；R-TX GREEN |
| Relied TX-IDEMP-001 | active plan §4.3；T5 §3.7 | terminal 与业务共同提交；失败无terminal；成功 replay 原回执，无新事件/水位/History | transport 主 proof / publisher failure proof；test_idempotency.py；R-TX GREEN |
| Relied EVENT-PORT-001 | A §12.2；active plan §4.3 | 注入 publisher，保留异步 Port；迟到事件只失效不携旧状态覆盖；通知锁外，不依赖网络；失败日志保留提交 | PlaybackChangedEvent + routing；publisher 中独立 Service 读取、事务身份检查；R-O / R-ARCH GREEN |
| Regression PB-STOP-001 | P §7–8；T5 §3.7 | 实际 STOPPED 确认后 disabled AutoPlay / History STOP；未确认无业务或terminal成功；Queue/Context 保留 | test_stop_confirmation.py、test_pre_batch6_corrective.py、transport unconfirmed_stop / barriers；R-PB GREEN |
| Regression PB-HISTORY-001 | P §7–8；T5 §3.7 | History 在所需确认后 finalize；pause/seek 保留 active/session；Stop exactly-once；rollback/replay 无 phantom/duplicate | transport 主 proof / barriers / cancellation / publisher failure；test_playback_relationships.py、test_transaction_relationships.py；R-PB/R-TX GREEN |

共同 U/T/F/I 均沿用 active plan；无新外部确认策略、恢复策略或合同 rows。语义比较排除 PlaybackState 的审计 updated_at，保留 state/current/context/position/autoplay；联合提交只产生联合 domains，改后恢复与实际 no-op 不造内容变化。同步 coordinator staging 登记在锁释放前；publisher 回调在锁外，提交后取消/失败不丢已登记的最后一次变化。

RT-PLAYBACK-001 **整体 PARTIAL**，final owner 仍为 Batch 6，本轮只验收 transport 子范围。

## RED → GREEN / 非预期失败 / 审查

- production 修改前运行指定 selector `test_transport_event_waits_for_confirmation_and_outer_commit`：pause/seek/stop **3 failed**，明确 assertion 为缺少 committed transport propagation；最小实现后同 selector **3 passed**。
- 其余新增用例为 confirmation/preservation/failure/no-op/cancellation regression proof；最终文件 **20 passed**，未声称每个 preservation test 首次运行是 RED。
- 一次非预期测试失败：测试写了不存在的 `disable_output`；读取完整 traceback、PlayerPort 和 MockMPD 后，只修正测试为 `set_output_enabled(0, False)`；精确 failing selector **1 passed**，随后全文件 GREEN。
- Ruff 首轮指出新增 imports 顺序和 dict iteration；只修正本轮新增行，复核 All checks passed。
- 独立只读审查无 actionable findings；其 fresh proof 19 passed；之后新增 publisher-failure preservation test **1 passed**、最终文件20 passed。没有 Critical/Important/Minor 待处理 finding 或 Contract Gap。

## Final fresh verification

所有命令从仓库根目录使用现有 `.venv`：

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_playback_transport.py
# 20 passed

.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_playback_transport.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_playback_service.py server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_lifecycle_injection.py server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# B4 + R-PB + R-TX + R-O + R-ARCH: 249 passed

.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_playback_transport.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_realtime_library.py server/tests/invariants/test_realtime_playlist.py
# B1–B4 proofs before final extra publisher-failure test: 57 passed
# That extra test separately passed; final full suite includes it.

.venv/bin/python -m pytest -q server/tests
# 794 passed

.venv/bin/python -m ruff check server/app/services/events.py server/app/services/playback_service.py server/tests/invariants/test_realtime_playback_transport.py
# All checks passed

.venv/bin/python -m compileall -q server
# exit 0

git diff --check
# exit 0
```

pytest 均只有一个基线已存在的 Starlette/httpx deprecation warning；未修改依赖。没有环境失败、测试未执行或当前 Batch 需要的物理 MPD/Docker/manual gate。

## Changed-files / isolation / completion

- 修改：server/app/services/events.py、server/app/services/playback_service.py。
- 新增：server/tests/invariants/test_realtime_playback_transport.py、本验收证据文件。
- 完整 tracked diff 和新增文件已审查：无其它 production 文件、未来 Batch/Task 行为、合同修改、重复 authority、无关格式化、依赖/环境/DB/runtime artifacts。
- Batch 4 implementation、automated tests、本地环境验证及两项 REQUIRED Gate/acceptance 满足；无当前 blocker/Contract Gap。
- active plan §5 明确“提交须用户另行授权”；本轮未获得另行 commit/push 指令，故未提交。上述 SHA 是既有 HEAD，不是 Batch 4 新提交；四个预期文件保留在工作树。
- Batch 5 的技术前置具备；本轮未开始 Batch 5。D6-RECOVERY 仍是自动恢复启用/Task 6 最终验收的后续 gate，未在本轮验收。
