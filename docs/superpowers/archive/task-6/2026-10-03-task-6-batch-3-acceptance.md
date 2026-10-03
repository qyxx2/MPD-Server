# Task 6 Batch 3 — 本地实施验收证据

日期：2026-10-03。只记录本轮 fresh evidence，不增加或修改合同语义。

## 基准与范围

- 分支 `feature/task-6-realtime-state`，开始 HEAD `c0f61d2ee45776cc0b6d7d70f642a32cf6e969bd`，working tree 干净；实际核对 status/branch/HEAD/log 与 B1/B2 提交。
- 实际读取 Superpowers README、主 Implementation Plan 的全局约束/Task6/依赖/关系与合同 Gate、active Task6 plan §4–6/B3、Library Spec §5/§7.1、Architecture Spec §12.1–12.2、Task5 frozen PL/TX rows 及 corrective acceptance/AB/CD scope、B2 acceptance，并检查直接涉及的 Services/Repositories/API/测试。
- B1/B2 前置不根据 checklist 判定；本轮重新运行其 executable proofs 与 R-PL/R-TX：56 passed。
- 仅实施 B3 Playlist/Favorites/save Queue 版本与提交后事件，以及用户明确批准的 QueueManager 直接保存入口 outer transaction 接线。B9 全局 composition 注入仍未实施；无 Playback producer、snapshot、observer、realtime API、WebSocket 或领域恢复改动。
- 使用既有 `.venv`：Python 3.14.4、pytest 9.1.1、Ruff 0.16.9。已检查 `server/requirements.txt`；无依赖/环境/schema/数据库/runtime artifact 修改，未用 Docker 或 live MPD。

## Contract Matrix Impact Analysis 与 traceability

Owned：**RT-PLAYLIST-001、RT-REVISION-001 final**。Relied：**TX-ROLLBACK-001、TX-IDEMP-001**。Regression：**PL-REP-001、PL-COLLECTION-001**。未新增或修改语义 rows。Relationship Gate / Contract Matrix Gate：**REQUIRED / PASS**。用户批准最小白名单扩展后，审查 finding 已在真实 checkout 修正并重新验收；最终 fresh evidence 如下。

逐项核对 active plan §4.1 U/T/F/I 与 §4.2/§4.3：

| ID / 分类 | Authority | Delta / unchanged / confirmation / failure / retry | Implementation → executable proof → fresh GREEN |
|---|---|---|---|
| RT-PLAYLIST-001 / Owned | Library Spec §5/§7.1；active B3 | 已提交列表存在性、名称、成员、顺序/Favorites 的联合失效；保留 unavailable membership/order、Library Song、Queue/PlaybackContext/History/active/session/PlayerPort；真实 SQLite commit 后发布，无 MPD 确认要求；验证/terminal/outer failure 与取消无成功事件；retry/replay 沿用原合同 | PlaylistService semantic view/outer staging + PlaylistRepository injected runner + QueueManager.save_as_playlist outer transaction + PlaylistChangedEvent → `test_playlist_versions_follow_outer_delta_and_replay`、direct outer/save/barrier/failure proofs → B3 文件11 passed |
| RT-REVISION-001 / Owned final | Library Spec §7.1；Architecture §12.1–12.2 | 同 outer commit 每变化域至多+1；排除审计时间；same-name/favorite/order、改后恢复、rollback/cancel/replay 不增；未变化域/Queue CAS 不变；新数据与版本共同可见；提交后发送失败不撤提交；新进程 epoch/0 不丢持久数据 | LibraryScanner/PlaylistService → RealtimeCoordinator.stage_change → B1 commit visibility、B2 real Library producer、B3 `test_library_and_playlist_share_one_outer_commit_and_restart` 与 barrier/outer proofs → B1 17+B2 10+B3 11 tests GREEN，完整生产级 proof 闭环 |
| TX-ROLLBACK-001 / Relied | active §4.3；Task5 frozen §3.5/§3.7；Architecture transaction rules | HTTP child Service 与 terminal 共用 outer unit-of-work；create/save terminal failure 无部分资源/版本/事件；direct save 成员失败整体回滚，active/session/Queue 保留；提交前取消回滚，提交后取消保留数据/版本/失效义务 | database.run_transaction + service runner → HTTP/direct cancellation proofs；R-TX → focused aggregate119 passed |
| TX-IDEMP-001 / Relied | active §4.3；Task5 frozen §3.5/§3.7 | 失败不留 terminal success，same-key retry 首次提交；create/save replay 原 status/body，无重复资源/版本/event；不改 scope/payload conflict 规则 | IdempotencyService/Repository + real API + producer → main B3 HTTP proof；R-TX → focused aggregate119 passed |
| PL-REP-001 / Regression | Library §2/§5/§7/§9；Task5 frozen §3.7 | resource 仍保留 AVAILABLE/MISSING/UNREADABLE 成员及顺序；CRUD 原错误与 REST schema 不变；Library availability 变化不增 Playlist 版本；不改 Song 内容 | existing persisted/REST invariant + B3 direct unavailable/joint scan proofs；R-PL → focused aggregate119 passed |
| PL-COLLECTION-001 / Regression | Library §4/§9；Task5 frozen §3.7 | Collection playable/unavailable split 保持；不修改持久 Playlist/Favorites，empty/unavailable 来源规则不变 | existing playlist relationship invariant + CollectionService regressions → focused aggregate119 passed |

