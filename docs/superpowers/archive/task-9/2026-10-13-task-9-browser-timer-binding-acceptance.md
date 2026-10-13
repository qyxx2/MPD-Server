# Task 9 — Browser timer binding corrective

2026-10-13（Asia/Shanghai）。**LOCAL PASSED；本记录保存提交前证据，远程交付由随后新 SHA 的实际 CI 证明。**

## 触发、根因与范围

用户已部署 `7a2b8fb67caba7eec2e89c3fe74caa38c5535842` 镜像后报告 Web 无法连接。只读访问实际页面发现 `TypeError: Illegal invocation`，稳定重载复现；堆栈 `index-BINlye1z.js:2:77627` 指向 realtime.connect 的 initial clock.setTimeout。与此同时 health/status/Library REST 正常，MPD connected，startup SYNCED、406 目标 confirmed、0 failed；因此不能把页面只读误判为 MPD 或数据库故障。

真实 App composition root 将原生 setTimeout/clearTimeout 直接放在 clock 对象上。realtime 以 clock 方法方式调用时 receiver 变为 clock，而浏览器要求 Window/无 receiver。C4 新增 initial deadline 在创建 socket 前就触发该边界，启动因此失败。原 fake timer/jsdom 用例及 shell helper 绕过真实 App 装配，未捕捉浏览器 receiver 限制。

最小生产修改仅 `web/src/App.vue`：timer 用箭头函数包装，调用原生全局函数；不修改 realtime/api 的预算、退避、generation、only-initial writable 规则，不修改后端、workflow、Docker、数据卷、数据库或依赖。用户明确授权修复、在原分支 commit/push 并启动 CI；未授权本轮自动部署，不操作播放或 NAS 配置。

起始分支 `fix/task-9-startup-library-reconciliation`，完整 HEAD `7a2b8fb67caba7eec2e89c3fe74caa38c5535842`，起始工作区干净。使用原 Node 依赖和现有 .venv；不安装/更新环境、不运行 Docker、不读写用户数据库。当前 dirty 是 App.vue、新永久测试及本验收/README 入口增量；HEAD 尚不含本轮修复。

## 永久 RED→GREEN

`web/tests/invariants/app-startup.test.ts::real App starts, reconnects and stops with browser timer receivers` 挂载真实 App、真实 router/AppShell/realtime/store，只替换外部 fetch/socket；timer 以 fake scheduler 控制时间，同时保留浏览器式 receiver 校验。这样测试旧生产装配，而不是复制待修复的 clock。测试证明：启动确实创建 socket，完整 initial 后可写；断线转只读并关闭旧 socket，500ms 原退避后重新创建；新 initial 未到前保持只读；unmount 清 pending initial deadline/全部 timers，无启动或清理异常。

生产修改前：1 failed，TypeError Illegal invocation，栈为 receiver guard → clock.setTimeout → realtime.connect:44 → realtime.start → AppShell mounted。没有 import/collection/fixture 缺失；与真实浏览器同一调用链。生产包装后精确节点 1 passed。本轮没有 skip/xfail、删除或弱化旧测试，也没有延长 10,000ms 预算。

精确命令：

```bash
npm --prefix web run test -- --run tests/invariants/app-startup.test.ts -t 'real App starts, reconnects and stops with browser timer receivers' --maxWorkers=1 --minWorkers=1
```

原始 RED/GREEN 日志 `/tmp/mpd-browser-timer-evidence/red.log`、`green.log`；新 test 与本地 receiver proof 永久进入仓库，不依赖临时日志。

## 真实浏览器生产 build RED→GREEN

现有 .venv 的临时 Python HTTP/WebSocket fixture 只在 127.0.0.1:18081 提供 web/dist 与既有 wire.json initial/state/favorites；不连接真实 MPD，不创建数据库，没有 mutation handler。fixture runner `/tmp/mpd-browser-timer-evidence/browser-fixture.py`，服务日志 `/tmp/mpd-browser-timer-fixture.log`。通过 Codex browser 的真实浏览器运行生产 bundle，未替换浏览器原生 timers。

