# 横屏布局 B4 — 共享 AppBar 状态验收

> 2026-10-18 归档：历史方案/阶段验收，原文中的“当前”“待实施”及授权限制均指记录当时。现状与未闭合项见[现行文档索引](../../README.md)。

日期：2026-10-16，Asia/Shanghai。仅执行 B4。

**最新状态（2026-10-17）：Implementation PASS；Automated PASS；Browser PASS（以下有限 IAB 样本，reduced-motion 为 CSSOM 静态核验）；HUMAN PASS；PWA PENDING（B5责任）。B4 Gate PASS，满足进入 B5 的前置条件；未启动 B5。**

## 基线、前置 Gate 与范围

已读取本地 AGENTS.override.md、现行文档索引、Batch 计划、最新横屏设计 §6、继承全局 UI 合同及 B0–B3 验收。开始时无 B4 记录。B0 人工记录按既有授权豁免；B1/B2 最新实机确认 PASS；B3 用户最终回复“通过”，H1/H2 HUMAN PASS。当前 web/src 指纹核验为 `3bb0b192a8d0c3e7d8a655561f29f14f1b24163ead61e99c296db47c8a7e7ba8`，与 B3 已确认版本一致，因此允许执行 B4。

分支 `fix/v0.2-execution-sample-reuse`，HEAD `6091d73dc35f756057ed37e65ea2a077a1acc34b`，与计划基线一致；15 个既存 tracked dirty 文件及已有 untracked B1–B3 源码/测试/文档全部保留。HEAD 不包含这些成果，不可单凭 HEAD 标识访问版本。未切分支、创建工作树、回退或覆盖已有修改。

本批最终 web/src 指纹：**`c252a1d9b15c307ed5aa3efe74263382c44c547ca3feb8692ef68f0fda65a2bd`**。算法：对完整路径排序的 web/src 文件依次 SHA256 输入路径、NUL、文件字节。浏览器和实机卡均使用这份未提交工作区源码。

## 实现及合同映射

| 合同 | 本批改动 | 证据 |
|---|---|---|
| WEB-LANDSCAPE-APPBAR-001 普通信息 | PlaybackStatus 的唯一共享展示时钟，按稳定 id/updatedOrder 保存绝对到期时间；同状态轮询不续期，真实状态变化重计时；卸载清理 | 4999/5000ms fake timers、导航/旋转、清理、真实歌词 snapshot 轮询测试 |
| 异常优先 | 全部活动汇总，warning/unknown/failed/retired 优先于 busy spinner；显式 warning 也常驻、不会被成功记录裁剪吞掉 | 最近5项外 warning+busy、信息在遮挡期间到期、汇总读取测试 |
| 展示与业务分离 | 消隐不删除最近5项/未解决事项/原重试或读取上下文；详情不因计时关闭；入口有焦点时保留，离焦再隐藏；后续新活动复用同一浮层 | details/focus 测试、global mutation/read-only/原key重试回归 |
| 横竖屏几何 | AppBar 移除 MPD SERVER 及隐藏的实时连接文字；现有高度、中心槽位与44px点击范围保持；只在双栏图标改24px，纵屏仍20px；状态局部橙色 token `--status-warning: #ffb45c` | 浏览器量测及 CSS 检查、responsive-layout、player-facts |

产品只改 `AppBar.vue`、`PlaybackStatus.vue`、`notices.ts`、`tokens.css`。新增/扩展测试只涉及 appbar-activities、global-notices、player-notices，另同步 library-sync 和 player-facts 两项明确被 B4 替代的旧断言。未改 AppShell/Player/Dock/页面整体几何、后端、依赖或环境。既存相关文件的早前 dirty 不计为 B4 新增改动。

**执行裁定：** 复用现有状态变化序号；显式 warning 的出现/解除也属于展示语义变化，undefined/info 的非警告级别变化与 message-only 轮询不续期。局部状态色 token 仅校准本状态图标，保留其它 warning 色。无需扩大结构或重开 B1。继承的 B3 测试隔离 Minor 未在本批扩大修复范围。

## 自动化、环境与审查

