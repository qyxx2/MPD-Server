# MPD-Server Task 7 — Contract Matrix / Batch Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans in each independent implementation window. Only implement the selected Batch. Steps use checkbox syntax for tracking. This planning window implements no production code or feature tests.

**Goal:** 实现 NAS_DAC 输出状态/控制及 MPD About；机械证明输出操作不破坏播放权威。

**Architecture:** API → OutputManager / MPDInfoService → PlayerPort；播放协调经 PlaybackService 提供的共同事务入口。输出事实来自 MPD；Queue/Context/History 仍由现有服务拥有。领域事件经 EventPublisher，最外层提交后才发布成功通知。

**Tech Stack:** 现有 Python/FastAPI/Pydantic/SQLite/pytest；MockMPD、VerifiedPlayerPort、MPDAdapter；不增加第三方依赖。

**Spec:** `../specs/2026-09-24-system-architecture-playback-output-design.md`（下称 O）；`../specs/2026-09-25-system-and-development-architecture-design.md`（A）；`../specs/2026-09-24-playback-model-queue-semantics-design.md`（P）。Task/Step/依赖权威为 `2026-09-25-mpd-server-v0-1-implementation-plan.md`（M）。

## 1. Scope、基线与审计结论

- 审计基线：`main@ca2d9d2e9569b3a99eac0c068003d09850e2124e`；远端 main 已再次用 `git ls-remote` 核实。审计开始工作区干净，未发现 AGENTS.md。
- 规划/后续工作分支：`feature/task-7-output-manager`，从上述 main 建立。实现窗口必须重新 fetch、核对 HEAD/工作区及本计划是否漂移，不能把此 SHA 当成未来最新状态。
- Task 1R `03f4de9`（transport 完成）、Task 4 corrective `86975d6` 均经 `git merge-base --is-ancestor <commit> HEAD` 验证可达。main 已含 Task 5 merge。代码/测试证据见 §2；提交可达不等于本窗口重新跑过测试。
- M Dependency Matrix：Task 7 依赖 1R + 4；Task 6 依赖 3 + 4 + 5 + 7。Task 7 先于 Task 6。
- Relationship Gate：**REQUIRED**；Contract Matrix Gate：**REQUIRED**。涉及外部输出事实、播放保留、HTTP 表示、外层事务和事件顺序。
- 规划审计窗口状态：Contract Audit / Matrix / Batch Planning，未实施 production/test。当前 B1 已完成只读/拒绝局部验收；B2–B9 NOT STARTED，O-STATE-001 请求转换仍 pending B5/B6，Task 7 未完成。执行证据：`../archive/task-7/2026-10-02-task-7-batch-1-acceptance.md`；后续窗口仍须核对真实 Git/代码/测试。
- 规划审计环境曾返回 `No module named pytest`，未跑测试。B1 使用现有 `.venv` 完成本地验证，未安装/修改依赖、未访问真实 NAS；fresh evidence 见上述归档，不沿用规划环境结论。

### Global Constraints

- MPD 0.23.5 能力以 `docs/mpd-0.23.5-capabilities.md` 和注入的真实验证结果为准；不硬编码探针样本、数字 output ID 或统计值。
- NAS_DAC 仅控制 selector 确定的输出；CLIENT_STREAM 永远不可用，所有 stream 字段为空。无 HTTP 音频传输。
- 输出启停不等于播放 Stop/Play，不写 Queue/Context/History，不更改 AutoPlay、repeat/random、volume 或音乐文件。
- API 不访问 repositories/SQLite/MPD；Service 不依赖 concrete MPDAdapter；不导入 Task 6 StateService/WebSocket 或 Task 10 config。
- Task 7 只作必要注入/路由接线；不改部署、Web、认证、备份、扫描或播放业务规则。
- 不把实时外部设备操作说成 SQLite 可回滚；不创建持久化 event outbox、Exactly-once 协议或新的 schema migration。

### Review Focus

1. 输出 ID 改变、多 ALSA、selector 无/多匹配：拒绝猜测、无变更命令（B1/B5）。
2. 命令 ACK/超时与回读不一致、回读也断线：真实状态与请求失败分开（B5/B6）。
3. 同 URI 的不同 current occurrence、PAUSED/STOPPED、空 Queue、未知位置与自然推进（B3/B5/B6）。
4. MPD 已变更后 terminal INSERT/响应构造/outer commit/cancellation 失败：无成功事件、可重试（B4/B8）。
5. About 部分数据失败、真实 0、已验证历史版本与实时连接不同：不伪造整体在线或 0（B2/B7）。

## 2. Repository evidence（全部从审计基线核实）

| Evidence ID | 现有文件 / 确认内容 | 能证明 / 不能证明 |
|---|---|---|
| E1 | `server/app/player/ports.py`：`outputs()`、`set_output_enabled(output_id, enabled)`、`status()`、`queue_entries()`、`stats()`、`database_update_status()`，typed `PlayerUnavailable/PlayerCommandError` | 端口存在；没有业务 OutputState、selector、原子多命令事务或物理 DAC 探测 |
| E2 | `server/app/player/models.py`：OutputInfo(id/name/plugin/enabled/attributes)、PlayerStatus(song_id/song_position/elapsed_seconds)、MPDStats、DatabaseUpdateStatus | 可以确认 MPD occurrence/输出启用与未知字段；不能证明扬声器出声 |
| E3 | `server/app/player/capabilities.py`：MPDCapabilities、supports_operation、VerifiedPlayerPort；运行时验证控制 output/stats/update-status | 不得把 from_commands 或 probe 历史 stats 当实时已验证结果 |
| E4 | `server/app/player/mock_mpd.py`：可注入 outputs/stats、disconnect/reconnect/fail_next；`mpd_adapter.py` 提供端口实现 | Adapter 的命令锁不等于完整业务事务锁；Mock 默认 plugin=mock 不是 ALSA |
| E5 | `server/app/services/playback_service.py`；QueueManager、HistoryService、AutoPlay；真实 repositories/models | start_track/play_context/play_now/next/previous/stop/reconcile_external_status 使用原子包装；reorder/clear/delete 使用 run_transaction。play_next/add_to_queue/pause/seek 没有整段共同事务包装；输出接入需要最小串行化补齐 |
| E6 | `server/app/repositories/database.py`：run_transaction(path, operation)、on_transaction_rollback(path, callback) | 已有嵌套事务、per-db serialization、BaseException rollback；**没有 after-commit hook** |
| E7 | `server/app/services/events.py`：DomainEvent(event_type)、EventPublisher.publish(event)、LibraryChangedEvent | 事件抽象存在；OutputChangedEvent 不存在；不能复用 LibraryChangedEvent 冒充输出事件 |
| E8 | `server/app/services/idempotency_service.py`、`server/app/main.py` mutation middleware、IdempotencyRepository | 业务/terminal 在外层事务；失败响应回滚；相同请求重放、不重执。当前路径前缀含所有 `/api/` mutation |
| E9 | `server/app/api/dependencies.py`、`server/app/main.py`、`server/app/api/schemas.py` | 已有 Service 注入/统一错误外壳；Output/API 未接线；main 当前直接构造 MPDAdapter，没有已验证 capabilities 注入或 OutputManager |
| E10 | `server/tests/invariants/assertions.py`：server_snapshot、assert_execution_relationship；`server/tests/support/playback.py`：real_client、run、mutate、start | 真实 SQLite/Service + Mock 关系测试基础。helper 用 asyncio.run，不可直接放在正在运行的 async test 中；并发 tests 在同一 loop 直接 await |

现有 executable proofs（存在性已核实，运行结果不在本次声明）：

