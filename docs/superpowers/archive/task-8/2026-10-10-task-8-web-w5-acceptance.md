# Task 8 / Web Batch W5 acceptance

日期：2026-10-10（Asia/Shanghai）。当前轮次：**W5-A06**。仅 W5；**HUMAN PASSED，Batch 已关闭；W6 NOT STARTED**。

| Gate | 当前结果 |
|---|---|
| implementation | DONE：同步歌词、同一媒体区切换、Output 请求及确认事实分离 |
| automated / Contract Matrix / Relationship | REQUIRED / PASSED，证据如下 |
| LAN environment | READY：A06实际构建、页面、API、同源 WS 已核对；用户已确认手机三项通过 |
| 当前真人 Gate | A04 歌词 HUMAN PASSED/FROZEN；A06 页面比例、顶部同步反馈/稳定布局、Output卡片移除及DAC摘要 HUMAN PASSED；原 H02 Output 启停入口 N/A |
| 真实 MPD / NAS / DAC | NOT RUN；明确注入 MockMPD，自建静音资源、独立 SQLite；不证明声音、设备连接或精度 |
| PWA | DEFERRED，不计入 W5 手机 Web Gate |
| W6 前置 | W5 真人前置已满足；按用户要求 W6 NOT STARTED，不自动推进 |

## 版本、前置和范围

分支 `feature/task-8-web-player`，HEAD `adf4171`。未提交修改以轮次和实际资源标识区分。A02 构建时间 **11:21:28 +08:00**；Vite 7.3.7，57 modules。实际 LAN 返回的两个资源与本次 dist 逐字节相同：

- `index-CFdmmbrh.js`，126455 bytes，SHA256 `912b1186ace69885a6d1f389b749ec79a4c0fabd0cf9cafc99cc50174a339d38`。
- `index-C0Fm-8Gd.css`，7890 bytes，SHA256 `d0528e0063ad44d6bdcdd99680077432dcb66031a05e1fe880bd9ec9b5246c87`。

开始前读取 AGENTS.override、README、Web Batch Plan、手机方法及其指向的实际 Spec/合同/前置计划。W4 单份记录已包含用户 H01/H02/H03 HUMAN PASSED；实际 store/clock/runtime/Output alias decoder 接口已检查。fresh W4 六文件 Gate 99 passed；fresh 后端 P3 四文件、计划指定回归和真实 wire fixture 合计 126 passed，不能仅由计划勾选或历史结论推定。

本轮新增 `lyrics.ts`、`LyricsStage.vue`、`OutputPanel.vue` 及三个计划测试；修改 `PlayerView.vue` 必要接线、现有本机 `web_acceptance.py` 的可选 `--w5` 场景及其 API 集成测试、当前计划状态。没有修改后端业务 owner、Python/Node 依赖或 lockfile。既有其他窗口的 Compose、Web 基础接线、文档、后端测试和未提交文件全部保留；未执行 reset/restore/clean/stash、commit 或远端操作。

## RED→GREEN 与自动证据

真实 store + display clock + LyricsStage 的高亮断言先 RED，再 GREEN；parser 三个语义失败、read_error/plain/手动跟随/产品切换、Output 五个空实现失败和产品接线失败均有 RED→GREEN。相同时间 cue、offset 及旧连接资源已有 guard 下直接 GREEN 的新增场景仅算回归，不伪称 RED。Output watcher 最初因返回新数组而在每个 snapshot 上清除反馈，精确 timeout/failure 用例复现后改为稳定 epoch/generation 标识。fixture 测试先揭示歌词不足、真实 Song format 是 `text`、URI 唯一性以及未采样 Output，按实际模型和 Services 最小修正。

一次独立只读 reviewer 发现 Important：本地终态请求反馈遮住后续 canonical PREPARING/SWITCH_FAILED。两项精确 RED→GREEN 后分别展示本地回执和服务端最近请求；未把 HTTP receipt 写入 canonical。只有一轮最终修复，无第二次 review，无未处理 Minor。

以下为最终产品修改后的 fresh 结果；最后新增产品 clock 关系测试没有再修改产品或构建：

