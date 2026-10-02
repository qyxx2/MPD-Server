# MPD-Server Task 5 Active Batch Plan

Branch: `feature/task-5-library-api`

本文件是 Task 5 的**当前执行合同**。完整的历史 Batch 计划、Contract Audit 记录和旧 completion log 保存在：
`docs/superpowers/archive/task-5/2026-09-29-mpd-server-task-5-batch-plan-full-history.md`。

## 1. Authority 与当前状态

权威顺序：
1. `docs/superpowers/specs/` 中与 Library / Playlist / Playback / Architecture 相关的规格；
2. `2026-09-25-mpd-server-v0-1-implementation-plan.md` 的 Task 5 与依赖规则；
3. 本 active plan；
4. 当前 corrective handoff；
5. 实际代码、测试和 Git 用于确认上述实现状态。

当前状态：
- Contract Audit：完成；
- Batch 1–5：完成；
- Pre-Batch-6 A/B corrective：完成；
- Batch 6：**COMPLETE**（final acceptance Gate GREEN）；
- Task 5 relationship/invariant foundation：**COMPLETE**；relationship gate 仍为 **REQUIRED**；
- A/B/C/D/E corrective 已关闭；Batch 6 pending duplicate occurrence corrective 已关闭，无已知未关闭 blocking finding；
- 原 Implementation Plan Task 5 Step 9–10 已完成；Task 5 final acceptance 与 PR/main merge 保持独立状态。

当前验收证据的唯一 handoff：
`2026-10-01-task-5-contract-architecture-corrective-acceptance.md`。

## 2. Dependency 与范围

Task 5 依赖 Task 3 和 Task 4 已完成的合同：
- Available Songs / DomainEvent；
- Queue / PlaybackContext / History / AutoPlay / PlaybackService；
- PlayerPort 与 SQLite Repository 边界。

Task 5 不依赖、也不得提前实现 Task 6–12：
WebSocket/StateService、Output Manager、Web/PWA 状态层与 UI、最终配置/备份/部署、物理环境验收。

固定架构：
```text
API
 ↓
Service
 ↓
Repository / PlayerPort
```

禁止：
- API → SQLite；
- API → concrete MPDAdapter；
- Service 绕过 PlayerPort 控制 MPD；
- 为当前 Batch 顺手实现未来 Task。

跨 Task 合同可以被当前范围调用和验证；若当前 Task 的明确 invariant 横跨已有接口，允许做满足该合同所必需的最小修复，不以“旧 Task 文件”作为保留错误行为的理由。

## 3. Frozen contracts

### 3.1 Collection

source type 固定为：
`ALBUM / ARTIST / GENRE / YEAR / TAG / SEARCH / PLAYLIST / FAVORITES / LIBRARY / SONGS`。

核心 invariant：
- `song_ids` 只包含当前可播放 Song，按最终播放顺序且去重；
- 已知但不可用成员进入 `unavailable_song_ids`；
- explicit SONGS 保留第一次出现的用户顺序；
- empty Collection 是合法空结果，不用随机歌曲补齐；
- random seed 每个新 PlaybackContext 生成一次，同一 Context 内顺序固定；
- Collection 决定“哪些歌曲、什么顺序”；PlaybackService 决定真正播放与 Queue/AutoPlay 行为。

默认排序保持原冻结规则：
- Album：disc → track → file_uri → song_id；
- Playlist：persisted position；
- Favorites：created_at DESC → song_id DESC；
- Artist/Genre/Year/Tag/Library：title → album → file_uri → song_id；
- Search：match rank 后使用稳定 fallback。

### 3.2 Playlist resource 与 Collection 必须分离

Playlist 资源表示**持久化成员关系**：
- list/detail/mutation response 的 `song_ids` 必须保留 persisted order；
- MISSING / UNREADABLE 成员仍属于 Playlist resource；
- `GET /playlists/{id}/songs` 应暴露这些成员及 availability；
- 不允许不同 Playlist endpoint 对成员集合使用不同 visibility policy。

Playlist 转为 Collection 时才应用 playable split：
- AVAILABLE → `song_ids`；
- unavailable → `unavailable_song_ids`。

不得用 Collection 的过滤结果替代 Playlist resource membership。

