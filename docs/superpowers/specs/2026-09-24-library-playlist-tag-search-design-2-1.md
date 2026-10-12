# 第二章：Library / Playlist / Tag / Search 数据模型

## 1. 目标与范围

本章定义音乐库的数据组织方式、分类集合、用户
Playlist、收藏、搜索以及扫描更新规则，并与第一章的 Queue / Playback
History / Playback Context / AutoPlay 语义衔接。

目标：

-   歌曲在整个系统中有稳定、统一的内部身份。
-   专辑、歌手、年代、Genre、搜索结果和 Playlist
    都能生成可供播放服务使用的歌曲集合。
-   分类浏览和搜索中的歌曲条目采用统一交互：点击具体歌曲后显示 Playback
    Action（Play Now、Play Next、Add to Queue）。
-   收藏是持久化的用户列表，按§5.3的Player与单曲菜单入口切换收藏状态。
-   保存必要的歌词及音频技术信息，便于歌词显示和音频信息展示。

本章不定义具体 UI 排版、MPD
协议实现细节或最终数据库引擎；这些留待后续架构章节和实施计划确定。

## 2. 统一数据组织方案

采用"统一歌曲实体 + 多种集合来源"的模型。

每首音乐对应一个 Song 实体和稳定的内部 `song_id`。其他数据对象通过歌曲
ID 关联 Song，而不是复制歌曲记录：

-   Album：由专辑元数据组织的歌曲集合。
-   Artist：由歌曲演唱者或专辑艺术家关联形成的集合。
-   Tag / Genre / Year：由标签值形成的分类集合。
-   Playlist：用户创建并持久保存的有序歌曲列表。
-   Favorites：系统提供的持久收藏列表，属于用户 Playlist
    体系中的特殊列表。
-   Collection：一次播放操作所使用的临时歌曲集合，可以来源于上述任一分类、搜索结果、Playlist
    或整个音乐库。

文件路径是歌曲的存储定位信息，不是歌曲在业务层的唯一身份。路径变化时，系统应尽可能保留
Song ID 及其 Playlist、收藏和历史关联。

## 3. 核心数据模型

### 3.1 Song（歌曲）

Song 是可播放、可加入 Queue、可收藏、可放入 Playlist 的基础实体。

建议字段：

  --------------------------------------------------------------------------
  字段                            含义
  ------------------------------- ------------------------------------------
  `song_id`                       内部稳定唯一标识

  `title`                         歌曲标题

  `artist_ids` / `artists`        一个或多个歌曲演唱者关联

  `album_id` / `album`            专辑关联及展示名称

  `album_artist_ids` /            专辑艺术家关联；与歌曲演唱者区分
  `album_artist`                  

  `track_number`                  专辑内曲目序号

  `disc_number`                   多碟专辑中的碟号

  `year` / `date`                 可规范化的发行年份或日期

  `genre_ids` / `genres`          一个或多个 Genre 关联

  `duration`                      音频时长

  `file_uri`                      文件定位信息

  `lyrics`                        从文件元数据或关联歌词文件读取的歌词内容

  `lyrics_format`                 歌词格式标识，例如普通文本或 LRC

  `bit_depth`                     音频位深，例如 16 bit、24 bit；未知时为空

  `sample_rate_hz`                采样率，以 Hz 保存，例如
                                  44100、48000、96000；未知时为空

  `channel_count`                 声道数；可选，未知时为空

  `codec`                         编码/容器信息，例如 FLAC、MP3；可选

  `metadata_status`               元数据读取状态或完整性标记

  `last_scanned_at`               最近扫描时间
  --------------------------------------------------------------------------

#### 歌词规则

-   支持读取嵌入在音频文件中的歌词，以及与歌曲关联的歌词文件。
-   LRC 歌词应保留时间戳，供播放器进行同步滚动。
-   非同步歌词可以显示为普通歌词文本，但不能伪造时间戳或承诺逐句同步。
-   歌词来源、格式及读取失败状态应可区分，避免把"无歌词"和"读取失败"混为一谈。
-   歌词数据与音频文件定位信息关联；文件移动或扫描更新后应重新确认关联关系。

