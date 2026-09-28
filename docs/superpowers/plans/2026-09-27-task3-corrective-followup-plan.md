# Task 3 Corrective Follow-up Plan

> 项目：MPD-Server  
> 基准：当前 `main`  
> 目标：在进入 Task 4 之前，修复 Task 3 审计发现的跨模块契约缺口，并消除会影响后续 Task 的歧义。  
> 本文件是**修复执行计划**，不是对当前实现的自动授权；执行时仍必须以仓库当前 `main`、现行规格书和 implementation plan 为最终依据。

---

## 1. 当前基准与结论

当前 `main`：

```text
d513e191893e8e038fe71ced57401c1f435b8ec0
Merge pull request #9
feat: add library scanner and metadata pipeline
```

Task 3 当前在 implementation plan 中被标记为 Step 1～12 全部完成。

本次审计确认：

1. Task 3 的媒体元数据解析、歌词解析、扫描器、watcher、scheduler、domain event 已经存在。
2. Task 3 的主要实现路径和测试体系符合整体架构方向。
3. 但存在**确定的跨模块契约缺口**，这些问题在当前 Task 3 测试中没有被端到端覆盖。
4. 因此，在进入 Task 4 前，应完成本文件定义的 corrective follow-up。
5. 不得通过直接修改 Task 4 或 Task 5 代码来绕过这些缺口。
6. 不得把这些修复偷偷混入下一 Task；需要保持独立、最小、可审计的修复批次。

---

## 2. 严格适用的上位约束

执行本修复时仍同时受以下文档约束：

```text
docs/superpowers/specs/
  2026-09-24-playback-model-queue-semantics-design.md
  2026-09-24-library-playlist-tag-search-design-2-1.md
  2026-09-24-system-architecture-playback-output-design.md
  2026-09-25-system-and-development-architecture-design.md

docs/superpowers/plans/
  2026-09-25-mpd-server-v0-1-implementation-plan.md

docs/mpd-0.23.5-capabilities.md
```

必须继续遵守 implementation plan 的全局规则：

- TDD：RED → 最小实现 → GREEN → 回归 → diff review。
- Task 依赖不可反向穿越。
- API 不直接访问 Repository/MPD。
- Service 不依赖具体 MPD Adapter。
- Scanner 不依赖 API、WebSocket 或最终 `config.py`。
- Task 3 不实现 WebSocket。
- 音乐目录严格只读。
- 不使用真实音乐目录作为可变测试 fixture。
- 每个修复批次完成后重新检查 changed-file list、`git diff --check`、相关测试和远程 commit/ref。
- 未通过依赖门时不得进入 Task 4。

---

# 3. 修复总顺序

必须按以下顺序执行：

```text
Batch 0
  重新建立当前基线与问题证据
        ↓
Batch 1
  Lyrics observability contract hardening
        ↓
Batch 2
  LRC sidecar incremental scan contract
        ↓
Batch 3
  Available Songs query contract hardening
        ↓
Batch 4
  Scanner / Repository move-matching contract alignment
        ↓
Batch 5
  Artwork reference lifecycle hardening
        ↓
Batch 6
  Task 3 final re-acceptance + Plan/README consistency
        ↓
Task 4 dependency gate
```

### 为什么是这个顺序

- Batch 1 先修复已经确认会丢失的数据语义，这是最明确、最基础的契约问题。
- Batch 2 建立增量扫描行为，直接依赖 Task 3 scanner/watch 现有接口，不应和数据库结构修改混在一起。
- Batch 3 在 Task 4 开始前明确“可用歌曲”来源，避免 Task 4 自己猜 Repository/API。
- Batch 4 再统一 move matching 的边界，避免重复身份匹配逻辑继续分叉。
- Batch 5 是 artwork 生命周期问题，不影响 Task 4 核心播放模型，但必须在 Task 5 artwork API 使用该引用前解决。
- Batch 6 只做最终验证、文档状态统一和依赖门检查，不新增业务功能。

