# MPD-Server v0.1 NAS最小真实交付 Final Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 用户选择委派时才使用superpowers:subagent-driven-development。Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以最小改动部署到NAS Docker，真实连接控制MPD，自动及时同步曲库，并用唯一AppBar最近活动和基本日志解释运行结果。

**Architecture:** 保留SQLite/Song.file_uri及既有Services/PlayerPort；配置只在composition root注入，URI映射集中在边界，单同步协调器驱动扫描和MPD确认。FullStateSnapshot与现有WS自动刷新同步状态；AppShell唯一活动投影复用现有notice/action owners。容器由用户手动重启。

**Tech Stack:** 既有Python/.venv、FastAPI/Pydantic/SQLite、pytest/Ruff、Vue/TypeScript/Vite/Vitest、NAS Docker Compose及独立MPD；本轮未批准新依赖。

**Spec:**
- [Architecture §22](../specs/2026-09-25-system-and-development-architecture-design.md)：MIN-DELIVERY/CONFIG/URI/HEALTH/LOG-001。
- [Library §7.2](../specs/2026-09-24-library-playlist-tag-search-design-2-1.md)：LIB-MPD-SYNC-001。
- [Visual §6](../specs/2026-10-03-web-pwa-visual-design.md)：WEB-UI-NOTIFY-001唯一视觉权威。
- 既有Playback/Output Specs、Architecture §4/§12/§19.5与SYS-MPD-CONNECTION-001继续适用。

**Status:** 2026-10-11本轮核查并关闭B01 Gate；B00 CLOSED / BASELINE PASSED；B00C CLOSED / AUTOMATED PASSED；B01 CLOSED / AUTOMATED PASSED，前置已闭合并完成fresh重验。B02 CLOSED / AUTOMATED PASSED；B03 IMPLEMENTED / AUTOMATED PASSED，NAS规模及时性HUMAN PENDING；B04 CLOSED / AUTOMATED PASSED / MOBILE VISUAL USER ACCEPTED（2026-10-12）；B05 CLOSED / AUTOMATED PASSED（2026-10-12）；B06 CLOSED / AUTOMATED PASSED（2026-10-12）；B07 READY FOR NAS / LOCAL AUTOMATED PASSED（2026-10-12），NAS部署及重启持久化HUMAN PENDING；B08–B09 NOT STARTED。不声明构建、Docker或实机通过；未授权Git整合。本文是新的唯一最终交付执行入口；旧Task9计划只继续管理其未关闭历史Gate，旧Task10–12步骤按主Plan增量映射，不照原清单恢复延期功能。

## Global Constraints

- 使用原.venv，不修改环境/依赖；native测试从repo root运行；真实音乐只读。
- 保留当前Task9 dirty成果和所有runtime文件；不能清理、重置、复制到遗漏dirty成果的基线。
- 自动测试只使用自有临时DB/媒体/配置；执行前检查conftest/lifespan不会fallback到现有DB。
- API→Service→Repository/Port；早期模块不import config。单worker；WS/GET读不控制MPD。
- 既有Queue/History/Context/AutoPlay/Output确认、事务、revision、opaque key/retry不变。
- 本轮不做备份恢复、update.sh、restart API、URI数据迁移、PWA、日志Web页面或通用管理后台。
- 容器重启由用户操作；没有物理声音/真实MPD反馈不能标记实机PASSED。
- 用户没有请求commit/push/PR/merge，本计划各Batch不含自动Git整合；旧“Commit Step”不是本轮授权。

## Review Focus

1. NAS音乐挂载失效与半写入：不能把旧库批量标MISSING；稳定文件随后能自动识别（B03）。
2. 本地URI/协议URI、重复occurrence与外部漂移：映射不得破坏当前确认/D6/身份（B02）。
3. MPD更新延迟/失败、处理中又新增文件：不提前SYNCED、不漏下一轮、重试不影响播放（B03/B05）。
4. 超过5项、成功历史与未知操作：显示有界但恢复owner不丢；旧epoch/旧poll不能倒灌（B04/B05）。
5. Docker生产artifact、IPv6网络、刷新深链接和重启配置：真实环境逐项确认，不拿Mock抵扣（B07/B08）。

## 1. 仓库核查与差距（非验收证据）

核查分支feature/task-9-web，HEAD14c6239；109个modified/untracked条目。主Plan1301行、Task9计划484行，因此独立本文，不移动archive、不重写历史验收。

| 实际基础 | 需闭合差距 | owner Batch |
|---|---|---|
| main.py环境装配、saved地址、observer；能力默认空、runner显式注入 | 最终配置/真实能力/后台生命周期未完整装配；MPD_MODE未消费 | B01/B03/B07 |
| Scanner commit→optional update→completion event；watch debounce/scheduler组件 | 无真实变化发现接线；update无逐URI确认；无同步状态 | B03 |
| Playback直接发送/比较file_uri | NAS/container与MPD路径需转换且反查保持一致 | B02 |
| AppBar中心PlaybackStatus＋notice Map＋TaskActions | 无统一时序/5项上限；成功撤下；专用/通用重复风险 | B04 |
| WS完整snapshot/失效/自动GET、resource cache | 尚无library_sync DTO/domain及联动 | B05 |
| /api/health恒ok、既有日志轮转 | 三项真实状态与定位日志 | B06 |
| Docker多阶段build/生产持久挂载 | 生产配置根、能力、音乐映射、dev隔离、深链接需验证 | B07 |
| 非空ArtworkRef→SongResponse已知500 | 独立最小DTO corrective，真实非空封面链 | B00C/B08 |

Task3/4/5/6/7实现和相关提交存在，关键修复抽查可达；本轮没有运行回归。Task9 B10仍OPEN/HUMAN PENDING，真实设备BLOCKED/NOT RUN；不自动关闭。Task9不是Task10原正式依赖，但本计划消费其saved地址与AppShell，必须按当前工作树确定可复现继承基线。旧主Plan“B10未启动”是过期时态，以最新acceptance核查并更正。

## 2. Contract Matrix（REQUIRED）

每行采用共同字段D0＋行增量，字段P/A/Δ/U/X/H/T/F/R/O/E必须合成完整合同；长期语义只引用上述Specs。

**D0:** P=B00已确认当前基线/允许文件且前置已验；A=文件/SQLite/MPD各自拥有事实，Services协调，Web只表达；Δ=仅该操作定义域；U=音乐只读及既有播放/资源合同不变；X=依赖实际文件/协议/部署事实确认；H=无虚构History，事件继承outer commit；T=既有最外层事务/sequence/terminal机制；F=失败不伪报成功，不用rollback宣称撤销外部副作用；R=业务重试原key，后台索引重试单owner有界；O=typed结果与AppBar唯一活动；E=下列新真实协作invariants＋相应已有回归，历史GREEN不抵扣。

