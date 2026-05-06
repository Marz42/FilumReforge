# Project Filum Ubuntu 24.04 LTS 部署操作手册

本文档基于当前仓库和一次真实成功部署整理，目标是让你在一台全新的 Ubuntu 24.04 LTS 服务器上，用最短路径完成 Project Filum 的生产部署。

部署形态固定为：

- 前端：Vue 静态产物，由 Nginx 直接托管
- 后端：FastAPI，通过 systemd 常驻，仅监听 `127.0.0.1:8000`
- Worker：ARQ，通过 systemd 常驻
- 数据库：PostgreSQL 16 + `pgvector`
- 队列：Redis 7
- 存储：本地目录 `/srv/filum/data/storage`

这份文档强调两件事：

1. 不跳步
2. 命令可直接复制执行

如果你使用 Cloudflare，第一次部署建议先把域名切到 `DNS only`，不要先开代理。等 HTTP 和 HTTPS 都验证通过后，再决定是否开启代理。

## 0. 部署前输入项

先把下面这些变量替换成你自己的值。后文所有命令默认都基于这些值。

```bash
export FILUM_DOMAIN="projectfilum.com"
export FILUM_WWW_DOMAIN="www.projectfilum.com"
export FILUM_REPO_URL="https://github.com/Marz42/FilumReforge.git"
export FILUM_ROOT="/srv/filum"
export FILUM_USER="filum"
export FILUM_GROUP="filum"
export FILUM_DB_NAME="filum"
export FILUM_DB_USER="filum"
export FILUM_DB_PASSWORD=""
export FILUM_JWT_SECRET=""
export FILUM_TIMEZONE="Asia/Shanghai"
```

生成 JWT 密钥的示例：

```bash
python3 -c "import secrets; print(secrets.token_hex(48))"
```

## 1. 新服务器基线要求

- 系统：Ubuntu 24.04 LTS
- 建议规格：至少 `2C4G`
- 域名：`A` 记录已指向这台服务器公网 IP
- 安全组：至少放行 `22`、`80`、`443`
- 生产机上不要替换系统 Python，不要改 `/usr/bin/python3`

先确认 `80/443` 没有被其他程序占用：

```bash
sudo ss -ltnp '( sport = :80 or sport = :443 )'
```

如果这里已经被其他服务占用，先停止冲突服务，再继续后面的部署。

## 2. 系统初始化

```bash
sudo apt update
sudo apt upgrade -y
sudo timedatectl set-timezone "$FILUM_TIMEZONE"
```

安装基础依赖：

```bash
sudo apt install -y \
  curl \
  git \
  ca-certificates \
  gnupg \
  lsb-release \
  software-properties-common \
  build-essential \
  pkg-config \
  libpq-dev \
  python3.12 \
  python3.12-venv \
  python3-dev \
  nginx \
  redis-server \
  certbot \
  python3-certbot-nginx \
  ufw \
  acl
```

## 3. 安装 Node.js 22

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node -v
npm -v
```

## 4. 安装 PostgreSQL 16 和 pgvector

```bash
sudo install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo gpg --dearmor -o /etc/apt/keyrings/postgres.gpg
echo "deb [signed-by=/etc/apt/keyrings/postgres.gpg] https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list > /dev/null
sudo apt update
sudo apt install -y postgresql-16 postgresql-client-16 postgresql-16-pgvector
```

启动并设置开机自启：

```bash
sudo systemctl enable --now postgresql redis-server nginx
sudo systemctl status postgresql redis-server nginx --no-pager
```

## 5. 初始化数据库

```bash
sudo -u postgres psql <<SQL
CREATE USER ${FILUM_DB_USER} WITH PASSWORD '${FILUM_DB_PASSWORD}';
CREATE DATABASE ${FILUM_DB_NAME} OWNER ${FILUM_DB_USER};
\c ${FILUM_DB_NAME}
CREATE EXTENSION IF NOT EXISTS vector;
SQL
```

确认扩展已启用：

```bash
sudo -u postgres psql -d "$FILUM_DB_NAME" -c "\dx"
```

## 6. 创建系统用户和部署目录

```bash
sudo adduser --system --group --home "$FILUM_ROOT" "$FILUM_USER"
sudo mkdir -p "$FILUM_ROOT" "$FILUM_ROOT/data/storage"
sudo chown -R "$FILUM_USER:$FILUM_GROUP" "$FILUM_ROOT"
sudo chmod 750 "$FILUM_ROOT" "$FILUM_ROOT/data" "$FILUM_ROOT/data/storage"
```

## 7. 拉取代码

```bash
cd /srv
sudo git clone "$FILUM_REPO_URL" "$FILUM_ROOT"
sudo chown -R "$FILUM_USER:$FILUM_GROUP" "$FILUM_ROOT"
```

## 8. 安装后端运行环境

生产环境默认只安装运行依赖，不安装测试依赖：

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e .
'
```