```bash
npm --prefix web run test -- --run tests/invariants/player-lyrics.test.ts tests/invariants/player-output.test.ts tests/unit/lyrics.test.ts tests/invariants/player-clock.test.ts tests/invariants/wire.test.ts
# 49 passed：7 + 9 + 3 + 7 + 23
npm --prefix web run test:invariants -- --run
# 157 passed
npm --prefix web run test -- --run
# 161 passed
npm --prefix web run typecheck
# exit 0
npm --prefix web run build
# exit 0，以上 A02 实际产物
.venv/bin/python -m pytest -q server/tests/api/test_web_acceptance.py server/tests/api/test_web_wire_fixture.py server/tests/api/test_system_output_mutations.py server/tests/api/test_system_reads.py server/tests/invariants/test_output_enable.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_transport.py
# 136 passed
.venv/bin/python -m ruff check server/tools/web_acceptance.py server/tests/api/test_web_acceptance.py
# passed
```

Python 为既有 `.venv`：3.14.4 / pytest 9.1.1 / Ruff 0.16.9，未改环境。后端有一项既有 Starlette/httpx deprecation warning，无失败。一次误指定不存在的 `test_system.py` 导致 collection error，检查真实布局后使用 `test_system_reads.py`，未改代码或抑制断言。最终 `git diff --check` 通过；review 同时检查新文件及基线差异，普通 git diff/stat 不包含既有 untracked 文件，不能作为完整范围证据。

## Contract / Relationship traceability

既有 Contract Matrix REQUIRED；本轮不新增或改变业务合同。共同 11 字段及 WEB-LYRICS/WEB-OUTPUT 行沿用 [Task 8 Contract Audit §8](../../plans/2026-10-09-task-8-contract-audit.md)，owner/test/Gate 由当前计划分配，具体消费链如下：

| Contract / Spec source | 实际 owner 与接线 | proof / 结果 |
|---|---|---|
| WEB-LYRICS-001；Library §3.1 LRC、Playback §7.2、Architecture §4.1/12 | 实际 snapshot Song → PlayerFacts → 既有 display clock → PlayerView → parseLyrics/activeCue/LyricsStage | 上述歌词 unit + 真实 store/clock/component invariant PASSED；正 offset、多 tag、同时间组、纯文本/失败 fallback、无时钟无高亮、迟到连接/切歌、手动恢复及 reduced-motion |
| WEB-OUTPUT-001；Output §6.1–6.3、Architecture §4.2/TX-IDEMP | 既有 runtime API → immutable intent → PUT system/output → REST alias decoder；confirmed facts 只消费 full snapshot | Output invariant + wire + native API fixture PASSED；pending/unknown、原 key 显式重试、失败保留 observed、alias/snake_case、后续 canonical 请求不被本地反馈遮蔽 |
| Output 与 Playback/Queue/History/Context/AutoPlay 关系 | 真实 Services + MockMPD + API；输出开关不建立页面播放权威 | fixture/API/backend output Gate PASSED；开关不改变业务队列/历史/播放/target，Source 44100 不冒充 DAC 参数，CLIENT_STREAM 不提供浏览器播放器 |

歌词只使用已有 snapshot 文本，没有独立资源获取或 cache owner；纯文本插值，不解释 HTML；保留 read_error 即使有 fallback。输出 receipt 只确认该请求并触发既有 refresh，不安装为设备事实。Shared clock/epoch/generation 继续拥有时钟、恢复和迟到屏障。Contract 与跨模块 Relationship Gate PASSED。

## LAN、进程与场景

当前产品 URL：**http://10.104.60.177:5173/**（11:56 +08:00 更新）。当前 wlan0 `10.104.60.177/24`，排除 lo、容器、VPN；此前 `192.168.3.18` 已失效。前端 `0.0.0.0:5173`，后端 `127.0.0.1:8000`，实际 `API_PROXY_TARGET=http://127.0.0.1:8000`；手机只访问产品端口。

11:28:13 +08:00 fresh 检查：页面/资源/API health/state/system-output HTTP 200；`ws://192.168.3.18:5173/api/realtime` 返回 protocol 1 full initial，epoch `3e849b5c-ee81-47b2-bb80-0d52153b4274`、sequence 14。真实进程和监听已核对：backend PID **25628**；复用实际 preview PID **31597**。证据在 ignored `.superpowers/sdd/2026-10-09-task-8-web-batch-plan/w5-a02-lan.json`。

