# Task 9 B05 acceptance — T9-B05-A02 / CLOSED

日期：2026-10-11（Asia/Shanghai）。B05 **实现完成；自动/Contract/Relationship/LAN PASSED；手机 HUMAN PASSED，Batch CLOSED**。用户在此前认可功能后明确接受A02界面并确认“可以了。通过验收”，最终关闭依据见本文末尾。B01–B04最新用户关闭记录保持有效；B06–B10未启动，Task9整体未完成。以下A01/A02交付时的OPEN/PENDING记录保留历史时态。

## 范围与实际前置

用户授权执行Task9 BATCH5。读取contract-audit、web-batch-plan B05及其引用的主Plan Task9 Steps5/7、Playback §3.1–3.3（PB-SONG-NOW-001）、Library §4/7.1、Architecture §4.1–4.3/§12/§19.5、Visual WEB-UI-*、手机方法H04/H05/H10与M01/M02/M04/M05。

实际分支feature/task-9-web，HEAD14c6239；B01–04仍为dirty checkout成果。最新B04验收是用户明确通过且不额外复测，旧OPEN/DRAFT为历史。fresh前置B02 API/invariants36项、Queue actions/save43项通过。沿用现有.venv：Python3.14.4、pytest9.1.1、ruff0.16.9，requirements已读，无依赖/环境/schema改动。

交付：

- Library五类albums/artists/genres/years/tags和全歌曲；类别summary使用服务端ID，详情/返回/刷新内部路由继承唯一壳及导航。query kind保留返回分类。
- 普通SongRow统一三个动作及完整长文本菜单；普通PlayNow单次POST song入口，Next/Add新增条目。Queue正文精确occurrence、已接受快捷移动/拖动保持；通用target含queue_item_id时仍走原item播放入口，没有将普通Next/Add用于Queue移动。
- 集合PlayAll/Shuffle仅发source_type/source_id/randomize，服务端解析成员与排序；不预先随机列表或入队后拼装播放。分类详情明确“可播放歌曲”，全songs保留不可用记录，空集合禁写。
- 一份app Library resource cache拥有全部Library paths；Queue Song投影和类别/列表共享同一generation/revision owner。资源/菜单不拥有连接或canonical state；所有mutation复用持久TaskActions，unknown原key恢复，ACK后state重读，确认后读失败仅read。
- 不可用标记留行内，原因与read错误只进顶部；菜单在app bar/通知层下方。真实Favorites B08未接入，仅建立独立slot并机械证明点击不触发菜单/播放；Search/Playlist/Settings仍各自未来Batch占位。

Ruling：执行授权覆盖现有设计与本批次计划，不重复申请方案批准；不复制dirty成果到另一个worktree。B04移动原occurrence与B05新增song occurrence不同，保留Queue独立入口，仅共享已冻结client/TaskActions恢复机制。

## Contract Matrix / Relationship REQUIRED

| Contract | Authority / preconditions | delta / unchanged / confirmation / boundary | failure / retry / observable / proof |
|---|---|---|---|
| T9-SONG-001 | Playback §3.3 PB-SONG-NOW-001；writable+fresh Song且AVAILABLE；PlaybackService唯一领域编排 | 新MANUAL occurrence；原pending ID/顺序/source保留，Queue/History/Context及terminal联合提交和MPD确认沿用B02。Web不由ACK写canonical，不代用StartTrack或两请求 | pending/unknown互斥；不可用/offline不发，跨页原key，wrong identity receipt unknown，confirmed/read失败仅read。owner songActions/SongRow/TaskActions；song-actions11中对应6项、B02 API/invariants36项及实际native UI before/after proof |
| T9-LIB-001 | Library §4/§7.1、Architecture4.1/4.2；category DTO真实ID，受library marker；播放需writable/fresh/非空 | 浏览只读；集合控制替换Queue/新Context由服务端执行，HTTP确认再read；浏览不创建Playlist、不播放、不随机重排、不猜标题为source ID | generation/revision/route迟到保护、空禁写、失败顶部，Shuffle retry原payload/key不重新build随机集合。owner resourceWire/createAppLibraryStore/libraryResources/LibraryView/CollectionView/songActions；library-collections5项、真实SQLite/API golden fixture、collection_service和library_api指定Gate、native集合请求/state proof |
| inherited SHELL/BG/NOTIFY/QUEUE | Visual WEB-UI、现有持久AppShell/PlayerSession及TaskActions；Queue合同不变 | 一个cache/connection/顶部系统；page draft离页丢弃，已发intent继续；背景不从Library选中推断 | Queue三文件、global-notices/wire/resource-cache、完整Web及浏览器层级/几何proof。独立Favorite slot无业务实现；不提前B08 |

