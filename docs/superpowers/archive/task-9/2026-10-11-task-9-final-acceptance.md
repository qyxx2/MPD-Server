# Task 9 / B10 final acceptance — T9-B10-A01

日期：2026-10-11（Asia/Shanghai）。**B10 OPEN / HUMAN PENDING；实机 Gate BLOCKED / NOT RUN；Task9整体未关闭。** B01–B09最新用户关闭保持有效，历史OPEN不重开。

## 范围与实际前置

核对入口contract audit、web batch plan B10、主Plan Task9、Visual WEB-UI-*、Architecture §4.1–4.3/§12/§19.5/SYS-MPD-CONNECTION-001、Playback §3–5/§8.9、Library §4–7、Output §6–7和手机方法。当前feature/task-9-web / HEAD14c6239；保留既有B01–B09 dirty成果，未复制到新checkout、未commit/push/PR/merge。

本批次仅新增`server/tests/api/test_task9_wire_fixture.py`、`web/tests/fixtures/task9.json`、`web/tests/invariants/task9-relationships.test.ts`及必要状态文档。产品代码、公开合同、依赖、.venv、既有DB、音乐文件均未修改。测试生成真实SQLite/Services/MockPort的四个阶段：初始收藏及歌单→取消收藏204→歌单加歌→普通歌曲原子Play Now；只归一化运行时ID及墙钟时间，保留版本、成员/occurrence顺序及跨DTO身份关系。

## 自动 Gate：PASSED

- 新后端精确节点/文件：`test_task9_wire_fixture.py::test_task9_server_fixture_to_resource_action_route_convergence`，**1 passed**。
- 新Web精确节点/文件：`task9-relationships.test.ts::server_fixture_to_resource_action_route_convergence`，**1 passed**。真实后端golden→shared decoder/cache→Favorites/Playlist/Song actions跨页pending→ACK→权威重读；精确occurrence、当前身份、默认背景、唯一通知/连接、不同intent key及断线GET不恢复可写。
- 负向敏感性验证：临时移除TaskActions的ACK后snapshot refresh，新增Web测试按预期失败（current仍a，预期b）；随后按原始字节恢复，精确测试GREEN。无永久产品修改，无假造缺功能RED。fixture准备阶段的observer独立loop竞争、非ASCII测试key及扫描时间归一化问题只修正本轮测试生成入口，未修改生产代码或削弱业务断言。
- Task9指定Web：global-notices/global-artwork/shell-navigation/queue-view/queue-actions/queue-save/song-actions/library-collections/search/playlists/favorites/settings/task9-relationships，单worker **13文件 / 114 passed**（32.92s）。完整Web `npm --prefix web run test -- --run --maxWorkers=1 --minWorkers=1`，**27文件 / 287 passed**（45.98s）。
- 后端指定关系Gate：`server/tests/invariants`，加API song_play_now/favorites_members/mpd_connection/library_web_fixture/playlist_web_fixture/search_groups/search_web_fixture/task9_wire_fixture/web_wire_fixture/system_reads/system_output_mutations/playlist_reads/idempotency/mutations_playback/library_api及service playback_service/queue_manager/collection_service/library_service/playlist_service，**1114 passed**（83.44s）。包含计划指定的Queue/History/Stop/current-target/事务/幂等/Library/Playlist/Output历史关系，先于完整回归执行。
- 完整后端 `.venv/bin/python -m pytest -q server/tests`，**1468 passed**（95.02s）。仅既有Starlette/httpx弃用warning，未改依赖。
- `npm --prefix web run typecheck`、production build、`.venv/bin/python -m ruff check server/tests/api/test_task9_wire_fixture.py`、`git diff --check`通过。Python3.14.4 / pytest9.1.1 / ruff0.16.9，使用原.venv。
- 独立只读审阅无Critical/Important；Minor覆盖限制：本轮综合fixture artwork=null，只证明默认背景与身份/跨页生命周期；非空图片解码/迟到拒绝沿用本轮fresh的global-artwork5项专项，其输入为前端构造snapshot。不能宣称真实非空ArtworkRef→REST单Song→背景完整链已证明。最后在自有临时SQLite fresh复现：歌曲需有album以实际持久化album_art_refs；确认Repository回读artwork非null后GET /api/library/songs/a触发Pydantic ValidationError，SongResponse.artwork拒绝ArtworkRef实例（期望ArtworkResponse/dict），生产表现500。根因是api/library.py::_song_response直接model_validate(song)未转换嵌套ArtworkRef；没有修改产品、没有清空封面掩盖。此既有批次外缺陷需单独裁决修复范围，非空封面实机项目不得记PASSED。