如果你希望在服务器上也执行后端测试，再额外安装开发依赖：

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/backend
source .venv/bin/activate
pip install -e ".[dev]"
'
```

## 9. 写入后端生产环境变量

先复制模板：

```bash
sudo -u "$FILUM_USER" cp "$FILUM_ROOT/backend/.env.production.example" "$FILUM_ROOT/backend/.env"
```

然后直接覆盖为可用版本：

```bash
sudo -u "$FILUM_USER" -H bash -lc "cat > $FILUM_ROOT/backend/.env <<EOF
APP_ENV=production
POSTGRES_DSN=postgresql+asyncpg://${FILUM_DB_USER}:${FILUM_DB_PASSWORD}@127.0.0.1:5432/${FILUM_DB_NAME}
REDIS_DSN=redis://127.0.0.1:6379/0
JWT_SECRET_KEY=${FILUM_JWT_SECRET}
CORS_ALLOWED_ORIGINS=https://app.example.com
FRONTEND_APP_URL=https://${FILUM_DOMAIN}
STORAGE_PROVIDER=local
STORAGE_BUCKET=filum-prod
STORAGE_BASE_PATH=${FILUM_ROOT}/data/storage
WORKERS=2

# Optional: refresh cookie tuning
# AUTH_REFRESH_COOKIE_NAME=filum_refresh_token
# AUTH_REFRESH_COOKIE_PATH=/api/v1/auth
# AUTH_REFRESH_COOKIE_DOMAIN=
# AUTH_REFRESH_COOKIE_SAMESITE=strict
# AUTH_REFRESH_COOKIE_SECURE=true

# Optional: AI features
# OPENAI_API_KEY=
# OPENAI_CHAT_MODEL=gpt-4o-mini
# OPENAI_EMBEDDING_MODEL=text-embedding-3-small
# OPENAI_EMBEDDING_DIMENSIONS=1536

# Optional: Web Push
# WEB_PUSH_PUBLIC_KEY=
# WEB_PUSH_PRIVATE_KEY=
# WEB_PUSH_SUBJECT=mailto:ops@example.com
EOF"
```

说明：

- `backend` 和 `worker` 必须共用同一份 `.env`
- `STORAGE_BASE_PATH` 必须对 `backend` 和 `worker` 都可读写
- `FRONTEND_APP_URL` 必须指向真实前端访问域名；邀请注册链接、后续用户跳转链接都依赖它生成，不能保留为 `http://localhost:5173`
- 当前会话模型为“前端内存态 access token + HttpOnly refresh cookie”；若前后端跨站点部署，需要显式配置 `CORS_ALLOWED_ORIGINS`，并按域名 / SameSite 策略调整 `AUTH_REFRESH_COOKIE_*`
- 若采用同域名 Nginx 反代 `/api/` 的部署方式，默认 `AUTH_REFRESH_COOKIE_SAMESITE=strict` 即可；若采用跨站点前后端分离，需要把 `AUTH_REFRESH_COOKIE_SAMESITE` 调整为 `none` 且同时启用 `AUTH_REFRESH_COOKIE_SECURE=true`
- 不启用 AI 或 Web Push 时，对应配置可以留空

## 10. 写入前端生产环境变量并构建

生产环境下，前端 API 根路径应保持为 `/api/v1`：

```bash
sudo -u "$FILUM_USER" -H bash -lc "cat > $FILUM_ROOT/frontend/.env.production <<EOF
VITE_API_BASE_URL=/api/v1
EOF"
```

安装依赖并构建：

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/frontend
npm ci
npm run build
'
```

确认前端产物已经生成：

```bash
ls -la "$FILUM_ROOT/frontend/dist"
```

## 11. 初始化数据库迁移

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/backend
source .venv/bin/activate
alembic upgrade head
'
```

### 11.1 如需执行 Phase 11-E 旧任务迁移

如果本轮发布包含 Phase 11-E 的旧任务迁移，推荐顺序是：先备份数据库，先跑一次 dry-run，再执行正式迁移，最后抽样核对；不要跳过 dry-run。

