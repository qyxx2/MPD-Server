# Task 6 Batch 13 recovery proof / blocked final acceptance

日期：2026-10-04（Asia/Shanghai）。仅本轮执行证据，不新增/修改合同语义。

**状态：重连恢复 proof 已执行并 GREEN；Batch13 / Task6 最终 acceptance BLOCKED（D6-RECOVERY）。**

## 真实基线与 scope

实际核对 branch/status/HEAD/history：`feature/task-6-realtime-state`，`9d80532a1ae9cbd1c8eeae6e040a2731ea821edb`，开始 working tree clean。读取 README、主 Implementation Plan 的 Task6/Dependency/Relationship/Contract Matrix Gate、active Task6 plan 全11 rows/§5/B13，以及 A §12.1–12.3、P §2.2.1/§6–8.8、L §7.1、O §6.1–6.3/§8.1 和真实直接相关代码/测试；B12/Task4 acceptance 仅定位，其结论未作为当前通过证据。

使用 using-superpowers、executing-plans、using-git-worktrees、test-driven-development、systematic-debugging、verification-before-completion、requesting-code-review。按指定 checkout/branch 和既有 `.venv` 执行，无 worktree/依赖/environment/schema 修改。环境实测 Python3.14.4、pytest9.1.1、Ruff0.16.9；server/requirements.txt 已读。

前置 B11/B12/snapshot/API proof：**39 passed**。没有重新实施 B1–12 或恢复状态机，没有 Task8 store / Task10 配置 / Task12 物理测试。

## Contract Matrix Impact Analysis

- Owned：**RT-RECOVER-001 final、RT-SNAPSHOT-001 final**。
- Relied-upon unchanged：**全部 Task6 rows**，即 RT-SNAPSHOT/REVISION/LIBRARY/PLAYLIST/PLAYBACK/OUTPUT/HISTORY/OBSERVE/CONNECT/DELIVERY/RECOVER-001。
- Regression：active §4.3 全部 IDs：**EVENT-PORT-001、TX-ROLLBACK-001、TX-IDEMP-001、O-EVENT-001、O-STATE-001、PL-REP-001；PB-STOP-001、PB-INSERT-001、PB-REORDER-001、PB-DELETE-PENDING-001、PB-DELETE-CURRENT-001、PB-NEXT-UNAVAILABLE-001、PB-HISTORY-001、PL-COLLECTION-001、O-PRESERVE-001**。
- Relationship Gate：**REQUIRED；本批恢复关系 proof GREEN，Task-level final 被 D6 阻塞**。
- Contract Matrix Gate：**REQUIRED；11 RT rows 的下列 proof 本轮 GREEN，完整最终 Gate 未通过 D6**。
- 新增/修改 frozen rows：0。Contract Gap：未发现新增语义 Gap；D6 是实施/验收依赖 blocker，不是待猜测语义。

共同 U/T/F/I 保持：读取/网络不改变 Queue occurrence/order/CAS、Context、Playlist/Favorites、History active/session/永久事件、terminal 或 MPD 控制事实；仅合法 producer/观察的原 delta 允许发生。capture/register 与 outer commit 同边界，网络在锁外；提交前失败不伪成功，提交后交付失败不撤 terminal；read/reconnect 不重放业务，成功 mutation replay 不重复 producer/version。External Confirmation 来自 Service 已确认样本，未知/stale 明确，不以 socket send 作 ACK 或物理成功。

## Traceability → 本轮 fresh GREEN

下表路径相对 server/tests/invariants/；每项都纳入显式 realtime gate **251 passed**，不能拿 full suite 替代。

