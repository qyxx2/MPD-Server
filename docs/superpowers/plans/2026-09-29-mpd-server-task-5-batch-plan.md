# MPD-Server Task 5 Batch Execution Plan

> Task 5：Collection、Library/Playlist Service 与 REST API
>
> 本文件用于 Task 5 的分批实施、TDD 验证、跨 AI 窗口交接与最终验收。
> Task 5 不采用一次性实现；固定采用 **1 个 Contract Audit + 6 个 Batch**。
>
> 本文件不是对原实施 Plan 的替代，不改变：
>
> `docs/superpowers/plans/2026-09-25-mpd-server-v0-1-implementation-plan.md`
>
> 中 Task 5 的业务目标、Dependency Matrix 和 Execution Order。
> 原 Plan 与 `docs/superpowers/specs/` 仍是唯一的功能规格依据。
> 本文件只规定 Task 5 的执行分批方式、边界、交接与验收方式。

---

## 1. Task 5 前置条件

Task 5 依赖：

- Task 3 已完成 corrective follow-up；
- Task 4 已完成最终验收；
- 当前 `main` 已包含 Task 0–4 及 Task 0–4 integration gate；
- Task 3 的 Available Songs contract、DomainEvent contract 已冻结；
- Task 4 的 Queue、PlaybackContext、History、AutoPlay、Playback Service contract 已冻结。

Task 5 不依赖：

- Task 6
- Task 7
- Task 8
- Task 9
- Task 10
- Task 11
- Task 12

执行顺序保持：

```text
0
→ 1
→ 2
→ 1R
→ 2R
→ 3
→ 4
→ 5
→ 7
→ 6
→ 8
→ 9
→ 10
→ 11
→ 12
```

Task 5 不得提前实现 Task 6/7/8/9/10/11/12。

---

## 2. 当前基线与分支

Task 5 必须从当前 `main` 开始，不得从旧的 Task 4 feature branch 继续。

本次建立的 Task 5 分支：

```text
feature/task-5-library-api
```

Task 5 分支基线：

```text
main
  ↓
feature/task-5-library-api
```

基线提交以建立分支时的真实远端 `main` 为准，不以旧窗口报告或旧分支状态为准。

---

# 3. 固定执行方式

## 3.1 一个 Batch = 一个全新 AI 窗口

Task 5 固定使用：

```text
feature/task-5-library-api
```

执行结构：

```text
main
  │
  └── feature/task-5-library-api
        │
        ├── Contract Audit
        │
        ├── Batch 1
        │   Collection + LibraryService
        │
        ├── Batch 2
        │   PlaylistService + repository contract
        │
        ├── Batch 3
        │   REST read API
        │
        ├── Batch 4
        │   REST mutation / Playback API
        │
        ├── Batch 5
        │   Idempotency + error contract
        │
        └── Batch 6
            Task 5 final acceptance
```

每个 Batch 完成后：

1. 只完成本 Batch 范围内的代码和测试；
2. 检查 diff、changed files、依赖边界和架构边界；
3. 提交本 Batch 的 commit；
4. 提交后重新读取远端 branch/ref/commit，确认提交真实存在；
5. 输出 Batch 结束交接摘要；
6. 结束当前 AI 窗口。

下一个 Batch 必须使用全新 AI 窗口。

---

## 3.2 Git 是事实来源

跨窗口事实来源优先级：

1. 当前仓库实际代码；
2. 当前 branch / HEAD；
3. Git 提交历史和远端 branch ref；
4. Tests 与实际测试输出；
5. Specs；
6. 原 Implementation Plan；
7. 本文件；
8. 上一窗口交接摘要。

若发生冲突，以仓库实际状态 + Specs + 原 Plan 为准。

不得因为上一窗口报告“完成”就跳过重新验证。

---

# 4. Contract Audit：Task 5 开始前的强制审计

Contract Audit **不是业务实现 Batch**。

目标是先冻结 Task 5 将要使用的 Service、Repository 和 HTTP contracts，避免在实现过程中临时改变架构。

## 4.1 必须核对的实际 Repository 能力

### LibraryRepository

当前已存在的能力至少包括：

- get_song
- list_songs_in_root
- list_available_songs
- candidate matching
- artwork reference/source lookup
- scan-batch persistence

必须确认 Task 5 所需的：

- Album
- Artist
- Genre
- Year
- Tag
- Search
- Collection

究竟通过：

- 已有 Available Songs contract + Service 聚合；
- 或必要的最小 Repository 查询 contract；

来实现。

禁止在 API 层直接查询 SQLite。

### PlaylistRepository

必须核对当前实际能力是否完整覆盖：

- create
- list/get
- rename/update
- delete
- add song
- remove song
- reorder
- Favorites
- list playlist songs