| Proof group | 现有路径 / 函数 |
|---|---|
| R-PORT | `server/tests/player/test_task1r_step4.py::test_mock_task1r_queue_output_stats_and_update_status`；`test_task1r_step5.py::test_adapter_task1r_transport_operations`；`test_task1r_step6.py::test_all_task1r_operations_are_blocked_until_runtime_verified`、`test_verified_task1r_operations_delegate_after_probe`；`test_task1r_step7.py::test_task1r_adapter_ack_and_connection_failures_are_typed` |
| R-PLAY | `server/tests/invariants/test_playback_relationships.py`：`test_same_uri_pending_mutation_preserves_occurrence_identity`、`test_duplicate_execution_occurrences_survive_mutation`、`test_transition_history_matches_confirmed_current`、`test_wrong_duplicate_current_is_reconciliation_failure`、`test_pending_duplicate_mutation_preserves_retained_occurrence_ids`、`test_insertion_rejects_actual_playback_divergence_and_can_retry` |
| R-STOP | `server/tests/invariants/test_stop_confirmation.py`：`test_unconfirmed_stop_preserves_all_authorities`、`test_stop_transport_failure_rolls_back_and_retries` |
| R-TX | `server/tests/invariants/test_transaction_relationships.py::test_transaction_restores_persisted_and_session_state_and_retry`；`server/tests/api/test_idempotency.py`：`test_playlist_create_commits_business_result_and_replay_record_together`、`test_schema_failure_does_not_consume_idempotency_key`、`test_terminal_record_write_failure_rolls_back_business_mutation` |
| R-EVENT | `server/tests/integration/test_task3_events_and_mpd.py`：`test_task3_events_follow_committed_sqlite_state`、`test_task3_repository_transaction_failure_blocks_mpd_and_event`（Library 的 proof，不是 Output proof） |
| R-ARCH | `server/tests/invariants/test_architecture_relationships.py::test_dependency_direction_preserves_repository_and_player_authorities` |
| R-PL | `server/tests/invariants/test_playlist_relationships.py::test_persisted_membership_matches_every_representation_and_collection_split` |

审计基线时以下文件不存在，标为 TO CREATE。B1 现已创建 models/output.py、services/output_manager.py、test_output_manager.py 和 F1 test_output_observation.py；其它 models/mpd_info.py、services/mpd_info_service.py、api/system.py、api/system_schemas.py 以及 F2–F9/transport、`test_mpd_info_*` / `test_system_*` / `test_transaction_commit_hooks.py` 仍 TO CREATE。未来命令只在对应 Batch 创建后执行，不能当成当前证据。

## 3. Contract Gap resolution（先于 Matrix 和 Batch）

| Gap | 权威原缺口 | 本次处理 / 权威归属 |
|---|---|---|
| G1 | O §6 未说明切换是否关闭其它启用输出 | 用户选择“只启用目标”；O §6.1 明确目标启停、其它输出保持、不引入排他模式 |
| G2 | O §5.2 `mode` 同时可能指请求/生效，SWITCH_FAILED 与旧 ACTIVE 如何共存不明确 | 用户选择“实际状态与请求结果分开”；O §6.1 明确实际状态、last request、stale 与能力边界 |
| G3 | 外部切换成功后 SQLite/terminal 失败的恢复政策未定义 | 用户选择“保留实际输出并重新核对”；O §6.2 明确不自动补偿、retry/replay；§6.3 定义最外层提交后事件 |
| G4 | 主 Task 7 Files 未列必要 domain schemas、事件、共同事务入口/API wiring，Step 5 易被误读为巨型 Batch | 仅修正 M Task 7 支持范围并指向本计划；未修改 Task 依赖顺序、未勾选实现 |
| G5 | About 未区分历史 capability 样本和实时值、部分失败的 null | 从 O §7.2 未知不可伪造约束细化 §7.3；不同来源独立读取与可观测失败，不引入新统计指标 |

G1–G3 是经用户选择补齐的语义，不是假称原规格早已定义。O §6.2 的 occurrence/串行化/确认及 §6.3 提交纪律是原保留合同、A §8.1/§19.5 和 P §8 的技术细化。没有以当前代码反向定义输出行为。

已知实现缺口：E5 缺完整 operation serialization、E6 缺提交钩子、E9 缺 capability 注入；分别归 B3、B4、B7。它们不重置历史 Task 验收，不授权全面重构。

物理可用性边界：当前端口没有独立 USB 物理健康信号；Task 7 只保证已验证 MPD 可观测事实。不能将 `enabled=true` 记为“真实 DAC 出声测试通过”。

## 4. Task-level Contract Matrix（在拆 Batch 前冻结）

### 4.1 分类和字段约定

- **新增业务 rows**：O-DISC-001、O-STATE-001、O-RESERVED-001、O-ENABLE-001、O-DISABLE-001、O-PRESERVE-001、O-FAIL-001、O-TX-001、O-EVENT-001、INFO-READ-001、SYS-READ-001、SYS-WRITE-001，完整稳定 ID 下列明。
- **继承并依赖**：PORT-OUTPUT-001、PORT-INFO-001、EVENT-PORT-001（本次只为既有明确合同建立索引 ID，并非本次实现）；TX-ROLLBACK-001、TX-IDEMP-001 沿用 Task 5 ID。
- **修改已有 rows**：不修改历史 row 的业务语义；TX-ROLLBACK-001 的实现机制会增加最外层提交钩子，故作为 affected/modified implementation row；TX-IDEMP-001 扩展到 system 路由的使用场景，必须回归。PB rows 的 wrapper 补齐只保护原行为。
- **仅历史 regression**：PB-STOP-001、PB-INSERT-001、PB-REORDER-001、PB-DELETE-PENDING-001、PB-DELETE-CURRENT-001、PB-NEXT-UNAVAILABLE-001、PB-HISTORY-001、PL-REP-001、PL-COLLECTION-001；其唯一原 row 在 Task 5 active plan §3.6，不复制/重定义原业务。

每 row 下显式列出全部 required fields。`Unchanged=PRESERVE` 指：服务端 Queue snapshot/revision/item identity/order、PlaybackState 的歌曲/状态/Context/AutoPlay、History persisted/active/session、MPD execution/current occurrence 与 repeat/random/volume 保持；position 按 O §6.2。`Proof F#` 的完整 TO CREATE 路径/函数与 owner 在 §6，不是现有测试。

### 4.2 新增 rows

**O-DISC-001 — REPRESENTATION / discover NAS_DAC**（O §4.2、§6.1；M Task 7）
- Preconditions：注入 PlayerPort、capabilities、可选 selector；只读取已获准操作。Authorities：MPD outputs / Service 模式身份。
- Expected State Delta：从最新输出识别唯一 ALSA 目标；ID 变更后重新绑定。Must Remain Unchanged：全部 MPD 启停与 PRESERVE。
- External Confirmation：实际 outputs 列表；多候选只能 selector 唯一有效命中。History/Event Semantics：无播放 History，无切换成功事件。
- Transaction Boundary：只读刷新通过同一输出 operation runner；不写 DB。Failure/Rollback：无匹配/歧义/读取失败不执行变更，失败数据不可伪装 fresh。
- Retry/Idempotency：重新读取，不信任旧 ID。Observable Result：可用目标/明确 unavailable 原因，不暴露数字 ID 为业务选择项。
- Executable Invariant Proof：F1；implementation B1，后续 B5 的 ID 漂移 failure/retry 复验。

**O-STATE-001 — REPRESENTATION / observed state + request outcome**（O §5.2、§6.1）
- Preconditions：可无旧缓存；有/无最近请求均合法。Authorities：MPD 的实际事实 / OutputManager 的请求过程。
- Expected State Delta：观察态 UNAVAILABLE/INACTIVE/ACTIVE；请求态独立 PREPARING/SUCCEEDED/SWITCH_FAILED；刷新更新时间和 fresh/stale。Must Remain Unchanged：失败目标不得替换旧已确认输出，PRESERVE。
- External Confirmation：fresh ACTIVE/INACTIVE 仅来自 outputs 回读。History/Event Semantics：请求准备/失败不是成功通知；不创建 History。
- Transaction Boundary：进程内状态；成功事件另受 O-EVENT-001/O-TX-001 约束。Failure/Rollback：保留带 stale 的最后确认事实，never fresh fabricated ACTIVE。
- Retry/Idempotency：新尝试覆盖最近请求过程，不改历史回执。Observable Result：observed 与 last_request 独立；stream 字段全 null。
- Executable Invariant Proof：F1；B1 冻结读取/表示，B5/B6 完成真实 transition proof，之前 row 不得标 COMPLETE。

