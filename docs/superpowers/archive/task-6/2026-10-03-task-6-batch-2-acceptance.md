# Task 6 Batch 2 — 本地实施验收证据

日期：2026-10-03。本文件仅记录本轮可复现证据，不增加或修改合同。

## 真实基准与范围

- 当前分支：`feature/task-6-realtime-state`。
- 开始 HEAD：`7a275c0363fafabf7bfe7630dabfc6553fb0fd7f`；working tree 干净。
- 实际读取 README、主 Implementation Plan 的依赖/Gate/Task 3/Task 6、active Task 6 plan 的共同字段/rows/验证集合/Batch 2、Library Spec §7/§7.1、Architecture Spec §7/§12.1–12.2、B1 acceptance，核对代码与历史提交。
- B1 coordinator/visible hooks/proofs 真实存在；前置 fresh regression 30 passed。
- 仅实施 Library 内容版本与扫描完成传播；未增加 Playlist producer、Playback producer、snapshot、observer、HTTP realtime 或 WebSocket。
- 使用原 `.venv`；无依赖、环境、schema、Docker、live MPD 或数据库文件修改。

## Contract Matrix Impact Analysis / traceability

新建或修改合同语义 rows：无。Relationship Gate 与 Contract Matrix Gate 均 **REQUIRED / 本 Batch PASS**。

共同字段沿用 active plan §4.1：未变化域/Queue/PlaybackContext/Playlist/Favorites/History/active/session/terminal/MPD 控制不因传播改变；outer commit 前失败无版本/事件，提交后通知失败不撤提交；retry/replay 沿用原幂等规则。

| 分类 / Contract ID | Authority | Delta、保持、失败/重试/确认 | Implementation → executable proof → fresh GREEN |
|---|---|---|---|
| Owned RT-LIBRARY-001 | Architecture §7/§12.2；Library §7.1；active plan §4.2/B2 | 扫描提交同步登记失效；completion 严守 commit→optional update→event，保留 result/error；不改变源文件、身份匹配与引用；outer failure/cancel 无外部完成作用；update/publisher failure 不撤提交；真实 SQLite commit 是确认，optional MPD update 不是扫描确认 | `LibraryScanner._apply_batch/_finalize` → `test_outer_scan_waits_for_commit_and_keeps_completion_order`、barrier/HTTP/failure/late-completion proofs → 新 invariant 文件10 passed |
| Owned RT-REVISION-001 Library部分 | Library §7.1；Architecture §12.1–12.2 | Service 比较完整持久 Song 资源，排除 last_scanned_at/last_seen_at；同 outer commit 变化最多+1，未变 Playlist 为0；no-op/restore/rollback/cancel/replay 不增；restart 新 epoch/0，不丢持久资源 | `LibraryService.revision_content` → scanner/coordinator.stage_change → `test_content_revision_is_visible_before_optional_update_and_completion`、outer-delta、HTTP replay、late/restart proofs → 新文件10 passed + B1文件17 passed |
| Relied EVENT-PORT-001 | 主 Plan Task3；active plan §4.3 | 原 LibraryChangedEvent result/error、异步 EventPublisher 保持；迟到 completion 只重申最新 marker，不携旧状态覆盖；无 socket 依赖 | 真实 scanner/completion→publisher/coordinator → ordering/late proofs + R-LIB |
| Relied TX-ROLLBACK-001 | active plan §4.3；主 Plan Gate | 同库 outer HTTP terminal failure 回滚扫描；失败/取消清理 staged delta/commit callback，active/session/Queue 保留；失败可重试 | HTTP terminal failure + outer rollback/cancel proofs；R-TX |
| Relied TX-IDEMP-001 | active plan §4.3；主 Plan Gate | 成功 terminal 与扫描同事务；replay 不重扫、不重 update/event/revision | `test_http_terminal_failure_retry_replay_preserve_other_domains`；R-TX |
| Regression Task2R references / PL-REP-001 | Library §7/§9；active plan §4.3/B2 | move/metadata/availability 不删除 Song 身份或 Playlist/Favorites/History 引用；unavailable membership/order 保留，传播不更改其它业务状态 | `test_real_metadata_move_and_availability_preserve_references`、HTTP preservation proof；R-LIB/R-PL |

`RT-LIBRARY-001` 的本 Batch 行为/proof 已验收；`RT-REVISION-001` 整体保持 **PARTIAL**，final owner 为 B3。D6-RECOVERY 仍是后续阶段的独立前置，不被本次 GREEN 替代。

## Step / RED→GREEN

