# MPD-Server Playback Executor Refactor — MS Queue / MPD Bounded Buffer

> **Status: CONTRACT FROZEN / IMPLEMENTATION NOT STARTED / LIVE MPD NOT RUN**  
> 日期：2026-10-12；工作分支：`refactor/mpd-bounded-execution`；**精确基线** `feature/task-9-web` @ `098d6eaea81495d1686a09f9e0ee68768610ed7e`（Task9 + NAS Final B07/CI文档最新commit）。  
> 本次只冻结合同并规划实施，不执行Batch、不修改产品、测试、数据库、容器、不触发真实MPD操作，不建PR、不合并main/Task9。基线不是当前main；正式集成要另行审计Task9及Final NAS并行变动。

## 1. 决策、事实及唯一权威

**用户决定（2026-10-12修订冻结）**：MS唯一管理完整业务Queue、Current occurrence、Played/History、AutoPlay、Next/Previous、元数据/曲库；**MPD唯一提供Web正在播放/暂停/停止、实际当前曲目、实际进度**。Web下一首/再下一首和待播仅取MS Queue，不从MPD获取UI顺序。MPD稳态缓冲当前+两首预备≤3、瞬态≤4；MS后台必须由idle+轮询+每次控制前后实采样始终掌握MPD实际current/next/next-next，不靠MS命令日志推断。

- **长期领域唯一权威**：[Playback Spec §8.10](../specs/2026-09-24-playback-model-queue-semantics-design.md) `PB-BUF-*`。旧 §8.9 对完整队列同步的**执行约束被替换**，其History保守证明、业务语义、Stop/Context等仍继承。
- **跨模块/部署权威**：[Architecture §6/§12/§19.5](../specs/2026-09-25-system-and-development-architecture-design.md)；[Output Architecture §2](../specs/2026-09-24-system-architecture-playback-output-design.md)。唯一Web视觉规范仍归原Visual Spec。
- **历史证据**：Task4 D6 corrective和 Task9 B10 acceptance 不等于新执行器验收。真实NAS MPD 0.23.5协议 probe、最近部署能力证据需在后续真实环境刷新，不能因命令存在宣称组合行为通过。
- **当前真实实现（审计输入、非未来规范）**：`PlaybackService._sync_player_queue`将全部DB待播映射到MPD；`ExecutionSynchronizer.execute`每条命令前后读取 `read_execution_sample`（MPD `status→playlistinfo→status`）；`_atomic_history_transition`/SQLite共同事务期间等待MPD网络；`RecoveryJournal.accepts`比较完整映射和playlist版本；`QueueView`可能请求大量pending元数据。它们是需替换/回归的代码路径，不是用户界面或业务模型重做授权。
- **已知实机症状**：用户NAS CI镜像对约400首随机播放观察到UI长时间不同步、Queue控制阻塞、实际MPD疑似切歌但显示裸文件URI；未拿到双边同期只读状态/日志前，不能把根因断言为单一竞态或宣称新方案已解决。
- **阶段策略**：保留旧 Task9 能用的单曲和页面；新分支逐Batch TDD，真实NAS明确验收前不替换旧部署，不自动merge/发布。

## 2. Contract Impact / 继承与替换清单

