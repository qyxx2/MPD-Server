# Task 9 B09 acceptance — T9-B09-A01

2026-10-11（Asia/Shanghai）。B09 **CLOSED / HUMAN PASSED**；implementation/automated/Contract/Relationship/LAN证据见所属执行轮次，用户最终验收见文末。B01–B09 CLOSED / HUMAN PASSED；B10未推进，Task9整体未完成。feature/task-9-web / HEAD14c6239，既有dirty成果保留，无commit/push/PR/merge。

## 范围与当前合同

- Settings About独立读取`/api/system/mpd`，严格MPDInfo decoder，展示版本/验证来源、连接、统计、更新及观察时间；null为破折号，实际0保留0，读取/字段错误仅顶部详情；epoch/generation/请求serial拒绝迟到。
- NAS_DAC启停迁入持久OutputActions→TaskActions；confirmed只从canonical snapshot/观察事实派生，REST alias回执不覆盖。跨页pending/unknown保留，原key/payloadretry；确认后只读，读取失败保持恢复。服务端PREPARING/SWITCH_FAILED进唯一顶部通知；Player仍只有确认摘要；CLIENT_STREAM禁用。
- LibraryTabs共用原分类标签风格，播放列表、收藏位于年代前；仅标签条横向滑动，自动使选中项可见，列表页保持选择。移除原两个独立列表链接；既有route/详情/动作不改。
- 用户明确MPD地址**保存配置，服务重启后生效**。架构末尾SYS-MPD-CONNECTION-001 FROZEN；独立最小文件owner/API，无通用Task10模块、无schema/依赖变更。文件默认SQLite同目录`mpd-connection.json`，可用MPD_CONNECTION_PATH指定；保存文件优先，首次无文件才解析环境默认。密码仍部署环境提供。保存仅原子落盘，不热换Player/能力/业务。GET区分active/saved/restart_required；HTTP确认后GET重读，草稿离页丢弃，已发intent持久恢复。new epoch清旧active和重启提示，同epoch断线显示最后确认地址（过期）并禁写。

Contract→owner→proof：T9-SETTINGS-001（Output §6/About §7、Architecture §4.1/4.2）→Settings/OutputActions/TaskActions→settings/player-output及指定System关系测试；T9-MPD-CONNECTION-001→SYS-MPD-CONNECTION-001→MPDConnectionService/main/system API及MPDConnection owner/Panel→test_mpd_connection/settings；T9-LIB-NAV-001→Visual末尾用户补充→LibraryTabs/三个list views→settings入口关系＋Library/Playlist/Favorites回归。

## Fresh自动证据

- 新Settings最初5项因页面占位/旧入口行为RED→GREEN；地址保存跨页原key关系另行RED→GREEN；审阅两项Important精确RED→GREEN：合法saved优先于无效旧环境、new epoch清旧地址/重启提示。
- Settings + player-output **13 passed**（早期6+7）；最终Settings新增epoch proof后 **7** 项纳入指定关系与完整回归。
- 最终指定Web **103 passed / 9 files**：`npm --prefix web run test -- --run tests/invariants/settings.test.ts tests/invariants/player-output.test.ts tests/invariants/global-notices.test.ts tests/invariants/player-facts.test.ts tests/invariants/wire.test.ts tests/invariants/library-collections.test.ts tests/invariants/playlists.test.ts tests/invariants/favorites.test.ts tests/invariants/shell-navigation.test.ts --maxWorkers=1`。
- 最终完整Web **284 passed / 26 files**，43.56s：`npm --prefix web run test -- --run --maxWorkers=1`。
- 指定后端 **57 passed**：`.venv/bin/python -m pytest -q server/tests/api/test_mpd_connection.py server/tests/api/test_system_reads.py server/tests/api/test_system_output_mutations.py server/tests/invariants/test_system_read_relationships.py server/tests/invariants/test_system_output_relationships.py`。
- 完整后端 **1466 passed**，126.51s：`.venv/bin/python -m pytest -q server/tests`。仅既有Starlette/httpx弃用warning，无环境变更。最终新文件排版后精确配置文件 **13 passed**；包含真实MPDInfo序列化→Web golden、真实文件/启动adapter选址、不改业务、验证拒绝、atomic replace失败、terminal失败落盘保留/同key安全retry与replay冲突。
- typecheck、生产build、定向Ruff、git diff --check通过；build目标为自有git-ignored runtime，外部outDir不自动清空的Vite提示属预期。未改.venv、依赖或既有DB。
- 独立只读审阅两个Important已修复并独立复验；无未关闭Critical/Important/Minor。

