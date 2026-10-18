# 横屏布局 B5 — 最终集成验收

> 2026-10-18 按用户要求归档：该计划/验收不再作为待执行事项。保留历史 PARTIAL/PENDING 等原始结果，不据此宣称验收通过；后续仅按新需求立项。现行入口见[文档索引](../../README.md)。

日期：2026-10-17，Asia/Shanghai；本轮验证约 09:28 起。仅执行 B5。

**Implementation PASS；Automated PASS；Environment PASS（本地前端）；Browser PASS（下述真实 IAB CSS 样本及明确限制）；HUMAN PENDING；PWA PENDING；最终 Gate PENDING。实施及自主验证完成，最终验收未完成，停在 B5。**

## 基线、前置 Gate 与证据版本

- 已读取本地 `AGENTS.override.md`、现行文档索引、Batch 计划、最新横屏设计 §1–8、继承全局 UI 合同，以及 B0–B4 验收；开始时没有 B5 验收文件。
- 分支 `fix/v0.2-execution-sample-reuse`，HEAD `6091d73dc35f756057ed37e65ea2a077a1acc34b`（音乐库默认歌曲及文件时间/标题排序），与计划基线一致。24 个既有 tracked dirty 文件和既有 untracked 源码、测试、计划、规格、验收全部保留；没有切分支、回退或创建工作树。HEAD 不包含前序横屏成果，不能单独标识访问版本。
- 开始时 `web/src` 指纹为 `c252a1d9b15c307ed5aa3efe74263382c44c547ca3feb8692ef68f0fda65a2bd`，与 B4 最终确认一致。B1 整体实机 PASS、B2-R1 用户“验收通过”、B3 用户“通过”、B4 用户“可以验收”，前置 Gate 满足。B0 人工记录按既有授权豁免，仍不改写为 BASELINE READY。
- 用户此前取消本次及后续实机 CSS/visualViewport/DPR/safe-area 数值采集；继续执行这一裁定，不再要求补测或猜算 2420×1668 对应的 CSS 尺寸。
- **最终访问源码指纹：`545bb108b5d0f33b4c8da39acc8c720314d08f6029267424cbc95eb14a765106`。** 算法同前序：按路径排序 `web/src` 文件，SHA256 逐一输入路径、NUL、文件字节。B5 修复后不可把 B4 指纹当成本次最终版本；前序未受影响的业务细项可复用，最终旋转集成项须本卡确认。

## 本批最小修复与范围

真实浏览器发现 B1 增量的分数断点缺陷：实际 visualViewport 宽 `899.6865`，`innerWidth` 取整为 `900`，CSS `(min-width:900px)` 为 false，但旧组件为 landscape，导致组件与 CSS 的断点判定不一致。

新增行为测试 `uses the CSS media query when innerWidth rounds up at the boundary`，先确认因实际组件仍为 landscape 而失败；最小修改 `web/src/components/layout/layoutMode.ts`，在浏览器支持时使用同一 `(min-width: 900px) and (orientation: landscape)` 查询；不支持时保留原数值判定。原高度预算、密度、退化、监听清理及 session owner 不变。测试另确认 resize 恢复、单 Player、只启动一次 realtime、无额外写请求。随后精确单项及所属文件通过。

本批交付改动仅为上述模式判定、`responsive-layout.test.ts` 新用例、本验收及计划进度。没有改 CSS、已确认尺寸/圆角/歌词留白、页面结构、播放/Library 合同、后端或依赖。共享几何无需重排；重开 B1 受影响的断点/旋转检查，并跑 B1 指定回归。

执行裁定：采用 CSS 媒体查询解决取整根因，而不是改变 900px 门槛。代价是分数宽度不足 900 时按规格保留单列。真实浏览器复测 `899.6865 → portrait`、`900.3135/900.9404 → landscape`。

## Spec §1–8 可追溯关系

