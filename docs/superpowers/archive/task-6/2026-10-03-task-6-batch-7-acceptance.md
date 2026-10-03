# Task 6 Batch 7 acceptance — 本地完整快照与 History availability

日期：2026-10-03。范围：active Task 6 plan Batch 7（主 Plan 原 Step 1 的当前 Batch scope）。本文件保存真实执行证据，不新增业务语义、Contract row 或平行 authority。

## 基线、读取与环境

- 真实分支 `feature/task-6-realtime-state`；开始时 HEAD `3413f265abe1e9c2d3d710a492a3f0d16f741320`，working tree 干净。已读取实际 commit history、相关 commit stat，而非依赖窗口摘要或勾选状态。
- 实际读取 `docs/superpowers/README.md`、主 Implementation Plan 的 Task 6/Dependency/Relationship/Contract gates、active Task 6 plan 的 Matrix/Batch 7/回归命令、Architecture Spec §12.1/§12.3、Playback Spec §2.2.1、Library Spec §7.1、T5 frozen PB-HISTORY/PL-REP/PL-COLLECTION rows、B6 acceptance，以及直接涉及的真实代码/测试。
- 前置 B1/B2/B3/B6 的 commit visibility、Library、Playlist、current/history proof 在当前 checkout 重新运行：84 passed。历史 acceptance 不替代此次执行。
- 使用 executing-plans、test-driven-development、systematic-debugging、verification-before-completion、requesting/receiving-code-review；保留用户指定 checkout/branch 和既有 `.venv`。
- 环境实际验证：Python 3.14.4，pytest 9.1.1，Ruff 0.16.9；已读取 `server/requirements.txt`。无环境/依赖/schema 变更，无 Docker、live MPD 或物理 NAS/DAC 验证。

## 实施前 Contract Matrix Impact Analysis

- Owned：**RT-SNAPSHOT-001 local**、**RT-HISTORY-001 final**。
- Relied-upon unchanged：**RT-REVISION-001、PL-REP-001、TX-ROLLBACK-001、TX-IDEMP-001**。
- Regression：**PB-HISTORY-001、PL-COLLECTION-001**。
- Relationship Gate：**REQUIRED**。Contract Matrix Gate：**REQUIRED**。
- 新增/修改 frozen 业务语义 rows：0。Contract Gap：0。

下表是对已冻结 rows 的实施影响/证据索引，语义 authority 仍为 Spec 和 active plan §4.1/§4.2/§4.3：

| Contract | Expected Delta / Must Remain Unchanged | Confirmation / Failure-Rollback / Retry | Executable proof / fresh evidence |
|---|---|---|---|
| RT-SNAPSHOT-001 local | 聚合完整、深复制的本地字段与 matching marker；不改 Queue occurrence/order/CAS/context、Playback、History、Playlist/Favorites、terminal 或 MPD 控制 | Service 的同库已提交切面；无外部原子性声明；本地必需读取失败整体失败；重读不重放 mutation；pending outer owner 不可导出成功 snapshot | `test_snapshot_is_one_committed_cut`、逐域 failure、deep-copy、empty/unknown、mutation/capture barriers、reader cancel、nested-owner regression；snapshot 文件 16 passed |
| RT-HISTORY-001 | has_entries 仅由持久事件存在性决定；active/session 独立；不按 playable 过滤或修改事件身份/reason/times/session、Queue Played | SQLite 已提交事实；无 MPD 确认要求；失败不冒充 false；rollback/cancel 恢复 runtime/持久态；重复读取不造事件 | `test_history_unavailability_preserves_events_and_has_entries`；snapshot 中 active-only/rollback/cancel/独立 availability barrier/failure；两个文件合跑 17 passed |
| RT-REVISION-001 | snapshot 的 epoch/sequence/Library/Playlist revisions 与本地切面匹配；read 不增加计数 | outer commit 可见登记；no-op/rollback/replay 原保证不变；无跨 epoch 大小推断 | joint mutation/capture barrier，read preservation，rollback/cancel；前置 Library/Playlist/commit proof 84 passed，完整 suite 905 passed |
| PL-REP-001 / PL-COLLECTION-001 | unavailable resource membership/order 保留；仅 Collection 进行 playable split，snapshot 不套用其过滤 | 原 Service/Repository 资源合同；原失败/幂等规则不变 | scanner/history proof 保留 Playlist/Favorites；R-PL（包含 playlist relationship invariant），包含于 final regression 151 passed |
| TX-ROLLBACK-001 / TX-IDEMP-001 | 业务/terminal/runtime 原 outer owner 保留；read 不新增 terminal；无 phantom History | outer exception/cancel rollback；retry 重读当前事实；terminal replay 不重做业务 | mutation-before-capture、nested-owner、terminal/read preservation；R-TX，包含于 final regression 151 passed |
| PB-HISTORY-001 | confirmed transition 的永久/active History 原身份、reason、时间、session 保留；scan/read 不制造播放事件 | 原 PlayerPort 确认与 joint commit；原失败、retry/replay 恰一次保证 | real scanner/API permanent events 比较；R-H/R-PB（包含 playback relationship/stop confirmation），包含于 final regression 151 passed |