当前为正常曲、PAUSED 37 秒、NAS_DAC ACTIVE（模拟）、DAC 参数 null；歌词 61 行、正 offset 500ms、35 秒双行 cue。点击恢复后夹具通过真实后端观察推进时间。下一首前三次依次为：长标题纯文本 → read_error 带可用 fallback → unknown/无歌词。AutoPlay 另有后续重复候选，不影响这前三步；需要重置由 AI 准备，不要求用户操作终端/数据库。所有歌曲是自建静音 fixture，不代表真实 MPD/DAC。

当前独立数据库 `w5-runtime/phone-4d1c985b3731445e853909822ee8b55e.db`；旧 W3/W4/W5 数据库均保留。本轮重启为 fresh owned DB，未删除旧数据。以下为 AI/维护者从仓库根目录启动、停止方法，**用户手机验收无需执行**：

```bash
.venv/bin/python -m server.tools.web_acceptance --runtime-dir .superpowers/sdd/2026-10-09-task-8-web-batch-plan/w5-runtime --port 8000 --advance-clock --w5
# 另一个终端；使用已有构建产物
API_PROXY_TARGET=http://127.0.0.1:8000 npm --prefix web run preview -- --host 0.0.0.0 --port 5173 --strictPort
# 停止前先 ps -p 25628,31597 -o pid,args 核对仍是上述 owned 进程；再分别 kill 对应 PID
# 前台新进程可 Ctrl-C；重启后重新核对 PID/IP/API/WS，不复用过期 PID
```

进程保持运行。本机浏览器已预检封面/歌词切换、键盘滚动暂停/恢复跟随、实际 Output 停用/启用以及后三个歌曲状态；最终恢复以上初始场景。辅助有效 viewport 355×601、320×509，无横向溢出，短屏可自然纵向滚动；歌词 `user-select:text`，具 accessible names；Tab 可从歌词内容到播放进度，visible solid focus。reduced-motion 自动用例通过，新歌词背景为不依赖 blur 的实色。Ubuntu/IAB 预检不替代手机长按选择、触摸和舒适度结果。

## W5-A02 手机验收卡

沿用 W3 设备记录：Samsung S20+、411dp、2400×1080、Samsung 浏览器、字体/页面缩放 100%。系统及浏览器版本当时未提供，仍待补充；设备/设置若变化再记录。本轮手机可达 **PENDING**。

| 编号 | 手机实际步骤与通过基准 | 状态 |
|---|---|---|
| W5-H01 | 打开上述 URL，页尾确认 W5-A02。正常曲切换封面↔歌词，保持同一媒体区；恢复播放查看当前行高亮/跟随。手动滑动、长按选择歌词文本，应暂停跟随、不触发 seek；点“回到当前行”恢复。下一首前三次查看普通文本、不丢失 read_error 提示的 fallback、无歌词，各自可辨且不串曲；unknown 不显示旧高亮。 | HUMAN PENDING |
| W5-H02 | 可先在正常曲完成：向下滚至音频输出，停用→确认事实变为 DAC未启用，再启用→DAC已启用。按钮/请求等待/确认事实清楚，Source 44.1kHz 不代填仍未知的 DAC 参数；CLIENT_STREAM 仅显示尚未支持，无浏览器播放入口。复杂失败/迟到竞态由自动 proof；需要可见异常时由 AI 准备同页最小 fixture。 | HUMAN PENDING |
| M01/M02 | 以上两卡同时检查竖屏无横向溢出、主操作可达、歌词与页面滚动不误触、按钮状态及请求反馈可读。 | HUMAN PENDING |
| M04/M07 | H01 的长文本/unknown/无歌词及 reduced-motion、无 blur fallback 可用；AI 预检已完成，手机可见效果随 H01 确认。 | HUMAN PENDING |
| M03 | 无文字输入/软键盘流程。 | N/A |
| M05/M06 | W4 本批前已有人类通过证据；W5 用共享恢复/clock、歌词迟到与 Output request-generation 自动回归，本轮不伪称重复手机通过；W6 综合复验未执行。 | W4 evidence retained / W6 NOT RUN |

用户可仅回复“W5-H01/H02 通过”，或编号与问题。反馈原意及日期：**尚未收到本轮反馈**。必要项确认前不标 HUMAN PASSED，不关闭 W5。若有问题，在本 Batch 复现、最小修复、受影响验证、更新同一页面并在本报告追加新轮次/需复验编号。