---

# 4. Batch 0：建立当前基线

## 4.1 目标

只确认问题，不修改生产代码。

## 4.2 必须重新检查

AI 必须重新读取：

```text
当前 main HEAD
implementation plan
四份 specs
docs/mpd-0.23.5-capabilities.md
README.md
```

重点确认：

```text
Task 3 当前 checkbox
Task 4 dependencies
Task 2R contracts
Task 3 files/allowed scope
```

## 4.3 必须确认的事实

至少确认以下三条：

### A. Lyrics 信息丢失

当前链路：

```text
parse_media_file()
    ↓
ParsedSongMetadata
    ↓
LibraryScanner
    ↓
Song
    ↓
LibraryRepository
    ↓
SQLite
```

`ParsedSongMetadata` 有：

```text
lyrics
lyrics_format
lyrics_source
lyrics_status
```

而当前 `Song` / `songs` persistence contract 没有完整保存：

```text
lyrics_source
lyrics_status
```

因此：

```text
missing
```

和：

```text
sidecar read_error + embedded fallback
```

进入持久化层后不能保持完整可区分状态。

### B. LRC 增量扫描

当前 `LibraryWatch` 能接收任意 Path，但 `LibraryScanner.scan_paths()` 当前只直接处理：

```text
.flac
.mp3
```

因此：

```text
track.lrc changed
    ↓
watcher
    ↓
scan_paths(track.lrc)
    ↓
unsupported suffix
    ↓
ignored
```

导致 sidecar LRC 的独立变更不能立即触发对应音频重新解析。

### C. Task 4 的 Available Songs contract 不清晰

Task 4 明确依赖：

```text
Task 3 available-library queries
```

但当前已完成的 Repository 公开 contract 中，没有明确的：

```text
list_available_songs()
```

等统一查询边界。

禁止让 Task 4 自己：

```text
查询所有 Song
→ 自己猜 availability 字段
→ 自己定义过滤规则
```

必须在进入 Task 4 前先冻结该 contract。

## 4.4 Batch 0 输出

只允许产生：

```text
问题确认记录
修复批次执行顺序
允许修改文件清单
```

不得修改生产代码。

---

# 5. Batch 1：Lyrics Observability Contract Hardening

## 5.1 问题

这是当前最明确的跨 Task 3 / Task 2R 契约缺口。

Parser 已经区分：

```text
lyrics_source:
  sidecar
  embedded
  null

lyrics_status:
  available
  missing
  read_error
```

但持久化模型没有完整保留这两个字段。

## 5.2 修复目标

必须保证：

```text
media file
 → parser
 → scanner
 → Song/domain model
 → repository
 → SQLite
 → get_song()
```

全链路保留：

```text
lyrics
lyrics_format
lyrics_source
lyrics_status
```

且：

```text
sidecar valid
sidecar read/parse failure with embedded fallback
embedded only
missing
```

四类状态不能重新合并。

## 5.3 严格边界

这里存在一个重要的 Superpowers scope 问题：

`lyrics_source` / `lyrics_status` 属于 Song persistence contract，因此修复很可能需要触及：

```text
server/app/models/library.py
server/app/repositories/migrations.py
server/app/repositories/library_repository.py
```

这些不是当前 Task 3 implementation list 中的新增文件。

因此：

> **禁止为了“完成 Task 3”而直接偷偷扩大 Task 3 scope。**

应把本批次定义为：

```text
Task 3 corrective prerequisite hardening
```

并通过一个独立的小修复提交完成。

若 implementation plan 的当前文字不允许这个修复，应先增加明确的 corrective hardening 节，而不是在 Task 3 代码中绕过。

## 5.4 建议最小修改范围

优先只允许：

```text
server/app/models/library.py
server/app/repositories/migrations.py
server/app/repositories/library_repository.py
server/tests/repositories/*
server/tests/services/test_media_metadata.py
server/tests/services/test_library_scanner.py
```

