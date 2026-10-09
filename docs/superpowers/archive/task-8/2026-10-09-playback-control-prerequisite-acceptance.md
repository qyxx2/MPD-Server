# Task 8 后端控制前置 P1/P2/P3 本地验收记录

日期：2026-10-09。范围仅 P1→P2→P3；用户已接受并授权执行当前未提交计划及 Spec。当前分支 `docs/web-common-contract-preflight`，基线与 HEAD 为 `e3a15b3`。无 commit/push/PR/merge；不进入 Web/PWA/Task 9。

## 环境与保留

使用现有 `.venv/bin/python`：Python 3.14.4、pytest 9.1.1、ruff 0.16.9；环境检查成功，无环境失败。未安装依赖、未修改 .venv、未使用 Docker、未联系真实 MPD/NAS。测试使用临时 SQLite、真实 Repository/Service、MockMPD，以及本地 TCP protocol fixture。

开始时已有修改，全部保留且本次未编辑：`docs/superpowers/README.md`、主 Implementation Plan、Library/Playback/Architecture 三份 Spec；原有未跟踪文件为 task-8 contract audit、playback-control prerequisite plan、web batch plan。

本次新增实现位于 `server/`，以及本验收记录；机器本地执行 ledger/log/review package 保存在 `.superpowers/sdd/2026-10-09-task-8-playback-control-prerequisite-plan/`（git ignored，继续保留，未提交）。未修改 DB schema、依赖、音乐文件、既有本地数据库、Web 代码。

## Contract 与自动 Gate

每个 Batch 的 Contract Matrix 和 Relationship Gate 均 REQUIRED。无新增产品语义；消费 active plan 的共同 11 字段及各专项 row。

| Contract ID | Spec authority | 实现 owner | 可执行 proof | 已运行结果 |
|---|---|---|---|---|
| PB-CONTROL-TARGET-001 | Architecture §4.2.1；Playback §7.1/8.8/8.9.2 | PlaybackControlTargets、PlaybackService、RecoveryJournal、PlaybackObservations | `server/tests/invariants/test_playback_control_target.py`（elapsed、同项重播、重启/重连、离开返回、rollback、不接受旧 rebind token） | P1 新文件最终 7 passed；P1 最终联合 Gate 162 passed |
| PB-RESUME-001 | Architecture §4.2.1；Playback §7.1/8.9 | PlaybackService.resume | `server/tests/invariants/test_playback_guarded_transport.py`；`test_mpd_adapter_tcp.py::test_parameterless_play_resumes_without_rebuilding_execution`；control API file | P2 最终联合 Gate 69 passed，API/terminal/replay 加入 P3 |
| PB-SEEK-TARGET-001 | Architecture §4.2.1；Playback §7.1/7.3/8.9 | PlaybackService.seek、SeekRequest、playback API | guarded transport file；control API file（跨切歌 replay、typed409、null拒绝、legacy） | P2/P3 targeted GREEN |
| RT-CONTROL-TARGET-001 | Architecture §4.2.1/12.1–12.3.1 | PlaybackObservation、PlaybackObservationResponse、PlaybackObservations | `server/tests/invariants/test_realtime_control_target.py`（GET/WS同表示、无I/O、outer visibility、stale null） | P3 最终联合 Gate 123 passed |
| TX-IDEMP-001、TX-ROLLBACK-001；PB-BINDING-001、PB-RECOVERY-RETRY-001；RT-SNAPSHOT/OBSERVE/PLAYBACK/RECOVER-001 | 既有 Architecture/Playback Spec 与 active prerequisite plan 的继承索引 | 既有 Repository/Service/coordinator/idempotency owners | 下列指定 regression，含真实跨 owner 联合路径 | 全部指定 targeted 命令 GREEN |

P1：实施及自动 Gate PASSED。P2：实施及自动 Gate PASSED。P3：实施及自动 Gate PASSED。后端 Web W4 自动依赖门禁满足；不代表 Web W4 或完整 Task 8 已实施/验收。

## 实际命令与结果

以下命令均从 repository root 执行。没有用 full-suite 替代 targeted acceptance。

环境：`test -x .venv/bin/python`；`.venv/bin/python --version`；`.venv/bin/python -m pytest --version`；`.venv/bin/python -m ruff --version`，全部成功。

