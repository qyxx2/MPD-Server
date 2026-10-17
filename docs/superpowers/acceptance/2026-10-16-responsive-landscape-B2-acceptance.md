# 横屏布局 B2 — Player、歌词与高度精修验收

日期：2026-10-16（Asia/Shanghai）。仅执行 B2。

**最新状态：Implementation PASS；Automated PASS；Browser PASS（下述有限样本）；HUMAN PASS。B2 Gate PASS，满足进入B3的前置条件；本次仅记录验收通过，未启动B3。PWA PENDING（B5责任，不阻塞B3）。**

最新修订为文末 **B2-R1专辑名称恢复**；当前源码指纹为`ac38dc1c5119434e0fc493b794ef3a66f31f52c75d04de55f520b7af680d9a80`。下文初版几何/测试记录按版本保留。

## 前置 Gate 与基线

本轮先读本地 `AGENTS.override.md`、现行索引、Batch计划、最新横屏设计、继承的全局UI合同、B0/B1及原B2前置核验记录，核对真实源码和Git状态。

原B2记录因B1 HUMAN PENDING而停止。随后用户明确反馈：“通过了，你说的尺寸无法测量，后续也无需测量。我实机真人测试没问题就可以继续下一batch.”，并再次要求“直接继续b2”。据此B1整体Gate HUMAN PASS，取消本次及后续人工CSS/visualViewport/DPR/safe-area数值采集要求；不补造设备数值、不要求重复已通过的横屏功能/R1测试。此裁定已写入计划、设计及B1记录，覆盖旧的尺寸必填/前置阻塞文字；不预先通过尚未实施的B2。

- 分支 `fix/v0.2-execution-sample-reuse`，HEAD `6091d73dc35f756057ed37e65ea2a077a1acc34b`；与计划一致，未切分支、回退、覆盖或创建工作树。
- B2开始源码指纹 `f4f23b4bd3d5e42689b6457819e40b73336b711dcc3e85219158ee5bb1a2d147`，与已确认B1-R1一致。最终 `web/src` 指纹 **`b560523cd9cf6dfdab01d1b7b3d1536c24172d8bacf33546869ac5deed0c8f0d`**。算法同B1：按路径排序web/src文件，逐一SHA256输入路径、NUL、文件字节；HEAD不能单独标识未提交源码。
- 开始时13个tracked dirty文件：四份performance验收、索引、全局UI合同及7个B1前端/测试文件；另有既存untracked横屏计划、设计、验收、layoutMode、PlayerPanel、PlayerLyrics、responsive-layout测试。全部保留，未提交。原tracked统计589 insertions / 130 deletions，本轮后599 / 130；untracked源码与文档另外逐项检查。

## 本批改动与合同

| 文件/范围 | 最小实现与边界 |
|---|---|
| `web/src/components/layout/layoutMode.ts` | 保留900px/横屏能力门槛；读取独立于布局模式的CSS舞台高度及rem探针，接收真实F与核心控制最小宽度。先紧凑、再缩封面，仍放不下则回可滚动单列；缓存紧凑量测跨Player卸载保留，恢复留16px余量，避免振荡。清理ResizeObserver、window/visualViewport监听 |
| `web/src/components/layout/AppShell.vue` | 加不可见且不参与布局的容量探针，转发信息区量测；唯一session、realtime、背景及业务owner不变 |
| `web/src/components/player/PlayerPanel.vue` | 同一次ResizeObserver量测实际信息高度与按钮自然总宽；横屏长格式单行省略，艺术家行随字体保持可用高度。标题可点开原生details查看完整歌曲/艺术家/专辑/格式/DAC信息，支持关闭/Escape及焦点返回；不改变正常标题尺寸，不改纵屏标题 |
| `web/src/styles/app.css` | compact仅隐藏专辑/格式/DAC次要展示并收紧间隙，完整内容仍在信息层；核心进度、时间、艺术家、收藏及控制保留。横屏或因容量退化的单列中，按钮不压缩/断行，主按钮按至少64px/4rem容纳200%字号。原手机纵屏几何不改 |
| `web/tests/invariants/responsive-player.test.ts` | 6项真实shell/session行为测试：紧凑核心内容、稳定退化/恢复与监听清理、放大控件宽度不足退化、媒体选择与pending seek锁、完整长文本信息、unknown操作跨退化保持锁定 |
| 文档 | 仅本计划/横屏设计、B1用户确认闭环及本B2验收；未修改其它既存dirty文档 |

