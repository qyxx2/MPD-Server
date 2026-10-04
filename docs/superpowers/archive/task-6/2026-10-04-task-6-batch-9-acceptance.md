# Task 6 Batch 9 acceptance — Observer 生命周期与 Output 接入

日期：2026-10-04（Asia/Shanghai）。本文件是执行证据，不新增产品语义或平行 Contract authority。

## 基线、权威读取与环境

起始真实分支 `feature/task-6-realtime-state`，HEAD `6e63ff169480f9a072b6d898ecbb9706689d81dd`，working tree 干净。实际检查 status/branch/log、当前实现和测试；没有从旧窗口、交接或 Plan 勾选状态推定完成。

读取 docs/superpowers/README.md；主 Implementation Plan Task 6、Dependency/Relationship/Contract gates；active Task 6 plan Matrix、验证集合、Batch 8/9、D6 边界；Architecture Spec §12.1–12.3；Output Spec §6.1–6.3；Playback Spec §8.8；Task 7 archive plan O-STATE/EVENT/PRESERVE 及 lifecycle capability；Batch 8 acceptance 与真实代码、测试。B8 observation/snapshot + historical lifecycle 的 fresh baseline **48 passed**。

采用 Superpowers using-superpowers、executing-plans、using-git-worktrees（沿用用户指定 checkout/branch）、TDD/writing-good-tests、systematic-debugging、verification-before-completion、requesting/receiving-code-review、finishing-a-development-branch（保持当前分支，不做远端变更）。既有 `.venv`：Python 3.14.4、pytest 9.1.1、Ruff 0.16.9，实际验证；server/requirements.txt 已读取。没有 dependency/schema/虚拟环境修改，没有 Docker 或物理 MPD/NAS/DAC 验收。

## Contract Matrix Impact Analysis

- Owned：**RT-OBSERVE-001 final、RT-OUTPUT-001 final**。
- Relied-upon unchanged：**RT-DELIVERY-001 core**。
- Regression：**O-STATE-001、O-EVENT-001、O-PRESERVE-001、O-TX-001、O-FAIL-001**，以及 Output 历史 discovery/reserved/enable/disable 相关 O-*；**TX-ROLLBACK-001、TX-IDEMP-001**。Root injection 另回归既有 System composition、Port 合同。
- RT-SNAPSHOT-001 是本批 cache 聚合的受影响既有消费者；运行其 B7/B8 proofs，不将整个 snapshot row 变成本批 final owner。
- Relationship Gate：**REQUIRED**；Contract Matrix Gate：**REQUIRED**。
- 新增或修改 frozen Contract rows：0；Contract Gap：0。技术支持文件范围修正写入唯一 active plan 的 Batch 9，未改 Spec 或业务合同。

| Row / authoritative source | Expected State Delta / Must Remain Unchanged | External Confirmation / Failure-Rollback / Retry | Executable invariant proof |
|---|---|---|---|
| RT-OBSERVE-001 / A §12.3、P §8.8 | 一个进程 observer，立即采样、每轮完成后1秒、共享5秒外部预算、默认age>6秒stale；只更新观察缓存/sequence；不改变 Queue identity/order/CAS、PlaybackState/context/AutoPlay、Library/Playlist/Favorites、History persisted/active/session、terminal 或 MPD控制 | 实际 PlayerPort读取及已有 occurrence/generation 校验；typed error 保留、预算超时立即降级；关停取消传播并 await，绝不解释为 Stop；分域失败/接受失败继续有界重试；重复时间戳不产生内容通知 | lifecycle 全文件，B8 observation proofs；真实 Library/Playlist/Favorites/terminal/History/Queue 保存关系与只读命令集合断言 |
| RT-OUTPUT-001 / O §6.1–6.3、A §12.3 | Output cache/外层 observation DTO/失效同步；observed 与 request 独立；sequence 不 bump Library/Playlist/Queue | 控制继承实际回读/播放保留；观察外部读取在锁外，接受与 capture 共边界；控制开始/结束各推进代次，控制前/中开始的迟到样本均丢弃；失败保留旧事实stale/unknown；outer rollback不撤外部事实，无terminal success，retry不重复已满足控制；replay原回执，publisher异常不改提交 | output 全文件：联合传播、timestamp no-op、unknown no-op、rollback/retry、HTTP terminal replay/publish failure、控制前/中屏障、freshness snapshot waterline、timeout TCP stream protection |
| RT-DELIVERY-001 core / A §12.2、active §4.2 | 提交可见hook只同步登记义务，网络不回滚提交；不改变terminal/其它域 | 继承共同visible边界、post-commit隔离/失败关闭；迟到领域payload不能当当前态；沿用重读/无重放mutation | B1 commit visibility proofs + R-TX/R-O；最终网络背压owner仍B12 |
| RT-SNAPSHOT-001 consumer / A §12.1–12.3 | 只读完整cache，expiry及sequence同切面；保持本地完整状态、null/unknown与深复制 | snapshot不进行外部采样；本地失败整体失败；expiry先登记再附visible marker；重读不重做业务 | output expiry+snapshot proof，B7 snapshot/B8 observation proofs |
| O-*、TX-* / Task7 §4、Task6 §4.3 与原 Spec | 原输出控制、请求/观察分离、Queue/History/Context保留、terminal/idempotency、外部不可假装回滚 | 原确认及outer事务/retry/replay/event语义不变；保持已注入publisher对象及一次get_state runner invocation | R-O/R-TX/R-ARCH、System composition、Port、OutputManager历史文件，见最终命令 |