| ID/type→Spec | P/A与Δ/U | X/H/T | F/R/O | E/Batch |
|---|---|---|---|---|
| FINAL-CONFIG-001 lifecycle→MIN-CONFIG | 文件/env/saved→一次启动注入；运行中地址/密码不热改 | 文件验证/新进程采用；启动新epoch，无控制成功事件 | 非法失败；MPD不可达可启动；密码不输出 | test_config_composition.py，B01 |
| FINAL-URI-001 representation→MIN-URI | 同一文件树与唯一mapper；保留Song/成员/occurrence | 发命令和反查精确对应；不以重排消除不匹配 | 越界/错误映射明确失败；重试保留原intent | test_uri_mapping.py，B02 |
| FINAL-SYNC-001 lifecycle→LIB-MPD-SYNC | 手动/自动同协调器；generation隔离 | commit/可见revision→update→逐URI确认；无播放/History | 外部失败保留MS索引；自动封顶重试；同步状态 | test_library_sync.py，B03 |
| FINAL-ACTIVITY-001 propagation→WEB-UI-NOTIFY | 所有旧/新提示同投影；最近5项，不改变事实 | 真ACK＋权威读才完成；聚合图标不漏5项外异常 | owner不因裁剪消失；unknown原key/confirmed只read | appbar-activities.test.ts，B04 |
| FINAL-SYNC-WIRE-001 propagation→LIB-MPD-SYNC/A§12 | 同步完整state＋独立domain；保留既有revisions | 原序列切面；仅同步变化sequence前进 | 旧epoch/generation拒绝；断线stale/首帧恢复 | test_library_sync_wire.py＋library-sync.test.ts，B05 |
| FINAL-HEALTH-001 representation→MIN-HEALTH | 三项独立读取；不控制/不扫描 | SQLite读取与有预算MPD观察，no-op | MPD unavailable HTTP200；本地必需失败503 | test_health_relationships.py，B06 |
| FINAL-LOG-001 representation→MIN-LOG | 关联id＋安全短消息；无秘密/完整body | 阶段变化日志；失败记录不改变结果 | 日志失败不伪造业务；UI独有日志在browser | test_logging.py/activities日志测试，B04/B06 |
| FINAL-DEPLOY-001 lifecycle→MIN-DELIVERY | prod真实/devMock；数据配置独立持久 | 真实构建/Compose/同源/重启配置；不管理MPD | 失败阶段不报部署成功；手动容器重启 | test_deploy_contracts.py＋NAS卡，B07/B08 |
| FINAL-ARTWORK-001 representation→Library/WEB-UI-BG | 非空持久ArtworkRef；Song/封面事实不改 | Repository→REST→Web解码；失败不清空掩盖 | typed读取失败；不伪造图片/删字段 | test_library_web_fixture.py增量＋global-artwork，B00C/B08 |

## 3. Batch执行规则与验收顺序

B00→B00C→B01→B02→B03→B04→B05→B06→B07→B08→B09。B04独立审阅和手机比例验收；不能在B05接入同步时顺便重做活动设计。

所有实施Batch重复以下明确步骤（适用每个下列selector）：
- [ ] 写所列精确节点及断言；运行节点确认因缺行为RED，既有bug先复现。
- [ ] 按Files/Interfaces最小实现；新增模块不挪动无关代码。
- [ ] 重跑精确节点GREEN，再该文件，再列出的relationship/历史回归。
- [ ] scoped Ruff；Web变化typecheck；相关产品生产build在B07/B09执行。
- [ ] 检查实际diff、git diff --check/stat/status；记录owner→proof→fresh evidence。
- [ ] 人工Gate适用时等待真实反馈，不用自动GREEN关闭。无自动commit。

下列新测试名均TO CREATE/NOT RUN，不表示已存在。命令从root运行；替换成另一个测试名须同步本计划，不能跳过指定关系验收。

### B00：冻结可执行基线与范围

Files：仅主Plan/本文/文档地图的必要状态同步；本Batch不改产品。
- [x] 核对git status/branch/log，记录完整dirty归属与HEAD；确认如何保留并继承Task9成果，未授权不commit/切分支/建worktree。
- [x] 复查各Spec、schema/运行时结构、能力记录与实际Port；确认本矩阵及拟新增字段。
- [x] 检查原.venv的python/pytest/ruff版本；检查server/requirements.txt，不安装依赖。
- [x] 在自有临时DATABASE_PATH运行test_health.py、test_mpd_connection.py、test_library_api.py，以及global-notices/shell-navigation/wire现有最小回归；环境失败与代码失败分列。
- [x] 记录Task9剩余手机Gate和真实地址/挂载要求；本文不以Task9整Task CLOSED作启动条件。
Gate：**CLOSED / BASELINE PASSED，2026-10-11**。基线可追溯、未丢原成果、Spec/matrix完整、最小回归fresh；本批未改变既有文件权限或本地DB。此Gate不证明后续合同已实现，不关闭Task9 B10或实机Gate。

#### B00 本轮简要证据与交接

- 基线：`feature/task-9-web`，HEAD `14c6239`（最近五条14c6239/adf4171/36cbd24/138fd98/e3a15b3）；当前工作树作为继承基线，不commit、切分支、建worktree或清理。实际111个dirty条目，替代§1编写时109条的数量；不改写历史快照。完整逐路径status与381个tracked/untracked文件的SHA256/权限清单保留于本轮自有`/tmp/mpd-b00-qr1umc_h/status.txt`及`baseline.json`（临时审计附件，长期结论在本节）。status SHA256 `932590115e28946537f9535bc5ed7886d5c59cf32e6df58f94cf0ac4812b1679`。
- dirty归属按现有路径职责核对，不推定作者或所有历史Gate通过：root 2 modified（README/.gitignore）；docs 7 modified＋5 untracked条目（Specs/主Plan/地图/手机方法、Task9计划与archive、本文）；server 18 modified＋13 untracked（Task9 API/领域/实时/MPD保存地址及测试）；web 24 modified＋42 untracked（共享壳/资源页/状态与actions/fixtures/invariants）。完整manifest包含目录条目的实际文件；均原地保留。
- 原环境：`.venv/bin/python`可执行，Python3.14.4、pytest9.1.1、ruff0.16.9；已读取`server/requirements.txt`，无缺失依赖、无安装或环境变更。
- 安全装配核查：main lifespan明确消费DATABASE_PATH；conftest在observer实际采样前close并await，不接触live MPD；recovery默认未启用，system读取无能力时fail closed。MPD连接测试显式Mock/Adapter factory，library测试用Fake服务/Scanner及tmp_path，`/music`仅为Fake入参。Web使用注入网络/WS fixture。临时DATABASE_PATH和MPD_CONNECTION_PATH同时指定，防止fallback读取现有SQLite或saved文件；未扫描真实音乐。
- fresh后端：`DATABASE_PATH=/tmp/mpd-b00-qr1umc_h/music.db MPD_CONNECTION_PATH=/tmp/mpd-b00-qr1umc_h/mpd-connection.json .venv/bin/python -m pytest -q -o cache_dir=/tmp/mpd-b00-qr1umc_h/pytest-cache server/tests/test_health.py server/tests/api/test_mpd_connection.py server/tests/api/test_library_api.py` → **36 passed**（2.98s）。
- fresh Web：`npm --prefix web run test -- --run tests/invariants/global-notices.test.ts tests/invariants/shell-navigation.test.ts tests/invariants/wire.test.ts --maxWorkers=1 --minWorkers=1` → **36 passed / 3 files**（global-notices10、shell-navigation1、wire25）。环境失败/代码失败均无；后端仅既有Starlette/httpx弃用warning，不改依赖。纯基线/文档批，无新行为或修复，不制造RED；未跑全量、Ruff代码检查、typecheck、build或后续Batch tests，不记通过。

| 矩阵→Spec / 当前owner | 当前源码核查与后续归属（均未实施） |
|---|---|
| FINAL-CONFIG/DEPLOY → Architecture新增§22.1 / main、connection service、deploy | saved优先与下次启动生效已存在；APP_ENV/MPD_MODE未消费，config/能力loader缺失，B01/B07闭合；历史probe/commands不授予新endpoint/version能力。 |
| FINAL-URI → §22.2 / Adapter、PlayerPort | 当前发送/回读直接使用URI，mapper缺失；保持Song.file_uri、occurrence、反查与D6，B02闭合。 |
| FINAL-SYNC/SYNC-WIRE → Library§7.2、Architecture§12 / Scanner、events、state DTO、Web decoder | 可选updater与commit→update→completion存在，main未注入自动扫描/同步；Port有update/stats/update-status，无has_library_uri；FullStateSnapshot及公开DTO/decoder无library_sync，B03/B05闭合。拟新增状态/计数/generation/activity_id字段和独立domain已有Spec；不在B00猜实现类型或改schema。 |
| FINAL-ACTIVITY/LOG → Visual§6、Architecture§22.3 / AppBar、PlaybackStatus、notices | 当前Notice为id/scope/message/busy/level/retry/read，播放与通用提示仍共投影；缺最近5项与成功保留，B04固定status/description/resource/updatedOrder并消费原owner，不增第二store。 |
| FINAL-HEALTH/LOG → §22.3 / main health、Services、日志 | health当前恒ok，无ms/mpd/library_sync三项真实健康装配，B06闭合；生产已有10m×3轮转。 |
| FINAL-ARTWORK → Library§3、Visual BG / Library Repository、SongResponse | domain ArtworkRef与公开ArtworkResponse不同，_song_response仍直接model_validate(song)；已知非空链500保留B00C。此次最小回归不含该非空链，不记已修复/通过。 |

