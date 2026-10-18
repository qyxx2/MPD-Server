# Task 9 Startup Library Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native execution after user approval of spec/plan. Use superpowers:subagent-driven-development only if the user selects delegation. Steps use checkbox syntax. No production code before C0 RED evidence.

**Goal:** 持久曲库启动差异校准且Web可读，扫描无长DB锁，按需MPD更新，初始Web读取有界失败并恢复。

**Architecture:** Library单owner短baseline事务→线程prepare→短commit；复用音频持久签名并补sidecar辅助索引。原coordinator拥有revision/sequence，原realtime/API客户端拥有有界read与恢复。

**Tech Stack:** 既有FastAPI、SQLite、Pydantic、pytest/Ruff、Vue、TypeScript、Vitest；原.venv及已有Node依赖。

**Spec:** [corrective design](../task-9/2026-10-12-task-9-startup-library-reconciliation-design.md)，长期合同Library §7.2、Architecture §4.1/8.2/12；[root-cause evidence](2026-10-12-task-9-startup-root-cause-evidence.md)。

**Status:** DRAFT / USER REVIEW REQUIRED。C0–C5 NOT STARTED；没有十项永久RED或corrective GREEN结果。

## Global Constraints

- 基线远端feature/task-9-web / 098d6eaea81495d1686a09f9e0ee68768610ed7e；独立fix/task-9-startup-library-reconciliation。
- 只处理本corrective；不合并main、不推进其它Task、不自动commit/push/PR。
- 所有Python使用.venv/bin/python，不改.venv/依赖；所有DB/音乐/配置使用自有临时目录。
- 不连接真实MPD/NAS/DAC，不本地运行Docker；CI交付新SHA，不用旧镜像验修复。
- 禁止调大start_period/SCAN_INTERVAL_SECONDS、删除DB、禁用startup同步或延长Web等待掩盖后端阻塞。
- 原媒体只读；Queue/Playback/Playlist/Favorites/History/Output/幂等语义保持。
- fixture下就绪/读取预算1秒；Web initial/GET默认10,000ms，可注入；500ms debounce、2秒detector、12小时deep、60秒确认、1秒poll及2/5/15/30秒retry保持。
- 所有十项新增缺陷RED先于任何生产修改；相关旧保护baseline GREEN不能伪造RED。

## Review Focus

1. 停机期间LRC删除与旧库缺签名：一次补齐，embedded fallback不丢（C1/C2）。
2. 相同size/mtime但内容不同：startup按签名合同跳过，deep发现差异（C2）。
3. mount replacement、半写入及commit前baseline冲突：不mass missing/陈旧覆盖（C2）。
4. 损坏文件与MPD确认同时失败、下一generation move/delete：只重试必要路径，不丢旧目标（C3）。
5. GET headers返回但body永不settle、abort被忽略、旧timer跨重连：有界失败且不倒灌（C4）。

## 文件职责与内部接口

