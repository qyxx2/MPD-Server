# 横屏布局 B3 — 右侧工作区、触摸与键盘验收

日期：2026-10-16，Asia/Shanghai。仅执行B3；**Implementation PASS；Automated PASS；Browser PASS（下列有限桌面样本及静态层级核验）；HUMAN PASS；PWA PENDING（B5责任）。B3 Gate PASS，满足进入B4的前置条件；本次未启动B4。**

## 基线与前置Gate

已读取本地AGENTS.override.md、现行文档索引、Batch计划、最新横屏设计、继承的全局UI合同及B0/B1/B2验收。执行前无B3验收记录。B0人工记录按用户既有授权豁免；B1/B2的最新用户确认均为HUMAN PASS，B2-R1确认“验收通过。”，因此允许进入B3。人工尺寸采集已由用户免除，不猜填设备数值；PWA仍归B5。

分支`fix/v0.2-execution-sample-reuse`，HEAD `6091d73dc35f756057ed37e65ea2a077a1acc34b`，与计划编写基线一致。当前工作区包含尚未提交的B1/B2成果，不能仅用HEAD识别访问版本。开始时13个tracked dirty文件及既存untracked源码/计划/设计/验收全部保留。未切分支、创建工作树、回退或覆盖。

继承源码指纹`ac38dc1c5119434e0fc493b794ef3a66f31f52c75d04de55f520b7af680d9a80`已核验与B2-R1一致；本批最终`web/src`指纹为 **`3bb0b192a8d0c3e7d8a655561f29f14f1b24163ead61e99c296db47c8a7e7ba8`**。算法：按完整路径排序web/src文件，逐一SHA256输入路径、NUL、文件字节。早期一次递归目录局部排序产生另一摘要，仅属工具算法差异，未作为版本依据。

## 改动与合同映射

| 合同/范围 | 本批实现或保留 | 证明 |
|---|---|---|
| WEB-LANDSCAPE-NAV-001 | 新增responsive-workspace.test.ts；搜索query/路由、设置host/五位端口草稿、DOM元素、焦点、滚动跨模式保留；不重建session/业务owner | 两项workspace行为测试、现有shell/navigation与Library回归；实际浏览器输入旋转 |
| WEB-LANDSCAPE-HEIGHT-001 | QueueView.vue仅新增共享layoutMode注入及同步watch；有捕获指针时模式变化调用既有cancelDrag，清除hold/RAF/捕获/浮层/未提交草稿；已提交操作仍由原task owner恢复 | queue-view新增旋转取消及右栏边缘滚动/移出取消测试；workspace测试pending→unknown→原key重试 |
| 工作区宽度/滚动/浮层 | 实查未发现必须修改的页面溢出，保留既有Lyrics/Settings限宽、Queue/Library右栏起点、横滑标签与菜单结构；未改CSS、纵屏几何或B2专辑行 | 真实IAB量测、菜单及子页检查；Library排序/收藏/歌单/搜索/Settings指定回归 |
| read-only | unknown/断线仍禁写；旋转和放弃未保存设置不发写请求 | workspace及既有settings/queue-actions测试 |

本批产品只改QueueView.vue的4行增量；测试新增responsive-workspace文件、queue-view两项测试。文档仅本验收及计划/设计的本批状态。既存performance验收、README、全局合同及B1/B2源码不属于本批新增改动。未实施B4状态功能或B5功能。

**根因及RED/GREEN：** Queue原来只在pointercancel、失去捕获、业务draft失效或卸载时取消拖动；布局切换保留Queue组件，缺少几何失效取消路径。新测试先证实旋转后ghost仍存在（expected false / received true），最小watch修复后原单项通过，再跑直接与指定回归。

**执行裁定：** 两项计划要求的workspace测试、右栏边缘滚动/无效落点测试初次即通过，属于继承合同的行为保护，不虚报RED或为制造失败改写正确实现。新增实现只对应确实失败的旋转拖动用例。设置取消沿用离页放弃未保存草稿，不新增接入设置功能或专用取消按钮；代价是仍没有表单内独立取消入口。整体几何与业务结构无需扩大范围或重开B1。

## 自动化、构建与环境

沿用Node v24.20.0、npm11.19.0及现有web/node_modules，无安装/更新依赖、锁文件或虚拟环境修改。纯前端任务未运行无关Python/Ruff/后端测试；未使用Docker、真实MPD或部署。

