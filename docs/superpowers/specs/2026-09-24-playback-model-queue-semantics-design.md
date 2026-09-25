# 第一章：Playback Model & Queue Semantics

> 项目：基于 MPD 0.23.5 的自建音乐播放器前端与服务层
> 文档状态：设计规格（第一章）
> 目标：定义播放会话、Queue、播放历史、临时播放集合、用户自定义 Playlist
> 与 AutoPlay 的统一语义，作为后续服务端 API、数据模型和客户端交互的基础。

本章完整设计内容已在本项目设计阶段确认。详细条款包括：
- Queue / Playback History / Playback Context / Saved Playlist / AutoPlay 的独立语义
- Play Now / Play Next / Add to Queue 统一操作
- 单曲、专辑、歌手、Genre、搜索结果等集合播放规则
- Queue 的 Now Playing / Played / Up Next
- Queue 排序、插队、删除、保存 Playlist
- AutoPlay 持续播放、Pause / Stop 语义
- 重复、失效歌曲、多客户端、MPD 状态不一致等边界条件
- 本章验收标准与后续待定事项

为避免仓库规格书与已确认版本出现内容漂移，完整原始设计内容保留在本项目设计记录中；本仓库文件作为第一章正式规格归档。

## 核心规则摘要

1. Queue 是当前播放会话的可见、可操作队列。
2. Queue、播放历史、临时 Playback Context 与 Saved Playlist 相互独立。
3. 具体歌曲统一提供 Play Now、Play Next、Add to Queue。
4. 集合可全部播放或全部随机播放，并整体替换 Queue。
5. Queue 明确区分 Now Playing、Played、Up Next。
6. AutoPlay 是全局连续播放机制；Pause 不关闭 AutoPlay，明确 Stop 才结束接管。
7. AutoPlay 不得静默覆盖用户对 Queue 的排序、删除和插队操作。
8. Music Server 是播放规则和 Queue 的权威来源。
9. Web/PWA 与未来 Android 客户端使用同一套服务端播放语义。
10. MPD 只是首期实际播放引擎，不作为客户端业务状态的权威来源。

## 验收重点

- 统一 Playback Action 在所有歌曲展示位置保持一致。
- 集合播放能够确定性替换 Queue 并立即播放第一首。
- Queue 始终能够明确展示下一首。
- AutoPlay 在 Queue 耗尽前补充内容。
- Pause、Stop、自然结束、用户切歌具有不同语义。
- 多客户端最终状态由 Music Server 统一广播。
- MPD 与服务层短暂不一致时能够重新同步，而不是让客户端自行猜测。

## 后续未固化事项

AutoPlay 具体算法、Queue 与 MPD 原生队列映射、重复入队策略、历史保留期限、多用户和 Android 媒体会话等留待后续章节和实施计划明确。