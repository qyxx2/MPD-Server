# Task 9 Startup Corrective — C5 本地 acceptance

日期：2026-10-12（Asia/Shanghai）。**C5 LOCAL ACCEPTANCE PASSED；远程容器交付未完成；手机/真实设备人工验收 NOT RUN。**

本记录只关闭 C5 本地配置与自动验证部分。没有 commit/push/PR/merge、workflow_dispatch、镜像发布或部署；Task 9 历史人工 Gate 保持原状态。用户本轮授权只完成 C5 本地步骤，不补做 C1–C4，不允许远程交付。实现判断以当前源码、永久测试、原始日志和本轮 fresh 输出为依据。

## 权威输入、Git 与环境

- [Corrective spec](2026-10-12-task-9-startup-library-reconciliation-design.md)、[Batch plan](../plans/2026-10-12-task-9-startup-library-reconciliation-batch-plan.md)、[历史 root-cause / C0–C4 原始证据索引](../plans/2026-10-12-task-9-startup-root-cause-evidence.md)。前两份历史草案页头仍是 DRAFT/NOT STARTED，已与实际实现不符；本轮按用户明确的 C5 授权和源码证据裁定，不越范围改计划/spec。
- archive 布局静态核对：已有 `docs/superpowers/archive/task-9/*-acceptance.md`；沿用同一路径约定，无替代布局。
- 起始/结束分支：`fix/task-9-startup-library-reconciliation`。
- 起始/结束完整 HEAD：`098d6eaea81495d1686a09f9e0ee68768610ed7e`，未生成修复提交。C1–C4 和 C5 当前内容均有尚未提交的 dirty 增量，HEAD 不是修复 SHA。旧 HEAD 的 CI/镜像不能证明当前修复。
- 起始 dirty：32 tracked modified + 11 untracked，逐文件列于下方。以所有 tracked/untracked 文件 SHA256 起始快照对比；本轮只改 workflow、README 当前 corrective 段，新增本 acceptance。其余起始文件逐字节保留，README 的既有 dirty 内容也保留在该段外。
- Linux aarch64；现有 `.venv` Python 3.14.4 / pytest 9.1.1 / Ruff 0.16.9；Node v24.20.0 / npm 11.19.0 / 仓库 Vitest 3.2.6。已读 `server/requirements.txt` 和 `web/package.json`；不安装/更新依赖、不创建/修改环境。
- 环境验证：`test -x .venv/bin/python`、`.venv/bin/python --version`、`.venv/bin/python -m pytest --version`、`.venv/bin/python -m ruff --version` 均 exit 0；Node/npm 与 `uname -sm` 只读核对。
- 每个 backend pytest 进程拥有不同自有临时 `config/`、`music/`、`state.db`，外层统一 `APP_ENV=development MPD_MODE=mock`，显式 `-p server.tests.support.playback`。两项 adapter 装配永久测试内部选择 real 分支并注入 MockMPD，未接触真实服务。没有操作用户数据库、MPD/NAS/DAC 或本地 Docker。
- 所有命令从 repository root 执行。Web 复用现有 node_modules；全部 Vitest 单 worker。build 产物 dist 保持 Git ignored。

起始状态（完整）：

```text
 M docs/superpowers/README.md
 M docs/superpowers/specs/2026-09-24-library-playlist-tag-search-design-2-1.md
 M docs/superpowers/specs/2026-09-25-system-and-development-architecture-design.md
 M server/app/config.py
 M server/app/models/library.py
 M server/app/player/music_uri.py
 M server/app/repositories/library_repository.py
 M server/app/repositories/migrations.py
 M server/app/services/library_change_detector.py
 M server/app/services/library_runtime.py
 M server/app/services/library_scanner.py
 M server/app/services/library_sync_service.py
 M server/tests/api/test_mpd_connection.py
 M server/tests/invariants/test_library_sync.py
 M server/tests/invariants/test_library_sync_wire.py
 M server/tests/invariants/test_realtime_history.py
 M server/tests/invariants/test_realtime_library.py
 M server/tests/invariants/test_realtime_observer_lifecycle.py
 M server/tests/invariants/test_realtime_playlist.py
 M server/tests/invariants/test_realtime_recovery.py
 M server/tests/invariants/test_realtime_snapshot.py
 M server/tests/repositories/test_library_reconciliation.py
 M server/tests/repositories/test_task3_batch4.py
 M server/tests/services/test_library_scanner.py
 M server/tests/services/test_library_sync_service.py
 M server/tests/test_config.py
 M web/src/runtime/playerSession.ts
 M web/src/services/api.ts
 M web/src/services/realtime.ts
 M web/src/stores/resourceCache.ts
 M web/tests/invariants/client.test.ts
 M web/tests/invariants/global-notices.test.ts
?? docs/superpowers/plans/2026-10-12-task-9-startup-library-reconciliation-batch-plan.md
?? docs/superpowers/plans/2026-10-12-task-9-startup-root-cause-evidence.md
?? docs/superpowers/specs/2026-10-12-task-9-startup-library-reconciliation-design.md
?? server/app/models/library_scan.py
?? server/app/services/library_scan_prepare.py
?? server/tests/api/test_startup_readiness.py
?? server/tests/invariants/test_startup_library_reconciliation.py
?? server/tests/repositories/test_library_scan_commit.py
?? server/tests/services/test_library_scan_prepare.py
?? server/tests/services/test_startup_sync_corrective.py
?? web/tests/invariants/startup-readiness.test.ts
```

## C4 前置门与复用裁定

**C4 prerequisite PASSED。** C1–C4 实现和 C0 十项永久证明在当前源码中存在；本轮精确→直接文件→完整关系→完整 suite 全绿。该同一轮最终源码结果同时充当前置门和 C5 acceptance，不在只改文档/workflow 后无必要重复同一集合。

已实际核对历史 C3 release 95 exact、22 个直接文件、Batch 完整 backend 关系集与完整 backend 输出；C4 gate 原始 backend 1660 passed / 127.67s，C4 原三个行为 RED、新永久测试、final exact 17、直接 61/5、关系 92/9、完整 Web 316/30、typecheck/build/Ruff 的日志存在。C4 起始 backend source-hashes 的 214 个文件与当前完全相同。本轮再执行更完整的 fresh gate，未用历史结果抵扣本轮。

源码与永久测试核对：

| Batch | 实际实现 | 当前永久证明（下方逐节点记录 fresh 输出） |
|---|---|---|
| C1 | `models/library.py` observed/SidecarSignature；`models/library_scan.py` immutable baseline；`repositories/migrations.py` v5；`library_repository.py` baseline、observed 与 sidecar 原子提交 | `test_library_scan_commit.py` 全部参数项；`test_library_reconciliation.py` v1/v4→v5、引用/absent/unknown、rollback/cancel、非法签名 |
| C2 | `library_scan_prepare.py` worker 差异、inventory/稳定性/根安全/坏路径；`library_scanner.py` prepare/precheck/commit/rebase、outer 原 baseline | `test_library_scan_prepare.py` 全部；mount 两参数；outer rollback/cancel/restore/batch、joint playlist/snapshot、metadata/lyrics 安全 |
| C3 | config 无根可读性 I/O、mapper 首次 resolve；runtime 单 owner；detector seed 后原间隔；sync 按需 update/精确确认、accepted/unknown retry、失败路径与旧 absence 合并 | startup API/invariants 与 `test_startup_sync_corrective.py` 全部；adapter、wire、realtime/API/logging 必要回归 |
| C4 | `api.ts` GET 独立 deadline race+abort；`realtime.ts` initial/flight 清理与禁写；`playerSession.ts` 原活动明确超时；`resourceCache.ts` 旧 generation timeout settle | startup-readiness 15 项；顶部 notices 2 参数；client AbortSignal 装配；原 realtime/cache/wire/mutation 等关系 |

GET 与 initial 默认均 **10,000ms**；GET 同一 deadline 包含 fetch/body/解码，无重新启动 body 预算。底层忽略 abort 仍在 deadline settle；typed timeout 先 reject 再 abort，finally 清理 timer/cancel listener。initial 成功/失败、stop/reconnect 清 timer；GET stop/reconnect 取消 flight。迟到结果按 generation/epoch/revision 拒绝，成功 GET 仅恢复只读；完整合法新 initial 才恢复写权限。未延长预算或修改 mutation unknown/key。

资源缓存裁定：只有旧 generation 的 typed READ_TIMEOUT 向原调用者 reject，防止自动发起下一读取使原 Promise 无界；不投影过时数据/错误，其它旧响应/普通失败保持原行为。原 C0 资源 fixture 的第二 socket initial 与 GET 同时超时，第二次既有 backoff 是 1,000ms，因此仅 fixture 等待 500→1,000ms；原 expect 保留、读取预算仍 10,000ms、生产退避未改。首轮 client RequestInit 缺 signal 和该 fixture 时序失败是装配问题，不算业务 RED。

## C0 十项合同 traceability

简称 I=`server/tests/invariants/test_startup_library_reconciliation.py`，A=`server/tests/api/test_startup_readiness.py`，P=`server/tests/services/test_library_scan_prepare.py`，C=`server/tests/repositories/test_library_scan_commit.py`，W=`web/tests/invariants/startup-readiness.test.ts`。参数化括号列出全部项，fresh 逐节点无漏项。

| C0 用户项 / 合同 | 永久证明 | 可核对的历史行为失败 / 当前结果 |
|---|---|---|
| 1 / LIB-STARTUP-RECONCILE-001 | I::test_persisted_second_start_skips_parse_and_hash | C0 exact-backend-01：二次真实 runtime parse/hash (2,2)≠(0,0)；当前 GREEN |
| 2 / LIB-WEB-READY-001 | A::test_http_ws_and_library_read_during_startup_prepare；root validation、startup failure 补充 | C0 exact-backend-19：barrier 下 state/library/ws 超过 1 秒；当前 GREEN |
| 3 / LIB-SCAN-TXN-001 | P::test_prepare_releases_database_lock；test_slow_media_io_runs_without_transaction[parse/hash] | C0 20/21/22：独立 DB 完成 0≠2、真实媒体 I/O 阻 event loop；当前 GREEN |
| 4 / LIB-MPD-SYNC-001 | I::test_unchanged_consistent_startup_does_not_update | C0 02：一致 URI update 1≠0；当前 GREEN |
| 5 / LIB-MPD-SYNC-001 | I::test_inconsistent_startup_updates_once_then_confirms | C0 03：update=1 但缺 precheck；当前 GREEN |
| 6 / LIB-STARTUP-RECONCILE-001 | I::test_reconcile_only_related_paths[add/modify/delete/move/lrc_add/lrc_modify/lrc_delete] | C0 04–10：重读无关音频；当前七项 GREEN，引用/身份/fallback 原断言保留 |
| 7 / LIB-SCAN-TXN-001 | C::test_mount_replacement_never_commits_mass_missing[during_prepare/before_scanner_commit] | C0 24 原 sync 保护 baseline GREEN；25 跨 prepare/commit mass missing RED；当前两项 GREEN |
| 8 / LIB-SCAN-PATH-RETRY-001 | I::test_corrupt_path_retry_does_not_repeat_good_media[new/known]；P inventory stat[new/known] 等补充 | C0 11/12：(False,3,3)≠(True,1,1)；当前 GREEN，坏路径独立重试 |
| 9 / LIB-DETECTOR-INVENTORY-001 | I::test_constructor_has_no_filesystem_io[resolve/stat/iterdir/open]；seed/failed-startup detector；C3 config/mapper 参数 | C0 13–15 构造 I/O；16 open baseline GREEN；17 walk 5≠1；18 失败后竞争 walk；当前全 GREEN |
| 10 / WEB-INITIAL-READ-001 | W::initial_snapshot_timeout_reports_and_reconnects；get_timeout_ends_loading_and_retries；body_timeout_and_late_response_cannot_restore_baseline，及全部补充 | C0 exact-web-01–03 / C4 同名 red：error=null、fetch/body 不 settle；当前 GREEN |