| Contract → authoritative Spec | Implementation owner / Expected Delta | Executable invariant proof / preservation-failure-retry |
|---|---|---|
| RT-SNAPSHOT-001 → A §12.1/§12.3 | StateService、Queue/History/Library facades；同一已提交 DTO、外部 freshness | test_realtime_snapshot.py::test_snapshot_is_one_committed_cut；required read failure / detached / committed-owner proofs；B13逐字段 Service/HTTP/WS 对照及本地失败1011/503后重试；没有读取业务 delta |
| RT-REVISION-001 → L §7.1 | Database visibility、RealtimeCoordinator；outer实际变化域+1、新epoch重置 | test_realtime_commit_visibility.py::test_committed_data_and_revision_become_visible_together；test_realtime_playlist.py::test_playlist_versions_follow_outer_delta_and_replay；no-op/rollback/cancel/replay/late-callback；restart数据保留而计数为0 |
| RT-LIBRARY-001 → A §7/§12.2、L §7.1 | LibraryScanner/Service/Repository；commit内容失效及原completion顺序 | test_realtime_library.py::test_outer_scan_waits_for_commit_and_keeps_completion_order；B13真实scanner AVAILABLE/MISSING/UNREADABLE，Playlist/Favorites/History引用保留、源媒体只读（仅tmp fixture移动/PermissionError注入） |
| RT-PLAYLIST-001 → L §5/§7.1 | PlaylistService/Repository；联合资源失效 | test_realtime_playlist.py::test_playlist_versions_follow_outer_delta_and_replay；B13创建/成员/Favorites精确3次版本、reconnect/restart保留资源，Library availability不伪增Playlist版本 |
| RT-PLAYBACK-001 → P §3–8、A §12.2 | PlaybackService producer wrappers；仅原已确认业务变化传播 | test_realtime_playback_transport.py::test_transport_event_waits_for_confirmation_and_outer_commit；test_realtime_queue.py::test_queue_only_notification_preserves_current_occurrence_and_history；test_realtime_transitions.py::test_transition_notification_matches_committed_history；B13重复Song Played/current/context及History/terminal保留 |
| RT-OUTPUT-001 → O §6.1–6.3、A §12.3 | OutputManager cache/control bridge；失效/缓存同步 | test_realtime_output.py::test_output_control_and_observation_share_delivery_without_history；B13 NAS_DAC关闭成功receipt与stale样本独立恢复，无歌曲History或重连控制 |
| RT-HISTORY-001 → P §2.2.1 | HistoryService availability；has_entries/active/session独立 | test_realtime_history.py::test_history_unavailability_preserves_events_and_has_entries；B13 unavailable仍返回永久事件；重启保留永久History，runtime active/session未知不伪造 |
| RT-OBSERVE-001 → P §8.8、A §12.3 | PlaybackService.observe、OutputManager、StateObserver；匹配缓存或unknown/stale | test_realtime_observation.py（迟到/重复URI/drift/重启）；test_realtime_observer_lifecycle.py::test_single_observer_retries_and_shutdown_preserves_playback；B13断线保留匹配位置17但stale，重启无fresh旧样本；D6领域恢复尚未验收 |
| RT-CONNECT-001 → A §12.2 | RealtimeConnections initial/live；先订阅再capture，水位覆盖 | test_realtime_handoff.py::test_last_mutation_during_initial_send_is_not_lost；registration/capture窗口、late callback与取消资源清理；B13本地失败不发成功首帧 |
| RT-DELIVERY-001 → A §12.2 | 独立queue/sender/invalidated monitor；失效关闭并清理 | test_realtime_delivery.py::test_overflow_and_timeout_isolate_clients_and_preserve_commit；B13容量1阻塞首帧1013后新连接直接恢复最后pause/seek提交、无旧增量重放 |
| RT-RECOVER-001 → A §12.1–12.3 | StateService + HTTP/WS 当前读取；完整替换旧表示，不加生产功能 | test_realtime_recovery.py::test_reconnect_replaces_all_domains_and_epoch（6组合）及overflow proof；api/test_realtime.py：barrier并发GET乱序、真实lifespan重启空/活跃两态、新epoch清比较基准、旧响应/相同sequence拒绝、本地失败后fresh全量retry；ProtocolProbe仅test harness，无Task8实现 |

继承/regression rows 的原 allowed delta、Must Remain Unchanged、confirmation、rollback/retry 与既有 authority 保持，执行 active §5 的 R-TX/R-LIB/R-PL/R-PB/R-H/R-O/R-ARCH 精确文件/selector union：**323 passed**。包含 architecture API不import repositories，Library reconciliation，PB/Playlist representation，History API，Output observation/control事务与幂等terminal证明。

## Step / RED-GREEN 事实

1. authority/Git/环境/pre-flight/前置proof 完成。
2. 先编写指定恢复 selector，再在原 production 上运行。首次6失败是测试误用 PlaylistService.repository；修正为真实_repository 后又暴露测试遗漏合法保留的旧Played occurrence。查阅既有Queue合同及replace实现后精确断言 `song_ids=[new,a,new] / positions=[-1,-2,0]`，保留更多既有关系；**6 passed**。
3. overflow和并发HTTP barrier首次运行即GREEN；真实重启首轮2失败为未知Output表示的读时updated_at变化，检查OutputManager后注入固定时钟，精确重跑 **2 passed**。本地失败后恢复 selector首次 **1 passed**。
4. 两个本批proof/API文件 **14 passed**。没有新增功能、bugfix或production行为修改，因此没有“因目标生产行为缺失正确RED→最小production→GREEN”的证据；fixture/setup failure不冒充RED，也未人为改坏代码制造RED。本批是既有行为的新增验收proof，不能宣称新的production TDD cycle完成。
5. 各focused结束检查diff/status；scoped Ruff只修复新增测试4处import layout。
6. 执行下列完整final regression和scope审查。提交Step未执行：D6 gate未通过，且active plan §5/Batch13要求另行commit/push授权。