## 实际执行与 RED→GREEN

1. 前置 authority/真实代码/Git/环境/合同与最小 baseline 核对完成；两项 Gate 分类均 REQUIRED。
2. 创建两个指定 selector，分别运行：snapshot **RED 1 failed**（StateService 缺失的明确断言）；history **RED 1 failed**（get_availability 缺失的明确断言）。不是 import/依赖错误。
3. 最小实现：四个 DTO；QueueManager.get_snapshot；HistoryService.get_availability（共同事务读取 persisted + runtime，深复制）；StateService.get_full_snapshot（共同 capture 边界，current Song 不过滤 availability，必需读取失败整体失败，最终 DTO 深复制）。两个指定 selector 分别 **GREEN 1 passed**。
4. 新增 executable preservation/proof：空态/active-only、同 Song 多次播放、scanner UNREADABLE/MISSING/恢复、current unavailable occurrence、逐本地域错误、required current reference 缺失、两方向 capture/mutation barrier、runtime/持久 rollback/cancel、读操作无控制副作用/无计数或 terminal delta、reader cancellation 释放边界、完整 Output request/stale/null 表示。初步 focused 16 passed；R-H/R-PL/R-TX/R-ARCH 47 passed；R-PB 104 passed；初步完整 suite 904 passed。
5. changed-files/独立 review 时，确认 nested-owner committed-cut defect：run_transaction 会复用调用者的 pending write owner，snapshot 可以导出 pending current/history + 旧 marker。新增 `test_snapshot_rejects_an_uncommitted_owner_instead_of_exposing_phantom_success` **RED 1 failed**（DID NOT RAISE）。只在 StateService 公共入口加 active owner 检查；拒绝不可信 nested capture，内部 Service reads 仍在 StateService 新建的 capture 内嵌套。精确 selector **GREEN 1 passed**。独立 reviewer 复核关闭该 Important finding，无剩余 Critical/Important/Minor。
6. 修复后重跑 focused、全部指定及直接受影响的历史回归、完整 suite、scoped lint/compile/diff/isolation review；结果见下表。每个实现阶段检查 diff/status；只有真实 GREEN 才进入下一阶段。

非预期失败：初版 barrier fixture 的相对 URI 不属于 scanner 指定临时 root，错误期待 MISSING。systematic debugging 读取 scanner/root-prefix reconciliation 查明 fixture 假设错误；只将测试 fixture URI/MockMPD 移入该临时 root，保持断言，不改 production scan 规则。Ruff 首次发现 QueueManager 新 import 需要多行格式，局部手工修正；未全库自动格式化。

## 实现范围与设计裁定

StateService 的 Output 输入是必需注入的同步 cached OutputSnapshot provider，在 capture 边界内消费并深复制；测试使用真实 OutputManager 返回的完整状态，包括 stale/null 和 last_request。无 capture-time 外部读取。实际 OutputManager cache facade、observation 接线与生命周期属于 B9，未提前修改 OutputManager/main。B7 两个 observation DTO 初值均 unknown，observed_at/null、matches_current=null、reconciliation_required=false，不伪造进度或 MPD 事实。

公共 get_full_snapshot 必须拥有新的只读边界；任意已有 owner 不足以证明已提交切面，因此 fail-fast，而不是等待自己的锁或猜测 dirty 状态。未来 B11 如需 trusted capture/handoff 入口，必须在其 scope 内证明只读边界；本批未提前添加该机制。

Context 仅沿用 PlaybackState/Queue 的 playback_context_id 和权威顺序。LibraryService 已有 identity-preserving get_song，无需修改。无 socket/API/observer loop、自动 recovery 或未来 Task 代码。

## 修复后 fresh 验证

所有命令从仓库根目录执行，使用既有 `.venv/bin/python`：