#### Web 歌词展示补充（2026-10-09）

Web 的提示位置及稳定媒体区继承 [全局 UI 合同](2026-10-03-web-pwa-visual-design.md) WEB-UI-NOTIFY/SHELL/BASE；本节只定义歌词内容与交互。无歌词、read_error、无法同步或进度未确认的说明统一进入 app bar 详情，不新增歌词区通知文字；普通歌词/fallback 正文和可用性语义保留。后续通知接入不得修改已冻结的解析、跟随、选择及 cue seek 行为。

- 仅消费服务端提供的歌词及 format/source/status。`read_error` 即使带有可用 fallback 文本也保留失败提示；不能改成“无歌词”。
- v0.1 同步解析支持 `[mm:ss]`、带 1–3 位小数的 `[mm:ss.xxx]` 和既有 parser 接受的 `[mm:ss:xxx]`；同一行多个时间标签展开为多个 cue。同时间 cue 保留原文顺序并一起高亮；按时间稳定排序，不改写原始歌词。
- 支持整数毫秒 `[offset:n]`：展示时间加 offset 后匹配原 cue 时间，正值使歌词提前；多个合法 offset 取最后一个。元信息标签不生成 cue。非时间行保留可读文本，异常标签不生成假时间；无合法 cue 时降级为普通文本并提示无法同步。逐字 karaoke 不属于 v0.1。
- 高亮共用 Playback Spec §7.2 的展示时钟，选取不晚于当前展示时间的最近 cue 组；首 cue 前无高亮。无可用匹配进度时不猜高亮。
- 2026-10-10 用户确认的 Web 交互修订：同步歌词手动滚动后暂停跟随，停止滚动 3 秒自动回到当前播放行；拖动过程中、惯性滚动及文字选择期间不抢回位置，结束后重新计时。普通歌词保持手动滚动位置。移除正常同步歌词的 format/source 字样和“跟随当前行 / 回到当前行”按钮；服务端歌词字段、读取失败及无歌词语义保留。切歌/连接或资源 scope 改变时清理旧计时器并重置跟随；卸载清理。reduced-motion 下定位无平滑滚动。
- 同一修订允许点击同步歌词 cue，复用既有 Playback seek 合同；目标秒数为 cue.seconds − offsetMs/1000。拖动、长按与文字选择不触发 seek；断连、不可 seek、请求锁、未知时长或目标超出 [0, duration] 时不提交。不直接改写 canonical position，高亮仍消费共享展示时钟。

#### 音频规格规则

-   位深与采样率分别存储，不能把"24 bit / 96
    kHz"合并成无法查询的单一文本字段。
-   采样率使用整数 Hz 存储；界面可格式化显示为 kHz。
-   位深、采样率、编码等信息以扫描或媒体解析结果为准；未知值保持为空，不猜测补全。
-   本字段描述文件的音频规格，不代表当前 DAC
    输出规格或实际播放链路的输出格式。

### 3.2 Album（专辑）

Album 是通过专辑元数据归并得到的实体，关联一首或多首 Song。

建议保存：

-   `album_id`
-   专辑标题
-   专辑艺术家关联
-   发行年份/日期
-   封面资源引用（如存在）
-   专辑内歌曲关联

专辑内默认排序优先使用
`disc_number`、`track_number`，缺失时再采用稳定的后备排序规则。不能仅凭专辑标题合并所有同名专辑；归并还应考虑专辑艺术家及其他可用元数据。Compilation
或多艺术家专辑应允许一张专辑关联多位歌曲演唱者。

### 3.3 Artist（艺术家）

Artist 表示个人或组合。歌曲演唱者与专辑艺术家应分开建模：