**O-RESERVED-001 — STATE_TRANSITION / reject CLIENT_STREAM**（O §5、§6.1）
- Preconditions：任意当前输出/播放态，CLIENT_STREAM enable 或 disable 请求。Authorities：服务端支持矩阵 / PlayerPort。
- Expected State Delta：请求明确不支持；CLIENT_STREAM 保持 UNAVAILABLE。Must Remain Unchanged：NAS observed state 与所有输出启停/PRESERVE。
- External Confirmation：不需要输出写入确认；必须证明没有 MPD mutation。History/Event Semantics：无 History/成功事件。
- Transaction Boundary：控制副作用前拒绝；HTTP 失败不提交 terminal success。Failure/Rollback：无业务状态回滚需求，不更改有效旧输出。
- Retry/Idempotency：重复拒绝，无累积效果。Observable Result：OUTPUT_MODE_UNSUPPORTED。
- Executable Invariant Proof：F1，B1 service proof；F9，B8 HTTP proof。

**O-PRESERVE-001 — TRANSACTION / serialize output with playback**（O §6.2；A §8.1/19.5；P §8）
- Preconditions：同一服务实例/同一 DB 的合法初始 server↔player 关系。Authorities：Playback/Queue/History/SQLite / PlayerPort / OutputManager。
- Expected State Delta：只有被授权输出字段改变；并发播放操作按既有事务顺序执行。Must Remain Unchanged：PRESERVE；输出不得创建或结束 History。
- External Confirmation：比较 current song_id + song_position + URI、执行队列 occurrence ID/order、状态；已知暂停位置不变、播放时间自然推进允许、未知不造值。
- History/Event Semantics：输出本身无 History；成功事件晚于共同操作确认。Transaction Boundary：PlaybackService 公共 operation runner 使用现有 run_transaction；锁顺序只有同一 DB outer transaction，不再嵌套反序 manager 锁。
- Failure/Rollback：guard 发现漂移报告 reconciliation error，不清队列/重播/擅自写 History；自然结束或外部客户端影响由既有 reconcile 处理。Retry/Idempotency：重新取基线；不能强行恢复过期 current。
- Observable Result：并发 serializable；未确认保留不得成功。Executable Invariant Proof：F3，B3 基础设施；F5/F6，B5/B6 最终输出行为 proof。

**O-TX-001 — TRANSACTION / external output vs outer commit**（O §6.2–6.3；A §19.5）
- Preconditions：API 外层事务或直接 Service operation，可能已产生 MPD 副作用。Authorities：MPD output / 进程内 observed/request state / SQLite terminal record。
- Expected State Delta：成功需实际确认、业务回执和 terminal commit；同 key replay 原结果。Must Remain Unchanged：PRESERVE；数据库失败不能伪造输出已回滚。
- External Confirmation：MPD 变更与 SQLite commit 是不同事实，重试前重新读。History/Event Semantics：未提交请求无成功通知；重放不再通知；不写 History。
- Transaction Boundary：最外层 run_transaction commit 为成功事件边界。Failure/Rollback：terminal/schema/outer failure 或 cancel：无 terminal success；丢弃提交通知、失效请求成功标记，实际输出保留并刷新/标 stale。
- Retry/Idempotency：未提交可 retry，若目标已经满足不重复控制；已提交 replay 不触发读写副作用。Observable Result：HTTP failure 与 MPD 实际变化可同时成立，读取接口呈现事实。
- Executable Invariant Proof：F4 基础设施 B4，F9 B8 全链路最终 proof；B4 不得宣称本 row 已完成。

**O-EVENT-001 — STATE_PROPAGATION / confirmed output notification**（O §6.3；M dependency rule 6）
- Preconditions：OutputChangedEvent + EventPublisher、已确认实际输出变化。Authorities：OutputManager / transaction owner / publisher。
- Expected State Delta：外层 commit 后交付不可变已确认快照事件；无变化的重复请求不制造第二次变化。Must Remain Unchanged：PRESERVE、已提交结果不受发布器异常影响。
- External Confirmation：事件 payload 来自已确认输出，不能用目标态假造。History/Event Semantics：event_type=output.changed；不保证持久投递；失败日志可观测。
- Transaction Boundary：注册于当前最外层事务，commit 后释放 DB 锁再发布，避免 publisher 读同库死锁。Failure/Rollback：rollback/cancel-before-commit 丢弃通知；commit 后发布失败不能使请求改判回滚。
- Retry/Idempotency：重放无事件；未提交重试重新确认。Observable Result：publisher 中读取真实 DB 可见 committed terminal；失败 logger 留证。
- Executable Invariant Proof：F4 B4 hook/事件基础，F5/F6 行为，F9 B8 outer API 最终 proof。

**O-ENABLE-001 — STATE_TRANSITION / ensure selected NAS_DAC enabled**（O §6.1–6.3）
- Preconditions：已验证输出控制能力、唯一目标；O-PRESERVE-001 runner。Authorities：MPD output / service observed+request / playback / transaction。
- Expected State Delta：目标 enabled=true，回读后 actual ACTIVE；请求 PREPARING→SUCCEEDED。Must Remain Unchanged：其它 outputs enabled、PRESERVE。
- External Confirmation：fresh outputs + playback preservation；不能仅凭 ACK。History/Event Semantics：O-EVENT-001；无 History。
- Transaction Boundary：runner 覆盖检查/写入/回读，加入外层事务。Failure/Rollback：O-FAIL-001/O-TX-001；不先关闭旧输出。Retry/Idempotency：布尔 ensure；已 enabled 只确认，无 toggle。
- Observable Result：确认状态或 typed failure + last_request 错误。Executable Invariant Proof：F5，B5；HTTP 部分 B8，不能用 B5 Service GREEN 冒充 HTTP 完成。

**O-DISABLE-001 — STATE_TRANSITION / ensure selected NAS_DAC disabled**（O §4.2、§6.1–6.3）
- Preconditions：同 O-ENABLE-001，显式 enabled=false。Authorities：同 O-ENABLE-001。
- Expected State Delta：仅目标 disabled，actual INACTIVE；不调用 Playback.stop。Must Remain Unchanged：其它 outputs、PRESERVE，包括 AutoPlay/active History。
- External Confirmation：目标 disabled 且播放关系未被操作破坏；若 MPD 实际漂移则报失败。History/Event Semantics：仅输出变化事件，无 STOP History。
- Transaction Boundary：同一 runner/最外层事务。Failure/Rollback：O-FAIL-001/O-TX-001；不重新启停其它设备。Retry/Idempotency：已经 disabled 时只确认。
- Observable Result：确认 INACTIVE 或明确失败。Executable Invariant Proof：F6，B6，HTTP proof B8。

**O-FAIL-001 — STATE_TRANSITION / failed or uncertain output command**（O §6.1–6.2、§8.2）
- Preconditions：命令拒绝、ACK 无效果、超时、取消或确认失败。Authorities：请求结果 / 真实 MPD / server playback。
- Expected State Delta：last_request=SWITCH_FAILED；实际输出由回读决定，旧可用输出继续保留。Must Remain Unchanged：不能为了恢复而改变其它输出、Queue、History、Context。
- External Confirmation：允许“已生效但失败”“未生效”“不可确认”；三者不可混同。History/Event Semantics：失败不是成功事件，无 History。
- Transaction Boundary：外部副作用不可回滚；异常不得被 catch 成普通 2xx；清理不得吞掉 cancellation。Failure/Rollback：回读也失败标 stale；无无限补偿/无限重试。
- Retry/Idempotency：下一次 fresh read，不 blindly repeat；未提交无成功 record。Observable Result：原始失败分类及可观察实际态/新鲜度。
- Executable Invariant Proof：F5/F6 的 failure parametrization；B5 建立、B6 扩展，不能把 failure 全推到 B9。

