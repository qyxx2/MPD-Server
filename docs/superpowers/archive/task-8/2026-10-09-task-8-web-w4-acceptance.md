# Task 8 Web Batch W4 acceptance

单份 W4 记录；日期 2026-10-09（Asia/Shanghai），当前 **W4-A10 / HUMAN PASSED / W4 CLOSED**（2026-10-10 更新）。HEAD `adf4171`，branch `feature/task-8-web-player`；未提交改动按本轮构建区分。仅 W4；W5/W6/Task 9 未实施。

| 状态层 | 当前结论与证据 |
|---|---|
| Implementation | DONE：transport（产品页已移除 Stop；后端与动作层保留）、guarded seek draft/receipt、有限展示时钟及必要共享接线 |
| Automated Gate | PASSED：A10 seek13、指定六文件99、invariants141、full Web142、typecheck/build；本Batch A05 fresh P3+wire126（后端生产未变）；既有本机 fixture/DTO5、定向 Ruff未涉及变更 |
| Contract Matrix / Relationship Gate | REQUIRED / PASSED；下表追溯到真实 API client/store/UI、时钟与后端前置 |
| Native / LAN | 本机 READY：wlan0 `192.168.3.18/24`，页面/API200、同源 WS initial 已核验；手机可达及断线恢复已由用户确认 |
| Human Gate | **HUMAN PASSED**：W4-H01、H02 normal/unknown、H03断线及后台/锁屏恢复均用户确认通过（2026-10-10） |
| 真实 MPD/NAS | NOT RUN：无真实 MPD/NAS/DAC、无音频/真实计时精度证明 |
| PWA | DEFERRED：不交付 manifest/SW/安装/冷离线壳 |
| Batch / 下一 Batch 前置 | W4 当前范围通过并关闭；W5 前置满足，但未实施/不自动推进；Task 8 整体未验收 |

## 产品页与当前最小场景

