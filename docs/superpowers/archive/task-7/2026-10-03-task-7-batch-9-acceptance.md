# Task 7 Batch 9 — Final backend acceptance / handoff

## Scope and actual baseline

2026-10-03；branch `feature/task-7-output-manager`，开始 HEAD `447eeb925e62a7951e92d6e80f945c2e422b5d46`，working tree clean。重新执行 status/branch/log/fetch/ls-remote；远端同名 HEAD 与本地一致。真实 Task baseline 为 `ca2d9d2e9569b3a99eac0c068003d09850e2124e`（git merge-base main HEAD）；新 fetch 后 origin/main 仍为该 SHA。Task 1R `03f4de9`、Task 4 `86975d6` ancestry 均 exit 0；B1–B8/B4.5 的真实 commits、代码、测试均重新核对。

读取文档地图、主 Plan Task 7/global/dependency/relationship/Contract gates、active Task 7 Plan、O 输出 Spec、A 模块/SQLite/Output/About/§19.5、P §8、能力记录、Task 5 归档 Matrix、B8 acceptance 和直接代码/测试。B8 日志仅定位，不继承其 GREEN。

本轮只执行原 Step 8 final gate 与 Step 9 final commit/handoff。Step 1–7 按真实历史 commits、现存实现/tests 与本轮 GREEN 复核后勾选；不声称本轮重做历史 RED。B9 RED→GREEN **N/A**：active B9 明确仅验收，无新功能/bugfix/行为或测试修改。

使用指定 checkout 和原 `.venv`：Python 3.14.4、pytest 9.1.1、Ruff 0.16.9；无依赖/环境变更，无 Docker、Web build/E2E、live NAS 或音乐文件操作。

## Contract Matrix Impact Analysis and final traceability

Owned：**无新 row**；原 implementation owner 保持不变。Relied/Regression：active §4 全部 **26 IDs**，本轮不新增/修改业务 row 或语义。

- 新 rows 最终验收：O-DISC-001、O-STATE-001、O-RESERVED-001、O-PRESERVE-001、O-TX-001、O-EVENT-001、O-ENABLE-001、O-DISABLE-001、O-FAIL-001、INFO-READ-001、SYS-READ-001、SYS-WRITE-001。
- 继承 rows：PORT-OUTPUT-001、PORT-INFO-001、EVENT-PORT-001、TX-ROLLBACK-001、TX-IDEMP-001。
- 历史 regression-only：PB-STOP-001、PB-INSERT-001、PB-REORDER-001、PB-DELETE-PENDING-001、PB-DELETE-CURRENT-001、PB-NEXT-UNAVAILABLE-001、PB-HISTORY-001、PL-REP-001、PL-COLLECTION-001。

Pre-flight 已逐 row 核对 Expected State Delta、Must Remain Unchanged、Failure/Rollback、External Confirmation、Retry/Idempotency 和 Executable Proof，并核对其它 required fields。唯一冻结合同仍在 active §4；下表只记录实现/proof 和本轮证据，不新增平行权威。

F1–F9/F4L 与 R-* 路径/函数沿用 active §2/6。表中 **FRESH-F=292 passed** 指完整 focused gate，**FRESH-R=128 passed** 指直接历史 gate，**FRESH-I=283 passed** 指独立全 invariants。每个所列文件均在本轮实际执行，无 skip/xfail/deselect。