B1确认的封面/Dock **24px圆角**、歌词 **4em左留白**、整体组关系与单session继续保留，未机械回退旧小圆角目标。未改LyricsStage/PlayerLyrics解析、资源scope、选择、seek、3秒跟随或时钟；这些现有行为通过回归验证。B3右侧页面/键盘业务适配、B4状态功能、B5集成未实施。

退化裁定：Player与封面保持同宽；最小可用宽度还须容纳核心控制，不能只按64px封面下限维持过窄双栏。临界短高/大字号可能较早进入可滚动单列，代价是失去双栏；符合Spec可达性例外，不留下空大左栏、不裁切核心操作。正常iPad空间骨架无需重开B1几何Gate。

## 自动化与环境

Node v24.20.0、npm11.19.0，沿用既有web/node_modules；无安装、依赖/锁文件、虚拟环境变更。纯前端任务未运行无关Python/Ruff/后端测试，未使用系统Python或修改`.venv`。

在 `web/` 执行，日志位于ignored的本计划`b2/`证据目录：

1. 新增3项模式行为测试最初 **3 failed**，原因是compact/容量退化不存在；最小实现后通过。追加完整身份信息与放大控制宽度用例，各先确认对应缺失失败，再实现并通过。unknown锁用例是对继承合同的补充保护，首次即通过，不虚报RED。
2. 初次实现集成1项失败，根因是测试ResizeObserver替身没有模拟样式改变后的下一帧量测；补齐通知帧，不削弱断言。首次typecheck发现测试在`get()`返回值调用被类型排除的`exists()`，改用`find()`后通过。
3. **B2指定针对性回归：9 files、97 passed、0 failed**（23.27s）：

```bash
npm test -- --run tests/invariants/responsive-player.test.ts tests/invariants/responsive-layout.test.ts tests/invariants/player-controls.test.ts tests/invariants/player-seek.test.ts tests/invariants/player-clock.test.ts tests/invariants/player-lyrics.test.ts tests/invariants/player-output.test.ts tests/invariants/mutation.test.ts tests/invariants/global-artwork.test.ts
```

4. 最终 `npm run typecheck` **PASS**；`npm run build` **PASS**（122 modules，6.72s）。CSS `index-Cz4lCFn6.css` SHA256 `3089247ef67412b55b096548c63da8e7979a5ec8c309fce6d7598e5731c9aeaa`；JS `index-CrZgChyF.js` SHA256 `a5baf84e6722a288cc8f43b5936037e623952adeb5d030e0f81f492703f28df1`。dist保持ignored；浏览器使用dev源码。
5. 最终完整前端补充回归 `npm test -- --run`：**35 files、347 passed、0 failed**（43.51s），不替代指定回归，不晋升B5。
6. 按executing-plans/requesting-code-review进行了独立只读审查，**无Critical/Important/Minor发现**；独立复跑当时responsive-player+responsive-layout **9 passed**。之后仅追加unknown锁保护测试，无产品改动。无延期Minor或未处理审查发现。

## 真实浏览器检查

Linux Codex IAB，非目标Safari、非独立PWA。下列为实际浏览器CSS inner读数，非实机数值；虚拟视口有小数舍入。默认根字号16px；另以临时夹具将字号设32px，验证200%字体，不声称等同Safari页面缩放。

| 实际inner | 模式 | A=P | F | 可见gap | 控制底 / Dock顶 |
|---|---|---:|---:|---:|---:|
| 1194×834 | 正常双栏 | 400.00 | 296.68 | 41.80 | 749.31 / 761.97 |
| 1024×768 | 正常双栏 | 368.69 | 252.68 | 35.84 | 678.81 / 696.28 |
| 1366×1024 | 正常双栏 | 400.00 | 296.68 | 47.81 | 842.72 / 948.78 |
| 1024×600 | 紧凑双栏 | 243.89 | 220.11 | 35.84 | 515.99 / 528.01 |
| 932×430 | 单列退化 | 原单列媒体约64 | 不套用双栏F | 不适用 | 滚到底366.20 / 366.35 |
| 1194×834、32px字体 | 单列退化 | 原单列媒体约128 | 不套用双栏F | 不适用 | 滚到底706.93 / 706.49（小数舍入＜1px） |

