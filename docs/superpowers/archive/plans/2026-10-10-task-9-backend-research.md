# Task 9 后端研究证据（2026-10-10）

本报告是 Task 9 Contract Audit 的只读后端输入，不是业务规格修订或实现完成证明。基线为本地 `main` / `14c6239`（`feat: deliver Task 8 mobile web player and acceptance`）；研究开始时 `git status --short` 为空。没有拉取远端，不能据此断言远端 main 同步。仅新增本文，没有修改生产代码、依赖或执行 MPD/网络操作。本研究未运行测试，下面的测试是**存在性和可复用证明入口**，不是本轮 PASS。

## 1. 结论及拆分约束

主计划明确允许先实施共享壳/导航/通知/背景，此阶段不依赖普通 song Play Now；依赖该播放动作的内容必须等待原子入口。依据：[主计划](2026-09-25-mpd-server-v0-1-implementation-plan.md) 第 1002–1017 行。

后端已有 Queue、集合、Playlist/Favorites、Search、Output/MPD About API，Task 9 主要应消费这些服务端权威。真实缺口是普通歌曲 Play Now：现有 `/tracks/{song_id}/play` 会替换 Queue，现有 `/queue/items/{queue_item_id}/play` 只选既有 occurrence，均不能实现已经接受的“新建 occurrence、保留原 pending、Stop 后重新开启会话/AutoPlay”。证据：`server/app/api/playback.py:188`、`:210`；`server/app/services/playback_service.py:434`、`:493`；[Playback Spec](../../specs/2026-09-24-playback-model-queue-semantics-design.md) 第 141–145 行。

建议 Batch 依赖关系为：共享 UI 基础先行 → 单独的后端 song Play Now prerequisite → 复用统一 SongRow 的各域 UI。后端 prerequisite 应包含服务/仓储/HTTP/幂等/确认及实时联合 delta 证明，不能只增加 endpoint 后交给前端串 `queue → play`。

## 2. 普通 song Play Now 的缺口和待冻结内容

| 真实代码/合同 | Task 9 含义 |
|---|---|
| `playback_service.py:441` 调用 `queue_manager.start_track`，随后建立 Context、开启 History、AutoPlay refill | Start Track 是明确替换上下文入口，不能冒充普通 Play Now |
| `playback_service.py:495` 只接受 `queue_item_id`；`:511` 采用所选行 Context 或当前 Context；`:520` 保留原 `autoplay_enabled` | Queue 行语义应保持；尤其不能直接借它实现 Stop 后普通 Play Now 的 AutoPlay 重启 |
| `queue_repository.py:310` 操作既有行；`:330` current 行直接返回，pending 中排除 selected 行 | Queue 行 Play Now 是 identity 精确操作，普通歌曲要创建新的 ID，不能按 song_id 找现有行 |
| `playback_service.py:534`、`:543` 分别提供 song Play Next/Add to Queue | 这两项已有原子 service 包装；不能在 Web 组合它们模拟 Play Now |
| `playback_service.py:118` 使用现有 DB 外层事务；`:172` 捕获完整 current delta；`:343` 认证/丢弃不可信旧 active；`:128` 有显式 current 操作名称枚举 | 新方法需审计这些扩展钩子，尤其 current token/binding/recovery 身份生命周期，不能只复制函数主体 |
| `main.py:179` 统一 mutation 幂等入口；`test_idempotency.py:19`/`:64` 有业务与 terminal record 同事务证明 | 新入口复用已有 middleware、同意图 key 与稳定 replay；不另造页级重试机制 |

已经接受、无需再问的产品点：每次普通 Play Now 新 occurrence、保留所有 pending ID/相对顺序和同 song 重复项；明确 Stop 后建立新会话并打开 AutoPlay；传输 retry 复用 Idempotency-Key。[Playback Spec](../../specs/2026-09-24-playback-model-queue-semantics-design.md) 第 143–145 行。

**仍需 audit 冻结，不能从现有方法猜测：**