若缺少 Task 5 所需的 CRUD contract，只允许进行**最小必要的 repository contract hardening**。

不得在 Task 5 中顺手重构整个 Repository。

---

## 4.2 Collection contract 必须先冻结

必须明确并测试以下 Collection source：

- Album
- Artist
- Genre
- Year
- Tag
- Search
- Playlist
- Favorites
- Entire Library
- Explicitly selected songs

必须明确：

- source type
- source id
- song ids
- 去重规则
- 默认排序
- random seed
- PlaybackContext 固定随机顺序
- empty collection 行为
- unavailable song 行为

不得让不同 API 自己解释 Collection 语义。

---

## 4.3 Search contract

规格书没有冻结完整的搜索算法，因此 Task 5 必须在实现前明确：

- 支持字段；
- 默认匹配规则；
- 默认稳定排序；
- 同一 Song ID 去重；
- 空查询/空结果状态。

Search 排序必须稳定。

不得引入复杂搜索引擎。

首期以 SQLite / 现有 Repository 能力完成。

---

## 4.4 API contract

在 REST 实现前必须冻结：

- URL/path
- HTTP method
- request model
- response model
- validation behavior
- error response shape
- HTTP status mapping

API 只负责：

```text
Request validation
    ↓
Service call
    ↓
Error mapping
    ↓
Response model
```

禁止：

```text
API → SQLite
API → concrete MPD adapter
API → complex business logic
```

---

## 4.5 Idempotency contract

必须先确认：

- request ID 的位置；
- 哪些 mutation 必须支持 request ID；
- 相同 request ID + 相同 payload；
- 相同 request ID + 不同 payload；
- 已成功 mutation 的重复请求；
- 失败 mutation 的处理；
- 幂等结果保存位置；
- 与业务事务的关系。

Idempotency 必须处在 Service/API 所属边界，不得通过全局临时变量实现。

---

## 4.6 Contract Audit 的停止条件

如果实际代码与 Task 5 所需 contract 存在不可绕过的缺口：

- 不允许用临时绕架构代码继续；
- 不允许 API 直接读取数据库；
- 不允许 Service 访问 concrete MPD adapter；
- 不允许把未来 Task 的实现提前搬入 Task 5；
- 先在本计划对应章节明确最小 contract hardening；
- 再进入相关 Batch。

Contract Audit 本身不引入业务行为。

---

# 4.7 Contract Audit Record（2026-09-29）

本记录以本分支当时的实际 HEAD
`ca9b25b970f7e332d776c985af9cabeaac0d3c17`
为审计基线。GitHub 实际检查确认：

- branch = `feature/task-5-library-api`
- `feature/task-5-library-api` 相对 `main` 为 ahead 1、behind 0
- 当前唯一分支新增提交为本 Task 5 Batch Plan
- `main` 当前 HEAD = `29c7d6158c235f1070a4dc2c61cfe44261fe2458`
- Task 0–4 integration gate 已在 main，Task 4 Batch 6 commit
  `cb02824273881fcb328f20391ec99fe144ac84d9` 已被当前 main 基线包含
- Task 0–4 永久回归文件均位于 `server/tests/`，本 Task 5 不建立对 Web build 的依赖

## 4.7.1 Dependency / Architecture Gate

当前代码实际具备：

- `Song`：包含 song_id、title、file_uri、artist/album/album_artist、
  genre/tag、year、disc/track、lyrics、音频规格、availability、
  ArtworkRef 等字段；
- `Playlist`：包含 playlist_id、name、created_at、updated_at、
  is_system；
- `PlaybackContext` / `QueueItem` / `PlaybackState`；
- `LibraryRepository`；
- `PlaylistRepository`；
- `PlaybackService`、`QueueManager`、`HistoryService`、
  `AutoPlay`；
- `PlayerPort`，且 Task 4 服务层已经通过 PlayerPort 与播放引擎交互；
- `DomainEvent` / `LibraryChangedEvent`。

当前 Task 5 不需要引入 Task 6/7/8/9/10/11/12 任何实现或 contract。

架构冻结为：

```
REST API
    ↓
Service
    ↓
Repository / PlayerPort
```

API 不访问 SQLite、QueueRepository、HistoryRepository 或 concrete
MPD adapter；Service 不依赖 concrete MPD adapter；CollectionService
不依赖 WebSocket。

## 4.7.2 LibraryRepository Audit

实际存在并核对的主要能力：

- `get_song(song_id)`
- `find_song_by_file_uri(file_uri)`
- `list_songs_in_root(root_uri_prefix)`
- `list_available_songs()`
- identity/content-hash candidate lookup
- artwork persisted-reference/source-song lookup
- scan-batch transactional persistence

结论：当前库规模和既有 contract 足以采用：

