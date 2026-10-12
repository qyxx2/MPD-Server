# Task 9 B01 acceptance — T9-B01-A01

日期：2026-10-10，Asia/Shanghai；本轮仅B01。分支`feature/task-9-web`，基线`14c6239283f4fed079f07ab817964b23e87e793c`，全部改动未提交。开始时已有README、文档索引、总计划及三个Task9文档改动，均保留；本轮只更新B01接口/执行状态和本报告。

| Gate | 当前证据/结论 |
|---|---|
| Task8前置 | W6最新真人确认及main提交已核对，手机Web前置满足；不把原PWA整体范围称为完成 |
| 环境 | READY：既有ARM64 Linux `.venv`，Python3.14.4/pytest9.1.1/ruff0.16.9；无依赖或虚拟环境变更 |
| 实现 | DONE：持久session/actions、通知注册表、解码后共享背景/封面、唯一bar/nav、四顶级及Library内部占位路由 |
| 自动/关系Gate | PASSED：下述新测试、Player/客户端回归、wire、类型检查、生产构建 |
| LAN | 本机HTML/assets/API/WS核验及用户手机测试确认通过 |
| 真人H01/H10 | HUMAN PASSED；最终用户确认及关闭结论见末节 |
| G9-01 | DRAFT：song Play Now后端合同未冻结，阻塞B02；B01不消费该候选接口 |
| B02–B10 | NOT STARTED |
| 真实MPD/NAS/DAC | NOT RUN；本轮使用真实app/service/API和显式MockMPD，不能替代设备验收 |
| PWA | DEFERRED |

## 合同与关系证据

入口：Task9 contract audit及web batch plan；依据Visual Spec WEB-UI-SHELL/NAV/BG/STYLE/NOTIFY、架构4.1–4.3/12/19.5、Playback既有identity/key/控制目标合同、Library资源身份合同和mobile manual acceptance。Task8最新W6手机Gate由用户实际确认，未仅凭清单推断。

- `global-notices`：请求发出后实际卸载Player进入Queue，pending/unknown保留；顶部retry引用原intent/key；确认仅重读；断网禁写/不自动补发，epoch退役；并发两个异常保留且显示可辨认的动作/目标。
- `global-artwork`：四页同identity只请求一次；只有解码成功URL发布，迟到A不盖B；404/503/解码失败fallback；stale只保留已接受背景，fresh失效清除，handoff不授权新背景身份。
- `shell-navigation`：四页和Library内部选中、返回/非法路径、唯一壳/通知入口，一次start及最终一次stop。路由refresh的生产HTML可达另在LAN确认。
- 持久owner提升既有Player动作、clock、presentation及mediaMode；歌词正文、解析、选择、cue及3秒跟随实现未改。Player原事实/lifecycle断言保留，只更新合法导航断言及旧测试装配。
- Notice可选level仅表达既有Visual优先级；taskActions可选description仅展示动作/目标，不参与网络请求、intent/key或恢复判定；接口表先更新再消费。

独立审阅给出两个Important问题：refresh跨epoch/dispose后仍执行旧资源读取closure；并发通知缺动作/目标。三项精确RED均复现，最小修复后`global-notices`8项及全套通过。无Critical。首选审阅模型因账户额度未运行，替代审阅已完成；未把失败启动算审阅证据。未来页面功能、旧Player已冻结恢复语义、手机触摸及真实设备行为不在该审阅的通过声明中。

## 自动验证

从仓库根运行；日志保留在忽略目录`.superpowers/sdd/2026-10-10-task-9-web-batch-plan/`。初始Web基线14文件173项通过，新主关系测试先RED后GREEN。最终：

| 命令 | 结果 |
|---|---|
| `npm --prefix web run test -- --run tests/invariants/global-notices.test.ts tests/invariants/global-artwork.test.ts tests/invariants/shell-navigation.test.ts` | 3文件14项通过；精确主节点均有单独通过记录 |
| `npm --prefix web run test -- --run tests/invariants/player-facts.test.ts tests/invariants/player-controls.test.ts tests/invariants/player-seek.test.ts tests/invariants/player-clock.test.ts tests/invariants/player-lyrics.test.ts tests/invariants/player-notices.test.ts tests/invariants/player-output.test.ts tests/invariants/wire.test.ts` | 8文件126项通过 |
| `npm --prefix web run test -- --run tests/invariants/realtime.test.ts tests/invariants/client.test.ts tests/invariants/mutation.test.ts tests/invariants/resource-cache.test.ts` | 4文件43项通过 |
| `.venv/bin/python -m pytest -q server/tests/api/test_web_wire_fixture.py` | 3通过；既有Starlette/httpx弃用警告1条，未改依赖 |
| `npm --prefix web run test -- --run` | 17文件187项通过 |
| `npm --prefix web run typecheck` | 通过 |
| `VITE_ACCEPTANCE_LABEL=T9-B01-A01 npm --prefix web run build` | 通过，73 modules |
| `git diff --check` | 通过 |

