# Superpowers 文档地图

本目录的目标是让实现窗口读取**最小、权威、当前**的上下文，而不是把所有历史记录重新塞入模型。

## 事实来源

按职责使用文档，不把多个文件当作同一事实的并列副本：

1. `specs/`：产品行为、领域语义、架构边界。长期合同的权威来源。
2. `plans/2026-09-25-mpd-server-v0-1-implementation-plan.md`：Task 依赖、Task scope、全局执行顺序和原始 Step。
3. 当前 Task 的 active plan：只记录当前 Task 的冻结合同、Batch 边界和验收 Gate。
4. 当前 corrective/acceptance handoff：只记录尚未关闭的 blocker 与最新可复现证据。
5. Git、实际代码和测试：验证实现/状态是否真的存在。历史文档中的“已完成”不能替代实际核对。

发生冲突时，不通过增加另一份解释文档解决；回到 spec、主 Plan、实际代码/测试定位冲突，并在必要时修正唯一权威来源。

## 当前 Task 8 最小读取集

Task 0–7、D6及Task6后端功能验收已完成；D6最终逐合同证明位于 `archive/task-4/2026-10-04-task-4-d6-recovery-acceptance.md`，Task6 Batch13状态位于 `archive/task-6/2026-10-04-task-6-batch-13-acceptance.md`。原本地DB保留未验证审计事件单独保留，不宣称已恢复。

开始 Task 8 时默认读取：

- `specs/2026-09-25-system-and-development-architecture-design.md` §4.1–4.3 与 §12：Task 8/9 共用的 Web authority/cache/reconnect/mutation/idempotency/PWA 合同；
- 与 Player/Library/Output 范围直接相关的其它 `specs/`，包括 Web/PWA visual design；
- 主 Implementation Plan 的 Task 8、依赖矩阵和全局约束；
- Task 6 plan 中仍约束客户端消费的快照、重连、actual/binding合同；
- [手机 Web 真人验收方法](plans/2026-10-09-mobile-web-manual-acceptance.md)：手机/LAN 交付、最小场景准备、反馈复验及报告模板；必验编号归 active Batch Plan，不新建验收平台；
- 本次将修改的实际代码与测试。

2026-10-09 的 Common Web preflight 只冻结共同前置语义：断线时 degraded read-only，重新接受完整 initial snapshot 后才恢复 mutation；v0.1 PWA 可安装但无离线业务模式；共享 resource cache 受 epoch/sequence/revision/请求代次保护；mutation 统一复用既有 Idempotency-Key 合同。**它没有创建 Task 8/9 Batch Plan，也没有完成任何 Task 8 Step。**

Task 8 的 Contract Audit / 执行计划应在开始该 Task 时另行制定，只为仍未冻结的 Task-8-specific 行为建立 Contract rows。Task 9 后续继承共同 Web 合同，只审计其 Queue/Library/Playlist/Favorites/Search/navigation 增量。只有需要追溯历史决定或测试证据时，才读取相应 `archive/`。

2026-10-09 用户优先级调整：手机浏览器为主要交付/触摸验收环境，Ubuntu Firefox/Chromium 仅辅助；PWA 安装/SW/冷离线壳延期，不阻塞 Task 8 手机 Web acceptance 或 Task 9，不声明延期部分完成。详见 Architecture §4.3 和 active Batch Plan。

当前入口：[Task 8 Web Batch Plan](plans/2026-10-09-task-8-web-batch-plan.md) 与 [后端控制前置计划](plans/2026-10-09-task-8-playback-control-prerequisite-plan.md)（计划待审阅，未实施）。[Contract Audit](plans/2026-10-09-task-8-contract-audit.md) 保留已接受决策与专项 rows/证明索引；公共接口已归入 Architecture §4.2.1，Task 8 尚未验收。Task 9 song Play Now 原子入口仍需其后续审计。

## Relationship / Invariant Test Gate

主 Implementation Plan 的 `Cross-Module Relationship / Invariant Test Gate` 是所有当前和未来 Task/Batch 的强制验收规则。

- 每个 Task、Batch、corrective 都要明确标记 `REQUIRED` 或 `N/A + 原因`。
- 只要触及跨模块接口、状态同步、事务、表示一致性、事件顺序或 retry/idempotency，关系测试就是 REQUIRED。
- Backend 新的可复用关系测试默认进入 `server/tests/invariants/`；完整 full-suite 不能替代显式 invariant gate。
- 已完成并归档的 Task 不因新增规则自动重开；但后续工作一旦触及其合同，就必须运行矩阵中对应的历史 invariant regression。
- 真实跨模块 defect 修复后必须留下机械保护，不能只在 acceptance 文档里描述“已审计”。

## plans/ 的内容规则

`plans/` 只保存仍会影响下一次实现决策的文件。

Active plan 应包含：
- dependency/scope；
- 已冻结 contract/invariant；
- Batch boundary；
- acceptance gate；
- 当前 blocker 的引用。

Active plan 不应累积：
- 每个 Batch 的完整命令输出；
- 重复 Git 操作流程；
- 新窗口提示词模板；
- 已关闭 finding 的长篇执行日志；
- 已完成阶段的逐 commit 叙述。

完成阶段的这些证据移入 `archive/`。

## archive/ 的语义

`archive/` 是审计证据，不是默认实施指令。

它保留：
- 已完成 Batch acceptance；
- corrective plan / acceptance；
- 历史 integration gate；
- active plan 压缩前的完整历史副本。

归档不改变当时记录，也不表示其结论自动适用于当前 HEAD。需要引用历史证据时，必须同时核对当前代码和测试。

## 文档更新纪律

- 新产品/架构语义：更新 spec。
- Task scope/dependency：更新主 Implementation Plan。
- 当前 Batch 的冻结合同/Gate：更新 active task plan。
- 临时 corrective blocker：使用一个当前 handoff；关闭后归档，不继续向 active plan 追加历史日志。
- 测试结果只记录能改变验收状态的摘要；完整命令/旧结果进入 acceptance/archive。
- README 只维护项目入口和高层状态，不保存每个 Batch 的测试数字与提交历史。

目标不是让文档更少，而是让每条规则只有一个清晰的长期归属。