```
LibraryRepository.list_available_songs()
        ↓
LibraryService / CollectionService
        ↓
Album / Artist / Genre / Year / Tag / Search 聚合、过滤、排序
```

因此 Contract Audit **不新增 LibraryRepository 的通用 SQL 搜索/聚合接口**。
这样避免把 Task 5 的业务排序规则泄漏到 Repository，并保持 API 永远不直接访问
SQLite。

必要的最小 Repository hardening 由 Batch 1 在出现不可避免的数据访问缺口时再补，
且必须保持 `Song` / `availability_status` / 既有扫描事务语义不变。

### Artwork contract

Artwork 继续使用：

```
Song.artwork: ArtworkRef
        ↓
Artwork source song
        ↓
read-only media file
```

Repository 只提供持久化引用和 source-song 信息；实际 artwork bytes 的读取由
LibraryService 在既有只读文件边界内完成。不得生成、修改、重命名、删除或写回
音乐文件。

## 4.7.3 PlaylistRepository Audit

实际存在：

- `create_playlist`
- `add_song`
- `remove_song`
- `reorder_playlist`
- `set_favorite`
- `list_favorite_song_ids`
- `list_song_ids`

实际缺口：

- list/get playlist
- rename/update playlist
- delete playlist
- 对不存在 playlist 的明确 not-found 语义
- list playlist songs 的资源级读取 contract

冻结的最小 hardening 分配如下：

- Batch 2 增加 playlist list/get/update/delete contract；
- 继续复用现有 SQLite transaction boundary；
- 不修改已经稳定的 duplicate-song、remove、reorder 事务语义；
- delete 依赖现有 `ON DELETE CASCADE` 删除 playlist_items，但不得删除 Song；
- `is_system=true` 的系统 Playlist 不允许通过普通自定义 Playlist CRUD 删除或重命名。

Favorites 不实现为 Queue，也不与 History 混用。当前 favorites relation
继续由 `favorites(song_id, created_at)` 持久化，默认顺序冻结为
`created_at DESC, song_id DESC`，与现有 Repository 实际行为一致。

## 4.7.4 Collection Contract Freeze

Collection 统一来源：

```
ALBUM
ARTIST
GENRE
YEAR
TAG
SEARCH
PLAYLIST
FAVORITES
LIBRARY
SONGS
```

字段语义冻结：

- `source_type`：以上固定枚举之一；
- `source_id`：实体型来源使用稳定实体 ID；`YEAR` 使用规范化年份字符串；
  `SEARCH`、`LIBRARY`、`SONGS` 无实体 source_id 时保持 null；
- `song_ids`：按最终播放顺序排列、且只出现一次的 Song ID；
- `unavailable_song_ids`：源集合中已知但当前不可用、因此未进入可播放
  `song_ids` 的 Song ID；不得伪装成 AVAILABLE；
- `random_seed`：随机播放时生成一次并固化；顺序播放为 null；
- `playback_context_id`：真正开始播放后由 PlaybackContext 持有，Collection
  本身不持有 Queue。

默认排序冻结：

- ALBUM：`disc_number ASC NULLS LAST` → `track_number ASC NULLS LAST`
  → `file_uri ASC` → `song_id ASC`；
- PLAYLIST：用户保存的 position；
- FAVORITES：`created_at DESC` → `song_id DESC`；
- ARTIST / GENRE / YEAR / TAG / LIBRARY：`title.casefold()` →
  `album.casefold()` → `file_uri` → `song_id`；
- SEARCH：按 Search contract 的稳定 score/rank，其后使用与 LIBRARY 相同的
  稳定 fallback；
- SONGS：用户提供的顺序，去重后保留第一次出现。

去重规则：

- 同一最终 `song_id` 只出现一次；
- 对用户明确选中的 `SONGS`，first occurrence wins；
- 不得把去重做成“发现重复即静默替换为其他歌曲”。

Availability 规则：

- Library、分类、Search、Playlist、Favorites 默认仅把
  `availability_status == AVAILABLE` 放入 `song_ids`；
- 不可用成员进入 `unavailable_song_ids`；
- 若 source 本身为空，Collection 为空；
- 空 Collection 不得用随机歌曲补齐；
- Explicitly selected empty Collection 不得触发随机替代。

Random / PlaybackContext：

- random 只在创建本次播放集合或开始本次播放时生成一次；
- 使用冻结的 `random_seed` 产生确定的 `ordered_song_ids`；
- 同一 PlaybackContext 内刷新、重读或重新生成展示数据不得改变既有随机顺序；
- 新的 PlaybackContext 才允许重新生成随机顺序。

Collection 负责“哪些歌曲、什么顺序”，PlaybackService 负责真正替换 Queue、
启动播放以及 AutoPlay 语义。