额外 observed / LIB-SCAN-OBSERVED-001：C::test_observed_unchanged_uri_is_not_missing，C0 exact-backend-23 原 observed 被置 MISSING；当前 GREEN。CI-SHA-DELIVERY-001 仅静态配置本地通过；新 SHA 远程证明未满足。

## 历史 RED→GREEN 与已有 baseline GREEN

本轮仅复跑最终 GREEN，没有回退或改写 C1–C4 来制造 RED；**本轮新行为 RED：无**。历史 RED 引用真实原始日志（校验和/失败摘录附后），永久节点与完整失败原因归 root-cause evidence 对应 C0/C1/C2/C3/C4 节。导入缺失、fixture 发现错误、运行环境冲突、client signal 装配以及第二退避 fixture 等不计行为 RED。

- C0：23 backend 行为 RED、2 baseline GREEN + 3 Web 行为 RED。constructor open、during_prepare mount 的旧保护不能伪称 RED。
- C1：observed、v4 表创建、缺签名持久行、非法 pair ValidationError 等 16 行为 RED；原 helper 缺表返回 []，真实断言失败而非 SQL/import 装配错误。当前 C1 全部参数项 exact GREEN。
- C2：旧签名未补、相同 stat startup 重读、半写入、stale 覆盖、取消未生效、revision/SYNCING 不原子；inventory stat new 未登记失败、known PermissionError 从生产 precheck 逃出属于路径失败隔离缺陷，非环境依赖缺失。相关永久节点当前 GREEN。
- C3：precheck→update→postcheck、accepted/unknown、owner baseline conflict、cache/new facts、generation absence 合并、根 I/O/seed/取消/日志等以历史表和原始日志核对，当前全部永久节点 GREEN。文件名含 red 但实际 passed 的记录仍归 baseline GREEN，不计 RED。
- C4：三个 C0 + 新十项行为 RED→GREEN，共 13；terminal network/json/http/decode 清 timer 四项原已 GREEN。red-new-5 是四项 baseline GREEN，不能因文件名误计 RED。
- C0 原 backend 七文件 74 passed / 2.09s，Web realtime/library-sync/resource-cache 28 passed / 7.36s；60 秒确认预算从 commit 后开始是既有 GREEN。原始 baseline 日志附后；本轮直接、关系和 full 包含这些永久保护。

## 本轮 fresh 验证

所有执行退出码、pytest count/duration、Vitest count/files/duration及进程 wall seconds见下表/命令账本。日志与 runner 目录 `/tmp/mpd-c5-evidence-ep2ppqpm`，永久测试不依赖 /tmp。

顺序为 backend 全部 corrective collect 并逐项 exact（包括全部参数）+ 历史 release 必要回归→Web exact→直接文件→两端完整关系→两端完整 regression→typecheck/build/Ruff。补充 schema、outer 四参数、metadata/歌词/配置、joint playlist/snapshot 节点在主 runner 直接文件开始前完成 exact。没有以 full 替代前面任何 gate。

补充 runner 首轮误把 schema 两节点指向 task3_batch4，在 collect 后自有节点校验 AssertionError；分类为临时 runner 错误路径假设，未执行不存在节点、未修改仓库测试。完整错误保留 first-supplement-progress/collect；按实际 layout 修正后 rerun exact，全部通过。该失败不抵扣最终验收、不是新增业务 RED。收尾临时 audit 首轮误将 no-index --check 的差异 exit 1 当失败；已用自有 clean/whitespace fixture 对照确认：无空白诊断 exit 1、trailing whitespace exit 3。纠正 runner 和本记录的退出码表述后复查，无仓库空白问题；不把此工具判定误差当业务失败。既有 Starlette/httpx deprecation warning 保留，无依赖或环境失败。

| Gate | exit | 实际结果 | wall seconds |
|---|---|---|---|
| Backend 独立 exact | 0 | 128/128 passed（主 111 + 补充 17） | 158.54 |
| Web 独立 exact | 0 | 18/18 passed（17 行为/保护 + 1 client 装配） | 62.35 |
| backend-direct | 0 | 291 passed in 19.80s | 20.96 |
| web-direct | 0 | Test Files  5 passed (5); Tests  61 passed (61); Duration  9.69s (transform 2.78s, setup 107ms, collect 3.90s, tests 914ms, environment 2.49s, prepare 535ms) | 10.93 |
| backend-relationships | 0 | 393 passed in 29.03s | 30.25 |
| web-relationships | 0 | Test Files  9 passed (9); Tests  92 passed (92); Duration  16.03s (transform 3.10s, setup 136ms, collect 5.49s, tests 1.82s, environment 4.48s, prepare 971ms) | 17.17 |
| backend-full | 0 | 1660 passed in 130.83s (0:02:10) | 132.42 |
| web-full | 0 | Test Files  30 passed (30); Tests  316 passed (316); Duration  51.34s (transform 4.10s, setup 419ms, collect 11.67s, tests 12.99s, environment 13.92s, prepare 2.94s) | 52.57 |
| web-typecheck | 0 | 成功，完整输出见日志 | 13.9 |
| web-build | 0 | ✓ built in 2.52s | 3.61 |
| ruff | 0 | All checks passed! | 0.29 |

## C5 实际变更与范围裁定

静态读取 `.github/workflows/container.yml` 起始 push branches 为 `[main, 'feature/**', 'codex/**']`，确实缺 `fix/**`。本轮唯一 workflow 变更是在该过滤末尾加入 `'fix/**'`。原 tags、workflow_dispatch、PR validate、validate 任务、image needs/PR 排除、SHA 标签/OCI revision、digest 记录及 `linux/amd64,linux/arm64` 原样保留。只读静态比较确保移除该一处增量后字节等于起始文件。

沿用现有 archive/task-9 路径新增本 acceptance；README 仅替换 Startup corrective 当前入口段为本地 PASSED、远程/人工 NOT RUN。Docker/start_period/SCAN_INTERVAL_SECONDS/Web timeout/依赖/构建平台/其它 workflow 行为均无变化。本轮没有新产品实现或新的永久测试。

最终 Git 检查：`git diff --check` exit 0；新增 acceptance 及所有未跟踪文件 `git diff --no-index --check /dev/null <file>` exit 1、输出为空（no-index 的差异状态，不是空白错误）；实际 tracked diff/stat/status 与新增文件均审阅。git diff --stat 的累计 dirty 不是本轮 C5 diff；另与起始文件快照比较，只发生上述三个 C5 文件增量。起始所有其它 tracked/untracked 文件 hash 一致，README 原段外一致。无临时 DB/log/config/venv/依赖/生成 dist 入 Git。