### 3.3 Search

字段：title、artists、album、album_artists、genres、tag_names、year。

规则：
- trim + Unicode `casefold()`；
- 非空 query 做 substring match；
- 排序：exact → prefix → substring → title → album → file_uri → song_id；
- 同一 Song 只返回一次；
- 空 query / 无结果均返回合法空结果；
- 不引入 FTS 或外部搜索引擎。

### 3.4 REST / schema

API 使用 `/api` 前缀，覆盖：
- Library Song/Album/Artist/Genre/Year/Tag/Search/Collection/artwork/scan；
- Playlist/Favorites read + mutation；
- Playback state/actions/Queue/collection play/save；
- History read。

统一原则：
- API schemas 与 domain models 分离；
- list 使用 `items + count`；
- mutation 返回 mutation 后 authoritative resource/state；DELETE 成功为 204；
- artwork 从 persisted ArtworkRef 只读返回真实 bytes/MIME；
- 同一资源类型跨 endpoint 使用同一资源语义。

统一错误 envelope：
```json
{"error":{"code":"STABLE_MACHINE_CODE","message":"human-readable message","details":null}}
```

状态类别保持：200/201/204 success；400 semantic invalid；404 missing source/resource；
409 resource/idempotency conflict；422 schema validation；500 repository/unexpected；
502 PlayerPort 命令已到达但失败；503 PlayerPort 不可达。Artwork read failure 不伪装成 404。

### 3.5 Idempotency / transaction

所有可重试 mutation 使用 `Idempotency-Key`。

同 method + canonical path + canonical payload + key：
- 首次执行业务；
- 成功后 replay 原 status/body，不重复 mutation；
- scope/payload 不同则 409 `IDEMPOTENCY_KEY_CONFLICT`；
- schema/service/player 失败且业务未提交时不保存 terminal success，允许 retry；
- 不使用进程内 dict/global mutable cache 作为唯一保证。

`business mutation + idempotency terminal record` 必须具有同一 SQLite unit-of-work 的原子边界。

任何同时修改 SQLite 权威状态与进程内会话状态的路径，还必须在外层事务失败时恢复进程内状态；不能仅依赖 SQLite rollback。C corrective 已为既有 History-changing playback paths 验证此保证（包括取消）。

### 3.6 Playback / Queue / History

- PlaybackService 是播放编排权威；
- API 不直接修改 Queue 或调用 PlayerPort；
- QueueManager/Repository 负责 Queue 业务与持久化，不成为第二个播放编排器；
- execution queue 不包含 Played；
- Queue、persistent History、Playlist/Favorites 相互独立；
- queue reorder/delete/clear 后，Repository/PlaybackService/PlayerPort 的可观察执行状态必须同步；
- 删除 current 必须基于可用 successor/AutoPlay/STOP 的实际结果更新 History；
- unavailable pending 的推进语义遵循 playback spec §8.3：跳过无效项并继续可用 successor；无可用项再进入 AutoPlay/终止语义；
- 任何 History transition 必须与最终成功事务一致，失败/retry 不得制造丢失或 phantom event。


### 3.7 Task 5 Cross-Authority Contract Matrix

本矩阵只索引 Task 5 已由 §3 frozen contracts、Playback/Library Specs 和当前 I1–I5 foundation 确立的跨权威语义；不新增业务规则，也不复制纯局部 Search/sort/schema 规则。架构依赖方向继续由 test_architecture_relationships.py 机械检查，不另造状态转换 row。