运行日志位于ignored `.superpowers/sdd/2026-10-10-task-9-web-batch-plan/b10/`：web-targeted/web-full/backend-targeted/backend-full/mutation-check.log。新golden可用`.venv/bin/python -m server.tests.api.test_task9_wire_fixture`在自有临时DB重建，不运行live MPD。

## Contract / Relationship Gate：REQUIRED

完整P/A/Δ/U/X/H/T/F/R/O继承audit §6 D0及各行冻结增量；以下是本轮owner→proof→fresh追溯，不新立领域合同。Web文件均位于`web/tests/invariants/`，后端节点位于所列测试目录。

| Contract → 唯一Spec | 实际owner | proof节点 / 本轮结果 |
|---|---|---|
| T9-SHELL-001 → Visual SHELL/NAV/NOTIFY、Architecture §4/12 | AppShell、playerSession/taskActions、notices | shell-navigation::one_shell_one_connection_four_routes；global-notices::pending_and_unknown_intent_survive_route_change；1+10通过 |
| T9-BG-001 → Visual BG/BASE | AppShell、artwork store、AppBackground | global-artwork::confirmed_identity_decode_and_route_lifetime，5通过；综合默认背景1通过，非空后端链限制如上 |
| T9-SONG-001 → PB-SONG-NOW-001 | PlaybackService/QueueManager、songActions | invariants/test_song_play_now::test_new_occurrence_preserves_pending_identity_and_joint_state；song-actions::ordinary_play_now_is_one_atomic_intent，Web6及后端指定Gate通过 |
| T9-QUEUE-001 → PB-QUEUE-VIEW-001 / PB-STOP-LIFECYCLE-001 | QueueView/queuePresentation/queueUi、PlaybackService/StateService | queue-view::entry_hides_played_pull_reveals_and_lifecycle_resets_without_inventing_stop，8通过；test_stop_lifecycle::test_stop_generation_survives_start_and_terminal_replay通过 |
| T9-QUEUE-002 → Playback §5.2 / G9-02 | queueActions、PlaybackService/QueueManager | queue-actions::drag_only_pending_submits_before_occurrence_without_replacing_hidden_queue及pending_move_unknown_preserves_occurrence_payload_and_key_across_route，37通过；test_queue_moves及realtime_queue通过；G9-02限制不消除 |
| T9-SAVE-001 → Playback §5.3 | queueActions、QueueManager/PlaylistService | queue-save6通过；test_queue_save::test_save_reads_latest_complete_up_next_and_replay_does_not_create_twice及duplicate rejection通过 |
| T9-LIB-001 → Library §4 / Playback §4 | LibraryView/CollectionView、library cache/songActions、CollectionService | library-collections::category_identity_and_server_collection_play，7通过；API/library/collection service指定Gate通过 |
| T9-SEARCH-001 → LIB-SEARCH-VIEW-001 | SearchView/CollectionView、library cache、LibraryService | search::category_opens_only_its_collection_and_returns_to_unchanged_search，6通过；search_groups/search_web_fixture指定Gate通过 |
| T9-PLAYLIST-001 → Library §5/7.1 | PlaylistView/playlistActions、playlists cache、PlaylistService | playlists::unknown_original_intent_survives_route_and_disconnect_without_optimistic_membership，9通过；test_playlist_relationships/realtime_playlist/playlist_web_fixture通过 |
| T9-FAV-001 → LIB-FAV-UI/MEMBERS-001 | FavoriteIcon/favorites store、共享playlists cache、PlaylistService | favorites::unavailable_membership_and_cross_view_stars，9通过；test_favorites_members及综合真实golden通过 |
| T9-SETTINGS-001 → Output §6/7 | SettingsView、outputActions、OutputManager/MPDInfoService | settings::about_and_output_are_distinct_authorities / output_unknown_survives_navigation_without_inline_notice，9通过；system read/output mutations/relationships通过 |
| T9-MPD-CONNECTION-001 → SYS-MPD-CONNECTION-001 | mpdConnection、MPDConnectionService、main startup | settings::saved_mpd_address_remains_distinct_from_active_and_survives_unknown_retry；API test_mpd_connection::test_saved_endpoint_overrides_invalid_old_environment_and_adapter_uses_it通过；真实网络独立BLOCKED |
| T9-LIB-NAV-001 → Visual B09补充 | LibraryTabs/route views | settings::library_tabs_are_the_only_playlist_and_favorite_entry_and_keep_selection通过；受影响Library/Playlist/Favorites指定回归通过 |