## 实际验证命令与结果

全部仓库根目录、既有 `.venv/bin/python`，仅1条既有 Starlette/httpx deprecation warning，无环境失败。

```text
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_handoff.py server/tests/invariants/test_realtime_delivery.py server/tests/api/test_realtime.py server/tests/invariants/test_realtime_snapshot.py
# baseline 39 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_recovery.py::test_reconnect_replaces_all_domains_and_epoch
# 6 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_recovery.py server/tests/api/test_realtime.py
# 14 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_*.py server/tests/api/test_realtime*.py
# 251 passed, 21.32s
.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/integration/test_task3_events_and_mpd.py server/tests/repositories/test_library_reconciliation.py server/tests/services/test_library_scanner.py server/tests/api/test_library_api.py server/tests/invariants/test_playlist_relationships.py server/tests/services/test_playlist_service.py server/tests/api/test_playlist_reads.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_playback_service.py server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/repositories/test_task2_steps_5_7.py server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_lifecycle_injection.py server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# 323 passed, 17.88s
.venv/bin/python -m pytest -q server/tests/invariants server/tests/api
# 711 passed, 55.46s
.venv/bin/python -m pytest -q server/tests
# 987 passed, 59.80s
.venv/bin/python -m ruff check server/tests/api/test_realtime.py server/tests/invariants/test_realtime_recovery.py
# All checks passed
.venv/bin/python -m compileall -q server
# exit0
git diff --check
# exit0
```

## Blocker / final verdict

D6-RECOVERY 未满足：重新搜索当前docs/tests/history，未找到要求的专项acceptance；当前 PlaybackService.reconcile_external_status 仍对所有 STOPPED 禁用AutoPlay并调用History.stop，不能证明自然完成/显式Stop/未知原因分离、可用successor、确认后恰一次和失败rollback/retry的领域能力。HistoryService单独natural reason测试、B6显式reconciliation传播测试、普通全套GREEN不能替代此能力门禁。

根据 active Batch13 原文“若D6未通过，只能报告恢复proof已做/最终验收未通过”，本轮不宣称Batch13/Task6 COMPLETE，不启用自动恢复，不具备以Task6已完成为前提进入Task8的条件。没有新的Contract Gap，不自行补设计或越界实施Task4 corrective。

## Changed files / Git

- server/tests/invariants/test_realtime_recovery.py（新增，恢复关系proof/测试协议消费者）
- server/tests/api/test_realtime.py（追加API并发/重启/失败恢复proof）
- 本archive执行证据（新增）

完整tracked diff与untracked测试分别审查；无production、无无关格式化/refactor、future Task、合同改写、平行权威文档、schema/dependency/环境/DB变更。

实际 `git ls-remote origin refs/heads/feature/task-6-realtime-state` 与本地 `git rev-parse HEAD` 均为 `9d80532a1ae9cbd1c8eeae6e040a2731ea821edb`；该SHA是本轮起始提交，不是新commit。未commit/push/PR/merge，工作区保留本批测试与本文件。

## 独立 changed-files review

requesting-code-review / executing-plans 指定的独立 reviewer 读取两文件实际diff/新增内容与authority后：**Critical 0 / Important 0 / Minor 0**；独立运行两proof/API文件 **14 passed，1.84s**，diff --check通过。没有review修复或第二轮扩写。

Declined项目逐一裁定：

- D6-RECOVERY：保持独立前置，最终验收BLOCKED；代价是本批不能close/commit，不能拿transport proof替代领域恢复。
- 全11 rows与历史regression fresh gate的独立重复审计：root已实际执行251/323/711/987 GREEN并完成上表traceability，reviewer未重复所有历史审计；代价是这些完整门禁证据来自本轮root验证，不是第二份独立复验。
- Production client store：ProtocolProbe严格是测试协议消费者，Task8未实现；代价是客户端实现仍需其owner独立验收。
- 物理MPD/NAS/DAC/reverse proxy：留Task12，本轮只做本地确定性proof；代价是本轮不提供物理端到端结论。

本轮执行裁定：按用户指定checkout/branch使用既有环境（代价：没有额外worktree隔离）；无生产delta时如实记录新proof验证既有行为、不制造RED（代价：没有新production TDD-cycle证据）；D6不越界扩写（代价：最终验收持续BLOCKED）。没有deferred minor。
