# Task 7 Batch 3 — 共同串行化与播放保留 guard acceptance

## 实际基线、范围与环境

- 指定分支 `feature/task-7-output-manager`，开始时 HEAD `a3404df7fb1fdaed39789538413ca2e8e5dfe5b1`，working tree 干净。重新 fetch 后同名远端 ref 相同；Task 1R `03f4de9`、Task 4 corrective `86975d6` 通过 ancestry 检查。
- 实际读取 README、主 Plan 全局约束/gates/Task 7、active Task 7 plan B3/相关 rows/冻结接口/F3/验收、O §6.2、A §8.1/19.5、P §8、Task 5 原始合同 rows，以及当前 playback/output/database/player/History/测试实现；没有用历史完成记录代替运行证据。
- 现有 `.venv`：Python 3.14.4、pytest 9.1.1、ruff 0.16.9。没有变更环境/依赖，没有 Docker、真实 NAS/MPD 或物理 DAC 操作。
- 本次完成共同规则的 pre-flight、RED、最小实现、focused/invariant、历史 regression、compile/lint/diff 和 review；对应主 Plan Step 4/5 的 **B3 prerequisite 部分**。主 Task 7 Steps 不因本 Batch 局部验收被标整体完成。

## Contract Matrix Impact Analysis 与逐字段 traceability

- Owned：**O-PRESERVE-001（guard/协调基础阶段）**。
- Relied-upon unchanged：**PORT-OUTPUT-001、TX-ROLLBACK-001**。
- Regression：**PB-STOP-001、PB-INSERT-001、PB-REORDER-001、PB-DELETE-PENDING-001、PB-DELETE-CURRENT-001、PB-NEXT-UNAVAILABLE-001、PB-HISTORY-001**。
- Affected existing implementation：PlaybackService 共同事务入口与上述四个缺少整段包装的方法；消费既有 TX-ROLLBACK 机制。新增/修改业务 row：无；不修改任何 frozen semantic。
- Relationship Gate：**REQUIRED / PASS（B3）**；Contract Matrix Gate：**REQUIRED / PASS（B3）**。O-PRESERVE-001 完整 Service row 仍 pending B5/B6 实际输出启停 proof，不提前宣称完成。

| ID / authoritative Spec | State delta / Must Remain Unchanged | Confirmation / failure / retry | Implementation → executable proof → fresh GREEN |
|---|---|---|---|
| O-PRESERVE-001；O §6.2、A §8.1/19.5、P §8，active §4.2/§5/B3 | B3 callback 是只读/协调 witness，输出启停不变；合法并发 playback 按共同事务顺序执行。输出自身保持 Queue snapshot/revision/item identity/order、PlaybackState/Context/AutoPlay、persisted/active/session History、MPD occurrence/order/state/repeat/random/volume；暂停已知位置不变，未知保持未知，允许自然推进 | 同一 DB 外层 run_transaction；manager 不新增锁或访问 Repository。before/after status + execution entries 确认；同 URI 不代替 occurrence ID。漂移报 OUTPUT_RECONCILIATION_FAILED，不重播/seek/重建 Queue/修复 History；读取失败、callback exception/cancel 不返回成功。retry 重新读取，已有外部 Queue/current 漂移留给既有 playback reconciliation。没有输出成功事件 | playback_service.py::run_output_operation 与四个 wrapper；output_manager.py::_run_preserved_operation；F3 test_output_serialization.py 两个 register 函数及 failure/clock/baseline cases，**61 passed** |
| PORT-OUTPUT-001；O §4/§10、M Task 1R、active §4.3 | 消费现有 PlayerPort/VerifiedPlayerPort，不修改 transport/capability；B3 没有输出写入 | 读取 status/queue_entries/outputs 经真实 wrapper；typed failure 可观察；不把 command ACK 当确认，不运行 probe | F3 real VerifiedPlayerPort + Mock + SQLite；F1/output service regression 在 focused 198 passed 内；端口实现没有修改 |
| TX-ROLLBACK-001；原 Task 5 Matrix、A §8.1/19.5，active §4.3 | runner 复用现有 unit-of-work；outer failure 恢复 persisted 和 History active/session，外部 MPD 不假称回滚 | callback 无 connection 参数；内层不会提前提交。原 run_transaction BaseException rollback 机制；失败后新 task 可重新取得锁 | F3 nested outer rollback/cancel/retry；R-TX test_transaction_relationships.py；fresh focused 198 passed 内 |
| PB-STOP-001；P Stop/History 语义、Task 5 原 row | 既有 confirmed STOP、AutoPlay disabled、History exactly-once 终止不变；Queue 不因 STOP 清空 | 未确认/transport failure 回滚，retry/replay 保持原合同 | R-STOP + F3 stop 两方向；focused GREEN |
| PB-INSERT-001；P Play Next/Add to Queue、Task 5 原 row | 只新增 pending execution occurrence；current/state/Context/History 不变 | 整段同步与确认在共同事务；失败不提交插入，外部副作用仍独立，retry 依原 reconciliation | R-PLAY insertion/duplicate cases；F3 两方向；直接 service sync-failure 完整 snapshot/History/session proof；focused GREEN |
| PB-REORDER-001；P Queue 语义、Task 5 原 row | 修改 pending order；retained occurrence/current/Context/History 不变 | revision/sync/confirmation failure 原 rollback/retry 不变 | R-PLAY retained duplicate reorder + F3 reorder 两方向；focused GREEN |
| PB-DELETE-PENDING-001；P Queue/AutoPlay、Task 5 原 row | 精确删除 pending、必要 refill；current/History 保持 | unavailable/divergence/terminal failure 原 rollback；无半提交成功 | R-PLAY + pre_batch6 corrective + F3 pending delete 两方向；focused GREEN |
| PB-DELETE-CURRENT-001；P current successor/Stop、Task 5 原 row | 确认可用 successor 或 STOP 后更新 state/History；stopped 不自动重启 | 不制造 unavailable current 或 phantom History；原 failure/retry 不变 | R-PLAY/R-STOP + pre_batch6 corrective + F3 current delete 两方向；focused GREEN |
| PB-NEXT-UNAVAILABLE-001；P §8.3、Task 5 原 row | 跳过 unavailable pending，再确认 successor/AutoPlay；无效项不能成为 current | skip/sync failure 回滚，retry 不重复 transition | R-PLAY transition、R-TX、playback service skip tests、F3 next 两方向；focused GREEN |
| PB-HISTORY-001；P History/Stop、Task 5 原 row | 原确认 transition 只产生一次 History；输出无新增/结束 History | confirmation 晚于所需 port 确认并属于 owning transaction；失败无 phantom/session 丢失 | R-PLAY/R-STOP/R-TX + F3 完整 persisted/active/session before/after；focused GREEN |

