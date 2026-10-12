# 真实 MPD 三首缓冲可行性实验（临时 Spike）

日期：2026-10-12（Asia/Shanghai）；目标：192.168.3.94:6600，实际 greeting MPD 0.23.5。

结论：**三首缓冲、独立 idle 监听、1 秒轮询兜底和前后实际采样，在本次设备/LAN 的 5 轮控制实验中可行。** 单命令 ACK 通常约 4–6ms，含真实确认约 19–24ms；预备项组合调整约 69–71ms。这足以作为 B1 开始开发的可行性证据，但不是 B1/B6 实施或 Web/DAC 联合验收。

## 范围与环境

- 按用户指令单独 clone `qyxx2/MPD-Server` 的 `refactor/mpd-bounded-execution`；HEAD `92b44c913e49052d2fd113b77eda0b13c429c0fc`。原 checkout 有未提交工作，未切换/覆盖。
- 阅读冻结 Playback Spec §8.10、2026-10-12 Refactor Plan；按 Superpowers 的 Spike、调试、完成前验证流程进行。无正式实现、B1、提交、PR、合并、部署。
- 使用 `/home/Gold/WorkSpace/MPD-Server/MPD-Server/.venv/bin/python`：Python 3.14.4 / pytest 9.1.1 / Ruff 0.16.9。读取 `server/requirements.txt`，未改环境或依赖。
- 真正复用目标分支的 `MPDAdapter._command`、TCP timeout/epoch/lock 和 `mpd_protocol.parse_response/quote_argument`；读取 public `status/read_execution_sample` 作对照。临时调用私有接口只是探针手段，正式 Port 不应继续依赖它。
- 本地已有服务经脚本核对使用 MockMPD；本实验未接入该 Mock。NAS `8000/api/health` refused。MPD 未提供 clients 命令，因此无法证明远端不存在任意其他控制器；实验期间未观察到外部 ID/队列/模式漂移。每次写前后做真实 fence；不是服务独占性证明。

## 安全与运行顺序

1. 初次只读发现 default 正播放、1098 项、position 998、consume=1；先保存完整 ID/URI/顺序/模式/状态，执行 50 轮基准和 300 秒观察，**零写命令**。
2. 用户随后明确授权「清空队列再测试」。授权后保存最新完整快照并 clear；原始备份位于 `controlled-run/original.json`（1097 项）。后续重试也保存当时快照；failed-owned resume 使用范围明确的 deleteid，不再 clear。
3. 四次控制运行：首次末尾 seek 竞态失败；第二次 2 轮完整通过、第三轮 seek 固定窗口失败；第三次补充诊断复现；最终 5 轮完整通过。共 3 次明确授权 clear，保留所有失败日志。第二、第三及最终运行都确认恢复；首次 fail closed 留下本实验三项，第二次按已保存的 owned IDs 接续。
4. 最终运行按其即时备份恢复 **1096 项** URI 顺序、原模式 random/repeat/single=0、consume=1，原 current URI/state/position 和 elapsed（135.357→136.210s，确认容差 1s）。所有实验条目已删除；原 ID 不可恢复，生成了新 ID。
5. 之后独立只读复查：正常继续播放，consume=1 自然进位后队列为 **1095 项**，current position 998，ID 4491，elapsed 67.738s。减少的一项发生在恢复后的正常播放；不是探针清理漏项。
6. **清空后的 MPD ID 已全部改变，旧 MS 执行绑定不可继续当作可信绑定。** 未改 MS SQLite、正式代码、音乐文件、音量/输出设置、MPD 配置、Docker、虚拟环境。文件/目录内容均仅写入实验 artifacts 目录。

## 已执行的行为检查

最终实验使用原曲库的五首：Melody / 味道 / 我都明白 / 回到过去 / EGOIST Departures。没有新建曲库、写音乐或调用服务器数据库。

| 检查 | 结果和证据 |
|---|---|
| 四模式 | set random/repeat/single/consume=0 后 status 实际确认；完成后恢复原值 |
| A/B/C 与 addid→playid | 5/5，真实 ID、URI、PLAYING 匹配；稳态3/瞬态≤4 |
| A→B 自然进位 | 5/5，末尾余段结束；无 next/playid B 命令，真实 Current position=1 |
| 清理 A + 补 D | 5/5，B ID 保持、elapsed 不倒退，位置从1变0；新 Current/Next/Next Next 来自真实读取 |
| 暂停/恢复 | 5/5，暂停约1.2秒 elapsed 差为0；播放检查约1.2秒进度增加1.252–1.366秒；恢复不重播/换 ID |
| seek | 同 ID/URI/state，播放态按推进＋1s容差确认，暂停态0.6s容差；不是精确到毫秒的 seek 证明 |
| 插入下一首、替换、删除、moveid | 每类5/5，actual playlist 顺序确认，删除预备项不换 Current |
| 同 URI 不同 ID | 5/5，缓冲同时存在同 URI 的两个独立 ID；playid 后确认实际选中第二 ID，而非第一个 URI |
| 大队列重复 URI | 初始只读发现 314 组同 URI 多 ID；完整样本保留其真实身份 |
| 独立 idle＋poll | 最终 idle TCP 与查询 TCP 分离；订阅 player/playlist/options，事件仅触发实际三次采样；每轮完成后1秒 poll |
| 一致性 | status→playlistinfo范围→status；比较 epoch、partition、版本、长度、ID、位置、state、四模式；允许 elapsed 推进，最多2次读取重试 |