- RED：旧生产 bundle `index-BINlye1z.js` 在同一本地 fixture 复现 Illegal invocation，全部播放控制禁用、未创建 WS。
- GREEN：新 production build `index-DIeVDtTZ.js`，WebSocket 101/完整 initial；页面显示“长标题 / Song A”，继续播放和下一首启用，`getByRole(button, 继续播放).isEnabled()` 为 true，新 bundle 的 error logs 为空。没有点击播放。
- 首次 GREEN 尝试仍复用旧入口缓存，console 实际加载的是 BINlye1z；不是新源码失败。检查当前 dist HTML 与 HTTP 响应确定新 asset 后，用 `/?build=index-DIeVDtTZ` 导航确认新 bundle；旧导航日志仍保留，未把它计作 GREEN。正式重新部署后也须刷新入口以加载新资源。
- fixture 自带 OUTPUT_FAILED 示例活动和旧媒体观察字段，不作为实际 DAC/播放验收。这里只验真实浏览器启动/initial/控制解锁，不关闭真实设备 Gate。

## Fresh 自动验证

顺序：新增 exact + 原 C4 全部 17 exact → 直接六文件 → 原九文件关系集加真实 App 文件 → 完整 Web → typecheck/build/Ruff。全部 Vitest 单 worker。后端源码与前一已验证提交完全相同，复用此前 1660 项本地及同 SHA CI GREEN；没有声称本轮本地重跑 backend。随后新 SHA CI 必须再完整执行 backend 和 Web。

| Gate | exit | 结果 | wall seconds |
|---|---|---|---|
| exact-app | 0 | Test Files  1 passed (1); Tests  1 passed (1); Duration  3.73s (transform 2.00s, setup 74ms, collect 2.58s, tests 119ms, environment 479ms, prepare 128ms) | 4.93 |
| exact-c4-00 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.29s (transform 308ms, setup 47ms, collect 385ms, tests 17ms, environment 450ms, prepare 101ms) | 2.19 |
| exact-c4-01 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.36s (transform 328ms, setup 57ms, collect 388ms, tests 23ms, environment 480ms, prepare 126ms) | 2.26 |
| exact-c4-02 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.25s (transform 318ms, setup 56ms, collect 384ms, tests 25ms, environment 416ms, prepare 98ms) | 2.12 |
| exact-c4-03 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.75s (transform 462ms, setup 63ms, collect 564ms, tests 36ms, environment 559ms, prepare 129ms) | 2.92 |
| exact-c4-04 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.80s (transform 502ms, setup 64ms, collect 626ms, tests 35ms, environment 501ms, prepare 130ms) | 3.0 |
| exact-c4-05 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.72s (transform 460ms, setup 67ms, collect 568ms, tests 25ms, environment 530ms, prepare 131ms) | 2.97 |
| exact-c4-06 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.67s (transform 486ms, setup 74ms, collect 576ms, tests 24ms, environment 525ms, prepare 129ms) | 2.83 |
| exact-c4-07 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.76s (transform 517ms, setup 69ms, collect 653ms, tests 19ms, environment 506ms, prepare 125ms) | 3.02 |
| exact-c4-08 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.67s (transform 471ms, setup 78ms, collect 576ms, tests 16ms, environment 486ms, prepare 122ms) | 2.86 |
| exact-c4-09 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.78s (transform 490ms, setup 76ms, collect 635ms, tests 20ms, environment 490ms, prepare 144ms) | 2.99 |
| exact-c4-10 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.77s (transform 478ms, setup 73ms, collect 624ms, tests 23ms, environment 506ms, prepare 124ms) | 2.92 |
| exact-c4-11 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.66s (transform 454ms, setup 62ms, collect 592ms, tests 22ms, environment 516ms, prepare 117ms) | 2.91 |
| exact-c4-12 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.69s (transform 483ms, setup 81ms, collect 607ms, tests 23ms, environment 509ms, prepare 127ms) | 2.92 |
| exact-c4-13 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.91s (transform 572ms, setup 62ms, collect 600ms, tests 251ms, environment 518ms, prepare 133ms) | 3.11 |
| exact-c4-14 | 0 | Test Files  1 passed (1); Tests  1 passed  /  14 skipped (15); Duration  1.30s (transform 321ms, setup 46ms, collect 417ms, tests 22ms, environment 455ms, prepare 101ms) | 2.39 |
| exact-c4-15 | 0 | Test Files  1 passed (1); Tests  1 passed  /  11 skipped (12); Duration  3.29s (transform 1.74s, setup 44ms, collect 2.26s, tests 147ms, environment 481ms, prepare 113ms) | 4.32 |
| exact-c4-16 | 0 | Test Files  1 passed (1); Tests  1 passed  /  11 skipped (12); Duration  3.33s (transform 1.75s, setup 40ms, collect 2.27s, tests 123ms, environment 481ms, prepare 102ms) | 4.47 |
| direct | 0 | Test Files  6 passed (6); Tests  62 passed (62); Duration  9.50s (transform 2.13s, setup 143ms, collect 3.41s, tests 927ms, environment 2.88s, prepare 597ms) | 10.63 |
| relationships | 0 | Test Files  10 passed (10); Tests  93 passed (93); Duration  14.75s (transform 2.24s, setup 111ms, collect 4.35s, tests 1.76s, environment 4.59s, prepare 953ms) | 15.79 |
| full | 0 | Test Files  31 passed (31); Tests  317 passed (317); Duration  55.56s (transform 4.40s, setup 451ms, collect 13.11s, tests 13.37s, environment 14.92s, prepare 3.18s) | 56.84 |
| typecheck | 0 | 成功 | 14.11 |
| build | 0 | ✓ built in 2.47s | 3.5 |
| ruff | 0 | All checks passed! | 0.31 |

