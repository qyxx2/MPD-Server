# Task 6 Batch 12 acceptance — 背压、取消与隔离

日期：2026-10-04（Asia/Shanghai）。本文件仅记录本轮执行证据，不新增合同语义。

## 真实基线与范围

起始分支 `feature/task-6-realtime-state`，HEAD `36a953bb885a274905b826bc73bc32890cbedbb9`，working tree 干净。实际核对 status/branch/HEAD/log，重新读取代码与测试，不从上一窗口、勾选或旧 ledger 判定完成。

已读 docs/superpowers/README.md、主 Implementation Plan、active Task6 plan（Matrix、§5、B11/B12/B13边界）、A §12.1–12.3、O §6.2–6.3，以及既有Output post-commit cancellation proof；B11 acceptance仅定位历史，实际前置handoff/API/commit proofs重新运行30 passed。按用户指定既有checkout执行，不新建worktree或环境。

Skills：using-superpowers、executing-plans、using-git-worktrees、test-driven-development、verification-before-completion、requesting-code-review。既有 `.venv` 实测 Python3.14.4、pytest9.1.1、Ruff0.16.9；已读取server/requirements.txt，无环境或依赖修改。

## Contract Matrix Impact Analysis / traceability

- Owned：**RT-DELIVERY-001 final**。
- Relied-upon unchanged：**RT-CONNECT-001、RT-REVISION-001**。
- Regression：**TX-IDEMP-001、TX-ROLLBACK-001、O-EVENT-001**。
- Relationship Gate：**REQUIRED / PASS（B12 scope）**。
- Contract Matrix Gate：**REQUIRED / PASS（B12 scope）**。
- 新增/修改frozen Contract rows：0；Contract Gap：0。

| Contract → authoritative Spec | Expected Delta / implementation | Must Remain Unchanged / External Confirmation / Failure-Retry | Executable invariant → 本轮fresh GREEN |
|---|---|---|---|
| RT-DELIVERY-001 → A §12.2、active §4共同U/T/F/I | coordinator独立queue默认64，可注入正容量；失效Event唤醒monitor；sender每帧默认10秒；退出先注销、取消并await子任务，再有界close | send不是应用ACK；网络不进入DB锁/commit await；overflow/timeout1013及日志，close失败/超时仍释放资源；不撤terminal/重做业务；Queue occurrence/order/CAS/context、History active/session、Library/Playlist/Favorites、Port queue/output及Output receipt保持；重连恢复owner仍B13 | test_overflow_and_timeout_isolate_clients_and_preserve_commit（initial/live × close成功/失败）；test_send_timeout_and_blocked_close_release_resources_without_rollback（initial/live × close超时/关闭中取消）；FakeClock、真实Service/SQLite/terminal replay、健康连接最后更新及all_tasks基线；delivery全文件10 passed |
| RT-CONNECT-001 → A §12.2 | 原先订阅、capture、首帧水位、live过滤不变；增加失效monitor；失败close移到清理之后 | 连接只消费Service快照，不查MPD、不改业务；本地读取失败仍1011且无成功首帧；普通断开/AnyIO取消await资源 | test_realtime_handoff.py及api/test_realtime.py；最后mutation、登记窗口、失败retry、ASGI取消；与delivery/B1组合40 passed |
| RT-REVISION-001 → L §7.1、A §12.2 | 原同步commit可见登记、epoch/sequence、两域revision策略不变；仅queue容量与注销信号变化 | no-op/rollback/replay不增内容版本；发送不改marker，迟到callback不倒退，Queue CAS独立 | test_realtime_commit_visibility.py；健康连接sequence对照真实marker及terminal replay不增marker；组合40 passed |
| TX-ROLLBACK-001 / TX-IDEMP-001 → active §4.3、原T5 frozen合同 | 业务/terminal共同提交接口未修改 | 提交前失败rollback；交付失败/取消不撤提交；replay不执行pause、不改terminal；不假装撤销外部作用 | delivery真实IdempotencyService execute、独立SQLite读取及replay；指定R-TX纳入125 passed集合 |
| O-EVENT-001 → O §6.3、active §4.3 | 原Output producer/commit/payload未修改 | 确认、outer commit锁外发布、发布失败日志、post-commit cancellation保留terminal、无History保持 | test_output_event_transactions.py含at-commit/during-publish取消与replay；完整R-O纳入125 passed集合 |

普通全套GREEN未替代上表显式关系证明。RT-RECOVER/Task6 final验收仍属B13/D6，不在本批宣称通过。

