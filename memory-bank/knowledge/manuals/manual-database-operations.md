---
type: paradigma-manual
title: 数据库操作手册
description: "PostgreSQL 手工操作与迁移。"
tags:
  - manual
  - 数据库
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: cold
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh:
      - 数据库
    en:
      - database
---
# 手动操作数据库指南

**适用范围**：开发 / 联调 / 自有测试环境；PostgreSQL 为 Filum 主库。  
**文档定位**：运维与排障时的**手工 SQL / 卷清理 / 迁移**参考；**生产环境**任何破坏性操作须走变更流程与备份。

**风险声明**

- 直接 `UPDATE` / `DELETE` 可能破坏外键、枚举与 ORM 假设；优先通过 **API 或管理后台** 改业务数据。
- 下列「重置」会删除业务数据；执行前确认 **无需保留** 或已完成 **备份 / 导出**。
- 修改 `users`、`refresh_tokens` 可能导致全员无法登录；删除管理员前须明确恢复路径。

---

## 1. 连接数据库

### 1.1 从连接串还原 psql 参数

应用使用 **asyncpg** DSN，形如：

`postgresql+asyncpg://用户:密码@主机:5432/库名`

`psql` 使用 **libpq** URI（去掉 `+asyncpg`）：

```text
postgresql://filum:filum@localhost:5432/filum
```

本地默认值见 [backend/.env.example](../../../backend/.env.example) 中的 `POSTGRES_DSN`。

### 1.2 本机已安装 psql 时

```bash
psql "postgresql://filum:filum@localhost:5432/filum"
```

若端口或密码与 `.env` / `infra/docker/.env` 不一致，请替换。

### 1.3 使用 Docker Compose 内的 Postgres（推荐与运行栈一致）

在仓库根目录或 `infra/docker` 下（与当前 `docker compose` 工作目录一致）：

```bash
cd infra/docker
docker compose -f docker-compose.yml exec postgres \
  psql -U "${POSTGRES_USER:-filum}" -d "${POSTGRES_DB:-filum}"
```

Windows PowerShell 可先 `cd infra/docker`，再：

```powershell
docker compose -f docker-compose.yml exec postgres psql -U filum -d filum
```

### 1.4 通过 backend 容器执行（已配置相同网络与常见环境）

```bash
cd infra/docker
docker compose -f docker-compose.yml exec backend \
  sh -c 'python -c "import os; print(os.environ.get(\"POSTGRES_DSN\",\"\"))"'
```

仅用于确认环境变量；**连 psql** 仍以 `postgres` 服务容器为宜。

---

## 2. 只读查询（查）

### 2.1 常用元数据

```sql
-- 当前库与角色
SELECT current_database(), current_user;

-- 迁移版本（与 alembic_version 表一致）
SELECT * FROM alembic_version;

-- 表数量概览
SELECT schemaname, COUNT(*) AS tables
FROM pg_tables
WHERE schemaname = 'public'
GROUP BY schemaname;
```

### 2.2 业务侧快速核对（示例）

```sql
-- 用户与角色
SELECT id, email, role, status FROM users ORDER BY created_at LIMIT 20;

-- 部门树
SELECT id, code, name, parent_id FROM departments ORDER BY code;

-- 近期任务
SELECT id, title, status, assignee_id, created_at FROM tasks ORDER BY created_at DESC LIMIT 20;
```

### 2.3 导出单表 CSV（可选）

在 `psql` 内：

```sql
\copy (SELECT * FROM users LIMIT 100) TO '/tmp/users_sample.csv' WITH CSV HEADER;
```

容器内路径需可写；本机 `psql` 可改为宿主路径。

---

## 3. 写入与修改（增 / 改 / 删）

**原则**：除非做数据修复或实验，避免手写 `INSERT`/`UPDATE`；枚举、JSONB、`uuid` 默认值与触发器与 ORM 不完全一致时易产生脏数据。

### 3.1 单条 UPDATE 示例（慎用）

```sql
BEGIN;
-- 示例：将某用户状态改为 inactive（先确认 id）
UPDATE users SET status = 'inactive', updated_at = NOW()
WHERE email = 'someone@example.com';
-- 检查影响行数
SELECT COUNT(*) FROM users WHERE email = 'someone@example.com' AND status = 'inactive';
ROLLBACK;  -- 确认无误后改为 COMMIT;
```

建议始终先 `BEGIN` … 验证 … 再 `COMMIT` 或 `ROLLBACK`。

### 3.2 删除单条与级联

```sql
-- 外键可能 ON DELETE RESTRICT，失败时需先删子表或改用应用层 API
DELETE FROM task_comments WHERE id = '...'::uuid;
```

删除 `users` / `tasks` 等核心表前，请查阅 [architecture.md](../architecture.md) 中 schema 关系，避免残留孤儿记录或破坏唯一约束。

### 3.3 清空非核心表（仅限开发）

