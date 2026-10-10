# Task 8 Web Batch W2 acceptance

Task / Batch / 轮次 / 日期（Asia/Shanghai）：Task 8 / W2 / W2-A01 / 2026-10-09 18:36–18:40。
代码标识：`feature/task-8-web-player`，BASE=HEAD `adf4171`，本轮 W2 未提交源码；W2-A01 表示审查修复后的代码及 fresh 验证，不仅使用 HEAD 标识。

| 状态维度 | 结论 |
|---|---|
| Implementation | DONE，限 canonical store / realtime / resource cache / Library、Playlist 薄包装 |
| Automated Gate | PASSED，targeted / relationship / inherited regression / typecheck / build |
| Contract Matrix / Relationship Gate | REQUIRED / PASSED，traceability 见下表 |
| Native environment | READY，既有 Node 24.20.0 / npm 11.19.0 / `.venv` Python 3.14.4 / pytest 9.1.1 / Ruff 0.16.9；未修改依赖 |
| LAN environment | N/A，W2 无产品页面；未启动 LAN 服务或核验手机 URL/API/WS |
| Human Gate | N/A，计划及手机验收方法明确 W1/W2 是 typed client/store 基础机制，没有产品 UI，不建设调试验收页 |
| 真实 MPD/NAS | NOT RUN，没有访问外部设备；网络/时间测试替身不证明设备精度/声音/DAC |
| PWA | DEFERRED，不计入本轮 Gate |
| Task-level 手机 Web acceptance | NOT RUN；W3–W6 未开始 |

产品 URL / 端口 / 场景 / 启动停止方法、手机型号/系统/浏览器、手机可达确认及 H 编号：均 N/A（W2 无产品 UI）。无用户手机反馈待处理。

## 开始前证据与范围

读取 AGENTS.override、README、Web Batch Plan、手机验收方法、主计划 Task 8/全局 Gate/依赖矩阵、Architecture §4.1–4.3/§12、Task 6 消费合同、Task 8 audit 和后端控制前置计划。以实际代码和 fresh tests 核验 W1。

开始 Git 状态：feature 分支；最近提交为 adf4171、36cbd24、138fd98、e3a15b3、8888304。已存在未提交 W1 plan、Compose proxy、package/lock、tsconfig/Vite/Vitest、services/api+wire、types、tests 和 W1 acceptance。全部保留，没有 reset/restore/clean/stash，没有改后端实现或 W1 源码/依赖/lockfile。

W1 fresh 前置：client/wire/mutation 40 passed；Python wire fixture 3 passed。真实 API client、DTO decoder、可注入 transport、测试 harness 均存在。P3 不是 W2 前置；本轮不判定其 Gate，W4 仍必须依当前代码重新核验。

新增：`web/src/services/realtime.ts`、`web/src/stores/{player,resourceCache,library,playlists}.ts`、`web/tests/invariants/{realtime,resource-cache}.test.ts`。必要文档仅更新 active plan 的 W2 状态/实际接口及本报告。App.vue/main.ts 未变；无第二个页面 store，没有 W3 UI、Task 9 页面或 PWA 实施。

## RED → GREEN 与审查修复

- 指定 late GET：缺 realtime/store import RED；最小代次隔离 GREEN。deferred GET 在确认已发出后关闭旧 socket，再接收新 initial；迟到结果被拒绝。
- 实时新增场景：8 个 RED，暴露同 epoch 倒退、跨 epoch 未禁写、缺水位/重试、坏首帧/首帧 invalidate/socket error 未 fail closed、重连退避未递增；实现后 GREEN。same epoch 旧 GET、duplicate sequence 在首个最小实现后已 GREEN，如实保留回归，不声称另一次 RED。
- 读取开始于 microtask；测试最初在请求发出前切换连接而超时。定位为 fixture 顺序后增加已发请求 barrier，不延长 timeout、不削弱断言。same epoch 旧 GET 返回 sequence=99 仍不能覆盖新 baseline=5。
- 缓存缺文件 RED，随后未实现 read 的五个场景全部 RED；实现双依赖、epoch/generation barrier、单飞及失败保留后 GREEN。
- 独立只读 reviewer 发现相同 marker 被误视为 explicit invalidate（Important）、同步 loader throw 毒化后续单飞（Minor）。后者按实际重试影响提升 Important，一次修复 pass 完成两项。
- 修复前分别运行 `playlist-only snapshot`、`synchronous loader`、`covering snapshot` 精确 selector，均 RED；区分 marker 同步与显式 force，将同步 throw 变为 await rejection后，三个 selector 全 GREEN。
- reviewer 无 Critical、无 declined-to-judge；修复经精确测试及完整 Web suite 验证，无遗留 finding/deferred minor，未重复 dispatch reviewer。

## Fresh 自动 Gate

命令均从仓库根执行。未使用系统 Python、Docker、真实 MPD/NAS；未改 `.venv` 或 Python 依赖。