## 4.7.5 Search Contract Freeze

首期只搜索 Song 已存在且可由 `list_available_songs()` 获得的数据：

- title
- artists
- album
- album_artists
- genres
- tag_names
- year

默认匹配：

- 去除首尾空白；
- 使用 Unicode 文本的 `casefold()` 进行不区分大小写匹配；
- 非空 query 对上述字段执行 substring match；
- year 按规范化十进制字符串匹配；
- 不引入 FTS、外部搜索引擎或复杂相关性基础设施。

稳定排序：

```
exact field match
→ prefix field match
→ substring match
→ title.casefold()
→ album.casefold()
→ file_uri
→ song_id
```

如果同一 Song 同时命中多个字段，只返回一个 Song ID；排序 score 取该 Song
的最佳匹配级别，再使用稳定 fallback。

空 query：

- 返回空结果，不解释为“整个音乐库”。

无结果：

- 返回合法空结果集合，不视为错误。

Search 结果可直接作为 Collection；API 不得另行定义一套 Search 排序或去重规则。

## 4.7.6 REST Contract Freeze

Task 5 首期 API 路径统一使用 `/api` 前缀。

### Library read

- `GET /api/library/songs`
- `GET /api/library/songs/{song_id}`
- `GET /api/library/albums`
- `GET /api/library/albums/{album_id}/songs`
- `GET /api/library/artists`
- `GET /api/library/artists/{artist_id}/songs`
- `GET /api/library/genres`
- `GET /api/library/genres/{genre_id}/songs`
- `GET /api/library/years`
- `GET /api/library/years/{year}/songs`
- `GET /api/library/tags`
- `GET /api/library/tags/{tag_id}/songs`
- `GET /api/library/search?q={query}`
- `POST /api/library/collections`（请求复杂、结果只读，故使用 POST）
- `GET /api/library/songs/{song_id}/artwork`

### Library mutation

- `POST /api/library/scan`

### Playlist / Favorites

- `GET /api/playlists`
- `POST /api/playlists`
- `GET /api/playlists/{playlist_id}`
- `PATCH /api/playlists/{playlist_id}`
- `DELETE /api/playlists/{playlist_id}`
- `GET /api/playlists/{playlist_id}/songs`
- `POST /api/playlists/{playlist_id}/songs`
- `DELETE /api/playlists/{playlist_id}/songs/{song_id}`
- `PUT /api/playlists/{playlist_id}/songs/order`
- `GET /api/favorites`
- `PUT /api/favorites/{song_id}`
- `DELETE /api/favorites/{song_id}`

### Playback / Queue

- `GET /api/playback/state`
- `GET /api/playback/queue`
- `POST /api/playback/tracks/{song_id}/play`
- `POST /api/playback/queue/items/{queue_item_id}/play`
- `POST /api/playback/songs/{song_id}/play-next`
- `POST /api/playback/songs/{song_id}/queue`
- `POST /api/playback/pause`
- `POST /api/playback/stop`
- `POST /api/playback/next`
- `POST /api/playback/previous`
- `POST /api/playback/seek`
- `PUT /api/playback/queue/items/{queue_item_id}`（reorder）
- `DELETE /api/playback/queue/items/{queue_item_id}`
- `DELETE /api/playback/queue`
- `POST /api/playback/queue/save-as-playlist`
- `POST /api/playback/collections/play`

### History

- `GET /api/history`
- `GET /api/history/played`

Request body / response model 原则：

- API schemas 与 domain models 分离；
- 同一资源类型使用同一 response schema；
- list endpoint 使用 `items` + `count` 的统一 envelope；
- 单资源使用资源对象本身；
- mutation 返回 mutation 后的 authoritative resource/state；
- DELETE 成功返回 HTTP 204，不再返回另一套资源 schema；
- artwork 成功返回真实媒体 bytes 和持久化 MIME type。

### Validation / status mapping

统一错误对象冻结为：

```json
{
  "error": {
    "code": "STABLE_MACHINE_CODE",
    "message": "human-readable message",
    "details": null
  }
}
```

其中 `details` 可为固定结构对象，不得因 endpoint 随意变更字段名。

状态映射：

- 200：读取成功、播放/控制成功并返回 state/resource；
- 201：创建 Playlist 成功；
- 204：删除 Playlist、删除 playlist song、取消 favorite、删除 Queue item、
  清空 Queue；
- 400：已通过 schema 校验但请求语义本身无效；
- 404：Song / Playlist / Queue item / collection source / artwork source 不存在；
- 409：duplicate playlist song、playlist reorder member mismatch、
  Queue revision conflict、Idempotency-Key payload conflict、系统 Playlist
  禁止修改等资源状态冲突；
