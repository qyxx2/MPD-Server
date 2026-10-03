# Task 7 Batch 7 — System read API acceptance

## 实际基线与范围

- 用户指定分支 `feature/task-7-output-manager`，真实开始 HEAD `27e3d370477f23eaf54d474486978f54105dace5`；working tree 干净。重新 fetch 和 ls-remote，远端同名 ref 为该 SHA。Task 1R `03f4de9` / Task 4 `86975d6` ancestry exit 0。
- 实际读取 README、主 Plan Task 7/global constraints/两个 gates、active Plan B7/rows/冻结接口/F7/共同验收、B6 acceptance；O §4–8/10、A §2/8.1/12–14/19.5、P §8；检查当前 main/dependencies、OutputManager/MPDInfoService/domain models、capabilities/PlayerPort/Mock、直接测试与历史 architecture/playlist/API tests。
- 本轮完成主 Step 5/6 的 B7 GET 暴露、Step 7 nullable representation、Step 8 本 Batch verification。只开放 GET `/api/system/output` 和 `/api/system/mpd`；没有 PUT、OutputSetRequest 或 B8 mutation/API 幂等集成。
- 原 checkout 与现有 `.venv` 保留（无额外 worktree 隔离）；Python 3.14.4 / pytest 9.1.1 / Ruff 0.16.9。无依赖、Docker、schema 改动或 runtime artifact 提交；新测试数据库均临时文件；未访问真实 MPD/NAS/DAC。

## Contract Impact Analysis / traceability

Owned **SYS-READ-001**。Relied-upon **O-STATE-001、INFO-READ-001、PORT-OUTPUT-001、PORT-INFO-001**。Regression **PL-REP-001、PL-COLLECTION-001**，另 R-ARCH、F1/F2。

Relationship **REQUIRED / GREEN**；Contract Matrix **REQUIRED / GREEN（B7 read scope）**。没有新增或修改业务语义，没有 Contract Gap。

实现前核对 Preconditions / Authorities / Expected State Delta / Must Remain Unchanged / External Confirmation / History-Event / Transaction / Failure-Rollback / Retry / Observable Result / Executable Proof。读取依赖真实存在；没有用历史 checklist 或交接代替本轮证据。

| ID → authoritative Spec | delta / unchanged / failure / confirmation / retry → implementation → fresh executable proof |
|---|---|
| SYS-READ-001 → O §5.2/7/8、A §2/13/14 | GET 只呈现真实 Service 数据，output 只刷新观察缓存；无 player/SQLite/history/event 写入，无 terminal/key 要求。unavailable/stale 可表示；内部错误使用既有统一外壳；每次 GET 重读。`system.py` / `system_schemas.py` / `dependencies.py` / `main.py` → API 5 cases + F7 14 cases；focused/regression **53 passed**。 |
| O-STATE-001 → O §5.2/6.1 | 实际 ACTIVE/INACTIVE/UNAVAILABLE 与 last_request 分开；stale、错误、时间和完整空串流字段保持。读取失败保留已确认事实并标 stale；ID 变化后重新读，PREPARING 只为请求事实。原 OutputManager → F7 output 六个真实协作 cases + API schema/PREPARING；F1 regression GREEN。 |
| INFO-READ-001 → O §7.1–7.3、A §14 | 历史 verified version 有来源；stats/update/status 独立读取，真实 0 保留、失败 null、不丢其它成功字段；connected true/false/null 区分；不执行 update_database/probe。原 MPDInfoService → F7 六种 live/partial/offline/unverified cases；F2 GREEN。 |
| PORT-OUTPUT-001 / PORT-INFO-001 → O §4/7/10、主 Plan 1R | 沿用已有 capability/nullable/typed-failure 合同；无 transport 修改。main 共享同一个 player/runner；能力缺失 fail closed，不把文档探针样本作 runtime 数据。F7 composition 两个 online/offline cases、启动未验证 case、F1/F2；全 invariants **256 passed**。 |
| PL-REP-001 / PL-COLLECTION-001 → Task 5 matrix §3.6 | 仅 main/dependencies wiring 影响，Playlist 所有表示与持久成员/Collection split 不变。R-PL `test_playlist_relationships.py` + 既有 `test_api_contracts.py` GREEN，属于 **53 passed** focused gate；R-ARCH 同次 GREEN。 |

F7 跨真实 Services→REST/DI 与 SQLite/playback authorities，断言 runtime Queue/Context/History/session 不变、MPD 调用只有 reads、SQLite dump 不变、无 publisher 事件、真实 schema GET-only；没有把普通 full-suite 代替 required gate。输出数字 ID、attributes 或 MPD password 不在 REST schema 内。

## RED → GREEN / fresh commands

1. Output GET RED：**1 failed**（404，无路由）→最小 output schema/dependency/router registration→**1 passed**；F7 output **6 passed**。
2. MPD GET RED：**1 failed**（404，无路由）→最小 info schemas/dependency/GET→focused **8 passed**（含上述 output proofs）。
3. Startup DI RED：**1 failed**（lifespan 未创建 output_manager）→shared player/runner、injected capabilities/selector/publisher、empty-capability default→exact **1 passed**。
4. 补充 F7 live/null/partial source、composition/SQLite/GET-only、PREPARING 与内部错误外壳 proof。未把既有行为的首次 GREEN 伪称新增 production RED cycle。

