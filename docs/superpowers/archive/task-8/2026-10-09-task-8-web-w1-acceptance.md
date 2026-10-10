# Task 8 Web Batch W1 acceptance

Task / Batch / 轮次 / 日期（Asia/Shanghai）：Task 8 / W1 / W1-A02 / 2026-10-09。

代码标识：`feature/task-8-web-player`，基线及当前 HEAD `adf4171`，未提交 W1 工作区。代码/工具链 fingerprint `416ab90e26e652ee`（按路径排序对 W1 源码、测试、配置（包括 dev Compose 接线）、fixture 和 lockfile 做 SHA-256；不含本报告与 active plan）。本轮 build 为原有 shell；W1 未交付 Player。

## 状态

| 维度 | 本轮结果 |
|---|---|
| Implementation | DONE：typed client、wire decoder、immutable mutation intent、test harness、真实 DTO fixture、本机代理支持 |
| Automated Gate | PASSED，命令/证据见下文 |
| Contract Matrix / Relationship Gate | REQUIRED / PASSED：按 W1 行和继承合同映射；未把 W2 store 或 W3 UI proof 计入 |
| Native environment | READY：既有 `.venv` + Node，显式 Mock/独立临时 SQLite 原生 lifespan proof 通过 |
| LAN environment | 启动条件已核对；实际 LAN IP/监听/手机/API/WS 代理连通 NOT RUN，W1 无产品页面交付要求 |
| Human Gate | N/A：W1 只有 typed client/test 基础机制，没有产品 UI；按手机验收方法不创建调试控制台凑真人 Gate |
| 真实 MPD/NAS | NOT RUN；仅本地 Mock/Pydantic/临时 SQLite，不能证明实际设备或声音/DAC |
| PWA | DEFERRED：未实现 manifest/SW/安装/冷离线壳 |
| Batch 结论 | 当前 W1 范围通过；只关闭 W1，不推进 W2 |

产品 URL / 端口 / 场景 / 启动停止：N/A（W1 无产品 UI 交付）；未留下服务进程。手机型号/系统/浏览器/可达确认：N/A，同上。用户反馈与需复验 H 编号：N/A，W1 没有 H 卡。

## 实际前置及环境

- 开始前 `git status --short` 无输出；分支 `feature/task-8-web-player`。最近提交为 `adf4171`、`36cbd24`、`138fd98`、`e3a15b3`、`8888304`。保留指定 checkout，不创建/切换 worktree；本轮无 commit/push/PR/merge。
- 检查了 AGENTS.override、文档地图、W1 Batch/手机验收方法、Architecture §4.1–4.3/§12、主 Plan 全局/关系矩阵/Task 8、Task 6 snapshot/actual 合同、Task 8 audit 和 backend prerequisite plan，以及相关 Playback/Library/Output/Visual Specs。
- 实际已有 StateService、GET `/api/state`、WS `/api/realtime`、Output REST DTO，以及 control_target/resume 模型/API。preflight state/WS/Output 回归 26 passed。后端前置计划中的“未实施”不作为当前代码证据；W1 fixture 使用现有真实模型，**未声明 P3 完整 Gate 通过**，W4 必须 fresh 核验。
- Python 3.14.4、pytest 9.1.1、Ruff 0.16.9；仅使用既有 `.venv`，未修改 Python 依赖。Node 24.20.0、npm 11.19.0；起始无 web/node_modules/lockfile。
- 新增 exact Vitest 3.2.6、jsdom 26.1.0、Vue Router 4.5.1、Vue Test Utils 2.4.6。npm engines/peer 元数据核对与实际安装/typecheck/build 通过；Vite 实际解析为 7.3.7。原有 dependency range 未改；首次 lockfile 固定完整依赖树。npm 安装产生上游 whatwg-encoding/glob deprecation 提示；未为提示更新无关依赖。
- 原入口已有 `app.state.player` 显式注入及独立 `DATABASE_PATH`；新增 native lifespan test 在启动前注入 MockMPD，使用 pytest tmp_path SQLite，验证 GET、WS envelope 与 REST Output aliases。不依赖未消费的 `MPD_MODE=mock`。
- 既有 dev Compose 的 web environment 显式设置 `API_PROXY_TARGET: http://server:8000`，避免本机默认 loopback 破坏容器入口；仅修改配置，不运行 Docker。Vite dev/preview 统一 `/api` REST/WS 代理，默认 `http://127.0.0.1:8000`，可用 `API_PROXY_TARGET` 配置；保留 LAN host `0.0.0.0`/5173。W3 才准备真实 Player、最小媒体和常驻 LAN 服务。本轮未操作真实音乐、现有 DB、Docker 或系统网络设置。