1. RED `test_outer_scan_waits_for_commit_and_keeps_completion_order`：真实独立 SQLite 读见0 Songs，optional update/completion 已在 outer commit 前运行。最小实现把 finalize 注册为 outer post-commit callback。精确 selector 与 Task3 event tests：4 passed。
2. RED `test_content_revision_is_visible_before_optional_update_and_completion`：明确 assertion 指出 scanner 缺少 coordinator 接线。增加 optional coordinator 注入，以及同事务 Service before/after 比较与 staging。精确 selector：1 passed；新文件+B1+Task3：22 passed。barrier 期间独立事务读取新资源/新版本，completion 尚未运行；无变化扫描保留 completion/error，revision不增。
3. 扩展 invariant/regression：真实 media metadata、move、UNREADABLE/MISSING、引用保留、outer rollback/cancel、改后恢复、batch +1、发布失败、提交后取消、HTTP terminal failure/retry/replay、迟到 completion、restart。新文件最终10 passed。这些补充 proof 首次 GREEN 时不冒充 RED。
4. 执行全部 B2 指定 regression、lint/diff 与独立审查；再执行 full suite/compile/architecture 检查。每次 production 修改后重新运行对应 invariant；各阶段 `git diff --check` 与 status 检查通过。

非预期失败均按 systematic-debugging 处理：

- 三个 restore/retry fixture 测试恢复字节后仍改变 `file_mtime_ns`；完整资源 diff 确认唯一差异，fixture 改为恢复原 mtime，保留 no-op/资源相等断言。没有修改生产比较语义。
- HTTP preservation test 最初使用不存在的 `PlaybackService.get_snapshot`；检查实际接口后改为真实 active_event/session/player.status 对比，未改生产接口。
- R-LIB 中9个历史 scanner tests 的 parser fake 缺少实际 transaction 所需 path；读取全部 traceback 后，仅增加 test-only temporary SQLite path fixture，32 tests GREEN。无原断言删除/放宽、无 skip/xfail、无 production fake 专用分支。
- Ruff 首轮仅两个新增 import block 排序错误；fix 限于本 Batch 两个文件，检查 diff 后 scoped Ruff GREEN。

## 最终 fresh 验证

均从仓库根目录使用既有 `.venv` 执行：

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_library.py
# 10 passed

.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_library.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/integration/test_task3_events_and_mpd.py server/tests/repositories/test_library_reconciliation.py server/tests/services/test_library_scanner.py server/tests/api/test_library_api.py server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/invariants/test_playlist_relationships.py server/tests/services/test_playlist_service.py server/tests/api/test_playlist_reads.py
# B2 + B1 + R-LIB/R-TX/R-PL: 125 passed

.venv/bin/python -m pytest -q server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# R-ARCH: 3 passed

.venv/bin/python -m pytest -q server/tests
# 763 passed, 48.48s

.venv/bin/python -m compileall -q server
# exit 0

.venv/bin/python -m ruff check server/app/services/library_scanner.py server/app/services/library_service.py server/tests/services/test_library_scanner.py server/tests/invariants/test_realtime_library.py
# All checks passed

git diff --check
# exit 0
```

pytest 唯一 warning 是基线已有的 Starlette/httpx deprecation；无 dependency/environment failure。full suite 不替代上述 REQUIRED proofs。

## 审查 / changed files / isolation

独立只读 reviewer 检查实际 diff、新文件、Spec 与 Batch scope；Critical/Important/Minor/Contract Gap 均0。最终隔离审查保留 B3双域版本、B7聚合/History表示、B9 observer/装配、B11–13网络/重连的后续所有权；未提前实现这些行为。原 parser/身份匹配逻辑未修改。

实际改动：

- `server/app/services/library_scanner.py`：共同提交边界、content staging、post-commit finalize。
- `server/app/services/library_service.py`：语义比较视图，复用现有 Repository.list_songs 完整读取，不增加重复 Repository reader。
- `server/tests/services/test_library_scanner.py`：仅直接受影响 fake 的8行 transaction fixture。
- `server/tests/invariants/test_realtime_library.py`：新增 B2 executable proofs。
- 本 archive acceptance 证据文件。

完整 tracked diff 和新增文件均审查。无无关格式化/重构、未来生产实现、重复权威合同文档、环境/依赖/DB/cache 文件。

本 Batch implementation、自动化、本地环境验证与两项 REQUIRED Gate acceptance 满足；无未关闭 blocker/Contract Gap；B3的本地技术前置具备。无本 Batch 必需但未运行的物理 MPD/Docker/manual gate；不宣称 Task6 完成。

## Git 与提交边界

本轮未 commit/push/PR/merge。active plan §5 明确“提交须用户另行授权”；本次按 plan 实施未包含该另行授权，工作区保留以上五个预期文件。

本轮结束再次验证本地 branch HEAD 与 `git ls-remote origin refs/heads/feature/task-6-realtime-state`：均为 `7a275c0363fafabf7bfe7630dabfc6553fb0fd7f`。这是既有提交，非本轮新增 SHA。

## 后续提交授权与提交前复核

同日用户明确要求“提交push”。提交前重新核对分支、HEAD、working tree、完整改动范围和远端 ref；远端仍为上述基准，与本地一致。

重新运行 B2+B1+R-LIB/R-TX/R-PL/R-ARCH：**128 passed**；目标 Ruff、compileall、diff-check 再次通过。生产和测试代码未新增修改；前述 full suite **763 passed** 证据保留。只提交上述五个预期文件；最终 commit SHA、本地及远端 HEAD 与 working tree 状态以提交后 Git 二次核对和本次提交报告为准。
