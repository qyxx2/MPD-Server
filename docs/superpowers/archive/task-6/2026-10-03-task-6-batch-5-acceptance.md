# Task 6 Batch 5 — 本地实施验收证据

日期：2026-10-03。仅执行证据，不新增或修订权威合同。

## 基准、范围与 Pre-flight

- 开始：`feature/task-6-realtime-state`，HEAD `abc0c6c29c982a80d9a8de04eda3305117040c0c`，工作树干净；核对真实 Git history 与当前代码，未根据旧摘要或 checklist 推定实现完成。
- 读取 README、主 Implementation Plan Task 6 / Relationship / Contract Matrix Gate、active Task 6 plan §4–6/B5、P §2/3.3/5.2/6–8、A §5/12.1–12.2/19.5、T5 §3.7 PB/TX rows、B4 acceptance 与直接代码/测试。
- 环境：现有 `.venv`，Python 3.14.4、pytest 9.1.1、Ruff 0.16.9；读取 server/requirements.txt，无依赖或环境修改。
- fresh 基线：B1/B2/B3 proof 文件 38 passed；B4 transport + playback/transaction invariant 文件 43 passed。
- 范围：play_next/add_to_queue/reorder/clear/pending delete 的确认后提交传播；仅修改 PlaybackService。QueueManager 无需修改。没有 current transition、snapshot、observer、socket、D6 或未来 Task 实现。

## Contract Matrix Impact Analysis / traceability

Relationship Gate 与 Contract Matrix Gate 均 **REQUIRED**。新增/修改合同语义 rows：无。RT-PLAYBACK-001 全 row 仍 **PARTIAL**，final owner 为 B6。

| 分类 / ID | Authority | Delta / unchanged / confirmation / failure / retry | Implementation → executable proof → 本轮 GREEN |
|---|---|---|---|
| Owned RT-PLAYBACK-001 queue-only | A §12.2；P §3.3/5.2/6/8；active §4.2/B5 | 原 pending mutation 已确认后暂存 Queue before/after，outer commit 联合登记；Queue CAS 策略不变；current occurrence/state/context、History active/session、Library/Playlist/Favorites 保留；确认/terminal/取消失败不发布，replay 不重发 | PlaybackService queue decorator、reorder/clear/pending-delete staging、按域合并 first-before/last-after → test_queue_only_notification_preserves_current_occurrence_and_history（5）、joint queue/transport（2）、barriers（5）、failure/availability/cancel/CAS/publisher proofs → B5 文件48 passed |
| Relied TX-ROLLBACK-001 | active §4.3；T5 §3.7；A §19.5 | owning SQLite transaction + runtime History 回滚；失败无成功 terminal/通知；不假装撤销外部 PlayerPort side effect，retry 沿既有 sync | terminal failure/retry（5）、cancellation（2）、unconfirmed（15）；test_transaction_relationships.py → R-TX19 passed |
| Relied TX-IDEMP-001 | active §4.3；T5 §3.7 | 业务与 terminal 同事务；失败 retry，成功 replay 原回执，不重复 Queue/History/event | 主 proof、terminal retry/replay、publisher failure；test_idempotency.py → R-TX19 passed |
| Regression PB-INSERT-001 | P §3.3/8；T5 §3.7 | 独立 execution occurrence；preserve current/state/context/History，实际 PlayerPort 确认；失败回滚/可 retry | B5 主 proof insert cases + wrong-current/status/retry；test_insertion_rejects_actual_playback_divergence_and_can_retry → R-PB104 passed |
| Regression PB-REORDER-001 | P §5.2/8；T5 §3.7 | execution order 同步、retained pending engine IDs 保留；current/History/context 不变；CAS 在外部副作用前拒绝 | B5 主 proof/revision conflict/barriers；historic duplicate occurrence invariants → R-PB104 passed |
| Regression PB-DELETE-PENDING-001 | P §5.2/6/8；T5 §3.7 | 删除精确 occurrence、原 AutoPlay refill 保留；current/History/context 不变；失败无 partial success | B5 pending delete/clear、current availability、terminal rollback proofs；historic pending invariants → R-PB104 passed |

传播仅采用 queue domain，不伪造 playback/history delta；联合 Queue+seek 在一个提交中包含 queue/playback，无中间通知。Library/Playlist revisions 不因 Queue 操作递增。

## RED → GREEN 与失败诊断