12项合同字段由上表和所引唯一Spec共同给出；本批次不扩展后端公开合同。所有服务端确认/History/事务/partial执行以B02及既有集合合同为准，不创造新的Web权威。

## 验证结果

| Gate | fresh结果 |
|---|---|
| 核心行为RED→GREEN | 两个核心测试先因Library空占位缺入口失败；后普通原子动作/类别关系GREEN。不可用顶部原因另有精确RED→GREEN。新增两个Web文件11项最终通过 |
| DTO来源 | test_library_web_fixture从真实SQLite Repository、LibraryService、CollectionService和实际REST序列化六类资源；全songs包含MISSING，album songs保持服务端曲序且过滤不可用，Collection保留unavailable IDs；golden library.json经后端test比较，Web真实decoder验证。fixture早期错误假定album_id可由Song指定，实际Repository生成ID；只修fixtureUUID/时间确定性，未改生产代码 |
| Web规定回归 | song-actions/library-collections + Queue actions/save/view + wire/resource-cache/global-notices：8文件108项通过 |
| 完整Web | `npm --prefix web run test -- --run`：22文件253项通过（包括Player/壳/背景回归） |
| 后端规定Gate | `.venv/bin/python -m pytest -q server/tests/api/test_library_api.py server/tests/services/test_collection_service.py server/tests/api/test_song_play_now.py server/tests/invariants/test_song_play_now.py server/tests/api/test_library_web_fixture.py`：86项通过 |
| 完整后端 | `.venv/bin/python -m pytest -q server/tests`：1448项通过，121.16秒；1条既有Starlette/httpx弃用warning，未改环境 |
| native/tooling | typecheck exit0；定向Ruff新Python文件All checks passed；production build成功。outDir为本计划ignored目录，不清理旧产物；警告仅说明不会自动empty目录 |
| 独立审阅 | 无Critical；一项Important：Song backdrop20与AppBar20相同，后DOM遮挡顶部。真实浏览器RED：toggle中心elementFromPoint为song-menu-backdrop；最小改15，GREEN：中心命中status-toggle，重叠处命中playback-status-details。无遗留Critical/Important/Minor |
| 本轮回归失败处理 | 新Library GET曾消费旧Queue测试的mutation序列，导致6个fixture失败；仅扩展shared shell test transport，为新category/list GET提供独立空DTO，保留原key/identity/no-write断言。精确8项→指定108→完整253通过，未修改Queue生产代码或弱化测试 |
| diff/scope | git diff --check通过；以启动时/tmp/task9-b05-baseline.json哈希区分B01–04已有dirty，实际B05只变更19个代码/测试文件及本报告/两个活动入口。无server/app变更，无DB/env/dependency/生成dist进Git状态。无commit/push/PR/merge |

完整Web/后端结果不是手机通过证据。最后仅CSS层级修正，已重新build及实际浏览器hit-test验证；未重复跑无关全量。

## 当前LAN与辅助页面证据