**INFO-READ-001 — REPRESENTATION / MPD About**（O §7.1–7.3；A §14）
- Preconditions：注入 capabilities / PlayerPort，可以缺能力或断线。Authorities：已验证版本 / 当前 stats / 当前 status/update-status。
- Expected State Delta：只更新读取结果，无业务写入。Must Remain Unchanged：所有输出、播放、Queue、DB；不触发 update_database。
- External Confirmation：stats/runtime update/status 当前读取，version 来源明确。History/Event Semantics：无 History/输出事件。
- Transaction Boundary：只读，不承诺多个 MPD 命令为原子快照；错误按来源分开。Failure/Rollback：失败/缺失字段 null，成功 0 保留，其它成功字段不丢弃。
- Retry/Idempotency：每次重新读；不重放历史 probe stats。Observable Result：version、stats 七字段、updating/job_id、连接事实与来源错误；不把能力拒绝推断为连接断开。
- Executable Invariant Proof：F2，B2；F7 API null/0 保留 B7。

**SYS-READ-001 — REPRESENTATION / system GET responses**（O §5.2/7/8；A §2/13/14）
- Preconditions：已注入 OutputManager/MPDInfoService；未配置能力也能启动。Authorities：Services / REST schemas。
- Expected State Delta：GET 只返回服务事实；output refresh 允许更新 observation cache。Must Remain Unchanged：无 output/playback/DB mutation、无新业务权威。
- External Confirmation：Service 完成；API 不再直接询问 MPD。History/Event Semantics：GET 无切换成功事件。
- Transaction Boundary：不使用 mutation terminal；不得返回 PREPARING 为成功切换结果。Failure/Rollback：可表示的 unavailable/stale 返回资源；不能构造的内部失败遵循统一错误外壳。
- Retry/Idempotency：GET 再读；无 key 要求。Observable Result：不泄漏 output ID/attributes/MPD password，null/0/错误语义不损失。
- Executable Invariant Proof：F7，B7。

**SYS-WRITE-001 — REPRESENTATION / output mutation HTTP boundary**（O §6；P §8.6；A §19.5）
- Preconditions：合法 mode+enabled、Idempotency-Key、Service 注入。Authorities：REST / OutputManager / IdempotencyService / MPD。
- Expected State Delta：成功回执对应已确认目标；terminal commit 后才成功通知。Must Remain Unchanged：PRESERVE；API 不自建 selection/playback policy。
- External Confirmation：由 Service 返回确认态；API schema failure 也是事务失败。History/Event Semantics：O-EVENT-001，无 API 直接广播。
- Transaction Boundary：复用现有 middleware，不新增 Task 7 独立幂等数据库。Failure/Rollback：4xx/5xx 不保存成功 record，O-TX-001；error 包含可理解原因。
- Retry/Idempotency：现有同 key 重放、payload/scope 冲突、未提交 retry 全覆盖。Observable Result：200 confirmed receipt；422 missing key/validation、409 key conflict、400 unsupported/ambiguous、503 unavailable、502 command/reconciliation failure；不把失败包装成 200。
- Executable Invariant Proof：F8/F9，B8。

### 4.3 继承 rows 的逐字段核对

下表补充本 Task 使用范围；不替换历史权威。所有 N/A 均说明不存在该副作用。历史 regression-only 的完整原操作字段仍由 Task 5 Matrix 拥有，§4.4 明确引用/复验，不给它们分配新的业务实现。

| ID / Type / Operation | Preconditions / Authorities | Expected Delta / Must Remain Unchanged | External Confirmation / History/Event | Transaction / Failure-Rollback / Retry | Observable Result / Executable Proof / 本 Task owner |
|---|---|---|---|---|---|
| PORT-OUTPUT-001 / STATE_TRANSITION / output bool transport；继承 O §4/10 + M 1R | 已验证 operation；Mock/Adapter/VerifiedPlayerPort | 指定 ID 启停；不能绕能力 gate；业务保留由 O-PRESERVE-001 另证 | 端口仅命令交付，不替代业务回读；无业务 History/event | 无跨命令事务；typed failure；不假定超时无效果，caller 重读 | 输出模型/typed error；R-PORT；B1/B5/B6 消费，B9 regression；无新增 transport implementation |
| PORT-INFO-001 / REPRESENTATION / stats-update-version；O §7/10 + M 1R | 已验证 capability；capabilities/PlayerPort | 返回真实 nullable 值；不造默认 0 | runtime stats/update-status，version 验证记录；无事件 | 只读，无 rollback；失败 typed；允许重读 | MPDStats/DatabaseUpdateStatus；R-PORT；B2 消费，B9 regression |
| EVENT-PORT-001 / STATE_PROPAGATION / publish；A §12 + M dependency rule 6 | DomainEvent/EventPublisher 已存在；service/publisher | 只经接口交付；不依赖 WebSocket | external output confirmation 由新 O-EVENT-001 所有；旧 Library ordering 不变 | 接口不提供 durable transaction；新提交 hook 不可破坏 Library 既有流程；不许声称 exactly-once | typed DomainEvent；R-EVENT + F4/F9；B4/B5/B8 消费/证明，原事件接口不重实现 |
| TX-ROLLBACK-001 / TRANSACTION / outer unit of work；原 Task 5 row | 同一 DB 嵌套事务，runtime History 独立 | 成功 atomic commit；失败 persisted/session 恢复，PRESERVE | SQLite 不撤外部 MPD；History 无 phantom；事件新增约束在 O-TX-001 | BaseException rollback callback；无 terminal success；retry 必须 reconcile | R-TX；B3/B4 modified implementation，B8 扩展场景；历史字段不更改 |
| TX-IDEMP-001 / TRANSACTION / request replay；原 Task 5 row | key + method/path/canonical payload；API/IdempotencyService | 首次业务+terminal 成功；重放无业务副作用 | 外部确认先于 terminal；重放无新 History/event | failed request 无成功记录；409 conflict；相同请求重放 | R-TX + F9；B8 消费，B4/B9 regression；无另起幂等实现 |

### 4.4 Regression-only IDs（每个均保持原 row，不重开历史 Task）

| Contract ID | 触及关系 / Must Remain Unchanged obligation | 原 row 权威 / 本 Task 实际验证 Batch |
|---|---|---|
| PB-STOP-001 | confirmed STOP、AutoPlay/History 终止；输出 disable 绝不偷偷调用 stop | Task 5 active §3.6，R-STOP；B3/B4/B6/B8/B9 |
| PB-INSERT-001 | 插入 pending 的 current occurrence/History/Context 不变 | 同上，R-PLAY insertion；B3/B5/B8/B9 |
| PB-REORDER-001 | Queue↔Player order、retained occurrence ID | 同上，R-PLAY；B3/B5/B8/B9 |
| PB-DELETE-PENDING-001 | 精确 pending occurrence 和 refill 关系 | 同上，R-PLAY + 既有 `server/tests/api/test_pre_batch6_corrective.py`；B3/B9 |
| PB-DELETE-CURRENT-001 | successor/STOP confirmation，History transition | 同上，同前及 R-STOP；B3/B9 |
| PB-NEXT-UNAVAILABLE-001 | 不可用 successor 不得成为 current，skip/history 一致 | 同上，R-PLAY transition + R-TX；B3/B4/B9 |
| PB-HISTORY-001 | confirmed transition 才创建/结束 History，输出不产 transition | 同上，R-PLAY/R-TX；B3–B6/B8/B9 |
| PL-REP-001 | Playlist persisted membership 对所有表示一致 | 同上，R-PL；仅共享 transaction/API wiring 影响时 B4/B7/B8，B9 |
| PL-COLLECTION-001 | playable split 不修改持久成员 | 同上，R-PL；同前；无 Task 7 新业务 |

