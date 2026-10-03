# Task 7 Batch 4 — 最外层提交通知与回滚纪律 acceptance

## 实际基线、范围与环境

- 指定分支 `feature/task-7-output-manager`；初始 HEAD `0acb5748e189bf1cd31e1f22d9cabd9343b58298`，工作树干净。重新 fetch 后同名远端 ref 与基线一致。Task 1R `03f4de9`、Task 4 corrective `86975d6` 的 ancestry 检查分别 exit 0。
- 实际读取 Superpowers README、主 Implementation Plan、active Task 7 Plan 的 B4/相关 rows/冻结接口/F4、O §6.2–6.3、A §8.1/12/19.5、P §8、B3 acceptance，以及当前 database/events/output model、真实 transaction/idempotency/event/playlist/playback tests。Task 5 原合同文件已归档，按真实路径 `archive/task-5/2026-09-29-mpd-server-task-5-batch-plan.md` 读取，不假定旧 active 路径存在。
- 使用现有 `.venv`：Python 3.14.4、pytest 9.1.1、Ruff 0.16.9。没有依赖/环境修改，没有 Docker、真实 NAS/MPD 或物理 DAC 操作。
- 完成 B4 共同执行步骤：pre-flight、RED tests、最小 production implementation、focused/invariant/历史 regression、compile/lint/diff/范围与 traceability review。对应主 Plan Step 5 的 lifecycle prerequisite 部分，不将 Task 7 原 Steps 标为整体完成。

## Contract Matrix Impact Analysis / traceability

- Owned：**O-TX-001、O-EVENT-001（基础设施阶段）**。
- Affected existing implementation：**TX-ROLLBACK-001**；不改变原业务语义。
- Relied-upon unchanged：**EVENT-PORT-001、TX-IDEMP-001**。
- Regression：**TX-ROLLBACK-001、TX-IDEMP-001、PB-STOP-001、PB-HISTORY-001、PL-REP-001、PL-COLLECTION-001**。
- Relationship Gate 与 Contract Matrix Gate 均 **REQUIRED**。下表只证明 B4 foundation，不替代 B5/B6 的实际输出 confirmation 或 B8 的完整 API proof。