| Contract ID → authoritative Spec | Implementation → executable invariant → fresh evidence / obligation review |
|---|---|
| O-DISC-001 → O §4.2/6.1 | output_manager.py → F1 + F5/F6 ID drift → FRESH-F/I；本次 ALSA/selector/ID 唯一识别，无猜测控制；retry 重读。 |
| O-STATE-001 → O §5.2/6.1 | models/output.py + manager → F1/F5/F6/F7/F8 → FRESH-F/I；observed/request 独立，fresh/stale 明确，失败不假造 ACTIVE，stream null。 |
| O-RESERVED-001 → O §5/6.1 | manager + system.py → F1/F8 + mutation API → FRESH-F/I；拒绝两种布尔请求，旧事实/播放/输出不变，无控制/terminal/event。 |
| O-PRESERVE-001 → O §6.2 / A §8.1/19.5 / P §8 | playback_service.py shared runner + output_operation.py + manager guard → F3/F4L/F5/F6/F8/F9 → FRESH-F/I；两向串行、current occurrence/Queue revision/Context/History/session/modes 不变，position 自然推进或未知保留，漂移无擅自修复。 |
| O-TX-001 → O §6.2–6.3 / A §19.5 | database.py + runner/lifecycle + manager + existing idempotency → F4/F4L/F9 → FRESH-F/I；terminal/schema/outer/commit/cancel failure 不撤实际 MPD，无 terminal success/event；retry 重读，committed replay 无读写。 |
| O-EVENT-001 → O §6.3 | events.py + database hooks + manager → F4/F4L/F5/F6/F9 → FRESH-F/I；确认后 outer commit、退出 context/释放锁才 publish，snapshot 不随后续操作变，发布失败日志可见且不能撤 commit；无 History。 |
| O-ENABLE-001 → O §6.1–6.3 | manager bool ensure → F5/transport/F8/F9 → FRESH-F/I；仅目标 enabled、回读+guard 确认，其它输出和播放不变，no-op/retry 不重复控制。 |
| O-DISABLE-001 → O §4.2/6.1–6.3 | manager bool ensure → F6/F8/F9 → FRESH-F/I；仅目标 disabled，非 Stop，无 Play/seek/Queue/History/AutoPlay 副作用，no-op/retry 安全。 |
| O-FAIL-001 → O §6/8.2 | manager + typed API errors → F5/F6/F8/F9/transport → FRESH-F/I；ACK无效果、effect后timeout、回读失败/cancel 与 actual 分开，失败无成功通知、不反向补偿。 |
| INFO-READ-001 → O §7.1–7.3 / A §14 | models/mpd_info.py + mpd_info_service.py → F2/F7 → FRESH-F/I；版本有 verified 来源，独立 runtime/null/0/status 连接事实，不触发 update 或其它写入。 |
| SYS-READ-001 → O §5/7/8 / A §2/13/14 | system.py/system_schemas.py + dependencies/main → F7/R-ARCH → FRESH-F/R/I；GET 保留事实/错误/null/0，未配置能力仍启动，shared port、无 probe、无内部 ID 暴露/资源写入。 |
| SYS-WRITE-001 → O §6 / P §8.6 / A §19.5 | system.py/system_schemas.py + existing middleware → F8/F9/R-ARCH + mutation API → FRESH-F/R/I；typed 200/400/409/422/502/503，对应确认或明确失败；schema/outer failure 不保存成功。 |
| PORT-OUTPUT-001 → O §4/10 / M Task 1R | existing PlayerPort/Mock/Adapter/VerifiedPlayerPort → R-PORT + transport → FRESH-R/F；指定 ID bool/verified gate/typed failures，无新增 transport 实现。 |
| PORT-INFO-001 → O §7/10 / M Task 1R | existing capabilities/models/ports → R-PORT + F2 → FRESH-R/F；runtime nullable stats/update，历史 version 不代表 live 连接。 |
| EVENT-PORT-001 → A §12 / M event dependency rule | existing EventPublisher + hooks → R-EVENT/F4/F9 → FRESH-R/F/I；经接口交付，Library ordering 不变，不依赖 WebSocket。 |
| TX-ROLLBACK-001 → Task 5 原 Matrix §3.7 / A §19.5 | existing UoW/History + lifecycle → R-TX/F4L/F9 → FRESH-R/F/I；persisted/runtime/session 恢复，无 phantom terminal/History，不冒充撤销外部 MPD。 |
| TX-IDEMP-001 → Task 5 原 Matrix §3.7 / P §8.6 | existing idempotency middleware/service/repository → API idempotency/R-TX/F9 → FRESH-R/F/I；成功 atomic terminal，scope/payload conflict，未提交 retry、已提交 replay 无副作用。 |
| PB-STOP-001 → Task 5 原 Matrix §3.7 / P | existing playback/History → R-STOP/R-PLAY → FRESH-R/I；STOPPED 确认后才结束 History/AutoPlay，失败恢复，output disable 不调用 Stop。 |
| PB-INSERT-001 → 同上 | existing playback/Queue → R-PLAY + playback service tests → FRESH-R/I；pending insert 保留 current/context/history，failure 无部分 server commit。 |
| PB-REORDER-001 → 同上 | existing playback/Queue → R-PLAY → FRESH-R/I；Queue/player order 与 retained occurrence identity。 |
| PB-DELETE-PENDING-001 → 同上 | existing playback/Queue → R-PLAY + pre_batch6 API → FRESH-R/I；精确删除/refill、current/history 不变与 failure protection。 |
| PB-DELETE-CURRENT-001 → 同上 | existing playback/History → pre_batch6 API/R-STOP/R-PLAY → FRESH-R/I；confirmed successor/Stop、STOPPED 不重启、History 一致。 |
| PB-NEXT-UNAVAILABLE-001 → 同上 | existing playback/library/History → R-PLAY/R-TX + pre_batch6 API → FRESH-R/I；skip unavailable，actual successor 确认，失败/retry 无 lost/phantom transition。 |
| PB-HISTORY-001 → 同上 | existing playback/History → R-PLAY/R-TX/R-STOP → FRESH-R/I；confirmed transition exactly once，failure/replay 不重复。 |
| PL-REP-001 → Task 5 原 Matrix §3.7 / Library Spec | existing playlist/resource → R-PL → FRESH-R/I；persisted membership/order/availability 对所有表示一致。 |
| PL-COLLECTION-001 → 同上 | existing playlist/collection → R-PL → FRESH-R/I；playable split 不更改 persisted members。 |