表中历史 rows 的权威完整字段仍在原 Task 5 Matrix，不新增平行长期合同。逐项核对其 Preconditions、Authorities、Delta、Unchanged、Confirmation、History/Event、Transaction、Failure、Retry、Observable Result、Proof 后，按指定历史 tests 复验。F3 使用真实 SQLite/Repositories/PlaybackService/History/OutputManager/VerifiedPlayerPort 和局部 Mock fault injection；两个参数化 register 函数分别证明所有公开 mutation 的串行关系与完整保留事实。

## RED → GREEN 与调查记录

1. shared runner：1 failed，明确缺少 B3 runner；最小复用 atomic wrapper 后 1 passed，nested callback 的业务/History 外层失败恢复和返回值均获机械证明；直接 R-TX/service regression 35 passed。
2. play_next、add_to_queue、pause、seek：逐个 reverse barrier RED，输出 callback 在 playback 外部确认暂停期间已经完成；各加一个现有 atomic decorator 后 bidirectional cases 分别 GREEN。最终 15 个公开 mutations × 2 个方向共 30 cases。Event barriers 和 attempted 事件证明调度顺序，不使用 sleep 猜时序。
3. guard 缺失：先修正 fixture 将 capabilities 当 Pydantic 的错误（真实类型为 dataclass），重新执行后因缺 preservation guard 正确 RED；最小 before/after 结构确认后 1 passed。
4. nonplaying/unknown position：3 failed（DID NOT RAISE）→3 passed；paused/stopped 位置及未知→已知漂移均被拒绝。
5. playing clock：reset/backwards/jump/freeze 四场景 4 failed（DID NOT RAISE）→4 passed；最小 monotonic 测量后不再忽略 elapsed 漂移。
6. unconfirmed duplicate/unknown/wrong current baseline：3 failed（DID NOT RAISE）→3 passed；不进入 callback。
7. reused mutable port models：status/entries 两场景 2 failed（DID NOT RAISE）→2 passed；baseline deep copy 防止读对象别名掩盖漂移。
8. supplemental GREEN proof 覆盖 PLAYING/PAUSED/STOPPED/empty/unknown/natural、same URI distinct occurrence、所有 mode drift、read/callback/cancel failure、独立 task retry、读取延迟窗口；不把补充 proof 冒充首次 RED。

每个 production 单元后运行对应 focused/invariant、直接相关 regression、diff check/status；出现 regression failure 后先用 systematic debugging 调查，不在失败状态继续 implementation。

### 直接相关旧测试冲突的 ruling

`test_mpd_queue_sync_failure_keeps_server_queue_authoritative` 原先要求 add_to_queue 同步失败后仍留下新增 g。新整段事务使其回滚，精确 test 可重复失败；在单独 Python 进程仅把该方法替换为 `__wrapped__` 后旧 test 通过，确认根因是原局部提交边界，不是环境或 Player 恢复算法。

