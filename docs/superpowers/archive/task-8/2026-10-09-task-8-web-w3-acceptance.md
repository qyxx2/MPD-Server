# Task 8 Web Batch W3 acceptance

唯一 W3 记录；轮次追加于本文件。日期：2026-10-09（Asia/Shanghai）。当前轮次 **W3-A03**（必要子场景均已获用户确认，W3已关闭），未提交版本，HEAD `adf4171` / branch `feature/task-8-web-player`。只执行 W3，W4–W6 / Task 9 未实施。

| 状态层 | 当前证据与结论 |
|---|---|
| Implementation | DONE；Player facts、单路由、shell 连接生命周期、封面与视觉基础，独立review两处Important已以精确RED→GREEN修复 |
| Automated Gate | PASSED；独立review修复后重新targeted/invariants/full/typecheck/build GREEN |
| Contract Matrix / Relationship Gate | REQUIRED；WEB-PLAYER-FACT-001 + Architecture §4.1/§12，见下表 |
| Native / LAN | READY；新LAN/API/WS本机核验通过；用户已继续确认当前手机页面无问题 |
| Human Gate | **HUMAN PASSED**；H01正常/长标题/无封面/unknown与H02 unbound/stale全部必要子场景已获用户确认，W3关闭 |
| 真实 MPD/NAS | **NOT RUN**；Mock 不证明声响、DAC、真实 MPD 精度 |
| PWA | **DEFERRED**；无 manifest/SW/安装/离线壳交付 |
| Task-level acceptance | 未验收；本记录不声明 Task 8 完成 |

## 当前页面、场景与运行方法