## 5. 冻结接口、数据表示与最小文件结构

接口在此规划中冻结；B1 模型、只读/拒绝 Service 和 F1 已存在，其余新增接口仍为未来实现目标。各 row 的最终 proof 阶段不因 B1 局部 GREEN 提前完成。

- B1 `server/app/models/output.py`：`OutputMode(NAS_DAC, CLIENT_STREAM)`；`OutputState` 包含 mode/status、stream 预留字段、error_code/error_message、updated_at、stale；`OutputRequestState` 包含 mode/enabled/status(PREPARING/SUCCEEDED/SWITCH_FAILED)/error/time；`OutputSnapshot(states: tuple[OutputState, ...], last_request: OutputRequestState | None)`。observed 只用三个事实状态，五种原规定状态分布在 observed/request 两个维度。API aliases 使用 O §5.2 的 camelCase。
- 读取仅要求对应读取能力；actual ACTIVE 不等于具备控制权限。B5/B6 在任何写命令前检查 `outputs`、`set_output_enabled`、`status`、`queue_entries` 所需能力，不能在副作用后才发现无法确认。
- B1 `OutputManager.__init__(*, player: PlayerPort, capabilities: MPDCapabilities, operation_runner, selector=None, event_publisher=None)`；`async get_state() -> OutputSnapshot`；`async set_enabled(mode: OutputMode, enabled: bool) -> OutputSnapshot`。B1 只实现查询和 CLIENT_STREAM 拒绝，不开放 NAS mutation 给 API。
- selector 技术签名：`Callable[[tuple[OutputInfo, ...]], OutputInfo | None]`；输入仅本次 ALSA candidates；返回必须唯一对应输入的一个成员，不能返回旧 ID/外部对象冒充匹配。无 selector 仅单候选可选。
- B3 `PlaybackService.run_output_operation(operation: Callable[[], Awaitable[T]]) -> T`：公开共同串行化入口，callback 不得到 Repository 或 sqlite connection。OutputManager 只经注入 runner 协调，不访问具体 adapter、不 import API。
- B3 输出 guard 在 `output_manager.py` 读 before/after PlayerStatus+queue_entries；检查 occurrence/order/state/音量模式，position 使用可注入 monotonic clock；播放中 elapsed 差须与测量窗口相容（测试用 fake clock，不硬编码“允许丢 5 秒”）。真实时钟/MPD 时间粒度容差须记录，不能用宽容差掩盖 reset；无法证明时不声称保留成功。
- B4 `database.on_transaction_commit(path: str, callback: Callable[[], object | Awaitable[object]]) -> None`；只能 active transaction 注册；嵌套只注册到最外层。commit 后先退出 transaction ContextVar/释放锁再调用 callbacks；rollback 丢弃。publisher 异常隔离及日志由提交通知路径保证，不能进入 rollback 分支。
- B4 `OutputChangedEvent(DomainEvent)`：`event_type="output.changed"`、`snapshot: OutputSnapshot`；快照 deep copy，不随下次 mutation 改变。成功只在有效输出实际变化时 emit；重复确保状态/重放不制造变化事件。B5/B6 集成时注册；请求失败状态由读取/错误响应可见，无“失败也算成功”的事件。
- B2 `server/app/models/mpd_info.py` / `MPDInfoService.__init__(*, player: PlayerPort, capabilities: MPDCapabilities)`；`async get_info() -> MPDInfo`。包含 version、MPDStats 七字段、DatabaseUpdateStatus 两字段、connected: bool | None、errors 按来源、observed_at。最后一次 status 读取确认连接：成功 true、PlayerUnavailable false、capability/command 未能确认时 null 并留错误；独立 stats 成功不伪造 status 成功。version 保留时标为 verified capability 来源。
- B7 `server/app/api/system_schemas.py`：OutputSnapshotResponse、MPDInfoResponse、OutputSetRequest(mode, enabled)；API 与 domain model 分离；schema 不开放 MPD 数字 ID/attributes。`system.py`：GET `/api/system/output`、GET `/api/system/mpd`；B8 才加入 PUT `/api/system/output`。
- B7 `get_output_manager(request)` / `get_mpd_info_service(request)` 放既有 dependencies.py；main 仅 minimal composition/router。OutputManager 与 PlaybackService 必须用同一个 PlayerPort；注入 capabilities/selector/publisher，不建第二播放引擎。没有已验证 capabilities 时 fail closed、可启动，不自动运行会修改 queue/output 的 CapabilityProbe；验证结果加载/最终 config 仍 Task 10。测试显式注入真实格式的 verified capabilities，不把 fixture 当生产证明。
- TO CREATE unit tests：`server/tests/services/test_output_manager.py`（B1/B5/B6）、`test_mpd_info_service.py`（B2）、`server/tests/repositories/test_transaction_commit_hooks.py`（B4）、`server/tests/api/test_system_reads.py`（B7）、`test_system_output_mutations.py`（B8）。

不得在接口冻结 Batch 写占位“成功”实现；不可用路径必须明确拒绝。内部 helper 名称可在所属 Batch RED 后决定，不得改变上述跨 Batch 合同。

## 6. 新 invariant proof register（F1 已存在，其余 TO CREATE）

| ID | TO CREATE 文件与函数 | 必须跨越的真实关系 / 核心断言 | owner / final proof |
|---|---|---|---|
| F1 | `server/tests/invariants/test_output_observation.py`：`test_output_identity_and_observation_follow_current_port`、`test_reserved_mode_has_no_external_side_effect` | OutputManager + VerifiedPlayerPort + Mock/spy；0/1/多 ALSA、ID 漂移、selector 无效/异常、缺能力、断线/cache stale、reserved 不写 MPD，包含 HTTPD enabled 仍 unsupported | B1；transition 状态追加在 F5/F6 |
| F2 | `server/tests/invariants/test_mpd_info_relationships.py::test_info_preserves_runtime_sources_nulls_and_real_zero` | MPDInfoService + verified port + Mock；runtime 值不同于 probe 样本；独立失败不丢成功值，version 不证明连接，无 mutation | B2 |
| F3 | `server/tests/invariants/test_output_serialization.py`：`test_output_operation_serializes_with_playback_mutations`、`test_output_guard_preserves_occurrence_context_and_history` | 真实 SQLite/PlaybackService/History + OutputManager guard + Mock；同一 loop 用 Events barrier，参数覆盖公开 playback mutation，验证相互阻塞/串行结果；duplicate current、PLAYING/PAUSED/STOPPED/空态、未知 position | B3 guard；B5/B6 实际启停后补最终 proof |
| F4 | `server/tests/invariants/test_output_event_transactions.py`：`test_output_notification_waits_for_outer_commit`、`test_rollback_and_cancellation_discard_notification`、`test_publisher_failure_cannot_undo_commit` | 真实 transaction + terminal/persisted witness + publisher；内层结束不发布、publisher 可另开读取看到 commit、不死锁、取消/rollback 丢弃、事件 snapshot 不被后续修改；commit 后取消不得删除已提交 terminal 或调用 rollback callbacks | B4 提交基础；B8 真实 API 输出最终 proof |
| F5 | `server/tests/invariants/test_output_enable.py`：`test_enable_preserves_other_outputs_and_all_playback_authorities`、`test_enable_failure_reconciles_actual_output_without_false_success` | 真实 repos+PlaybackService+OutputManager+verified/fault port；after-ACK no effect、effect then timeout、ID 漂移、readback fail、取消后 retry；断言完整 before/after snapshot、MPD occurrences、输出 enable calls 及 commit/event 次序 | B5 |
| F6 | `server/tests/invariants/test_output_disable.py`：`test_disable_is_not_playback_stop`、`test_disable_failure_keeps_truth_and_retry_is_safe` | 同 F5 协作栈；不得调用 stop/seek/play/queue mutation，不结束 active History/AutoPlay；disable/no-op/failure/uncertain result 与其它 outputs 不变 | B6 |
| F7 | `server/tests/invariants/test_system_read_relationships.py::test_system_rest_preserves_service_facts_and_sources` | real Service + API schema；fresh/stale/last_request/unknown/0 无丢失，不暴露内部 IDs；无能力/MPD unavailable 启动与读可观察；实际 service wiring 共享 port | B7 |
| F8 | `server/tests/invariants/test_system_output_relationships.py::test_output_mutation_response_matches_confirmed_service_and_port` | real API→Service→Port；合法 enable/disable/no-op 与 unsupported/validation/MPD failures 不伪报成功；response body 和实际 confirmed state 比较 | B8 |
| F9 | `server/tests/invariants/test_output_idempotency.py::test_output_external_effect_outer_failure_retry_and_replay` | real SQLite+middleware+OutputManager+port+publisher；terminal INSERT、response schema、outer failure、cancel、commit failure（可控 seam）；MPD 可以已变、无 terminal success/成功事件，重试先读取、无反向补偿，最终成功同 key replay 无控制/事件 | B8 |

