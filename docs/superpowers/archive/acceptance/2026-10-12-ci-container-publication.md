# GitHub 镜像 CI 与授权提交 — 2026-10-12

用户在B07后明确授权“提交push，进行CI构建流程”。本轮新增GitHub Actions，
将当前Task9与B00–B07源码及文档一起提交到feature/task-9-web，不合并main。
这次授权覆盖提交、push及GHCR构建发布；不代表B08/B09或NAS实机Gate通过。

## 实施

- `.github/workflows/container.yml`：push main/feature/**/codex/**、v* tags及手动触发；PR仅验证。后端/Web完整回归、Ruff、typecheck、生产build通过后，构建并发布linux/amd64和linux/arm64到GHCR。Actions固定已核对的官方仓库commit，权限仅contents read与发布job packages write。
- 使用`sha-<完整commit>`镜像标签与OCI source/revision标签，发布后imagetools验证manifest并在summary记录digest。无latest、无NAS凭据、无部署或重启副作用；使用GitHub自动token。
- 自动数据在runner自有临时目录，生产real启动只接测试替身，外层MPD地址loopback:9；不依赖live MPD/真实音乐。依赖仅在CI临时runner按现有requirements/lockfile安装，不修改本机.venv或版本声明。
- 部署卡新增GHCR拉取步骤与private包鉴权说明；NAS采用pull和up --no-build仍须真实挂载/网络/重启验收。

## 提交前必要修复与fresh证据

完整回归初跑发现后端6 failed/1537 passed，Web2 failed/297 passed。不是B07通过项的替代或倒改历史记录。

- 3个output取消节点先精确RED，根因为新增日志BaseHTTPMiddleware多包一层将Cancel转换成No response returned；改为同任务的纯ASGI诊断middleware，保留事务取消、原key/replay/外部设备事实断言。3节点GREEN。
- seek测试旧文案按Visual §6修改为读取失败的状态未同步/read-only恢复；由此继续暴露新权威观察后旧readFailed未清除的有效RED。只在同target、fresh观察时间确认收敛时清标记，GREEN；新增无第二POST断言。
- Queue成功活动按B04新合同保留成功历史，保留请求体/权威读取/Queue不替代断言。扫描历史测试改为B03已定义202短接纳并实际等待临时SQLite+SyncService确认，保留invalid year及音乐字节不变断言。
- endpoint proof测试明确其fixture端口6600，避免外层隔离port9覆盖；不改变能力授予规则。
- workflow结构测试因缺文件先RED，后GREEN；actionlint发现job级runner.temp不可用，改step设置GITHUB_ENV后GREEN。结构测试不伪称执行Actions。

验证使用原`.venv/bin/python`，APP_ENV=production/MPD_MODE=real、临时CONFIG_DIR/MUSIC_ROOT/DATABASE_PATH，unset MPD_CONNECTION_PATH/秘密/能力环境覆盖，各fixture为自有数据；MPD_HOST=127.0.0.1/MPD_PORT=9。日志保留在本轮自有`/tmp/mpd-ci-88r9t4tl`，不提交日志。

- 精确复现→文件回归：后端6相关文件91 passed；Web seek/queue-save/appbar/player-notices 36 passed。
- `.venv/bin/python -m pytest -q server/tests` → **1544 passed**（原Starlette/httpx弃用warning）。
- `npm --prefix web run test -- --run --maxWorkers=1 --minWorkers=1` → **299 passed / 29 files**。
- `.venv/bin/python -m ruff check server/app server/tests`、Web typecheck、生产build（自有临时outDir保护旧web/dist）、actionlint及git diff --check → **passed**。

完整本地回归是本次授权提交的验证，不宣布B09完成。NAS Docker/真实MPD/手机声音、真实持久化重启仍NOT RUN；CI远程结果在完成后单独报告，不预记通过。

## 首轮远程运行与工具基线修正

[c442028 首轮Actions](https://github.com/qyxx2/MPD-Server/actions/runs/38191189875)
后端 **1544 passed**；之后Ruff **73 failed**，镜像job按门禁SKIPPED。
完整日志确认CI选择范围内新Ruff0.17.0，本地已验证0.16.9；没有repository
Ruff配置。未进行全库自动fix或ignore规则，也不把镜像跳过记为构建通过。
CI在runner临时constraints文件固定`ruff==0.16.9`，仍按原requirements安装，
只固定CI检查工具，不修改项目依赖声明、Docker运行依赖或本机.venv。
workflow结构精确节点RED→GREEN，文件4 passed；本地广域Ruff/actionlint/diff检查
通过。后续远程运行结果待实际确认。