当前真实产品 URL：[http://192.168.3.18:5173/](http://192.168.3.18:5173/)。LAN 来自 `wlan0 192.168.3.18/24`（A03最终核验发现Wi-Fi地址变化；A01/A02的10.59.115.177已失效）；排除了 loopback、ds-br0 和 tun0。监听 `0.0.0.0:5173`，后端 `127.0.0.1:8000`；Vite preview `/api` REST/WS 使用 `API_PROXY_TARGET=http://127.0.0.1:8000`。手机只访问产品 URL。

当前stale场景：先通过实际Service观察normal，再断开本地Mock，actual_freshness=stale、绑定freshness=unknown、error_code=PLAYER_UNAVAILABLE；业务current保留`夜航 · 本地验收曲`。页面应标“最后观察（已过期）”，业务歌曲仍独立作为最后业务歌曲，进度与源参数未知。WS服务本身保持连接。页面页脚 `W3-A03 · Mock 本地验收夹具 · 不代表真实 MPD/DAC`。

已准备并用实际 API 检查 normal / long / unknown / unbound / stale。长中英文标题、unknown duration/metadata、actual外部URI与最后业务歌曲不同、断开Mock产生stale 均由同一个原应用的 Service/Repository/Mock 生成。没有合成 state endpoint、公开故障注入 API或独立控制台。场景由 AI 修改本机 ignored `w3-runtime/scene.txt`（normal/long/unknown/unbound/stale），watcher 通过既有 Service/PlayerPort 执行；用户不用终端/数据库/开发者工具。每场景切换都在同一产品页继续，由AI确认后告知。

相关进程保持运行：backend PID `11213`（exec session38181），preview PID `11219`（session77042）。启动/停止由AI操作，记录可复现方法如下，用户无需执行：

```bash
# 仓库根目录；每次后端启动生成新的独立 owned DB，不覆盖旧DB
.venv/bin/python -m server.tools.web_acceptance --runtime-dir .superpowers/sdd/2026-10-09-task-8-web-batch-plan/w3-runtime --port 8000
# web目录；使用本轮实际dist和原生代理
API_PROXY_TARGET=http://127.0.0.1:8000 node node_modules/vite/bin/vite.js preview --host 0.0.0.0 --port 5173 --strictPort
# 仅停止本记录的进程，重启后必须重新查PID/监听/API/WS
kill 11213 11219
```

DB、自建1秒静音WAV、scene文件、日志都在 ignored `.superpowers/sdd/2026-10-09-task-8-web-batch-plan/w3-runtime/`或对应ledger目录；不访问已有音乐/DB。未修改Python依赖、`.venv`，未使用Docker或真实MPD/NAS。

首轮标识（已由A02替代）：`VITE_ACCEPTANCE_LABEL='W3-A01 · Mock 本地验收夹具 · 不代表真实 MPD/DAC' npm --prefix web run build`；2026-10-09约18:50构建。dist index使用 `index-xsGuoLpI.js`、`index-B69xRjXX.css`；SHA256：

- JS `3da8255ee1f7ec12c5d1bb4f5357dc354ba4a384e34a12a8902dafcdda2d9a72`
- CSS `68002a2189865faaded6509db9543353e81e70a3343f88bdc9cdc1ed3d04131c`
- index `4724d5583d5a9749d11ce17d0c1415c5eaf3be61f106f0e44eb3fa50b6dd0d2e`

## 自动证据与关系追溯

| 命令 / Gate | fresh结果 |
|---|---|
| `npm --prefix web run test -- --run tests/invariants/player-facts.test.ts tests/invariants/realtime.test.ts` | 36 passed（facts21 + realtime15） |
| `npm --prefix web run test:invariants -- --run` | 87 passed |
| `npm --prefix web run test -- --run` | 88 passed |
| `npm --prefix web run typecheck` | PASSED；测试helper类型与final nullable模板类型错误已修正，重跑通过 |
| A02 label下 `npm --prefix web run build` | PASSED；实际dist已启动 |
| `.venv/bin/python -m pytest -q server/tests/api/test_web_acceptance.py server/tests/api/test_web_wire_fixture.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_recovery.py` | 45 passed；既有Starlette/httpx deprecation warning独立记录，无环境失败 |
| `.venv/bin/python -m ruff check server/tools/web_acceptance.py server/tests/api/test_web_acceptance.py` | PASSED |
| LAN page / `/api/state` / `/api/health` + WS | loopback及10.59.115.177 origin HTTP200；proxied snapshot protocol1 / live invalidate通过；五个场景由实际StateService验证 |
| `git diff --check`、实际diff/stat/status | PASSED；实际diff/stat/status及11个W3新文件whitespace检查通过 |

WEB-PLAYER-FACT-001 的11字段继承audit §8.1共同字段和专项row；本轮不修改业务语义。具体traceability：

| Contract / source | owner | executable proof |
|---|---|---|
| WEB-PLAYER-FACT-001 / audit §8.2、Architecture §12.3.1、Playback §8.8–8.9 | playerFacts.ts、PlayerView.vue | 实际 decoder→realtime→readonly store→AppShell→Player；fresh actual不同、missing/unknown、stale/断线、四种异常sync、NO_CANDIDATES仍匹配、confirmedSTOPPED、unavailable身份保留 |
| Source与Output分离 / Library §3.1、Output §6–8 | playerFacts源参数/输出参数独立函数、PlayerView独立区 | 16bit44.1kHz源 vs 24bit96kHz输出，未知不补零；无输出样本不伪报confirmed |
| 资源身份/失效 / Architecture §4.1、主Plan artwork API | ArtworkStage.vue | API404/503/network/decode失败，占位稳定；切歌旧图片迟到不串曲、同歌library revision旧结果拒绝；当前歌词引用随snapshot切换，不提前实现W5同步歌词 |
| RT-CONNECT/RECOVER/SNAPSHOT/OBSERVE inherited | AppShell唯一生命周期 + W2 realtime/store | default Player无Task9 nav；shell卸载释放socket listener；W2新代次/lateGET/read-only回归；后端snapshot/observation/recovery关系回归 |
| Local fixture真实接线 / 手机方法§2–3 | server/tools/web_acceptance.py | 原main.lifespan显式Mock注入、实际Service选曲/观察、独立DB与媒体、初始WS同模型、无公开验收接口 |

RED：首个指定测试因尚无shell/view失败；最小未绑定表示后GREEN。随后9个表示场景实际失败→GREEN、5个artwork场景实际失败→GREEN、router缺失→GREEN、无Output样本误报不可用失败→GREEN。Capability补充回归已由之前实现支持，不伪称新增RED。详见ignored progress.md和日志。

夹具调试不是生产缺陷：第一次外部观察根据旧binding正确为EXTERNAL_DRIFT，后续采样在binding失效后为UNBOUND，准备场景时显式观察两次；现有StaticFiles对未知POST返回405，改用GET404验证无公开夹具读入口，不修改backend路由。后端P3未在W3验收；W4仍需fresh全Gate。

## 辅助预检与手机验收卡

A01/A02辅助预检（历史证据）：仅可用Codex IAB（Chromium）进行实际构建预检；Chrome工具不可用，Firefox未运行。请求320/430 viewport在面板实际为277/377 CSS px；normal、长中英文、unbound完整URI换行可读，无普通内容横向溢出（scrollWidth=clientWidth）；实际computed backdrop为blur16px。CSS具备无backdrop的实色fallback与reduced-motion静态规则；未伪称已执行手机文字缩放、系统reduced-motion或无blur真机验证。

用户设备：三星S20+，最小宽度411dp，2400×1080分辨率，三星浏览器，页面和字体缩放100%；系统与浏览器版本未提供。手机可达：用户已确认可以打开。A02正常页显示无异常，用户要求去掉一大一小两个外层卡片并融合背景。

| 必验卡 | 操作和通过基准 | 状态 |
|---|---|---|
| W3-H01 | 手机竖屏打开URL并上下滚动；先查看正常曲/无封面。AI随后切long、unknown，用户继续同页查看。封面占位/层级稳定；长标题可读且无横向溢出；未知metadata/时长不伪造为0；源文件不标为DAC参数。M01/M04，M02本批无按钮，触摸滚动可达；控件在W4、切歌词在W5 | HUMAN PASSED：A03正常/无封面及融合背景、long、unknown均获用户确认 |
| W3-H02 | AI切unbound，然后stale，用户继续同页查看。external.wav实际URI与“最后业务歌曲”分层，旧业务曲不标实际Now Playing；未绑定/未知/过期说明可读 | HUMAN PASSED：unbound及stale均获用户确认 |

M03 N/A（无输入）；M05/M06由W4-H03主验，本批继承自动断线表示proof；M07本批无动画/歌词菜单，静态reduced-motion/opaque fallback保留，辅助环境限制如上。无业务按钮并不代表播放控制已交付。

首次可回复“已打开 + 手机型号/系统/浏览器 + H01当前场景结果”；AI切剩余场景时会明确告知，不要求用户用本机脚本。产品缺陷在本W3内复现、最小修复、精确测试及回归、更新同一页面与本记录。只有用户确认所有必要子场景后才记录HUMAN PASSED。

用户首次反馈日期：2026-10-09。W3剩余blocker：无。W3作为下一Batch的前置已满足；W4完整前置仍须在W4开始时fresh核验后端P3与扩展DTO，本次未认证、不自动推进。真实MPD/NAS NOT RUN、PWA DEFERRED。

## Rulings与范围保留

- 按用户指定checkout实施，不另建worktree；全部初始dirty W1/W2/Compose/文档/backend fixture保留；代价是无额外并发隔离。
- 用户明确覆盖skill默认commit/清理/下一任务流程：不commit、不删除ledger/evidence、不进入下一Batch；变更供本地审查。
- 原手机方法授权的必要最小接线：本机fixture脚本/关系测试、可选构建label；代价是仅Mock显示证明，不提供设备证明。

Batch结论：**W3已关闭，HUMAN PASSED**。实施、自动/关系Gate、LAN和本Batch必要手机验收均满足；Task8整体未完成。以下轮次条目为历史状态，以本表及最终关闭记录为准。

## W3-A02 · 2026-10-09 19:00（Asia/Shanghai）

独立只读审查发现两项Important，无Critical/Minor：无成功Output样本被误标为历史确认；confirmed Stop / fresh unbound actual被绑定进度freshness误标“未确认”。已依据Output §6.1及实际backend observation字段核实，两项在同一个最终修复pass完成。三个精确关系测试实际RED→GREEN（output fallback有NAS_DAC行但无observed_at、有效confirmedStop形状、fresh unbound），原身份/进度保护未放宽。

最终自动结果：facts21/realtime15=36、invariants87、fullWeb88；typecheck与labelled build通过。final nullable模板类型错误（outputFreshness不为unknown不自动令TS收窄output）以原有optional访问修正，精确typecheck与全Web重新通过。native45/Ruff仍适用（backend源码未在本修复pass改变）。没有第二次review，以RED→GREEN和完整绿色回归证明修复。

当前实际构建：`index-B95GBR2l.js`（SHA256 `dd6c2948638785b7a38cd2407f531e558a754dc55d31f2ce2c7a6ab53e91a0cf`）、CSS仍为`index-B69xRjXX.css`（同上hash）、index SHA256 `e571a1e9994df535ffc41bbb84ca483b640eabd95c7bdcc0946783501ceecb4b`。页面已reload并可见W3-A02标识、`输出尚未确认 / 输出未知 / 参数未知`。LAN page/API200、同源WS当前initial再次通过；进程及端口不变，正常无封面场景保持运行。

需用户首验：W3-H01/H02全部子场景（此前没有用户通过项，因此不是复验旧手机结论）。用户反馈仍为空，HUMAN PENDING，Batch未关闭。

审查设置 aside的裁定：手机视觉/可达只由用户判定，不以IAB截图抵扣；真实MPD/NAS维持NOT RUN；W4/W5/Task9/PWA及无关W1/W2改动不扩大本次范围，消费边界已检查。代价分别为手机证据未取得、无设备证明、后续Batch仍须单独履行前置。没有deferred minors。


## W3-A03 · 2026-10-09（Asia/Shanghai）· 手机视觉反馈修复

用户A02反馈：三星S20+、411dp、2400×1080、三星浏览器、100%页面与字体缩放；产品页可以打开，显示本身无异常，但不希望播放区/输出区存在一大一小两个额外卡片背景。另询问未来全局模糊专辑背景是否会影响文字可见性。此反馈不等于全部H01/H02通过。

最小视觉修复：PlayerView去掉两个外层glass类；app.css删除相应背景/边框/阴影/blur，播放区与输出区直接融入页面背景，并保留内容间距、封面占位与文字层级。纯样式反馈没有业务语义变更，不添加镜像CSS测试；按手机方法在当前W3处理，既有用户授权覆盖重复设计批准，不扩大为未来背景功能。

当前背景仍是固定深色渐变。对最亮页面底色#142438计算sRGB相对亮度对比：primary #f3f7fc为14.58:1、secondary #bdcadb为9.43:1、muted #9cacc2为6.79:1；此数值仅覆盖当前页面文字tokens与底色，不替代字体大小/手机可读性，也不证明任意封面图通过。Visual Spec要求ambient artwork背景保持稳定对比和neutral dark fallback；未来接入必须用稳定深色遮罩/明度约束，而仅模糊不足以保证文字可见。不在本轮提前实现动态专辑背景；此约束记录为后续接入需验事项。

fresh验证：facts21 + realtime15 =36 passed；typecheck和带A03标签build通过。业务代码、backend未改变，A02完整Web88/invariants87/native45/Ruff证据仍适用；Contract/Relationship Gate保持PASSED。LAN产品页/API200及同源WS initial再次通过，backend11213/preview11219保持运行，normal场景不变。最终核验发现wlan0变为192.168.3.18，旧地址超时；新地址的页面/state/health均200，同源WS protocol1 initial通过。IAB换用新地址成功，实际A03页可见且computed两外层section均透明背景、border0、shadow none、blur none；本次辅助截图为桌面宽度，不能替代411dp手机复验。新地址手机可达仍待用户确认。

构建命令：`VITE_ACCEPTANCE_LABEL='W3-A03 · Mock 本地验收夹具 · 不代表真实 MPD/DAC' npm --prefix web run build`。实际JS `index-B4n8DjMt.js`，SHA256 `3ecb2445d77e274c206fe070c47d878af201e2ffa05c888ba674315a4c29ec0e`；CSS `index-CVaFkqAo.css`，SHA256 `42f57d47f46f12456a092695087f0e57166cf0f28c3d9a2a7862bd24c178eb2e`；index SHA256 `05b3858bd99d803020da540e443a2fd200963c0b6422f6e251827cb4ffb41a39`。

请改用新URL http://192.168.3.18:5173/ 见A03，先复验W3-H01正常/无封面子场景的融合背景、文字可读性、间距与滚动。用户确认后由AI依次准备long/unknown（H01）、unbound/stale（H02），不要求用户操作数据库/终端/开发者工具。HUMAN PENDING；未关闭W3，下一Batch前置未满足（W3真人必要项未全通过，W4仍须fresh核验P3）。真实MPD/NAS NOT RUN；PWA DEFERRED。


### W3-A03 场景推进：long

2026-10-09 用户反馈“w3-h01目前可以测试到的没有问题了，你继续”。据当前实际场景为normal，记录H01正常/无封面、融合背景/可读性/间距滚动复验通过；不推断未展示的long/unknown或H02通过。已将本地scene切到long；实际LAN page/health200，state及proxied WS protocol1 initial均核实长中英文标题与长艺术家数据。构建仍A03，无源码/依赖变更，不重建或重复执行无影响测试。相关进程保持运行。等待用户在同一页确认长标题换行、文字可读与无横向溢出后再切unknown；W3仍HUMAN PENDING。


### W3-A03 场景推进：unknown

用户反馈长标题“测试显示正常。你继续下个测试”，记录H01 long通过。已切unknown：实际LAN page/health/state200，同源WS protocol1 initial核实current song=acceptance-unknown、artists为空、codec/bit_depth/sample_rate_hz/channel_count及observed duration均null。构建仍A03，无源码修改；自动Gate证据不变，运行进程保持。手机需确认未知艺术家/源参数/时长以未知表示、没有补成0时长或虚构音频参数；其后H02 unbound/stale仍待验收。W3 HUMAN PENDING，不进入下一Batch。


### W3-A03 场景推进：unbound

用户对unknown反馈“都符合，继续”，H01正常/长标题/无封面/unknown全部必要子场景HUMAN PASSED。已由原fixture的Service/Mock链路切unbound；实际LAN page/health/state200与同源WS protocol1 initial核实实际URI external.wav、sync_status UNBOUND、matches_current=null，业务current为acceptance-normal。核验脚本最初误假设matches_current必须false；实际未绑定形状为null，既有fixture关系测试要求is not True，属于核验假设错误，未修改生产代码或测试。构建仍A03，无代码变更；运行进程保持。手机需确认实际URI/未绑定说明清楚、正常曲仅位于“最后业务歌曲 · 不代表实际正在播放”区，并且长URI可换行无横向溢出。H02 stale仍未展示；W3 HUMAN PENDING，不关闭、不进入下一Batch。


### W3-A03 场景推进：stale

用户对unbound反馈“测试没有问题。继续”，H02 unbound HUMAN PASSED。现切stale，原Service先观察normal后仅断开本地Mock；actual_freshness=stale、绑定freshness=unknown、无bound target、PLAYER_UNAVAILABLE。核验脚本最初误假设两个freshness都stale；已核查playback_observation.accept failure路径：原matches_current非true时绑定freshness为unknown，actual观察有历史样本则stale，属于核验假设错误，未改生产代码/测试。实际LAN page/health/state200，同源WS protocol1 initial确认actual stale，相关进程保持运行。此夹具不代表真实MPD/DAC断线，且WS连接与播放器观察的新鲜度不同。构建仍A03，无源码变化。手机需确认“最后观察（已过期）”与“观察已过期”说明可读，旧业务正常曲位于最后业务歌曲区，观察位置/时长显示未知，不把旧数据呈现为当前已确认播放。等待最后必要子场景用户确认，W3仍HUMAN PENDING；不进入下一Batch。


## W3-A03 最终关闭记录 · 2026-10-09（Asia/Shanghai）

用户对最后stale场景反馈“没有问题”，记录H02 stale HUMAN PASSED。本次三星S20+（411dp，2400×1080，三星浏览器，页面/字体100%缩放）已确认H01正常/无封面融合背景复验、长标题、unknown，以及H02 unbound和stale全部必要项。无未关闭的W3真人缺陷；W3 HUMAN PASSED并关闭。

最终实现与自动证据：player facts21 + realtime15=36；invariants87；full Web88；native相关45；Ruff/typecheck/build通过。A03纯视觉反馈修复后重新targeted36/typecheck/build，后续仅场景与验收记录更新，无源码或依赖变更，因此未重复无影响测试。Contract/Relationship Gate PASSED。最终git diff --check与diff/stat/status及本轮记录实际修改检查通过；初始其他窗口dirty全部保留，没有commit/push/PR/merge。

实际构建仍为上文A03产物；当前LAN http://192.168.3.18:5173/，产品page/API/同源WS已核验，用户已在此轮完成手机反馈；backend11213及preview11219保持运行，当前stale场景保留。启动停止方法仍见本记录。夹具只证明显示与合同接线，不证明真实MPD/NAS/DAC/音频；真实MPD/NAS NOT RUN。PWA DEFERRED；动态专辑背景的任意封面可读性未接入/未认证，未来接入须履行既有稳定对比/fallback约束。

W3剩余blocker：无。W3前置产物已可供W4消费；W4完整前置不能仅凭本结论确认，后端P3及扩展DTO须在W4用当前代码与fresh test evidence核验。W4–W6 NOT STARTED；不进入下一Batch，不声明Task8整体完成。
