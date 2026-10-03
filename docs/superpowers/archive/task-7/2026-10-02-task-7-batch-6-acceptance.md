# Task 7 Batch 6 — NAS_DAC disable acceptance

## 真实基线和范围

- 分支 `feature/task-7-output-manager`，开始 HEAD `184cf0a20f9526cbf4a37bc755a54ea814a8fada`，working tree 干净。重新检查 history、fetch 和 ls-remote：同名远端 ref 等于开始 HEAD。Task 1R `03f4de9`、Task 4 `86975d6` ancestry exit 0。
- 实际读取 README、主 Plan Task 7/依赖/两个 Gate、active Plan rows/接口/F6/B6/共同验收、B5 acceptance、O §4–6/8.2、A §8.1/12/13/19.5、P §7–8、原 Task 5 matrix §3.6、直接实现和测试；未以历史文档的状态代替本轮测试。
- 完成主 Step 1/3/4/5 的 B6 disable 部分及 Step 8 本 Batch Gate。只把既有 enable 算法改为布尔 ensure；没有复制算法，没有新增播放业务、API、schema、依赖或基础设施。原“before its batch”拒绝测试随 B6 授权替换为真实 disable 成功测试，未放宽合同。
- 使用既有 `.venv`：Python 3.14.4、pytest 9.1.1、Ruff 0.16.9；未修改环境、依赖、Docker 或本地数据库，未访问真实 MPD/NAS/DAC。localhost fake TCP 是已有 F5 transport regression。

## Contract pre-flight / traceability

Owned：**O-DISABLE-001、O-FAIL-001（disable）、O-PRESERVE-001（最终 Service proof）**。

Relied-upon unchanged：**O-DISC-001、O-STATE-001、O-TX-001、O-EVENT-001、PORT-OUTPUT-001**。

Regression：**PB-STOP-001、PB-HISTORY-001、O-ENABLE-001、O-STATE-001、TX-ROLLBACK-001、TX-IDEMP-001**；F5、R-TX。

Relationship Gate：**REQUIRED / GREEN**。Contract Matrix Gate：**REQUIRED / GREEN（B6 Service scope）**。

无新增/修改业务语义 row；实现前逐项核对 Preconditions、Authorities、Expected Delta、Must Remain Unchanged、External Confirmation、History/Event、Transaction Boundary、Failure/Rollback、Retry/Idempotency、Observable Result、Executable Proof。B3 guard/B4 lifecycle/B4.5 runner/B5 算法均真实存在；本轮前置回归 **152 passed**。未发现 Contract Gap。

| Contract → authoritative Spec | Delta / unchanged / confirmation / failure / retry → implementation → executable fresh proof |
|---|---|
| O-DISABLE-001 → O §4.2/6.1–6.3 | 只把当前 selector 目标置 false，actual INACTIVE；其它输出及完整播放权威保持。fresh outputs + guard 后才成功；已 disabled 仍确认，无重复写/事件；当前 ID 每次重读。`OutputManager._ensure_enabled` → F6 success/no-op/ID-rebind/capabilities，**49 F6 GREEN**。 |
| O-FAIL-001(disable) → O §6.1–6.2/8.2 | typed failure/cancellation 继续抛出，request SWITCH_FAILED；实际 output 回读独立于失败，读不到则缓存 stale。无补偿/播放修复/成功通知；retry fresh ensure，已生效不重写。共用 `_fail_request`/`_observe` → F6 ACK无效果、拒绝、effect-timeout、readback-once/offline、cancel、initial-offline、after-status、cache/retry，**49 F6 GREEN**。 |
| O-PRESERVE-001 → O §6.2、A §8.1/19.5、P §8 | Queue revision/identity/order、Context/AutoPlay、persisted/active History/session、MPD occurrence/queue/status/modes 保持；paused/unknown 位置保持、playing 自然推进容许。相同 DB runner/guard，发现 drift 报错不修复。F3/F4L + F5/F6 完整 authority snapshots、duplicate URI、PLAYING/PAUSED/STOPPED/empty/unknown/natural、最后一个 enabled output、drift；控制白名单证明 stop/play/seek/queue/mode mutation call count=0，**271 direct regression GREEN**。 |
| O-DISC-001、O-STATE-001 → O §4.2/5.2/6.1 | 唯一当前 ALSA/selector；请求 enabled=false，PREPARING→SUCCEEDED/SWITCH_FAILED，actual 与 request 分离，stream unavailable/null，独立返回快照与 stale 事实。原 `_select_target`/`_snapshot` + shared ensure → F1/F5/F6，**271 GREEN**。 |
| O-TX-001、O-EVENT-001 → O §6.2–6.3、A §19.5 | 公共 per-invocation lifecycle 注册；outer commit 后且 guard 确认后才通知。outer failure/cancel 丢弃通知和 terminal，失效 success 标记，MPD 已停用不反向启用；retry no-op 无重复通知。F4/F4L/F5/F6 outer terminal witness，**271 GREEN**。最终 REST/schema/middleware proof 仍 B8。 |
| PORT-OUTPUT-001 → O §4/10、主 Plan Task 1R | 能力缺失先拒绝、端口 bool control/typed error 保持，不改 Adapter 或 probe。F6 + R-PORT step4–7/F5 localhost transport，**271 GREEN**。 |
| PB-STOP-001、PB-HISTORY-001、O-ENABLE-001、O-STATE-001、TX-ROLLBACK-001、TX-IDEMP-001 → Task 5 original matrix §3.6、P §7–8、O §6、A §8.1/19.5 | 历史确认、History/session、rollback/retry/replay 合同不变；disable 不触发 STOP。R-STOP/R-PLAY/R-TX、API idempotency、playback service、F5；**271 GREEN**。 |