```bash
sudo -u postgres pg_dump -Fc <your_db_name> > /srv/filum/backups/filum-$(date +%Y%m%d%H%M%S).dump
```

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/backend
source .venv/bin/activate
python -m app.scripts.migrate_legacy_tasks_to_graph --batch-id phase11e-$(date +%Y%m%d%H%M%S) --dry-run
'
```

确认 dry-run 输出的 `eligible`、`task_ids` 与预期一致后，再执行正式迁移：

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/backend
source .venv/bin/activate
python -m app.scripts.migrate_legacy_tasks_to_graph --batch-id <same-batch-id>
'
```

迁移后至少抽样核对一批历史任务：

- `tasks.metadata` 已写入 `workflow_graph_instance_id` / `workflow_node_instance_id`
- `workflow_graph_instances.source_id` 能回指到原 `tasks.id`
- 待验收历史任务已补出 `workflow_deliverables`

如果迁移结果不符合预期，先停止继续发布，按同一批次标识执行 rollback：

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/backend
source .venv/bin/activate
python -m app.scripts.rollback_legacy_task_migration --batch-id <same-batch-id>
'
```

## 12. 先手工验证后端启动

先手工启动一次后端，确认数据库、Redis、配置没有问题：

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/backend
source .venv/bin/activate
./scripts/start-prod.sh
'
```

另开一个 SSH 会话执行：

```bash
curl http://127.0.0.1:8000/healthz
```

预期输出：

```json
{"status":"ok"}
```

确认无误后，回到前一个终端按 `Ctrl+C` 停掉手工启动的进程。

## 13. 创建 systemd 服务

### 13.1 backend 服务

```bash
sudo tee /etc/systemd/system/filum-backend.service > /dev/null <<'EOF'
[Unit]
Description=Filum Backend
Wants=network-online.target
After=network-online.target postgresql.service redis-server.service

[Service]
Type=simple
User=filum
Group=filum
WorkingDirectory=/srv/filum/backend
EnvironmentFile=/srv/filum/backend/.env
Environment="PATH=/srv/filum/backend/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart=/srv/filum/backend/scripts/start-prod.sh
Restart=always
RestartSec=5
TimeoutStartSec=180
UMask=0027

[Install]
WantedBy=multi-user.target
EOF
```

### 13.2 worker 服务

```bash
sudo tee /etc/systemd/system/filum-worker.service > /dev/null <<'EOF'
[Unit]
Description=Filum Worker
Wants=network-online.target
After=network-online.target postgresql.service redis-server.service filum-backend.service

[Service]
Type=simple
User=filum
Group=filum
WorkingDirectory=/srv/filum/backend
EnvironmentFile=/srv/filum/backend/.env
Environment="PATH=/srv/filum/backend/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
ExecStart=/srv/filum/backend/.venv/bin/arq app.workers.arq_worker.WorkerSettings
Restart=always
RestartSec=5
TimeoutStartSec=180
UMask=0027

[Install]
WantedBy=multi-user.target
EOF
```

### 13.3 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now filum-backend filum-worker
sudo systemctl status filum-backend filum-worker --no-pager
```

查看日志：

```bash
sudo journalctl -u filum-backend -n 100 --no-pager
sudo journalctl -u filum-worker -n 100 --no-pager
```

再次确认健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

## 14. 配置 Nginx，先跑 HTTP

第一次上线时，先只做 HTTP 验证，不要一上来就先配 HTTPS。

先删掉默认站点：

```bash
sudo rm -f /etc/nginx/sites-enabled/default
```

写入站点配置：

```bash
sudo tee /etc/nginx/sites-available/filum.conf > /dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${FILUM_DOMAIN} ${FILUM_WWW_DOMAIN};

    root /srv/filum/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        client_max_body_size 64m;
        proxy_read_timeout 120s;
        proxy_buffering off;
    }

    location = /sw.js {
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        expires 0;
    }

    location = /manifest.webmanifest {
        add_header Cache-Control "public, max-age=3600";
    }

    location /assets/ {
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    location / {
        try_files \$uri \$uri/ /index.html;
        add_header Cache-Control "no-cache, must-revalidate";
    }
}
EOF
```

启用站点：

```bash
sudo ln -sf /etc/nginx/sites-available/filum.conf /etc/nginx/sites-enabled/filum.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 15. 修复 Nginx 读取静态文件的目录权限

这是一次真实部署中踩到过的坑：即使 `dist/index.html` 存在，如果 `www-data` 无法穿越 `/srv/filum` 这一级目录，Nginx 依然会因为 `Permission denied` 返回 `500`。

推荐用 ACL 给 `www-data` 最小读取权限：

```bash
sudo setfacl -m u:www-data:rx /srv/filum
sudo setfacl -m u:www-data:rx /srv/filum/frontend
sudo setfacl -m u:www-data:rx /srv/filum/frontend/dist
sudo setfacl -R -m u:www-data:rX /srv/filum/frontend/dist
```

