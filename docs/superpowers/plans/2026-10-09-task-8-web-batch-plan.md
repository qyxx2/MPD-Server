# Task 8 Web State and Player Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Execution method requires user selection; do not start implementation solely because this plan exists.

**Goal:** 交付共用 typed REST/WS 状态基础与手机浏览器中真实表达播放状态、可触摸操作的 Player。2026-10-09 用户调整：PWA 安装/静态缓存延期，不阻塞手机 Web 验收及 Task 9。

**Architecture:** Vue reactive stores 分离 canonical realtime、revision-dependent resource cache 与 UI state；API client 统一 mutation/key/error，realtime client 统一 baseline/invalidate/reconnect。Player 消费上述事实，禁止本地 Queue/AutoPlay 权威。

**Tech Stack:** Vue 3/TypeScript/Vite，Vue Router，Vitest/Vue Test Utils/jsdom；使用现有 CSS 及语义 tokens，不为视觉样式额外引入框架。

**Spec:** Architecture §4.1–4.3、§12；Playback §7–8.9；Library §3.1；Output §6–8；Web/PWA Visual Spec；主 Implementation Plan。

**Status:** 计划待审阅，所有 W1–W6 均 NOT STARTED。拟新增接口/测试不是已有实现。原 Task 8 Step 未勾选。

## Global Constraints

- 同源 REST/WS；不直接访问 MPD、不认证、不新增浏览器音频播放。
- canonical state 仅完整 snapshot，资源需 epoch/revision/generation 保护；所有 mutation 使用共同幂等机制。
- 断线 degraded read-only，新连接 initial snapshot 才恢复写入；成功 GET 不独立开写。
- 手机浏览器为主要使用/真人验收环境；LAN HTTP 交付真实页面，Ubuntu Firefox/Chromium 仅作辅助预检，不开发桌面专用布局。
- 不新增验收场景控制台/平台；最小启动与数据准备纳入现有 W1–W3 支持范围。
- PWA manifest/SW/安装/冷离线壳延期；不引入 API 缓存、业务持久化或离线 replay，不使用真实音乐目录作测试 fixture。
- Task 9 页面/底部导航/通用 SongRow/Favorites UI 不在本计划实施；仅提供共享 stores 与 Player 单路由。
- 不改 `.venv`，不自动 commit/push/PR；Node 依赖只在 W1 的已授权实施范围新增并提交 lockfile供审查。

## Review Focus

- 同 epoch 重连及跨 epoch 旧请求倒灌：W2 barriers。
- HTTP 成功、旧 observation 尚在、当前歌曲已变：W4 seek proof。
- stale actual 与旧业务歌曲在同一页面出现：W3 facts proof。
- API Output alias 和 realtime snake_case 混用：W1 wire/W5 output proof。
- 手机触摸、断线恢复、后台页面恢复与实际构建：W6 自动与人工 Gate；SW/安装/冷离线壳为 DEFERRED。

## 依赖与 Contract Impact

W1→W2→W3→W4→W5→W6。W4 额外依赖 [后端前置 P3 自动 Gate](2026-10-09-task-8-playback-control-prerequisite-plan.md)；W1–W3 可使用明确标记的 fixture，但不能声称真实新接口已验收。

全部 W Batch：Contract Matrix **REQUIRED**；Relationship Gate **REQUIRED**。

新 rows 采用 [Task 8 audit §8](2026-10-09-task-8-contract-audit.md) 的共同 11 字段与 WEB-PLAYER-FACT/CONTROL、WEB-SEEK、WEB-PROGRESS、WEB-LYRICS、WEB-OUTPUT 六行；本计划分配 owner/test/Gate。继承 Architecture §4.1–4.3 与 Task 6 RT-SNAPSHOT/CONNECT/DELIVERY/RECOVER/OBSERVE、Task 5 TX-IDEMP、Task 7 Output 合同；不重新定义这些共同规则。