例如第一轮 B={ID 3458, position 1}；清理/补充后真实读取为：

```json
{
  "status": {
    "volume": "100",
    "repeat": "0",
    "random": "0",
    "single": "0",
    "consume": "0",
    "partition": "default",
    "playlist": "3536",
    "playlistlength": "3",
    "mixrampdb": "0",
    "state": "play",
    "song": "0",
    "songid": "3458",
    "time": "1:237",
    "elapsed": "0.956",
    "bitrate": "539",
    "duration": "237.333",
    "audio": "44100:16:2",
    "nextsong": "1",
    "nextsongid": "3459"
  },
  "entries": [
    {
      "file": "味道 - 辛晓琪.flac",
      "Last-Modified": "2024-11-10T15:03:35Z",
      "Format": "44100:16:2",
      "Album": "味道",
      "Artist": "辛晓琪",
      "Date": "1994",
      "Title": "味道",
      "Time": "237",
      "duration": "237.333",
      "Pos": "0",
      "Id": "3458"
    },
    {
      "file": "我都明白 - 范倪Liu.flac",
      "Last-Modified": "2024-11-10T15:03:33Z",
      "Format": "48000:24:2",
      "Album": "我都明白",
      "Artist": "范倪Liu",
      "Date": "2023",
      "Title": "我都明白",
      "Time": "250",
      "duration": "249.600",
      "Pos": "1",
      "Id": "3459"
    },
    {
      "file": "回到过去 - 周杰伦.flac",
      "Last-Modified": "2024-11-10T15:05:45Z",
      "Format": "192000:24:2",
      "Album": "八度空间",
      "Artist": "周杰伦",
      "Date": "2002",
      "Title": "回到过去",
      "Track": "8",
      "Time": "233",
      "duration": "233.466",
      "Pos": "2",
      "Id": "3460"
    }
  ],
  "current": {
    "file": "味道 - 辛晓琪.flac",
    "Last-Modified": "2024-11-10T15:03:35Z",
    "Format": "44100:16:2",
    "Album": "味道",
    "Artist": "辛晓琪",
    "Date": "1994",
    "Title": "味道",
    "Time": "237",
    "duration": "237.333",
    "Pos": "0",
    "Id": "3458"
  },
  "next": [
    {
      "file": "我都明白 - 范倪Liu.flac",
      "Last-Modified": "2024-11-10T15:03:33Z",
      "Format": "48000:24:2",
      "Album": "我都明白",
      "Artist": "范倪Liu",
      "Date": "2023",
      "Title": "我都明白",
      "Time": "250",
      "duration": "249.600",
      "Pos": "1",
      "Id": "3459"
    },
    {
      "file": "回到过去 - 周杰伦.flac",
      "Last-Modified": "2024-11-10T15:05:45Z",
      "Format": "192000:24:2",
      "Album": "八度空间",
      "Artist": "周杰伦",
      "Date": "2002",
      "Title": "回到过去",
      "Track": "8",
      "Time": "233",
      "duration": "233.466",
      "Pos": "2",
      "Id": "3460"
    }
  ]
}
```

## 耗时统计（全部毫秒）