| 规格/合同 | 当前实现及保护范围 | 本轮证据/前序复用 |
|---|---|---|
| §1 基线 | 当前 dirty 工作区与实际源码，不以历史勾选替代代码 | 当前 Git、源码指纹、前序最新确认；无切分支/覆盖 |
| §2 WEB-LANDSCAPE-001 | AppShell 唯一 layoutMode；本批查询修复 | 新用例 RED→GREEN；精确 899/900/901 浏览器四页；square/窄横屏自动化 |
| §3 GEOMETRY-001 | 既有 app.css 舞台/组宽/右侧限宽 | 五组主要横屏四页量测、2560 舞台1440上限、切页 Player 不移位 |
| §4 HEIGHT-001 | 既有实际 F、高度预算与稳定退化 | 1024×600、932×430、844×390、200%字号和实际滚动；responsive-player 回归 |
| §5 NAV-001 | 单 shell/session、真实四页及 Library 子路由、媒体选择和草稿 | B1 指定回归；B3 workspace/Queue/Library/Settings 全套在完整回归中；搜索/Settings 草稿旋转及手机媒体往返 |
| §6 APPBAR-001 | 既有共享计时、异常优先、统一详情及恢复权限 | 本轮完整 AppBar/notices/mutation 测试；浏览器 unknown+busy、详情与 Escape；复用 B4 精确计时/实机细项 |
| §7 STYLE-001 | 既有连续背景、Dock、tokens 和资源身份 | 四页同 blob、亮/暗/杂乱/无图/500错误；对比度保守计算；global-artwork 全套及前序资源细项 |
| §8 ACCEPTANCE-001 | 自动化、构建、浏览器、实机分别判定 | 本记录；H1/H2 及独立 PWA 尚待反馈，不宣称全量交付通过 |

## 自动化及本地环境

沿用 Node `v24.20.0`、npm `11.19.0`、既有 `web/node_modules`（Vitest `3.2.6`、Vite `7.3.7`），没有安装或修改依赖、锁文件、`.venv`。纯前端任务未执行无关 Python/Ruff/后端测试；没有 Docker、真实 MPD、部署、提交或推送。

以下均在 `web/` 执行，日志保存在 ignored 目录 `.superpowers/sdd/2026-10-16-responsive-landscape-player-batch-plan/b5/`：

| 顺序 | 命令/范围 | 真实结果 |
|---|---|---|
| 开始全量 | `npm test -- --run` | 36 files / 359 passed，0 failed，37.63s |
| 新增单项 RED | `npm test -- --run tests/invariants/responsive-layout.test.ts -t 'uses the CSS media query'` | 1 failed：预期 portrait、实际 landscape；其余4项仅因 `-t` 未选中 |
| 最小修复后同项 | 同上 | 1 passed；没有 skip/xfail 改动 |
| 所属文件 | `npm test -- --run tests/invariants/responsive-layout.test.ts` | 5 passed |
| B1 指定＋受影响高度回归 | 下列命令 | 9 files / 86 passed，0 failed，8.30s |
| 最终全量 | `npm test -- --run` | **36 files / 360 passed，0 failed，40.54s** |
| 最终类型检查 | `npm run typecheck` | exit 0 |
| 最终构建 | `npm run build` | exit 0，122 modules，6.66s |

```bash
npm test -- --run tests/invariants/responsive-layout.test.ts tests/invariants/shell-navigation.test.ts tests/invariants/app-startup.test.ts tests/invariants/realtime.test.ts tests/invariants/global-artwork.test.ts tests/invariants/player-controls.test.ts tests/invariants/player-lyrics.test.ts tests/invariants/player-library-navigation.test.ts tests/invariants/responsive-player.test.ts
```

最终构建 CSS `index-C8Y1PZae.css` SHA256 `8e45293da1f27f5ec4fb810614255df1686754171693c0b8e8fdf1ef9180b370`，与 B4 CSS 一致；JS `index-BslNw661.js` SHA256 `9be7627397e310753344ce67ef007907ea25b08c1c4bb4dc10808f5d84712898`。浏览器访问 dev 当前源码而非 dist；构建产物保持 ignored。