## 裁决、限制与当前结论

- 按用户指定 checkout 执行，保留共享 dirty、ignored ledger/runtime 和旧 DB；不采用技能默认隔离、提交、清理或下一任务步骤。代价是并行窗口修改仍需范围审查，分支集成由用户控制。
- 仅在既有验收入口增加可选 `--w5` 及真实 API proof，W4 默认行为保留；不创建公开故障入口或独立控制台。代价是 fixture 必须正确采样/注入，已由集成测试保护。
- reviewer 无法判定手机选择/触摸/短屏舒适度，交由 H01/H02 HUMAN PENDING；辅助预检不抵扣，必要反馈仍可能要求 W5 修复。
- 真实 MPD/NAS/DAC 未运行，遵守用户禁止真实服务的边界；不能认证设备精度/声音或物理连接。
- W6 综合网络/后台/手机流程及 PWA 超出 W5；W4既有恢复证据仅作为前置，不能称本 Task 整体验收通过。

实现和自动 Gate 已通过，LAN READY；剩余 blocker 是本轮手机连通性及 W5-H01/H02 必要项的用户确认。**W5 HUMAN PENDING，未关闭；W6 前置尚不满足。Task 8 整体未完成，PWA DEFERRED。**

## W5-A02 入口更新 — 11:56 +08:00

用户要求重新查看 IP 并配置后端/界面入口。fresh 网卡及路由检查显示 Wi-Fi IP 变为 `10.104.60.177`；已有前端 wildcard 监听与 loopback API/WS 代理无需写死新 IP 或重启。backend 25628、preview 31597 命令与实际监听再次核对，进程保持运行，数据库和当前暂停 37 秒场景保留。

新入口页面、两项 assets、health/state/system-output 均 HTTP 200，资源与 A02 dist 完全相同；同源 WS protocol 1 full initial 成功，epoch/sequence 仍为上述值。实际产品浏览器已切换到新 URL，显示“实时连接”和 W5-A02。fresh 证据：ignored `w5-a02-lan-ip-update.json`。没有产品/依赖修改，不需重新构建或重复自动 Gate；H01/H02 沿用 A02 验收卡，手机新网段可达及 HUMAN Gate 仍 PENDING。


## W5-A03 — 封面点击入口与透明歌词（12:08 +08:00）

用户确认局部设计：移除“封面 / 歌词”切换按钮，点击整张专辑封面（含无封面占位）进入歌词；歌词右上角向内对角箭头返回封面。歌词容器改为透明、无边框与卡片圆角，融入页面背景。专辑高斯模糊背景及深色蒙版留待后续，没有在本轮实现。

本轮仅修改 PlayerView.vue、LyricsStage.vue、既有 player-lyrics invariant 的切换入口断言与本份验收记录/计划轮次。歌词 parser、共享 clock、高亮、手动滚动/长按选择、恢复跟随、read_error/plain/missing fallback、Output、后端及依赖均未修改。新增返回按钮是独立的 44px 原生按钮，位于歌词内容之外；正文点击不触发切换。原高亮行样式与“回到当前行”按钮保留。

切换 invariant 先 RED（旧媒体选择器仍存在），最小实现后该单例及歌词文件 7 项 GREEN。fresh W5 指定五文件 49 passed，Web 全量 161 passed（含 157 invariants），typecheck、build、git diff --check 通过。未重复运行后端回归/Ruff/P3：本轮无 Python、后端合同或依赖变更，A02 证据保留，不冒充本轮重跑。

构建命令：`VITE_ACCEPTANCE_LABEL=W5-A03 npm --prefix web run build`。实际 LAN 的两个资源与 dist 逐字节一致：

- `index-uZjvrJ8b.js`，126659 bytes，SHA256 `98f7685523fdc4a2630108f5bd3d11764cf45e06eaf679652f780ee5cf5792ad`。
- `index-Dxy_kJX3.css`，7895 bytes，SHA256 `489607f287b4c684414c50fca40577b2d123bfcfd911b2492bdbf242977bd07a`。