命令均在web/执行；完整日志在ignored的`.superpowers/sdd/2026-10-16-responsive-landscape-player-batch-plan/b3/`。

- 开始基线queue-view/settings/search：3文件、23 passed。
- workspace新增行为：2 passed，初次即通过。最初一次命令因工作目录误用未写入文件并报No test files found，纠正路径后执行；此为工具调用错误，不是代码RED。
- queue两新增用例初次：边缘滚动通过、旋转取消预期失败；修复后精确失败单项通过，随后直接两文件12 passed。
- **B3指定回归：12文件、105 passed、0 failed（12.84s）**：

```bash
npm test -- --run tests/invariants/responsive-workspace.test.ts tests/invariants/queue-view.test.ts tests/invariants/queue-actions.test.ts tests/invariants/queue-save.test.ts tests/invariants/library-collections.test.ts tests/invariants/library-sorting.test.ts tests/invariants/search.test.ts tests/invariants/favorites.test.ts tests/invariants/playlists.test.ts tests/invariants/settings.test.ts tests/invariants/player-library-navigation.test.ts tests/invariants/shell-navigation.test.ts
```

- `npm run typecheck` PASS；`npm run build` PASS（122 modules、3.25s）。CSS `index-CRR51YVN.css` SHA256 `7d0a186c5ce8ccd368869181d19308c36c8017021466196d83cdd43f8015939a`；JS `index-C_w4Xg6n.js` SHA256 `08ad4edd0169bb7804bbfd49aea9bb25444ce04c772fb496dda84e1ea70547a5`。浏览器使用dev源码；dist为ignored构建产物。
- 补充完整前端回归：**36文件、351 passed、0 failed（29.08s）**，不替代指定回归、不作为B5完成。
- 独立只读审查无Critical/Important。延期Minor：新增queue测试以Object.defineProperty设置document.elementFromPoint，现有vi.restoreAllMocks不会还原属性描述符，未来测试存在隔离隐患；本轮完整测试均通过，未扩大本批修复范围。审查未证明实机/浏览器交互，相关证据由本记录单独列明。

## 真实浏览器检查及边界

Linux Codex IAB，非目标iPad Safari、非独立PWA。使用本批隔离Vite 5176，挂真实AppShell/四页和现有store/API解码器，合成40条待播、50首Library歌曲、分类/歌单/搜索数据；夹具拒绝全部写请求且无后端代理。未联系8015或真实MPD。夹具初次启动遇EMFILE文件监听上限，仅为夹具启用polling后恢复，不改项目配置/依赖。

| 实际CSS inner | 核验结果 |
|---|---|
| 1194×834 | Player x101.61、宽400，右栏x543.41、宽549.46，gap41.80；AppBar约44px、Dock x437.24/y761.97；Queue滚动0→1668.97后这些几何不变 |
| 1024×768 | 四页Player x91.14、右栏x461.89、宽471.10，gap约35.84；Lyrics/Queue/Library/Settings切页边界一致，无document横向溢出 |
| 834×1194↔横屏 | Settings host及Search输入保留值与活动元素；离开设置再回来恢复mock地址，未提交修改 |
| 1024×430 | 继承B2可滚动单列退化；host/port可键盘Tab到达，port位于y180.59–224.59；不声称这是真实软键盘测量 |
| 390×844 | Queue菜单约272×261，x59.17/y291.40，无越界；AppBar y11.99/h43.39、导航约64px；标签条client343/scroll527，实际横滑scrollLeft0→183.45，document无横向溢出 |

全部Library现有子页已查看：默认歌曲、专辑/艺术家/风格/年代/标签列表及各自详情、收藏、歌单列表/详情、搜索；均无document横向溢出，1194样本Player与右栏左边界不变。空队列、空Library与空收藏检查；歌曲菜单、Queue菜单、保存歌单浮层均处于视口内。长中英/emoji菜单出现内部滚动而不推宽页面；正常歌曲菜单Escape关闭已检查。Settings滚至底部约184px、Library长列表滚至约2713px时左栏及AppBar/Dock均固定，纵向滚动所有者为shell-content。

层级以真实浏览器计算样式/CSSOM核验：AppBar stacking z20、固定drag ghost规则z10，通知详情属于AppBar层，位于拖动层之上；**未把此静态层级检查宣称为真实触摸拖动与通知并发实测**。触摸捕获、边缘手势、Safari软键盘避让仍由B3-H1承担，jsdom/缩小窗口不能替代。

