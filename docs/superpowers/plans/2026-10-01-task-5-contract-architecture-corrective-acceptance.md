# Task 5 Current Pre-Batch-6 Corrective Handoff

Date: 2026-10-01  
Branch: `feature/task-5-library-api`

本文件只保存**当前未关闭 Gate**。完整的 A/B corrective、独立审计过程、逐命令输出和旧 handoff 已归档：
`docs/superpowers/archive/task-5/2026-10-01-task-5-contract-architecture-corrective-acceptance-full-history.md`。

## Current ruling

- Batch 1–5：COMPLETE。
- A — Queue reorder/delete/clear 未同步 PlayerPort/History：**CLOSED**。
- B — Playlist resource 在 list/mutation/detail 之间成员 visibility 不一致：**CLOSED**。
- C — playback History 内存状态在外层 idempotency transaction 失败后不恢复：**OPEN / BLOCKING**。
- D — Next 遇到 unavailable pending 时中止，而不是继续下一个可用项：**OPEN / BLOCKING**。
- Batch 6 / 原 Task 5 Step 9–10：**BLOCKED**。
- 不得据 A/B 已关闭推断整个 Task 5 已通过。

A/B 生产修复的最近代码提交为
`fe043af388f391abb967a262b4aea909eb6a800d`
(`fix(task-5): close queue orchestration and playlist membership blockers`)。
后续纯文档整理不改变这一代码状态。

## Closed invariant A — Queue mutation orchestration

当前实现已把 queue reorder/delete/clear 编排收回 PlaybackService，并验证：
- Queue business state 与 PlayerPort execution queue 同步；
- Played 不进入 execution queue；
- current deletion 根据实际 successor/AutoPlay/STOP 结果更新 state/History；
- stale revision 在 PlayerPort side effect 前失败；
- Player failure / reconciliation failure 不伪装为成功；
- Playlist/Queue/History 边界保持独立。

这些结论不覆盖 blocker C/D。

## Closed invariant B — Playlist persisted membership

Playlist resource 现在按 persisted order 暴露所有成员：
- AVAILABLE；
- MISSING；
- UNREADABLE。

list/detail/mutation/`GET /playlists/{id}/songs` 使用同一 membership policy。
Playlist 转 Collection 时再进行 playable/unavailable split。

## Blocker C — History memory vs transaction rollback

### 现状

既有 `PlaybackService.start_track`、`play_now`、`next` 等路径会在 API 外层 idempotency transaction 内调用 `HistoryService.start_track()`。
该调用会修改进程内 `_active` / session state。

如果业务 mutation 已执行、随后 idempotency terminal record 写入失败：
- SQLite transaction rollback；
- 进程内 History state 不自动 rollback；
- retry 可能丢失真实旧 transition，并记录 phantom transition。

A/B corrective 只给新 delete 路径增加了 checkpoint/rollback，不能覆盖其它既有 playback transition。

### Minimum corrective scope

对所有会改变 History active/session 的既有 playback path 建立统一 transaction-failure restore 语义，至少覆盖：
- start_track；
- queue-item play / play_now；
- next；
- 以及检查后确认会改变同一 state 的 previous/stop/context/reconciliation path。

必须使用真实 SQLite outer-transaction failure（例如 terminal-record trigger）验证：
1. failed request 后 SQLite 权威状态回滚；
2. History in-memory active/session 也恢复；
3. 同一 key retry 只产生正确的一次最终 History；
4. 不把 SQLite rollback 错误解释成 MPD external side-effect rollback。

## Blocker D — Next unavailable successor

### 现状

当前 `PlaybackService.next()` 直接选择第一个 pending 并执行 availability check。
当第一个 pending 为 MISSING/UNREADABLE、后面仍有 AVAILABLE 项时，请求中止，未继续有效 successor。

这违反 playback spec §8.3 的“跳过无效项并继续；无可用项再进入 AutoPlay/终止语义”。

### Minimum corrective scope

Next successor resolution 必须验证：
- MISSING / UNREADABLE pending 被跳过；
- 找到后续 AVAILABLE 时继续并确认实际 transition；
- 所有 pending 均 unavailable 时进入既有 AutoPlay/terminal 规则；
- Queue/History/PlayerPort 最终一致；
- revision、player failure、idempotency failure/retry 不破坏上述语义；
- unavailable reason 保持可观察，不通过删除持久化成员来“解决”。

## Required next execution

下一阶段是一个独立的 C/D corrective，不是 Batch 6。

顺序：
1. 根据上述两个 blocker 写 RED；
2. 做最小 production fix；
3. focused GREEN；
4. affected Task 4/5 regression；
5. full server regression + compileall + Ruff + diff check；
6. 重新按 active Task 5 Plan 的合同/架构 Gate 审查；
7. 只有 C/D 均关闭且没有新的 blocking contract violation，才允许进入 Batch 6。

最近一次 A/B corrective 的完整验证证据（代码提交前）包含：
- focused/affected aggregate：198 passed；
- full `server/tests`：386 passed；
- compileall：exit 0；
- Ruff：All checks passed；
- diff check：exit 0。

这些是历史证据，不替代 C/D corrective 后的新鲜验证。
