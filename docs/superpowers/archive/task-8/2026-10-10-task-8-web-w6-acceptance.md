# Task 8 / Web Batch W6 acceptance

日期：2026-10-10（Asia/Shanghai）。当前轮次：**W6-A02**。仅 W6；**HUMAN PASSED，Batch 已关闭**。

| Gate | 当前结果 |
|---|---|
| implementation | DONE：A02按用户反馈修复 Player 提示行造成布局跳动；详见末节 |
| automated Gate | PASSED：本轮 fresh Web / wire / P3 / typecheck / build，见下文 |
| Contract Matrix / Relationship Gate | REQUIRED / PASSED；继承合同不重新定义 |
| native / LAN environment | 本机 READY；A01/A02手机验收已确认 |
| W6-H01 / Task-level 手机 Web acceptance | HUMAN PASSED；A01其余项及A02受影响项均由用户确认 |
| 真实 MPD / NAS / DAC | NOT RUN；明确注入 MockMPD、自建静音媒体及独立 SQLite，不证明声音、设备或位置精度 |
| PWA | DEFERRED：manifest / SW / 安装 / 冷离线壳不计入本轮 Gate |
| Task 9 前置 | 当前手机Web范围前置已满足；没有启动 Task 9 |

## A01 基线、前置与执行边界（历史轮次）

开始时分支 `feature/task-8-web-player`、HEAD `adf4171`；最近提交已核对。工作区已有文档、Web W1–W5、Node lockfile、fixture/tests 等未提交产物，全部保留。读取用户指定 AGENTS.override、文档地图、active Batch Plan、手机方法、主 Plan Task 8/依赖/Gate、Architecture §4.1–4.3/§12、相关领域/视觉 Spec、Task 6 消费合同、Task 8 audit 与后端前置计划，并核对实际源码和测试。

W3/W4 最新单份 acceptance 已关闭；W5 最后追加记录用户原话“以上通过”，A04 歌词 HUMAN PASSED/FROZEN、A06 比例/顶部反馈/Output移除/DAC摘要 HUMAN PASSED，原 Output 手机启停项 N/A。active plan 页首历史 PENDING 与其最新 W5 Gate/acceptance 不一致，本轮仅同步该摘要，不重认证历史真人结果。当前没有记录中仍未关闭的 W3–W5 必要真人问题。

W6 不是新功能 Batch。既有绿色回归不伪称 RED→GREEN；本轮未发现需修改产品的自动失败，未新增镜像测试。若手机反馈暴露合同缺陷，按精确 RED→GREEN、最小修复及受影响回归处理。本轮没有新背景、共享导航、Task 9 页面、song Play Now、PWA、依赖或后端业务变更，没有 commit / push / PR / merge。

执行裁决：按用户指定 dirty checkout 工作，保留现有 ledger/runtime/DB，不采用技能默认隔离、提交、清理或下一任务步骤；代价是须按本轮文件哈希审查并行窗口修改。W6 未关闭，不写任务完成 ledger 行。

## 本轮自动证据

从仓库根目录执行，全部 exit 0。Python 为既有 `.venv`：3.14.4 / pytest 9.1.1 / Ruff 0.16.9；Node 24.20.0 / npm 11.19.0。没有安装或修改依赖。

```bash
npm --prefix web run test:invariants -- --run
# 11 files / 161 passed
npm --prefix web run test -- --run
# 13 files / 165 passed
npm --prefix web run typecheck
# passed
VITE_ACCEPTANCE_LABEL=W6-A01 npm --prefix web run build
# Vite 7.3.7 / 57 modules / passed
.venv/bin/python -m pytest -q server/tests/api/test_web_wire_fixture.py
# 3 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_playback_control_target.py server/tests/invariants/test_playback_guarded_transport.py server/tests/api/test_playback_control_api.py server/tests/invariants/test_realtime_control_target.py server/tests/api/test_idempotency.py server/tests/api/test_mutations_playback.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_recovery.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_output_transport.py server/tests/invariants/test_d6_stock_joint.py
# 完整 P3 Gate（含 P1/P2 与指定回归）：123 passed
```

后端两次运行各有既有 Starlette/httpx deprecation warning，无测试失败；不据警告修改依赖。无 Python 文件变化，Ruff 本轮 N/A（环境工具存在已核对）。未运行 Docker、真实 MPD/NAS 或额外全后端 suite；计划指定 targeted P3/wire Gate 已显式运行。

