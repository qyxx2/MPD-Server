# Task 9 B08 acceptance — T9-B08-A01

日期：2026-10-11（Asia/Shanghai）。范围仅B08；B01–07 CLOSED / HUMAN PASSED保留，B09/B10未推进。当前B08 **实现完成 / 自动Gate PASSED / CLOSED / HUMAN PASSED**。真实MPD/NAS/DAC NOT RUN，PWA DEFERRED。

## 前置、合同与用户裁决

核对入口contract-audit及web-batch-plan、主Plan Task9、Library §5/7、Playback既有Song/Queue动作、Visual WEB-UI-*、Architecture §4.1–4.3/§12/§19.5及手机方法H07/H04/H10、M01/02/05。当前feature/task-9-web / HEAD14c6239，已有dirty B01–07成果保留；未创建替代checkout或另一venv。

1. 用户确认：Player艺术家同行靠右直接切换收藏；其它具体Song位置仅已收藏展示、不能直接切换；既有单曲菜单提供一个当前状态收藏项。Queue整行occurrence播放保持，通过更多菜单收藏。随后用户明确改用爱心、实心颜色协调。Library §5.3 **LIB-FAV-UI-001 FROZEN**，SVG空心/实心、统一现有--accent（蓝色），无五角星或额外杂色。
2. 实际模型没有系统Favorites Playlist实体，Favorites独立表且GET /api/favorites拆分可用/不可用，无法恢复完整顺序。用户批准最小只读GET `/api/favorites/members` → `{song_ids}`，Library §5.4 **LIB-FAV-MEMBERS-001 FROZEN**；复用既有Service/Repository按created_at DESC、song_id DESC返回完整成员。不迁移DB/schema，不改PUT/DELETE、revisions、播放或History。
3. 独立审阅的metadata-error modal键盘问题由Minor重评为Important：aria-modal却无法获得焦点和直接Escape退出会使必要取消入口不可达；本批次修正初始焦点、Tab约束、Escape和opener恢复。无deferred finding。上述裁决代价均由合同/proof约束；没有改变未来Batch或公开写接口。

## Contract Matrix / owner / proof

| ID与权威 | Owner及范围 | Fresh proof / 结果 |
|---|---|---|
| T9-FAV-001 / LIB-FAV-MEMBERS-001 | api/playlists.py + FavoriteMembersResponse；既有PlaylistService/Repository，无额外数据库模型 | test_favorites_members.py：404 RED→GREEN，空集合、完整有序含MISSING、Collection分离、读取不改revisions/Queue/History/Playback、DELETE后读取；真实API生成favorites.json golden |
| T9-FAV-001 / Architecture §4.1–4.2 | stores/favorites.ts薄包装同一playlists cache，AppShell持久owner；library+playlist revision、epoch/generation及通知共用 | favorites.test.ts：same song pending、无乐观事实、失败保留、unknown原keyretry、断线拒写、204/read-failure仅read、跨route不补发、epoch退役、迟到旧成员拒绝 |
| LIB-FAV-UI-001 / WEB-UI-* | FavoriteIcon、SongRow/Menu、Player、Queue、Library、Search、Playlist/选歌、Favorites及metadata缺失占位 | 跨页同song展示、未收藏行无图标、只Player/菜单互动、静态爱心点击零播放请求、单状态菜单、完整不可用取消、metadata失败保留身份/取消入口；收藏不改播放 |
| T9-FAV-001 / Library §5.2–5.4 | FavoritesView完整服务端顺序，Song metadata仍使用既有Library cache，原因唯一顶部；播放全部/随机交FAVORITES source | 完整['c','a']含不可用顺序保持；source交后端，不提交浏览器拼出的成员；真实后端golden解码与重复/空id拒绝 |
| Player保护 / Architecture与既有presentation合同 | PlayerView新收藏控件仅新增Artist右侧，handoff/unknown/Player action pending禁用历史presentation target | 独立审阅Important精确RED enabled→GREEN disabled；既有Player title/source/progress保持，新增disabled状态单独断言 |

新文件：FavoriteIcon.vue、FavoriteUnavailableMenu.vue、FavoritesView.vue、favorites.ts、favorites.test.ts、favorites.json、test_favorites_members.py。整合existing AppShell/resourceWire/playlists cache/router/Player/Queue/Song menus/Playlist picker/Library入口及定向样式。未改歌词、clock、seek、播放转移、Queue移动/保存、Settings或依赖。

## 自动与环境证据

