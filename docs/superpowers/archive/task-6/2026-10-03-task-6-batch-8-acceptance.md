# Task 6 Batch 8 acceptance — Playback 只读观察与进度绑定

日期：2026-10-03。仅记录 active Task 6 plan Batch 8 的执行证据，不新增合同或平行 authority。

## 基线与读取

真实分支 `feature/task-6-realtime-state`；起始 HEAD `ef47395d3e716a3a2afc8c8cf1bbd5ed3cc49e6e`，working tree 干净。重新读取 git log、代码和测试，不以旧窗口/勾选状态作实现证据。

实际读取：docs/superpowers/README.md；主 Implementation Plan Task 6/Dependency/Relationship/Contract gates；active Task 6 plan §4/§5/Batch 8/D6 边界；Playback Spec §8.8；Architecture Spec §12.1–12.3；B7 acceptance；实际 PlaybackService/StateService/RealtimeCoordinator/DTO/PlayerPort/PlayerStatus/Queue identity/MockMPD/Adapter status 与能力记录；B7/B6 invariant tests。B7 History/snapshot/B6 transitions 在当前 HEAD fresh baseline 为 **63 passed**。

使用 using-superpowers、executing-plans、using-git-worktrees、test-driven-development、systematic-debugging、verification-before-completion、requesting/receiving-code-review。保留用户指定 checkout/branch 与既有 `.venv`；Python 3.14.4、pytest 9.1.1、Ruff 0.16.9 已实际验证，server/requirements.txt 已读取。无依赖、schema、环境修改，无 Docker/live MPD/NAS 验证。

## Contract Matrix Impact Analysis

- Owned：**RT-OBSERVE-001 采样部分、RT-SNAPSHOT-001 外部播放部分**。
- Relied-upon unchanged：**RT-REVISION-001、RT-PLAYBACK-001**。
- Regression：**PB-STOP/INSERT/REORDER/DELETE-PENDING/DELETE-CURRENT/NEXT-UNAVAILABLE/HISTORY-001、TX-ROLLBACK-001、TX-IDEMP-001**。执行计划指定 R-O/R-ARCH，保护历史 Output/架构边界；不把这些变成新增 owner。
- Relationship Gate：**REQUIRED**；Contract Matrix Gate：**REQUIRED**。
- 新增或修改 frozen Contract rows：0。Contract Gap：0。

| Contract / authority | Expected Delta / Must Remain Unchanged | External Confirmation / Failure-Rollback / Retry | Executable proof |
|---|---|---|---|
| RT-OBSERVE-001 / P §8.8、A §12.3 | 仅接受 cache/sequence；不写 PlaybackState/Queue/order/CAS/context/History/session/Library/Playlist/Favorites/terminal，不控制 MPD | 已确认 runtime occurrence + PlayerPort ID/position/URI + 业务代次；缺少绑定 unknown，确定漂移 false/reconciliation_required 且进度 null；失败 stale/error，最近同 current 样本可保留；取消传播；runtime 随 outer rollback 恢复；retry 只重读 | late sample next/pause/seek、duplicate/foreign/STOPPED、disconnect/restart、clock expiry、overlap ordering、replaced Port、rollback/cancel、nullable/error/deletion proof，见 observation 文件 |
| RT-SNAPSHOT-001 外部播放 / A §12.1/§12.3 | 完整、深复制的 observation 与同切面 sequence；业务 playback 仍为提交时状态，不用 DB updated_at 冒充进度 | capture 只消费 Service cache，不发外部调用；expiry 在共同边界登记并在锁释放前附上新水位；本地必需读取异常整体失败；重读不重放 mutation | progression/snapshot/expiry/preservation proof + B7 snapshot committed-cut/failure/deep-copy/nested owner proofs |
| RT-REVISION-001 / L §7.1、active §4.2 | sample 变化只推 sequence，Library/Playlist revisions 与 Queue CAS 不增；observed_at 单独变化无通知 | 继承 outer visible/rollback/no-op/replay/epoch；不比较跨 epoch 计数 | observation preservation + commit visibility/playlist proofs |
| RT-PLAYBACK-001 / P §3–8、active §4.2 | 领域操作只增加 runtime 代次/清理旧 sample/登记可信 binding；原业务 delta、确认、联合事件与保留关系不变 | 在已确认 occurrence 路径登记进程内绑定；outer failure 恢复 cache/binding/代次；terminal replay 不重做；无自动 reconcile | B4 transport/B5 queue/B6 transition proofs + observation late/deletion/runtime rollback proofs |
| PB-* / P、active §4.3；TX-* / active §4.3 | 原 current/Played/pending/History/AutoPlay/terminal 与幂等合同保持 | 原 PlayerPort 确认；外部作用不被 SQLite 假装撤销；rollback/retry/replay 原合同不变 | R-PB/R-TX；R-O/R-ARCH 保护 Output shared operation runner 和层次边界 |

