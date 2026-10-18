# 横屏布局 B0 — 基线验收

> 2026-10-18 归档：历史方案/阶段验收，原文中的“当前”“待实施”及授权限制均指记录当时。现状与未闭合项见[现行文档索引](../../README.md)。

日期：2026-10-16（Asia/Shanghai）；本轮自动化/浏览器采样约 16:38–16:43。

**Gate：HUMAN PENDING，尚未达到 BASELINE READY，不允许进入 B1。** 本批无前序依赖；开始时不存在本计划的 B0 验收记录。只完成自主基线核验，没有实施横屏功能。

## 用户最新范围覆盖

用户在本轮明确要求：**“手机布局完全不变！禁止修改已有手机纵向布局”**。

此要求优先于原计划及规格中“共享 AppBar 同时改变横竖屏”的描述。后续不得用共享 AppBar、状态图标、标题去除、尺寸/预算、导航或通用样式改动影响已有手机纵向布局；手机纵屏以本轮当前源码为冻结参照。B4 原有共享视觉改动范围需按此要求收紧，不得机械执行旧文本。本批仅将覆盖关系记在验收文件，不改写原计划、规格或产品。手机纵屏采样用于保护参照，不是重新设计授权。

## 状态与版本

| 分类 | 状态 | 证据/边界 |
|---|---|---|
| Implementation | PASS | B0 文档和基线采样；产品实现不适用，产品/测试代码零修改 |
| Automated | PASS | 指定 6 文件 63 项通过；typecheck/build exit 0 |
| Browser | PASS | 当前源码 Mock 页面四页、媒体切换、尺寸和滚动基线；不代表未来横屏合同通过 |
| HUMAN | PENDING | 目标 iPad 横/竖屏及手机纵屏实际样本未收到 |
| PWA | PENDING | 实际设备安装/display-mode 状态待用户说明；本批不要求 PWA 全测，不安装 PWA |
| BASELINE READY | PENDING | 必需 B0-H1 证据不全；停在 B0 |

- 分支：`fix/v0.2-execution-sample-reuse`。
- HEAD：`6091d73dc35f756057ed37e65ea2a077a1acc34b`，`feat: default library to songs and add file time and title sorting`。
- 与计划编写基线一致；`web/` 无未提交源码差异。`HEAD:web` tree：`07eaca06161b847125bee56813d303a786e9c09f`。
- 开始时已有 dirty：performance B5/B6a/B6b/B7 四份 acceptance、`docs/superpowers/README.md`、全局 UI 规格；另有未跟踪的本计划及横屏设计规格。全部保留；前述 tracked diff 为 527 insertions / 36 deletions。本轮新增本验收记录；采样文件放在 ignored workspace。
- 当前工作区 Spec SHA256：`95fc41e37f1906e56ef4411ab289bd946159ee10612922a6dff6ae74dedee691`；Plan SHA256：`d81c2e98c3da2b80dc1a1613d8ef75b088786a130aedc9c2cc82c4420d2f77a1`。两者均是读取时的未提交文件，不把 HEAD 当作全部文档版本。
- 已读取本地 `AGENTS.override.md`、现行索引、计划、最新横屏规格、继承的全局 UI 合同。Task 8 W5 / Task 9 final 归档仅作历史参照：W5 有旧版手机通过，Task 9 有未闭合项，均非当前横屏前置 Gate，也不能冒充本版本实机证据。未找到可证实为当前 `6091d73` 的 iPad/手机尺寸及截图，未复用历史通过。

## 访问方式及环境

