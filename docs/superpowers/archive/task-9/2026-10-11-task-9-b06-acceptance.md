# Task 9 B06 Search acceptance

当前状态（2026-10-11）：**B06 CLOSED / HUMAN PASSED**。用户认可A04最终版本；最新关闭依据见文末。下文各轮OPEN/PENDING均为历史，B01–B06已关闭，B07–B10未启动。
A01交付时历史状态：2026-10-11（Asia/Shanghai），**B06 OPEN / HUMAN PENDING**；B01–B05保持CLOSED，B07–B10未推进。feature/task-9-web / HEAD14c6239及既有dirty成果已核对并保留；未commit/push/PR/merge，未修改依赖、环境、DB schema或服务端业务算法。

## 范围与合同

只实现Library搜索入口、`/library/search?q=...`与查询生命周期。输入/清空更新route q；空白不请求、不留旧命中；返回/刷新保留q并重新读取Collection。使用已有Library cache的单key强制读取，不失效其它Library资源。Collection IDs按服务端顺序读取Song，共用B05 SongRow、三项动作及持久TaskActions；不建本地索引、不补unavailable IDs、不加Search PlayAll、Playlist或Favorites。

T9-SEARCH-001 → Library Spec §6 / Playback §4.3 / Architecture §4.1–4.3、§12、§19.5 / Visual WEB-UI-* / audit §5 → SearchView、parseLibraryResource、既有Library/resourceCache → `search.test.ts`四个关系节点及`test_search_web_fixture.py::test_search_web_fixture_from_real_resources` → 本轮fresh验证。只有本地query结果变化，Queue/Playback/History/revisions不因搜索读取而改变；mutation仍沿用T9-SONG-001。查询serial+path+epoch保护页面结果，同一缓存generation/revision保护Collection/Song；GET不恢复写权限，失败只进顶部通知。

实施裁决：执行已批准Batch设计，沿用包含未提交前置成果的现有feature checkout；不复制至空worktree、不自动安装环境、不提交；ledger继续保留。共享缓存增加可选`read(key,{force:true})`以履行进入/返回权威重读，仅失效该key，旧flight遵守原generation拒绝合同。若裁决错误的影响为重复资源读，本轮返回/缓存关系测试负责约束。

## 自动证据

- 新Search四节点先RED（占位route无输入和结果），最小实现后GREEN：`six_fields_empty_and_latest_query_only`、`route_return_and_reload_reread_query_and_share_song_actions`、`revision_and_epoch_reject_late_collection_and_song_dtos`、`read_failure_is_top_only_and_rest_does_not_restore_write_permission`。
- 真实SQLite/Library/Collection/API fixture精确节点通过，六字段命中`a,b`、MISSING c不补入、空白/无匹配为空；public Song DTO由实际API验证，稳定业务snapshot域不变。初始测试误比captured_at/output观察时间戳，仅改为稳定业务域断言；生产后端未改。
- 精确后端API search节点、Service search三个节点及fixture共11项通过；指定API/service完整文件及fixture共36项通过。现有Starlette/httpx deprecation warning保留，未改依赖。
- 指定Web Search/song-actions/resource-cache/library-collections共28项包含在扩展受影响关系Gate（再含global-notices/shell-navigation/global-artwork）7文件44项中通过；完整Web23文件259项通过。
- typecheck、定向Ruff `server/tests/api/test_search_web_fixture.py`、production build及diff check通过。后端完整suite本轮未运行（服务端生产代码未修改）；B05既有1448不冒充B06fresh结果。
- 独立只读审阅覆盖B06 delta及shared cache/notice/action接口，无Critical/Important；审阅者fresh Search/resource-cache15项通过。手机软键盘/触摸仍不能由自动或浏览器结果关闭。

审阅未裁决项的执行结论：手机键盘/触摸继续等待用户；最终重建CSS已由实际浏览器验证；B01–05维持既有关闭，不重开；Favorites/star按B08边界保留未实施；既有批次外缺陷保持单列。没有deferred Minor，没有新领域合同裁决。这样保留范围与证据归属，若手机不通过只修正受影响B06行为并回归。

## LAN与手机Gate