| 命令 | 本轮结果 |
|---|---|
| `npm --prefix web run test -- --run tests/invariants/realtime.test.ts -t 'late GET'` | RED → GREEN |
| `npm --prefix web run test -- --run tests/invariants/resource-cache.test.ts -t 'playlist-only snapshot'` | RED → GREEN，1 passed |
| `npm --prefix web run test -- --run tests/invariants/resource-cache.test.ts -t 'synchronous loader'` | RED → GREEN，1 passed |
| `npm --prefix web run test -- --run tests/invariants/resource-cache.test.ts -t 'covering snapshot'` | RED → GREEN，1 passed |
| `npm --prefix web run test -- --run tests/invariants/realtime.test.ts tests/invariants/resource-cache.test.ts tests/invariants/mutation.test.ts` | 35 passed：15 realtime + 11 cache + 9 mutation |
| `npm --prefix web run test:invariants -- --run` | 66 passed / 5 files |
| `npm --prefix web run test -- --run` | 67 passed / 6 files |
| `npm --prefix web run typecheck` | exit 0，含全部新增源码/tests |
| `npm --prefix web run build` | exit 0，Vite 7.3.7；仍为原 shell 的 11 modules，W2 未接入 UI；新增模块由 typecheck/关系测试验证 |
| `.venv/bin/python -m pytest -q server/tests/api/test_web_wire_fixture.py` | 3 passed，W1 前置 |
| `.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_recovery.py server/tests/api/test_realtime.py server/tests/api/test_idempotency.py` | 33 passed |
| `.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_delivery.py server/tests/invariants/test_realtime_observation.py` | 28 passed |
| `git diff --check` + 新文件 no-index whitespace check | PASSED；实际 diff/stat/status 均审查 |

Python 各组只有既有 Starlette/httpx TestClient deprecation warning，无代码/测试/环境失败。未改 Python 文件，无本轮 Ruff 范围。最终 Web 日志在 ignored `.superpowers/sdd/2026-10-09-task-8-web-batch-plan/w2-{targeted,invariants,web-full}.log`；本报告为唯一 W2 acceptance。

## Contract traceability 与实际接口

无新增/修改业务合同。继承 rows 的 Preconditions、Authorities、Delta、Unchanged、Confirmation、History/Event、Transaction、Failure/Rollback、Retry/Idempotency、Observable、Proof 仍归 active plan/Spec；本轮只实现客户端消费。

| Contract / Spec | 实际 owner | executable proof / fresh evidence |
|---|---|---|
| Architecture §4.1、§12.2；RT-SNAPSHOT/CONNECT/RECOVER-001 | player.ts + realtime.ts + W1 api/wire | late GET、同 epoch 新连接、跨 epoch GET、initial 禁倒退、只读 GET/断线禁写；15 realtime passed + 后端 snapshot/recovery/API 回归 |
| Architecture §4.1、§12.2；RT-DELIVERY/RECOVER-001 | realtime 单飞/最高水位/read retry | in-flight higher invalidation、失败 retry、未覆盖不得完成义务、duplicate/old sequence；只发 GET，不重放 mutation；delivery 回归通过 |
| Architecture §4.1 resource contract | resourceCache.ts、library.ts、playlists.ts | 双 revision、旧 epoch/query generation、迟到 failure、stale/error、显式 retry、matching snapshot 不误失效；11 cache passed |
| Architecture §4.2；TX-IDEMP unchanged | 继承 api.ts immutable intent | mutation 9 passed、后端 idempotency 回归；realtime/cache 不调用 send/createIntent |
| RT-OBSERVE-001 的只读完整表示 | canonical snapshot 不采样/推导/部分提交 | 继承 observation 回归通过；不是 Player 展示时钟证明 |

新增接口已同步 active plan：beginConnection/invalidate/acceptInitial/acceptRefresh 归实时 owner；snapshot 深只读，marker 独立。GET 无法建立 writable；不同 epoch 触发新 socket 确认。clock 的 setTimeout/clearTimeout/random 可注入；读失败和连接失败采用 0.5/1/2/4/8 秒基数和最多 20% jitter，initial 后重置连接退避，stop 取消 timer/listener并隔离迟到回调。

Cache 以 key 分隔查询，记录每个请求 generation；相关 marker 前进使旧结果不能写 fresh，仍需要的 pending read 重读。无 pending 资源保留 stale，下一次 read 重读；失败保留 error/最后 data，显式 read 可重试，无资源后台轮询。Library 依赖 library，Playlist/Favorites 依赖 playlist+library；同步 watcher 在通知到达时推进 cache，stop 释放 watcher。明确失效使用可选 `{force:true}`，自动相同 marker 是 no-op。

## 裁定、收尾与下一 Batch

- 按用户 checkout 执行，不另建 worktree，保留外部修改；代价是无额外并发隔离。
- 不 commit、不 push/PR/merge、不删除 evidence、不进入 W3，遵循明确边界；变更保持未提交供审查。
- marker/entry/watch-stop 辅助接口和 force option 为 W2 最小接线，实际接口回写原 plan；若区分错误会影响 freshness，由上述 invariant 保护。
- 同步 throw 提升 Important 后修复，否则合法 loader 的重试会永久复用失败 promise；精确 RED→GREEN及全套 GREEN证明。

最终实际 diff/check/stat/status 已核对；只新增上述 W2 文件和对应 plan/acceptance。既有 W1 Compose/package/lock/tsconfig/Vite/wire/types/backend fixture 保留；dist/node_modules/证据 ignored，无 DB/环境文件变更。

W2 blocker = 0，当前范围通过。满足 W3 的 W1→W2 canonical store/realtime 前置；W3 未开始。W4 必须 fresh 核验 P3，本报告不能代替。Task 8 整体未验收；LAN/真人 Player、真实 MPD/NAS及 PWA 状态分别保留如上。
