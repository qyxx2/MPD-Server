# Task 9 B02 acceptance — T9-B02-A01

日期：2026-10-10，Asia/Shanghai。范围仅B02普通歌曲原子Play Now后端prerequisite。分支`feature/task-9-web`，HEAD/BASE `14c6239283f4fed079f07ab817964b23e87e793c`；开始时B01及Task9文档已有未提交改动，全部保留。没有commit/push/PR/merge，没有进入B03或接入普通歌曲菜单。

## Gate 状态

| Gate | 证据 / 状态 |
|---|---|
| B01前置 | 最新真人关闭记录已核对；当前AppShell/持久owners存在，本轮共享壳/通知/背景3文件14项通过；没有要求用户重做手机验收 |
| G9-01 / Contract | CLOSED：用户批准建议并授权冻结后直接B02；唯一Playback Spec §3.3.1 PB-SONG-NOW-001。审阅中暴露不可用pending边界，用户另行明确选择整次拒绝并保留队列后冻结；没有自行选择跳过/删除语义 |
| 实现 | DONE：additive POST `/api/playback/songs/{song_id}/play`，单Service外层编排，Queue新MANUAL occurrence；既有Queue行入口、Start Track/集合公共结果保留 |
| 新API / Relationship | PASSED：2文件36项；精确主节点先真实HTTP405 RED，后GREEN；重要审阅问题分别精确RED→GREEN |
| 指定受影响回归 | PASSED：10文件209项；最初与最终各跑一轮，最终覆盖全部生产修改 |
| Wire / typecheck / Ruff | PASSED：后端wire fixture3、Web wire23、typecheck、6个Python文件定向Ruff；未改DTO/schema/依赖 |
| 完整后端回归 | PASSED：最终代码`.venv/bin/python -m pytest -q server/tests` → 1434 passed / 1既有warning / 107.35s |
| LAN / phone HUMAN | N/A：B02无独立UI，普通歌曲手机菜单交B05，不使用B01历史URL冒称B02交付 |
| 真实MPD/NAS/DAC | NOT RUN：真实SQLite/Services/API与显式MockMPD；不代表物理设备通过 |
| PWA | DEFERRED |
| B03及以后 | NOT STARTED |

## 合同→owner→proof