P1 RED：`test_playback_control_target.py::test_elapsed_does_not_rotate_target` 因 observation 缺字段失败；随后生命周期各例因缺 guard 或返回旧 token 失败。P1 GREEN：

```sh
.venv/bin/python -m pytest -q server/tests/invariants/test_playback_control_target.py server/tests/invariants/test_d6_binding.py server/tests/invariants/test_d6_recovery.py server/tests/invariants/test_realtime_observation.py
```

结果：161 passed（`p1-green.log`）。原 rollback observation 节点经 Spec 要求的单字段调整后，精确重跑 1 passed。

P2 RED：resume 首节点因方法缺失失败；guarded transport file 8 failed/1 passed（legacy characterization）。TCP parameterless play proof 1 passed，Adapter 能力既有，未伪造 RED。P2 GREEN：

```sh
.venv/bin/python -m pytest -q server/tests/invariants/test_playback_guarded_transport.py server/tests/invariants/test_playback_control_target.py server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_transaction_relationships.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_realtime_playback_transport.py server/tests/player/test_mpd_adapter_tcp.py
```

结果：65 passed（`p2-green.log`）。resume 精确首节点 1 passed，新 transport file 9 passed。

P3 RED：replay 首节点先修复 test fixture import，然后确实因 target extra field 422 失败；API file 10 failed/2 legacy cases passed；GET/WS/no-I/O/stale 用例因 wire 缺字段失败；outer visibility 精确节点因 commit 只登记 queue domain 失败。P3 GREEN：

```sh
.venv/bin/python -m pytest -q server/tests/invariants/test_playback_control_target.py server/tests/invariants/test_playback_guarded_transport.py server/tests/api/test_playback_control_api.py server/tests/invariants/test_realtime_control_target.py server/tests/api/test_idempotency.py server/tests/api/test_mutations_playback.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_recovery.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_output_transport.py server/tests/invariants/test_d6_stock_joint.py
```

结果：119 passed（`p3-green.log`）。API/realtime 两个新文件 16 passed；两个直接受影响的旧 regression 精确重跑 2 passed。

定向 Ruff：覆盖全部修改/新增 Python 文件；全部通过。自动修复仅限 playback_service 的 import layout、playback API 的 import order、两个新增 test 的 __all__ 排序，已检查 diff。

完整后端回归、最终独立审查与最终 Git 检查结果见文末；均已执行。

## 实施裁定（完整列表）

1. 使用当前 checkout 并保留 scratch evidence：用户明确要求覆盖技能的建 worktree/commit/cleanup 步骤。代价：没有独立提交历史，证据本地保留。
2. 直接受影响的 rollback observation invariant 保留全部旧字段，唯新增 control_target 必须 null，并登记 read-side 失效：Architecture §4.2.1 禁止失效 token 复活。代价：旧 whole-object equality 仅对此字段被新合同替换。
3. legacy seek 与 Adapter parameterless play 的能力 proof 原本就 GREEN，不制造 RED：它们是消费的既有能力。代价：这些 proof 不声称新增实现了既有能力。
4. 完整空 DTO 的精确预期增加 control_target=None：Spec 已接受 additive 字段，保留所有旧断言。代价：完整结构 fixture 变更一字段。
5. 最终 review package 使用当前未提交 server diff 及完整 untracked 文件：用户禁止 commit，当前 Spec 未提交。代价：reviewer 检查 live checkout，不能只读 HEAD..HEAD。

普通技术选择：token 使用 UUID4，identity 含 service/connection/partition/binding generation/current occurrence/显式失效代次；elapsed 不轮换。snapshot 只读已有 token；stale 导出 null，fresh 后可重新确认同一连续绑定。resume 调用无参数 play，不改 Queue/Context/AutoPlay/History；已 PLAYING 先后确认后 no-op。position 确认允许 playing 的 monotonic 自然推进加 1 秒协议精度，paused 为 0.05 秒。命令或 terminal 失败回滚业务但不宣称撤销 MPD 副作用；失效 token 不恢复。首次实际 current/完整执行/mode 核验在 Service 边界，terminal replay 仍先由既有 IdempotencyService 返回，不执行 Service。

测试既有 Starlette/httpx deprecation warning 单列：不是环境阻塞，未按 warning 安装或升级依赖。

## 真实设备 manual gate

