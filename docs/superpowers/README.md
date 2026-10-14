# MPD-Server v0.2 现行文档入口

**开发模式：在现有已可用产品上按需求渐进迭代。** 原 Task 主 Plan 与分 Batch 计划已退役；其 Task 10–12 及后续里程碑**不再是待执行路线图**。

## 必须优先参考

- [播放/Queue 性能优化指导](../performance/2026-10-14-v0.2-playback-latency-optimization-guide.md)：本次优化的实际数据、批次边界、TDD 与 NAS 验收；尚未实施。
- [系统与开发架构](specs/2026-09-25-system-and-development-architecture-design.md)：API、SQLite、WebSocket、播放状态与事务。
- [播放/Queue/History 语义](specs/2026-09-24-playback-model-queue-semantics-design.md)：队列 occurrence、恢复、安全与 AutoPlay。
- [音频与输出架构](specs/2026-09-24-system-architecture-playback-output-design.md)：MPD→ALSA→USB DAC；未来客户端串流只作历史设计候选。
- [Library、Playlist、Search 规格](specs/2026-09-24-library-playlist-tag-search-design-2-1.md)：曲库只读、数据与可用性语义。
- [Web UI 视觉合同](specs/2026-10-03-web-pwa-visual-design.md)：页面视觉/通知/导航合同。
- [MPD 能力实测记录](../mpd-0.23.5-capabilities.md)及[探针 JSON](../mpd-0.23.5-probe-2026-09-26-091948.json)：历史设备证据，不能代替当前 MPD 能力确认。
- [部署说明](../../deploy/README.md)和[根 README](../../README.md)。

## 历史资料

[归档入口](archive/README.md)存放原始 Task 计划、验收、研究、测试证据、专项过期设计与部署交接；历史文档中写的 `NOT STARTED`、`BLOCKED`、Future Task 等**不代表现在的状态**。长期规格里亦保留一些当时的实施状态注记：仅行为/安全合同中与现有实现一致的部分有效，具体实现与测试仍以真实仓库为准。

**权威次序：真实 v0.2 代码/测试与实际镜像 → 当前有效架构/领域规格 → 明确授权的新迭代方案 → 历史归档。**