| 已有合同/实现 | 裁决 | 精确边界 |
|---|---|---|
| Playback Spec §2–7 / PB-SONG-NOW-001 | **INHERIT** | Queue Item ID、重复、MANUAL、Context、普通与Queue Play Now、Played、Stop provenance、API/HTTP idempotency及业务History、PlayNext/Add/清空待播语义不变；原 pending unavailable 整次拒绝暂保留 |
| PB-CURRENT/BINDING/QUEUE-ADOPT / §8.9.1–3 | **REPLACE EXECUTION ONLY** | MS业务current仍以可信occurrence推进；Web实际current/状态/进度只以MPD实时采样表示，即使未业务绑定也可显示实态；以三首实际执行缓冲替换全部MPD队列映射 |
| PB-HISTORY / UNCERTIFIED / §8.9.4 | **INHERIT** | 无natural因果证明；不虚构missed项；只登记确证的显式离开/活动 |
| PB-AUTOPLAY-EXEC / §8.9.5 | **REPLACE TRANSPORT** | AutoPlay低水位/候选/来源不变；只向MPD预备当前后的两首，不同步batch/所有pending；Web Next仍MS Queue |
| PB-RECOVERY-RETRY/RECOVERY-RUNNER / §8.9.6–7 | **REPLACE EXECUTION, INHERIT SAFETY** | 保留未知前缀、token、fail-closed、独立1s调度和恢复只读分离；执行器不持长SQLite事务 |
| Architecture §4/§12, Task8/Task9 UI + Output/URI | **INHERIT + ADDITIVE ACTUAL STATE** | 保留API/WS epoch/sequence/旧DTO及Output，按§8.10.7增加actual_song/实际进度可选字段；Web Next仍取MS Queue，通知仅在AppBar |
| Task9 Final NAS/Task4历史验收 | **HISTORICAL** | 旧运行方式有效记录，不自动给新执行器 GREEN；不把旧计划文本作为额外权威 |

任何发现与既有已接受业务定义冲突：**先更新Playback唯一Spec，再本plan矩阵，再写RED invariants**；不能为了让Mock GREEN随意改用户业务语义。

## 3. Cross-Authority Contract Matrix（REQUIRED / FROZEN）

共同字段 `D0` 适用于全部下列行：**P**＝已核对Task9基线，单owner/经能力验证的MPD Port，可读取对应已提交业务代次；**A**＝SQLite Queue/Playback/History/Context/AutoPlay拥有业务，MPD拥有播放实际事实，Service执行器拥有临时ID绑定/操作记录，API/WS/Web只传播；**Δ**＝仅目标行定义业务与外部变化；**U**＝其它业务occurrence、已确认History、Library/Playlist/Favorites、音乐只读、Output与用户已验收Web布局不改变；**X**＝真实MPD样本/命令返回+可归属current确认，不用单URI推断；**H**＝未知自然原因不造History，成功事件仅outer commit后；**T**＝单owner业务fence与短SQLite事务，不在SQLite写锁内等MPD；**F**＝外部副作用无法SQL rollback，unknown不伪报；**R**＝同key success replay零再执行，命令响应不明不盲重发；**O**＝原API/WS确认/降级与诊断；**E**＝本表列明的真实关系proof及对应旧回归，新代码未建/未跑。以下是**D0增量**, 完整合同按 D0 + 行特有约束组成：