Relationship Gate：**REQUIRED / GREEN**。Contract Matrix Gate：**REQUIRED / GREEN**；完整 26-row traceability/coverage review 通过，无 Contract Gap 或未关闭 blocker。Full suite 未替代上述独立 proof。

## Commands and actual output

全部从 repo root 以原 `.venv/bin/python` 运行：

```bash
.venv/bin/python -m pytest -q server/tests/services/test_output_manager.py server/tests/services/test_mpd_info_service.py server/tests/api/test_system_reads.py server/tests/api/test_system_output_mutations.py server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_mpd_info_relationships.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_output_lifecycle_injection.py server/tests/invariants/test_output_enable.py server/tests/invariants/test_output_transport.py server/tests/invariants/test_output_disable.py server/tests/invariants/test_system_read_relationships.py server/tests/invariants/test_system_output_relationships.py server/tests/invariants/test_output_idempotency.py
# 292 passed, 1 warning, 14.13s
.venv/bin/python -m pytest -q server/tests/player/test_task1r_step4.py server/tests/player/test_task1r_step5.py server/tests/player/test_task1r_step6.py server/tests/player/test_task1r_step7.py server/tests/services/test_playback_service.py server/tests/api/test_idempotency.py server/tests/api/test_pre_batch6_corrective.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_transaction_relationships.py server/tests/invariants/test_playlist_relationships.py server/tests/invariants/test_architecture_relationships.py server/tests/integration/test_task3_events_and_mpd.py
# 128 passed, 1 warning, 7.81s
.venv/bin/python -m pytest -q server/tests/invariants
# 283 passed, 1 warning, 24.50s
.venv/bin/python -m pytest -q server/tests
# 736 passed, 1 warning, 34.77s
.venv/bin/python -m compileall -q server
# exit 0
.venv/bin/python -m ruff check server
# All checks passed
```

无 failed/error/skip/xfail/deselect；唯一 warning 为已有 Starlette TestClient/httpx deprecation，未改依赖。每阶段均执行 git diff --check/status，clean。

## Final review, changed files and remaining boundaries

独立只读 reviewer 审查真实 `ca2d9d2..447eeb9` 逐文件代码/tests/边界及五项 Review Focus，独立 focused F3/F9/F2/transport **84 passed**，range diff check clean。Critical/Important/Minor implementation finding 均无；无 deferred minor。README/main Plan 历史 planning-only 状态由本 B9 更新，不作为 production defect。

完整 branch diff 审查：Task baseline 后 44 个文件的实现/测试/docs 均属于 Task 7 支持范围或已提交的事实状态/Task 5 原样归档；playback 历史测试修改加强 rollback protection，未放宽合同。当前 B9 只修改 **README.md、主 Implementation Plan、active Task 7 Plan、本 acceptance archive**。无 production/function-test 改动，无无关格式化/refactor/未来 Batch/Task 6/8/10、schema migration、依赖或 runtime artifact；本轮不改 Spec。

Reviewer set-aside / executor rulings：物理 DAC/可听/bit-perfect 和 live NAS 均无本轮证据，不能宣称通过，后续 Task 12 验收；生产 capability loading 与实时完整交付/恢复分别由 Task 10/6 拥有，不提前实施；远端最终 ref、最终文档和完整后端/invariant gates 由 executor 负责，本轮上述 gates 已实际执行，最终 commit/ref 在写入后核实。用户指定 checkout、原 .venv 和仅 B9 scope 优先于另建 worktree/环境或技能 integration 菜单；按 active final ref requirement 推送当前 feature branch，保留分支、不创建 PR/merge main。若这些边界被扩大，将错误宣称硬件/未来 Task 完成或改变用户指定执行环境。

**B9 后端 acceptance 满足，Task 7 后端实现可供 Task 6 独立 pre-flight 消费；没有下一个 Task 7 Batch。** 本地实现/自动测试/环境检查与 Contract/relationship Gate 已满足；真实 NAS/DAC 手工验收未执行。最终提交包含本记录；SHA、branch HEAD、changed-files、clean working tree、远端 ref 及新 fetch 后 ancestry 均须在提交/推送后二次核对，具体结果由最终报告给出。