| ID / 权威 | Expected delta / Must Remain Unchanged | Confirmation / failure / retry | Implementation → executable proof → fresh GREEN |
|---|---|---|---|
| O-TX-001；O §6.2–6.3、A §19.5、active §4.2/B4 | 所属最外层 commit 后才通知；既有业务/terminal 原子性与 rollback runtime/History 不变。SQLite 不获得撤销 MPD 的能力 | B4 使用真实 SQLite terminal witness；不是实际输出命令确认。outer failure、commit failure、提交前 cancellation 无 terminal/通知，retry 可提交；commit 后取消保留 terminal 且真实 IdempotencyService 可 replay | database.py::on_transaction_commit/run_transaction；F4 的 outer rollback/cancel/commit failure、postcommit cancellation/replay tests；显式 B4 gate 15 passed |
| O-EVENT-001；O §6.3、A §12、active §4.2/§5 | `output.changed` 携带源快照的 deep copy；退出所属 DB ContextVar/释放锁后通知；publisher failure 不改变已提交结果 | B4 confirmed snapshot 是 foundation witness，实际 OutputManager emits 仍 pending B5/B6。嵌套不提前发布；rollback/precommit cancel 丢弃；普通同步/异步 callback exception 留可定位日志并隔离；postcommit cancel 可中断交付，不调用 rollback hook | events.py::OutputChangedEvent、database.py callback drain；F4 register 三函数、snapshot/replay tests + repository notification exception tests；15 passed |
| EVENT-PORT-001；A §12、主 Plan dependency rule 6、active §4.3 | 仍经 DomainEvent/EventPublisher；不引入 WebSocket、outbox 或 exactly-once；Library 旧 publication 顺序不变 | publisher 读取同 DB 的已提交 terminal，不死锁；原 Library commit/update/publish 和 DB failure 无事件回归 | F4 + integration/test_task3_events_and_mpd.py；135 passed 的 focused/regression gate 内 |
| TX-ROLLBACK-001；原 Task 5 Matrix、A §8.1/19.5、active §4.3 | 仅增 commit-hook lifecycle；rollback 后 persisted/History active/session 恢复、无 phantom terminal；已提交事实不能被 callback failure/cancel 撤销 | 保留 BaseException rollback、反序 runtime restoration；外部 PlayerPort 副作用独立，retry reconciliation 不变 | test_transaction_relationships.py + commit-hook failure/retry + F4；focused 135 passed 内 |
| TX-IDEMP-001；P §8.6、原 Task 5 Matrix、active §4.3 | 原 fingerprint/scope/status/replay 行为不变；成功 replay 不重复业务/History/通知 | 原失败无 terminal、scope/payload conflict 保持；F4 commit 后取消仍保留可重放的原 status/body | api/test_idempotency.py、test_transaction_relationships.py、F4 postcommit cancellation；focused GREEN |
| PB-STOP-001；P Stop/History、原 Task 5 Matrix | 实际确认 STOP 后才结束 active History/AutoPlay；Queue 保持 | 既有失败恢复与 retry/replay 无 phantom transition；B4 不调用 Stop | test_stop_confirmation.py、R-TX；focused GREEN |
| PB-HISTORY-001；P History、原 Task 5 Matrix | confirmed transition exactly-once；本轮 hook/event 不创建或结束播放 History | 原 confirmation/outer rollback/session restoration/replay 关系保持 | test_playback_relationships.py、R-TX/R-STOP/F3；focused GREEN |
| PL-REP-001 / PL-COLLECTION-001；Library Spec、原 Task 5 Matrix | persisted unavailable membership/order 和 REST 表示不丢失；Collection playable split 不修改 Playlist | 共享 transaction lifecycle 不改变 resource/collection 原合同 | test_playlist_relationships.py；focused GREEN |

逐项核对 Preconditions、Authorities、Delta、Unchanged、External Confirmation、History/Event、Transaction、Failure/Rollback、Retry/Idempotency、Observable Result 和 Proof；没有新增业务 row、修改冻结合同或 Contract Gap。O-TX-001/O-EVENT-001 的最终 integration proof **仍 pending B8**。

## RED → GREEN

1. nested commit hook：目标 test **1 failed**，明确断言缺少 hook（不是 import/environment error）；增加 active-only 注册与最外层提交后 drain，repository focused **5 passed**。其中其它 registration/rollback/cancel/commit-failure cases 是补充 GREEN proof，不冒充独立 RED。
2. notification exception isolation：sync/async 两 case **2 failed**，RuntimeError 从 postcommit 路径泄漏；最小日志/exception isolation 后 repository focused **7 passed**，TX/Event regression **15 passed**。
3. OutputChangedEvent：目标 test **1 failed**，明确缺少 snapshot event；增加固定 event_type 与源 snapshot deep copy 后 **1 passed**。F4/repository 当时 **13 passed**，TX/Event regression **15 passed**。
4. 补充 commit 后取消的两个确定性 case：commit seam 触发取消，以及 publisher Event barrier 后取消，**2 passed**。真实 terminal 保留、rollback callback 未执行、同 key replay 无新增业务/通知；无需额外 production 修改，不记录为新 RED cycle。

每个 production 单元后执行 focused/affected invariant、直接 regression、`git diff --check`/status，GREEN 后才继续。没有 unexpected code/test failure；只有既有 Starlette/httpx deprecation warning，未为消除 warning 更换依赖。

## Fresh verification（repo root / .venv）

所有 pytest 命令的实际前缀为 `.venv/bin/python -m pytest -q`。