独立只读审查只针对本批实际修复，无 Critical/Important。**延期 Minor：** 新用例的 matchMedia stub 未校验查询字符串；当前已覆盖故障及 resize 恢复，但未来断点/方向查询写错时保护较弱。未借此扩展既有测试工具。前序 B3 `elementFromPoint` 测试隔离 Minor 仍按原记录延期。审查不代替本轮实际测试或实机/PWA。

## 浏览器环境、矩阵与结果

Linux Codex IAB，display-mode=browser（standalone=false），根字号16px，DPR≈1.1、visualViewport.scale=1。不能视为 iPad Safari 或独立 PWA，也未获得真实屏幕阅读器、操作系统减少动态偏好、Safari 浏览器栏及软键盘的新增证据。设备型号/系统/浏览器具体版本不猜填。

新建本地只读夹具 `b5/serve.mjs`，5178 直接加载真实 AppShell、路由、当前源码及既有 JSON 测试数据。所有业务写请求拒绝，无后端代理；`B5 测试`菜单只注入合成通知。新增加深/亮/杂乱封面和图片500失败样本仅存在于 ignored 夹具，不进产品。页面标题 `MPD-Server · LANDSCAPE B5 · 6091d73 · MOCK`。本机 LAN HTTP 200，设备端可达性待用户确认。

主窗口 viewport override 与实际 CSS 存在取整差异，以下以实际 inner/DOM/visualViewport 量测为准；不把输入参数当实测。主窗口1366请求实际 inner1367，故另用同源真实浏览器 iframe 补测：根 clientWidth/clientHeight **899×700、900×700、901×700、1366×1024**，每组均点四页并量测，scrollWidth等于clientWidth。iframe 是真实 CSS 布局补证，不是目标设备或独立窗口的实机证据；夹具 HTML 位于 ignored `web/dist/b5-css-viewport.html`。其余主要样本使用真实主窗口。

下表各组均检查 Player/歌词、Queue、Library、Settings；P/A 是可见 Player/封面宽，G 是 Player 到右栏容器间距；滚动栏占宽使列表实际Q略小于R。

| 实测 CSS 样本 | 模式 / P或A / F / G（px） | 四页与可达性结果 |
|---|---|---|
| 1194×834（VV1193.73×833.86） | 双栏 /400 /296.27 /41.77 | Player x101.42；R549.11，歌词/设置Q480；Dock x436.87/y761.36/320×60；控制距Dock12.56 |
| 1024×768（VV1023.82×768.65） | 双栏 /336.38 /296.27 /35.83 | 专辑行保留，高度让给信息；Player x90.33；R470.95；距Dock12.03，不使用已取消的369px硬目标 |
| 1366×1024（精确子视口） | 双栏 /400 /约296 /47.81 | Player x179.17、右栏x626.98；Dock x523.08/y948.48/320×60；四页位置一致 |
| 1920×1080 | 双栏 /400 /296.27 /47.99 | 舞台1440；Player x456.19；R560；额外宽度在组外围 |
| 2560×1440 | 双栏 /400 /296.27 /48 | 舞台1440；Player x776.25；Dock x1120.25/y1364.14；内容不扩大 |
| 899×700（精确子视口） | 单列 | 首项正在播放；仅Player页有1份Player，其余页0；无横向溢出 |
| 900×700、901×700（精确子视口） | 双栏 /268.04 /296.27 /24 | 每页1份Player；x32、右栏x324.04；控制距Dock12.03 |
| 844×390 | 单列 | Player需内部滚动约176px；其它页单一shell-content纵向滚动；无横向溢出 |
| 932×430 | 高度退化单列 | Player需滚动约137px；核心控件保留，无布局振荡 |
| 1024×600 | fresh双栏compact /200.83 /263.79 /约35.83 | 右栏、控制与Dock可达；连续极短高后可保守维持单列，恢复1194×834后正常双栏 |
| 390×844、768×1024、834×1194 | 单列保护 | 原AppBar约43.4、导航64；默认控件和媒体选择保留，四页无横向溢出 |
| 1194×834、200%字号（32px根字号） | 可滚动单列 | 四页无横向溢出；实际滚动253.29后控制y578.20/h128，底部706.20与导航y705.86仅亚像素舍入；核心按钮可达 |