-   歌曲演唱者页面按 `artist` 关联检索歌曲。
-   专辑艺术家页面按 `album_artist` 关联检索专辑或歌曲。
-   一首歌可以关联多位演唱者。
-   多艺术家字段应解析为多个关联值，而不是将整段字符串当作一个不可拆分的艺术家名称；解析规则需避免误拆合法名称。

### 3.4 Tag / Genre / Year（分类）

分类通过规范化的值与 Song 建立关联：

-   Genre 支持一首歌具有多个流派。
-   年代以可解析的年份或日期为依据。
-   无法读取或解析的字段进入"未知"分类，不应被静默丢弃。
-   分类集合的成员按 `song_id` 去重。
-   标签原始值可保留用于纠错或展示；规范化值用于检索和聚合。

## 4. Collection（播放集合）

Collection 描述一次播放操作的目标歌曲范围及顺序，不等同于持久化
Playlist。

### 4.1 Collection 来源

允许来源包括：

-   Album
-   Artist（歌曲演唱者或专辑艺术家）
-   Genre
-   Year / 年代
-   其他标签分类
-   Search results（搜索结果）
-   用户 Playlist
-   Favorites
-   整个音乐库
-   用户明确选中的多首歌曲

### 4.2 集合内容与顺序

Collection 至少需要表达：

-   来源类型及来源标识（若有）
-   去重后的 Song ID 列表
-   默认排序规则
-   本次播放是否采用随机顺序

默认顺序应符合来源语义：专辑按碟号和曲序；用户 Playlist
按用户保存的顺序；分类集合按明确且稳定的排序字段；搜索结果按搜索排序规则。随机播放应在开始播放时生成本次集合的随机顺序，避免每次刷新列表都无意改变顺序。

### 4.3 播放执行边界

Collection
负责定义"播放哪些歌曲、以什么顺序"；播放服务负责执行第一章的播放语义：

-   集合播放会替换当前 Queue。
-   从集合开始播放时，停止当前曲目并播放新集合的第一首。
-   顺序播放和随机播放集合均不要求用户逐首添加歌曲。
-   Collection 结束后，AutoPlay
    按第一章全局规则继续工作，除非用户明确选择播放结束策略（例如播放完后停止）。
-   Collection 的临时存在不意味着自动创建一个持久化 Playlist。

## 5. Playlist 与 Favorites（收藏）

### 5.1 用户自定义 Playlist

Playlist 是用户创建并持久保存的有序歌曲列表。

建议字段：

-   `playlist_id`
-   `name`
-   `created_at`、`updated_at`
-   成员关系：`playlist_id`、`song_id`、`position`

基本行为：

-   支持创建、重命名、删除 Playlist。
-   支持添加歌曲、移除歌曲和调整顺序。
-   同一歌曲是否允许在同一 Playlist
    中重复出现，需由产品规则统一定义；建议初版默认不允许重复，避免意外重复播放。
-   删除 Playlist 不删除 Song 或音频文件。
-   从 Queue 保存 Playlist
    时，按用户确认的保存范围和当前可见顺序生成持久化列表；播放历史不应自动混入保存结果。

### 5.2 Favorites（收藏列表）

Favorites 是系统提供的持久收藏列表，由现有独立Favorites表保存（完整读取合同见§5.4）：

-   系统提供固定Favorites入口，不要求用户创建Playlist实体。
-   用户通过§5.3定义的入口收藏或取消收藏。
-   Favorites
    按收藏状态维护成员关系；取消收藏只移除该列表中的关联，不删除
    Song、音频文件或其他 Playlist 中的引用。
-   Favorites 本身不因 Queue 替换、切换播放集合、AutoPlay
    补充歌曲或重启应用而清空。
-   Favorites 可像其他 Playlist
    一样打开并播放；播放时按第一章规则替换当前 Queue。