| Contract / source | implementation owner | proof | Gate |
|---|---|---|---|
| Architecture §4.1–4.2 / typed wire | services/api.ts、wire.ts | client.test.ts、wire.test.ts、mutation.test.ts | W1 |
| Architecture §4.1/§12 / authority/recovery | services/realtime.ts、stores/player.ts、resourceCache.ts | realtime.test.ts、resource-cache.test.ts | W2 |
| WEB-PLAYER-FACT-001 | playerFacts.ts、PlayerView.vue | player-facts.test.ts | W3 |
| WEB-PLAYER-CONTROL-001 / WEB-SEEK-001 | playerActions.ts、ProgressControl.vue | player-controls.test.ts、player-seek.test.ts | W4 |
| WEB-PROGRESS-001 | playerClock.ts | player-clock.test.ts | W4 |
| WEB-LYRICS-001 / WEB-OUTPUT-001 | lyrics.ts、LyricsStage.vue、OutputPanel.vue | player-lyrics.test.ts、player-output.test.ts | W5 |
| 手机 Web delivery / Architecture §4.1–4.2 | 现有启动入口、vite proxy、Player build | 已有 Web invariants/build、本文真人 Gate | W6 |
| Architecture §4.3 / PWA | sw.ts、manifest、build integration（延期未交付） | pwa.test.ts、PWA build-output proof（延期未运行） | DEFERRED；不阻塞 W6/Task 9 |

所有测试路径默认 `web/tests/invariants/`；解析器局部测试位于 `web/tests/unit/`。测试不是已存在文件。

## 跨 Batch 接口

- `types/api.ts` 定义实际 REST DTO、FullStateSnapshot、SnapshotFrame/InvalidateFrame、PlaybackControlTarget、ApiError；REST Output DTO 独立，不假定与 realtime 相同。
- `services/wire.ts`: `parseSnapshot(value: unknown): FullStateSnapshot`、`parseRealtimeFrame(value: unknown): RealtimeFrame`、`normalizeOutput(value: RestOutputSnapshot): StateOutputSnapshot`；坏数据抛 WireError，未知 protocol version 不接受。
- `services/api.ts`: `createApiClient({fetch, origin})`，`get<T>(path, decode): Promise<T>`，`createIntent(method, path, payload): MutationIntent`，`send<T>(intent, decode): Promise<T>`。MutationIntent 的 key/method/path/canonical payload 不可变，重试重用同对象；204 decoder 不解析空 JSON。
- `stores/player.ts`: `createPlayerStore()`，`acceptInitial(snapshot, connectionId)`、`acceptRefresh(snapshot, connectionId)`、`markDisconnected()`；只读 snapshot/writable/status 给组件，组件不直接写 snapshot。
- `services/realtime.ts`: `createRealtimeClient({api, store, socketFactory, clock})`，`start(): void`、`stop(): void`、`refresh(): Promise<void>`；connectionId 是每连接新代次，GET 结果不得建立 writable。
- `stores/resourceCache.ts`: `createResourceCache<T>({load, dependencies})`，`read(key): Promise<T>`、`invalidate(marker): void`，entry 包含 data/fresh/loading/error。dependencies 明确 library/playlist；Task 8 提供 library.ts/playlists.ts 薄包装，Task 9 不再造缓存机制。
- `components/player/playerFacts.ts`: `derivePlayerFacts(snapshot, writable): PlayerFacts`，输出实际身份、最后业务身份、按钮能力；映射 audit §8.2。
- `components/player/playerClock.ts`: `createPlayerClock(clock)`，`accept(snapshot, timing)`、`suspend()`、`position(): number | null`；Timing 含 requestStarted/responseReceived 单调时间，未知为 null。返回展示值，不写 store。
- `components/player/playerActions.ts`: `createPlayerActions({api,realtime,store})`，显式 pause/resume/next/previous/stop/seek(seconds,target)；控制 pending/unknown/confirmed-awaiting-state，不以 WS 代替 HTTP ACK。
- `components/player/lyrics.ts`: `parseLyrics(text, format): LyricsDocument`、`activeCue(document, seconds): number[]`，相同时间返回 cue 组。

实现过程中接口需要改名/调整时先同步本接口表与所有消费者，不能在后续 Batch 发明另一套 API。

## 手机真人验收 Gate（2026-10-09 用户优先级调整）

操作、LAN 交付、最小数据准备和报告模板见 [手机 Web 真人验收方法](2026-10-09-mobile-web-manual-acceptance.md)。不新建 W0，不建设独立控制台；W3 起交付实际产品页面。表中真人项是各 Batch 的关闭条件，自动通过后标记 HUMAN PENDING，用户必要项通过后才关闭。复杂时序由 REQUIRED 自动 invariant 证明，不强迫用户用终端/开发者工具。

