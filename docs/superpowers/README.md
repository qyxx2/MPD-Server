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

## 当前 Task 5 最小读取集

实施 Task 5 或其 corrective 时，只需默认读取：

- 与本次范围直接相关的 `specs/`；
- 主 Implementation Plan 的 Task 5、依赖矩阵和必要的全局约束；
- `plans/2026-09-29-mpd-server-task-5-batch-plan.md`；
- `plans/2026-10-01-task-5-contract-architecture-corrective-acceptance.md`；
- 本次将修改的实际代码与测试。

只有需要追溯某项历史决定、旧测试证据或旧 commit 时，才读取 `archive/`。

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
