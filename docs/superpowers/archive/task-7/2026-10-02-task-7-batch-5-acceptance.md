# Task 7 Batch 5 — NAS_DAC enable acceptance

## 实际基线与完成范围

- 分支 `feature/task-7-output-manager`；开始 HEAD `c5726c8eae439ebb474008b86d9e409eed1ccaa6`，working tree 干净。重新核对 branch、HEAD、最近 history、fetch、`git ls-remote`；同名远端 ref 与开始 HEAD 相同。Task 1R `03f4de9` 和 Task 4 corrective `86975d6` ancestry 检查 exit 0。
- 本轮实际读取 README、主 Plan Task 7/依赖/两个 Gate、active Task 7 Plan 相关 rows/冻结接口/F5/B5/共同验收、B4.5 acceptance、O §4/5/6.1–6.3、A §5/8.1/12/13/19.5、P §7–8、原 Task 5 Matrix、实际代码/测试和 MPD capability reference；不沿用历史 GREEN。
- 使用现有 `.venv`，Python 3.14.4、pytest 9.1.1、Ruff 0.16.9。未修改依赖/虚拟环境、未使用 Docker、未联系真实 MPD/NAS/DAC。localhost fake TCP 属于确定性本地测试。
- 完成 B5 共同步骤：依赖及 Matrix pre-flight → enable 最小行为 RED→GREEN → failure/reconcile RED→GREEN → lifecycle rollback RED→GREEN → invariant/transport/历史 regression → compile/lint/diff/范围和 traceability review。主 Plan Step 1/3/4/5 仅完成 B5 enable 部分，Step 8 仅本 Batch 验证；Task 级 Steps 和跨 Batch rows 不提前标完成。

## Contract Matrix Impact Analysis / traceability

- Owned：**O-ENABLE-001、O-FAIL-001（enable）、O-STATE-001（请求态）**。
- Relied-upon unchanged：**O-DISC-001、O-RESERVED-001、O-PRESERVE-001、O-TX-001、O-EVENT-001、PORT-OUTPUT-001、EVENT-PORT-001**。
- Regression：**PB-INSERT-001、PB-REORDER-001、PB-HISTORY-001、TX-ROLLBACK-001**，F1/F3/F4/F4L；B5 acceptance 消费 R-PORT/R-PLAY/R-TX，故现有 TX-IDEMP-001 的 R-TX proof 也重新运行，不重新定义 owner。
- Relationship Gate：**REQUIRED**；Contract Matrix Gate：**REQUIRED**。
- 无新业务 row、无修改合同语义。逐项核对每个受影响 row 的 Preconditions/Authorities、Expected Delta、Must Remain Unchanged、External Confirmation、History/Event、Transaction Boundary、Failure/Rollback、Retry/Idempotency、Observable Result、Executable Proof；B4.5 runner/public lifecycle 实际存在，fresh prerequisite **107 passed**。