-   收藏列表按§5.4服务端完整顺序展示，收藏时间倒序、song_id倒序作稳定tie-break；本批次不提供手动排序。

### 5.3 收藏图标与交互一致性（2026-10-11，LIB-FAV-UI-001 FROZEN）

用户本次B08设计优先于旧的全列表直接收藏标志控件：正在播放页在艺术家同行靠右提供独立44px爱心收藏标志，未收藏空心、已收藏主题强调色实心，可点击切换。其余任何具体Song位置（Library、Search、Playlist、Favorites、Queue及选歌列表）仅已收藏显示实心爱心，爱心仅展示、不响应点击；未收藏不显示爱心。已有单曲菜单内提供且仅提供一个当前状态收藏项，纯文字收藏或取消收藏，可点击切换；Queue保持整行按occurrence播放，从既有更多菜单操作收藏。收藏不触发播放/菜单打开，不改变Queue。

状态来自同一完整membership owner；不可用成员仍保留已收藏标志并可取消，收藏写权限不以播放availability判定。pending/unknown不能猜造confirmed收藏标志，同song互斥，HTTP后权威重读、失败保留最后事实、unknown原key恢复、跨页不补发、断线禁写及epoch退役继承Architecture §4.1–4.2。

### 5.4 完整收藏读取（2026-10-11，LIB-FAV-MEMBERS-001 FROZEN）

用户批准B08最小只读补充。实际Favorites持久表独立于playlist_items，没有自动初始化的系统Playlist投影；本节覆盖§5.2关于系统Playlist实体及旧B08按系统Playlist读取的假设，不迁移模型或新建系统Playlist。

- Authority：PlaylistService.list_favorite_song_ids → 既有Favorites repository，按created_at DESC、song_id DESC稳定排序，包含不可用成员。
- API：GET /api/favorites/members → {song_ids: string[]}；空收藏返回200和空数组，读取失败按既有错误边界失败，不能伪装空集合。不加revision字段，继承shared cache的epoch/generation及library+playlist revision失效。
- 只读，不改变任何membership/revision、Queue、Playback、History或MPD；无新DB/schema/依赖。GET /api/favorites的可播放Collection和现有PUT/DELETE语义保持。
- Favorites展示严格按该完整服务端顺序取得Song metadata，不从可用/不可用两个数组拼接顺序。缺失metadata仍保留身份和取消入口；错误进唯一顶部。
- Proof：server/tests/api/test_favorites_members.py及web/tests/invariants/favorites.test.ts，含不可用、完整顺序、读取无领域副作用、失败/unknown/204/跨页/epoch/revision关系。

## 6. Search（搜索）

搜索用于帮助用户定位歌曲或其他音乐库对象。

建议支持的检索对象：

-   歌曲标题
-   歌曲演唱者
-   专辑标题
-   专辑艺术家
-   Genre
-   年代（按规范化年份）
-   Playlist 名称（可作为后续扩展；若纳入初版，需与歌曲结果分组展示）

搜索行为：

-   搜索结果中的具体歌曲条目按§5.3仅显示已收藏收藏标志。
-   点击歌曲条目弹出 Playback Action，不直接播放。
-   搜索结果可以作为
    Collection，但必须明确其排序规则；默认采用相关性或稳定的匹配排序。
-   搜索结果中同一 Song ID
    只出现一次，除非界面明确展示的是不同的匹配上下文。
-   搜索为空、无匹配结果或索引尚未更新时，应显示明确状态，不应伪造结果。

### 6.1 搜索归类与内容（LIB-SEARCH-VIEW-001，2026-10-11，FROZEN）

用户在B06手机反馈中明确：归类本身置顶，归类内容在同一页下方一起展示，跟随归类已有排序；A03反馈进一步要求类型用矢量图标表示，下方不再分组且歌曲不重复；默认完整结果直接显示；A04反馈要求顶部归类可点击进入已有归类详情，只显示对应对象内容，默认结果保持。