同Wi-Fi URL：[Search](http://10.104.60.177:5180/library/search)，构建版本 **T9-B06-A01**。wlan0实际10.104.60.177已核实；preview0.0.0.0:5180同源代理127.0.0.1:8008。独立owned SQLite/真实Services/AcceptancePlayer Mock，advance_clock=True；不连接真实MPD/NAS/DAC，不改旧Batch进程或DB，不提供公开场景控制API。

启动脚本：ignored `.superpowers/sdd/2026-10-10-task-9-web-batch-plan/b06/runtime/serve.py`，每次新建owned `phone-*.db`，本轮phone-94608a12897c41a59ad814891ba0464c.db。backend session89693，preview session12287继续运行。预览使用同目录b06/dist产物；HTML/JS/CSS逐字节LAN核对，同源Search/Song/state及`/api/realtime`WS首帧snapshot/protocol1通过。最初核验脚本误用REST protocol_version及`/api/ws`，检查实际API后修正核验脚本，未改产品。

320×510窄屏实际innerWidth/document.scrollWidth均320；输入44px、长菜单约256px、三动作44px，框架稳定。浏览器已验证Search→Library→back及刷新保留q、歌曲菜单、320×310短视口菜单内部滚动；辅助浏览器不替代手机软键盘和触摸反馈。预检发现清空按钮使用native白底，最小CSS修正为既有tokens，重建后浏览器确认透明底/近白字。截图存ignored `b06/runtime/search.png`。

最终产物：`index-y2xPS2Tb.js` SHA256 `eefbb789a35d4eeb0f89f3634e6b294b46e8cb767d84dd0d45410bfb70cb82aa`；`index-CrF9v1gL.css` SHA256 `2664cfa08a0e763bbe6761a252f6ef8629cc6e5a850995ed102c4f221869cafa`；LAN均逐字节匹配，HTML title仅验收构建标识T9-B06-A01，不改产品业务或增加场景UI。

最少手机项（H08/H04，M01/M02/M03/M04）：

1. 依次搜索 `本地验收曲`（标题）、`夜航歌手`（演唱者）、`手机验收专辑`、`专辑艺术家`、`夜间音乐`、`2024`；有命中，缺失文件不作为命中补入。
2. 快速改词、清空、输入`不存在`，确认不残留上一查询结果；输入`夜航歌手`后去Library再浏览器返回、刷新，q与结果一致。
3. 软键盘打开时点长歌曲：先出统一菜单，三个动作/关闭可达；选一项确认状态与Queue一致，点外侧或收起键盘后框架正常。横屏/窄屏无横向溢出，四项导航和顶部保持。

用户反馈前B06不能关闭。真实MPD/NAS/DAC **NOT RUN**，PWA **DEFERRED**；G9-02和既有ArtworkRef单Song500均批次外保持，本Mock无ArtworkRef不证明其已修复。Task9整体未完成。

## A02 用户反馈：对象搜索需求待冻结

用户报告“只能搜标题、搜不到tags、搜专辑艺术家不展示对应艺术家，别的正常”，随后明确选择“希望结果直接列出艺术家、专辑、标签等对象”。本轮实际LAN API复核六字段均有匹配：专辑艺术家返回normal/lyrics-error/long三Song ID，实际浏览器同样显示三首歌；根因是现行Collection→Song表示与用户期望对象搜索不同，不能将反馈归为已关闭或用既有自动通过驳回。

现行B06/唯一Library §6没有冻结跨对象搜索DTO、分组及点击合同。建议限定增量：后端提供additive对象搜索读取（原Collection接口保持），复用已有分类summary稳定ID；歌曲/艺术家/专辑/风格/年代/标签按类型分组，艺术家沿用既有演唱者+专辑艺术家共同分类；对象点击既有Collection详情，Song仍统一菜单；后端匹配排序，Web继承Library revision/epoch/query迟到拒绝，无schema/依赖/未来Batch变更。此段为待用户确认的提案，不是已冻结Spec；未实施新产品代码、未自行改公开合同。

B06仍OPEN，新对象表示合同待确认；“别的正常”作为既有行为的用户反馈保留，后续只针对对象搜索做必要补测，不要求重做已接受操作。

### A02 表示纠正：归类在上、内容在下

用户否定上一段“对象分组后点击进入详情”的表示建议，明确“要把归类本身置顶展示，下面再展示归类下的内容”。当前意图是同一搜索页先显示匹配归类身份，再显示该归类的内容；不能把上一方案写为已批准，不用只列对象并跳页代替此要求。歌曲菜单和已认可的查询生命周期保持。多归类命中时顶部选择后显示单个内容，或逐归类内联展开的边界正在澄清；此边界关闭后再同步唯一Library Spec与B06合同，并按新合同实施/验收。


### T9-B06-A02 当前合同与实施证据（2026-10-11）

用户最终明确“归类置顶，归类下的内容一起往下展示。根据归类本身的排序来排序展示”。此前跳页或单选归类提案均为历史，唯一Library §6.1 LIB-SEARCH-VIEW-001已冻结。顶部集中显示全部匹配归类，下面按albums/artists/genres/years/tags现有catalog顺序连续呈现各组；组内保持既有Collection排序。同Song跨组保留归类上下文，直接歌曲仅追加未在组内的匹配。顶部按钮只定位本页，不启动播放。

最小增量：Service + domain/HTTP DTO +只读GET /api/library/search/results?q=，原search Collection接口保持；Web同Library cache decoder/路由查询/epoch/revision保护、SongRow与通知复用。后端实际关系测试先RED404→GREEN2，证明稳定身份、演唱者/专辑艺术家、标签、多归类、原排序、直接去重复、空白/无匹配及读取不变更Queue/History/revision。真实API golden fixture再生成并独立对照通过；Web原四节点加集中顶部/连续全部内容排序节点5通过。严格typecheck发现并修正局部kind类型、nullable Vue key与测试Queue fixture访问，不放松断言。受影响后端7文件77通过（已有Starlette/httpx warning），Web完整23文件260通过，typecheck/production build/定向Ruff/diff check通过。独立A02只读审阅无Critical/Important；手机键盘/触摸未由自动测试替代。

当前URL http://10.104.60.177:5181/library/search ，title T9-B06-A02；native backend127.0.0.1:8009/session37572，preview0.0.0.0:5181/session45385。owned脚本runtime/serve-a02.py，owned DB phone-3d36e1b9ab804983a552cb15fefcf44e.db，真实SQLite/Services+Mock，新增非空夜航标签验收数据，不触碰旧runtime。实际LAN专辑艺术家=1组3歌曲、夜航标签=1组2歌曲、夜航=专辑/艺术家/标签3组；所有Song/state读取200，同源/api/realtime首帧snapshot/protocol1。JS index-CC1BMgYd.js SHA256 3e53616ac847340928008fac21f46ddadefbbd14ff295b9b220be86f0df3415f；CSS index-BhZIYHpR.css SHA256 240d90d4b46df49fa0112b320a356ab8c9e48ea9fc94dc1f98061e88c4d76022，LAN与本地产物字节一致。320×510浏览器宽度/scrollWidth320，归类按钮约44px，顶部顺序及连续内容实测一致；专辑艺术家/夜航标签分别实测命中。截图ignored b06/runtime/search-a02.png。

只需手机复核两项：搜专辑艺术家、夜航标签，确认归类本身在顶部且对应歌曲在下方；搜夜航，确认顶部专辑→艺术家→标签及下方各自内容以相同顺序连续展示，长标题/软键盘下可操作。用户“别的正常”保留，既有已认可行为不重复要求验收。B06 OPEN / HUMAN PENDING，B07–10未推进。真实MPD/NAS/DAC NOT RUN，PWA DEFERRED，G9-02/ArtworkRef批次外保持；HEAD14c6239，原dirty保留，无commit/push/PR/merge。

A02最终fresh完整后端：`.venv/bin/python -m pytest -q server/tests` **1451 passed**，119.53s，仅既有Starlette/httpx弃用warning；不能替代上述77项定向Gate。最终diff check通过。


### T9-B06-A03 图标归类与单列表去重（2026-10-11）

用户本轮明确要求：顶部“专辑”“艺术家”等类型文字改为对应矢量图标＋归类名字；下方只展示内容，不分类、不重复。A02的跨组重复和组标题表示被此次反馈替代，手机Gate仍OPEN。当前分支feature/task-9-web、HEAD14c6239与实际代码/运行状态已核对，既有dirty保留。

Library §6.1 LIB-SEARCH-VIEW-001同步为当前表示合同。SearchView复用LibraryIcon SVG，上方仅显示名称（aria-label保留类型）；下方单一SongRow列表沿服务端归类与组内顺序展开，按Song ID保留首次出现，未在归类内的直接歌曲追加。移除组标题与“其它匹配歌曲”标题。顶部入口定位该归类首首歌曲的已有行，空成员禁用；没有播放/筛选副作用。后端results与旧Collection接口、DTO、匹配与成员排序不修改。

自动验证：原表示测试按新授权合同替换，首先RED为类型文字前缀仍显示；最小实现后Search5项GREEN。新断言覆盖五类SVG、单列表、跨归类去重、首组[b,a]顺序优先、尾部直接歌曲c；独立审阅指出归类定位缺少自动覆盖，已补充后组点击定位先前保留的a及空归类禁用，5项fresh通过。添加断言时误将空标签加入原查询循环，导致fixture无结果；仅修正测试输入，不改产品或削弱断言。相关7文件45项、完整Web23文件260项、typecheck及production build通过。独立只读审阅无Critical/Important，唯一Minor覆盖建议已落实。本轮未改Python生产或测试代码，未重跑后端/Ruff；A02后端77/1451为历史证据，不冒充本轮fresh。

当前手机URL：http://10.104.60.177:5182/library/search ，title T9-B06-A03。新ignored dist-a03及preview session22040；复用已有A02 owned native Mock backend127.0.0.1:8009，不重启、不改其SQLite或旧预览。LAN HTML/JS/CSS与本地产物字节一致：index-BcWCXgVh.js SHA256 54506612269f3339d86be912bf474757a754305118451f9faac4e7bc3034d4ad；index-kGnW2_6t.css SHA256 92e083b3179141ee3988c90c4efcef72c4af3284f518301085931983a6196805。浏览器LAN实际读取专辑艺术家1归类3歌曲、夜航标签1归类2歌曲、夜航3归类但仅2歌曲；标签定位和共享三动作菜单可用。viewport请求320×510，实际innerWidth/scrollWidth均291（浏览器缩放后的CSS像素），无横向溢出，入口实测约44 CSS px；不宣称本次实际innerWidth320。截图ignored b06/runtime/search-a03.jpg。沿用同一后端；本轮未另做WS握手验证，不以A02握手替代新证据。

仅待手机复核当前两项改动：搜“夜航”，顶部专辑/艺术家/标签为图标＋名字，下方两首歌曲无分组标题且不重复；搜“专辑艺术家”“夜航标签”，对应内容与共享菜单在软键盘下可用。B06 OPEN / HUMAN PENDING；B01–05保持CLOSED，B07–10未推进。真实MPD/NAS/DAC NOT RUN，PWA DEFERRED；没有commit/push/PR/merge，没有环境/依赖修改。


A03最终复跑说明：补充定位/空归类断言后，默认并发Web复跑发生7文件14项超时（246 passed），另有vitest-worker snapshotSaved RPC超时；涉及Queue save/actions、Song actions、Library collections及Player等，不能将该轮写为通过。已见具体超时包括same_page_unknown_save_recovery_closes_original_form_without_second_intent、valid_but_wrong_song_receipt_stays_unknown_and_cannot_change_canonical、category_identity_and_server_collection_play、empty_collection_never_plays_and_read_errors_are_only_top_notices、drag_only_pending_submits_before_occurrence_without_replacing_hidden、known_revision_cancels_drag_without_play。未据超时修改无关产品/测试或放宽超时，按执行环境并发异常候选处理；同一最终代码以`node node_modules/vitest/vitest.mjs run --maxWorkers=1`重跑，**23文件260 passed、exit0、33.20s**，完整日志ignored `b06/runtime/a03-web-final.log`。这支持并发执行环境超时判断，不宣称已定位主机根因。最终typecheck exit0，diff check通过；源文件/文档delta已对本轮前备份核对，只有B06 Search相关7文件修改，原dirty和环境保留。


### 2026-10-11 B06 A04归类入口可进入

用户明确要求搜索命中的专辑、艺术家、标签等入口点击进入后只展示对应内容，原默认完整去重无分组列表保留。此前A03入口仅定位为历史。Library §6.1 LIB-SEARCH-VIEW-001已同步：复用既有CollectionView和分类成员API，按稳定kind/source_id跳转，原搜索词通过详情query search保留；详情“返回搜索”恢复q并重读原列表，普通Library入口返回合同保持。空归类也可进入空详情；默认搜索无PlayAll，详情沿用已存在的菜单与集合动作。后端/API/依赖及B07–10未改。

Fresh Search6、相关7文件46、完整Web23文件261（单worker，39.55s）、typecheck/build/diff通过；独立只读审阅无Critical/Important/Minor。手机当前地址 http://10.104.60.177:5183/library/search（T9-B06-A04），本轮同源LAN归类进入与返回已辅助验证，B06 OPEN / HUMAN PENDING。详细证据见B06 acceptance末尾；不关闭手机Gate，原dirty保留，无commit/push/PR/merge。


A04证据补充：新导航关系测试先RED（点击仍留在/library/search）→GREEN，覆盖专辑/艺术家/标签三对象及含斜线source_id编码、服务端成员顺序、仅对应成员、SongRow三个菜单、返回q与完整[b,a]结果、全部请求GET；既有A03默认列表顺序/图标/去重证明保持。原定位测试按新授权行为替换，不再断言scrollIntoView或空归类禁用。实际本轮产品delta为SearchView入口、CollectionView搜索来源返回、Search CSS；Search结果合并与缓存/迟到/菜单逻辑保持。未改Python代码，无后端/Ruff复跑，A02后端1451不冒充fresh。本轮Web完整日志ignored b06/runtime/a04-web-final.log，exit0。

预览新session8660、ignored dist-a04；复用A02既有owned SQLite/真实Services+Mock backend8009，不重启或写DB、不改旧预览。LAN HTML/JS/CSS与本地产物字节核对通过：index-NBQPan_N.js SHA256 0b428bb576902fe82fd561d0fa94b6f30a516f6de9aae478a347e1eb4cdcd126；index-XX-gxFfb.css SHA256 e3c03cbc2026d276bd179dde5e9a7e3e37e388e9cef37e01d9aabd18f8d87f85。实际浏览器搜夜航仍3归类＋2首唯一歌曲；点夜航标签进入既有tags详情仅2首（normal,long），返回原q，再进专辑仅2首（long,normal），均按其服务端顺序。入口不播放；截图ignored b06/runtime/tag-a04.jpg。未复跑WS握手、未模拟手机键盘，不能由辅助浏览器关闭真人Gate。

手机只需复核：搜夜航，点专辑/艺术家/标签进入对应内容，点“搜索”返回；原去重无分组列表和搜索词保留。B01–05 CLOSED，B06 OPEN / HUMAN PENDING，B07–10未推进，真实MPD/NAS/DAC NOT RUN、PWA DEFERRED。


## 2026-10-11 B06最终关闭：用户验收认可

用户在T9-B06-A04交付后明确“可以验收了，更正相关必要文档。规避没必要的重复跑测试”，本轮按对当前版本的验收认可记录，**B06 CLOSED / HUMAN PASSED**。当前合同为Library §6.1 LIB-SEARCH-VIEW-001：顶部SVG图标＋归类名称，默认下方无分组且按首次出现去重；点击归类进入对应内容，返回恢复原搜索词与结果。此前“别的正常”的既有操作认可保留，必要H08/H04及M01/M02/M03/M04手机Gate按本次整体认可关闭，不编造逐项手机操作日志。

B01–B06 CLOSED，B07–B10未启动，Task9整体未完成。自动证据沿用所属轮次：A04 Search6/关系46/完整Web261、typecheck/build及独立审阅；A02后端定向77/完整1451。A03并发超时与单worker通过记录继续保留。本轮只改必要状态/入口文档并检查文档差异与diff check，没有重跑测试、构建或运行环境验证，不宣称新增自动验证结果。原dirty保留，无commit/push/PR/merge；真实MPD/NAS/DAC NOT RUN、PWA DEFERRED，G9-02与ArtworkRef批次外限制保持。