验证 ACL：

```bash
getfacl /srv/filum
getfacl /srv/filum/frontend/dist
```

重新加载 Nginx：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 16. 开放防火墙

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

说明：

- 不要向公网开放 `5432`
- 不要向公网开放 `6379`
- 不要向公网开放 `8000`

## 17. HTTP 阶段验证

### 17.1 本机验证

```bash
curl -I -H "Host: ${FILUM_DOMAIN}" http://127.0.0.1/
curl -s -H "Host: ${FILUM_DOMAIN}" http://127.0.0.1/ | head -20
curl http://127.0.0.1:8000/healthz
```

预期：

- `/` 返回 `200 OK`
- 页面内容是前端 `dist/index.html`
- `healthz` 返回 `{"status":"ok"}`

### 17.2 公网验证

```bash
curl -I "http://${FILUM_DOMAIN}"
curl -I "http://${FILUM_WWW_DOMAIN}"
```

浏览器验证：

- 打开 `http://projectfilum.com`
- 打开 `http://projectfilum.com/login`
- 用真实账号登录
- 确认 API 正常返回
- 确认站内通知和推送订阅链路正常

## 18. 配置 HTTPS

确认 HTTP 完全正常后，再申请证书：

```bash
sudo certbot --nginx -d "$FILUM_DOMAIN" -d "$FILUM_WWW_DOMAIN"
```

然后验证：

```bash
sudo nginx -t
sudo systemctl reload nginx
curl -I "https://${FILUM_DOMAIN}"
curl -I "https://${FILUM_WWW_DOMAIN}"
sudo certbot renew --dry-run
```

如果你启用了 Cloudflare，建议在 HTTPS 本机和公网验证都通过后，再切回代理模式。

## 19. 发布前检查

在仓库根目录执行：

```bash
cd /srv/filum
bash scripts/check-release.sh
```

说明：

- 生产机默认只安装 runtime 依赖时，脚本会把 `pytest` 缺失记为 `WARN`，不是阻塞项
- `compileall`、`frontend build`、`type-check`、`alembic check` 应通过

如果你需要在服务器上也执行后端测试，请先安装：

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/backend
source .venv/bin/activate
pip install -e ".[dev]"
'
```

## 20. 最终验收清单

执行并确认以下结果：

```bash
curl http://127.0.0.1:8000/healthz
sudo systemctl status filum-backend filum-worker nginx --no-pager
curl -I "https://${FILUM_DOMAIN}"
curl -I "https://${FILUM_WWW_DOMAIN}"
```

浏览器确认：

- 能正常打开登录页
- 能正常登录
- 首页、任务中心、汇报中心、消息中心、知识库可访问
- 能收到站内通知
- Push 订阅成功，浏览器可收到推送

## 21. 后续更新发布流程

当前推荐的后续发布方式是：**本地完成修改并提交到 Git -> 服务器 `git pull` -> 按变更类型更新依赖 / 构建产物 -> 通过 systemd / Nginx 让修改生效**。

不要在服务器上直接改业务代码；服务器只负责拉取已经验证过的提交并发布，这样后续回滚、排障和对比差异都更直接。

### 21.1 发布前本地建议

在本地或至少在一台非生产环境中先完成本轮修改，并尽量执行：

```bash
cd /path/to/FilumReforge
bash scripts/check-release.sh
```

如果本轮只涉及前端或某个小范围后端修复，也至少执行与改动直接相关的测试、`type-check`、`build` 或 `compileall`，不要完全跳过验证就直接推到生产机。

### 21.2 服务器拉取新代码

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum
git pull
'
```

这里不要直接用 `root` 在 `/srv/filum` 下执行 `git pull`。按本文前面的部署步骤，仓库目录属主是 `filum`，如果切到 `root` 再直接操作，Git 会报 `detected dubious ownership`。如果你已经在 `root` shell 里，继续使用 `sudo -u "$FILUM_USER" -H bash -lc '...'` 即可，不建议通过 `git config --global --add safe.directory /srv/filum` 长期绕过这个检查。

如果你平时不是直接在 `main` 上发布，而是用 tag 或固定 commit 发布，推荐改成：

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum
git fetch --all --tags
git checkout <tag-or-commit>
'
```

### 21.3 更新 backend 依赖并执行迁移

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/backend
source .venv/bin/activate
pip install -e .
alembic upgrade head
'
```

如果本轮包含 11-E 旧任务迁移，在这里插入上一节的 dry-run / 正式迁移 / 抽样核对步骤，再继续前端构建与服务重启。

如果本轮后端依赖有变化，`pip install -e .` 不能省略。

