# Task 8 Playback Control Prerequisite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Execution method remains user-selected; this document does not authorize agents or production implementation.

**Goal:** 为 Web 提供不串 occurrence 的 guarded seek 与原位 resume，保留现有调用兼容性。

**Architecture:** API → PlaybackService → 既有事务/recovery/PlayerPort；新增小型 runtime control-target owner，由 PlaybackService 管理。StateService 只表示已有事实，IdempotencyService 仍拥有 terminal replay。

**Tech Stack:** 现有 Python/Pydantic/FastAPI/SQLite/pytest；使用 `.venv`，不新增 Python 依赖。

**Spec:** Architecture §4.2.1、§12；Playback §7.1–7.4、§8.8–8.9；主 Implementation Plan 的 Matrix/Relationship Gate。

**Status:** 执行计划待审阅；所有新文件、接口和测试均为 TO CREATE，未运行、未验收。基础代码基线 `e3a15b3`，产品合同以同工作区更新后的 Spec 为准。

## Global Constraints

- 不修改音乐文件、数据库 schema、现有 Playlist/Queue 产品语义或 Task 9 song Play Now。
- 使用现有 `.venv/bin/python`，不安装/更新依赖；普通测试不连接真实 MPD、不启动 Docker。
- 无 target seek 保持兼容；Web 的保护来自新 target，不能宣称覆盖旧请求。
- full snapshot 只读，不发 MPD 命令；实际命令确认在 Service。
- runtime rollback 不可复活已丢失外部连续性的 token。
- 不自动 commit/push/PR/merge；本计划中的 Gate 不包含隐式 Git 写操作授权。

## Review Focus

- 相同 song/URI 不同 occurrence，以及同 occurrence 重播后的旧 token：P1 identity tests。
- MPD 副作用后确认/terminal 写入失败：P2 transport/rollback tests。
- 成功 replay 发生在切歌之后：P3 idempotency tests。
- 单纯 elapsed 与快照读取不得轮换 token 或执行命令：P1/P3 tests。
- pending Queue 变化触发重新绑定可能保守失效，不能误用旧 token：P1 binding tests。

## Contract Matrix 与 traceability

全部 Batch：Contract Matrix **REQUIRED**；Relationship Gate **REQUIRED**。

共同字段：Preconditions=已解析请求且通过既有幂等入口；Authorities=PlaybackService/recovery 与 MPD 实际事实，Repository 提交态；Transaction=同一 SQLite outer unit-of-work/Service 串行边界；History/Event=只在确认后登记 transport 变化，不新建 History；Failure=业务与 runtime 按既有合同回滚，外部副作用独立 reconciliation；Retry=同 key terminal 优先返回，失败不造 terminal。各行另列差异，11 个 Matrix 字段由本段和表格共同给出。

| ID | Preconditions / Expected Delta | Must Remain Unchanged | External Confirmation / Observable | Executable Proof / owner |
|---|---|---|---|---|
| PB-CONTROL-TARGET-001 | 有效绑定 current；发布或失效 token | elapsed 不轮换；不修改 Queue/History/Context | snapshot 导出 fresh target/null；错误目标 409 | `test_playback_control_target.py` / P1 |
| PB-RESUME-001 | 有效 target，实际 PAUSED 或已 PLAYING；确认后恢复/no-op | occurrence、位置连续性、Queue、Context、AutoPlay、active/session | 前后一致样本；PLAYING 后提交，无新 History | `test_playback_guarded_transport.py` / P2 |
| PB-SEEK-TARGET-001 | 有效 target 与 seconds；确认目标位置 | occurrence/Queue/Context/AutoPlay/History；失败无成功回执 | current 改变前拒绝或后确认失败；不向新 current 补发 | 同上 / P2 |
| RT-CONTROL-TARGET-001 | committed target + freshness | capture 不采样/控制；GET/WS 同表示 | target 改变失效 playback，outer commit 后交付 | `test_realtime_control_target.py` / P3 |

继承回归：TX-IDEMP-001、TX-ROLLBACK-001、PB-BINDING-001、PB-RECOVERY-RETRY-001、RT-SNAPSHOT/OBSERVE/PLAYBACK/RECOVER-001；Output 通过共享 transport owner 不应产生伪 playback change。旧 ID 定义以对应 Spec/既有 plan 为准，本表不重定义。