完整输出位于 ignored `.superpowers/sdd/2026-10-09-task-8-web-batch-plan/w6-{invariants,web,typecheck,build,wire,p3}.log`。baseline 为 `w6-baseline.json`，LAN证据为 `w6-a01-lan.json`。日志是证据，不是新的并列验收记录。

## 最终 Contract / Relationship traceability

共同 11 字段及六个 Player rows 沿用 active audit §8、Architecture 与领域 Specs；本轮只汇总实际 owner 与 fresh proof。

| Contract / 来源 | 实际 owner / 消费链 | 本轮 proof |
|---|---|---|
| Architecture §4.1–4.2、§12 / RT-SNAPSHOT、CONNECT、DELIVERY、RECOVER、TX-IDEMP | api/wire → realtime → player store / resourceCache → AppShell / PlayerView | client、wire、mutation、realtime、resource-cache invariants PASSED；同源、坏首帧 fail closed、旧代次拒绝、水位覆盖、原 key retry、断线只读及完整首帧恢复 |
| WEB-PLAYER-FACT-001 / Playback §8.8–8.9 | snapshot actual/business → playerFacts / playerPresentation → PlayerView | player-facts 28 passed；actual 与最后业务分层、stale/unknown、handoff；不猜 Context |
| WEB-PLAYER-CONTROL-001 / WEB-SEEK-001、Architecture §4.2.1、Playback §7 | playerActions → immutable intent → REST receipt → realtime read → ProgressControl / PlaybackStatus | player-controls 28、player-seek 13 passed；目标、pending、原 key、迟到 receipt、旧观察等待、不串 occurrence |
| WEB-PROGRESS-001 / Playback §7.2–7.4 | player store readTiming → playerClock → 同一进度/歌词时钟 | player-clock 7 passed；有限外推、后台/暂停/过期停止、同样本不续命、后台 GET 不误开外推 |
| WEB-LYRICS-001 / Library §3.1 | server Song → lyrics parser / LyricsStage → 既有 actions seek | player-lyrics 10、lyrics unit 3 passed；offset/同时间 cue、文本选择、3秒跟随、scope 清理、plain/read_error/no lyrics，不改冻结行为 |
| WEB-OUTPUT-001 / Output §6–8 | REST alias decoder / 独立 OutputPanel + snapshot → Player DAC摘要 | player-output 9、wire 23 passed；请求/确认分离、失败保留 fact、未知参数、无 Output卡片；手机启停仍 N/A |
| PB-CONTROL-TARGET / RESUME / SEEK-TARGET、RT-CONTROL-TARGET | 当前 PlaybackService token owner → API schema/typed409 → StateService/GET/WS | 上述 P3 123 passed + wire 3 passed；fresh target、原位 resume、无 I/O capture、outer visibility、切歌后 terminal replay |

## 本次构建与 LAN 交付

产品 URL：**http://10.104.60.177:5173/**。浏览器标题：**MPD-Server · W6-A01**。本轮构建约14:48 +08:00；14:48:37 +08:00 核验页面和 assets 与 disk dist 逐字节一致，未使用 W5 的旧 JS。

- `index-CLy8F0RZ.js`：127463 bytes；SHA256 `11ba39c79d96567671e56fae5ce8147e6cadcec2e455c31b2d4790219c18f40c`。
- `index-B8QQ05hW.css`：8585 bytes；SHA256 `7b61a7c1402bb3187ef21e18184c43ef8c6a2f371c4477995af5929aa593cda9`。CSS 未变与保护基线一致。

当前 wlan0 `10.104.60.177/24`；排除 loopback、容器、tun/VPN。实际 preview PID **31597**、`0.0.0.0:5173`，其进程环境 `API_PROXY_TARGET=http://127.0.0.1:8000`；backend PID **7628**、`127.0.0.1:8000`，命令明确 `server.tools.web_acceptance --advance-clock --w5`。页面、`/api/health`、`/api/state`、`/api/system/output` HTTP 200；同源 `ws://10.104.60.177:5173/api/realtime` 首帧为 protocol 1 完整 snapshot，epoch `69a8cd61-43b1-4313-93c7-c5aa73f3ac33`、sequence 360，envelope/state 一致且 target 存在。sequence 随场景和观察继续前进。