本轮未修改Python生产代码，Ruff N/A；没有以全套替代指定targeted Gate。首次Node-only proxy测试因HTMLImageElement不存在失败，解码测试边界stub已加DOM存在检查；新增测试`get().exists()`类型错误改为`find().exists()`，随后类型检查通过。最后一次WS预检误用`/api/ws`得403；检查实际路由后使用`/api/realtime`取得snapshot，未修改产品路由。

## 实际交付与辅助预检

URL：**http://10.104.60.177:5174/**；标题 **MPD-Server · T9-B01-A01**，构建/核验约19:35 +08:00。wlan0地址10.104.60.177。页面、health/state、Library search深路径均HTTP200；HTML及所有assets与磁盘dist逐字节相同。WS `/api/realtime`首帧protocol1 snapshot，epoch`b7a5b0da-1c3e-4c7d-a31d-e2a930422c9f`，sequence27。

| 文件 | SHA256 |
|---|---|
| `index-C0iFFvvZ.js`（135997字节） | `8fc08430a56d65351651b0e6efc748882535f6ff81e74063c364e36dd15cdded` |
| `index-D3loImyA.css`（10381字节） | `c4f7fd7762ab944cce1440f17850c32e44ba81a548650e014bd2f27e5e1b9372` |

355×601辅助viewport无横向溢出：header y11.99/h43.39，transport y473.38/h64，nav y537.38/h64。旧基线同viewport header y11.99/h43.37、transport y473.38/h64。固定title/artist/album槽位后正常曲media高度114.54，旧基线未知曲214.55（场景字段不同，不能冒称封面比例完全未变）；Player比例是否合适交手机H01确认。封面↔歌词media及transport坐标不变。四页保留同一背景blob、一个header/nav；通知按钮44×44，导航/既有按钮至少44px（CSS规则，触摸体验待手机）。截图`b01-player.png`在上述忽略证据目录。

亮/杂乱128×128封面已通过真实资源端点及浏览器解码。全白最坏背景与rgba(8,13,24,.8)遮罩合成时，primary约10.06、secondary6.51、muted4.68、accent6.60对比度；不是只按深色默认背景估算。无图显示默认背景，不额外遮罩。`@supports not (filter:blur(1px))`隐藏图/遮罩，reduced-motion关闭动画/平滑滚动：源规则已检查；当前辅助浏览器未实际模拟这两个平台分支，M07仍PENDING，不能把源检查称为设备通过。

独立本地夹具：正常曲PAUSED37秒/LRC61行/亮封面；后三次下一首为长中文普通歌词→歌词read_error→未知字段/无歌词/无封面。clock仅推进Mock样本，不伪造自然完成。新独立SQLite、PNG、FLAC及日志均在忽略runtime目录，旧数据库/旧进程保留。后台8001只监听loopback；前端5174同源代理API/WS。当前进程保持运行。

以下仅供维护者重启/停止，手机用户无需终端。端口被占用不重复启动；前台Ctrl-C可停本轮进程，后台仅停止本轮拥有PID（本次后端612、前端3699），不停止旧8000/5173。重启生成新独立DB，保留旧文件。

```sh
PYTHONPATH=. .venv/bin/python .superpowers/sdd/2026-10-10-task-9-web-batch-plan/b01-runtime/serve.py
API_PROXY_TARGET=http://127.0.0.1:8001 npm --prefix web run preview -- --host 0.0.0.0 --port 5174 --strictPort
```

## 最少手机操作（待反馈）

首次记录手机型号/系统/浏览器版本（已有记录且未变可沿用）。同一LAN刷新URL，核对T9-B01-A01；手机可达：PENDING。

| 编号 | 操作及通过基准 | 状态 |
|---|---|---|
| 1 / H01、M01/02 | 四导航切换→返回Player；浏览器返回/刷新（可刷新`/library/search`检查Library选中）。bar/nav/背景连续，只换中间。Player封面↔歌词、播放后拖动歌词观察3秒恢复跟随；比例和控件触摸正常 | HUMAN PENDING |
| 2 / H01/H10、M04/07 | 下一首检查长中文，放大文字；再下一首检查歌词异常，下一首检查缺图/未知。顶部详情可打开/关闭及读取，正文控件不跳；亮图文字可读，缺图稳定。已有系统“减少动态效果”条件下仍可用；无blur分支若手机无法触发，保留AI平台预检待补 | HUMAN PENDING |
| 3 / H10、M05/06 | 已加载页断网、跨页查看顶部详情，操作禁用；恢复LAN及短暂后台/锁屏返回，事实/计时恢复，没有离线补发，顶部恢复入口可达 | HUMAN PENDING |

