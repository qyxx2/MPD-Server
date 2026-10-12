# Superpowers 文档地图

本目录的目标是让实现窗口读取**最小、权威、当前**的上下文，而不是把所有历史记录重新塞入模型。

## 事实来源

按职责使用文档，不把多个文件当作同一事实的并列副本：

1. `specs/`：产品行为、领域语义、架构边界。长期合同的权威来源。
2. `plans/2026-09-25-mpd-server-v0-1-implementation-plan.md`：Task 依赖、Task scope、全局执行顺序和原始 Step。
3. 当前 Task 的 active plan：只记录当前 Task 的冻结合同、Batch 边界和验收 Gate。Web视觉、通知位置、背景、比例和四项导航长期规则唯一归 [全局 UI 合同](specs/2026-10-03-web-pwa-visual-design.md) WEB-UI-*；计划只引用与分配证明，不复制规则。
4. 当前 corrective/acceptance handoff：只记录尚未关闭的 blocker 与最新可复现证据。
5. Git、实际代码和测试：验证实现/状态是否真的存在。历史文档中的“已完成”不能替代实际核对。

发生冲突时，不通过增加另一份解释文档解决；回到 spec、主 Plan、实际代码/测试定位冲突，并在必要时修正唯一权威来源。

## v0.1 最终最小交付入口（2026-10-11）

开始配置、URI映射、曲库同步、AppBar活动、基本健康日志或NAS部署时，先读[Final Batch Plan](plans/2026-10-11-v0-1-nas-final-batch-plan.md)，再按Batch读取Architecture §22、Library §7.2和Visual §6。主Plan只保留范围映射；长期语义不复制到执行计划。

2026-10-11用户仅授权执行B00，现为CLOSED / BASELINE PASSED；指定后端36项、Web36项fresh通过，基线/合同/安全装配证据见Final Batch Plan B00。B00C及B01–B09 NOT STARTED，未改产品或执行Docker/实机/手机验收。核心目标是实际Docker部署和真实MPD功能；备份恢复、update.sh、重启API、PWA延期。AppBar完善独立B04，同步wire独立B05。旧Task9 B10剩余Gate保留，重叠实机项可引用B08同一次真实证据，不能自动关闭。历史计划/验收中的成功通知撤下方案属于旧轮次，后续活动展示按Visual本次增量。

## 当前 Task 8 最小读取集

Task 0–7、D6及Task6后端功能验收已完成；D6最终逐合同证明位于 `archive/task-4/2026-10-04-task-4-d6-recovery-acceptance.md`，Task6 Batch13状态位于 `archive/task-6/2026-10-04-task-6-batch-13-acceptance.md`。原本地DB保留未验证审计事件单独保留，不宣称已恢复。

开始 Task 8 时默认读取：

- `specs/2026-09-25-system-and-development-architecture-design.md` §4.1–4.3 与 §12：Task 8/9 共用的 Web authority/cache/reconnect/mutation/idempotency/PWA 合同；
- [全局 UI 合同](specs/2026-10-03-web-pwa-visual-design.md)：先读当前Player保护基线与WEB-UI-*；再读与Player/Library/Output范围直接相关的领域Specs；
- 主 Implementation Plan 的 Task 8、依赖矩阵和全局约束；
- Task 6 plan 中仍约束客户端消费的快照、重连、actual/binding合同；
- [手机 Web 真人验收方法](plans/2026-10-09-mobile-web-manual-acceptance.md)：手机/LAN 交付、最小场景准备、反馈复验及报告模板；必验编号归 active Batch Plan，不新建验收平台；
- 本次将修改的实际代码与测试。

2026-10-09 的 Common Web preflight 只冻结共同前置语义：断线时 degraded read-only，重新接受完整 initial snapshot 后才恢复 mutation；v0.1 PWA 可安装但无离线业务模式；共享 resource cache 受 epoch/sequence/revision/请求代次保护；mutation 统一复用既有 Idempotency-Key 合同。**它没有创建 Task 8/9 Batch Plan，也没有完成任何 Task 8 Step。**