如测试需要，才增加对应专项测试文件。

禁止：

```text
API
WebSocket
Task 4
Task 5
config.py
```

## 5.5 TDD 要求

先写 RED：

1. `Song` 可以表达 `lyrics_source`。
2. `Song` 可以表达 `lyrics_status`。
3. 数据库可以持久化并读回这两个字段。
4. Scanner 将 Parser 结果完整映射到 Song。
5. sidecar valid → `available/sidecar/lrc`。
6. sidecar read/parse failure + embedded fallback →
   `read_error/embedded/text`。
7. missing → `missing/null/null`。
8. 已知良好记录发生解析失败时不能覆盖既有有效歌词状态。

先运行 RED，再实现。

## 5.6 Batch 1 验收

必须至少通过：

```text
Parser focused tests
Scanner focused tests
Repository focused tests
existing Task 2R regression tests
compileall
ruff on changed scope
git diff --check
changed-file review
```

此外必须进行一次跨层断言：

```text
parse result
==
scanner Song
==
repository get_song result
```

## 5.7 完成条件

只有确认“歌词状态从 parser 到数据库再读回完全不丢失”后，才能进入 Batch 2。

---

# 6. Batch 2：LRC Sidecar Incremental Scan Contract

## 6.1 问题

当前 watcher 可以看到 `.lrc` 变化，但 scanner 不会把 `.lrc` 当作需要重新解析关联音频的输入。

这违反 Task 3 的：

```text
sidecar LRC changes are independently detected
```

## 6.2 修复目标

当收到：

```text
/path/track.lrc
```

事件时，系统应找到同 stem 的支持音频文件并重新扫描其 metadata。

推荐确定为：

```text
track.lrc
    ↓
track.flac
track.mp3
```

### 情况 A：只有一个对应音频

扫描该音频。

### 情况 B：同时存在 `.flac` 与 `.mp3`

由于同 stem sidecar 的语义本身可以同时适用于两个音频文件，允许把两个对应音频都加入一次去重后的 scan batch。

### 情况 C：没有对应音频

无对应 Song，事件变更无需生成扫描任务。

### 情况 D：LRC 删除

删除事件也必须触发对应音频重新扫描，以便将歌词更新为：

```text
embedded
```

或者：

```text
missing
```

而不是永久保留旧歌词。

## 6.3 建议修改范围

只允许：

```text
server/app/services/library_watch.py
server/app/services/library_scanner.py
server/tests/services/test_library_watch.py
server/tests/services/test_library_scanner.py
```

必要时修改对应 Task 3 service tests。

禁止：

```text
Repository schema
Task 4
API
WebSocket
config.py
```

## 6.4 TDD 测试必须包含

### 新增/修改 LRC

```text
notify(track.lrc)
→ 关联 audio 被扫描
```

### 删除 LRC

```text
track.lrc deleted
→ 关联 audio 被重新扫描
```

### 去重

```text
track.lrc
track.lrc
track.mp3
```

同一批不能重复扫描。

### 两种音频同 stem

```text
track.flac
track.mp3
track.lrc
```

两首关联 audio 都能被正确重新扫描。

### 无对应 audio

不得制造虚假 Song。

### 音频本身变化

现有 `.mp3/.flac` 逻辑必须不受影响。

### 完整扫描

`scan_full()` 对 `.lrc` 语义保持正确；不能因为增量逻辑修复而改变 full scan 的生命周期语义。

## 6.5 完成条件

必须证明：

```text
LRC change
→ watcher batch
→ scanner
→ parser
→ updated Song
```

完整闭环可运行。

---

# 7. Batch 3：Available Songs Query Contract Hardening

## 7.1 问题

Task 4 依赖 Task 3 提供“可用歌曲”。

当前没有冻结明确的上层读取 contract。

## 7.2 修复目标

必须定义一个明确、可复用的 contract，表达：

```text
return Songs that are currently AVAILABLE
```

并保证：