## RED → GREEN 和实际命令

- 服务状态测试 RED **1 failed**，F6 last-enabled/playing RED **1 failed**：production 明确拒绝 disable，`OUTPUT_CONTROL_UNAVAILABLE`。
- F6 ACK-no-effect 和 automatic state drift RED **2 failed**：收到 unavailable 而非需要的 reconciliation failure。完整 traceback 已读，原因是目标行为尚缺，非环境/fixture/import 错误。
- 将 `_enable` 最小推广为 `_ensure_enabled(lifecycle, enabled)`，请求、写入、比较、确认传递同一 bool；上述四个原 RED 目标重跑 **4 passed**。
- 第一轮 focused F6/service/F5/F3/F4/F4L/R-STOP **181 passed**。补充 outer lifecycle/capability/ID-rebind 八项 proof 首次 **8 passed**；复用已有实现，不伪称另有 production RED cycle。
- 首次 scoped Ruff 发现新 F6 import 的 I001，按建议仅改 multiline import；再次 scoped Ruff **All checks passed**。

全部命令从 root 使用 `.venv/bin/python`；每个测试命令均 exit 0：

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_output_disable.py
# 49 passed

.venv/bin/python -m pytest -q server/tests/services/test_output_manager.py server/tests/invariants/test_output_disable.py server/tests/invariants/test_output_enable.py server/tests/invariants/test_output_observation.py server/tests/invariants/test_output_serialization.py server/tests/invariants/test_output_event_transactions.py server/tests/invariants/test_output_lifecycle_injection.py server/tests/invariants/test_output_transport.py server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/services/test_playback_service.py server/tests/player/test_task1r_step4.py server/tests/player/test_task1r_step5.py server/tests/player/test_task1r_step6.py server/tests/player/test_task1r_step7.py
# 271 passed

.venv/bin/python -m pytest -q server/tests/invariants
# 242 passed; includes architecture gate
.venv/bin/python -m pytest -q server/tests
# 679 passed
.venv/bin/python -m compileall -q server
# exit 0
.venv/bin/python -m ruff check server/app/services/output_manager.py server/tests/services/test_output_manager.py server/tests/invariants/test_output_disable.py
# All checks passed
```

测试均有一个既有 StarletteDeprecationWarning；未安装/升级依赖处理警告。没有 failing/skipped/xfail tests。各已完成行为单元之后均检查 focused/invariant 和 `git diff --check`、`git status --short`。

## Changed-files / isolation review

- Production：`server/app/services/output_manager.py`，只复用 bool ensure。
- Tests：`server/tests/services/test_output_manager.py`、新 `server/tests/invariants/test_output_disable.py`。
- Docs：active Task 7 plan 的当前 B6 状态/F6 存在性，以及本 acceptance archive；无平行权威文档、无合同改写。
- 真实 diff 审查无无关重构/格式化/未来 imports、无环境/数据库/生成物；B7–B9 和 Task 6/10 未实施。选择保留用户指定 checkout 与 `.venv`，没有新 worktree；代价是没有额外 checkout 隔离。
- B6 Service acceptance 满足后可进入 B7 独立 pre-flight。Task 7 尚未完成；O-TX/O-EVENT 最终 API gate pending B8，B9 整体验收 pending。真实 NAS/DAC/出声验证不属于本轮本地 acceptance，未执行。
- Active B6 plan 没有明确 push 要求；本轮只本地提交，提交后的 local SHA/branch/changed files/clean tree 与远端 ref 二次确认见执行报告和本地 ledger，不推送/PR/merge。

独立 code review：无 Critical/Important/Minor finding；审查者实际重跑 Service/F6/F5/F3/F4/F4L **184 passed**，R-STOP/R-TX/idempotency/observation/transport **41 passed**，scoped Ruff/diff check 通过。审查后更新的文档由主执行者完整审查。

审查边界处理：历史 RED 由主执行者本轮原始失败输出证明；最终文档由主执行者审查。B7/B8 HTTP/schema/middleware 的最终 proof、整 Task 完成、真实 NAS/physical DAC、部署及 merge 均不作为本 Batch 完成声明，分别保留后续或外部验收；代价是 B6 GREEN 不证明这些范围。无 deferred minors。