- 搜索歌曲标题、演唱者、专辑、专辑艺术家、风格、年代及现有标签。艺术家沿用Library已有演唱者和专辑艺术家共同分类，使用同一稳定ID，不制造独立的album-artist分类。
- 顶部集中展示命中的归类，以Library对应SVG类型图标加归类名称表示，不显示“专辑”“艺术家”等类型文字前缀；无障碍名称仍保留类型。下方为一个连续可播放歌曲列表，不显示归类分段标题或“其它匹配歌曲”标题。分类类型顺序继承Library的专辑、艺术家、风格、年代、标签；同类型命中沿用分类列表原顺序，不另按歌曲标题排序归类。归类内歌曲沿用现有Collection默认顺序。顶部归类入口按稳定kind/source_id进入既有Library归类详情页，只读取该对象的成员，按其服务端顺序展示，点击入口不发播放请求。包括空归类，详情沿用空状态。携带原始搜索词作为返回上下文，详情提供“返回搜索”；浏览器返回或该入口恢复原q并权威重读，完整无分组去重列表保持。详情复用既有菜单与集合动作，不新增Search PlayAll。
- Web按服务端归类顺序、组内歌曲顺序依次展开，以Song ID全局去重，只保留首次出现的位置，不另行排序；重复归类中的歌曲不再展示第二份。原搜索命中而未属于任何命中归类的歌曲，按原搜索排序追加为直接歌曲结果，并参与同一去重。后端groups仍保留完整成员和上下文，不改现有DTO或接口。
- 后端拥有归类匹配、成员和排序；新增只读`GET /api/library/search/results?q=...`返回`{groups:[{kind,source_id,name,song_ids}],song_ids}`。kind为albums/artists/genres/years/tags；source_id来自现有summary，song_ids是已有Collection的可播放成员顺序。原`GET /api/library/search`的Collection合同保持。缺q沿用422，空白返回空groups/song_ids；规范化查询为trim/casefold，名称精确/前缀/子串可命中，结果按上述归类排序；读不改变Queue、Playback、History或revision。
- Web通过同一Library cache读取该结果和Song资源，不建本地匹配索引、不猜造归类成员、不补不可用项；q保留于route，空白/快速改词/清空、返回重读及epoch/revision/generation迟到保护沿用Architecture §4.1。未知/失败只进唯一顶部通知；GET不能恢复写权限。
- Song仍复用统一播放菜单，无Search PlayAll；Favorites/star依B08接入，Playlist名称不扩入B06。本合同仅扩大B06必要搜索表示，不改变B01–05已接受行为或推进未来Batch。
- 证明：真实SQLite/Service/API的归类稳定身份、分类及成员顺序、专辑艺术家/标签/多归类命中、完整归类成员上下文/直接歌曲尾部、空白/无匹配及读取不改业务域；Web真实fixture→decoder/cache→顶部SVG图标和名称、单列表首次出现去重及尾部直接歌曲、点击归类只读对应成员及返回搜索、迟到拒绝、查询与菜单关系。手机仅复核新增归类表示，已接受其它操作不重复要求。

## 7. 扫描与数据更新

音乐库扫描负责发现文件、解析元数据并更新 Song 及其分类关联。

规则：

-   新文件被识别后创建或匹配 Song，并更新分类索引。
-   文件移动或重命名时，尽可能根据可用文件信息识别为原 Song 并更新
    `file_uri`，避免无必要地破坏 Playlist、Favorites 和 History 引用。
-   文件确实被删除或无法访问时，将其标记为不可用或移除出当前音乐库索引；是否保留历史记录中的元数据应与第一章历史语义一致。
-   元数据变更后，更新 Album、Artist、Genre、Year 等关联。
-   标签缺失、格式错误或解析失败应可被记录；未知值进入相应的"未知"分类。
-   歌词和音频技术信息应在扫描时读取或更新。扫描失败不能覆盖已有有效数据为空，除非确认文件中确实不存在该信息。
-   不允许把文件路径变化直接视为歌曲内容变化并无条件生成新的 Song
    ID；匹配策略将在实现设计中明确。

