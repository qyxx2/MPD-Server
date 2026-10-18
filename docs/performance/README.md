# v0.2 播放性能现状

2026-10-18 按当前分支源码、Git 历史及阶段记录整理。全部性能方案和验收已按用户要求[归档](../superpowers/archive/v0.2-performance/README.md)，不再作为待执行计划；本页保留实现概况和重要限制。

| 范围 | 当前实现 |
|---|---|
| B1–B4 | Played occurrence 映射交接、Song 批量读取、提交后通知、完整 preflight 样本复用 |
| B6-A / B7 / B6-B / B5 | 提交唤醒、后台稳定检查锁外采样、最终确认观察交接、连接 epoch 保护的 ID 播放 |
| B8 | 连接级歌曲标签过滤及失败回退；完整队列身份和核验次数保留 |

历史 NAS 实测表明适用路径的读取和长队列采样成本下降，但存在短队列波动。[B8 原验收](../superpowers/archive/v0.2-performance/2026-10-16-v0.2-batch-8-full-sample-acceptance.md)记录短队列端到端无明显退化 NOT PASSED、整体 PARTIAL；归档不改写该结果，也不宣称全部延迟已解决。

历史实验多为共享 NAS 上每条件 n=3 的对照，并存在数据库历史量、宿主负载等差异；按各卡限制解释结果，不能归纳为稳定 P95。自动化、CI、镜像交付和真人/DAC/PWA 验收分别判断；后续只按明确的新需求立项。

[现行文档索引](../superpowers/README.md) · [历史归档](../superpowers/archive/README.md) · [部署说明](../../deploy/README.md)