1. 正在播放时普通 Play Now 是否保留当前 Playback Context；Stop 后是否建立单曲 Context，既有 pending 的 Context ID 是否保持，以及 AutoPlay 候选属于哪一个 Context。Spec 把完整 Context 生命周期留给专项审计（第 145 行）。本研究原建议作为可评审选项；本轮用户随后选择“采用建议，写入待审核方案”，最新准确方案统一见主[Contract Audit §4 G9-01](2026-10-10-task-9-contract-audit.md)，不能标记为已冻结后端合同。
2. History 生命周期应明确**继承既有规则**而非新增用户选择：运行中的确认切换沿用既有 session，明确 Stop 后新 session；未知外部切歌丢弃不可信 active 但保留 session（Playback Spec 第 402 行）。`history_service.py:69`–`:94` 仅在 session 为空时生成新 UUID，`:128`/`:146` 负责 finish active，Stop reason 清 session（`:166`）。新入口仍须冻结确认、提交及 replay 时点的技术合同，不为旧 active 补造原因。
3. 旧 Played 是否随新 Context/新 session清理，以及 Queue Played 折叠复位应以 Context、session 还是新入口结果为 key。这与普通 Play Now 不替换 pending 的新行为直接相关，不能借 Start Track 的清队列行为暗中决定。
4. 原子 endpoint 路径、请求/响应形状、404/409/502/503 映射与确认失败规则属于技术合同，audit 可以提出明确方案；不把尚未存在的接口写成现有能力。HTTP replay、无副作用失败、MPD 已发生但最终确认未知、rollback 后 token/binding 不复活都应有专门证明。

## 3. 可复用接口及 UI 容易误用之处

| 域 | main 真实入口 | 约束与代码证据 |
|---|---|---|
| Queue read/当前行 Play Now | GET `/api/playback/queue`；POST `/api/playback/queue/items/{id}/play` | REST list 无 revision（`schemas.py:235`）；实时 canonical queue 才拥有共同 authority。position `<0 / =0 / >0` 区分 Played/current/pending。QueueItem 携带 occurrence ID/source/context（`schemas.py:227`） |
| Queue reorder | PUT `/api/playback/queue/items/{id}`，body `{before_queue_item_id}` | `api/playback.py:347`；HTTP 不接受 expected_revision（`schemas.py:268`），虽然 service/repository 支持 CAS。不能声称 UI 已有 stale revision rejection 合同，也不能传未定义字段 |
| Queue delete/clear | DELETE 指定行 / DELETE `/api/playback/queue` | `api/playback.py:367`、`:379`；clear 仅 pending（`queue_manager.py:217`）；删除 current 走 PlaybackService 确认路径，不是客户端过滤 |
| Queue save | POST `/api/playback/queue/save-as-playlist`，body `{name}` | `queue_manager.py:268` 只保存 Up Next；同 song 重复会拒绝而非去重（`:272`）。UI 要明确解释此已有合同，避免乐观成功 |
| song Next/Add | POST `/api/playback/songs/{song_id}/play-next` / `/queue` | 每次入新 occurrence。Queue 行菜单若沿用这两项应传 song_id，不能假定为移动既有行；若想增加“移动该行至下一首”，必须单独命名并审计 |
| 集合 Play All/Shuffle | POST `/api/playback/collections/play` | `api/playback.py:319`；`CollectionRequest` 在 `schemas.py:85`，由 source_type/source_id/query/song_ids/randomize/seed 定义。服务端生成固定顺序/context（`collection_service.py:80`–`:123`）并替换 Queue（`playback_service.py:478`）；空集合是 no-op（`:468`） |
| Library 分类 | GET songs / albums / artists / genres / years / tags 及分类 `/songs` | `api/library.py:74`、`:137`、`:162`、`:187`、`:212`、`:237`；分类列表有稳定实体 ID，不用标题拼 ID。分类曲目 GET 过滤不可用（`:62`–`:71`），完整 Library songs 不同于 playable Collection |
| Search | GET `/api/library/search?q=...` → CollectionResponse | `api/library.py:262` 返回 IDs **不是 SongList**。`library_service.py:84` 空白返回空列表，仅 available；`:312` 搜索 title/artists/album/album_artists/genres/tag_names/year，精确→前缀→子串排序，然后确定性排序。Web 不另行过滤/重排/补不可用搜索项 |
| Playlist | list/detail/songs；POST create；PATCH rename；DELETE；POST add song；DELETE song；PUT `/songs/order` | `api/playlists.py:69`、`:84`、`:103`、`:193`、`:208`、`:228`、`:240`、`:267`、`:283`；全量 ordered_song_ids，不是局部拖动位置。Playlist `/songs` 返回持久成员，含不可用歌曲（`:120`–`:125`）；播放 Collection 则拆分 playable/unavailable（`collection_service.py:146`–`:172`）。两种展示不可混为一体 |
| Favorites | GET `/api/favorites`；PUT / DELETE `/api/favorites/{song_id}` | `api/playlists.py:129`、`:306`、`:324`；CollectionResponse 的 song_ids + unavailable_song_ids 都属于持久收藏成员展示输入，不能只用 playable IDs 判定星标。SongResponse 无 favorite bool（`schemas.py:45`–`:77`）。更改发布 playlist revision（`playlist_service.py:89`–`:137`），全站星标复用同一个资源 store |
| Settings Output/About | GET/PUT `/api/system/output`；GET `/api/system/mpd` | `api/system.py:19`、`:48`、`:55`。输出 states confirmed 与 last_request 分开（`system_schemas.py:43`）；CLIENT_STREAM 不可用仍按现有合同；About 返回 version 来源/stats/update/error/observed_at（`:68`），不得用缺失值猜事实。Task 10 config、backup、logs 不进此 Batch |