当前入口仍为 **http://10.104.60.177:5173/**；页面、health/state/system-output 均 HTTP 200。复核 backend 25628、preview 31597 的命令与监听，复用进程及数据库。产品浏览器显示“实时连接”和 W5-A03，封面点击、返回图标、两侧 Enter 操作均通过辅助预检。实际 viewport 319×597，无横向溢出；computed style 为透明背景、0px border、0px radius，返回按钮约 44×44px。截图保存在本地 visualization 工作区。未触发播放、下一首或 Output 修改；当前观察是正常曲、暂停约 60 秒、DAC已启用且参数未知，未重置用户已操作的运行时。

用户已说明页面可打开，记为此前入口手机连通性反馈；**A03 新构建的 H01/H02 仍 HUMAN PENDING**。本轮 H01 改为“点击封面进入歌词 → 右上角内对角图标返回”，其余原验收步骤和 H02 不变；请刷新后核对页尾 W5-A03。Contract/Relationship 未新增业务合同，既有共享时钟、迟到隔离、歌词与 Output 关系由上述 49 项及全量回归保护。

W5 未关闭，W6 NOT STARTED；真实 MPD/NAS NOT RUN，PWA DEFERRED。共享修改保留，未提交、推送或执行远端操作。


## W5-A04 — 紧凑歌词、自动恢复跟随与 cue seek（12:21 +08:00）

用户确认本轮设计，覆盖原 Spec “按钮恢复跟随、歌词点击不 seek”的 Web 交互约束；已在 Library Spec Web 歌词补充同步记载。保留 A03 的封面点击入口、右上角内对角返回图标与透明背景。本轮移除正常同步歌词的“同步歌词 · embedded”字样及整个跟随按钮，收紧顶部留白。异常/plain/malformed/no lyrics 的提示保留；后端 source/status 等字段不改。

同步歌词 pointer/wheel/键盘手动滚动暂停跟随，指针释放且停止滚动后 3 秒恢复；惯性 scroll 重置倒计时，文字选择阻止自动回弹，结束选择后重新计时。普通歌词无恢复计时器、不产生 seek，保留用户位置。资源/连接/歌曲 scope 改变及卸载清理计时器，窗口 pointerup/cancel 处理区域外释放。

可 seek 的 cue 点击/Enter/Space 经 PlayerView → 既有 actions beginSeek/preview/releaseSeek → POST playback/seek，保持目标 token、pending 锁、请求回执/观察分离及进度待确认展示。位置为 cue 秒数减 offset；未知时长、断连、不可 seek、锁定和超出 [0,duration] 的行不发请求。移动超过 8px、滚动、长按至少 500ms、非折叠文本选择抑制点击跳转。没有改后端、API/public wire、共享 clock/parser 或 playerActions 实现。

自动 proof：三项先 RED（旧字样/按钮、无 cue emit、无产品 seek request），实现后歌词文件 10 passed。普通文本保持位置的新场景在旧实现也通过，仅作为回归，不算 RED。fresh W5 + seek 六文件 **65 passed**；Web 全量 **164 passed**（含 **160 invariants**）；typecheck/build/diff 检查通过。新增/调整测试覆盖 2999/3000ms、长按/拖动/选择、惯性重置、scope/卸载清理、inverse offset、真实 request target/pending/preview/canonical/越界/断连。后端与 Python 未变，不重复后端/P3/Ruff，也不将历史证据冒充本轮重跑。

构建：`VITE_ACCEPTANCE_LABEL=W5-A04 npm --prefix web run build`，57 modules；实际 LAN assets 与 dist 逐字节一致：

- `index-BDNqAzQo.js`，129124 bytes，SHA256 `aa4e931862c5181c524f9e94e2960f34d25fa1fac56dc51573c379aba094c432`。
- `index-CdEEhfUg.css`，7748 bytes，SHA256 `6babcd88f7b0a80434bba176e2753528ef3ec37e4994609328aaa8b7f6417c41`。

入口仍为 **http://10.104.60.177:5173/**，页面/health/state/system-output HTTP 200，产品浏览器“实时连接”、W5-A04。现有 backend 25628、preview 31597 命令与 IP 复核，进程和数据库继续运行。未触发播放/seek/下一首/Output 写入，保留用户当前正常曲、暂停约 165 秒的状态。