D0＋九行增量具备P/A/Δ/U/X/H/T/F/R/O/E追溯，拟新增接口/字段与所引用Spec一致，未发现阻塞B00的合同缺失。§22指Architecture文末新增“最小真实交付范围”，区别于旧同号“安全边界”。共同Web authority/epoch/sequence/opaque key及输出selector/真实回读合同继续适用，不能以此核查替代后续关系测试。

Task9历史只读取与依赖有关的final acceptance/A02、能力记录的当前范围：B10仍OPEN / HUMAN PENDING，非空封面、实机BLOCKED/NOT RUN；不以整Task9 CLOSED作为B00前置。能力文档旧NAS endpoint/版本仅历史证据，本轮未连接NAS或探针。现有runtime/服务保留，不重启、不停止；26个既有DB/connection文件内容与权限基线在测试后比对相同。

后续实机准备卡（信息待确认，不是B00人工Gate）：①实际MPD IPv6/port，密码由部署MPD_PASSWORD注入；②NAS音乐根、容器可读只读挂载根与MPD相对URI前缀，确认同一文件树；③NAS架构/Compose环境、数据与配置持久目录；④用户切IPv6后独立测试，恢复Codex网络反馈。Task9手机综合跨页/收藏一致/断线恢复仍待用户，物理声音不能自动证明。本批没有Docker/实机/手机操作。

本批结束核对：实际增量仅本文、主Plan入口、文档地图；381个基线文件中除上述3份文档外，其余378个文件内容保留，原权限及既有DB/connection文件不变，未新增可提交runtime/env/依赖文件，`git diff --check`通过。B00C/B01–B09均未推进。


### B00C：非空封面DTO最小corrective

Files：Modify server/app/api/library.py；Extend server/tests/api/test_library_web_fixture.py、必要server/tests/invariants/test_realtime_library.py；Web仅复用global-artwork回归。
Interface：保留SongResponse公开字段；_song_response对嵌套domain model安全转换，不清空artwork。
- [x] RED test_library_web_fixture.py::test_non_null_artwork_preserves_song_and_resource_identity：真实临时SQLite持久引用→单曲/列表/集合REST，非空字段和值正确且不500。
- [x] 最小转换后重跑节点/文件；现有test_library_api.py、test_realtime_library.py及global-artwork.test.ts。
Gate：**CLOSED / AUTOMATED PASSED，2026-10-11**。真实临时SQLite非空引用→单曲/歌曲列表/专辑集合REST已证明，既有Web背景回归fresh；不改变封面/歌词业务规则。真实图片解码与NAS/手机联合链仍归B08，不以此关闭Task9实机Gate。

本轮简要证据（FINAL-ARTWORK-001→Library§3 / WEB-UI-BG）：
- 当前源码包含此前B01成果，原地继承`feature/task-9-web` / HEAD `14c6239`；不回退main/config，不推进后续Batch。原`.venv` Python3.14.4 / pytest9.1.1 / Ruff0.16.9，requirements不变。
- 精确节点`server/tests/api/test_library_web_fixture.py::test_non_null_artwork_preserves_song_and_resource_identity`新增3个route参数：单Song、SongList、Album歌曲集合。先确认Repository回读非空ArtworkRef，断言完整8个公开封面字段、Song/album/file_uri身份、歌词、集合成员与只读后持久Song不变。初次夹具错误假定album_id直接持久化；查明Repository按专辑identity生成ID后，仅将夹具UUID固定（沿用本文件既有做法），未改生产归并规则。随后有效RED **3 failed**，均为`_song_response→SongResponse.artwork`的model_type ValidationError；不将夹具失败冒充业务RED。
- 根因：顶层from_attributes没有让嵌套不同domain/DTO类型自动兼容。生产仅`api/library.py::_song_response`一行改为`SongResponse.model_validate(song.model_dump())`，与现有collection/album/realtime递归转换一致；不删字段、不清空封面、不扩大schema。现有Realtime先model_dump已兼容，本批不改其测试或协议。
- 精确节点GREEN **3 passed**；随后整个`test_library_web_fixture.py` **4 passed**（含原null封面golden，未重写fixture）；指定`server/tests/api/test_library_api.py server/tests/invariants/test_realtime_library.py` **31 passed**；`npm --prefix web run test -- --run tests/invariants/global-artwork.test.ts --maxWorkers=1 --minWorkers=1` **5 passed**。后台fixture关闭observer，显式`APP_ENV=development MPD_MODE=mock`；CONFIG_DIR/MUSIC_ROOT/DATABASE_PATH/MPD_CONNECTION_PATH均指向自有`/tmp/mpd-b00c-83wrc4mu`，测试实际DB由tmp_path隔离，未访问真实媒体/live MPD。Python命令均`.venv/bin/python -m pytest -q`，cache_dir也在该临时目录。
- scoped `.venv/bin/python -m ruff check server/app/api/library.py server/tests/api/test_library_web_fixture.py`通过；首次F811为导入pytest fixture与同名测试参数的既有工具误报，按本文件原惯例标注，仅作用新参数行。后端只有既有Starlette/httpx弃用warning，无环境/业务回归失败；未改依赖/断言来压制真实失败。
- 仅增量修改上述2份代码/测试及本文本批状态；结束逐文件hash/权限/既有DB与connection文件比对、实际diff及`git diff --check/stat/status`检查，原成果及运行文件保留。未执行全量测试、typecheck/build、Docker、NAS/手机或Git整合；无Web修改故不触发typecheck。



### B01：最小配置与启动

Files：Create server/app/config.py、server/tests/test_config.py、server/tests/invariants/test_config_composition.py；Create server/app/player/capability_loader.py；Modify main.py、mpd_connection_service.py（仅默认源注入）、deploy/.env.example。
Interfaces：load_config(env:Mapping[str,str], config_path:Path|None=None)->AppConfig；AppConfig frozen、秘密不repr；lifespan先加载配置/解析active endpoint，再验证能力和决定runner启用，最后启动后台任务。能力文件由MPD_CAPABILITIES_PATH指定，JSON envelope含endpoint{host,port}、mpd_version、result（既有MPDCapabilities字段）；endpoint匹配且连接版本确认后才授予verified_operations，版本尚未取得不授予。兼容历史裸result需显式重新绑定证据，不静默认作当前目标。多个ALSA输出消费既有selector，使用配置名称/插件匹配且歧义拒绝，不固定output ID。
- [x] RED test_config.py::test_defaults_precedence_and_secret_redaction：12h/500ms、JSON/env/default、未知/非法、IPv6、password不model_dump/API/log。
- [x] RED test_config_composition.py::test_saved_endpoint_and_mode_are_applied_only_at_start：saved优先、损坏失败、prod不回退Mock、MPD离线可启动。
- [x] 实现配置装配；能力使用既有显式验证证明，不启动副作用探针；没有有效证明如实限制控制。
- [x] 文件/关系回归：test_mpd_connection.py、test_output_lifecycle_injection.py、test_realtime_observer_lifecycle.py、test_d6_runner.py。
Gate：**CLOSED / AUTOMATED PASSED，2026-10-11**。config仅main.py消费；不含通用配置UI/restart。B00C已独立闭合，原ORDER GATE阻塞解除。本轮按精确节点→文件→指定关系完成fresh重验；以下原实施证据保留其轮次归属。