- 422：Pydantic/request schema validation failure；
- 500：Repository / unexpected service failure；
- 502：MPD / PlayerPort 已到达但上游命令失败；
- 503：MPD / PlayerPort 当前不可达；
- artwork read failure 使用 500 + `ARTWORK_READ_ERROR`，绝不伪装成 404
  “无封面”；
- 空 Collection 是成功的 200 结果，不是错误。

### Playback request semantics

REST 不重新解释 Playback Service 语义：

- `tracks/{song_id}/play` 对应已有 Start Track / 新 PlaybackContext；
- Queue item play 对应已有 Play Now；
- song play-next / queue 对应已有 Play Next / Add to Queue；
- pause / stop / next / previous / seek 原样进入 PlaybackService；
- queue reorder/delete/clear/save-as-playlist 只调用 QueueManager/
  PlaybackService/PlaylistService 现有业务；
- collection play 先通过 CollectionService 生成统一 Collection，再交由
  PlaybackService 执行；
- API 不直接修改 Queue，不直接向 MPD 发命令。

## 4.7.7 Idempotency Contract Freeze

Task 5 使用标准 HTTP header：

```
Idempotency-Key: <opaque-client-key>
```

以下所有 mutation endpoint 都要求 `Idempotency-Key`：

- library scan；
- playlist CRUD / song membership / reorder；
- favorite / unfavorite；
- playback / queue mutations。

同一路径、同 HTTP method、同 canonical request payload 与同
`Idempotency-Key`：

- 第一次执行实际调用 Service；
- 后续重复成功请求直接返回第一次保存的 status + response body；
- 不再次执行业务 mutation。

同一 Key：

- endpoint/method/payload 任一不同 → HTTP 409 +
  `IDEMPOTENCY_KEY_CONFLICT`；
- 不得错误复用前一次结果。

失败语义：

- schema validation 失败不创建幂等记录；
- Service/Repository/Player 失败且业务事务未提交时，不保存 terminal response，
  同一 Key 可以 retry；
- 不允许通过进程内 dict、global mutable cache 或单进程状态作为唯一保证。

持久化位置冻结为 SQLite 专用幂等记录表，后续 Batch 5 实现；记录至少需要：

- operation scope（method + canonical path）
- idempotency key
- canonical payload hash
- response status
- serialized response body
- created_at

并建立唯一约束：

```
(operation_scope, idempotency_key)
```

事务关系冻结为：

```
business mutation
+
idempotency terminal result
```

必须具有明确的同一 SQLite transaction / unit-of-work 原子边界。Batch 5
不得通过“先执行业务、后写幂等记录”的可竞态序列实现保证。

失败业务若未提交，则 terminal idempotency result 不存在；因此 retry 可以重新执行。

## 4.7.8 Audit Conclusion / Batch Allocation

Contract Audit 本身**不实现业务功能**，当前审计结果为：

- Dependency Gate：通过；
- Architecture Gate：通过；
- LibraryRepository：现有 Available Songs contract 足以支撑首期 Service 聚合；
- PlaylistRepository：确认存在 CRUD contract gap，分配到 Batch 2 的最小 hardening；
- Collection contract：已冻结；
- Search contract：已冻结；
- REST contract：已冻结；
- Idempotency contract：已冻结，实际 SQLite persistence 分配到 Batch 5；
- Future Task dependency：未发现；
- WebSocket / Output Manager / final config / deployment / physical acceptance：
  均不属于 Task 5。

后续 Batch 不得重新定义上述语义；如实际代码暴露不可绕过的新冲突，必须先停止当前 Batch，
记录冲突并修正本计划，再继续实现。


# 5. Batch 1：Collection + LibraryService

## 对应原 Plan

- Step 1
- Step 2
- Step 3
- Step 4
- Step 5 的 LibraryService / CollectionService 部分

## 核心文件

允许主要涉及：

- `server/app/services/library_service.py`
- `server/app/services/collection_service.py`
- `server/tests/services/test_library_service.py`
- `server/tests/services/test_collection_service.py`
- 为冻结 contract 所必需的最小既有 Repository/model 文件

不得创建最终 REST API。

## TDD 顺序

### Step 1 RED

为每一种 Collection source 编写最小失败测试。

必须覆盖：

- Album
- Artist
- Genre
- Year
- Tag
- Search
- Playlist
- Favorites
- Entire Library
- Explicit song selection

### Step 2 RED

验证：

- 默认排序；
- 去重；
- random seed；
- 同一 PlaybackContext 内随机顺序固定；
- 新建 Context 才重新生成随机顺序。

### Step 3 RED

验证：

- empty collection；
- 不把随机歌曲替代明确的空集合；
- 不伪造结果。

### Step 4 RED