| 命令 | 实际输出 |
|---|---|
| `-m pytest -q server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_realtime_library.py server/tests/invariants/test_realtime_playlist.py server/tests/invariants/test_realtime_transitions.py`（实施前） | 84 passed |
| `-m pytest -q server/tests/invariants/test_realtime_snapshot.py::test_snapshot_is_one_committed_cut` | RED 1 failed → GREEN 1 passed |
| `-m pytest -q server/tests/invariants/test_realtime_history.py::test_history_unavailability_preserves_events_and_has_entries` | RED 1 failed → GREEN 1 passed |
| `-m pytest -q server/tests/invariants/test_realtime_snapshot.py::test_snapshot_rejects_an_uncommitted_owner_instead_of_exposing_phantom_success` | RED 1 failed → GREEN 1 passed |
| `-m pytest -q server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_history.py` | **17 passed** |
| `-m pytest -q server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/repositories/test_task2_steps_5_7.py server/tests/invariants/test_playlist_relationships.py server/tests/services/test_playlist_service.py server/tests/api/test_playlist_reads.py server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_playback_service.py`（R-H/R-PL/R-TX/R-ARCH + R-PB） | **151 passed** |
| `-m pytest -q server/tests` | **905 passed**，47.04s |
| `-m ruff check server/app/models/realtime.py server/app/services/history_service.py server/app/services/queue_manager.py server/app/services/state_service.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_history.py` | All checks passed |
| `-m compileall -q server` | exit 0 |
| `git diff --check` | exit 0 |

每次 pytest 有 1 条既有 Starlette TestClient/httpx deprecation warning；无环境失败、skip、xfail 或未报告最终失败。初步 904 GREEN 已由修复后 905 fresh GREEN 替代。全套 GREEN 不替代显式关系/合同门禁。

## Traceability / review 结论

- RT-SNAPSHOT-001 local → Architecture §12.1/§12.3 → FullStateSnapshot/StateService/QueueManager facade/Library 既有 get_song → snapshot committed-cut、nested-owner、失败、复制、空态与 preservation proof → 本轮 snapshot 16 + 两文件 17 GREEN。
- RT-HISTORY-001 final → Playback §2.2.1 → HistoryAvailability/HistoryService + 真实 scanner/Library/API → history unavailable proof 与 availability read/rollback barriers → 本轮两文件 17 + R-H regression GREEN。
- RT-REVISION/PL-REP/TX-* 与 PB-HISTORY/PL-COLLECTION → Library §7.1、active Matrix/T5 frozen rows、既有领域 authority → 原 producer/repository/transaction/idempotency/Collection 实现（未改语义）→ 前置 proof、scanner/Queue/runtime preservation、新 invariant 与历史 relationship tests → 本轮 84/17/151/905 GREEN。
- Relationship Gate：**PASS**；Contract Matrix Gate：**PASS（B7 scope）**。RT-HISTORY-001 的 B7 final owner 满足；RT-SNAPSHOT-001 仅本地部分满足，外部/API/最终恢复仍待 B8–10/13，不声明整个 row/Task 6 完成。
- 独立 reviewer 的未来范围 declined 项逐项保持隔离：B1/B2 producer/callback completion、B8 occurrence/progress、B11 transmission/handoff、B12/13 背压/隔离、B9 Output cache、B10 HTTP 503、B13 recovery final；本批无对应生产 delta。D6-RECOVERY 仍是自动恢复启用和 Task 6 final acceptance 的独立前置。

## 实际 changed files 与 Git 状态

完整 tracked diff 与全部新文件已审阅。仅七文件：

- `server/app/models/realtime.py`：四个 required DTO。
- `server/app/services/queue_manager.py`：get_snapshot facade。
- `server/app/services/history_service.py`：get_availability facade。
- `server/app/services/state_service.py`：63 行 capture/committed-boundary 聚合。
- `server/tests/invariants/test_realtime_snapshot.py`：新建 snapshot invariant proof。
- `server/tests/invariants/test_realtime_history.py`：新建 scanner/History/API invariant proof。
- 本 archive acceptance：执行证据。

无无关格式化/refactor、无 future Batch/Task 实现、无合同语义修改或平行权威文档、无依赖/schema/环境/DB/runtime artifact 变更。忽略的本地 ledger 不提交。

B7 implementation、automated tests、本地环境验证、acceptance 与两项 REQUIRED Gate 满足。当前 blocker/Contract Gap：无。B8 技术前置具备，本轮未开始 B8。

未 commit/push/PR/merge。active plan §5 原文“提交须用户另行授权”，本次指令要求按该 plan 执行，没有另行 commit/push 指令。既有本地 HEAD 和只读远端 `refs/heads/feature/task-6-realtime-state` 核对均为 `3413f265abe1e9c2d3d710a492a3f0d16f741320`；该 SHA 是 B6 基线，不是本批 commit。七文件保留为未提交改动。

后续用户明确指令“提交push”，授权提交并推送上述七文件。提交前重新运行 B7 两个 invariant 文件：17 passed；scoped Ruff 和 diff 检查通过，完整实际文件内容与范围复核无新增实现改动。实际 commit SHA、本地/远端 HEAD 和 clean working tree 的二次核对结果由后续 Git 操作及对话记录提供，不在创建提交前预填。
