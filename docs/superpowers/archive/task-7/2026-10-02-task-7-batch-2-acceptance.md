# Task 7 Batch 2 — MPD About Service acceptance

## 实际基线与范围

- 2026-10-02，指定分支 `feature/task-7-output-manager`。
- 开始时 HEAD `8afd51323773e30e95db6d7ecdd6b4d6a723b346`，工作区干净；重新 fetch 后远端同名 branch 也是该 SHA。Task 1R `03f4de9`、Task 4 corrective `86975d6` 可达。
- 使用现有 `.venv`：Python 3.14.4、pytest 9.1.1、ruff 0.16.9；没有修改依赖或环境，没有访问真实 NAS/MPD。
- 仅执行 active plan B2：主 Plan Step 6 的 About Service 和 Step 7 的未知字段测试。未实现 API、输出控制、probe、Task 6 或后续 Batch；Task 7 整体未完成。

## Contract Matrix Impact Analysis / traceability

- Owned：INFO-READ-001；Relied-upon unchanged：PORT-INFO-001。
- 新增实现对应已冻结 row；不新增或修改合同语义，不修改历史 row 实现。Regression Contract IDs：无旧业务 row；直接端口 regression 为 R-PORT step5/6/7。
- Relationship Gate：REQUIRED；Contract Matrix Gate：REQUIRED，均通过显式 F2 和以下字段审查。

| ID / 权威 | Expected State Delta / Must Remain Unchanged | External Confirmation / Failure-Rollback / Retry | Implementation / executable proof |
|---|---|---|---|
| INFO-READ-001；输出 Spec §7.1–7.3，架构 Spec §14，active plan §4.2/§5/B2 | 只更新读取结果；输出、播放状态/位置、Queue occurrence/order、repeat/random/volume、DB 更新任务不变；不依赖 Repository、不产生 History/event | version 来自注入 capability 并标 source；stats 七字段、update-status、最终 status 独立实时读取；成功 0 保留、失败/未知 null；按来源区分 capability/command/unavailable；每次重新读，不缓存 probe stats；不承诺多命令原子快照 | models/mpd_info.py、services/mpd_info_service.py；F2 `test_info_preserves_runtime_sources_nulls_and_real_zero` 六场景及 service tests；显式 fresh 6 passed，focused 20 passed |
| PORT-INFO-001；输出 Spec §7/§10、主 Plan Task 1R、active plan §4.3 | 消费现有 nullable port/capability 合同，不改 transport 或能力验证政策；读取不触发 update_database | VerifiedPlayerPort gate；typed errors 保留分类；只读无 rollback 副作用，允许重新读取 | 既有 capabilities/ports/Mock/Adapter；R-PORT step5/6/7 fresh 4 passed（另加 architecture 2 passed 的组合命令共 6 passed） |

F2 使用真实 Service + VerifiedPlayerPort + MockMPD；暂停、相同 URI 两个 Queue occurrence、seek、repeat/random/volume、ALSA 输出均先建立事实。读取成功/部分拒绝/断线/缺能力后比较完整端口事实，断言只有读取调用；失败后重新读取成功且旧返回对象保持独立。DB/History/event 不变由只读调用范围和零 Repository/Publisher 依赖共同保护；未把物理 DAC 或 REST 声明为已验收。

## RED → GREEN

1. stats/version 来源：首次单测试 1 failed，明确断言 About Service 尚不存在（无 collection/import 环境错误）；最小模型及实时统计实现后 1 passed。
2. stats 失败分类：command/disconnected/unverified 三场景 3 failed，typed exception 未被转成部分结果；最小 capability gate/错误表示后 service 文件 4 passed。
3. update-status：4 failed、1 passed（全未知场景已有正确默认），失败是缺实时 true/false/0 及来源错误；最小独立读取后 service 文件 9 passed。
4. final status：4 failed，缺连接事实或 status 来源错误；最小最终读取后 service 文件 13 passed。
5. 补充 F2 六场景、变化的实时统计/更新状态重读与旧对象独立保护；focused 最终 20 passed。补充 proof 验证已实现行为，不宣称其曾 RED。

每个最小实现后执行 service 文件、`git diff --check` 与 `git status --short`；没有在失败状态进入后续实现单元。Ruff 首次发现一处 import 排序，手工最小修正后复验通过。

## Fresh verification（均从 repository root）

| 实际命令 | 结果 |
|---|---|
| `.venv/bin/python -m pytest -q server/tests/services/test_output_manager.py server/tests/invariants/test_output_observation.py server/tests/player/test_task1r_step5.py server/tests/player/test_task1r_step6.py server/tests/player/test_task1r_step7.py`（开始前） | 28 passed |
| `.venv/bin/python -m pytest -q server/tests/services/test_mpd_info_service.py server/tests/invariants/test_mpd_info_relationships.py` | 20 passed |
| `.venv/bin/python -m pytest -q server/tests/invariants/test_mpd_info_relationships.py` | 6 passed；显式 F2 gate |
| `.venv/bin/python -m pytest -q server/tests/player/test_task1r_step5.py server/tests/player/test_task1r_step6.py server/tests/player/test_task1r_step7.py server/tests/invariants/test_architecture_relationships.py` | 6 passed；R-PORT + architecture |
| `.venv/bin/python -m pytest -q server/tests` | 488 passed，无 skip/xfail |
| `.venv/bin/python -m compileall -q server` | exit 0 |
| `.venv/bin/python -m ruff check server/app/models/mpd_info.py server/app/services/mpd_info_service.py server/tests/services/test_mpd_info_service.py server/tests/invariants/test_mpd_info_relationships.py` | All checks passed |
| `git diff --check` | exit 0 |

测试显示已有 Starlette/httpx deprecation warning；无环境失败，未为消除 warning 修改依赖。Full suite 不替代显式 F2 Gate。

## 范围及完成边界

实际 production 为两个新文件；test 为两个新文件；文档为本 acceptance 和 active plan 的事实状态更新。没有修改 API/main/playback/database/player/requirements/Spec，没有未来 Batch imports、运行产物或机器配置进入提交范围。无 blocker、无 Contract Gap。B2 acceptance 满足；B3 可按其 active scope 独立进行新的 pre-flight。B7 REST/真实 NAS/整体 Task 7 验收仍未执行。

Superpowers 要求的独立只读 reviewer 已读取四个 Python 文件及 B2 权威合同，独立复跑 focused 20 passed、R-PORT/architecture 6 passed 与 scoped Ruff；没有 Critical/Important/Minor findings。审查明确排除 B2 范围之外的 API、capability loading/probe、output control、DB/History integration 和真实 NAS 验收。

提交 SHA 与远端 HEAD 应以本文件所属实际 Git commit 和提交后新 `git ls-remote` 为准，不在提交内自引用 SHA；本 Batch 没有明确 push 指令，不执行 push/PR/merge。