### 7.1 Library / Playlist revision 合同（Task 6，2026-10-03）

本节来自当前对话人工决策 G6-02 / A；revision 是缓存失效标识，不是事件重放游标或业务 CAS token，不改变既有 Queue revision。

- **Preconditions**：单个服务进程提供 Library/Playlist 的业务写入口与读取；系统初始化及持久数据载入后开始对外服务。
- **Authority / Source of Truth**：领域 Service 确定可观察内容变化，事务 owner 确定提交；Library/Playlist 数据仍由其持久模型拥有。每次进程启动生成新 `epoch`，两个非负整数计数 `library_revision`、`playlist_revision` 从 0 开始；不把时间戳当版本。
- **Expected State Delta**：一个最外层事务成功提交时，对最终内容相对事务前确有变化的每个域最多递增一次。Library 内容包括 Song 身份、定位、availability、元数据、分类、歌词及 artwork reference 等可观察资源；仅扫描时间、内部审计时间或错误日志变化不递增。Playlist 内容包括列表存在性、名称、成员和顺序，Favorites 属于同域。事务中改后又恢复原内容属于 no-op。
- **Must Remain Unchanged**：未变化域计数不变；业务的 Queue/History/播放状态及 Playlist 成员保留语义不因版本机制改变。歌曲元数据或 availability 改变只递增 Library 域，不伪造 Playlist 成员变化；Playlist 展示缓存必须同时关注 Library revision。
- **Transaction Boundary**：计数与最外层提交后的业务数据按架构 Spec §12.1 同时可见；嵌套操作、批量扫描、save Queue 的逐成员操作不对外暴露中间版本。禁止在已可读取新数据之后异步补增版本。网络交付在该边界外。
- **Failure / Rollback**：失败、提交前取消、outer rollback 不消耗版本且无成功变更通知。提交后的发送失败/取消不能撤销数据或版本。进程崩溃后用新 epoch 开始，不尝试恢复旧进程计数。
- **Retry / Idempotency**：未提交失败可正常重试；提交成功的同请求 replay 不重复修改版本。无变化扫描、同名重命名、重复设置同一收藏状态等 no-op 不递增；本身属于验证错误的操作仍按原错误合同处理，不能改成成功 no-op。
- **Revision / Ordering**：同 epoch 内各域单调不减，变化事务 +1；跨 epoch 不比较大小，客户端必须废弃旧版本判断并整体刷新。Library/Playlist/Queue 的数字互不比较。内部时间戳不计入内容变化；直接承担资源语义的业务字段仍计入。
- **Observable Result**：snapshot 与领域失效通知携带相应 epoch/revisions；无内容变化扫描仍保留原有扫描完成事件及 MPD update error 可见性，不能用“revision 未增”吞掉扫描结果。原 Library 扫描 commit → optional MPD update → completion event 顺序不变。
- **Executable Invariant Proof**：新增真实 Repository/Service/outer transaction 测试，比较提交前后资源、计数和事件，覆盖成功、no-op、改后恢复、双域事务、嵌套/批量、terminal failure、rollback、取消、retry/replay、发布失败及重启 epoch。用 barrier 验证新数据不可搭配旧 revision；availability 改变不丢 Playlist/Favorites/History 引用。测试由 Task 6 Batch Plan 分配，当前仅为待执行证明义务。

### 7.2 自动MS/MPD曲库同步（LIB-MPD-SYNC-001，2026-10-11）

用户确认：保留现有两种URI表示并做最小映射；手动扫描/被动发现后自动及时同步并自动更新页面。同步活动只进入WEB-UI-NOTIFY-001的AppBar中心，不在Song行/页面另加同步说明或图标。业务文件availability与同步状态独立，不修改现有AVAILABLE/MISSING/UNREADABLE含义。