所有 proof 位于 `server/tests/invariants/`，真实 SQLite/Services/MockPort/临时媒体 fixture 跨边界验证；full suite 未被用来替代 REQUIRED 门禁。

## Step / RED → GREEN 与修正证据

1. RED：指定 `test_playlist_versions_follow_outer_delta_and_replay` 明确失败于 Service 缺少 coordinator 接线。实现 semantic content view、outer staging、PlaylistChangedEvent 后 selector1 passed，B3+B1+B2+R-PL/R-TX57 passed，diff/status 检查通过。
2. 补充 HTTP save Queue proof 得到行为 RED：成功响应后 playlist_revision 仍9，预期10。根因：既有 `QueueManager.save_as_playlist` 直接写 shared PlaylistRepository。仅在 B3 白名单内增加 Repository 可注入 mutation runner，由 Service 提供语义比较/事务边界；同 outer 保存逐成员不暴露中间版本/事件。未改 QueueManager/API/main 或保存范围。selector1 passed，规定 aggregate65 passed。
3. 提交后取消 proof 得到 RED：先前 async callback 取消使新 Service event-stage owner 残留。按 database hooks 顺序定位清理迟于可取消回调；改为同步 visible hook 释放 owner，commit closure 保留最终 delta。精确 selector1 passed，aggregate65 passed。
4. 补齐 direct CRUD/Favorites/save、unavailable members、restore/no-op、outer rollback/cancel、双域联合提交、restart、barrier、迟到发布、publisher failure，以及 HTTP create/save terminal failure/retry/replay 和 Queue/History/active/session/PlayerPort 保留 proof。补充测试首次 GREEN 的部分不冒充 RED。该阶段审查前 B3 文件9 passed，focused aggregate117 passed；最终证据由下一步修正后的结果取代。

5. 独立审查新增 direct QueueManager save success/cancel invariant，实际 RED2 failed。用户明确批准最小白名单扩展后，重新核对 branch/HEAD/working tree 并再次实际重现 RED2；只将原方法 body 包入 outer run_transaction。真实 selector2 passed，B3+QueueManager文件29 passed，B3完整文件11 passed，最终focused119 passed/full774 passed；独立复核 finding CLOSED。每阶段检查 diff/status，未以测试进程提议版本替代真实 GREEN。

非预期失败按 systematic-debugging 定位：新 reader 的含 await tuple generator 是 async_generator，改为 awaited list comprehension；HTTP save fixture 起初误加 `song_ids`，实际冻结请求仅接受 `name`，修正 fixture；原 Queue Up Next 含 AutoPlay refill `a`，保存顺序正确为 `b,c,a`，保留既有行为与断言。没有放宽业务合同或修改原 API。Ruff 仅新 import 排序问题，手动最小修正。

## 实际验证命令

从仓库根目录执行；均使用既有 `.venv/bin/python`。

