# v0.1 NAS B06：健康与日志验收

2026-10-12，范围仅[Final Plan B06](../plans/2026-10-11-v0-1-nas-final-batch-plan.md)。状态：**IMPLEMENTED / AUTOMATED PASSED / Gate CLOSED**。本批无人工Gate；B03 NAS及时性、B08真实联合验收仍待确认，B07–B09未推进。

## 合同与实现

- `FINAL-HEALTH-001 → Architecture §22.3 MIN-HEALTH-001`：composition root注入HealthService，API只调用Service；Repository用SQLite `mode=ro`读取songs表，不创建缺失DB、不迁移、不写入。Service独立读取MS、Port.status与协调器已提交library_sync。MS正常HTTP200/status=ok，即使MPD unavailable；本地必需读取失败503/error，仍保留其它可读事实。MPD预算默认1秒可注入，超时unavailable；未验证/被拒绝读取unknown，不用saved地址证明连接。同步字段复用Library §7.2原DTO，不新增同步owner。
- `FINAL-LOG-001 → Architecture §22.3 MIN-LOG-001`：幂等console JSON配置；启动、API失败、MPD连接/控制ACK、扫描、同步进度/失败/重试/取消按operation_id或generation关联。请求关联只取key的短SHA256摘要，ACK日志明确为accepted，不证明业务confirmed。重复状态/轮询无新增phase日志，独立控制失败不被去重。旧事务/播放/输出/实时错误保留来源、固定安全描述、异常类型和栈位置，不插入参数、异常原文、源码行或locals；阻止向父logger再次转发原文。日志写入失败隔离。生产Compose原json-file 10m×3配置仅静态核查，未改部署文件或运行Docker。
- Web沿用B04 diagnostics，只在浏览器console记录本地状态变化，未改Web产品、未声称浏览器独有错误进入后端。

## Fresh验证

原`.venv`：Python3.14.4、pytest9.1.1、Ruff0.16.9；已核对requirements，未安装/修改依赖。所有命令从repo root运行，自有`/tmp/mpd-b06-jni0_5gr`配置/默认DB/音乐根及pytest tmp_path合成媒体、MockPort/Fake传输；不访问真实音乐、live MPD或外部服务。pytest统一附`-o cache_dir=/tmp/mpd-b06-jni0_5gr/cache`。

1. 指定`test_health_relationships.py::test_mpd_failure_is_independent_and_health_has_no_control_side_effects`和`test_logging.py::test_activity_phase_and_errors_are_correlated_without_secrets`先因缺ms/日志模块RED，再GREEN。补充预算/unknown、API关联与日志失败、MPD协议日志、父logger泄漏、取消terminal及独立失败去重节点均先确认RED再最小实现/修复。
2. `.venv/bin/python -m pytest -q server/tests/test_health.py server/tests/test_logging.py server/tests/invariants/test_health_relationships.py` → **9 passed**。真实临时SQLite读取不改hash，Port只status；SQLite缺表503仍保留同步状态，缺失DB不被创建；同步超时/失败/重试和取消可定位，无秘密/完整key/body。
3. `.venv/bin/python -m pytest -q server/tests/api/test_system_reads.py server/tests/invariants/test_system_read_relationships.py server/tests/invariants/test_architecture_relationships.py` → **21 passed**。
4. 必要历史关系 `.venv/bin/python -m pytest -q` 下列文件 → **88 passed**：
   - `server/tests/services/test_library_sync_service.py`
   - `server/tests/invariants/test_library_sync.py`
   - `server/tests/api/test_library_sync_wire.py`
   - `server/tests/invariants/test_library_sync_wire.py`
   - `server/tests/invariants/test_config_composition.py`
   - `server/tests/player/test_mpd_adapter_errors.py`
   - `server/tests/player/test_mpd_adapter_tcp.py`
   - `server/tests/invariants/test_uri_mapping.py`
   - `server/tests/repositories/test_transaction_commit_hooks.py`
   - `server/tests/invariants/test_realtime_commit_visibility.py`
   - `server/tests/api/test_idempotency.py`
   - `server/tests/invariants/test_output_event_transactions.py`
   - `server/tests/invariants/test_realtime_delivery.py`
   - `server/tests/api/test_task9_wire_fixture.py`
   - `server/tests/api/test_web_wire_fixture.py`
5. `npm --prefix web run test -- --run tests/invariants/appbar-activities.test.ts -t 'diagnostics_record_changes_once_without_secrets_paths_bodies_or_keys|diagnostics_failure_does_not_change_business_or_hide_activity|player_unknown_diagnostics_do_not_report_transient_failure_or_poll_noise' --maxWorkers=1 --minWorkers=1` → **3 passed**；去掉`-t`完整文件 → **8 passed**。
6. `.venv/bin/python -m ruff check`本批7个生产/8个测试文件、`git diff --check`通过。实际diff及初始hash/权限清单比对仅本批允许范围，无删除或权限变化，原dirty成果及已有DB/connection/runtime保留。审阅为本会话自审，未委派。

## 失败归因与范围

- 旧健康测试未运行lifespan，改为自有临时DB＋显式Mock；system装配测试不再依赖B01前的默认Adapter假设，保留共享Port、无探针、完整schema和只读断言。
- conftest原先await关闭library任务后才取消observer，observer会抢跑采样。先同时cancel，再await关闭；两份后端golden builder显式采样原baseline，保留原Web JSON和逐字段断言，没有改生产sequence或压低断言。
- 测试代码两次错误假设（不存在的Mock计数字段、FakeReader把多行作为一行）修正夹具；日志测试隔离既有handler，未改幂等配置去适配测试。临时命令的空MPD_CAPABILITIES_PATH被当作目录、全局saved路径覆盖配置测试的自有默认路径，修正命令为unset capabilities及该关系集合`env -u MPD_CONNECTION_PATH`，默认路径仍由自有临时DATABASE_PATH派生；环境/依赖未更改。
- 自审补精确RED→GREEN修复：SQLite失败误清空仍可读同步事实、父logger输出旧异常原文、取消时漏terminal日志、独立控制失败被轮询去重。无剩余本批测试失败；仅既有Starlette/httpx弃用warning。Ruff仅修本批import排序及明确诊断失败隔离注释/测试with格式。
- 本轮增量：7个生产文件、8个测试文件、Plan状态和本文；Repository只读helper为Service分层必需，同步/Adapter只接日志；未新增监控、备份、管理页或远程采集。未commit/push/PR/merge。

**NOT RUN**：全量server/Web suite、广域Ruff、typecheck/build、真实浏览器/手机、NAS/Docker、真实声音。B06自动Gate不证明部署轮转实际执行或实机健康；这些留给B07/B08。现有运行服务未重启，因此当前运行进程不会自动获得本批接线。
