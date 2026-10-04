# Task4 D6 原版 MPD 合同迁移与执行计划

> **For agentic workers:** 后续实现使用 `superpowers:executing-plans` 顺序执行；本轮仅文档。用户已授权合同修订，未授权本轮代码、测试、依赖、环境、schema/数据库修改、commit/push/PR、Docker/live MPD。本计划只有一份；归档中的旧 consumer 和旧 S0/S1 为历史记录，不是当前执行指令。

**Goal:** 保留原版 MPD 0.23.5，以可信当前 occurrence 接纳、提前执行队列和真实状态展示实现核心体验，不伪造自然完成或遗漏历史。

**Architecture:** PlaybackService 是唯一控制编排者；独立 runner 调用它，observer/GET/WS/snapshot 只读。Adapter 给出有界一致样本，Service 持有进程内绑定/固定执行意图，Repository 管理 CAS/outer transaction，实时层只传播已提交事实。

**Tech Stack:** 当前 Python/SQLite/asyncio/pytest，既有 `.venv/bin/python`，不引入包、schema 或后端扩展。

## 文档缩写、权威与读取规则

以下简称适用于本计划及本轮合同迁移；无需用户再次提供映射。路径链接就是对应文档，不按首字母猜测。首次执行必须读取 P/E/B/F/A/T/M/C；续作先核对 Git 和实际变更，再读取相关权威条款及当前验收状态。

| 简称 | 文档（完整文件名与链接） | 角色 / 使用时机 |
|---|---|---|
| P | [2026-10-04-task-4-d6-recovery-corrective-plan.md](2026-10-04-task-4-d6-recovery-corrective-plan.md)（本文） | 唯一 active D6 计划；当前 S0–S12、白名单、依赖和 proof 迁移入口 |
| E | [2026-10-04-task-4-d6-recovery-acceptance.md](../archive/task-4/2026-10-04-task-4-d6-recovery-acceptance.md) | 唯一 D6 验收记录；执行前后核对最新状态，历史 GREEN 不替代当前验收 |
| B | [2026-10-04-task-6-batch-13-acceptance.md](../archive/task-6/2026-10-04-task-6-batch-13-acceptance.md) | Batch13 联合门禁记录；S12 必读，D6 未满足时不能关闭 |
| F | [2026-09-24-playback-model-queue-semantics-design.md](../specs/2026-09-24-playback-model-queue-semantics-design.md) | 唯一领域语义 authority；§8.9 及所引用 Queue/History/AutoPlay 条款 |
| A | [2026-09-25-system-and-development-architecture-design.md](../specs/2026-09-25-system-and-development-architecture-design.md) | 架构、DTO、只读和提交传播 authority；§12.1–12.3.1/§19.5 |
| T | [2026-10-03-mpd-server-task-6-batch-plan.md](2026-10-03-mpd-server-task-6-batch-plan.md) | Task6 依赖与 Contract Matrix；§5 回归集合及 Batch13 门禁 |
| M | [2026-09-25-mpd-server-v0-1-implementation-plan.md](2026-09-25-mpd-server-v0-1-implementation-plan.md) | 总体 Task 依赖、Task4/Task6 边界与联合验收 |
| C | [mpd-0.23.5-capabilities.md](../../mpd-0.23.5-capabilities.md) | 目标版本实测能力记录；不以命令存在推断原因能力或未实测操作 |

优先以当前源码/Git 核查实施事实，以 F/A 决定合同；P/T/M 分解实施，E/B 记录证据，C 限定能力证据。发现冲突应停止相关步骤并修正文档，不能用旧测试或旧 GREEN 覆盖当前 Spec。E/B 虽位于 archive，仍承担上述最新验收状态记录职责。

旧文档或历史表中的 `P §8.9` 可能指 Playback Spec，即本表 F；不把旧简称带入当前步骤。人工“方案 A”也不是架构文档 A，须结合上下文识别。旧 consumer、旧 S0/S1 与废止步骤只见 [历史归档](../archive/task-4/2026-10-04-task-4-d6-recovery-plan-history.md)；只有追溯旧 proof、SOURCE 裁定或调查过程时读取，不作为执行清单。


## 当前状态与路线裁定

2026-10-04（Asia/Shanghai），branch `feature/task-6-realtime-state`，HEAD `651aade83d0df52601f4555e0a682c9f16afd25e`。起始 P/E 已有未提交 S1 调查，保留。`6b05d7f` 是旧严格合同，`651aade` 是 conservative consumer，`82391fc` 是 Batch13 proof；源码核查未发现生产自然 producer/validator 或恢复 runner。历史 GREEN 不作为本轮运行结果。

推荐 **预同步后续执行项 + 确认当前转移 + 剩余量补充**。拒绝 status/idle 推断 natural；不采用自定义 MPD。History 选择不持久记录未经认证离开，原因/时间 DTO 和 schema 不扩张。代价：永久历史不完整、A→C 时未观察 B 保留待播可能再次播放、未知停止不自动重启、服务/MPD 重启后实际状态可恢复而业务绑定需明确接管。不会以这些限制弱化 occurrence/手动顺序/只读/事务。

`D6-SOURCE = SUPERSEDED`：原能力要求被授权替换，绝非来源 PASS。`PB-NATURAL-001/PB-NATURAL-EMPTY-001` 只保留历史 consumer proof。新合同 DEFINED；新实施 NOT STARTED；本轮 pytest/运行时测试 NOT RUN；D6/Batch13/Task6 final **BLOCKED**。新 S0/S1 与归档旧 S0/S1 不是同一轮编号。当前 S0 静态审计与 S1 主体文档已完成，R1重启接管限制已由用户接受；S0 的未来执行前测试复核仍待跑，S2–S12 未执行。

## S0 审计证据与官方 v0.23.5 复核