## 实际 Steps、RED→GREEN 与修正

1. 当前 Git/环境/权威/真实前置 proofs 与 Matrix pre-flight 完成。
2. 采样预算最小 proof：`test_observation_budget_degrades_but_shutdown_cancellation_does_not`，正确 RED 为缺少 read_timeout 参数 → GREEN。测试编写时先纠正两次 helper 使用错误（同步 server_snapshot 不能在 asyncio.run 内 await），这些 fixture failures 不算目标 RED。
3. 指定 Output proof：`test_output_control_and_observation_share_delivery_without_history`，cache facade 缺失 RED → GREEN；capability fixture 按真实 verified_operations 修正，不修改 production capability 合同。
4. Output expiry/失败/同切面水位 selector（disconnect、timeout）**2 RED→2 GREEN**；StateService 消费 OutputManager cache 与 observation facade。未知缓存读取不得制造变化，**1 RED→1 GREEN**。
5. 指定 lifecycle selector `test_single_observer_retries_and_shutdown_preserves_playback`：缺少 StateObserver **RED→GREEN**；证明立即采样/1秒重试/无重叠、分域降级/恢复、重复run拒绝、取消await、不停止播放。补同轮预算、独立timeout重试等已实现行为的 regression proof，这些首次GREEN不冒充RED。
6. Root lifecycle 缺接线 **RED→GREEN**；关停 subscription 未失效 **RED→GREEN**；可注入 playback age 缺入口 **RED→GREEN**。真实 lifespan 无客户端采样，shared coordinator 接入 producers，关停清理，不接 D6 recovery。
7. Root 接入后出现跨线程 fixture 的 SQLite lock：历史 TestClient app 在一个事件循环采样，fixtures 在另一个循环直接初始化同库/替换Services。隔离旧 fixture 的应用 observer，在独立 lifecycle gate 直接运行真实 main.lifespan；没有改数据库超时、削弱断言或跳过测试。测试支持范围写入 active plan。
8. `test_blocked_output_sample_releases_business_boundary_and_rejects_late_control_fact`：观察网络持业务锁导致控制 timeout **RED→GREEN**；Output采样移到边界外，接受时重验代次/Port/样本顺序。临时接受失败终止loop的 proof **RED→GREEN**，cache刷新分域捕获/记录后重试，取消继续传播。
9. 独立只读 reviewer 给出2 Important，均在本轮重现：控制中开始的sample覆盖已确认关闭输出，以及预算取消后 MPD旧响应被下一次读取误用。新增两个 invariant **各1 RED→1 GREEN**；控制开始/结束推进代次，在共同边界接受/丢弃样本；MPDAdapter在正在进行命令被取消时弃用连接并传播 CancelledError。后者留下确定性本地 TCP proof，并回归全部 server/tests/player。没有 Stop/补偿/新Port业务语义。
10. 历史兼容性失败全部读取、定位、精确回归：首次全套 **932 passed/2 failed**（injected publisher identity）→保持原assertion，恢复注入对象；第二次全套 **936 passed/2 failed**（get_state runner从一次变两次）→保持原assertion，采用控制开始/结束代次 fence，接受仍只有一次runner；两项历史selector及控制前/中race **4 passed**，相关文件 **18 passed**。没有为当前实现修改合同或旧测试。
11. 完整 final focused/regression/full、scoped Ruff、compile、diff/status、future-scope isolation、traceability 完成。reviewer 未做修改；修复由父执行者 RED→GREEN 和最后全套验证，不声称 reviewer 做了二次复核。

## Fresh final verification

最终生产代码及加强后的保留/屏障测试之后，真实运行：

- Batch focused + 前置合同文件：**201 passed，15.14s**。
- R-O/R-TX/R-ARCH + 直接受影响 System/Port/OutputManager 历史回归：**176 passed，8.00s**。
- 全部 server/tests：**938 passed，53.20s**。
- scoped Ruff：**All checks passed**；compile：exit 0；git diff --check：exit 0。
- 每次 pytest 有1条既有 Starlette TestClient/httpx deprecation warning；没有未解决失败、skip、xfail或环境失败。201/176 targeted gates独立执行，938 full suite不替代relationship/Contract gates。