| Contract ID | Type / Operation | Authorities & Preconditions | Expected State Delta | Must Remain Unchanged | Confirmation / Failure / Retry | Executable Proof |
|---|---|---|---|---|---|---|
| **PB-STOP-001** | STATE_TRANSITION — Stop | PlaybackService / PlaybackState / PlayerPort / History；前态 PLAYING 或 PAUSED | PlayerPort 实际确认 STOPPED；PlaybackState→STOPPED；AutoPlay disabled；active History exactly-once 结束为 STOP | Queue membership/order；Playlist/Collection | 未确认或 transport/status failure 不得提交 STOPPED、History 或 terminal idempotency success；persisted + runtime state 回滚；retry 可重试，replay 不重复 transition | I2/I3/I4；test_stop_confirmation.py；test_transition_history_matches_confirmed_current |
| **PB-INSERT-001** | STATE_TRANSITION — Play Next / Add to Queue | active 或 stopped Queue；QueueRepository / PlaybackState / PlayerPort | 插入新的 execution occurrence 并同步 PlayerPort Queue | current song/occurrence、Playback state、History active/session、PlaybackContext 不因插入被改变 | 同步后必须确认实际 current/state 未漂移；divergence→reconciliation failure；事务失败无 terminal success，可 retry | I1/I2/I4；test_insertion_rejects_actual_playback_divergence_and_can_retry |
| **PB-REORDER-001** | STATE_TRANSITION — pending reorder | QueueRepository / PlayerPort；目标是 pending occurrence | authoritative execution order 与 PlayerPort order 同步；retained pending occurrence identity 保持 | current occurrence/state、History、PlaybackContext | revision conflict 在 player side effect 前失败；sync/current confirmation 失败则 rollback/retry | I1/I2；test_duplicate_execution_occurrences_survive_mutation；test_pending_duplicate_mutation_preserves_retained_occurrence_ids |
| **PB-DELETE-PENDING-001** | STATE_TRANSITION — delete pending | QueueRepository / PlayerPort；目标 position>0 | 精确删除目标 occurrence；必要时 AutoPlay refill；最终 execution Queue 与 PlayerPort 一致 | current occurrence/state、History active/session | Player unavailable/divergence/terminal failure 不得留下部分成功或 terminal record | I1/I2/I4；test_queue_mutations_sync_real_player_and_history；pending duplicate invariant cases |
| **PB-DELETE-CURRENT-001** | STATE_TRANSITION — delete current | current occurrence + PlaybackState + available successor/AutoPlay/STOP 分支 | 有可用 successor 时实际播放并确认 successor 后更新 state/history；无 successor 时遵循 AutoPlay 后 confirmed STOP；原态 STOPPED 时不得因删除而重新开始播放 | 不制造 unavailable current、phantom/lost History；Playlist/Favorites 独立 | successor/current occurrence 必须由 PlayerPort 确认；失败回滚 server/history；external player side effect 需 reconciliation 后 retry | I1/I2/I3/I4；test_delete_current_without_pending_uses_autoplay_or_confirmed_stop；test_current_delete_skips_unavailable_successor；test_current_deletion_after_explicit_stop_does_not_restart |
| **PB-NEXT-UNAVAILABLE-001** | STATE_TRANSITION — Next across unavailable pending | active playback；Library availability + Queue + PlayerPort + History | MISSING/UNREADABLE/absent pending 被跳过；第一个可用 successor 才成为 current；无可用项时尝试 AutoPlay/既定终止语义 | invalid item 不得成为 authoritative current；仅跳过 invalid 不产生虚假 active History | actual successor 必须确认；skip/sync failure 回滚；same-key retry 不丢失/重复 transition | I2/I3/I4；test_next_skips_unavailable_pending；test_next_skips_unavailable_later_pending；test_next_unavailable_exhaustion_attempts_autoplay |
| **PB-HISTORY-001** | STATE_TRANSITION — confirmed playback transition ↔ History | switch / skip / stop；PlaybackService + PlayerPort + History | 每次已确认的实际离开 current 只产生一次对应 History transition；新的 confirmed current 建立正确 active event | 未确认 transition、failed retry、idempotent replay 不得产生 lost/phantom/duplicate event | History finalize 必须晚于所需 PlayerPort confirmation，并与 owning transaction 一致 | I3/I4；test_transition_history_matches_confirmed_current；stop/transaction invariant suites |
| **TX-ROLLBACK-001** | TRANSACTION — business + runtime rollback | SQLite authoritative state + History active/session + idempotency terminal；可能已有外部 PlayerPort side effect | 成功时业务 mutation 与 terminal record 同一 unit-of-work；outer failure/cancel 时 persisted 与 runtime session 恢复 | rollback 后不得残留 terminal record、phantom History 或半提交 server state | SQLite 不能撤销外部 PlayerPort side effect；retry 前按既定 reconciliation 恢复外部状态关系 | I4；test_transaction_restores_persisted_and_session_state_and_retry |
| **TX-IDEMP-001** | TRANSACTION — retry/replay | method + canonical path + canonical payload + Idempotency-Key | 首次成功提交业务 + terminal result；同 scope replay 原 status/body | replay 不重复 Queue/History/Playlist mutation | scope/payload 不同→409；业务/player/schema failure 未提交时不保存 terminal success；retry 重新执行业务 | I4 + API idempotency regressions；test_transaction_relationships.py；server/tests/api/test_idempotency.py |
| **PL-REP-001** | REPRESENTATION — Playlist resource | persisted Playlist membership/order；Repository / Service / REST list/detail/mutation/songs | AVAILABLE/MISSING/UNREADABLE 均保持 resource membership/order；songs surface 暴露 availability | endpoint 不得各自过滤成不同成员集合；rename/reorder 等 mutation 不丢 unavailable member | mutation response 必须返回 mutation 后 authoritative resource；失败不得伪造成功 representation | I5；test_persisted_membership_matches_every_representation_and_collection_split |
| **PL-COLLECTION-001** | REPRESENTATION — Playlist → Collection | persisted Playlist resource + current song availability | 仅转换到 Collection 时：AVAILABLE→song_ids，unavailable→unavailable_song_ids，并保持来源顺序语义 | 转换不得修改 Playlist persisted membership/order，也不得用 playable filter 替代 resource semantics | empty/all-unavailable 仍是合法已知来源语义；不得伪造随机 playable item | I5；同一 playlist relationship invariant + Task 5 Collection focused regressions |

