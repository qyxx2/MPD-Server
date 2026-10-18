# 横屏布局 B1 — 完整双栏骨架验收

> 2026-10-18 归档：历史方案/阶段验收，原文中的“当前”“待实施”及授权限制均指记录当时。现状与未闭合项见[现行文档索引](../../README.md)。

日期：2026-10-16（Asia/Shanghai）；本轮自动化/浏览器约16:54起。仅执行 B1。

**最新Gate：B1整体HUMAN PASS，允许执行B2。** 用户已确认实机测试通过，并取消本次及后续实际CSS尺寸测量要求，详见文末最新裁定。下文保留B1各阶段历史事实；未测数值不补造，PWA仍归B5待验。

## 授权与最新基线

- 分支 `fix/v0.2-execution-sample-reuse`，HEAD `6091d73dc35f756057ed37e65ea2a077a1acc34b`。以当前工作区执行；未切分支、回退、覆盖或创建工作树。
- 开始时已有四份 performance acceptance、`docs/superpowers/README.md`、全局视觉合同的 tracked dirty 修改，以及横屏计划、设计、B0记录等 untracked 文档。它们均保留；本次只增补指定横屏计划/设计及B1记录，并修改下表前端文件。HEAD相同不代表页面版本相同。
- 用户明确要求忽略B0人工验收记录问题、执行B1；此为本次前序Gate的人工豁免。B0仍保留真实的HUMAN PENDING，不伪造BASELINE READY。B1自身实机Gate未豁免。
- 最新要求已写入计划“2026-10-16 用户最新要求”和设计“用户实施修订”：iPad Pro 2025／11英寸、默认Safari、用户提供2420×1668；顶部栏存在，物理/CSS分辨率分记；桌面只扩外围背景；iPad/手机纵屏结构保持；Appbar最终新状态功能归B4，纵屏只改功能、不动大小/位置/图标及槽位。B1仅横屏44px高度预算，未提前做B4状态功能。

## 访问版本和前置