精确命令：

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_observer_lifecycle.py server/tests/invariants/test_realtime_output.py server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_realtime_library.py server/tests/invariants/test_realtime_playlist.py server/tests/invariants/test_realtime_playback_transport.py server/tests/invariants/test_realtime_queue.py server/tests/invariants/test_realtime_transitions.py

.venv/bin/python -m pytest -q server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_lifecycle_injection.py server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories server/tests/invariants/test_system_read_relationships.py server/tests/player server/tests/services/test_output_manager.py

.venv/bin/python -m pytest -q server/tests
.venv/bin/python -m ruff check server/app/main.py server/app/player/mpd_adapter.py server/app/services/output_manager.py server/app/services/playback_service.py server/app/services/playback_observation.py server/app/services/state_service.py server/app/services/state_observer.py server/app/services/realtime_coordinator.py server/tests/conftest.py server/tests/invariants/test_realtime_output.py server/tests/invariants/test_realtime_observer_lifecycle.py
.venv/bin/python -m compileall -q server
git diff --check
```

## Traceability / scope / acceptance

RT-OBSERVE-001 → A §12.3/P §8.8 → StateObserver/Playback observations/Root → lifecycle+observation proofs → fresh201 GREEN。

RT-OUTPUT-001 → O §6/A §12.3 → OutputManager/Coordinator/StateService/Root、最小Adapter cancellation支持 → output proofs → fresh201 GREEN、历史176 GREEN。

RT-DELIVERY core → A §12.2 → 原visible/commit义务 + 本批stage_observation → commit visibility/O-event/TX proofs → fresh201/176 GREEN；row最终网络owner仍B12。

RT-SNAPSHOT consumer → A §12.1–12.3 → StateService cache/expiry marker → snapshot/B8/output expiry proofs → fresh201 GREEN；RT-SNAPSHOT最终owner仍B13。

O/TX historical rows → 原 Spec/Task7/active §4.3 → 原控制、outer transaction、terminal replay及注入方向 → 指定R-* / System / Port文件 → fresh176 GREEN。

实际13个文件：

- `server/app/main.py`
- `server/app/player/mpd_adapter.py`
- `server/app/services/output_manager.py`
- `server/app/services/playback_observation.py`
- `server/app/services/playback_service.py`
- `server/app/services/realtime_coordinator.py`
- `server/app/services/state_service.py`
- `server/app/services/state_observer.py`（新增）
- `server/tests/conftest.py`
- `server/tests/invariants/test_realtime_observer_lifecycle.py`（新增）
- `server/tests/invariants/test_realtime_output.py`（新增）
- `docs/superpowers/plans/2026-10-03-mpd-server-task-6-batch-plan.md`（仅B9技术支持白名单/验收补正）
- 本 archive acceptance（新增证据）

完整 tracked diff、新文件内容和保留断言均审阅；生产变更含新observer222新增/25删除行，在原B9约180–320LOC预算内，额外支持文件有当前Batch必要性记录。没有无关格式化/重构、未来API/WS/网络背压/恢复状态机、Spec合同语义更改、重复权威矩阵、schema/dependency/environment/DB/cache artifacts。

Reviewer declined范围：B10 API、B11 snapshot send race、B12网络背压、D6领域恢复、物理MPD/DAC验收。裁定保持原owner，不在B9提前实现；相关row未由本批GREEN冒充完成。

B9 implementation、自动化测试、本地环境验证、当前Batch acceptance均满足。Relationship Gate：**PASS**；Contract Matrix Gate：**PASS（B9 scope）**。RT-OBSERVE-001与RT-OUTPUT-001的B9 final-owner验收通过；当前B9 blocker/Contract Gap均无。D6-RECOVERY仍未由本批验收，继续约束自动恢复及Task6最终acceptance；Task6整体未完成。B10技术前置具备，本批未开始B10。

## Git 与提交权限

没有commit/push/PR/merge。active plan §5明确“提交须用户另行授权”；本次按该plan实施，不自行增加提交/推送授权。最终只读核对：本地HEAD与远端`refs/heads/feature/task-6-realtime-state`均为`6e63ff169480f9a072b6d898ecbb9706689d81dd`，这是起始基线而非本批新提交。branch保持不变，index无staged delta；working tree为上述13个必要文件的未提交变更。

后续用户明确授权“提交push”。提交前重新核对 branch/HEAD/history/working tree及完整 tracked diff，仍为上述13个必要文件；生产代码未新增修改。重新运行 lifecycle/output/observation/snapshot 四文件：49 passed，3.58s（1条既有 deprecation warning）；相同 scoped Ruff：All checks passed。按授权提交并推送当前 feature branch；实际提交和远端 HEAD 由提交后 Git 二次确认记录报告。