#### Batch 6 Contract Matrix ruling

Batch 6 不新增业务语义。其 Contract Matrix gate 为 **REQUIRED**，上述 Task 5 rows 全部作为 final acceptance regression obligations：

- 若 Batch 6 只做验收，New rows = none、Modified rows = none；
- Affected/relied-upon rows = PB-STOP-001、PB-INSERT-001、PB-REORDER-001、PB-DELETE-PENDING-001、PB-DELETE-CURRENT-001、PB-NEXT-UNAVAILABLE-001、PB-HISTORY-001、TX-ROLLBACK-001、TX-IDEMP-001、PL-REP-001、PL-COLLECTION-001；
- 必须执行完整 server/tests/invariants/，以及这些 rows 指向的 Task 5 focused/API regressions；
- 结束前逐 row 完成 Contract ID → authoritative Spec/frozen contract → implementation owner → executable proof → fresh GREEN evidence traceability review；
- 如果验收发现现有 row 与 Spec/实现不一致，按 contract/invariant gap 处理，不允许通过修改 Matrix 文案来迎合现有代码。


## 4. Batch map

| 阶段 | 原 Plan | 状态 | 长期输出 |
|---|---|---|---|
| Contract Audit | — | COMPLETE | 本文件 §3 contracts |
| Batch 1 | Step 1–5 部分 | COMPLETE | Collection + LibraryService |
| Batch 2 | Step 5 剩余 | COMPLETE | PlaylistService + repository contract |
| Batch 3 | Step 6 read | COMPLETE | REST read API |
| Batch 4 | Step 6 mutation/playback | COMPLETE | mutation/playback/history API |
| Batch 5 | Step 7–8 | COMPLETE | idempotency + error/schema |
| A/B corrective | pre-Batch-6 | COMPLETE | Queue mutation orchestration + persisted Playlist membership |
| C/D corrective | pre-Batch-6 | COMPLETE | History rollback + Next unavailable successor；证据见 archive/task-5/ |
| E corrective | pre-Batch-6 | CLOSED | Stop confirmation；relationship gate REQUIRED |
| Invariant foundation | Step 9 prerequisite | COMPLETE | I1–I5 reusable cross-module tests under `server/tests/invariants/` |
| Batch 6 | Step 9–10 | COMPLETE | final acceptance + full invariant gate + final Task 5 commit |

已完成 Batch 的逐步 RED/GREEN、commit、命令输出不再追加到本文件；需要追溯时读取 `archive/task-5/`。

## 5. Batch 6 Final Acceptance Gate

