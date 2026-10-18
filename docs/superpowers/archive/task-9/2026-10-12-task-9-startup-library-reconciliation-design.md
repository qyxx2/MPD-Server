# Task 9 Corrective — Startup Library Reconciliation / Web Readiness

日期：2026-10-12。**DRAFT / USER REVIEW REQUIRED；未授权生产代码。**

## 1. 意图、基线与边界

用户要求持久曲库启动时Web及时可读，后台只校准签名差异并重新确认MPD，不重复解析/哈希未变全库，也不以timeout或部署参数掩盖后端阻塞。目标基线feature/task-9-web，远端重新核对为098d6eaea81495d1686a09f9e0ee68768610ed7e；修复分支fix/task-9-startup-library-reconciliation。证据归[调查报告](../plans/2026-10-12-task-9-startup-root-cause-evidence.md)。

本轮只处理startup Library reconciliation及Web读取预算；不推进其它Task，不合并main，不连接真实MPD/NAS/DAC，不本地运行Docker。所有机械验证用临时SQLite、media fixtures、MockMPD/Fake Player。环境沿用现有.venv和Node依赖，禁止修改依赖或数据库清空。容器交付沿用CI构建新SHA双架构镜像，旧CI成功不是修复验收；push/PR需另有显式授权。

长期语义唯一归修订后的[Library §7.2](../../specs/2026-09-24-library-playlist-tag-search-design-2-1.md)和[Architecture §4.1、§8.2、§12](../../specs/2026-09-25-system-and-development-architecture-design.md)。本文锁定corrective的组件/数据流与证明分配，不另定义播放/Queue/History合同。两份长期合同的本次增量同样待用户确认。

## 2. 方案选择

推荐A：短baseline读取→线程prepare→短commit，持久音频签名差异校准，辅助sidecar签名，复用startup inventory，MPD先确认再按需更新。它同时切断lifespan、event loop和DB lock三个阻塞来源，并保留原业务一致性。

B：仅把当前scan_full移到线程。无法安全跨线程共享事务连接，仍可能长时间占用应用DB锁，也没有解决重复hash、重复inventory和无条件update，不能满足目标。

C：新增文件系统事件平台/另一个索引数据库或MPD全库导入。改变权威/部署复杂度，超出范围；本轮保留既有2秒签名轮询、12小时deep校准及SQLite。

## 3. 组件与内部数据边界

`LibraryRuntime`只启动/关闭单owner，constructor无音乐树I/O。后台startup owner捕获音乐根identity、加载持久baseline并准备校准；HTTP不等它。必要DB migrations、本地Queue与协调器初始化仍在lifespan中完成。AppConfig只验证音乐根路径配置的语法/类型，不访问该音乐树；music_root的readability从startup配置验证移到后台prepare。配置JSON损坏/其它非法值仍fail startup。MusicUriMapper构造只存配置，canonical root resolve延到第一次实际映射使用，保留原resolve及symlink越界检查语义，不将本地URI规则改成纯字符串前缀。

新增小型内部prepare模块，使用frozen数据对象：FileSignature、SidecarSignature、LibraryInventory、ScanBaseline、PreparedScan。baseline包含Song快照、sidecar成功签名及album artwork依赖；线程只消费这些值，不调异步Repository、不携SQLite连接。prepare执行路径规范化、inventory、签名比较、metadata/hash与移动候选选择；身份规则继续exact URI→唯一identity且旧路径确实消失→唯一missing hash，不合并live copy或歧义候选。

PreparedScan包含ScanBatch、完整inventory、root identity、baseline fingerprint、失败路径、音频索引是否实际变化和sidecar签名delta。ScanBatch增加observed_file_uris；未变化音频只进入observed，不创建新的Song实例用于upsert。不以ScanResult.updated_song_ids（现实现对所有已解析记录都列updated）直接判定是否需要MPD update；比较签名/availability/URI delta及失败恢复事实。