## 实际 Batch Steps / RED→GREEN

1. 前置 authority、真实 Git/环境/代码/测试及 Matrix pre-flight 完成，两个 Gate 均 REQUIRED。
2. 指定最小 `test_late_sample_never_becomes_new_current_progress`：**RED 3 failed**（observe facade 缺失）→ **GREEN 3 passed**；覆盖 next 同 URI 不同 occurrence、pause、seek 与屏障中迟到样本。
3. 最小 production implementation：独立 PlaybackObservations runtime module；PlaybackService.observe/get_observation；复用既有 confirmed current occurrence 建立非持久绑定；业务代次与 rollback hooks；外部 status/queue_entries 在 DB 锁外，接受时重验 identity/代次/样本顺序；StateService 可注入 PlaybackService 并读取 cache。
4. 按最小行为补 proof：snapshot 注入缺失、expiry 旧 sequence、确定漂移（4 cases）、disconnect（2 cases）分别 RED→GREEN。仅 observed_at 刷新无通知、unknown 数值保持 null、restart 无可信绑定、业务/Playlist/Favorites/terminal/MPD 控制保留、cancel 释放与 runtime rollback 都有 executable assertion。
5. `test_older_overlapping_sample_cannot_replace_newer_accepted_progress`：**RED 1 failed**（旧3覆盖新12）→ **GREEN 1 passed**。`test_replaced_port_with_reused_ids_cannot_reuse_old_occurrence_proof`：**RED 1 failed**（新 Port 重用 ID 被错误标 fresh37）→ **GREEN 1 passed**。
6. 独立只读 reviewer 发现1 Important：delete current 的不同-song successor 在保存新 state 前登记 binding，随后被校验清除。新增 `test_delete_current_binds_confirmed_different_song_successor` **RED 1 failed→GREEN 1 passed**；只移动 observation binding 登记，原 occurrence 确认仍先于 save，History 原顺序保持。没有 Critical/Minor。修复由 targeted/regression/full tests 验证，没有声称 reviewer 做了二次复核。
7. 最终 source audit 确认 Adapter status parsing 可抛 ValueError；`test_unparseable_port_sample_degrades_without_swallowing_cancellation` **RED 1 failed→GREEN 1 passed**。外部读取边界捕获已验证 Port/timeout/parsing 错误，保留 typed code；不捕获本地读取失败或 BaseException cancellation。
8. 每个实现阶段检查 diff/status，逐次执行 focused tests，之后执行下列 final gates；未实现 Batch 9 或后续 Task。

非预期失败及处理：新增 cache staging 原先与领域 playback staging 使用不同 before/after 表示，导致既有 explicit-reconcile no-op（2 cases）和 stopped deletion（1 case）误推 sequence/domain。systematic debugging 定位 coordinator 的同 domain 第一 before/最后 after 比较边界；统一 state+cache 的语义比较表示（排除 updated_at/observed_at），三项精确历史 regression + late selector **6 passed**。没有修改既有断言。

两处测试 fixture 假设经排查修正：MockMPD 清除私有 current ID 后会合成 fallback ID，改为在 Port 边界返回完整 nullable PlayerStatus；同 URI next 可沿用 MPD 执行 ID，rollback 场景使用两次真实 next 到不同 Song b，确保外部漂移真实发生。保留原合同，不修改生产播放行为迁就测试。Ruff 拒绝 broad Exception 后收窄为已验证 typed/ValueError parsing 错误；未添加 lint ignore。

## Fresh final verification

所有命令均从仓库根目录执行，使用既有 `.venv/bin/python`。下列结果来自最后 production 修改（收窄 parsing 错误捕获）后的真实运行。

- Final focused/前置 invariant：**176 passed**，12.89s。
- R-PB/R-TX/R-O/R-ARCH：**229 passed**，13.51s。
- 全部 server/tests：**923 passed**，50.05s。
- scoped Ruff：**All checks passed**；compile：exit 0；tracked `git diff --check`：exit 0；新文件无 whitespace diagnostic。每次 pytest 有1条既有 Starlette TestClient/httpx deprecation warning；没有环境失败、skip、xfail 或未解决 test failure。初步全套921/922 GREEN 已由最终923 GREEN替代，不拿 full suite 代替176/229 targeted gates。