355×601 辅助预检：无横向溢出，歌词正文高度约 184px，正文顶端距固定 header 约 12px，返回图标与正文横向间距约 8px；原 A03 319×597 正文区被状态栏与跟随按钮占用，此轮释放约两行双行歌词空间，实际容量随手机字体/宽度变化。实际浏览器 wheel 之后 scrollTop 约 1825，停止后回到当前第34行，scrollTop 约2474。截图在本地 visualization 的 w5-a04-lyrics.jpg，预检完恢复默认 viewport。手机长按/拖动/舒适度仍需用户反馈，辅助预检不替代 HUMAN Gate。

**A04 H01 复验卡（替代历史按钮恢复步骤）：** 刷新并核对页尾 W5-A04；点击封面进入透明歌词，图标返回。恢复播放检查高亮；手动拖动后只松手，等待约3秒回到播放行，连续拖动/惯性滚动期间不抢位置；再拖动并点具体 cue，进度跳到该句，长按选择不跳转。下一首前三次检查普通文本（拖动后不回弹）、read_error fallback、无歌词，各自可辨且不串曲。H02 沿用原 Output 停用→启用及未知 DAC 参数要求。

W5 implementation/受影响 automated 与 Contract/Relationship 回归通过；**H01/H02 HUMAN PENDING，W5 未关闭，W6 NOT STARTED**。真实 MPD/NAS NOT RUN，PWA DEFERRED。共享修改保留，未提交或执行远端操作。


## W5-A05 — 移除底部 Output 卡片与自适应页面（12:34 +08:00）

用户明确确认歌词部分无问题、禁止再修改；本轮冻结 LyricsStage.vue、lyrics.ts、playerActions.ts 和 player-lyrics.test.ts。修改前后 SHA256 核验一致，未改这些文件。仅调整 PlayerView.vue 外层布局/OutputPanel 接线、App.vue 的验收标签展示、app.css shell 高度与底部预留，以及 player-output.test.ts 的产品接线断言和当前验收/计划记录；既有共享修改保留。

用户确认移除整块 NAS DAC / CLIENT_STREAM 卡片，包括启停按钮、参数和请求反馈；进度条上方 DAC confirmed facts 和 title 详情保留。OutputPanel 实现及其独立合同测试保留，后端/API/依赖不变。原 W5-H02 页面启停 Gate 按本次用户范围修订为 N/A，不伪称已手工完成。

页面使用动态 viewport 高度和可伸缩媒体区；封面保持正方形，实际尺寸取媒体区可用宽/高较小值。底部预留 4rem（默认64px）加 safe-area，仅作 Task 9 空间预算，不增加导航元素、路由或功能。必要的最后业务歌曲与状态读取异常提示移到播放控件上方；空 operation-status 不占位，实际反馈/恢复控件保留。验收轮次移到浏览器标题 **MPD-Server · W5-A05**，不在底部新增内容。

Output 产品接线 invariant 先 RED（旧卡片仍存在），移除接线后该单例及 Output 文件 9 passed。中间新测试错误假定既有 fixture 的 DAC 参数未知，实际 fixture 有 96kHz 参数；只修正该测试的场景输入为显式 null，未修改产品状态逻辑或弱化断言。fresh W5 + seek + facts 七文件 **93 passed**；最终布局调整后 Web 全量 **164 passed**（160 invariants），typecheck、build 与 diff 检查通过。未运行后端回归/Ruff/P3：Python/后端未修改，历史证据保留。

浏览器布局预检发现 size container 在不确定父高度下把封面缩为44px；通过 shell 明确动态高度和显式 grid 轨道修正。短屏初版最小媒体区12rem挤掉导航预留，最终外层最小区4rem且预留归属 Player，保持短屏内容和预留共同参与尺寸预算。最终真实浏览器结果：

- 约320×510：页面高度510px，媒体区约123px，控件底部距窗口底约64px，无横向溢出。
- 355×601：页面高度601px，媒体区约215px，封面约215px正方形，底部约64px。
- 411×900：页面高度900px，媒体区约512px，封面约379px正方形，底部约64px；额外高度由媒体区吸收，不积累底部空白。

歌词根组件可随外层媒体区尺寸伸缩，歌词文件/交互逻辑不变。浏览器预检不替代手机页面比例反馈；极短屏或额外错误提示/较大字体允许必要的自然滚动，不裁切操作。预检后恢复默认viewport。截图 w5-a05-player.jpg 在本地 visualization 工作区。