```text
MISSING 不返回
UNREADABLE 不返回
AVAILABLE 返回
```

此 contract 应成为 Task 4 AutoPlay 的唯一数据入口之一。

## 7.3 Scope 原则

这个问题本质上属于“Task 4 的前置 contract”。

因此：

> **不要在 Task 4 中临时实现过滤逻辑。**

优先在现有 Library Repository contract 中提供明确查询能力，或在一个已经属于前置层的 service/contract 中冻结该能力。

由于当前 Task 5 才定义 `LibraryService`，不能为了这个 contract 把 Task 5 提前实现。

## 7.4 推荐方案

优先考虑：

```text
LibraryRepository.list_available_songs()
```

而不是让调用者：

```text
list all songs
→ 自己过滤
```

contract 至少明确：

```python
async def list_available_songs() -> list[Song]: ...
```

实现层只按：

```text
availability_status = AVAILABLE
```

过滤。

## 7.5 允许修改范围

优先：

```text
server/app/repositories/library_repository.py
server/tests/repositories/*
```

必要的 contract/model 调整只能保持最小范围。

如果 implementation plan 现有文件清单不包含这项前置 contract，应先作为 prerequisite hardening 明确记录，再实施。

禁止：

```text
Task 4 production code
Task 5 LibraryService
API
WebSocket
```

## 7.6 TDD

必须测试：

```text
AVAILABLE → included
MISSING → excluded
UNREADABLE → excluded
empty library → []
mixed library → only AVAILABLE
stable ordering
```

以及：

```text
song becomes MISSING
→ next list_available_songs() no longer returns it

song becomes AVAILABLE
→ next list_available_songs() returns it
```

## 7.7 完成条件

Task 4 可以在不读取 SQLite、不自己猜状态、不依赖 Task 5 的情况下获得明确的 Available Songs 数据。

---

# 8. Batch 4：Scanner / Repository Move Matching Contract Alignment

## 8.1 问题

Scanner 已有更严格的规则：

```text
exact URI
→ unique identity + old path no longer exists
→ unique content hash among MISSING
→ ambiguous = no match
```

而 Repository 的 `apply_scan_batch()` 自己还保留 identity matching fallback，其条件比 Scanner 更宽。

这可能导致未来其它调用者绕开 Scanner 的安全规则。

## 8.2 修复目标

必须使：

```text
Scanner semantics
=
Repository persistence boundary semantics
```

至少不能出现：

```text
Scanner 不会把 live copy 当 move
Repository fallback 却可能把 live copy 当 move
```

## 8.3 原则

Repository 不应新增 filesystem 业务依赖。

不能为了判断旧文件是否存在而把：

```text
Path.stat()
```

塞进 Repository。

应通过 persistence contract 本身表达“只有安全候选才可复用”。

## 8.4 推荐方向

优先使 Repository 的内部 fallback 只允许安全候选，例如：

```text
identity match
+
candidate availability/status 满足可迁移条件
```

或者确保 Scanner 在进入 atomic batch 前已经提供明确的 `song_id`，并将 Repository 的 fallback 限制为不会违反稳定身份规则的情况。

具体实现前必须：

1. 重新阅读 Task 2R spec。
2. 明确哪一层负责“是否是 move”。
3. 不新增第二套独立 matching algorithm。

## 8.5 必须测试

```text
live copy with same identity → new Song
unique missing candidate → reuse Song ID
ambiguous identity → new Song
ambiguous content hash → new Song
exact URI → existing Song
move → same Song ID
```

还必须增加跨层测试：

```text
Scanner result passed to Repository
```

和：

```text
direct repository atomic batch contract
```

二者不产生冲突语义。

## 8.6 完成条件

不存在两个互相矛盾的 move identity 规则。

---

# 9. Batch 5：Artwork Reference Lifecycle Hardening

## 9.1 问题

当前使用：

```text
album_art_refs
one preferred artwork reference per album
```

Scanner / Repository 会在发现 artwork 时更新 ref。