- Node `v24.20.0`、npm `11.19.0`；既有 `web/node_modules`；实际 Vite `7.3.7`、Vitest `3.2.6`。无缺依赖或环境阻塞，无安装/升级。
- 本机浏览器：`http://127.0.0.1:5173/`；候选设备地址：[当前工作区 Mock 页面](http://10.104.60.177:5173/)。本机访问 LAN 根页面及 `/src/views/LibraryView.vue` 均 HTTP 200；**设备端可达性尚未确认**。
- 复用既有 Vite dev PID 14107，cwd 为本仓库 `web/`；读取当前源码，代理 `http://127.0.0.1:8015`。后端 PID 14399 的既有 `/tmp/mpd-b04-mobile-o2wjv06n/serve_mock.py` 明确注入 `MockMPD`，未连接真实 MPD。没有启动/停止/改配服务，没有部署。
- 页面历史标题仍是 `MPD-Server · B04 MOBILE · MOCK`，**不是本批构建标识**。本次访问版本标识为 `B0 / 6091d73 / web-tree 07eaca06 / dev5173 / 2026-10-16`。后续源码或服务改变时需重核版本，不能只看此旧标题。
- 当前样本为“归途／B04 合成测试”、暂停、0:00/0:08、无封面占位、两行同步歌词；Queue 5 项含长中文/emoji，Library 7 首。只导航、切媒体及滚动，未点击播放/seek/收藏/排序提交/保存连接。
- 当前 `5188` 为历史 live preview，不用于本批访问版本，避免把旧构建混入。
- 本次 `npm run build` 校验成功，但浏览器访问的是 dev 源码，不是 dist。构建产物：CSS `index-BTuS8SLu.css`（SHA256 `85b7cd15728fbcce15a3a3834a40cc4bacc62dfa18e7512bf1a9500d0b683a3b`）；JS `index-C77VDZd1.js`（SHA256 `4b420bfcd6dda5de2ce90f118f1ba6a638724d0872a263ecf86d853441b1c206`）。产物保持 ignored，不提交。

## 自动化基线

以下命令均从 `web/` 执行，2026-10-16 本轮 fresh 结果：

```bash
npm test -- --run tests/invariants/shell-navigation.test.ts tests/invariants/player-lyrics.test.ts tests/invariants/player-controls.test.ts tests/invariants/global-artwork.test.ts tests/invariants/appbar-activities.test.ts tests/invariants/library-sorting.test.ts
# 6 files passed; 63 tests passed; 0 failed; 6.51s; exit 0
npm run typecheck
# exit 0
npm run build
# 117 modules; exit 0; 2.51s
```

测试输出中的 `[activity]` 为活动诊断日志，无测试失败。本批无新行为、无 RED→GREEN 实现，也未修改既存测试。按 B0 指定范围未跑全前端/后端、Ruff、Docker、真实 MPD 或 NAS 测试；不以缺少这些无关测试阻塞本批。

## 当前事实与保护范围

| 合同/关注点 | 当前源码 owner（本轮均不改） | 自动化及浏览器基线 | 与目标的差异 |
|---|---|---|---|
| WEB-UI-SHELL/NAV、WEB-LANDSCAPE-NAV-001 | AppShell、App.vue、router、playerSession | shell-navigation；四页导航返回歌词仍为歌词 | 唯一 shell/session/realtime 已有；Player 仍仅 `/` 展示，横屏双栏/常驻 Player 尚无 |
| WEB-UI-BASE、歌词/控制保护 | PlayerView、LyricsStage、ArtworkStage、playerSession | player-lyrics/player-controls；封面→歌词→跨页→歌词→封面 | 保留控制、seek/锁定、媒体选择、歌词和原 owner；不借本批拆组件 |
| WEB-UI-BG、WEB-LANDSCAPE-STYLE-001 | AppBackground、AppShell、artwork store、tokens | global-artwork；本次实际页面为无图默认背景 | 全局背景/资源身份已有；本次截图不证明非空封面或对比度全覆盖 |
| Library 当前默认入口/排序 | LibraryView、LibraryTabs、library store | library-sorting；默认“全部歌曲”，`title:asc`，时间/标题四项可见 | 必须保留；本批不操作集合播放 |
| WEB-LANDSCAPE-GEOMETRY/HEIGHT-001 | app.css、tokens.css、PlayerView | 浏览器边界实测，见下表 | 当前限宽 28rem 单列，未实现目标几何/高度预算或 Dock |
| WEB-LANDSCAPE-APPBAR-001 | AppBar、PlaybackStatus、notices | appbar-activities；切页几何稳定 | 现有 MPD SERVER、约43.4px栏/20px图标仍保留；5秒消隐等尚无。后续不得因此改变手机纵屏布局 |

已核对 Queue/Library/Settings 实际页面及相关状态接线，未新增 API、后端变更、业务 owner 或响应式监听。

## 浏览器证据（不能替代实机）

环境：Linux Codex IAB，浏览器具体版本未从当前工具获得；display-mode 为 browser（standalone=false），根字号16px。测得 DPR≈1.1、visualViewport.scale=1。**viewport override 输入不是最终 CSS 尺寸**；例如请求390×844时实际 inner 为355×767，故下面只以实际读数报告，不把输入尺寸冒充实测。未更改浏览器缩放设置；测试结束恢复 viewport override。

| 实际 innerWidth×innerHeight | visualViewport 宽×高 | frame 宽/左边缘 | AppBar 高 | 导航高/顶部 | 封面边长 |
|---|---|---|---|---|---|
| 355×767 | 354.859×767.398 | 322.864 / 15.997 | 43.397 | 63.999 / 703.399 | 274.138 |
| 834×1194 | 833.856×1193.730 | 447.992 / 192.927 | 43.397 | 63.999 / 1129.722 | 447.992 |
| 1194×834 | 1193.730×833.856 | 447.992 / 372.864 | 43.397 | 63.999 / 769.857 | 330.182 |

后两项分别使用917×1313、1313×917 override 获得上述实际读数，仅桌面浏览器尺寸样本，绝非目标 iPad 实测。目标设备描述 **2420×1668** 原样保留，其物理像素/DPR/CSS 关系未知，未据此换算。

355×767 四页共用 AppBar y≈11.991、shell-content y≈55.388/h≈648.011、导航 y≈703.399。Player 控制 y≈639.401/h≈63.999，不与导航重叠。媒体切换不改变壳边界；返回 `/` 保留歌词选择。Library shell 内容 scrollHeight=680；Settings=928；Settings 实际滚动至 scrollTop≈280.251 后 AppBar/导航位置不变。Queue 此样本不需要滚动。正常页无额外 Player；横屏也仍为单列，这是当前基线，非本批待修缺陷。Mock 的 MPD stats/输出能力未验证提示如实保留，不据此改生产代码。

当前浏览器未独立测出 `env(safe-area-inset-*)`，也不能模拟 Safari 顶部栏；只记录实际壳 padding/边界，不虚报 safe-area=0。目标设备的系统、浏览器版本、safe-area、顶部栏状态、DPR、CSS/visualViewport 及 PWA 状态待补。

本地证据目录（ignored，勿作为产品或提交内容）：`.superpowers/sdd/2026-10-16-responsive-landscape-player-batch-plan/b0/`。包含 `measurements.json` 与 `player-artwork.jpg`、`player-lyrics.jpg`、`queue.jpg`、`library.jpg`、`settings.jpg`、`settings-scrolled.jpg`、`tablet-portrait-artwork.jpg`、`tablet-landscape-artwork.jpg`。这些截图仅为浏览器基线；完整设备截图必须由实机提供。

## B0-H1 简短实机验收卡

**访问版本**：上述 B0/6091d73/dev5173。地址 `http://10.104.60.177:5173/`；在同一可达网络打开，标题可能仍显示 B04 MOBILE · MOCK。若不能访问，反馈地址/网络情况，先解决可达性；不要改用旧5188或部署版本冒充本次源码。

**前置**：目标 iPad，浏览器顶部栏保持可见；手机也使用现有纵屏设置。无需播放、拖动、保存或改变 MPD 配置。

1. 告知 iPad/手机型号、系统及浏览器版本、页面/字体缩放；PWA 是否已安装（仅记录，不要求安装）。
2. iPad 竖屏打开 Player，保留顶部栏，分别截图封面和歌词；预期同一媒体区切换，现有控件和布局原样保留。
3. 依次打开 Queue、音乐库、设置，各保存完整可见页面截图（含浏览器栏和底部导航）；预期单列结构，音乐库默认全部歌曲/标题正序，设置可滚动。不要点播放或保存。
4. 回 Player 后转横屏，保持浏览器栏可见，保存完整截图并采集下述尺寸；竖屏也采集一次。预期当前仍单列；本批不应出现双栏或布局改动。
5. 手机竖屏采一组 Player（封面/歌词）与四页现状截图/尺寸；若已有可证明同版本证据，给记录位置即可，不重复无关流程。预期手机原布局完全不变。

**所需反馈**：截图＋两台设备信息＋iPad横/竖及手机竖屏尺寸JSON；注明浏览器栏是否展开、是否有遮挡/横向溢出、访问标题及地址。物理分辨率与CSS尺寸分开填写；不靠截图像素推算 CSS viewport。

如有 Safari Web Inspector/浏览器控制台，可在当前产品页面运行以下仅测量的片段。它临时插入不可见探针读取 safe-area，随后立即移除，不保存配置、不发网络请求。无法采尺寸时直接反馈，保留 PENDING，不以猜测补值：

```js
(() => {
  const probe = document.createElement('div');
  probe.style.cssText = 'position:fixed;visibility:hidden;pointer-events:none;padding:env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left)';
  document.body.append(probe);
  const css = getComputedStyle(probe);
  const result = {
    url: location.href, title: document.title, userAgent: navigator.userAgent,
    innerWidth, innerHeight, dpr: devicePixelRatio,
    visualViewport: visualViewport && {
      width: visualViewport.width, height: visualViewport.height,
      scale: visualViewport.scale, offsetTop: visualViewport.offsetTop
    },
    safeArea: [css.paddingTop, css.paddingRight, css.paddingBottom, css.paddingLeft],
    displayMode: matchMedia('(display-mode: standalone)').matches ? 'standalone' : 'browser',
    rootFont: getComputedStyle(document.documentElement).fontSize
  };
  probe.remove();
  console.log(JSON.stringify(result, null, 2));
  return result;
})();
```

## 收尾与进入下一批条件

本轮 `git diff --check` 通过；tracked diff/stat 与开始时相同，唯一新增的可交付文件是本记录，另有 ignored 截图/量测/进度账本。未改产品/测试/依赖/.venv/数据库/已有文档；未做 Docker、真实 MPD、部署、提交、推送或切分支。

进入 B1 前仍需 B0-H1 的目标 iPad 横竖尺寸/截图、纵屏四页保护参照、手机同版本样本及实际设备/PWA 状态。收到反馈后仍在 **B0** 补证与裁决，证据齐全才可标记 **BASELINE READY**。当前不满足下一批条件。