短高退化的保守恢复沿用 B2 已说明的可达性取舍：宁可临界时保留单列，不裁切核心操作；本轮没有改该算法或为了维持双栏缩字号。常规目标 iPad 空间恢复双栏已实测。200%本轮为**字号放大**，不是浏览器原生200% zoom或设备系统字号的实测；未将 Ctrl+0 无效尝试记为缩放成功。

补充检查：

- 1194 样本四页保持同一背景 blob。Queue 实际滚至2212.54px、Settings至184.33px后，Player/AppBar/Dock几何不动；Library长列表的scrollHeight约3410。纵向所有者为shell-content，歌词自身跟随沿用既有歌词视口及回归，不增加外层滚动。
- 连续两轮834×1194↔1194×834，Settings草稿 `b5-unsaved.example` 保留；搜索 `B5 draft` 同样保留。390竖屏歌词→844横屏→390竖屏仍有返回封面入口；最终1194正常双栏仅1份Player、1份歌词。未点击播放、seek、收藏或设置保存。
- 长中文/连续英文/emoji完整身份详情在视口内（x372.87/y117.45/w447.99/h598.95），关闭可用；列表长身份不撑宽页面。空Queue、空Library保持框架，Library显示暂无歌曲。
- 亮白、纯黑、杂乱彩色封面、无图/缺字段及封面HTTP500分别检查。无图与真正读取失败区分，500在顶部出现封面读取失败，背景回默认；Player和Dock不跳动。资源迟到拒绝、pending/unknown写锁、重试原key及重复读取由本轮全套测试和既有安全合同承担，不用真实MPD造异常。
- unknown+busy安全合成样本显示警告、没有spinner；统一详情能打开、显示另有1项未完成及原读取入口，Escape可关闭；浮层x436.87/y45.98/w319.99/h261.12，不推动Dock。精确5秒、焦点例外及轮询不续期复用未改的B4细项和本轮全套测试。
- 浏览器读取的正文/次级/muted/歌词/强调色均来自既有tokens，opacity=1。以白色背景图经0.8深色蒙版得到的最亮保守底色，按sRGB相对亮度计算主文字10.06:1、次级6.51:1、muted4.68:1、accent6.60:1、focus7.79:1、状态warning6.15:1，满足普通文字4.5/必要非文本3的颜色阈值。另实际查看杂乱和暗图。此为token与不透明合成边界的检查，不宣称所有透明/禁用态或实机逐像素都已测量。

主窗口整数像素、分数边界及精确子视口输出保留在本会话工具记录，本文件整理实测摘要；截图只用于本轮目视查看，未伪造不存在的本地截图文件。一次单列导航误用“歌词”、一次summary误按button角色、一次搜索入口误用“搜索”均读取新DOM后修正；被拒绝的fractional viewport参数、不可读取的navigator/iframe.contentDocument及未返回的动作不计入通过证据。最终用受支持的frame locator完成精确样本。

## B5-H1/H2 最终实机验收卡

