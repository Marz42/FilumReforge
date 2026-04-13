# Filum Docker Compose

## 准备

```sh
cp .env.example .env
docker compose -f docker-compose.yml up --build
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
