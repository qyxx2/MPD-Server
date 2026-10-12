# Task 9 B04 剩余范围验收

当前Gate（2026-10-11）：完整B04 **CLOSED / HUMAN PASSED**；用户明确验收通过并要求不额外复测。最终关闭依据见文末；此前OPEN/PENDING及A01复制语义为历史。

## 2026-10-11 B04剩余续作：合同裁决与最小计划

用户授权当前dirty checkout继续B04剩余范围；feature/task-9-web / HEAD14c6239已重新核验，既有修改保留。B01/B02/B03及B04点击/拖动、A04/A05维持CLOSED，旧OPEN/PENDING及“本轮不实施”仅指历史轮次。完整B04 IN PROGRESS / HUMAN PENDING。

| 冲突/共享接口 | 裁决（既有Spec/API为准） |
|---|---|
| Queue默认整行播放 vs Next/Add菜单 | 独立更多按钮；整行精确queue_item_id播放不变。Next/Add按song_id创建新MANUAL occurrence，不移动/去重旧项，不抽取B05 SongRow。 |
| “清空”可能误作Stop/全部Queue | DELETE item按queue_item_id，可作用current/Played/pending；DELETE queue只清UpNext，服务端AutoPlay补充、current删除后继/停止及History规则原样保留。 |
| 可见候选子集 vs 保存完整UpNext | POST save-as-playlist仅{name}，服务端在事务内读取提交时完整UpNext；不含current/Played、不去重、重复拒绝零半成品。HTTP确认后state及Playlist列表重读。 |
| 页面草稿 vs 跨页恢复 | 菜单/名称/确认草稿离页丢弃；已发intent交持久TaskActions，unknown原key/payload重试；confirmed/read失败只读；epoch退役、断线禁写。 |

执行清单：
- [ ] 新Queue Next/Add/delete/clear独立入口行为测试RED，保存{name}/名称草稿/unknown/读失败/重复失败关系测试RED；真实Playlist DTO序列化及完整UpNext/重复/写入回滚后端proof。
- [ ] 最小QueueActions + Queue局部菜单/清空确认/保存输入；共享壳/唯一通知及冻结展示/排序不变；PB-SONG-NOW-001、PB-STOP-LIFECYCLE-001不改。
- [ ] 精确节点→Queue动作/保存文件→Queue表示、wire/resource-cache/mutation/player/global-notices/shell/global-artwork；后端QueueManager/save节点→文件→mutations_playback/idempotency/realtime_queue/realtime_history/playlist_relationships/realtime_playlist/stop_lifecycle/song_play_now/control_target；完整Web、typecheck/build，定向Ruff及diff检查。
- [ ] 独立审阅；新的自有SQLite/Mock手机URL及版本，LAN产物/同源API/WS核验，窄屏/键盘/入口/操作收敛辅助验证。
- [ ] 用户手机H03/H04/H10、M01/02/03/05反馈后才关闭完整B04。

G9-02未送达并发窗口保留，无expected_revision或新公开字段。ArtworkRef单Song500批次外未修复；真实MPD/NAS/DAC NOT RUN、PWA DEFERRED。不commit/push/PR/merge，不推进B05。自动、Mock、真人证据分开记录于B04 acceptance。

## 真人最少验收标准（尚未执行）

1. 独立更多入口Next/Add，各创建新项、同曲重复保留，不能触发行播放；原整行点击/待播拖动保持。
2. 删除一条重复项只删除选中occurrence；Played删除不删永久History，current删除按服务端确认后继。清空确认可取消；执行后current/Played保留，可能显示补充AutoPlay，不冒认Stop。
3. 保存名称软键盘可达；重复UpNext保存顶部拒绝，名称保留且无半成品；agent准备唯一UpNext场景后保存成功，服务端列表证明含隐藏候选、不含current/Played。
4. 断线新动作禁用无补发；如回执未知，跨页顶部保留原操作恢复；成功收敛后临时通知撤下。

以上由手机真人反馈关闭；浏览器/Mock与自动proof不抵扣。

## T9-B04-A01 实施与fresh验证（2026-10-11）

**实现已完成；自动与Mock辅助验证通过；完整B04 HUMAN PENDING / Gate OPEN。** 不重开B01/B02/B03、点击/拖动子集或A04/A05。

### 实际变更

Queue行独立⋯入口提供Next/Add/delete；整行queue_item_id播放和既有drag不变。Next/Add按该occurrence的song_id创建新项，仅fresh AVAILABLE可用；delete精确item、DELETE queue明确清空待播并本地确认。当前/Played删除和AutoPlay补充完全由既有PlaybackService编排，不增加Stop或其他公开字段。

