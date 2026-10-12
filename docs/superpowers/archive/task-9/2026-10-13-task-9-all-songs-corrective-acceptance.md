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