**权威与顺序**：文件系统拥有真实文件，Library Repository拥有MS索引，MPD拥有自身索引；统一同步Service拥有协调进度。发现→debounce/合并→扫描提交→登记SYNCING并通知→MPD update→等待更新结束→精确URI确认→SYNCED/FAILED。扫描数据的revision在提交时立即可见；沿用§7.1 commit→optional update→completion event，不延迟revision登记，不把新同步事件当原扫描完成事件。MPD失败不回滚MS已提交Song，不伪造History/Queue变化。

**及时性与合并**：复用500ms debounce。单实例变化发现每2秒检查文件路径/size/mtime签名，仅变化进入增量扫描；不每2秒重新解析/哈希全库。此默认轮询方式减少NAS挂载监听依赖，真实文件树性能在部署Gate测量；若规模导致不能满足检查预算，再单独批准优化，不迁移URI。12小时完整校准兜底遗漏，手动扫描进入同一协调器。首次启动自动扫描/确认；无可读根时失败保留旧索引。文件尚在写入导致解析失败可重试，稳定后收录。变更正在处理时新到变更进入下一generation，不被旧轮完成清除。移动/删除继续既有身份/引用规则；确认更新后的精确新URI，删除确认旧URI不在MPD索引。

**MPD确认**：Port新增只读has_library_uri(song_uri:str)->bool，Mock/真实/Verified实现同一合同；由独立同步Service消费，不通过Queue查找代替曲库查询。协议实现依据目标允许命令验证精确file字段，不整库拉取作为每曲确认。update返回不是成功证据；更新状态每1秒有界读取，只有update已接受、无正在更新且本generation目标URI符合存在/缺失预期，才SYNCED。更新非常快而未观察到busy也可由精确URI确认。每轮确认预算60秒；超时FAILED，自动按2/5/15/30秒封顶间隔重试，断线后恢复继续；不忙循环，不自动重做用户播放/收藏等mutation。MPD更新可能不改变曲目内容，不因此虚增Library revision。

**状态**：IDLE/SYNCING/SYNCED/FAILED；服务启动时IDLE未证明已同步，首次确认后才SYNCED。每轮generation单调递增并带activity_id、trigger、pending_count、confirmed_count、failed_count、updated_at及安全错误码/短原因；确认只覆盖本轮捕获目标，迟到旧结果不覆盖新轮。同一generation重试更新同一活动，不制造无限活动列表。重启丢弃运行时成功证明，重新扫描/确认，不持久化旧snapshot为权威。

**传播**：FullStateSnapshot增量字段library_sync承载当前完整同步状态；独立失效domain library_sync共用现有epoch/sequence/初始snapshot及bounded sender机制。同步状态改变只推进sequence，不推进Library/Playlist revision；Library索引变化仍由原library域刷新资源。一次提交登记扫描可见变化与SYNCING，不能展示新Song却仍宣称旧轮同步成功。snapshot读取无扫描/MPD控制。Web自动重读，不靠刷新页面；旧epoch/sequence/generation结果丢弃，断线最后状态明确过期，重连完整首帧恢复。

**不变项与证明**：音乐文件只读；同步不播放/清空/重排Queue、不更改Playlist/Favorites/History；已有业务控制成功仍需原确认。真实SQLite＋Scanner＋状态协调器＋Fake/Mock Port测试覆盖提交/通知/更新/精确确认、update错误/超时、断线恢复、并发新文件、no-op、移动删除、取消和重启；真实NAS至少新增一份用户自有测试曲目并观察无需刷新完成同步。完整日志归MIN-LOG-001，短活动展示归Visual。

## 8. 与第一章播放模型的接口

建议以统一的服务端接口概念连接浏览层与播放服务：

-   `get_song(song_id)`：读取歌曲详情。
-   `get_collection(source, filters, order)`：根据来源和筛选条件生成歌曲集合。
-   `play_collection(collection, mode)`：将集合交给播放服务，并按第一章规则替换
    Queue。