F5/F6 使用 Mock 的有效 ALSA outputs 注入和局部 fault-port；不改变生产 Mock 默认含义。至少有一组新 test 在 `server/tests/invariants/test_output_transport.py::test_output_confirmation_through_mpd_adapter`（TO CREATE，B5）用真实 MPDAdapter + localhost fake TCP 确认 output command 与 readback 的集成；不把已有静态 transport ACK test 说成新的 preservation proof。F5 owner 同时拥有这项 proof，不需新增业务 row。

## 7. Batch Execution Plan

### 共同执行与验收规则

每 Batch 先读取：M Task 7/相关 gates、O 本 Batch 引用段、下列 Contract rows、直接 production/test dependencies；无需读整个项目历史。

每个实现 Batch（B1–B8）执行：
- [ ] 检查依赖实际 commits/接口与 clean scope；记录本 Batch Owned/Relied/Regression 和两个 Gate。
- [ ] 创建/扩展本 Batch TO CREATE RED tests，运行并确认因缺行为失败，而非依赖/导入环境错误。
- [ ] 最小实现 → focused GREEN → 本 Batch invariant proof；失败不进入下一 Batch。
- [ ] 运行下列直接 regression；`python -m compileall -q server`、`python -m ruff check <本 Batch 实际修改的 Python 路径>`、`git diff --check`；检查 diff/越界/未来 Task imports。
- [ ] 记录 RED/GREEN/未完成 row/commit；仅在实际提交后核实远端 ref。未完成跨 Batch row 不标 COMPLETE。

以下复杂度为估算 production substantive LOC（不含 tests/docs），不是扩大范围额度。任一 Batch 预测接近 500–800 行、超过表列明显数量或出现多个独立状态机，重新拆；约 1000 行默认禁止。基础设施 Batch 的 partial row 仅能通过自身局部 gate，不满足整个 output 合同 completion。

### B1 — 只读输出身份/状态与 reserved 拒绝

- Scope / 原 Step：Step 1 读取态、Step 2、Step 5 只读部分；冻结 §5 Output 接口/模型。
- Owned：O-DISC-001、O-STATE-001（只读阶段）、O-RESERVED-001。Relied：PORT-OUTPUT-001。Regression：无旧业务 row；R-PORT 为直接端口回归。
- Relationship **REQUIRED**（port→mode/状态）；Matrix **REQUIRED**（表示/拒绝无副作用）。
- RED/invariants：`test_output_manager.py` + F1；包括 target ID 非 0、多个 ALSA、无 selector、selector 无效/抛错、已开 httpd、unverified、unreachable、旧缓存 stale。
- 允许 production：TO CREATE models/output.py、services/output_manager.py（仅读与 reserved）。禁止：NAS 启停成功路径、DB/History/playback 修改、API/events/main、WebSocket。
- Acceptance：F1 GREEN、R-PORT 相关 step4/6 tests；读操作没有 mutation。O-STATE-001 的 request transition 仍 pending B5/B6；B1 不宣称 Task 7 控制已完成。
- 当前局部验收：B1 focused 24 passed、显式 F1 20 passed、R-PORT step4/6 4 passed；compile、changed-Python Ruff、架构/范围审查通过。完整执行/关系 Gate 证据见 §1 归档引用；未完成 row 保持 pending。
- Complexity：3 紧密相关 rows，1 主边界，0 成功写转换，2 production files，约 180–300 行；失败定位于 observation/selector/schema，diff 单窗口可审阅。

### B2 — MPD About 真实来源与空值

- Scope / 原 Step：Step 6–7；可在 B1 后执行，与控制路径独立。
- Owned：INFO-READ-001。Relied：PORT-INFO-001。Regression：无旧业务 row；R-PORT stats/update 部分。
- Relationship **REQUIRED**（port/capability→service）；Matrix **REQUIRED**（多来源表示）。
- RED/invariants：TO CREATE test_mpd_info_service.py + F2；统计样本与 runtime 不同、0/null、partial failure、拒绝/断线分开、更新读取不触发 update。
- 允许 production：TO CREATE models/mpd_info.py、services/mpd_info_service.py。禁止：输出控制、probe 写入、API、NAS 监控、配置/部署。
- Acceptance：F2 GREEN、R-PORT step5/6/7，确认 MPDStats 七字段无缺失、无伪造/缓存实时统计。
- Complexity：1 row，2 读取来源边界，0 状态转换，2 files，约 100–180 行；RED/GREEN 按一个数据来源定位。

### B3 — 共同串行化与播放保留 guard

- Scope / 原 Step：Step 4、Step 5 prerequisite；依赖 B1。只建立已定义的输出操作保护边界，不实现 NAS 控制。
- Owned：O-PRESERVE-001（guard/协调基础）。Relied：PORT-OUTPUT-001、TX-ROLLBACK-001。Regression：PB-STOP-001、PB-INSERT-001、PB-REORDER-001、PB-DELETE-PENDING-001、PB-DELETE-CURRENT-001、PB-NEXT-UNAVAILABLE-001、PB-HISTORY-001 rows。
- Relationship **REQUIRED**（SQLite/runtime/player 并发）；Matrix **REQUIRED**（保留/事务）。
- RED/invariants：F3；用 output callback 的人工 barrier 与公开 playback operations 交错，不能用 sleep 猜顺序。B3 test callback 不模拟最终 enable 已实现。pause/seek/insert 的既有语义必须回归。
- 允许 production：playback_service.py（runner + play_next/add_to_queue/pause/seek 的整段现有 run_transaction 包装），output_manager.py（注入 runner、before/after preservation guard）。如其它 mutation 实际未整段串行，先记录具体证据并只补同类边界，不重写播放算法。
- 禁止：改 Queue/AutoPlay/History 规则、自动 seek/重播恢复、repository schema、NAS 启停、API。
- Acceptance：F3 GREEN；R-PLAY/R-STOP、`server/tests/services/test_playback_service.py`、`server/tests/api/test_pre_batch6_corrective.py` GREEN；没有新增播放副作用。O-PRESERVE-001 仍等待 B5/B6 对真实输出操作证明。
- Complexity：1 新 row + 既有关系回归，3 边界，1 协调机制，2 files，约 120–220 行。若需要通用播放器重构即超范围，停在证据化 gate 重新规划。

### B4 — 最外层提交通知与回滚纪律