仅在你明确表含义且**无 FK 指向**或已处理依赖时使用，例如清空某张日志实验表；**不要**对生产库执行下列模式：

```sql
TRUNCATE TABLE some_log_table RESTART IDENTITY CASCADE;
```

---

## 4. 迁移（Alembic）

迁移脚本位于 [backend/alembic/versions](../../../backend/alembic/versions)。**规范路径**是在 `backend` 目录、已配置 `POSTGRES_DSN` 的环境中执行。

### 4.1 常用命令

```bash
cd backend
# 激活虚拟环境后
alembic current
alembic history -r -5:head
alembic upgrade head
alembic downgrade -1
```

### 4.2 Docker 内执行（与 Compose 数据库一致）

```bash
cd infra/docker
docker compose -f docker-compose.yml exec backend alembic current
docker compose -f docker-compose.yml exec backend alembic upgrade head
docker compose -f docker-compose.yml exec backend alembic downgrade -1
```

`start-dev.sh` / 生产启动脚本通常会在服务启动前执行 `alembic upgrade head`，手工执行用于排障或新迁移未自动跑的场景。

### 4.3 回退到空库（删除全部应用表）

```bash
cd backend
alembic downgrade base
```

会按迁移逆序删除对象；之后需再 `alembic upgrade head` 才能恢复 schema。  
注意：`vector` 等扩展由迁移创建；`downgrade base` 后再次 `upgrade head` 会按迁移重新创建。

---

## 5. 整库重置（清空业务数据）

### 5.1 方案 A：删除 Docker 卷（Compose 开发栈）

适用于 **`infra/docker/docker-compose.yml`** 且数据仅在命名卷中：

```bash
cd infra/docker
docker compose -f docker-compose.yml down -v
docker compose -f docker-compose.yml up -d
```

`-v` 会删除 `postgres-data` 等卷，**PostgreSQL 数据全部丢失**。  
重新 `up` 后，`backend` 启动会执行 `alembic upgrade head`，得到空结构。

### 5.2 方案 B：保留容器，重建 public schema（暴力 SQL）

在 `psql` 中（**仅开发**）：

```sql
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO filum;
GRANT ALL ON SCHEMA public TO public;
```

然后：

```bash
cd infra/docker
docker compose -f docker-compose.yml exec backend alembic upgrade head
```

若数据库用户不是 `filum`，请将 `GRANT` 中的角色改为实际库用户。

### 5.3 方案 C：仅删数据保留表结构（极少用）

可对各表 `TRUNCATE ... CASCADE` 或按依赖顺序清空；维护成本高，**不如** `downgrade base` + `upgrade head` 或方案 A/B。

---

## 6. 系统初始化（管理员与演示数据）

### 6.1 空库后的首次管理员

1. 确保迁移已到最新：`alembic upgrade head`（或启动 `backend` 一次）。
2. 浏览器打开前端登录页，使用 **「初始化管理员」** 流程创建首个 `admin` 账号（具体文案以当前前端为准）。

若库中已存在用户，初始化接口会拒绝重复引导。

### 6.2 演示组织与 demo 账号（推荐）

在 `backend` 环境（本地 venv 或 `docker compose exec backend`）：

```bash
python -m app.scripts.seed_sample_data --password 'FilumTest123!'
```

行为与账号表见根目录 [README.md](../../../README.md)「测试组织与 demo 账号」。  
若已有管理员，脚本**不会**重置其密码；会 upsert demo 部门与用户。

### 6.3 重置后 Redis（可选）

会话与队列在 Redis 中；仅重置 Postgres 时，若出现旧 refresh token 或队列脏数据，可在开发环境清空 DB 索引或 `docker compose down -v` 一并重建 Redis 卷（与 5.1 相同卷策略时）。

---

## 7. 与对象存储、附件的关系

`STORAGE_BASE_PATH`（或容器内 `/app/.storage`、`/srv/filum/data/storage`）中的文件**不会**随 `DROP SCHEMA` 自动删除。  
若要做「完全干净」环境，请同时清理该目录或对应 Docker volume，避免元数据已删但文件仍占空间。

---

## 8. 生产与预发注意

- 禁止在无备份时执行 `DROP SCHEMA`、`downgrade base`、`docker ... down -v`。
- 大表 `DELETE` 无 `WHERE` 等同事故；使用带条件的批处理或归档表。
- 变更结构应通过 **新 Alembic 迁移** 进入版本库，而非手工 `ALTER` 后与迁移历史分叉。

---

## 9. 相关文档与入口

- Schema 与表关系：[`data-contracts.md`](../data-contracts.md)；模块流程：[`architecture.md`](.../architecture.md)
- 本地 / Compose 启动：[README.md](../../../README.md)、[infra/docker/README.md](../../../infra/docker/README.md)
- 基于 Docker 的 GUI 验证清单：[infra/docker/E2E-GUI-VERIFICATION.md](../../../infra/docker/E2E-GUI-VERIFICATION.md)