1. 主 selector 五个操作初次全部 RED：成功 REST mutation 后 subscriber.pending 仍为 None，目标提交登记缺失。
2. 最小接线后逐操作 GREEN：插入两例2 passed、reorder1、clear1、pending delete1；B4 transport20 passed；直接相关历史 occurrence/insert6 passed、clear1 passed。
3. 测试假设诊断：初版把 pending engine ID 在 insertion/retry 中的连续性也当作 PB-INSERT 约束。冻结 row 只要求 current 不变；PB-REORDER/DELETE 才明确 retained pending engine identity。成功 proof 保留每个操作的 occurrence bijection/current 检查，并按该 row 检查 retained IDs；terminal rollback/retry 独立证明，避免假设 SQLite 能撤销 MPD。未改变原领域动作或已有测试。
4. joint Queue+seek 两个顺序均 RED：coordinator 已登记，但 B4 DomainEvent 累积器替换 after-map，post-commit KeyError 丢事件。最小按域合并 first-before/last-after 后2 passed；保留 executable invariant，B4 regression20 passed。
5. 扩展确认/outer commit 屏障、unavailable/status/错误 occurrence、MISSING/UNREADABLE、取消、revision conflict、publish failure/replay：全文件48 passed。

## Batch Final Gate 实际命令

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_queue.py::test_queue_only_notification_preserves_current_occurrence_and_history
# 5 passed

.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_queue.py
# 48 passed

.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_queue.py server/tests/invariants/test_realtime_playback_transport.py server/tests/invariants/test_realtime_commit_visibility.py
# 85 passed

.venv/bin/python -m pytest -q server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_playback_service.py
# R-PB: 104 passed

.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py
# R-TX: 19 passed

.venv/bin/python -m pytest -q server/tests
# 842 passed

.venv/bin/python -m ruff check server/app/services/playback_service.py server/tests/invariants/test_realtime_queue.py
# All checks passed

.venv/bin/python -m compileall -q server
# exit 0

git diff --check
# exit 0
```

pytest 仅有一条既有 Starlette/httpx deprecation warning。第一次 Ruff 发现新测试 import layout I001；仅手工调整该 import，复跑通过。无环境失败、未执行的本 Batch 必需测试或物理 MPD/Docker/manual gate。

## Changed-files / completion / Git

- 修改：server/app/services/playback_service.py（29新增/1删除实质接线；无领域状态机修改）。
- 新增：server/tests/invariants/test_realtime_queue.py；本验收证据文件。
- 完整 production diff、新测试全文及 evidence 审查：无其它 production 文件、未来 Batch/Task 行为、合同修改、重复 authority、无关格式化、环境/依赖/DB/runtime artifacts。
- 独立只读 code review：无 Critical/Important 或 production defect；独立复跑 B5+B4+B1 85 passed、R-PB+R-TX123 passed、Ruff/diff check通过。审查员在真实临时fixture中额外验证延迟callback期间第二次Queue mutation，再释放/取消旧writer，两例通过。
- Deferred minor：上述双writer屏障仍是独立审查临时检查，未固化到B5测试文件；B1已有coordinator race保护、B5已有producer cancellation保护。审查定级为非阻断测试强化建议，本批不追加实现。
- Review scope ruling：current transitions、snapshot/observer/WS/D6/物理MPD属于未来或独立gate，均不由本批结论验收；不宣称整个历史feature分支完成。误把本批GREEN当成这些能力通过会漏掉后续门禁，故保留全部义务。
- 本批 implementation、automated tests、本地环境验证、changed-files/isolation review、两项 REQUIRED Gate 与 Batch acceptance 已满足；无当前 blocker/Contract Gap。
- 本地 HEAD 与只读 `git ls-remote origin refs/heads/feature/task-6-realtime-state` 均实际返回 `abc0c6c29c982a80d9a8de04eda3305117040c0c`。
- active plan §5 明确“提交须用户另行授权”；当前请求按 active plan 执行，未提供另行 commit/push 指令。因此未提交/未推送/未建 PR/未合并；该 SHA 是既有 HEAD，不是本批新提交。预期三文件保留在工作树。
- B6 的技术前置由本批 tests/proofs 提供；本轮未开始 B6。D6-RECOVERY 仍为自动恢复启用/Task 6 最终 acceptance 的独立门禁，本批不关闭该义务。