- 环境fresh验证：现有.venv Python3.14.4 / pytest9.1.1 / Ruff0.16.9；server/requirements.txt已读，未安装/升级/修改依赖，未用system Python或Docker。
- Backend精确完整成员API/golden **1 passed**；指定 `test_favorites_members.py`、`test_playlist_reads.py`、`test_playlist_web_fixture.py`、`test_playlist_relationships.py`、`test_realtime_playlist.py`、`test_playlist_service.py` **23 passed**。先精确节点再文件再指定关系；既有Starlette/httpx弃用warning单列，不修改环境。没有生产Service/DB mutation变更，未重复完整后端；B06完整1451只属历史证据。
- Web `favorites.test.ts` **9 passed**；指定 Favorites/Playlist/Song actions/Queue actions/Search/resource-cache/global-notices 加受影响Player controls/notices **124 passed（9文件）**。
- 完整Web `npm --prefix web run test -- --run --maxWorkers=1` **279 passed（25文件，43.77s）**，包括静态Queue爱心点击隔离修正。随后只补Playlist缺metadata占位行的展示爱心，并撤销不必要的其它Player notice测试setup改动；最后 Favorites/Playlist/Player notices **26 passed**，未因低影响展示补充重复全量。
- `npm --prefix web run typecheck`及最终T9-B08-A01 production build通过；Ruff定向api/playlists.py、schemas.py及新backend test通过；git diff --check通过。
- 独立只读审阅：无Critical；Player retained-media target Important和fallback modal焦点问题均精确RED→GREEN并指定/全量回归。额外自查发现Queue静态爱心点击继承整行播放，test RED一条POST→GREEN零POST；保留整行播放与菜单原焦点顺序。无遗留Critical/Important/Minor。

早期失败区分：Library测试默认albums而非songs、旧实时DTO字段名history/playback假设是test/fixture问题；新增共享Favorites GET曾占用旧逐响应transport序列，现有player/shell测试support提供独立空Favorites读取（与既有Library reads相同边界），保留原mutation/assertions。少数Player即时通知测试等待初始资源读完再检查播放/歌词自己的通知，不削弱原断言。冻结identity HTML只归一化新增爱心disabled属性并另断言handoff disabled。未删除/skip/xfail测试。

## LAN与辅助预检

