# Task 6 Batch 11 acceptance — WebSocket initial → live 交接

日期：2026-10-04（Asia/Shanghai）。仅记录当前执行证据，不新增合同或平行权威文档。

## 真实基线 / authority / scope

起始分支 `feature/task-6-realtime-state`，HEAD `1dc865cef571e2baf342ba94278d8eb7add45ab3`，working tree 干净；核对 status/branch/HEAD/log 与 HEAD 的六个 changed files。按用户指定 checkout/branch 原地执行，不创建环境/worktree，不根据旧 handoff、勾选或 ledger 推定完成。

已读 README、主 Implementation Plan Global Constraints/Task6/Dependency/Relationship/Contract Matrix Gate、active Task6 plan Matrix/§5/B11及B12/B13边界；A §12.1–12.3/§19.5，L §7.1，P §2.2.1/§8.8；B10 acceptance仅作历史定位，并重新读取真实 coordinator/StateService/DTO/router/dependencies/main、transaction hooks、fixtures及B1/B7/B10 proofs。前置 API/B1/B7 fresh 48 passed。

Skills：using-superpowers、executing-plans、using-git-worktrees（用户指定既有checkout优先）、test-driven-development、systematic-debugging、verification-before-completion、requesting-code-review。既有 `.venv` 为 Python3.14.4/pytest9.1.1/Ruff0.16.9；读取 server/requirements.txt，无依赖或环境修改。

## Contract Matrix Impact Analysis / traceability

- Owned：**RT-CONNECT-001 final**。
- Relied-upon unchanged：**RT-SNAPSHOT-001、RT-REVISION-001、RT-DELIVERY-001**。
- Regression：**EVENT-PORT-001、TX-ROLLBACK-001、TX-IDEMP-001**；执行指定 R-TX/R-ARCH，并加原 event integration/output-event proofs。
- Relationship Gate：**REQUIRED / PASS（B11 scope）**。
- Contract Matrix Gate：**REQUIRED / PASS（B11 scope）**。
- 新增/修改 frozen Contract rows：0。Contract Gap：0。RT-DELIVERY final owner仍B12；完整RT-SNAPSHOT/RECOVER final owner仍B13。

| ID → authoritative Spec | implementation / Expected State Delta | Must Remain Unchanged / Confirmation / Failure-Retry | invariant proof → fresh GREEN |
|---|---|---|---|
| RT-CONNECT-001 → A §12.2 | coordinator.subscribe_committed → StateService capture → RealtimeConnections initial/live；共同DB边界先登记订阅，首帧水位过滤已覆盖通知；API传入原public snapshot DTO encoder | U：读取/发送/重试不改变Queue occurrence/CAS/context、History/active/session、Playlist/Favorites、MPD控制及terminal；只消费Service cache，无socket→Port；本地capture/登记失败1011且无成功snapshot，清理后重新读取 | test_last_mutation_during_initial_send_is_not_lost；四个register/capture窗口；失败/retry/no-I/O、registration rollback、ASGI cleanup proof；B11两文件13 passed，含真实SQLite/Services/MockPort与屏障 |
| RT-SNAPSHOT-001 → A §12.1–12.3 | 首帧public state与GET同DTO/完整语义；epoch/sequence与state一致 | 沿用Service联合已提交切面，本地必需域失败整体失败；unknown/stale/null不伪造MPD确认，重读无业务replay | B11 API完整GET parity/1011 retry、B7 snapshot、B10 API → 61 passed集合；whole row不在B11宣称final |
| RT-REVISION-001 → L §7.1 / A §12.2 | 消费原epoch/sequence/revisions；迟到领域callback仅重申当前marker，live严格递增 | 不修改原delta/no-op/rollback/replay策略、Queue CAS；网络不持DB锁、不撤提交 | B1 17 tests；真实Playlist两个提交/逆序callback通知proof、API terminal replay proof → 61 passed集合 |
| RT-DELIVERY-001 core → A §12.2 | 每订阅64帧有界queue，同步put_nowait；独立连接sender与disconnect receiver；网络锁外，默认10秒send budget | 原已提交业务/terminal保留；普通disconnect/ASGI取消await子任务且注销；完整overflow/timeout/isolation验收仍由B12承担 | B1登记隔离、B11send屏障/普通取消清理proof → 61 passed集合；row仍PARTIAL到B12 |
| EVENT-PORT-001 → A §5/§7/§12.2、active继承row | 原DomainEvent→coordinator桥保留，连接不反向接入领域producer | 原Library/Output payload/commit-confirm语义保持；允许冗余失效，不允许迟到payload改版本；无业务重放 | integration/test_task3_events_and_mpd.py、invariants/test_output_event_transactions.py → 33 passed regression集合；真实Playlist迟到callbackproof |
| TX-ROLLBACK/IDEMP-001 → active继承rows及原T5合同 | 仅增加订阅登记事务的runtime rollback cleanup；HTTP mutation terminal流程保持 | 提交前失败不留订阅/成功通知；提交后交付/取消不撤数据/terminal；成功replay无新版本/资源 | failed-registration SQLite proof、WS真实HTTP replay；R-TX → 33 passed regression集合 |

## Step / RED→GREEN / debugging

