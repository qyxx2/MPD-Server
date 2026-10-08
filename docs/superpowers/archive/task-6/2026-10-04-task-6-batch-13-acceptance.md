# Task 6 Batch 13 recovery proof / PASSED final acceptance

**当前有效状态（2026-10-09）：Batch13 / Task6 functional final PASSED。D6 S10/S11/S12已通过；原本地DB保留未验证独立记录；全部11 RT rows和RT-ACTUAL逐项追溯见[唯一D6 acceptance](../task-4/2026-10-04-task-4-d6-recovery-acceptance.md)文末S12。历史BLOCKED记录保留，不能替代最新证据。**

日期：2026-10-04（Asia/Shanghai）。仅本轮执行证据，不新增/修改合同语义。

**2026-10-04历史状态：既有重连恢复 proof 的历史 GREEN 保留；原版 MPD 新合同已定义，新实现/联合验收未执行；Batch13 / Task6 final BLOCKED（D6-RECOVERY）。**

> 下文各轮结果均有各自基线；最新门禁见文末“2026-10-09 S12 final acceptance”，不把历史状态作为新实施指令。

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

## 2026-10-04 D6专项重新核对（最新 gate 状态）

实际起始/结束HEAD为 `82391fcf6bb02a8bb480e99ea5be4a93ec43746b`，branch `feature/task-6-realtime-state`；起始clean。上文三份Batch13修改已经在该提交，两个Python proof本次未修改。上文命令与“没有新的Contract Gap”保留为历史记录，不作为本次D6结论。

唯一D6专项记录：[Task4 D6 acceptance](../task-4/2026-10-04-task-4-d6-recovery-acceptance.md)；active执行计划：[D6 corrective plan](../../plans/2026-10-04-task-4-d6-recovery-corrective-plan.md)。专项真实SQLite/Services/MockPort测试 `server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history` **1 failed**：无用户Stop请求，仅外部STOPPED，仍新增STOP History、清active/session并禁用AutoPlay。重复运行相同RED；没有fixture/environment失败。

本次发现Task4 D6领域Contract Gap：自然完成可信识别、外部漂移分类/确认/History reason、自然完成无可用歌曲终态、恢复retry转移身份及未知原因正向处理策略缺少权威定义。P §7/§8.8禁止错误归因，§10仍将精确Queue映射/故障恢复协议列为未决；不得从现有Next/delete/Mock事件或方法名补语义。Task6 G6-01–05已冻结的观察/传播协议不重开。本次按用户停止条件停止production implementation，未启用恢复loop。

本次fresh检查：Batch13 recovery selector **6 passed**；recovery/API两文件 **14 passed**；Stop/observation/History/playback基线 **57 passed**；R-TX **19 passed**；R-ARCH **3 passed**；新增D6 Python Ruff及compileall exit0。完整命令、RED差异和未执行Gate见上述唯一D6记录。

**最新状态：D6 Relationship Gate FAILED / Contract Matrix Gate BLOCKED；Batch13与Task6最终acceptance继续BLOCKED。** D6未完成，未进入“D6完成后”的完整final sequence；其余realtime/全部R集合/invariants+API/全套本次未重新执行，旧GREEN不得冲抵专项RED。无commit/push/PR/merge，不具备以Task6完成为前提进入后续Task的条件。物理MPD/NAS/DAC/reverse-proxy未执行。


## D6 Contract Gap Resolution / 人工 A（2026-10-04，最新 blocker）

用户明确选择A，唯一领域authority新增于Playback Spec §7/§8.9；[D6 corrective plan](../../plans/2026-10-04-task-4-d6-recovery-corrective-plan.md)已分解保守consumer合同、逐行为selectors及rollback/retry。当前完整事实只在[唯一D6 acceptance](../task-4/2026-10-04-task-4-d6-recovery-acceptance.md)，本节不复制领域定义或第二份实施计划。

consumer合同已闭合但未实施；自然完成生产因果证据来源仍缺机制/验证，D6-SOURCE BLOCKED。专项unknown STOPPED selector本窗口重复 **1 failed**；Stop/observation/History/playback基线 **57 passed**，仅基线，旧reconciliation成功断言需后续按新Spec迁移。未修改两个Batch13 Python proof，未运行本批最终sequence；历史GREEN不能解除当前RED/来源能力门禁。

**最新状态：D6 consumer definition CLOSED / implementation NOT COMPLETE；Relationship Gate FAILED；完整Contract Matrix验收及D6-SOURCE BLOCKED；Batch13与Task6 final acceptance继续BLOCKED。** 允许下一窗口从D6 Step2.1保守consumer TDD开始，不启用自动恢复，不扩展Task8，不将Fake completion输入当作生产来源proof。无commit/push/PR/merge。


## 2026-10-04 D6 consumer 实施后（最新 blocker）

实际 branch=`feature/task-6-realtime-state`，起始/结束 HEAD=`6b05d7f434024488a736db5be83ada82bb0abf91`；起始 clean。上文 consumer 未实施 / UNKNOWN RED 属历史状态。完整逐行为 TDD、修复、审查及验收只记录于[唯一 D6 acceptance](../task-4/2026-10-04-task-4-d6-recovery-acceptance.md)。