- 表中均无document横向溢出。932×430单列内容滚动约137.24px后完整控制可达；200%字号单列滚动约253.10px后完整控制可达，主按钮约128×128px。正常iPad与B1-R1的Player左边缘、封面、gap和Dock几何一致；短高缩小Player后重新居中整个组。
- 长中英文连续串/emoji、超长艺术家/专辑不推挤框架，标题省略；点开完整信息层后正文可换行/滚动，关闭恢复标题入口焦点，不触发播放。1194样本信息层约448×607px，位于视口内。
- 亮白/纯黑测试封面、无图、缺标题/艺术家/专辑/歌词均检查：缺标题沿原语义显示file URI，空歌词保持空资源语义。亮图背景仍是同一0.8蒙版，未增加页级背景或改token。最亮白底按现有蒙版保守计算，主/次/muted/accent文字对比度约10.06/6.51/4.68/6.60，满足普通文字4.5阈值；暗图更高。
- 无背景/无backdrop效果及reduced-motion样式以临时夹具强制关闭效果检查，保持可读；这不是原生不支持filter的浏览器或OS reduced-motion设置实测。实际reduced-motion行为分支、3秒边界与卸载清理由现有player-lyrics自动化承担，不冒充实机证据。
- 60行歌词真实手动滚动：当前行37，scrollTop约1457.24→622.76，约3秒后回1457.24；进度始终37。真实拖选得到“第32行 中文 English 🎵”，无新活动/seek预览，进度保持37。精确计时及gesture/selection禁止seek由回归测试覆盖。
- 390×844纵屏AppBar y11.994/h43.394、原导航高约64px保持；封面→歌词→横屏→纵屏后恢复媒体选择和“显示封面”入口，仅一份Player/Lyrics。932短高与200%退化后可恢复双栏，不重建session。
- 浏览器首轮发现Vue scoped `:global`写法把compact选择器编译成整个shell的`display:none`；检查实际生成CSS定位后将依赖shell的规则放回app.css，完整重测上述矩阵。夹具最初以非法null标题导致wire拒绝，修正为合法空字符串后重测；没有为夹具错误修改业务decoder。

证据：`.superpowers/sdd/2026-10-16-responsive-landscape-player-batch-plan/b2/`（ignored）中的measurements.json、各视口截图、long-identity.png、font200-controls.png、lyrics-selection.png及测试日志。临时只读夹具、亮暗SVG和字号/效果开关仅在此目录的serve.mjs中，不进入产品；没有用模拟图冒充浏览器渲染或实机截图。

## B2-H1 简短实机验收卡