关闭Gate的fresh证据：核查当前`_song_response`递归DTO转换及B00C测试，非空封面节点 **3 passed**、文件 **4 passed**；B01两个指定节点 **2 passed**、专项文件 **31 passed**、四组指定历史关系 **51 passed**，scoped Ruff与`git diff --check`通过。使用原`.venv/bin/python`，配置/音乐根/默认DB均指向自有`/tmp/mpd-b01-gate-4h7i8pr2`，各fixture另建临时DB；无live MPD或真实媒体。此次仅更新本文Gate与当前状态，不改产品、不重做RED、不执行Docker/NAS/手机或全量测试、不推进B02。

本轮简要证据（FINAL-CONFIG-001→Architecture §22.1 / SYS-MPD-CONNECTION-001）：
- 原`.venv` Python3.14.4 / pytest9.1.1 / Ruff0.16.9，已检查requirements，无环境或依赖修改。`load_config` frozen，env→JSON→default；saved地址优先且兼容无效旧env，损坏/未知/非法配置明确失败。password仅env，排除repr/dump；扫描默认43200s/0.5s，音乐根验证可读。
- 两个指定精确节点先RED（缺config模块/未装配config），后GREEN **2 passed**；能力与selector补充RED（缺loader/未注入selector）。随后完整`test_config.py`＋`test_config_composition.py` **31 passed**，含地址/版本不匹配、离线、旧裸result拒绝、启动顺序、无命令greeting与关闭、当前输出名/插件唯一匹配；补充启动/transport断言仅记fresh验证，不伪称其RED。
- 指定关系`test_mpd_connection.py`＋`test_output_lifecycle_injection.py`＋`test_realtime_observer_lifecycle.py`＋`test_d6_runner.py` **51 passed**。历史Adapter注入路径以`APP_ENV=production MPD_MODE=real`运行，`DATABASE_PATH`/`MUSIC_ROOT`为本轮自有`/tmp/mpd-b01-883173j2`；测试临时DB与Mock/协议替身，不连接live MPD。
- scoped Ruff（config/capability_loader/main/mpd_connection_service及两份新测试）通过。MPDConnectionService既有默认Callable无需改动，仅main注入最终配置；不复制第二保存owner。能力文件只接受endpoint/version/result envelope，匹配active地址与有预算greeting版本后授予；无证据/离线不启恢复runner且真实控制受限，不启动副作用探针。
- `.env.example`列明新环境名及JSON snake_case、单worker、当前ALSA name/plugin selector；Compose/HTTP进程应用保留B07，自动扫描参数装配保留B03。Docker/NAS/手机、生产build、全套server/Web测试 **NOT RUN**，不属于本批自动Gate。
- Git HEAD仍`14c6239`、分支不变；本轮初始manifest 381个文件保留，增量仅本批允许文件和本文状态。未提交/推送/PR/合并。独立审查无Critical/Important；实际增量diff及`git diff --check/stat/status`已核对通过。非阻塞审查项暂留：JSON scan/debounce目前接受boolean数值转换；启动saved文件读取两次存在外部同时替换时config与active地址不同的窗口（能力/Adapter均绑定最终active地址）。不在本轮扩大MPDConnectionService保存合同，后续如调整需先补RED。

### B02：最小URI映射

Files：Create server/app/player/music_uri.py、server/tests/player/test_music_uri.py、server/tests/invariants/test_uri_mapping.py；Modify mpd_adapter.py/main.py及必要Port模型边界；不改SQLite/Song.file_uri。
Interfaces：MusicUriMapper(local_root:Path, mpd_prefix:str='')；to_mpd(local_uri:str)->str；to_local(mpd_uri:str)->str。Adapter可选注入mapper，旧默认identity兼容。
- [x] RED test_music_uri.py::test_relative_uri_round_trip_and_escape_rejection：子目录/中文/空格/重复文件名/越界/symlink越界。
- [x] RED test_uri_mapping.py::test_mapped_execution_and_current_confirmation_preserve_occurrences：真实Adapter协议Fake＋Services，发送raw URI、回读local URI、重复Song occurrence及当前/History关系不变。
- [x] 应用映射于全部status/queue/sample输出及命令输入；日志诊断区分raw/local，不改公开Song定位语义。
- [x] test_mpd_adapter_tcp.py/test_execution_sample.py、test_d6_binding.py/test_d6_execution.py/test_d6_stock_joint.py及播放关系回归。
Gate：**CLOSED / AUTOMATED PASSED，2026-10-11**。已完成真实Adapter协议Fake＋Services/SQLite关系验证，不仅字符串转换unit test；NAS同一相对路径对应同一文件仍须B08实机确认，未声明实机通过。

本轮简要证据（FINAL-URI-001→Architecture §22.2 / MIN-URI-001）：
- 前置核查：当前`feature/task-9-web` / HEAD `14c6239`，保留dirty工作树；核查B01配置及main装配、Scanner绝对本地路径、Port/status/sample和D6既有确认/重试边界。原`.venv` Python3.14.4 / pytest9.1.1 / Ruff0.16.9，requirements未改，无依赖/环境变更。
- 两个指定节点先因缺`music_uri`模块RED，后GREEN；补充`test_uri_mapping.py::test_real_startup_injects_configured_mapper`先因mapper未注入RED，后GREEN。最终三个精确节点 **3 passed**，两个新文件 **9 passed**。覆盖子目录/中文/空格/同名/大小写、穿越/越界/symlink越界；Adapter原始命令与本地status/Queue/sample、重复occurrence当前切换/History、外层rollback后原计划重试不重发控制、同URI外部ID替换UNKNOWN及业务状态不变。补充既有关系断言记fresh验证，不虚称另有RED。
- 实现：唯一`MusicUriMapper`在真实Adapter启动时由`music_root/mpd_uri_prefix`注入；未注入的旧Adapter与Mock维持identity。所有URI输入及status/Queue/execution sample输出在Adapter边界转换，D6仍比较本地URI；错误typed失败且不清空/重排掩盖。诊断仅记录local_to_mpd/mpd_to_local方向与command，不输出完整路径或秘密。SQLite/Song.file_uri、Services业务和公开定位合同未改。
- 指定回归：`test_mpd_adapter_tcp.py`、`test_execution_sample.py`、`test_d6_binding.py`、`test_d6_execution.py`、`test_d6_stock_joint.py`及`test_playback_relationships.py` → **140 passed**。必要启动关系：`test_config_composition.py`、`test_mpd_connection.py`、`test_realtime_observer_lifecycle.py`、`test_output_lifecycle_injection.py`、`test_d6_runner.py` → **64 passed**；配置精确节点 **1 passed**、`test_config.py` **18 passed**。补充`test_mpd_adapter_errors.py`、`test_mock_mpd_injection.py`、`test_d6_current.py`、`test_d6_history.py` → **67 passed**。
- 全部命令使用`.venv/bin/python -m pytest -q`并按精确节点→文件→指定关系运行。默认DB/音乐根/cache指向自有`/tmp/mpd-b02-j4flt7gd`；各fixture另建tmp_path DB，网络仅loopback协议Fake，启动专项禁止打开连接。配置历史测试依赖各自DB父目录默认saved路径，运行该组时移除外层`MPD_CONNECTION_PATH`覆盖，仍只落在自有临时目录。两处旧Adapter工厂因新增注入参数先复现TypeError，仅补齐`uri_mapper`签名，精确节点 **2 passed** 后文件关系通过；协议fixture补齐已有moveid并按现有执行器准备/同步顺序断言，未修改播放生产逻辑。最终无未解决测试/环境失败，仅既有Starlette/httpx弃用warning。
- scoped Ruff（两份实现/main、两份新测试及两处必要工厂测试）通过；独立静态审查无可操作发现。实际diff与初始SHA256/权限manifest对比：增量仅新增3个Files、Adapter/main、两处工厂测试和本文；无既有文件删除或其他增量，`git diff --check/stat/status`通过核查。未commit/push/PR/merge；全量server/Web、typecheck/build、Docker/NAS/手机 **NOT RUN**。不推进B03及后续Batch。