## 接口与文件归属

- 新建 `server/app/models/playback_control.py`：`PlaybackControlTarget(queue_item_id: str, token: str)`；字段非空。
- 新建 `server/app/services/playback_control.py`：`PlaybackTargetConflictError` 与 `PlaybackControlTargets`，只管理 runtime identity/opaque token，不依赖 API。
- `PlaybackControlTargets.publish(identity: tuple[object, ...], queue_item_id: str) -> PlaybackControlTarget`；同 identity 返回同 token。
- `invalidate() -> None` 使既有 token 永久失效；`read(queue_item_id: str) -> PlaybackControlTarget | None` 只读；`require(target: PlaybackControlTarget) -> None` 不匹配抛 typed conflict。
- identity 使用 service_epoch、connection_epoch、partition、binding_generation、current queue_item_id 与显式重播控制代次。允许受控重新绑定保守轮换，禁止 observation elapsed 自行轮换。
- 修改 `PlaybackService`：`resume(target: PlaybackControlTarget) -> PlaybackState`；`seek(seconds: float, *, target: PlaybackControlTarget | None = None) -> PlaybackState | None` 保持旧调用签名兼容。
- 修改 `models/realtime.py`、`api/realtime_schemas.py`：observation 增加 nullable control_target；`api/schemas.py` 增加 ResumeRequest 和 SeekRequest.target（省略合法、显式 null 拒绝）。
- `api/playback.py` 只做 schema→Service 和 typed 409 映射；不读取 journal。API response 仍是 PlaybackStateResponse。

token owner 生命周期：Service 构造时建立 owner；已确认 binding/current 发布时更新，普通 observe 可读取/在新确认 identity 时发布，但 snapshot get 不 mint。显式 current-changing 操作在可能开始 MPD 副作用前作保守失效，包括同 occurrence play_now；失败可以保持不可用直到新的确认，但不得复活旧 token。绑定失效路径同步 invalidation，查询时再次比较实际 journal identity，防止漏钩子。新 token 仅在确认且事务可见后对外可读，rollback 清除候选；已失效的旧 token 不恢复。无需持久存储 token。

## Batch P1 — target 生命周期与 Service 守卫

**Files:** Create models/playback_control.py、services/playback_control.py；Modify models/realtime.py、services/playback_service.py、playback_observation.py、playback_recovery.py；Create `server/tests/invariants/test_playback_control_target.py`。以上路径均在 `server/app/`，测试除外。

**Interfaces:** 产出上述 owner 与 typed conflict；get_observation 暂可在内部模型携带 target，public wire 接入由 P3 验收。

- [ ] RED：新增 `test_elapsed_does_not_rotate_target`，断言真实 Service 多次 observe 后 token 相同且 Queue/History 无变化；运行 `.venv/bin/python -m pytest -q server/tests/invariants/test_playback_control_target.py::test_elapsed_does_not_rotate_target`，确认因缺失能力失败。
- [ ] 实现 owner 与模型、确认/失效接线，保持 snapshot 只读。
- [ ] 增加并逐个 RED→GREEN：`test_old_target_rejected_after_same_item_replay`、`test_restart_and_reconnect_reject_old_target`、`test_current_leaves_and_returns_rejects_old_target`、`test_rollback_never_revives_invalidated_target`、`test_pending_rebind_cannot_accept_stale_target`；使用实际 Repository/Service/MockMPD，不能只测 token 字符串。
- [ ] 运行新文件及 `.venv/bin/python -m pytest -q server/tests/invariants/test_d6_binding.py server/tests/invariants/test_d6_recovery.py server/tests/invariants/test_realtime_observation.py`。
- [ ] 定向 Ruff、diff 检查；记录 Contract→test fresh GREEN，P1 Gate 通过后再接 P2。

## Batch P2 — 原位 resume 与 guarded seek

**Files:** Modify `server/app/services/playback_service.py`、`playback_control.py`；Create `server/tests/invariants/test_playback_guarded_transport.py`；必要的协议证明写入现有 `server/tests/player/test_mpd_adapter_tcp.py`，不做无关 Adapter 重构。