**访问版本：** [B2当前页面](http://192.168.3.18:5175/)，标题 `MPD-Server · LANDSCAPE B2 · 6091d73 · MOCK`，最终源码指纹见上。新启动的本地Vite dev 5175读取当前源码，代理已存在且已核对注入MockMPD的8015；未部署、未联系真实MPD。LAN地址本机HTTP 200，设备可达性需实际打开确认；5174旧B1标题不作为本卡标识。

1. iPad Safari按日常工具栏状态使用Player；看封面、控制是否完整，横竖往返一次，确认布局稳定、原媒体选择可恢复。点标题可查看/关闭完整歌曲信息。预期已确认整体关系不变，没有控制遮挡或反复跳动。
2. [长标题/长歌词只读样本](http://192.168.3.18:5175/?fixture=1&cover=light)：横屏看长标题，点开完整信息，手指滚歌词并松开，等待约3秒恢复跟随；长按选择文字不应seek。此样本拒绝写操作，不用它测试播放/seek。可选[200%字号样本](http://192.168.3.18:5175/?fixture=1&cover=light&font=200)检查单列时控制能滚动到达，不要求调整设备设置。
3. 回到普通5175根页面，仅在显示B04合成测试/Mock MPD内容时，用该认可Mock内容验证一次播放/暂停和歌词点击seek；预期进度与控制正常、一次操作不重复提交。若无法安全操作或页面内容不符，直接反馈该项未验，不操作真实MPD。
4. 手机纵屏短查Player封面/控制大小和封面↔歌词切换保持原样。

**所需反馈：** 简单回复“B2通过（iPad布局/歌词/播放seek、手机纵屏均正常）”，或指出未测项目/具体异常即可；可附异常截图帮助定位。**不再要求任何CSS尺寸、DPR或safe-area采集。** 不能用本次用户对B1的通过代替这些B2新增项。独立PWA继续PENDING，归B5，无需此时安装或重复全页测试。

## 收尾与下一批

已检查实际源码/测试、diff/stat/status及新增文件；`git diff --check`通过。既存四份performance文档、索引、全局合同及非本批B1代码保留；无无关后端、依赖、数据库、环境或生成文件改动。未提交、推送、PR、Docker、真实MPD或部署。保留ignored证据供本批实机反馈复用。

B2实施/自动化/有限浏览器检查完成，**B2 HUMAN PENDING，当前不满足进入B3条件**。用户按上述卡确认通过后再闭合本批Gate；PWA仍独立待B5。实机尺寸要求已按用户指示永久从本计划人工反馈中取消，不再以缺数值阻塞。

## B2-R1 — 实机反馈：封面过大、专辑名消失（本批修复）

用户反馈“横屏状态下，专辑图片太大了，导致下面专辑名称都不显示了。立即修复”。仍停在B2处理，不进入B3。此反馈覆盖前文允许隐藏专辑次要信息的旧做法，已同步写入本计划和设计。

**根因与修复：** 真实浏览器1024×768复现专辑文本存在但计算样式`display:none`、行高0，封面约368.69px。PlayerPanel的`max-height:800px`规则，以及app.css的compact规则，都会主动隐藏专辑行，并将这部分高度预算留给封面。取消两处专辑隐藏；专辑行至少44px且随字号容纳行高，信息区不参与flex压缩。原实际F量测自动纳入专辑行、缩小封面，不修改高度算法或基础字号。紧凑模式只隐藏格式/DAC展示，专辑名保持可见。

**本轮fresh验证：** 先以实际浏览器专辑可见性断言确认FAIL，再最小修改CSS，重复检查PASS（44px读数存在约0.002px舍入，以1px容差核验）；未添加只断言CSS字符串的伪布局测试。

| CSS样本 | 专辑行 | 封面A | F | gap | 控制底 / Dock顶 |
|---|---|---:|---:|---:|---:|
| 1024×768 | 可见、约44px | 334.90（原368.69） | 297.37 | 35.84 | 684.27 / 696.28 |
| 1194×760 | 可见、约44px | 326.63 | 297.37 | 41.80 | 675.99 / 688.01 |
| 1194×834 | 可见、约44px | 400.00 | 297.37 | 41.80 | 749.66 / 761.97 |
| 1024×600 | 可见、约44px | 199.20（原约244） | 264.80 | 35.84 | 515.99 / 528.01 |

均无横向溢出，控制与Dock间保留约12px或更多。缩小Player后由原算法重算整体组宽/居中；右栏宽度、gap、Dock及路由结构不变。390×844手机纵屏AppBar y11.994/h43.394、导航h63.998保持原值。证据`b2/album-fix-measurements.json`与`album-fix.png`。

B2规定9文件针对性回归 **97 passed、0 failed（9.78s）**；typecheck **PASS**；build **PASS（122 modules，3.29s）**。此纯横屏CSS修复未重跑全套，前文347项只属于B2初版。日志`album-fix-regression.log`、`album-fix-typecheck.log`、`album-fix-build.log`。

最新访问仍为[5175 B2页面](http://192.168.3.18:5175/)，刷新加载修复；web/src新指纹 **`ac38dc1c5119434e0fc493b794ef3a66f31f52c75d04de55f520b7af680d9a80`**，覆盖前文初版指纹。新构建CSS `index-CRR51YVN.css`、JS `index-Do7itJRA.js`，浏览器仍使用dev源码。未改依赖、环境、播放事实、后端或真实MPD；未部署、提交、推送。diff/check/stat/status已核对；本轮仅2个产品CSS文件及本批相关文档变化。

**最小实机复验：** 同一iPad Safari刷新5175，横屏浏览器栏展开/收起各看一次，预期专辑名称始终显示、封面随可用高度收小、播放控制不被Dock盖住。直接反馈此项是否恢复即可，无需测量尺寸或重复无关测试。B2 HUMAN仍PENDING，实机通过前不进入B3。


## B2-R1 用户最终验收确认

用户对修复交付明确回复 **“验收通过。”**。据此将B2及B2-R1专辑名称恢复的实机验收记为 **HUMAN PASS**，B2 Gate闭合；此最新确认覆盖上文各实施阶段的HUMAN PENDING/不能进入B3状态。确认版本为同一5175 B2页面，web/src指纹`ac38dc1c5119434e0fc493b794ef3a66f31f52c75d04de55f520b7af680d9a80`；本轮重新核对分支`fix/v0.2-execution-sample-reuse`、HEAD`6091d73dc35f756057ed37e65ea2a077a1acc34b`及源码指纹均未变化。

本次只更新验收、计划、设计状态，未改产品或测试；沿用R1同版本的97项指定回归、typecheck/build和浏览器证据，不重复运行测试，不虚报新增截图或设备数值。实机尺寸采集继续按用户既有要求免除。PWA仍归B5单独验收，不作为进入B3的阻塞。

**结论：B2验收通过，满足进入B3条件。** 原单批边界继续有效；本轮未启动B3，也未提交、推送、部署或改动环境。
