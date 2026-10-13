# Task 9 单曲播放与同步活动图标整改

日期：2026-10-13。基线：7f5ce25，分支 feature/task-9-web。

## 根因与修复

单曲点击统一调用 Song Play Now。原执行计划先删除旧 current，再 play 新 occurrence。真实 MPD 在播放中删除 current 时会立即播放后继项，而 ExecutionSynchronizer 的删除结果预期 STOPPED，因而报 UNKNOWN current changed during execution，业务事务回滚并失绑，Web 只能展示实际 URI、禁用控制。MPD 上游行为可核对 [PlaylistEdit.cxx / DeleteInternal](https://github.com/MusicPlayerDaemon/MPD/blob/master/src/queue/PlaylistEdit.cxx)。

修复仅调整 Queue 执行计划：准备好新项及所需顺序后先明确 play（需要时 pause），再删除 obsolete 项。保留 pending occurrence 身份和顺序、逐命令 receipts、固定意图、失去响应不重发、完整最终映射及绑定核验。集合替换的 clear/add-all/play 路径不改。

AppBar 原先在任何未解决告警存在时用告警图标覆盖 busy 转圈。现在 busy 时总是转圈，同时保留 warning 颜色与活动详情，完成同步后仍可查看未解决告警。

## 复现与验证

- 本地真实 PlaybackService → MPDAdapter → TCP 模拟器重现 stock MPD 删除 current 的立即后继播放。旧实现已有集合时稳定失败，最小修复后通过。
- 永久播放回归 16 项：空队列、1/2/8 首原始集合、播放/暂停、同首/不同首、绝对 /music URI 映射。核对最终完整队列、保留 pending 身份顺序、current position=0、CONFIRMED 与非空 control_target；一致队列无需 clear。
- Spinner 回归在旧组件失败、修复后通过，核对同步期间存在旧告警也转圈、结束后保留告警；原实时曲库同步回归保留。
- 受影响后端回归 160 项通过（扩大新矩阵前），扩大后的新增矩阵 16 项通过。
- 完整 Web：31 文件、319 项通过；typecheck、生产 build、全 server/app 与 server/tests Ruff、diff check 通过。
- 独立只读审阅：无 Critical/Important；原有 after-play 回滚重试测试覆盖已确认播放后继续固定后缀，不重发 play。

## 交付边界

本轮未修改依赖、虚拟环境、数据库、MPD 模式或部署配置。上述播放验证使用本地协议模拟器；只读实机状态显示旧容器 UNBOUND、control_target=null，与症状吻合。新版镜像部署后的 NAS 页面点击及真实音频输出仍需用户复测，不能用本地模拟器声称新版容器已完成实机验收。

完整后端与远端 CI 结果在实际执行完成后补充。镜像以本次提交对应 CI 的发布日志中 manifest digest 为准。

最终本地完整后端：1714 项通过（148.52 秒）；仅既有 Starlette TestClient/httpx 弃用警告，未修改依赖。所有生产变更仅上述执行次序与 spinner 条件两处。提交后 push 自动触发既有 container.yml 的 validate 与双架构 image 作业；远端结果由交付消息给出。