Queue底部保存入口只有name草稿，POST{name}后以真实Playlist DTO解码，再由共享TaskActions权威state + Playlist列表重读收敛。失败保留名称、离页丢弃本地草稿；已发intent跨页持久、unknown原key恢复、confirmed读失败只读。同页原key恢复成功同步收拢原保存表单；epoch改变取消旧确认/菜单/名称草稿。新增浮层仅操作内容，错误/unknown仍唯一顶部通知，成功不累计。无B05 SongRow/Library功能。

### fresh自动证据

| 范围 | 本轮实际结果 |
|---|---|
| 首轮行为RED | Next/Add/delete独立入口3项、clear确认1项、save4项因功能未接入失败；实现后GREEN。首轮watch初始化错误已按完整trace修复；断线fixture补共享Player重连state读取，不改其合同。 |
| 审阅修正RED→GREEN | 同页unknown保存恢复、旧epoch清空确认、过期AVAILABLE门禁、不可用菜单焦点4项各精确复现后通过。 |
| Web目标关系10文件 | 131 passed（审阅修正前）；最终完整Web包含所有关系与修正。 |
| 最终完整Web | **237 passed / 20 files**，full-web-final.log；QueueActions32、queue-save6、queue-view8。 |
| 后端保存新proof / DTO样本 | 3个真实Service/SQLite proof + wire3 = **6 passed**；完整UpNext含AutoPlay、current/Played排除、same-key replay、重复400零Playlist/revision变更、第二成员写失败整笔回滚。现有功能证明，不冒充产品RED；初始测试对AutoPlay/末尾顺序/Mock方法的错误假设已修正。 |
| 后端精确既有节点 | clear仅UpNext、save范围不改Queue、API mutation delegates **3 passed**。 |
| 后端指定关系13文件 | **157 passed**，backend-relationships.log：QueueManager、mutations/idempotency、realtime_queue/history、playlist_relationships/realtime_playlist、stop_lifecycle、API/invariant song_play_now、control_target、wire及新queue_save。 |
| 完整后端 | **1446 passed**，115.17s，full-backend.log；仅既有Starlette/httpx弃用warning。 |
| typecheck / production build | PASSED；83 modules，产物位于本轮独立ignored runtime/dist，未覆盖旧验收dist。Vite只提示outDir在项目外不会自动清空；该目录本轮新建。 |
| 定向Ruff | 新queue_save与wire fixture All checks passed；初次新增import排序I001已仅交换两行，未全仓fix。 |
| 环境 | 既有.venv Python3.14.4 / pytest9.1.1 / ruff0.16.9，requirements已读，环境/依赖未修改。 |

日志位于ignored `.superpowers/sdd/2026-10-10-task-9-web-batch-plan/b04/`。覆盖重叠的数字不相加成独立总数。

### 独立审阅及裁决

requesting-code-review独立只读审阅完成，3项Important及1个epoch边界均裁决修复，4项精确RED→GREEN，随后最终完整Web237通过。没有剩余Critical/Important或延期Minor。审阅者Queue34/后端6是其审阅时结果，不当作最终作者237/1446。未发确认草稿属于当前epoch，因此epoch改变取消；无需expected_revision。

### Mock / LAN辅助证据

实际同Wi-FiURL **http://192.168.3.18:5177/queue**；title **MPD-Server · T9-B04-A01**。wlan0 IP192.168.3.18重新核实；新preview0.0.0.0:5177代理本轮127.0.0.1:8005，独立新SQLite/真实Services/MockPort并启用真实单调时钟。旧8004/5176及其数据库保留。初次launcher缺PYTHONPATH导致import失败，已以PYTHONPATH=.启动，不是产品故障或依赖缺失。

HTML/JS/CSS LAN响应逐字节等于本轮dist：JS index-Djz0zYqv.js SHA256 `d386e006f6a90ae9d546e690eb8ece15dad53721f0a0a67406b21efa986f8d7e`；CSS index-Bt559FUZ.css SHA256 `1d72d3093dc9949389740ce4a6ae0ad8890e00e92238953e568ca0b1a0043ee6`。同源state及所有样本Song GET200，WS首完整snapshot protocol1通过。

辅助浏览器实际窄屏innerWidth341、Queue clientWidth=scrollWidth309；菜单聚焦、输入、取消可达。Next新MANUAL occurrence、Add新手动项、精确delete后同曲原AutoPlay occurrence仍存在。重复保存顶部400、名称保留，服务端无该名称Playlist；clear后current ID保留、Played11保留且AutoPlay补两项；只预览第一候选时成功保存两条完整候选，服务端列表与完整pending逐项一致。旧重复失败通知仍作为原失败事项保留，没有新增成功事项。暂态播放重同步“需明确选曲”收敛后撤下，不改既有Player合同。