Playlist/Favorites 同时依赖 Library revision 和 Playlist revision 的 Web 资源失效规则已由 Task 8 共同客户端合同持有；后端 `playlist_service.py:89` 明确 revision 内容包含名称/成员/顺序/Favorites，传播仅在外层提交的净 delta 后出现。证据入口：`test_realtime_playlist.py:29`、`:242`、`:290`。

## 4. 可复用测试及新增证明边界

以下是已检查存在的测试入口，执行时应先核对节点名与 fixture：

- `server/tests/services/test_queue_manager.py::test_queue_play_now_preserves_prior_pending_items_after_selected_song`（第 102 行）；Start Track替换、Next插入、reorder、clear、save和CAS分别在第 72/127/146/219/235/263 行。
- `server/tests/services/test_playback_service.py::test_play_now_failure_does_not_record_switch_or_advance_state`（第 137 行）；Start Track orchestration（82）、MPD sync failure（310）、Play Context replacement（526）。这些是 Queue occurrence/Start Context 证明，不覆盖新 song Play Now。
- `server/tests/invariants/test_realtime_queue.py`：queue-only保持 current/history（43）、terminal failure/retry/replay（119）、联合 transport delta（170）、外层确认屏障（221）、拒绝无通知（269）、CAS优先于MPD副作用（384）。
- `server/tests/api/test_library_api.py`：unavailable song资源（217）、分类统一Collection（243）、Search query/empty（260）、稳定分类ID（452）。
- `server/tests/invariants/test_playlist_relationships.py::test_persisted_membership_matches_every_representation_and_collection_split`（第 5 行）：Playlist/Favorites不可用成员与播放拆分的权威入口。
- `server/tests/api/test_playlist_reads.py`（47/81）；`server/tests/invariants/test_realtime_playlist.py`（29/157/221/242/369）；`server/tests/api/test_idempotency.py`（19/46/64）。
- `server/tests/api/test_system_reads.py`、`test_system_output_mutations.py`；`server/tests/invariants/test_system_read_relationships.py`、`test_system_output_relationships.py`；控制 token proof `test_playback_control_target.py`。

后续 backend prerequisite 最少新增：普通 Play Now新ID和同URI重复pending；当前/Played/pending与source/context完整保持关系；Stop后session/AutoPlay；空/无Context分支；available/not-found验证先于副作用；MPD命令失败/确认未知/最终commit失败；同key replay只一次occurrence、不同payload key冲突；Queue/Playback/History联合版本/event；旧token失效、新token仅确认后可见；未知旧active不补造History reason。应先新增直接失败的 contract test，再实现；不能用旧测试总数抵扣新入口验收。

## 5. 范围与未解决限制

- 本次没有把任何历史 Gate 升为 PASS；自动化、手机真人、真实 MPD/NAS Gate由主 audit逐项核实。
- Queue HTTP revision 缺口是当前真实接口事实。若 Batch要提供多客户端拖动冲突防护，必须单独审计是否引入HTTP expected_revision；不能在普通 Task 9 view中偷偷改变后端合同。
- Favorites不可用成员星标和Playlist不可用行已有服务端表达，不需要为了UI另造favorite字段或新schema。
- 新动作尚未冻结的 Context/Played生命周期及技术确认合同阻塞对应后端和歌曲动作Batch；session继承既有History规则，不重开。它们不阻塞纯共享壳/导航/背景的计划拆分。