## RED → GREEN

1. 指定 `same-origin HTTPS uses wss without changing host`：RED 得到 `https://music.example:8443/api/realtime`，期望 `wss://music.example:8443/api/realtime`；实现 protocol 映射后 GREEN。
2. GET/HTTP→ws/204/typed error/network unknown：未实现 GET 时 4 failures；实现网络读取与 decode/error 边界后 GREEN。
3. immutable canonical payload/同对象 key retry/204 mutation/typed conflict：缺失 createIntent 时 3 failures；实现冻结、payload 捕获及 send 后 GREEN。网络重试只由显式 send 触发，零自动重试。
4. 后端 fixture proof：缺 `wire.json` 的断言 RED；以 domain/public Pydantic `model_dump(mode="json", by_alias=True)` 生成后 GREEN。fixture 记录 target 为当前真实 DTO，P3 仍须 W4 重验。
5. wire 正常 REST/WS、legacy additive fallback、Output alias：stub 下 4 failures。最小 parse 成功后，缺 validation 的畸形帧/版本/enum/类型/nullability/target/sequence 等 15 cases RED；完整 decode 后 18 tests GREEN。
6. 同源路径约束、body transport loss、无效 JSON 意图：7 failures RED；拒绝跨源/非 API 路径、区分 SyntaxError 与传输未知、拒绝 NaN/Infinity/undefined/Date/function payload 后 GREEN。
7. 额外 deferred regression 使用真实 client+wire，证明 invalidate 不结束待确认 HTTP receipt；transport/clock 位于 test support，不引入产品 clock/store。

测试工具定位：Vite/esbuild 在 jsdom 中导入会触发 TextEncoder/Uint8Array realm invariant。代理配置测试单独使用 Node 环境；业务 client/wire/mutation 默认仍为 jsdom。TypeScript 将 tests 与 vitest config 纳入检查，曾识别 JSON import enum widening；显式 DTO 边界声明修正后通过。

## 自动 Gate 命令与 fresh 结果

| 命令（仓库根目录） | 结果 |
|---|---|
| `npm --prefix web run test -- --run tests/invariants/client.test.ts -t 'same-origin HTTPS'` | RED → GREEN，1 passed |
| `npm --prefix web run test -- --run tests/invariants/client.test.ts tests/invariants/wire.test.ts tests/invariants/mutation.test.ts` | 40 passed / 3 files |
| `npm --prefix web run test:invariants -- --run` | 40 passed / 3 files |
| `npm --prefix web run test -- --run` | 41 passed / 4 files（含 native proxy config） |
| `.venv/bin/python -m pytest -q server/tests/api/test_web_wire_fixture.py` | 3 passed |
| `.venv/bin/python -m pytest -q server/tests/api/test_web_wire_fixture.py server/tests/api/test_idempotency.py server/tests/api/test_realtime_state.py server/tests/api/test_realtime.py server/tests/invariants/test_output_transport.py` | 32 passed；1 条既有 Starlette TestClient/httpx deprecation warning |
| `.venv/bin/python -m ruff check server/tests/api/test_web_wire_fixture.py` | All checks passed；仅该新文件 import 排序定向 fix |
| `npm --prefix web run typecheck` | exit 0，包括源码及全部新 tests/config |
| `npm --prefix web run build` | exit 0，Vite 7.3.7；11 modules，原 shell build |
| `git diff --check` | 通过；最终状态检查见收尾记录 |

## Contract traceability

不新增或重定义业务合同；本报告映射 active W1 行与既有 authority rows。