最终场景已复位multi-played+pause，重复MANUAL待播、Played隐藏、current暂停，浏览器reload清除自有测试页面内存intent；不会在用户观察时自动换场景。截图/runtime raw及自有数据库均ignored，不进入提交。真实MPD/NAS/DAC **NOT RUN**，PWA **DEFERRED**，浏览器不抵扣真人触摸/软键盘。ArtworkRef单Song500仍批次外未修复，本轮无封面Mock不能证明该缺陷消除。

### 最少手机验收（等待反馈，不提前关闭Gate）

1. 确认A01版本。点一行⋯，分别Next/Add：各增加新条目，原重复仍在，菜单不触发整行播放；删除其中一条重复只删该条。可用待播存在时删除current应由服务器确认后切后继。
2. 在重复待播尚存在时保存名称：拒绝原因在顶部，名称保留、键盘下保存/取消可达，无半成品（agent核对服务端）。
3. 清空先取消一次，再确认：current/Played保留，可能出现AutoPlay候选；随后保存另一名称成功，表单收拢，成功事项收敛后撤下。agent按完整服务端UpNext核对包含隐藏候选。
4. 断线时⋯动作/清空/保存禁用，无排队补发；恢复后可用。若遇unknown，跨页顶部原key恢复；成功后不能重复留原保存表单。

适用H03/H04/H10、M01/02/03/05；不要求重做已通过播放进度/拖动手感/Queue展示。用户反馈之前完整B04 **OPEN / HUMAN PENDING**，B05及其它Batch未推进。无commit/push/PR/merge。

### 最终Git核验

git diff --check通过；实际diff/stat/status已检查。相对启动时dirty baseline的tracked差异仅Playback Spec、Visual Spec、wire fixture Python/JSON及Queue CSS；新增Queue/UI/audit/Batch/acceptance文件原多为untracked，本轮新增queue-save Web/server proof。server/app既有dirty diff逐文件与baseline一致，未修改Python产品、PB生命周期或既有A04/A05 owner。无环境/依赖、DB或runtime进入Git status。分支feature/task-9-web、HEAD14c6239不变，无commit/push/PR/merge。

## 2026-10-11 A01用户反馈：仅Queue Next/Add语义需修正

用户：“别的都可以，但是下一首和添加到队尾这两项为什么是创造一个重复曲目？我要的逻辑是移动过去而不是复制过去。”其它已交付B04范围获得本次整体反馈接受；不编造逐场景日志。Next/Add复制语义未通过，完整B04仍OPEN，A01自动结果仅历史证据。

本轮修正已明确部分：Queue快捷操作必须移动精确原queue_item_id，条目总数及同曲其他occurrence身份保持，不能调用song-id新入队接口。待播项可沿用既有PUT item/before_queue_item_id，与drag一致；下一首是完整UpNext首位，队尾是完整UpNext末尾，均包含隐藏候选。current/Played能否移动尚待用户确认：现有reorder只接受position>0，支持current/Played会改变生命周期合同，不能暗改。普通歌曲（未来B05）Next/Add入队语义不因此改变。

最小验证计划：新精确移动测试RED→pending shortcut GREEN→Queue动作/保存/展示及Player/壳/通知关系→typecheck/build；后端既有reorder/Queue并发/History/幂等关系Gate，不改服务端或G9-02。提供新label手机页只复测两个入口；其它已通过行为不重做。

## T9-B04-A02：Queue快捷移动修正交付（2026-10-11）

用户已确认“仅待播项提供移动入口”。此前A01 Next/Add按song_id创建occurrence的说明/测试/自动结果为历史；本次只修正Queue快捷移动语义。其它B04行为本次用户“别的都可以”已接受，不重测或优化。完整B04仍OPEN，等待A02两个入口真人复测。

QueueActions.move以原queue_item_id发PUT；next的before是完整pending首项（含隐藏候选），tail的before=null；已在完整首尾本地no-op。只有position>0入口与action均可执行；current/Played菜单只删除，整行播放保持。标签“移为下一首/移到队尾”，不再暗示复制。原song-id Next/Add API及未来普通SongRow合同不改，source/隐藏候选/队列成员不由客户端重建；继承原drag的服务端权威、互斥、原key及G9-02限制。availability门禁是A01新入队的历史规则；移动继承reorder，metadata仅表示，服务端裁决既有可用性/确认边界。