-   `apply_playback_action(song_id, action)`：执行 Play Now、Play Next
    或 Add to Queue。
-   `set_favorite(song_id, is_favorite)`：添加或移除 Favorites 关联。
-   `create_playlist(name)`、`update_playlist(...)`、`delete_playlist(playlist_id)`：管理自定义
    Playlist。
-   `save_queue_as_playlist(name, queue_selection)`：将指定 Queue
    内容按确定顺序保存为 Playlist。
-   `search_library(query, filters)`：检索音乐库对象。

以上是逻辑接口定义，不是已确定的 HTTP
路由或函数签名。服务端仍是播放状态和 Queue
的权威来源；客户端展示状态并提交用户操作。

## 9. 异常与一致性规则

-   已删除或不可访问的歌曲不应被悄悄当作正常可播放文件；播放服务应按第一章规则处理失效条目。
-   收藏状态更新失败时，客户端不得假装持久化成功；应提供失败反馈并重新同步服务端状态。
-   多页面的收藏爱心状态必须来自同一收藏状态源，避免页面之间状态不一致。
-   歌曲元数据更新不得意外清除 Favorites 或用户 Playlist 的成员关系。
-   同名歌曲、同名专辑和多艺术家歌曲应依赖实体关联与元数据规则处理，不能仅靠展示字符串判断身份。
-   空集合应有明确的空状态，不应以随机歌曲悄悄替代用户明确选择的空集合。

## 10. 验收标准

1.  同一首歌曲在专辑、歌手、年代、Genre、搜索和 Playlist 中引用同一个
    Song ID。
2.  Song
    可以保存歌词内容、歌词格式、位深、采样率等音频信息；未知值不会被猜测填充。
3.  LRC 时间戳得到保留，能够供同步歌词功能使用。
4.  分类集合可按来源规则生成稳定、去重的歌曲列表，并支持顺序或随机播放。
5.  所有歌曲位置按§5.3显示已收藏爱心；收藏与取消收藏后，各页面状态保持一致。
6.  收藏列表持久存在，且不随 Queue 或临时 Collection 变化而清空。
7.  Player爱心和单曲菜单收藏项只切换收藏；普通歌曲条目弹出Playback Action，Queue按既有occurrence合同播放。
8.  Playlist 的增删改和排序不影响底层音乐文件。
9.  扫描更新元数据、路径或分类后，尽可能保留 Song 身份、Favorites 和
    Playlist 关联。
10. 搜索结果能形成 Collection，并遵循统一的歌曲操作和播放规则。

## 11. 本章尚待后续章节明确的事项

-   数据库表结构、索引与唯一性约束。
-   文件路径变化时 Song ID 的可靠匹配算法。
-   歌曲/专辑/艺术家元数据规范化与合并策略。
-   搜索匹配算法、过滤器及排序细节。
-   收藏列表默认排序是否采用"最新收藏优先"。
-   初版是否允许同一歌曲在同一自定义 Playlist 中重复出现。
-   实际 API 路由、请求/响应结构、实时同步方式。


### 2026-10-11 B08 A02展示修正（用户反馈优先）

Player爱心保持艺术家同行，向左8px/向上3px微调，SVG从22px放大到26px；未收藏明确使用--text-primary描边，已收藏仍用--accent。所有单曲菜单收藏/取消收藏仅纯文字，不显示爱心、不使用蓝色，字体颜色/对齐沿用其它菜单项；按用户最新反馈，Queue单曲菜单与Library共用样式：无按钮边框、文字左对齐、相同尺寸/间距/歌曲信息排版；清空和保存弹窗保持原样。其它位置已收藏展示爱心及所有状态/写权限/请求/恢复功能不改。只复验这两类展示，不重开已认可功能；B08手机Gate仍待本轮反馈。