| ID → authoritative Spec / row | Delta、unchanged、confirmation、failure/rollback、retry → implementation / executable proof / fresh GREEN |
|---|---|
| O-ENABLE-001 → O §6.1–6.3 / active §4.2 | 仅目标 enabled=true；其它输出、Queue/revision/identity/Context/History/AutoPlay/modes/position 保持。目标回读及 playback guard 完成后才成功；已 enabled 不重复命令/事件；fresh ID/selector 每次重取。OutputManager `_enable` → F5 success/no-op、ID-rebind、capability/selection、漂移、fake TCP；**53 F5+transport GREEN**。本 row 仅 Service 完成，HTTP 仍 B8。 |
| O-FAIL-001(enable) → O §6.1–6.2/8.2 / active §4.2 | 原始 typed failure/cancellation 继续抛出；last_request=SWITCH_FAILED，实际输出独立回读，无法读取则旧事实 stale；无其它输出补偿、无 History/成功事件。下次先读取，效果已存在时 retry 不再控制。`_fail_request`/`_observe` + lifecycle cleanup → F5 ACK-no-effect/reject/effect-then-timeout/readback-once/offline/initial-offline/after-status/cancel/cache/retry；**49 F5 GREEN**。disable 扩展仍 B6。 |
| O-STATE-001(request) → O §5.2/6.1 / active §4.2 | PREPARING→SUCCEEDED 或 SWITCH_FAILED；fresh actual ACTIVE/INACTIVE 来自真实 outputs，stream 保持 unavailable/null；失败请求不掩盖实际 ACTIVE。独立快照不受后续 mutation 污染。OutputManager `_last_request`/`_snapshot` → F5 准备、成功、失败、外层 cleanup/cache + F1；**227 focused/regression GREEN**。整个 row 的 disable transition 仍 B6。 |
| O-DISC-001、O-RESERVED-001 → O §4.2/6.1 / active §4.2 | 当前唯一 ALSA/合法 selector；无匹配/歧义/foreign/异常/重复 ID 拒绝无控制；缓存 ID 变化后绑定新 ID。CLIENT_STREAM 仍拒绝、无副作用。`_select_target` + 原 reserved guard → F1 + F5 selection/rebind，**227 GREEN**。 |
| O-PRESERVE-001 → O §6.2、A §8.1/19.5、P §8 / active §4.2 | 继续使用 PlaybackService 同 DB runner 和原 guard；不写服务端播放权威，不添加 manager lock。真实启用后证明 duplicate occurrence、PLAYING/PAUSED/STOPPED/empty/unknown/natural elapsed、Queue/History/Context/modes 完整 unchanged，异常 drift 无自动修复。F3/F4L + F5 authority snapshots/drift，**227 GREEN**。 |
| O-TX-001、O-EVENT-001 → O §6.2–6.3、A §12/19.5 / active §4.2/§5 | mutation 注册当前 invocation 的 public lifecycle：outer rollback/cancel/commit failure 清理请求成功标记、丢弃通知，外部输出不反向补偿；outer commit 后、释放锁且确认事实后才通知；postcommit cancel 保留 terminal/request，publisher failure 日志且不改判 rollback；no-op 无重复事件。F4/F4L + F5 direct Service/outer transaction/terminal witness；**227 GREEN**。最终 REST schema/terminal/middleware integration 仍 B8。 |
| PORT-OUTPUT-001、EVENT-PORT-001 → O §4/10、A §12、主 Plan dependency rule 6 / active §4.3 | 端口/能力及事件接口保持原 owner；不绕运行时验证、不改 Adapter/探针、不导入 WebSocket、不保证 durable/exactly-once。R-PORT step4–7、fake TCP、Task 3 events + F4；**227 GREEN**。 |
| PB-INSERT-001、PB-REORDER-001、PB-HISTORY-001、TX-ROLLBACK-001 → 原 Task 5 Matrix §3.6、P §8、A §8.1/19.5 / active §4.4 | 保持原 insertion/reorder occurrence、History/session、persisted/runtime rollback 和 retry 合同；不新增播放规则。R-PLAY、R-TX、PlaybackService、idempotency tests；**227 GREEN**。 |

Output baseline deep copy 的 executable protection：`test_enable_keeps_independent_output_baseline_when_port_reuses_models`。若 PlayerPort 复用模型，其它输出发生漂移也不能污染 before baseline 而被误判成功；没有要求修改生产 Mock/Adapter。

## RED → GREEN / Step evidence

1. enable 缺行为：`test_enable_preserves_other_outputs_and_all_playback_authorities[False-playing]`，**1 failed**，原代码抛 `OUTPUT_CONTROL_UNAVAILABLE`；最小 enable/确认/请求态/event registration → **12 passed**。覆盖六种播放/位置状态 × 真实启用/no-op；focused **118 passed**，diff check/status 检查。
2. 失败请求态：ACK-no-effect 用例 **1 failed**，last_request 仍 PREPARING；最小失败处理和有限回读 → **8 passed**，focused **126 passed**；原错误/取消传播、实际效果/cache/retry/unchanged 受保护。
3. outer rollback：外层失败用例 **1 failed / 1 passed**，last_request 残留 SUCCEEDED；经注入 lifecycle 注册 rollback cleanup → **3 passed**，focused **129 passed**；MPD enabled 事实保留且无成功通知。
4. shared output baseline：**1 failed（DID NOT RAISE）**，其它 output 对象被外部改变同时污染 captured baseline；deep copy → **1 passed**，focused **150 passed**。
5. 补充既有语义 GREEN proofs：capability/selection/ID/漂移、commit failure/postcommit cancel/publisher failure、失败后 GET 断线的 cached actual、real Adapter fake TCP；不伪称这些补充测试各自触发了额外 production RED 周期。
6. 独立 review 修复：新 `test_enable_receipt_cannot_corrupt_last_confirmed_fact_when_later_offline`（真实启用/no-op）**2 failed**，调用方修改回执污染缓存，随后离线读取误报 INACTIVE；`_snapshot` 对 observation deep copy → **2 passed**。单次 fix pass 后重新取得 **227 focused/regression、53 F5+transport、193 invariants GREEN**，scoped Ruff/compile/diff check PASS；完整 backend **630 passed**。没有修改合同语义。
7. 非预期失败按 systematic debugging 定位：random-drift 测试写入 `_random` RNG，真实 status 读取 `_random_enabled`；只修测试注入字段，exact case **1 passed**、当时 F5 **43 passed**。Ruff 初次 2 个 import layout finding，按实际建议仅整理当前 imports，复跑 scoped Ruff PASS；未更改合同/production 来迁就测试、未抑制检查。