Step2.1 已闭合；Step2.2–2.7 可执行 consumer 实现/证明 GREEN，Step3 consumer PASSED。最终 D6+只读系统112 cases（其中 D6 98）、计划直接 focused/R-PB/R-H/R-TX/R-O/R-ARCH union355、额外 native `server/tests` 全套1087 passed；scoped Ruff/compileall/diff 检查通过。首次全套的两个本轮只读回归及独立审查的执行绑定 finding 已修复并 targeted 重验；既有 Starlette/httpx warning，无环境失败。两个 Batch13 Python proofs 实际 diff --exit-code unchanged。

**D6-SOURCE BLOCKED；完整 D6 验收 NOT COMPLETE；Step4、Batch13 与 Task6 final acceptance 继续 BLOCKED。** Fake completion validator 是 consumer 测试输入，不能验证生产因果来源、断线/重启 continuity 或真实重复 occurrence。额外全套 GREEN 不是“完整 D6 通过后”的最终验收序列；不解除 blocker，不具备以 Task6 完成为前提进入 Task8 的条件。

本轮未实施 producer，未启用 loop/API 恢复接线，未扩展 Task6/Task8；物理 MPD/NAS/DAC/reverse proxy、Docker/live MPD 均未执行。只用既有 .venv，未改依赖/环境，未 commit/push/PR/merge。


## 2026-10-04 S0 基线同步（最新 blocker）

branch=`feature/task-6-realtime-state`，HEAD=`6b05d7f434024488a736db5be83ada82bb0abf91`；已有未提交 consumer 修改全部保留。仅核对基线与同步 P/E/B，未修改生产或测试。用户指定 D6/realtime recovery/API 三文件本次 fresh **112 passed，1 warning，11.61s**（D6 98 + 本批 14），两份 Batch13 Python proof 无 diff；仅既有 Starlette/httpx warning，无测试/环境失败。完整依据见[唯一 D6 acceptance 的 S0 节](../task-4/2026-10-04-task-4-d6-recovery-acceptance.md)。

consumer Step2.1–Step3 已实施/验收，P 的旧时态/checklist 已同步；历史 RED 保留。生产因果来源/validator 尚未接线，D6-SOURCE 继续 BLOCKED，完整 D6/Batch13/Task6 final NOT COMPLETE。未进入 T §5/Batch13 最终序列；355/1087 等仅是前次记录，本次未重跑，不以三文件 GREEN 解除来源门禁。S1 及后续未执行，未启用恢复 loop，未 commit/push/PR/merge。

## 2026-10-04 原版 MPD 合同迁移（当时 gate；最新见S12）

当前HEAD=`651aade83d0df52601f4555e0a682c9f16afd25e`，branch=`feature/task-6-realtime-state`。本轮文档修订；两份Batch13 Python proofs未改、未运行。旧源码/consumer存在已核对，历史GREEN不作为本轮执行证据。

用户授权由严格自然SOURCE迁移为[F §8.9](../../specs/2026-09-24-playback-model-queue-semantics-design.md)的原版MPD合同，补充[A §12.3.1](../../specs/2026-09-25-system-and-development-architecture-design.md)实际identity/未绑定表示。SOURCE是SUPERSEDED而非PASSED；原strict natural/empty proof仅历史consumer。原有11 RT rows的切面、只读、epoch/sequence、完整首帧和迟到响应拒绝继续保留，新增RT-ACTUAL以及D6 binding/current/提前执行/History真实性/部分执行/runner验收。

唯一实施计划[P S0–S12](../../plans/2026-10-04-task-4-d6-recovery-corrective-plan.md)；唯一证据[E最新节](../task-4/2026-10-04-task-4-d6-recovery-acceptance.md)。S2–S9未实施，S10新本地联合proof未创建/执行，S11目标运行时未执行，S12本批最终序列未执行。正常刷新/换浏览器取得真实完整状态；服务/MPD重启后actual可重新采样，业务binding不得按URI认回，不能把旧current_song显示为已确认实际歌曲。

**Relationship Gate REQUIRED / BLOCKED；Contract Matrix新合同DEFINED / acceptance BLOCKED；D6、Batch13、Task6 final仍BLOCKED。** 不具备以Task6完成为前提进入Task8的验收条件。没有新实现完成、目标能力通过或新pytest GREEN声明；未commit/push/PR。

R1 同步（2026-10-04）：用户已接受重启后“恢复 actual 显示、明确播放操作经确认重建业务绑定”；仅刷新/换浏览器不丢失有效服务绑定。当前合同已定义，旧计划历史已从 P 移入 task-4 归档，当前执行仍仅 P 的 S0–S12。新实现/自动测试/目标运行时未完成，final 仍 BLOCKED。


## 2026-10-09 S12 final acceptance

D6已按S12完整顺序执行自动验收；本批指定selector6、两文件14、realtime251、invariants/API1072及server全量1355均fresh GREEN；七组T5 R集合逐条通过，scoped Ruff/diff/link/status通过。逐RT row和继承Contract的Spec→implementation→proof→fresh result只记录于[唯一D6 acceptance](../task-4/2026-10-04-task-4-d6-recovery-acceptance.md)文末S12，避免复制领域权威。Batch13 / Task6 functional final PASSED；本轮用户已授权提交、push、PR及合规合并main。原本地DB保留UNVERIFIED独立列为审计事件，不改变产品合同通过结论。旧API测试本地DB fallback隔离事件及owner修复/重新运行事实均保留于该记录，不能声称整个窗口无runtime DB副作用。Task8UI、Task12DAC/HTTPS仍未验收。
