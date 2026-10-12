# Task 9 — 全部歌曲滚动与大集合播放整改

日期：2026-10-13。范围：feature/task-9-web，基线32f2996；用户授权测试192.168.3.94:18000，并提交/push/CI镜像交付。不改变公开API、依赖、数据库模型或MPD模式合同。

## 证据与原因

- 实机曲库GET返回406首AVAILABLE歌曲。旧页面每次snapshot刷新，SongRow的数组getter watcher都触发close；所有行调用focus，最后一行夺取焦点。浏览器直接核对最后一行ID与activeElement所属行相同，shell scrollTop=25612.412。新回归在旧代码报focus被调用3次。
- 旧部署LIBRARY顺序播放请求45秒无响应，随后GET state也超时；几分钟后自行恢复，原key HTTP200 replay、Queue409项、观察CONFIRMED。没有删除数据库。因此这次观测证明长事务阻塞读取，不证明数据库损坏或永远不能恢复。
- 旧队列规划把即将删除的旧条目也当作排序约束，对每个新条目追加后再move；每次move另读playlistinfo，执行确认也逐命令读取全队列。本地406首真实Service→Adapter→TCP模拟链原计划3692条MPD请求。整改按保留条目的相对顺序规划，新条目有序追加，旧条目最后删除；保留逐命令回执、漂移确认、固定意图及同key重试语义。
- 实机只读status另发现consume=1。现行Playback §8.9.5要求random=0/repeat=0/single=0/consume=0；其它模式暂停自动接管。歌曲自然结束后consume删除条目会导致映射失效。此运行配置独立于滚动修复，未偷偷覆盖；请求用户授权改consume=0并重新明确选曲。Library SYNCED与Playback绑定不同，不能混同。

## 修复与自动验证

- SongRow仅监听标量song_id/epoch；只有打开的菜单才归还焦点，并使用preventScroll。背景snapshot不关闭菜单、不聚焦歌曲行。
- 队列规划回归旧实现因冗余move失败，整改后通过；扩大为406首、固定随机种子与顺序两种输入，验证业务Queue和MPD完整顺序、零冗余move、观察CONFIRMED。两项6.89秒通过（协议模拟器，不是NAS耗时承诺）。
- targeted：后端integration/playback/D6/realtime Queue共133通过；Web song-actions/library-collections/task9关系共15通过。
- 完整后端1661通过（106.22秒，发生于新增scale参数化前）；完整Web318通过。随后新增406首参数化2项通过；CI将执行包含两项的完整suite。
- Web typecheck/build、全server/app与server/tests Ruff、git diff --check通过；既有Starlette TestClient弃用提示归环境警告，无依赖修改。
- requesting-code-review独立只读审阅无Critical/Important。保留限制：每个剩余命令仍完整读取MPD队列，不能声称已取得NAS大库耗时上界。
- 本地修复Web通过代理读取实机406首：首次scrollTop=0，手动向下到1440，背景刷新未抢焦点；旧部署仍未替换。SSH root@192.168.3.94可达但本机已有认证被拒绝，未操作容器或读取容器日志。

## 交付边界

实现及上述自动测试完成；镜像以本次提交实际CI结果交付。容器首次启动/重部署后的顺序与随机播放耗时、consume配置调整后的自然换曲恢复尚未完成实机验收。无数据库删除，无本地Docker或虚拟环境修改，不把代码修复当作全部运行问题已关闭。

## 同轮实机恢复补充

用户随后明确允许改consume=0并验证。原生MPD TCP consume 0返回OK，status核对为0；通过新key调用SONGS单曲集合明确选曲，HTTP200（旧容器清理400余项耗时27.76秒），GET state观察CONFIRMED/matches_current=true，曲库SYNCED。seekcur定位歌曲结束前2秒后等待实际自然换曲，业务song_id变化，实际下一首位置已由Service归并至0，观察仍CONFIRMED/matches_current=true、fresh、无error、reconciliation_required=false。没有删DB或重启容器；设置MPD模式后无需删DB即可恢复。MPD重启后模式是否持久取决于该MPD自己的state_file配置，未读取NAS配置。

最终本地针对性后端包含406首参数化共134通过（13.65秒）；完整suite数字仍属于前述轮次。修复Web使用实机API在背景快照更新后保持scrollTop=1440、无歌曲行焦点，向上滚动可到720。容器中的新版代码尚未部署，因此新版容器首次启动及大库实际耗时仍待重部署验证；未冒称已在NAS验证代码性能。

## 用户复测后的第二次整改：集合准备期间提前播放

用户复测全部歌曲展示已正常，但Queue/控件仍异常。重新读取实机：consume=0、MPD连接正常，实际队列413项、暂停current position=7；SQLite业务Queue15项，observed actual_freshness=fresh、sync_status=UNBOUND、control_target=null。当前URI展示与控制禁用源于失绑，不能宣称MPD连接失败；此前单曲重绑/一次自然换曲通过不能证明全库播放问题关闭。

新永久RED：`test_collection_does_not_start_current_until_the_complete_queue_is_prepared`，真实Service→Adapter→TCP fake，在addid期间模拟顺序模式（consume=false）的当前转移，旧代码报UNKNOWN current changed during execution。原因是play_context先播放临时当前项，然后慢慢准备全库；中途当前变化导致本地事务回滚，但MPD已添加的前缀无法由SQLite回滚。

修复：仅用户明确替换集合的play_context走固定context执行计划；已有MPD队列使用经过能力检查的clear，按固定occurrence顺序add全部项目，最后才play一次。普通队列增删/移动不改。clear纳入逐命令sent/ACK/confirmed回执、独特结果核验与generation/connection/partition/version fences，不因成功clear就假称业务提交。目标endpoint既有`deploy/config/mpd-capabilities.json`与能力文档实测已证明queue_clear；未改能力证据、未绕过VerifiedPlayerPort。

已确认准备保留为私有synced_entries/sync_sample，退役旧binding而不提前增加generation，最终Queue sync才bind；独立审阅发现的旧binding丢弃准备、再次全库加歌问题已用bound=True参数RED→GREEN修正。已有后续Queue执行计划的rollback/key重试复用原固定后缀；新连接只允许结果已知的明确接管，sent或未完成UNKNOWN不重发clear/add。历史业务、Queue、terminal与通知仍由原外层事务联合提交；不新增持久绑定或重启自动接管合同。

受影响golden/URI证明的MPD数字ID少一次临时add，按真实生成器更新（golden仅四处entry_id减1）。Stock fake补充真实协议clear实现及相应本地能力声明，不能当作目标新实测。没有减弱未知漂移、同URI不同occurrence、失败回滚或重试断言。

第二次fresh验证：针对性138项（丢失响应追加前）、Stock/URI25项、context请求重试与丢失clear/add响应再连接3项、完整后端1667项（新增丢失响应2项收集前）全部通过；完整Web318、typecheck/build、全后端Ruff/diff通过。两轮独立审阅发现已修正，最终无Critical/Important。CI将运行最终包含全部新增测试的suite。没有删DB/重启容器/再次修改consume；新代码尚未部署到NAS，不将自动回归或上一轮consume调整误记为当前实机问题已关闭。