| ID / type | Preconditions + Δ / 必须不变 | External confirmation / H/T/F/R/O 增量 | Executable invariant proof（TO CREATE） |
|---|---|---|---|
| **PB-BUF-AUTH-001** STATE_TRANSITION | N=0/1/400，重复URI和Played/MANUAL/AUTOPLAY；仅业务Queue排序与occurrence改变 | MPD playlist不导出业务Queue；提交后原全量列表及revision一致；无执行时不写MPD | `test_buf_authority.py`：400、重复、Played、context、未绑定读取 |
| **PB-BUF-EXEC-001** STATE_TRANSITION | 受控执行短缓冲steady≤3/瞬态≤4；不把400首推MPD | 真实MPD id/URI/current确认，不能用ACK冒充；版本/连接/模式fence | `test_buf_executor.py`：3/4上限、重复URI、响应不明与实际进位 |
| **PB-BUF-PLAY-001** STATE_TRANSITION | 明确Start/集合/普通Song/Queue/Played/Next/Previous；业务occurrence精确 | 真current+uri+state确认后提交；未确认不建History；不修改其它待播 | `test_buf_playback_actions.py`：各入口+重复URI/Stop/Context |
| **PB-BUF-TAKEOVER-001** LIFECYCLE | unbound/legacy400/foreign/STOPPED；**只有用户明确选歌**授权 | 读实际mode/playlist；一次性安全清理/接管；未知结果失败，不在重启或GET清空 | `test_buf_takeover.py`：400旧队列、断线、模式、重启只读 |
| **PB-BUF-NEXT-001** STATE_TRANSITION | MPD A→B/→C；旧A未清理时B实际位置可为1 | 新MPD样本确认后才接纳B；不重复playid；按真实顺序补两个后续，不虚构漏播历史 | `test_buf_natural_advance.py`：position1/重复/pausing/race |
| **PB-BUF-QUEUE-001** TRANSACTION | Add/PlayNext/reorder/delete/clear；只有触及物理预备两项才需MPD改变 | 实际采样+业务CAS重排受控预备项；不能假成功；Web下一首仍业务Queue | `test_buf_queue_mutations.py`：删除next/next-next、自然进位竞争 |
| **PB-BUF-AUTO-001** STATE_TRANSITION | 低水位5/每批5，候选和Queue属MS | 仅把最多两个业务后续放MPD；PAUSED不强启、UNKNOWN/STOP不自动启动 | `test_buf_autoplay.py`：提前2首/批次/故障 |
| **PB-BUF-MODE-001** STATE_TRANSITION | random/repeat/single/consume适配与能力门禁 | 明确取得控制权时校验/配置四模式；日常GET/runner不可覆盖外部模式；未知失败闭锁 | `test_buf_modes.py`：各模式、能力缺失、外部改变 |
| **PB-BUF-TRANSPORT-001** STATE_TRANSITION | 已绑定token + PAUSED/PLAYING | Pause/resume/seek实态+token确认；不addid、重启或改变Queue/History | `test_buf_transport.py`：resume原位、seek迟到、token冲突 |
| **PB-BUF-TX-001** TRANSACTION | 固定op+revision+代次，外部命令期间SQLite另有只读/业务读 | MPD ACK非commit；SQL commit/terminal失败回滚业务但保留unknown命令前缀，无成功通知 | `test_buf_transaction.py`：锁释放barrier、commit失败、取消、response lost |
| **PB-BUF-RECOVERY-001** LIFECYCLE | 断线/重启/MPD外改/同URI外播/旧request | 无自动claim/clear/stop/重启；显示actual而非business；显式接管后恢复 | `test_buf_recovery.py`：epoch/版本漂移、未知key、同URI异ID |
| **PB-BUF-STATE-001** STATE_PROPAGATION | 联合业务snapshot与MPD最新实态分离 | Web只有实际播放/暂停/停止、current和progress取MPD；媒体URI精确查MS元数据；Web Next只取MS；GET/WS只读 | `test_buf_state_wire.py`及Web事实源proof |
| **PB-BUF-ACTUAL-001** REPRESENTATION | MPD自然进位、外部改队列或MS命令记录尚存 | 后端实时MPD采样确定actual current/next/next-next，不能用上次控制ACK/计划代替；不覆盖MS业务Queue | `test_buf_actual_state.py`：position1、同URI异ID、旧400、未绑定 |
| **PB-BUF-OBSERVE-001** LIFECYCLE | 一个专用idle连接、约1秒status poll、命令前后最新采样 | 收到player/playlist/options先读真实MPD、统一ActualStateOwner；晚样本丢弃，idle掉线poll兜底 | `test_buf_observer.py`：idle/poll/状态竞争/失败时效 |
| **PB-BUF-WEB-001** STATE_PROPAGATION | MPD实时事实/URI精确Library匹配/业务Next独立 | actual播放/暂停/current/progress优先、未绑定也显示真实媒体不认领occurrence；3秒延迟6秒stale；AppBar告警；无MPD物理Next UI | `test_buf_actual_wire.py`＋Web actual-authority/freshness/next invariants |
| **PB-BUF-PERF-001** REPRESENTATION | collection≥400，持久DB已有，前端加载 | MPD命令/样本条目≤常数，与N无关；浏览器资源加载有界，不阻塞控制 | `test_buf_scale.py` + Web Queue资源并发proof |
| **PB-BUF-MIGRATION-001** LIFECYCLE | 旧Task9数据库与MPD大队列，现有NAS容器用户数据 | 新进程不自动清MPD；schema正向兼容；真实MPD受控实验可恢复；未通过不发布 | `test_buf_migration.py` + NAS用户验收记录 |