复用既有独立 `w5-runtime` Mock 进程及数据库，所有旧DB保留。使用既有本地 scene 文件及受幂等保护的真实 API 准备正常曲 PAUSED 37秒、LRC 61行、offset500ms、35秒双cue、DAC模拟启用/参数未知；接下来三次下一首为：长标题普通歌词 → read_error fallback → 未知元数据/时长/无歌词。已有 Played 保留，可检查上一首。fixture 只推进模拟 elapsed，到终点不伪造自然完成。

预检 scene 切换保留了一个重复待播 normal，已用现有 `/api/playback/queue/items/{id}` 删除该夹具项、guarded seek恢复37秒，并核对最终三个 pending。首次准备脚本误用 `/api/queue/...` 得405；UI脚本误用“暂停”而实际名称“暂停播放”、误查 `.transport` 而实际 `.transport-row`，更正后操作/测量成功。这些是预检假设错误，无产品失败或代码修复。

辅助产品浏览器已核对新标题/实时连接、封面↔冻结歌词、resume37秒不归零、暂停、顶部同步与控件锁。本轮实际测得有效 viewport 323×547（设置目标355×601，未把目标冒充有效尺寸）；scrollWidth323，无横向溢出，控件底边约482.71px，保留约64px底部预算。浏览器 viewport 已复原。截图位于本地 visualizations 的 `w6-a01-player.jpg`。键盘、reduced-motion、无 blur 可用性由当前测试/CSS及先前辅助证据支持；本轮未伪称完成双浏览器/放大字体全矩阵。真人触摸、网络和后台仍待手机。

进程保持运行。以下供 AI/维护者重启或停止，**手机用户无需操作终端/数据库**：

```bash
.venv/bin/python -m server.tools.web_acceptance --runtime-dir .superpowers/sdd/2026-10-09-task-8-web-batch-plan/w5-runtime --port 8000 --advance-clock --w5
API_PROXY_TARGET=http://127.0.0.1:8000 npm --prefix web run preview -- --host 0.0.0.0 --port 5173 --strictPort
# 停止前核对 ps -p 7628,31597 -o pid,args；仅仍属上述验收进程时 kill 对应PID。
# 前台新进程用 Ctrl-C；端口被占用时不重复启动。重启产生新独立DB，旧DB不删。
# 产品变更后 VITE_ACCEPTANCE_LABEL=W6-A02 npm --prefix web run build，再核对实际assets/API/WS。
```

## W6-H01 综合手机验收卡

沿用已有设备记录 Samsung S20+ / Samsung浏览器 / 字体与页面缩放100%；系统及浏览器版本未提供，不编造，变化时补记。本轮手机可达与以下结果全部 **NOT RUN / HUMAN PENDING**。

| W6-H01 子项 | 实际手机操作与通过基准 | 状态 |
|---|---|---|
| a / M01、M02 | 刷新上述URL，核对标题W6-A01；竖屏页面比例/底部预留正常，无横向溢出，主按钮可点；Output卡片和Stop UI不恢复，DAC摘要保留 | PENDING |
| b / W4关键流 | 从暂停37秒继续→暂停，位置不归零；拖进度松手、再快速点播放/暂停，顶部反馈清楚、页面不跳动；下一首/上一首切换后身份与进度一致 | PENDING |
| c / W5关键流 | 封面进入歌词、右上角返回；播放高亮、拖动后停止约3秒恢复跟随；点cue跳转，长按选字不seek；下一首的普通歌词保持手动位置、read_error fallback和无歌词可辨、不串曲 | PENDING |
| d / M04 | 顺序下一首检查长中英文标题/缺封面与未知时长，必要时放大文字；结构/控件可达、unknown不显示为零、未知时长不能seek | PENDING |
| e / M05 | 已加载页面断开Wi-Fi及移动数据，再恢复同一LAN；断线显示只读/控件禁用，恢复完整状态后可操作，不补发离线点击 | PENDING |
| f / M06 | 正常播放时切后台或锁屏约10秒再返回；按服务新样本恢复，不显示虚假后台推进/串曲，不重复动作 | PENDING |

M03 N/A：Player无文字输入，软键盘不在W6范围。M07已有reduced-motion自动proof；必要额外辅助检查仍可在反馈后执行，不要求手机调试工具。若进入未知时长曲后需重置正常场景，告知 AI，由 AI 准备同一页面；不要求用户数据库、终端或开发者工具操作。W3 actual≠business复杂关系由fresh player-facts自动proof覆盖，需要可见异常时再由AI切换既有unbound/stale最小场景。