当前地址：[B08验收](http://10.104.60.177:5185/)，title `MPD-Server · T9-B08-A01`；收藏直达 [Favorites](http://10.104.60.177:5185/library/favorites)。当前wlan0地址已核对，非沿用旧批次URL。

自有runtime `.superpowers/sdd/task-9-b08/runtime`：native backend8011显式Mock、全新自有SQLite；preview5185同源REST及WS代理。旧Batch服务/数据库未删除或修改。预置当前normal已收藏、unknown/MISSING已收藏；long在Queue有两个occurrence且未收藏。预置Playlist含long/unknown/normal；搜索词「夜航」可查看同song。播放时钟使用已接受advance_clock=True，不访问live MPD。

最终LAN与本地产物字节一致：HTML SHA256 `d27beda79963f5ddda84740d92c17a51e7dba3747c83f1eb31128d7f29541b83`；JS index-1p-GGSCM.js `4c2009c4843a7488543f72af6142ae500281980e6354541d95785972452cca9b`；CSS index-S6-aim3G.css `860b18f5eec75d05dc095d32da4851be2d1d788c2739c516d190357d72adf771`。同源members含['acceptance-unknown','acceptance-normal']，GET favorites不可用数组含unknown，WS首帧snapshot通过。

辅助浏览器viewport设置320×650，当前宿主缩放对应DOM内容宽291 CSS px，scrollWidth同291无横溢；不冒称原生320 CSS px截图。Player爱心约44×44，艺术家同排最右侧，颜色rgb(130,213,248)=既有--accent。Favorites不可用/normal两展示爱心均可见，行内无直接toggle/五角星；Queue静态爱心点击仍paused，更多菜单仅一个主题色取消收藏项，整行和原删除焦点不变。桌面辅助不替代真机，viewport临时覆盖恢复。

## 最少手机卡与剩余Gate

同一Wi-Fi，打开当前URL并确认T9-B08-A01；无需终端/DB/devtools。

1. Player艺术家行右侧爱心取消再收藏：空心/实心及颜色协调；不切歌或改变播放状态。进入Queue，当前行同步实心，点展示爱心无操作；长标题两重复项初始无爱心，通过其中一个更多菜单收藏，两项同步显示。
2. 音乐库→全部歌曲、搜索「夜航」、预置歌单、收藏页往返/刷新，已收藏一致、未收藏行无标志；普通单曲菜单只有当前状态收藏项。收藏页的MISSING歌曲仍显示爱心且能在菜单取消；在预置歌单同曲菜单可以重新收藏，播放入口仍受不可用门禁。检查长文字与菜单触摸可达，不被导航遮挡。
3. 已加载后断Wi-Fi，Player及菜单收藏不能写、保留最后事实且顶部说明；恢复连接后正常切换一次并跨页确认，没有离线补发或假成功。

H07/H04/H10、M01/M02/M05 **HUMAN PENDING**。自动测试负责失败/unknown、key/epoch/迟到响应，不要求手机伪造HTTP错误。用户反馈前B08 OPEN，B09/B10不推进。

既有ArtworkRef单Song REST500批次外保持，metadata失败有顶部恢复与完整取消入口；真实MPD/NAS/DAC NOT RUN、PWA DEFERRED。没有commit/push/PR/merge，现有dirty工作与.venv保留。


## 2026-10-11 A02用户展示整改，等待手机复核

用户要求优先：Player爱心向左8px、向上3px，SVG22→26px；未收藏明确使用主题正文色描边，修复原生button默认黑色导致不可见，已收藏保留单一主题accent。所有单曲菜单收藏项仅文字、与其它项同色。用户最新要求覆盖此前Queue居中要求：Queue单曲菜单与Library共用宽度、背景、圆角、无按钮边框、左对齐字号/间距以及歌曲标题/艺术家/专辑排版。仅menuItem分支使用共享样式，清空/保存弹窗及操作/锁定/恢复行为保持。

Fresh定向Favorites9 + Queue actions37 + Queue save6 + Song actions6 = **58 passed / 4 files**；typecheck、生产build通过。纯展示整改未重复完整Web/后端，A01自动证据仍属原轮次。LAN同源REST/WS通过，保留用户当前收藏状态（members只有acceptance-unknown），未重置数据。最终HTML SHA256 `8ea2932ef2c0df9a586863ba6aedb3250cb9862d97881391088237533361c703`；JS index-BIK6_FZP.js `2d69d98a6d68deb87966f2b3317c22bb23f7d0547bb5c621140fcbf560eea2d8`；CSS index-nWypQcdr.css `8f7a27c9e31b766853a120249649d3dd32d4f14c6bd75fe46111192d32060290`。

辅助浏览器实际页面核对：Library与Queue菜单均271.994px宽，按钮border0/透明背景/left/16px/9.6px padding/正文色rgb(243,247,252)，收藏项无SVG；Player未收藏fill none/stroke currentColor/26px、margin-right8px/translateY(-3px)，空心描边正文色。菜单关闭仍恢复更多按钮焦点。此为桌面辅助，不能替代手机反馈。

当前手机地址 [B08 A02](http://10.104.60.177:5185/)，刷新确认title `T9-B08-A02`。最少复核：① Player空心/实心爱心可见、大小和位置合适；② Queue更多菜单与Library歌曲菜单的边框、文字对齐/颜色/间距一致，收藏项无爱心。此前未反馈的A01功能Gate继续保留。**B08 OPEN / HUMAN PENDING**，H07/H04/H10、M01/M02/M05待用户反馈；B09/B10不推进，无commit/push/PR/merge。


## 2026-10-11 最终关闭：用户验收通过

用户在T9-B08-A02整改交付后明确：“验收通过。无需重复测试。更正需要的文档即可”。据此将B08记为 **CLOSED / HUMAN PASSED**，必要H07/H04/H10及M01/M02/M05手机Gate按本次整体验收认可关闭，不编造逐项手机操作日志。现行实现包含Player空心/实心爱心与位置修正、其它位置仅已收藏展示、菜单纯文字、Queue单曲菜单与Library共享样式，以及获准的最小只读完整收藏成员接口。

自动证据沿用所属轮次：A01指定Web124/完整279、后端指定23；A02展示整改定向58、typecheck/build、产物字节/REST/WS与辅助DOM核对。此次仅更新必要文档并检查文档差异及diff check，未重跑测试、构建或运行环境验证，不宣称新增自动证据。

B01–B08 CLOSED，B09/B10未启动，Task9整体未完成。真实MPD/NAS/DAC NOT RUN、PWA DEFERRED、G9-02及既有ArtworkRef REST500批次外限制保持。原dirty成果保留，无commit/push/PR/merge。此前OPEN/HUMAN PENDING和验收URL段落保留为历史，当前状态以本节为准。
