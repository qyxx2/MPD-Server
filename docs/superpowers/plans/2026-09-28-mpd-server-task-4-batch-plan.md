# MPD-Server Task 4 Batch Execution Plan

> Task 4：Queue、Playback Context、History、AutoPlay、Playback Service
>
> 本文件用于 Task 4 的分批实施与跨 AI 窗口交接。  
> **Task 4 一共 15 个 Plan Steps，固定拆为 6 个 Batch；每个 Batch 使用一个全新的 AI 窗口。**
>
> 本文件不是对原实施 Plan 的替代，不改变 `docs/superpowers/plans/2026-09-25-mpd-server-v0-1-implementation-plan.md` 中的 Step、Dependency Matrix 或 Execution Order。
> 原 Plan 和相关 Specs 仍是唯一的实现依据，本文件只规定 Task 4 的执行分批方式、边界和交接方式。

---

## 1. Task 4 前置条件

Task 4 依赖：

- Task 1R 已完成并存在于当前历史；
- Task 2R 已完成并存在于当前历史；
- Task 3 已完成 corrective follow-up，并已经冻结 Task 4 所需的 Available Songs contract 和 DomainEvent contract。

Task 4 不依赖：

- Task 5
- Task 6
- Task 7
- Task 8
- Task 9
- Task 10
- Task 11
- Task 12

执行时必须再次以当前仓库实际状态确认上述依赖，不得只相信本文件或上一窗口的报告。

---

## 2. 固定执行方式

### 2.1 一个 Batch = 一个全新 AI 窗口

Task 4 固定使用：

`feature/task-4-playback`

分支。

执行结构：

```text
main
  │
  └── feature/task-4-playback
        │
        ├── Batch 1 commit
        ├── Batch 2 commit
        ├── Batch 3 commit
        ├── Batch 4 commit
        ├── Batch 5 commit
        └── Batch 6 commit
```

每个 Batch 完成后：

1. 完成该 Batch 的代码/测试工作；
2. 检查 diff、changed files、依赖边界；
3. 按原 Plan 要求提交；
4. 再次读取远端 branch/ref/commit，确认提交真实存在；
5. 输出 Batch 结束交接摘要；
6. 结束当前 AI 窗口。

下一个 Batch：

1. 使用新的 AI 窗口；
2. 读取本文件、原 Plan、相关 Specs；
3. 读取当前仓库真实 branch/HEAD/工作区/提交历史；
4. 验证上一 Batch commit 真实存在并已包含在当前分支；
5. 重新验证历史 Step，而不是相信上一窗口口头描述；
6. 只实施本 Batch 指定的 Steps。

### 2.2 Git 是事实来源

跨窗口不要复制上一窗口的大量实现过程。

交接的事实来源按优先级：

1. 当前仓库实际代码；
2. 当前分支与 HEAD；
3. Git 提交历史及远端 branch ref；
4. Tests 与实际测试输出；
5. Plan / Specs；
6. 上一窗口交接摘要。

如果交接摘要与仓库实际状态冲突，以仓库 + Plan + Specs 为准。

---

# 3. Batch 划分总览

| Batch | Plan Steps | 范围 | 核心目标 | 风险 |
|---|---:|---|---|---|
| Batch 1 | 1-4 | Queue 基础语义 | Queue / PlaybackContext / Play Now / Play Next / Add to Queue / reorder / delete / clear / save-as-playlist | 中 |
| Batch 2 | 5-6 | History 语义 | Played 与永久 History 分离；自然完成 / skip / stop / switch-away | 中 |
| Batch 3 | 7-9 | AutoPlay | low-watermark 5 / refill 5 / Context / MANUAL 优先 / 边界与并发 | **最高** |
| Batch 4 | 10-11 | 并发与状态 | Queue transaction / revision-CAS / Pause / Stop / exhaustion | **高** |
| Batch 5 | 12-13 | Playback Service | 唯一编排层；MPD 失败、状态回读与一致性 | **最高** |
| Batch 6 | 14-15 | 整体验收 | Task4 regression / diff / lint / compile / commit | 中 |