验证 Service/Repository boundary：

```text
LibraryService / CollectionService
        ↓
Repository contract
```

而不是：

```text
Service → SQLite connection
```

## 实现

只实现满足上述测试的最小 LibraryService / CollectionService。

## Batch 1 不做

- PlaylistService
- REST API
- Idempotency
- WebSocket
- Output Manager
- config.py
- Web/PWA
- 浏览器测试

## Batch 1 接受条件

- focused service tests GREEN；
- 受影响 Task 3 / Task 2R regression GREEN；
- compile 通过；
- Ruff 通过；
- diff --check 通过；
- 无未来 Task 依赖；
- Collection 不越界进入 Playback Service 内部实现。

---

# 6. Batch 2：PlaylistService + Repository Contract

## 对应原 Plan

- Step 5 剩余 PlaylistService 部分

## 核心目标

完成：

- Playlist CRUD
- Playlist add/remove/reorder
- Favorites
- Queue save-as-playlist

## 核心文件

允许主要涉及：

- `server/app/services/playlist_service.py`
- `server/app/repositories/playlist_repository.py`（仅在 Contract Audit 证明缺失时最小补齐）
- 相关 model 文件
- `server/tests/services/test_playlist_service.py`
- 必要的 repository tests

## 必须保持

- 删除 Playlist 不删除 Song；
- 删除 Song relation 不影响原始音乐文件；
- Favorites 与普通 Playlist 独立；
- Favorites 不随 Queue/Collection 改变；
- Queue save 不混入 Played/History；
- Queue save 的顺序稳定；
- Playlist duplicate 行为严格按规格和已有 Repository 约束；
- reorder/delete 的原子性不被破坏。

## 特别限制

如果需要补 Repository contract：

- 只补 Task 5 实际需要的最小方法；
- 不做 Repository 全量重构；
- 不修改 Task 2 已经确认的事务语义；
- 不改变历史数据模型，除非测试证明 Task 5 contract 无法成立且修改是必要的。

## Batch 2 不做

- REST API
- request ID / idempotency
- WebSocket
- Output Manager
- config
- Web/PWA

## 接受条件

除上述 Batch 2 focused tests 外，至少回归：

- Task 2R affected tests；
- Task 3 affected tests；
- Task 4 affected tests。

并通过：

- compileall
- Ruff
- git diff --check
- architecture boundary review

---

# 7. Batch 3：REST Read API

## 对应原 Plan

- Step 6 的 read-side 部分

## 核心目标

先把查询和资源读取 API 完整打通，不进入 mutation idempotency。

## API 范围

至少包括：

- Song
- Album
- Artist
- Genre
- Year
- Tag
- Search
- Collection
- Library
- Favorites / Playlist read
- Album artwork read
- Manual library scan result/query contract

## 核心文件

- `server/app/api/schemas.py`
- `server/app/api/library.py`
- 必要的 read-only API modules
- `server/tests/api/*`

## 必须验证

### Request validation

非法参数不能进入 Service。

### Response schema

同一资源不得因为不同 endpoint 产生互不兼容的数据结构。

### Empty result

必须明确表达：

- empty collection
- no search results
- unavailable item

不得返回伪造内容。

### Artwork

Artwork 必须：

```text
Persisted ArtworkRef
        ↓
Read-only source file
        ↓
API response
```

不得修改音频文件。

Artwork 读取失败必须是可观察的 API 错误，而不是伪装成“没有封面”。

### Manual scan

API 只能调用已有 Scanner/Service contract。

不得让 API 自己扫描音乐目录。

## Batch 3 不做

- WebSocket
- browser E2E
- frontend build
- idempotency implementation
- Output Manager
- config system

## 接受条件

- API focused tests GREEN；
- Service focused tests GREEN；
- affected regression GREEN；
- schema stable；
- API 不直接访问 SQLite/MPD；
- compile / Ruff / diff green。

---

# 8. Batch 4：REST Mutation + Playback API

## 对应原 Plan

- Step 6 的 mutation / playback 部分

## 核心目标

对外暴露已经存在的服务端业务能力，不重新实现业务。

## Playback API

至少覆盖：

- Play Now
- Play Next
- Add to Queue
- Pause
- Stop
- Next
- Previous
- Seek
- Queue reorder
- Queue delete
- Queue clear
- Save Queue as Playlist

这些请求必须进入已有：

```text
PlaybackService
QueueManager
PlaylistService
        ↓
Repository / PlayerPort
```

禁止 API 自己操作 Queue 或 MPD。

## Playlist/Favorites mutation API

覆盖：

- create playlist
- rename/update playlist
- delete playlist
- add song
- remove song
- reorder
- favorite/unfavorite

## History API

按已有 HistoryService / Repository contract 读取历史。