测试搭建错误单独修正：首次 F7 的 monkeypatch 默认要求尚未接线的 state attribute 存在，改为允许显式注入；没有修改 production 掩盖问题。路由审查测试假设 `app.routes` 都有 path，当前 FastAPI `_IncludedRouter` 不满足；重跑读取完整 traceback，改用公开 OpenAPI 验证完全相同 GET-only 合同，exact 两个 cases **2 passed**。两项 Ruff PLR0402 仅修改新测试导入。

所有命令从 root 使用既有 `.venv/bin/python`：

```bash
.venv/bin/python -m pytest -q server/tests/services/test_output_manager.py server/tests/invariants/test_output_observation.py server/tests/services/test_mpd_info_service.py server/tests/invariants/test_mpd_info_relationships.py server/tests/invariants/test_output_disable.py
# 前置核验：92 passed
.venv/bin/python -m pytest -q server/tests/api/test_system_reads.py server/tests/invariants/test_system_read_relationships.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_mpd_info_relationships.py server/tests/invariants/test_architecture_relationships.py server/tests/invariants/test_playlist_relationships.py server/tests/test_health.py server/tests/api/test_api_contracts.py
# 53 passed
.venv/bin/python -m pytest -q server/tests/api/test_system_reads.py server/tests/invariants/test_system_read_relationships.py
# 19 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_system_read_relationships.py
# 14 passed（独立 F7 gate）
.venv/bin/python -m pytest -q server/tests/invariants
# 256 passed
.venv/bin/python -m pytest -q server/tests
# 698 passed
.venv/bin/python -m compileall -q server
# exit 0
.venv/bin/python -m ruff check server/app/api/system.py server/app/api/system_schemas.py server/app/api/dependencies.py server/app/main.py server/tests/api/test_system_reads.py server/tests/invariants/test_system_read_relationships.py
# All checks passed
```

无 skip/xfail；各 pytest run 只有既有 StarletteDeprecationWarning，未通过更改依赖处理。每个行为单元 focused/invariant GREEN 后检查 `git diff --check` / `git status --short`。

## Changed files / isolation / remaining gates

Production 四文件：新 `server/app/api/system.py`、`system_schemas.py`；修改 `dependencies.py`、`main.py`，共 130 新增行。Tests 两文件：新 `server/tests/api/test_system_reads.py`、`server/tests/invariants/test_system_read_relationships.py`。Docs：active Plan 的当前事实/存在性和本 acceptance archive。

完整 changed-files review：没有无关格式化/refactor、依赖/runtime/generated 文件、合同改写、并列权威文档、Task 6/10 imports 或未来 B8 功能。main 不改变其它服务构造/lifespan 逻辑；未配置能力默认 unavailable，最终 config loading 属 Task 10。

B7 本地 acceptance 满足后具备进入 B8 独立 pre-flight 的条件；O-TX-001/O-EVENT-001 最终 REST proof 和 SYS-WRITE-001 仍 pending B8，Task 7 final gate 仍 B9。本轮不声明物理 DAC/部署验收。

Active B7 未明确要求 push；本轮 acceptance/review 通过后只本地 commit，最终报告给出实际 local SHA/branch/changed files/clean tree 和 remote ref 二次核对，不 push/PR/merge。

## 独立审查与 disposition

独立只读 reviewer 审查实际 working diff（含 untracked files），重跑上述 **53 tests passed**，`git diff --check` 通过；无 Critical/Important、无 production 修改要求，B7 acceptance supported。

Deferred Minor：active Plan §5 把 `OutputSetRequest(mode, enabled)` 排期在 B7，但 B7 明确只 GET 且请求 schema 不参与 SYS-READ-001；留给 B8 pre-flight 处理排期一致性，本轮没有修改该冻结接口语义或添加未来 mutation schema。该文档排期差异不是业务 Contract Gap，不阻塞 B7。

审查者未判断的范围已逐项处理：
- B8 PUT/terminal/response-commit-cancel integration：保留 B8 owner；B7 GREEN 不证明这些关系。
- B1/B5/B6 selection/switch/failure/preservation 算法：当前没有实现改动，不重开；F1 和本轮前置/F7 regression 提供读取相关 evidence，不能替代未来 REST mutation proof。
- production capability loader/config：保留 Task 10；默认未验证时不可用，当前只证明显式注入/fail closed。
- WebSocket/reconnect：保留 Task 6；本轮不证明事件投递。
- live MPD/physical DAC/NAS/Docker/deployment：本轮没有授权要求且没有执行，local fixtures 不证明真实设备。
- 历史 RED/remote refs/全量测试 provenance：由主执行者本轮实际工具输出证明；reviewer 仅独立确认 53 focused tests，不伪称重复跑 256/698。
- commit/push/PR/merge/完整 Task 7 acceptance：commit 与 ref 由主执行者提交后二次核对；未授权 push/PR/merge，B8/B9 和 Task 7 complete 保持未完成。

上述边界处置的代价均为 B7 acceptance 不覆盖被保留的后续/外部范围。除该排期 Minor 外无 deferred finding。验收文档最后的事实更新由主执行者审查。