- **访问地址：[B1 Mock 页面](http://10.104.60.177:5174/)**，同一可达网络访问。页面标题 `MPD-Server · LANDSCAPE B1 · 6091d73 · MOCK · 2026-10-16`。这是本轮单独启动的本地Vite dev服务，代理已有127.0.0.1:8015 Mock，未启动真实MPD、Docker或部署。5173/5188旧标题页面不是本卡版本。
- 当前 `web/src` 指纹：`8e3e5490f572c62eb7db37d02c4d245e7ba05a3e4c58d9588085626f39898c8e`。算法为按路径排序的web/src文件，逐一SHA256输入“路径、NUL、文件字节”。后续源码变化必须重新标识，不能只按HEAD复用证据。
- 构建通过，但浏览器访问dev源码而非dist。构建CSS：`index-B4IpGaGs.css`，SHA256 `8ea76733e5e1467f4a5a44598c220479aa1787d5dec7f7f0af0402239bce6e35`；JS：`index-B7POPOtk.js`，SHA256 `01aa979ad62514842eda71d3d5e0f497810440b95e4a268fcf2579dbb7e62070`。dist保持ignored。
- Mock样本沿用B0：暂停的“归途／B04合成测试”、0:00/0:08、无封面占位、两行同步歌词、Queue5项含长中文/emoji、Library7首。只导航/滚动/切媒体；未播放、seek、拖动、收藏、保存或改变连接配置。Mock的stats/输出能力未验证提示如实保留。

## 合同到实现与证据

| 合同 | 本批实现 | 自动化/浏览器 |
|---|---|---|
| WEB-LANDSCAPE-001、NAV-001 | AppShell创建并注入唯一layoutMode，resize只改展示；PlayerView保持原路由。横屏PlayerPanel在路由区外常驻，PlayerLyrics绑定同一session；不另建事实/时钟/realtime/背景请求 | responsive-layout、shell-navigation、app-startup、realtime；四页切换、旋转 |
| NAV-001、原播放/资源合同 | PlayerPanel提取原信息、收藏、专辑/艺术家链接、控制和进度；异步艺术家读取增加路由身份约束，防止常驻后迟到读取拉走当前页 | player-controls、player-lyrics、player-library-navigation、global-artwork |
| GEOMETRY-001、HEIGHT-001 | app.css中唯一舞台预算；PlayerPanel量测实际信息区F，通过CSS剩余高度约束Player/封面同宽，缩小时重算组宽；正常双栏无左栏滚动；右栏单独滚动 | 浏览器实际P/A/F/G、控制/Dock边界，见下表 |
| HEIGHT-001、纵屏保护 | 只在landscape限定间距/单行高度；高度≤800px仅隐藏次要专辑行以容纳完整控制。纵屏原样式保留，新增结构包装display:contents；Appbar纵屏约43.4px与原位置保留 | 媒体回归、浏览器390×844及834×1194，原Appbar/导航边界 |
| NAV-001、STYLE-001 | Dock四项歌词/Queue/音乐库/设置，原href及子路由选中态不变；320×60px、viewport居中；全局背景不改owner/token | 所有Library子路由、返回、设置草稿旋转、四页几何 |
| 歌词合同 | LyricsStage新增可选showArtworkReturn，默认沿用已有返回入口；横屏右侧无返回封面，只有一份歌词。解析、选择、跟随、seek行为未改 | player-lyrics及responsive-layout；浏览器媒体往返 |

B2的极短高度/200%字体稳定退化、B3完整触摸/键盘、B4状态功能均未实施。不把普通B1高度预算修正扩大为未来批次。设置草稿同一路由旋转保留真实DOM和值，Library子路由保持音乐库选中。

## 自动化与环境

Node v24.20.0、npm11.19.0，使用已安装web/node_modules，无安装/版本/锁文件修改。Python仅用现有`.venv/bin/python`读取/编辑文档及指纹，版本3.14.4；本批纯前端，不运行无关后端/Python测试。

在web目录执行：

1. 基线6个文件（shell-navigation/player-lyrics/player-controls/global-artwork/appbar-activities/library-sorting）：**63 passed，0 failed**。
2. 新增responsive-layout最初**4 failed**，分别因横屏无常驻Player、旋转仍有封面返回入口、边界无横屏Player、Library无常驻Player，符合RED预期；实现后**4 passed**。
3. 首次B1回归**73 passed、6 failed**：5项旧媒体测试的jsdom隐含1024×768进入了新横屏模式；1项迟到艺术家读取在常驻后仍跳转。按systematic-debugging检查完整失败，tests/setup明确旧合同的390×844纵屏前提（响应式测试另行覆盖尺寸），生产读取增加路由身份约束；不削弱断言。原失败所属2文件复跑**19 passed**。
4. B1指定回归最终**8 files、79 passed、0 failed**，约8.11s：

```bash
npm test -- --run tests/invariants/responsive-layout.test.ts tests/invariants/shell-navigation.test.ts tests/invariants/app-startup.test.ts tests/invariants/realtime.test.ts tests/invariants/global-artwork.test.ts tests/invariants/player-controls.test.ts tests/invariants/player-lyrics.test.ts tests/invariants/player-library-navigation.test.ts
```

5. `npm run typecheck` **PASS**；`npm run build` **PASS**（122 modules，2.75s）。
6. `npm test -- --run` 完整前端补充验证 **34 files、341 passed、0 failed**（23.06s）；不替代上述指定回归，也不晋升B5。独立只读代码审查无Critical/Important发现；独立复跑responsive-layout及player-library-navigation为 **10/10通过**。测试空/错误资源只证明生命周期与导航，填充页面几何以浏览器及待验iPad为准。

`tests/support/shell.ts`新增统一resize辅助及session探针；新responsive-layout同时承担计划所列shell-navigation横屏扩展，不重复在旧文件复制相同用例。现有shell-navigation仍完整运行。测试setup视口变更属于本次响应式测试前置条件，不改业务断言。

## 浏览器结果（不能替代 iPad）

环境：Linux Codex IAB，实际浏览器版本/UA未从当前接口取得，不猜填；非Safari、非独立PWA。DPR≈1、visualViewport.scale=1；根字体16px。临时viewport override后的实际inner和visualViewport分开记录，以下整数为inner读数。浏览器有小数舍入（如1194×834对应visualViewport约1194.483×834.483），不是设备实测。目标iPad的CSS尺寸/浏览器栏/safe-area仍待实机提供。

| 实际inner（CSS） | 检查页面 | P=A | F | G | R / Lyrics、Settings实际Q | Player左边缘 | 控制底 / Dock顶 |
|---|---|---:|---:|---:|---|---:|---|
| 1194×834 | 四页、设置滚动 | 400 | 296.68 | 41.80 | 549.46 / 480 | 101.61 | 749.31 / 761.97 |
| 1024×768 | 四页 | 368.69 | 252.68 | 35.84 | 471.10 / 471.10 | 74.26 | 678.81 / 696.28 |
| 1920×1080 | 四页 | 400 | 296.68 | 48.00 | 560 / 480 | 约456 | 870.33 / 1004.01 |

- 上述四页换页时Player和右栏起点保持相同；窄Lyrics/Settings从右栏起点排布。桌面内容组仍约1008px、舞台≤1440px，多余宽度留外围；Appbar约44px，Dock320×60px且相对viewport居中。
- 1194设置页右栏scrollHeight≈882、clientHeight≈698；真实滚动至scrollTop≈184.14时Player/控制/Appbar/Dock坐标不变，只有右页位移。歌词由既有lyrics-content滚动，壳无第二条歌词滚动。
- 门槛实际899×701为单列，900×701和901×701为双栏；844×390为单列；均无document横向溢出。900/901缩小后的Player≈312px、可见gap24px，未留空的大左栏。高度差来自浏览器override舍入，如实记录。
- 390×844和834×1194保持单列，Appbar y≈11.994/h≈43.394，导航h≈63.998，shell限宽与既有合同一致。纵屏封面→歌词→横屏→竖屏恢复“显示封面”入口，未强制重写媒体选择。
- 浏览器四页、无封面、长列表标题、旋转和右侧滚动通过；未声称亮暗封面对比度、Safari顶部栏、触摸、软键盘、PWA或所有异常组合已验收。

证据目录（ignored，不提交）：`.superpowers/sdd/2026-10-16-responsive-landscape-player-batch-plan/b1/`，含measurements.json及1194四页/设置滚动、1024 Player、1920四页、390 Player、834旋转恢复截图。自动化日志在本机`/tmp/landscape-b1-*.log`，结束时汇总复制到该目录。

## B1-H1 简短 iPad 实机验收卡

**状态：HUMAN PENDING。** 使用上方5174 B1版本，iPad Pro2025／11英寸、默认Safari，正常缩放，顶部浏览器栏保持实际使用状态。无需播放、seek、保存配置或操作真实MPD；若地址不通，反馈可达性，不改用旧版本。

1. 横屏依次打开歌词、Queue、音乐库、设置。预期左Player常驻且足够大，左右靠近成组，换页位置不跳，背景连续，Dock在屏幕中央；控制完整且不被盖住。评价“整体比例/左右距离可接受或需改哪里”。
2. 在设置右侧向下滚动。预期只滚右页，Player、Appbar、Dock不动，底部信息可达；不要保存。
3. 返回Player后转竖屏，切封面/歌词，再横屏→竖屏。预期竖屏结构、Appbar大小位置与当前原版相同；恢复所选媒体，横屏右侧没有“返回封面”，URL不变。
4. 反馈横屏Player、横屏Queue、竖屏Player的**完整截图（含Safari栏）**，设备/iPadOS/Safari版本、缩放设置，以及是否遮挡/横溢出/滚动异常。能采集时补横竖innerWidth/innerHeight、visualViewport宽高/scale、DPR、safe-area；可复用B0卡的只读测量片段。不能采尺寸时如实说明，不猜算2420×1668为CSS。

B1-H2桌面由本轮真实IAB渲染与四页截图完成，仅证明桌面外围背景/内容组关系；不代替上述iPadH1。独立PWA目前无证据，列PWA PENDING，留后续指定批次，未授权安装/部署。

## 收尾与下一批

Implementation PASS；Automated PASS（指定回归）；Browser PASS（上述有限样本）；HUMAN PENDING；PWA PENDING。

未修改后端、依赖、虚拟环境、数据库、部署配置、原全局背景owner或播放事实/恢复合同。未提交、推送、PR、Docker、真实MPD、NAS操作。保留所有既存dirty文档。`git diff --check`通过；已检查tracked diff、全部新增前端源码与测试、stat/status，未见无关产品改动。开始时六份tracked文档的diff统计保持原样，横屏计划/设计是既存untracked文档的授权增补。独立审查无阻塞问题。

**进入B2条件：本轮横屏功能及R1视觉修订已获用户通过。竖屏/旋转与目标设备CSS尺寸记录尚未提供，不能把横屏截图或一句视觉通过写成这些项目已测；仍在B1补证，不自动开始B2。**


## 2026-10-16 晚间实机反馈及 B1-R1 视觉修订

用户提供原版本IMG_0031.PNG（设置、Safari工具栏展开）、IMG_0032.PNG（歌词、工具栏展开）、IMG_0033.PNG（歌词、工具栏收起），原图2420×1668；明确表示“功能本身没有问题”。这是有效的目标设备横屏人工反馈，补充了两种Safari栏状态的证据，不能将截图像素推算为CSS视口，也不冒充未提供的纵屏/PWA证据。原图复制至ignored的b1证据目录，保留原文件名。

用户只要求两处调整：增加封面/Dock圆角，歌词文字向右移约3–4个汉字。作为B1实机反馈闭环执行，未启动B2：

- PlayerPanel横屏封面圆角12→24px，横屏Dock圆角16→24px。
- LyricsStage仅`.lyrics-workspace`左padding从8px改为4em（默认字体64px），文字较原起点右移约56px。右栏容器、Player和Dock位置/尺寸均不移动；Queue、Library、Settings不跟随歌词文字右移。纵屏padding、封面/导航/Appbar几何仍为原值。
- 本轮为纯CSS修订，没有新增运行时行为，不添加class字符串伪布局测试；先记录真实浏览器修改前参数，再实施并重复量测。计划/设计已写入此最新要求，覆盖原较小圆角目标。

访问仍为 **http://192.168.3.18:5174/**，原B1标题；刷新页面加载R1源码。最新web/src指纹 **f4f23b4bd3d5e42689b6457819e40b73336b711dcc3e85219158ee5bb1a2d147**，替代上文初版指纹用于本次新增视觉效果。未重新部署/更换后端；原版本功能证据可复用，视觉部分以R1为准。

本轮fresh检查：直接影响responsive-layout/player-lyrics两文件 **17 passed**；typecheck PASS；build PASS（122 modules、2.09s）。B1规定8文件针对性回归 **79 passed、0 failed**。初版341项完整前端结果仅属于初版，不声称本次重跑全套。CSS `index-cx6O8-Cn.css` SHA256 `e2411fb30e97ae6de434e8751c0388ef113dba88613adc6fc2fc409a0883f481`，JS `index-kJ8j5PTh.js` SHA256 `7ca92bfe03e9e045042dd1bfef73c4cbe82e21fae5180d360b4d53e61f08152f`；浏览器仍使用dev源码。

真实IAB对比：1194×834时封面和Dock计算圆角均24px，歌词行左边界551.401→607.403（右移56.002px），Player左边界101.606、右栏左边界543.405、Dock x437.241/y761.972及宽高均与修改前一致。1024×768、900×701无横向溢出；834×1194纵屏封面仍17.6px圆角、导航无新增圆角、歌词左padding8px，Appbar y11.994/h43.394。证据：`feedback-r1-measurements.json`、`feedback-r1-1194.png`及本轮测试日志，同在ignored目录。

**最小复验卡：** 在同一iPad Safari刷新5174页面，横屏仅看封面/Dock圆角和歌词起点，工具栏展开/收起时各看一次；预期圆角更明显，歌词右移约3.5字，原功能与其它页结构不变。回复这两处是否合适即可，不要求重复已确认的全部功能。纵屏保护尚未收到实机反馈，可在方便时附一次竖屏Player确认；PWA仍PENDING。R1已获用户确认，剩余证据状态见下方最终记录。


## B1-R1 用户最终确认

用户在本会话对R1调整回复 **“可以通过”**。据此记录横屏封面/Dock圆角、歌词右移的实机验收 **HUMAN PASS**，复用此前“功能本身没有问题”和Safari工具栏展开/收起截图；不要求重复这部分测试。

确认版本：同一5174服务、web/src指纹`f4f23b4bd3d5e42689b6457819e40b73336b711dcc3e85219158ee5bb1a2d147`。本次仅更新验收/计划/设计状态，无源码改变，因此沿用该版本79项回归、typecheck/build和浏览器结果，不重复运行测试。

剩余事实：未收到竖屏/旋转实机记录及实际CSS/visualViewport尺寸，不将其标为已测；PWA仍PENDING（后续B5责任）。整体B1 Gate暂保留HUMAN PENDING，已通过的横屏功能与R1视觉项冻结。本次确认不作为自动执行下一Batch的请求，未开始B2、未提交或推送。


## B2开始前用户补验确认与尺寸要求撤销

用户本轮明确反馈：“通过了，你说的尺寸无法测量，后续也无需测量。我实机真人测试没问题就可以继续下一batch.”，随后明确“直接继续b2”。据此B1竖屏/旋转等剩余实机项按用户确认记HUMAN PASS；设备CSS/visualViewport/DPR/safe-area数值与额外尺寸采集不再是人工Gate要求，缺失数据不猜填，既有横屏截图不要求重复。此最新裁定覆盖上文HUMAN PENDING/不进入B2结论。确认源码仍为f4f23b4bd3d5e42689b6457819e40b73336b711dcc3e85219158ee5bb1a2d147。B1整体Gate PASS，允许执行B2；PWA PENDING不阻塞B2，仍归B5。用户对当前实机功能的确认不预先通过尚未实施的B2。