不得在 API 层重新解释 History reason。

## 错误

先使用已有 Service error，再由 API 统一映射。

不要为了 API 方便改变底层 Service 语义。

## Batch 4 不做

- WebSocket
- StateService
- Output Manager
- config.py
- Web/PWA
- browser E2E
- Idempotency final storage（Batch 5）

## 接受条件

- mutation API focused tests GREEN；
- playback behavior regression GREEN；
- Task 4 affected regression GREEN；
- API → Service → Repository/PlayerPort boundary 检查通过；
- compile / Ruff / diff green。

---

# 9. Batch 5：Idempotency + Error Contract + API Consistency

## 对应原 Plan

- Step 7
- Step 8

## 核心目标

把 REST mutation 的可重试行为和错误契约固定下来。

## Idempotency

必须测试：

1. 首次 request-id；
2. 同 request-id + 相同 payload；
3. 同 request-id + 不同 payload；
4. mutation 已成功后重复请求；
5. mutation 执行失败后的请求；
6. 不带 request-id 的允许 mutation；
7. 要求 request-id 的 mutation 缺失 request-id。

实现必须保证：

- 业务成功与幂等记录的关系明确；
- 重复请求不得重复执行业务；
- 不同 payload 不得错误复用旧结果；
- 不使用进程内临时 dict 作为唯一持久状态；
- 不破坏现有 SQLite transaction boundary。

## Error contract

统一验证：

- 404
- 409
- validation failure
- service/domain failure
- repository failure
- playback/MPD failure
- artwork read failure
- empty collection

具体 status code 必须以 Task 5 contract audit 后冻结的定义为准。

## Stable response schemas

同一类错误不能因为 endpoint 不同而随机改变字段结构。

同一类资源返回字段必须保持稳定。

## Batch 5 不做

- WebSocket
- FullStateSnapshot
- Output Manager
- Web/PWA
- Task 10 configuration system

## 接受条件

- 所有 idempotency focused tests GREEN；
- API error mapping focused tests GREEN；
- stable schema tests GREEN；
- affected service/API regressions GREEN；
- compile / Ruff / diff green。

---

# 10. Batch 6：Task 5 Final Acceptance

## 对应原 Plan

- Step 9
- Step 10

## Step 9

禁止新增功能。

只做：

- 全量 Task 5 focused tests；
- Service aggregate tests；
- API aggregate tests；
- affected Task 2R regression；
- affected Task 3 regression；
- affected Task 4 regression；
- full `server/tests`；
- compileall；
- Ruff；
- git diff --check；
- changed-files review；
- architecture-boundary review。

## 必须审查

### Service boundary

```text
API
 ↓
Service
 ↓
Repository / PlayerPort
```

不得存在：

```text
API → SQLite
API → MPDAdapter
```

### Collection

- 各来源一致；
- song_id 稳定；
- 去重；
- random order 在 PlaybackContext 内固定；
- empty collection 不伪造歌曲。

### Playlist/Favorites

- Playlist 与 Song 独立；
- Favorites 独立；
- Queue save 不混入 Played/History；
- reorder/delete 语义正确。

### Playback

- API 只调用 PlaybackService；
- PlaybackService 仍是播放编排权威；
- API 不新增第二套播放业务。

### Artwork

- 原始音乐文件严格只读；
- API 通过持久化 ArtworkRef 读取。

### Idempotency

- mutation retry 不重复执行；
- request-id conflict 行为明确；
- 不引入进程内临时唯一状态。

### Future Task isolation

不得引入：

- WebSocket / StateService
- Output Manager
- Task 8 Web/PWA 状态层
- Task 9 UI
- Task 10 final config system
- Task 11 deployment automation
- Task 12 physical acceptance

## Step 10

使用：

```text
feat: expose library and playback api
```

作为 Task 5 最终提交。

Task 5 Batch 6 commit 成功 ≠ Task 5 自动进入 `main`。

---

# 11. 测试策略

Task 5 采用后端为主的回归策略。

## 每个 Batch

执行：

```text
focused tests
+
受影响的历史 Task regression
+
compileall
+
Ruff
+
git diff --check
```

## Batch 6

增加：

```text
full server/tests
```

## Web 测试

Task 5 不修改 Web/PWA，因此：

- 不重复运行 Web build；
- 不重复运行 Web typecheck；
- 不新增复杂浏览器 E2E；
- 不把 Web 构建加入 Task 5 的永久后端回归命令。

只有实际 Task 5 变更触及 `web/` 时，才重新判断是否需要 Web build/typecheck。

---

# 12. 真实 MPD 与实机验证边界

Task 5 正常实现与 API 验证不要求真实 MPD。

原因：