---

# 4. Batch 1：Queue 基础语义

## Steps

**Step 1**
RED tests for Start Track replacing pending Up Next and creating PlaybackContext.

**Step 2**
RED tests for Queue Play Now preserving prior pending items after the selected song.

**Step 3**
RED tests for Play Next and Add to Queue insertion order.

**Step 4**
RED tests for reorder/delete/clear/save-as-playlist and current-song deletion.

## 允许涉及的核心文件

- `server/app/models/queue.py`
- `server/app/repositories/queue_repository.py`
- `server/app/repositories/playback_state_repository.py`
- `server/app/services/queue_manager.py`
- `server/tests/services/test_queue_manager.py`

需要使用已有 Repository / PlayerPort / Library contract 时，只能通过已有接口。

## 本 Batch 必须解决

- `PlaybackContext` 的建立与持久状态边界；
- Server Queue 是业务权威；
- Start Track 与 Queue 内 Play Now 的语义区别；
- Play Next 插入当前歌曲之后；
- Add to Queue 追加到待播末尾；
- Queue reorder / delete / clear；
- current-song deletion 的明确语义；
- save-as-playlist 默认只保存 Up Next，不把 Played 历史混入；
- Queue item source / playback context 字段符合 Plan 定义；
- Server `queue_item_id` 与 MPD `mpd_song_id` 不混用。

## 本 Batch 不做

- AutoPlay refill；
- Queue CAS/revision；
- Playback Service 总编排；
- WebSocket；
- API；
- Output Manager；
- Task5/6/7 等未来 Task。

## 特别注意

不要把 Queue 的 Played 与永久 History 当成同一数据结构。Batch 2 才处理 History 语义。

---

# 5. Batch 2：Played 与 Playback History

## Steps

**Step 5**
RED tests for Played view versus persistent History.

**Step 6**
RED tests for natural completion, skip, stop and switch-away reasons.

## 允许涉及的核心文件

- `server/app/services/history_service.py`
- 与 Queue / playback state 必要的现有模型或 Repository
- `server/tests/services/test_history_service.py`

## 本 Batch 必须解决

- Queue 当前会话中的 Played 视图与永久 Playback History 分离；
- History 记录 song_id、start/end、reason、session_id；
- 自然播放完成；
- 用户 skip；
- 用户 Stop；
- 用户切换歌曲 / switch-away；
- 清理 Queue 历史展示不能删除永久 History；
- History 写入不能改变 Queue；
- History 不依赖未来 API/WebSocket；
- 避免把所有离开事件统一标成 `ended`。

## 本 Batch 不做

- AutoPlay 产生新 Queue item；
- CAS/revision；
- Playback Service；
- API/WebSocket；
- Task5/6/7。

---

# 6. Batch 3：AutoPlay 核心

## Steps

**Step 7**
Implement AutoPlay low-watermark 5/refill 5 using Task 3 available Songs while respecting PlaybackContext.

**Step 8**
Prevent AutoPlay from overwriting MANUAL items and mark every generated item source.

**Step 9**
Test empty library, one-song library, insufficient candidates and concurrent Queue mutation.

## 允许涉及的核心文件

- `server/app/services/autoplay.py`
- `server/app/services/queue_manager.py`（仅为当前 AutoPlay 所需的最小接口整合）
- `server/app/models/queue.py`（仅必要字段）
- `server/tests/services/test_autoplay.py`
- Task3 已冻结的 Available Songs contract 所在模块，仅通过既有契约调用

## 本 Batch 必须解决