沿用 Node v24.20.0、npm 11.19.0 和现有 web/node_modules。未安装、更改依赖/锁文件/虚拟环境，纯前端任务未运行无关 Python/Ruff/后端测试。未使用 Docker、真实 MPD、部署、提交、push 或 PR。

日志和原始产品快照保存在 ignored 目录 `.superpowers/sdd/2026-10-16-responsive-landscape-player-batch-plan/b4/`。

- 开始三文件基线：29 passed。
- 5 项新增核心测试先 RED：5000ms 仍显示、warning 被 spinner 覆盖、到期离焦不隐藏、显式 warning 未聚合、非状态文字未删除；随后 GREEN。焦点测试一次失败源于 detached mount 无法真实聚焦，改为 attachTo document.body 后精确重跑通过；未修改生产代码迎合该夹具问题。
- 初次 B4 指定回归：6 文件 51 passed；后补独立入口焦点用例，使指定集合为 52 项。
- 补充完整前端首次：356 passed、2 failed。完整读取失败后确认：library-sync 旧用例要求 warning+busy 仍显示 spinner，player-facts 旧用例要求品牌/连接文字，与本批规格冲突。仅将这些断言改为 warning 优先和无非状态文字，同时保留活动详情、DAC/源格式等断言。两项精确重跑均通过。
- **最终指定及受影响回归：8 文件、83 passed、0 failed（6.33s）**：

```bash
# web/ 工作目录
npm test -- --run tests/invariants/appbar-activities.test.ts tests/invariants/global-notices.test.ts tests/invariants/player-notices.test.ts tests/invariants/mutation.test.ts tests/invariants/shell-navigation.test.ts tests/invariants/responsive-layout.test.ts tests/invariants/library-sync.test.ts tests/invariants/player-facts.test.ts
```

- **最终完整前端补充回归：36 文件、359 passed、0 failed（27.34s）**。不抵扣 B5 实机/PWA验收。
- `npm run typecheck` PASS；`npm run build` PASS（122 modules，2.24s）。CSS `index-C8Y1PZae.css` SHA256 `8e45293da1f27f5ec4fb810614255df1686754171693c0b8e8fdf1ef9180b370`；JS `index-C0IwgE42.js` SHA256 `eb83f2c23e879634246004e67f7ddbab82916ee689dec2ebcd7e3fcef41b0743`。
- 独立只读代码审查无 Critical/Important/Minor；review.md 已实际读取。审查不代替测试或实机证据。其不作判断的浏览器/设备/几何/朗读及 B5/PWA/Gate 事项，以本记录相应证据及 PENDING 状态为准；继承 B1–B3及后端属于已冻结范围。
- 两次准备命令误用了 web/ 工作目录，文件操作 ENOENT，均在修改前纠正；测试日志与最终文件已核对。误建的空 web/.superpowers 目录仅用 rmdir 清理。

## 浏览器证据及限制

Linux Codex IAB，非目标 iPad Safari、非独立 PWA。5177 隔离 Vite 夹具加载真实 AppShell、路由及现有状态投影；测试 Probe 仅在 ignored serve.mjs 内注入合成状态。全部写请求拒绝、无后端代理，未联系真实服务。测试菜单不进入产品代码。LAN 本机 HTTP 200；设备可达性须用户确认。

| 实际 CSS viewport | 检查结果 |
|---|---|
| 1194×834 | 信息入口可见，之后自动消隐；AppBar y0/h43.998、32px槽、44px点击范围、24px图标；Dock x437.24/y761.97/w320/h60。入口消隐与并发警告/打开详情前后 AppBar/Dock 数据相同 |
| 1194×834 | 最近5项外 unknown+busy 显示橙色三角 warning，spinner 不显示，全部未解决事项保留汇总；汇总读取后模拟异常/忙碌解除，无写请求 |
| 1194×834 | 打开普通信息详情，超过5秒仍显示；实际 Escape 后详情关闭、焦点回到“查看最近活动”；实际 Tab 离焦后入口隐藏 |
| 390×844 | 纵屏 AppBar y11.994/h43.394、槽32px、目标44px、computed SVG20px，导航h63.998；警告详情 x35.17/y57.68/w320/h261.20，处于视口内，未推移 Player/Dock |

