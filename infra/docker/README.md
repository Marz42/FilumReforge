# Filum Docker Compose

`infra/docker/` 提供当前项目推荐的本地集成运行方式，包含数据库、Redis、后端、worker、前端与 Nginx 统一入口。

当前这套 Compose 的定位是**开发 / 集成联调环境**，不是直接公网生产编排：

- `backend` 使用 [../../backend/scripts/start-dev.sh](../../backend/scripts/start-dev.sh)，其中 `uvicorn` 带 `--reload`
- `frontend` 容器运行的是 Vite dev server，而不是生产静态文件服务
- `backend` 与 `frontend` 都通过 bind mount 挂载源码目录，便于本地开发，不适合直接公网部署

## 准备

```sh
cd infra/docker
cp .env.example .env
# Edit .env and set JWT_SECRET_KEY before starting.
docker compose -f docker-compose.yml up --build -d
```

Compose 已为 `backend` / `worker` 注入与当前代码基线一致的环境变量（可在 `.env` 覆盖）：

- `FRONTEND_APP_URL`：默认 `http://127.0.0.1:8080`，与 **Nginx 统一入口**一致，便于邀请注册、外链回跳演练；若只使用 Vite `:5173` 直连，请在 `.env` 中改为 `http://127.0.0.1:5173`。
- `WORKFLOW_GRAPH_ENGINE_ENABLED` / `TASK_CENTER_V2_ENABLED`：默认 `true`，与 `backend/app/core/config.py` 及生产 Compose 对齐。
- `WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED`：默认 `false`；**图模板 Tab 实例化**须在 `.env` 设为 `true` 并重启 `backend`（`worker` 可选同步）。
- `WORKFLOW_WAIT_ANY_ENABLED` / `WORKFLOW_DEEP_REJECTION_ENABLED`：默认 `false`，与 Settings 默认一致；需要演练或签 / 深度打回时可改为 `true`。

启动后：

- `backend` 与 `worker` 容器都会先执行 `alembic upgrade head`
- 统一 Web 入口为 `http://127.0.0.1:8080`
- Backend API 默认为 `http://127.0.0.1:8000`
- Frontend Dev 默认为 `http://127.0.0.1:5173`

查看日志：

```sh
docker compose -f docker-compose.yml logs -f backend worker frontend nginx
```

## 端到端（GUI）验证

基于本 Compose 栈的 **分层账号、拟真浏览器操作** 清单见 [E2E-GUI-VERIFICATION.md](./E2E-GUI-VERIFICATION.md)（含环境前置、L0–L4 权限矩阵、任务/汇报/消息闭环与可选知识库 / AI / Push）。

## 生产部署

若要基于 Docker Compose 方式上线，请改用 `docker-compose.prod.yml`：

```sh
cp .env.prod.example .env.prod
# 编辑 .env.prod，填入真实密钥与数据库连接
docker compose -f docker-compose.prod.yml --env-file .env.prod up --build -d
```

生产 Compose 与开发 Compose 的关键区别：

- `backend` / `worker` 使用 `Dockerfile.prod`（仅安装 core 依赖，无 `[dev]` extras）
- `backend` 通过 `start-prod.sh` 启动，禁止 `--reload`
- `frontend` 采用多阶段构建，由 `nginx:alpine` 托管 `dist/` 静态文件
- 无 bind mount，不挂载源码目录
- `redis` 启用 RDB + AOF 持久化
- 数据库 / Redis / ingress 端口均不对外暴露（除 Nginx 的 80 端口）

**推荐在 Compose 前方再挂一层 host-level Nginx 做 HTTPS 终止**。  
模板见 [`infra/nginx/nginx.prod.conf`](../nginx/nginx.prod.conf)，Nginx 内部转发配置见 [`infra/nginx/nginx.compose.prod.conf`](../nginx/nginx.compose.prod.conf)。

---

如果采用 Ubuntu + Nginx + systemd（不用 Compose），请参考根目录 [README.md](../../README.md) 的云服务器部署章节。

## Web Push 配置

浏览器 Push 的标准配置路径如下：

- `backend` 与 `worker` 读取 `.env` 中的 `WEB_PUSH_PUBLIC_KEY`、`WEB_PUSH_PRIVATE_KEY`、`WEB_PUSH_SUBJECT`
- 已登录前端从 `/api/v1/push-subscriptions/config` 动态获取公钥，再在消息中心完成浏览器订阅
- `frontend` 不再要求必须注入 `VITE_WEB_PUSH_PUBLIC_KEY`；该变量仅保留为兼容兜底

如果消息中心提示后端未完成 Web Push 配置，请先检查以上三个环境变量和 `worker` 进程状态。

## 服务说明

- `postgres`: PostgreSQL 主数据库（`pgvector/pgvector:pg16`）
- `redis`: Redis broker / cache
- `backend`: FastAPI 开发服务
- `worker`: ARQ worker，负责通知投递、embedding job、定时扫描等异步任务
- `frontend`: Vite 开发服务
- `nginx`: 统一入口，转发 `/api/` 到 backend，其余流量到 frontend

## 常见后续动作

生成 demo 数据：

```sh
docker compose -f docker-compose.yml exec backend python -m app.scripts.seed_sample_data --password 'FilumTest123!'
docker compose -f docker-compose.yml exec backend python -m app.scripts.seed_workflow_video_templates
```

（与仓库根目录 `README.md` 中 demo 账号说明一致；图模板实测见 `memory-bank/knowledge/manuals/workflow-video-v1-docker-runbook.md`。）

停止环境：

```sh
docker compose -f docker-compose.yml down
```

## 本地直启（不走 Docker）

如果不走 Docker，请改用仓库根目录 `README.md` 中的 backend / worker / frontend 启动方式。

## 云部署说明

如果要部署到云服务器，请不要直接复用当前 Compose 作为公网生产方案。推荐改用：

- Nginx 提供前端静态 `dist/` 与 `/api/` 反向代理
- backend / worker 以 systemd 常驻
- PostgreSQL / Redis 使用云数据库或单独的受控服务

根目录 [README.md](../../README.md) 已补充实际云服务器部署指南，可直接按其中的 Ubuntu + Nginx + systemd 路径执行。