## 收尾与交付边界

作者自审检查 App 装配、receiver、initial/clear/reconnect/unmount、测试隔离、实际 diff；独立 review NOT RUN，不算审查 PASS。git diff --check、stat/status 和新增未跟踪文件 whitespace 检查均无问题；本轮只有上述四个范围文件，无环境/依赖/生成 dist、临时 fixture 或数据库入 Git。

提交/push 后必须核对本地提交、远端 HEAD、run.head_sha 一致，validate/image 均成功，以及镜像 sha 标签/digest/linux/amd64+linux/arm64。具体新提交 SHA 与 CI 结果由该次交付结果报告，不用旧 7a2b8fb 镜像抵扣。此提交前记录不声称远程已完成；NAS 新镜像重新部署和真实设备复验仍未运行。历史 Task 9 人工 Gate 不自动关闭。

## 完整命令账本

- `npm --prefix web run test -- --run tests/invariants/app-startup.test.ts -t 'real App starts, reconnects and stops with browser timer receivers' --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-app.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t initial_snapshot_timeout_reports_and_reconnects --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-00.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t get_timeout_ends_loading_and_retries --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-01.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t body_timeout_and_late_response_cannot_restore_baseline --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-02.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t success_stop_and_reconnect_clear_timeout_timers --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-03.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t get_after_timeout_does_not_enable_mutations --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-04.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t never_settling_abort_ignored_fetch_uses_one_total_budget --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-05.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t never_settling_abort_ignored_body_uses_one_total_budget --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-06.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t abort_rejection_cannot_replace_typed_read_timeout --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-07.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t terminal_network_failure_clears_read_timer --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-08.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t terminal_json_failure_clears_read_timer --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-09.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t terminal_http_failure_clears_read_timer --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-10.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t terminal_decode_failure_clears_read_timer --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-11.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t injected_budgets_use_fixture_clock_and_dispose_old_initial --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-12.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t resource_timeout_ends_loading_and_uses_existing_notice_read --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-13.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t generation_change_cannot_restart_a_timed_out_resource_budget --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-14.log`。

- `npm --prefix web run test -- --run tests/invariants/global-notices.test.ts -t top_timeout_INITIAL_SNAPSHOT_TIMEOUT_keeps_existing_read_recovery --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-15.log`。

- `npm --prefix web run test -- --run tests/invariants/global-notices.test.ts -t top_timeout_READ_TIMEOUT_keeps_existing_read_recovery --maxWorkers=1 --minWorkers=1` → exit 0；日志 `exact-c4-16.log`。

- `npm --prefix web run test -- --run tests/invariants/app-startup.test.ts tests/invariants/startup-readiness.test.ts tests/invariants/realtime.test.ts tests/invariants/client.test.ts tests/invariants/resource-cache.test.ts tests/invariants/global-notices.test.ts --maxWorkers=1 --minWorkers=1` → exit 0；日志 `direct.log`。

- `npm --prefix web run test -- --run tests/invariants/app-startup.test.ts tests/invariants/startup-readiness.test.ts tests/invariants/realtime.test.ts tests/invariants/resource-cache.test.ts tests/invariants/wire.test.ts tests/invariants/mutation.test.ts tests/invariants/global-notices.test.ts tests/invariants/library-sync.test.ts tests/invariants/shell-navigation.test.ts tests/invariants/task9-relationships.test.ts --maxWorkers=1 --minWorkers=1` → exit 0；日志 `relationships.log`。

- `npm --prefix web run test -- --run --maxWorkers=1 --minWorkers=1` → exit 0；日志 `full.log`。

- `npm --prefix web run typecheck` → exit 0；日志 `typecheck.log`。

- `npm --prefix web run build` → exit 0；日志 `build.log`。

- `.venv/bin/python -m ruff check server/app server/tests` → exit 0；日志 `ruff.log`。