无状态时保持空槽，AppBar 不再包含品牌文字；入口具有“查看最近活动/查看活动异常/查看正在处理的活动”名称，统一 role=status/aria-live=polite 及 dialog 名称可通过可访问树读取。**仅验证可访问语义，未声称真实屏幕阅读器朗读通过。** reduced-motion 的静态忙碌规则已从浏览器 CSSOM 核验（动画 none），默认偏好下 busy 使用 spinner；当前控制能力未提供媒体偏好模拟，未声称操作系统减少动态偏好或实机已测。

`measurements.json` 保存3组几何数据，`landscape-warning.png`、`phone-warning.png` 为实际 IAB 截图。其余行为输出见本会话及此表，不伪造缺失数据。一次 DOM locator.press 超时后，使用实际键盘接口重做 Escape/Tab，并核对返回焦点；超时动作不作为通过证据。测试结束恢复视口并关闭临时 tab；5177 服务保留供本批实机验收。

## B4-H1 简短实机验收卡

**访问版本：** [B4 隔离只读验收页](http://192.168.3.18:5177/)，标题 `MPD-Server · LANDSCAPE B4 · 6091d73 · MOCK`，源码指纹 `c252a1d9…a65a2bd`。使用5177，本批不以5174–5176旧标题识别版本。无需测量尺寸，不播放、保存设置或操作真实 MPD。

在 **iPad Safari 和手机浏览器各一轮**：

1. 点右上“B4 测试”→“清除模拟活动”，再选“模拟普通信息”。暂不点顶部中心入口，预期蓝色信息约5秒消失，AppBar/内容/Dock不跳动。
2. 再选“模拟普通信息”，立即点顶部中心信息图标打开详情；等待超过5秒，预期详情仍开着、文字和关闭按钮可触摸；关闭后点一下其它控件将焦点移开，图标消隐。触摸浏览器可能在入口保留焦点，保留至移焦属于规格明确例外。
3. 选“模拟警告并发”，预期顶部橙色三角警告持续显示，打开统一详情可见“另有N项未完成”；点“重新读取未完成状态”可安全解除模拟异常。预期浮层不挡住自身关闭/读取操作，AppBar仍够低且位置不变。

**需要反馈：** 回复“B4通过（iPad和手机：消隐、详情、警告、触摸正常）”，或注明未测项目与异常；有问题可附截图。无需重测 Library 全功能/完整播放链。无设备反馈不得标 HUMAN PASS；PWA继续归B5。

## 收尾结论

本批实施、自动化、有限浏览器检查完成；实机验收未完成。已核验实际 diff、git diff --check/stat/status，未引入依赖、数据库、生成物或无关产品修改。停在 B4，**HUMAN/PWA PENDING；不满足进入 B5 条件**。本地验收服务不等于部署，不自动提交或推送。


## 2026-10-17 用户验收确认

用户对本批完整实机验收卡回复 **“可以验收”**，据此记录 B4-H1 验收确认，HUMAN PASS。此确认覆盖上文实施阶段的 HUMAN PENDING 和不满足进入 B5 条件结论；不补造设备版本、尺寸、截图或逐项测试细节，不扩展为独立 PWA、真实屏幕阅读器或操作系统 reduced-motion 实测证据。

已重新核对分支 `fix/v0.2-execution-sample-reuse`、HEAD `6091d73dc35f756057ed37e65ea2a077a1acc34b`，源码指纹仍为 `c252a1d9b15c307ed5aa3efe74263382c44c547ca3feb8692ef68f0fda65a2bd`，与 B4 交付版本一致。本轮仅更新验收、计划和设计状态，复用同版本 83 项针对性回归、359 项完整前端回归、typecheck/build及有限浏览器证据，不重复执行未受影响测试。

**结论：B4 验收通过，满足进入 B5 的前置条件；本次不自动启动 B5。PWA 继续 PENDING，归 B5。** 未改产品、测试、环境，未提交、推送或部署。
