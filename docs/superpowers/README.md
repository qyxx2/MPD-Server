# MPD-Server 现行文档入口

现行目录保留规格书、重要入口与部署说明；全部实施计划、阶段验收和旧路线图已归档。2026-10-18 用户确认剩余计划不再推进，后续只按明确的新需求立项。

## 规格书

- [系统与开发架构](specs/2026-09-25-system-and-development-architecture-design.md)：API、SQLite、WebSocket、播放状态与事务。
- [播放/Queue/History 语义](specs/2026-09-24-playback-model-queue-semantics-design.md)：队列 occurrence、恢复、安全与 AutoPlay。
- [音频与输出架构](specs/2026-09-24-system-architecture-playback-output-design.md)：MPD→ALSA→USB DAC。
- [Library、Playlist、Search 规格](specs/2026-09-24-library-playlist-tag-search-design-2-1.md)：曲库只读、数据与可用性语义。
- [Web UI 视觉合同](specs/2026-10-03-web-pwa-visual-design.md)：页面视觉、通知与导航。
- [横屏常驻播放器与右侧工作区](specs/2026-10-16-responsive-landscape-player-design.md)：iPad/横屏布局、尺寸算法与共享状态合同；文中的阶段进度只作历史注记，不构成新计划。

## 部署与重要入口

- [根 README](../../README.md)：功能、版本状态、开发验证与快速部署。
- [NAS / Docker 部署说明](../../deploy/README.md)：镜像选择、持久化、环境变量和部署后检查。
- [播放性能现状](../performance/README.md)：已实现机制及历史实测限制。
- [MPD 能力实测记录](../mpd-0.23.5-capabilities.md)及[探针 JSON](../mpd-0.23.5-probe-2026-09-26-091948.json)：历史设备参考，不能代替当前 MPD 能力确认。
- [历史归档](archive/README.md)：全部实施计划、验收、研究与退役路线图。原文中的 NOT STARTED、BLOCKED、PARTIAL、PENDING 只保留历史事实，不代表当前待办，也不因归档改记为通过。

**权威次序：当前检出的代码/测试与实际镜像 → 与实现一致的现行规格 → 明确授权的新需求 → 历史归档。**