用户反馈及日期：**尚未收到本轮反馈**。可回复“W6-H01 全部通过”，或“W6-H01-e不通过：……，其余通过”。失败后在此记录追加新轮次、对应精确失败测试/修复、构建与需复验子项，必要项用户确认后才标记 HUMAN PASSED。

## Task 9 实际接口交接（候选，Gate待满足）

- `services/api.ts`：`createApiClient({fetch,origin})` → `realtimeUrl/get/createIntent/send`；immutable intent/key；`wire.ts` 的 `parseSnapshot/parseRealtimeFrame/parsePlaybackState/parseRestOutput/normalizeOutput`，未知protocol fail closed。
- `services/realtime.ts`：`createRealtimeClient({api,store,socketFactory,clock,now?})` → `start/stop/refresh`；AppShell唯一生命周期。`player.ts`：`createPlayerStore` 的只读 snapshot/writable/status/error/marker/readTiming；`beginConnection/acceptInitial/acceptRefresh/invalidate/markReadError/markDisconnected`。
- `resourceCache.ts`：`createResourceCache({load,dependencies})` → `entry/read/invalidate(marker,{force?})`；`library.ts/playlists.ts` 的注入decode薄包装及 `stop()`；Playlist依赖library+playlist，Favorites路径由既有wrapper接受。
- `playerActions.ts`：`createPlayerActions(store,{api,refresh})` → `act/beginSeek/preview/releaseSeek/cancelDraft/retry/refresh/dispose` 及 ui/facts/locked；`playerRuntimeKey` 注入。receipt 不成为 canonical，UI迁移不得丢intent/key或恢复断线写权限。
- 测试入口就是上述13个Web文件及P3/wire Gate；未来Task9先审计并交付共享壳/通知→背景→四项导航，保护Player和冻结歌词；不冒称这些未来UI或SongRow/Queue/Library/Playlist/Favorites/Search/song Play Now已交付。

## 独立审阅与最终范围检查

executing-plans 指定的一次 fresh-context 只读 reviewer（gpt-6-astra）已检查当前相关源码、测试、本轮日志、构建证据与开工哈希；Critical / Important / Minor 均无。296个开工文件在审阅时无变化；本轮随后只更新 active plan 的 Gate摘要及本份 acceptance。不进行第二次审阅或扩大实现。

reviewer 未判定事项及裁决：手机触摸/断网/后台必须留待W6-H01用户确认（代价：可能仍需W6修复）；物理DAC/MPD/NAS NOT RUN（代价：无真实设备认证）；新全局背景/持久壳/导航/其它通知统一归Task9（代价：W6不交付新UI合同）；PWA安装/SW/冷离线壳DEFERRED（代价：不提供安装和冷离线启动）；整个dirty分支的合并准备度及Task8整体完成不属于本次交付判定（代价：仍须独立集成与关闭Gate）。这些范围均来自用户/计划，不是reviewer自动放宽必要项。

结束前 `git diff --check` 通过，diff/stat/status已检查；按W6开工文件哈希核对，本轮只改变本Batch计划摘要/两项自动check，并新增此acceptance。其它原有296文件中除该计划外均未变化，包括冻结歌词、产品代码、测试、依赖与lockfile；新untracked记录单独检查行尾空白。没有DB/cache/dist进入Git范围。最终页面/health/state再次HTTP200，正常曲PAUSED37秒及三个指定pending已核对，进程继续运行。

W6结论：自动、Contract、Relationship及本机LAN交付通过；**W6-H01 HUMAN PENDING是当前关闭blocker**。本轮尚不满足Task9前置，不进入下一Task/Batch；不声明Task8整体完成。真实MPD/NAS NOT RUN，PWA DEFERRED。


## W6-A02：手机反馈修复及复验（当前轮次）

2026-10-10 用户反馈：“别的没有问题。唯一的问题为什么切歌的时候最下面会出现‘需明确选曲后播放’……导致上面的控件缩放并跳一下。”明确要求迁入上方appbar感叹号、点击详情或重试、恢复后消失，并检查Player其它附加说明行。A01其它必要项按本次反馈记HUMAN PASSED；唯一未关闭问题是提示行及本次迁移的受影响手机回归。A01上述未修改产品/未收到反馈等描述仅属历史轮次。