实际产品 URL：[http://192.168.3.18:5173/](http://192.168.3.18:5173/)。前端 `0.0.0.0:5173`，后端 `127.0.0.1:8000`，Vite preview 的 `/api` REST/WS 统一代理到 `http://127.0.0.1:8000`；手机只访问一个端口。排除 lo、ds-br0、tun0/VPN 地址，不改防火墙/路由。

当前 A10 normal（已恢复；实际位置/状态以实时snapshot为准）：`夜航 · 本地验收曲`，**PAUSED 约 0:37**，fresh target 与 5:00 Mock 时长；有 Queue 候选。通过实际 API 准备已知位置和暂停，等待 observer 的匹配样本后才交付。用户可继续/暂停、seek、上一首/下一首；无 Stop 按钮。相同产品页无独立控制台、无选曲页面、无公开故障注入 API。

首轮启动使用显式 AcceptancePlayer/MockMPD 注入、独立 `w4-runtime/phone-cd8ff6423b9f4281be54c849005e4b16.db`（当前owned DB为A09重启记录中的phone-c017145ca7cb4e7ca172c33e237e98c7.db） 与自建静音 WAV。`--advance-clock` 只在本机夹具内按单调时间更新 Mock elapsed；PAUSED/STOPPED 不推进，duration 到尾不制造自然完成。WAV 本身为短静音资源，Mock 5:00 不代表文件或设备实测时长。页面页脚显示模拟计时、不代表真实 MPD/DAC。

normal/long/unknown/unbound/stale 场景通过既有本地 `scene.txt` watcher/Service 准备。unknown 的 duration=null；用户不需要终端、数据库或开发者工具。正常场景反馈后，由 AI 切 unknown 供 W4-H02 子项，再恢复 normal 供其余验收；每次切换核验 API 后告知，不能把尚未展示的子场景标通过。

构建 W4-A03，2026-10-09 约 23:39，实际 preview 读取本次 dist：

- JS `index-pBIW4BcC.js`，SHA256 `7e2e00a49fa492e8df707f0cc6c75ab0a381bd6e9b4723bd5a86b9a1503aff12`。
- CSS `index-GNnpicdi.css`，SHA256 `3fbc89aaa3ef3705538920c98ba0c59a392aa7a597169230296d83f08e165476`。
- index SHA256 `6e5a65159333a86fce52a32d16eab34bcdf46fad0fa419c2c14c5b5a4ea1ce68`。

运行进程保留：backend PID **8456**（session59617），preview PID **8457**（session23180）。W3旧进程11213/11219已正常停止并复用同 URL；旧DB/场景/记录保留。以下为 AI 的复现操作，用户无需执行：

```bash
# 仓库根；每次后端启动创建新的独立 owned DB
.venv/bin/python -m server.tools.web_acceptance --runtime-dir .superpowers/sdd/2026-10-09-task-8-web-batch-plan/w4-runtime --port 8000 --advance-clock
# web 目录；已有本轮 dist
API_PROXY_TARGET=http://127.0.0.1:8000 node node_modules/vite/bin/vite.js preview --host 0.0.0.0 --port 5173 --strictPort
# 仓库根；通过原 API 准备当前暂停37秒场景，等待真实 observer，无 mutation 自动重试
.venv/bin/python .superpowers/sdd/2026-10-09-task-8-web-batch-plan/w4-runtime/prepare-paused.py
# 仅停止本记录所属进程；重启后重新查PID/端口/API/WS
kill 8456 8457
```

## 自动与合同证据

| Contract / owner | proof与fresh结果 |
|---|---|
| WEB-PLAYER-CONTROL-001 / playerActions、PlaybackControls | player-controls6：resume target/原位事实保留、pending lock/独立Stop、STOPPED不选曲、timeout原key、新意图新key、HTTP成功/read失败、旧Stop跨连接迟到拒绝 |
| WEB-SEEK-001 / playerActions、ProgressControl | player-seek6：拖动零请求/释放一次/409清草稿、changed token、server receipt.updated_at与observation.observed_at比较、keyboard单次/cancel/unknown duration、Stop与迟到seek、重复URI occurrence、实际后端短暂unknown期间保留同步反馈 |
| WEB-PROGRESS-001 / playerClock、store readTiming、realtime RTT | player-clock7：FakeClock6秒寿命、同sequence canonical不替换/重复sample不续命、暂停/stale/断线/后台停止、foreground重新锚定/旧GET不重开、duration到尾无命令、重复URI/epoch、真实realtime→timing→clock联合 |
| Architecture §4.1–4.2/§12 / 既有共用 owner | realtime15、mutation9、player-facts21 等回归；fresh initial才可写，旧代次/水位不倒灌，canonical无optimistic mutation |
| PB-CONTROL-TARGET / PB-RESUME / PB-SEEK-TARGET / RT-CONTROL-TARGET | 当前实际后端代码与 P3联合Gate重新核对；不是沿用计划勾选/历史结论 |

fresh命令与输出摘要（完整输出保留 ignored `.superpowers/sdd/2026-10-09-task-8-web-batch-plan/` 的 w4-* logs）：

1. `.venv/bin/python -m pytest -q server/tests/invariants/test_playback_control_target.py server/tests/invariants/test_playback_guarded_transport.py server/tests/api/test_playback_control_api.py server/tests/invariants/test_realtime_control_target.py server/tests/api/test_idempotency.py server/tests/api/test_mutations_playback.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_recovery.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_output_transport.py server/tests/invariants/test_d6_stock_joint.py server/tests/api/test_web_wire_fixture.py` → **126 passed**；实际 Pydantic扩展DTO与W1 fixture相等。后端生产实现未在本W4修改。
2. `npm --prefix web run test -- --run tests/invariants/player-clock.test.ts tests/invariants/player-controls.test.ts tests/invariants/player-seek.test.ts tests/invariants/player-facts.test.ts tests/invariants/realtime.test.ts tests/invariants/mutation.test.ts` → **64 passed**。
3. `npm --prefix web run test:invariants -- --run` → **106 passed**；`npm --prefix web run test -- --run` → **107 passed**。
4. `npm --prefix web run typecheck` → exit0；`VITE_ACCEPTANCE_LABEL='W4-A03 · Mock 本地验收夹具 · 模拟计时，不代表真实 MPD/DAC' npm --prefix web run build` → exit0。
5. `.venv/bin/python -m pytest -q server/tests/api/test_web_acceptance.py server/tests/api/test_web_wire_fixture.py` → **5 passed**；`.venv/bin/python -m ruff check server/tools/web_acceptance.py server/tests/api/test_web_acceptance.py` → GREEN。

环境：Python3.14.4/pytest9.1.1/ruff0.16.9，既有 `.venv` 可执行。Python只有现有 Starlette/httpx deprecation warning，未改依赖；W4未安装/修改Node依赖或lockfile（W1原修改保留），无Docker/真实服务访问。

首个seek RED为缺range；控件RED为缺按钮，之后GREEN。clock首次缺module属于collection failure，不能当行为证明；随后将仅本轮新clock退为observed-only，实际4条断言RED，再恢复有限外推GREEN。独立审查Important“后台时间累加”及派生旧GET边界精确RED→GREEN；LAN真实后端unknown观察交接也精确RED→GREEN。其余新增回归覆盖已有消费能力，不假称它们都经历新production RED。

独立只读review：无Critical；Important后台样本重用已在同一个修复pass修复并跑完整绿色回归，无第二次review。非阻断Minor保留：共享transport pending也显示“正在提交进度”，实际请求/锁语义正确，仅文案待细化。

## 手机验收卡与反馈

手机型号 / 系统 / 浏览器版本：本轮待用户确认（沿用此前设备时无需重报）；手机本轮URL可达确认：PENDING。Ubuntu/IAB仅辅助：真实A03可见、暂停/keyboard seek、本机320/390窄屏无横向溢出、控件约44px以上，页面不依赖blur；未以这些证据抵扣手机触摸/锁屏/reduced-motion实测。

| 编号 | 用户操作 / 可见通过基准 | 当前结果 |
|---|---|---|
| W4-H01 | 当前暂停约0:37，点继续→暂停→继续，位置不归零；下一首/可用的上一首改变实际曲目。复验三按钮布局与点按；Stop UI 项按 2026-10-10 用户指示 N/A，外部 STOPPED 不代选曲仍由自动 invariant 证明 | NOT RUN / HUMAN PENDING |
| W4-H02 normal | 拖动进度，移动时为预览、释放后反馈可读；上下滚动不误触；快速重复点按不造成重复副作用。取消/竞态/key次数由自动invariant证明，手机必测普通拖动释放 | NOT RUN / HUMAN PENDING |
| W4-H02 unknown | AI切unknown并确认后，同页显示时长未知，进度禁拖；保留可用elapsed只读，不伪造时长 | 尚待场景交付后的手机反馈 / HUMAN PENDING |
| W4-H03 | 已加载页面临时断网，显示只读/过期、按钮不可写；恢复同一LAN后新snapshot恢复。后台/锁屏后返回按服务器事实重新校准，不累加后台展示估计，不重复业务请求 | NOT RUN / HUMAN PENDING |

M01/M02必验；M04 unknown及窄屏适用，M05/M06映射H03；M03 N/A（无文字输入/软键盘）；M07既有reduced-motion规则且本批无新增装饰动画/blur依赖，辅助检查不能冒充手机反馈。

用户反馈（2026-10-10）：“目前看着没什么问题”，提出去除停止按钮、保留后端且页面不调用它。此反馈未逐项确认 H01/H02/H03，仍 HUMAN PENDING。正常场景可先反馈 H01/H02/H03；AI继续在同一个W4准备unknown子场景与必要复验。只有用户明确确认全部必要项通过后更新 **HUMAN PASSED** 并关闭W4。

## 轮次与实施裁定

A01（约23:30）为首个本机预检构建；A02（约23:34）修复后台时钟；A03（约23:39）修复实际后端observation短暂unknown期间seek同步反馈。此前没有手机通过项，当前A03全部必验项是首验，不是自动认可历史结果。

- 使用用户指定checkout、保留初始dirty，不另建worktree或执行commit/清理：代价是无额外并发隔离，靠 scoped review保护。
- 为W4添加共享readTiming与runtime injection，不建立页面canonical副本：代价是后来消费者须遵守同sequence/样本寿命约束，已留机械证明。
- 原本机fixture增加opt-in模拟计时与候选准备：代价是Mock依然不能证明真实设备位置/声响。
- 将active plan接口表同步至实际store-watching clock/actions签名：代价是W5须读实际导出接口，不沿用拟定accept(snapshot)副本。
- 手机Gate仅由用户反馈认证：代价是未拿到反馈前手机行为仍未认证；本机截图不是HUMAN PASSED。
- 只读review不替代typecheck/build/acceptance：代价是若未核验产物会交付旧代码，本轮已核验实际hash/标识。
- 真实MPD/NAS、W5/Task9/PWA、完整重开无关历史Batch不进入W4：代价是无设备/整体Task8证明，前置仅按实际消费范围fresh核验。

最终diff/check/stat/status检查：通过；原工作区W1–W3/Compose/Node/backend文档修改全部保留。W4改动限新4个player模块/组件、3个invariant文件/共用测试helper、Player与必要App/Shell/store/realtime接线、本机fixture及测试、active plan接口/状态、本文。无DB/缓存/dist/.venv/机器配置进入Git变更范围，无commit/push/PR/merge。

**结论：W4 implementation与automated Gate通过，LAN本机READY，HUMAN PENDING；W4未关闭，W5前置未满足。**

## W4-A04：手机反馈内最小修复（2026-10-10 00:58）

用户明确调整本 Batch UI 范围：不显示或调用停止按钮，后端 Stop 不改。此决定覆盖原 W4-H01 独立 Stop 的页面验收要求，不改变后端合同或 STOPPED 事实消费规则。只删除 PlaybackControls 的一个按钮和专属样式；动作层原实现未改，旧 Stop 跨连接/迟到 seek 竞态改为直接动作层验证，保持断言。新增产品三按钮/无 Stop 请求 invariant 精确 RED（实际仍有第四个按钮）→GREEN。

A04 fresh evidence：controls+seek 13 passed；计划六文件 targeted 65 passed；full Web 108 passed（invariants 107）；typecheck exit0；带 A04 标签 build exit0。Relationship/Contract Gate：真实 AppShell→PlayerView→PlaybackControls→API/store 接线及原目标捕获、幂等 key、锁、seek、clock 65 项回归通过；仅用户明确批准的 Stop UI 范围例外。后端生产代码/依赖没有本轮改动，P3/DTO 的本 Batch fresh 126 passed 证据保留。

当前 dist：JS `index-CtfnihHW.js` SHA256 `d0139a65e720cd6cef3c5c2f0bf63e5919d095c224091a68497f4a61cbb46302`；CSS `index-CL7SWMz8.css` SHA256 `a6693430cb47766b2630b5cfa5e86badcca9a17ea9a01d09def3fe67d9a03d46`；index SHA256 `75f315765ee9d253e4b6a1cb70d8e05ae6f5087c66b37329dfa1bf2676cb8c58`。前文 A03 构建为历史轮次。

LAN fresh：wlan0 192.168.3.18/24，PID8456/8457 继续运行，页面与 `/api/state` 200，实际客户端 `/api/realtime` WS initial snapshot sequence369。一次手工探针误用 `/ws` 超时，核对当前客户端后正确端点通过，不是产品故障。既有 agent-only prepare-paused.py 准备 normal/paused约37秒/fresh target，无 Stop 调用。浏览器真实 A04 页确认只含上一首、继续播放、下一首；截图位于 ignored `.superpowers/sdd/2026-10-09-task-8-web-batch-plan/w4-a04-player.jpg`。

复验：W4-H01 三按钮布局与继续/暂停/切歌；H02/H03 未获明确通过的必要项继续待反馈。Implementation/automated/LAN READY，HUMAN PENDING，真实 MPD/NAS NOT RUN，PWA DEFERRED；W5 前置尚不满足。启动/停止沿用本记录上述命令和 PID，无 commit/push/PR。

## A04 后续手机反馈：首屏高度与操作跳变（待修复）

2026-10-10 用户报告浏览器工具栏占用后进度以下首屏不可见、所有按钮看似刷新整页，要求先分析。此次只调查，未更改产品代码/构建，仍 A04 / HUMAN PENDING；两项体验问题保持 OPEN，不关闭 W4。

辅助有效视口390×661测量：pageHeight1045，artwork top104/height343，identity top463/height86，metadata top602/height43，progress top661/bottom747，transport top763/bottom827，output top843/bottom955。固定宽度正方形封面 + 纵向堆叠/gap + padding 造成内容超过可见高度；100svh仅为外壳min-height，没有约束子内容预算。用户真实手机现象优先，此辅助尺寸不冒充设备实测。

一次真实产品 resume 点击配合现有 .venv 的只读 /api/state 采样：sequence434 actual_state=null/freshness=unknown/actual_freshness=unknown/bound=null/position=null/duration=null，约0.446秒后sequence435恢复playing/fresh/同一queue item/position62.43/duration300。随后实际页面 pause 点击也捕获实际歌曲未知/艺术家未知/源文件未知/进度未知/最后业务歌曲新增，下一观察恢复。根因：PlaybackService._save_confirmed_status→PlaybackObservations.changed 清观察；客户端收到HTTP ACK及WS失效后读真实snapshot；derivePlayerFacts非fresh绑定时song=null；ArtworkStage因此清资源，identity与时间重新展示；另ProgressControl和PlaybackControls同时插入pending段落。无页面导航/重载，AppShell和PlayerView无snapshot-key重建。真实MPD生产路径同样清观察，故不能承诺换真机自然解决；真实设备交接时长未测。

建议在同一W4修复：按浏览器可用高度制定封面/间距预算，让正常场景进度和transport首屏可见，长文本/字体放大仍可滚动；不固定整个页面18:9或依赖浏览器自动隐藏工具栏。保持canonical unknown/禁用控制，展示层为未改变identity的短暂交接保留明确标注“上次确认/同步中”的媒体展示并冻结进度，真实切歌/epoch/generation变化撤销旧展示；固定单一局部操作反馈区域，避免重复pending与布局跳动。必须以新的RED→GREEN/合同Gate和新手机轮次核验，尚未实施。临时viewport已reset；本地Mock恢复PAUSED约1:36，服务继续运行。首屏截图位于ignored w4-a04-short-viewport.jpg。


## W4-A05：首屏高度与操作交接修复（2026-10-10，Asia/Shanghai）

**当前交付：Implementation DONE / Automated Gate PASSED / Contract与Relationship REQUIRED且PASSED / LAN本机READY / HUMAN PENDING。** 两项 A04 手机反馈已有最小修复与本地证明，手机复验仍未执行；W4 未关闭，W5 前置不满足。真实 MPD/NAS/DAC **NOT RUN**，PWA **DEFERRED**。

### 原始反馈及本次范围

用户反馈原意与本次明确指示保留：

> 手机浏览器首屏过长。实际手机有系统状态栏、地址栏和底部浏览器工具栏，默认打开时“观察位置、时长”以下内容不可见，下滑自动隐藏工具栏后仍放不下。辅助测量约390×660内容区：页面总高1045px，封面高343px，进度从661px开始，播放按钮从763px开始。
>
> 操作后内容突兀清空与恢复。HTTP ACK及WS失效后读取unknown，再等待fresh样本；歌曲、封面、metadata、进度切为未知后恢复。ProgressControl与PlaybackControls重复插入pending，暂停也显示“正在提交进度”。不是网页重载，不通过mock、兼容分支、乐观store或猜造target绕过合同。

仅修改必要前端代码、行为测试与本记录；Stop 仍不显示/不调用，后端与既有动作层语义保留。使用现有dirty `feature/task-8-web-player` checkout；HEAD仍为 `adf4171`。既有大量未提交实现/文档保留，无reset/restore/clean/stash/commit/push/PR/merge，未进入W5/W6/Task9/PWA。

### 根因复现与修复边界

本次实际 browser 内容区355×600的 A04 fresh测量：页面1010、封面309、进度627、transport729–793，确认宽度限定正方形封面与纵向间距耗尽首屏预算。实际backend resume采样再次捕获 sequence472 unknown（actual/binding/position均null）→sequence474 fresh/playing，采样时间约0.046→0.166秒；完整采样 `w4-a05-reproduction.json`。核对当前 `_save_confirmed_status`→`PlaybackObservations.changed(status)` 与前端derive/Artwork的清资源路径，生产后端未修改。

- 布局：Artwork 根据实际可用 `dvh`（`svh` fallback）扣除文字/进度/控件及safe-area预算后缩小；缩紧必要间距。页面仍为自然文档流，长标题/字体放大/异常事实正常滚动；无整页18:9、全屏依赖、截断或触摸目标缩小。64px主按钮保留，其余按钮实测至少44px。
- 展示：新增本地 `playerPresentation`，只暴露song/title/duration/冻结位置，不暴露能力或target。仅当前本地意图触发的同业务occurrence/context/song、epoch/generation/library范围的无错误纯unknown交接可以保留“上次确认 · 同步中（实际状态未知）”媒体；进度明确标为“上次确认位置”。fresh回来重新使用当前观察；六秒仍未收敛撤销旧展示，重复unknown不续命。已经结束的旧操作不能为日后未知观察提供保留资格。
- 权威与撤销：canonical unknown/null即时保留，derivePlayerFacts、store、clock与后端未改；所有transport/seek能力始终读取当前权威事实，不能使用展示缓存发请求。新occurrence（含重复URI）、实际entry/token、epoch/generation、相关Library范围、业务歌曲/context改变、stale/drift/error、断线和失败均有撤销保护。时长未知仍禁seek，冻结值不是新样本，也不继续插值或使用seek预览值伪造确认。
- Artwork：交接不把同一song传成null，原请求/资源可保持；资源scope增加实际occurrence/token/entry，新身份迟到封面不可倒灌。原revision/generation/abort保护保留。
- 提示：ProgressControl移除重复pending；PlaybackControls保留单一、始终存在的局部live region，区分“提交播放操作”与“提交进度”，并明确unknown/typed error/已确认但未同步。读取失败且仍等seek观察同时表达两层事实，保留原合法断言；正常短交接不插入恢复按钮/错误选曲提示，异常时仍有恢复入口。

### RED→GREEN与自动证据

完整日志在 ignored `.superpowers/sdd/2026-10-09-task-8-web-batch-plan/w4-a05-*.log`；没有以日志/旧勾选替代当前命令。

| 证明 / fresh命令 | 实际结果 |
|---|---|
| controls `-t 'handoff\|persistent local'`：实际旧UI在unknown丢标题、缺稳定反馈区域 | **11行为RED** → 同文件GREEN；保留原7项controls断言 |
| old-confirmed-action不能为以后unknown保留媒体 | **1行为RED** → GREEN |
| Artwork handoff与六秒不续命：先修正新增测试的artwork DTO shape；该wire setup失败不当作行为RED。临时仅撤销本轮展示绑定/expiry逻辑的受控mutation（随后恢复本轮文件） | 封面消失与超时不撤销两项 **行为RED→GREEN**，不是覆盖历史未提交内容 |
| 直接受影响 controls+seek+facts | **49 passed** |
| 计划六文件 controls / seek / clock / facts / realtime / mutation | **80 passed**（21/6/7/22/15/9） |
| `npm --prefix web run test:invariants -- --run` | **122 passed** |
| `npm --prefix web run test -- --run` | **123 passed** |
| `npm --prefix web run typecheck` | **exit0**；首次发现新增测试nullable entry_id，按实际DTO修正测试赋值后重跑通过，无生产绕过 |
| `VITE_ACCEPTANCE_LABEL='W4-A05 · Mock 本地验收夹具 · 模拟计时，不代表真实 MPD/DAC' npm --prefix web run build` | **exit0**，实际preview读取本次dist |
| 当前P3四文件+计划幂等/mutation/snapshot/recovery/visibility/output/D6联合回归+实际DTO wire fixture，命令同本记录前述126项 | **本次重新运行126 passed**；既有Starlette/httpx deprecation warning1，环境/依赖未改 |

本次新增15项行为/invariant：unknown canonical与禁用控件/零额外请求、冻结标注展示与fresh恢复、occurrence/epoch/generation/song/context/library/stale/error/drift撤销、单一稳定operation region、未知结果不伪确认、六秒寿命不续命、旧操作不可复活展示、同曲Artwork一次读取及重复URI新实际身份迟到资源拒绝。已有seek/key/replay/pending/clock/后台/重连回归断言未削弱。并非每条新断言都独立进行了production RED；上表区分实际RED与补充回归。

Contract traceability：WEB-PLAYER-FACT/CONTROL/SEEK/PROGRESS→Architecture4.1/4.2/12、Playback7.1–7.4→实际decoder/store/actions/clock/presentation/Player/Artwork→上述80项联合回归与全Web invariants；后端PB-CONTROL-TARGET/PB-RESUME/PB-SEEK-TARGET/RT-CONTROL-TARGET→实际Service/API/observation/DTO→本次P3/DTO126。关系Gate REQUIRED且PASSED；无新合同、后端兼容路径或target副本。

依executing-plans的一次独立只读审查（gpt-6-astra）：**无Critical/Important/Minor发现**；审查同步watcher、local-action收敛/失败、identity与connection/revision撤销、Artwork代次、CSS自然滚动。审查不独立执行测试或认证产物，由本窗口fresh验证。Declined-to-judge裁定：手机触摸/后台/网络由用户认证；真实MPD/NAS禁止本轮接触且NOT RUN；历史dirty与未来Batch不扩展；不声明merge readiness或W4关闭。

### 本次构建、LAN与辅助预检

- 产品URL：[http://192.168.3.18:5173/](http://192.168.3.18:5173/)，页脚必须显示 **W4-A05**。wlan0实际 `192.168.3.18/24`；监听preview `0.0.0.0:5173` PID8457，backend `127.0.0.1:8000` PID8456，命令/进程/端口均重新核验，不凭原PID推定。
- 实际页面、`/api/health`、`/api/state`、当前JS/CSS均200；同源客户端实际WS **ws://192.168.3.18:5173/api/realtime** initial protocol1/snapshot sequence796，歌曲正常。preview进程实际 `API_PROXY_TARGET=http://127.0.0.1:8000`。证据 `w4-a05-lan.json`。
- JS `index-DtJc8QAq.js` SHA256 `e1135944cd9591c091be10255cb272bc2e607c83f4b2247955ebd70466e4abd4`；CSS `index-B6ovXoTS.css` SHA256 `147d6d35ad23c094272ff4db25c9ce86d4798d0ea882a3ee0c036bd70aaca651`；index SHA256 `c11b5558e412f9438ae5ef7335e29f455368f11e3c24097373d8c90c8a34010f`，served hash与磁盘一致。
- 正常场景实际CSS内容区：355×600 transport bottom562；390×660约621（最终截图390×661约623）；320×560约522；390×520约482；411×700约662。各自歌曲身份/进度/三按钮首屏可用，无横向溢出；页面输出/夹具说明仍可向下滚动，不要求全部事实挤入一屏。
- long标题320×560：title156px、transport约670、自然页面894px，无截断/横向溢出。字体放大采用**同一构建JS/CSS、同源真实API**的临时index适配（root24px/150%、title36px），long title234px、页面1217px，允许正常滚动，按钮≥64px；临时HTML仅本次辅助检查，已从dist移走至ignored证据，不新增产品页面/控制台。IAB快捷键放大未改变测量，不当作字体放大证明。
- unknown场景实际API duration=null；产品页“观察位置0:01/时长未知”、seek disabled；stale场景actual stale/PLAYER_UNAVAILABLE，显示过期/实际未绑定与分层最后业务歌曲、位置/时长未知、三按钮禁写且自然滚动。未冒充手机断网/锁屏证明。
- 本地证据截图：`w4-a05-short-viewport.jpg`、`w4-a05-font-long.jpg`，均在上述ignored目录。所有辅助viewport已reset。

当前交付恢复 normal：`夜航 · 本地验收曲`、**PAUSED约0:37 / duration5:00 / fresh target**，有可用切歌候选；准备走既有product API，无Stop请求，无终端/数据库步骤交给用户。场景文件normal保留；unknown已由AI本次实际准备与预检，待手机normal反馈后AI再切换并核验，不能标为手机通过。

启动/停止继续使用本文“产品页与当前最小场景”中的既有命令：根目录 `.venv/bin/python -m server.tools.web_acceptance --runtime-dir .superpowers/sdd/2026-10-09-task-8-web-batch-plan/w4-runtime --port 8000 --advance-clock`；web目录 `API_PROXY_TARGET=http://127.0.0.1:8000 node node_modules/vite/bin/vite.js preview --host 0.0.0.0 --port 5173 --strictPort`；agent准备 `.venv/bin/python .../w4-runtime/prepare-paused.py`。只在重新核验PID与命令后 `kill 8456 8457`停止本轮所属服务；本次两进程继续运行，原DB保留，重启会使用新的独立owned DB。

### 手机复验与剩余blocker

| 编号 | A05需复验范围 | 当前真人状态 |
|---|---|---|
| **W4-H01** | 浏览器默认工具栏显示时首屏能读歌曲身份、位置/时长，并点上一首/继续或暂停/下一首；同曲操作期间媒体不清空闪回，同步标注清楚；触摸目标保持。Stop仍N/A | A04首屏/跳变FAILED；**A05 HUMAN PENDING** |
| **W4-H02 normal** | 拖动释放单次、同步等待进度冻结且标注清楚、仅一处正确pending；不回跳猜造目标，取消/快速操作仍受锁 | A04跳变FAILED；**A05 HUMAN PENDING** |
| **W4-H02 unknown** | AI切换并核验后，未知时长/元数据真实表达、进度禁拖且可用elapsed只读 | 辅助预检通过，**手机场景待再交付 / HUMAN PENDING** |
| **W4-H03** | 临时断网与恢复、后台/锁屏返回：清楚只读/过期、禁写，新snapshot后恢复；无后台累加、串曲或重复请求。展示层与资源scope涉及这条路径，必须复验 | **HUMAN PENDING** |

唯一剩余验收blocker：上述必要手机反馈，包含AI再次准备的unknown子场景。A05自动Gate与辅助浏览器不是用户确认；只有用户明确确认必要项通过才能HUMAN PASSED/关闭W4。**W5前置当前不满足，不自动推进；不宣称Task8整体完成。**

A05交付前最终检查：`git diff --check`、实际stat/status及43个untracked文件的whitespace检查均通过；tracked diff与本窗口开始时逐字节相同（7 files / 79 insertions / 170 deletions为此前窗口改动）。本次实际范围为6个前端文件、2个测试文件与本文共9个文件；独立审查已读取实际untracked实现。无DB/缓存/环境/依赖变更，原进程8456/8457继续运行。首次no-index审计脚本误把新增文件正常exit1当失败，空诊断后修正判断并重跑通过，未为通过审计修改历史文件。


## W4-A06→A07：状态行与同步视觉稳定性反馈（2026-10-10，Asia/Shanghai）

用户原始补充：“‘已暂停’‘正在播放’这个位置的信息不需要，可以完全摒弃”；“在按下交互按钮进行快照同步的时候不要改变那么多元素，控件灰掉就已经足够明显了，不要看起来到处都在跳变”；“后期底下的tab（列表，库，设置等）准备放在哪里合适？直接叠加吗？你要考虑到底下tab栏的位置。”

本次作为既有W4手机反馈继续修正，采用executing-plans；brainstorming只用于收敛已明确的局部呈现与未来底栏位置，用户直接指示覆盖旧UI选择，不重复要求设计批准。未扩展产品功能，未实现tab/Task9、W5/W6或PWA。仅5个前端文件、2个现有测试文件及本文；actions/store/clock/backend、依赖与历史dirty保留。

修复：

- 移除歌曲标题上方整个独立状态行，不再显示普通“已暂停/正在播放”，正常“已确认”诊断行也不再单独占位。
- 同曲pure-unknown交接保持identity、metadata、进度标签与读数、主按钮图标稳定；media仅新增展示图标选择，不提供能力或target，disabled与实际dispatch仍严格由当前canonical facts/动作层决定。
- 普通pending不插入可见文字，控件禁用并有`aria-busy`；同身份unknown展示仍需诚实说明历史数据，只在控件下方固定局部区域标注“正在同步 · 展示上次确认数据”。HTTP确认、seek等待、typed error、unknown结果、stale/断线仍在同一区域明确表达；预留两行供正常同步文字，不推动其它内容。真正异常的长反馈允许正常滚动。
- 移除其他同步标签/诊断替换，历史标记从identity/进度迁到上述单一区域；A05 canonical unknown/六秒寿命/身份撤销/迟到资源/失败不伪确认合同不变。

底部tab的布局考虑：未来由**AppShell拥有视口底部的独立一行**（约56–64px按钮行 + bottom safe-area），Player在它上方滚动；底栏不能直接盖住Player，也不应接在Output之后随长页面被推走。当前Artwork预算已加入 `--app-bottom-bar-height`（默认0），后续shell提供底栏实际高度时再扣除，safe-area另计；本轮不创建底栏组件、路由或导航入口。后续Task9仍须在其Batch按实际footer高度验证，当前不是Task9实现/验收。

RED→GREEN与审查：

- 3条实际行为RED：旧pending仍插文案；标题上方旧状态行仍存在；同曲交接identity HTML改变。修复后GREEN。两条新测试与更新后的pending测试保护稳定DOM/图标/标签、唯一局部状态、canonical null、禁写及accessible busy。
- 因用户明确移除状态文字/迁移历史标注位置，仅更新对应旧UI文字/位置断言；原domain state/freshness/停止语义用真实deriveFacts断言保留，其余identity/binding/seek/key/clock断言不弱化。
- 一次独立只读review（gpt-6-astra）发现Important：合并状态区后stopped分支可能把真实`UNCONFIRMED_STOP`误只显示“已停止”，丢失异常诊断。核对当前backend D6 unknown-stop证明后，新增UNCONFIRMED_STOP/SYNC_FAILED/EXTERNAL_DRIFT/UNBOUND四种stopped组合，**4 RED→GREEN**；仅CONFIRMED stopped显示状态，其他异常保留原诊断。无Critical/Minor；同一个fix pass修复，无第二次review。
- A06为首个预检构建；review修复后重建并递增为**A07最终交付**。不拿A06中间构建冒充修复后的版本。

fresh自动Gate（日志 `w4-a06-*.log` 与 `w4-a07-build.log`，位于同一ignored workspace）：

| Gate | 最终结果 |
|---|---|
| 最小stopped诊断回归 | 4 passed |
| controls+seek+facts直接受影响文件 | **55 passed** |
| W4指定六文件 | **86 passed**（controls27/seek6/clock7/facts22/realtime15/mutation9） |
| 全Web invariants | **128 passed** |
| 全Web | **129 passed** |
| typecheck / A07 build | **exit0 / exit0** |
| Contract/Relationship | **REQUIRED / PASSED**：真实decoder/store/Player presentation/capability/actions/Artwork联合；旧seek/key/pending/clock/reconnect断言保留 |
| 后端P3/DTO | 本Batch A05 fresh **126 passed**适用；本轮核对`git diff HEAD -- server/app`为空、backend路径/前置测试与进程未改变，无证据缺口需重复执行；Python依赖未动 |

A07实际页面与辅助证据：

- 正常实际有效内容区390×661：封面约213px、transport bottom约575px、固定反馈区bottom约625px；320×560 transport约474/反馈525；390×520 transport约434/反馈485；均无横向溢出，正常歌曲/位置/三按钮首屏可用，状态行不再出现。
- 使用**相同构建资源与真实同源API**的临时HTML预算适配，注入64px底栏预算：390×661封面149、transport513、feedback563，均在扣除后的597px可用高度内；实际无nav。该适配仅用于辅助测量，已从dist移走至ignored `w4-a07-bottom-budget.html`，无产品页面/控制台交付。
- 实际long标题390×520自然页面796px；同构建root24px/150%字体+64px预算时自然页面1222px，完整标题仍可读、正常滚动、无横向溢出。unknown duration=null时进度禁拖但显示真实可用elapsed；stale PLAYER_UNAVAILABLE时同一局部区“实际播放未绑定 · 观察已过期”、三按钮禁写、业务歌曲分层仍正确。不能用此替代手机断线/锁屏/触摸验收。
- 最终normal恢复 **PAUSED约0:37 / fresh target / duration300秒 / 有切歌候选**，服务继续运行。viewport override已reset；截图 `w4-a07-normal.jpg`、`w4-a07-font-budget.jpg`保留ignored。
- 实际URL仍为 [http://192.168.3.18:5173/](http://192.168.3.18:5173/)，页脚必须是 **W4-A07**；wlan0仍192.168.3.18/24。PID8456 backend127.0.0.1:8000、PID8457 preview0.0.0.0:5173已核对实际命令/端口；页面/health/state/JS/CSS200，同源实际WS `ws://192.168.3.18:5173/api/realtime` initial protocol1/snapshot sequence922。启动/停止与agent场景准备仍使用本文既有方法；停止前再次核验PID归属，当前不停止。
- index SHA256 `dc03f5cd955e0c8ff2e5f133c5dba25cce9a3b9c837719085b37b2e096c98fd9`；JS `index-CTU-QRTk.js` SHA256 `043edeaef583b3bbae62d32d4392cc8dac679d509439f379920098c68f4ac747`；CSS `index-BAcWdVuf.css` SHA256 `8ef6ac49cf86c5ae0880a390301062b9123acfc1268c8eea4234155d8a4d1184`。实际served hashes一致，LAN证据 `w4-a07-lan.json`。

**最终状态：Implementation DONE，Automated/Contract/Relationship PASSED，LAN本机READY；HUMAN PENDING。** H01复验精简首屏/三按钮/同曲视觉稳定，H02复验seek与单一区域说明（unknown子场景由AI再准备供手机），H03复验断线/后台恢复。用户本条为修改反馈，不作为必要项通过确认；手机未认证仍是剩余blocker，**W5前置不满足**。真实MPD/NAS **NOT RUN**，PWA **DEFERRED**，不称Task8整体完成。独立review未判断手机/屏幕阅读器、LAN产物、真实设备或其它dirty/future工作：分别由人类Gate、本窗口fresh证据与既定范围裁定保留。

A07最终diff/check/stat/status及43个actual untracked文件whitespace检查通过，tracked diff与本轮开始时逐字节一致；本轮template/presentation实际增量diff保留ignored w4-a07-scoped.diff。原数据、依赖、进程与无关修改保留，无commit/remote操作。

### A07页面恢复（2026-10-10）

用户反馈“看不到页面，你重新打开一下”。fresh检查原backend/preview已不在运行，8000/5173无监听，浏览器ERR_CONNECTION_REFUSED；按本文原命令恢复，无代码/构建变更，仍为W4-A07。新backend PID22562（session90369）、preview PID22563（session66779）；实际监听127.0.0.1:8000与0.0.0.0:5173，wlan0仍192.168.3.18。保留原数据库，新启动使用夹具自动新建owned DB。既有prepare-paused.py恢复normal/paused约37秒/fresh target/已知300秒时长及切歌候选。LAN health200；实际浏览器页面实时连接、正常歌曲/三按钮/0:37与5:00及W4-A07页脚已确认，已重新显示并保留标签页。停止前重新核验上述PID归属，使用本文原启动命令；HUMAN PENDING保持不变。

### A07接续核验（2026-10-10，Asia/Shanghai）

接续窗口已读取本地指令、Web Batch Plan、手机验收方法、本文与所引用的共同 authority/mutation/current-target/recovery 及 W4 control/seek/clock 合同。fresh核验 PID22562/22563 的实际命令与监听，wlan0仍为192.168.3.18；LAN页面、health、state成功，实际served JS/CSS与A07磁盘构建逐字节相同，JS包含W4-A07标识。同源 `ws://192.168.3.18:5173/api/realtime` 返回protocol1完整initial snapshot（epoch `6fc6835b-c255-40ac-be20-591d5a5d0390`、sequence25）。当前正常曲暂停约38.9秒/300秒，observation fresh、target非空且有切歌候选；保留当前场景与进程，无重置或构建变更。

本窗口只核验交付环境，未重跑自动Gate，不将历史测试数字冒充本窗口fresh结果。先交付W4-H01默认浏览器工具栏下首屏、三按钮及同曲操作稳定性复验；H02 normal/unknown与H03仍待手机确认。HUMAN PENDING，W4未关闭，W5前置不满足；真实MPD/NAS NOT RUN、PWA DEFERRED保持。


## W4-A08：页面长度与单行DAC摘要反馈（2026-10-10，Asia/Shanghai）

用户要求：播放控件及以上区域不大幅移动；移除“播放器”，MPD SERVER与连接状态横向对齐，利用释放空间稍放大封面；底部NAS DAC三行合并为单行并放到源文件格式右侧；移除多余空页，保留导航栏预留空间。

本次仅修改PlayerView.vue、app.css、player-facts.test.ts与本记录；executing-plans继续，brainstorming用于收敛用户已经明确的局部设计，不重复索要实施许可。无W5/Task9控制/导航实现。源文件格式允许窄屏自然换行，DAC摘要保持单行；删除独立output-summary。正常pending/历史交接、唯一反馈区及冻结进度机制保留。页脚验收说明收紧间距；底部只增加64px未来导航预算与8px/safe-area边距，后续真实导航由AppShell占独立一行，不可重复叠加此空白。封面预算从28rem调整到22rem并扣除64px底栏。

Ruling：正常输出使用“DAC已启用”，未启用/不可用/尚未确认/已过期分别显示，不能将ACTIVE改写为物理“DAC已连接”——Output Spec §6.1明确ACTIVE只证明MPD回读启用；成本：当前端口没有物理设备连接证明。输出参数与错误保留在title辅助说明中，手机验收不要求访问tooltip；可见摘要本身承担当前确认/异常状态表达，不用源文件参数补输出值。

RED→GREEN：五种Output status/freshness与断线降级，加单品牌/摘要位置共6条行为RED，修复后GREEN。原source-vs-output断言改为可见“DAC已启用”及独立output title中的96kHz，44.1kHz源文件仍不得串入output。一次测试误假定默认fixture codec=FLAC，实际为null；只在该测试显式准备FLAC后重跑单例通过，不改production适配错误假设。

fresh Gate：facts28；W4指定六文件92；Web invariants134；全Web135；typecheck与W4-A08 build exit0。Contract/Relationship REQUIRED/PASSED：真实decoder/realtime/store/Player Output freshness摘要及源文件分离；既有actions/key/seek/clock/身份/迟到资源回归全部保留。后端生产git diff HEAD -- server/app为空，未重跑P3，不冒称本窗口fresh126。

单次独立只读review（gpt-6-astra）：无Critical/Important/确认的Minor，独立facts28通过；未进行二次review。Ruling：审查未判断的精确布局由本窗口实际构建预检及用户手机确认承担；手机触摸/断网/后台仍HUMAN PENDING，真实MPD/NAS仍NOT RUN，历史dirty与整个branch merge readiness不属本次范围。成本：辅助浏览器无法认证手机行为。未因review范围扩大实现。

实际LAN：PID22562 backend127.0.0.1:8000与PID22563 preview0.0.0.0:5173命令/监听fresh核验，URL仍http://192.168.3.18:5173/。页面/health成功；同源WS protocol1完整initial epoch6fc6835b-c255-40ac-be20-591d5a5d0390/sequence25；served index/JS/CSS与dist逐字节相同。JS index-BybLsZF7.js SHA256 10205d6e3d562f8b4c96a542c46ffd07a8abbd96e2c6a47a1b372c5ef8f82820；CSS index-DpktyFlb.css SHA256 dccbb9ba6fa2d577844d6f36f72bb6f30c89c1d85d5577d07697052a6cb07ca4。页脚W4-A08。

辅助浏览器请求390×661被IAB实际限制为355×601，记录实际值，不当作390×661精确证明：A07封面153px/transport bottom515/page759；A08封面185px/transport508/page673，封面增32px，按钮约上移8px；版本说明bottom600后仅72px导航预留/底部边距。其它实际有效视口291×509、355×473、373×637正常三按钮可达，DAC均单行；狭窄源格式可换行，无横向溢出。长标题291×509自然页750，标题完整；同构建/真实API临时index root24px（150%）页1370、标题421px、DAC一行且无横向溢出；临时HTML已从dist移动到ignored证据，无产品页面新增。unknown实际duration=null/seek禁用，观察位置真实可读。之后恢复normal并用既有prepare-paused.py确认约37秒/fresh target/300秒；viewport reset，页面保留。截图w4-a08-normal.jpg与日志在本计划ignored workspace。

Implementation DONE；Automated/Contract/Relationship PASSED；LAN本机READY；A08 H01精简布局/三按钮/同曲稳定待手机复验，H02普通seek及AI再交付unknown、H03断线/后台仍HUMAN PENDING。本轮修改反馈不能当通过确认；W4未关闭，W5前置不满足，真实MPD/NAS NOT RUN，PWA DEFERRED。无依赖/DB删除/commit/push/PR/merge。


## W4-A09：服务恢复与两行文字上限（2026-10-10，Asia/Shanghai）

用户反馈页面无法打开，并明确要求长标题、艺术家、专辑名至多两行。本次fresh发现preview PID22563已退出、5173无监听，backend PID22562仍正常、wlan0仍192.168.3.18；退出的具体原因无证据，不能归因于代码。首次nohup后台启动未存活/日志为空，未将其宣称成功；改用持续exec session81446启动原preview命令，实际新PID30189、0.0.0.0:5173，代理仍127.0.0.1:8000。最终页面/health/state/静态资源与同源WS均成功，进程命令/监听重新核验。backend未重启、未删除DB、不更改防火墙。

本次产品修改仅app.css：当前歌曲标题、艺术家、专辑名及异常分层最后业务歌曲的身份文字使用两行line-clamp与对应line-height的max-height fallback；其余错误/反馈不截断。原文本留在DOM/accessibility，浏览器呈现省略，不修改Song/权威/动作/时钟。用户明确局部设计继续既有W4反馈闭环，纯低影响CSS用实际浏览器前后测量验证，不新增镜像CSS测试或重复设计审批。

修改前长标题实际156px/31.2px（约5行）；修改后在实际291×509窄视口：标题62.4px/31.2、艺术家48px/24、专辑44.8px/22.4，均两行，computed -webkit-line-clamp=2，截图可见省略号，无横向溢出。为覆盖三种长字段，仅通过现有LibraryRepository在确认playback_context匹配的owned DB phone-3759482734e945c7818fa7bd36da554a.db扩充acceptance-long艺术家/专辑名；原Song JSON保留ignored w4-a09-long-original.json。不是产品新接口或真实媒体。当前交付保留**长标题/长艺术家/长专辑名，PAUSED约1:56/5:00、fresh target、有切歌候选**，便于用户直接验两行。normal歌曲及旧DB保留，后续AI可按既有prepare-paused.py恢复普通场景。

fresh直接facts+controls55、W4指定六文件92、typecheck/build通过；本轮未跑全Web/P3，A08全Web135/invariants134与本Batch既有P3证明不冒称本窗口fresh。纯CSS不改变Contract/Relationship行为，六文件回归required/passed。A09 JS index-D6bPvy-t.js SHA256 5394f43910677f28778942c07c3a04f6b6dcf5421f8afb492d79b7a56ad1a1a4；CSS index-yfDQWKOM.css SHA256 27261fd7db5f4dca4335ac6c7df91cc1b7b1657b5afa9f12bbb1b67bf51400cd；served index/JS/CSS与dist逐字节相同，JS含W4-A09。同源WS protocol1 initial sequence204，长文本暂停事实匹配。截图w4-a09-long.jpg在ignored workspace。最终viewport reset、页面保留。

W4仍HUMAN PENDING；需用户重新确认手机可达、H01页面比例/两行与三按钮/同曲稳定；H02/H03未跳过，W5前置不满足。真实MPD/NAS NOT RUN，PWA DEFERRED，无依赖/commit/remote操作。


### A09最终服务生命周期修正

本轮最后检查时session81446 preview返回exit143/SIGTERM，backend22562也退出；未将此前成功探测当作仍在服务的证据。没有观察到终止源，不虚构原因。随后用现有.venv Python subprocess.Popen(start_new_session=True)独立启动相同backend/preview命令，日志重定向到ignored w4-a09-{backend,preview}-detached.log，PID文件也在同一workspace。最终backend **31596**（127.0.0.1:8000）、preview **31597**（0.0.0.0:5173）实际命令/监听/API再次核验，页面重新打开为W4-A09并保留。启动短暂500发生于preview先于backend就绪，之后health200。

新backend按原夹具行为新建owned DB **phone-c017145ca7cb4e7ca172c33e237e98c7.db**，旧DB全部保留；再次核对context归属后仅扩充本DB long歌曲艺术家/专辑以供三字段验收（原Song备份w4-a09-detached-long-original.json）。最终当前长文本暂停约 **0:15/5:00**、fresh target；因新夹具暂无Played候选，上一首禁用符合合同，下一首/继续可用。此前1:56场景是重启前证据，不能当当前状态。后续普通三按钮验收由AI恢复normal准备脚本。停止前必须重新核验31596/31597归属，不能凭PID文件停止不相关进程。


### A09 H01真人确认与H02交付（2026-10-10，Asia/Shanghai）

用户原话：“这个‘观察位置’和‘时长’以后实机是会省略的对吧？H01通过”。按明确结论记录 **W4-H01 HUMAN PASSED**，含当前页面比例/两行呈现与H01操作验收；不将其扩大到未确认的H02/H03。已说明两标签为当前固定产品文案，接入真实MPD不会自动省略；本条疑问不作为已经移除标签的实施/验收证据，本轮无产品代码或构建变更，仍A09。

fresh PID31596/31597命令及LAN health200核验。为H02 normal已由AI通过原scene watcher恢复normal、运行既有prepare-paused.py，API确认暂停约37秒/300秒/fresh target及候选。用户继续同URL拖动至约1:30释放，检查同步等待冻结/反馈与稳定性、快速重复操作受锁。取消/复杂key时序由既有自动Gate覆盖；unknown子场景在normal反馈后由AI准备，手机不操作终端/数据库。

H01 PASSED；H02 normal/unknown与H03 PENDING；W4未关闭，W5前置仍不满足。真实MPD/NAS NOT RUN，PWA DEFERRED，无重新测试/修改依赖/commit/remote。


## W4-A10：seek松手后同步回跳（2026-10-10，Asia/Shanghai）

用户原话：“拖动本身没有问题。但是拖动以后同步过程中，进度条会跳回原来的位置，同步后跳到正确位置，应该要调整一下，同步过程中也应该跟着我的手指。”H02 normal拖动本身确认可用，同步呈现FAILED，不能标整项通过。H01既有手机通过保留；本次seek变化需复验H02，与暂停/继续锁及单一区域反馈一并检查。

根因：releaseSeek立即cancelDraft；ProgressControl随即回到旧canonical/display clock位置，HTTP成功后还要等待receipt.updated_at之后的匹配observation。本次只修改playerActions.ts、ProgressControl.vue、player-seek.test.ts及本文：新增独立UI seekPreview {seconds,duration}，提交中与确认后同步期间保留松手位置/已知duration的disabled范围几何，标注“待确认位置”。drag仍为预览；timestamp/identity匹配的新观察后撤销proposal并用真实位置（自动测试80目标→82真实样本，不强制假装80）。不写canonical、不外推proposal、不推导target/capability、不重复提交。失败/unknown结果清proposal，显式同key重试只在当前seek能力有效时恢复proposal；切歌/occurrence/epoch/连接scope、断线、stale、异常unknown、Stop撤销，不让迟到receipt复活。HTTP已确认但读失败保留明确待确认和失败反馈，不要求新mutation。

RED→GREEN：首轮3条行为RED复现37代替80（pending/断线前proposal/read失败）；新增stale守卫再1RED→GREEN。原取消、409回到实际事实、keyboard单次、Stop、重复URI、unknown duration断言均保留。单次独立review（gpt-6-astra）发现3 Important：null control identity下业务scope变化未撤销旧proposal；stale重试复活saved proposal；异常unknown沿用quiet宽判定。三条精确行为RED→GREEN同一个fix pass完成：watch独立观察business scope、retry按当前能力恢复、unknown仅允许state/current/binding/target为空且UNBOUND/无reconciliation/错误。无Critical/Minor，无二次review。

Ruling：本地submitted proposal可以在同步中保持拖到的位置与捕获的范围，但只能叫“待确认位置”，不叫服务端已确认进度——用户明确需求与Architecture UI draft/authority分层——成本：等待较久时仍需用户理解待确认标记。过去媒体6秒历史保留上限不改变，proposal不是新clock样本。Ruling：review未判断手机/真实MPD/历史dirty与merge readiness；仅本轮关系/实际LAN构建预检由AI证明，手机H02/H03仍须人类，真实MPD/NAS NOT RUN，whole branch不宣称ready；成本：没有设备或整体Task8认证。

fresh最终Gate：seek13、W4六文件99、invariants141、全Web142、typecheck/build exit0；Contract/Relationship REQUIRED/PASSED（真实client→store→actions→ProgressControl，pending/ACK/unknown/receipt time/newsample/failedretry/late receipt/scope撤销，canonical旧值与null断言）。后端生产diff HEAD -- server/app为空，未重新运行P3，不冒称fresh126。未改依赖/其他业务owner。

实际产品仍http://192.168.3.18:5173/；backend31596与preview31597命令/监听fresh核验、独立session服务继续；最终servedindex/JS/CSS与磁盘一致，JS index-jyF6zP_D.js SHA256 238d750df2c09a1f7fcb9363815a75fa2b042d808c86f03c3d4bb395523f3040（先前index-6y7008rW是review前中间构建，不能代表最终）/CSS index-D7wvlGnh.css SHA256 2fd803c57e7731413813d9cb6c070b32c5e9e5099c3b6f3fbce957ad05e625b9，页脚W4-A10。真实浏览器键盘seek177→176同步中slider disabled/value176、“待确认位置2:56”与唯一“操作已确认·正在同步进度”区域同时显示，随后由匹配actual观察176接管。本机证据w4-a10-pending-final.jpg和各w4-a10日志/最终scoped diff在ignored workspace；不当作手机触摸验收。保留用户当前normal paused位置约2:56/5:00，未重置至37。

Implementation DONE；Automated/Contract/Relationship PASSED；LAN READY；H01 PASSED、H02 normal修复HUMAN PENDING（unknown须再交付）、H03 PENDING，W4未关闭/W5前置未满足。真实MPD/NAS NOT RUN、PWA DEFERRED；无commit/push/PR/merge、无DB/依赖/旧文件删除。


### A10 H02 normal真人通过与unknown交付（2026-10-10，Asia/Shanghai）

用户对A10回跳复验明确回复“可以了，没有问题”。记录 **H02 normal HUMAN PASSED**：拖动与松手后待确认位置/同步呈现修复通过。H01已通过保留；不扩大为尚未执行的unknown或H03通过。

fresh核验独立服务31596/31597命令、8000/5173监听、LAN health200；通过原scene.txt watcher切unknown。LAN REST与同源WS完整initial确认acceptance-unknown、observed duration=null、codec/bit_depth/sample_rate_hz为空。仍W4-A10，无代码/构建/依赖修改、无重跑测试。手机交付：同页显示未知时长/源字段真实未知，进度不可拖动；elapsed如有样本可只读显示，不将未知时长冒充0:00。待用户确认后由AI恢复normal供H03。

H01 PASSED；H02 normal PASSED、unknown PENDING；H03 PENDING。W4未关闭/W5前置不满足，真实MPD/NAS NOT RUN、PWA DEFERRED。


### A10 H02全部通过与H03交付（2026-10-10，Asia/Shanghai）

用户对已交付unknown子场景明确回复“通过”。**H02 unknown HUMAN PASSED，H02全部HUMAN PASSED**；H01既有通过保留，不能将本条扩大为H03通过。

fresh核验31596/31597实际命令、LAN health200；AI用既有scene watcher恢复normal并运行prepare-paused.py，REST确认PAUSED约37秒/300秒/fresh target，同源WS完整initial确认normal。仍W4-A10，无产品代码/构建/依赖变更、无重跑测试。

H03手机验收卡：已加载页面先临时断开Wi-Fi和移动数据，确认连接中断/只读、控件禁用、进度不继续伪造推进；恢复同一Wi-Fi，等待实时连接和控件按新事实恢复，不补发断线操作。随后点击继续，切后台或锁屏约10秒，返回确认页面恢复且按新服务端观察校准，无长期卡住/串曲/重复跳变。夹具backend在playing时实际推进，因此锁屏返回进度可按新样本前进，不能误要求停在离开前位置。无需终端/开发工具，用户分别报告断线恢复与后台锁屏结果。

H01/H02 PASSED；H03 PENDING为当前唯一手机Gate。W4未关闭/W5前置不满足，真实MPD/NAS NOT RUN、PWA DEFERRED。服务继续运行，无commit/remote。


## W4最终关闭（2026-10-10，Asia/Shanghai；W4-A10）

用户对已明确交付的H03断线恢复、后台/锁屏恢复卡回复“通过”。据此 **W4-H03 HUMAN PASSED**；H01已有明确“H01通过”，H02 normal修复后“可以了，没有问题”、unknown“通过”，全部必要手机项已具用户确认。无尚未关闭的W4验收blocker，**W4当前范围通过/关闭**，W5前置满足，但本轮不自动实施W5/W6/Task9。

| 最终层次 | 结论 |
|---|---|
| Implementation | DONE：W4范围，不包含W5/W6/Task9 |
| Automated / Contract / Relationship | PASSED：最终A10 seek13/指定六文件99/invariants141/fullWeb142/typecheck/build；本Batch P3+wire126适用，后端生产未变。最终日志与实际源码核对，无产品修改后失效；本次仅状态记录，不为关闭重复跑相同测试 |
| Native/LAN/mobile | READY/PASSED：31596/31597实际命令仍符合；LAN最终A10页面/静态资源与dist逐字节相同、health成功、同源WS protocol1 initial epoch13aade50-0cf5-4790-af24-c94538c5fd4b sequence640。手机可达与H03恢复由用户通过确认 |
| H01 / H02 normal / H02 unknown / H03 | 全部HUMAN PASSED |
| Batch conclusion | W4 CLOSED；W5 NOT STARTED；Task8整体未完成 |
| 真实MPD/NAS/DAC | NOT RUN：Mock通过不证明声音/物理连接/真实计时精度 |
| PWA | DEFERRED：安装/SW/冷离线壳不计入本轮 |

当前URL http://192.168.3.18:5173/，构建W4-A10；backend31596/preview31597保持独立进程运行，停止前核验命令/监听归属。保留本计划ignored日志/截图/owned DB/原DB与历史dirty，不按通用finish流程删除未提交验收证据。Git仍feature/task-8-web-player/HEAD adf4171；无commit/push/PR/merge，本次仅更新同份acceptance与active plan的W4状态及执行ledger。
