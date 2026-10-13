# Task 9 B07 Playlist acceptance — T9-B07-A01

日期：2026-10-11（Asia/Shanghai）。当前 **B07 CLOSED / HUMAN PASSED**；用户明确“验收通过。更正相关文档。不需要额外测试。”，必要手机Gate按对T9-B07-A01的整体认可关闭。B01–B07 CLOSED / HUMAN PASSED；B08–B10未启动，Task9整体未完成。下文交付时等待反馈的描述保留为历史，最新关闭依据见末尾。

## 范围与前置

实际分支feature/task-9-web，HEAD14c6239；既有dirty B01–B06保留。核对入口audit/Batch Plan、主Plan Task9、Library §5/§7.1、Architecture §4.1–4.3/§12/§19.5、Playback歌曲动作及唯一Visual WEB-UI-*、手机方法H06/H04/H10与M01/M02/M03/M05。B06最终用户关闭成立；既有Library/SongRow/shared tasks/cache真实存在，Playlist路由原为占位。本批次无未关闭前置或需要新产品决策的合同缺口。

实现：歌单列表/详情、创建/重命名/删除、Library歌曲选择添加（重复交服务端拒绝）、完整成员移除/拖动及键盘排序、空列表、系统歌单改名删除保护。SongRow沿用统一菜单，点行不自动播放，无B08星标。拖动只改草稿；稳定原行、跟指投影、插入标记、无效释放/回原位不提交。名称和排序草稿离页丢弃；已发intent继续由持久TaskActions拥有。

新owner：PlaylistView、playlistActions、playlistResources。现有AppShell持久装配/最终dispose同一个playlists cache；依赖library+playlist revision，新增路径decoder和PlaylistResource，Library入口及router接线，CSS只增加Playlist规则。后端生产API/Service/DB schema/依赖均未更改，仅新增真实DTO fixture proof。所有原dirty成果保留，无commit/push/PR/merge。

## 合同追溯及Gate

T9-PLAYLIST-001（mutation/resource/representation/propagation）→Library §5/§7.1、Architecture §4.1/§4.2/§12/§19.5及Visual WEB-UI-* → PlaylistView/playlistActions/playlistResources、shared playlists/resourceCache/taskActions，既有PlaylistService/Repository/API → web playlists.test.ts、后端playlist reads/service/relationships/realtime/idempotency及新真实DTO fixture。

- Preconditions/Authority：当前可信realtime baseline+writable，详情与成员完整匹配且fresh；Service/SQLite持久成员/name/order为权威，cache仅投影，系统保护由服务端裁决。
- Delta/Unchanged：允许目标歌单存在性、name、成员和完整顺序及playlist revision变化；不改Song/文件、Queue/Playback/History、其它歌单。服务端关系测试对版本、事件、rollback/replay及不变域负责。
- Confirmation/Event/Transaction：HTTP成功确认操作；204不从payload猜资源，统一refresh及REST强制重读列表/对应详情和成员；既有Service最外层事务提交/事件，不增加MPD动作。
- Failure/Retry/Observable：409重复或成员不匹配保留最后事实并重读，顶部typed错误，排序需重新拖；unknown原method/path/payload/key，confirmed读失败只读；离页不补发，epoch退役，GET不恢复写权限。未解决事项仅在唯一顶部入口显示。
- Ordering/Lifecycle：library/playlist marker、epoch/generation/trust/成员变化取消已知旧drag；迟到资源由同一cache代次拒绝。继承G9-02：未送达的并发变化不获严格expected-version保护，未暗加字段。

| Gate | 本轮证据 | 状态 |
|---|---|---|
| Contract / implementation | 上述现行合同与实际owners，无新API语义 | DONE |
| 精确RED→GREEN | 原占位完整成员[]→[b,c,a]；核心4行为先RED后GREEN；review回原行仍PUT1→0 | DONE |
| Playlist Web | 9 passed，含unavailable/duplicate/system/CRUD/204/readFailed/unknown跨页/断线/epoch/旧响应/冲突与drag取消 | PASSED |
| 指定Web关系Gate | playlists + song-actions + resource-cache + global-notices：36 passed | PASSED |
| 完整Web | 24文件270 passed，单worker，35.02s，exit0（review修正后） | PASSED |
| 后端精确/文件 | playlist_songs单节点1、playlist_reads文件2、新golden fixture1 passed | PASSED |
| 指定后端关系Gate | playlist_reads、playlist_service、playlist_relationships、realtime_playlist、idempotency、playlist_web_fixture：25 passed | PASSED |
| 类型/构建/Ruff/diff | typecheck、生产build、定向Ruff新Python测试、git diff --check exit0 | PASSED |
| 独立审阅 | 无Critical，唯一Important回原位提交旧目标已精确RED→GREEN并回归；无deferred Minor | RESOLVED |
| LAN/API/WS | 当前真实LAN/产物字节一致、完整成员REST、WS snapshot | PASSED |
| H06/H04/H10、M01/M02/M03/M05 | 用户对T9-B07-A01明确整体验收通过；不编造逐项操作日志 | HUMAN PASSED / CLOSED |
| 真MPD/NAS/DAC | 本轮仅自有SQLite+显式Mock；未跑实机 | NOT RUN |
| PWA | 继承延期 | DEFERRED |