最终构建 assets 与 LAN 逐字节一致：

- index-BWpcTgE5.js / 124865 bytes / SHA256 9b0f264857f597e4e2e2f7310e961e517f36db19adb7909633d2de74436fcd3e
- index-CQJZR0us.css / 7484 bytes / SHA256 d62ba1f63ae35eb7d571e177f69e9162a188b81e311e9f70f7d20bf0a17b2426

页面/health/state/system-output HTTP 200，产品显示实时连接。现有 preview PID31597 保留；原 backend25628 在本轮预检中已退出，loopback健康请求拒绝连接，未对退出原因作无证据推断。复用原启动器恢复验收，new backend PID **7628**（执行会话27313），监听127.0.0.1:8000；启动器按既有行为生成新独立数据库 `phone-2569e1cfcec44b76b1ad88437d1f12ff.db`，旧数据库全部保留。默认正常曲暂停37秒，DAC启用、参数未知；未连接真实MPD/NAS。启动/停止方法沿用旧节，但停止前使用当前PID7628/31597并再次核对命令。

用户此前原话“歌词部分没有问题了”，记录为 **A04歌词部分 HUMAN PASSED / FROZEN**；不是全部Task已验收。当前只需刷新原入口 **http://10.104.60.177:5173/**，确认 A05 页面底部卡片已移除、DAC状态仍位于进度上方，不同比例仅在控件下留导航空间。**页面比例 HUMAN PENDING，W5未关闭，W6 NOT STARTED**；Task9仅预留，NOT STARTED。真实MPD/NAS NOT RUN，PWA DEFERRED；未提交或执行远端操作。


## W5-A06 — 顶部操作状态图标与稳定布局（12:43 +08:00）

用户确认仅调整播放操作反馈，不修改额外区域。新增 PlaybackStatus.vue，将原 PlaybackControls 的 feedback 优先级和 retry/read 操作原样接入顶部 MPD SERVER 栏中间；PlaybackControls 保留原播放按钮、能力/锁和 aria-busy，移除底部 operation-status 和 recovery-row。PlayerView 仅新增 header 状态组件和 position:relative，并去掉已无用途的底部空状态样式。app.css、App.vue、页面高度/媒体尺寸预算/底部64px预留、歌词组件/样式/逻辑、后端与依赖不改。

请求/pending/syncing/handoff 显示转圈图标，结束后消失。异常或结果未知显示异常图标；点击打开绝对定位的详情浮层，包含原来的重试原操作/重新读取状态和关闭入口，Escape可关闭。状态区域固定尺寸且不参与文档流，浮层也不挤压媒体区；没有导航实现。原反馈保留在屏幕阅读器 live region，正常同步不显示详细文字；reduced-motion 禁止图标旋转。操作 intent、target、key、锁、收敛等待逻辑未改。

新产品 invariant 先 RED（header内没有反馈区域），接入后单例GREEN。既有单条提示用例原断言要求提示位于player-content，按用户要求改为header唯一提示且底部零提示，其状态/内容断言保留；该精确用例复跑通过。fresh相关七文件 **93 passed**，Web全量 **165 passed**（161 invariants）、typecheck/build/diff检查通过。冻结的LyricsStage.vue、lyrics.ts、playerActions.ts、player-lyrics.test.ts与A05前快照SHA256一致。未重跑Python后端/Ruff/P3：本轮无相关代码变更。

355×601真实产品seek预检：先ArrowRight将暂停进度188→189，再ArrowLeft回到188；pending及“已确认/同步中”阶段在header显示spinner，底部无operation-status。操作前后transport底边均约537.38px，media高度均约213.86px，页面高度601px；原底部64px预留保持，不出现反馈导致的跳动。此为静音Mock验收fixture，不是真实MPD验证。截图 w5-a06-status.jpg显示真实同步图标，预检后恢复默认viewport。

构建：`VITE_ACCEPTANCE_LABEL=W5-A06 npm --prefix web run build`，57 modules。实际LAN与dist逐字节一致：

- index-B8QQ05hW.css / 8585 bytes / SHA256 7b61a7c1402bb3187ef21e18184c43ef8c6a2f371c4477995af5929aa593cda9
- index-Mez0Dmhy.js / 127463 bytes / SHA256 a751fe620cb53cb74e4529bacb3306606468be8c68909dcd6cf7e9c4cce7674d