精确 focused/前置命令：

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_realtime_playlist.py server/tests/invariants/test_realtime_playback_transport.py server/tests/invariants/test_realtime_queue.py server/tests/invariants/test_realtime_transitions.py
```

历史回归精确命令（展开 active §5 的 R-PB/R-TX/R-O/R-ARCH）：

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_playback_service.py server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_lifecycle_injection.py server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
```

```bash
.venv/bin/python -m pytest -q server/tests
.venv/bin/python -m ruff check server/app/services/playback_observation.py server/app/services/playback_service.py server/app/services/state_service.py server/tests/invariants/test_realtime_observation.py
.venv/bin/python -m compileall -q server
git diff --check
```

## Traceability、scope 与 Git

RT-OBSERVE-001 → P §8.8/A §12.3 → PlaybackService/PlaybackObservations → observation 文件全部 proof → fresh final focused evidence。RT-SNAPSHOT-001 外部播放 → A §12.1/§12.3 → StateService cached aggregation/visible marker → clock/progress/preservation + B7 committed-cut proofs → focused evidence。RT-REVISION/RT-PLAYBACK/PB/TX → active Matrix 及原领域 authority → unchanged coordinator/producer/Repository/terminal 语义与最小 binding 接线 → 前置 invariant 与 R-* fresh evidence。

实际文件仅五个：

- `server/app/services/playback_observation.py`：新建，只读采样/校验/cache/rollback。
- `server/app/services/playback_service.py`：observation facade、代次与既有 occurrence confirmation 接线，playback semantic comparison。
- `server/app/services/state_service.py`：cache 聚合与 expiry 后 matching marker。
- `server/tests/invariants/test_realtime_observation.py`：新建 executable invariant/regression proof。
- 本 archive acceptance：执行证据，不承担产品语义 authority。

B7 models/realtime.py 已有完整 DTO，本批不需要修改。生产代码新增199行、删除5行（新 module 154行，两个 tracked production files 新增45行/删除5行），在 B8 complexity 预算内。实际 diff 与新文件全文已审阅：没有无关 formatting/refactor、future Batch/Task 实现、重复权威文档、合同语义变更、schema/dependency/environment/DB/cache artifacts。

Reviewer declined 项的范围裁定：observer 调度/预算/可注入 age 参数/关停为 B9；Output/HTTP/WS/交接/背压/重连为后续 Batches；自然结束/外部恢复属于 D6-RECOVERY。保持 active plan 已冻结边界，本批不声称完成这些能力。代价是这些功能仍待原 owner 验收，不把本批 GREEN 代替它们。

B8 implementation、自动化测试、本地环境验证、acceptance criteria 均满足。Relationship Gate：**PASS**；Contract Matrix Gate：**PASS（仅 B8 scope）**。当前 blocker/Contract Gap：无。RT-OBSERVE-001 仍 PARTIAL 到 B9 final owner；RT-SNAPSHOT-001 仍待 B9/B10/B13 完成其它部分和最终 owner，不声称整个 row/Task 6 COMPLETE。

B9 技术前置具备，本轮未开始 B9。D6-RECOVERY 未在本批验收，仍约束自动恢复启用和 Task 6 最终 acceptance；本地 tests 不替代 Task 12 的物理 MPD/NAS/DAC/反向代理验收。

未 commit/push/PR/merge。active plan §5 明确“提交须用户另行授权”；本次要求按该 plan 执行，没有另行 commit/push 指令。结束时本地 HEAD 与只读远端 `refs/heads/feature/task-6-realtime-state` 二次核对均为 `ef47395d3e716a3a2afc8c8cf1bbd5ed3cc49e6e`，它是 B7 基线，不是本批 commit。working tree 为上述五个文件的未提交修改；index 无 staged delta。

后续用户明确指令“提交push”，授权提交并推送上述五个文件。提交前重新核对真实 branch/HEAD/working tree 和完整修改范围，重跑 observation + snapshot invariant 文件：**34 passed**，2.53s；scoped Ruff 与 diff 检查通过。无新增 production 行为修改。实际 commit SHA、本地/远端 HEAD 及 clean working tree 由提交后的 Git 二次验证与对话结果记录，不在创建提交前预填。
