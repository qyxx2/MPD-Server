# Task 6 Batch 10 acceptance — 只读 snapshot API

日期：2026-10-04（Asia/Shanghai）。本文件仅保存执行证据，不新增 Contract authority。

## 基线与前置核验

真实起始分支 `feature/task-6-realtime-state`，HEAD `8c6809f1b968f68b3ed9f010971e2f5caa13b677`，working tree 干净。实际核对 status/branch/HEAD/log、HEAD changed files、当前代码/测试，未根据旧摘要、Plan勾选或历史验收推定完成。

读取 README、主 Implementation Plan 的全局约束/Task6/Dependency/Relationship/Contract Gate、active Task6 plan Matrix/§5/Batch10/B11–13边界、A §12.1–12.3/§19.5、P §2.2.1/§8.8、L §7.1、B9 acceptance；检查 StateService、domain DTO、dependencies、main、API schemas、真实 fixtures 与 B7/B8/B9 proofs。前置四文件 snapshot/observation/lifecycle/output fresh **49 passed，2.48s**。

适用 skills：using-superpowers、executing-plans、using-git-worktrees（遵循用户指定checkout/branch，原地实施）、test-driven-development、systematic-debugging、verification-before-completion、requesting-code-review。执行已冻结 Batch，不重新设计 Task，不实施后续 Batch。使用既有 `.venv`：Python3.14.4/pytest9.1.1/Ruff0.16.9；读取 server/requirements.txt，无环境/依赖修改。

## Contract Matrix Impact Analysis 与 traceability

- Owned：**RT-SNAPSHOT-001 HTTP部分**；整体 row final owner 仍 B13。
- Relied-upon unchanged：**RT-HISTORY-001、RT-OBSERVE-001、RT-REVISION-001**。
- Regression：**API architecture**；按 B10 指令执行 **R-ARCH / R-H**。
- Relationship Gate：**REQUIRED / PASS（B10 scope）**。
- Contract Matrix Gate：**REQUIRED / PASS（B10 scope）**。
- 新增/修改 frozen rows：0；Contract Gap：0。

| ID → Spec | 本批 implementation / Expected Delta | Must Remain Unchanged / Confirmation / Failure-Retry | Executable proof → fresh GREEN |
|---|---|---|---|
| RT-SNAPSHOT-001 HTTP → A §12.1–12.3 | get_state_service → StateService.get_full_snapshot → 独立 FullStateSnapshotResponse → GET /api/state；完整public DTO、本地联合切面/marker、缓存外部观察 | 不改 Queue occurrence/order/CAS、Playback/context/AutoPlay、Library/Playlist/Favorites、History persisted/active/session、既有terminal或MPD控制；API消费 Service已确认cache，不自行读Port；本地失败整体503/STATE_SNAPSHOT_UNAVAILABLE，外部unknown/stale/error仍完整200，重试重读、无terminal或mutation replay | API文件15 tests + B7 snapshot16 tests + B8 observation18 tests + B7 History1 test，共50 GREEN；其中真实SQLite/Services/MockPort联合保留、逐本地域失败、root实际producer版本和既有barrier proof共同满足关系Gate |
| RT-HISTORY-001 → P §2.2.1 | 传递 has_entries/active_event/session_id；不把active当永久事件，不过滤unavailable | 原History REST及事件身份/reason不改；继承同切面、本地读取失败整体503，读取/重试不造事件 | API AVAILABLE/MISSING/UNREADABLE保留proof、B7 history proof → 50 GREEN；R-H →18 GREEN集合 |
| RT-OBSERVE-001 → A §12.3/P §8.8 | cache字段、null/unknown、fresh/stale/error、时间与sequence按既有 Service语义传递 | 不调用observe/get_state/reconcile或Port网络来完成GET；不将DB位置当实时位置；断线有/无样本分别stale/unknown；过期先登记水位，重复GET无重复内容变化；控制回执保留 | API降级/expiry/no-I/O/full DTO proof + B8 proof →50 GREEN；B9前置49 GREEN，不重开领域恢复 |
| RT-REVISION-001 → L §7.1/A §12.1–12.2 | 原epoch/sequence/revisions/Queue CAS完整表示；真实root scanner/playlist提交后library=playlist=1 | 不新增计数策略，不改Queue CAS，不产生业务版本增量；联合capture marker由StateService负责；失败重读无mutation | root版本API proof + B7切面/barrier proof + B8 observation版本保留 →50 GREEN |
| API architecture → A §5、M Dependency/Relationship Gate | API仅依赖Service及API DTO；main仅增加router注册 | 无API→Repository/SQLite/MPDAdapter，无新WS/后续模块；旧REST schema不改 | R-ARCH及旧schema/新OpenAPI一致性proof →18/50 GREEN |

## 实际 Step / RED→GREEN