原 B1 service test 的“NAS 所有控制均拒绝”只保留 B6 之前的 disable 拒绝断言；enable 已由真实 F5 control/capability proofs 替代，不是为了逃避 failure 放宽断言。

## 本轮实际验证

所有命令从 repo root 使用 `.venv/bin/python`。

```bash
.venv/bin/python -m pytest -q server/tests/services/test_output_manager.py server/tests/invariants/test_output_enable.py server/tests/invariants/test_output_transport.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_output_lifecycle_injection.py server/tests/player/test_task1r_step4.py server/tests/player/test_task1r_step5.py server/tests/player/test_task1r_step6.py server/tests/player/test_task1r_step7.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/services/test_playback_service.py server/tests/integration/test_task3_events_and_mpd.py server/tests/repositories/test_transaction_commit_hooks.py
# 227 passed

.venv/bin/python -m pytest -q server/tests/invariants/test_output_enable.py server/tests/invariants/test_output_transport.py
# 53 passed

.venv/bin/python -m pytest -q server/tests/invariants
# 193 passed; includes architecture relationship check

.venv/bin/python -m pytest -q server/tests
# 630 passed

.venv/bin/python -m compileall -q server
# exit 0

.venv/bin/python -m ruff check server/app/services/output_manager.py server/tests/services/test_output_manager.py server/tests/invariants/test_output_enable.py server/tests/invariants/test_output_transport.py
# All checks passed

git diff --check
# exit 0
```

无 skip/xfail；仅现有 FastAPI/Starlette httpx 弃用警告。没有环境/依赖失败。普通全 suite 不替代 F5/F1/F3/F4/F4L 和 Matrix 逐 row proof。

## Changed-files / future isolation / remaining acceptance

- Production：只修改 `server/app/services/output_manager.py`（enable、请求态、公共 failure/reconcile、lifecycle/event 注册），约 90 substantive 新行；无 disable 实现、API 接线、Task 6/10、播放器/DB/事件接口重写。
- Tests：新增 `server/tests/invariants/test_output_enable.py`（F5）和 `test_output_transport.py`；直接修改 `server/tests/services/test_output_manager.py` 的 B1-only refusal 范围。
- Docs：active Task 7 Plan 只维护 F5 实际存在性/B5 局部状态和本文件引用；本文件只记录 acceptance evidence，不定义第二份合同。
- `.venv`、依赖、音乐文件、运行时数据库、部署、Web、认证、README、其它生产/测试文件未修改。
- 独立只读 reviewer：Critical 0、Important 1、Minor 0；独立 focused **157 passed**、直接 required regression **32 passed**，diff check PASS。Important finding 已经本轮作者机械复现并修复，见下；无未处理 finding / deferred minor / Contract Gap。
- **B5 本地 acceptance 满足，Relationship / Contract Matrix Gate 均 REQUIRED / PASS，无 blocker / Contract Gap，可进入 B6 独立 pre-flight。**
- O-ENABLE-001 Service proof GREEN；O-FAIL-001/O-STATE-001 的 disable 扩展仍 B6，O-PRESERVE-001 两操作最终 proof 仍 B6，O-TX-001/O-EVENT-001 最终 REST integration 仍 B8；Task 7 不宣称完成。物理 DAC/真实 NAS 属后续硬件验收，本 Batch 未执行也未要求。
- active plan 未明确要求 push，本轮只按用户 Batch commit 指令在通过全部 gate 后提交；不 push/PR/merge。实际 commit SHA、branch HEAD、changed files、clean tree 和 fresh remote ref 在最终报告及忽略的 ledger 中二次确认。

独立 review 的范围裁定（不定义新业务语义）：
- disable 由 B6 所有：本轮无 disable acceptance。
- About/read API/composition 由 B2/B7 所有且未变：本轮无更新的 API/About evidence。
- HTTP serialization/terminal-write/replay integration 由 B8 所有：Service witness 不完成 HTTP final proof。
- 整个 Task、live MPD/物理 DAC、Docker、merge readiness 不属本地 B5：本轮不取得这些验收。
- reviewer 未重建历史 RED：本轮 RED 来自作者实际输出，历史 RED 未由 reviewer 独立认证。
- acceptance archive 不属 reviewer 的代码包：文档由作者对照实际证据审计，没有独立文档 review。
- review 范围使用本轮 B5 基线到实际工作 diff，而非重开整个未完成 Task 分支；成本是之前 Batch 未获新的代码审查，但明确历史回归已执行。

使用 user 指定 checkout/branch 和既有环境；按 finishing skill 保留本分支，用户已经禁止未授权 push/PR/merge，不重复要求整合选择。active-plan scratch 保留供未来 Batch，未删除已有文件。