并发未知写请求的原key/intent及退役由自动测试证明；空占位页面没有业务写按钮，不要求用户制造未来Queue动作或读取网络内部字段。场景需重置时通知AI，由AI准备，不要求用户操作DB。

用户反馈：尚未收到。结论：**实现及自动Gate通过，B01未关闭；等待手机H01/H10及适用M项确认，不进入B02。** 未commit、push、创建PR或merge。

## A02 — 手机反馈修复（2026-10-10约20:28 +08:00）

用户反馈：Queue/音乐库/设置的重复标题离品牌过远，愿意去掉；顶部详情像半透明、下层内容干扰、项目字号过大。播放暂停及上下首反应慢，用户明确“这个问题也可以暂时不解决”。性能问题暂缓，未推断为已解决，也未改写确认语义。

根因与修复：占位h1及额外padding删去，保留section可访问名称和导航标签。弹框背景实际已是实色#1b293c；浏览器elementsFromPoint显示lyrics-content在status-details之上，是媒体容器绘制层覆盖而非背景alpha。唯一AppBar提升stack层级后status-details位于内容之上。弹框/按钮继承统一.8125rem（默认13px）、缩小间距；slot最后歌曲文本同样紧凑，仍保留44px点击范围。用户统一视觉选择已同步唯一Visual Spec，不建立另份设计规则。

纯样式/占位修复，不添加镜像CSS测试。实际浏览器先复现后验证层序、实色底、默认字号13px、按钮44px、三页无重复标题及四页持久壳。未改歌词正文及动作/API/backend。指定受影响回归：

`npm --prefix web run test -- --run tests/invariants/shell-navigation.test.ts tests/invariants/global-notices.test.ts tests/invariants/player-notices.test.ts tests/invariants/player-controls.test.ts tests/invariants/player-lyrics.test.ts`：5文件55项通过。typecheck、`VITE_ACCEPTANCE_LABEL=T9-B01-A02 npm --prefix web run build`、diff check通过。A01其余自动证据仍适用，未宣称A02重复运行全套/后端。

同URL **http://10.104.60.177:5174/**，标题 **T9-B01-A02**。HTML/assets再次逐字节匹配dist：

```text
index.html 444 09ccc77e82c60fe802d7612205f6eeec4eee47b05dafa15e3f4a95661bb23d1f served-identical
index-C9RcnpJN.css 10646 bea83d1c79a3621a286a23f19480cf2183c9a22b4f2ced42fe2495147f857699 served-identical
index-CkIizgk6.js 135973 206d80a14624d07b5e966194fccf4f3ab798cc446a293341fa2302c85edbc88c served-identical
```

截图忽略目录`b01-a02-popup.png`。现有夹具场景保留用户已选未知元数据曲，未重置/改用户操作结果；可切歌词显示“无歌词”以打开通知入口。本轮复验只需：①三个占位页无重复标题；②Player歌词模式打开感叹号，检查遮挡/字号/点按及关闭无跳动。其他尚未明确通过的A01真人项继续PENDING，不重做已确认项。播放/暂停/上一首/下一首延迟：DEFERRED（用户明确允许），源码无固定半秒延迟、pending在请求前设置；没有手机性能测量，不把网络/确认等待假设写成根因。B01仍未关闭，等待A02及必要手机Gate确认。无commit/push/PR/merge。

## 最终真人确认与B01关闭（2026-10-10，Asia/Shanghai）

用户在A02交付后原话：“测试都可以通过。”据此记录本次B01手机H01/H10及适用M01/02/04/05/06/07通过，A02重复标题和弹框可读性复验通过；上述PENDING为各轮交付时的历史状态，以本节为最新结论。手机沿用用户实际设备和浏览器，未提供新的型号/系统/版本，不编造设备信息。

本次只更新文档/ledger及检查Git，不重复测试、构建或要求用户重复验收。A01自动187项/wire3及A02受影响55项、类型检查、生产构建和实际LAN证据继续适用。用户手机通过不扩展为AI已执行no-blur/reduced-motion平台强制模拟；该辅助浏览器分支未执行的事实保留，源规则已检查。不声明真实MPD/NAS/DAC或PWA完成。

**B01当前授权范围关闭：实现、自动/关系Gate及手机验收通过。** 播放/暂停/上下首响应慢仍为用户明确允许暂缓的遗留问题，未修复，不作为本次通过声明中的性能成果。B02–B10未启动，G9-01仍DRAFT，后续B02还需独立授权及合同审核。全部工作未提交；未commit、push、创建PR、merge或删除分支/运行时文件。