### B03：自动及时发现、更新与确认

Files：Create services/library_sync_service.py、services/library_change_detector.py、models/library_sync.py、services/library_runtime.py；Modify api/library.py/api/schemas.py及tests/api/test_library_api.py的扫描合同；Extend player/ports.py/mpd_adapter.py/mock_mpd.py/capabilities.py、services/events.py；Modify main.py/library_scanner.py（仅协作注入）；Create tests/services/test_library_sync_service.py、test_library_change_detector.py及invariants/test_library_sync.py。
Interfaces：Port.has_library_uri(song_uri:str)->bool；LibrarySyncService.request_scan(paths:tuple[Path,...]|None, trigger:str)->str返回activity_id，get_state()->LibrarySyncState；LibraryChangeDetector.run()/close()；LibraryRuntime.run()/close()单owner。
- [x] RED test_library_change_detector.py::test_new_stable_file_is_detected_without_rescanning_unchanged_media：可控2秒检查/500msdebounce，暂不可读/半写入恢复，mount失效不标全库missing。
- [x] RED test_library_sync.py::test_commit_update_confirmation_and_next_generation_are_ordered：SQLite真实提交→SYNCING→update→精确URI存在/删除；阻塞期间新文件下一轮，旧确认不盖新轮。
- [x] RED test_library_sync_service.py::test_disconnect_timeout_retry_and_shutdown_preserve_business_state：60秒预算/2-5-15-30秒retry、重连、取消，无播放或Queue/History变化。
- [x] 给只读Port查询补Mock/真实/Verified一致性测试；目标新命令不借历史commands列表冒充runtime verified。
- [x] 注入scanner可选updater进入统一协调路径，确保一次扫描只触发一次更新；原completion顺序不变；不让API等待60秒确认、不保持DB outer事务跨等待。
- [x] 手动scan请求使用短事务接纳job并返回202 ScanJobResponse{activity_id,status:'accepted'}；原scan_full Service接口保留供内部/历史测试。更新api/library.py、schemas.py及test_library_api.py的该endpoint断言，接纳replay不新增job；该API增量为本Batch允许范围。
- [x] 新文件/节点GREEN后运行test_library_scanner.py/test_library_watch.py/test_library_scheduler.py、test_task3_events_and_mpd.py、test_library_reconciliation.py、test_realtime_library.py及事务关系。
Gate：**AUTOMATED PASSED / NAS TIMELINESS HUMAN PENDING，2026-10-11**。实现及指定自动Gate完成；update接受不当SYNCED，元数据签名检查与单owner确认已验证。真实NAS规模及时性未测，整体Gate保持待确认；本批未运行Docker/NAS/手机，不以本地GREEN抵扣实机。