但如果重新扫描时某一歌曲已经没有 embedded artwork，当前 persistence path 没有完整定义：

```text
old artwork ref 是否失效
是否删除
是否切换到同 album 的其它可用歌曲
```

因此可能留下 stale artwork reference。

## 9.2 重要限制

这项问题不应为了修 Task 3 而提前实现 Task 5 artwork API。

它应该解决“persistence contract”，而不是实现 HTTP artwork endpoint。

## 9.3 推荐处理原则

必须先明确：

1. 一个 album 只有一个 preferred ref。
2. ref 指向 source song + picture index。
3. source song 不再提供该 picture 时，旧 ref 不能无限期继续被视为有效。
4. 如果 album 还有其它有效 embedded artwork，可按确定规则选择其它 ref。
5. 如果没有有效 artwork，则 album 应处于“无 artwork reference”状态，而不是返回旧数据。

## 9.4 允许修改范围

优先：

```text
server/app/repositories/library_repository.py
server/app/models/library.py
server/tests/repositories/test_library_reconciliation.py
```

必要时才添加针对 artwork lifecycle 的最小测试。

禁止：

```text
Task 5 API
Web
WebSocket
```

## 9.5 完成条件

必须有测试证明：

```text
artwork present
→ reference present

artwork removed from referenced source
→ stale reference no longer treated as valid

another valid artwork exists
→ deterministic replacement

no valid artwork exists
→ no stale reference
```

---

# 10. Batch 6：最终 Task 3 Re-acceptance

本批次**禁止新增业务功能**。

只做：

```text
focused tests
relevant prior-task regressions
full server tests
compileall
ruff
diff review
changed-file review
plan consistency
README consistency
remote ref verification
```

## 10.1 必须重新执行

至少：

```text
Task 3 service tests
Task 2R repository tests
Task 1R player regression tests
health test
full server/tests
python -m compileall -q server
python -m ruff check server
```

前端：

```text
npm --prefix web run typecheck
npm --prefix web run build
```

只有被本次修复影响到时才要求重新跑前端；若没有前端改动，应明确记录为 unaffected。

## 10.2 必须进行 diff 检查

必须确认：

```text
没有 Task 4 production code
没有 Task 5 production code
没有 Task 6 production code
没有 config.py
没有 WebSocket
没有 API
没有不相关 refactor
```

并执行：

```text
git diff --check
```

## 10.3 必须检查 Plan

不要删除历史 Task 3 verification record。

应该保留历史记录，同时增加一个明确的 corrective follow-up 记录，例如：

```text
Task 3 corrective follow-up
- Batch 1 ...
- Batch 2 ...
- Batch 3 ...
- Batch 4 ...
- Batch 5 ...
- Final re-acceptance ...
```

每批记录：

```text
RED
GREEN
focused verification
regression
diff review
commit
remote ref
```

## 10.4 README

最终 README 不得再写：

```text
下一阶段：Task 3 开始实现
```

应反映实际：

```text
Task 3 已完成并经过 corrective follow-up acceptance
```

但不要提前描述 Task 4 已实现的功能。

---

# 11. 每个 Batch 的通用 Superpowers 执行协议

每一批严格执行：

```text
1. 从当前分支实际 HEAD 开始
2. 重读该 Batch 的相关 spec/plan
3. 确认 dependency gate
4. 确认 allowed files
5. 写最小 RED test
6. 运行 RED
7. 实现最小修复
8. 运行 GREEN
9. 运行相关 regression
10. git diff --check
11. changed-file review
12. 检查是否存在 scope creep
13. commit
14. push
15. 二次确认 remote branch/ref
16. 记录验证结果
17. 才允许进入下一 Batch
```

## 绝对禁止