最终状态补充：33 tracked modified + 12 untracked；相较起始新增 workflow 修改和本 acceptance 未跟踪文件。累计 tracked stat 为 33 files changed, 796 insertions(+), 495 deletions(-)，不包含 untracked；不得把累计旧修复算作 C5 新增。起始快照中 421 个未被 C5 允许修改的文件 SHA256 一致，源码/测试 manifest SHA256 为 `aef57c0d5c3e83e845a91c31dca49d00634fcf3b3234554f38f033c95b9e55b1`，从 fresh 验证到收尾无变化。workflow 移除唯一 fix/** 增量后等于起始字节；README corrective 段之前/之后均等于起始内容。

最终检查命令的实际退出码：`git diff --check`、`git diff --stat`、`git status --short`、`git diff`、`git rev-parse HEAD`、`git branch --show-current` 均 0；12 个 untracked 的 `git diff --no-index --check /dev/null <file>` 均 1 且无空白诊断。命令/输出分别保存 final-audit.json 与 final-*.log。新增 acceptance 内容也核对了合同表、逐节点账本、历史日志校验和与未运行项；没有占位符或把历史 GREEN 伪称新 RED。

## 审查状态、未运行项与独立授权门槛

- C1–C4：原作者自审记录已核对，本轮对源码/合同/测试/实际 diff 再作作者自审；没有已确认未解决的 C1–C4 行为缺口，全部 fresh suite GREEN。**独立 review NOT RUN**；历史 C3 reviewer 额度导致未启动，不算 PASS。当前 native 执行依计划不默认委派；本 acceptance 不冒充独立审查通过。
- C5：作者自审完成，workflow 一行过滤增量和 documentation 范围已检查。独立 review NOT RUN。源码不变，测试结果不冒充远程运行结果。
- 远程新提交 SHA、remote HEAD、新 SHA CI run.head_sha、validate/image、镜像 sha 标签/digest/双平台：**NOT RUN / 未满足**。静态 CI 配置准备好不等于容器交付完成；不引用历史 CI、旧 SHA 镜像或其它 SHA 成功抵扣。
- 未来另获 **commit/push** 授权后，必须核对实际修复提交、远端 HEAD、`run.head_sha` 与修复新 SHA 完全一致，validate/image 均成功；再核对 `sha-<新SHA>` 镜像标签、digest，以及 `linux/amd64` 和 `linux/arm64` 两个目标平台。没有授权本轮不触发 workflow_dispatch、不发布/部署。
- 手机综合、真实 MPD/NAS/DAC、Docker/真实设备人工验收：**NOT RUN**。不关闭 Task 9 历史人工 Gate；本地自动通过不替代这些 Gate。

C5 本地部分通过后停止。远程容器交付未完成，真实设备人工验收未运行。

## Fresh 完整命令与逐节点账本

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_startup_library_reconciliation.py::test_persisted_second_start_skips_parse_and_hash -p server.tests.support.playback` → exit 0；1 passed in 0.12s；wall 1.24s；日志 `backend-exact-000.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_startup_library_reconciliation.py::test_unchanged_consistent_startup_does_not_update -p server.tests.support.playback` → exit 0；1 passed in 0.11s；wall 1.23s；日志 `backend-exact-001.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_startup_library_reconciliation.py::test_inconsistent_startup_updates_once_then_confirms -p server.tests.support.playback` → exit 0；1 passed in 0.16s；wall 1.24s；日志 `backend-exact-002.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[add]' -p server.tests.support.playback` → exit 0；1 passed in 0.09s；wall 1.12s；日志 `backend-exact-003.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[modify]' -p server.tests.support.playback` → exit 0；1 passed in 0.09s；wall 1.16s；日志 `backend-exact-004.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[delete]' -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.11s；日志 `backend-exact-005.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[move]' -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.19s；日志 `backend-exact-006.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_add]' -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.18s；日志 `backend-exact-007.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_modify]' -p server.tests.support.playback` → exit 0；1 passed in 0.10s；wall 1.16s；日志 `backend-exact-008.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_delete]' -p server.tests.support.playback` → exit 0；1 passed in 0.09s；wall 1.14s；日志 `backend-exact-009.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[new]' -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.12s；日志 `backend-exact-010.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[known]' -p server.tests.support.playback` → exit 0；1 passed in 0.12s；wall 1.24s；日志 `backend-exact-011.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[resolve]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.1s；日志 `backend-exact-012.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[stat]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.06s；日志 `backend-exact-013.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[iterdir]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.1s；日志 `backend-exact-014.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[open]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.09s；日志 `backend-exact-015.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_startup_library_reconciliation.py::test_startup_inventory_seed_does_not_immediately_walk -p server.tests.support.playback` → exit 0；1 passed in 0.06s；wall 1.15s；日志 `backend-exact-016.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_startup_library_reconciliation.py::test_failed_startup_has_no_competing_detector_walk -p server.tests.support.playback` → exit 0；1 passed in 0.15s；wall 1.21s；日志 `backend-exact-017.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/api/test_startup_readiness.py::test_http_ws_and_library_read_during_startup_prepare -p server.tests.support.playback` → exit 0；1 passed in 0.16s；wall 1.26s；日志 `backend-exact-018.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/api/test_startup_readiness.py::test_startup_failure_keeps_http_ready_and_old_library_readable -p server.tests.support.playback` → exit 0；1 passed in 0.18s；wall 1.28s；日志 `backend-exact-019.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/api/test_startup_readiness.py::test_http_ws_and_library_read_during_startup_root_validation -p server.tests.support.playback` → exit 0；1 passed in 0.16s；wall 1.27s；日志 `backend-exact-020.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_prepare_releases_database_lock -p server.tests.support.playback` → exit 0；1 passed in 0.03s；wall 1.12s；日志 `backend-exact-021.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[parse]' -p server.tests.support.playback` → exit 0；1 passed in 1.24s；wall 2.29s；日志 `backend-exact-022.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[hash]' -p server.tests.support.playback` → exit 0；1 passed in 1.24s；wall 2.31s；日志 `backend-exact-023.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_old_missing_signatures_are_backfilled_once -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.2s；日志 `backend-exact-024.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_deep_reconciliation_detects_same_stat_content_change -p server.tests.support.playback` → exit 0；1 passed in 0.09s；wall 1.16s；日志 `backend-exact-025.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_media_changed_during_prepare_is_retried -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.17s；日志 `backend-exact-026.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_stale_baseline_cannot_overwrite_new_commit -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.24s；日志 `backend-exact-027.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_prepare_cancellation_never_commits -p server.tests.support.playback` → exit 0；1 passed in 1.24s；wall 2.37s；日志 `backend-exact-028.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_commit_data_revision_and_sync_are_atomic -p server.tests.support.playback` → exit 0；1 passed in 0.09s；wall 1.17s；日志 `backend-exact-029.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_commit_has_no_music_io_and_workers_have_no_repository_access -p server.tests.support.playback` → exit 0；1 passed in 0.04s；wall 1.11s；日志 `backend-exact-030.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_file_changed_before_commit_retains_other_prepared_results -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.17s；日志 `backend-exact-031.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_conflict_reprepare_reuses_unrelated_successful_media -p server.tests.support.playback` → exit 0；1 passed in 0.11s；wall 1.24s；日志 `backend-exact-032.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_full_prepare_artwork_fallback_revisits_only_related_observed_song -p server.tests.support.playback` → exit 0；1 passed in 0.10s；wall 1.2s；日志 `backend-exact-033.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_single_file_stat_failure_keeps_other_prepared_media -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.17s；日志 `backend-exact-034.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_library_scan_prepare.py::test_inventory_entry_stat_failure_is_isolated[new]' -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.18s；日志 `backend-exact-035.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_library_scan_prepare.py::test_inventory_entry_stat_failure_is_isolated[known]' -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.14s；日志 `backend-exact-036.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_directory_inventory_failure_preserves_old_library -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.16s；日志 `backend-exact-037.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_manual_deep_retry_does_not_repeat_good_media -p server.tests.support.playback` → exit 0；1 passed in 0.10s；wall 1.22s；日志 `backend-exact-038.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scan_prepare.py::test_observed_signature_backfill_survives_new_metadata_failure -p server.tests.support.playback` → exit 0；1 passed in 0.06s；wall 1.27s；日志 `backend-exact-039.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/repositories/test_library_scan_commit.py::test_observed_unchanged_uri_is_not_missing -p server.tests.support.playback` → exit 0；1 passed in 0.05s；wall 1.22s；日志 `backend-exact-040.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[during_prepare]' -p server.tests.support.playback` → exit 0；1 passed in 0.06s；wall 1.13s；日志 `backend-exact-041.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[before_scanner_commit]' -p server.tests.support.playback` → exit 0；1 passed in 0.06s；wall 1.15s；日志 `backend-exact-042.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/repositories/test_library_scan_commit.py::test_v4_migration_preserves_library_and_references -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.14s；日志 `backend-exact-043.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/repositories/test_library_scan_commit.py::test_sidecar_absence_is_distinct_from_unknown -p server.tests.support.playback` → exit 0；1 passed in 0.03s；wall 1.07s；日志 `backend-exact-044.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/repositories/test_library_scan_commit.py::test_signature_delta_rolls_back_with_song_batch[commit]' -p server.tests.support.playback` → exit 0；1 passed in 0.03s；wall 1.11s；日志 `backend-exact-045.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/repositories/test_library_scan_commit.py::test_signature_delta_rolls_back_with_song_batch[rollback]' -p server.tests.support.playback` → exit 0；1 passed in 0.03s；wall 1.08s；日志 `backend-exact-046.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/repositories/test_library_scan_commit.py::test_signature_delta_rolls_back_with_song_batch[cancel]' -p server.tests.support.playback` → exit 0；1 passed in 0.04s；wall 1.07s；日志 `backend-exact-047.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/repositories/test_library_scan_commit.py::test_failed_sidecar_delta_is_never_recorded_as_success[read_error]' -p server.tests.support.playback` → exit 0；1 passed in 0.03s；wall 1.1s；日志 `backend-exact-048.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/repositories/test_library_scan_commit.py::test_failed_sidecar_delta_is_never_recorded_as_success[unreadable]' -p server.tests.support.playback` → exit 0；1 passed in 0.03s；wall 1.14s；日志 `backend-exact-049.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/repositories/test_library_scan_commit.py::test_failed_sidecar_delta_is_never_recorded_as_success[new_unreadable]' -p server.tests.support.playback` → exit 0；1 passed in 0.03s；wall 1.12s；日志 `backend-exact-050.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/repositories/test_library_scan_commit.py::test_scan_baseline_tracks_content_and_signatures_but_not_audit_time -p server.tests.support.playback` → exit 0；1 passed in 0.03s；wall 1.06s；日志 `backend-exact-051.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/repositories/test_library_scan_commit.py::test_sidecar_signature_rejects_partial_or_negative_stats[None-1]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.1s；日志 `backend-exact-052.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/repositories/test_library_scan_commit.py::test_sidecar_signature_rejects_partial_or_negative_stats[1-None]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.08s；日志 `backend-exact-053.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/repositories/test_library_scan_commit.py::test_sidecar_signature_rejects_partial_or_negative_stats[-1-0]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.12s；日志 `backend-exact-054.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/repositories/test_library_scan_commit.py::test_sidecar_signature_rejects_partial_or_negative_stats[0--1]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.12s；日志 `backend-exact-055.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/repositories/test_library_scan_commit.py::test_sidecar_table_enforces_signature_pairs_and_song_reference -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.12s；日志 `backend-exact-056.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/repositories/test_library_scan_commit.py::test_sidecar_delta_follows_song_identity_on_move -p server.tests.support.playback` → exit 0；1 passed in 0.03s；wall 1.07s；日志 `backend-exact-057.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_baseline_conflict_reuses_unrelated_successful_media[wrapper]' -p server.tests.support.playback` → exit 0；1 passed in 0.10s；wall 1.2s；日志 `backend-exact-058.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_baseline_conflict_reuses_unrelated_successful_media[owner]' -p server.tests.support.playback` → exit 0；1 passed in 0.11s；wall 1.19s；日志 `backend-exact-059.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_precheck_failure_never_blindly_updates[status]' -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.22s；日志 `backend-exact-060.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_precheck_failure_never_blindly_updates[uri]' -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.19s；日志 `backend-exact-061.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_precheck_failure_never_blindly_updates[timeout]' -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.17s；日志 `backend-exact-062.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_precheck_failure_never_blindly_updates[unknown]' -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.25s；日志 `backend-exact-063.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_accepted_update_is_not_repeated_on_confirmation_retry -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.2s；日志 `backend-exact-064.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_update_outcome_is_reread_before_any_retry[unknown]' -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.13s；日志 `backend-exact-065.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_update_outcome_is_reread_before_any_retry[rejected]' -p server.tests.support.playback` → exit 0；1 passed in 0.05s；wall 1.11s；日志 `backend-exact-066.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[add]' -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.21s；日志 `backend-exact-067.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[modify]' -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.22s；日志 `backend-exact-068.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[delete]' -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.16s；日志 `backend-exact-069.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[move]' -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.19s；日志 `backend-exact-070.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[lrc]' -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.13s；日志 `backend-exact-071.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_empty_startup_checks_status_without_update -p server.tests.support.playback` → exit 0；1 passed in 0.04s；wall 1.1s；日志 `backend-exact-072.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[stat-config]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.09s；日志 `backend-exact-073.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[stat-mapper]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.13s；日志 `backend-exact-074.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[resolve-config]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.07s；日志 `backend-exact-075.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[resolve-mapper]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.14s；日志 `backend-exact-076.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[iterdir-config]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.08s；日志 `backend-exact-077.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[iterdir-mapper]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.05s；日志 `backend-exact-078.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[open-config]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.15s；日志 `backend-exact-079.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[open-mapper]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.09s；日志 `backend-exact-080.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_mapper_first_use_canonicalizes_root_and_rejects_symlink_escape -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.16s；日志 `backend-exact-081.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_shutdown_during_prepare_has_no_late_update -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.16s；日志 `backend-exact-082.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_next_generation_keeps_failed_paths_and_move_absence -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.23s；日志 `backend-exact-083.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_startup_seeds_same_inventory_in_memory_outside_lock -p server.tests.support.playback` → exit 0；1 passed in 0.06s；wall 1.21s；日志 `backend-exact-084.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_config_construction_has_no_os_root_probe[stat]' -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.98s；日志 `backend-exact-085.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_config_construction_has_no_os_root_probe[access]' -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.06s；日志 `backend-exact-086.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_accepted_update_timeout_retry_preserves_single_update -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.13s；日志 `backend-exact-087.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_shutdown_after_commit_keeps_facts_without_success_or_late_update -p server.tests.support.playback` → exit 0；1 passed in 0.06s；wall 1.36s；日志 `backend-exact-088.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_partial_scan_rollback_does_not_drop_good_uncommitted_paths -p server.tests.support.playback` → exit 0；1 passed in 0.09s；wall 1.37s；日志 `backend-exact-089.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_root_readability_validation_is_deferred_to_worker -p server.tests.support.playback` → exit 0；1 passed in 0.04s；wall 1.24s；日志 `backend-exact-090.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_conflict_retry_reuses_stable_success_and_prepares_new_facts[new_generation]' -p server.tests.support.playback` → exit 0；1 passed in 0.11s；wall 1.3s；日志 `backend-exact-091.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_conflict_retry_reuses_stable_success_and_prepares_new_facts[new_generation_directory]' -p server.tests.support.playback` → exit 0；1 passed in 0.13s；wall 1.38s；日志 `backend-exact-092.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_conflict_retry_reuses_stable_success_and_prepares_new_facts[changed_media]' -p server.tests.support.playback` → exit 0；1 passed in 0.11s；wall 1.34s；日志 `backend-exact-093.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/services/test_startup_sync_corrective.py::test_conflict_retry_reuses_stable_success_and_prepares_new_facts[changed_stable_media]' -p server.tests.support.playback` → exit 0；1 passed in 0.10s；wall 1.42s；日志 `backend-exact-094.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_startup_path_retry_does_not_seed_unprocessed_new_media_as_accepted -p server.tests.support.playback` → exit 0；1 passed in 0.09s；wall 1.45s；日志 `backend-exact-095.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_rebased_prepared_audio_delta_uses_real_database_baseline -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.37s；日志 `backend-exact-096.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_startup_sync_corrective.py::test_prepared_unreadable_availability_delta_requires_audio_update -p server.tests.support.playback` → exit 0；1 passed in 0.06s；wall 1.39s；日志 `backend-exact-097.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scanner.py::test_step7_full_scan_does_not_follow_symlinked_directories -p server.tests.support.playback` → exit 0；1 passed in 0.04s；wall 1.35s；日志 `backend-exact-098.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scanner.py::test_step7_traversal_error_disables_missing_reconciliation -p server.tests.support.playback` → exit 0；1 passed in 0.03s；wall 1.24s；日志 `backend-exact-099.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_sync_service.py::test_confirmation_budget_starts_after_scanner_commit -p server.tests.support.playback` → exit 0；1 passed in 0.05s；wall 1.34s；日志 `backend-exact-100.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_library_sync.py::test_commit_update_confirmation_and_next_generation_are_ordered -p server.tests.support.playback` → exit 0；1 passed in 0.13s；wall 1.27s；日志 `backend-exact-101.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_library_sync.py::test_runtime_startup_scheduler_and_shutdown_share_one_owner -p server.tests.support.playback` → exit 0；1 passed in 0.04s；wall 1.27s；日志 `backend-exact-102.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_library_sync.py::test_runtime_does_not_duplicate_startup_before_scheduled_interval -p server.tests.support.playback` → exit 0；1 passed in 0.30s；wall 1.4s；日志 `backend-exact-103.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/api/test_mpd_connection.py::test_saved_endpoint_overrides_invalid_old_environment_and_adapter_uses_it -p server.tests.support.playback` → exit 0；1 passed in 0.16s；wall 1.28s；日志 `backend-exact-104.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_realtime_observer_lifecycle.py::test_composition_root_starts_one_sampler_without_clients_and_awaits_shutdown -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.16s；日志 `backend-exact-105.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/api/test_library_sync_wire.py::test_library_sync_server_golden_uses_real_scanner_and_public_wire -p server.tests.support.playback` → exit 0；1 passed in 0.24s；wall 1.34s；日志 `backend-exact-106.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/api/test_realtime.py::test_real_lifespan_restart_replaces_epoch_and_discards_late_old_get[True]' -p server.tests.support.playback` → exit 0；1 passed in 0.30s；wall 1.42s；日志 `backend-exact-107.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/api/test_realtime_state.py::test_root_snapshot_reports_real_producer_versions -p server.tests.support.playback` → exit 0；1 passed in 0.22s；wall 1.4s；日志 `backend-exact-108.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/test_logging.py::test_activity_phase_and_errors_are_correlated_without_secrets -p server.tests.support.playback` → exit 0；1 passed in 0.05s；wall 1.11s；日志 `backend-exact-109.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/test_logging.py::test_sync_shutdown_logs_terminal_phase_without_changing_business_result -p server.tests.support.playback` → exit 0；1 passed in 0.04s；wall 1.06s；日志 `backend-exact-110.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t initial_snapshot_timeout_reports_and_reconnects --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  3.16s (transform 525ms, setup 77ms, collect 634ms, tests 22ms, environment 1.76s, prepare 248ms)；wall 5.61s；日志 `web-exact-00.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t get_timeout_ends_loading_and_retries --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.67s (transform 419ms, setup 73ms, collect 528ms, tests 32ms, environment 504ms, prepare 130ms)；wall 2.85s；日志 `web-exact-01.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t body_timeout_and_late_response_cannot_restore_baseline --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.75s (transform 489ms, setup 77ms, collect 615ms, tests 35ms, environment 503ms, prepare 128ms)；wall 3.02s；日志 `web-exact-02.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t success_stop_and_reconnect_clear_timeout_timers --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.78s (transform 491ms, setup 70ms, collect 622ms, tests 28ms, environment 526ms, prepare 133ms)；wall 3.03s；日志 `web-exact-03.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t get_after_timeout_does_not_enable_mutations --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.75s (transform 502ms, setup 59ms, collect 637ms, tests 30ms, environment 513ms, prepare 140ms)；wall 3.01s；日志 `web-exact-04.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t never_settling_abort_ignored_fetch_uses_one_total_budget --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.76s (transform 464ms, setup 80ms, collect 593ms, tests 25ms, environment 522ms, prepare 121ms)；wall 3.04s；日志 `web-exact-05.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t never_settling_abort_ignored_body_uses_one_total_budget --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.76s (transform 511ms, setup 89ms, collect 601ms, tests 17ms, environment 514ms, prepare 140ms)；wall 2.95s；日志 `web-exact-06.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t abort_rejection_cannot_replace_typed_read_timeout --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.66s (transform 480ms, setup 67ms, collect 616ms, tests 13ms, environment 473ms, prepare 126ms)；wall 2.92s；日志 `web-exact-07.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t terminal_network_failure_clears_read_timer --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.70s (transform 465ms, setup 74ms, collect 581ms, tests 19ms, environment 503ms, prepare 142ms)；wall 2.94s；日志 `web-exact-08.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t terminal_json_failure_clears_read_timer --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.64s (transform 469ms, setup 64ms, collect 604ms, tests 16ms, environment 489ms, prepare 129ms)；wall 2.92s；日志 `web-exact-09.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t terminal_http_failure_clears_read_timer --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.76s (transform 527ms, setup 78ms, collect 637ms, tests 25ms, environment 483ms, prepare 130ms)；wall 3.0s；日志 `web-exact-10.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t terminal_decode_failure_clears_read_timer --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.72s (transform 429ms, setup 58ms, collect 572ms, tests 19ms, environment 606ms, prepare 151ms)；wall 2.9s；日志 `web-exact-11.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t injected_budgets_use_fixture_clock_and_dispose_old_initial --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.69s (transform 427ms, setup 60ms, collect 524ms, tests 22ms, environment 597ms, prepare 141ms)；wall 2.9s；日志 `web-exact-12.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t resource_timeout_ends_loading_and_uses_existing_notice_read --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.84s (transform 542ms, setup 52ms, collect 598ms, tests 237ms, environment 512ms, prepare 126ms)；wall 3.18s；日志 `web-exact-13.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t generation_change_cannot_restart_a_timed_out_resource_budget --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.80s (transform 560ms, setup 77ms, collect 701ms, tests 21ms, environment 478ms, prepare 133ms)；wall 3.02s；日志 `web-exact-14.log`。

- `npm --prefix web run test -- --run tests/invariants/global-notices.test.ts -t top_timeout_INITIAL_SNAPSHOT_TIMEOUT_keeps_existing_read_recovery --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 11 skipped (12); Duration  5.11s (transform 2.93s, setup 57ms, collect 3.81s, tests 252ms, environment 498ms, prepare 131ms)；wall 6.29s；日志 `web-exact-15.log`。

- `npm --prefix web run test -- --run tests/invariants/global-notices.test.ts -t top_timeout_READ_TIMEOUT_keeps_existing_read_recovery --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 11 skipped (12); Duration  5.00s (transform 2.85s, setup 80ms, collect 3.73s, tests 146ms, environment 505ms, prepare 127ms)；wall 6.29s；日志 `web-exact-16.log`。

- `npm --prefix web run test -- --run tests/invariants/client.test.ts -t '^HTTP uses ws and GET stays same-origin without an idempotency key$' --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  1 passed (1); Tests  1 passed | 7 skipped (8); Duration  1.27s (transform 209ms, setup 69ms, collect 159ms, tests 21ms, environment 501ms, prepare 135ms)；wall 2.48s；日志 `web-client-exact.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_startup_library_reconciliation.py server/tests/api/test_startup_readiness.py server/tests/services/test_library_scan_prepare.py server/tests/repositories/test_library_scan_commit.py server/tests/services/test_startup_sync_corrective.py server/tests/repositories/test_library_reconciliation.py server/tests/services/test_library_scanner.py server/tests/services/test_library_sync_service.py server/tests/services/test_library_change_detector.py server/tests/test_config.py server/tests/player/test_music_uri.py server/tests/invariants/test_library_sync.py server/tests/invariants/test_library_sync_wire.py server/tests/api/test_library_sync_wire.py server/tests/invariants/test_realtime_library.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_playlist.py server/tests/invariants/test_realtime_history.py server/tests/invariants/test_realtime_recovery.py server/tests/repositories/test_task3_batch4.py server/tests/api/test_mpd_connection.py server/tests/invariants/test_realtime_observer_lifecycle.py server/tests/api/test_realtime.py server/tests/api/test_realtime_state.py server/tests/test_logging.py -p server.tests.support.playback` → exit 0；291 passed in 19.80s；wall 20.96s；日志 `backend-direct.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts tests/invariants/global-notices.test.ts tests/invariants/resource-cache.test.ts tests/invariants/realtime.test.ts tests/invariants/client.test.ts --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  5 passed (5); Tests  61 passed (61); Duration  9.69s (transform 2.78s, setup 107ms, collect 3.90s, tests 914ms, environment 2.49s, prepare 535ms)；wall 10.93s；日志 `web-direct.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_startup_library_reconciliation.py server/tests/api/test_startup_readiness.py server/tests/services/test_library_scan_prepare.py server/tests/repositories/test_library_scan_commit.py server/tests/services/test_library_scanner.py server/tests/services/test_library_change_detector.py server/tests/services/test_library_sync_service.py server/tests/repositories/test_library_reconciliation.py server/tests/invariants/test_library_sync.py server/tests/invariants/test_library_sync_wire.py server/tests/api/test_library_sync_wire.py server/tests/invariants/test_transaction_relationships.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_realtime_library.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_handoff.py server/tests/player/test_music_uri.py server/tests/test_config.py server/tests/invariants/test_config_composition.py server/tests/invariants/test_uri_mapping.py server/tests/invariants/test_health_relationships.py server/tests/invariants/test_realtime_queue.py server/tests/invariants/test_realtime_history.py server/tests/invariants/test_playlist_relationships.py server/tests/services/test_startup_sync_corrective.py server/tests/api/test_mpd_connection.py server/tests/invariants/test_realtime_observer_lifecycle.py server/tests/invariants/test_realtime_playlist.py server/tests/api/test_realtime.py server/tests/api/test_realtime_state.py server/tests/test_logging.py server/tests/repositories/test_task3_batch4.py server/tests/invariants/test_realtime_recovery.py -p server.tests.support.playback` → exit 0；393 passed in 29.03s；wall 30.25s；日志 `backend-relationships.log`。

- `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts tests/invariants/realtime.test.ts tests/invariants/resource-cache.test.ts tests/invariants/wire.test.ts tests/invariants/mutation.test.ts tests/invariants/global-notices.test.ts tests/invariants/library-sync.test.ts tests/invariants/shell-navigation.test.ts tests/invariants/task9-relationships.test.ts --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  9 passed (9); Tests  92 passed (92); Duration  16.03s (transform 3.10s, setup 136ms, collect 5.49s, tests 1.82s, environment 4.48s, prepare 971ms)；wall 17.17s；日志 `web-relationships.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests -p server.tests.support.playback` → exit 0；1660 passed in 130.83s (0:02:10)；wall 132.42s；日志 `backend-full.log`。

- `npm --prefix web run test -- --run --maxWorkers=1 --minWorkers=1` → exit 0；Test Files  30 passed (30); Tests  316 passed (316); Duration  51.34s (transform 4.10s, setup 419ms, collect 11.67s, tests 12.99s, environment 13.92s, prepare 2.94s)；wall 52.57s；日志 `web-full.log`。

- `npm --prefix web run typecheck` → exit 0；成功；wall 13.9s；日志 `web-typecheck.log`。

- `npm --prefix web run build` → exit 0；✓ built in 2.52s；wall 3.61s；日志 `web-build.log`。

- `.venv/bin/python -m ruff check server/app server/tests` → exit 0；All checks passed!；wall 0.29s；日志 `ruff.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_realtime_library.py::test_outer_scan_waits_for_commit_and_keeps_completion_order -p server.tests.support.playback` → exit 0；1 passed in 0.05s；wall 1.38s；日志 `supplement-exact-00.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_realtime_library.py::test_outer_scan_delta_rollback_cancel_restore_and_batch[rollback]' -p server.tests.support.playback` → exit 0；1 passed in 0.09s；wall 1.38s；日志 `supplement-exact-01.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_realtime_library.py::test_outer_scan_delta_rollback_cancel_restore_and_batch[cancel]' -p server.tests.support.playback` → exit 0；1 passed in 0.10s；wall 1.4s；日志 `supplement-exact-02.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_realtime_library.py::test_outer_scan_delta_rollback_cancel_restore_and_batch[restore]' -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.31s；日志 `supplement-exact-03.log`。

- `.venv/bin/python -m pytest -q --tb=long 'server/tests/invariants/test_realtime_library.py::test_outer_scan_delta_rollback_cancel_restore_and_batch[batch]' -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.32s；日志 `supplement-exact-04.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_realtime_library.py::test_post_commit_publisher_failure_and_cancel_keep_content_visible -p server.tests.support.playback` → exit 0；1 passed in 0.07s；wall 1.37s；日志 `supplement-exact-05.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/repositories/test_library_reconciliation.py::test_fresh_database_is_schema_v5_with_reconciliation_artwork_and_idempotency_tables -p server.tests.support.playback` → exit 0；1 passed in 0.03s；wall 1.35s；日志 `supplement-exact-06.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/repositories/test_library_reconciliation.py::test_v1_to_v5_migration_preserves_song_playlist_favorite_history_data -p server.tests.support.playback` → exit 0；1 passed in 0.03s；wall 1.35s；日志 `supplement-exact-07.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scanner.py::test_step4_failed_parse_does_not_overwrite_known_good_metadata -p server.tests.support.playback` → exit 0；1 passed in 0.05s；wall 1.3s；日志 `supplement-exact-08.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scanner.py::test_step5_unreadable_file_is_marked_unreadable -p server.tests.support.playback` → exit 0；1 passed in 0.06s；wall 1.21s；日志 `supplement-exact-09.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scanner.py::test_step7_parse_failure_never_applies_partial_batch -p server.tests.support.playback` → exit 0；1 passed in 0.04s；wall 1.38s；日志 `supplement-exact-10.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scanner.py::test_batch1_known_good_lyrics_status_survives_parse_failure -p server.tests.support.playback` → exit 0；1 passed in 0.04s；wall 1.25s；日志 `supplement-exact-11.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/test_config.py::test_missing_music_root_is_deferred_and_invalid_environment_fails -p server.tests.support.playback` → exit 0；1 passed in 0.02s；wall 1.34s；日志 `supplement-exact-12.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_realtime_playlist.py::test_library_and_playlist_share_one_outer_commit_and_restart -p server.tests.support.playback` → exit 0；1 passed in 0.05s；wall 1.18s；日志 `extra-exact-00.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/invariants/test_realtime_snapshot.py::test_snapshot_is_one_committed_cut -p server.tests.support.playback` → exit 0；1 passed in 0.16s；wall 1.39s；日志 `extra-exact-01.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scanner.py::test_step7_unknown_title_is_not_fabricated -p server.tests.support.playback` → exit 0；1 passed in 0.04s；wall 1.16s；日志 `extra-exact-02.log`。

- `.venv/bin/python -m pytest -q --tb=long server/tests/services/test_library_scanner.py::test_batch2_lrc_with_flac_and_mp3_same_stem_rescans_both -p server.tests.support.playback` → exit 0；1 passed in 0.08s；wall 1.27s；日志 `extra-exact-03.log`。

## 已核对的历史原始日志索引

下表是历史运行，不能作为本轮新 RED 或抵扣 fresh GREEN；完整文件是本机临时日志，摘要和真实失败原因也永久保存在 root-cause evidence 对应节。记录 SHA256 以固定原始证据；文件名含 red 但输出 GREEN 的行明确保留 GREEN。判定需看实际输出，不看文件名。

| 原始日志（绝对路径） | 实际历史结果 / 失败摘录 | SHA256 |
|---|---|---|
| `/tmp/mpd-c0-evidence/baseline-backend.log` | baseline GREEN（完整 passed 输出见原日志）； | `1b1c66c320752a3b73cee290b78787da9919906096a4b8b012f21b410ce475d1` |
| `/tmp/mpd-c0-evidence/baseline-web.log` | Test Files  3 passed (3); Tests  28 passed (28); Duration  7.36s (transform 2.76s, setup 94ms, collect 3.94s, tests 290ms, environment 1.66s, prepare 355ms)； | `5d0687d81d273dddab1d426abbc244ff4d5013d82073ed6dc2a4957d7b0d7c46` |
| `/tmp/mpd-c0-evidence/exact-backend-01.log` | 1 failed, 1 warning in 0.20s；E   assert (2, 2) == (0, 0); E; E     At index 0 diff: 2 != 0; E     Use -v to get more diff | `84d2e626871700a4c43743444e29983768e92edc3afc28003d570764ffca97ad` |
| `/tmp/mpd-c0-evidence/exact-backend-02.log` | 1 failed, 1 warning in 0.13s；E   AssertionError: assert 1 == 0; E    +  where 1 = <built-in method count of list object at 0x718da27680>(('update',)); E    +    where <built-in method count of list object at 0x718da27680> = [('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-253/test_unchanged_consistent_star0/music/ | `b9b2515f89e308e9f2f642ffc91741721820124a613528dacf3277ae22cd57d5` |
| `/tmp/mpd-c0-evidence/exact-backend-03.log` | 1 failed, 1 warning in 0.11s；E   AssertionError: [('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-254/test_inconsistent_startup_upda0/music/a.flac', True), ('uri', '/tmp/pytest-of-Gold/pytest-254/test_inconsistent_startup_upda0/music/sidecar.mp3', True)]; E   assert False; E    +  where False = any(<generator obje | `1c65d021902b631d3c09f9b10d7653a510325f4f14962960c3677b915b838528` |
| `/tmp/mpd-c0-evidence/exact-backend-04.log` | 1 failed, 1 warning in 0.13s；E   AssertionError: assert (Counter({'/t...car.mp3': 1})) == (Counter({'/t...ew.flac': 1})); E; E     At index 0 diff: Counter({'/tmp/pytest-of-Gold/pytest-255/test_reconcile_only_related_pa0/music/a.flac': 1, '/tmp/pytest-of-Gold/pytest-255/test_reconcile_only_related_pa0/music/new.flac': 1, '/tmp/ | `a709c7cefee9f781c184e88b29d4cefcf40d628ce9fee2abfd97d3a11813f0b0` |
| `/tmp/mpd-c0-evidence/exact-backend-05.log` | 1 failed, 1 warning in 0.12s；E   AssertionError: assert (Counter({'/t...car.mp3': 1})) == (Counter({'/t.../a.flac': 1})); E; E     At index 0 diff: Counter({'/tmp/pytest-of-Gold/pytest-256/test_reconcile_only_related_pa0/music/a.flac': 1, '/tmp/pytest-of-Gold/pytest-256/test_reconcile_only_related_pa0/music/sidecar.mp3': 1}) != | `40cb545f5a4ea5b39dbc51aeb0ebb868d07c020dd4db656eaa8234953901fc27` |
| `/tmp/mpd-c0-evidence/exact-backend-06.log` | 1 failed, 1 warning in 0.12s；E   AssertionError: assert (Counter({'/t...car.mp3': 1})) == (Counter(), Counter()); E; E     At index 0 diff: Counter({'/tmp/pytest-of-Gold/pytest-257/test_reconcile_only_related_pa0/music/sidecar.mp3': 1}) != Counter(); E     Use -v to get more diff | `3ef6de01d3c036b519edcb88bd1ad731ea65909fb7a4527d02bb2e2d545a71e5` |
| `/tmp/mpd-c0-evidence/exact-backend-07.log` | 1 failed, 1 warning in 0.13s；E   AssertionError: assert (Counter({'/t...car.mp3': 1})) == (Counter({'/t...ed.flac': 1})); E; E     At index 0 diff: Counter({'/tmp/pytest-of-Gold/pytest-258/test_reconcile_only_related_pa0/music/moved.flac': 1, '/tmp/pytest-of-Gold/pytest-258/test_reconcile_only_related_pa0/music/sidecar.mp3': 1} | `28a2358269a861b70e77ae36838a4d5828fdc36df50a37f3c65617c2a64832d8` |
| `/tmp/mpd-c0-evidence/exact-backend-08.log` | 1 failed, 1 warning in 0.11s；E   AssertionError: assert (Counter({'/t...car.mp3': 1})) == (Counter({'/t...}), Counter()); E; E     At index 0 diff: Counter({'/tmp/pytest-of-Gold/pytest-259/test_reconcile_only_related_pa0/music/a.flac': 1, '/tmp/pytest-of-Gold/pytest-259/test_reconcile_only_related_pa0/music/sidecar.mp3': 1}) != | `bf2ceefa0b3a63a858f97482acc194e974396df83ee77c92e811bf7d46a517b7` |
| `/tmp/mpd-c0-evidence/exact-backend-09.log` | 1 failed, 1 warning in 0.12s；E   AssertionError: assert (Counter({'/t...car.mp3': 1})) == (Counter({'/t...}), Counter()); E; E     At index 0 diff: Counter({'/tmp/pytest-of-Gold/pytest-260/test_reconcile_only_related_pa0/music/a.flac': 1, '/tmp/pytest-of-Gold/pytest-260/test_reconcile_only_related_pa0/music/sidecar.mp3': 1}) != | `4f2ccede0b0749212f4600236e857ccf125849d9f2f923445e9d89ae0e3b4ca3` |
| `/tmp/mpd-c0-evidence/exact-backend-10.log` | 1 failed, 1 warning in 0.13s；E   AssertionError: assert (Counter({'/t...car.mp3': 1})) == (Counter({'/t...}), Counter()); E; E     At index 0 diff: Counter({'/tmp/pytest-of-Gold/pytest-261/test_reconcile_only_related_pa0/music/a.flac': 1, '/tmp/pytest-of-Gold/pytest-261/test_reconcile_only_related_pa0/music/sidecar.mp3': 1}) != | `fcbe5a308eba8d78aa90a34624514b26f541a95c4c3b897389f397d7ba4a5696` |
| `/tmp/mpd-c0-evidence/exact-backend-11.log` | 1 failed, 1 warning in 0.11s；E   assert (False, 3, 3) == (True, 1, 1); E; E     At index 0 diff: False != True; E     Use -v to get more diff | `54b9b48206f59de3d46730ba0553454bea878d1a32bac912431da5dbefb666f5` |
| `/tmp/mpd-c0-evidence/exact-backend-12.log` | 1 failed, 1 warning in 0.11s；E   assert (False, 3, 3) == (True, 1, 1); E; E     At index 0 diff: False != True; E     Use -v to get more diff | `8227435ea3dc2eb4ee8a34d3303560ae6d926bba196785336ed2fd9750790c7d` |
| `/tmp/mpd-c0-evidence/exact-backend-13.log` | 1 failed, 1 warning in 0.05s；E   AssertionError: constructor performed Path.resolve: ['/tmp/pytest-of-Gold/pytest-264/test_constructor_has_no_filesy0', '/tmp/pytest-of-Gold/pytest-264/test_constructor_has_no_filesy0']; E   assert ['/tmp/pytest...s_no_filesy0'] == []; E; E     Left contains 2 more items, first extra item: '/tmp/ | `b89ca140057f10f2e39ef950facbef2d4d220d9813468daf1c50ed9b9b06cf4d` |
| `/tmp/mpd-c0-evidence/exact-backend-14.log` | 1 failed, 1 warning in 0.05s；E   AssertionError: constructor performed Path.stat: ['/tmp/pytest-of-Gold/pytest-265/test_constructor_has_no_filesy0', '/tmp/pytest-of-Gold/pytest-265/test_constructor_has_no_filesy0', '/tmp/pytest-of-Gold/pytest-265/test_constructor_has_no_filesy0', '/tmp/pytest-of-Gold/pytest-265/test_constructor | `9092f103ae4a9cdbb175266bb72418056781c3c098bdb291188f8716bb46a828` |
| `/tmp/mpd-c0-evidence/exact-backend-15.log` | 1 failed, 1 warning in 0.05s；E   AssertionError: constructor performed Path.iterdir: ['/tmp/pytest-of-Gold/pytest-266/test_constructor_has_no_filesy0']; E   assert ['/tmp/pytest...s_no_filesy0'] == []; E; E     Left contains one more item: '/tmp/pytest-of-Gold/pytest-266/test_constructor_has_no_filesy0'; E     Use -v to get mor | `6a970350e68e559cb72997cf4a5d515e23b33ea53100282b89b2d6fdd0de6eea` |
| `/tmp/mpd-c0-evidence/exact-backend-16.log` | baseline GREEN（完整 passed 输出见原日志）； | `c200a87cfd30a6534e114bdedcae42153dfbd2bf0cf72066c77f76d42cba882f` |
| `/tmp/mpd-c0-evidence/exact-backend-17.log` | 1 failed, 1 warning in 0.12s；E   AssertionError: ['inventory', 'inventory', 'inventory', 'audio', 'inventory']; E   assert 5 == 1; E    +  where 5 = len(['inventory', 'inventory', 'inventory', 'audio', 'inventory']) | `e6d3fce886514c908a57e3ef50caf02177ad0d5cb5cda87e2b9dba42d7b3ba12` |
| `/tmp/mpd-c0-evidence/exact-backend-18.log` | 1 failed, 1 warning in 0.20s；E   AssertionError: ['startup', 'detector']; E   assert ['startup', 'detector'] == ['startup']; E; E     Left contains one more item: 'detector'; E     Use -v to get more diff | `80edccfe1437cdcdd3309c1c3a4c2f3436927523abe4e3fd6fbe3e4fe57c2b76` |
| `/tmp/mpd-c0-evidence/exact-backend-19.log` | 1 failed, 1 warning in 1.59s；E   AssertionError: 1s readiness budget failed while prepare held: {'lifespan': True, 'state': False, 'library': False, 'ws': False}; E   assert False; E    +  where False = all(dict_values([True, False, False, False])); E    +    where dict_values([True, False, False, False]) = <built-in method val | `4be4a172b48eaba5b78bbbd87802fa94ddbf7591a230e569251006cf9af88888` |
| `/tmp/mpd-c0-evidence/exact-backend-20.log` | 1 failed in 1.54s；E   AssertionError: prepare holds shared DB lock: SELECT 1 / list_songs blocked; E   assert 0 == 2; E    +  where 0 = len(set()) | `0a6431e7f68bfe200b756477d57c4b7a43783a296c4c3d35d839d5c1c30a850c` |
| `/tmp/mpd-c0-evidence/exact-backend-21.log` | 1 failed in 1.67s；E   AssertionError: real media I/O blocked event-loop progress; E   assert (861405.926206241 - 861404.715191711) < 1; E    +  where 861405.926206241 = <built-in function monotonic>(); E    +    where <built-in function monotonic> = time.monotonic | `5a5d780beeb064e9f7beb6a66c7794504ae0c69aa186da67397b47aa58d36db1` |
| `/tmp/mpd-c0-evidence/exact-backend-22.log` | 1 failed in 1.71s；E   AssertionError: real media I/O blocked event-loop progress; E   assert (861408.132637074 - 861406.918913793) < 1; E    +  where 861408.132637074 = <built-in function monotonic>(); E    +    where <built-in function monotonic> = time.monotonic | `0619a924a13b920de141d73ff2a8a57c4e63df2fe6b41daf3b117aa8c4d11b2e` |
| `/tmp/mpd-c0-evidence/exact-backend-23.log` | 1 failed in 0.49s；E   AssertionError: ScanResult(added_song_ids=(), updated_song_ids=(), moved_song_ids=(), missing_song_ids=('e1ad491e-f098-4ff3-a645-af6303bade4f', '384cad03-c411-4582-a1da-454815fd86b6'), unreadable_song_ids=()); E   assert [Song(song_id...artwork=None)] == [Song(song_id...artwork=None)]; E; E      | `7a8e5520c956470a2c01a81ee2495d3f56e68bd87202a5016455731cf0773794` |
| `/tmp/mpd-c0-evidence/exact-backend-24.log` | 1 passed in 0.46s； | `acb50bc88917f57929611d63c707e0ccd387dae970fefba6e9100a81f12eba7b` |
| `/tmp/mpd-c0-evidence/exact-backend-25.log` | 1 failed in 0.51s；E   AssertionError: assert [Song(song_id...artwork=None)] == [Song(song_id...artwork=None)]; E; E     At index 0 diff: Song(song_id='6d956727-c522-453c-8f0b-3a603f24d8f6', title='Test Song', file_uri='/tmp/pytest-of-Gold/pytest-276/test_mount_replacement_never_c0/music/a.flac', identity_key='620c464 | `e0b899881966db9f81f3976577a6e622f560d04d66459f57a00538ed16cd65bc` |
| `/tmp/mpd-c0-evidence/exact-existing-budget.log` | 1 passed in 0.89s； | `057a4f811934a7c8e0413d700e4be6b0e9bcd24fc5edea4612ed45c4e19a021e` |
| `/tmp/mpd-c0-evidence/exact-web-01.log` | Test Files  1 failed (1); Tests  1 failed \| 2 skipped (3); Duration  1.73s (transform 416ms, setup 67ms, collect 535ms, tests 34ms, environment 592ms, prepare 134ms)；AssertionError: expected null to match object { …(2) } | `35718b2929638b47be53cfdc1729aec0ca0eefeb9981df2cc87ee25798202e97` |
| `/tmp/mpd-c0-evidence/exact-web-02.log` | Test Files  1 failed (1); Tests  1 failed \| 2 skipped (3); Duration  1.61s (transform 401ms, setup 66ms, collect 524ms, tests 32ms, environment 485ms, prepare 127ms)；AssertionError: expected false to be true // Object.is equality | `1bd9230744154a06a64e2df583a06f9a202f215f14d3af6cc89ace8cca308a3c` |
| `/tmp/mpd-c0-evidence/exact-web-03.log` | Test Files  1 failed (1); Tests  1 failed \| 2 skipped (3); Duration  1.60s (transform 411ms, setup 69ms, collect 535ms, tests 33ms, environment 472ms, prepare 120ms)；AssertionError: expected false to be true // Object.is equality | `2f8ed5a2889fc5199bd806e3149c1c686958fe900ccbf9592c8144f9a087ad81` |
| `/tmp/mpd-c1-evidence/c1-red-00.log` | 1 failed in 0.54s；E       AssertionError: ScanResult(added_song_ids=(), updated_song_ids=(), moved_song_ids=(), missing_song_ids=('7288f9f8-5114-43fe-a0e1-0409a00ae0ad', '1d016b97-0479-4eaa-bae2-ff406ae1235e'), unreadable_song_ids=()); E       assert [Song(song_id...artwork=None)] == [Song(song_id...artwork=None)]; E | `ad87070eb7262c270ee600a054af722aa9150fb34b8ca48cdd36601f6739fda1` |
| `/tmp/mpd-c1-evidence/c1-red-01.log` | 1 failed in 0.46s；E           assert None == ('library_sidecar_signatures',); E            +  where None = <built-in method fetchone of sqlite3.Cursor object at 0x7d31027a40>(); E            +    where <built-in method fetchone of sqlite3.Cursor object at 0x7d31027a40> = <sqlite3.Cursor object at 0x7d31027a40>.fetcho | `13f80acdbbe62c8e2ca42919770fdc21eb5299ccd6a18e499a4c7b3501a6ccb5` |
| `/tmp/mpd-c1-evidence/c1-red-02.log` | 1 failed in 0.60s；E           AssertionError: assert [] == [('known', 'm...lrc', 12, 34)]; E; E             Right contains 2 more items, first extra item: ('known', 'music/known.lrc', None, None); E             Use -v to get more diff | `4db686b46635e02d90f5e9f8ce84d21f9c2d6975c7a4739c61135f8063cd55a8` |
| `/tmp/mpd-c1-evidence/c1-red-03.log` | 1 failed in 0.52s；E           AssertionError: assert [] == [('kept', 'mu...a.lrc', 1, 2)]; E; E             Right contains one more item: ('kept', 'music/a.lrc', 1, 2); E             Use -v to get more diff | `b4df519d85a3828cb8a6f75b9cd1c3fb2b9e915d3960da153ff03b8822f72ab2` |
| `/tmp/mpd-c1-evidence/c1-red-04.log` | 1 failed in 0.52s；E           AssertionError: assert [] == [('kept', 'mu...a.lrc', 1, 2)]; E; E             Right contains one more item: ('kept', 'music/a.lrc', 1, 2); E             Use -v to get more diff | `4e5fea25fea95b43f04a74f1b3fa993df6b03116ce976f5f822748b8781c6a63` |
| `/tmp/mpd-c1-evidence/c1-red-05.log` | 1 failed in 0.51s；E           AssertionError: assert [] == [('kept', 'mu...a.lrc', 1, 2)]; E; E             Right contains one more item: ('kept', 'music/a.lrc', 1, 2); E             Use -v to get more diff | `476922fc3a4c0fb90540abab759c28833288b9ffab6704d732f64ad315a71fc7` |
| `/tmp/mpd-c1-evidence/c1-red-06.log` | 1 failed in 0.50s；E           AssertionError: assert [] == [('known', 'm...a.lrc', 1, 2)]; E; E             Right contains one more item: ('known', 'music/a.lrc', 1, 2); E             Use -v to get more diff | `26338218187093c0824a460a7c1bd14070300a6040daf8abb60bd045aca8c163` |
| `/tmp/mpd-c1-evidence/c1-red-07.log` | 1 failed in 0.51s；E           AssertionError: assert [] == [('known', 'm...a.lrc', 1, 2)]; E; E             Right contains one more item: ('known', 'music/a.lrc', 1, 2); E             Use -v to get more diff | `3b6573ff93badeafd041ae61b07d71a3a19c3fc01c32f5a5b41e8452821ce894` |
| `/tmp/mpd-c1-evidence/c1-red-08.log` | 1 failed in 0.49s；E           AssertionError: assert [] == [('known', 'm...a.lrc', 1, 2)]; E; E             Right contains one more item: ('known', 'music/a.lrc', 1, 2); E             Use -v to get more diff | `64f0df3edfe94df2fe190a3b348e492ea2eaee8b2944c0bf941ad41c99d95725` |
| `/tmp/mpd-c1-evidence/c1-red-09.log` | 1 failed in 0.49s；E           AssertionError: assert [] == [('a', 'music..., None, None)]; E; E             Right contains one more item: ('a', 'music/曲.lrc', None, None); E             Use -v to get more diff | `7877229eb5f4f8007a1e1837f9a7c7c20cfd1f542ea937b63b684e0678270319` |
| `/tmp/mpd-c1-evidence/c1-red-10.log` | 1 failed in 0.47s；E       Failed: DID NOT RAISE ValidationError | `89d255fa7e5f2c7505221f9b2b8f6dd0e0c4c3e7ab6d793786c8f87f1dd1b2b6` |
| `/tmp/mpd-c1-evidence/c1-red-11.log` | 1 failed in 0.49s；E       Failed: DID NOT RAISE ValidationError | `5718e97c106678b847dc5d17fa43dc02a1a597c4edbbd109c6228343d83bc38e` |
| `/tmp/mpd-c1-evidence/c1-red-12.log` | 1 failed in 0.48s；E       Failed: DID NOT RAISE ValidationError | `a3553ea8203140f4abed16adcd76cb68afb2a83111a42eed32abdaf2e96f96d8` |
| `/tmp/mpd-c1-evidence/c1-red-13.log` | 1 failed in 0.51s；E       Failed: DID NOT RAISE ValidationError | `2dab6b352183c64adfe88d0b00820f499b32aa667f3d115ceabb2d207c9fb057` |
| `/tmp/mpd-c1-evidence/c1-red-14.log` | 1 failed in 0.45s；E           AssertionError: assert [] == [('a', 'music..., None, None)]; E; E             Right contains one more item: ('a', 'music/a.lrc', None, None); E             Use -v to get more diff | `aae8979ad0e8788c2f171a7ddc1ce61b5eb2b1ae1c562964a1a006589b2a8abe` |
| `/tmp/mpd-c1-evidence/c1-red-move.log` | 1 failed in 0.56s；E           AssertionError: assert [] == [('kept', 'mu..., None, None)]; E; E             Right contains one more item: ('kept', 'music/旧.lrc', None, None); E             Use -v to get more diff | `86ef139635da78a96a5cede6e810f68570d4fef68125c65798567a8e4dd012c8` |
| `/tmp/mpd-c2-evidence/red-atomic.log` | 1 failed in 0.59s；E   assert (0,) == (2,); E; E     At index 0 diff: 0 != 2; E     Use -v to get more diff | `6ffd67f1c97716377c1e5e9e58323d7b50de302e35949d0e57e742360777f4f9` |
| `/tmp/mpd-c2-evidence/red-backfill.log` | 1 failed in 0.57s；E   AssertionError: successful legacy signatures were not persisted; E   assert 0 == 2; E    +  where 0 = len(()); E    +    where () = ScanBaseline(songs=(_BaselineSong(song_id='4ca5c0cf-ceb0-493c-a639-cc4438671c61', title='MP3 Song', file_uri='/tmp/pyt...zone.utc), artwork=None)), sidecars=(), fin | `f6f364177afdf7cfe739137f9d03088b4cde07f9af1450f326f738dcef5481af` |
| `/tmp/mpd-c2-evidence/red-deep_reconciliation_detects_same_stat_content_change.log` | 1 failed in 0.59s；E   AssertionError: assert 2 == 0; E    +  where 2 = sum(dict_values([1, 1])); E    +    where dict_values([1, 1]) = <built-in method values of Counter object at 0x78c7940470>(); E    +      where <built-in method values of Counter object at 0x78c7940470> = Counter({'/tmp/pytest-of-Gold/pytest-385/t | `e9b21314b96e5b0985db1b656ee258001ba5ddab35641890d0367df5b5ce44a7` |
| `/tmp/mpd-c2-evidence/red-media_changed_during_prepare_is_retried.log` | 1 failed in 0.51s；E   AssertionError: assert Song(song_id='3bc9988f-9409-4d95-bb03-fdc1b3524ffd', title='Test Song', file_uri='/tmp/pytest-of-Gold/pytest-386/test_...AVAILABLE', last_seen_at=datetime.datetime(2026, 10, 12, 7, 17, 9, 191354, tzinfo=datetime.timezone.utc), artwork=None) is None | `cc3556171fa7d07d51c23a85c549fa2aebb261210f7b738dbc260a44fafb9e78` |
| `/tmp/mpd-c2-evidence/red-prepare_cancellation_never_commits.log` | 1 failed in 1.74s；E   Failed: DID NOT RAISE CancelledError | `83847367fcf357d4e10466779d5f015e4ffab8c23f46640586f360912aa5d728` |
| `/tmp/mpd-c2-evidence/red-stale_baseline_cannot_overwrite_new_commit.log` | 1 failed in 0.54s；E   Failed: stale prepared result overwrote a newer Library commit | `6337ec4c4ed8dfd872e2a6e4b9fabb49bfbdd1eb5378a5adcb05888de3fd97c7` |
| `/tmp/mpd-c2-stat-fix-evidence/red-known.log` | 1 failed in 0.53s；E   PermissionError: fixture entry stat unavailable | `78cf518c163101852de0aedb9cc7584ea9fc371164736e952a1edab862981be1` |
| `/tmp/mpd-c2-stat-fix-evidence/red-new.log` | 1 failed in 0.78s；E           AssertionError: assert () == (PosixPath('/...sic/a.flac'),); E; E             Right contains one more item: PosixPath('/tmp/pytest-of-Gold/pytest-539/test_inventory_entry_stat_fail0/music/a.flac'); E             Use -v to get more diff | `4ccbfd94d7fcc2c0facfc86313ef82991d1eea7c5c1eb5e8637783aa02ba25a4` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-00.log` | 1 passed in 0.47s； | `71cecd4a03d26fc192e472bf26020cdc2172e564ac64a719b16960d8dffd73a1` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-01.log` | 1 failed in 0.52s；E   AssertionError: {'/tmp/pytest-of-Gold/pytest-639/test_baseline_conflict_reuses_0/music/a.flac': 2, '/tmp/pytest-of-Gold/pytest-639/test_baseline_conflict_reuses_0/music/sidecar.mp3': 2}; E   assert 2 == 1 | `561435062a132573a67fc1acf0c51813e810a55d1895b9caae3682c5f4b86755` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-02.log` | 1 failed in 0.50s；E   AssertionError: [('update',), ('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-640/test_precheck_failure_never_bl0/music/a.flac', True), ('uri', '/tmp/pytest-of-Gold/pytest-640/test_precheck_failure_never_bl0/music/sidecar.mp3', True)]; E   assert 2 == 0; E    +  where 2 = <built-in | `2fd502486ba4c385ad33ac605d80adb820e2738cc8613366ddc155e825016d69` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-03.log` | 1 failed in 0.51s；E   AssertionError: [('update',), ('status',), ('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-641/test_precheck_failure_nev...usic/a.flac', True), ('uri', '/tmp/pytest-of-Gold/pytest-641/test_precheck_failure_never_bl0/music/sidecar.mp3', True)]; E   assert 2 == 0; E    +  where 2 = < | `c5f5580d308e5bc01a78b957cb78c746b31a704b3f07fb26e24ae3541178c4b5` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-04.log` | 1 failed in 0.52s；E   AssertionError: [('update',), ('status',), ('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-642/test_precheck_failure_nev...usic/a.flac', True), ('uri', '/tmp/pytest-of-Gold/pytest-642/test_precheck_failure_never_bl0/music/sidecar.mp3', True)]; E   assert 2 == 0; E    +  where 2 = < | `0058f7fcfbf817f46cdb8ca3f5794c9d815cd466f2ef03e70f5292c5f8e20452` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-05.log` | 1 failed in 0.49s；E   assert [1] == [2]; E; E     At index 0 diff: 1 != 2; E     Use -v to get more diff | `123becf1839399813d2938cdba72e90cbdd5ac54a14370466496367ffe7d836e` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-06.log` | 1 failed in 0.50s；E   AssertionError: [('update',), ('status',), ('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-644/test_accepted_update_is_n...usic/a.flac', True), ('uri', '/tmp/pytest-of-Gold/pytest-644/test_accepted_update_is_not_re0/music/sidecar.mp3', True)]; E   assert 2 == 1; E    +  where 2 = < | `789b4e07393390a467c89a129a80fa61575c099ff4c52acfbcc65a99483565f3` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-07.log` | 1 failed in 0.50s；E   AssertionError: assert 2 == 1; E    +  where 2 = <built-in method count of list object at 0x7d27cb4e00>(('update',)); E    +    where <built-in method count of list object at 0x7d27cb4e00> = [('update',), ('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-645/test_update_outcome_is_re | `4c1e4cd3d8f679c5ee15260b92b95a3bc82d87237982db3cfa88936860f43243` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-08.log` | 1 failed in 0.51s；E   AssertionError: [('update',), ('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-646/test_update_outcome_is_reread_0/music/a.flac', True), ('uri', '/tmp/pytest-of-Gold/pytest-646/test_update_outcome_is_reread_0/music/sidecar.mp3', True)]; E   assert ('update',) == ('status',); E; E    | `7367ef48ca81b81b9425b6f4836398a964418905277f661664a7535d512010d5` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-09.log` | 1 failed in 0.55s；E   AssertionError: [('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-647/test_local_delta_updates_only_0/music/added.flac', True)]; E   assert ('update',) == ('status',); E; E     At index 0 diff: 'update' != 'status'; E     Use -v to get more diff | `5c96485f59d859ee8133cbeb15784da1f3dbaae26164133ac848f27ff0aebd6b` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-10.log` | 1 failed in 0.53s；E   AssertionError: [('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-648/test_local_delta_updates_only_0/music/a.flac', True)]; E   assert ('update',) == ('status',); E; E     At index 0 diff: 'update' != 'status'; E     Use -v to get more diff | `a39b30fc4f464c7cb801ff6c907b118a2805c8f8c60f5aec181485a6da62b9bc` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-11.log` | 1 failed in 0.50s；E   AssertionError: [('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-649/test_local_delta_updates_only_0/music/a.flac', False)]; E   assert ('update',) == ('status',); E; E     At index 0 diff: 'update' != 'status'; E     Use -v to get more diff | `c26159f607c05d4bafc2b38e31f25ba10ba93f05ff4a7b27872be1d4f88b3a09` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-12.log` | 1 failed in 0.49s；E   AssertionError: [('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-650/test_local_delta_updates_only_0/music/a.flac', False), ('uri', '/tmp/pytest-of-Gold/pytest-650/test_local_delta_updates_only_0/music/moved.flac', True)]; E   assert ('update',) == ('status',); E; E     At index 0  | `c05ae465642d7582ae8399179626820ace33403095571ccd5510f14d92ac07db` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-13.log` | 1 failed in 0.52s；E   AssertionError: [('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-651/test_local_delta_updates_only_0/music/a.flac', True)]; E   assert ('update',) == ('status',); E; E     At index 0 diff: 'update' != 'status'; E     Use -v to get more diff | `552b2df353db6ecbaa83a073c0799917f62b88b1124abb1fb44db0179f0a9468` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-14.log` | 1 failed in 0.48s；E   AssertionError: assert ['update', 'status'] == ['status']; E; E     At index 0 diff: 'update' != 'status'; E     Left contains one more item: 'status'; E     Use -v to get more diff | `4a046a17eda233afadfb74d108c32fce2622559cb1143c8a0f146295e94e9903` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-15.log` | 1 passed in 0.43s； | `0dff5a7b4f7b627aa5d5ba9609862b0c83a9c34efeac8569b0ff66edb0c0e2d9` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-16.log` | 1 passed in 0.42s； | `791acbb2840ecff621592488f8e65512e312896e3865560d4000495c22ef5d13` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-17.log` | 1 passed in 0.40s； | `59b9466559aeabf218a54ec041fd83cd357cf9bf1d80a17c47aab62ed0c205bf` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-18.log` | 1 failed in 0.44s；E   AssertionError: ['/tmp/pytest-of-Gold/pytest-656/test_config_and_mapper_constru0/music']; E   assert ['/tmp/pytest...nstru0/music'] == []; E; E     Left contains one more item: '/tmp/pytest-of-Gold/pytest-656/test_config_and_mapper_constru0/music'; E     Use -v to get more diff | `23148a812049008d54a030825ea5b37b8d67c3929a367ef04d4abfb066b87552` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-19.log` | 1 passed in 0.40s； | `59b9466559aeabf218a54ec041fd83cd357cf9bf1d80a17c47aab62ed0c205bf` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-20.log` | 1 passed in 0.40s； | `59b9466559aeabf218a54ec041fd83cd357cf9bf1d80a17c47aab62ed0c205bf` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-21.log` | 1 passed in 0.41s； | `f6b6e232e0345fa742cf57cbc60c8884709a6f029bd43161ca6e812c9175f2a8` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-22.log` | 1 passed in 0.41s； | `f6b6e232e0345fa742cf57cbc60c8884709a6f029bd43161ca6e812c9175f2a8` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-23.log` | 1 failed in 0.45s；E   AssertionError: [PosixPath('/tmp/pytest-of-Gold/pytest-661/test_mapper_first_use_canonica0/alias')]; E   assert [PosixPath('/...nica0/alias')] == []; E; E     Left contains one more item: PosixPath('/tmp/pytest-of-Gold/pytest-661/test_mapper_first_use_canonica0/alias'); E     Use -v to get more  | `73141b32d9ba3fcb0c526cba6c5940785e081089fe2d3fd96f1727ad66411b8f` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-24.log` | 1 passed in 0.46s； | `acb50bc88917f57929611d63c707e0ccd387dae970fefba6e9100a81f12eba7b` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-25.log` | 1 failed in 0.52s；E   assert 2 == 1 | `e062cefd61e5e50a2ce85e5008f11ecc91f237afb0b08afb5f8c6d47c1fd9b9d` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-26.log` | 1 failed in 0.49s；E   AssertionError: assert [] == [LibraryInven...omplete=True)]; E; E     Right contains one more item: LibraryInventory(root=PosixPath('/tmp/pytest-of-Gold/pytest-664/test_startup_seeds_same_invent0/music'), identity=(92,...test_startup_seeds_same_invent0/music/sidecar.mp3', file_size=2362, file_mt | `56d181a27efb182db60292e486057a5436f311d0e5404ccf8191851667334148` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-27.log` | 1 failed, 1 warning in 0.53s；E   AssertionError: valid path configuration blocked lifespan instead of background failure: Invalid application configuration; E   assert ValueError('Invalid application configuration') is None | `6125a71de9ba27cc889e085003ed6132675f99109f17163316e9b82bd5b9f04b` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-28.log` | 1 failed, 1 warning in 0.12s；E   AssertionError: assert 1 == 0; E    +  where 1 = <built-in method count of list object at 0x74f2841400>(('update',)); E    +    where <built-in method count of list object at 0x74f2841400> = [('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-666/test_unchanged_consistent_star0/music/ | `488940a0c7bff21478e6e17b18a4b5324b0150bec1defd69fb71bc6bef5766fd` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-29.log` | 1 failed, 1 warning in 0.13s；E   AssertionError: [('update',), ('status',), ('uri', '/tmp/pytest-of-Gold/pytest-667/test_inconsistent_startup_upda0/music/sidecar.mp3', True), ('uri', '/tmp/pytest-of-Gold/pytest-667/test_inconsistent_startup_upda0/music/a.flac', True)]; E   assert False; E    +  where False = any(<generator obje | `4c92b63ba6a1c26ec63eb9f9cadd2266675ca7c79e72bfdb4f4669ca44749fd8` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-30.log` | 1 failed, 1 warning in 0.04s；E   AssertionError: constructor performed Path.resolve: ['/tmp/pytest-of-Gold/pytest-668/test_constructor_has_no_filesy0', '/tmp/pytest-of-Gold/pytest-668/test_constructor_has_no_filesy0']; E   assert ['/tmp/pytest...s_no_filesy0'] == []; E; E     Left contains 2 more items, first extra item: '/tmp/ | `ab5c86262a8f8a0a165eeac8a86b98aebec86de0402e61c4dd4a37e3918d6d20` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-31.log` | 1 failed, 1 warning in 0.05s；E   AssertionError: constructor performed Path.stat: ['/tmp/pytest-of-Gold/pytest-669/test_constructor_has_no_filesy0', '/tmp/pytest-of-Gold/pytest-669/test_constructor_has_no_filesy0', '/tmp/pytest-of-Gold/pytest-669/test_constructor_has_no_filesy0', '/tmp/pytest-of-Gold/pytest-669/test_constructor | `f803cb385465feeb786959fde596fb5f2bcbf7f53d250bb4836ae59d56a83f67` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-32.log` | 1 failed, 1 warning in 0.04s；E   AssertionError: constructor performed Path.iterdir: ['/tmp/pytest-of-Gold/pytest-670/test_constructor_has_no_filesy0']; E   assert ['/tmp/pytest...s_no_filesy0'] == []; E; E     Left contains one more item: '/tmp/pytest-of-Gold/pytest-670/test_constructor_has_no_filesy0'; E     Use -v to get mor | `d0f7688345f07f7706caec2be6770cfa46c31187401ac0ea97b911d6f8e810be` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-33.log` | 1 failed, 1 warning in 0.10s；E   AssertionError: ['inventory', 'inventory', 'audio']; E   assert 3 == 1; E    +  where 3 = len(['inventory', 'inventory', 'audio']) | `87f7c4f6fda98a8917efa2b896562b3b97028612c3047879d6ad4af10d480e22` |
| `/tmp/mpd-c3-fresh-preflight/c3-red-34.log` | 1 failed, 1 warning in 0.21s；E   AssertionError: ['detector', 'startup']; E   assert ['detector', 'startup'] == ['startup']; E; E     At index 0 diff: 'detector' != 'startup'; E     Left contains one more item: 'startup'; E     Use -v to get more diff | `9ea41ccececfee717e49001f7cb731bc4aab91538d3a05f6f20089759bd786ca` |
| `/tmp/mpd-c3-fresh-preflight/config-os-access-red.log` | 1 failed in 0.46s；E   AssertionError: ['/tmp/pytest-of-Gold/pytest-675/test_config_construction_has_n0/music']; E   assert ['/tmp/pytest...has_n0/music'] == []; E; E     Left contains one more item: '/tmp/pytest-of-Gold/pytest-675/test_config_construction_has_n0/music'; E     Use -v to get more diff | `c85a7b5ee05b1fe689d2b9d42e5a24e24b949e3eb0ad2cfb6e2ff67583fb22a4` |
| `/tmp/mpd-c3-fresh-preflight/config-os-stat-red.log` | 1 failed in 0.46s；E   AssertionError: ['/tmp/pytest-of-Gold/pytest-674/test_config_construction_has_n0/music']; E   assert ['/tmp/pytest...has_n0/music'] == []; E; E     Left contains one more item: '/tmp/pytest-of-Gold/pytest-674/test_config_construction_has_n0/music'; E     Use -v to get more diff | `e02c0c4812f61d0fcf548430c36b871946d720382b739d200460716cb87fcb99` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-body_timeout_and_late_response_cannot_restore_baseline.log` | Test Files  1 failed (1); Tests  1 failed \| 2 skipped (3); Duration  1.74s (transform 433ms, setup 85ms, collect 582ms, tests 36ms, environment 515ms, prepare 142ms)；AssertionError: expected false to be true // Object.is equality | `c208b185d629c30c62c65f5fa5088715e0e81a7184152a3f840b912d86ead856` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-generation-budget.log` | Test Files  1 failed (1); Tests  1 failed \| 14 skipped (15); Duration  1.78s (transform 513ms, setup 75ms, collect 643ms, tests 35ms, environment 488ms, prepare 144ms)；AssertionError: expected false to be true // Object.is equality | `35d076d29ac8a249c31c990a667f65caf4fb656320b6891816be6a286264edfd` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-get_timeout_ends_loading_and_retries.log` | Test Files  1 failed (1); Tests  1 failed \| 2 skipped (3); Duration  1.69s (transform 423ms, setup 79ms, collect 536ms, tests 35ms, environment 500ms, prepare 133ms)；AssertionError: expected false to be true // Object.is equality | `7f6d7358d8fa53ec8731e7257e5eb0e29d35523d7a90606ed7760cca06bd188a` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-initial_snapshot_timeout_reports_and_reconnects.log` | Test Files  1 failed (1); Tests  1 failed \| 2 skipped (3); Duration  1.64s (transform 358ms, setup 66ms, collect 475ms, tests 30ms, environment 552ms, prepare 116ms)；AssertionError: expected null to match object { …(2) } | `6e290ab27a47b4a8203271d6b480dfdce010ce645d4c3935d729e1c55b0fe898` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-new-0.log` | Test Files  1 failed (1); Tests  1 failed \| 12 skipped (13); Duration  1.67s (transform 463ms, setup 58ms, collect 588ms, tests 34ms, environment 511ms, prepare 138ms)；AssertionError: expected +0 to be 1 // Object.is equality | `4ae8bd2be4e0a943b9995376bf65c1c0c36a68ebdeaf70da8057814c6279f0af` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-new-1.log` | Test Files  1 failed (1); Tests  1 failed \| 12 skipped (13); Duration  1.72s (transform 473ms, setup 63ms, collect 617ms, tests 53ms, environment 520ms, prepare 133ms)；AssertionError: expected undefined to match object { code: 'READ_TIMEOUT' } | `0f42bf55c4fd8e03671d0c70643e3f916c5a01c551c79debdd3436f53c40e881` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-new-2.log` | Test Files  1 failed (1); Tests  1 failed \| 12 skipped (13); Duration  1.63s (transform 444ms, setup 67ms, collect 577ms, tests 36ms, environment 484ms, prepare 129ms)；AssertionError: expected false to be true // Object.is equality | `ec85bb8d26ce02ec8fe9ef362c57b0f17781454f56270f7c12352e81f5033b94` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-new-3.log` | Test Files  1 failed (1); Tests  1 failed \| 12 skipped (13); Duration  1.78s (transform 503ms, setup 65ms, collect 651ms, tests 32ms, environment 515ms, prepare 143ms)；AssertionError: expected false to be true // Object.is equality | `271fcd5fcebbc738cc38921e9a7f6240f56eb682390b2ee68e1f23f71ec39d53` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-new-4.log` | Test Files  1 failed (1); Tests  1 failed \| 12 skipped (13); Duration  1.73s (transform 465ms, setup 77ms, collect 592ms, tests 30ms, environment 517ms, prepare 135ms)；AssertionError: expected undefined to match object { code: 'READ_TIMEOUT', …(1) } | `400b5128f1ebacc18cc51ab62a3abffba9c5cc8281f8b0000ab6904d1bb3474e` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-new-5.log` | Test Files  1 passed (1); Tests  4 passed \| 9 skipped (13); Duration  1.72s (transform 490ms, setup 88ms, collect 617ms, tests 37ms, environment 500ms, prepare 142ms)； | `6dd446ddf1adf2ad35d9c1c504973869f7bedeb85f5d37a6e23a9646bcacb91e` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-new-6.log` | Test Files  1 failed (1); Tests  1 failed \| 12 skipped (13); Duration  1.71s (transform 431ms, setup 92ms, collect 536ms, tests 33ms, environment 521ms, prepare 141ms)；AssertionError: expected undefined to match object { code: 'READ_TIMEOUT' } | `a7b09cc38b1fcda701a18e55827c5c7cbf25216727513612123ec09ae930a061` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-new-7.log` | Test Files  1 failed (1); Tests  2 failed \| 10 skipped (12); Duration  4.90s (transform 2.69s, setup 68ms, collect 3.50s, tests 298ms, environment 518ms, prepare 125ms)；AssertionError: expected '状态读取异常，保留最后事实重新读取连接中断 · 只读；等待完整状态恢复重新…' to contain '初始状态读取超时，正在重连'; AssertionError: expected '状态读取异常，保留最后事实重新读取连接中断 · 只读；等待完整状态恢复重新…' to contain '状态读取超时，请重试' | `63004c47299f831a7ffc2cbe7edfcbb859ed2755e509253e37eb8011837a2e82` |
| `/tmp/mpd-c4-evidence-d7yw10mo/red-resource-notice.log` | Test Files  1 failed (1); Tests  1 failed \| 13 skipped (14); Duration  1.97s (transform 613ms, setup 66ms, collect 620ms, tests 253ms, environment 512ms, prepare 123ms)；AssertionError: expected true to be false // Object.is equality | `63574cb079ff8e83e218d16a5af2bfc596e0075cd010822668ccb2069952b5ef` |
