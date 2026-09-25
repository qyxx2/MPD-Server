# MPD-Server

Music Server 骨架：\`Web/PWA → FastAPI → Services → MPD Adapter → MPD\`。

当前主线以工程骨架为优先，服务端提供 \`/api/health\` 健康端点，Web 使用 Vue 3 + Vite，开发和生产环境通过独立 Docker Compose 配置管理。

## 本地检查

\`\`\`text
make test
make lint
make typecheck
make build
\`\`\`

前端目录：\`web/\`

\`\`\`text
npm install
npm run dev
npm run build
npm run typecheck
\`\`\`

## Docker

开发环境：

\`\`\`text
docker compose -f deploy/docker-compose.dev.yml up
\`\`\`

生产环境首先复制 \`deploy/.env.example\` 为 \`deploy/.env\` 并填写现有 MPD、音乐目录和持久化目录，再执行：

\`\`\`text
docker compose --env-file deploy/.env -f deploy/docker-compose.yml config
docker compose --env-file deploy/.env -f deploy/docker-compose.yml build
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
\`\`\`

开发环境默认保留 \`MPD_MODE=mock\` 配置；真实 MPD 连接在后续 MPD Adapter Task 中实现。

生产环境只读挂载音乐目录，SQLite、配置和备份目录位于容器外。

## 目录

\`\`\`text
server/   FastAPI 服务端
web/      Vue 3 / Vite 前端
deploy/   Docker Compose、Dockerfile 和生产环境配置示例
docs/     规格与实施计划
\`\`\`