fresh证据：
- 精确RED：2个请求仍POST、2个current/Played移动入口、2个首尾no-op、unknown移动重试，共7失败；delete既有精确行为通过。最小修正后精确8通过；新增hidden-first节点1通过。不是import失败。
- Queue三个文件修正后50通过（加入hidden节点前），最终QueueActions37/表示8/save6已包含在完整Web。
- 受影响Queue/Player/通知/壳/幂等关系7文件 **99 passed**；最终完整Web **242 passed / 20 files**，move-full-web.log。
- 后端精确QueueMoves新proof + 既有reorder节点 **2 passed**；新proof验证duplicate occurrence首尾移动保留全部ID/song/source/context、current/Played、History及原key replay不再次移动。
- 后端指定8文件 **104 passed**（queue_moves、queue_manager、mutations_playback、idempotency、realtime_queue/history、control_target、stop_lifecycle），move-backend.log；既有Starlette/httpx弃用warning。没有Python产品修改，本轮未重跑完整后端，A01的1446只作历史证据。
- typecheck/build **PASSED**，83 modules；新queue_moves定向Ruff **All checks passed**。无依赖/环境修改。
- 独立只读审阅：未发现Important/Critical，作者随后最终完整Web242通过；审阅者独立QueueActions37及queue_moves1通过，无延期项。

实际新手机URL **http://192.168.3.18:5178/queue**，title **MPD-Server · T9-B04-A02**。新preview5178代理本轮新8006，独立SQLite/Services/Mock+advance_clock，未改变旧5177/8005或5176/8004验收环境。wlan0 192.168.3.18重新核对。HTML/JS/CSS LAN响应逐字节匹配dist-a02；JS index-CrstopWR.js SHA256 `dddd39eb7f5fb39fe748cdcab80bd838e119d162d8ef3607ad4b7d9f1b82edd5`；CSS index-Bt559FUZ.css SHA256 `1d72d3093dc9949389740ce4a6ae0ad8890e00e92238953e568ca0b1a0043ee6`。同源state、所有所需Song GET200，WS initial snapshot protocol1通过。

Mock浏览器实际操作第二条同名MANUAL occurrence `f7513708-f927-56c1-b37a-3efa406ed3c3`：移为下一首后完整position1，再移到队尾后position7；before/after REST全量集合逐项比较，ID/song/source/总数不变，current及Played条目不变，同曲其它occurrence保留。有4条隐藏候选，快捷操作不以可见行重建队列。截图move-runtime/move-menu.jpg及raw JSON/日志均ignored；临时窄屏viewport已撤销。当前Mock暂停current/三条MANUAL待播可用于复测，未在交付后自动换场景。

最少真人复测：在A02点一条待播⋯→移为下一首，再选同一条⋯→移到队尾；只改变位置、没有新增同曲条目；current/Played没有这两个入口。已在目标时再点不得复制。其它已通过项无需重做。真人反馈前完整B04 **OPEN / HUMAN PENDING**；实现/本轮自动/Mock验证已完成。真实MPD/NAS/DAC NOT RUN、PWA DEFERRED、ArtworkRef单Song500批次外未修复。既有dirty保留，无commit/push/PR/merge，B05未推进。

## 2026-10-11 最终用户验收关闭记录

用户明确反馈：“验收通过，记录一下。不需要额外的复测”。结合此前“别的都可以”及仅待播移动的边界确认，T9-B04-A02快捷移动真人验收通过，完整B04 **CLOSED / HUMAN PASSED**。B01/B02/B03及已关闭点击/拖动、A04/A05保持CLOSED。

最终Queue语义：仅待播项提供“移为下一首/移到队尾”，移动原queue_item_id到完整UpNext首位/末尾，不复制、不增加条目；current/Played保留整行精确播放和删除。删除/清空/保存及共享恢复沿用已接受合同，保存由服务端读取完整UpNext、不含current/Played、不去重、重复拒绝无半成品。A01复制语义及此前OPEN/PENDING段落保留为历史，不再作为当前状态。

关闭依据为A02既有实际自动/Mock证据与用户本次明确验收；不新增逐场景真人日志，不将历史测试计为本轮新执行。本轮只记录状态，按用户要求未复测、未改产品代码、未修改环境/依赖或验收场景。最近A02完整Web242、后端关系104及typecheck/build/定向Ruff结果仍属于A02实施轮次；A01完整后端1446属于其原轮次。

交付版本T9-B04-A02，手机URL http://192.168.3.18:5178/queue。G9-02已知未送达并发限制保留；真实MPD/NAS/DAC NOT RUN，PWA DEFERRED，ArtworkRef单Song500仍批次外未修复。未启动B05或其它Batch，Task9整体未完成。

重新核对feature/task-9-web / HEAD14c6239；所有既有未提交修改保留。无commit/push/PR/merge。
