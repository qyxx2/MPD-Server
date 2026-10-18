# Web/PWA 横屏布局 Batch Implementation Plan

> 2026-10-18 按用户要求归档：该计划/验收不再作为待执行事项。保留历史 PARTIAL/PENDING 等原始结果，不据此宣称验收通过；后续仅按新需求立项。现行入口见[文档索引](../../README.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 默认在当前会话顺序执行；本计划不要求并行代理。每次只执行用户指定的一批。

**Goal:** 先在实际 iPad 浏览器验证完整双栏框架，再完善 Player、右侧交互、状态提示，最后完成跨设备验收，避免局部完成后推翻整体。

**Architecture:** 保留唯一 AppShell、playerSession、realtime 和业务状态。先将现有 Player 展示提取为可组合组件，接入真实四页及完整高度预算，再在已确认的空间结构上逐批精修。尺寸、路由和状态合同以 Spec 为唯一来源，计划只分配执行及证据责任。

**Tech Stack:** Vue 3、TypeScript、Vue Router、Vite、Vitest；浏览器及实际 iPad/手机人工验证。

**Spec:** [横屏常驻播放器与右侧工作区](../../specs/2026-10-16-responsive-landscape-player-design.md)；继承[全局 UI 合同](../../specs/2026-10-03-web-pwa-visual-design.md)。

日期：2026-10-16。**B0人工记录按既有授权豁免；B1–B4必需实机Gate已获用户通过；2026-10-17 B5自主实施、自动化及限定真实浏览器验收完成，HUMAN/PWA PENDING，最终Gate未通过，停在B5。状态以对应acceptance为准。** 编写时分支 `fix/v0.2-execution-sample-reuse`、HEAD `6091d73`，有既存文档 dirty 修改；下次以用户给出的基线和届时实际工作区重新核验。

**2026-10-16 最新用户裁定（B2开始前）：** 用户确认“通过了”“实机真人测试没问题”，B1整体实机Gate据此HUMAN PASS；用户明确表示尺寸无法测量，后续无需测量。取消实际设备CSS/visualViewport/DPR/safe-area数值作为本次及后续人工验收的必需反馈，不补造数值。自主浏览器几何检查仍按各Batch执行，不能冒充实机数据。既有横屏功能/R1证据复用；继续B2，仍逐批等待各批实机确认，PWA责任归B5。此裁定覆盖下文旧的尺寸必填及B1待补证状态。

**B2实机反馈修正：** 用户反馈横屏封面过大、专辑名称不显示，要求立即修复。横屏专辑名称必须保留可见行，封面按包含专辑行的实际F让出高度；取消旧的≤800px/compact隐藏专辑规则，紧凑时仅允许隐藏格式/DAC等次要展示。其余整体布局、纵屏及原播放合同保持。

**B2最终验收：** 用户在B2-R1修复后明确回复“验收通过。”，B2 HUMAN/Gate PASS，满足B3前置条件；本次只更新记录，不自动实施B3。PWA仍归B5，人工尺寸采集继续免除。

## 2026-10-16 用户最新要求（优先于旧范围与 B0 记录）

**B1 iPad实机反馈修订（2026-10-16晚）：** 用户提供Safari工具栏展开/收起截图并确认功能无问题；本批只增大横屏封面圆角12→24px、Dock圆角16→24px，歌词文字起点较原版右移约3–4个汉字（默认字号下56px，横屏歌词左padding .5rem→4em）。此要求覆盖旧10–12px封面/16pxDock目标；只调整歌词内部留白，不移动Player、右栏容器、其它页面或Dock，不改纵屏。R1修订效果已获用户回复“可以通过”，横屏功能/视觉项HUMAN PASS；尚未提供竖屏/旋转及实际CSS尺寸记录，不虚报已测，整体B1补证状态见acceptance，不自动实施B2。


- 本项目几乎只为 **iPad Pro 2025／11 英寸、默认 Safari** 服务；用户提供设备分辨率 **2420×1668**。横竖屏均考虑 Safari 顶部浏览器栏，物理分辨率不等于 CSS viewport；实际 CSS/visualViewport、DPR、safe-area 由 B1 实机记录，禁止猜算。
- 其它桌面分辨率仅在此 iPad 内容组基础上扩大外围背景，不新增桌面专用结构、比例或控件适配；原多设备矩阵保留为有限的溢出/退化回归样本，不再是额外设备定制目标。B1 桌面检查只确认外围背景和已冻结内容组。
- iPad 竖屏维持当前纵屏结构，不重做；手机纵屏亦保护。**Appbar 必须实现新状态功能要求，但纵屏只改功能，不改大小、位置、几何槽位和控件尺度。** §6 中去除非状态文字、异常优先、忙碌、普通信息5秒消隐、统一详情和恢复行为归 B4；24px图标/44px栏预算仅用于横屏，纵屏保留现有图标与栏尺寸。B1 不提前实施 B4。
- 用户明确授权本次忽略 **B0 人工验收记录问题** 并执行 B1；B0 仍如实保留 HUMAN PENDING，不伪造 BASELINE READY。本次进入 B1 依据是此人工豁免，不再以 B0-H1 缺记录阻塞。B1 自身整体实机 Gate 仍须通过才能进入 B2，必要实机/PWA 不以自动化替代。
- 基线为当前最新分支工作区；留在当前分支，不创建工作树、不回退、不覆盖既存文档。只执行 B1，不自动提交/推送/部署或改变依赖、虚拟环境、Docker、真实 MPD。

## 全局约束

- 每次先核验分支、HEAD、dirty 内容及前序 Gate。用户提供的基线是核对依据，不是自动 checkout/reset/pull 的命令；不一致时先说明差异，再判断能否安全沿用当前最新成果，不能覆盖已有工作。
- 一次只执行一个 Batch。前序必需 HUMAN Gate 未通过时，不开始依赖它的下一批；可以完成当前批代码、自动化、浏览器检查和验收卡，随后明确等待用户实机反馈。
- 原有 API、播放事实、mutation owner/原 key、read-only、歌词行为和 Library 当前默认歌曲/排序保持；不新增依赖、不改后端、不重做纵屏。
- 尺寸按 Spec §3–4，横竖模式按 §2。主舞台1440px上限、常规Player340–400px、目标gap32–48px、AppBar约44px、Dock约60px、触摸目标至少44px；遇实际可用高度限制按Spec退化，不能隐藏核心控件凑数。
- **设备分辨率与CSS viewport分开记录。** Spec新增的2420×1668作为用户设备描述保留，不能假定它就是CSS视口，也不能擅自假定DPR或换算成1194×834。横竖屏均测量浏览器顶部栏存在时的实际宽高；动态视口已扣除的浏览器UI不要再扣一次，safe-area也只计一次。
- 本轮规格中的1194×834等表格是CSS计算样本；目标设备实测尺寸必须加入矩阵。PWA单独记录display-mode与可用高度，不能用Safari截图代替PWA证据。
- 本计划不授权自动提交、push、PR、部署或Docker操作。实机访问环境由现有可用地址承载；需要发布到NAS、安装PWA或改设备配置时，先给出具体必要动作并获得该动作授权，不把“验收”扩展为任意部署许可。
- 失败先读完整输出、辨别代码/测试/环境/数据根因，最小修复后重跑原失败项及相关回归；不得跳过、弱化断言或使用历史通过抵扣。

## Review Focus

| 易漏条件 | 归属及必须证明的行为 |
|---|---|
| 设备分辨率、浏览器栏与CSS尺寸混淆 | B0实测；B1真实高度预算，不能封面过小或Dock盖控件 |
| 同一路由旋转卸载子页导致草稿/歌词状态丢失 | B1断点切换及B3输入/滚动回归；不写mediaMode、不重建session |
| 短高、200%字号、键盘引发双栏/单列来回振荡 | B2稳定降级测试、B3键盘实机验证 |
| 异常被busy或最近5项裁剪遮住，轮询反复续期 | B4并发活动及fake timers测试；异常常驻、普通信息按真实变化计时 |
| 高度缩小封面后仍保留空左栏，窄右页再次居中 | B1/B2四页量测可见gap；换页Player位置稳定、额外宽度在外围 |

## 批次顺序与硬门槛

| Batch | 独立交付物 | 必需实机验证 | 允许进入下一批的条件 |
|---|---|---|---|
| B0 | 最新基线、设备尺寸、纵屏保护样本及测试基线 | 目标iPad一次基线采样；手机现状采样可复用同版本有效证据 | 原要求BASELINE READY；本次用户豁免人工记录阻塞，见最新要求；不伪造通过 |
| B1 | 可运行的完整双栏骨架：真实Player+四页、Dock、预算、背景 | **目标iPad横竖屏＋真实桌面浏览器整体确认** | 自动化/浏览器通过且用户确认整体关系 |
| B2 | Player尺寸、短高降级、封面/歌词媒体表现精修 | iPad当前浏览器高度下的Player和歌词；手机纵屏短回归 | B2自动化与HUMAN通过 |
| B3 | Queue/Library/Settings滚动、菜单、触摸和键盘适配 | iPad触摸/键盘/旋转；手机仅受影响交互 | B3自动化与HUMAN通过 |
| B4 | 共享AppBar优先级、5秒消隐及详情可达性 | iPad与手机各一轮短状态检查 | B4自动化与HUMAN通过 |
| B5 | 最终全量前端回归、跨视口及PWA验收记录 | iPad Safari＋独立PWA、桌面、手机综合短流程 | 所有必验项有当前版本有效证据 |

B1是防返工Gate：必须使用真实页面，不能用空占位块或概念图通过；必须已经有正确的AppBar/Dock占位、Player核心信息高度和右侧滚动接缝。允许局部装饰未精修，不允许把比例、常驻结构、控制遮挡留给B2解决。B2–B4不得擅自重排整体框架；如果必须修改整体，记录原因与影响，重开B1受影响的几何验收，而不是继续叠补丁。

## 文件与组件接缝

以下是基于当前代码的执行落点；执行时若文件已移动，先证明等价接缝并更新计划映射，不能仅按旧路径机械覆盖。

| 文件 | 批次/责任 |
|---|---|
| `web/src/components/layout/AppShell.vue`、`web/src/App.vue` | B1持久布局组合；沿用现有provide/session/slot职责 |
| 新建 `web/src/components/layout/layoutMode.ts` | B1统一响应式模式，B2扩展实际高度不足的退化 |
| 新建 `web/src/components/player/PlayerPanel.vue` | B1从PlayerView提取现有信息/控制/媒体展示，B2精修尺寸 |
| 新建 `web/src/components/player/PlayerLyrics.vue` | B1封装共享session到LyricsStage的现有绑定；横屏右侧与纵屏媒体区复用 |
| `web/src/views/PlayerView.vue` | B1保持 `/` 路由入口，按模式组合展示，不创建第二session |
| `web/src/components/player/LyricsStage.vue` | B1可隐藏返回封面入口；B2只调整容器适配，保护歌词交互 |
| `web/src/components/layout/BottomNavigation.vue` | B1响应式标签、Dock和选中态 |
| `web/src/styles/app.css`、`web/src/styles/tokens.css` | B1结构预算，B2/B3各自局部样式，B4状态尺寸 |
| `web/src/views/QueueView.vue`、`LibraryView.vue`、`CollectionView.vue`、`SearchView.vue`、`PlaylistView.vue`、`FavoritesView.vue`、`SettingsView.vue` | B3按实际溢出修改；不要求每个文件都变更 |
| `web/src/components/queue/QueueOccurrence.vue`、`web/src/components/library/LibraryTabs.vue`、`SongActionMenu.vue`、`web/src/components/settings/MPDConnectionPanel.vue` | B3必要的手势、浮层、横滑、输入适配 |
| `web/src/components/layout/AppBar.vue`、`web/src/components/player/PlaybackStatus.vue`、`web/src/stores/notices.ts` | B4状态展示；B1只设最终高度预算，不提前做计时 |
| `web/src/runtime/playerSession.ts`、`web/src/components/layout/AppBackground.vue`、`web/src/router/index.ts` | 主要是核验/回归入口；只有明确证明需要时才改动 |

B1组件接口约定：`PlayerPanel`接收 `presentation: 'portrait' | 'landscape'`，仍inject已有session；`PlayerLyrics`接收 `showArtworkReturn: boolean`，从同一session绑定资源scope/position/seek；`LyricsStage`新增同名可选prop、默认true，既有props/emits保持。`layoutMode.ts`提供唯一注入上下文 `layoutModeKey`，值含只读 `mode: Ref<'portrait' | 'landscape'>`；由AppShell创建及清理观察者，消费者不另建监听。B2的高度退化沿用此上下文，不再引入第二模式来源。

此处“portrait”表示单列展示，也包含窄横屏退化。具体内部函数可按项目习惯实现，组件接口变动必须同时核对所有消费者。模式切换不以给整个RouterView加mode key的方式重建页面；Player实体在横屏导航期间持续存在，纵横切换可重组展示但不得复制业务owner。

## 通用验证与验收记录

所有下列npm命令在 `web/` 目录执行；Git命令在仓库根目录执行。先核对现有Node/npm、已安装依赖与package scripts，不自动安装。单项测试先用 `npm test -- --run <文件> -t '<测试名>'`，再跑所属文件及批次回归列表。新行为测试先确认因预期行为缺失而失败，再实现并验证通过；纯CSS尺寸用真实浏览器测量，不写只检查class字符串的伪布局测试。

B1–B4每批必须运行 `npm run typecheck`、`npm run build`。B0只记录基线；B5统一完整 `npm test -- --run`、typecheck和build。不每批重复全套后端测试，不联系真实MPD来修单元测试；实机播放操作只能使用用户认可的测试队列，不能擅自清空真实列表或修改连接设置。

各批建立 `docs/superpowers/acceptance/2026-10-16-responsive-landscape-B<N>-acceptance.md`（N为0–5；执行时创建，不预填通过）。记录：

- 实际分支、HEAD、本批dirty范围、构建标识/访问URL、测试时间；HEAD相同但工作区不同必须区分。
- 合同ID→改动文件→自动化测试→浏览器/实机用例的对应关系。
- 命令、通过/失败数量、环境阻塞；浏览器几何实测；设备/系统/浏览器版本、DPR、`innerWidth/innerHeight`、`visualViewport`宽高/scale、safe-area、display-mode、浏览器栏状态。
- Implementation、Automated、Browser、HUMAN、PWA分别标记 `NOT RUN / PASS / FAIL / BLOCKED / PENDING`，不得用一个“完成”覆盖缺项。
- 每张实机卡写清访问版本、前置状态、3–6个操作、期望结果、需要截图/尺寸还是仅反馈。实机卡可在自动化结束后一次发给用户，避免每个CSS改动都要求重测。
- 失败反馈在本Batch闭环；同一版本且依赖未变的有效证据可以引用。后续修改了共享几何/样式/生命周期时，失效的前序证据必须补测。

无设备、无可访问构建或用户尚未反馈时，交付具体卡片并停在 `HUMAN PENDING`；不得以桌面模拟器替代iPad通过，也不要求无关的NAS音频性能/后端验收。

## B0 — 基线与实测，禁止改产品代码

**依赖：** 无。**产出：** 后续各批可复用的当前版本证据。

- [ ] 核对用户基线、Git状态、Spec最新修改和上述文件；列出现有功能/新需求差异及本轮保护范围。
- [ ] 运行基线：`npm test -- --run tests/invariants/shell-navigation.test.ts tests/invariants/player-lyrics.test.ts tests/invariants/player-controls.test.ts tests/invariants/global-artwork.test.ts tests/invariants/appbar-activities.test.ts tests/invariants/library-sorting.test.ts`，再运行typecheck/build；只记录既存失败，不借机修无关缺陷。
- [ ] 浏览器记录四页当前纵向结构、媒体切换、AppBar/导航尺寸，核对当前提供测试数据和访问版本的方法。
- [ ] **B0-H1 必需实机：** 用户的目标iPad在浏览器顶部栏存在时横/竖各采集一次CSS/visualViewport数据和完整页面截图；纵屏记录封面/歌词、Queue、Library、Settings基线。手机采集一组纵屏样本；已有可证实同版本样本可引用，免重复。
- [ ] 写B0验收记录，明确物理分辨率与CSS值，列出实际可用设备/PWA状态。只在数据和基线证据齐全后标记 `BASELINE READY`。

不要求实机播放/拖动/保存，不要求PWA全测或桌面全视口矩阵；本批目的仅为下一批提供真实尺寸与保护参照。缺测试依赖与缺实机证据分别记录。

## B1 — 一次接通完整布局，先确认整体

**依赖：** B0 READY，或本次用户明确的 B0 人工记录豁免（见上方最新要求）。**Files：** 文件表中的B1接缝；新增 `web/tests/invariants/responsive-layout.test.ts`，扩展 `web/tests/support/shell.ts`、`shell-navigation.test.ts`。**产出：** 可运行、可旋转、能浏览真实四页的完整框架。

- [x] 新增行为测试 `keeps one session across landscape routes`、`restores portrait media mode after rotation`、`uses one layout mode at the width boundary`：断言899/900/901及orientation映射一致，横屏各页只有一个Player，realtime只start一次、最终unmount只stop一次；旋转不发mutation、不改URL/mediaMode。
- [x] 运行上述单项，确认失败原因符合新增需求。提取PlayerPanel/PlayerLyrics并接入统一模式，不复制请求、操作和时钟；复用现有PlayerView信息/收藏/链接逻辑。
- [x] 实现完整舞台、宽度组、右侧限宽起点和高度预算、独立右侧滚动、横屏Dock及纵屏原导航。接入全部真实路由；横屏AppBar从此预留最终44px，Dock从此使用最终60px预算；纵屏Appbar大小与位置维持当前值。常规高度下Player控制完整，长右页滚动不推动左侧。
- [x] 增加路由测试 `keeps player geometry ownership across library children`：全部现有Library子路由选中音乐库，前进后退不重建shell，横屏 `/` 只挂一份LyricsStage且无返回封面入口。同一路由改变模式不清空现有表单/筛选状态；复杂触摸留B3。
- [x] 回归：`npm test -- --run tests/invariants/responsive-layout.test.ts tests/invariants/shell-navigation.test.ts tests/invariants/app-startup.test.ts tests/invariants/realtime.test.ts tests/invariants/global-artwork.test.ts tests/invariants/player-controls.test.ts tests/invariants/player-lyrics.test.ts tests/invariants/player-library-navigation.test.ts`；typecheck/build。
- [x] 真实浏览器测目标iPad的CSS尺寸及1194×834、1024×768、1920×1080；四页切换记录Player/右页边界、gap、AppBar/Dock边界及滚动所有者。899/900/901和844×390检查无横向溢出；此时无需精修所有极端高度。 **自主浏览器样本已完成；目标iPad实际CSS尺寸按最新用户裁定免采，不猜填。**
- [x] **B1-H1 必需iPad整体Gate：** 浏览器栏保持实际使用状态，依次查看四页、滚右侧长页、横竖旋转；确认Player足够大、左右靠近且整体内收、Dock居中、核心控制未遮挡，纵屏与B0一致。需用户明确评价整体比例及距离，至少保留横屏 `/`、Queue、纵屏Player截图。
- [x] **B1-H2 必需桌面整体Gate：** 1920×1080附近实际窗口查看四页；确认超出内容宽度的空间在外围、没有巨大中央空洞。可由执行者在真实桌面浏览器完成并给出截图，不强求用户重复点测。

**Gate：** 两个整体Gate与自动化通过才进入B2。只冻结空间骨架；封面圆角、局部密度、短高和状态动画仍可后续完善。明显比例错误必须本批修正，不以“后面精修”通过。


## B2 — Player、歌词与高度精修

**依赖：** B1整体确认。**Files：** PlayerPanel/PlayerLyrics、LyricsStage、layoutMode、局部样式tokens；新增 `web/tests/invariants/responsive-player.test.ts`。**产出：** 在已确认结构上满足真实高度、长文本与短屏要求。

- [x] 新增 `keeps core controls reachable in compact mode`、`does not oscillate when height is insufficient`、`preserves media choice and seek locks`：用可控尺寸/事件测试模式稳定、核心内容存在、listener清理、mediaMode与pending/unknown锁保持；CSS是否真可达交给浏览器量测。
- [x] 先确认失败再实现Spec高度算法：量测/预算实际F，逐级收紧封面和次要信息，必要时单列退化；保持基本字号和触摸范围，缩小Player后重新计算组关系。封面1:1及微圆角、长文本省略/完整信息可访问性在本批收口。
- [x] 歌词使用原position/seek/资源scope绑定，保护3秒恢复跟随、选择/拖动不误seek；横屏隐藏返回封面、纵屏保留。无封面、空歌词、迟到资源仍使用现有语义。
- [x] 回归：`npm test -- --run tests/invariants/responsive-player.test.ts tests/invariants/responsive-layout.test.ts tests/invariants/player-controls.test.ts tests/invariants/player-seek.test.ts tests/invariants/player-clock.test.ts tests/invariants/player-lyrics.test.ts tests/invariants/player-output.test.ts tests/invariants/mutation.test.ts tests/invariants/global-artwork.test.ts`；typecheck/build。
- [x] 浏览器检查Spec的三个iPad样本、932×430、1024×600、200%字号、长中英文/emoji/缺字段。记录实际A/F/gap及退化条件；无背景支持/reduced-motion、亮暗封面对比度同时核验，必要的背景token改动仅限Spec范围。
- [x] **B2-H1 必需实机：** iPad实际顶部栏状态下看长标题、封面、歌词；触摸歌词滚动/选择并等待恢复跟随，使用认可测试内容验证一次seek/播放控制。旋转后媒体选择及布局稳定；手机纵屏短查Player大小、控制和媒体切换。无法安全使用真实播放时先交付布局证据，相关操作明确待验，不能伪造已验证。

**Gate：** 实测几何与交互通过。无需重新逐页测试Library/Settings，也不要求后端性能采样。若核心Player仍需重新设计舞台，回到B1受影响Gate。

## B3 — 右侧页面、触摸、浮层与键盘

**依赖：** B2通过。**Files：** 文件表中的B3接缝及相关现有测试；新增 `web/tests/invariants/responsive-workspace.test.ts`。**产出：** 四页及子页适配已确认的右侧区域。

- [x] 新增 `preserves drafts and route when layout changes`、`keeps pending ownership across workspace navigation`：在搜索/设置输入中切换模式，保留现有草稿/路由；已有pending操作跨页仍由原owner恢复。先确认新增行为的失败再实现最小适配。
- [x] 校准Lyrics/Settings较窄内容及Queue/Library宽度，保持统一右侧起点。只修实际溢出的页面和浮层，不重构业务组件；标签横滑、Queue拖动滚动、菜单层级、输入焦点及键盘避让形成完整可用链路。
- [x] 扩展现有Queue测试覆盖右侧边缘滚动与无效落点取消；Library默认歌曲/排序和子路由回归；设置输入在布局切换后值不丢、未知/断线禁写。手势几何由实机证明，不把jsdom通过当成手势通过。
- [x] 回归：`npm test -- --run tests/invariants/responsive-workspace.test.ts tests/invariants/queue-view.test.ts tests/invariants/queue-actions.test.ts tests/invariants/queue-save.test.ts tests/invariants/library-collections.test.ts tests/invariants/library-sorting.test.ts tests/invariants/search.test.ts tests/invariants/favorites.test.ts tests/invariants/playlists.test.ts tests/invariants/settings.test.ts tests/invariants/player-library-navigation.test.ts tests/invariants/shell-navigation.test.ts`；typecheck/build。
- [x] 浏览器检查所有Library子页、长列表/空列表、菜单和详情不越界、通知覆盖拖动层，换页Player位置不动。
- [x] **B3-H1 必需iPad：** 右侧Queue触摸滚动、长按拖动到边缘并取消（有效提交仅用认可测试队列）；Library标签横滑/搜索输入；Settings输入后旋转并关闭键盘，取消而不保存连接配置。验证无双重滚动、输入/取消可达、Player/Dock不遮挡。
- [x] **B3-H2 条件手机回归：** 若修改共用菜单/输入/拖动组件，手机纵屏复验对应动作；只改横屏样式且已有浏览器证据证明隔离时可省，验收记录写明理由。

**本次执行说明：** 两项workspace行为初次即GREEN，未为制造失败改写既有合同；Queue旋转取消为实际RED→GREEN修复。其余页面未发现需改CSS的溢出；通知/拖动层以实际CSSOM静态核验，实机并发手势不冒充通过。105项指定回归、351项补充完整回归、typecheck/build通过。详见[B3验收](2026-10-16-responsive-landscape-B3-acceptance.md)。用户对完整实机卡回复“通过”，H1/H2及软键盘HUMAN PASS；B3 Gate PASS，满足B4前置条件，本次不自动启动B4。

**Gate：** 必需触摸/键盘项通过。无需重做播放时钟、DAC事实、背景全部实机测试；相关自动化仍按本批影响执行。

## B4 — 共享AppBar与状态完成

**依赖：** B3通过。**Files：** AppBar、PlaybackStatus、notices及必要局部tokens；扩展 `appbar-activities.test.ts`、`global-notices.test.ts`、`player-notices.test.ts`。**产出：** 横竖屏统一最终状态入口，不改变B1已冻结的高度。

- [x] fake timers新增 `expires information after five seconds without polling renewal`：4999ms仍可见、5000ms消隐；同id同状态轮询不续期、真实状态变化重新计时；切页/旋转不续期、unmount无残留timer。
- [x] 新增 `warnings outrank concurrent busy outside recent five`、`expiry preserves details focus and recovery`：异常优先于spinner；未解决项被最近5项裁剪仍汇总；高优先级期间普通信息继续过期；已打开详情/入口焦点按Spec例外保留；read/retry和活动历史不被消隐删除。
- [x] 确认上述测试预期失败后，最小实现共享显示计时和图形优先级，移除MPD SERVER并实现状态功能；横屏使用24px可见图标和44px目标，纵屏维持已有图标/栏/槽位大小位置；保留最近5项、统一浮层、原有业务状态类型与恢复行为。计时只控制展示，不改变Notice业务完成事实。
- [x] 回归：`npm test -- --run tests/invariants/appbar-activities.test.ts tests/invariants/global-notices.test.ts tests/invariants/player-notices.test.ts tests/invariants/mutation.test.ts tests/invariants/shell-navigation.test.ts tests/invariants/responsive-layout.test.ts`；typecheck/build。
- [x] 浏览器检查普通信息→消隐、异常+busy、打开详情超5秒、Escape/焦点返回、reduced-motion及屏幕阅读器可访问名称；确定AppBar/Dock位置不动。难以安全触发的异常使用测试夹具，不人为破坏MPD服务。
- [x] **B4-H1 必需短实机：** iPad和手机各确认状态入口可触摸、普通信息约5秒消隐、详情不被强关、不遮挡操作、AppBar够低。并发/精确时间边界由自动化承担，不要求用户手动构造所有组合；已有测试环境能安全提供异常时检查警告可辨认。

**本次执行状态：** B4实施、83项指定及受影响回归、359项完整前端回归、typecheck/build及有限IAB检查完成；详见[B4验收](2026-10-16-responsive-landscape-B4-acceptance.md)。2026-10-17用户回复“可以验收”，HUMAN/Gate PASS，满足B5前置条件，本次不自动启动B5。PWA归B5；reduced-motion仅CSSOM静态核验，不冒充实机/媒体偏好测试。

**Gate：** 共享AppBar两端实机及自动化通过。无需重测Library全部功能或完整播放链。

## B5 — 集成验收与交付

**依赖：** B1–B4全部必需Gate通过。**Files：** 主要为本批验收记录；只允许修复本增量造成的明确缺陷，修复后回归所属Batch，不增加功能。

- [x] 核对Spec §1–8覆盖及前序证据版本，运行完整 `npm test -- --run`、`npm run typecheck`、`npm run build`，记录真实结果。
- [x] 在真实浏览器完成Spec全部CSS视口矩阵，包括2560×1440和899/900/901、手机短高与200%缩放；加上B0记录的目标设备CSS尺寸。每种主要视口查看四页，实际量测几何/滚动；既有同版本有效证据可引用，不为截图重复实施。**本轮边界/1366以真实浏览器精确子视口补证，200%为字号；实际设备尺寸按最新用户裁定免采，原生zoom/Safari/PWA不冒充已测，见验收限制。**
- [ ] **B5-H1 必需最终iPad：** Safari保留浏览器栏及独立PWA各跑一次“Player/歌词→Queue→Library搜索或详情→Settings→旋转恢复”短流程；检查布局连续、无双份播放器、背景连续、输入和Dock可达。PWA没有已安装可用环境时列为PWA PENDING，不能宣称全部完成。
- [ ] **B5-H2 必需桌面/手机：** 桌面实际宽窗口四页快速核验；手机纵屏Player/导航/状态及一次横屏往返。复用前序已通过细项，仅确认最终集成没有回退；发生共享布局改动时重测对应细项。
- [x] 检查亮/暗/杂乱封面对比度、无图/错误、pending/unknown、通知展开及快速旋转证据覆盖；危险异常只用夹具/已有安全环境，不要求重做NAS播放性能或设备输出测试。
- [x] 核验 `git diff --check`、`git diff --stat`、`git status --short`及实际diff。汇总产品实现、自动化、环境、浏览器、HUMAN、PWA状态；给出未通过/未执行清单和最终基线，不自动提交。

**本次执行状态（2026-10-17）：** 仅修复B1分数CSS视口被innerWidth取整后过早进入双栏的问题；新增测试RED→GREEN、所属文件5项、B1指定及受影响回归86项、最终完整前端360项、typecheck/build通过。主窗口矩阵及精确CSS子视口四页检查完成；不改变CSS/已确认整体几何。详见[B5验收及最终实机卡](2026-10-16-responsive-landscape-B5-acceptance.md)。源码指纹`545bb108…a765106`，H1/H2最终Safari/桌面/手机及独立PWA反馈仍待；没有可用PWA环境时保持PWA PENDING，不新增安装/部署/manifest功能。**实施完成，最终验收未完成，停在B5。**

**完成标准：** 所有Spec要求可追溯到实现与证据；必需实机项没有悬空。只有代码/自动化完成但HUMAN/PWA待验时，明确交付“实施完成，验收未完成”。

## 单批执行提示词模板

下列模板只有两个替换字段；基线建议写“分支@完整SHA + 必须保留的未提交改动”，不要只写一个可能移动的分支名。B0第一次执行，后续按顺序使用B1–B5；验收未通过时仍指定同一Batch处理反馈。

```text
请按以下计划执行一个Batch：
docs/superpowers/plans/2026-10-16-responsive-landscape-player-batch-plan.md

核对基线：{{基线}}
本次Batch：{{Batch}}

先读取本地AGENTS指令、现行文档索引、上述计划、其引用的最新设计规格，以及前序和本Batch已有验收记录。核对当前分支、HEAD、dirty内容和真实代码；以当前最新工作区为准，给出的基线仅用于核验，不自动切分支、回退或覆盖已有修改。如不一致，说明具体差异及影响；不能安全继续时再提出所缺信息。

本次仅执行指定Batch，不跨批，不顺带实施后续功能。按计划顺序先建立对应测试/证据，再最小实现、针对性回归、浏览器检查并写本Batch acceptance文档。按当前仓库实际工具执行；不新增依赖、不改虚拟环境、不擅自启动Docker或联系真实MPD。

必要的实机测试不能省略，也不能用自动化或模拟截图代替；完成本批可自主完成的工作后，给我具体、简短的实机验收卡，说明访问版本、步骤、预期结果及需要反馈的证据。已有同版本有效证据可按计划复用，不重复无关测试。实机反馈缺失时标为HUMAN/PWA PENDING并停在本批；前序硬Gate未通过不得开始依赖它的后续Batch。

保护已确认的整体布局，只有本批明确授权的范围可以修改；发现需要推翻框架或扩大业务范围时报告依据，不自行扩展。不要自动提交、push、创建PR或部署。

结束时分别报告：本批改动、自动化结果、浏览器结果、实机/用户侧待验项、验收文档路径，以及是否满足进入下一批的条件。
```