Repository新增内部schema v4→v5迁移：`library_sidecar_signatures(song_id PRIMARY KEY REFERENCES songs(song_id) ON DELETE CASCADE, lrc_uri TEXT NOT NULL, file_size INTEGER NULL, file_mtime_ns INTEGER NULL)`；两个NULL表示已观察的不存在，缺行表示未知。两个签名列须同为NULL或同为非负整数。迁移只建辅助表，不清空或迁移Song URI/引用，不改公开DTO。首次未知LRC：有当前sidecar或旧lyrics_source=sidecar才重解析关联音频；无sidecar且旧非sidecar歌词直接记录已知absence。签名仅在对应路径成功prepare/commit后更新；lyrics_status=read_error不能写成功sidecar签名，必须进入路径重试。

删除保留Song及既有引用；移动同Song更新签名关联，不生成无必要新身份。LRC-only变化只解析同stem关联音频，音频stat未变则复用content_hash；同stem的FLAC/MP3均处理。沿用现有小写`.lrc`sidecar读取规则，不在此修复扩张命名策略。

artwork source变化可能需要prepare同专辑候选以选fallback；这是被变化资源直接关联的路径，不能扩大为全库重读。其它未变音频在startup必须0 parse/0 hash。补齐签名只在成功后记账；失败记录不能缓存成成功。

## 4. 扫描、事务与并发

1. 短事务读baseline，退出事务后启动线程。startup根检查也在线程；无read_signatures constructor调用。
2. 一次inventory同时提供音频/LRC签名、完整性与root identity。需要处理的文件读前/读后stat一致才接受结果；全树不可读或root identity变化时拒绝absence校准，保留旧数据并报错。
3. prepare结束及进入commit前在线程复核root identity/准备结果，禁止为该复核再完整遍历。文件系统不是SQLite可锁定权威；结果代表安全检查时捕获的事实，后续外部变化由下一generation收敛。测试在检查前/期间替换mount必须拒绝mass missing。
4. commit重新核对数据库baseline，仅SQL和内存登记；冲突拒绝陈旧batch，仅重做冲突路径，复用仍有效prepared结果。单扫描owner不绕开共享事务锁。支持旧scan_full/scan_paths包装器，但它们不得在已有outer transaction内开始prepare；明确拒绝这种调用，更新仅受本corrective影响的调用者/测试。已在outer transaction内的commit允许消费提前准备好的batch，仍保留rollback/cancel/联合提交/no-op证明；同一outer事务多个batch必须依据该outer进入时的有效baseline进行一次验证与顺序提交，不能把本事务自己的前一次修改误判为外部陈旧冲突。
5. 原子提交Song/classification/availability/sidecar signatures、library revision、SYNCING及待通知义务。实际MPD/WS在锁外。没有内容变化不增Library revision；扫描完成事件仍保留。
6. shutdown协作取消线程准备，取消后不commit、update或通知成功；已提交事实保留，失效义务继续遵守既有合同。

扫描期间旧已提交事实可读。fixture中的prepare barrier保持关闭时，lifespan进入、/api/state、WS initial snapshot、Library REST及独立DB事务均在1秒预算完成；慢真实parser/hash在线程中仍允许event loop进展。commit后通过现有revision/WS原子失效，不建旁路cache或独立快照权威。

## 5. Detector与失败路径

startup完整inventory交接给detector后，等待既有2秒间隔再检查，不立刻重复walk；startup未完成/失败时不启动竞争的全树轮询。保留500ms debounce与下一generation变更合并，删除通过安全完整inventory差异校准。deep/manual prepare在同owner、锁外执行；不调大SCAN_INTERVAL_SECONDS。

单文件MediaMetadataError/OSError/read_error转成路径失败，正常路径准备结果不丢；正常结果提交后坏路径单独retry。已知坏文件UNREADABLE但保留元数据、lyrics/artwork引用适用的既有保护；新坏文件不建虚构Song。失败路径未解决时活动不能SYNCED。路径变稳定后恢复AVAILABLE与签名；成功路径不被重复解析/哈希。root不可读与mount replacement作为根级失败保留旧索引，不能转成空成功batch。