环境：现有.venv Python3.14.4/pytest9.1.1/ruff0.16.9，无安装/升级/Docker。后端仅既有Starlette/httpx弃用warning，不据warning修改依赖。临时golden捕获脚本最初绕过pytest observer隔离导致自有临时SQLite锁，恢复相同autouse隔离+显式Mock后解决；Song扫描时间固定为既有Library golden的方法，真实DTO再比对GREEN。早期missing fixture/import和夹具API/DOM修正不算业务RED；原占位完整成员和review精确失败为行为证据。

完整后端未重跑：无生产Python变化，本批次要求25项已fresh执行；B06完整1451属历史，不冒称本轮结果。新测试也不代替上述指定服务/关系Gate。

## LAN与辅助浏览器

地址：[B07歌单验收](http://10.104.60.177:5184/library/playlists)，页面title `MPD-Server · T9-B07-A01`。当前wlan0 IP10.104.60.177，非照抄历史。自有runtime .superpowers/sdd/task-9-b07/runtime，backend8010显式Mock、全新自有SQLite（旧文件未删除），preview5184代理同源/api及WS；已有旧Batch服务未改。为手机预置「验收样本 · 含不可用歌曲」3成员（long/unknown/normal），另可自行新建空歌单。

LAN字节SHA256：HTML 5d5a8a90648fbc27f59f20332bd89a5fa7ed1e37b1e8728ba13c50a1a243e69b；JS index-CFRN1q6A.js ceb4d48cb3a797fc6069941773f4c400d41722ebe26622c90384710dca544a75；CSS index-XRXmgz0W.css 492137f275ba136d7719446cd45ca7ae14aa33ba35be4ba46a9b3785415881a3。REST列表/detail/song_ids完整对应，MISSING保留；/api/realtime首帧snapshot通过。

实际浏览器320×650辅助验证：document width/scrollWidth均320；3成员、长文本省略、独立排序/移除按钮约44CSS px可点；名称输入聚焦/滚动可达且长名不扩宽，输入与保存区域在底部导航上方。使用统一深色token，页面名/框架不重建；取消草稿后返回列表，未写入手机样本。viewport临时覆盖已恢复。桌面辅助不能证明手机软键盘/手指拖动，不能关闭HUMAN Gate。

## 最少手机卡（同一Wi-Fi，无终端/DB/devtools）

1. 创建歌单，输入长中文名称；打开空歌单，添加两首歌曲，再对其中一首点一次加入。应只有两成员，重复原因在顶部详情；键盘打开/收起后输入和保存可达。
2. 用左侧≡拖动两首的顺序，再试拖走后回到原行松手；离开到Queue再回来/刷新，顺序一致。点歌曲只打开现有菜单；明确选择动作才播放。可在预置样本看到MISSING仍是完整成员且可排序/移除，播放禁用。
3. 对新建歌单移除一首、重命名、返回再打开，结果一致；删除该新建歌单，列表与刷新结果一致。无需删除预置样本。
4. 已加载页面断Wi-Fi，确认业务控件禁用、原因/恢复仅顶部；恢复Wi-Fi等重新连上再操作一次，切Queue后返回。没有离线补发/重复成员，壳/导航不跳动。原key/unknown及已发pending跨页由上述自动proof负责，无需手机读网络字段。

请反馈是否通过，以及有问题的步骤。收到必要手机反馈前保持B07 OPEN，不推进B08。G9-02保留；既有ArtworkRef单Song REST500仍批次外未修复；真实设备NOT RUN/PWA DEFERRED。


## 2026-10-11 B07最终关闭：用户验收通过

用户在T9-B07-A01交付后明确“验收通过。更正相关文档。不需要额外测试。”。据本次整体反馈，B07 **CLOSED / HUMAN PASSED**，必要H06/H04/H10及M01/M02/M03/M05手机Gate关闭；不追加或编造逐项真人操作日志。上文OPEN/等待反馈为当时交付状态，不作为当前阻塞。

B01–B07 CLOSED / HUMAN PASSED；B08–B10未启动，Task9整体未完成。自动证据仍归属B07实施轮次：Playlist9、指定Web36/完整Web270、指定后端25及typecheck/build/Ruff、独立审阅修正和LAN预检。本次仅更正验收记录与进度入口，检查文档差异和git diff --check，没有重跑测试、构建或环境验证，不宣称新增自动验证结果。

feature/task-9-web / HEAD14c6239重新核对，原dirty保留；本轮不改产品、测试、环境、依赖或Mock场景，不清理运行文件，不推进B08，无commit/push/PR/merge。G9-02限制保留，真实MPD/NAS/DAC NOT RUN、PWA DEFERRED，ArtworkRef单Song500仍为批次外未修复项。