| Batch / 编号 | 页面与用户操作 | 可见基准 |
|---|---|---|
| W1 / W2 | 无产品页面；真人 N/A：typed client/store 基础机制 | 执行既有 REQUIRED 自动 Gate，不为真人验收造调试 UI |
| W3-H01 | LAN 手机打开 Player；正常/长标题/无封面/unknown 场景 | M01/M02/M04；封面占位与层级稳定，身份/未知值真实，不要求宽屏专用布局 |
| W3-H02 | AI 准备 actual 与业务 current 不一致场景，用户查看 | 旧业务歌曲不标为实际正在播放；stale/unknown 说明可读 |
| W4-H01 | 已准备歌曲/位置；暂停→恢复、上一首/下一首、独立 Stop | 原位恢复不归零；各动作符合既有合同；STOPPED 主按钮不代选曲 |
| W4-H02 | 手机拖进度→释放、取消；快速重复点操作；未知时长 | 触摸与页面滚动不误冲突；反馈清楚；取消不提交；未知时长禁 seek；提交次数/key 由自动测试证明 |
| W4-H03 | 手机断网→恢复、后台/锁屏→返回 | M05/M06；只读和重连状态可辨，时钟不伪造推进；旧 target/迟到 receipt 自动 Gate 保留 |
| W5-H01 | 封面↔歌词，手动滚动/选择歌词、恢复跟随、切歌 | 同一媒体区；LRC 高亮/跟随真实，plain/no lyrics/read_error 可辨，不串曲；M07 |
| W5-H02 | 手机 Output enable/disable；AI 按需准备失败状态 | 确认事实与 pending/错误分开；源 metadata 不冒充 DAC 参数；CLIENT_STREAM 不提供播放 |
| W6-H01 | 本次构建的手机页面综合重复 W3–W5 关键流 | 当前版本 LAN 可达；M01–M06 适用项通过；实际 build 不是旧 dist；无真人 blocker |

W4-H02 的冲突/取消细节可以先由 AI 预检并自动证明，手机必须实测常用拖动/释放。需要异常场景时由 AI 最小脚本/fixture 准备并给步骤，不建设公开故障入口。真实 NAS 前置 manual gate 独立保留，不由手机 Mock 通过抵扣。

## 通用 RED→GREEN 与检查规则

每个 Batch 按以下步骤执行：1 写指定最小测试并运行单个测试证明 RED；2 最小实现；3 新增场景逐个 RED→GREEN；4 运行该 Batch 文件及明确的回归文件；5 typecheck/build、实际 diff 和 Contract traceability。下列命令中的测试文件在对应 Step 创建，不声称现在可运行。

## Batch W1 — 可测试 typed client 与 mutation 意图

**Files:** Modify web/package.json、vite.config.ts；Create web/package-lock.json、vitest.config.ts、tests/setup.ts、tests/fixtures/wire.json、src/types/api.ts、src/services/wire.ts、api.ts；Create tests/invariants/{client,wire,mutation}.test.ts。

**Interfaces:** 上述 typed client、decoder、MutationIntent。W1 还提供可注入 transport 与 clock 的 test fixtures，不用真实服务器。

- [ ] 核对 native/LAN 启动条件：显式 Mock 注入、独立 DB、前端 `/api` 的本机 REST/WS 代理；必要最小启动支持随 W1–W3 实施，不导入 Task 10 最终配置或新增控制台。
- [ ] 检查当前 Node/npm 与已有安装状态，选择满足现有 Vite/Node engines 的 Vitest/jsdom 与 Vue Router/Vue Test Utils 版本，锁定 lockfile；不更新无关既有依赖。增加 test=`vitest`、test:invariants=`vitest tests/invariants`，jsdom environment。
- [ ] RED `same-origin HTTPS uses wss without changing host`：`npm --prefix web run test -- --run tests/invariants/client.test.ts -t 'same-origin HTTPS'`。
- [ ] 实现 URL 与 client/decoder，再逐个 RED→GREEN：HTTP→ws、204、typed error、网络未知、同 key retry/payload immutable、畸形 WS 首帧、旧服务器缺 target→null、Output alias 转换。
- [ ] wire fixture 从真实 Pydantic model_dump(by_alias=True)/WS envelope 生成；增加 `server/tests/api/test_web_wire_fixture.py` 对 fixture 与实际 DTO 字段/alias/nullability 作确定性验证，命令 `.venv/bin/python -m pytest -q server/tests/api/test_web_wire_fixture.py`。P3 之前新 target fixture 标明前置未完成，W4 Gate 必须用真实 P3 模型重新核验。
- [ ] `npm --prefix web run test -- --run tests/invariants/client.test.ts tests/invariants/wire.test.ts tests/invariants/mutation.test.ts`；typecheck/build；diff 检查。