```bash
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_playlist.py::test_playlist_versions_follow_outer_delta_and_replay
# final: 1 passed
.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_playlist.py
# final: 11 passed

.venv/bin/python -m pytest -q server/tests/invariants/test_realtime_playlist.py server/tests/invariants/test_realtime_commit_visibility.py server/tests/invariants/test_realtime_library.py server/tests/invariants/test_playlist_relationships.py server/tests/services/test_playlist_service.py server/tests/api/test_playlist_reads.py server/tests/repositories/test_transaction_commit_hooks.py server/tests/invariants/test_transaction_relationships.py server/tests/api/test_idempotency.py server/tests/repositories/test_playlist_repository_task5.py server/tests/services/test_queue_manager.py server/tests/services/test_collection_service.py server/tests/invariants/test_architecture_relationships.py server/tests/api/test_api_contracts.py::test_api_does_not_import_repositories
# final B3+B1+B2+R-PL+R-TX+affected Task4/5+R-ARCH: 119 passed

.venv/bin/python -m pytest -q server/tests
# final: 774 passed, 37.26s; after approved production correction
.venv/bin/python -m compileall -q server
# exit 0
.venv/bin/python -m ruff check server/app/services/playlist_service.py server/app/services/queue_manager.py server/app/services/events.py server/app/repositories/playlist_repository.py server/tests/invariants/test_realtime_playlist.py
# All checks passed
git diff --check
# exit 0
```

仅基线已有 Starlette/httpx deprecation warning；无 environment failure。本 Batch 无必须但未运行的 Docker/物理 MPD/NAS/DAC/manual gate。D6-RECOVERY 属后续阶段前置，不由这些 GREEN 关闭。

## Review / isolation / Git

独立只读 reviewer 初次确认一项 Important：direct QueueManager save 没有 outer transaction，暴露空列表/逐成员资源及revision1/2/3，发布取消可留空列表。Root 的真实 success/cancel invariant 重现2 failed。合同语义已明确，无 Contract Gap；原白名单遗漏该必需入口，因此先停在 scope 边界，准备并独立验证最小提议补丁，未擅自修改生产文件。

用户明确批准最小白名单扩展后，active plan B3 只补充该保存事务接线与 proof；真实 QueueManager 方法应用原 body 的 outer transaction，不改 Up Next 范围/顺序、duplicate validation、Queue/播放规则或 API。重新重现 RED2 → 真实 GREEN2；B3文件11 passed；focused119 passed；full774 passed。独立 reviewer 再读实际 diff 并重新运行29 tests/scoped Ruff/diff-check，确认 finding **CLOSED**，Critical/Important/Minor/Contract Gap 均0。

逐 row traceability、changed-files 与 future-isolation 审查完成。**本 Batch implementation、自动化、本地环境验证、Relationship/Contract Matrix Gate 与 acceptance 满足；RT-PLAYLIST-001 / RT-REVISION-001 COMPLETE。具备进入 B4 的本地技术条件，不自动开始 B4，不宣称 Task6整体完成。**

Reviewer 原 Declined-to-judge 项逐一保持当前边界：B9 composition/lifecycle；B7 snapshot/history 与 B8 occurrence/progress；B11 handoff；B12/13 socket 故障/重连；未要求的 live MPD/Docker/物理部署；无已证实缺陷的多 competing Service/大库性能；Task6整体与 D6-RECOVERY。root 不以这些后续能力宣称整体完成。

实际 changed files：

- `server/app/services/playlist_service.py`
- `server/app/repositories/playlist_repository.py`
- `server/app/services/events.py`
- `server/app/services/queue_manager.py`（仅批准的保存事务接线）
- `docs/superpowers/plans/2026-10-03-mpd-server-task-6-batch-plan.md`（仅批准的B3白名单/proof说明）
- `server/tests/invariants/test_realtime_playlist.py`
- 本 archive acceptance 证据文件。

tracked 完整 diff 与新 proof 文件均检查；没有无关格式化/重构、未来 Batch/Task 实现、重复权威文档、合同语义/依赖/环境/DB/cache 变更。

本轮未 commit/push/PR/merge。active plan §5 明确“提交须用户另行授权”；实施指令未提供该另行授权。只保留上述预期文件。

本轮已实际重读本地 HEAD/branch 与 `git ls-remote origin refs/heads/feature/task-6-realtime-state`，均为 `c0f61d2ee45776cc0b6d7d70f642a32cf6e969bd`；这是已有提交，非本轮新增 SHA。

## 后续提交授权与提交前复核

同日用户明确要求“提交push”。重新核对实际分支、HEAD、完整预期七文件范围与远端 ref；本地/远端仍为上述基准。

提交前 fresh B3+B1+B2+R-PL/R-TX+直接受影响历史回归+R-ARCH：**119 passed**；compileall、目标 Ruff、diff-check 再次通过。生产/测试代码没有新增修改，前述 full suite **774 passed** 证据保留。只提交上述七个文件；提交 SHA、本地/远端 HEAD 和工作树状态以实际提交/push 后 Git 二次核对及提交报告为准。