本轮简要证据（FINAL-SYNC-001 → Library §7.2 / LIB-MPD-SYNC-001）：
- 前置：核查`feature/task-9-web` / HEAD `14c6239`、当前Scanner提交/完成事件、B01配置装配、B02 URI边界、能力与API terminal事务。保留当前dirty成果；原`.venv` Python3.14.4 / pytest9.1.1 / Ruff0.16.9，requirements、依赖、环境未改。
- 新协调器/状态/变化发现/runtime：启动一次完整校准；2秒metadata签名检查、500ms稳定合并、配置12h校准进入同一队列。只变化文件进入解析/哈希；删除完整校准、mount不完整/替换及扫描中mount变化均不提交批量MISSING。半写入/不可读重试保留已提交索引；重启不沿用成功证明。Scanner仅加batch_observer协作，原`scan_full`与commit→optional update→completion合同保留。
- 短事务接纳请求，outer commit后才排job；`POST /api/library/scan`返回202 `{activity_id,status:'accepted'}`，terminal失败不启动job，同key replay不再次接纳。后台scan提交时登记SYNCING，update一次后才确认；等待期间无DB outer事务或外层Port锁。确认预算从扫描提交后开始60秒，1秒轮询，2/5/15/30秒封顶重试，同generation/activity不增生；新轮保留未确认的旧URI存在/缺失预期，新提交事实可覆盖同URI。
- Port的Mock/真实/Verified精确查询独立于Queue；Adapter用映射后的`find file URI`并检查精确file字段，loopback TCP Fake覆盖中文/空格/不匹配/缺失及无嵌套锁。`find`出现在commands不授予`has_library_uri`，仍须与当前endpoint/version绑定的独立runtime evidence；本轮未连接真实目标、未运行副作用探针。[协议依据](https://mpd.readthedocs.io/en/stable/protocol.html)。同步不发播放/Queue/History控制。
- RED→GREEN：三个指定节点初始缺新模块RED；202接纳、半写入新文件、mount扫描中替换、startup与scheduler/发现重复、确认预算、未完成目标跨新轮、不可读请求根均补精确RED并GREEN。独立审查1个Important（移动旧URI缺失确认在下一轮丢失）用`test_failed_move_absence_confirmation_survives_the_next_generation`复现RED→最小修复→GREEN；无其他审查发现。超时测试虚拟重试曾抢过FAILED观察窗口，改用retry barrier保留完整60秒/FAILED断言，未弱化断言或改生产码掩盖。
- fresh顺序与结果：三个指定精确节点 **3 passed**；三份新文件＋`test_library_api.py` **37 passed**。指定`test_library_scanner.py/test_library_watch.py/test_library_scheduler.py/test_task3_events_and_mpd.py/test_library_reconciliation.py/test_realtime_library.py`及`test_transaction_relationships.py/test_transaction_commit_hooks.py` **79 passed**。必要Port/装配关系`test_mpd_adapter_tcp.py/test_capabilities.py/test_execution_sample.py/test_uri_mapping.py/test_config_composition.py/test_mpd_connection.py/test_realtime_observer_lifecycle.py/test_output_lifecycle_injection.py/test_d6_runner.py` **79 passed**。两项历史启动测试需production默认real模式且显式Fake Adapter；初次mock外层env错误后仅校正运行环境，精确节点 **2 passed**、全文件集合复验通过，未改其断言。另有必要HTTP历史节点从同步200改成202＋真实后台Service，保留terminal rollback、retry/replay、revision/Queue/History断言；conftest仅提前关闭新runtime，防旧fixture触发扫描/网络。
- 所有Python测试用`.venv/bin/python -m pytest -q`；Gate命令的默认DB/config/music/cache指向自有`/tmp/mpd-b03-xk7ntn8d`，fixture DB/媒体另用tmp_path，网络仅loopback Fake。scoped Ruff及`git diff --check`通过；仅既有Starlette/httpx弃用warning，无剩余代码/环境失败。初始hash/权限manifest核对：增量仅本批7个新文件、允许生产边界、API测试、两份必要协作fixture/HTTP合同回归和本文；无文件删除/权限变更或其他Batch代码增量。未commit/push/PR/merge。全量server/Web、Web typecheck/build、Docker/NAS/手机 **NOT RUN**。

NAS及时性验收卡（本轮不执行，待后续授权部署/验收阶段）：在实际文件树规模及endpoint/version的`update/database_update_status/has_library_uri`能力证明具备后，向自有测试子目录添加稳定小曲目，至少3轮记录“文件稳定→扫描/同步活动开始”（目标≤5秒）、MS扫描、MPD精确索引确认三段耗时；MPD处理耗时单列。再测删除/断线恢复及不可读挂载不会批量MISSING。B05/B08接线后用同次证据验无需刷新；反馈曲库规模、每轮耗时及PASSED/FAILED/NOT RUN后才评估关闭实机Gate。


### B04：AppBar活动区专属完善

Files：Modify web/src/stores/notices.ts、components/layout/AppBar.vue/AppShell.vue、components/player/PlaybackStatus.vue、runtime/playerSession.ts/taskActions.ts及styles/app.css；Create services/diagnostics.ts、tests/invariants/appbar-activities.test.ts；Extend global-notices/player-notices/shell-navigation。
Interfaces：Notice增加status、description、resource、updatedOrder；NoticeStore统一upsert活动、recent(max=5)、summary；保留retry/read函数和原TaskActions owner。字段名在本Batch固定后后续复用，不另建通知store。
- [x] RED appbar-activities.test.ts::all_sources_share_one_center_and_five_recent_entries：播放专用＋通用共7项只显示5、状态变化排序、同一事项不重复、成功保留且上限5、poll不抢最近顺序。
- [x] RED appbar-activities.test.ts::hidden_unknown_keeps_original_intent_and_aggregate_warning：第6项unknown仍黄色，裁剪/切页不丢owner；汇总只读检查让旧事项回到最近5项而不新增第6项或重发mutation；随后重试原key，confirmed-read失败只GET。
- [x] RED appbar-activities.test.ts::epoch_motion_focus_and_long_copy_preserve_shell：旧成功不回新epoch，Escape/焦点/live region、reduced-motion、长中文/URI不推动壳；正文/按钮比例与44px触摸。
- [x] 接入所有现有notices/operation/statusFeedback/连接及媒体说明；简短用户动作名替代HTTP方法＋URI；diagnostics记状态变化且脱敏，完整技术详情不堆浮层。
- [x] 完整文件GREEN后global-notices/player-notices/player-controls/player-lyrics/shell-navigation/settings回归及typecheck。
- [x] 手机视觉用户验收：2026-10-12用户反馈“可以验收”，记录为USER ACCEPTED；原320级宽/字号/触摸验收卡保留，未提供的逐项测量不记为已测通过。
Gate：**CLOSED / AUTOMATED PASSED / MOBILE VISUAL USER ACCEPTED，2026-10-12**。基于本批fresh自动证据及用户对B04测试页面的“可以验收”反馈关闭视觉Gate；用户未提供设备、字号、320级宽/触摸/reduced-motion逐项测量，不把这些细项另记为已测PASSED。不关闭B03 NAS及时性或B08真实交付Gate，已记录的两项轻微问题仍延期。

本轮简要证据（FINAL-ACTIVITY-001 / FINAL-LOG-001 → Visual §6、Architecture §22.3）：
- 前置核查：`feature/task-9-web` / HEAD `14c6239`；按当前源码继承B00–B03成果，B03 NAS及时性仍HUMAN PENDING，不以历史GREEN证明实机。原`.venv` Python3.14.4 / pytest9.1.1 / Ruff0.16.9及requirements已核查，未修改环境或依赖。
- Owner→projection：既有PlayerSession/PlayerActions、TaskActions和各资源notice统一进入原NoticeStore；输出Activity固定`status/description/resource/updatedOrder`，旧`set`入口兼容，`upsert/recent(max=5)/summary/readUnfinished`供后续复用。状态变化排序、总展示≤5、成功缓存≤5；隐藏unknown继续汇总黄色与保留原owner。汇总只调用已有read，原key重试与confirmed后只GET关系不变。跨epoch移除旧成功，TaskActions成功先等权威read，不以ACK或handoff超时造“已同步”。
- UI/diagnostics：AppBar只消费这一投影，去掉独立operation/statusFeedback段；短动作名替代默认HTTP方法/URI，长文限长/安全换行、浮层内滚动，按钮继承正文且至少44px，保留唯一live region、Escape/焦点返回和reduced-motion CSS。浏览器日志只记本地关联序号/白名单来源/状态，不输出原key、路径、body或秘密；logger失败隔离，不改变业务结果。既有资源提示的`remove`仍为撤下，不猜它是成功还是切页取消；只有owner明确确认才记录success。
- RED→GREEN：三个指定节点及状态日志脱敏节点先确认缺行为RED；补精确测试复现ACK后read未完成的早success、player UI逐字段更新的瞬时failed噪声、console抛错和ACK+unknown观察在handoff超时后误成功，均最小修复后GREEN。独立审阅的重要项（logger异常、handoff早成功）已闭合。旧global-notices三项成功撤下断言及player-controls两项pending/旧aria断言与Visual增量冲突，按新合同最小更新，保留原key/GET-only/业务事实/几何断言；扩展player-notices/shell-navigation覆盖真实来源上限和成功跨页。
- Fresh验证顺序：`npm --prefix web run test -- --run tests/invariants/appbar-activities.test.ts -t 'all_sources_share_one_center_and_five_recent_entries|hidden_unknown_keeps_original_intent_and_aggregate_warning|epoch_motion_focus_and_long_copy_preserve_shell' --maxWorkers=1 --minWorkers=1` → **3 passed**；该完整文件 → **8 passed**；指定`global-notices/player-notices/player-controls/player-lyrics/shell-navigation/settings.test.ts`六文件（同样`--run --maxWorkers=1 --minWorkers=1`）→ **68 passed**；`npm --prefix web run typecheck`与`git diff --check`通过。一次扩展命令重复`-t`导致CLI参数错误，校正后精确节点/文件通过；六来源测试误期望第6项显示，按明确五项合同改为验证隐藏且汇总恢复保留，未改生产码掩盖。无剩余环境/测试失败。Python产品未改、未执行pytest，Ruff不适用于本轮TS/Vue；全量suite/build、真实浏览器320测量、手机/NAS/Docker **NOT RUN**。
- 范围：相对本轮前hash/权限快照，仅7个允许生产文件、5个相关测试文件及本文增量；未删除或改权限、未触碰其他Batch源码、原dirty成果原地保留。临时审计证据在自有`/tmp/mpd-b04-n69xhe8l`，不纳入repo。未commit/push/PR/merge，不推进B05。
- 审阅轻微项延期（不隐藏、未顺手扩大修复）：连续独立失败Stop intent可能复用同一播放活动id（现有产品无Stop入口；原mutation key不受影响）；短文路径替换的`\b`边界不能替换独立`/api/...`或`/music/...`，仍会限长/换行，logger不输出原文。两项均不是自动或视觉验收的已验证成功结论。

手机验收卡（2026-10-12用户已接受；以下为原检查范围，非逐项测量结果）：用320级宽及实际手机字号，逐项查看正常/同步/错误、最近5项、长中文/URI、正文与按钮比例、44px触摸、关闭/Escape/焦点返回、减少动态效果；AppBar中心与Player/导航几何应保持。把旧unknown挤出最近5项后应仍黄色，汇总读取让原项回到最近且不重发mutation；成功跨页保留、重连新epoch不带回旧成功。用户整体接受已记录；设备/浏览器/字号及各项测量详情未提供，不虚构结果。本卡不要求本批启动Docker或接入真实MPD。


B04用户接受记录：2026-10-12，测试页面`http://192.168.3.18:5173/`（当前源码Vite、临时DB与7首合成FLAC、显式曲目MockMPD）。本机通过局域网地址验证页面/深链接/API、播放与暂停HTTP200、WebSocket首帧snapshot及paused/CONFIRMED；这些是本地启动烟测，不是真实MPD/声音/NAS验收。用户随后反馈“可以验收”，据此记录本批视觉USER ACCEPTED。本次仅更新本文，不改源码、不重跑自动suite、不进行Git整合或推进后续Batch，保留运行服务。

### B05：同步状态经真实wire自动收敛

Files：Modify models/realtime.py、services/state_service.py/realtime_coordinator.py/events.py、api/realtime_schemas.py；Web types/api.ts、services/wire.ts、stores/player.ts、AppShell.vue；Create server/tests/api/test_library_sync_wire.py、server/tests/invariants/test_library_sync_wire.py、web/tests/fixtures/library-sync.json、web/tests/invariants/library-sync.test.ts。
必要接线范围补充（本轮已核对）：main.py注入同步event publisher；library_sync_service.py在扫描outer commit内登记SYNCING并发布部分确认进度。两处为完成本批同切面/传播合同所必需，不改B03发现、目标确认或重试算法。
Interfaces：FullStateSnapshot.library_sync:LibrarySyncState；invalidate domain='library_sync'；Web parseSnapshot与notice投影消费同一DTO。可注入同步state facade，历史未装配fixture默认IDLE，不伪SYNCED。
- [x] RED server/tests/invariants/test_library_sync_wire.py::test_sync_sequence_does_not_change_library_revision：真实scanner/DB/coordinator，newSong可见同步SYNCING同切面；同步确认只sequence变，Queue等不变。
- [x] RED library-sync.test.ts::server_fixture_updates_appbar_without_manual_refresh：真实后端golden→decoder→realtime→AppShell，新增/确认/失败自动显示，列表无重复同步提示。
- [x] RED server/tests/invariants/test_library_sync_wire.py::test_old_generation_disconnect_and_initial_snapshot_recover：晚到旧轮、no-op扫描仍同步可见，断线stale/reconnect完整首帧，多个client隔离。
- [x] 明确JSON decoder/domain允许集合、snapshot schema和golden同步更新；full snapshot GET不发Port控制/查询。
- [x] 文件GREEN后realtime snapshot/delivery/handoff/library及Web wire/realtime/resource-cache/global-notices/task9-relationships回归。
Gate：**CLOSED / AUTOMATED PASSED，2026-10-12**。真实SQLite/Scanner/MockPort→公共REST/WS golden→decoder/realtime→AppShell有fresh proof；无需手动刷新，旧epoch/sequence/generation拒绝，复用原WS/自动GET/最近5项活动。不声明真实NAS/MPD或手机通过；B03 NAS及时性与B08实机Gate继续待确认。

本批简要证据（FINAL-SYNC-WIRE-001 → Library §7.2 / Architecture §12）：
- 当前工作树核查：`feature/task-9-web` / HEAD `14c6239`，继承既有dirty成果；原`.venv` Python3.14.4 / pytest9.1.1 / Ruff0.16.9、requirements已核查。初始新测试的DB由real_client强制tmp_path且conftest关闭后台任务；之后所有测试入口另显式指向自有`/tmp/mpd-b05-qtjkfoak`配置/音乐/默认DB，只有临时合成媒体及MockPort，无live MPD。
- Owner→wire→projection：协调器持有深复制的已提交同步state；扫描变化与SYNCING联合登记，确认/失败/部分计数独立推进sequence，时间变化和重复poll不虚增revision/sequence。完整state读取只消费缓存，无扫描或Port查询。历史未装配owner为IDLE；Web缺字段兼容仅为IDLE，不补造SYNCED。同步活动按activity_id复用原notice投影，断线/读取失败标过期，新epoch清除旧同步证明；原mutation/retry owner不变。
- RED→GREEN：两个指定后端节点先因缺字段失败；Web自动AppBar与旧generation节点分别复现无活动及状态倒退；额外部分确认节点复现计数未传播后GREEN。精确节点：后端指定两项＋golden **3 passed**，部分确认 **1 passed**；Web指定自动收敛 **1 passed**，完整新文件 **2 passed**；两个后端完整新文件 **4 passed**。
- Fresh关系回归：`test_realtime_snapshot.py/test_realtime_delivery.py/test_realtime_handoff.py/test_realtime_library.py`及必要`test_web_wire_fixture.py/test_task9_wire_fixture.py/test_realtime_commit_visibility.py/test_library_sync.py/test_library_sync_service.py/test_config_composition.py` → **95 passed**。Web `wire/realtime/resource-cache/global-notices/task9-relationships/appbar-activities.test.ts` → **70 passed**。scoped Ruff、typecheck、git diff --check通过。全量suite/生产build/Docker/NAS/手机 **NOT RUN**，仅现有Starlette/httpx弃用warning。
- 失败归因与最小校正：临时MUSIC_ROOT首次未创建导致配置setup错误，仅创建自有目录；新API文件补注册real_client fixture；golden按本轮terminal sequence消费帧，避免把上一轮通知当失败帧。旧snapshot字段集合与两份golden按新增DTO更新；wire fixture显式固定IDLE时间。Task9 golden按同一隔离Mock启动环境重建（启动观察sequence较旧环境+2，业务资源/身份不变）；Task9 Web旧“成功撤下”断言按B04明确成功历史合同更新为“已同步”，未弱化业务确认/原key/跨页/只读保护。
- 独立只读审阅：无Critical/Important。低优先级边界项延期：同一outer transaction中连续多次调用stage_library_sync时，排序只比较已提交state，逆序staged generation/timestamp可能覆盖；当前单同步owner每事务只登记一次，正常B05链不触发。后续若允许批量staging需先补事务内排序证明；本轮不扩展这个入口。
- 范围审计：初始文件hash与实际diff核对，仅本批6个后端/4个Web生产文件、2个新后端测试/1个新Web测试、新golden及必要历史schema/golden/关系断言和本文增量；无删除、无依赖/环境/运行文件变更。保留既有运行服务；无commit/push/PR/merge，不推进B06。


### B06：基本健康与排障日志

Files：Create services/health_service.py、logging_config.py、tests/test_logging.py、tests/invariants/test_health_relationships.py；Modify main.py/api/system.py/test_health.py、相关错误日志调用；Web复用B04 diagnostics。
Interfaces：HealthService.read()->HealthResponse(status,ms,mpd,library_sync)；configure_logging()幂等；MPD读取经Service/Port且预算，不直接API访问Adapter。
- [x] RED test_health_relationships.py::test_mpd_failure_is_independent_and_health_has_no_control_side_effects：实际临时SQLite、Port失败，200/ok+mpd unavailable；SQLite失败503/error；无update/play调用。
- [x] RED test_logging.py::test_activity_phase_and_errors_are_correlated_without_secrets：每状态变化一次，密码/完整key/body不泄露，重复configure不重复handler。
- [x] 更新健康测试兼容正常status=ok；回归test_system_reads.py/test_system_read_relationships.py及架构方向测试。
Gate：**CLOSED / AUTOMATED PASSED，2026-10-12**。三项独立健康读取、关联安全日志及指定关系回归已fresh验证；本批无手机/NAS人工Gate，不抵扣B03/B08实机验收。

必要范围补充：repositories/database.py增加只读SQLite探测；library_sync_service.py/mpd_adapter.py接日志，不改控制/同步算法。conftest先取消observer避免启动抢跑；相关system读取测试显式注入Mock，两份后端golden builder显式只读采样以保留原golden与断言，Web源码/fixture未修改。
简要证据：两个指定节点RED→GREEN；B06 Gate三文件 **9 passed**，system/架构方向 **21 passed**，必要历史关系 **88 passed**；B04 diagnostics精确节点 **3 passed**、完整文件 **8 passed**；scoped Ruff与diff检查通过。前置、精确命令、边界修复及保留范围见[B06验收记录](../../acceptance/2026-10-12-v0-1-nas-b06-health-logging.md)。未运行全量、build/typecheck、Docker、NAS或手机；未推进B07。

### B07：真实生产构建与NAS部署准备

Files：Modify deploy/Dockerfile/docker-compose.yml/docker-compose.dev.yml/.env.example；Create deploy/README.md、server/tests/test_deploy_contracts.py；Modify main.py生产SPA静态路由及server/tests/api/test_web_acceptance.py（若深链接确需修复）、README。
Interfaces：生产同源REST/WS；不存在/api路径不得fallback为HTML；前端深链接支持SPA；dev/prod数据库配置分离。
- [x] RED test_deploy_contracts.py::test_prod_and_dev_persistence_modes_and_single_worker：环境/只读music/配置位置/单worker/轮转/健康路径；仅配置结构测试，不伪运行Compose。
- [x] 若新问题，RED test_web_acceptance.py::test_spa_deep_link_and_unknown_api_are_distinct：/library等HTML，未知/api 404JSON；按真实baseline最小修改。
- [x] npm --prefix web run typecheck；npm --prefix web run build；.venv/bin/python -m ruff check server/app server/tests（广域遗留单列）；检查Docker COPY/产物路径一致。
- [ ] 明确NAS真实music root、MPD相对根/IPv6/port/password注入、数据/配置挂载和镜像架构；不把本机可达性假定为NAS可达性。
- [ ] 在有Docker且用户授权的NAS：compose config→build→up→health/REST/WS/静态产物核验；本机普通验证不启Docker、不改网络/挂载。
- [ ] 用户手动重启容器，确认saved地址生效及持久数据未丢；提供最短操作与日志查看卡。update.sh/restart按钮延期。
Gate：**READY FOR NAS / LOCAL AUTOMATED PASSED，2026-10-12**；NAS构建/容器部署/手动重启持久化 **HUMAN PENDING / NOT RUN**，整体不CLOSED。

简要证据（FINAL-DEPLOY-001→Architecture §22/§9–11）：部署结构、SPA深链接和HTTP启动配置RED→GREEN；指定精确节点 **3 passed**、两份Gate文件 **7 passed**；必要健康/配置/observer/output关系 **34 passed**。Web typecheck、临时目录生产build、fresh产物HTML/JS/CSS/404检查及广域Ruff通过。Docker COPY产物位置原本正确，仅补防本机node_modules覆盖镜像依赖的RED→GREEN。环境、前置、精确命令及剩余项见[B07验收记录](../../acceptance/2026-10-12-v0-1-nas-b07-deploy.md)；最短实机步骤与反馈见[部署卡](../../../deploy/README.md)。实际NAS架构/根目录/endpoint待用户确认，不采用历史值或示例冒充本轮事实；未运行Docker/live MPD/手机，不推进B08。

### B08：真实功能联合验收

Files：Create docs/acceptance/v0-1-nas-minimal.md；必要缺陷先立最小corrective和测试，不把本Batch作为任意重构入口。
- [ ] 连接/About与输出事实；现有能力证明匹配实际endpoint，缺能力显式验证后才开放；物理声音由用户确认。
- [ ] Library/Search/分类/非空封面/歌词；播放、Pause/Resume/seek/Next/Previous、Stop生命周期（既有API）、AutoPlay、重复occurrence和current-target。
- [ ] Queue点击/移动/删除/清空/保存、集合PlayAll/Shuffle、Playlist CRUD/reorder、Favorites跨页一致；错误/unknown/断线时不伪成功。
- [ ] 用户在测试子目录添加自有曲目：自动发现→AppBar同步中→精确MPD识别→已同步，全程不刷新；再手动扫描；记录发现/扫描/MPD确认三段耗时，至少3轮。MS/MPD根映射一致，容器内可读。
- [ ] 正常可达、稳定小文件的单项元数据变化目标：5秒内进入扫描/同步活动；MPD索引/媒体解析时间另列，不承诺5秒完成。大型NAS实测达不到则记录原因和最小修复，不能拿12h兜底抵扣及时性。
- [ ] 断线恢复、容器手动重启与配置/DB持久化；AppBar最多5项、所有页面统一、完整错误查Docker/browser日志。
- [ ] 用户IPv6期间不能使用Codex时，事先准备部署/验收卡→用户独立切网测试→恢复网络反馈；不要求agent同时在线、不伪造观察。
Gate：所有实际功能逐项PASSED/FAILED/NOT RUN；必要项无未闭合失败，物理声音/手机视觉依据用户反馈。旧Task9 B10相交项目引用同一次真实证据，经其原Gate确认后更新状态，历史不删改。

### B09：最终验收与交接

Files：本文仅更新Gate状态；新archive/final acceptance记录fresh证据；README/主Plan/文档地图更新高层状态。
- [ ] 新config/mapping/sync/activity/wire/health/deploy文件先逐节点/文件/相关invariants通过；运行全部server/tests/invariants及受影响Task9 relationships。
- [ ] 自有临时DATABASE_PATH完整.venv/bin/python -m pytest -q server/tests；完整Web npm --prefix web run test -- --run --maxWorkers=1 --minWorkers=1。
- [ ] .venv/bin/python -m ruff check server；npm --prefix web run typecheck；npm --prefix web run build。环境失败、遗留问题、目标Docker验证分列，不能改环境掩盖。
- [ ] 逐Contract ID→Spec→owner→精确proof→fresh结果追溯；读实际diff/check/stat/status，确认没有DB/env/依赖/音乐或无关变更。
- [ ] 核对B08真实结果，分别报告实现、自动、NAS构建部署、手机/设备、延期项；未执行项不得记完成。
Gate：最小真实交付范围完成；延期备份/一键更新/PWA不抵扣也不阻塞修订范围。发布tag/commit/push/PR/merge仍需用户单独明确授权。

## 4. 文档范围与后续交接

B00轮次已完成基线核查与文档状态同步；本轮B01实施与验证见本批简要证据。新增2秒检查/1秒确认/60秒预算等为可注入实施默认值，用户审阅可调整；不能把本文当作这些行为已存在的证据。已有未来Task限制按主Plan本次明确合并分配解除到B01–B08所列文件/功能，不能借“最终交付”实施延期项。

B00C已独立闭合，B01/B02已fresh验证并关闭自动Gate；B03实现与自动验证完成，NAS及时性待确认；B04已关闭自动及用户视觉Gate，B05已关闭自动Gate；B06已关闭自动Gate；B07本地准备与自动Gate通过，NAS部署/重启持久化待确认；B08–B09仍未执行，后续Batch需授权。遇到协议查询不可用、真实NAS规模性能或路径映射不成立，记录最小阻塞并提出局部修正，不先改URI模型/引入复杂基础设施。所有完成证据写入新acceptance，不把日志堆回本文。


## 5. 精确验收命令索引

新文件TO CREATE；先运行各Batch列明的`文件::节点`，再该文件，最后本表关系集合，不能直接用全量替代。服务/协议unit文件按Batch Files运行同样的`.venv/bin/python -m pytest -q`；本表不重复旧计划全部回归命令。

| Batch | 精确新增关系/专项文件命令 |
|---|---|
| B00C | `.venv/bin/python -m pytest -q server/tests/api/test_library_web_fixture.py` |
| B01 | `.venv/bin/python -m pytest -q server/tests/test_config.py server/tests/invariants/test_config_composition.py` |
| B02 | `.venv/bin/python -m pytest -q server/tests/player/test_music_uri.py server/tests/invariants/test_uri_mapping.py` |
| B03 | `.venv/bin/python -m pytest -q server/tests/services/test_library_sync_service.py server/tests/services/test_library_change_detector.py server/tests/invariants/test_library_sync.py` |
| B04 | `npm --prefix web run test -- --run tests/invariants/appbar-activities.test.ts tests/invariants/global-notices.test.ts tests/invariants/player-notices.test.ts tests/invariants/shell-navigation.test.ts --maxWorkers=1 --minWorkers=1` |
| B05 backend | `.venv/bin/python -m pytest -q server/tests/api/test_library_sync_wire.py server/tests/invariants/test_library_sync_wire.py` |
| B05 Web | `npm --prefix web run test -- --run tests/invariants/library-sync.test.ts tests/invariants/wire.test.ts tests/invariants/realtime.test.ts tests/invariants/resource-cache.test.ts --maxWorkers=1 --minWorkers=1` |
| B06 | `.venv/bin/python -m pytest -q server/tests/test_health.py server/tests/test_logging.py server/tests/invariants/test_health_relationships.py` |
| B07 | `.venv/bin/python -m pytest -q server/tests/test_deploy_contracts.py server/tests/api/test_web_acceptance.py` |

每条命令的PASSED只证明其断言，需按Batch再执行列明历史关系回归和人工Gate。Docker命令只在B07目标环境阶段执行；B00–B04结果见各批证据。本轮B06指定节点/文件及必要关系回归已执行，结果见B06验收记录；B07本地指定命令已执行，详见B07验收记录；NAS命令及B08–B09未执行。