失败归因：旧system路由白名单按获准GET/PUT最小扩展；旧OutputPanel行内测试迁移到持久壳/顶部断言，unknown retry/read失败关系由Settings补齐，原确认、alias、epoch、只读、metadata隔离、服务端请求与Player摘要断言保留。raw wire fixture带SWITCH_FAILED，用于wire解析；普通playerState测试baseline改为无未解决请求，Output失败测试显式注入，避免有效新全局warning污染“无通知”场景。Settings GET在support提供独立读取，不占用旧mutation传输序列。配置不改Output测试保留除自然读取updated_at之外全部Output字段；未压制 legitimate failure。表单测试用真实submit事件。LAN WS初次脚本错用不存在的`/api/ws`得到403，核对真实路由后`/api/realtime`fresh snapshot通过，非产品/环境故障。

## LAN / 辅助浏览器

当前地址：[设置](http://10.104.60.177:5186/settings)，title `MPD-Server · T9-B09-A01`；[音乐库](http://10.104.60.177:5186/library)。当前wlan0 IP已重新读取。自有runtime `.superpowers/sdd/task-9-b09/runtime`，native backend8012显式Mock、新SQLite、preview5186同源REST/WS；旧批次服务/DB未修改。

LAN HTML/JS/CSS与自有production产物字节一致；GET system/mpd、connection、state均200；`ws://10.104.60.177:5186/api/realtime`交付真实snapshot。自有Mock REST已验证saved新地址而active不变、GET一致、业务Queue/Playback/History/revisions/epoch不变；配置随后保存回active地址，未删除文件。NAS_DAC off/on均SUCCEEDED且保留业务事实。无live MPD请求。

实际浏览器320×740：Settings页面/内容无横向溢出（document320/scroll320；content273/scroll273），表单/输出/About可滚动；Library仅标签条横滑（width288/scroll527，document320），进入播放列表/收藏后选择态正确、对应已完成列表呈现，导航/背景保持。桌面辅助不抵扣手机触摸Gate。

## 最少手机验收（H09/H10及新增入口，M01/02/03/04/05）

1. 打开音乐库，横向滑动分类标签；播放列表和收藏在年代前，分别进入已有列表，选中态明确，无另一个独立链接。
2. 设置页滚动查看About：版本/来源可辨，未知统计为“—”，原因仅顶部；停用NAS_DAC后到Player确认摘要变化，再返回启用。CLIENT_STREAM不可点击。
3. 主机/IP填`192.0.2.9`、端口`6601`并保存：当前地址不变，已保存地址改变；顶部说明“服务重启后生效”。换页/刷新后保存值仍在；软键盘不遮保存/返回。不需要实际重启，此地址只用于自有Mock验收、不会连接。
4. 已加载设置页断开网络：保存/输出不能写；恢复同一Wi-Fi后可操作。操作后迅速切页，顶部仍承接正在进行/失败恢复（复杂unknown/原key已自动证明，无需人为制造超时）。

等待用户反馈，HUMAN Gate未关闭。真实MPD/NAS/DAC **NOT RUN**；PWA **DEFERRED**；G9-02未送达并发窗口与既有ArtworkRef单Song REST500为批次外限制，本轮未改。不推进B10。

## 2026-10-11 A02：用户认可原测试，局部布局整改

用户确认“测试项没问题”，随后要求标签排序、DAC同行开关、实际重启入口与地址同行输入。原A01功能测试按本次认可接受，不编造逐项真人日志；当前新增表示仍 **OPEN / HUMAN PENDING**，B10不推进。

- 最新标签顺序：全部歌曲、专辑、艺术家、收藏、播放列表、风格、年代、标签。唯一入口/横滑/选择与已接受列表功能保持。
- NAS DAC状态行末尾提供单一开关；checked只来自canonical已确认ACTIVE/INACTIVE；pending时不提前切位置。未知/不可用不声明checked，stale/断线/unknown intent禁写；显式enabled布尔目标、共享key/恢复与顶部反馈不变。
- 地址同一行：可收缩长域名/IP框、固定不可编辑冒号、四数字视觉宽度端口框。没有maxlength，合法五位端口不截断；长内容框内横向滚动，输入框/页面尺寸固定。
- 用户澄清“MPD 接入地址：域名/IP + 端口，不使用 HTTP 前缀”；原生TCP合同不扩展为HTTP/TLS，不能用剥除https前缀冒充安全连接。
- 用户询问IPv6：原后端验证器/连接层已允许裸IPv6。本轮补真实文件/API保存/读取/下次startup proof，Web提交裸host与完整五位port；组合表示改为`[IPv6]:port`避免歧义。真实IPv6 MPD网络连通仍NOT RUN。
- 当前Task10管理配置、Task11管理部署，但原计划没有设置页restart API。按用户允许后续Task处理，将真实设置页“立即重启”按钮及监管后端登记主Plan Task11待办，要求先冻结native/Compose监管、执行确认、配置生效/新epoch重连合同；B09不加入假按钮、进程自杀接口或部署操作。

自动：新开关canonical/双向显式目标与标签顺序两项RED→GREEN；IPv6组合显示RED→GREEN。设置/输出2文件 **16 passed**；最终指定9文件 **105 passed**、完整Web26文件 **286 passed**（38.70s）；命令与A01相同范围。新增IPv6 API精确节点 **1 passed**、配置文件最终 **14 passed**；后端生产代码未变化，不重复全套后端。typecheck、production build、定向Ruff、diff check通过。聚焦独立只读审阅无Critical/Important/Minor。

LAN当前仍[设置](http://10.104.60.177:5186/settings)，title更新`MPD-Server · T9-B09-A02`。当前wlan0 IP、HTML/JS/CSS字节、三个GET200及同源`/api/realtime`snapshotfresh核验通过。继续使用A01自有SQLite/Mock，不重启或删除服务/数据库。保留用户已保存的验收地址/列表操作结果；agent本轮仅填写未提交的长IPv6/五位port草稿验证布局，离页丢弃，不覆写保存值。

实际浏览器320×740：document/scroll均320；host框185.20px、端口54.58px，输入长IPv6与16600前后尺寸相同；DAC开关52×44px，与状态row340.02–384.02同一行末尾。实际DOM标签顺序和收藏选中确认。浏览器缩窄不是手机触摸验收。

手机最少复核，仅新增表示：① 收藏在艺术家后、播放列表在收藏后，横滑选择可用；② DAC同行开关启停手感与确认位置；③ 同行地址框/固定冒号/端口协调，长文字及五位端口框内可查看、键盘下保存可达。原A01其它测试不重复要求。反馈前B09仍OPEN，真实MPD/NAS/DAC/IPv6连通NOT RUN，PWA DEFERRED，无commit/push/PR/merge。


## 2026-10-11 B09最终关闭：CLOSED / HUMAN PASSED

用户最终反馈：“验收通过。无需重复测试。记录更正需要的文档。”结合此前“A01测试项没问题”，接受B09原功能及A02标签顺序、DAC同行开关、同行地址输入与IPv6组合表示。H09/H10、M01/M02/M03/M04/M05及A02局部手机Gate按用户整体验收关闭，不编造逐项操作日志。

自动验证及LAN证据沿用本报告/验收记录的A01、A02所属轮次；本次仅更新必要文档并检查文档差异，未重复测试、构建、环境或网络验证，不新增自动证据。B01–B09 **CLOSED / HUMAN PASSED**；B10未启动，Task9整体未完成。此前OPEN/PENDING为历史状态，以本次最终关闭为准。

真实MPD/NAS/DAC及IPv6网络连通仍NOT RUN，PWA DEFERRED；设置页真实立即重启入口及监管后端仍为Task11待办，G9-02与既有ArtworkRef单Song REST500批次外限制保持。未改产品代码，无commit/push/PR/merge。