```text
- 不根据旧窗口口头状态推断完成
- 不直接从旧 task3 分支继续
- 不在 Task 3 修复时顺便实现 Task 4
- 不提前实现 LibraryService
- 不提前实现 PlaybackService
- 不提前实现 API
- 不提前实现 WebSocket
- 不提前实现 config.py
- 不为了通过测试而删除真实边界
- 不把历史 RED 当作当前 failure
- 不把“代码存在”当作“契约成立”
- 不因为一个问题很小就跳过 RED/GREEN
- 不一次修改整个 repository architecture
```

---

# 12. 批次之间的状态门

## Gate 1

必须满足：

```text
Lyrics parser → Song → SQLite
```

语义完整无丢失。

否则不得进入 Batch 2。

## Gate 2

必须满足：

```text
LRC filesystem event
→ associated audio scan
```

增量行为正确。

否则不得进入 Batch 3。

## Gate 3

必须存在稳定的：

```text
Available Songs query contract
```

否则不得进入 Task 4。

## Gate 4

Scanner 与 Repository move matching 不得存在安全语义冲突。

否则不得开始使用 move semantics 的更高层业务。

## Gate 5

Artwork reference lifecycle 有明确 contract 和测试。

此 Gate 在进入 Task 5 artwork API 前必须通过。

---

# 13. 预期最终状态

完成本文件后，Task 3 应满足：

```text
Media Parser
    ↓
Scanner
    ↓
Song domain
    ↓
Repository
    ↓
SQLite
```

信息不丢失。

并且：

```text
Audio file change
LRC file change
file move
file delete
unreadable file
```

都进入确定、可测试、可追踪的 reconciliation 行为。

同时 Task 4 可以通过明确 contract 获得：

```text
AVAILABLE Songs
```

而不需要自己重新定义 Library persistence semantics。

最终依赖关系应保持：

```text
Task 1R
   ↓
Task 2R
   ↓
Task 3 corrective follow-up
   ↓
Task 4
```

而不是：

```text
Task 3
   ↓
Task 4 临时补 contract
   ↓
Task 5 再回头修 Task 3
```

---

# 14. 完成判定

只有同时满足以下条件，才允许认为“Task 3 corrective follow-up 已完成”：

- 所有确定的 cross-layer contract issue 已关闭。
- 新增测试先出现 RED，再 GREEN。
- Task 3 focused tests 全部通过。
- Task 2R 相关 regression 全部通过。
- 全局 Python tests 通过。
- compileall 通过。
- Ruff 通过。
- diff 无越界修改。
- 远程 commit/ref 已二次核对。
- Plan 中 corrective follow-up 有独立验证记录。
- README 与实际 main 状态一致。
- Task 4 所需 Available Songs contract 已冻结。
- 不需要在 Task 4 中重新发明 Task 3 的 Library 语义。

在此之前：

```text
不要开始 Task 4 Step 1。
```

---

# 15. 对问题级别的最终分类

| 问题 | 当前级别 | 是否必须在 Task 4 前修复 |
|---|---|---|
| `lyrics_source` / `lyrics_status` 持久化丢失 | 确定的跨层契约缺口 | **是** |
| `.lrc` 增量事件无法触发关联音频重扫 | 确定的 Task 3 行为缺口 | **是** |
| Available Songs contract 未冻结 | Task 4 前置契约缺口 | **是** |
| Scanner / Repository move matching 规则略有分叉 | 一致性/安全边界问题 | **是，至少完成 contract alignment** |
| Artwork reference 生命周期可能留下 stale ref | 持久化生命周期缺口 | **Task 5 artwork API 前必须解决** |

---

# 16. 不属于本修复计划的内容

以下不应借本次修复提前实现：

```text
Task 4
- Queue Manager
- AutoPlay
- Playback Service
- Playback state orchestration

Task 5
- LibraryService
- PlaylistService
- CollectionService
- REST API
- artwork API

Task 6
- WebSocket
- FullStateSnapshot

Task 7
- Output Manager
- MPD About API

Task 8+
- Web player / PWA UI

Task 10+
- config.py
- backup
- logging
- deployment updater
```

这些仍严格按照 implementation plan 的 dependency matrix 执行。