每generation持有未解决路径与MPD目标，新的请求合并时保留尚未确认的旧move/delete absence；旧结果不能覆盖新generation。重试保持activity_id，用既有2/5/15/30秒退避。

## 6. MPD确认状态机

startup本地无变化：短commit后读database_update_status、对当前应存在/缺失目标调用has_library_uri。全部一致且not updating则SYNCED，update=0。明确URI不一致才update一次并重新确认；update接受后60秒预算内按1秒poll等待结束，不在确认重试中重复update。网络失败/unknown不是索引不一致，先退避重读，不盲目控制MPD。

本地音频新增/变化/删除/移动先update再确认；LRC-only不要求音频数据库更新。确认预算从确认/update阶段开始，不含prepare。失败既有安全错误码，真实成功必须精确确认，不修改业务Queue/Playback/History/Output。空库仍检查update状态，不能沿用重启前SYNCED证明。

## 7. Web初始与GET预算

WS initial默认10,000ms，从socket创建起计算；GET默认10,000ms，含fetch和JSON读取/解码。注入时钟/预算便于fake timer。initial超时INITIAL_SNAPSHOT_TIMEOUT：关闭旧socket、清timer、显示明确顶部错误，沿既有退避重连。GET超时READ_TIMEOUT：abort底层读取、在预算内settle、释放loading，明确错误并可重读。底层mock忽略abort也必须settle；迟到结果继续按generation/epoch/revision拒绝。

错误文案：“初始状态读取超时，正在重连”“状态读取超时，请重试”；资源GET采用“资源读取超时，请重试”。保留最后事实stale只读，成功GET不能恢复写权限；只有完整新initial恢复。成功/失败/stop均清timer；不改变mutation unknown/key，不重放任何业务mutation。

## 8. 必须先建立的十项RED与验收

| 用户项 | 永久证明目标 | Batch |
|---|---|---|
| 1 | 持久DB、完整音频/sidecar签名，第二次真实runtime启动parse=0/hash=0 | C0→C2/C3 |
| 2 | 真实lifespan与prepare barrier，HTTP state/Library、WS首帧1秒内完成 | C0→C2/C3 |
| 3 | 真实parse/hash线程barrier下独立run_transaction完成、event loop可进展 | C0→C2 |
| 4 | 无变化Fake URI一致update=0且重新精确确认 | C0→C3 |
| 5 | URI不一致update=1，确认顺序为precheck→update→postcheck | C0→C3 |
| 6 | 增/改/删/移/LRC参数化路径spy，只访问相关音频，引用保持 | C0→C1/C2 |
| 7 | prepare中mount replacement不mass missing，DB/revision保留 | C0→C2 |
| 8 | 持续损坏与随后恢复，仅重试坏路径，正常parse/hash不增加 | C0→C2/C3 |
| 9 | constructor禁止resolve/stat/iterdir/open；startup一次inventory，seed后不立即walk | C0→C3 |
| 10 | fake timers：无首帧/永不返回GET/迟到body明确错误、结束loading、可重试 | C0→C4 |

所有新缺陷证明在任何生产修改前记录真实RED；旧合同已经满足的保护（例如mount replacement）可baseline GREEN，但须增加能够暴露新prepare/commit交界风险的测试，不能为制造RED破坏现有代码。新接口缺失导致的RED不能代替现有行为断言失败。每Batch完成精确测试、相关服务/API/关系、完整后端与Web回归，并fresh记录。全部通过后才能报告本corrective自动Gate；手机/真实设备仍NOT RUN。

## 9. 审阅与实施门槛

用户已要求本轮准备spec和分Batch plan，故一并提供草案；尚未把“推荐设计”当作书面spec/plan批准。批准两份文档后，先C0 RED，不跳过其它Batch的精确/关系/完整回归。默认建议当前会话native按Batch实施；用户选择委派时再使用subagents。无自动commit/push/PR/merge。容器CI新SHA交付必须在远程授权与实际CI结果后才记完成。