| 继承合同 / Spec | 本轮 owner | executable proof / fresh Gate |
|---|---|---|
| typed wire / Architecture §4.1、§12，RT-SNAPSHOT/RT-ACTUAL 表示 | types/api.ts、services/wire.ts | wire.test.ts REST→真实 client→decoder 与 WS 同字段；Python fixture/原生 GET+WS proof；40 Web + 3 Python passed |
| 同源 REST/WS / Architecture §4.1 | services/api.ts、vite.config.ts | client.test.ts HTTP/HTTPS/host/path；proxy.test.ts dev/preview 共用本机 proxy；41 Web passed |
| mutation receipt/retry / Architecture §4.2，TX-IDEMP | services/api.ts、types/api.ts | mutation.test.ts 同 key+method/path/canonical body、typed error、204、deferred HTTP 非 WS ACK；后端 idempotency regression；40 Web + 32 backend passed |
| current-target additive DTO / Architecture §4.2.1 | types/api.ts、wire.ts、真实 DTO fixture | legacy 缺 target→null、坏 target 拒绝；**不是 P3 Gate 或 resume/seek UI proof** |
| Output alias/nullability / Output §6–8、实际 system/realtime DTO | types/api.ts、wire.ts | failure request 与 confirmed ACTIVE 分开、nested camelCase→snake_case、未知参数保留 null；fixture+Output regressions |

W2 authority/reconnect/cache 的关系 proof 留在 W2；W1 没有 stores/canonical commit。W3–W6 Player/clock/actions/lyrics/Output UI 及手机 Gate 未开始。

## 审查与收尾

独立只读 reviewer 已完成（初验 36 Web tests/typecheck/diff-check 独立通过），无 Critical、无 declined-to-judge 项；指出容器代理回归（Important）与整数 DTO 接受小数（Minor）。整数 gap 重新分级为 Important：已宣称 validated 的身份/位置不应接受实际 DTO 禁止的值。只做一次修复 pass：

- 实际解析 dev Compose environment 的测试因缺 proxy target RED；补两行环境接线后精确测试 GREEN。未创建/启动/停止/修改容器。
- 四个 fractional identity/position/Song/Output cases RED；整数 validator GREEN。仍允许 Played 负位置和大整数纳秒 timestamp，不误套安全整数约束到媒体时间字段。
- 本轮 W1-A02 重跑 targeted 40、invariant 40、full Web 41、Python fixture/config 3、相关后端 32、Ruff/typecheck/build，全部通过。无遗留 review blocker/minor。

最终 actual diff/stat/status 已复核；`git diff --check` 通过，新文件也做 no-index whitespace check。本轮仅有 W1 文件与 acceptance/状态更新；dist/node_modules/.superpowers evidence ignored，AGENTS.override/.venv/DB 不进入改动范围。

下一 Batch 前置：W1 类型、decoder、immutable client、injectable transport/clock 与测试脚本已交付；满足 W2 的 W1 前置。没有启动 W2，不宣称 Task 8 整体完成。W4 的 fresh P3 Gate、W3 起实际 LAN/手机验收和真实 MPD/NAS 均不能由本轮代替。


### 执行裁定与环境记录

- 按用户指定 checkout/已有 feature branch 执行并保留所有外部修改，覆盖 skill 的额外 worktree 设置；代价是无法隔离其他窗口的并发写入。
- 按用户要求不 commit、不删除本轮 evidence、不进入 W2；保留未提交审查结果。
- 增加 test support、Node 环境 proxy config test 和 tsconfig tests/config include，属于 W1 必要测试接线；避免 jsdom/Vite 的 realm 冲突，未增加产品行为。
- 新依赖 exact 版本按实际 engines/peer 选择，原有版本 range 未改；首次 lock 固定当前解析树，后续以该 lock 重现。
- 整数 gap 提升为 Important 并修复；dev Compose environment 是保持既有代理能力的最小接线，均非后续 Batch 或 Task10 扩展。
- 一次元数据检查误用 `npm exec -- node`，npm 将 Node26 解到临时 exec cache，随后因 cwd 错误找不到 lockfile而退出；改用已有 `node` 直接检查成功。PATH Node 仍为 24.20.0，未改系统 Node、项目依赖或 Python 环境。全部成功验证仍使用原有 Node24。

本轮日志在 ignored `.superpowers/sdd/2026-10-09-task-8-web-batch-plan/`，不是独立验收应用。W1-A01 初验 35 invariants/36 full Web/2 fixture/31 backend；W1-A02 是审查修复后的最终结果。没有必要真人项等待反馈，W1 blocker = 0。