- Scope / 原 Step：Step 5 必要 lifecycle 支持；依赖 B1/B3；不实现 HTTP 或真实启停。
- Owned：O-TX-001、O-EVENT-001（基础设施阶段）；affected existing implementation：TX-ROLLBACK-001。Relied：EVENT-PORT-001、TX-IDEMP-001。Regression：TX-ROLLBACK-001/TX-IDEMP-001/PB-STOP-001/PB-HISTORY-001/PL-REP-001/PL-COLLECTION-001 rows。
- Relationship **REQUIRED**（outer SQLite/runtime/publisher）；Matrix **REQUIRED**（commit 与事件次序）。
- RED/invariants：TO CREATE test_transaction_commit_hooks.py + F4；nested 注册、rollback/cancel、commit 抛错、callback 读同 DB 不死锁、publisher exception 不撤 commit、commit 后取消仍保留 terminal 供重放（不能假称回滚）。独立声明这是 hook proof，非最终 output API proof。
- 允许 production：database.py（only transaction lifecycle hooks）、events.py（OutputChangedEvent）、output_manager.py（注册通知/回滚请求标记的 helper）。禁止：改幂等 fingerprint/status 策略、新 outbox/schema、重写 scanner publication、WebSocket、输出 mutation/API。
- Acceptance：F4 GREEN；R-TX/R-EVENT/R-PL GREEN；所有 callbacks 在 transaction context/锁退出后运行；DB 已 commit 后不得执行 rollback callbacks 或冒充回滚。O-TX-001/O-EVENT-001 最终 proof 仍 pending B8。
- Complexity：2 新 rows + 1 affected implementation row，3 边界，单一 commit lifecycle，3 files，约 160–280 行；以确定性 transaction failure seam 缩短反馈周期。

### B5 — NAS_DAC enable：完整成功/失败最小操作

- Scope / 原 Step：Step 1/3/4/5 的 enable 部分；依赖 B1/B3/B4（B2 不阻塞核心）。
- Owned：O-ENABLE-001、O-FAIL-001（enable）、O-STATE-001（请求态落地）。Relied：O-DISC-001/O-RESERVED-001/O-PRESERVE-001/O-TX-001/O-EVENT-001 rows、PORT-OUTPUT-001、EVENT-PORT-001。Regression：PB-INSERT-001、PB-REORDER-001、PB-HISTORY-001、TX-ROLLBACK-001 rows；F1/F3/F4。
- Relationship **REQUIRED**（MPD output 与全部播放权威）；Matrix **REQUIRED**（确认/失败/保留）。
- RED/invariants：F5 + TO CREATE test_output_transport.py；完整 success/no-op/ACK-no-effect/timeout-after-effect/断线/取消/ID变化；不把失败补偿留给最终审计。
- 允许 production：output_manager.py（enable、公共 failure/reconcile helpers）。必要 typed output errors 放该模块，不改 PlayerPort 或探针。测试 fault adapters 放 tests 内。
- 禁止：disable 业务、其它输出停用、API、重写 playback reconciliation、Task 6。
- Acceptance：F5 + F1/F3/F4 GREEN；R-PORT、R-PLAY 中 insertion/occurrence、R-TX；目标确认前不得成功/通知；其它输出保持；direct Service transaction 的事件确认顺序成立。O-ENABLE-001 Service 完成；O-FAIL-001 disable 扩展及整体 O-TX-001 API 仍 pending。
- Complexity：3 相关 owned rows，3 边界，1 布尔目标转换及其失败分支，1 production file，约 150–250 行；大型基础设施已经 B3/B4 拆出，失败定位在命令/回读。

### B6 — NAS_DAC disable：不等于 Stop

- Scope / 原 Step：Step 1/3/4/5 的显式 disable；依赖 B5。
- Owned：O-DISABLE-001、O-FAIL-001（disable 扩展）、O-PRESERVE-001（最终 Service 两操作 proof）。Relied：O-DISC-001/O-STATE-001/O-TX-001/O-EVENT-001、PORT-OUTPUT-001 rows。Regression：PB-STOP-001、PB-HISTORY-001、O-ENABLE-001、O-STATE-001、TX-ROLLBACK-001、TX-IDEMP-001；F5、R-TX。
- Relationship **REQUIRED**（输出与播放状态分离）；Matrix **REQUIRED**（停用副作用保留）。
- RED/invariants：F6；包括最后一个 enabled output、Paused/Playing/Stopped/empty、already-disabled、ACK-without-effect、effect-then-timeout、取消、回读失败；MPD 自动改变播放状态时不得伪报保留成功。
- 允许 production：output_manager.py（disable + 复用已有确认/失败），models/output.py 仅已有冻结模型必要校正。禁止：Playback Stop/seek/queue rebuild、修改其它输出/AutoPlay/History/stream。
- Acceptance：F6/F5/F3/F4、R-STOP GREEN；stop/play/seek/queue mutation 的 call count=0；active History/session 保持；没有重复 enable 算法副本。O-STATE-001/O-FAIL-001/O-PRESERVE-001 Service rows 可完成；API 关系仍 pending B8。
- Complexity：1 新行为 + 2 已有 row final proof，3 边界，1 转换，1–2 files，约 40–120 行。

### B7 — System read API 与最小接线

- Scope / 原 Step：Step 5/6 API 暴露部分、Step 7 表示；依赖 B1/B2/B6。只 GET，不暴露 mutation。
- Owned：SYS-READ-001。Relied：O-STATE-001、INFO-READ-001、PORT-OUTPUT-001、PORT-INFO-001。Regression：PL-REP-001、PL-COLLECTION-001（main wiring）、R-ARCH；F1/F2。
- Relationship **REQUIRED**（Service→REST/DI）；Matrix **REQUIRED**（字段真值/边界）。
- RED/invariants：TO CREATE test_system_reads.py + F7；DI 实例一致，GET schemas/full nullable fields、MPD unavailable startup、能力缺失 fail closed、无输出 probe 写入。
- 允许 production：TO CREATE api/system.py、api/system_schemas.py；modify dependencies.py/main.py（仅 System Services injection + router registration）。不改变其它 app 生命周期行为。
- 禁止：PUT 路由、幂等/事务规则改写、未来 config loader/dev-prod 重构、WebSocket/Web/真实 NAS 操作。
- Acceptance：F7/R-ARCH/R-PL、`server/tests/test_health.py`、既有 `server/tests/api/test_api_contracts.py` GREEN；GET 无 Idempotency-Key 也合法、null/0 原样保留。未验证 capability 时不谎报 ready。
- Complexity：1 row，2 边界，0 写转换，4 production files，约 170–270 行。4 文件都是同一 read representation+DI，不能在此展开第二生命周期或配置系统。

### B8 — 输出 mutation REST 与外层事务最终 proof

- Scope / 原 Step：Step 5 API 剩余、Step 3/4/8 integration；依赖 B4–B7。
- Owned：SYS-WRITE-001、O-TX-001、O-EVENT-001（最终 integration/proof）。Relied：O-ENABLE-001/O-DISABLE-001/O-FAIL-001/O-PRESERVE-001/O-RESERVED-001、TX-ROLLBACK-001/TX-IDEMP-001/EVENT-PORT-001 rows。Regression：全部 §4.4 rows（共享 middleware/事务实际关系），F1–F7。
- Relationship **REQUIRED**（REST↔Service↔MPD↔terminal/event）；Matrix **REQUIRED**（跨权威提交/重试）。
- RED/invariants：TO CREATE test_system_output_mutations.py + F8/F9；missing key、422 schema、409 payload/scope、unsupported、typed MPD errors、outer/commit/cancel failure、schema failure-after-effect；same key retry/replay 同时断言输出 calls/DB/history/event。
- 允许 production：system.py/system_schemas.py；output_manager.py 仅 outer transaction 集成缺口，不能新增输出语义。若需修改通用 idempotency/database 超出 B4 冻结接口，先报告 concrete failed invariant，另开最小 corrective，不顺带扩张本 Batch。
- 禁止：重写已有幂等协议、让 API 导入 Repository、在 API 直接 publish/调用 MPD、新增状态机/持久表、Task 6。
- Acceptance：F8/F9 GREEN，publisher 看到 committed terminal；failed terminal 后 MPD 可保持已变，读取不伪装 rollback；retry 先观察；成功 replay 不再控制/发事件。R-TX/R-STOP/R-PLAY/R-PL/R-ARCH 全部 GREEN；此时所有新增 row 最终 executable proof 都已存在并通过。
- Complexity：3 高相关 rows，4 边界，**不新增设备转换**，2–3 files，约 80–180 行；主要工作是故障注入关系测试，生产事务/设备行为已由前面 Batch 实现。若生产改动超 300–400 行说明前置合同未闭合，回到对应最小 Batch 修正。