## Batch W2 — canonical store、reconnect 与 resource cache

**Files:** Create services/realtime.ts、stores/player.ts、resourceCache.ts、library.ts、playlists.ts；Create tests/invariants/realtime.test.ts、resource-cache.test.ts（源文件均位于 web/src）。

- [ ] RED `late GET cannot replace a newer connection baseline`，用 deferred promises 控制旧 GET/新 initial 顺序；运行 `npm --prefix web run test -- --run tests/invariants/realtime.test.ts -t 'late GET'`。
- [ ] 实现连接代次、最高失效水位和单飞刷新：invalidation 到达立即推进已知 dependency revision；响应不能清除它未覆盖的失效义务。刷新失败保留义务并重试读取，不能清除错误伪称 fresh。
- [ ] 逐个 RED→GREEN：same epoch 新连接、跨 epoch GET 触发重新确认、duplicate/old sequence、请求中更高 invalidation、playlist+library 双依赖、查询 generation、断线禁写、只读 GET 不开写、重复连接清理。
- [ ] 重连采用有上限退避 0.5/1/2/4/8 秒并加至多 20% jitter；稳定 initial 后重置，stop 时取消 timer/listener。禁止自动业务 retry。
- [ ] `npm --prefix web run test -- --run tests/invariants/realtime.test.ts tests/invariants/resource-cache.test.ts tests/invariants/mutation.test.ts`；typecheck/build；确认 UI 不含第二个 store。

## Batch W3 — Player 真实状态与视觉基础

**Files:** Modify src/App.vue、main.ts；Create router/index.ts、views/PlayerView.vue、components/player/playerFacts.ts、ArtworkStage.vue、components/layout/AppShell.vue、styles/tokens.css、styles/app.css；Create tests/invariants/player-facts.test.ts。

- [ ] RED `unbound actual never labels the persisted song as now playing`，挂载真实 store→Player，fixture actual 与 current_song 不同；运行该测试。
- [ ] 实现 audit §8.2 表示与单 Player 默认路由；连接生命周期属于 AppShell 而不是页面 mount。Task 9 bottom navigation 不提前出现。
- [ ] 逐个 RED→GREEN：missing/unknown/stale、NO_CANDIDATES+matches_current、源文件 metadata 与 DAC 分离、Artwork API 404/读取失败、切歌后迟到图片/歌词引用不串曲；不凭 queue 推断 Context 名称。
- [ ] 跑 player-facts + realtime invariants、typecheck/build；按手机验收方法准备最小数据和 LAN 启动，交付实际 URL/端口/轮次；用户执行 W3-H01/H02。Ubuntu 只辅助窄屏/长文本/玻璃 fallback 预检。

## Batch W4 — transport 控件、seek 与展示时钟

**Prerequisite:** 后端 P3 自动 Gate 已通过，W1 fixture 与实际扩展 DTO 已重新核验。

**Files:** Create components/player/playerActions.ts、playerClock.ts、PlaybackControls.vue、ProgressControl.vue；Modify PlayerView.vue；Create tests/invariants/{player-controls,player-seek,player-clock}.test.ts。

- [ ] RED `seek release sends one intent and rejects a changed target`；pointer moves 不发 HTTP，release 一次，服务端冲突清除草稿而 canonical 未变化。
- [ ] 实现目标捕获、key 复用、pending 控件锁与独立 Stop。HTTP success 后 refresh；seek 的同步等待需观察当前 identity 及 observation.observed_at 不早于已确认 receipt.updated_at（均服务器时间），否则保留“正在同步”；current 已变化则撤销旧等待。
- [ ] FakeClock 实现 audit §9.1 的保守有限外推；same sequence snapshot 可用于读取时序估计，但不能替换 canonical 或重新赋予样本寿命。键盘 keyup/blur 单次提交，Escape/pointercancel 撤销；unknown duration 禁 seek。
- [ ] 逐个 RED→GREEN：resume 原位回执、STOPPED 主按钮不选曲、timeout retry 原 key、Stop 与迟到 seek receipt、HTTP 成功/read 失败、暂停/stale/后台停止插值、相同样本不续命、duration 到尾不 next、重复 URI 切歌。
- [ ] 跑三个新文件 + player-facts/realtime/mutation invariants；typecheck/build。不得用前端通过替代后端 target Gate。
- [ ] 更新同一 LAN 页面，交付 W4-H01/H02/H03 手机触摸验收卡；必要时间推进仅放在最小验收夹具，失败后按本 Batch 反馈复验闭环处理。