根因：PlaybackControls在切歌短暂失去pause/resume能力时插入条件p；flex布局重新分配媒体高度。最小修复仅在Player将selection、读状态失败、文件缺失/不可读、最后业务事实说明、封面加载/异常、歌词read_error/plain/malformed/missing/未确认进度迁入既有PlaybackStatus。连接断线详情同入口；正常“实时连接”不显示，保留隐形占位保护既有header尺寸。单个异常感叹号（纯同步仍沿用spinner），详情浮层不占正文高度，正常无提示即消失。歌词正文、标题/作者/专辑、源格式、DAC确认摘要、进度读数仍为事实内容。DAC详情仍沿用既有摘要title，本轮不扩展Output入口。

原key重试只在结果未知时提供；其它通知可重新读取状态，不因封面/歌词异常重放播放动作。操作结果和canonical诊断分别保留，不互相吞掉。没有修改canonical权威、WS状态机、token、clock、队列或冻结歌词解析/3秒跟随/选择/cue行为；LyricsStage只删除说明caption及其样式。用户此次明确要求是W6缺陷修复范围授权，覆盖先前将“剩余通知归一”留Task9的范围约束；全局背景/持久壳/四项导航和其它页面仍不实施。

RED→GREEN：新增player-notices精确复现底部selection/正文说明、并发read/file/lyrics、missing/plain/malformed、封面失败、结果未知与NO_CANDIDATES并存。断言先失败，再迁移；没有删测试/skip/xfail。旧事实/歌词测试改为真实Player的顶部详情及placeholder aria-label，保留所有合同区分。独立审阅发现Important：旧图片DOM load/error缺少当前资源身份校验，可能误报/清除新封面通知。新增迟到event测试先RED（旧error移除新img），以blob src身份校验最小修复，GREEN 8/8；未运行第二轮同内容审阅。首次canonical测试错误地更换目标而撤销旧操作，已按现有合同改用同身份NO_CANDIDATES；不是生产缺陷。首次targeted命令误列4个旧文件名，改正为以下实际8文件，并以全量结果交叉核验。

最终fresh验证（最后封面事件修复之后）：

```bash
npm --prefix web run test -- --run tests/invariants/player-notices.test.ts
# 8 passed
npm --prefix web run test -- --run tests/invariants/player-notices.test.ts tests/invariants/player-controls.test.ts tests/invariants/player-seek.test.ts tests/invariants/player-facts.test.ts tests/invariants/player-lyrics.test.ts tests/invariants/player-output.test.ts tests/invariants/player-clock.test.ts tests/invariants/wire.test.ts
# 8 files / 126 passed
npm --prefix web run test:invariants -- --run
# 12 files / 169 passed
npm --prefix web run test -- --run
# 14 files / 173 passed
npm --prefix web run typecheck
# passed
VITE_ACCEPTANCE_LABEL=W6-A02 npm --prefix web run build
# Vite 7.3.7 / 57 modules / passed
```

Contract/Relationship Gate PASSED：上述身份/目标/迟到事件/原key/只读/unknown及完整原Player回归通过，先前traceability保持适用。后端未改，A01 fresh wire3/P3完整123证据继续适用，不冒称A02重复运行。Node/Python依赖及lockfile未改。日志w6-a02-*-final.log及RED日志仅证据，不另建验收记录。

实际新构建LAN交付 2026-10-10T15:16:01.150227+08:00：URL **http://10.104.60.177:5173/**，运行后标题 **MPD-Server · W6-A02**。HTML和assets与磁盘dist逐字节匹配，标签在JS启动后设置（HTML静态title仍MPD-Server）。页面/health/state/output HTTP200；protocol1 WS首帧snapshot，epoch `69a8cd61-43b1-4313-93c7-c5aa73f3ac33`、sequence 567。wlan0/IP/监听/现有PID7628、31597再次核验；启动停止方法与A01相同，进程继续运行。

- `/assets/index-D14KtEFN.js`：128231 bytes，SHA256 `16688abfd6c7e0b4d425b94e6ba7fc16842ba5010dd040dca159abaf4cd5f9ac`。
- `/assets/index-BwypyLR0.css`：8651 bytes，SHA256 `03d59e6e2dc2a40a776e72f87b5a73c84aef6f472875c8e1fc50acb7e7177937`。