**Proof强制关系链**：每行必须映射 `spec §8.10 ID → owner代码 → RED invariant → 最小GREEN → MPDAdapter/MockMPD/SQLite/API联合回归 → 最后真实MPD（如适用）`。仅Mock适配器同函数测试、只检查返回200、旧历史GREEN均不足以关闭行。

## 4. 实施边界、依赖与建议Batch

**共用安全边界**：不触碰真实音乐写权限，不清空/重建NAS现有数据库，不改MPD配置文件/daemon，真实设备一律用户控制维护窗口；禁用并发多owner，客户端不连接MPD TCP；不改Task8/9已接受路由/视觉，未经独立产品裁决不得放宽§3.3.1 pending unavailable行为；不新增不必要外部依赖。后续工作与NAS Final Task B08并行时以本分支新合同为主，旧final计划只作为部署/URI等未冲突工作输入。

| Batch | 仅允许的工作与主要文件 | EXIT / 验证 |
|---|---|---|
| **B0 Contract Freeze（本次）** | 唯一Spec更新、Architectural refs、主Plan迁移说明、本计划、doc地图；无产品/测试 | 冲突来源标记、矩阵完整、Task9 commit/branch精确可核对；**合同冻结，非代码验收** |
| **B1 Executor + Port proof** | `player/{ports,mpd_adapter,models,mock_mpd}.py`、短缓冲执行器、唯一ActualStateOwner及独立MPD idle连接；真实样本一致性与单写owner FakePort tests | 3稳态/4瞬态；实际status+受控playlist读取；idle+1s poll、重复URI、旧400及丢失响应RED→GREEN；本批不接API |
| **B2 Explicit Playback** | `playback_service`/`queue_manager`接新执行器，Start/集合/普通Song/Queue/Played/Next/Previous及显式takeover；强制控制前后实样本 | 400首不逐项MPD add；业务occurrence/History/Context/Key/Token不变，确认的actual事实来自MPD而非操作日志 |
| **B3 Pending/AutoPlay/runner** | Pending增删改/AutoPlay、MPD已预备两项维护、真实A→B自然进位接纳、独立后台runner | position1/并发删预备next/next-next/PAUSED与短曲；MS Web Next不改变，History不伪造 |
| **B4 Transactions/Recovery/State** | 短SQLite事务/fence/journal/restart/实际观察单owner→兼容actual DTO+actual Song；播放租约有界限频invalidate | MPD ACK失败/旧采样不串曲；持续PAUSED状态lease可靠；HTTP/WS只读、现有epoch/seq兼容、SQLite读不被MPD I/O锁住 |
| **B5 Web/Scale/Regression** | 仅改既有Web数据选择器、实际URI展示、可选actual字段解码、3/6秒独立过期、AppBar反馈及400 Queue元数据请求有界化 | MPD四类实际事实正确、Web Next始终MS Queue；unbound不错误显示业务current，UI布局保护，旧Wire及全部回归 |
| **B6 NAS 真人验收与移交** | 独立验收说明/必要最小bugfix；真MPD/USB DAC可恢复实验；整套关系回归与分支diff | 用户亲测下列场景GREEN，未测逐项NOT RUN；再考虑PR/合并、镜像、生产替换，**不得自动进行** |

实施时对每个Batch严格：先核对远端HEAD/CI和涉及的Spec/代码/历史proof→规定可改文件与不变项→先写精确失败证明RED→最小修复GREEN→小范围与跨模块回归→记录diff及已验证/未验证；只做用户指定Batch，不默认实施下一Batch。旧Task9/Final NAS并行分支发生变动，先做差异审计及rebase冲突决策，不静默覆盖。