1. Git/文档/环境/真实前置与Contract pre-flight完成。
2. 指定 `test_state_api_fails_whole_local_snapshot_but_keeps_external_degradation`：**1 RED**，目标路由不存在，404而非503；白名单四生产文件最小实现后 **1 GREEN**。随后加强有/无成功样本参数，最终两个case均GREEN。
3. 真实Service/SQLite endpoint tests覆盖六类本地读取失败、恢复重试、no terminal；完整DTO/current/context/全部重复occurrences/Played/current/pending/AutoPlay；持久History及unavailable Song；Output确认回执/实时位置与DB位置分离；禁止外部I/O/control/recovery；empty/root wiring/cache expiry/版本/旧REST。首次GREEN的增强regression不冒充RED。
4. 追加测试曾出现错误假设，systematic-debugging检查真实schema/服务实现：Song域对象包含内部identity_key，public Library SongResponse刻意不含；既有AutoPlay在next后补充occurrence。按原合同验证public Song及全部真实occurrences，保留MANUAL三项和额外AUTOPLAY的明确断言；不改生产领域或旧测试。Mock存储名称按真实_queue核对。此类test/setup failures不作为目标RED记录。
5. `test_snapshot_openapi_describes_its_actual_output_field_names`：**1 RED**，复用旧Output API schema会声明camelCase但新snapshot返回snake_case；仅新增snapshot Output DTO，**1 GREEN**，旧system schema保持camelCase。无Contract语义改动。
6. selector→完整API文件→B7/B8/History proofs→R-ARCH/R-H按顺序取得GREEN；各实现阶段执行diff --check/status。scoped Ruff/compile通过。
7. 使用fresh-context只读reviewer审阅五个代码/测试文件：**无Critical/Important/Minor findings**；reviewer最终API文件15 passed，独立验证B7/B8/R-ARCH/R-H及scoped Ruff/diff。reviewer未编辑或提交。
8. 最终changed-files/完整内容/traceability/future-scope审查完成。

## Fresh final commands

```bash
.venv/bin/python -m pytest -q server/tests/api/test_realtime_state.py
# 15 passed，2.50s

.venv/bin/python -m pytest -q server/tests/api/test_realtime_state.py server/tests/invariants/test_realtime_snapshot.py server/tests/invariants/test_realtime_observation.py server/tests/invariants/test_realtime_history.py
# 50 passed，4.41s

.venv/bin/python -m pytest -q server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories server/tests/services/test_history_service.py server/tests/api/test_history_api.py server/tests/repositories/test_task2_steps_5_7.py
# 18 passed，0.62s

.venv/bin/python -m ruff check server/app/api/realtime.py server/app/api/realtime_schemas.py server/app/api/dependencies.py server/app/main.py server/tests/api/test_realtime_state.py
# All checks passed
.venv/bin/python -m compileall -q server
# exit0
git diff --check
# exit0
```

扩展回归实际命令 `.venv/bin/python -m pytest -q server/tests/api server/tests/invariants`：最终 **677 passed，44.05s**。每次pytest仅1条既有Starlette TestClient/httpx deprecation warning；无环境失败。B10没有要求全部server/tests，本次未执行全server suite；B13的full-suite与D6最终门禁不由本批替代。未进行live MPD/NAS/DAC、Docker、frontend或reverse-proxy验收。

## 修改范围 / 验收 / Git权限

实际文件：

- `server/app/api/realtime.py`（新增）
- `server/app/api/realtime_schemas.py`（新增）
- `server/app/api/dependencies.py`
- `server/app/main.py`
- `server/tests/api/test_realtime_state.py`（新增）
- 本archive acceptance（新增执行证据）

四生产文件新增135行，在B10约80–160LOC范围。tracked diff及全部新文件内容已检查，无无关格式化/重构、future Batch/Task功能、schema migration/dependency/environment/DB/cache artifacts、旧合同变更或平行权威文档。忽略目录内执行ledger不提交。

B10 implementation、自动化测试、本地环境验证及本批acceptance满足，当前Batch blocker/Contract Gap均无；RT-SNAPSHOT整体仍PARTIAL到B13。B11技术前置具备，本次未实施B11。D6-RECOVERY仍约束自动恢复启用及最终Task6验收，本批不作完成声明。

active plan §5规定“提交须用户另行授权”，本轮没有另行commit/push授权，因此无新commit/push/PR/merge。只读真实二次核对：本地branch HEAD及远端`refs/heads/feature/task-6-realtime-state`均为`8c6809f1b968f68b3ed9f010971e2f5caa13b677`。此SHA是起始基线，不是B10提交。工作区保留上述六个必要文件的未提交变更。

后续用户明确授权“提交push”。提交前重新核对当前branch/HEAD/history/working tree及六个必要文件，无新增生产修改；重新运行API/B7 snapshot/B8 observation/B7 History四文件：50 passed；相同scoped Ruff：All checks passed。按授权提交并推送当前feature branch，提交后通过git status/log/show及远端ref再次确认，具体SHA由提交后的报告给出。