1. 实际Git/authority/环境/前置测试、Contract pre-flight完成；无重设计Task或后续Batch。
2. 指定 handoff selector **RED1**：连接manager不存在；最小coordinator有界queue与manager后 **GREEN1**；全文件+B1 **18 passed**。
3. WS endpoint selector **RED1**：路由不存在，连接关闭1000；新增固定WS路由/public DTO encoding后 **GREEN1**。完整endpoint文件最终 **3 passed**。
4. 增强四个register/capture屏障、失败1011/retry、真实Playlist逆序callback和无外部I/O/业务副作用proof；这些首次GREEN的扩展不冒充独立目标RED。
5. 新测试曾错误假设AutoPlay只保留三项、fixture新StateService自动共享root coordinator、一次提交只有一个通知、空态已创建Favorites；依据真实服务/fixture/合同纠正测试输入和明确断言，不改领域production或旧测试，不将setup错误计作目标RED。
6. 审查发现订阅已加入集合但登记read transaction commit失败时connect尚未接管：新增真实SQLite RejectCommit invariant **RED1**，留下孤儿订阅。subscribe_committed注册原rollback hook注销该订阅，精确selector **GREEN1**；B11+B1 **29 passed**。
7. 首次扩展full suite **1 failed / 963 passed**，失败为新API test_initial_local_read_failure_closes_1011_and_unsubscribes在第二次WS退出时concurrent.futures.CancelledError。读取完整trace及已安装Starlette TestClient，确认ASGI AnyIO重复取消打断finally的gather清理。新增确定性AnyIO cancellation invariant **RED1**（receive cleanup checkpoint未完成）；仅在manager finally使用既有anyio.CancelScope(shield=True)，保留取消传播。该selector **GREEN1**、原失败API selector **GREEN1**；增强assert全部child tasks退出；B11+B1最终 **30 passed**。无环境/依赖变更，不提前完成B12故障矩阵。
8. 执行focused→proof→R-TX/R-ARCH/event历史回归及最终full suite；各阶段diff --check/status；最终scoped Ruff/compile通过。
9. fresh-context只读reviewer审查全部五个代码/测试文件，最终无Critical/Important/Minor findings；独立复核B11/B1、最后取消proof及原失败API selector、Ruff/diff。没有编辑/提交。
10. changed-files及traceability/future-scope审查完成；三个生产文件新增152行、删除10行，在B11预估范围内；未改其他生产模块或旧测试。

## Fresh final commands

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_handoff.py server/tests/api/test_realtime.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/api/test_realtime_state.py server/tests/invariants/test_realtime_snapshot.py
# 61 passed，3.83s（B11 13 + B1 17 + B10 15 + B7 16）

.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories server/tests/integration/test_task3_events_and_mpd.py server/tests/invariants/test_output_event_transactions.py
# 33 passed，1.23s

.venv/bin/python -m pytest -q server/tests
# 修复后最终966 passed，49.27s

.venv/bin/python -m ruff check server/app/api/realtime.py server/app/services/realtime_coordinator.py server/app/services/realtime_connections.py server/tests/api/test_realtime.py server/tests/invariants/test_realtime_handoff.py
# All checks passed
.venv/bin/python -m compileall -q server
# exit0
git diff --check
# exit0
```

pytest仅1条既有Starlette TestClient/httpx deprecation warning。没有剩余测试/环境失败。未进行live MPD、Docker、NAS/DAC或reverse proxy验证；这些不属于B11本地验收。Full suite不替代已显式完成的relationship/Contract Matrix gates。

## 实际文件 / acceptance / Git二次确认

- `server/app/api/realtime.py`
- `server/app/services/realtime_coordinator.py`
- `server/app/services/realtime_connections.py`（新）
- `server/tests/api/test_realtime.py`（新）
- `server/tests/invariants/test_realtime_handoff.py`（新）
- 本archive acceptance（新，仅执行证据）

完整tracked diff与untracked新文件内容均已审查；无无关格式化/refactor、未来Batch/Task功能、业务合同改写、平行权威文档、schema/dependency/environment/database/cache变化；忽略目录内ledger不提交。`api/realtime_schemas.py`无需修改，直接沿用B10 public DTO。

B11 implementation、自动化测试、本地环境验证及本批acceptance满足；RT-CONNECT-001在本批闭环，blocker/Contract Gap均0。具备进入B12的技术前置；B12异常隔离与B13恢复/epoch/D6最终验收尚未执行，Task6整体未完成。

active plan §5明确“提交须用户另行授权”，本轮没有另行commit/push授权，故未commit/push/PR/merge。二次只读核对本地feature branch HEAD与远端`refs/heads/feature/task-6-realtime-state`均为`1dc865cef571e2baf342ba94278d8eb7add45ab3`，这是起始提交而非B11新commit。工作区保留上列六个必要文件的未提交变更。

后续用户明确授权“提交push”。提交前重新核对真实branch/HEAD/history及六个必要文件，未新增production修改；复跑上述focused/proof与R-TX/R-ARCH/EVENT-PORT集合，合并命令94 passed（4.67s），相同scoped Ruff全部通过。按授权提交并push当前feature branch；实际SHA及本地/远端HEAD一致性由提交后的Git核对和报告给出。