## Step与RED→GREEN

1. 实际Git/authority/环境/前置测试与Contract pre-flight完成；没有重设计Task。
2. 指定双连接overflow selector **RED：2 failed**，两种close结果均在等待close开始处超时。真实pause/seek提交、健康连接和terminal replay先通过；缺失行为是queue已失效却不能中断阻塞initial sender。
3. 最小production：独立invalidated Event/monitor；先注销、取消并await子任务，最后有界close；本地capture失败保留1011。原selector **GREEN：2 passed**，相关delivery/B11/B1 **32 passed**；diff --check/status通过。
4. 容量注入selector **RED：1 failed**，缺少queue_capacity构造参数；coordinator最小增加正容量注入、默认64，禁止0/负值成为无界队列。精确selector **GREEN：1 passed**；相关文件/B11/B1 **30 passed**；diff --check/status通过。
5. 扩展initial/live overflow、close失败、FakeClock默认10秒send/close deadline、关闭中取消、资源先清理、健康连接最后更新、terminal replay与Must Remain Unchanged。扩展proof首次GREEN，不冒充新目标RED；没有为扩展另改production。
6. focused/proof **40 passed**；指定R-TX/R-O/R-ARCH **125 passed**。初次scoped Ruff仅新文件import排序失败，手工调整该block，重新执行全部通过；无业务/test或环境失败。
7. 补充full suite **976 passed**；compile、完整tracked diff与新测试全文审查通过。独立fresh-context只读reviewer无可操作finding，独立delivery+handoff **20 passed**、diff --check通过。
8. Contract→Spec→implementation→proof→fresh evidence及future-scope审查完成；没有D6恢复、B13客户端恢复测试或Task8+功能，无schema/dependency/environment变化。

## Fresh命令与结果

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_delivery.py server/tests/invariants/test_realtime_handoff.py server/tests/api/test_realtime.py server/tests/invariants/test_realtime_commit_visibility.py
# 40 passed，1.73s；delivery本批10 tests

.venv/bin/python -m pytest -q server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_lifecycle_injection.py server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# 125 passed，7.28s（严格展开R-TX/R-O/R-ARCH）

.venv/bin/python -m pytest -q server/tests
# 976 passed，57.46s；额外回归，不能替代targeted gates

.venv/bin/python -m ruff check server/app/services/realtime_connections.py server/app/services/realtime_coordinator.py server/tests/invariants/test_realtime_delivery.py
# All checks passed
.venv/bin/python -m compileall -q server
# exit0
git diff --check
# exit0
```

pytest仅1条既有Starlette/httpx deprecation warning。无依赖安装/升级，无live MPD、Docker、NAS/DAC或reverse proxy测试；它们不属于B12本地验收。

## Changed files / acceptance / Git二次确认

- `server/app/services/realtime_connections.py`
- `server/app/services/realtime_coordinator.py`
- `server/tests/invariants/test_realtime_delivery.py`（新）
- 本archive acceptance（新，仅执行证据）

API路由无需修改，沿用B11实现。生产diff仅24新增/8删除；无无关格式化/refactor、未来功能、平行权威文档或合同改写。未跟踪文件已独立读取审查，不能拿git diff --stat的tracked两文件数字冒充完整changed-files。

B12 implementation、自动化测试、本地环境验证和本批acceptance满足；blocker/Contract Gap为0，RT-DELIVERY-001在本批闭环。具备进入B13恢复proof实施的本批前置；D6 fresh验收尚未在本轮执行，Task6整体未完成。

active plan §5明确“提交须用户另行授权”；本轮无另行commit/push授权，故没有commit/push/PR/merge。二次只读核对本地branch HEAD与远端refs/heads/feature/task-6-realtime-state均为`36a953bb885a274905b826bc73bc32890cbedbb9`，这是起始提交，不是B12新commit。工作区保留上述四个必要文件变更。

## 后续提交授权与fresh复验

用户随后明确授权“提交push”。提交前重新核对实际branch/HEAD/history及上述四个必要文件，无新增production修改。将上述focused/proof与R-TX/R-O/R-ARCH命令合并执行：**165 passed，7.71s**；再次执行完整server suite：**976 passed，49.56s**。相同scoped Ruff、compile及diff检查通过；仅既有deprecation warning。按授权提交并push当前feature分支；提交后的实际SHA、本地/远端HEAD一致性和工作区状态由Git二次核对及最终报告给出，不创建PR或合并main。