辅助浏览器有效viewport319×597，scrollWidth319；正常transport top469.48/height64px。实测切歌短暂selection只在header live region；普通歌词时打开/关闭顶部详情，transport和media几何完全不变。长标题本身增高导致媒体合理缩小，不由提示行挤占；transport位置不变。正常LRC恢复后感叹号count0。恢复封面模式与正常PAUSED37秒场景；待播long→lyrics-error→unknown，由AI使用既有本地scene/API准备，预检产生的本地重复normal已经既有queue API删除，旧数据库保留。fixture不代表真实MPD/DAC。viewport已复原；截图w6-a02-player.jpg。手机触摸反馈仍不能用辅助浏览器替代。

| 本轮需复验编号 | 手机操作/通过基准 | 当前状态 |
|---|---|---|
| W6-H01-a/b | 刷新同一URL核对W6-A02；在封面/歌词模式反复下一首/上一首，底部不再出现“需明确选曲后播放”，控件不因提示缩放或跳动 | HUMAN PASSED |
| W6-H01-c | 普通歌词/read_error/无歌词的说明仅在顶部感叹号详情；点开能读详情及可用恢复按钮，关闭不挤正文；正常LRC/封面恢复后相应感叹号消失；歌词选择/跟随/cue保持正常 | HUMAN PASSED |
| W6-H01-e（受影响通知位置） | 断网只读仍有效，异常说明在同一顶部入口，恢复后连接异常消失；不补发离线操作 | HUMAN PASSED |
| 其余A01必要项 | 用户“别的没有问题” | HUMAN PASSED |

需复验范围仅本次改动；若正常状态需准备，由AI准备，无需手机用户终端/数据库/开发者工具。implementation/automated/Contract/Relationship PASSED，LAN READY，**W6 HUMAN PASSED**。用户已确认本次受影响手机项通过，无剩余W6 blocker；当前手机Web范围满足Task9前置，不进入下一Batch。真实MPD/NAS NOT RUN，PWA DEFERRED。

范围核对：对296个开工文件的哈希，本轮只改变5个Player生产文件、2个相关测试和active Batch plan；另新增player-notices及本份单一acceptance。其它窗口的代码/文档/依赖/lockfile保持原样。git diff --check、stat/status及实际涉及文件检查通过；无DB/dist/cache入Git范围，无commit/push/PR/merge。


## W6 最终手机确认 / 关闭

2026-10-10 用户原话：“可以通过。快速验收不要搞一堆复核浪费时间”。结合此前“别的没有问题”，W6-A02受影响W6-H01-a/b/c/e及A01其余必要项均 HUMAN PASSED。implementation、automated、Contract/Relationship及LAN Gate已具备上述实际证据；没有新增代码或环境变更，本次仅更新验收/计划/ledger并检查文档diff，不重复测试、构建或手机复核。

W6已关闭，当前手机Web范围满足下一Task前置；上述实际接口交接可使用。无剩余W6 blocker。真实MPD/NAS/DAC NOT RUN，PWA DEFERRED，不能据此声称原始PWA范围或Task8整体完成。不进入下一Batch/Task9，不commit/push/PR/merge，验收进程保留。


## 2026-10-10 合并前实际状态核验

用户授权核对 Task 8 后全部提交、push 并合并 main。本轮核对实际 dirty checkout、最新手机确认及两个独立只读审阅，无当前手机 Web 范围合并 blocker。同步根 README 与文档地图的过期 W5/W6 摘要；不修改产品行为或重开真人验收。

Fresh 自动验证：Web 全量 14 files / 173 passed；invariants 12 files / 169 passed；typecheck/build exit 0；wire 与验收工具 6 passed；计划指定完整 P3 Gate 123 passed；后端完整 `server/tests` 1398 passed；新增 Python 文件定向 Ruff 与 diff check 通过。Python 使用既有 .venv，没有依赖或环境修改。仅既有 Starlette/httpx deprecation warning，无失败。

当前 W1–W6 手机 Web 范围通过，Task 9 前置满足；PWA DEFERRED，真实 MPD/NAS/DAC NOT RUN，原始 Task 8 整体验收仍不能宣称完成。真人结论沿用上节已确认记录，本轮未重新手机测试。提交排除本机配置、DB、缓存、dist 和 runtime；保留现有运行时文件与分支。