| 文件 | 本轮责任 |
|---|---|
| server/app/models/library.py | ScanBatch observed/sidecar delta内部表示，不改公开Song DTO |
| server/app/repositories/migrations.py | v4→v5 sidecar辅助表，兼容已有数据 |
| server/app/repositories/library_repository.py | baseline读取、observed保留、sidecar原子提交 |
| server/app/services/library_scan_prepare.py（新） | immutable输入、线程inventory/差异/parse/hash/移动匹配/失败集合 |
| server/app/services/library_scanner.py | async prepare调度与短commit、既有扫描包装器/事件顺序 |
| server/app/services/library_sync_service.py | 单owner、路径retry、条件update与精确确认 |
| server/app/config.py / player/music_uri.py | 音乐根验证移至prepare、mapper延迟resolve，保留配置语法及映射安全 |
| server/app/services/library_change_detector.py / library_runtime.py / main.py | 无I/O构造、startup inventory交接、HTTP先放行、关闭 |
| web/src/services/api.ts / realtime.ts | GET/initial预算、abort/timer/重试清理 |
| web/src/runtime/playerSession.ts | typed超时投影到既有唯一活动与重读 |
| .github/workflows/container.yml | fix/** push进入现有验证/双架构SHA构建 |

计划内接口（批准后实现；无新公开API）：

- `FileSignature(file_uri: str, file_size: int, file_mtime_ns: int)`为frozen dataclass；`SidecarSignature(lrc_uri: str, file_size: int | None, file_mtime_ns: int | None)`为frozen Pydantic model，供ScanBatch消费。不存在用两NULL、未知用缺记录。
- `LibraryInventory(root: Path, identity: tuple[int,int], entries: tuple[FileSignature,...], complete: bool)`；包含audio与LRC，保留原URI/Unicode。
- `ScanBaseline(songs: tuple[Song,...], sidecars: tuple[tuple[str,SidecarSignature],...], fingerprint: str)`；sidecars按song_id，含当前album artwork来源所需信息（Song已有album_id/artwork）。fingerprint覆盖本轮可能修改的Library与签名，不包括扫描审计时间。ScanBaseline放models/library_scan.py，Repository不import services；该模块不反向import repository/scanner。
- `PreparedScan(batch: ScanBatch, inventory: LibraryInventory, baseline: ScanBaseline, failed_paths: tuple[Path,...], audio_index_changed: bool)`。新增ScanBatch `observed_file_uris: tuple[str,...]`与`sidecar_signatures: dict[str,SidecarSignature]`（key为audio URI，commit映射到Song ID）；SidecarSignature在models/library.py定义。FileSignature/LibraryInventory/ScanBaseline/PreparedScan在models/library_scan.py定义，prepare函数在services/library_scan_prepare.py，避免循环import。
- `LibraryRepository.read_scan_baseline() -> ScanBaseline`：短事务immutable读；禁止Repository import services。`apply_scan_batch(batch: ScanBatch) -> ScanResult`保持既有签名。
- `prepare_scan(root: Path, baseline: ScanBaseline, paths: tuple[Path,...] | None, *, deep: bool, identity: tuple[int,int] | None, cancelled: threading.Event) -> PreparedScan`：同步函数只在线程执行；paths=None安全全inventory差异，deep=True才强制全解析/hash。
- `LibraryScanner.prepare(root: Path, paths: tuple[Path,...] | None = None, *, deep: bool = False, identity: tuple[int,int] | None = None) -> PreparedScan`：async、baseline在锁内读取后退出，再to_thread；拒绝active outer transaction。
- `LibraryScanner.commit(prepared: PreparedScan, *, stage_sync: Callable[[ScanResult], None] | None = None) -> ScanResult`：async、线程预检后短事务SQL+内存；baseline冲突抛`LibraryScanConflict`，不覆盖。已存在outer事务时只允许消费提前准备且已做线程预检的batch，不再await线程检查；首次commit验证outer原始baseline，同outer后续batch可共享已验证原始baseline，自己的前一次修改不算外部冲突。stage_sync同步回调不得I/O；最终scan completion由sync在必要update之后调用scanner finalize，避免同轮双update。
- `LibraryChangeDetector.seed(inventory: LibraryInventory) -> None`：纯内存，不做resolve/stat；startup交接后run先sleep再check。
- Web `createApiClient`增加可选`readTimeoutMs`及timer clock；`createRealtimeClient`增加可选`initialSnapshotTimeoutMs`，默认10,000。Mutation接口不变。

## Contract Matrix — REQUIRED

所有行共用：P=自有临时DB/fixture、单扫描owner、已初始化协调器；A=FS/Repository/PlayerPort/coordinator/Web各自事实；U=Queue/Playback/Playlist/Favorites/History/Output及mutation/key不变；H=原LibraryChangedEvent顺序和§12通知，不伪造播放History；O=既有REST/WS/typed错误。以下每行补充Δ、X、T、F、R与精确proof，连同共用字段构成Architecture §19.5完整合同。

| ID / Type / Operation → 唯一Spec | Δ / External confirmation(X) | Transaction(T) / Failure(F) / Retry(R) | Owner → executable proof |
|---|---|---|---|
| LIB-STARTUP-RECONCILE-001 / LIFECYCLE / restart → Library §7.2 | 仅签名差异，丢旧MPD证明；X安全inventory与精确URI | T签名同Song提交；F保留旧；R缺签名成功后只一次 | scanner/runtime → test_persisted_second_start_skips_parse_and_hash |
| LIB-SCAN-OBSERVED-001 / REPRESENTATION / commit → Library §7.2 | observed未变URI保AVAILABLE；X完整inventory | T同batch原子；F无删除证据不missing；R幂等不增revision | repository → test_observed_unchanged_uri_is_not_missing |
| LIB-SCAN-TXN-001 / TRANSACTION / prepare+commit → Architecture §8.2/12 | prepare旧数据可读，commit新revision/SYNCING共可见；Xworker barrier | T仅SQL/内存；F冲突/rollback无覆盖；R复用有效prepare | scanner/coordinator → test_prepare_releases_database_lock、test_commit_data_revision_and_sync_are_atomic |
| LIB-WEB-READY-001 / LIFECYCLE / lifespan → Architecture §8.2 | HTTP先放行；Xstate/Library/WS真实响应 | T读取既有边界；F扫描错误不阻启动；R后台恢复 | main/runtime → test_http_ws_and_library_read_during_startup_prepare |
| LIB-DETECTOR-INVENTORY-001 / LIFECYCLE / seed → Library §7.2 | 复用startup inventory；X遍历计数 | T内存seed锁外；F无安全seed不并行walk；R等间隔/保下一轮 | detector → test_constructor_has_no_filesystem_io、test_startup_inventory_seed_does_not_immediately_walk |
| LIB-SCAN-PATH-RETRY-001 / STATE_TRANSITION / parse failure → Library §7.2 | 正常提交、坏路径FAILED/恢复；X每路径parser/hash计数 | T好数据/签名原子；F不清好元数据；R仅坏路径 | sync/scanner → test_corrupt_path_retry_does_not_repeat_good_media |
| LIB-MPD-SYNC-001 / STATE_TRANSITION / confirm → Library §7.2 | 一致0update，不一致1update再确认；X精确URI+not updating | T所有MPD锁外；F已提交不rollback；R确认失败不重复accepted update | sync/PlayerPort → test_unchanged_consistent_startup_does_not_update、test_inconsistent_startup_updates_once_then_confirms |
| WEB-INITIAL-READ-001 / STATE_PROPAGATION / timeout → Architecture §4.1 | 错误/结束loading/重试，只读；X新完整首帧恢复 | T无业务事务；Fstale保留；Rgeneration拒迟到、清timer | api/realtime/session → startup-readiness.test.ts全部节点 |
| CI-SHA-DELIVERY-001 / LIFECYCLE / build → Architecture部署合同 | fix分支新SHA镜像；Xrun SHA/jobs/digest/platforms | T远程授权后；F不得复用旧artifact报成功；R同新SHA rerun | container.yml → 静态filter检查及授权后实际CI |

## C0 — 永久RED证据，生产文件零修改

**Files:** 新增server/tests/invariants/test_startup_library_reconciliation.py、server/tests/api/test_startup_readiness.py、server/tests/services/test_library_scan_prepare.py、server/tests/repositories/test_library_scan_commit.py、web/tests/invariants/startup-readiness.test.ts；复用现有media_fixture_dir与support/transport。

**Interfaces:** 先调用现有runtime/scanner/sync/API/client；尚不存在prepare时在当前_scan_files边界装barrier，后续迁到真实prepare，保留相同公开读取断言。

- [ ] 写`test_persisted_second_start_skips_parse_and_hash`：fixture只复制正常audio/LRC到独立music；首轮入库并关闭，保持同SQLite、重新创建runtime，spy真实parse/hash；第二轮await完成事件，assert parse==hash==0；不以直接scan_full调用替代进程生命周期证明。
- [ ] 写`test_http_ws_and_library_read_during_startup_prepare`：用main.lifespan的新测试app及MockMPD，避免legacy conftest取消后台owner。thread entered/release barrier阻prepare，TestClient/context启动及GET state/songs、WS receive首帧分别1秒内完成，读旧数据；所有finally释放barrier/关闭，不允许测试挂住。
- [ ] 写`test_prepare_releases_database_lock`（async barrier独立Task SELECT 1/list_songs）及参数化`test_slow_media_io_runs_without_transaction`（真实parse和hash各thread barrier），assert独立transaction与event-loop回调在1秒内完成；不能从同transaction继承child context伪造无锁。
- [ ] 写`test_unchanged_consistent_startup_does_not_update`与`test_inconsistent_startup_updates_once_then_confirms`：Fake有调用日志、update后修正URI集；assert0或1update、pre/postcheck顺序、60秒预算不含prepare、未触碰业务域。
- [ ] 写参数化`test_reconcile_only_related_paths`（add/modify/delete/move/lrc_add/lrc_modify/lrc_delete）：parser/hash每路径计数、delete零parse/hash、move保Song ID、LRC只关联解析且hash0、其它正常路径均0，停机后重启也覆盖。
- [ ] 写`test_mount_replacement_never_commits_mass_missing`：inventory开始后/commit预检前替换自有root，assertSong/refs/revision不mass missing；已有mount保护保baseline GREEN，新增预检交界测试先失败于现实现缺口。
- [ ] 写`test_corrupt_path_retry_does_not_repeat_good_media`：a正常/b坏，b连续失败后恢复；asserta parse/hash各1，重试仅b，已知坏文件好metadata保留，新坏不造Song，未解决不SYNCED。
- [ ] 写constructor禁止Path.resolve/stat/iterdir/open的`test_constructor_has_no_filesystem_io`；inventory计数与FakeClock的`test_startup_inventory_seed_does_not_immediately_walk`，启动仅一次walk、seed后一个间隔前无walk，失败startup无竞争detector。
- [ ] Web写`initial_snapshot_timeout_reports_and_reconnects`、`get_timeout_ends_loading_and_retries`、`body_timeout_and_late_response_cannot_restore_baseline`：fake timers，永久pending transport/body，明确错误、socket关闭、loading false、重读恢复只读、只有新首帧可写。
- [ ] 加`test_observed_unchanged_uri_is_not_missing`：真实Repository observed未解析URI不missing，no-op revision0。
- [ ] 逐节点运行，记录actual失败断言/traceback。导入缺失不是充分行为RED；root原保护GREEN单列。按用户十项逐行对照，无缺陷RED证据时禁止开始C1。
- [ ] 跑本轮74项backend/28项Web baseline集合，再完整两端回归；新增corrective失败按RED账本列出，环境/fixture失败先修测试装配，无xfail/skip/删断言。C0完成表示RED建立，不表示实现通过。

## C1 — observed表示与持久sidecar基线

**Files:** models/library.py、新models/library_scan.py、repositories/migrations.py、library_repository.py；test_library_scan_commit.py、现有repositories/test_library_reconciliation.py。

**Consumes/Produces:** ScanBatch observed/sidecar delta，ScanBaseline与read_scan_baseline；辅助表v5，旧apply_scan_batch签名保持。

- [ ] 增RED `test_v4_migration_preserves_library_and_references`、`test_sidecar_absence_is_distinct_from_unknown`、`test_signature_delta_rolls_back_with_song_batch`；assert所有旧行/refs不丢，两NULL与缺行不同，rollback无签名提前可见。
- [ ] 运行上述节点确认RED；实现schema migration、baseline读和observed union，observed未变化不upsert业务字段，成功签名与Song同事务提交。
- [ ] GREEN上述节点及observed证明；运行现有repository文件与realtime_library、realtime_commit_visibility、transaction_relationships关系集。
- [ ] 跑完整回归并记录尚未处理C0 RED；审实际diff、targeted Ruff，不commit。

## C2 — 线程prepare与短commit、路径差异/安全

**Files:** 新services/library_scan_prepare.py，services/library_scanner.py、library_sync_service.py中_scan边界；C0新测试，现有services/test_library_scanner.py仅冲突断言定向更新。

**Consumes/Produces:** C1 baseline/observed/sidecar，prepare_scan/Scanner.prepare/commit/LibraryScanConflict；commit同步stage_sync与result交接，不在线程触Repository。

- [ ] 补RED `test_old_missing_signatures_are_backfilled_once`、`test_deep_reconciliation_detects_same_stat_content_change`、`test_media_changed_during_prepare_is_retried`、`test_stale_baseline_cannot_overwrite_new_commit`、`test_prepare_cancellation_never_commits`；明确每path调用数/rollback/revision。
- [ ] 锁外线程prepare：一次完整inventory+差异、only changed parse/hash、LRC-only复用hash、旧签名一次补齐、失败路径保留好prepared结果、既有唯一移动匹配/album artwork依赖限相关路径。
- [ ] commit前线程检查root/文件稳定，事务内baseline检查/SQL/apply/revision/SYNCING，禁止FS/MPD/WS；移除sync._scan的outer包住scan模式。旧包装器outer transaction使用明确拒绝，调用者需先prepare再commit。检查并定向改造test_realtime_library等当前outer扫描调用：媒体变化的各版本先在锁外prepare/线程预检，事务中只commit；新增同outer两批次共享原始baseline的证明，保持双变更/no-op最终比较、rollback/cancel、commit→update→completion断言，不删除这些测试。
- [ ] 建立`test_commit_data_revision_and_sync_are_atomic`：rollback不改数据/签名/revision/同步成功，commit新数据不能配旧revision，发送失败不撤提交；原事件在必要update后完成。
- [ ] 按新合同替换仅两个MediaMetadataError整批失败断言，保留good metadata、歌词/封面/引用保护。PermissionError现测试需保证音频stat变更或明确deep/路径强制准备，以免“未变化跳过”令故障注入失效。
- [ ] 精确GREEN C2全部、C0项3/6/7/8的prepare断言；运行scanner/repository/LRC/artwork及transaction/realtime_library关系回归。
- [ ] 跑完整两端回归、Ruff和diff检查，剩余C3/C4 RED逐项记录，不把完整suite未绿记PASSED。

## C3 — HTTP就绪、inventory交接与条件MPD确认

**Files:** services/library_sync_service.py、library_change_detector.py、library_runtime.py、main.py、config.py、player/music_uri.py；C0 lifecycle/API/invariants测试，既有sync/detector测试。

**Consumes/Produces:** C2 PreparedScan，纯内存seed；单owner失败路径/目标集合，按需update状态机。

- [ ] 补RED `test_accepted_update_is_not_repeated_on_confirmation_retry`、`test_next_generation_keeps_failed_paths_and_move_absence`、`test_startup_failure_keeps_http_ready_and_old_library_readable`、`test_config_and_mapper_construction_do_not_touch_music_root`、`test_shutdown_during_prepare_has_no_late_update`，assertcall log/旧facts/单owner与取消后0副作用。
- [ ] constructor去resolve/stat/read；AppConfig音乐根readability移到prepare，mapper构造延迟canonical resolve但保留真实使用时symlink拒绝；定向替换test_config.py的missing-root配置失败断言为config接受而后台FAILED/HTTP可读，保留其它非法config测试。后台startup prepare捕获identity且HTTP先放行，seed完整inventory后detector先等待间隔；startup失败有界retry不竞争walk；scheduler/manual同owner。
- [ ] 仅失败路径retry，保留未确认旧move/delete目标；先无变化精确确认，再必要update一次→not updating+精确目标确认。明确网络unknown/timeout只退避重读，update明确失败才重试。
- [ ] C0项1/2/4/5/8/9及C3新节点精确GREEN；跑test_config、config_composition、player/test_music_uri及sync服务/detector、invariants/library_sync/library_sync_wire、api/library_sync_wire，URI映射、健康、realtime快照/交接/提交及Queue/History关系回归。
- [ ] 完整两端回归fresh记录；C4前端RED仍列未解决，不关corrective自动Gate。

## C4 — Web有界读取与明确恢复

**Files:** web/src/services/api.ts、realtime.ts、runtime/playerSession.ts；startup-readiness.test.ts，必要现有realtime/resource-cache/global-notices测试。

**Consumes/Produces:** 可注入10,000ms GET/initial预算、typed READ_TIMEOUT/INITIAL_SNAPSHOT_TIMEOUT；既有reconnect/read retry、store/cache generation不变。

- [ ] 精确运行C0前端三个节点见RED；补`success_stop_and_reconnect_clear_timeout_timers`、`get_after_timeout_does_not_enable_mutations`及永不settle abort mock/body测试。
- [ ] initial计时覆盖socket创建到首帧，超时dispose旧socket并重连；GET计时覆盖fetch/body，abort与Promise deadline同时保证settle，在finally清timer。
- [ ] 接入既有唯一AppBar明确文案/重读，无页面第二loading authority；资源loading结束，迟到拒绝，mutation unknown/key逻辑不改。
- [ ] 精确GREEN；跑realtime/resource-cache/wire/mutation/global-notices/library-sync/shell-navigation及task9-relationships关系集；typecheck/build。
- [ ] 跑完整后端/Web及Ruff；所有corrective十项/关系/full必须GREEN后才能进入C5自动验收。

## C5 — CI与最终证据（远程交付单独门槛）

**Files:** .github/workflows/container.yml；新archive/task-9/2026-10-12-task-9-startup-reconciliation-acceptance.md；docs/superpowers/README.md仅当前入口/状态。

- [ ] 静态证明push过滤缺fix/**，只加入fix/**到既有过滤，不调Docker/start_period/SCAN_INTERVAL_SECONDS或依赖；保留workflow_dispatch/PR validate和原双架构SHA标签。
- [ ] 全部永久RED→GREEN的exact节点重跑；运行下列关系集、完整两端、typecheck/build/Ruff，再diff --check/stat/status及实际diff审阅。
- [ ] 写fresh acceptance：每Batch exact/relationship/full命令、SHA、测试计数/时长/环境、RED失败原因、合同traceability；未运行项明确NOT RUN，不引用旧绿色替本轮结果。
- [ ] 用户显式授权commit/push后才触发远端CI；verify提交与远端HEAD、run.head_sha==修复新SHA、validate/image都success、image sha标签/digest/两platforms。没有授权则报告本地自动通过/CI未触发，不能记container delivery完成。
- [ ] 真实设备/手机Gate NOT RUN；本轮不请求连接设施、不关闭Task9历史Gate、不合并main。

## 可复用fresh验证命令与结果纪律

从repo root运行。每次backend前用mktemp建立新的根并export APP_ENV=development、MPD_MODE=mock、DATABASE_PATH=<自有根>/state.db、CONFIG_DIR=<自有根>/config、MUSIC_ROOT=<自有根>/music（先mkdir）；禁止指向已有运行DB。不要重新创建/安装.venv。Web命令使用已存在node_modules。

精确节点格式：`.venv/bin/python -m pytest -q <file>::<node>`；Web `npm --prefix web run test -- --run <file> -t '<node>' --maxWorkers=1 --minWorkers=1`。每个Batch先精确GREEN，再直接文件、关系、完整。

后端关系集（C1/C2可按上文子集先运行，每Batch结束仍执行完整本集合）：

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_startup_library_reconciliation.py server/tests/api/test_startup_readiness.py server/tests/services/test_library_scan_prepare.py server/tests/repositories/test_library_scan_commit.py server/tests/services/test_library_scanner.py server/tests/services/test_library_change_detector.py server/tests/services/test_library_sync_service.py server/tests/repositories/test_library_reconciliation.py server/tests/invariants/test_library_sync.py server/tests/invariants/test_library_sync_wire.py server/tests/api/test_library_sync_wire.py server/tests/invariants/test_transaction_relationships.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_realtime_library.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_handoff.py server/tests/player/test_music_uri.py server/tests/test_config.py server/tests/invariants/test_config_composition.py server/tests/invariants/test_uri_mapping.py server/tests/invariants/test_health_relationships.py server/tests/invariants/test_realtime_queue.py server/tests/invariants/test_realtime_history.py server/tests/invariants/test_playlist_relationships.py
```

Web关系集：

```bash
npm --prefix web run test -- --run tests/invariants/startup-readiness.test.ts tests/invariants/realtime.test.ts tests/invariants/resource-cache.test.ts tests/invariants/wire.test.ts tests/invariants/mutation.test.ts tests/invariants/global-notices.test.ts tests/invariants/library-sync.test.ts tests/invariants/shell-navigation.test.ts tests/invariants/task9-relationships.test.ts --maxWorkers=1 --minWorkers=1
```

每Batch完整命令（C0–C3尚未实现的已登记RED允许预期失败，但绝不能标full PASSED、skip/xfail或删测试；全GREEN门槛在C4/C5）：

```bash
.venv/bin/python -m pytest -q server/tests
npm --prefix web run test -- --run --maxWorkers=1 --minWorkers=1
npm --prefix web run typecheck
npm --prefix web run build
.venv/bin/python -m ruff check server/app server/tests
git diff --check
git diff --stat
git status --short
```

每次只修改当Batch范围；有新失败先读完整traceback，区分代码/测试/装配/环境/DB/错误基线，检查spec再最小修复，精确复跑后关系回归。新增产物/DB/dist/log/env不得入Git。计划不包含自动commit步骤。

## 审阅决定

请确认corrective spec及本计划；建议native在当前会话按C0→C5执行，因为组件接口紧密相连且用户要求分Batch fresh证据。选择委派时再按已批准Batch派发，不默认启用并行agents。批准不等于授权push、PR、merge或连接真实设备。