| 操作 | n | 平均 | P95 | 最大 | ACK平均 |
|---|---:|---:|---:|---:|---:|
| status 单命令基准 | 50 | 3.58 | 5.78 | 6.53 | — |
| playlistinfo 0:4 | 50 | 3.41 | 6.43 | 7.70 | — |
| 大队列 Current 窗口三次一致读取 | 50 | 12.71 | 19.98 | 25.71 | — |
| 完整 1098 项 playlistinfo | 51 | 69.67 | 96.19 | 142.87 | — |
| 现有 Adapter.status（含 currentsong） | 50 | 8.19 | 11.99 | 35.64 | — |
| 现有 Adapter 全量一致采样 | 50 | 80.42 | 89.74 | 98.99 | — |
| 每秒 status 观察 | 297 | 9.85 | 12.57 | 855.16 | — |
| 只读所有 status（含精细参考连接） | 854 | 8.64 | 12.29 | 1157.33 | — |
| 三/四项缓冲三次一致读取 | 286 | 15.92 | 22.65 | 33.58 | — |
| addid → 实际 ID/URI 确认 | 35 | 19.29 | 25.81 | 33.40 | 4.22 |
| playid → 实际 ID/URI/PLAYING 确认 | 10 | 21.90 | 39.08 | 39.08 | 4.70 |
| pause → PAUSED 确认 | 10 | 21.90 | 27.99 | 27.99 | 4.38 |
| resume → PLAYING 确认 | 10 | 21.13 | 25.81 | 25.81 | 4.38 |
| seekid → 进度确认 | 10 | 24.04 | 34.89 | 34.89 | 4.91 |
| deleteid → 条目消失及 Current 确认 | 35 | 18.81 | 23.13 | 23.76 | 3.98 |
| 插入下一首＋删除原预备项（完整操作） | 5 | 70.95 | 79.60 | 79.60 | — |
| 替换下下一首（完整操作） | 5 | 69.40 | 76.70 | 76.70 | — |
| 移动预备项（含前后采样） | 5 | 38.70 | 44.39 | 44.39 | 6.26 |
| 自然 A→B：idle 确认延迟上界 | 5 | 40.80 | 44.32 | 44.32 | — |
| 自然 A→B：1s poll 确认延迟上界 | 5 | 1045.14 | 1049.07 | 1049.07 | — |

- 基准全量读取 n=51（50轮＋备份读取），其余 n=50；全量读取平均约局部读取 **20.5倍**。这证明本 LAN 下读取规模有明显影响，不证明既有生产 UI 阻塞的唯一根因。
- ACK 是发命令至完整 OK/ACK 响应；确认总耗时是发命令至新鲜一致采样通过，**不含独立前置 fence**。前置通常再增加约16ms。表中组合插入/替换/移动是完整操作、包含其前置/后置读取。pause ACK平均合并暂停及恢复。
- 5轮/10次样本的 nearest-rank P95 常等于最大值，尾部估计不稳定；只用于描述本次运行。逐项原始样本均保存 JSON，未将失败运行混入最终成功运行的操作统计。
- 全量基准/控制使用正常真实 TCP，没有 mock、网络代理或人工延迟。细粒度参考连接只为测切歌时间区间，不建议正式实现20ms轮询。

### 自然切换的观察延迟区间

对实际切换时间用独立 reference status 的前后请求/响应作区间包络，保留网络不确定性；无法取得 MPD 内部精确切换时刻。上表统计的是**区间上界**，不是伪造精确测量。

| 轮次 | idle确认延迟区间ms | 1s poll确认延迟区间ms | 切换时间包络宽度ms |
|---|---:|---:|---:|
| 1 | 12.11–42.73 | 1010.30–1040.91 | 30.61 |
| 2 | 0.00–31.30 | 1011.32–1043.70 | 32.38 |
| 3 | 12.83–44.32 | 1017.09–1048.58 | 31.49 |
| 4 | 4.37–41.43 | 1012.01–1049.07 | 37.06 |
| 5 | 14.70–44.21 | 1013.93–1043.43 | 29.51 |

自然结束测试在暂停态 seek 到结束前3秒，再恢复让 MPD 自主完成剩余片段。**未测试五首完整从头播至尾、无缝音频、DAC听感或 History NATURAL_COMPLETION 因果认证。** §8.9/§8.10 禁止根据这个实验给业务 History 认证自然原因。

## 实际发现的限制、瓶颈与竞态

1. **seek ACK不等于进度精确确认**：诊断运行请求10秒，连续 status 返回10.455→10.842，随后递增到13.847；identity/state/playlist稳定。固定±0.6秒的探针窗口造成超时，真实请求未重启歌曲。最终明确以播放态推进＋1秒容差确认，暂停 seek 的实际读数为266.000。可能涉及MPD进度更新/输出缓冲，**没有确认其内部原因**；正式容差应由目标输出配置和更多样本决定，不直接把1秒写成新产品合同。
2. **读取之间会自然切歌**：首轮等待A末尾 seek确认时，真实 Current已成为B(position1)，探针当时误分类为竞争，停止写入。最终先暂停并确认 seek，再启动独立观察，证明预定 B 可被接纳，而不是再次 playid B。正式执行器遇到相同竞态须按精确代次重采样/重规划，不能跳过前后校验。
3. **观察存在长尾**：初始大队列自然切歌附近，单个真实 status 请求最大 **1157.33ms**；每秒poll最大855.16ms，参考切换包络约1184.69ms。最终小缓冲没有复现此量级。不能据此断言队列长度或MPD/DAC是唯一原因，保持连接/命令超时和 stale 门禁。
4. **idle不是普通快请求**：只读探针将 idle 安静等待预算设为15秒，周期性超时后关闭重连是探针行为，不能解释为 MPD 15秒断线。正式 idle owner 应有独立、可取消的长等待策略/重连退避，查询和1秒poll继续工作。控制实验的专用 idle 在12秒自然观察预算内运行。
5. **foreign大队列不能被0:4代表**：initial Current position998，需要读取当前位置窗口才能显示其真实URI/后继；受控≤4时才读0:4并认领执行缓冲。不能用局部头四项证明整个大队列一致或触发清空。
6. **模式/ID不可忽略**：consume=1会删完曲项；目标consume=0才能先看到B位置1再清理A。原生next不是MS业务next。clear无法恢复旧临时ID，即便URI和顺序完全恢复也必须使旧绑定失效。
7. 这次未观察到控制竞争，但没有远程进程清单/唯一owner保证；未注入外部删改、响应丢失、MPD重启、网络断线或SQLite提交失败。无跨SQLite/MPD原子性证明。
8. player自然变化与playlist consume通知已观察；订阅options命令被目标接受，**未单独触发并验收外部options事件**。无Web→MS→WS联合验证、400项Web元数据压力或3/6秒客户端提示验收。