## 5. 重点风险、验收事实与停止条件

1. **双权威竞态**：MPD自主A→B的瞬间，用户删除/插队B；不能做到真正跨MPD+SQLite物理原子。必须允许明确冲突/UNKNOWN并用新样本和业务版本重新裁决，**不能**返回删除成功却把B继续当作受控下一首。
2. **三首短缓冲**：稳态Current+2首预备≤3、瞬态≤4；第三首用于MPD后台连续播放准备，**不是Web展示的下一首权威**。短曲/断线时仍可能停播，不能宣称绝对gapless。
3. **协议能力**：MPD command列表包含不等于可按权限成功调用；`consume/single`设置、新加ID/删除正在播/自然进位/queue局部读取组合须后续真实NAS验证；禁止使用未知MPD命令试探当前正在听的队列。
4. **部分成功不可回滚**：必须有sent/ACK/confirmed前缀、服务代次和旧key恢复边界；响应丢失后不根据URI猜唯一性，不能在CI模拟器里假装提供外部因果保证。
5. **过渡接管**：旧MPD队列可有400首，不能把「稳态≤3」当成旧运行现实；仅明确播放接管授权才整理旧队列，先保留/确认现有状态及可恢复计划，不在startup/GET自动清空。
6. **后台持续性与Web真实性**：idle player/playlist/options＋约1秒status poll＋命令前后强制实采样；仅一套actual缓存。Web三秒无新采样显延迟，六秒标stale；真实PAUSED时也需定期证明采样仍新鲜，Web Next始终MS Queue。客户端无连接时runner仍执行，未知STOPPED不自动播放。
7. **旧持久数据**：Queue/History不删除、不重新编号、不批量丢pending；schema有增量须迁移/兼容proof与备份验证。失败升级保留可退回旧容器的数据库格式或明确迁移回退策略，不能无证明声称直接降级兼容。
8. **Web资源成本**：400首Song详情并发可能引起独立负载；需要单独界定并发/缓存/分页策略，不改业务分页内容或现有layout。
9. **端到端真人Gate**（NAS真实MPD+USB DAC）：真实MPD播放/暂停/停止、当前歌曲标题及elapsed/duration与Web一致（包括业务unbound可识别URI）；MS 400首而MPD稳态3首；B在MPD位置1自然进位及预备C/D；Web Next/Queue/Played来自MS且不被MPD列表覆盖；Queue next/next-next删除/插队/重排/AutoPlay/前进后控制前后采样；idle失联轮询兜底、MPD断线与Web断线区分；PAUSED超过6秒持续新采样不会误stale、3秒延迟/6秒过期AppBar提示；旧镜像安全回退。每项实测PASSED/FAILED/NOT RUN，Mock/CI不代替。

**停止/升级条件**：发现会改变业务语义、MPD版本不支持必要命令、部分成功无法给出保守终态、SQLite锁解耦证明失败、Web现有接口需要破坏性变更、NAS真机存在无法解释的自动切歌时，停止对应Batch，先修Spec/矩阵/RED再继续。没有本人真机结果不宣布B6完成。

## 6. 本次交付与退出状态

- 合同冻结：**YES**（2026-10-12补充修订：MS唯一业务Queue与Web Next；MPD实际播放/暂停/当前/进度权威；三首MPD缓冲＋统一idle/poll/强制控制前后读取；实现仍NOT RUN）。
- 分支：只允许基于 Task9 HEAD 的 `refactor/mpd-bounded-execution`；不动 `feature/task-9-web` 或 `main`。
- 代码实施、测试RED/GREEN、CI、NAS播放/DAC验收：**NOT RUN**，只完成远端文档提交及读取校验。
- 后续实施默认从 **B1** 开始；未获得新的范围指令不自行开工、不提交PR、不合并或生产部署。