**Interfaces:** 实现 resume/seek Service 签名；复用 PlayerPort.play() 无参数恢复，禁止 queue_play/play(uri) 重播。若实际协议证明显示 play() 不满足原位合同，停止该实现并修订 port 方案，不能悄悄重播。

- [ ] RED：`test_resume_preserves_occurrence_position_and_history`，在暂停 37 秒的真实 Service 场景中断言恢复 PLAYING、位置不归零、Queue/Context/active/session/AutoPlay 不变；运行对应 node。
- [ ] 先在 TCP 协议 fixture 证明发送无参数 play 且无 clear/add/playid/seek；再实现前置 target+完整 sample 校验、命令和后置确认。已 PLAYING 分支无 play 命令。
- [ ] RED→GREEN：`test_seek_target_conflict_sends_no_command`、`test_same_uri_is_not_same_target`、`test_external_drift_after_command_is_not_success`、`test_confirmation_failure_preserves_business_state`、`test_legacy_seek_stays_compatible`、`test_resume_noop_does_not_create_history`。
- [ ] 运行新文件、P1 文件及 `.venv/bin/python -m pytest -q server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_transaction_relationships.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_realtime_playback_transport.py server/tests/player/test_mpd_adapter_tcp.py`。
- [ ] 定向 Ruff、diff 与保留关系审计；P2 Gate 不把模拟器结果当真实 NAS 验收。

## Batch P3 — API、snapshot、幂等联合 Gate

**Files:** Modify `server/app/api/playback.py`、`schemas.py`、`realtime_schemas.py`、`server/app/models/realtime.py`；必要时 `services/state_service.py` 只调整映射；Create `server/tests/api/test_playback_control_api.py`、`server/tests/invariants/test_realtime_control_target.py`。

**Interfaces:** Architecture §4.2.1 wire 合同，protocol_version 保持 1；不修改 IdempotencyService 的 replay 优先顺序。

- [ ] RED：`test_seek_replay_after_current_change_returns_original_receipt`，首次成功→切歌→同 key replay，断言原 status/body、零新 MPD 命令和 History；运行该 node 后实现 API schema/route/error mapping。
- [ ] RED→GREEN：`test_resume_requires_target`、`test_explicit_null_seek_target_is_rejected`、`test_legacy_seek_without_target_is_accepted`、`test_token_conflict_is_typed_409`、`test_terminal_failure_does_not_commit_transport_state`。
- [ ] RED→GREEN：`test_get_and_initial_ws_export_identical_control_target`、`test_snapshot_target_capture_has_no_player_io`、`test_target_invalidation_waits_for_outer_visibility`、`test_stale_snapshot_exports_null_target`。target 尚未对外可见不得提前宣称可写。
- [ ] 运行 P1/P2/P3 四个新测试文件及 `.venv/bin/python -m pytest -q server/tests/api/test_idempotency.py server/tests/api/test_mutations_playback.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_recovery.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_output_transport.py server/tests/invariants/test_d6_stock_joint.py`。
- [ ] 按实际修改文件运行 `.venv/bin/python -m ruff check`；运行 `git diff --check`、检查实际 diff/stat/status，记录没有依赖/DB/运行时文件变化。

## 验收与交接

执行前按 AGENTS 验证 `.venv`、pytest、ruff；依赖缺失单列环境阻塞，不换环境。新测试节点必须先创建再执行；本计划不伪造既有测试名。

P3 自动 Gate 全部通过才能交付 Web Batch W4 的 target/resume 依赖；manual target-runtime gate 单列：现有目标 MPD 上暂停已知位置→resume 原位、guarded seek→实际位置确认、切歌后旧 target 拒绝、断线后旧 target 失效。真实设备操作需用户授权；未做则记录 NOT RUN，不能声称 Task 8 完整验收。

完成后输出 Contract ID→Spec→实际实现→测试命令→fresh 结果；P1/P2/P3 不以提交存在代替测试通过。实施过程中发现违反现有合同的缺陷只在必要范围修复并保留 invariant regression。