- low-watermark = **5**；
- refill = **5**；
- AutoPlay 使用 Task3 Available Songs；
- 尊重当前 PlaybackContext；
- 生成的 QueueItem 标记 `AUTOPLAY`；
- MANUAL item 不能被 AutoPlay 删除、覆盖或重新排序；
- 同批次不能无故重复；
- 曲库为空；
- 只有一首歌；
- 候选少于 refill 数量；
- AutoPlay 生成期间发生用户 Queue 修改时，以串行化后的最新 Queue 为准；
- 预生成内容必须进入可见 Up Next，而不是仅存在后台状态。

## 本 Batch 是 Task4 最高风险批次之一

严禁为了处理并发问题提前引入未来 Task 的 API、WebSocket 或配置体系。

如果发现 Queue transaction / revision-CAS 是正确实现所必需的：

- 允许识别该依赖；
- 允许在不越界的情况下使用 Task4 当前已存在的 Repository transaction boundary；
- 不得提前实现 Batch 4 之外的大段逻辑；
- 不得为了测试方便引入未来 Task 代码。

---

# 7. Batch 4：Queue 并发与播放状态语义

## Steps

**Step 10**
Serialize Queue mutations using Repository transaction boundaries plus Queue revision/CAS.

**Step 11**
Test Pause keeps AutoPlay, Stop disables it, and Queue exhaustion is not terminal.

## 允许涉及的核心文件

- `server/app/repositories/queue_repository.py`
- `server/app/repositories/playback_state_repository.py`
- `server/app/services/queue_manager.py`
- `server/app/services/autoplay.py`
- `server/tests/services/test_queue_manager.py`
- `server/tests/services/test_autoplay.py`
- 与 playback state 所需的当前 Task 模型

## 本 Batch 必须解决

- Queue mutation 的 transaction boundary；
- revision / CAS；
- stale write 不覆盖新 Queue；
- 并发用户修改与 AutoPlay refill 的正确序列化；
- Pause 保留 AutoPlay；
- Stop 关闭 AutoPlay 接管；
- Queue exhaustion 不是 terminal state；
- `PLAYING` / `PAUSED` / `STOPPED` 语义保持一致。

## 本 Batch 不做

- Playback Service 最终总编排；
- API；
- WebSocket；
- Output Manager；
- 配置系统。

---

# 8. Batch 5：Playback Service 与 MPD 一致性

## Steps

**Step 12**
Implement Playback Service as the sole orchestration layer between Queue/History/AutoPlay and PlayerPort.

**Step 13**
Test MPD failures do not falsely advance current-track service state and reconcile external status.

## 允许涉及的核心文件

- `server/app/services/playback_service.py`
- `server/app/services/queue_manager.py`
- `server/app/services/history_service.py`
- `server/app/services/autoplay.py`
- `server/tests/services/test_playback_service.py`
- 既有 PlayerPort / MPD models / errors

## 本 Batch 必须解决

Playback Service 必须成为：

```text
Queue Manager
History Service
AutoPlay
        ↓
Playback Service
        ↓
PlayerPort
```

之间的唯一播放编排层。

必须覆盖：

- Start Track；
- Play Now；
- Play Next；
- Add to Queue；
- 集合播放相关的已有服务级能力；
- Pause；
- Stop；
- 切歌；
- Queue / History / AutoPlay 状态联动；
- MPD command failure；
- command success 后再推进服务状态；
- 必要时重新读取 MPD status/current-song；
- MPD 与 SQLite / service state 短暂不一致时显式处理；
- MPD 不可用不能伪造播放成功。

## 本 Batch 是 Task4 第二个最高风险批次

禁止：

- Playback Service 直接访问 SQLite；
- Playback Service 直接访问 MPD TCP；
- 绕过 PlayerPort；
- 为方便测试引入 API；
- 提前引入 WebSocket；
- 引入 Task6 的 realtime code；
- 引入 Task10 config.py。

---

# 9. Batch 6：Task4 整体验收与提交

## Steps

**Step 14**
Verify Queue/Playback persistence, MPD synchronization, compile/lint and diff.

