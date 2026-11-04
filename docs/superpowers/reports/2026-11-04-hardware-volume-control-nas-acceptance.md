# MPD 硬件音量控制 NAS 真机验收报告

- 日期：2026-11-04
- 仓库分支：`feature/hardware-volume-control`
- 部署代码：`7194191b27ad117b593d1cd302cf78bb11792457`
- NAS：Synology DS920；MPD 0.23.5
- 验收范围：仅服务端硬件音量 B4，不包含 Web / Android 客户端

## 验收结论

服务端已部署到真实 NAS，硬件音量开关开启。真实 MPD 状态查询、API 写入与读回、恢复原音量、播放状态保护、WebSocket 净变化通知、输出禁用后的 stale 状态和重新启用后的恢复均通过。

本批验收不作“完整硬件验收通过”的结论，仍有三项未完成：本次 API 写入前后没有取得新的 ALSA PCM 左右声道原始值；没有执行第三方 ALSA mixer 直接写入测试；没有主动断开 MPD 连接。前两项分别对应原始硬件读回和外部 Mixer 变化可观察性，不能以 MPD 的逻辑百分比代替。

## CI 构建与 NAS 部署

GitHub Actions run #56（run ID `41785096694`）：
- `validate`：成功。包括完整后端测试与 Ruff、Web 测试、类型检查和生产构建。
- `image`：成功。发布 amd64 / arm64 镜像。
- 固定镜像：`ghcr.io/qyxx2/mpd-server:sha-7194191b27ad117b593d1cd302cf78bb11792457`
- 多架构 manifest digest：`sha256:d8ec86384ca831e1843e8b46e89d99e0db29403bffb5be67a3f5282ad3733464`

NAS 本地 Compose 已将镜像更新至上述 SHA，并设置 `MPD_HARDWARE_VOLUME_ENABLED=true`。更新前备份为 `/volume1/docker/mpd-server/docker-compose.yml.b4-backup-20261104`。原有 `18000:8000` 端口映射保持不变，没有添加 `/dev/snd` 或其他宿主机设备映射，也没有创建或提交 NAS 本地 `.env`。容器检查到的镜像 revision 与部署 SHA 完全一致，容器运行状态为 running。

部署后 `GET /api/health` 返回 HTTP 200，服务状态为 `ok`，MPD 状态为 `connected`。

## 硬件 Mixer 前置条件与基线

复用 B0 已核实的 NAS 本机 MPD 配置：USB DAC 使用 ALSA 输出，`mixer_type "hardware"`，Mixer 设备为 `hw:0`，控件为 `PCM`。本次从 MPD 服务再次读取的输出为：

| MPD output ID | 名称 | 插件 | enabled |
|---:|---|---|---|
| 0 | USB DAC | alsa | 1 |
| 1 | HTTP Stream (port 6680) | httpd | 0 |

这满足本功能的唯一启用 ALSA 输出选择条件。MPD `config` 命令仍限制为本地客户端，因此本次服务端没有通过 MPD TCP 协议推断 Mixer 配置；采用此前在 NAS 本机核实的配置结果。

部署后首次读取：
- `GET /api/system/hardware-volume`：HTTP 200，`status=AVAILABLE`，`volumePercent=80`，输出 USB DAC / ALSA / enabled，`controlSource=MPD_HARDWARE_MIXER`，`stale=false`。
- MPD `status`：`volume: 80`、`state: pause`、`songid: 1`、`repeat: 0`、`random: 0`。
- `GET /api/state` 含 `hardware_volume` 和 `hardware_volume_observation`，音量为 80 且 freshness 为 fresh。
- WebSocket 首帧是 `protocol_version=1` 的 snapshot，包含音量 80 和 fresh observation。

## API 写入、恢复与播放保护

在 MPD 暂停状态下，执行一次可恢复的真实 NAS API 调整：

| 阶段 | API 请求 | API 状态 / 读回 | MPD status.volume |
|---|---|---|---:|
| 原始基线 | GET | AVAILABLE / 80 | 80 |
| 测试写入 | PUT `{"volumePercent":77}` | HTTP 200；lastRequest=SUCCEEDED；读回 77 | 77 |
| 恢复 | PUT `{"volumePercent":80}` | HTTP 200；lastRequest=SUCCEEDED；读回 80 | 80 |
| 最终复查 | GET | AVAILABLE / 80 / fresh | 80 |

两次 PUT 均使用不同的 `Idempotency-Key`。写入后 MPD status 的逻辑百分比与 API 的确认读回相等；恢复后音量回到原始值 80。输出列表在整个过程中保持 USB DAC enabled、HTTP Stream disabled。