浏览器控制曾连续超时，重置连接后重新完成普通菜单/空态/短高/搜索输入等检查；超时调用未返回的输入/旋转结果不纳入通过证据。旧连接已返回的全子页与Settings焦点量测仍保留；早期设置viewport参数与实际inner有缩放差异，记录按实际inner，恢复后1194/1024/390重新量测。退出前已恢复临时viewport并关闭临时tab。

证据目录：`b3/measurements.json`（恢复连接后的12组实测）、`queue1194.png`、`long-song-menu.png`、各测试日志、`serve.mjs`及`review.md`。部分前期量测和全子页输出记录在本会话及上文，不伪造遗失的JSON或截图。只读夹具未进入产品代码。

## B3-H1/H2 简短实机验收卡

**访问版本：** [B3隔离验收页](http://192.168.3.18:5176/?route=/queue)，标题`MPD-Server · LANDSCAPE B3 · 6091d73 · MOCK`；源码指纹`3bb0b192…e7ba8`。本机LAN HTTP 200；设备可达性需实际打开确认。5175是旧B2夹具，不作为本批版本标识。5176所有写操作被拒绝，不用于有效提交/播放测试；无需保存接入设置。用户不必采集CSS/DPR等数值。

1. **iPad Safari Queue：** 右栏手指滚动；长按待播条目右侧排序手柄，拖到上下边缘观察滚动，再移出列表到左侧Player后松手取消；另一次长按期间旋转。预期右栏独立滚动，取消/旋转后浮层消失，没有误播放或误提交，Player/Dock不遮挡。只测取消，不在只读夹具内有效落点提交。
2. **Library：** 点音乐库，横滑分类标签，打开搜索输入文字，保持输入时横竖往返、关闭软键盘。预期值与路由保留、输入可达、没有双重滚动或反复跳动；可打开一首歌曲菜单后关闭。长文本可选[长文本样本](http://192.168.3.18:5176/?route=/library/search%3Fq%3Ddraft&long=1)。
3. **Settings：** 输入临时host/port，旋转并关闭软键盘，查看输入及保存入口可达；**不点保存**，点音乐库离页放弃，再返回确认未保存。预期草稿旋转不丢，关闭键盘后恢复布局，离页取消不改变连接。
4. **手机纵屏：** 因修改共用Queue拖动组件，本批不能豁免手机；短查Queue滚动、长按后移出/取消、菜单关闭。预期无误播放/写入、浮层能关闭；无需重测Player/时钟/歌词全流程。

**反馈：** 回复“B3通过（iPad拖动取消/搜索/软键盘/设置旋转、手机Queue正常）”，或列明未测项目与异常；有异常可附截图。实际设备/浏览器版本未知则不猜填，尺寸仍免采。独立PWA留B5，当前PWA PENDING不单独阻塞B4，但B3 HUMAN PENDING必须先闭合。

## 收尾

已检查实际本批diff、新增测试、git diff --check/stat/status；仅上述产品/测试及本批文档为新改动，既存dirty保留。无依赖、环境、数据库、后端、Docker、真实MPD、提交、推送、PR或部署动作。本地5176夹具保留用于验收。

**自主实施与自动化完成；本批实机验收未完成。停在B3，收到本版本必要实机反馈之前不得进入B4。**


## B3 用户最终实机验收确认

用户对本批完整实机验收卡明确回复 **“通过”**。据此B3-H1（iPad Queue触摸滚动、拖动取消/旋转、Library搜索与软键盘、Settings输入旋转并离页取消）及B3-H2（手机Queue受影响交互）记为 **HUMAN PASS**。此最新确认覆盖上文实施阶段的HUMAN PENDING与不能进入B4结论；不补造设备版本、尺寸或截图，不扩展为PWA或有效写入提交的实机证据。

重新核对分支`fix/v0.2-execution-sample-reuse`、HEAD`6091d73dc35f756057ed37e65ea2a077a1acc34b`，当前源码指纹仍为`3bb0b192a8d0c3e7d8a655561f29f14f1b24163ead61e99c296db47c8a7e7ba8`，与交付版本一致。本轮只更新验收、计划、设计状态，复用同版本105项指定回归、351项完整回归、typecheck/build和已记录浏览器证据；未改产品或测试，未重复执行测试。

**结论：B3验收通过，满足进入B4的前置条件；不自动启动下一批。** PWA继续PENDING，归B5；既有延期Minor保持记录。未提交、推送、部署或改变环境。
