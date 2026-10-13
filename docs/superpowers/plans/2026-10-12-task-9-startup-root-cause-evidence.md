# Task 9 Startup Library Reconciliation — root-cause evidence

日期：2026-10-12（Asia/Shanghai）。当前状态：C1/C2/C3/C4 已实现；本轮 C3 fresh gate 完整 backend GREEN，C4 完整 Web、typecheck/build/Ruff GREEN。C4 满足本地进入 C5 的条件，C5 最终验收/远程交付尚未执行；最新节点、回归结果及审查限制见末尾 C4 记录。

## 基线与交付事实

- `git ls-remote`、`git fetch origin feature/task-9-web` 和本地 history 重新核对：远端/本地基线均为 `098d6eaea81495d1686a09f9e0ee68768610ed7e`。起始 `git status --short` 无输出。
- 已创建 `fix/task-9-startup-library-reconciliation`，从远端目标分支开始；未合并 main、未提交、未 push、未创建 PR。
- 最近提交：098d6ea（部署能力/Compose文档）、38d87a5（consume不变时恢复暂停）、81129b9（CI Ruff基线）、c442028（Task9/NAS与容器CI）、14c6239（Task8）。扫描协调器、detector和main装配来自c442028；scanner更早已有全量解析行为。
- 最新 [CI run 38203973292](https://github.com/qyxx2/MPD-Server/actions/runs/38203973292) 对应完整基线SHA，validate/image均success；读取jobs确认后端、Web检查及linux/amd64、linux/arm64构建发布步骤成功。这是旧SHA事实，不证明修复通过。
- `.github/workflows/container.yml` 的push过滤只有main、feature/**、codex/**，不包括fix/**；workflow_dispatch已存在。计划将修复分支纳入过滤，远程操作仍需显式授权。
- 原`.venv`：Python3.14.4、pytest9.1.1、Ruff0.16.9；已读server/requirements.txt，无环境修改。

## 源码证据

行号以基线SHA为准。

| 假设 | 代码核对与调用链 | 结论 |
|---|---|---|
| constructor阻塞lifespan | `library_change_detector.py:52–65` resolve/stat/read_signatures；`main.py:163–170`同步构造runtime，早于yield | 确认；不仅read_signatures，resolve/stat也属于文件系统I/O |
| 每进程startup全扫 | `library_runtime.py:51–57` request_scan(None,"startup")→sync.run | 确认；启动重新确认是合同，全量解析不是必要条件 |
| 所有音频重解析/哈希 | `library_scanner.py:172–245,284–296`，parse/hash早于existing查询，完全未比较已存签名 | 确认 |
| 长事务阻塞状态/资源 | `library_sync_service.py:165–242` outer run_transaction中scan_full/scan_paths；`database.py:173–237`同一DB asyncio锁覆盖await和nested调用；解析/哈希直接同步执行 | 确认；同时有数据库锁与event loop阻塞 |
| 重复inventory | detector构造先读，run先check再sleep；sync `_scan:150,175`扫描前to_thread与事务内同步read_signatures，加上scanner `_walk` | 确认；不是只有一次2秒轮询 |
| 无条件MPD更新 | scanner `_apply_batch`提交回调→`_finalize:249–253`无条件update；sync注入自己为updater | 确认；无变化也update |
| 错误重读全库 | MediaMetadataError不是OSError，逃出`_scan_files`；sync.run中scanned只有_scan成功后才置True，失败保持原job进入重试 | 确认；正常文件准备结果丢失，重试全job |
| Web无限初始等待 | `web/src/services/realtime.ts`无initial timer；`api.ts` GET fetch/json无deadline；重读重试只处理已经reject的Promise | 确认静态缺口；未伪称已经有超时RED结果 |

额外启动证据：`config.py:34–39`的music_root validator同步is_dir/os.access；`player/music_uri.py:7`的mapper constructor同步resolve，main构造真实Adapter时执行。它们必须与Library constructor一起解除音乐根I/O，否则缺失/慢挂载仍可能阻断HTTP。配置格式错误继续是startup失败，音乐根运行时不可用改由后台校准报告。

附加约束：ScanBatch只有songs/unreadable/prefix；repository `apply_scan_batch:775–800`仅把前两类计为seen。直接跳过未变化文件会将其标MISSING。现有schema v4没有sidecar签名；停机期间的LRC增删改不能由音频签名推知。

## 临时隔离动态探针

运行：`PYTHONPATH=. .venv/bin/python /tmp/mpd-task9-startup-evidence/probe.py`。脚本在TemporaryDirectory里创建SQLite和从测试conftest解压的一首FLAC；Player仅继承MockMPD，update记录调用、status返回not updating。没有读取用户媒体、连接MPD/NAS/DAC或启动Docker。

1. 首轮scanner入库后，重建sync/scanner并调用startup `_scan`及 `_confirm`；spy真实parse/hash。结果：parse=1，hash=1，update=1，SYNCED。新目标是0/0/0。
2. spy `read_signatures`构造detector，再check_once：constructor=1，总计=2。新目标是constructor=0，startup inventory交接后首次轮询先等待间隔。
3. 子类 `_scan_files`用async entered/release barrier暂停；独立Task调用repo.list_songs及run_transaction(SELECT 1)，100ms shield预算内两个Task均未完成；释放后均完成。这隔离证明外层数据库锁问题，不依靠慢磁盘猜测。
4. 添加排序在正常FLAC之后的损坏b.mp3，让真实正常parser运行、损坏路径抛MediaMetadataError，重复原job两次：`['a.flac','b.mp3','a.flac','b.mp3']`。新目标正常a只准备一次，第二次只b。

这些探针证明当前根因；没有代替真实lifespan/HTTP/WS、worker thread和Web fake timer的永久RED测试。临时脚本不是生产文件，也不是可交付测试资产；批准后Batch C0把证明落到仓库测试，不依赖/tmp保留。

## Fresh baseline regression

原`.venv`从repo root运行，显式APP_ENV=development、MPD_MODE=mock；DATABASE_PATH/CONFIG_DIR/MUSIC_ROOT全部指向本轮mktemp目录。测试媒体、DB均自有。

- 后端：services/test_library_scanner、test_library_change_detector、test_library_sync_service；invariants/test_library_sync、test_library_sync_wire、test_realtime_library；repositories/test_library_reconciliation：**74 passed，2.11s**。既有Starlette/httpx deprecation warning保留，未改依赖。
- Web：realtime/library-sync/resource-cache，单worker：**3 files / 28 passed，6.86s**。
- 未运行完整回归：本轮仅调查/文档，尚未执行implementation Batch。已有绿色结果不能抵扣十项corrective RED或后续fresh acceptance。

## 旧合同冲突与范围

旧Library §7.2把“启动扫描/确认”与“update已接受才SYNCED”绑定；需明确启动扫描是持久签名差异校准，允许先精确确认一致而不update。旧scanner测试要求MediaMetadataError整批回滚（test_step4_failed_parse_does_not_overwrite_known_good_metadata、test_step7_parse_failure_never_applies_partial_batch）；批准新合同后定向替换整批失败断言，但保留旧元数据不被失败清空、引用不丢等断言。

最终NAS计划、Task9历史acceptance仍有真实设备/用户Gate；不据本轮Mock结果关闭。其它已知/新发现且无关缺陷不在本corrective中处理。


## C0 fresh 执行记录 — 2026-10-12（Asia/Shanghai）

用户本轮明确授权只执行 C0；不将此授权扩展到 C1 生产修改。当前 spec/plan 原有 DRAFT 状态未改。

### Checkout 与范围

- 本轮起始分支 `fix/task-9-startup-library-reconciliation`，完整 HEAD `098d6eaea81495d1686a09f9e0ee68768610ed7e`；最终 HEAD 未变。
- 起始 dirty：README、2026-09-24 Library spec、2026-09-25 Architecture spec 已修改；corrective spec、Batch plan、本证据文档已未跟踪。全部保留；本轮不修改前述 README/spec/plan。
- 本轮新增且只新增计划指定的五个测试文件（下表 I/A/P/C/W），更新本证据记录。生产文件、依赖、配置、数据库、CI 全部零修改；无 commit/push/PR。
- Linux ARM64；现有 `.venv` Python 3.14.4 / pytest 9.1.1 / Ruff 0.16.9。已核对 `server/requirements.txt`，没有安装或改动依赖。
- 每次 backend 命令都建立新的自有临时根，`APP_ENV=development MPD_MODE=mock`；`DATABASE_PATH/CONFIG_DIR/MUSIC_ROOT` 指向该根（先建 config/music）。测试内部另用 tmp_path 的 SQLite/音乐。Web 使用现有 node_modules、单 worker。不访问用户媒体或真实 MPD/NAS/DAC，不运行 Docker。

### 永久资产与测试装配

| 简称 | 永久测试文件 |
|---|---|
| I | `server/tests/invariants/test_startup_library_reconciliation.py` |
| A | `server/tests/api/test_startup_readiness.py` |
| P | `server/tests/services/test_library_scan_prepare.py` |
| C | `server/tests/repositories/test_library_scan_commit.py` |
| W | `web/tests/invariants/startup-readiness.test.ts` |

I 使用复制的正常 FLAC/MP3/LRC、真实 parser/hash 与重新构造的 Repository/Scanner/Sync/Runtime；等待真实 `LibraryChangedEvent` 和 SYNCED 后关闭，每次重启使用同一 SQLite。refs 证明包含 Playlist/Favorites/History。第一轮 v4 baseline 无 sidecar 辅助表；C0 不伪造完整 v5 签名，C1/C2 实现后同一真实生命周期用例须再次运行来证明完整持久签名语义。

A 使用新 FastAPI app + `main.lifespan` + 真实 state/Library/WS routes，避开 legacy global-app conftest 的 owner 取消。thread entered/release barrier 位于当前 `_scan_files`；在 barrier 未释放时，以同一个 1 秒窗口观察三个读取。lifespan 进入有单独 1 秒预算。finally 释放 barrier、排空 futures、关闭 TestClient；另有线程 watchdog 防止 event loop 卡住时测试无法退出。读取成功后还须校验旧 Song IDs、WS snapshot 与 revision。

P 的 async barrier 独立隔离长 DB 锁；SELECT 1/list_songs 的 Task 从测试 Task 创建，不继承扫描事务。parse/hash 的 thread barrier 包裹真实 I/O，并以 event-loop 外 watchdog 在 1.2 秒后放行；验证 event loop 进展、独立事务在放行前完成及媒体 I/O 的线程身份。没有以仅把测试 barrier 放到 worker 来伪造生产线程行为。

C 的 observed 通过现有 `ScanBatch.model_copy(update=...)` 承载计划内字段，让真实 repository 执行 absence reconciliation；当前行为 RED 是 Song 被置 MISSING，不是缺字段/导入错误。C1 必须将其变为正式模型字段。mount `during_prepare` 使用真实 sync，保留现有安全 GREEN；`before_scanner_commit` 在完整 inventory/prepare 已结束、现有公共 `scan_full` wrapper 调用 `_apply_batch` 前替换自有根，暴露 wrapper 缺少跨边界 root 验证。**没有把“最后安全检查之后才发生的外部变化”误当成规范禁止的行为**；C2 需迁移此 seam 到真实 prepare/commit。

W 只替换 transport/时钟，使用现有 API/realtime/library store。10,000ms 默认预算，永久 pending fetch、已返回 headers 的 pending JSON body均不合作 abort；还有迟到 body、重连、GET 仅恢复只读、新 initial 恢复写权限的断言。不引入尚不存在的超时参数/接口。

### 十项 proof → 实际行为

| 用户项 | 精确节点 | Fresh 结论 |
|---|---|---|
| 1 | I::test_persisted_second_start_skips_parse_and_hash | RED：第二次真实 runtime 启动 parse/hash `(2,2)`，期待 `(0,0)` |
| 2 | A::test_http_ws_and_library_read_during_startup_prepare | RED：lifespan True；state/library/ws 均 False，超过 barrier 下 1 秒预算 |
| 3 | P::test_prepare_releases_database_lock；P::test_slow_media_io_runs_without_transaction[parse/hash] | RED：两个独立 DB 读取完成数 `0 != 2`；真实 parse/hash 均令 event loop 停顿约 1.21 秒 |
| 4 | I::test_unchanged_consistent_startup_does_not_update | RED：URI 全一致并已精确确认，update `1 != 0`；Queue/status 保护通过 |
| 5 | I::test_inconsistent_startup_updates_once_then_confirms | RED：update 确实 1 次、postcheck 一致，但日志从 update 开始，缺 precheck；不是多次 update 的伪证据 |
| 6 | I::test_reconcile_only_related_paths[add/modify/delete/move/lrc_add/lrc_modify/lrc_delete] | 七项均 RED：重启差异校准解析无关音频。保 Song ID、引用、歌词 fallback 的前置行为断言通过；路径 parse/hash 期望同时比较 |
| 7 | C::test_mount_replacement_never_commits_mass_missing[during_prepare/before_scanner_commit] | 原 sync 保护 GREEN；scanner wrapper 跨准备/提交边界 RED，空旧根后替换导致已提交 Song 快照变化（MISSING） |
| 8 | I::test_corrupt_path_retry_does_not_repeat_good_media[new/known] | 两项 RED：连续两次坏路径失败、随后真实媒体恢复；`(good_committed, good_parse, good_hash)=(False,3,3)`，期待 `(True,1,1)`。失败间新坏 Song 未伪造，已知坏 metadata/lyrics/artwork 保留 |
| 9 | I::test_constructor_has_no_filesystem_io[resolve/stat/iterdir/open]；I::test_startup_inventory_seed_does_not_immediately_walk；I::test_failed_startup_has_no_competing_detector_walk | resolve/stat/iterdir RED（2/4/1 次），open 为已有 GREEN（0 次）；虚拟时钟尚未前进却累计 5 次遍历，期待 1；失败 startup 仍出现 detector 竞争遍历 |
| 10 | W::initial_snapshot_timeout_reports_and_reconnects；W::get_timeout_ends_loading_and_retries；W::body_timeout_and_late_response_cannot_restore_baseline | 三项 RED：首帧预算到期 error 仍 null；fetch/body 到期 Promise 均未 settle，loading/迟到恢复后续断言保留供 C4 GREEN 验证 |

另增 C::test_observed_unchanged_uri_is_not_missing：RED，两个 observed URI 被当作 absence，`ScanResult.missing_song_ids` 含两个 Song。no-op revision 保护断言仍保留。

60 秒确认预算不包含 prepare 的已有保护：本轮精确运行 `server/tests/services/test_library_sync_service.py::test_confirmation_budget_starts_after_scanner_commit`，GREEN；其 SlowScanner 将 prepare 时间推进 120 秒。该节点也在指定 74 项基线集合内。没有将其已有 GREEN 伪称新增缺陷 RED。

### 每个 exact 节点的 fresh 账本

下表是最终测试源对应的独立进程逐节点运行；不是只用全套结果推断。backend 每条命令为 `.venv/bin/python -m pytest -q --tb=short '<完整file>::<node>'`；Web 为 `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t '<node>' --maxWorkers=1 --minWorkers=1`。失败均为实际 AssertionError；没有缺失接口导入或 collection error。

| 完整节点（文件简称见上） | 结果 | pytest / Vitest 观察 |
|---|---|---|
| `I::test_persisted_second_start_skips_parse_and_hash` | RED | 1 failed, 1 warning in 0.20s |
| `I::test_unchanged_consistent_startup_does_not_update` | RED | 1 failed, 1 warning in 0.13s |
| `I::test_inconsistent_startup_updates_once_then_confirms` | RED | 1 failed, 1 warning in 0.11s |
| `I::test_reconcile_only_related_paths[add]` | RED | 1 failed, 1 warning in 0.13s |
| `I::test_reconcile_only_related_paths[modify]` | RED | 1 failed, 1 warning in 0.12s |
| `I::test_reconcile_only_related_paths[delete]` | RED | 1 failed, 1 warning in 0.12s |
| `I::test_reconcile_only_related_paths[move]` | RED | 1 failed, 1 warning in 0.13s |
| `I::test_reconcile_only_related_paths[lrc_add]` | RED | 1 failed, 1 warning in 0.11s |
| `I::test_reconcile_only_related_paths[lrc_modify]` | RED | 1 failed, 1 warning in 0.12s |
| `I::test_reconcile_only_related_paths[lrc_delete]` | RED | 1 failed, 1 warning in 0.13s |
| `I::test_corrupt_path_retry_does_not_repeat_good_media[new]` | RED | 1 failed, 1 warning in 0.11s |
| `I::test_corrupt_path_retry_does_not_repeat_good_media[known]` | RED | 1 failed, 1 warning in 0.11s |
| `I::test_constructor_has_no_filesystem_io[resolve]` | RED | 1 failed, 1 warning in 0.05s |
| `I::test_constructor_has_no_filesystem_io[stat]` | RED | 1 failed, 1 warning in 0.05s |
| `I::test_constructor_has_no_filesystem_io[iterdir]` | RED | 1 failed, 1 warning in 0.05s |
| `I::test_constructor_has_no_filesystem_io[open]` | GREEN 保护 | 1 passed, 1 warning in 0.02s |
| `I::test_startup_inventory_seed_does_not_immediately_walk` | RED | 1 failed, 1 warning in 0.12s |
| `I::test_failed_startup_has_no_competing_detector_walk` | RED | 1 failed, 1 warning in 0.20s |
| `A::test_http_ws_and_library_read_during_startup_prepare` | RED | 1 failed, 1 warning in 1.59s |
| `P::test_prepare_releases_database_lock` | RED | 1 failed in 1.54s |
| `P::test_slow_media_io_runs_without_transaction[parse]` | RED | 1 failed in 1.67s |
| `P::test_slow_media_io_runs_without_transaction[hash]` | RED | 1 failed in 1.71s |
| `C::test_observed_unchanged_uri_is_not_missing` | RED | 1 failed in 0.49s |
| `C::test_mount_replacement_never_commits_mass_missing[during_prepare]` | GREEN 保护 | 1 passed in 0.46s |
| `C::test_mount_replacement_never_commits_mass_missing[before_scanner_commit]` | RED | 1 failed in 0.51s |
| `W::initial_snapshot_timeout_reports_and_reconnects` | RED | 独立 `-t`，1 failed；其余仅由 -t 过滤，无显式 skip/xfail |
| `W::get_timeout_ends_loading_and_retries` | RED | 独立 `-t`，1 failed；其余仅由 -t 过滤，无显式 skip/xfail |
| `W::body_timeout_and_late_response_cannot_restore_baseline` | RED | 独立 `-t`，1 failed；其余仅由 -t 过滤，无显式 skip/xfail |

最终永久新测试：backend **23 RED / 2 GREEN（25 节点）**；Web **3 RED（3 节点）**。RED 保留为普通失败测试；未改旧测试、未 skip/xfail/删除/放宽断言。

### Fresh baseline / relationships / full

所有命令从 repo root 运行；下表结果来自本轮新进程，不能用此前调查/CI GREEN 抵扣。

| 集合 / 命令 | 实际结果 | 状态 |
|---|---|---|
| 新 backend 四文件（最终源码再次运行） | 23 failed, 2 passed, 1 warning in 6.19s | 预期 RED；0 errors |
| 指定 backend 基线 7 文件（scanner/detector/sync service、library_sync/library_sync_wire/realtime_library、library_reconciliation） | 74 passed，2.09s | GREEN |
| 指定 Web 基线（realtime/library-sync/resource-cache）单 worker | 3 files / 28 passed，7.36s | GREEN |
| Batch plan 完整 backend 关系集；追加 `-p server.tests.support.playback` | 23 failed, 221 passed，19.11s | 只有登记 RED，0 errors |
| Batch plan Web 关系集单 worker | 1 failed / 8 passed files；3 failed / 75 passed tests，16.04s | 只有登记 RED |
| `.venv/bin/python -m pytest -q --tb=short server/tests` 最终源码 | 25 failed, 1562 passed，96.98s | **FULL FAILED**：23 corrective RED + 2 旧环境假设冲突 |
| `npm --prefix web run test -- --run --maxWorkers=1 --minWorkers=1` | 1 failed / 29 passed files；3 failed / 299 passed tests，56.25s | **FULL FAILED**：3 corrective RED |
| `npm --prefix web run typecheck` | exit 0，16.96s（进程 wall time） | GREEN |
| `npm --prefix web run build` | exit 0；Vite built in 2.78s | GREEN；dist 为忽略产物 |
| `.venv/bin/python -m ruff check server/app server/tests` 最终运行 | All checks passed，exit 0 | GREEN |

精确命令/关系集合与 [Batch plan 验证段](2026-10-12-task-9-startup-library-reconciliation-batch-plan.md#可复用fresh验证命令与结果纪律)一致，仅增加 traceback 格式选项及以下已说明的 fixture 注册。临时完整 stdout/traceback 位于 `/tmp/mpd-c0-evidence`，不作为永久测试的依赖，不加入 Git；永久结论、节点、命令、失败原因均已归本记录。

### 非预期失败与最小装配处理

1. 首轮 restart 测试误把 `last_seen_at` 审计刷新纳入全对象相等；已改为先断言真实 parse/hash 数，再比较除审计时间外的完整 Song 内容。最终 RED 是 `(2,2)!=(0,0)`，没有使用时间戳差异证明扫描缺陷。
2. 失败 startup detector 观察曾在 retry Event 出现时过早采样，不能证明 detector 没有运行；给独立 detector Task 一个有界调度观察窗口后，最终 exact 与关系/full 都稳定看到 `['startup','detector']`。正常启动 inventory 用 FakeClock/可控 sleep，时间未推进。
3. 按原关系命令首次运行是 `23 failed,170 passed,51 errors`；errors 都是现有 `real_client` fixture 未找到，涉及 URI mapping、realtime Queue/History、Playlist 关系节点，**不计 RED**。现有 `invariants/conftest.py` 从 `support/playback.py` 注册该 fixture；单独 Queue 节点正常，带 C0 四文件也正常。针对混合完整关系集合显式加载原支持模块 `-p server.tests.support.playback` 后，所有 51 个装配错误消失，变成 `23 failed,221 passed,0 errors`。无仓库 conftest/旧测试修改，不声称已修复 pytest 的底层发现机制。
4. 完整 mock 回归另外两项旧测试失败，精确 mock 复跑均失败：
   - `server/tests/api/test_mpd_connection.py::test_saved_endpoint_overrides_invalid_old_environment_and_adapter_uses_it`：`created=[]`，期待 adapter 被构造；测试本身没有设置 MPD_MODE。
   - `server/tests/invariants/test_realtime_observer_lifecycle.py::test_composition_root_starts_one_sampler_without_clients_and_awaits_shutdown`：等待 injected adapter 的 outputs sample 1 秒超时；测试本身没有设置 MPD_MODE。
   两项都显式把 `main.MPDAdapter` 替换为 MockMPD，但 C0 plan 的 `MPD_MODE=mock` 会走另一条 MockMPD 构造分支。仅这两个 exact 节点在新临时根、`APP_ENV=development MPD_MODE=real` 下补充验证：**2 passed,0.12s**；adapter 仍由测试替换，绝未连接真实 MPD。此结果证明环境分支假设冲突，不抵扣 mock 完整运行的两项失败。统一 mock full 命令与这两项旧测试的假设尚未统一，按本轮范围不修改无关测试/生产配置。
5. Starlette/httpx deprecation warning 保留；无依赖缺失、安装失败、媒体 fixture collection 错误或真实基础设施依赖。

### Diff 审查与 C0 / 下一 Batch 门槛（首轮状态，已由下方补充记录更新）

- 已审实际五个新增测试 diff（未跟踪文件用 `git diff --no-index /dev/null <file>`，而非只看 tracked stat）；`git diff --check` 及五个新文件的 whitespace check 均无问题。现有三份 tracked 文档 diff 保持起始状态；仅在原未跟踪证据文档追加/更新本轮事实。
- 无生产代码、未来 Batch、临时调试代码、数据库、环境或依赖变更进入 diff。测试 fault injection/计数/barrier 属于永久证明本体。build/cache 产物仍忽略；没有 commit/push。
- **C0 十项行为 RED 建立门槛已满足**，同时保留两个新文件内既有 GREEN 保护；所要求的 baseline、关系、完整回归、typecheck/build/Ruff 均 fresh 执行。此结论不代表 corrective 实现/自动验收通过，也不扩展当前只授权 C0 的范围。
- **下一 Batch 的严格准入条件当前不满足**：统一 mock 完整回归仍有两项旧环境假设冲突未解决（上列独立 adapter 分支已 GREEN）。需先统一完整命令与这两项测试的独立装配假设；不能把 full 写成 PASSED，也不能把它们计作本 corrective 的预期 RED。本轮 C0 的测试/证据步骤均已执行，但不关闭这一回归门槛。
- 23 backend + 3 Web corrective 行为缺陷尚未修改；v5/prepare/commit/seed/超时公开读取恢复的 GREEN 要留给 C1–C4。测试中标明的 seam 迁移是后续工作，C0 不引入缺失接口。
- 真实设备、手机、容器新 SHA/CI Gate **NOT RUN**；本轮在 C0 停止。


## 两项旧测试环境装配修正 — 2026-10-12（C0 后补充）

用户追问这两项是否影响 C2、是否可以现在安全解决。本轮只处理已证实的测试环境假设；不执行 C1/C2，也不修改生产代码或旧业务断言。C0 首轮结果保持为历史事实，当前状态以下列 fresh 复核为准。

### 对 C2 的影响与最小修正

两项不依赖 C2 新的 ScanBaseline/prepare/commit 接口；不会改变线程准备、短事务提交或路径差异合同。但旧测试隐式依赖外层 MPD_MODE，使完整 mock 回归出现额外失败，会妨碍 C2 判断真正的回归。应在生产改造前消除这项测试装配歧义。

- `server/tests/api/test_mpd_connection.py::test_saved_endpoint_overrides_invalid_old_environment_and_adapter_uses_it`
- `server/tests/invariants/test_realtime_observer_lifecycle.py::test_composition_root_starts_one_sampler_without_clients_and_awaits_shutdown`

两项各自用 monkeypatch 显式设 `APP_ENV=development`、`MPD_MODE=real`，选择其本来要验证的 adapter 构造分支；`CONFIG_DIR` 和 `MUSIC_ROOT` 同时隔离到自己的 tmp_path。原有 `main.MPDAdapter` 替换为 MockMPD 的逻辑保持，确保选择 adapter 分支也不会连接真实 MPD。fixture 退出后环境由 monkeypatch 恢复。没有延长 sampler 的 1 秒等待、弱化 adapter 参数/endpoint、状态/revision、sampler 单 owner 或 shutdown 断言。

### Fresh 验证（外层仍统一 mock）

每条命令均从 repo root 执行、用现有 `.venv`；外层 `APP_ENV=development MPD_MODE=mock`，全新自有临时 DATABASE_PATH/CONFIG_DIR/MUSIC_ROOT。无需临时把两个节点的进程整体改为 real mode。

| 顺序 | 命令 / 节点 | Fresh 结果 |
|---|---|---|
| 修改前 exact 1 | `.venv/bin/python -m pytest -q --tb=short server/tests/api/test_mpd_connection.py::test_saved_endpoint_overrides_invalid_old_environment_and_adapter_uses_it` | 1 failed，1.01s；created=[] |
| 修改前 exact 2 | `.venv/bin/python -m pytest -q --tb=short server/tests/invariants/test_realtime_observer_lifecycle.py::test_composition_root_starts_one_sampler_without_clients_and_awaits_shutdown` | 1 failed，1.20s；sampled.wait 超时 |
| 修改后 exact 1 | 同一命令、同一外层 mock 装配 | 1 passed，0.64s |
| 修改后 exact 2 | 同一命令、同一外层 mock 装配 | 1 passed，0.07s |
| 两个直接文件 | `.venv/bin/python -m pytest -q --tb=short server/tests/api/test_mpd_connection.py server/tests/invariants/test_realtime_observer_lifecycle.py` | 20 passed，1.26s |
| 关系集 | 原 Batch plan 完整 backend 关系集，保留 `-p server.tests.support.playback`，再加入上述两个直接文件 | 23 failed,241 passed，19.61s；仅登记的 C0 RED，0 errors |

完整后端本轮 fresh 命令 `.venv/bin/python -m pytest -q --tb=short server/tests`：**23 failed,1564 passed,1 warning，123.96s**。核对全部失败节点集合，恰好等于已登记的 23 个 C0 backend RED；无额外失败、无 fixture/collection errors。完整套件仍是 FAILED，不能称 corrective GREEN。

全 backend Ruff `.venv/bin/python -m ruff check server/app server/tests` 与 `git diff --check` 通过。实际测试 diff 仅 11 行新增（模式/临时路径及原因注释），所有旧断言保留；证据记录追加本轮 fresh 事实。HEAD 仍为 `098d6eaea81495d1686a09f9e0ee68768610ed7e`，未改生产代码、依赖或 C0 永久测试，未 commit/push。Web 本轮未重跑：没有 Web 代码/测试修改，上一轮 C0 的 3 个 Web RED 和 Web baseline/关系/full/typecheck/build 结果保持历史记录，未伪称本轮 fresh。

**当前门槛结论：两项额外失败已安全消除，C0 首轮记录的环境假设阻塞解除。** C0 新缺陷证明、既有基线保护与“完整回归只余登记 corrective RED”的证据条件已具备，可以在后续授权范围内进入 C1；C2 仍按计划消费 C1 的 baseline/observed/sidecar。C1/C2 本轮 NOT STARTED，corrective 自动验收仍待 C1–C4 GREEN，真实设备/容器 Gate 仍 NOT RUN。


## C1 fresh 执行记录 — 2026-10-12（Asia/Shanghai）

本轮用户明确授权仅 C1；spec/plan 中历史 DRAFT/C0 NOT STARTED 标签不作为事实门槛或替代本轮授权。按实际源码、Git、fresh 行为验证执行，C2–C5 不推进。

### 起点和 C0 门槛复核

- 分支 `fix/task-9-startup-library-reconciliation`，HEAD `098d6eaea81495d1686a09f9e0ee68768610ed7e`，本轮结束 HEAD 不变。起始 dirty 包括三份 tracked 文档、两项 adapter 装配测试修正、三份未跟踪 corrective 文档及五个 C0 测试资产；全部保留。
- 阅读本 corrective design、Batch plan、本证据记录，核对五个永久测试源与两项旧测试实际 diff。不是基于 checklist/此前 handoff 判断 C0 完成。
- **生产修改之前**，25 个 C0 backend 节点均用独立 pytest 进程 fresh exact 复跑：23 行为 RED、2 个已有 GREEN（constructor open、during_prepare mount）；三个 Web 节点逐个 `-t` fresh 均行为 RED。失败断言与本记录 C0 十项表完全一致，无缺接口导入或 collection error。
- 确认预算节点 fresh `1 passed`；两个旧 adapter 节点在统一外层 mock 各 fresh `1 passed`，仍由测试内部 MockMPD 注入，未连接真实设施。74 项 backend baseline fresh GREEN；Web 三文件/28 项 baseline fresh GREEN。
- 生产修改之前完整 mock 后端 fresh：**23 failed,1564 passed,1 warning,125.99s**。逐项比较失败节点集合，恰好等于登记的 23 C0 RED；无额外回归/装配错误。两项旧 adapter 测试已在 full 中通过，不能再作为预期失败。
- 因此本轮 C0 前置证据满足，才写 C1 生产代码。full 仍 FAILED，不标 PASSED。
- Linux ARM64；现有 `.venv` Python 3.14.4、pytest 9.1.1、Ruff 0.16.9；已读 server/requirements.txt，无依赖变更。每个 backend 验证进程均创建不同的自有临时根（config/music 先 mkdir），外层 `APP_ENV=development MPD_MODE=mock DATABASE_PATH=<新根>/state.db CONFIG_DIR=<新根>/config MUSIC_ROOT=<新根>/music`；测试另用 tmp_path fixture。Web 使用已有 node_modules。未使用 Docker、真实 MPD/NAS/DAC 或用户数据库/媒体。

### 实际变更与范围裁定

- `models/library.py`：增加 frozen `SidecarSignature`（非负整数或成对 NULL）与 ScanBatch observed URI / sidecar delta 正式字段；公开 Song DTO 不变。
- 新 `models/library_scan.py`：frozen ScanBaseline，内部 frozen Song/Artwork 副本，无 DB/service 引用。避免普通公开 Song 变为 frozen。songs/sidecars 为 tuple。
- `repositories/migrations.py`：schema v5、新库辅助表、v4→v5 原子建表迁移；不清空旧表、不改 Song 身份/URI/引用、不替未知签名制造 absence。数据库 CHECK 区分两个 NULL 与成对非负整数，外键 cascade。
- `library_repository.py`：单事务读取 detached baseline；fingerprint 覆盖 Song 内容/分类/签名、sidecar 及 artwork source owner，排除 last_scanned_at/last_seen_at；无媒体 I/O。observed union 只用于保留存在证据，不 upsert 未变化 Song。成功 sidecar 按 audio URI 解析为既有/新 Song ID，与 Song 同一事务提交。unreadable/read_error/无成功观察路径不记录新成功签名，旧成功事实保留。
- `test_library_scan_commit.py`：新增 15 个 C1 节点，保留 C0 mount 两节点及全部既有断言；observed proof 从 model_copy seam 迁到正式字段。
- `test_library_reconciliation.py`：仅按 v5 合同更新两项 schema 版本/名字、增加辅助表存在断言；旧 migration 数据/引用/identity 保护断言全部保留。
- 唯一文档变更为本 evidence 记录。没有 scanner/sync/runtime/config/Web/CI 生产修改，没有实现线程 prepare/commit、路径差异或条件 MPD update。
- Ruling：沿用用户指定的现有 fix checkout，保留 dirty，不创建/移动 worktree，不触发 commit/push；用户指定本轮 native C1 边界优先于 skill 通用工作区/分支收尾流程。未启动子 agent。
- Ruling：frozen 内部快照使用私有 Song/Artwork 子类；Pydantic 跨类型 equality 为 false，两个新测试首轮 GREEN 阶段因此失败。最小独立探针确认其 model_dump 全字段相等；改成比较**全部字段**（没有排除字段/放宽内容断言），保留 frozen 的所有拒绝赋值断言；exact 两节点重新通过。这属于测试对表示类型的错误假设，非生产回归或预期 RED。

### C1 逐节点真实 RED → GREEN

每行在任何 C1 生产修改前 exact RED；最终源码再次独立 exact GREEN。永久源的 RED 阶段用现有 ScanBatch.model_copy 携带 delta，SidecarSignature 尚无时用 test-only SimpleNamespace，sidecar SQL helper 在缺表时返回空事实；实际失败是未持久化/误 missing/未验证非法签名，**不是导入错误**。GREEN 源已改成正式模型构造，测试不依赖临时文件。

文件均为 `server/tests/repositories/test_library_scan_commit.py`，每条命令 `.venv/bin/python -m pytest -q '<file>::<node>'`：

| exact 节点 | 修改前行为 RED | 最终 fresh 结果 |
|---|---|---|
| `test_observed_unchanged_uri_is_not_missing` | 两个 observed Song 被置 MISSING | 1 passed in 1.07s |
| `test_v4_migration_preserves_library_and_references` | 旧数据/refs 检查已通过，但迁移未建 sidecar 表 | 1 passed in 0.47s |
| `test_sidecar_absence_is_distinct_from_unknown` | 真实 repository 提交后签名行 []，不等于预期持久成功/absence 行 | 1 passed in 0.52s |
| `test_signature_delta_rolls_back_with_song_batch[commit]` | 真实 repository 提交后签名行 []，不等于预期持久成功/absence 行 | 1 passed in 0.46s |
| `test_signature_delta_rolls_back_with_song_batch[rollback]` | 真实 repository 提交后签名行 []，不等于预期持久成功/absence 行 | 1 passed in 0.46s |
| `test_signature_delta_rolls_back_with_song_batch[cancel]` | 真实 repository 提交后签名行 []，不等于预期持久成功/absence 行 | 1 passed in 0.46s |
| `test_failed_sidecar_delta_is_never_recorded_as_success[read_error]` | 真实 repository 提交后签名行 []，不等于预期持久成功/absence 行 | 1 passed in 0.44s |
| `test_failed_sidecar_delta_is_never_recorded_as_success[unreadable]` | 真实 repository 提交后签名行 []，不等于预期持久成功/absence 行 | 1 passed in 0.47s |
| `test_failed_sidecar_delta_is_never_recorded_as_success[new_unreadable]` | 真实 repository 提交后签名行 []，不等于预期持久成功/absence 行 | 1 passed in 0.45s |
| `test_scan_baseline_tracks_content_and_signatures_but_not_audit_time` | 真实 repository 提交后签名行 []，不等于预期持久成功/absence 行 | 1 passed in 0.46s |
| `test_sidecar_signature_rejects_partial_or_negative_stats[None-1]` | DID NOT RAISE ValidationError；非法 stats 被接受 | 1 passed in 0.43s |
| `test_sidecar_signature_rejects_partial_or_negative_stats[1-None]` | DID NOT RAISE ValidationError；非法 stats 被接受 | 1 passed in 0.43s |
| `test_sidecar_signature_rejects_partial_or_negative_stats[-1-0]` | DID NOT RAISE ValidationError；非法 stats 被接受 | 1 passed in 0.42s |
| `test_sidecar_signature_rejects_partial_or_negative_stats[0--1]` | DID NOT RAISE ValidationError；非法 stats 被接受 | 1 passed in 0.45s |
| `test_sidecar_table_enforces_signature_pairs_and_song_reference` | 真实 repository 提交后签名行 []，不等于预期持久成功/absence 行 | 1 passed in 0.44s |
| `test_sidecar_delta_follows_song_identity_on_move` | 真实 repository 提交后签名行 []，不等于预期持久成功/absence 行 | 1 passed in 0.45s |

GREEN 后续断言实际执行：v4 每张旧表全行与引用/队列/播放/idempotency 保留、foreign_key_check/integrity_check/重开幂等；absence 与 unknown 不同，present→absence，观察但未解析不改业务/审计字段且 revision=0；outer commit/rollback/CancelledError 中新旧 Song 与 sidecar 共同可见/回滚、独立连接不见未提交、revision 同步；read_error/known unreadable/new unreadable 不缓存失败；移动保 Song ID 和 Playlist 引用、签名切换到新 LRC URI；baseline frozen/deep snapshot、audit 不影响 fingerprint、业务/sidecar 内容影响 fingerprint；数据库拒绝半签名/负值/非整数/孤儿引用并验证 FK cascade。

### Fresh 顺序验证结果

顺序为 exact → 直接文件 → repository / 指定关系集 → 完整两端 → typecheck/build/Ruff。关系集需要 real_client 时显式加载原 `-p server.tests.support.playback`，没有改 fixture 发现规则。

| 集合 | fresh 结果 | 判定 |
|---|---|---|
| 两个直接 repository 文件 | 1 failed, 30 passed in 0.80s | FAILED，仅下方登记 RED；不标 PASSED |
| 整个现有 repository 目录 | 1 failed, 68 passed in 1.18s | FAILED，仅下方登记 RED；不标 PASSED |
| realtime_library / realtime_commit_visibility / transaction_relationships | 36 passed in 1.86s | GREEN |
| Batch plan 完整 backend 关系集 + 两个旧 adapter 文件 | 22 failed, 257 passed in 20.02s | FAILED，仅下方登记 RED；不标 PASSED |
| Batch plan Web 关系集 | Test Files 1 failed / 8 passed (9); Tests 3 failed / 75 passed (78); Duration  16.18s (transform 3.12s, setup 178ms, collect 5.59s, tests 1.74s, environment 4.65s, prepare 964ms) | FAILED，仅下方登记 RED；不标 PASSED |
| 完整 backend server/tests | 22 failed, 1580 passed, 1 warning in 125.66s (0:02:05) | FAILED，仅下方登记 RED；不标 PASSED |
| 完整 Web | Test Files 1 failed / 29 passed (30); Tests 3 failed / 299 passed (302); Duration  54.33s (transform 4.40s, setup 410ms, collect 13.04s, tests 13.07s, environment 14.50s, prepare 3.07s) | FAILED，仅下方登记 RED；不标 PASSED |
| Web typecheck | exit 0; > vue-tsc --noEmit | GREEN |
| Web build | exit 0; ✓ built in 2.66s | GREEN |
| C1 targeted Ruff | exit 0; All checks passed! | GREEN |
| server/app server/tests Ruff | exit 0; All checks passed! | GREEN |

可复现的 fresh 命令（每条 backend 前分别建立上述新临时根，均从 repo root）：

```bash
.venv/bin/python -m pytest -q server/tests/repositories/test_library_scan_commit.py server/tests/repositories/test_library_reconciliation.py
.venv/bin/python -m pytest -q server/tests/repositories
.venv/bin/python -m pytest -q -p server.tests.support.playback server/tests/invariants/test_realtime_library.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_transaction_relationships.py
.venv/bin/python -m pytest -q server/tests/invariants/test_startup_library_reconciliation.py server/tests/api/test_startup_readiness.py server/tests/services/test_library_scan_prepare.py server/tests/repositories/test_library_scan_commit.py server/tests/services/test_library_scanner.py server/tests/services/test_library_change_detector.py server/tests/services/test_library_sync_service.py server/tests/repositories/test_library_reconciliation.py server/tests/invariants/test_library_sync.py server/tests/invariants/test_library_sync_wire.py server/tests/api/test_library_sync_wire.py server/tests/invariants/test_transaction_relationships.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_realtime_library.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_handoff.py server/tests/player/test_music_uri.py server/tests/test_config.py server/tests/invariants/test_config_composition.py server/tests/invariants/test_uri_mapping.py server/tests/invariants/test_health_relationships.py server/tests/invariants/test_realtime_queue.py server/tests/invariants/test_realtime_history.py server/tests/invariants/test_playlist_relationships.py -p server.tests.support.playback server/tests/api/test_mpd_connection.py server/tests/invariants/test_realtime_observer_lifecycle.py
npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts tests/invariants/realtime.test.ts tests/invariants/resource-cache.test.ts tests/invariants/wire.test.ts tests/invariants/mutation.test.ts tests/invariants/global-notices.test.ts tests/invariants/library-sync.test.ts tests/invariants/shell-navigation.test.ts tests/invariants/task9-relationships.test.ts --maxWorkers=1 --minWorkers=1
.venv/bin/python -m pytest -q server/tests
npm --prefix web run test -- --run --maxWorkers=1 --minWorkers=1
npm --prefix web run typecheck
npm --prefix web run build
.venv/bin/python -m ruff check server/app/models/library.py server/app/models/library_scan.py server/app/repositories/migrations.py server/app/repositories/library_repository.py server/tests/repositories/test_library_scan_commit.py server/tests/repositories/test_library_reconciliation.py
.venv/bin/python -m ruff check server/app server/tests
```

完整 backend 与完整 backend 关系集均逐项核对失败集合：以下 **22 个 C2/C3 backend 登记 RED**，比 C0 少的唯一节点是 C1 observed proof；无新增失败，无 collection/fixture/environment errors：

- `server/tests/api/test_startup_readiness.py::test_http_ws_and_library_read_during_startup_prepare`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[iterdir]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[resolve]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[stat]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[known]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[new]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_failed_startup_has_no_competing_detector_walk`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_inconsistent_startup_updates_once_then_confirms`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_persisted_second_start_skips_parse_and_hash`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[add]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[delete]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_add]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_delete]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_modify]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[modify]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[move]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_startup_inventory_seed_does_not_immediately_walk`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_unchanged_consistent_startup_does_not_update`
- `server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[before_scanner_commit]`
- `server/tests/services/test_library_scan_prepare.py::test_prepare_releases_database_lock`
- `server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[hash]`
- `server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[parse]`

Web 关系/full 均仅保留 C4 三节点：`initial_snapshot_timeout_reports_and_reconnects`、`get_timeout_ends_loading_and_retries`、`body_timeout_and_late_response_cannot_restore_baseline`。无 Web 新回归。两项旧 adapter 装配测试在统一 mock full 中 GREEN，不列作预期 RED。既有 Starlette/httpx deprecation warning 保留，无依赖缺失。

### 非预期验证失败处理

初轮 targeted/full Ruff 发现 8 个 I001 import 布局问题，仅涉及本轮 library_repository.py import 和 C1 新测试的局部 import。已读完整诊断，对这两个 C1 文件限定 `ruff check --fix`；实际修复只展开 import 和插入分组空行，无业务改动。检查修复 diff 后对最终源码重新执行全部 C1 exact → 直接文件 → repository → 指定 narrow/完整关系集 → 完整 backend → targeted/full Ruff。没有把 lint 失败计入预期 corrective RED。

### 实际 diff 审阅与 C2 准入

- 用 verification-before-completion 技能核对输出；按 code-reviewer 检查点对实际 C1 tracked diff 与未跟踪 library_scan/test 文件源码做单独一轮自审。依用户批准计划仅 native 执行，未委派独立 reviewer；自审不冒充外部 review。没有发现 C1 范围内未解决回归。
- `git diff --check` 通过；另对新增/未跟踪文件执行 no-index whitespace 检查；已看实际 diff/stat/status（stat 不包含未跟踪文件，另核对新模型及 C1 永久测试）。起始 README/长期 specs/两个 adapter 测试及 C0 非 C1 文件原变更保留；无依赖、用户 DB、环境、生成产物或调试代码进入工作 diff。
- **C1 实现及其精确 acceptance 满足，可作为后续 C2 的 baseline/observed/sidecar 输入；C1→C2 的本地准入条件满足。** 指定既有关系集 GREEN，完整回归只有允许保留的登记 RED。
- **corrective 总体验收尚未通过：完整 backend/Web 明确 FAILED。** 当前尚未解决的线程/锁/差异/根稳定、生命周期/inventory/条件 MPD、Web deadline 等仍分别属于 C2/C3/C4。它们没有被跳过、xfail、删除、削弱或修复。
- C2/C3/C4/C5 本轮 NOT STARTED；真实设备/手机/容器新 SHA/CI Gate NOT RUN。无 commit/push/PR/merge，HEAD 不变。本轮在 C1 停止。


## C2 fresh 执行记录 — 2026-10-12（Asia/Shanghai）

本轮用户授权只完成 C2，不推进 C3，不 commit/push。沿用当前 dirty checkout，分支 `fix/task-9-startup-library-reconciliation`、HEAD `098d6eaea81495d1686a09f9e0ee68768610ed7e`。开始时已重新核对 Git、三份 corrective 文档、C1 实际 diff/模型/迁移/Repository 和上方 C1 exact/关系/full 记录。此前停止时确实只有 v4；本轮实际源码已经变为 v5，不用上轮结论覆盖新 checkout。

### C1 准入复核及环境

- 实际 v5 migration/sidecar 表、paired-null absence 与 unknown、不可变 ScanBaseline/read_scan_baseline、observed union 和同事务成功签名提交均在源码中存在。C1 的 15 个新增 exact GREEN、关系集及完整回归的永久记录已逐项核对，不仅查看 checkbox。
- 本轮先 fresh 跑两个 C1 repository 文件，排除尚属 C2 的两个 mount 节点：`29 passed, 2 deselected in 0.76s`。迁移/引用保护、baseline、observed、signature rollback 等实际行为通过，才开始 C2。
- 现有 `.venv`（Python 3.14.4 / pytest 9.1.1 / Ruff 0.16.9）和 Node 依赖；核对既有 requirements/package scripts，没有改依赖或虚拟环境。每个 backend 进程新建自有临时 config/music/SQLite，外层 `APP_ENV=development MPD_MODE=mock`，从 repo root 执行；测试内继续用各自 tmp_path。两个 adapter 测试仍由原测试注入 MockMPD，没有真实 MPD/NAS/DAC 或 Docker。

### 实际实现及边界

- 新 `models/library_scan.py` 的 FileSignature/LibraryInventory/PreparedScan frozen 边界；ScanBaseline 增加 detached artwork_sources，Repository 返回原本已经纳入 fingerprint 的同一 SQL 所有权事实。没有更改 schema、公开 Song DTO 或 C1 签名语义。
- 新 `services/library_scan_prepare.py`：线程内一次 audio/LRC inventory、音频/sidecar 差异、旧签名补齐、真实 parser/hash、唯一移动匹配、相关 album artwork fallback，以及路径失败集合。LRC-only 用已有音频 hash；UNREADABLE 恢复重新 hash。正常成果保留，坏新文件不伪造 Song，坏已知文件保留有效 metadata/lyrics/artwork/引用。
- `LibraryScanner.prepare/precheck/commit`：baseline 短事务后退出锁再线程准备；prepare 返回和 commit 前线程校验 root identity/文件稳定，不再 walk。已重现的 absence 重新出现拒绝提交；单路径变化或 stat/metadata/read_error 不丢其它成果。线程不访问 Repository/SQLite，commit 只 SQL/内存登记；stale baseline 抛 LibraryScanConflict。wrapper 冲突只重做相关 DB/sidecar/artwork 依赖路径，保留其它已准备媒体。
- active outer transaction 明确拒绝 scan_full/scan_paths/prepare/precheck；只消费提前线程检查的 PreparedScan。同一 outer 多 batch 验证一次原始 baseline，不把本事务自己的第一次写当外部冲突；commit/rollback 均释放验证登记。stage_sync 必须同步，不 await I/O；Song/signature/revision/SYNCING/通知义务联合提交，实际 update/WS/completion 在释放事务后执行。
- Sync 仅改 `_scan` 准备/提交边界：锁外 prepare，短 commit 内同步 stage targets/SYNCING；targets/state 只在 commit visibility 注册。manual/scheduled deep 每 activity 只一次，已成功提交路径在同 activity 的失败重试中复用签名；不改现有 run/确认/update 状态机、generation 合并或退避预算。
- 受影响的 realtime_library/snapshot/playlist outer 调用改为锁外准备各媒体版本、事务内 commit；保留 rollback/cancel、联合两域提交、同 outer 两 batch、恢复 no-op、commit→update→completion 和 post-commit 发送失败保护。未变化完成事件的 updated IDs 现在为空，但原 revision/no-op/发送失败断言保留。
- C0 parse/hash/path spy 和 barrier 已迁到真实 prepare module / Scanner.prepare/commit。所有 PermissionError 媒体注入先改变自有音频 mtime，确保确实准备；UNREADABLE/revision/refs 断言保持。旧 fake Repository 增加 detached baseline 接口，线程没有调用 fake Repository。
- 仅混合 good/bad 的旧整批 MediaMetadataError 断言需要改成 good 成果提交 + bad URI 失败；未知 title 原错误匹配和“不伪造 Song”、known-good metadata/lyrics 的旧断言继续保留。兼容 wrapper 在没有可用新媒体时仍可以报告 MediaMetadataError，但 observed 成功签名先提交；prepare/commit 按路径保留成果。

Ruling：用户批准的分 Batch/native/保留 dirty 范围优先于通用 skill 的新 worktree、委派 reviewer 和 commit 收尾；只做单独一轮作者自审，不冒充独立 review。旧 incomplete traversal 证明改为更严格的根级拒绝/no-write，仍验证不能 mass missing。两者不扩张 C3，也不删除/skip/xfail 或放宽业务断言。

### 真正 RED、已有 GREEN 与装配/回归的区分

以下六个节点在任何 C2 生产修改之前均独立进程执行，真实失败，不依赖缺失接口导入：

| 节点（P = server/tests/services/test_library_scan_prepare.py） | 修改前真实 RED |
|---|---|
| test_old_missing_signatures_are_backfilled_once | sidecars 为 0，期待 2；成功旧签名未持久化 |
| test_deep_reconciliation_detects_same_stat_content_change | startup parse/hash 各 2，期待 0；后续 deep 真实 metadata/hash 断言保留 |
| test_media_changed_during_prepare_is_retried | 读期间变化的 a.flac 被接受并提交旧 title，而不是路径失败 |
| test_stale_baseline_cannot_overwrite_new_commit | 陈旧 batch 覆盖 Concurrent Writer，没有拒绝 |
| test_prepare_cancellation_never_commits | 同步 parser 阻塞 loop，任务已提交；cancel 未抛 CancelledError |
| test_commit_data_revision_and_sync_are_atomic | rollback 已有保护通过；成功提交 sidecar 行数 0，期待 2；媒体事务隔离后续断言保留 |

RED 阶段 prepare/commit 用旧 _scan_files/_apply_batch 的 test-only fallback，以现有生产行为失败；最终源全部使用正式接口，没有保留缺接口导入式 RED。

单独审查还发现四个 C2 范围缺陷，先 exact RED 再最小修复：full artwork fallback 先 observed 的关联 Song 未重读导致 ref 丢失；单文件 stat PermissionError 中断整个 prepare；manual deep 三次失败/恢复令 good parse/hash 为 3 而非 1；新坏文件令 observed 成功 absence 签名未提交。四节点最终 exact GREEN；没有用取消、预算增加或弱断言处理。

线程/Repository 隔离、commit 前文件变化保留其它成果、冲突只重做相关路径三个补充节点建立时已 GREEN，单列为保护，不虚称 RED。C0 during_prepare mount 原 GREEN 继续 GREEN；C0 项 3、6、7 的 before_commit、8 原有行为 RED 的历史 exact 证据在 C0/C1 记录中可核对，最终均通过实际 prepare/commit。

非预期问题分别处理：

- 首轮旧 spy/import/fake baseline 缺接口均是边界迁移的测试装配错误，不计行为 RED；迁到实际 worker 并补 test double 的值接口后消除。失败 startup fault injection 一度沿用 read_signatures 参数，可能抛 TypeError；已改成调用真实 prepare 后抛指定 PermissionError，final exact 仍因 detector 竞争 walk 而 RED，不用装配失败冒充 C3。
- requested 非媒体缺失根一度被误接受，worker 内恢复原根级拒绝；known UNREADABLE 恢复 hash 为 0 的回归按原 hash=1 断言修复，不弱化计数。
- relationship/full 分别发现 snapshot、playlist 尚有 outer scan_full，按同一批准边界迁移，旧联合提交/一致切面断言保留；exact 和直接文件 GREEN。
- Ruff import/undefined os/C413 均为 lint/装配失败，限定本轮文件修复，不计预期 RED。没有依赖/环境失败。

### 最终源码 exact 账本

每行单独 backend 进程：`.venv/bin/python -m pytest -q --tb=short '<完整节点>'`，新建临时 DATABASE_PATH/CONFIG_DIR/MUSIC_ROOT；无导入/collection error。下表是最后修复后的 fresh 输出。

| 完整节点 | Fresh 结果 |
|---|---|
| `server/tests/services/test_library_scan_prepare.py::test_old_missing_signatures_are_backfilled_once` | 1 passed in 0.51s |
| `server/tests/services/test_library_scan_prepare.py::test_deep_reconciliation_detects_same_stat_content_change` | 1 passed in 0.60s |
| `server/tests/services/test_library_scan_prepare.py::test_media_changed_during_prepare_is_retried` | 1 passed in 0.60s |
| `server/tests/services/test_library_scan_prepare.py::test_stale_baseline_cannot_overwrite_new_commit` | 1 passed in 0.51s |
| `server/tests/services/test_library_scan_prepare.py::test_prepare_cancellation_never_commits` | 1 passed in 1.65s |
| `server/tests/services/test_library_scan_prepare.py::test_commit_data_revision_and_sync_are_atomic` | 1 passed in 0.50s |
| `server/tests/services/test_library_scan_prepare.py::test_prepare_releases_database_lock` | 1 passed in 0.46s |
| `server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[parse]` | 1 passed in 1.66s |
| `server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[hash]` | 1 passed in 1.67s |
| `server/tests/services/test_library_scan_prepare.py::test_commit_has_no_music_io_and_workers_have_no_repository_access` | 1 passed in 0.48s |
| `server/tests/services/test_library_scan_prepare.py::test_file_changed_before_commit_retains_other_prepared_results` | 1 passed in 0.53s |
| `server/tests/services/test_library_scan_prepare.py::test_conflict_reprepare_reuses_unrelated_successful_media` | 1 passed in 0.52s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[add]` | 1 passed, 1 warning in 0.10s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[modify]` | 1 passed, 1 warning in 0.11s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[delete]` | 1 passed, 1 warning in 0.09s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[move]` | 1 passed, 1 warning in 0.09s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_add]` | 1 passed, 1 warning in 0.09s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_modify]` | 1 passed, 1 warning in 0.10s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_delete]` | 1 passed, 1 warning in 0.10s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[new]` | 1 passed, 1 warning in 0.09s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[known]` | 1 passed, 1 warning in 0.12s |
| `server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[during_prepare]` | 1 passed in 0.50s |
| `server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[before_scanner_commit]` | 1 passed in 0.49s |
| `server/tests/services/test_library_scan_prepare.py::test_full_prepare_artwork_fallback_revisits_only_related_observed_song` | 1 passed in 0.55s |
| `server/tests/services/test_library_scan_prepare.py::test_single_file_stat_failure_keeps_other_prepared_media` | 1 passed in 0.48s |
| `server/tests/services/test_library_scan_prepare.py::test_manual_deep_retry_does_not_repeat_good_media` | 1 passed in 0.54s |
| `server/tests/services/test_library_scan_prepare.py::test_observed_signature_backfill_survives_new_metadata_failure` | 1 passed in 0.49s |

额外 exact：persisted second start `1 passed, 0.16s`（parse=0/hash=0）；真实 lifespan/HTTP/WS readiness `1 passed, 0.63s`（原 1 秒窗口不变）；outer rollback/order + 四种 rollback/cancel/restore/batch `5 passed, 0.30s`。joint playlist exact `1 passed, 0.11s`；snapshot exact `1 passed, 0.24s`。未知 title 的原错误匹配 exact `1 passed, 0.55s`，scanner 文件最终 `32 passed, 1.56s`。

### Fresh 精确 → 文件 → 关系 → 完整

| 集合 | 最终 fresh 结果 | 判定 |
|---|---|---|
| C2/C0 准备、安全及补充 exact | 27 个独立节点全部 GREEN | GREEN |
| 全部直接受影响文件（含 C0 I/A 和 realtime/history/recovery/snapshot/playlist） | 7 failed,148 passed,13.41s | FAILED；仅登记 C3 RED |
| Batch plan backend 完整关系集，`-p server.tests.support.playback`，加两个旧 adapter 文件及 realtime_playlist | 7 failed,296 passed,21.73s | FAILED；仅登记 C3 RED；无 errors |
| 完整 backend `.venv/bin/python -m pytest -q --tb=short server/tests` | 7 failed,1608 passed,1 warning,129.10s | **FULL FAILED**；仅登记 C3 RED |
| Web 关系集，原计划 9 文件/单 worker | 3 failed,75 passed；1 failed/8 passed files；17.41s | FAILED；仅 C4 三 RED |
| 完整 Web 单 worker | 3 failed,299 passed；1 failed/29 passed files；56.97s | **FULL FAILED**；仅 C4 三 RED |
| Web typecheck / build | 独立核对 exit 0；vue-tsc / Vite build 成功 | GREEN |
| targeted 与 server/app server/tests Ruff | All checks passed，exit 0 | GREEN |

完整 backend 首次 fresh 为 `8 failed,1605 passed,122.96s`，其中 realtime_playlist 是尚未迁移的受影响调用，不能计预期 RED。修复该调用并补齐收尾问题后，再次从 exact→直接文件→关系→完整运行，最终结果以上表为准，不拿首轮结果抵扣。

直接文件/关系/full 三者均用完整 FAILED 节点集合比较，恰好等于以下七个 C3 RED：

- `server/tests/invariants/test_startup_library_reconciliation.py::test_unchanged_consistent_startup_does_not_update`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_inconsistent_startup_updates_once_then_confirms`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[resolve]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[stat]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[iterdir]`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_startup_inventory_seed_does_not_immediately_walk`
- `server/tests/invariants/test_startup_library_reconciliation.py::test_failed_startup_has_no_competing_detector_walk`

Web 仍原三个 C4 普通失败节点：initial_snapshot_timeout_reports_and_reconnects、get_timeout_ends_loading_and_retries、body_timeout_and_late_response_cannot_restore_baseline。无 skip/xfail。两个 adapter 节点在统一 mock full 中已通过，不再列预期失败。Starlette/httpx warning 保留。

所有命令从 repo root 执行。backend 关系集合为上方 C1/Batch plan 原完整命令追加 `-p server.tests.support.playback server/tests/api/test_mpd_connection.py server/tests/invariants/test_realtime_observer_lifecycle.py server/tests/invariants/test_realtime_playlist.py`；Web/全套/typecheck/build/Ruff 命令与计划一致。临时逐节点日志、完整 tracebacks 及 runner 命令在 `/tmp/mpd-c2-evidence`，不作为永久测试依赖，不加入 Git。本节记录足以复现结论。

### Diff / 自审 / C3 准入

- 按 verification-before-completion 与 code-reviewer 检查点单独审 actual tracked diff、未跟踪 models/library_scan.py/prepare module/C0 测试，检查正常/失败/冲突/取消、artwork/LRC/移动身份及外层事务安全；四项自审发现已 RED→GREEN。没有把作者自审冒充独立 reviewer。
- C1 起始模型/迁移/observed/sidecar和已存在 README/spec/adapter 等 dirty 变更保留；C2 只新增 prepare 数据边界、scan/commit、受影响测试与本证据。没有修改依赖、用户媒体/DB、CI、Web 生产实现、detector/runtime/config/mapper 或确认状态机。无临时数据库、环境文件、生成文件/调试代码进入 diff。
- 已审实际 diff（含 untracked 源码，stat 不替代源码检查）、git diff --check/stat/status；无 whitespace 问题。无 commit/push/PR/merge。
- **C2 实现、精确 acceptance 及关联 C0 项 3/6/7/8 的 prepare/安全证明满足；本地进入 C3 的条件满足。** 仍需 C3 完成无 I/O constructor、inventory seed/owner 和条件 MPD 确认；C4 完成读取预算。完整 backend/Web 仍 FAILED，corrective 自动验收没有 PASSED。
- 真实手机/MPD/NAS/DAC、Docker、新 SHA 容器/CI Gate NOT RUN。本轮停止在 C2，不实施 C3。


## C3 前置审计停止记录 — 2026-10-12（Asia/Shanghai）

用户本轮只授权 C3，明确要求 C2 不完整或证据不足时停止，不补做 C2、不开始 C3。本轮先核对实际 checkout、C1/C2 代码、上方记录及 `/tmp/mpd-c2-evidence` 原始 exact/direct/relationship/full 日志，再在未改任何生产或仓库测试源码前 fresh 复跑 C2。

- 分支 `fix/task-9-startup-library-reconciliation`；HEAD `098d6eaea81495d1686a09f9e0ee68768610ed7e`。起始 tracked/untracked dirty 全部保留。
- 现有 `.venv`：Python 3.14.4、pytest 9.1.1、Ruff 0.16.9；已读 server/requirements.txt，未修改依赖。所有 backend 子进程从 repository root 使用新 mktemp config/music/SQLite，`APP_ENV=development MPD_MODE=mock`，fixture 使用 tmp_path；未连接真实 MPD/NAS/DAC，未使用 Docker。
- 实际 Scanner 的短 baseline 事务→`asyncio.to_thread` prepare、线程 precheck、commit baseline fingerprint/SQL/revision/SYNCING 联合提交已经核对。原 C0 项 3/6/7/8 与 C2 exact 本轮通过，但新增 inventory entry stat 审计暴露路径失败隔离缺口。因此**上方 C2→C3 准入结论被本轮反证撤销，C2 尚不完整，C3 NOT STARTED，不能进入 C4**。

### 阻塞缺陷：inventory 分类吞掉单文件 stat 错误

实际 `server/app/services/library_scan_prepare.py::_walk`（行 69–78）先调用 `entry.is_dir(follow_symlinks=False)`、`entry.is_file(follow_symlinks=False)`。在本机既有 Python 3.14.4 中，这两个 pathlib 方法在内部捕获 OSError 并返回 False（已用 .venv 的 inspect.getsource 核对实际运行代码）；外层 `except OSError` 没有机会识别错误。于是列目录已发现的媒体在 stat PermissionError 时被静默遗漏，inventory 仍被标 complete。

- 新媒体：prepare 正常返回，却有 `failed_paths == ()`，没有错误路径义务；不能保证坏新路径后续 retry，也可能允许虚假的完成。
- 已知媒体：遗漏被视为 absence 候选；`validate_prepared` 行 390 再次 stat 抛 PermissionError，整批 prepare 失败，而非仅把该媒体登记 unreadable/failed 并保留其它正常路径成果。旧索引未被破坏，但路径隔离合同不成立。
- 现有 `test_single_file_stat_failure_keeps_other_prepared_media` 只替换 `_signature`，位于 entry 类型判断之后；它通过不能证明更早的真实 stat/lstat 失败边界安全。

这是 C2 的 inventory / 单路径 OSError 隔离实现缺陷，不是环境依赖失败、测试缺接口/导入失败，也不是已登记 C3/C4 RED。本轮不修复、不迁入 C2 永久测试文件；以下临时诊断完整源码作为可复现证据保存，不计作 C3 RED→GREEN。

临时诊断文件 `/tmp/mpd-c3-evidence/test_c2_inventory_stat_gate.py`，源码：

```python
"""Audit C2 traversal failures before permitting C3. No production changes."""
import asyncio
from pathlib import Path

import pytest

from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.services.library_scanner import LibraryScanner
from server.tests.invariants.test_startup_library_reconciliation import music_fixture


@pytest.mark.parametrize('known', [False, True], ids=['new', 'known'])
def test_inventory_entry_stat_failure_is_isolated(tmp_path, media_fixture_dir, monkeypatch, known):
    root = music_fixture(tmp_path, media_fixture_dir)
    failed = root / 'a.flac'
    original = Path.stat
    injected = []

    def denied(path, *args, **kwargs):
        # Persistent stat/lstat failure of a single entry must not silently
        # disappear or discard independent successful media preparation.
        if path == failed:
            injected.append(path)
            raise PermissionError('fixture entry lstat unavailable')
        return original(path, *args, **kwargs)

    async def run():
        db = str(tmp_path / 'audit.db')
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        if known:
            await scanner.scan_full(root)
        with monkeypatch.context() as patch:
            patch.setattr(Path, 'stat', denied)
            prepared = await scanner.prepare(root)
            assert injected, 'fault did not reach entry classification'
            assert prepared.failed_paths == (failed,), 'inventory silently omitted a stat-failed media path'
            await scanner.commit(prepared)
        good = await repo.find_song_by_file_uri(str(root / 'sidecar.mp3'))
        assert good is not None and good.availability_status == 'AVAILABLE'
        bad = await repo.find_song_by_file_uri(str(failed))
        if known:
            assert bad is not None and bad.availability_status == 'UNREADABLE'
        else:
            assert bad is None

    asyncio.run(run())
```

精确复现从 repo root，每次创建独立运行根（不要改为真实配置/DB）：

```bash
audit_root=$(mktemp -d /tmp/mpd-c2-stat-audit-XXXXXX)
mkdir -p "$audit_root/config" "$audit_root/music"
APP_ENV=development MPD_MODE=mock DATABASE_PATH="$audit_root/state.db" CONFIG_DIR="$audit_root/config" MUSIC_ROOT="$audit_root/music" .venv/bin/python -m pytest -q --tb=long -p server.tests.conftest '/tmp/mpd-c3-evidence/test_c2_inventory_stat_gate.py::test_inventory_entry_stat_failure_is_isolated[new]'
# known 节点另建新的 audit_root 后执行同一命令，节点参数替换为 [known]。
```

两个最终 exact 独立进程结果：

| 节点 | fresh 输出 | 分类 |
|---|---|---|
| `test_inventory_entry_stat_failure_is_isolated[new]` | 1 failed in 0.53s；期待 failed_paths=(a.flac,)，实际 () | 新发现 C2 行为缺陷 |
| `test_inventory_entry_stat_failure_is_isolated[known]` | 1 failed in 0.50s；validate_prepared 的 Path.stat 抛 PermissionError，中断整批 prepare | 新发现 C2 行为缺陷 |

已阅读两节点完整 long traceback，日志 `/tmp/mpd-c3-evidence/c2-stat-new.log`、`c2-stat-known.log`；没有 collection/import error。先前仅 lstat 故障的诊断同样两个失败（new 漏失败路径；known 被误报 absent media reappeared），最终上述持续 stat/lstat 故障更贴近实际文件级权限故障，不依赖预检前权限恢复。

### Fresh 前置验证结果（不冒充 C3 验收）

C2 上节 exact 27 个唯一节点逐个独立进程通过；runner 又重复末尾两个补充节点，共 29 次通过。命令每次为 `.venv/bin/python -m pytest -q --tb=short '<完整节点>'`，独立临时环境。节点结果如下：

| 完整节点 | 本轮 fresh 输出 |
|---|---|
| `server/tests/services/test_library_scan_prepare.py::test_old_missing_signatures_are_backfilled_once` | 1 passed in 0.47s |
| `server/tests/services/test_library_scan_prepare.py::test_deep_reconciliation_detects_same_stat_content_change` | 1 passed in 0.45s |
| `server/tests/services/test_library_scan_prepare.py::test_media_changed_during_prepare_is_retried` | 1 passed in 0.46s |
| `server/tests/services/test_library_scan_prepare.py::test_stale_baseline_cannot_overwrite_new_commit` | 1 passed in 0.44s |
| `server/tests/services/test_library_scan_prepare.py::test_prepare_cancellation_never_commits` | 1 passed in 1.62s |
| `server/tests/services/test_library_scan_prepare.py::test_commit_data_revision_and_sync_are_atomic` | 1 passed in 0.44s |
| `server/tests/services/test_library_scan_prepare.py::test_prepare_releases_database_lock` | 1 passed in 0.42s |
| `server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[parse]` | 1 passed in 1.60s |
| `server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[hash]` | 1 passed in 1.62s |
| `server/tests/services/test_library_scan_prepare.py::test_commit_has_no_music_io_and_workers_have_no_repository_access` | 1 passed in 0.42s |
| `server/tests/services/test_library_scan_prepare.py::test_file_changed_before_commit_retains_other_prepared_results` | 1 passed in 0.45s |
| `server/tests/services/test_library_scan_prepare.py::test_conflict_reprepare_reuses_unrelated_successful_media` | 1 passed in 0.46s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[add]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[modify]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[delete]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[move]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_add]` | 1 passed, 1 warning in 0.06s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_modify]` | 1 passed, 1 warning in 0.08s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_delete]` | 1 passed, 1 warning in 0.06s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[new]` | 1 passed, 1 warning in 0.09s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[known]` | 1 passed, 1 warning in 0.09s |
| `server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[during_prepare]` | 1 passed in 0.43s |
| `server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[before_scanner_commit]` | 1 passed in 0.45s |
| `server/tests/services/test_library_scan_prepare.py::test_full_prepare_artwork_fallback_revisits_only_related_observed_song` | 1 passed in 0.47s |
| `server/tests/services/test_library_scan_prepare.py::test_single_file_stat_failure_keeps_other_prepared_media` | 1 passed in 0.43s |
| `server/tests/services/test_library_scan_prepare.py::test_manual_deep_retry_does_not_repeat_good_media` | 1 passed in 0.46s |
| `server/tests/services/test_library_scan_prepare.py::test_observed_signature_backfill_survives_new_metadata_failure` | 1 passed in 0.43s |

复跑顺序为 exact→直接文件→指定关系集→完整 backend。直接文件沿用 C2 最终文件集；关系集为 Batch plan 的完整 backend 命令，显式追加 `-p server.tests.support.playback`，并加入两个已修正 adapter 装配文件及 realtime_playlist。完整 backend 使用 `.venv/bin/python -m pytest -q --tb=short server/tests`。

| 集合 | fresh 输出 | 判定 |
|---|---|---|
| 首轮前置 prepare/repository/C0 筛选 | 44 passed,8 deselected,1 warning in 5.04s | GREEN，筛选未代替后续 full |
| C2/C0 exact | 27 unique nodes / 29 invocations 全通过 | GREEN，但未覆盖上述 entry stat 缺口 |
| 直接受影响 C2 文件集（同 C2 final） | 7 failed,148 passed in 11.10s | FAILED，仅已有 7 个 C3 登记 RED |
| Batch plan 完整 backend 关系集 + adapter/playlist | 7 failed,296 passed in 17.42s | FAILED，仅已有 7 个 C3 登记 RED；无 errors |
| 完整 backend | 7 failed,1608 passed,1 warning in 102.14s | FULL FAILED，仅已有 7 个 C3 登记 RED；两个 adapter 装配测试通过 |
| 完整 Web 单 worker | 3 failed,299 passed；1 failed/29 passed files；48.24s | FULL FAILED，仅 C4 三登记 RED |
| 独立临时 C2 stat 审计 | new/known 各 1 failed | C2 准入阻塞；临时测试不在 server/tests，因此不能用 full 的原失败集合掩盖此缺陷 |
| Ruff server/app server/tests | All checks passed，exit 0 | GREEN |
| Web typecheck / build | vue-tsc --noEmit / Vite build，均 exit 0；build 2.20s | GREEN |

本轮 backend full 的失败节点集合与上方 C2 final 的七节点完全一致。Web 仍为 `initial_snapshot_timeout_reports_and_reconnects`、`get_timeout_ends_loading_and_retries`、`body_timeout_and_late_response_cannot_restore_baseline` 三个 C4 普通失败；未提前实现 C4，未删除、skip/xfail、放宽断言或延长预算。现有 Starlette/httpx warning 保留；未修改依赖。

原始命令/日志：`/tmp/mpd-c3-evidence/prerequisite.py`、`run.py`、`exact-results.tsv`、`direct-final.log`、`relationships-final.log`、`full-backend-final.log`、`prerequisite-web-full.log`。运行 wrapper 为每个 backend 进程创建自己的临时 config/music/app.db。临时日志不是永久测试依赖。

### 本轮实际变更与停止判定

只追加本节证据记录；没有修改生产代码或仓库测试，不补做 C2，不开始 C3/C4/C5。C3 与关联 C0 的本轮 RED→GREEN 记录为**无**，通过的 C2/C0 保护不被伪称新增 RED。C3 准入不满足，更不能报告 C3 完成或满足进入 C4 的条件。无 commit/push/PR/merge，HEAD 不变；真实设备/手机/容器/CI Gate NOT RUN。

已检查本轮追加内容的 actual no-index diff（与 /tmp/mpd-c3-evidence/evidence-before.md 比较，只有证据追加），并复核 git diff --check/stat/status、HEAD；原有 tracked diff 的文件集/stat 保持原样。typecheck/build 日志在 prerequisite-web-typecheck.log / prerequisite-web-build.log，未把生成的 dist 加入工作 diff。


## C2 stat 缺陷修复及 fresh 复验 — 2026-10-12（Asia/Shanghai）

用户在前置审计停止后显式授权“修复这两个缺陷并继续 C2”。本轮只修复该 C2 阻塞，不开始 C3/C4/C5，不 commit/push。分支仍 `fix/task-9-startup-library-reconciliation`，HEAD `098d6eaea81495d1686a09f9e0ee68768610ed7e`，全部既有 dirty 变更保留。

使用 systematic-debugging、TDD、verification-before-completion 技能按根因→永久 RED→最小改动→exact→文件→关系→full 执行。现有 .venv 为 Python 3.14.4 / pytest 9.1.1 / Ruff 0.16.9；再次读既有 requirements，不改依赖。每个 backend 子进程创建自有临时 config/music/SQLite，APP_ENV=development、MPD_MODE=mock，repo root 执行；不连接真实 MPD/NAS/DAC、不使用 Docker。

### 两个真实 RED 与同一根因的最小修复

将临时审计改为 `server/tests/services/test_library_scan_prepare.py::test_inventory_entry_stat_failure_is_isolated[new/known]` 永久参数化测试。修复前对两个节点各用独立 backend 进程运行，均在真实 prepare 行为失败，未依赖缺接口或导入错误：

| 永久节点 | 修改前 RED | 最终 fresh GREEN |
|---|---|---|
| `test_inventory_entry_stat_failure_is_isolated[new]` | 1 failed in 0.78s；期待 failed_paths=(a.flac,)，实际 () | 1 passed in 0.46s |
| `test_inventory_entry_stat_failure_is_isolated[known]` | 1 failed in 0.53s；validate_prepared 的 stat PermissionError 中断整个 prepare | 1 passed in 0.48s |

根因是 Path.is_dir/is_file 在现有 Python 内吞掉 OSError。只修改 prepare 模块的 `_walk`：用 context-managed `os.scandir` 得到 DirEntry，按不跟随 symlink 的目录项类型遍历；类型已确定的普通媒体继续进入原 `_signature` 边界，stat 错误由现有 inventory_failures/unreadable_file_uris 路径集合处理。没有按 `.flac` 名字猜它是文件；目录枚举或目录项类型无法确定的 OSError 仍使 complete=False，根级拒绝整批，防止对子树 mass missing。保持 `_walk` 的二元返回接口、canonical 排序、原 symlink 策略和原 prepare/commit 数据边界。

永久测试在整个 prepare/precheck/commit 窗口持续对单媒体 Path.stat 注入 PermissionError，证明：

- 新坏媒体被登记 failed/unreadable，无虚构 Song、无成功 sidecar 签名；正常媒体照常提交。
- 已知坏媒体是 UNREADABLE，保留 Song ID/title/lyrics/artwork/hash 和 Playlist/Favorites 引用；另一媒体真实 LRC 改动仍可提交。
- 故障解除后只 parse/hash 失败媒体各 1 次；正常媒体 parse 保持 1，hash 保持原次数（known LRC-only 为 0），不因失败重试重复读成功成果。

新增 `test_directory_inventory_failure_preserves_old_library` 在**修复前已是 GREEN**（1 passed in 0.42s），不伪称 RED。它用真正的子目录枚举 PermissionError（目录名特意为 nested.flac）确认旧 Song 集与 revision 不变，不能把未知/不可读目录当单媒体隔离。最终 fresh 为 1 passed in 0.50s。原 symlink/incomplete/mount/引用/sidecar/rollback 保护均保留。

### 最终源码 fresh 精确账本

每个节点独立使用 `.venv/bin/python -m pytest -q --tb=short '<完整节点>'` 和新临时运行根。先原 C2/C0 的 27 个唯一节点，再新增两 stat 节点、目录保护、symlink/incomplete、持久二次启动、真实 lifespan barrier，34 个全部通过：

| 完整节点 | fresh 输出 |
|---|---|
| `server/tests/services/test_library_scan_prepare.py::test_old_missing_signatures_are_backfilled_once` | 1 passed in 0.44s |
| `server/tests/services/test_library_scan_prepare.py::test_deep_reconciliation_detects_same_stat_content_change` | 1 passed in 0.44s |
| `server/tests/services/test_library_scan_prepare.py::test_media_changed_during_prepare_is_retried` | 1 passed in 0.43s |
| `server/tests/services/test_library_scan_prepare.py::test_stale_baseline_cannot_overwrite_new_commit` | 1 passed in 0.44s |
| `server/tests/services/test_library_scan_prepare.py::test_prepare_cancellation_never_commits` | 1 passed in 1.62s |
| `server/tests/services/test_library_scan_prepare.py::test_commit_data_revision_and_sync_are_atomic` | 1 passed in 0.45s |
| `server/tests/services/test_library_scan_prepare.py::test_prepare_releases_database_lock` | 1 passed in 0.42s |
| `server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[parse]` | 1 passed in 1.62s |
| `server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[hash]` | 1 passed in 1.61s |
| `server/tests/services/test_library_scan_prepare.py::test_commit_has_no_music_io_and_workers_have_no_repository_access` | 1 passed in 0.44s |
| `server/tests/services/test_library_scan_prepare.py::test_file_changed_before_commit_retains_other_prepared_results` | 1 passed in 0.44s |
| `server/tests/services/test_library_scan_prepare.py::test_conflict_reprepare_reuses_unrelated_successful_media` | 1 passed in 0.46s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[add]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[modify]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[delete]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[move]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_add]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_modify]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_delete]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[new]` | 1 passed, 1 warning in 0.10s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[known]` | 1 passed, 1 warning in 0.08s |
| `server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[during_prepare]` | 1 passed in 0.47s |
| `server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[before_scanner_commit]` | 1 passed in 0.47s |
| `server/tests/services/test_library_scan_prepare.py::test_full_prepare_artwork_fallback_revisits_only_related_observed_song` | 1 passed in 0.49s |
| `server/tests/services/test_library_scan_prepare.py::test_single_file_stat_failure_keeps_other_prepared_media` | 1 passed in 0.47s |
| `server/tests/services/test_library_scan_prepare.py::test_manual_deep_retry_does_not_repeat_good_media` | 1 passed in 0.50s |
| `server/tests/services/test_library_scan_prepare.py::test_observed_signature_backfill_survives_new_metadata_failure` | 1 passed in 0.52s |
| `server/tests/services/test_library_scan_prepare.py::test_inventory_entry_stat_failure_is_isolated[new]` | 1 passed in 0.46s |
| `server/tests/services/test_library_scan_prepare.py::test_inventory_entry_stat_failure_is_isolated[known]` | 1 passed in 0.48s |
| `server/tests/services/test_library_scan_prepare.py::test_directory_inventory_failure_preserves_old_library` | 1 passed in 0.50s |
| `server/tests/services/test_library_scanner.py::test_step7_full_scan_does_not_follow_symlinked_directories` | 1 passed in 0.49s |
| `server/tests/services/test_library_scanner.py::test_step7_traversal_error_disables_missing_reconciliation` | 1 passed in 0.42s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_persisted_second_start_skips_parse_and_hash` | 1 passed, 1 warning in 0.06s |
| `server/tests/api/test_startup_readiness.py::test_http_ws_and_library_read_during_startup_prepare` | 1 passed, 1 warning in 0.63s |

### 精确 → 直接文件 → 关系 → 完整结果

| 集合 | 最终 fresh 结果 | 判定 |
|---|---|---|
| 34 个 unique exact | 全部 passed | GREEN |
| 直接修改的 test_library_scan_prepare.py | 19 passed in 4.66s | GREEN |
| C2 全部受影响文件集（同此前 C2 final） | 7 failed,151 passed in 10.84s | FAILED；仅原登记 C3 RED |
| Batch plan backend 完整关系集 + adapter/playlist，显式 `-p server.tests.support.playback` | 7 failed,299 passed in 17.08s | FAILED；仅原登记 C3 RED；无 errors |
| 完整 backend | 7 failed,1611 passed,1 warning in 97.64s | **FULL FAILED**；仅原登记 C3 RED |
| Web 关系集：计划原 9 文件 / 单 worker | 3 failed,75 passed；1 failed/8 passed files；14.17s | FAILED；仅 C4 三 RED |
| 完整 Web / 单 worker | 3 failed,299 passed；1 failed/29 passed files；47.00s | **FULL FAILED**；仅 C4 三 RED |
| targeted Ruff 与 server/app server/tests Ruff | All checks passed，exit 0 | GREEN |
| Web typecheck / build | vue-tsc / Vite exit 0；build 2.42s | GREEN |

actual FAILED 节点集合机械比较 direct/relationship/full，三者与前置审计的七个 C3 登记节点完全一致，无新增失败。两个已修正 adapter 装配测试在统一 mock full 中通过。Web 两集合也机械核对仅三个 C4 timeout 节点，未实现任何 Web timeout。既有 Starlette/httpx warning 保留，无环境/依赖/装配失败。

仍保留的 C3 RED：

- `test_unchanged_consistent_startup_does_not_update`
- `test_inconsistent_startup_updates_once_then_confirms`
- `test_constructor_has_no_filesystem_io[resolve]`
- `test_constructor_has_no_filesystem_io[stat]`
- `test_constructor_has_no_filesystem_io[iterdir]`
- `test_startup_inventory_seed_does_not_immediately_walk`
- `test_failed_startup_has_no_competing_detector_walk`

均在 `server/tests/invariants/test_startup_library_reconciliation.py`。C4 仍是 `web/tests/invariants/startup-readiness.test.ts` 的 `initial_snapshot_timeout_reports_and_reconnects`、`get_timeout_ends_loading_and_retries`、`body_timeout_and_late_response_cannot_restore_baseline`。constructor open 的既有 GREEN 保留，不伪称 RED；无删除/skip/xfail、弱化断言或延长预算。

### 可复现命令、实际 diff 和判定

原始日志及 runner 在 `/tmp/mpd-c2-stat-fix-evidence`：red-new/red-known、green-new/green-known、directory-baseline、exact-00..33、exact-results.tsv、prepare-file、direct-final、relationships-final、full-backend-final、web-relationships/web-full/web-typecheck/web-build、ruff.log。`verify.py` 记录完整 backend 文件/命令；`web-verify.py` 记录完整 Web 命令及退出码。runner 对每个 backend 进程创建自有 mktemp 配置/音乐/DB；测试无永久 `/tmp` 日志依赖。

backend 直接集合沿用此前 C2 final 的 13 文件，包括 prepare/commit/scanner/sync、C0 startup/API，以及受影响 realtime/Repository 文件。关系命令为本 Batch plan 完整 backend 关系命令，追加 `-p server.tests.support.playback server/tests/api/test_mpd_connection.py server/tests/invariants/test_realtime_observer_lifecycle.py server/tests/invariants/test_realtime_playlist.py`。完整为 `.venv/bin/python -m pytest -q --tb=short server/tests`；Web/typecheck/build/Ruff 依计划原命令。不是以一次 full 代替 exact 和关系验收。

单独按 code-reviewer 检查点自审本轮 actual no-index diff（prepare-before.py/tests-before.py 与最终源码），核对线程/锁边界、目录资源释放、文件与目录错误分类、symlink、取消/root/commit、引用和成功成果重用；无新的 C2 未解决问题。作者自审不冒充独立 reviewer，未委派。只改 `server/app/services/library_scan_prepare.py`、`server/tests/services/test_library_scan_prepare.py` 和本证据追加；原 C1/C2/README/spec/adapter 等 dirty 全部保留。没有改 config/runtime/detector/mapper/MPD 状态机、Web 生产代码、依赖、用户数据库或环境。

**本轮两个 C2 阻塞节点已永久 RED→GREEN；C2 及关联 C0 项 3/6/7/8 的 fresh 验收满足，恢复本地进入 C3 的条件。** 前置审计停止记录仍作为历史反证保留，其两个缺陷以本节修复及永久测试解除。corrective 全套仍 FAILED，不能标 PASSED；C3/C4/C5 本轮 NOT STARTED。无 commit/push/PR/merge，HEAD 不变；真实手机/MPD/NAS/DAC、Docker、新 SHA/CI Gate NOT RUN。本轮在 C2 停止。

收尾已检查 git diff --check/stat/status、完整 HEAD，并对本轮三个原未跟踪文件的 actual no-index diff 做 whitespace 检查，均无问题。tracked diff/stat 与起始状态一致；新增修改以 no-index diff 核对，未把 stat 中缺少 untracked 内容当作没有修改。


## C3 fresh 前置复核停止：C2 owner baseline 冲突成果复用缺口 — 2026-10-12（Asia/Shanghai）

本轮用户只授权 C3，同时明确 C2 有未解决缺陷时停止、不补做 C2、不开始 C3。已核对当前分支 `fix/task-9-startup-library-reconciliation`、完整 HEAD `098d6eaea81495d1686a09f9e0ee68768610ed7e`、dirty 状态，阅读 corrective spec/Batch plan、实际 C1/C2 模型/迁移/Repository/prepare/scanner/sync 与最近 stat 永久 RED→GREEN 和 fresh 记录。保留已有全部变更，没有 commit/push/PR。

现有 .venv：Python 3.14.4 / pytest 9.1.1 / Ruff 0.16.9；已检查 server/requirements.txt。每次 backend 子进程使用新建 mktemp 配置目录、音乐目录、SQLite，外层 APP_ENV=development / MPD_MODE=mock；测试媒体来自真实 fixture。使用已有 Node 依赖，不安装/改动依赖、venv，不访问真实 MPD/NAS/DAC，不运行 Docker，不访问或清除用户数据库。

### 既有 C2 fresh 保护及关联证明

先逐个独立进程 exact 复跑最近 C2 stat 修复记录的 34 个 unique 节点，全部通过；随后直接文件、计划关系集、完整后端。没有用 full 代替 exact/关系验收。以下账本直接取自本轮输出，不引用上轮摘要作为通过证据：

| exact 节点 | 本轮结果 |
|---|---|
| `server/tests/services/test_library_scan_prepare.py::test_old_missing_signatures_are_backfilled_once` | 1 passed in 0.45s |
| `server/tests/services/test_library_scan_prepare.py::test_deep_reconciliation_detects_same_stat_content_change` | 1 passed in 0.45s |
| `server/tests/services/test_library_scan_prepare.py::test_media_changed_during_prepare_is_retried` | 1 passed in 0.44s |
| `server/tests/services/test_library_scan_prepare.py::test_stale_baseline_cannot_overwrite_new_commit` | 1 passed in 0.45s |
| `server/tests/services/test_library_scan_prepare.py::test_prepare_cancellation_never_commits` | 1 passed in 1.62s |
| `server/tests/services/test_library_scan_prepare.py::test_commit_data_revision_and_sync_are_atomic` | 1 passed in 0.44s |
| `server/tests/services/test_library_scan_prepare.py::test_prepare_releases_database_lock` | 1 passed in 0.43s |
| `server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[parse]` | 1 passed in 1.63s |
| `server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[hash]` | 1 passed in 1.62s |
| `server/tests/services/test_library_scan_prepare.py::test_commit_has_no_music_io_and_workers_have_no_repository_access` | 1 passed in 0.43s |
| `server/tests/services/test_library_scan_prepare.py::test_file_changed_before_commit_retains_other_prepared_results` | 1 passed in 0.45s |
| `server/tests/services/test_library_scan_prepare.py::test_conflict_reprepare_reuses_unrelated_successful_media` | 1 passed in 0.45s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[add]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[modify]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[delete]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[move]` | 1 passed, 1 warning in 0.06s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_add]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_modify]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_delete]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[new]` | 1 passed, 1 warning in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[known]` | 1 passed, 1 warning in 0.09s |
| `server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[during_prepare]` | 1 passed in 0.82s |
| `server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[before_scanner_commit]` | 1 passed in 0.42s |
| `server/tests/services/test_library_scan_prepare.py::test_full_prepare_artwork_fallback_revisits_only_related_observed_song` | 1 passed in 0.46s |
| `server/tests/services/test_library_scan_prepare.py::test_single_file_stat_failure_keeps_other_prepared_media` | 1 passed in 0.45s |
| `server/tests/services/test_library_scan_prepare.py::test_manual_deep_retry_does_not_repeat_good_media` | 1 passed in 0.48s |
| `server/tests/services/test_library_scan_prepare.py::test_observed_signature_backfill_survives_new_metadata_failure` | 1 passed in 0.43s |
| `server/tests/services/test_library_scan_prepare.py::test_inventory_entry_stat_failure_is_isolated[new]` | 1 passed in 0.44s |
| `server/tests/services/test_library_scan_prepare.py::test_inventory_entry_stat_failure_is_isolated[known]` | 1 passed in 0.45s |
| `server/tests/services/test_library_scan_prepare.py::test_directory_inventory_failure_preserves_old_library` | 1 passed in 0.42s |
| `server/tests/services/test_library_scanner.py::test_step7_full_scan_does_not_follow_symlinked_directories` | 1 passed in 0.41s |
| `server/tests/services/test_library_scanner.py::test_step7_traversal_error_disables_missing_reconciliation` | 1 passed in 0.47s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_persisted_second_start_skips_parse_and_hash` | 1 passed, 1 warning in 0.07s |
| `server/tests/api/test_startup_readiness.py::test_http_ws_and_library_read_during_startup_prepare` | 1 passed, 1 warning in 0.59s |

这些都是已有 GREEN 复核，不计本轮 C3 新增 RED→GREEN。两个 `test_inventory_entry_stat_failure_is_isolated[new/known]` 的原永久 RED→GREEN 记录与当前 `_walk` 的 os.scandir 实现对应；目录枚举失败仍根级拒绝、保旧库/revision。C0 项 3 的锁外 worker、真实 parser/hash 与独立数据库事务，项 6 的七种路径差异，项 7 的两个 mount 边界，项 8 的 new/known 坏路径恢复均 fresh GREEN。提交前检查、事务内零音乐 I/O、短 SQL/内存提交、原子 data/revision/SYNCING、陈旧 baseline 拒绝，以及 scanner **包装器**的冲突成果复用均由上表对应节点证明。包装器证明不能扩展成 owner 证明，见下方反证。

额外已有 GREEN exact 独立复跑：constructor `[open]` 1 passed (0.02s)；确认预算从 commit 后开始 1 passed (0.47s)；两个已修正 adapter 装配节点各 1 passed (0.11s / 0.05s)，显式 `-p server.tests.support.playback`。它们没有被伪称新增 RED。

### 新发现的 C2 集成行为缺陷：真实 owner 冲突后重新解析无关成功成果

长期 Library §7.2 / corrective spec §4.4 要求 baseline 冲突拒绝陈旧覆盖、仅重新校准冲突路径、复用正常已准备结果；Batch C2 包含 baseline 冲突和成果复用，用户本轮又要求 fresh 验证该前置条件。

现有永久 `test_conflict_reprepare_reuses_unrelated_successful_media` 只走 `scanner.scan_full`。`library_scanner.py:192` 的 LibraryScanConflict 分支保留旧 PreparedScan，只重做冲突路径；真实 startup owner 的 `library_sync_service.py:149` 却直接 prepare→precheck→commit，不使用该分支。commit 抛冲突时 PreparedScan 局部值丢失；`run` 的 scanned 仍 False，按 2 秒退避后再次 `_scan(job)`，所有未提交签名的变化媒体都会再解析。

临时独立行为探针对同一场景分别使用 wrapper 和 owner：先入库，修改 a.flac 音频与 sidecar.mp3 的关联 LRC，在首轮 prepare 后仅对 a.flac 做真实 Repository 并发写入。真实 commit 确认抛出一次 `LibraryScanConflict("Library baseline changed before commit")`。两条路径最终内容都正确；区别在未冲突的 sidecar.mp3 成果是否被复用。parser/hash spy 调用真实媒体 I/O，非假解析，期间不改变无关媒体或 LRC。

| 临时精确节点 | 最终 fresh 结果 | 分类 |
|---|---|---|
| `test_baseline_conflict_reuses_unrelated_successful_media[wrapper]` | 1 passed in 0.19s；a parse/hash=2/2，sidecar parse/hash=1/0 | 已有 C2 wrapper GREEN 控制 |
| `test_baseline_conflict_reuses_unrelated_successful_media[owner]` | 1 failed in 0.31s；同 generation、2 秒 retry、最终 Song/lyrics 断言均通过；sidecar parse=2，期望 1 | C2 owner 集成缺陷，非既登记 C3/C4 RED |

owner 在未加冲突类型记录的首次审计也真实失败（0.27s），随后 long traceback 复核失败（0.24s）；最终加入精确冲突类型/消息断言后再次真实失败（0.31s）。已读取最终完整 long traceback；失败位于最后的 `assert parsed[str(unrelated)] == 1`，实际 2。没有 collection/import/fixture/环境错误，没有产生新的生产修改。

探针只在 `/tmp/mpd-c3-fresh-preflight/test_owner_conflict.py`，不在 server/tests；因此完整 suite 的原七个失败集合不能掩盖这个新缺口。不补做 C2 测试/实现；为避免依赖临时文件存活，下方保存最终探针全文：

```python
"""Temporary preflight probe: same C2 conflict, wrapper versus real owner."""
import asyncio
import pytest
from mutagen.flac import FLAC
from server.app.repositories.database import initialize_database
from server.app.repositories.library_repository import LibraryRepository
from server.app.services.library_scanner import LibraryScanner, LibraryScanConflict
from server.app.services.library_sync_service import LibrarySyncService
from server.tests.conftest import media_fixture_dir  # noqa: F401
from server.tests.invariants.test_startup_library_reconciliation import (
    IndexedPlayer, music_fixture, spy_media, wait_synced,
)

@pytest.mark.parametrize('entry', ['wrapper', 'owner'])
def test_baseline_conflict_reuses_unrelated_successful_media(tmp_path, media_fixture_dir, monkeypatch, entry):
    root = music_fixture(tmp_path, media_fixture_dir)
    db = str(tmp_path / 'conflict.db')

    async def run():
        await initialize_database(db)
        repo = LibraryRepository(db)
        scanner = LibraryScanner(repo)
        await scanner.scan_full(root)
        audio, unrelated = root / 'a.flac', root / 'sidecar.mp3'
        tags = FLAC(audio)
        tags['title'] = ['Changed Audio']
        tags.save()
        (root / 'sidecar.lrc').write_text('[00:01.00] Changed Lyrics\n')
        parsed, hashed = spy_media(monkeypatch)
        commit = scanner.commit
        raced = False
        retries, conflicts = [], []

        async def racing(prepared, **kwargs):
            nonlocal raced
            if not raced:
                raced = True
                song = await repo.find_song_by_file_uri(str(audio))
                await repo.upsert_song(song.model_copy(update={'title': 'Concurrent Writer'}))
            try:
                return await commit(prepared, **kwargs)
            except LibraryScanConflict as exc:
                conflicts.append(str(exc))
                raise

        async def sleep(seconds):
            retries.append(seconds)
            await asyncio.sleep(0)

        monkeypatch.setattr(scanner, 'commit', racing)
        if entry == 'wrapper':
            await scanner.scan_full(root)
        else:
            sync = LibrarySyncService(scanner, IndexedPlayer(root), root, sleep=sleep)
            await sync.request_scan(None, 'startup')
            task = asyncio.create_task(sync.run())
            try:
                await wait_synced(sync)
                assert sync.get_state().generation == 1
                assert retries == [2]
            finally:
                await sync.close()
                await asyncio.wait_for(task, 1)
        assert raced
        assert conflicts == ["Library baseline changed before commit"]
        assert (await repo.find_song_by_file_uri(str(audio))).title == 'Changed Audio'
        assert (await repo.find_song_by_file_uri(str(unrelated))).lyrics == '[00:01.00] Changed Lyrics\n'
        assert parsed[str(audio)] == hashed[str(audio)] == 2
        assert hashed[str(unrelated)] == 0
        assert parsed[str(unrelated)] == 1, dict(parsed)

    asyncio.run(run())
```

复现时将上述源码写到自有临时文件，每个参数分别新建运行根，从 repo root 执行：

```bash
for entry in wrapper owner; do
  audit_root=$(mktemp -d /tmp/mpd-c2-owner-conflict-XXXXXX)
  mkdir -p "$audit_root/config" "$audit_root/music"
  APP_ENV=development MPD_MODE=mock DATABASE_PATH="$audit_root/state.db" CONFIG_DIR="$audit_root/config" MUSIC_ROOT="$audit_root/music" PYTHONPATH=. .venv/bin/python -m pytest -q --tb=long "/tmp/mpd-c3-fresh-preflight/test_owner_conflict.py::test_baseline_conflict_reuses_unrelated_successful_media[$entry]"
done
```

### Fresh 文件、关系、完整回归与检查结果

| 集合 | 本轮结果 | 判定 |
|---|---|---|
| C2 34 个 unique exact | 全部通过 | 已有 GREEN |
| 直接 prepare 文件 | 19 passed in 5.01s | GREEN |
| C2 全部直接受影响 13 文件，显式 playback plugin | 7 failed,151 passed in 10.75s | FAILED，仅原登记 C3 RED |
| Batch plan 完整 backend 关系集 + adapter/playlist，显式 playback plugin | 7 failed,299 passed in 17.08s | FAILED，仅原登记 C3 RED |
| 原计划完整 backend | 7 failed,1611 passed,1 warning in 96.22s | FULL FAILED |
| 显式 `-p server.tests.support.playback` 的统一 mock 完整 backend | 7 failed,1611 passed in 96.70s | FULL FAILED，仅原登记 C3 RED；两个 adapter 节点通过 |
| Web 计划 9 文件关系集，单 worker | 3 failed,75 passed；1 failed/8 passed files；13.87s | FAILED，仅原 C4 RED |
| 完整 Web，单 worker | 3 failed,299 passed；1 failed/29 passed files；46.28s | FULL FAILED，仅原 C4 RED |
| Ruff server/app server/tests | All checks passed，exit 0 | GREEN |
| Web typecheck / build | vue-tsc / Vite exit 0；build 2.44s | GREEN |

直接/关系/两种完整后端 FAILED 集合已机械比对完全相同，七个节点仍是 unchanged consistent、inconsistent precheck、constructor resolve/stat/iterdir、startup inventory seed、failed startup detector；无新增 suite 失败。临时 owner 审计另有上述真实 C2 RED，不能仅凭 suite 未纳入探针而报告 C2 准入满足。

C4 三个 RED 原样保留：`initial_snapshot_timeout_reports_and_reconnects`、`get_timeout_ends_loading_and_retries`、`body_timeout_and_late_response_cannot_restore_baseline`。已读取关系/full 的失败详情，仍分别为 error=null、fetch/body Promise 未 settle；不修改 Web GET/WS timeout/timer/错误文案或任何 Web production code，不删除/skip/xfail/放宽断言/延长预算。没有新环境或装配失败；既有 Starlette/httpx deprecation warning 保留，不改依赖。

所有 runner/原始日志在 `/tmp/mpd-c3-fresh-preflight`，包括 exact-results.tsv、prepare-file、direct-final、relationships-final、full-backend-final、full-backend-plugin、conflict-wrapper-final、conflict-owner-final、web-relationships/web-full/web-typecheck/web-build。run.py 对每个 backend 子进程设置自有临时环境；verify.py 的 13 文件及计划关系命令沿用最近 C2 final，完整显式 plugin 命令为 `.venv/bin/python -m pytest -q --tb=short server/tests -p server.tests.support.playback`；Web/Ruff/typecheck/build 为 Batch 原命令。

### 实际修改、diff 与停止判定

本轮仓库只追加本节证据，未改生产代码或永久测试；临时探针作为前置审计证据，不冒充 C3 新增永久节点。已检查 actual C1/C2 diff、prepare/scanner/sync 源码与两个 adapter 装配 diff，核对线程/锁/提交及冲突分支；收尾检查本轮 evidence-before 与追加后的 actual no-index diff、git diff --check/stat/status/完整 HEAD，原有生产/测试/文档 dirty 全部保留。没有把未跟踪文件不出现在 stat 误当作没有变更。

**C2 前置准入不满足：wrapper 的冲突复用是 GREEN，但实际 startup owner 的同一合同有未解决缺口。按用户明确停止条件，本轮停止前置审计，不修 C2、不开始 C3/C4/C5。C3 新节点/关联 C0 的本轮 RED→GREEN 为无；shutdown/新确认状态机等 C3 acceptance NOT RUN。C3 未完成，不满足进入 C4 的条件。** 上节 stat 修复仍有效；其 C2 整体准入结论被此 owner 反证限定，不能继续引用成完整准入证明。没有 commit/push/PR/merge；HEAD 不变，真实设施/手机/Docker/CI Gate NOT RUN。


## C3 实现与最终 fresh 验收 — 2026-10-12（Asia/Shanghai）

前置审计发现 owner baseline 冲突成果复用缺口后，用户追加授权“有额外的缺口允许在安全的情况下修复好，继续 C3 的实现”，随后要求“继续工作”。因此先前停止记录保留为历史事实；本节是该授权后的实际结果。只完成 C3 及其必要的安全缺口修复，不开始 C4/C5，不 commit/push/PR。

### 本轮实际实现与变更范围

生产代码只改七个文件：

- `server/app/config.py`：music_root 仅语法/类型验证，取消 constructor 的 os.stat/access；JSON 损坏/非法类型及其它非法配置仍 fail startup。
- `server/app/player/music_uri.py`：构造只保存 root，第一次实际映射才 canonical resolve；保留原相对路径、symlink 越界拒绝及 in-tree alias 拼写合同。
- `server/app/services/library_change_detector.py`：纯内存 seed，constructor 零音乐 I/O，run 先等待原 2 秒间隔；独立 check 的首次 root probe 仍在线程。
- `server/app/services/library_runtime.py`：detector 等单 owner 成功 startup 后消费同一 inventory，不竞争失败/未完成的 startup prepare。scheduler 与 owner 生命周期仍沿原结构关闭。
- `server/app/services/library_sync_service.py`：root identity/canonical root 来自 worker PreparedScan；单 owner precheck status/精确 URI→必要 update→postcheck，accepted/unknown 状态跨确认 retry 保留，只有明确拒绝才按合同重试控制。local audio/signature/availability/URI delta 要求 update；LRC-only 不要求 update。确认阶段预算 60 秒、poll 1 秒、retry 2/5/15/30 未改。失败路径与未确认 move/delete targets 随 generation 合并，成功成果与 committed facts 保留；失败路径记账同 commit visibility，关闭拒绝旧 owner 后续副作用。
- `server/app/services/library_scanner.py`：抽出并共用 C2 rebase 成果复用；以 detached 成功签名作比较缓存，而真实 SQL baseline/fingerprint 保持为 commit 权威。冲突等待中新路径、目录请求及缓存媒体再次变化被重新准备；稳定成功成果不重 parse/hash；observed 与 songs 不重复。owned commit 暂存完成义务，必要 update 后由 owner finalize，保留原 wire completion 顺序和错误完成事件，避免同轮双 update。
- `server/app/services/library_scan_prepare.py`：root readability 从配置迁到 worker 的初始检查；身份/文件 precheck 仍按 C2 线程检查，未额外 walk。音频 delta 补齐 UNREADABLE availability 转换；rebase 合并后的 delta 使用真实 DB baseline。未改 C2 worker shield/Event/join、数据库事务、模型/迁移/Repository 或媒体读写方式。

`main.py` 的真实 lifespan 原本已后台启动 runtime，消除构造 I/O 后即可满足预算，未修改它。没有修改任何 Web production code、timeout/timer/错误文案、依赖、Docker/CI、用户媒体或数据库。

测试新增 `server/tests/services/test_startup_sync_corrective.py`（40 节点）；扩充原 `server/tests/api/test_startup_readiness.py` 的 root-stat barrier/失败 startup HTTP/REST/WS 证明；定向更新 `server/tests/test_config.py` 的 missing-root 合同与 `server/tests/invariants/test_library_sync.py` 的 conditional update 装配。`test_library_sync_wire.py` 的 fake disconnect 同时作用于新 precheck status 读取；wire golden 原文件与全部业务断言保持。其它原有 dirty 测试/文档保留。本证据记录追加本节，并更新顶部当前状态。

### RED→GREEN、已有 GREEN 与 C0 关联

所有表中 RED 都是独立进程的真实行为失败，已读取完整结果/traceback；无缺接口、import/collection 错误充当 RED。首次 35 节点记录为 26 RED / 9 GREEN；后续补充 12 个真实 RED，共 **38 个行为节点 RED→GREEN**（包括原 7 个 C0/C3 登记 RED）。其中 31 为本轮新增行为节点，7 为原登记节点。表中 GREEN 是最终源码 release exact 的独立输出。

下表 log 名称均指 `/tmp/mpd-c3-fresh-preflight/<log>.log`；临时日志不是永久测试依赖。永久节点、失败原因与结果在此保存，可直接按完整节点重新运行。

| 完整节点 | RED 实际断言/结果（日志） | 关联 C0 | 最终 exact GREEN |
|---|---|---|---|
| `server/tests/services/test_startup_sync_corrective.py::test_baseline_conflict_reuses_unrelated_successful_media[owner]` | assert 2 == 1；1 failed in 0.52s (`c3-red-01`) | 3 / 6 / 8 | 1 passed in 0.07s |
| `server/tests/services/test_startup_sync_corrective.py::test_precheck_failure_never_blindly_updates[status]` | assert 2 == 0；1 failed in 0.50s (`c3-red-02`) | 4 / 5 | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_precheck_failure_never_blindly_updates[uri]` | assert 2 == 0；1 failed in 0.51s (`c3-red-03`) | 4 / 5 | 1 passed in 0.05s |
| `server/tests/services/test_startup_sync_corrective.py::test_precheck_failure_never_blindly_updates[timeout]` | assert 2 == 0；1 failed in 0.52s (`c3-red-04`) | 4 / 5 | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_precheck_failure_never_blindly_updates[unknown]` | assert [1] == [2]；1 failed in 0.49s (`c3-red-05`) | 4 / 5 | 1 passed in 0.05s |
| `server/tests/services/test_startup_sync_corrective.py::test_accepted_update_is_not_repeated_on_confirmation_retry` | assert 2 == 1；1 failed in 0.50s (`c3-red-06`) | 4 / 5 | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_update_outcome_is_reread_before_any_retry[unknown]` | AssertionError: assert 2 == 1；1 failed in 0.50s (`c3-red-07`) | 4 / 5 | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_update_outcome_is_reread_before_any_retry[rejected]` | assert ('update',) == ('status',)；1 failed in 0.51s (`c3-red-08`) | 4 / 5 | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[add]` | assert ('update',) == ('status',)；1 failed in 0.55s (`c3-red-09`) | 4 / 5 / 6 | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[modify]` | assert ('update',) == ('status',)；1 failed in 0.53s (`c3-red-10`) | 4 / 5 / 6 | 1 passed in 0.05s |
| `server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[delete]` | assert ('update',) == ('status',)；1 failed in 0.50s (`c3-red-11`) | 4 / 5 / 6 | 1 passed in 0.05s |
| `server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[move]` | assert ('update',) == ('status',)；1 failed in 0.49s (`c3-red-12`) | 4 / 5 / 6 | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[lrc]` | assert ('update',) == ('status',)；1 failed in 0.52s (`c3-red-13`) | 4 / 5 / 6 | 1 passed in 0.05s |
| `server/tests/services/test_startup_sync_corrective.py::test_empty_startup_checks_status_without_update` | AssertionError: assert ['update', 'status'] == ['status']；1 failed in 0.48s (`c3-red-14`) | 4 / 5 | 1 passed in 0.03s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[resolve-mapper]` | assert ['/tmp/pytest...nstru0/music'] == []；1 failed in 0.44s (`c3-red-18`) | 9（root 另关联 7） | 1 passed in 0.03s |
| `server/tests/services/test_startup_sync_corrective.py::test_mapper_first_use_canonicalizes_root_and_rejects_symlink_escape` | assert [PosixPath('/...nica0/alias')] == []；1 failed in 0.45s (`c3-red-23`) | 9（root 另关联 7） | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_next_generation_keeps_failed_paths_and_move_absence` | assert 2 == 1；1 failed in 0.52s (`c3-red-25`) | 6 / 8 | 1 passed in 0.08s |
| `server/tests/services/test_startup_sync_corrective.py::test_startup_seeds_same_inventory_in_memory_outside_lock` | AssertionError: assert [] == [LibraryInven...omplete=True)]；1 failed in 0.49s (`c3-red-26`) | 8 / 9 | 1 passed in 0.04s |
| `server/tests/api/test_startup_readiness.py::test_startup_failure_keeps_http_ready_and_old_library_readable` | assert ValueError('Invalid application configuration') is None；1 failed, 1 warning in 0.53s (`c3-red-27`) | 2 / 9 | 1 passed in 0.12s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_unchanged_consistent_startup_does_not_update` | AssertionError: assert 1 == 0；1 failed, 1 warning in 0.12s (`c3-red-28`) | 4 / 5 | 1 passed in 0.06s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_inconsistent_startup_updates_once_then_confirms` | assert False；1 failed, 1 warning in 0.13s (`c3-red-29`) | 4 / 5 | 1 passed in 0.05s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[resolve]` | assert ['/tmp/pytest...s_no_filesy0'] == []；1 failed, 1 warning in 0.04s (`c3-red-30`) | 9（root 另关联 7） | 1 passed in 0.02s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[stat]` | assert ['/tmp/pytest...s_no_filesy0'] == []；1 failed, 1 warning in 0.05s (`c3-red-31`) | 9（root 另关联 7） | 1 passed in 0.02s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[iterdir]` | assert ['/tmp/pytest...s_no_filesy0'] == []；1 failed, 1 warning in 0.04s (`c3-red-32`) | 9（root 另关联 7） | 1 passed in 0.02s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_startup_inventory_seed_does_not_immediately_walk` | assert 3 == 1；1 failed, 1 warning in 0.10s (`c3-red-33`) | 8 / 9 | 1 passed in 0.05s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_failed_startup_has_no_competing_detector_walk` | assert ['detector', 'startup'] == ['startup']；1 failed, 1 warning in 0.21s (`c3-red-34`) | 8 / 9 | 1 passed in 0.14s |
| `server/tests/api/test_startup_readiness.py::test_http_ws_and_library_read_during_startup_root_validation` | assert False；1 failed, 1 warning in 1.60s (`root-barrier-red`) | 2 / 9 | 1 passed in 0.13s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_construction_has_no_os_root_probe[stat]` | assert ['/tmp/pytest...has_n0/music'] == []；1 failed in 0.46s (`config-os-stat-red`) | 9（root 另关联 7） | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_construction_has_no_os_root_probe[access]` | assert ['/tmp/pytest...has_n0/music'] == []；1 failed in 0.46s (`config-os-access-red`) | 9（root 另关联 7） | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_partial_scan_rollback_does_not_drop_good_uncommitted_paths` | assert None is not None；1 failed in 0.57s (`rollback-paths-red`) | 3 / 6 / 8 | 1 passed in 0.08s |
| `server/tests/services/test_startup_sync_corrective.py::test_root_readability_validation_is_deferred_to_worker` | Failed: DID NOT RAISE LibraryScanError；1 failed in 0.53s (`root-readability-red`) | 9（root 另关联 7） | 1 passed in 0.03s |
| `server/tests/services/test_startup_sync_corrective.py::test_conflict_retry_reuses_stable_success_and_prepares_new_facts[new_generation]` | assert None is not None；1 failed in 0.60s (`conflict-new-generation-red`) | 3 / 6 / 8 | 1 passed in 0.07s |
| `server/tests/services/test_startup_sync_corrective.py::test_conflict_retry_reuses_stable_success_and_prepares_new_facts[new_generation_directory]` | assert (2 == 1)；1 failed in 1.15s (`conflict-directory-red`) | 3 / 6 / 8 | 1 passed in 0.07s |
| `server/tests/services/test_startup_sync_corrective.py::test_conflict_retry_reuses_stable_success_and_prepares_new_facts[changed_media]` | assert None is not None；1 failed in 0.54s (`conflict-new-media-red`) | 3 / 6 / 8 | 1 passed in 0.08s |
| `server/tests/services/test_startup_sync_corrective.py::test_conflict_retry_reuses_stable_success_and_prepares_new_facts[changed_stable_media]` | AssertionError: assert 'MP3 Song' == 'Changed During Conflict Wait'；1 failed in 0.56s (`conflict-stale-media-red`) | 3 / 6 / 8 | 1 passed in 0.08s |
| `server/tests/services/test_startup_sync_corrective.py::test_startup_path_retry_does_not_seed_unprocessed_new_media_as_accepted` | TimeoutError；1 failed in 1.61s (`startup-new-media-seed-red`) | 8 / 9 | 1 passed in 0.08s |
| `server/tests/services/test_startup_sync_corrective.py::test_rebased_prepared_audio_delta_uses_real_database_baseline` | AssertionError: assert False is True；1 failed in 0.62s (`rebase-audio-flag-red`) | 3 / 6 / 8 | 1 passed in 0.05s |
| `server/tests/services/test_startup_sync_corrective.py::test_prepared_unreadable_availability_delta_requires_audio_update` | AssertionError: assert False is True；1 failed in 0.56s (`unreadable-audio-flag-red`) | 6 / 8 | 1 passed in 0.05s |

已有 GREEN 单列，不伪称新增缺陷 RED：

| 节点 | 修改前/建立时的事实 | 最终 exact |
|---|---|---|
| `server/tests/services/test_startup_sync_corrective.py::test_baseline_conflict_reuses_unrelated_successful_media[wrapper]` | 1 passed in 0.47s，已有 GREEN | 1 passed in 0.15s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[stat-config]` | 1 passed in 0.43s，已有 GREEN | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[stat-mapper]` | 1 passed in 0.42s，已有 GREEN | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[resolve-config]` | 1 passed in 0.40s，已有 GREEN | 1 passed in 0.03s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[iterdir-config]` | 1 passed in 0.40s，已有 GREEN | 1 passed in 0.03s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[iterdir-mapper]` | 1 passed in 0.40s，已有 GREEN | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[open-config]` | 1 passed in 0.41s，已有 GREEN | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[open-mapper]` | 1 passed in 0.41s，已有 GREEN | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_shutdown_during_prepare_has_no_late_update` | 1 passed in 0.46s，已有 GREEN | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_accepted_update_timeout_retry_preserves_single_update` | 新状态机上建立时已 GREEN，不冒充修改前 RED；`accepted-timeout-protection` | 1 passed in 0.04s |
| `server/tests/services/test_startup_sync_corrective.py::test_shutdown_after_commit_keeps_facts_without_success_or_late_update` | 新状态机上建立时已 GREEN，不冒充修改前 RED；`committed-shutdown-protection` | 1 passed in 0.04s |

上表 config 的 Path.stat GREEN 仅证明该 API 未被调用；Python 3.14 的 is_dir 可直接走 os.stat，所以另补 os.stat/access 两个真实 RED，不能以 Path spy 掩盖实际 I/O。shutdown during prepare 在 C2 已经 GREEN，本轮增加 owner/runtime 真实 barrier 的永久保护仍 GREEN，未人为制造失败。

C0 项 1/2 的持久第二次启动与原 prepare barrier 已在 C2 GREEN，release 再次 GREEN；root-stat barrier 则是新增真实 RED→GREEN。C0 项 3/6/7/8 的真实 parser/hash worker、独立 DB transaction、七种差异/引用、mount 前后检查和坏路径恢复均 fresh GREEN。C0 项 4/5/9 的原七个 RED 本轮精确 GREEN；startup inventory 在正常成功路径只 prepare/walk 一次，同对象纯内存 seed，随后原 2 秒等待。失败路径 retry 保留首次安全 inventory，避免把 retry 只枚举却未处理的新文件错误 seed 为 accepted；它们在成功后按原 detector debounce 正常被发现。

### 验证中实际回归与最小修复（不是预期 RED）

- partial batch observer 过早修改 `_failed_paths`，事务 rollback 后 retry 丢弃未提交正常路径：新增永久 rollback 节点真实 RED（正常 Song 为 None）→记账移到 commit visibility→GREEN。
- cache rebase 新 inventory 曾使旧缓存 metadata/hash 被新 stat 误验证，且漏准备等待期间的新文件/新 generation：四个参数节点分别真实 RED（新 Song None、旧 title、重复 parse）→以缓存签名比较真实新事实，真实 DB baseline 仍用于 commit→GREEN。
- 合并 cached songs 与 observed 一度重复同 URI，precheck 产生 duplicate song match：读取完整失败后限定消重；原 C2 conflict node 与新增节点 exact 重新 GREEN，无改断言。
- wire golden 首次出现 success/failure sequence/domain 顺序差异：保持 commit→必要 update→scan completion→sync confirmation 的原完成义务语义，失败完成带 mpd_update_error，取消不完成旧义务；原 golden 精确恢复 GREEN，没有改 fixture JSON。
- 首次完整 backend **4 failed,1652 passed**：API restart active/root snapshot 是 closed updater 的 CancelledError 倒灌独立 scanner 调用；两个 logging 节点缺 SYNCING phase。改为 closed compatibility updater 的普通拒绝，owner `_bounded` 仍取消旧工作；补纯日志 phase，不增加 realtime 事务或控制。四个原节点精确 GREEN，API/logging 原测试未改，最终直接/关系/full 加入复核。
- 旧 order barrier 用所有 call 数判首个 update，新 precheck 会先产生 confirm；改为仅数 update，原 commit/两代顺序断言不变。空库 scheduler 旧断言强制每代 update，按新合同改为 update=0 同时断言 generation 1→2；shutdown busy 保护改为明确注入已在进行的外部 update，保留不能 SYNCED 的原断言。旧断言替换有明确 spec 依据，没有弱化 C4 或其它业务保护。
- targeted Ruff 首次有 unused os 和 import I001，限定当前文件移除/整理；最终全 backend Ruff GREEN。没有新增依赖/环境/fixture/collection 失败；已有 Starlette/httpx warning 保留。

### 最终 fresh exact → 直接文件 → 关系 → 完整

每个后端进程均新建自有临时 SQLite/config/music，APP_ENV=development、MPD_MODE=mock，从 repository root 执行；release exact、直接、关系、full 都显式 `-p server.tests.support.playback`。没有真实 MPD/NAS/DAC 或 Docker。已完整读取最终输出；不是以 full 替代 targeted/relationship。

| 集合 | 最终结果 | 判定 |
|---|---|---|
| release 95 个独立 exact（C3、C2/C0、adapter、wire、真实回归） | 95/95 GREEN | PASSED |
| 直接文件 22 个 | 258 passed in 14.63s | PASSED |
| Batch 原 backend 关系集 + C3/adapter/playlist/API/logging | 376 passed in 20.46s | PASSED |
| 完整 backend，统一 mock / 显式 playback plugin | 1660 passed in 97.80s | **FULL PASSED** |
| Web 原 9 文件关系集，单 worker | 3 failed,75 passed；1 failed/8 passed files；14.19s | FAILED，仅 C4 三登记 RED |
| 完整 Web，单 worker | 3 failed,299 passed；1 failed/29 passed files；48.23s | **FULL FAILED**，仅 C4 三登记 RED |
| 全 backend Ruff server/app server/tests | All checks passed，exit 0 | PASSED |
| Web typecheck / build | vue-tsc / Vite 均 exit 0；build 2.57s | PASSED |
| git diff --check（含新增源的 no-index 检查） | 无 whitespace 问题 | PASSED |

95 个最终 exact 逐行记录如下；均是 release 最终源码，不引用首次/上轮 GREEN：

| 完整 exact 节点 | fresh 输出 |
|---|---|
| `server/tests/services/test_startup_sync_corrective.py::test_baseline_conflict_reuses_unrelated_successful_media[wrapper]` | 1 passed in 0.15s |
| `server/tests/services/test_startup_sync_corrective.py::test_baseline_conflict_reuses_unrelated_successful_media[owner]` | 1 passed in 0.07s |
| `server/tests/services/test_startup_sync_corrective.py::test_precheck_failure_never_blindly_updates[status]` | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_precheck_failure_never_blindly_updates[uri]` | 1 passed in 0.05s |
| `server/tests/services/test_startup_sync_corrective.py::test_precheck_failure_never_blindly_updates[timeout]` | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_precheck_failure_never_blindly_updates[unknown]` | 1 passed in 0.05s |
| `server/tests/services/test_startup_sync_corrective.py::test_accepted_update_is_not_repeated_on_confirmation_retry` | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_update_outcome_is_reread_before_any_retry[unknown]` | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_update_outcome_is_reread_before_any_retry[rejected]` | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[add]` | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[modify]` | 1 passed in 0.05s |
| `server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[delete]` | 1 passed in 0.05s |
| `server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[move]` | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_local_delta_updates_only_audio_and_confirms_exact_targets[lrc]` | 1 passed in 0.05s |
| `server/tests/services/test_startup_sync_corrective.py::test_empty_startup_checks_status_without_update` | 1 passed in 0.03s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[stat-config]` | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[stat-mapper]` | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[resolve-config]` | 1 passed in 0.03s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[resolve-mapper]` | 1 passed in 0.03s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[iterdir-config]` | 1 passed in 0.03s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[iterdir-mapper]` | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[open-config]` | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_and_mapper_construction_do_not_touch_music_root[open-mapper]` | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_mapper_first_use_canonicalizes_root_and_rejects_symlink_escape` | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_shutdown_during_prepare_has_no_late_update` | 1 passed in 0.06s |
| `server/tests/services/test_startup_sync_corrective.py::test_next_generation_keeps_failed_paths_and_move_absence` | 1 passed in 0.08s |
| `server/tests/services/test_startup_sync_corrective.py::test_startup_seeds_same_inventory_in_memory_outside_lock` | 1 passed in 0.04s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_construction_has_no_os_root_probe[stat]` | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_config_construction_has_no_os_root_probe[access]` | 1 passed in 0.02s |
| `server/tests/services/test_startup_sync_corrective.py::test_accepted_update_timeout_retry_preserves_single_update` | 1 passed in 0.04s |
| `server/tests/services/test_startup_sync_corrective.py::test_shutdown_after_commit_keeps_facts_without_success_or_late_update` | 1 passed in 0.04s |
| `server/tests/services/test_startup_sync_corrective.py::test_partial_scan_rollback_does_not_drop_good_uncommitted_paths` | 1 passed in 0.08s |
| `server/tests/services/test_startup_sync_corrective.py::test_root_readability_validation_is_deferred_to_worker` | 1 passed in 0.03s |
| `server/tests/services/test_startup_sync_corrective.py::test_conflict_retry_reuses_stable_success_and_prepares_new_facts[new_generation]` | 1 passed in 0.07s |
| `server/tests/services/test_startup_sync_corrective.py::test_conflict_retry_reuses_stable_success_and_prepares_new_facts[new_generation_directory]` | 1 passed in 0.07s |
| `server/tests/services/test_startup_sync_corrective.py::test_conflict_retry_reuses_stable_success_and_prepares_new_facts[changed_media]` | 1 passed in 0.08s |
| `server/tests/services/test_startup_sync_corrective.py::test_conflict_retry_reuses_stable_success_and_prepares_new_facts[changed_stable_media]` | 1 passed in 0.08s |
| `server/tests/services/test_startup_sync_corrective.py::test_startup_path_retry_does_not_seed_unprocessed_new_media_as_accepted` | 1 passed in 0.08s |
| `server/tests/services/test_startup_sync_corrective.py::test_rebased_prepared_audio_delta_uses_real_database_baseline` | 1 passed in 0.05s |
| `server/tests/services/test_startup_sync_corrective.py::test_prepared_unreadable_availability_delta_requires_audio_update` | 1 passed in 0.05s |
| `server/tests/api/test_startup_readiness.py::test_http_ws_and_library_read_during_startup_prepare` | 1 passed in 0.12s |
| `server/tests/api/test_startup_readiness.py::test_startup_failure_keeps_http_ready_and_old_library_readable` | 1 passed in 0.12s |
| `server/tests/api/test_startup_readiness.py::test_http_ws_and_library_read_during_startup_root_validation` | 1 passed in 0.13s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_persisted_second_start_skips_parse_and_hash` | 1 passed in 0.06s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_unchanged_consistent_startup_does_not_update` | 1 passed in 0.06s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_inconsistent_startup_updates_once_then_confirms` | 1 passed in 0.05s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[add]` | 1 passed in 0.06s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[modify]` | 1 passed in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[delete]` | 1 passed in 0.06s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[move]` | 1 passed in 0.06s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_add]` | 1 passed in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_modify]` | 1 passed in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_reconcile_only_related_paths[lrc_delete]` | 1 passed in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[new]` | 1 passed in 0.07s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_corrupt_path_retry_does_not_repeat_good_media[known]` | 1 passed in 0.09s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[resolve]` | 1 passed in 0.02s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[stat]` | 1 passed in 0.02s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[iterdir]` | 1 passed in 0.02s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_constructor_has_no_filesystem_io[open]` | 1 passed in 0.02s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_startup_inventory_seed_does_not_immediately_walk` | 1 passed in 0.05s |
| `server/tests/invariants/test_startup_library_reconciliation.py::test_failed_startup_has_no_competing_detector_walk` | 1 passed in 0.14s |
| `server/tests/services/test_library_scan_prepare.py::test_old_missing_signatures_are_backfilled_once` | 1 passed in 0.07s |
| `server/tests/services/test_library_scan_prepare.py::test_deep_reconciliation_detects_same_stat_content_change` | 1 passed in 0.06s |
| `server/tests/services/test_library_scan_prepare.py::test_media_changed_during_prepare_is_retried` | 1 passed in 0.05s |
| `server/tests/services/test_library_scan_prepare.py::test_stale_baseline_cannot_overwrite_new_commit` | 1 passed in 0.05s |
| `server/tests/services/test_library_scan_prepare.py::test_prepare_cancellation_never_commits` | 1 passed in 1.24s |
| `server/tests/services/test_library_scan_prepare.py::test_commit_data_revision_and_sync_are_atomic` | 1 passed in 0.06s |
| `server/tests/services/test_library_scan_prepare.py::test_prepare_releases_database_lock` | 1 passed in 0.03s |
| `server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[parse]` | 1 passed in 1.23s |
| `server/tests/services/test_library_scan_prepare.py::test_slow_media_io_runs_without_transaction[hash]` | 1 passed in 1.24s |
| `server/tests/services/test_library_scan_prepare.py::test_commit_has_no_music_io_and_workers_have_no_repository_access` | 1 passed in 0.04s |
| `server/tests/services/test_library_scan_prepare.py::test_file_changed_before_commit_retains_other_prepared_results` | 1 passed in 0.05s |
| `server/tests/services/test_library_scan_prepare.py::test_conflict_reprepare_reuses_unrelated_successful_media` | 1 passed in 0.06s |
| `server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[during_prepare]` | 1 passed in 0.05s |
| `server/tests/repositories/test_library_scan_commit.py::test_mount_replacement_never_commits_mass_missing[before_scanner_commit]` | 1 passed in 0.05s |
| `server/tests/services/test_library_scan_prepare.py::test_full_prepare_artwork_fallback_revisits_only_related_observed_song` | 1 passed in 0.08s |
| `server/tests/services/test_library_scan_prepare.py::test_single_file_stat_failure_keeps_other_prepared_media` | 1 passed in 0.05s |
| `server/tests/services/test_library_scan_prepare.py::test_manual_deep_retry_does_not_repeat_good_media` | 1 passed in 0.07s |
| `server/tests/services/test_library_scan_prepare.py::test_observed_signature_backfill_survives_new_metadata_failure` | 1 passed in 0.05s |
| `server/tests/services/test_library_scan_prepare.py::test_inventory_entry_stat_failure_is_isolated[new]` | 1 passed in 0.05s |
| `server/tests/services/test_library_scan_prepare.py::test_inventory_entry_stat_failure_is_isolated[known]` | 1 passed in 0.06s |
| `server/tests/services/test_library_scan_prepare.py::test_directory_inventory_failure_preserves_old_library` | 1 passed in 0.05s |
| `server/tests/services/test_library_scanner.py::test_step7_full_scan_does_not_follow_symlinked_directories` | 1 passed in 0.03s |
| `server/tests/services/test_library_scanner.py::test_step7_traversal_error_disables_missing_reconciliation` | 1 passed in 0.03s |
| `server/tests/services/test_library_sync_service.py::test_confirmation_budget_starts_after_scanner_commit` | 1 passed in 0.04s |
| `server/tests/invariants/test_library_sync.py::test_commit_update_confirmation_and_next_generation_are_ordered` | 1 passed in 0.07s |
| `server/tests/invariants/test_library_sync.py::test_runtime_startup_scheduler_and_shutdown_share_one_owner` | 1 passed in 0.03s |
| `server/tests/invariants/test_library_sync.py::test_runtime_does_not_duplicate_startup_before_scheduled_interval` | 1 passed in 0.28s |
| `server/tests/api/test_mpd_connection.py::test_saved_endpoint_overrides_invalid_old_environment_and_adapter_uses_it` | 1 passed in 0.09s |
| `server/tests/invariants/test_realtime_observer_lifecycle.py::test_composition_root_starts_one_sampler_without_clients_and_awaits_shutdown` | 1 passed in 0.03s |
| `server/tests/api/test_library_sync_wire.py::test_library_sync_server_golden_uses_real_scanner_and_public_wire` | 1 passed in 0.22s |
| `server/tests/api/test_realtime.py::test_real_lifespan_restart_replaces_epoch_and_discards_late_old_get[True]` | 1 passed in 0.23s |
| `server/tests/api/test_realtime_state.py::test_root_snapshot_reports_real_producer_versions` | 1 passed in 0.15s |
| `server/tests/test_logging.py::test_activity_phase_and_errors_are_correlated_without_secrets` | 1 passed in 0.04s |
| `server/tests/test_logging.py::test_sync_shutdown_logs_terminal_phase_without_changing_business_result` | 1 passed in 0.03s |

原始 runner/完整日志：`/tmp/mpd-c3-fresh-preflight/release_verify.py`、`run.py`、`release-exact-results.tsv`、`release-direct.log`、`release-relationships.log`、`release-full-backend.log`；Web 为 `final_web_verify.py` / `final-web-relationships/full/typecheck/build.log`，Ruff 为 release-ruff.log。每次运行的具体节点与文件参数在 runner 中；永久测试不依赖这些临时文件。

可复现命令与范围：exact 为 `.venv/bin/python -m pytest -q --tb=short '<完整节点>' -p server.tests.support.playback`；直接文件包含 C3 新测试、prepare/commit/scanner/sync/detector/config/mapper、startup、受影响 realtime/Repository，以及 API realtime/state 与 logging；关系为 Batch 原完整命令追加 C3 新文件、两个 adapter 装配文件、realtime_playlist、API realtime/state、logging。full 为 `.venv/bin/python -m pytest -q --tb=short server/tests -p server.tests.support.playback`。Web relation/full/typecheck/build 与 Batch 原命令一致，所有 Vitest 都单 worker。两 adapter 节点 release exact/full 均通过。

### 实际 diff、审查限制与门槛

已对比本轮前 source-hashes/tracked diff 与最终源码，检查 actual diff（含原未跟踪 prepare、startup API、新 C3 测试），没有覆盖原 C1/C2/README/spec/adapter dirty；原模型/迁移/Repository、Web fixtures/production、依赖保持。检查 Git diff --check/stat/status/完整 HEAD，并审 no-index 本轮源码/证据差异，未把 stat 不列 untracked 当作没有变更。当前 dirty 包含起始全部变更与上述 C3 文件；无生成 dist、临时 DB/log/config/venv 入 Git。

按 requesting-code-review 技能尝试只读独立 C3 reviewer；agent 因平台 usage limit 未启动，**独立 review NOT RUN，不算 review PASS**。随后继续作者自审，对照 code-reviewer 检查点核对真实 diff、root/seed、accepted/unknown、取消、target 合并、baseline/cache、事务与完成义务，确认所有已发现 C3 缺口已由永久行为证据解决。作者自审不冒充独立审查；review 工具额度限制与代码/测试/依赖失败分开记录。

Ruling：用户后续明确授权安全修复额外缺口，故原前置停止后可补齐 owner conflict、cache/new facts 和 delta flags，再继续 C3；仍不扩张 C4/C5。失败 retry 保留首次安全 startup inventory，未处理的新媒体留给等待原间隔后的 detector；不额外立即全树 walk，也不丢新媒体。旧 conditional update 相关测试装配按新合同定向替换，所有业务/预算断言及 C4 RED 保持。独立 reviewer 无法运行时采用作者自审并明确限制，不将工具失败冒充审查通过。

**C3 实现、精确节点及最终验收证据满足本地进入 C4 的条件；本轮在 C3 停止。** 完整 backend GREEN，完整 Web 仍 FAILED，只剩 `initial_snapshot_timeout_reports_and_reconnects`、`get_timeout_ends_loading_and_retries`、`body_timeout_and_late_response_cannot_restore_baseline` 三个 C4 普通 RED；不 skip/xfail/删除/放宽断言/延长预算。当前没有已确认未解决的 C3 回归，corrective 总体自动 Gate 尚未通过。C4/C5、真实设备/手机/MPD/NAS/DAC、Docker/新 SHA/远端 CI Gate NOT RUN。

分支仍 `fix/task-9-startup-library-reconciliation`；HEAD `098d6eaea81495d1686a09f9e0ee68768610ed7e`；无 commit/push/PR/merge。


## C4 Web 有界读取与明确恢复 — 2026-10-12（Asia/Shanghai）

用户确认 C3 已完成后要求重试，本轮重新核对当前 checkout，不引用先前 C3 缺失的结论。分支 `fix/task-9-startup-library-reconciliation`，完整 HEAD `098d6eaea81495d1686a09f9e0ee68768610ed7e`；已有 C1/C2/C3 与文档/测试 dirty 全部保留。本轮只实现 C4，不 commit/push/PR，不推进 C5，不运行 Docker、不连接真实 MPD/NAS/DAC、不修改 Node/Python 依赖或 .venv。

### C3 前置门：源码 + 本轮 fresh 结果

已重新读取 corrective spec/Batch plan/evidence，并对照实际 C1 observed/sidecar/v5/baseline、C2 worker/precheck/commit/rebase、C3 config/mapper/owner/runtime/detector 实现。构造音乐树 I/O 已移除，mapper 首次使用才 resolve；startup_ready 后 seed 同一完整 inventory，detector 等原间隔；conditional precheck/update/postcheck、accepted/unknown retry、失败路径和旧 absence 合并、取消/完成义务与实际永久测试对应。

使用本轮新临时运行根逐进程 `.venv/bin/python -m pytest -q --tb=short <节点或集合> -p server.tests.support.playback`，APP_ENV=development、MPD_MODE=mock、临时 CONFIG_DIR/MUSIC_ROOT/DATABASE_PATH。没有使用已有运行数据库或真实设施。95 个 release exact 逐节点重新执行，覆盖 C3 指定节点、关联 C0 项 1/2/4/5/8/9、C2 安全保护和 adapter/wire/真实回归。

| C3 gate 集合 | 本轮 fresh 结果 |
|---|---|
| release 95 个独立 exact | 95/95 passed |
| 原 C3 22 个直接文件 | 258 passed in 17.64s |
| Batch 完整 backend 关系集 + C3/adapter/playlist/API/logging | 376 passed in 25.36s |
| 完整 backend / 显式 playback plugin | 1660 passed in 127.67s |
| 修改前完整 Web / 单 worker | 3 failed,299 passed；1 failed/29 passed files；57.39s |

完整 Web 的失败集精确为三个登记 C4 RED，无新增失败、import/collection/装配/环境错误。C3 gate 通过后才开始 C4 测试和生产修改。后端源码本轮没有变化，以起始文件 SHA256 与收尾比较确认，所以没有无必要重跑完整 backend。Python 3.14.4 / pytest 9.1.1 / Ruff 0.16.9；已核对 requirements，不安装或改版本。

### 永久 RED → GREEN 与 baseline GREEN

三个 C0 节点分别以 `npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts -t '<完整名称>' --maxWorkers=1 --minWorkers=1` fresh 执行：initial 在 9,999ms 未关闭、10,000ms error 仍 null；fetch/body 两项在 10,000ms 的 settled 仍 false。均为真实行为断言失败，非测试 timeout、接口缺失或导入错误。原业务断言、错误文案与 10,000ms 预算全部保留。

| 永久节点 | 实现前 RED 原因 | 最终 |
|---|---|---|
| initial_snapshot_timeout_reports_and_reconnects | error=null，无关闭/重连 | GREEN |
| get_timeout_ends_loading_and_retries | 永不返回 fetch 未 settle | GREEN |
| body_timeout_and_late_response_cannot_restore_baseline | headers 已返回，body 未 settle | GREEN |
| success_stop_and_reconnect_clear_timeout_timers | 创建 socket 后计时器数为 0，缺首帧预算 | GREEN |
| get_after_timeout_does_not_enable_mutations | 无 READ_TIMEOUT，未撤销旧写权限 | GREEN |
| never_settling_abort_ignored_fetch_uses_one_total_budget | 10,000ms 未 settle | GREEN |
| never_settling_abort_ignored_body_uses_one_total_budget | headers 7,000ms 到达后 body 仍无界；10,000ms 未 settle | GREEN |
| abort_rejection_cannot_replace_typed_read_timeout | 预算到期没有 typed 错误 | GREEN |
| injected_budgets_use_fixture_clock_and_dispose_old_initial | 注入预算到期没有 typed 错误 | GREEN |
| resource_timeout_ends_loading_and_uses_existing_notice_read | loading 保持 true，notice 仍 pending | GREEN |
| generation_change_cannot_restart_a_timed_out_resource_budget | generation 变化导致旧 timeout 自动启动下一读取，原 Promise 未 settle | GREEN |
| top_timeout_INITIAL_SNAPSHOT_TIMEOUT_keeps_existing_read_recovery | 顶部详情只有泛化异常/连接文案 | GREEN |
| top_timeout_READ_TIMEOUT_keeps_existing_read_recovery | 顶部详情没有状态读取超时文案 | GREEN |

共 13 个真实行为 RED→GREEN（原三项 + 新十项）。四个 `terminal_network/json/http/decode_failure_clears_read_timer` 在实现前已有 GREEN，保留为 baseline GREEN，不伪称 RED。最终 17 个 exact（startup 15 + 顶部 notice 2）逐节点均通过；`-t` 输出中的其它 skipped 仅来自节点筛选，源中未添加 skip/xfail，完整 suite 所有测试实际执行。

### 实际改动及范围裁定

- `web/src/services/api.ts`：可注入 readTimeoutMs/ReadClock，默认 10,000ms；GET 独立 deadline race 覆盖 fetch、body、decode，并触发 AbortController。abort 被忽略时仍按预算 settle；超时先 reject typed READ_TIMEOUT 再 abort，避免同步 AbortError 覆盖。finally 清理 timer 和外部取消监听；迟到 fetch/body 不再调用 decoder。Mutation/send/key/unknown 原语义保持，没有重放。
- `web/src/services/realtime.ts`：socket 创建时启动默认 10,000ms initial 计时器，完整合法 initial 才清除；创建失败、协议失败、disconnect、stop 均清理。initial 超时移除旧监听/关闭 socket，沿既有退避重连。state GET flight 带取消信号，stop/reconnect settle 并清 deadline；state timeout 撤销旧 baseline 写权限，成功 GET 只读，完整新 initial 才恢复。
- `web/src/runtime/playerSession.ts`：typed timeout 映射到原 connection/read notice 和原重读入口。文案分别为“初始状态读取超时，正在重连”“状态读取超时，请重试”。initial 不再重复生成一个泛化 read 异常活动；资源 GET 原组件自动投影“资源读取超时，请重试”，无第二套 loading/notice authority。
- `web/src/stores/resourceCache.ts`：仅旧 generation 的 READ_TIMEOUT 分支向原调用方 reject，不隐式重启预算，也不写入当前数据/错误；其它旧响应、旧普通失败与 generation/epoch/revision 规则不改。该现有缓存 owner 是 C4 总预算必要关联边界，新增永久节点先 RED 后最小修复，未引入新权威。
- `web/tests/invariants/startup-readiness.test.ts`：保留原行为断言，增加预算、清理、禁写、迟到、永不 settle、notice/loading/重读永久证明。
- `web/tests/invariants/global-notices.test.ts`：增加两种 typed timeout 的原顶部详情与原重读入口证明。
- `web/tests/invariants/client.test.ts`：精确 RequestInit 期望补 AbortSignal 类型与成功后未 abort；原 same-origin、GET、无幂等键断言不变。

Ruling：原 C0 资源测试在第二个 socket 创建后才发 GET，两个默认预算同一时刻到期。新 initial timeout 合法触发第二次既有 backoff（1,000ms）；测试末尾仅把 fixture 等待 500ms 改为真实第二次退避 1,000ms，保留所有原 expect，预算断言仍是 10,000ms。没有延长读取预算、改退避算法或弱化写权限/重试断言。首轮未改此 fixture 时失败在恢复 initial 的 writable=true 断言，分类为新增同时超时后的测试时序装配，不能充作新的业务 RED。

首轮直接文件的唯一额外失败是旧 client 对 RequestInit 精确比较遗漏 signal；读完整错误后按上述必需 abort 接口定向更新测试并 exact 通过。该装配更新不计行为 RED→GREEN；原 mutation/wire/其它业务测试未改。没有超出 C4 的后端或 C5 变更。

### 最终 fresh exact → 直接文件 → 关系 → 完整 Web

所有 Vitest 使用仓库既有 Node 依赖、单 worker。精确 17 项逐节点后，直接五文件为 startup-readiness/global-notices/resource-cache/realtime/client；关系使用 Batch 原九文件；full 不带路径过滤。旧 client 适配后先 rerun 该 exact，再重跑直接→关系→full。此前失败日志保留，不用失败结果抵扣最终验收。

| 集合 | 最终结果 | 判定 |
|---|---|---|
| C4 17 个独立 exact | 17/17 passed | PASSED |
| client AbortSignal 装配 exact | 1 passed | PASSED（装配保护） |
| 直接五文件 | 61 passed / 5 files；10.11s | PASSED |
| Batch 指定 Web 九文件关系集 | 92 passed / 9 files；16.64s | PASSED |
| 完整 Web | 316 passed / 30 files；54.18s | FULL PASSED |
| npm --prefix web run typecheck | vue-tsc --noEmit，exit 0 | PASSED |
| npm --prefix web run build | Vite exit 0，2.55s | PASSED |
| .venv/bin/python -m ruff check server/app server/tests | All checks passed，exit 0 | PASSED |
| git diff --check + scoped no-index whitespace | 无 whitespace 问题 | PASSED |

最终 exact 的逐节点命令/输出：

- `initial_snapshot_timeout_reports_and_reconnects`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.67s (transform 478ms, setup 64ms, collect 599ms, tests 41ms, environment 478ms, prepare 133ms)，exit 0。
- `get_timeout_ends_loading_and_retries`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.71s (transform 465ms, setup 80ms, collect 568ms, tests 34ms, environment 489ms, prepare 135ms)，exit 0。
- `body_timeout_and_late_response_cannot_restore_baseline`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.63s (transform 466ms, setup 84ms, collect 565ms, tests 34ms, environment 480ms, prepare 135ms)，exit 0。
- `success_stop_and_reconnect_clear_timeout_timers`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.67s (transform 482ms, setup 93ms, collect 593ms, tests 32ms, environment 478ms, prepare 126ms)，exit 0。
- `get_after_timeout_does_not_enable_mutations`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  2.17s (transform 516ms, setup 78ms, collect 638ms, tests 32ms, environment 840ms, prepare 180ms)，exit 0。
- `never_settling_abort_ignored_fetch_uses_one_total_budget`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.69s (transform 469ms, setup 57ms, collect 633ms, tests 28ms, environment 505ms, prepare 119ms)，exit 0。
- `never_settling_abort_ignored_body_uses_one_total_budget`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.70s (transform 530ms, setup 70ms, collect 629ms, tests 24ms, environment 479ms, prepare 148ms)，exit 0。
- `abort_rejection_cannot_replace_typed_read_timeout`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.74s (transform 509ms, setup 83ms, collect 629ms, tests 13ms, environment 503ms, prepare 142ms)，exit 0。
- `terminal_network_failure_clears_read_timer`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.83s (transform 461ms, setup 68ms, collect 635ms, tests 22ms, environment 518ms, prepare 159ms)，exit 0。
- `terminal_json_failure_clears_read_timer`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.79s (transform 498ms, setup 74ms, collect 629ms, tests 18ms, environment 535ms, prepare 138ms)，exit 0。
- `terminal_http_failure_clears_read_timer`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.76s (transform 505ms, setup 80ms, collect 622ms, tests 23ms, environment 516ms, prepare 128ms)，exit 0。
- `terminal_decode_failure_clears_read_timer`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.88s (transform 509ms, setup 65ms, collect 700ms, tests 23ms, environment 538ms, prepare 130ms)，exit 0。
- `injected_budgets_use_fixture_clock_and_dispose_old_initial`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.76s (transform 513ms, setup 67ms, collect 672ms, tests 28ms, environment 507ms, prepare 131ms)，exit 0。
- `resource_timeout_ends_loading_and_uses_existing_notice_read`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.85s (transform 527ms, setup 61ms, collect 588ms, tests 193ms, environment 489ms, prepare 129ms)，exit 0。
- `generation_change_cannot_restart_a_timed_out_resource_budget`：Test Files  1 passed (1); Tests  1 passed | 14 skipped (15); Duration  1.71s (transform 503ms, setup 68ms, collect 639ms, tests 25ms, environment 477ms, prepare 145ms)，exit 0。
- `top_timeout_INITIAL_SNAPSHOT_TIMEOUT_keeps_existing_read_recovery`：Test Files  1 passed (1); Tests  1 passed | 11 skipped (12); Duration  4.89s (transform 2.75s, setup 66ms, collect 3.57s, tests 160ms, environment 539ms, prepare 124ms)，exit 0。
- `top_timeout_READ_TIMEOUT_keeps_existing_read_recovery`：Test Files  1 passed (1); Tests  1 passed | 11 skipped (12); Duration  5.05s (transform 2.83s, setup 83ms, collect 3.67s, tests 255ms, environment 516ms, prepare 141ms)，exit 0。


可复现 runner/完整原始日志位于 `/tmp/mpd-c4-evidence-d7yw10mo`：gate.py/run.py 与 release-exact-results.tsv、release-direct/relationships/full-backend.log；gate-web-full.log；三个 red-<C0 node>.log；red-new-0..7.log、red-resource-notice.log、red-generation-budget.log；verify_web.py/web-results.json 与 final-exact-00..16、final-direct/relationships/full/typecheck/build.log，client-adapter-exact.log、final-ruff.log。初次失败记录 first-green-file.log、green-exact-01.log、final-direct-first.log 保留。临时文件和生成 dist 不进入 Git，永久测试不依赖临时日志。

### Actual diff、自审及停止判定

对本轮起始所有 tracked/untracked 源文件 SHA256 与最终文件比较，并保存原始 scoped 文件/no-index patch：本轮只改七个上述 Web 文件及本证据记录；C1/C2/C3 后端、原 README/specs、其它 dirty 文件保持原始内容，没有删除文件、依赖变化、临时数据库/配置/日志/venv 入 Git。检查 tracked diff/stat/status/HEAD，未把 untracked startup 测试或 evidence 不在 stat 中误当作没有修改。

沿用户指定的当前 native checkout 与 Batch 不默认委派规则，完成独立于实现步骤的作者自审，对照 code-reviewer 检查点检查 deadline/abort 的先后、总预算、dispose/generation、body late result、timer/listener 清理、缓存 stale timeout、原顶部 notice、只读与 mutation unknown/key 合同；未发现未解决的 C4 缺口。作者自审不冒充独立 reviewer；独立 review NOT RUN。

**C4 实现与本地精确/关系/完整 Web 验收已满足进入 C5 的条件。** 本轮 C3 fresh backend 全绿且源码未改，没有已确认未解决的 C3/C4 或其它自动回归。C5 最终 acceptance/CI 工作尚未开始；不把本地 GREEN 当作远程容器交付或真实设备验收。手机、真实 MPD/NAS/DAC、Docker、新 SHA/远端 CI NOT RUN。无 commit/push/PR/merge；HEAD 不变，在 C4 停止。