**Step 15**
Commit: `feat: implement authoritative playback model`.

## 必须完成

### 测试

至少执行：

- Task4 Queue tests；
- History tests；
- AutoPlay tests；
- Playback Service tests；
- 受影响的 Task2R regression；
- 受影响的 Task3 regression；
- 全局 Python tests；
- compileall；
- Ruff；
- 必要时运行类型检查。

### 代码审查

必须检查：

- API → Service → Repository/PlayerPort 边界没有被破坏；
- Service 未依赖未来 Task；
- Queue / History / PlaybackContext 独立；
- MPD 仅通过 PlayerPort；
- AutoPlay 不覆盖 MANUAL；
- Queue transaction/CAS 正确；
- Stop / Pause / exhaustion 语义正确；
- 真实音乐文件保持只读；
- 没有无关文件修改；
- diff --check 通过。

### Git

必须确认：

- branch = `feature/task-4-playback`
- HEAD 正确；
- 工作区状态正确；
- changed files 仅属于 Task4；
- commit message 正确；
- 远端 branch ref 已更新；
- commit SHA 通过远端读取再次确认。

Batch6 完成后，**不要自动合并 main**。Task4 应先进入独立的最终 Task 验收和 PR 流程。

---

# 10. 每个 Batch 开始窗口的统一提示词

使用下面模板。只替换 `<BATCH>`、`<STEP>`、`<PREVIOUS_COMMIT>`。

```text
继续实施 MPD-Server Task 4。

**本次使用全新 AI 窗口。不要相信上一窗口的口头描述，必须以当前仓库实际状态、规格书和 Plan 为准。**

请先阅读：
1. docs/superpowers/specs/ 下与 Task 4 及其前置依赖相关的规格
2. docs/superpowers/plans/2026-09-25-mpd-server-v0-1-implementation-plan.md
3. docs/superpowers/plans/2026-09-28-mpd-server-task-4-batch-plan.md
4. docs/mpd-0.23.5-capabilities.md
5. 当前仓库实际代码、当前 branch、HEAD、提交历史及工作区状态

当前 Task：
Task 4：Queue、Playback Context、History、AutoPlay、Playback Service

当前 Batch：
<BATCH>

本次只实施：
Step：<STEP>

上一 Batch 预计 commit：
<PREVIOUS_COMMIT>

**特别要求：**
- 必须先检查当前实际 branch 是否为 feature/task-4-playback。
- 必须确认上一 Batch commit 是否真实存在于当前分支历史。
- 必须确认工作区、HEAD、changed files。
- 必须重新核对 Plan 中 Task 4 的 dependencies、Dependency Matrix 和 Execution Order。
- 必须重新验证已经完成的历史 Step，不得只根据 Plan [x] 或上一窗口报告判断。
- 如果仓库实际状态与上一窗口描述不一致，以仓库 + Specs + Plan 为准。

严格执行我一直使用的 Task 实施模板：
- 严格禁止越界修改。
- 严格执行 TDD：RED → 最小实现 → GREEN → diff 检查。
- 不得修改测试语义来制造 GREEN。
- 不得删除失败测试。
- 不得 mock 掉本来必须验证的真实行为。
- 不得提前实现未来 Task。
- 不得绕过 Repository / Service / PlayerPort / DomainEvent 等既有契约。
- 不得引入未来 Task 的 API、WebSocket、config 或其它实现。
- 真实音乐文件严格只读。
- 正确区分代码问题与环境问题。
- ENV-BLOCKED / PHYSICAL-VALIDATION-PENDING 不得伪装成 GREEN。
- 如果环境缺失但不影响后续生产实现，可以继续并单独记录。
- 如果环境结果直接决定本 Batch 或后续 Batch 的生产实现，则必须在依赖边界停止。
- 每个 Step 完成后检查测试、diff --check、changed files、未来 Task 依赖和架构边界。

**Batch 边界：**
只允许修改本 Batch 的文件和为满足本 Batch 所必需的既有 Task4 文件。
不得顺手实现下一 Batch。

完成本 Batch 后：
1. 运行本 Batch focused tests；
2. 运行受影响的历史 Task regression；
3. compile / lint（在环境允许时）；
4. 检查完整 diff；
5. 检查工作区；
6. 按 Plan 要求提交 commit；
7. 提交后重新读取远端 branch/ref 和 commit SHA，确认提交真实存在；
8. 不要合并 main；
9. 输出详细 Batch 结束交接摘要。

最终汇报必须按 Batch 交接模板输出，不得只说“完成”。
```

