# Filum Docker Compose

`infra/docker/` 提供当前项目推荐的本地集成运行方式，包含数据库、Redis、后端、worker、前端与 Nginx 统一入口。

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
```

停止环境：

```sh
docker compose -f docker-compose.yml down
```

## 本地直启（不走 Docker）

如果不走 Docker，请改用仓库根目录 `README.md` 中的 backend / worker / frontend 启动方式。