依据冻结 PB-INSERT-001/TX-ROLLBACK-001 与 B3 明确整段 run_transaction 要求，修正直接受影响 test 的预期为原 Queue，并加强 snapshot/revision/identity、persisted History、active/session 完全恢复。Player error、实际 MPD Queue、PlaybackState 断言均保留。修正后的 test 对 process-local unwrapped 方法 RED，对真实 wrapper GREEN；R-PLAY/service regression 40 passed。没有修改合同、降低断言或扩大到无关测试。代价：直接 Service 的失败插入不再局部持久化，这是已冻结合同要求。

### 时钟实现选择与限制

已知 PLAYING elapsed 差使用 `[max(0, after_start-before_end-0.001), after_end-before_start+0.001]`；时钟在两次 status read 前后分别采样，纳入 transport latency，1 ms 用于 elapsed rounding/numerics，不采用数秒宽容差，不允许 backwards movement。paused/stopped 已知值精确保持；任一未知时要求未知关系不变，不制造数值。fake clock 测试证明自然推进/读取窗口与 reset/freeze/jump 的区分；低精度 legacy whole-second status 可能被保守拒绝。没有把本地 clock proof 宣称为真实 NAS 时间精度/出声验收。

## Fresh verification（repository root、现有 .venv）

| 实际命令 | 实际结果 |
|---|---|
| `.venv/bin/python -m pytest -q server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_transaction_relationships.py server/tests/services/test_playback_service.py server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_output_manager.py server/tests/invariants/test_output_observation.py`（实现前） | 137 passed |
| `.venv/bin/python -m pytest -q server/tests/invariants/test_output_serialization.py` | 61 passed；显式 F3 gate |
| `.venv/bin/python -m pytest -q server/tests/invariants/test_output_serialization.py server/tests/invariants/test_playback_relationships.py server/tests/invariants/test_stop_confirmation.py server/tests/invariants/test_transaction_relationships.py server/tests/services/test_playback_service.py server/tests/api/test_pre_batch6_corrective.py server/tests/services/test_output_manager.py server/tests/invariants/test_output_observation.py` | 198 passed；Batch focused + 指定 PB regression + TX rollback + B1 regression |
| `.venv/bin/python -m pytest -q server/tests/invariants` | 118 passed；包含 architecture，独立 relationship gate |
| `.venv/bin/python -m pytest -q server/tests` | 549 passed；0 failed/errors/skip/xfail |
| `.venv/bin/python -m compileall -q server` | exit 0 |
| `.venv/bin/python -m ruff check server/app/services/output_manager.py server/app/services/playback_service.py server/tests/invariants/test_output_serialization.py server/tests/services/test_playback_service.py` | All checks passed |
| `git diff --check` | exit 0 |

只有既有 Starlette/httpx deprecation warning，没有环境失败；没有为消除 warning 更换依赖。Full suite 不替代显式 F3/历史关系 Gate。

Superpowers 独立 read-only reviewer 另行复跑 F3 61 passed、R-PLAY/R-STOP/R-TX/service/pre-batch6 corrective 113 passed、scoped Ruff/diff check。无 Critical/Important/Minor findings。作者和 reviewer 都检查了实际 production diff 和新增 invariant 文件。

## changed-files / 隔离 / 完成边界

- Production：`server/app/services/playback_service.py`、`server/app/services/output_manager.py`。
- Tests：新 `server/tests/invariants/test_output_serialization.py`、直接相关 `server/tests/services/test_playback_service.py` 单 test。
- Docs：本 acceptance 和 active Task 7 plan 的 B3 事实/归档引用。
- 未修改 Spec、主 Plan、PlayerPort/Adapter/Mock、database/schema、事件、API/main、依赖、部署/Web/Task 6/Task 10；没有输出命令、自动 seek/replay/Queue rebuild、其它播放算法或无关格式化进入 diff。机器配置/运行产物不提交。
- reviewer set aside 的真实启停/物理 DAC 与真实 timing、commit hooks/events、API 和远端操作分别归 B5/B6、物理联调、B4/B8、B7/B8 和明确 Git 授权；这些行为不属于本次 B3 acceptance。没有据此扩大 B3 或掩盖 blocker。
- 无 blocker、无 Contract Gap；B3 acceptance 满足，可进入 B4 的新 pre-flight。O-PRESERVE-001 完整业务仍 pending B5/B6；Task 7 未完成。
- 按用户指令提交本 Batch 后验证 branch/HEAD/commit files/clean state，再核实 remote ref。当前 active plan 无明确 push 指令，不执行 push/PR/merge。提交 SHA 和远端 HEAD 以提交后实际 Git 输出为准，不在提交内自引用 SHA。