## 对B1的具体建议（仅建议，未实施）

- Port增加明确的ID控制与bounded读取入口，保留URI mapper；不要复用现有 `play(uri)` 的首个同URI查找，也不要复用全量 `queue_move/read_execution_sample` 作常规短缓冲路径。
- 唯一 ActualStateOwner 持有新鲜样本/epoch/generation/observed_at/current/两个物理后继；写owner串行、控制前后各做真实短采样，业务队列与MPD实际状态分离。无业务层接入/API变更，保持B1边界。
- 受控时 `status→playlistinfo 0:4→status` 已获实测支持，steady3/transient4；unknown/foreign旧大队列只显示实际Current，不自动清空或认领。查询全量保留为显式迁移/诊断路径。
- 用 exact MPD ID＋URI＋模式/版本/连接代次 fence；B位置1是正常可接纳状态。自然进位只确认B，再删A补D；暂停时调整也必须保持pause，零重复playid B。
- 专用 idle连接与查询连接分离，idle仅发变更信号；单实际缓存＋约1秒status兜底，迟到样本不能覆盖新控制确认。budget/timeout/freshness与Web3秒延迟6秒stale分开设计，不为每秒采样拉全量业务Queue。
- B1 RED proof优先覆盖本次真实发现：seek readback步进和identity不变、A→B发生在确认中、position1、同URI异ID、四模式漂移、unknown ACK、epoch改变；再覆盖foreign400、单writeowner、取消/idle重连，按Plan做FakePort/真实Adapter联合证明。实验结果不是自动化关系测试的替代。
- 性能起点可按一次短一致采样约16ms、发命令到确认约20–24ms、复杂预备变更约70ms估算；这支持连续预备和状态同步的设计。但短曲、多用户/外部控制及网络长尾须另外验收，不能承诺绝对gapless。

## 复跑与交付索引

只读脚本（默认不会控制MPD）：

```bash
/home/Gold/WorkSpace/MPD-Server/MPD-Server/.venv/bin/python /home/Gold/WorkSpace/MPD-Server/mpd-bounded-experiment-artifacts/probe.py --samples 50 --observe-seconds 300 --out /tmp/mpd-readonly-new-run
```

控制脚本（**显式参数允许清空当时队列**；先备份，最终尽可能恢复）：

```bash
/home/Gold/WorkSpace/MPD-Server/MPD-Server/.venv/bin/python /home/Gold/WorkSpace/MPD-Server/mpd-bounded-experiment-artifacts/control_probe.py --authorize-clear-existing --trials 5 --out /tmp/mpd-controlled-new-run
```

请为每次运行选择新输出目录，以保留旧备份和日志。命令连接3秒/普通命令5秒/idle10或15秒、seek确认3秒/自然观察12秒，所有循环有样本数或时间边界。遇到外部队列/模式漂移停止有副作用实验，保留原始备份；不自动覆盖未知foreign状态。

- `probe.py` / `control_probe.py`：可复跑临时脚本，正式项目无 diff。
- `environment.json`：分支/commit/venv版本证据。
- `run/original.json`, `run/final.json`, `run/events.jsonl`, `run/results.json`, `run-console.log`：初始只读实测。
- `controlled-run*`：每次真实实验的原状态、逐命令与实际status、结果和统计；`controlled-run-final/results.json` 是最终5轮结果，前面的失败不删除。
- `control-final-console.log`：关键可读日志；`post-check.json`：恢复后的新鲜独立复查；`derived-statistics.json`：跨只读status统计。
- 本地回归：目标clone的 `test_mpd_protocol.py`, `test_mpd_adapter_tcp.py`, `test_execution_sample.py` 共14通过（这组本地协议测试不替代live结果）；两脚本Ruff通过。