唯一长期合同：[PB-SONG-NOW-001](../../specs/2026-09-24-playback-model-queue-semantics-design.md#331-普通歌曲原子-play-now--pb-song-now-0012026-10-10-已冻结)。矩阵稳定ID `T9-SONG-001`，共同字段D0继承Architecture §4.1–4.2/§12及Playback §8.9.4–8.9.6；不创造另一份领域合同。

| 关系 / 不变量 | 实际owner | 本轮proof（完整节点名位于两个新test_song_play_now.py） |
|---|---|---|
| 新MANUAL ID、同song重复pending身份/来源/context/相对序保留、old current→Played、会话内Context/session保留、Queue revision+1与joint event | QueueRepository/QueueManager.play_song_now、PlaybackService.play_song_now | invariant `test_new_occurrence_preserves_pending_identity_and_joint_state` |
| 明确Stop后新Context/session、清旧current/Played、保留pending provenance；Stop标记可回滚且任何确认开始均消费；重启/STOPPED不补造Stop来源 | PlaybackService._set_explicit_stop、confirmed save及HistoryService | `test_explicit_stop_starts_new_context_and_session_preserving_pending`、`test_confirmed_start_consumes_prior_stop_provenance`；lifecycle九分支含restart-stopped |
| 初始/Context缺失、PAUSED、same song、关闭AutoPlay意图、unknown外部STOPPED、无绑定、不可信active无旧History原因 | PlaybackService、现有History认证和ExecutionSynchronizer | `test_lifecycle_does_not_infer_stop_or_reuse_song_occurrence` |
| 提交前不可见、old token失效、新target须提交后fresh observation；Queue/Playback/History联合提交与通知 | 现有外层transaction/realtime/current-target owner | `test_new_target_and_joint_state_are_hidden_until_outer_commit`及主节点；提交失败节点保留joint baseline |
| 命令/确认/terminal/materialization/outer commit/取消失败恢复本地，无成功record/notification；外部副作用不假称回滚 | 现有RecoveryJournal/ExecutionSynchronizer/transaction/idempotency middleware | `test_failures_restore_joint_state_without_success_notification`六分支 |
| 固定ID/新Context/AutoPlay allocation、confirmed add或play前缀不重发、unknown add响应不按URI认领；成功terminal replay无重复控制 | 固定allocation/账本、Service请求基线 | `test_retry_keeps_fixed_occurrence_and_owned_execution_prefix`四分支、`test_new_context_and_autoplay_allocations_survive_terminal_retry`两分支 |
| 同failed key固定原operation/base generation/revision，竞争current或Queue revision推进后fail closed；同key换payload409，新key新occurrence | Service请求身份与现有middleware terminal优先 | `test_failed_key_retry_cannot_become_new_intent_after_competing_mutation`两分支；API `test_failed_intent_cannot_change_payload_and_new_key_is_distinct`；invariant `test_keyword_service_retry_preserves_fixed_request_identity` |
| key必需、selected missing/unavailable与pending MISSING/UNREADABLE预检先于控制/失效token，整次拒绝保留原事实；DTO及replay/payload/path冲突 | API、Service availability preflight、existing QueueItemResponse | API `test_key_required_and_unavailable_validation_precedes_control`、`test_unavailable_pending_rejects_before_control_preserving_entire_queue`、`test_replay_returns_original_occurrence_after_current_changes` |

当前Context模型只有持久Context ID；保留ID时沿用Service从Queue重建候选范围，不新增Context仓储或schema。新单曲Context用固定operation分配ID；新Context清Played只影响临时Queue，不删除永久History。

## 自动验证与环境

既有Linux ARM64 `.venv`：Python3.14.4、pytest9.1.1、ruff0.16.9；已读取`server/requirements.txt`，环境/依赖未修改。测试从仓库根运行，日志留在忽略目录`.superpowers/sdd/2026-10-10-task-9-web-batch-plan/`。

- 精确主节点：`.venv/bin/python -m pytest -q server/tests/invariants/test_song_play_now.py::test_new_occurrence_preserves_pending_identity_and_joint_state`，缺失endpoint实际405 RED→1 GREEN。原计划Expected404修正为实际已有fallback405，未用import异常当行为证明。
- 新文件：`.venv/bin/python -m pytest -q server/tests/invariants/test_song_play_now.py server/tests/api/test_song_play_now.py` → **36 passed**。
- 指定回归：`.venv/bin/python -m pytest -q server/tests/services/test_playback_service.py server/tests/services/test_queue_manager.py server/tests/api/test_idempotency.py server/tests/api/test_mutations_playback.py server/tests/invariants/test_realtime_queue.py server/tests/invariants/test_realtime_playback_transport.py server/tests/invariants/test_playback_control_target.py server/tests/invariants/test_playback_guarded_transport.py server/tests/invariants/test_d6_history.py server/tests/invariants/test_d6_execution.py` → **209 passed**（`b02-final-regression.log`）。
- `.venv/bin/python -m pytest -q server/tests/api/test_web_wire_fixture.py` → **3 passed**；`npm --prefix web run test -- --run tests/invariants/wire.test.ts` → **23 passed**；`npm --prefix web run typecheck` → exit0。生产最后修改后复验，未创建新Web UI或构建/LAN Gate。
- `.venv/bin/python -m ruff check server/app/api/playback.py server/app/services/playback_service.py server/app/services/queue_manager.py server/app/repositories/queue_repository.py server/tests/invariants/test_song_play_now.py server/tests/api/test_song_play_now.py` → **All checks passed**。仅对新invariant文件做一次import排序fix并检查diff，未全仓库fix。
- 完整后端：`.venv/bin/python -m pytest -q server/tests` → **1434 passed, 1 warning in 107.35s**（`b02-full-server.log`）；最终关键字retry修复后重跑，不以先前1433结果替代。
- 既有Starlette/httpx弃用warning保留；不安装httpx2，不将warning误称测试失败。

## 独立审阅、修复与裁决

一次只读独立审阅，审阅者实跑初版24项通过，但发现3个Important：失败key在其他变更后重新分配occurrence、不可用pending边界未闭合、失败key换payload错误502。没有Critical或Minor。一个修复阶段内：竞争current/Queue的200→502、换payload的502→409、pending预检提前保留token均精确RED→GREEN；边界先由用户选择并冻结。补充生命周期检查发现Stop标记未由旧Queue/Start/collection开始消费，三个精确RED→GREEN，加入初始/Stop后的terminal retry固定新Context与AutoPlay IDs证明。最终接口核对另以精确RED复现关键字形式 `song_id=...` 的失败请求重试IndexError，最小参数归一化修复后精确节点及两个新文件通过，随后重跑指定与完整回归。没有第二次独立审阅；依执行技能以针对性测试和完整回归完成修复证明。

本轮裁决及其限制：

1. 使用现有Task9分支/checkout与`.venv`，按此前分支偏好及用户直接执行授权推进，不再复制dirty B01或重复请求设计批准；改动保持未提交，代价是需在最终Git diff中区分原B01与B02。
2. Context按实际持久ID+Queue重建读取，保留旧项provenance；不虚构独立资源。若未来要求保留原集合未入队的完整候选范围，需要独立Context存储合同，不由本批次补定。
3. token可用性沿用提交后fresh observation，不能要求cached get凭空产生样本；原测试前提已按Architecture合同纠正。无新采样表示时仍允许control_target=null。
4. after-add retry允许首次执行尚未发送的play；after-play/terminal retry禁止重播。原before-play阶段的“零play”假设已纠正，不能把继续固定计划误称重放。
5. raw TimeoutError仅在新增route映射现有PlayerUnavailable503；其他旧API不改。部分执行unknown仍fail closed，不承诺物理回滚。
6. pending unavailable的整次拒绝由用户批准；新入口不绕开完整执行映射。代价是需先处理不可用pending，才能从普通入口立即播放；不静默移除用户内容。
7. 竞争Queue proof使用真实QueueManager独立推进revision；失败执行使旧binding无法确认时，普通Service pending API本就拒绝，测试不冒称其成功。证明的是原key基线不能被重分配；多客户端现实顺序由共享串行边界处理。

审阅者明确未独立验证的项目及本轮处置：真实MPD/DAC/手机/browser为NOT RUN/N/A；B01和B03以后不修改；指定/full/wire/typecheck由主执行者fresh运行；并发runner/current与连接代次的完整组合不宣称穷举，新竞争基线/unknown前缀及现有D6回归承担机械证明；跨进程unfinished exactly-once由Spec明确不承诺；旧Queue/Start/Stop的其他缺陷不在范围，指定回归保护受影响合同。无未关闭Critical/Important、无deferred Minor。

## 最终检查与关闭

最终完整后端1434项通过；实际生产/合同diff已阅读，git diff --check通过，diff --stat/status已区分既有B01与本轮B02。B02实现、自动/关系及G9-01合同Gate CLOSED；B03–B10仍NOT STARTED。所有改动未提交，HEAD仍14c6239。没有Docker、live MPD操作、依赖/schema变化或运行时文件删除；已有本机数据库/服务与B01产物保留。