当前约束：原版 v0.23.5 无本合同要求的自然完成原因证明；一致快照只能接纳有效绑定内的当前 occurrence。多命令可部分成功，ID 可复用，idle 不提供事件日志。原始 probe 已取得并与 C 核对（105 commands、17 status fields，无 verified_operations）；第二轮原始 probe 未取得，目标运行时未验证。完整来源、摘要与调查过程见 [能力复核归档](../archive/task-4/2026-10-04-task-4-d6-recovery-plan-history.md#合同迁移时的能力复核记录)，实现前按需查证，不重复运行 live probe。

| 当前文件/方法 | 真实基线与新工作 |
|---|---|
| `server/app/player/ports.py` / `models.py` | 有 status/queue_entries/控制；缺一致 ExecutionSample、连接代次、playlist version/single/consume/error；S2补读取合同 |
| `server/app/player/mpd_adapter.py::status` | 顺序 status/currentsong，锁只约束本连接；未验证跨命令身份；S2加有界一致采样 |
| `server/app/player/capabilities.py` | VerifiedPlayerPort 命令/运行时操作门禁；九项不认证 natural；S2新读合同不自动加入 verified_operations |
| `PlaybackService.reconcile_external_status/_reconcile_completion` | 同 current pause/resume可确认；无 evidence 的新 current拒绝；自然分支依赖validator默认None；S5/S6迁移生产入口 |
| `PlaybackService._sync_player_queue` | 有按URI的fallback，不能作为新绑定证据；S3/S4覆盖服务控制路径，不能把重复项猜测遗留在新路线 |
| `RecoveryJournal` / `models/recovery.py` | 进程epoch/代次/pending/receipt存在；批量add完成后才登记execution，部分成功缺口；S4新增逐命令账本 |
| `QueueRepository.complete_current` | 单次CAS仅原自然后继模型；S6新增adopt_current保留未观察pending |
| `AutoPlay.plan_refill/refill` | 已有5/5、Context→全库、Queue排除/单曲fallback；S7保持策略，把规划/提交/同步分开 |
| `HistoryService.start_track/_finish_active/stop` | start会自动SWITCH_AWAY旧active；S5先校验/丢弃不可信active，不能借现有finalizer补原因 |
| `PlaybackObservations` | 当前binding是runtime tuple，匹配要求MPD position0；S3/S8改为完整映射，观察始终只读 |
| `StateService.get_full_snapshot` / `models/realtime.py` / `api/realtime_schemas.py` | current_song来自持久state；无actual identity；S8 additive字段 |
| `StateObserver` / `RealtimeConnections` / `api/realtime.py` / `main.py` | 只读sampler、完整首帧/失效/GET已存在，无领域runner；S9独立接线 |

## Contract Matrix 与旧 proof 迁移

以下共同字段是**每行、每步的合同组成部分**，不能在执行时省略：

- **U（保持）**：Library内容/revision、Playlist/Favorites及revision、Output observed/request/MPD outputs、已存在永久History/REST terminals、Context ID与未操作occurrence的ID/source/context、MANUAL相对顺序。新合同只允许行中delta；媒体只读、schema/dependencies不变。
- **T/F（事务/故障）**：同库outer/CAS及runtime hooks；最终完整MPD确认才提交业务；提交前失败/取消/materialization/terminal/commit失败恢复persisted/runtime，零成功receipt/通知；MPD副作用留账本，不假装回滚。提交后取消/发送失败不撤提交；可见性故障沿用A §12.2。
- **I（幂等）**：固定operation_id/基线/候选IDs/目标，逐命令前缀保存；同ID冲突抛PlaybackReconciliationError；已到目标不play；receipt先查，同ID同内容REPLAYED零控制/变化；失去归属UNKNOWN；REST replay不变。
- **O（观察）**：MPD真实事实与本地业务确认独立；HTTP/WS/observer不发控制、不写History/Queue，不借read修复。实际状态变化只更新观察及sequence，业务成功只在outer commit之后。

| Contract ID / type | authority / precondition / owner | delta、confirmation、History/输出 | proof owner |
|---|---|---|---|
| PB-BINDING-001 / REPRESENTATION | F8.9.2；明确控制后完整确认；Adapter+PlaybackService | 建立/失效进程映射；连接、partition、version、完整ID队列校验；无History；S2/S3 | test_d6_binding.py |
| PB-CURRENT-001 / STATE_TRANSITION | F8.9.1–3；有效绑定；PlaybackService | 目标事实可确认，原因未知；同entry不拆代次；不虚构中间播放；S6 | test_d6_current.py |
| PB-QUEUE-ADOPT-001 / STATE_TRANSITION | F8.9.3；精确目标+最终执行确认；QueueManager/Repository | A Played、目标0、未观察项留pending，一次revision+1；U/T/F/I；S6 | test_d6_current.py |
| PB-HISTORY-UNCERTIFIED-001 / STATE_TRANSITION | F8.9.4；active资格核对；HistoryService+PlaybackService | 未认证active可在领域转移中discard，不写永久History、不造时间；S5 | test_d6_history.py |
| PB-HISTORY-001 / modified | F8.9.4；本服务明确操作已确认 | 原reason保留，新增finalizer资格边界；自然consumer仅历史，S5/S6 | test_d6_history.py + 原Stop/Next proofs |
| PB-AUTOPLAY-EXEC-001 / STATE_TRANSITION | F8.9.5；有效绑定/允许模式/意图true；AutoPlay+Service | 按已确认剩余量5/5补充，完整同步后提交；Stop不重启；S7 | test_d6_autoplay.py |
| PB-RECOVERY-UNKNOWN-001 / modified | F8.9.1/2/5；不可确认、停止或漂移 | UNKNOWN/reconciliation_required，业务保留；无推断reason/控制；S3/S6/S8 | test_d6_binding.py/test_d6_current.py |
| PB-RECOVERY-TRANSPORT-001 / relied | F8.9.3；同绑定PLAYING↔PAUSED | 实际回读确认只更新transport；U/T/F/I；S3/S6 | 旧bound pause/retry + 新current |
| PB-RECOVERY-RETRY-001 / modified TRANSACTION | F8.9.6；固定意图；journal/Service | 前缀核验、业务rollback、commit receipt、非盲重发；S4 | test_d6_execution.py |
| RT-ACTUAL-001 / REPRESENTATION | A12.3.1；一致样本与本地快照；observation/StateService | additive实际identity/同步标签，旧current_song语义不变；O；S8 | test_d6_state.py |
| PB-RECOVERY-RUNNER-001 / LIFECYCLE | F8.9.7；S2–S8；PlaybackService/main | 单实例/预算/退避/Stop fencing，关停无Stop；S9 | test_d6_runner.py |
| D6-RECOVERY / joint gate | F8.9.8–9；真实Adapter/Services/SQLite | S10本地联合、S11目标能力、S12最终门禁；不以Fake自然原因替代 | test_d6_stock_joint.py + E |

Relied unchanged：PB-STOP/NEXT-UNAVAILABLE/INSERT/REORDER/DELETE-PENDING/DELETE-CURRENT-001、TX-ROLLBACK/TX-IDEMP/EVENT-PORT-001、PL-REP/COLLECTION-001、O-PRESERVE/STATE/EVENT-001。Regression：T 全11个 RT rows。Task4 无 Task8/WS 依赖；S8是现有Task6 owner的窄表示修改，S9 core不import网络层。

**旧 proof 分类（存在≠本轮执行）**：

1. 仍适用：`test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history`、`test_bound_external_pause_resume_preserves_history`、`test_transport_recovery_rollback_and_retry`；Stop确认、TX、只读observer、Batch13恢复/水位均保留回归。
2. 需迁移：`server/tests/invariants/test_d6_recovery.py::test_unknown_recovery_preserves_all_authorities[foreign]` 名字虽叫foreign，实际调用的是已绑定Queue中的 `player.play("b.flac")`，按新合同应APPLIED；不能继续断言UNKNOWN。将此参数拆成新stock成功proof（S6），保留真正陌生entry的UNKNOWN负向case；stop/duplicate/pending-duplicate/missing-id/queue-mismatch/unbound/elapsed-at-end继续保守。`test_recovery_binding_uses_the_confirmed_execution_sample` 保留原目的，用新Sample接口补完整映射。
3. 仅证明旧合同：natural successor/refill/empty、TestCompletionValidator、旧completion identity/rollback/replay。保留历史测试，不将NATURAL_COMPLETION断言放宽成任意reason；新建独立stock selectors证明新路线。旧consumer类型可暂留为隔离legacy路径，生产装配不注入validator，不由runner调用该路径。
4. `server/tests/services/test_playback_service.py::test_reconcile_external_status_updates_service_state_but_not_server_queue` 的start_track会预填b；新合同应让精确已绑定b变current、A Played、无永久History、active=None，而不是业务current=a。`server/tests/api/test_pre_batch6_corrective.py::test_reconciliation_outer_rollback_restores_history[foreign]` 同样是已绑定b：保留outer失败后全部恢复断言，retry按S4完成同一固定目标、无重播/新History，成功后active=None；stop/pause参数原语义不动。`server/tests/invariants/test_realtime_transitions.py::test_explicit_reconciliation_propagates_only_committed_existing_delta` 仅stop/pause，保留原业务断言，仅新绑定fixture接口可机械适配。
5. `server/tests/invariants/assertions.py::assert_execution_relationship` 只在新stock场景修订active可为空的前提；明确服务发起active/Stop/session断言仍保留，禁止一刀删除。新增专用helper核验current绑定/History未知，不能靠放松旧helper让测试绿。

## 公共执行纪律、接口与验证集

后续每个实现步骤（S2–S9）：先跑该步“已有”直接proof基线；创建本步列出的 **TO CREATE** 测试及literal assertions → 精确selector取得因目标行为缺失而失败的RED → 最小白名单实现 → **同selector** GREEN → 同文件 → 该步直接回归 → scoped Ruff与diff。fixture/依赖失败不算RED；首次即GREEN记为新增proof验证既有行为，不人为改坏代码。每个参数都执行，不以一个参数替代整组。并发测试中的 before_business 指被测试恢复尝试获得边界后、其它合法提交已经完成的基线；不能要求迟到样本撤销并发合法变更。未知的实现缺口若超出F/S1冻结接口，停止该步，不擅改合同。

路径约定：生产白名单均完整前缀 `server/app/`；测试下文均给全路径。除本步精确列出的文件/方法外不得改动。`server/tests/support/d6_stock.py` 为S2起可新增的专用fixture/计数/权威快照helper；`server/tests/integration/support/stateful_fake_mpd.py` 仅S2/S10允许扩展协议响应/屏障/故障，不新增自然原因能力。不改通用conftest来隐藏runner竞态。旧tests如因Port入口从status/queue_entries改为read_execution_sample而失去注入点，只允许相同故障语义的机械fixture迁移：上表明确consumer selectors、`server/tests/invariants/test_realtime_observation.py`/`test_realtime_transitions.py` 的绑定构造及source-failure注入；不得删原rollback/只读断言，新增实际sample失败proof必须同时通过。

新增内部类型（TO CREATE，除特别注明player/models.py外放 `server/app/models/recovery.py`，不进永久schema/REST）：

- `ExecutionSample`（player/models.py）：`connection_epoch:str, partition:str, playlist_version:int, status:PlayerStatus, entries:tuple[PlayerQueueEntry,...], single:str, consume:bool, error:str|None`；status保留repeat/random，样本观察时间由Service clock提供。类型不可变/深复制；没有completed/reason字段。
- `ExecutionBinding`：`service_epoch, connection_epoch, binding_generation, partition, queue_revision, playlist_version, entries:tuple[tuple[str,int,str],...]`。不同ID/URI/position组合不能合并。
- `ExecutionIntent`：`operation_id:str, binding:ExecutionBinding, expected_revision:int, target_id:str|None, final_items:tuple[QueueItem,...], commands:tuple[ExecutionCommand,...]`。`ExecutionCommand(kind:add|delete|move|play, queue_item_id:str, mpd_id:int|None, before_id:int|None, uri:str|None)`；`CommandReceipt(index:int, returned_id:int|None, confirmed_sample:ExecutionSample)`，状态sent/acknowledged/confirmed独立记录，unknown响应不可改成not-sent。
- `RecoveryResult` 保留 UNKNOWN/UNCHANGED/APPLIED/REPLAYED 和 reconciliation_required；diagnostic 使用A12.3.1标签。operation_id作为新路径transition_id回执值，不称MPD事件ID。旧CompletionEvidence仅legacy consumer使用。

固定直接回归集（命令从根目录执行；本轮未跑）：

```bash
# R-PB-D6
.venv/bin/python -m pytest -q server/tests/services/test_queue_manager.py server/tests/services/test_autoplay.py server/tests/services/test_playback_service.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/api/test_pre_batch6_corrective.py
# R-H-D6
.venv/bin/python -m pytest -q server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/invariants/test_realtime_history.py
# R-TX-D6
.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py
# R-OBS-D6
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_transitions.py server/tests/invariants/test_output_serialization.py
# R-ARCH-D6
.venv/bin/python -m pytest -q server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
```

下列 `T(path::selector)` 是精确命令展开 `.venv/bin/python -m pytest -q path::selector`；`T(path)` 为同命令整文件。不是未定义工具。每步U/T/F/I/O及本节RED/GREEN顺序均为必需字段，S0/S1/S10–S12非新实现不伪造RED。

## 新执行步骤（当前唯一有效 S0–S12）

### S0 — 当前基线、能力、proof和迁移审计

- **目标/排除**：确认真实checkout/源码/原始JSON/官方tag及已有proof；不重做旧consumer、不以历史GREEN做fresh证据。
- **Authority/依赖**：F8.9.1/9、A19.5，全部matrix IDs；无前置。HEAD/未提交范围不符即停止沿用此基线，更新E。
- **白名单/接口**：本轮只P/E/C及同步文档；无生产/测试白名单。输入Git、8份文档、JSON、源码/AST；输出审计表与proof分类；缺文件明确NOT OBTAINED，不能补造。
- **事实/事务/U**：全只读；无MPD命令、DB mutation、通知或retry；U全保留。
- **proof/验证**：本轮静态审计完成。未来执行前 `T(server/tests/invariants/test_d6_recovery.py::test_unclassified_external_stop_does_not_fabricate_history)` → `T(server/tests/invariants/test_d6_recovery.py)`；`.venv/bin/python -m pytest --version`、`-m ruff --version`。不为审计制造RED。
- **完成/gate**：记录实际结果后才开始S2；新SOURCE无法认证原因是限制而非待实现magic。当前静态DONE/上述测试NOT RUN，final BLOCKED。

### S1 — 新合同冻结与影响矩阵

- **目标/排除**：冻结F8.9/A12.3.1与上表、接口、状态机；不实施、不开第二份plan。比较History两路线并选择不记未知原因。
- **Authority/依赖/停止**：F8.9全部、A12.1–3.1；S0静态审计。若需要持久绑定、UNKNOWN History schema或无用户动作跨重启接管，超出已选路线，先提出具体合同修订，不默认后端扩展。
- **白名单/接口**：P/E/B/F/A/T/M/C；文档输入输出。执行期如改接口只改对应权威+本计划；不修改生产。
- **事实/事务/U**：新合同定义≠目标能力/实现证明，U全保留，无控制/通知。
- **proof/验证**：逐条检查12个场景→S2–S10 test映射、文档链接/selector存在性、`git diff --check`；S1非TDD，NOT RUN不能填GREEN。
- **完成/gate**：本轮合同DEFINED，R1重启接管子合同已由用户接受；最终实现门禁仍BLOCKED。以下S2–S12全未执行。

### S2 — 一致执行样本与只读能力门禁

- **目标/排除**：只读准确提供current/完整queue/version/modes/connection epoch；不生成完成原因、不注册业务绑定、不写Queue。
- **Authority/依赖/停止**：PB-BINDING/PB-CURRENT，F8.9.1/2/5；S0执行前复核+S1。目标命令/字段缺失、冲突两次或断线则UNKNOWN/typed error，不能fallback到URI拼接。
- **白名单**：`server/app/player/models.py` ExecutionSample；`ports.py` PlayerPort；`mpd_adapter.py::read_execution_sample/_ensure_connected/close`；`capabilities.py::VerifiedPlayerPort`；`mock_mpd.py` 同接口；专用support文件及下列测试。
- **接口**：新增 `PlayerPort.read_execution_sample() -> ExecutionSample`。Adapter一次本连接lock内status→playlistinfo→status（必要currentsong须验证），至多2次attempt；不一致抛 `PlayerCommandError(command="read_execution_sample", message="inconsistent execution sample")`；失联原PlayerUnavailable，取消弃连接并原样传播。VerifiedPlayerPort要求status/playlistinfo命令，不自动标transport verified；greeting/连接生成本地connection_epoch。
- **确认/事务/失败**：输出只表示采样时事实；不含原子跨客户端承诺；T/F用于调用方接受样本，S2自身无业务事务/receipt。U全保留，O只读；没有控制重发。
- **TO CREATE** `server/tests/player/test_execution_sample.py::test_sample_rejects_torn_current_and_queue`，参数current/version/length/duplicate-id/position：`sample.status.song_id == sample.entries[sample.status.song_position].mpd_song_id`；冲突两次 `error.command == "read_execution_sample"; controls == []; attempts == 2`。
- **TO CREATE** 同文件 `test_sample_epoch_and_modes_are_not_completion_evidence`：`new.connection_epoch != old.connection_epoch; sample.single == "0"; sample.consume is False; sample.error == "decoder error"; "reason" not in sample.model_dump()`；error为空仍无reason；另含空队列STOPPED `sample.entries == (); sample.status.song_id is None`，STOPPED但仍选中entry仅表示选择位置、不表示播放。单次断线不返回半样本。
- **已有/验证**：`T(server/tests/player/test_execution_sample.py::test_sample_rejects_torn_current_and_queue)`逐参数RED→实现→同selectorGREEN；第二selector同循环→该文件→`T(server/tests/player/test_mpd_adapter_tcp.py)`→`T(server/tests/player/test_mpd_adapter_errors.py)`→`T(server/tests/player)`；Ruff仅本步文件。
- **完成/gate**：端口/Mock/Adapter/wrapper一致，typed失败全覆盖。只本地协议proof；目标模式/组合运行时仍NOT VERIFIED，final BLOCKED。

### S3 — occurrence 绑定与失效

- **目标/排除**：Service维护完整运行期映射，禁止URI重建；无自动current推进/History/refill。
- **Authority/依赖/停止**：PB-BINDING/RECOVERY-UNKNOWN/TRANSPORT，F8.9.2；S2。丢绑定、意外version、连接代次/partition变化、同ID复用则UNKNOWN；不以连续连接绝对证明没有重播。
- **白名单**：`server/app/models/recovery.py::ExecutionBinding`；`services/playback_recovery.py::RecoveryJournal`；`services/playback_service.py::_confirm_current_occurrence/_sync_player_queue` 的绑定建立/读取facade；`services/playback_observation.py::confirmed/changed/observe` 仅消费绑定、不得控制；下列测试。
- **接口**：`PlaybackService.get_execution_binding() -> ExecutionBinding|None`（受共同读取边界）；`RecoveryJournal.bind(sample, *, item_ids:tuple[str,...], queue_revision:int) -> ExecutionBinding` 只接收明确已确认控制的IDs，`invalidate_binding() -> None`。不在observer读取私有tuple。受控addid返回ID直接登记，旧按URI fallback不能成为绑定入口。
- **事务/事实/U**：绑定visible与outer commit一致，rollback恢复旧业务绑定；疑似外部连续性丢失必须保留失效标志，不能由rollback复活外部事实。无新History，样本递增不增business generation；U/I/O保持。
- **TO CREATE** `server/tests/invariants/test_d6_binding.py::test_duplicate_uri_binding_uses_confirmed_entry_ids`：`binding.entries == ((a,11,"same.flac"),(b,12,"same.flac")); a != b`；替换12为13不得映射到b。
- **TO CREATE** 同文件 `test_binding_invalidates_on_gap_version_reuse_and_restart` 参数disconnect/service-restart/mpd-restart/version-change/id-reuse/foreign-partition：`binding is None; result.outcome == "UNKNOWN"; after_business == before_business; controls == []`。同entry elapsed回退只更新观测，无新occurrence/history；单纯采样间隔超过6秒只使缓存stale，同连接同版本完整样本可再次确认current，不恢复遗漏历史。
- **已有/验证**：两selector各RED→最小实现→同selectorGREEN→整文件→`T(server/tests/invariants/test_d6_recovery.py::test_recovery_binding_uses_the_confirmed_execution_sample)`→R-OBS-D6/R-ARCH-D6。如旧测试接口必须迁移，仅该selector保持原确认样本断言。
- **完成/gate**：所有业务current-changing入口（start/play_context/play_now/next/previous/delete/stop）使绑定更新或失效，observer只读；跨重启自动绑定不在合同内，final BLOCKED。

### S4 — 固定执行意图、逐命令前缀、部分成功与retry

- **目标/排除**：先补安全执行基础，再允许新转移/补充；不改变候选算法、不完成current/History业务提交。
- **Authority/依赖/停止**：PB-RECOVERY-RETRY、TX-*，F8.9.6；S3。响应丢失且不能唯一归属、外部version变化、connection epoch改变则UNKNOWN并停止后续控制。
- **白名单**：`server/app/models/recovery.py::ExecutionIntent/ExecutionCommand/CommandReceipt`；`services/playback_recovery.py::RecoveryJournal`；新增 `server/app/services/playback_execution.py::ExecutionSynchronizer`；`services/playback_service.py::_sync_player_queue` 委托，保留原操作的确认/错误终端；专用support及下列测试。
- **接口**：`ExecutionSynchronizer.execute(intent:ExecutionIntent) -> ExecutionSample`；`RecoveryJournal.prepare_execution(intent) -> ExecutionIntent`、`record_command(operation_id,index,receipt) -> None`、`get_execution_receipt(operation_id) -> RecoveryResult|None`。同步器仅经Port控制，Service负责DB/业务；journal冲突统一PlaybackReconciliationError。固定最终items/id，不每次重试重新规划。
- **事务/事实**：每条响应先登记，回读验证后确认prefix；add响应丢失封存sent未知，不按URI恢复。rollback留intent/prefix但恢复业务；提交前成功receipt不可见，commit后replay零控制，U/T/F/I全适用。队列控制失败不发成功通知。
- **TO CREATE** `server/tests/invariants/test_d6_execution.py::test_each_command_prefix_is_retried_only_when_owned` 参数command=add/delete/move/play × failure=before-send/after-ack/after-confirm；`intent_after == intent_before; new_item_ids == planned_ids; duplicate_add_count == 0; replay_controls == []; replay_revision == committed_revision`。
- **TO CREATE** 同文件 `test_lost_add_response_never_guesses_or_resends`：服务器执行add但响应EOF，`outcome == "UNKNOWN"; add_calls == 1; after_business == before_business; receipt is None`；再次tick不再次add。
- **TO CREATE** 同文件 `test_execution_outer_failures_and_post_commit_receipt` 参数queue/state/history-runtime/terminal/materialization/outer-commit/precommit-cancel/postcommit-cancel/publisher/visibility；提交前 `after == before; events == []; receipt is None`，提交后 `after == committed; replay.outcome == "REPLAYED"; controls_on_replay == []`，visibility故障GET503但不rollback。
- **已有/验证**：三个selector逐个RED/GREEN→整文件→R-TX-D6→R-PB-D6→`T(server/tests/invariants/test_realtime_delivery.py)`。旧completion rollback tests仍作为隔离legacy回归，不替代新stock故障proof。
- **完成/gate**：每个command边界都有证据，不能用单一“transport failure”替代；不可归属故障明确需处理，final BLOCKED。

### S5 — 未认证 History active 的安全退出

- **目标/排除**：不把外部离开或后来Stop写为旧active的原因；不增加HistoryReason/schema/公开事件字段。
- **Authority/依赖/停止**：PB-HISTORY/UNCERTIFIED、PB-STOP，F8.9.4；S3/S4。不能确认active对应本服务操作作用目标时，禁止finalize旧active。
- **白名单**：`server/app/services/history_service.py::discard_unconfirmed_active/preserve_active_on_rollback`；`services/playback_service.py` start_track/play_context/play_now/next/previous/delete/stop中的active资格检查；`services/playback_recovery.py` 的active绑定资格；下列测试。不改HistoryRepository/enum/model/schema。
- **接口**：新增 `HistoryService.discard_unconfirmed_active() -> None`，仅清_active保留_session_id，必须在已有outer runtime hook保护内；新增 `PlaybackService._validate_history_active(sample:ExecutionSample) -> bool`，不能凭song URI比较。
- **事实/事务/U**：明确操作绑定有效时沿用旧reason；无可信active不写事件，Stop仍清session/AutoPlay。UNKNOWN只读观察不调用discard；真正领域操作中discard失败/outer rollback恢复runtime。U/T/F/I保持，不用观测时间生成起点或终点。
- **TO CREATE** `server/tests/invariants/test_d6_history.py::test_unknown_departure_then_explicit_stop_does_not_relabel_old_active`：`history_after == history_before; active is None; session is None; autoplay_enabled is False`；parameter stop/next/play_now 对后两项只保留各自原新active规则。
- **TO CREATE** 同文件 `test_discard_preserves_session_and_rolls_back_without_event`：`active is None; session == old_session; persisted == before`；注入outer failure后 `active == old_active; session == old_session; events == []`。
- **已有/验证**：两selector逐个RED/GREEN→整文件→`T(server/tests/invariants/test_stop_confirmation.py)`→R-H-D6/R-TX-D6/R-PB-D6。明确Stop确认不通过不得新增STOP，原tests保持。
- **完成/gate**：不再通过start_track隐式SWITCH_AWAY伪造过去；自动观测目标无runtime active，final BLOCKED。

### S6 — 确认当前转移与 Queue CAS/清理

- **目标/排除**：A→B/C当前事实接纳，保留未观察pending；不认证自然原因、不触发候选生成、不在未知STOPPED play。
- **Authority/依赖/停止**：PB-CURRENT/QUEUE-ADOPT/RECOVERY-UNKNOWN/TRANSPORT，F8.9.1–4/6；S4/S5。目标不在有效映射、已Played项、最终执行确认失败、CAS/generation变化停止提交。
- **白名单**：`server/app/services/playback_service.py::reconcile_external_status` 新stock分支；`services/queue_manager.py::adopt_current`；`repositories/queue_repository.py::adopt_current`；`services/playback_execution.py` 清理/移动计划；`models/recovery.py` 新计划使用；下列tests、上文明确列出的 `server/tests/invariants/test_d6_recovery.py`、`server/tests/services/test_playback_service.py`、`server/tests/api/test_pre_batch6_corrective.py` 的冲突selector和专用helper；不修改其它用例的产品断言。
- **接口**：`QueueRepository.adopt_current(previous_id:str,target_id:str,*,expected_revision:int) -> QueueSnapshot`（Manager同签名），仅原current→原pending；A-1/C0/其余原pending稳定排序，revision+1。`PlaybackService.reconcile_external_status(*, evidence=None)` 无evidence走stock读/固定intent/确认；legacy evidence仍隔离，不能当stock生产输入。错误使用原PlayerUnavailable/PlayerCommandError/ReconciliationError/CAS conflict；UNKNOWN零业务delta。
- **确认/事务/U**：先验证原完整执行映射，计划清理A并保留C ID、未观察B；最终MPD current C0且全映射准确才同outer提交Queue/state/discard旧active/binding/receipt/通知。PAUSED保持PAUSED，无play/seek/next；U/T/F/I适用。
- **TO CREATE** `server/tests/invariants/test_d6_current.py::test_current_adoption_preserves_unobserved_manual_occurrences` 参数target=b/c，A/B/C/D固定ID：C case `positions == {a:-1,c:0,b:1,d:2}; pending_ids == [b,d]; history_after == history_before; active is None; revision == old_revision+1; play_calls == 0`；B case只A Played，C/D pending；source/context逐项相等；另加existing-played参数，`old_played_ids_after == old_played_ids_before` 且各旧position减1，不丢旧Played。
- **TO CREATE** 同文件 `test_current_fact_never_claims_cause` 参数natural-like/seek-end/seek-remainder/external-next/playid/seekid/decoder-error/input-error/output-error/same-entry-replay：前9种给相同合法目标样本，`new_history == []; claimed_reason is None`；same-entry `queue_after == queue_before; new_history == []`。error可能空，不改变因果结论。
- **TO CREATE** 同文件 `test_stop_foreign_drift_and_concurrent_mutation_fail_closed` 参数stop/foreign/queue-edit/id-reuse/late-sample/queue-cas/new-current-during-cleanup：`controls_after_unknown == []; after_business == before_business; reconciliation_required is True`；已执行清理的失败单独比较MPD prefix，不能断言外部未变化。
- **已有/验证**：3个selector各RED/GREEN→整文件→`T(server/tests/invariants/test_d6_recovery.py)`（只按上表迁移冲突参数）→R-PB-D6/R-H-D6/R-TX-D6/R-OBS-D6。
- **完成/gate**：重复URI、A→C和并发barrier均通过；中间项完整播放/实际ended_at依然不认证，final BLOCKED。

### S7 — AutoPlay 按确认后剩余量预同步

- **目标/排除**：正常播放期间提前补充，不等STOPPED；候选策略5/5、手动顺序与dedup边界不变。
- **Authority/依赖/停止**：PB-AUTOPLAY-EXEC、PB-STOP、F8.9.5/6；S6。模式非顺序、binding失效、意图false、UNKNOWN STOPPED停止控制；无候选返回NO_CANDIDATES。
- **白名单**：`server/app/services/autoplay.py::plan_refill/refill` 仅planner复用；`services/playback_service.py::maintain_execution` 新一次编排入口；`services/playback_execution.py` append计划；`services/playback_recovery.py`固定refill意图；必要 `repositories/queue_repository.py::add_autoplay_batch` 接受固定IDs（不可另分配）；下列tests。
- **接口**：`PlaybackService.maintain_execution() -> RecoveryResult` 先reconcile当前，再按确认剩余量规划；`AutoPlay.plan_refill(context,snapshot) -> tuple[QueueItem,...]`保持现接口与策略；repository新增可选 `planned_items:tuple[QueueItem,...]|None=None`，验证song/source/context和CAS，不成为任意Queue覆盖接口。
- **确认/事务**：规划纯函数式不持久；固定IDs的Queue写与执行sync位于同outer，全部确认才可见；current自动前进则使旧计划失效重新采样，不增加重复候选；Stop barrier使pending intent失效。U/T/F/I/O保持；refill不产生History/新active。
- **TO CREATE** `server/tests/invariants/test_d6_autoplay.py::test_refill_uses_confirmed_remaining_and_preserves_manual_order`：剩余4时 `added_count == 5`（足量曲库），剩余5时 `added == ()`；`manual_ids_after == manual_ids_before; new_sources == {"AUTOPLAY"}; queue_ids == confirmed_execution_item_ids; current_entry_id == old_entry_id; play_calls == 0`；A→C B重排确认后再计数。
- **TO CREATE** 同文件 `test_empty_stop_disconnect_and_refill_failure_do_not_restart` 参数empty/no-candidates/stop/disconnect/append-failure/late-stop：`play_calls == 0; natural_events == []; autoplay == expected_user_intent`；empty无伪next、failure业务rollback；Stop后Library变化也不启动。
- **已有/验证**：2selector逐个RED/GREEN→整文件→`T(server/tests/services/test_autoplay.py)`→`T(server/tests/invariants/test_d6_execution.py)`→R-PB-D6/R-TX-D6。保留已有context优先/单曲/同批去重/手动并发测试。
- **完成/gate**：正常续播无需natural输入；预算耗尽/极短歌曲可失败且明示，不承诺无限不中断，final BLOCKED。

### S8 — 实际状态 DTO、完整快照与只读传播

- **目标/排除**：新页面准确区分业务current/实际identity/stale/unknown/不同步；不实现Task8，不把恢复写入读取链路。
- **Authority/依赖/停止**：RT-ACTUAL、RT-SNAPSHOT/OBSERVE/RECOVER，A12.3.1、F8.9.7；S6/S7。必需本地域读取失败整体503；缺样本不能填业务歌作actual。
- **白名单**：`server/app/models/realtime.py::PlaybackObservation`、`api/realtime_schemas.py::PlaybackObservationResponse`；`services/playback_observation.py::observe/get`；`services/state_service.py::get_full_snapshot`；`services/playback_service.py::get_observation` 的同步诊断facade；`api/realtime.py` 仅共享encoder兼容，`services/realtime_coordinator.py` 仅新增字段变化登记；下列tests。
- **接口**：严格A12.3.1 additive字段；actual_current.entries来自S2采样，不查URI重建业务绑定；旧current_song仍Library按persisted song_id读取。新字段默认unknown/null/UNBOUND以兼容旧构造；GET/WS相同schema、protocol_version仍1。
- **事务/事实**：snapshot仅同一已提交切面+外部缓存；sample接受检查generation并与sequence共同可见。未知/stale actual independent；不改变Queue/History/terminal，U/O全保持。读取失败重读不控制。
- **TO CREATE** `server/tests/invariants/test_d6_state.py::test_actual_identity_is_separate_from_persisted_current`：foreign时 `snapshot.current_song.song_id == "a"; actual_current.uri == "foreign.flac"; bound_queue_item_id is None; matches_current is False; position_seconds is None; after_business == before_business; controls == []`；unbound freshness实际可fresh而旧progress unknown。
- **TO CREATE** `server/tests/api/test_d6_state.py::test_fresh_browser_reconnect_and_restart_show_truthful_full_state` 参数refresh/new-browser/ws-reconnect/service-restart/mpd-restart：`ws_state == get_state; protocol_version == 1`；service restart `new_epoch != old_epoch; history.active_event is None; bound_queue_item_id is None`；MPD restart仅binding失效不强制realtime epoch变化；迟到GET `applied == newest_snapshot`。
- **已有/验证**：两个selector分别RED/GREEN→两文件→`T(server/tests/invariants/test_realtime_recovery.py::test_reconnect_replaces_all_domains_and_epoch)`→`T(server/tests/api/test_realtime.py)`→R-OBS-D6/R-H-D6/R-ARCH-D6。新增字段需补旧公共DTO expected keys，仅白名单对应表示断言，保留水位/只读断言。
- **完成/gate**：四种恢复分别验收，不冒充完整Context/未知历史恢复；Task8未实现，final BLOCKED。

### S9 — 独立恢复 runner 与生命周期装配

- **目标/排除**：无页面时也预补充/接纳当前；observer继续只读，无多进程控制/Task10配置系统。
- **Authority/依赖/停止**：PB-RECOVERY-RUNNER、F8.9.7；S2–S8本地proof GREEN，允许本地可控装配验证；目标自动启用须S11/S12门禁，不能先部署。发现两个control owner即启动失败，不用SQLite锁假装跨进程MPD排他。
- **白名单**：新增 `server/app/services/playback_recovery_runner.py`；`main.py::lifespan` 单owner装配/关闭；`services/playback_service.py::maintain_execution`仅预算参数 `read_timeout:float|None=None`；下列test。不改StateObserver.run来执行控制。
- **接口**：`PlaybackRecoveryRunner(playback, *, interval=1, budget=5, sleep, clock)`，`run()->None/close()->None`；仅调用PlaybackService公开facade。main通过可注入 `app.state.recovery_enabled` 和已注入capabilities控制启动；未注入/目标未验收默认不启动恢复runner、不运行探针，不改既有observer。S9/S10测试显式启用并注入本地Port，S11/S12验证启用组合；最终配置加载仍由Task10负责，runner核心不得延后。顺序轮询，failure延迟1/2/4/8/16/30，成功重置；UNKNOWN进入只读核验，不推进sent未知命令。
- **事务/事实/U**：业务串行化沿用Service，不在runner持DB锁睡眠/发送；取消已发命令按S4，关停不Stop；observer故障不夺控制，U/T/F/I/O保持。
- **TO CREATE** `server/tests/invariants/test_d6_runner.py::test_single_runner_refills_without_clients_and_never_restarts_stop`：`max_concurrent_ticks == 1; clients == 0; refill_committed is True; play_calls_after_stop == 0; observer_controls == []`，FakeClock驱动并发Stop barrier。
- **TO CREATE** 同文件 `test_runner_budget_backoff_and_shutdown_preserve_commit`：`delays == [1,2,4,8,16,30,30]; delay_after_success == 1; budget == 5; stop_calls_on_close == 0; pending_tasks == []`，提交前/后取消分别按T/F断言。
- **已有/验证**：2selector RED/GREEN→整文件→`T(server/tests/invariants/test_realtime_observer_lifecycle.py)`→`T(server/tests/invariants/test_realtime_output.py)`→R-TX-D6/R-ARCH-D6。
- **完成/gate**：runner是D6核心步骤而非可无限延后的选配；本地生命周期通过不授权目标运行，final BLOCKED。

### S10 — 显式 stock Adapter 联合 proof（先显式，再runner）

- **目标/排除**：验证真实TCP Adapter/VerifiedPort/Service/SQLite/实时协议联合，不mock每个边界、不产生自然event假输入。
- **Authority/依赖/停止**：全部新matrix/F8.9.8–9/A12；S2–S9。若靠TestCompletionValidator通过即不合格；任何失败回owner，不能final补大功能。
- **白名单**：仅新增 `server/tests/invariants/test_d6_stock_joint.py`、`server/tests/integration/support/stateful_fake_mpd.py` 和专用support、E；不新增生产代码。local TCP fake只模拟0.23.5协议facts/失败。
- **接口/事实**：显式 `maintain_execution()` 后采样/snapshot/WS，再独立启动runner；输入ID/version/队列/transport，输出已提交联合状态。unknown causes不伪造成natural；U/T/F/I/O逐项断言。
- **TO CREATE** `test_stock_adapter_current_queue_history_and_snapshot_joint` 参数A-B/A-C/duplicate/seek-end/seek-remainder/errors/external-next/playid/seekid：`business_current_id == confirmed_target; history_after == history_before; queue_revision_delta == 1; ws_state == http_state; natural_events == []; target_play_calls == 0`；至少一个参数从无客户端runner推进。
- **TO CREATE** 同文件 `test_stock_joint_failure_restart_and_read_only_boundaries` 参数lost-response/partial-add/delete/move/service-restart/mpd-restart/unknown-stop/foreign/queue-race/late-sample：`reads_control_count == 0; old_terminals_after == old_terminals_before; playlist_after == playlist_before; output_after == output_before`，其余按各owner literal断言，重启不补History。
- **验证顺序**：两个完整selector → 整文件 → `T(server/tests/player)` → 新D6所有文件 → 旧D6 consumer文件 → R-PB-D6/R-H-D6/R-TX-D6/R-OBS-D6/R-ARCH-D6。新验收测试若首次GREEN，记proof新增而非虚构RED；暴露bug回owner创建真实RED修复后重跑同selector。
- **完成/gate**：本地联合PASSED仅在实际执行后填写；目标未验证不宣称运行时能力，final BLOCKED直到S11/S12。

### S11 — 目标原版 MPD 运行时能力验收（本轮禁止执行）

- **目标/排除**：验证新依赖的顺序模式、current ID位置/version、预同步及错误边界；不试图证明自然原因，不执行DAC听觉/Task12发布验收。
- **Authority/依赖/停止**：F8.9.9/A6.1，D6-RECOVERY能力子门禁；S10且用户另行授权目标环境/维护窗口。无授权、无法保护原队列/输出、版本/build不明则NOT RUN/BLOCKED，不能以旧九项替代。
- **白名单/接口**：E记录命令/原始响应/版本/build说明/局限，C仅在获得新原始实测后记录；本步骤不授权生产/测试/schema修改。输入受控重复URI队列、模式、状态样本；输出可复核原始记录，不能复制旧probe冒充新数据。
- **精确手工场景/断言**：A/B/C含重复URI不同ID，读取status/playlistinfo，确认 `songid == entry.Id` 与position；正常前进只确认目标，不判reason；预排B可推进且无服务playid B；A→C遗漏B不补史；移动/删除已离开entry后目标ID保留/position改变；Stop后不重启；断线/重启旧绑定失效。记录每一步实际ID/version/命令和业务snapshot；触发故障必须有安全隔离条件，未能实测的项留NOT VERIFIED，不删义务。
- **事务/U/retry**：遵守T/F/I，备份并可核对原执行队列/状态，不动媒体/库/schema/输出；恢复方案先审查，不能声称恢复原物理播放瞬间或原MPD ID。响应丢失不盲重发。自动测试selector为S10，仅协议输入证明；手工报告不是pytest GREEN。
- **完成/gate**：所有新目标能力及保护恢复记录满足才能力PASSED；当前NOT RUN，final BLOCKED。Task12 DAC/反向代理仍另有验收。

### S12 — D6 联合验收与 Batch13/Task6 final gate

- **目标/排除**：逐Contract追溯实现/精确proof/fresh结果/目标能力，重新执行最终门禁；不以删除SOURCE直接关闭，不实施Task8。
- **Authority/依赖/停止**：F8.9.9、A19.5、T §5/Batch13、M dependency；S10/S11均通过且runner proof完成。任何红项/NOT RUN/真实产品合同缺口保留BLOCKED。
- **白名单/接口**：P/E/B/T/M/C验收状态；测试执行只读源码，测试DB限tmp。输出每row命令/结果/局限，更新gate而非复制权威合同。无新生产或测试实现；发现缺陷回S2–S9 owner。
- **事实/事务/U**：检验T/F/I/O及全部U，不把全套替代focused、不把已定义当已实现。S12无新RED周期。
- **精确顺序/命令**：S10两个selector→该文件→下列新D6集合→旧D6→T §5全部R集合（原表命令逐条）→指定Batch13 selector→两份Batch13文件→realtime全集→invariants/API→server/tests→实际改动Python scoped Ruff→diff/link/status。必须记录每段，不能只写“全套通过”。

```bash
.venv/bin/python -m pytest -q server/tests/player/test_execution_sample.py server/tests/invariants/test_d6_binding.py server/tests/invariants/test_d6_execution.py server/tests/invariants/test_d6_history.py server/tests/invariants/test_d6_current.py server/tests/invariants/test_d6_autoplay.py server/tests/invariants/test_d6_state.py server/tests/api/test_d6_state.py server/tests/invariants/test_d6_runner.py server/tests/invariants/test_d6_stock_joint.py
.venv/bin/python -m pytest -q server/tests/invariants/test_d6_recovery.py
# 此处先逐条执行 T §5 的 R-TX/R-LIB/R-PL/R-PB/R-H/R-O/R-ARCH 原命令
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_recovery.py::test_reconnect_replaces_all_domains_and_epoch
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_recovery.py server/tests/api/test_realtime.py
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_*.py server/tests/api/test_realtime*.py
.venv/bin/python -m pytest -q server/tests/invariants server/tests/api
.venv/bin/python -m pytest -q server/tests
git diff --check
git diff --stat
git status --short
```

- **完成/gate**：E分别写implementation/automated/local-env/target-runtime/acceptance/manual余项；D6通过后B13再标满足，Task6所有11RT rows和RT-ACTUAL新增义务通过才final可关闭。Task8实际浏览器UI、Task12 DAC/HTTPS仍未执行，不混为D6已完成。当前所有新selector **TO CREATE / NOT RUN**，没有新GREEN。

## 执行进度（不得以文档复选替代证明）

- [x] S0 静态Git/源码/能力/proof审计（未来执行前pytest仍未运行）。
- [x] S1 合同、接口和影响矩阵已写入；R1 已接受，见 F §8.9.2。
- [ ] S2 一致样本；S3绑定；S4安全执行；S5 History；S6当前接纳。
- [ ] S7 AutoPlay；S8实际DTO；S9 runner。
- [ ] S10本地联合；S11目标运行时；S12最终gate。

## Review Focus / 场景覆盖核对

1. 相同URI/ID复用/版本ABA：S2/S3 binding selectors（不能把URI fallback算成功）。
2. A→C漏B/外部控制/seek/errors：S6两个current selectors + S10联合；中间B保留可重播的代价必须写给用户。
3. Queue修改、采样、清理时再次前进：S6 barrier + S4 command-prefix；不能以进程锁冻结MPD。
4. 多命令部分成功/响应丢失/outer失败：S4全部命令×故障参数 + S10；禁止URI猜add结果。
5. 页面重连/服务与MPD分别重启/Stop与runner竞态：S8/S9/S10，actual显示可恢复≠业务绑定或遗漏History可恢复。

本轮最终只检查文档 diff、链接、源文件字节和未授权范围，不执行上述未来测试，不 commit。**产品项 R1 已接受（2026-10-04）**：服务/MPD 重启后自动恢复准确的 actual 显示；业务 occurrence 绑定必须由明确 Start Track/Play Context/Queue Play Now 经实际确认重建。仅刷新、换浏览器或 WebSocket 重连不使有效服务绑定丢失；若同时发生 MPD 连接失效，仍按 F §8.9.2 处理。S3/S8/S9 按此已定合同设计和验收，不再等待 R1 答复；本轮仍只修改文档，新实现和验收未完成，最终 gate BLOCKED。