**NOT RUN**：目标 MPD/NAS 暂停已知位置→resume 原位；guarded seek→实际位置确认；切歌拒旧 target；断线后旧 target 失效。TCP fixture 与 Mock 不能替代真实设备验收。不宣称 Task 8 完整运行时验收。

## 独立整体审查与一次修复轮

fresh-context 独立 reviewer（gpt-6-astra/high）检查 live diff、新文件、合同及 ledger；无 Critical/Minor，提出两个 Important：

1. Stop 外部成功后 terminal rollback 可恢复旧 target。已先新增 `test_stop_terminal_rollback_never_revives_target` 并观察旧 target 被导出的 RED；在 `PlaybackService.stop()` 的 MPD stop 前不可逆失效 token。精确重跑 GREEN，旧 target 在同 entry 外部重启后仍拒绝。
2. 暂停原 elapsed=None 时 resume 会跳过位置确认并接受归零。已先新增 `test_resume_missing_position_evidence_is_not_success[before]` 并观察成功被错误接受的 RED；非有限原位置也单独 RED。暂停 resume 在 play 前要求有限原位置，缺失时按既有 reconciliation 错误边界失败，不发控制、不改业务；命令后缺失 elapsed 的既有拒绝分支另测 GREEN。已 PLAYING 的无控制 no-op 保持合同。

两个 findings 均在同一次最终修复轮关闭；精确位置证据节点 3 passed，直接受影响组合 49 passed。按 executing-plans 不进行第二次独立 review，修复关闭依据为 RED→GREEN 与后续完整回归。

修复后的原计划 targeted 门禁完整复跑：P1 **162 passed**（`p1-final.log`）；P2 **69 passed**（`p2-final.log`）；P3 **123 passed**（`p3-final.log`）。全部修改文件定向 Ruff **PASSED**（`ruff-final.log`）。前文初次执行命令/数量保留为过程证据，最终门禁以本节 fresh 结果为准。

reviewer 探针事件：首次直接调用 fixture 遗漏 observer 隔离，出现 `database is locked`，lifespan 创建默认 MPDAdapter；无法排除后台 localhost 连接尝试。已停止该探针；纠正后所有 reviewer 复现明确注入 MockMPD、隔离 observer，使用临时数据库。该 fixture 设置失败不是生产测试结果，也不构成真实设备验收。未由此修改环境、数据库或依赖。

reviewer 的 Declined to judge 由执行者作以下裁定：

6. 完全未被采样观察的外部 A→B→A 保留原版 MPD 已接受能力限制，不补造可检测性；代价：不提供无条件跨客户端连续性保证。
7. 目标 MPD/NAS 原位恢复与 seek 精度留待 manual gate，仍 NOT RUN；代价：部署行为尚无本轮真实运行时证明。
8. Web 与 Task 9 不进入本次实施/审查；代价：本次不交付这些客户端实现。

延期 minor：无。未关闭自动问题：无。

## 最终结果与 Git 检查

最终命令 `.venv/bin/python -m pytest -q server/tests`：**1392 passed, 1 warning，105.60s**（`full-suite-final.log`）；初次 broader run 1388 passed 保留为审查前证据，最终以本次结果为准。正式自动验证无环境失败；既有 deprecation warning 未触发任何环境变更。

最终 `git diff --check`、`git diff --stat`、`git status --short` 及实际 scoped diff 检查完成；无依赖/schema/Web/音乐文件或本地 DB 改动进入 Git diff。`git diff --stat` 仅显示 tracked 文件，另检查 untracked 列表：本次 6 个 server 新文件和 1 份 acceptance；原有 3 份未跟踪计划仍保留。实现共 16 个 scoped server 文件（10 modified、6 new）。机器本地 ledger/log/review package 为 git-ignored，继续保留以恢复执行记录。

HEAD 仍 `e3a15b3`，分支仍 `docs/web-common-contract-preflight`。按用户选定的 keep-as-is 收尾；无 commit/push/PR/merge/worktree/文件清理。

结论：P1/P2/P3 实施和自动 Gate **PASSED**；Web W4 的后端自动依赖门禁 **满足**。独立整体审查两项 Important 已修复并验证，无未关闭自动问题、无延期 minor。真实 MPD/NAS manual gate **NOT RUN**；不宣称完整 Task 8 运行时验收，不自动进入 Web。