- Task 1/1R 已验证 MPD 0.23.5 capabilities；
- Task 4 已验证 PlaybackService → PlayerPort → MPDAdapter 集成；
- Task 5 的主要新增边界是 API → Service。

因此：

```text
API tests
→ Mock MPD / Fake PlayerPort
```

即可覆盖 Task 5 的主要实现。

真实：

- 播放；
- USB DAC；
- NAS；
- 输出切换；
- 长时间运行；
- WebSocket 重连；
- NAS 重启恢复；

保留到后续对应 Task / Task 12。

---

# 13. Batch 间统一 Git 要求

每个 Batch 完成后必须确认：

1. branch = `feature/task-5-library-api`
2. HEAD 正确；
3. workspace 状态明确；
4. changed files 仅属于本 Batch；
5. commit message 明确；
6. commit 已 push；
7. 重新读取远端 branch/ref；
8. 重新读取该 commit，确认真实存在；
9. 不自动 merge `main`。

禁止：

- force push；
- 无必要的 squash；
- 把多个互不相关 Batch 压成一个 commit；
- 提交测试目录里的临时文件；
- 把环境生成物加入 Git。

---

# 14. 每个 Batch 的统一交接模板

完成后必须输出：

```text
【Task 5 Batch <N> 结束交接】

1. 本次实际范围
- Task:
- Batch:
- 原 Plan Steps:
- 实际执行到：

2. Contract Audit 状态
- 本 Batch 使用的 contract:
- 是否发现与上一窗口不同:
- 是否发生最小 contract hardening:
- 是否存在未冻结 contract:

3. Step 状态
- Step X: COMPLETE / PARTIALLY COMPLETE — ENVIRONMENT VALIDATION PENDING / BLOCKED
- ...
- RED：
- GREEN：
- 最终状态：

4. 实际修改
新增：
- ...

修改：
- ...

删除：
- ...

并说明每个文件为什么属于本 Batch。

5. 测试
逐项写实际命令和实际结果：
- focused:
- regression:
- compile:
- lint:
- diff:

不得把未执行测试写成 PASS。

6. 环境限制
- NONE
或：
- 测试目的：
- 当前环境：
- 阻塞原因：
- 是否影响下一 Batch：

7. Specs / Plan / Code 冲突
- NONE
或具体记录。

8. 依赖状态
- Task 3:
- Task 4:
- 本 Batch 是否引入未来 Task：
- 下一 Batch 所需 contract 是否已经存在：

9. Git
- branch:
- HEAD:
- workspace:
- changed files:
- commit SHA:
- commit message:
- remote branch:
- remote ref:
- 二次确认：

10. 下一 Batch
- Batch:
- Steps:
- 本 Batch commit:
- 下一窗口必须重新确认：
- 已知风险：
- 必须避免的越界：

11. 最终判定
只能使用：
COMPLETE
PARTIALLY COMPLETE — ENVIRONMENT VALIDATION PENDING
PARTIALLY COMPLETE — BLOCKED
BLOCKED BY DEPENDENCY
```

---

# 15. Task 5 最终完成后的处理

Batch 6 完成后，在创建 PR 前必须再次执行一次完整 Task 5 verification：

1. 检查原 Plan Task 5 的 10 个 checkbox；
2. 检查本文件 1 Audit + 6 Batch 的完成状态；
3. 检查所有 Specs 覆盖；
4. 检查 changed files；
5. 检查 architecture boundary；
6. 检查未来 Task isolation；
7. 检查 full server regression；
8. 检查 branch / commit / remote ref；
9. 确认没有未验证的环境阻塞；
10. 再决定是否创建 PR 并合并 `main`。

**Task 5 的最终 commit、Batch 6 完成和进入 main 是三个独立状态，不得混为一谈。**

---

# 16. Task 5 Batch 总览

| 阶段 | 原 Plan Steps | 核心范围 | 主要风险 |
|---|---:|---|---|
| Contract Audit | — | Repository / Collection / Search / API / Idempotency contract 冻结 | **最高** |
| Batch 1 | 1–5 部分 | Collection + LibraryService | 高 |
| Batch 2 | 5 剩余 | PlaylistService + Repository contract | 高 |
| Batch 3 | 6 read-side | REST read API | 中高 |
| Batch 4 | 6 mutation-side | REST mutation + Playback API | **最高** |
| Batch 5 | 7–8 | Idempotency + error/schema contract | **最高** |
| Batch 6 | 9–10 | 整体验收与最终提交 | 中 |

Task 5 的实现原则：

```text
先冻结 contract
    ↓
再实现 Service
    ↓
再暴露 Read API
    ↓
再暴露 Mutation / Playback API
    ↓
再加入 Idempotency / Error Contract
    ↓
最后做全量验收
```

**不要一次性实现整个 Task 5。**