| 实际参数 / 命令 | 实际结果 |
|---|---|
| `server/tests/invariants/test_transaction_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_playlist_relationships.py server/tests/api/test_idempotency.py server/tests/integration/test_task3_events_and_mpd.py server/tests/invariants/test_output_serialization.py`（实现前） | 82 passed |
| `server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_output_event_transactions.py`（最终显式 B4/F4 gate） | 15 passed |
| `server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_playlist_relationships.py server/tests/integration/test_task3_events_and_mpd.py server/tests/invariants/test_output_serialization.py server/tests/services/test_output_manager.py server/tests/invariants/test_output_observation.py` | 135 passed；B4 focused + 所有指定历史 rows + B1/B3 直接 regression |
| `server/tests/invariants` | 126 passed；包含 architecture gate |
| `server/tests` | 564 passed；0 failed/errors/skip/xfail |
| `.venv/bin/python -m compileall -q server` | exit 0 |
| `.venv/bin/python -m ruff check server/app/repositories/database.py server/app/services/events.py server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_output_event_transactions.py` | All checks passed |
| `git diff --check` | exit 0 |

独立 read-only reviewer 重新执行 hook/F4 **15 passed**，TX/Event/Playlist/Stop regression **21 passed**，diff check 通过；无 Critical/Important/Minor findings。作者完成 changed-files、future-Batch/future-Task isolation 与逐 row traceability review。Relationship Gate **REQUIRED / PASS（B4 foundation）**；Contract Matrix Gate **REQUIRED / PASS（B4 foundation）**。

### Review 边界裁定

以下是 reviewer declined-to-judge 项的本轮裁定，不新增 Spec 语义或扩大 B4。没有 deferred minor finding。

| Review 项 | 裁定 / 代价 |
|---|---|
| selection、ACK/readback、实际 enable/disable preservation | 保持 B1/B3/B5/B6 owner；本轮仅基础设施，代价是尚无实际启停完成声明 |
| OutputManager 注册通知、失败请求标记清理 | 保持 B5/B6/B8 集成，不造未使用 helper；代价是这些 request 行为仍待实际业务测试 |
| MPD effect 后 API terminal/schema failure | F9/B8 最终 proof；代价是 foundation GREEN 不证明完整 HTTP failure policy |
| About 来源/null | B2/B7 owner，未改变；代价是本轮不重新宣称 About REST 验收 |
| durable/exactly-once、不同事务间 delivery ordering | B4 不承诺这些机制；代价是通知可丢失/交错，后续按 Spec 读取/完整快照恢复 |
| publisher 主动修改 event 内部 nested fields | 冻结接口按 deep-copy ownership/后续 source mutation 隔离验收；未承诺递归 frozen domain models，代价是 publisher 必须将交付 payload 当只读事实 |
| detached child ContextVar、跨 DB nesting | 不改既有 transaction model；计划中的消费者 await 所属 operation，代价是不能据本 proof 宣称 fire-and-forget 或跨 DB atomic notification 安全 |
| physical DAC/live MPD/Docker/whole Task | 不属于 B4 本地验收；代价是没有这些外部/整 Task acceptance 证据 |

B4 acceptance 满足，无 blocker/Contract Gap；可以进入 B5 的独立 pre-flight。Task 7 与 O-TX-001/O-EVENT-001 最终 rows 仍未完成。

## 范围与完成边界

- Production：database.py（提交生命周期）、events.py（OutputChangedEvent）。Tests：新增 test_transaction_commit_hooks.py、test_output_event_transactions.py。Docs：本 acceptance 与 active Task 7 Plan 的事实/归档引用。
- 没有 OutputManager NAS 控制、API/main、幂等策略重写、schema/outbox、播放算法、scanner publication、MPD transport、WebSocket/Task 6、Web/Task 8 或 config/Task 10 改动；没有无关格式化、环境/数据库/缓存文件进入提交。
- 不新增未使用的 OutputManager 请求 rollback/通知 helper；它的调用与实际请求状态只在 B5/B6 实际行为中集成，本轮基础设施接口和 F4 可独立验收。
- 没有真实物理 DAC 验收；B4 foundation GREEN 不声称整个输出合同或 Task 7 已完成。
- 按用户指令提交当前 Batch；active plan 没有明确 push 指令，不执行 push/PR/merge。提交后以实际 Git 输出二次核实 SHA、branch HEAD、changed files、working tree 和同名远端 ref，不在提交内自引用 SHA。