**访问版本：** [B5只读验收页](http://192.168.3.18:5178/)，标题 `MPD-Server · LANDSCAPE B5 · 6091d73 · MOCK`，源码指纹 `545bb108…a765106`。先刷新；5177旧标题和NAS旧版本不作为本次标识。若设备打不开，反馈“5178无法访问”即可，先处理可达性，不擅自部署。尺寸采集继续免除。

1. **iPad Safari（保留浏览器栏）：** Player/歌词→Queue滚动→音乐库“搜索音乐库”输入几个字→Settings输入临时host但不保存→横竖往返→关闭键盘。预期布局连续、只有一份Player、背景连续，搜索和当前表单草稿旋转保留，输入/导航可达；离页放弃设置。浏览器栏展开/收起时专辑仍可见、控制不被Dock遮挡。
2. **iPad独立PWA：** 仅当已有能访问**相同5178且标题/源码版本相符**的主屏独立窗口时，在独立窗口重复第1步，注明“主屏独立窗口，无Safari地址栏”。旧NAS PWA或仅Safari标签页不抵扣。若没有此环境，反馈“PWA未安装/无法使用当前版本”，保持PWA PENDING；本批没有新增manifest/service worker，也未安装或部署PWA。
3. **桌面实际宽窗口：** 同一版本快速点歌词、Queue、音乐库、设置，滚一下右页；预期外围空间扩大、左Player不动、Dock居中。iPad/手机模拟视口不能替代这一实际宽窗确认。
4. **手机纵屏：** 看Player并切歌词，导航四页，点“B5测试→模拟普通信息”观察约5秒消隐；纵→横→纵一次。预期原纵屏布局/媒体选择和状态功能保持、控件可达；无需重做播放、拖动有效提交或后端性能。

**反馈只需逐项注明：** `iPad Safari 通过/问题；独立PWA通过/未安装/当前版本不可用；桌面通过/未测；手机通过/未测`，附设备/系统/浏览器版本（知道时填写）。有异常给截图及发生步骤；无异常不要求截图、数值或重复前序完整用例。可选用同版本 `?cover=dark`、`?cover=clutter` 查看背景；无需自行构造危险异常。

## 收尾与未闭合项

已核对实际改动、`git diff --check`、`git diff --stat`、`git status --short`；本轮tracked既存diff未改，新增修复位于原本untracked的两文件内，不能只看git diff漏掉它们。ignored证据/夹具和dist不作为提交内容。未引入数据库、依赖或环境文件；没有自动提交、推送、PR、Docker、真实MPD或部署。

仍缺 **B5-H1最终Safari与独立PWA、B5-H2实际桌面/手机反馈**；独立PWA环境未知，当前仓库无manifest/service worker，不能把普通浏览器窗口标成PWA。真实Safari软键盘、浏览器栏和独立窗口的最终行为仍由本卡承担，不用自动化替代。

**本批自主实施/自动化/限定浏览器验收已完成；HUMAN/PWA PENDING，尚不满足最终完成标准。计划无B6，不进入其它功能或后续工作；收到反馈后仍在B5闭合。**

## 用户追加授权：提交、推送与 CI 镜像交付

2026-10-17 用户明确要求以手机/iPad为主停止扩大矩阵，测试无问题后将本轮改动一起提交、push、触发CI并提供镜像标签，由用户自行部署实机测试。此授权允许在最终HUMAN/PWA闭合前交付测试镜像，不代表用户已通过B5；不授权代理部署、操作NAS或真实MPD、创建PR或合并main。

提交范围为B1–B5横屏产品、测试、规格/计划/验收及相关文档索引；四份既存performance acceptance修改不属于本轮，保留在工作区。push前发现远端多一条文档提交`15f52bf`（仅全局视觉合同旧版内联横屏规则）：保留其Git历史，以当前专篇及后续用户裁定为尺寸/范围权威，避免旧封面公式、隐藏专辑及纵屏图标尺度重新覆盖已验收成果。整合不改产品源码，最终源码指纹仍为`545bb108…a765106`。

当前分支push会自动触发`.github/workflows/container.yml`：先validate（后端测试/lint、前端测试/typecheck/build），再发布linux/amd64和linux/arm64镜像。仅在两job成功且发布步骤核验标签/OCI revision后，才能将`ghcr.io/qyxx2/mpd-server:sha-<交付完整提交SHA>`作为成功镜像交给用户；本段不预填CI成功。

**部署后短卡（替代Mock访问卡的入口）：** 访问该交付镜像的实际NAS Web地址，确认容器版本与交付SHA一致；iPad Safari浏览器栏存在时走“Player/歌词→Queue→Library搜索→Settings未保存输入→横竖往返”，手机纵屏导航/歌词/一次横竖往返。预期无双Player、背景连续、专辑及核心控制可见，搜索/当前表单草稿旋转保留，关闭键盘后输入和导航可达。只使用认可的测试队列，勿清空真实列表或保存临时MPD地址。独立PWA已有同版本可用环境则重复短流程；没有则继续标PWA PENDING。真实镜像没有“B5测试”夹具菜单，不要求人为制造异常。反馈Safari、手机、独立PWA各“通过/未测/问题”，异常附步骤或截图；尺寸仍免采。