## Batch W5 — 同步歌词与 Output

**Files:** Create components/player/lyrics.ts、LyricsStage.vue、OutputPanel.vue；Modify PlayerView.vue；Create tests/unit/lyrics.test.ts、tests/invariants/player-lyrics.test.ts、player-output.test.ts。

- [ ] RED `lyrics highlight uses the player display clock`，真实 store+clock+LyricsStage；运行新 invariant 单例。
- [ ] 实现 Library Spec 规定 LRC 语法/offset/多 cue/plain fallback、手动滚动与恢复跟随。歌词文本渲染为 text，不解释 HTML。
- [ ] 实现 NAS_DAC enable/disable，confirmed fact 与 request/pending 分离；CLIENT_STREAM 只表示预留不可用，不提供浏览器播放器。Source metadata 不代填 output 参数。
- [ ] RED→GREEN：同时间 cue、read_error 带 fallback、切歌与迟到资源、无时钟无高亮、reduced motion、失败 Output 回执保留 observed fact、REST aliases/WS DTO 交错。
- [ ] 跑两个 invariant、lyrics unit、player-clock/wire invariants；typecheck/build；验证歌词可选择、按钮可访问名称及键盘焦点。
- [ ] 交付 W5-H01/H02，同一手机页面验证歌词选择/滚动及 Output 反馈；复杂失败与迟到资源用自动 proof，不新增控制台。

## Batch W6 — 手机 Web 综合与 Task-level acceptance

**Files:** 当前 Task 8 Web 源码/测试、现有启动/代理支持和 Batch acceptance；仅按验收缺陷修改对应 owner，不增加新的产品功能或测试平台。

- [ ] 运行 `npm --prefix web run test:invariants -- --run`、`npm --prefix web run test -- --run`、`npm --prefix web run typecheck`、`npm --prefix web run build`；使用本次实际构建产物启动同源 REST/WS 的 LAN 预览。可复用此前有效结果，不为凑数重复测试；核对没有误用旧 dist。
- [ ] 运行 `.venv/bin/python -m pytest -q server/tests/api/test_web_wire_fixture.py` 与后端 P3 gate，更新最终 traceability；检查 diff/check/stat/status，无无关依赖、DB、缓存或生成 dist 进入提交范围。
- [ ] 手机执行 W6-H01：复验 W3–W5 关键流及 M01–M06 适用项；必要真人项通过且本 Task 范围 blocker 清零，才报告手机 Web acceptance PASSED。真实 MPD/NAS 结果仍单列；未运行不能宣称完整真实运行时验收。
- [ ] 按手机验收方法归档结果及 Task 9 实际接口交接；明确 PWA 为 DEFERRED，不把延期原始 Step 勾选完成。

### PWA 延期范围（非 W6 阻塞 Gate）

2026-10-09 用户明确手机浏览器显示/触摸优先，安装非刚需。原 W6 的 manifest/icons、standalone shell、SW build/cache、pwa/build-output tests、安装/冷离线/SW 更新人工门禁均延期；当前不创建这些文件，不为手机验收部署 HTTPS。以后有明确需要再制定实施/验收入口，沿用 Architecture §4.3 的同源、静态缓存限定、API 不缓存/重放和无离线业务合同。本轮 Task 8 手机 Web 范围通过可作为 Task 9 依赖，不代表原始全部 PWA 范围通过。

## 验收状态必须分开记录

Implementation、automated GREEN、native/LAN environment、手机真人 Gate、真实 MPD/NAS、Task-level 手机 Web acceptance 分列；PWA 单列 DEFERRED。Task 8 的 REQUIRED 自动 Gate 不允许只跑组件或只看截图。手机真机触摸为主要证据，桌面窄屏/文字缩放/keyboard/reduced motion/无 blur 为必要辅助检查，不要求桌面专用效果或全浏览器矩阵。真实设备验收引用后端前置结果，未运行则如实 NOT RUN。

Task 9 交接必须列明 api/realtime/store/cache/actions 的实际导出接口与测试入口；不要宣称已交付其 SongRow、Queue/Library/Playlist/Favorites/Search 页面或 song Play Now 原子操作。

## 执行前审阅

先审阅本计划与后端前置计划，再选择 native 或 subagent-driven 执行。本次文档变更不自动授权依赖安装、生产代码变更、commit 或远程操作；后续明确执行请求授权计划范围内必要实施，仍受 AGENTS 约束。