---

# 11. 每个 Batch 结束窗口的统一总结模板

完成后要求 AI 按以下格式汇报：

```text
【Task 4 Batch <N> 结束交接】

1. 本次实际范围
- Task: Task 4
- Batch: <N>
- Plan Steps: <X-Y>
- 实际执行到：Step <...>

2. Step 状态
- Step X: COMPLETE / IMPLEMENTED-ENV-BLOCKED / PHYSICAL-VALIDATION-PENDING / BLOCKED
- Step Y: ...

每个 Step 必须说明：
- RED：PASS / 环境阻塞
- GREEN：PASS / 未执行 / 环境阻塞
- 最终状态

3. 实际修改
新增：
- ...

修改：
- ...

删除：
- ...

并说明每个文件为什么属于本 Batch。

4. 测试
逐项写实际运行命令和实际结果：
- focused tests:
- regression:
- compile:
- lint:
- 其它：

不得把未执行测试写成 PASS。

5. 环境 / 实机待验证
如果存在：
- 测试目的：
- 当前环境：
- 阻塞原因：
- 完整测试命令：
- 预期结果：
- 失败时需要收集：
- 是否影响下一 Batch：

如果不存在，明确写：
NONE

6. Specs / Plan / code 冲突
- NONE
或列出具体冲突、文件、影响和当前状态。

7. 依赖状态
- Task4 前置依赖是否满足：
- 上一 Batch commit 是否真实存在：
- 是否引入未来 Task：
- 是否存在未验证的后续依赖：

8. Git 状态
- branch:
- HEAD:
- workspace:
- changed files:
- commit SHA:
- commit message:
- remote branch:
- remote ref / HEAD 二次确认：
- commit 是否已真实存在于远端：

9. 历史 Step 证明
- 可以证明：
- 部分证明：
- 无法证明：

10. 下一 Batch 交接
- 下一 Batch：
- 下一 Batch Steps：
- 本 Batch commit：
- 下一窗口必须重新确认的事项：
- 已知风险：
- 必须避免的越界：

11. 最终判定
只能使用：
COMPLETE
PARTIALLY COMPLETE — ENVIRONMENT VALIDATION PENDING
PARTIALLY COMPLETE — BLOCKED
BLOCKED BY DEPENDENCY

不得因为“代码写完”自动判定 COMPLETE。
```

---

# 12. Batch 间最小交接信息

新窗口实际上只需要知道：

```text
Task 4
Batch N
Steps X-Y
上一 Batch commit SHA
feature/task-4-playback
```

其它内容一律重新从仓库读取。

不要复制上一窗口的大段代码解释、聊天记录或未经验证的判断。

---

# 13. Task4 最终完成后的处理

Batch6 完成并确认 Task4 所有 15 Steps 后：

1. 再做一次完整 Task4 verification；
2. 核对原 Plan 中 Task4 的 15 个 checkbox；
3. 核对 Task4 本身与 Specs 的覆盖；
4. 核对 changed files / diff；
5. 确认没有未来 Task 依赖；
6. 确认 branch / commit / remote ref；
7. 再决定创建 PR 并合并 `main`。

**Batch6 commit 成功 ≠ Task4 已自动进入 main。**
