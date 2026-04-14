# Filum Docker Compose

## 准备

```sh
cp .env.example .env
docker compose -f docker-compose.yml up --build -d
```

启动后：

- `backend` 容器会先自动执行 `alembic upgrade head`，再启动 FastAPI。
- 统一入口为 `http://127.0.0.1:8080`
- 如需查看日志：

```sh
docker compose -f docker-compose.yml logs -f backend frontend nginx
```

## 本地直启（不走 Docker）

后端本地 `.env` 可直接从 `backend/.env.example` 复制，默认指向本机的 PostgreSQL 与 Redis：

```sh
cd backend
cp .env.example .env
. .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端：

```sh
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

## 服务说明

- `postgres`: PostgreSQL 主数据库
- `redis`: Redis broker / cache
- `backend`: FastAPI 开发服务
- `frontend`: Vite 开发服务
- `nginx`: 统一入口，转发 `/api/` 到 backend，其余流量到 frontend

## 当前限制

如果本机尚未安装 Docker，可先执行配置级验证：

```sh
cd ../../frontend
npx prettier --check ../infra/docker/docker-compose.yml
```
