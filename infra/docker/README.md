# Filum Docker Compose

`infra/docker/` 提供当前项目推荐的本地集成运行方式，包含数据库、Redis、后端、worker、前端与 Nginx 统一入口。

当前这套 Compose 的定位是**开发 / 集成联调环境**，不是直接公网生产编排：

- `backend` 使用 [../../backend/scripts/start-dev.sh](../../backend/scripts/start-dev.sh)，其中 `uvicorn` 带 `--reload`
- `frontend` 容器运行的是 Vite dev server，而不是生产静态文件服务
- `backend` 与 `frontend` 都通过 bind mount 挂载源码目录，便于本地开发，不适合直接公网部署

## 准备

```sh
cp .env.example .env
docker compose -f docker-compose.yml up --build -d
```

启动后：

- `backend` 与 `worker` 容器都会先执行 `alembic upgrade head`
- 统一 Web 入口为 `http://127.0.0.1:8080`
- Backend API 默认为 `http://127.0.0.1:8000`
- Frontend Dev 默认为 `http://127.0.0.1:5173`

查看日志：

```sh
docker compose -f docker-compose.yml logs -f backend worker frontend nginx
```

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
docker compose -f docker-compose.yml exec backend python -m app.scripts.seed_sample_data --password 'F123456'
```

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

根目录 [README.md](README.md) 已补充实际云服务器部署指南，可直接按其中的 Ubuntu + Nginx + systemd 路径执行。