播放保护对照：
- 服务端当前歌曲 ID 写入前后均为 `b3eb02f1-184c-4740-8666-41ab6e9e71c9`；MPD songid 始终为 1。
- Playback state 始终为 `PAUSED`。
- Queue revision 写入前后均为 641。
- MPD `repeat` 和 `random` 均保持 0。
- 最终 MPD volume 为 80，未留下测试音量。

## WebSocket 实测

在保持 WebSocket 连接期间：
- 80 → 77 后收到 `type=invalidate`、`protocol_version=1`、`domains=["hardware_volume"]`，sequence 7。
- 连续观察 3 秒，没有再次收到 `hardware_volume` invalidate。
- 77 → 80 恢复后收到对应 invalidate，sequence 8。
- 恢复后再观察 3 秒，没有重复 invalidate。
- 断开并重新连接，首帧重新提供完整 snapshot，硬件音量为 80，freshness 为 fresh。

## 输出消失与恢复

通过 MPD 服务命令进行可逆输出测试（测试开始时播放已暂停）：

1. 对 MPD output 0 执行 `disableoutput 0`。
2. 查询硬件音量 API，得到 `status=UNAVAILABLE`、`volumePercent=80`（保留 last-known）、`outputEnabled=false`、`stale=true`，错误码 `HARDWARE_VOLUME_UNAVAILABLE`；observation freshness 为 stale。
3. WebSocket 收到 `domains=["hardware_volume"]` invalidate，sequence 9。
4. 在同一流程的 finally 恢复路径执行 `enableoutput 0`。
5. 再查询 API，恢复为 `AVAILABLE`、volume 80、`outputEnabled=true`、fresh，且 WebSocket 收到 sequence 10 的硬件音量 invalidate。
6. MPD outputs 确认 output 0 已重新 enabled；最终健康检查和 MPD volume 80 均正常。

该测试验证了输出禁用/重新启用时硬件音量状态的 stale 与恢复语义。没有主动中断 MPD 服务或断开 MPD 网络连接，因此“MPD disconnect 后恢复”这一子项未实测。

## ALSA 原始值与外部 Mixer 变化限制

本次 NAS 只提供服务端远程测试入口；只读查看到的 `/proc/asound/card0/usbmixer` 描述了 USB DAC 的 `PCM Playback Volume` 控件和双声道控制元数据，但不包含当前左右声道原始值；NAS 未安装 `amixer`。因此本次 API 的 80 → 77 → 80 往返没有取得对应的 ALSA raw pre/post 数值，不能把 MPD `status.volume` 的百分比说成 ALSA 原始值。

可复用的历史 B0 硬件链路证据：此前通过 ALSA control ioctl 读取到原始范围 0–127；历史检查曾记录 126/126，且 MPD `setvol 80` 后曾读到 117/117。此数据来自此前独立的 Mixer 验证，并非本次 B4 API 写入前后的同步读数，所以只作为既有链路证据，不替代本批次缺失的 raw readback。

本次没有通过第三方程序直接写 ALSA Mixer。因而“外部 ALSA 直接变化能否被 MPD status 感知并广播”仍为未知，不能宣称已支持，也不能宣称已实测不支持。要关闭这一验收项，需要在 NAS 允许的硬件控制测试路径上执行可恢复的外部 Mixer 写入，并同时读取 MPD status / API。

## 自动化验证

| 验证 | 结果 |
|---|---|
| `.venv/bin/python -m pytest -q server/tests` | 2073 passed，1 条既有 Starlette/httpx deprecation warning |
| `.venv/bin/python -m pytest -q server/tests/api/test_system_hardware_volume.py` | 23 passed，1 条既有 warning |
| `.venv/bin/python -m pytest -q server/tests/test_deploy_contracts.py` | 5 passed |
| `.venv/bin/ruff check server/app server/tests` | All checks passed |
| `git diff --check` | 通过 |
| GitHub Actions #56 validate + image | 均成功 |

部署合同测试确认功能开关默认关闭，生产 Compose 可显式传入开关，未添加 `/dev/snd` 或 `devices:` 映射。

## 最终状态

- NAS MPD-Server 容器运行于 commit `7194191b27ad117b593d1cd302cf78bb11792457`，硬件音量开关为 true。
- 最终硬件音量为 80，状态 AVAILABLE / fresh。
- MPD USB DAC output 0 已启用；HTTP Stream output 1 保持禁用。
- MPD volume 为 80，播放仍为 PAUSED，当前歌曲及 Queue revision 未改变。
- NAS Compose 变更有本地备份；未修改 Web / Android 客户端。
- B4 已完成部署、API/MPD 往返、WebSocket 变化、输出恢复和自动化验证；由于 ALSA raw pre/post、外部 Mixer 写入及 MPD disconnect 测试未完成，整体硬件验收保留上述明确限制。