### 21.4 更新 frontend 依赖并重建静态产物

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/frontend
npm ci
npm run build
'
```

`npm ci` 会按锁文件重装依赖；如果本轮完全没有前端和 Node 依赖变更，也可以按你的发布习惯改成只执行 `npm run build`，但默认建议保守一点，优先保证产物和锁文件一致。

### 21.5 按变更类型让修改生效

#### A. 只改前端页面、样式、静态资源

通常执行完 `npm run build` 后，新静态文件就已经落到 `/srv/filum/frontend/dist`。保守起见可以再执行：

```bash
sudo systemctl reload nginx
```

#### B. 改 backend API、service、schema、鉴权、配置读取逻辑

执行：

```bash
sudo systemctl restart filum-backend
```

#### C. 改 worker 任务、通知链路、embedding、定时任务或共享后端逻辑

执行：

```bash
sudo systemctl restart filum-backend filum-worker
```

#### D. 改 Nginx 配置

先验证配置：

```bash
sudo nginx -t
```

通过后再：

```bash
sudo systemctl reload nginx
```

#### E. 不确定本轮到底影响了哪些进程

用最保守方式：

```bash
sudo systemctl restart filum-backend filum-worker
sudo systemctl reload nginx
```

### 21.6 一次完整的手工发布示例

如果你不想逐条判断，本仓库当前最稳的主机发布顺序就是：

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum
git pull
'
```

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/backend
source .venv/bin/activate
pip install -e .
alembic upgrade head
'
```

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum/frontend
npm ci
npm run build
'
```

```bash
sudo systemctl restart filum-backend filum-worker
sudo systemctl reload nginx
```

### 21.7 发布后快速验证

至少执行：

```bash
curl http://127.0.0.1:8000/healthz
curl -I "https://${FILUM_DOMAIN}"
sudo systemctl status filum-backend filum-worker nginx --no-pager
sudo journalctl -u filum-backend -n 100 --no-pager
sudo journalctl -u filum-worker -n 100 --no-pager
```

如果本轮改动了前端登录、导航、任务中心、汇报中心、消息中心、部门管理等页面，浏览器里还要至少再点一遍对应入口，不要只看 `200 OK`。

### 21.8 出问题时的最小回退原则

如果发布后发现问题，优先回到上一版代码，再重新构建和重启服务：

```bash
sudo -u "$FILUM_USER" -H bash -lc '
cd /srv/filum
git log --oneline -n 5
git checkout <previous-good-commit>
'
```

然后重复本节中的 backend / frontend / systemd / Nginx 生效步骤。

如果本轮已经执行了数据库迁移，回退前先确认这次迁移是否兼容旧代码；**不要在未确认数据兼容性的情况下直接执行 Alembic downgrade**。

如果问题只集中在 11-F 的默认切流，而不是 schema 或业务数据本身，也可以先用环境变量做短期回退，再决定是否回退代码：

- 只回退任务中心读侧：把 `TASK_CENTER_V2_ENABLED=false`，重启 backend。
- 连同手动任务写侧一起回退：把 `WORKFLOW_GRAPH_ENGINE_ENABLED=false`，backend 与 worker 同步重启。

这两个开关只应作为短期止血手段；确认问题后，仍应尽快回到固定 commit 或补丁版本，不要长期维持双口径漂移。

## 22. 常用排障命令

### 服务状态

```bash
sudo systemctl status filum-backend filum-worker nginx --no-pager
```

### 实时日志

```bash
sudo journalctl -u filum-backend -f
sudo journalctl -u filum-worker -f
sudo journalctl -u nginx -f
```

### Nginx 错误日志

```bash
sudo tail -n 100 /var/log/nginx/error.log
```

### 端口占用

```bash
sudo ss -ltnp '( sport = :80 or sport = :443 or sport = :8000 or sport = :5432 or sport = :6379 )'
```

### 目录权限链

```bash
namei -l /srv/filum/frontend/dist/index.html
```

## 23. 真实部署中已经验证过的坑

1. `80/443` 被别的程序占用时，Nginx 可能不会按你预期接管站点
2. `www-data` 无法穿越 `/srv/filum` 时，Nginx 会因为 `Permission denied` 返回 `500`
3. `backend` 与 `worker` 如果不用同一份 `.env`，常见症状是 worker 启动失败或者通知链路异常
4. 生产机上不建议替换系统 Python，否则会影响 `ufw`、`certbot` 等系统工具
5. 正式环境不要暴露 Vite dev server，不要把开发态 Compose 直接开放到公网

按照本文顺序执行，并在 HTTP 阶段先跑通，再切 HTTPS，是当前最稳的上线方式。