Task 8 的 Contract Audit / 执行计划应在开始该 Task 时另行制定，只为仍未冻结的 Task-8-specific 行为建立 Contract rows。Task 9 后续继承共同 Web 合同，只审计其 Queue/Library/Playlist/Favorites/Search/navigation 增量。只有需要追溯历史决定或测试证据时，才读取相应 `archive/`。

2026-10-09 用户优先级调整：手机浏览器为主要交付/触摸验收环境，Ubuntu Firefox/Chromium 仅辅助；PWA 安装/SW/冷离线壳延期，不阻塞 Task 8 手机 Web acceptance 或 Task 9，不声明延期部分完成。详见 Architecture §4.3 和 active Batch Plan。

Task 8入口：[Task 8 Web Batch Plan](plans/2026-10-09-task-8-web-batch-plan.md) 与 [W6 acceptance](archive/task-8/2026-10-10-task-8-web-w6-acceptance.md) 最新关闭记录。W1–W6 手机 Web 范围已实现，必要自动与真人 Gate 通过，满足当前 Task 9 前置；A04 歌词保护基线保持。PWA 仍延期，真实 MPD/NAS/DAC NOT RUN，不宣称原始 Task 8 整体验收完成。[Contract Audit](plans/2026-10-09-task-8-contract-audit.md)保留决策/证明索引；公共接口归Architecture §4.2.1，后端前置证据归archive/task-8，不据旧计划措辞判断未实施。Task9继承全局UI合同§8；共享基础及song Play Now原子入口已分别由B01/B02完成，当前Task9状态以下方入口为准。

## 当前 Task 9 最小读取集

Task 9 审计基线为 main `14c6239`；当前feature/task-9-web中B01–B09已实现并获必要验收，**CLOSED / HUMAN PASSED**，B06 Search（A04）已获用户手机验收，CLOSED / HUMAN PASSED；B07 Playlist已获用户验收，CLOSED / HUMAN PASSED；B08 Favorites/爱心及A02展示整改已获用户验收，CLOSED / HUMAN PASSED；B09 Settings、MPD接入配置及A02布局整改已获用户验收，CLOSED / HUMAN PASSED；B10自动/关系及production/LAN预检完成，手机综合PENDING、新实机功能Gate BLOCKED/NOT RUN。先读[Contract Audit](plans/2026-10-10-task-9-contract-audit.md)与[Web Batch Plan](plans/2026-10-10-task-9-web-batch-plan.md)，再读全局 UI 合同、Architecture §4.1–4.3/§12/§19.5及本 Batch 所属领域 Spec、主 Plan Task9、实际代码/测试。B01共享基础已交付；B02普通song Play Now生命周期PB-SONG-NOW-001已冻结并实现。最新关闭依据见[B09 acceptance最终关闭记录](archive/task-9/2026-10-11-task-9-b09-acceptance.md)。后端精确接口证据见[研究输入](plans/2026-10-10-task-9-backend-research.md)，不把研究报告当作并列规格或验收。

Task8最新关闭记录只证明修订手机Web前置及保护基线；不抵扣Task9新共享UI或页面验收。各Batch Contract/Relationship REQUIRED，必要手机Gate通过才关闭；PWA延期、真实MPD/NAS/DAC尚未运行分别报告。

当前B10证据与未关闭Gate：[Task9 final acceptance](archive/task-9/2026-10-11-task-9-final-acceptance.md)。真实地址请填写本轮LIVE Adapter页面（5188），旧Mock页面保存地址不会连接实机。

## 2026-10-12 播放执行重构（仅合同冻结）

新工作分支 `refactor/mpd-bounded-execution` 基于 Task9 的 `098d6eaea81495d1686a09f9e0ee68768610ed7e` 创建；用户选择 MS 唯一业务Queue + MPD当前/下一首有界执行缓冲。**唯一长期领域合同是 [Playback Spec §8.10](specs/2026-09-24-playback-model-queue-semantics-design.md)，工作分批、迁移影响、Contract Matrix及真人Gate在 [Refactor Plan](plans/2026-10-12-mpd-bounded-execution-refactor-plan.md)**。Task4 §8.9旧完整同步与Task9/NAS旧验收作为历史证据保留，但未来执行路径不再照旧实施；本次未改代码、未做测试、未进行实际MPD播放、未合并或替换NAS部署。后续只能按用户单独指定Batch执行，不默认从B1开始。

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