## Production / LAN：本机辅助PASSED；手机PENDING

当前wlan0 `10.104.60.177`，不是历史192.168.3.*地址。两个URL共享同一生产JS/CSS，构建标识T9-B10-A01（未提交）：JS SHA256前缀15902342b568 / CSS648d6b1e8e7e。实际LAN HTML/JS/CSS字节与各自production目录一致；两origin的state、mpd/connection、mpd GET200及`/api/realtime`真实首帧snapshot已核验。

- [综合手机页面（Mock）](http://10.104.60.177:5187/)：preview5187→native8013，显式Mock，新自有SQLite/媒体，模拟单调时钟；正常/长标题/不可用收藏及歌单/重复occurrence。不证明设备声音。
- [实机地址入口（LIVE Adapter）](http://10.104.60.177:5188/settings)：preview5188→native8014，无Mock注入，无虚构能力；独立live.db和mpd-connection.json。当前未配置，active127.0.0.1:6600，不代表可达；初始WS baseline后地址保存可操作，About/输出能力未知如实显示，空Library不能冒充实机曲库。

自有runtime/live启动脚本、DB、dist、log全部ignored。启动命令：`PYTHONPATH=. .venv/bin/python <b10目录>/runtime/serve.py`（或live/serve.py）；preview使用对应API_PROXY_TARGET和outDir，strictPort。当前工具session：Mock backend58190/preview42738；live backend28167/preview99629。保持运行；只停止/重启这些本轮owned进程，保留数据库及保存文件，不终止旧B09服务。重启实机服务由agent操作，不新增Task11产品restart API。

辅助浏览器按320×740 viewport预检，当前浏览器缩放下有效CSS宽291；document/scroll均291，Queue与Settings header top11.99/height43.40，nav top608.73/height64.00相同。Player→Queue→Library→Favorites/Playlist→Settings可读，唯一框架连续。缩窄和本机API检查不抵扣手机触摸/用户可达确认。

## 最少手机综合项（H01/H10、M01/M02/M05/M06）

1. 手机打开5187：Player→Queue→音乐库，进入搜索/播放列表/收藏，再到设置返回Player；观察顶部、底部和当前歌曲背景槽连续，无重复导航或横向溢出。
2. 在音乐库取消/添加一个收藏后立刻换到Queue/收藏页；结果一致，处理/异常只在顶部，成功后操作记录撤下。复杂unknown、原key及已确认仅read已由自动proof覆盖，不要求人为制造。
3. 已加载页面断网，再恢复同一LAN，并后台/锁屏后返回；断线禁写、事实过期，重连恢复，无离线操作补发或虚假计时。

B01–B09已通过且未受本轮修改的H02–H09不重复全量Mock手机复验。用户本次补充的实机各功能是新增独立验收范围，不能套用旧Mock HUMAN PASSED。

## 实机 Gate：BLOCKED / NOT RUN，原因与方案

用户已授权真实MPD各功能测试，并要求在Settings填写地址。已实测历史NAS endpoint192.168.3.94:6600 TCP连接3秒超时；尚无当前实机地址/可读音乐目录答复，不能推断NAS仍在该地址或本机具跨网段路由。当前自有LIVE页面可保存地址，但冻结合同为下次启动生效；此前5186显式Mock保存地址不会更换Player。

最少用户项：在**5188/settings**填写真实host/IP与port并保存，回复“已保存”；补充本机可只读访问的音乐根及对应MPD URI根（或说明尚未挂载）。agent随后读取保存文件→TCP/greeting/认证诊断→按目标实测能力准备自有运行装配→重启同一live进程→核验active/新epoch/REST/WS，再给实际设备功能卡。

能力加载与扫描调度目前不会在普通main startup自动执行；Task10/11通用能力配置、扫描部署和restart UI仍未授权，本批次不能静默扩展。可用既有能力probe/只读scanner在ignored验收装配内完成目标验证与曲库准备；不能把commands存在或历史probe当新地址的runtime verified_operations。若需要密码，保留部署MPD_PASSWORD入口，不要求在公开聊天粘贴秘密。无可读音乐目录时可先做真实TCP/状态/输出诊断，完整Library/封面/歌词与集合播放验收需只读文件映射；不通过手造完整曲库或假availability掩盖。

目标网络恢复后实机卡按阶段交付：连接/About→选曲/暂停继续/seek/下一首及连续播放→精确Queue/移动/删除/保存→Library/Search/集合→歌单CRUD/收藏跨页→DAC回读与物理声音用户确认→地址保存/重启/断线恢复。所有功能需记录真实REST/Port事实；物理出声由用户确认。若地址仍超时，先核查同网LAN、NAS监听/可达路由、Wi-Fi隔离或VPN；可由用户在能访问NAS的主机部署本构建，再验同源URL，不擅改路由/防火墙或使用Docker替代native自动Gate。

剩余：手机综合HUMAN PENDING；真实MPD/NAS/DAC各功能及新地址网络验收NOT RUN/BLOCKED；非空ArtworkRef单Song已知500需单独范围裁决后处理，不记通过；PWA DEFERRED；G9-02未送达并发窗口保留。未关闭B10或Task9，不推进Task10/11，不执行Git整合。最终git diff/check/stat/status及实际diff核对：相对本轮开始，tracked差异仅README与文档地图更新，四个新增文件为综合后端测试、golden、Web测试和本报告；既有产品diff不变，原untracked未删除，DB/dist/log/env/依赖均未新增进可提交范围。audit/batch计划为先前untracked文件，本轮仅改当前状态/B10 Gate与追加交付记录。


## 2026-10-11 A02：用户澄清IPv6离线验收及远程音乐目录

用户说明：只能用IPv6连接MPD，启用IPv6后无法使用Codex；agent只能事先启动/准备服务，设备连接与各功能由用户独立测试后反馈。音乐文件位于远程NAS，MPD能够直接读取。接受此验收方式，不要求agent在该网络条件下实时判断连接或运行设备测试，不把用户无法使用Codex作为UI失败。实机PASSED只依据用户反馈及其提供的实际结果，不伪造agent观察。

当前owned服务已重新以setsid独立session启动：LIVE backend8014 PID17897、preview5188 PID17916（进程标识仅属本轮），LAN地址http://10.104.60.177:5188/settings；配置GET200，active127.0.0.1:6600/saved=null，尚未取得实机IPv6 endpoint。后端没有Mock。当前shell会话退出后仍监听；不宣称操作系统重启后自动恢复。本轮仅核验本地启动/HTTP，没有请求NAS。

下一顺序：保持Codex网络可用→用户提供MPD IPv6/port及目录访问方案→agent预配置与启动同一owned服务→用户切换IPv6并独立验收→恢复Codex网络后反馈。这样不依赖用户在agent离线时保存新地址并等待agent重启；SYS-MPD-CONNECTION-001下次启动生效合同不变，不新增自动restart watcher/API或热切换。

实际代码边界：LibraryScanner读取后端本地Path并建立SQLite索引，PlayerPort/MPDAdapter没有MPD曲库枚举导入能力。MPD能读NAS音乐不代表本机后端能读，当前live.db空库不能完成全功能验收。可选①后端在NAS读取已有音乐根，②本机只读挂载NAS音乐根，③先有限IPv6连接诊断、完整资源/集合功能暂缓。需要同时核对实际file_uri与MPD可播放URI，不能假定不同文件根天然映射；当前adapter没有自动root映射。不得擅自新增MPD元数据导入或替代唯一Library合同。用户已通过异步问题收到上述选项及IPv6/音乐目录所需信息。

本轮没有产品/测试/依赖修改，没有重复跑suite，没有Git整合；B10仍OPEN，真实功能Gate等待准备信息及用户独立反馈。此前agent联网测试方案被本节用户澄清替换，A01自动结果保留原轮次归属。