Batch 6 已执行并通过：Relationship / Contract Matrix、I1–I5、11 行 traceability、Task 5 focused、affected Task 2R/3/4 regression、full server tests、compileall、Ruff、architecture、diff review 与 future-task isolation。最新可复现证据仅在上述唯一 handoff 中记录，不向本文件追加执行日志。

Task 5 已完成，可进入 PR/main merge 审查；尚未创建 PR 或合并 main。以下冻结 Gate 继续作为后续触及 Task 5 合同时的 regression obligations。

E corrective 的 relationship gate 为 **REQUIRED**：Stop 的成功不能只由 History/SQLite 局部结果证明，必须通过关系测试证明 PlayerPort 最终确认 STOPPED 后才允许关闭 active History；失败/未确认时 History 与 authoritative playback state 不得伪装成功。

`server/tests/invariants/` 已机械化以下 Task 5 基础 invariant；Batch 6 必须重新执行该独立 Gate：

- **I1 Queue ↔ PlayerPort execution consistency**：authoritative execution Queue 与 PlayerPort 实际 Queue/occurrence/order 一致；Played 不进入 execution queue。
- **I2 PlaybackState/current ↔ PlayerPort current occurrence**：PLAYING/PAUSED/STOPPED 与实际 player status/current occurrence 相容，重复 Song/URI 不得只按 song_id 猜 identity。
- **I3 Playback transition ↔ History consistency**：成功 switch/skip/stop 每次只产生正确的一次 History transition；未确认的 player transition 不得提前 finalize History。
- **I4 Transaction rollback ↔ persisted + in-memory consistency**：outer idempotency/business transaction 失败或取消后，SQLite 权威状态及 History active/session 等进程内状态都恢复；retry 不得产生 lost/phantom transition。
- **I5 Playlist persisted membership ↔ REST representations / Collection split**：Playlist list/detail/mutation/songs endpoint 保持同一 persisted membership/order/availability；Collection 只在播放集合层做 playable/unavailable split。

这些不是五个孤立 endpoint regression，而是可复用关系断言。现有真实 SQLite/API fixture 已提取到 `server/tests/support/playback.py`；共享 execution/current 与 persisted/session assertions 位于 `server/tests/invariants/assertions.py`。当前执行结果和测试映射见唯一 corrective handoff。

所有 blocker 关闭后，Batch 6 **禁止新增功能**，只做：
- Task 5 focused/service/API aggregate；
- affected Task 2R/3/4 regression；
- full `server/tests`；
- full `server/tests/invariants` relationship gate；
- compileall；
- Ruff；
- `git diff --check`；
- changed-files review；
- architecture boundary review；
- contract/invariant matrix re-check；
- future Task isolation。

必须再次确认：
- API → Service → Repository/PlayerPort；
- Collection 与 Playlist resource 语义不混淆；
- Queue/PlayerPort/History 在所有 mutation/transition 后一致；
- History 与 idempotency transaction failure/retry 一致；
- unavailable successor semantics 一致；
- artwork 只读；
- 无未来 Task 实现。

只有这些证据成立，才能完成原 Step 9，并进入 Step 10 的 Task 5 final commit。Task 5 final commit、创建 PR、合并 main 仍是独立状态。

## 6. 验证与记录规则

每次 corrective/Batch：
- 先按主 Plan Relationship-Test Matrix 将 relationship gate 标为 REQUIRED 或 N/A，并记录原因；
- REQUIRED 时先命名本 Batch 触及的 invariant，focused GREEN 后运行对应 `server/tests/invariants` 测试；
- focused tests + 直接受影响 regression；
- 必要时 full server regression；
- compileall / Ruff / diff check；
- changed-files + architecture review；
- 只记录真实执行结果。

新的真实 defect 必须分类为：
- code gap；
- test gap；
- contract/invariant gap；
- architecture guard gap。

若属于后三类，不能只改 production code 后关闭 finding；必须留下对应的可执行保护或唯一权威合同。跨模块 finding 必须进入 relationship/invariant regression；若暴露的是通用状态关系，优先留下可复用 assertion/property/state-machine test，而不是只写单一 endpoint regression。

历史完整计划：
`docs/superpowers/archive/task-5/2026-09-29-mpd-server-task-5-batch-plan-full-history.md`。