### B9 — Task final gate / handoff（不新增 production/test 功能）

- Scope / 原 Step：Step 8–9；依赖 B1–B8。
- Owned：无新 row；执行所有 rows 最终验收，原 implementation owner 不改变。Relied/Regression：§4 全部 IDs。
- Relationship **REQUIRED**（M Task 7 + affected historical）；Matrix **REQUIRED**（完整 traceability）。
- RED tests：N/A，仅验收；发现 defect 则停止本 Batch，回到对应 row owner 单独 corrective RED→GREEN，不能偷偷在 final gate 开发。
- 允许：文档中事实状态/acceptance、已验证范围的 final commit。禁止：任何新增 production/function test、Web build/E2E、自动切换真实 NAS output、提前 Task 6。
- Acceptance：§8 所有命令/覆盖复核、diff 范围、远端 commit/ref 二次验证；Task 7 Step 1–9 按真实完成勾选。未运行真实 NAS 不宣称物理 DAC 验收。PR/merge 不等于实现 gate，本计划不授权自动合入 main。
- Complexity：0 新行为、0 production files/LOC；full backend suite 与 scoped review，不能用 full suite 替代 F1–F9 明确执行。

## 8. 验证命令与 Coverage Review

命令从 repo root 执行；`python` 为已安装 `server/requirements.txt` 的目标虚拟环境，不要求 Docker。当前已核实 Makefile 使用 `PYTHONPATH=. python -m pytest server/tests`、ruff/compileall 可按以下形式运行；工具本次不可用，不把命令列举写成执行成功。

### 8.1 已存在最小前置/历史回归命令

```bash
python -m pytest -q server/tests/player/test_task1r_step4.py server/tests/player/test_task1r_step5.py server/tests/player/test_task1r_step6.py server/tests/player/test_task1r_step7.py
python -m pytest -q server/tests/invariants server/tests/services/test_playback_service.py server/tests/api/test_idempotency.py server/tests/api/test_pre_batch6_corrective.py
python -m pytest -q server/tests/integration/test_task3_events_and_mpd.py
```

各 Batch 使用上面命令中的实际直接相关路径，不强制每小步全量跑。B3/B4 扩共享基础必须跑表列历史关系。

### 8.2 未来 Batch 命令（全部测试目标 TO CREATE；创建后才可执行）

| Batch | focused / explicit invariant command（均 `python -m pytest -q` 后的参数） |
|---|---|
| B1 | `server/tests/services/test_output_manager.py server/tests/invariants/test_output_observation.py` |
| B2 | `server/tests/services/test_mpd_info_service.py server/tests/invariants/test_mpd_info_relationships.py` |
| B3 | `server/tests/invariants/test_output_serialization.py` + 本 Batch 历史回归 |
| B4 | `server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_output_event_transactions.py` |
| B5 | `server/tests/services/test_output_manager.py server/tests/invariants/test_output_enable.py server/tests/invariants/test_output_transport.py` + F1/F3/F4 |
| B6 | `server/tests/services/test_output_manager.py server/tests/invariants/test_output_disable.py` + F3/F4/F5 |
| B7 | `server/tests/api/test_system_reads.py server/tests/invariants/test_system_read_relationships.py` |
| B8 | `server/tests/api/test_system_output_mutations.py server/tests/invariants/test_system_output_relationships.py server/tests/invariants/test_output_idempotency.py` + §7 要求回归 |

B9 必须运行独立关系 gate，再跑全 backend：

```bash
python -m pytest -q server/tests/invariants
python -m pytest -q server/tests
python -m compileall -q server
python -m ruff check server
git diff --check
```

基准：0 failed / 0 errors；所有本 Task 必需 case 被收集执行，不允许靠 skip/xfail/deselect 取得绿色。预期通过数量由新实际 collection 确认，不抄历史数字。最终检查 `git diff <本 Task 实际基线>...HEAD --stat` 与逐文件 diff（尚未提交的工作区另查 `git diff`），核实无额外 production/test 范围；远端 `git ls-remote --heads origin feature/task-7-output-manager` 对照真实 commit，并在新 fetch 后核对 ancestry。

### 8.3 Spec → ID → Batch → implementation → proof → acceptance

| Spec | IDs | Implementation owner | Implementation path（TO CREATE / Modify） | final proof / Gate |
|---|---|---|---|---|
| O §4/6.1 | O-DISC-001 | B1 | TO CREATE output_manager.py | F1 B1 + F5 ID drift；B9 aggregate |
| O §5.2/6.1 | O-STATE-001 | B1 freeze/read；B5/B6 behavior | TO CREATE models/output.py + manager | F1/F5/F6；B6 Service final、B8 REST |
| O §5/6.1 | O-RESERVED-001 | B1 | manager | F1；F8/F9 B8 HTTP；B9 |
| O §6.2 + A §8.1 | O-PRESERVE-001 | B3 guard；B5/B6 behavior | Modify playback_service.py；manager | F3/F5/F6；B6 Service final、B8 cross-authority |
| O §6.2/6.3 + A §19.5 | O-TX-001 | B4 foundation；B8 integration | Modify database.py；manager；TO CREATE system.py | F4/F9；B8 final |
| O §6.3 | O-EVENT-001 | B4 foundation；B5/B6 emit；B8 integration | Modify events.py/database.py；manager | F4/F5/F6/F9；B8 final |
| O §6 | O-ENABLE-001 | B5 | manager | F5 + fake TCP；F8/F9 B8；B9 |
| O §4.2/6.1 | O-DISABLE-001 | B6 | manager | F6；F8/F9 B8；B9 |
| O §6/8.2 | O-FAIL-001 | B5 enable；B6 disable | manager | F5/F6；F9 outer failures；B8 final |
| O §7 + A §14 | INFO-READ-001 | B2 | TO CREATE models/mpd_info.py/mpd_info_service.py | F2；F7 B7；B9 |
| O §5/7/8 + A API boundary | SYS-READ-001 | B7 | TO CREATE system.py/system_schemas.py；Modify dependencies.py/main.py | F7/R-ARCH；B7 final |
| O §6 + P §8.6 + A §19.5 | SYS-WRITE-001 | B8 | system.py/system_schemas.py | F8/F9/R-ARCH；B8 final |

Coverage review results:
- 12 新 rows 都有 implementation owner 和最终 proof；无 ownerless row。继承 rows 不分配重复实现，§4.3 指定消费/证明 Batch；9 个 regression-only rows 的原 implementation owner 保留，§4.4 指定本 Task 验证 Batch。
- 每 Batch Owned/Relied/Regression 均列出；B9 Owned=none 合法，因为不新增跨模块行为。
- 所有跨模块行为都有 row：selector/表示、preservation serialization、external/SQLite、post-commit event、About、REST。纯依赖方向使用 R-ARCH，不重复造业务 row。
- Contract/interface freeze 在本计划 §4/5；跨 Batch 的 foundation→behavior→final proof 已逐 row 列明，中间阶段不可标 COMPLETE。
- 无 Task 6 snapshot schema/reconnect/WebSocket fan-out、Task 8 store/UI、Task 10 config/backup 或 CLIENT_STREAM transport 语义混入 Matrix。
- 未把 probe 样本当 runtime、未把计划 tests 当现有证据、未把 Task 5 历史 GREEN 当新验证。
- 当前完成的是规划，后续 fresh GREEN/远端实现提交仍待各 Batch。若发现新 Contract Gap，先回到唯一 Spec，再更新对应 row/最小 Batch；不得扩大某 Batch 掩盖缺口。