入口仍为 **http://10.104.60.177:5173/**，浏览器标题 **MPD-Server · W5-A06**，页面/API健康/state HTTP200，产品实时连接。沿用backend7628、preview31597及A05数据库，未重启/删除运行时。新的手机复验只需点击播放/暂停或进度操作，检查顶部状态图标且页面不跳动；失败/未知由自动测试保护，手机可见异常按需另行准备。

A04歌词 HUMAN PASSED/FROZEN 证据保留，原Output启停H02 N/A。A06页面比例/顶部操作反馈 HUMAN PENDING；W5未关闭，W6 NOT STARTED，Task9仅预留NOT STARTED。真实MPD/NAS NOT RUN，PWA DEFERRED。共享修改保留，未提交或执行远端操作。


## W5-A06 手机真人验收入口复核 — 2026-10-10T14:42:08.273725+08:00

按用户要求只继续 W5-A06，不推进 W6。fresh 核对 wlan0 为 `10.104.60.177/24`；backend PID7628 使用既有 `.venv/bin/python -m server.tools.web_acceptance --advance-clock --w5`，监听127.0.0.1:8000；preview PID31597监听0.0.0.0:5173。复用进程和已有独立Mock运行时，未重启或重置场景。

手机入口：**http://10.104.60.177:5173/**。页面、health、playback/state、system/output 均 HTTP200；实际 HTML/JS/CSS 与当前 dist 逐字节相同，JS/CSS名称、大小、SHA256与上节A06相同。实际浏览器标题 **MPD-Server · W5-A06**，显示实时连接，底部无Output卡片，进度上方DAC确认摘要存在。同源WS返回protocol 1 `snapshot`完整首帧，envelope/state epoch及sequence一致。核验脚本曾误将首帧type断言为initial/full，按实际wire合同改为snapshot后通过；属于核验脚本假设错误，无产品修改。原始fresh证据保存在ignored `w5-a06-lan-recheck.json`。

当前曲为“歌词读取失败 · 本地验收曲”，PAUSED约84秒，DAC已启用、参数未知；此歌词fallback场景不等于播放操作异常，不要求重新验收已冻结歌词。手机可直接点击播放/暂停或调整进度，检查顶部同步图标、媒体区和按钮不跳动，页面比例自然、底部导航预留保持、控件不被遮挡；确认Output卡片移除且DAC摘要仍保留。异常详情按需由AI准备最小场景，再验文字大小、关闭和原retry/read操作。

本轮仅复核服务与入口，未修改产品/依赖，未重新运行产品自动测试，A06历史自动证据保留。手机当前可达、页面比例与顶部反馈仍 **HUMAN PENDING**；不以本机预检替代。W5未关闭，W6 NOT STARTED；真实MPD/NAS/DAC NOT RUN，PWA DEFERRED。


## W5-A06 手机真人结论 — 2026-10-10（Asia/Shanghai）

用户对本轮实际入口及三项手机验收卡回复原话：**“以上通过”**。据此记录：

| 本轮手机项目 | 结果 |
|---|---|
| 打开当前入口、核对W5-A06；页面比例自然、底部导航预留保持、主控件不被遮挡 | HUMAN PASSED |
| 播放/暂停或调整进度时顶部同步图标出现，媒体区和按钮不跳动 | HUMAN PASSED |
| 底部Output卡片已移除，进度上方DAC确认摘要仍保留 | HUMAN PASSED |

A04歌词HUMAN PASSED/FROZEN继续保留；原Output启停H02按用户修订N/A。异常详情最小场景本轮未请求、未执行手机验收，不能把“以上通过”扩展为该可选场景的真人通过；其原恢复行为沿用A06历史自动proof。

W5 implementation及required automated/Contract/Relationship沿用本报告已有证据，本次仅更新验收文档，未修改产品或重跑自动测试。结合A06入口fresh核验与上述真人反馈，当前W5必要Gate已满足，**W5 HUMAN PASSED / CLOSED**。W6真人前置已满足，但按用户要求**W6 NOT STARTED，不自动推进**；Task8整体验收尚未完成。真实MPD/NAS/DAC NOT RUN，PWA DEFERRED。未提交、推送或执行远端操作。