主URL：[音乐库](http://10.104.60.177:5179/library)，版本 **MPD-Server · T9-B05-A01**。空可播放集合：[未知年代](http://10.104.60.177:5179/library/years/unknown)，真实GET200 `{items:[],count:0}`，不是合成前端空列表。该类别仅有MISSING成员，summary可播放列表不提供它的名称，详情保留服务端source ID `unknown`；不存在完整membership编辑承诺。

wlan0实际IP10.104.60.177已重新核对，不沿用此前192.168.3.18。前端0.0.0.0:5179，同源代理至127.0.0.1:8007；单独新SQLite/真实Services/显式AcceptancePlayer Mock注入，advance_clock=True。没有live MPD/NAS/DAC连接；没有公开场景控制API。旧B04进程/DB保留。

HTML/JS/CSS LAN响应逐字节匹配本轮dist；最终JS `index-sfN5CSxO.js` SHA256 `3ba2bc1564ce68b05c400b8e60f067052575c914c7e6f7b4d1d675c0837405ad`，CSS `index-PPULoUcl.css` SHA256 `b0db11a554ffc5ed874e1cf24732207557be3f614e6dd62aecb56125e6c51138`。同源六类GET/state200，WS `/api/realtime` initial snapshot protocol1及epoch一致已验证。

实际浏览器请求355×601、有效CSS viewport323px（IAB比例换算）；Library/Queue均document.scrollWidth=innerWidth，header/nav位置不变。菜单正常长文本/MISSING有完整身份、动作44px目标；菜单上方唯一通知可点击。真实空集合两个动作禁用，暂无歌曲可见。截图存ignored本计划b05/runtime/{library,menu-notice}.png；仅辅助，不当手机触摸通过。

自有native实际UI普通SongNow：新current接受确认playing，全部4个原pending occurrence ID/song/source/顺序保留（before-song/after-song.json）；服务端集合顺序按专辑曲号long→normal，Shuffle仅包含选中专辑两曲，重复GET没有重排（collection-evidence.json）。当前Mock场景有长中文/英文/emoji、重复待播、MISSING歌曲及缺封面；未承诺真实声音。

启动：根目录`PYTHONPATH=. .venv/bin/python .superpowers/sdd/2026-10-10-task-9-web-batch-plan/b05/runtime/serve.py`（每次启动新owned SQLite）。预览：`API_PROXY_TARGET=http://127.0.0.1:8007 npm --prefix web run preview -- --host 0.0.0.0 --port 5179 --strictPort --outDir ../.superpowers/sdd/2026-10-10-task-9-web-batch-plan/b05/dist`。本次exec backend session1717/preview78658保持运行；停止仅对本次进程Ctrl-C，不删除DB。

## 手机最少验收卡（等待用户）

1. **H05/M01/M02/M04**：主URL切分类→专辑详情→返回/刷新；长名称、完整歌曲菜单可读，正文无横向溢出、框架稳定。打开空集合链接，暂无歌曲且PlayAll/Shuffle禁用。
2. **H04**：全歌曲任选可用曲，分别“立即播放/下一首播放/加入队尾”，切Queue看结果；普通立即播放保留原待播，后两项新增条目。MISSING项三个动作禁用，顶部原因可读。真实收藏未到B08，本轮不测星标业务。
3. **H05**：夜航专辑“播放全部/随机播放”，Queue当前及手动集合对应该专辑，刷新不再重新随机；AutoPlay额外候选按既有Queue显示规则处理，不误认为集合成员。
4. **H10/M05**：已加载页面断网，只读禁写；恢复同Wi-Fi后再操作，切Queue/Library/Player时状态和顶部事项一致，无离线补发。unknown原key/pending跨页时序已机械验证，不要求用户devtools/故障注入。

手机型号/系统/浏览器及实际可达：沿用此前设备资料（未获本轮新信息），**本轮可达及操作反馈尚未收到，以上全部HUMAN PENDING**。反馈可只写“1–4通过”或失败编号/现象，不编造逐项真人日志。

## 剩余Gate与限制

- B05必要手机H04/H05/H10、M01/M02/M04/M05待用户反馈；收到前B05 OPEN，B06不得推进。
- 既有ArtworkRef单Song REST序列化500仍批次外未修复，本轮没有扩展API修复；失败显示顶部，不过滤Queue或假装资源成功。手机fixture无ArtworkRef，因此本轮不证明这项缺陷已解决。
- G9-02既有未送达拖动并发限制保持；PB-SONG-NOW/STOP及Queue冻结合同未改变。
- 真实MPD/NAS/DAC **NOT RUN**，PWA **DEFERRED**，Task9整体未完成。未commit/push/PR/merge。

## 2026-10-11 A02：按用户六项要求调整 Library 界面

用户反馈此前功能可以通过，并要求现在直接修改界面；本轮仅调整 B05。分类导航改为矢量图标＋短文字的轻量按钮，全部歌曲排第一，窄屏单行横向滚动；返回入口字号增大，使用返回箭头与分类图标，与详情标题分层。专辑详情在返回下方采用左侧104px方形封面、右侧名称/专辑艺术家/年代/数量，文字高度限定于封面；缺图使用矢量占位。播放全部/随机播放加图标、居中单行。歌曲菜单收窄至最多272px，去掉关闭项，保留外侧点击、Escape、焦点返回；全部动作禁用时面板仍可聚焦。

封面沿用既有 Song artwork API，无新公开合同。URL/节点身份包含 epoch、Library revision 与已接受 artwork 描述；迟到错误不能覆盖新图。失败使用占位，原因/只读重试进入唯一顶部通知，路由/版本变化与卸载清理。独立审阅指出的旧封面不重载 Important 已精确 RED→GREEN 修复并复核关闭，无遗留 Critical/Important。新增测试最初遗漏 Artwork DTO 的 content_sha256 字段导致 Invalid wire value，已仅修正测试 fixture。

本轮 fresh：B05两文件13项通过；完整 Web 22文件255项通过；typecheck/build/diff check通过。后端、依赖及环境未修改，未重复执行后端测试；此前1448项属于A01证据。IAB实际320px/390px正文无横向溢出，分类按钮同一行，播放按钮同一行居中，返回/详情独立；外侧点击及Escape关闭已实际验证。截图：ignored `b05/runtime/album-a02.png`。图片成功加载/失败/版本更新/迟到错误由自动测试验证；手机Mock没有真实封面，不冒充实机证明。

最新同Wi-Fi URL仍为 http://10.104.60.177:5179/library，页面版本 **T9-B05-A02**。产物 `index-C-pwLoLi.js` SHA256 `c66394cfce6599353e98c7e3c0854b60c8450c984caf95e66a144e9c9d9ddd45`；`index-C3eqYzIU.css` SHA256 `16fa0c67616c073eb77a9994ff530bbec658cc3d72624b8b13a679ea46e88251`。LAN HTML/JS/CSS与dist逐字节一致；同源state/albums/songs返回200有效JSON。预览检查期间此前owned Mock进程退出，已按原脚本重新启动（session40505，新owned `phone-c202106c10ca4c829d109c9147ff041a.db`），保留已有DB，不连接真实MPD。分类ID由新的真实SQLite场景生成，应从首页进入，不沿用旧详情ID。

已记录用户整体功能认可；新界面手机Gate仍 **HUMAN PENDING / B05 OPEN**。最少操作：刷新首页检查分类单行/顺序并横滑；进专辑检查返回与左图右文、居中按钮；点曲目检查窄菜单并点外侧关闭。反馈后按原H04/H05/H10与M01/02/04/05关闭范围记录，不编造逐项手机结果。B06未启动，无commit/push/PR/merge；真实设备/PWA及既有ArtworkRef单Song500限制不变。

## 2026-10-11 最终关闭：用户验收通过

用户明确：“可以了。通过验收。快速验收并更正需要的文档。不需要重复测试流程”。结合此前整体功能认可，T9-B05-A02六项界面修正及完整B05当前范围获用户接受，B05 **CLOSED / HUMAN PASSED**；必要手机H04/H05/H10与M01/M02/M04/M05按用户整体验收反馈关闭，不编造逐项操作日志、设备资料或新测试结果。

本次仅核对Git及文档并同步关闭状态，不重跑测试、不改产品代码/环境/依赖/Mock场景。A02 Web255/typecheck/build及A01后端1448属于各自实施轮次的既有证据；feature/task-9-web / HEAD14c6239已重新核对，dirty成果保留。B05无剩余必要Gate；B06–B10未启动，Task9整体未完成。PWA DEFERRED、真实MPD/NAS/DAC NOT RUN、G9-02及既有ArtworkRef单Song500批次外限制保持。未commit/push/PR/merge。
