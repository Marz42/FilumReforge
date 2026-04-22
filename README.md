# Project Filum

Project Filum 是一个面向 **50–100 人企业** 的模块化单体内部管理平台，统一承载 **人事档案、事务协同、流程 / 汇报、消息中心、知识库与 AI 指令入口**。当前仓库已经完成 **Phase A–Phase 5** 与重构 **Step 1–Step 7**，且 Step 7 已通过用户验测；当前已进入工作流 E 的后续增强阶段，并已完成首批“结构化任务模板与多步骤协作”实现。

## 当前状态

- **已完成**
  - 用户与会话：管理员初始化、JWT access/refresh、角色控制
  - 组织与 HR：部门树、一人一档、字段级权限、多岗位、虚线汇报、生命周期事件、代理授权
  - 事务与协同：任务状态机、评论留痕、任务模板、审批流、周期调度、统计、多视图、六标签任务中心
  - 工作流 E 首批：模板实例运行态、按依赖逐步激活、多人扇出 / 汇聚（`all` / `any`）、模板实例快照、结构化设计器首版与已有模板编辑
  - 总览与汇报：总览看板 / 公告 / 当前任务、逐级向上汇报 / 向下传达、历史归档
  - 消息与通知：通知总线、delivery 记录、消息中心、回执、浏览器推送订阅与 Web Push 链路，以及 Step 6 的来源回跳 / 用户级隔离
  - Knowledge / AI：Markdown 知识库、向量检索、`@系统` / `/` 路由、Tool Calling
  - 前端体验：通用模块 / 特殊模块分组导航、统一人员工作台、消息工作台、Push 订阅卡片、PWA manifest / service worker
- **仍待补齐**
  - 公开注册能力
  - 生命周期事件与模板 / 审批流联动
  - 工作流 E 的后续收口：模板 / 调度管理动作深化、全量回归、部署硬化与更强设计器校验
  - 消息附件
  - 通知适配器的真实外部集成深化（当前 Email / WebSocket 为最小实现）
  - 针对当前基线的进一步重构与测试强化

## 主要能力

### 人事与组织

- 部门树与管理范围控制
- 一人一档与 `custom_fields JSONB`
- 多岗位 / 兼职 / 代理岗
- 直属 / 虚线汇报线
- 字段级权限裁剪
- 入职、转岗、晋升、奖惩、离职、返聘
- 代理授权与按时间窗生效

### 任务、模板与审批

- 严格状态机：`Todo -> Doing -> Review -> Done`
- 任务评论、内部备注、活动流、评论附件
- 前置依赖
- 任务模板与模板实例化
- 模板实例运行态、按依赖逐步激活、多人扇出 / 汇聚（`all` / `any`）
- 结构化模板设计器、JSON 导入 / 预览与模板实例快照
- 周期任务调度
- 审批流定义、实例、会签 / 或签 / 驳回 / 打回 / 代理审批
- 列表 / 看板 / 甘特图

当前任务模板的工作流 E 首批已经落地：实例化只会激活当前可执行步骤，后续步骤会随着任务完成自动推进；模板页已提供结构化设计器、JSON 导入、实例运行态快照与已有模板的结构化编辑。下一批重点转向模板 / 调度管理深化、生命周期联动、全量回归与部署收口。

### 消息、Push 与 AI

- 统一通知总线：`NotificationService.send(message_obj)`
- `notification_messages` / `notification_deliveries` / `notification_receipts`
- 消息中心收件箱与回执
- 浏览器 Push 订阅与 Web Push 投递
- Markdown 知识库、RAG 检索
- `@系统 ...` 与 `/...` 命令入口
- 后端工具注册与 OpenAI Tool Calling

## 技术栈

| 层 | 技术 |
| --- | --- |
| Frontend | Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router |
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic |
| Database | PostgreSQL + JSONB + pgvector |
| Cache / Queue | Redis |
| Worker | ARQ |
| AI | 官方 `openai` Python SDK |
| Push | Web Push (`pywebpush`) |
| Deploy | Docker Compose + Nginx |

## 仓库结构

```text
.
├── backend/        # FastAPI、服务层、模型、迁移、worker、脚本
├── frontend/       # Vue 3 管理后台
├── infra/          # Docker Compose 与 Nginx 配置
└── memory-bank/    # 设计文档、架构基线、实施计划、进度记录
```

## 文档入口

- `memory-bank/design-document.md`：产品目标、业务边界、未来增强方向
- `memory-bank/architecture.md`：当前工程基线、关键模块、运行时结构、完整 schema
- `memory-bank/implementation-plan.md`：从当前代码状态出发的下一步实施路线
- `memory-bank/progress.md`：已完成事项与验测补记
- `memory-bank/tech-stack.md`：技术选型与落地状态

## 快速开始

### 方式一：Docker Compose（推荐）

```sh
cd infra/docker
cp .env.example .env 2>/dev/null || true
docker compose -f docker-compose.yml up --build -d
```

启动后统一入口：

- **Web**: `http://127.0.0.1:8080`
- **Backend API**: `http://127.0.0.1:8000`
- **Frontend Dev**: `http://127.0.0.1:5173`

查看日志：

```sh
docker compose -f docker-compose.yml logs -f backend worker frontend nginx
```

说明：当前 [infra/docker/docker-compose.yml](infra/docker/docker-compose.yml) 用于开发 / 集成联调，`backend` 通过 [backend/scripts/start-dev.sh](backend/scripts/start-dev.sh) 以 `uvicorn --reload` 启动，`frontend` 运行 Vite dev server，并通过 bind mount 挂载源码目录；它适合本地验证，不建议原样直接暴露到公网生产环境。

### 方式二：本地直启

#### Backend

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
./scripts/start-dev.sh
```

#### Worker

```sh
cd backend
. .venv/bin/activate
./scripts/start-worker.sh
```

#### Frontend

```sh
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## 云服务器部署（推荐 Ubuntu + Nginx + systemd）

当前仓库已经具备实际部署基础，但还没有开箱即用的 production compose 文件。若要部署到云服务器，推荐采用“**前端静态文件 + Nginx + backend/worker systemd + PostgreSQL/Redis**”这条路径，而不是直接把开发态 Compose 暴露到公网。

如果需要一份按真实成功部署整理、可以逐条复制执行的完整操作手册，请直接看 [memory-bank/deployment-runbook-ubuntu-2404.md](memory-bank/deployment-runbook-ubuntu-2404.md)。该文档覆盖 Ubuntu 24.04 LTS 全新服务器初始化、PostgreSQL/Redis/Nginx/systemd 配置、前端静态文件权限、HTTP/HTTPS 验证、推送通知验证以及后续更新发布流程。

### 推荐拓扑

- Nginx：公网 80 / 443 入口、TLS、前端静态资源与 `/api/` 反向代理
- Backend：`uvicorn app.main:app`，仅监听 `127.0.0.1:8000`
- Worker：`arq app.workers.arq_worker.WorkerSettings`
- PostgreSQL 16 + `pgvector`
- Redis 7
- 本地持久化目录：`/srv/filum/data/storage`（当前对象存储仍以 `local` provider 为主）

### 1. 服务器准备

- Ubuntu 22.04 / 24.04
- 建议起步 2C4G；若启用 RAG、浏览器推送与较高并发，建议 4C8G
- 域名解析到云服务器公网 IP
- 公网放行 80 / 443；数据库和 Redis 优先走内网或安全组白名单

### 2. 拉取代码与安装依赖

```sh
sudo mkdir -p /srv/filum /srv/filum/data/storage
sudo chown -R $USER:$USER /srv/filum
git clone <your-repo-url> /srv/filum

cd /srv/filum/backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cd /srv/filum/frontend
npm install
npm run build
```

### 3. 配置后端环境变量

在 `/srv/filum/backend/.env` 中至少配置：

```env
APP_ENV=production
POSTGRES_DSN=postgresql+asyncpg://<user>:<password>@<db-host>:5432/<db-name>
REDIS_DSN=redis://<redis-host>:6379/0
JWT_SECRET_KEY=<至少 32 字节随机串>
OPENAI_API_KEY=<可选，不使用 AI 时可留空>
WEB_PUSH_PUBLIC_KEY=<可选，不使用浏览器推送时可留空>
WEB_PUSH_PRIVATE_KEY=<可选，不使用浏览器推送时可留空>
WEB_PUSH_SUBJECT=mailto:ops@example.com
STORAGE_PROVIDER=local
STORAGE_BUCKET=filum-prod
STORAGE_BASE_PATH=/srv/filum/data/storage
```

约束说明：

- `backend` 与 `worker` 必须使用同一份 `.env`
- `STORAGE_BASE_PATH` 必须对 `backend` 和 `worker` 都可读写
- 当前如果继续使用本地对象存储，需要把 `/srv/filum/data/storage` 纳入云盘快照或备份策略

### 4. 初始化数据库与管理员

```sh
cd /srv/filum/backend
source .venv/bin/activate
alembic upgrade head
```

正式环境建议首次打开 `/login` 完成管理员初始化；`seed_sample_data` 更适合测试 / 预发环境，不建议在正式环境导入 demo 组织与账号。

### 5. 配置 backend / worker 为 systemd 服务

`/etc/systemd/system/filum-backend.service`：

```ini
[Unit]
Description=Filum Backend
After=network.target

[Service]
User=filum
Group=filum
WorkingDirectory=/srv/filum/backend
EnvironmentFile=/srv/filum/backend/.env
ExecStart=/srv/filum/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/filum-worker.service`：

```ini
[Unit]
Description=Filum Worker
After=network.target

[Service]
User=filum
Group=filum
WorkingDirectory=/srv/filum/backend
EnvironmentFile=/srv/filum/backend/.env
ExecStart=/srv/filum/backend/.venv/bin/arq app.workers.arq_worker.WorkerSettings
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用服务：

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now filum-backend filum-worker
```

### 6. 使用 Nginx 提供前端与 API 反代

示例 `/etc/nginx/sites-available/filum.conf`：

```nginx
server {
  listen 80;
  server_name filum.example.com;

  root /srv/filum/frontend/dist;
  index index.html;

  location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

加载配置：

```sh
sudo ln -sf /etc/nginx/sites-available/filum.conf /etc/nginx/sites-enabled/filum.conf
sudo nginx -t
sudo systemctl reload nginx
```

如需 HTTPS，推荐使用 Certbot：

```sh
sudo certbot --nginx -d filum.example.com
```

### 7. 部署后验证

```sh
curl http://127.0.0.1:8000/healthz
sudo systemctl status filum-backend filum-worker
sudo journalctl -u filum-backend -u filum-worker -f
```

上线检查清单：

- 浏览器能正常访问 `/login`
- `POSTGRES_DSN`、`REDIS_DSN` 指向生产或托管服务
- 浏览器推送使用真实 `WEB_PUSH_*` 配置
- 已完成数据库备份与 `STORAGE_BASE_PATH` 目录备份
- Nginx 已启用 HTTPS

## 测试与验证

### Backend

```sh
cd backend
. .venv/bin/activate
pytest -q
python -m compileall app tests
```

### Frontend

```sh
cd frontend
npm run test:unit -- --run
npm run type-check
npm run build
npm run lint
```

## 测试组织与 demo 账号

仓库内置了可重复执行的测试数据脚本：

```sh
cd backend
. .venv/bin/activate
alembic upgrade head
python -m app.scripts.seed_sample_data --password 'FilumTest123!'
```

脚本行为：

- 如果库里**没有管理员**，会自动初始化 `admin@example.com`
- 如果库里**已有管理员**，会复用现有管理员，不重置其密码
- 会创建一套测试组织、岗位、档案、汇报线和 demo 账号

### demo 账号

除现有管理员外，脚本创建的 demo 账号默认密码统一为 **`FilumTest123!`**。

| 邮箱 | 角色 | 部门 | 状态 |
| --- | --- | --- | --- |
| `demo.hr@example.com` | HR | 人力运营中心 | active |
| `demo.hrbp@example.com` | HR | 人力运营中心 | active |
| `demo.tech.director@example.com` | 员工 | 技术中心 | active |
| `demo.platform.lead@example.com` | 员工 | 平台研发组 | active |
| `demo.engineer.a@example.com` | 员工 | 平台研发组 | active |
| `demo.engineer.b@example.com` | 员工 | 平台研发组 | active |
| `demo.success@example.com` | 员工 | 客户成功部 | active |
| `demo.finance@example.com` | 员工 | 财务行政部 | active |
| `demo.former@example.com` | 员工 | 客户成功部 | offboarded |

## 当前主要页面与路由

- `/login`：登录与管理员初始化
- `/overview`：总览（看板、公告、待办事项、任务跟踪）
- `/task-center`：任务中心（模板、发布、待办、跟踪、历史、备忘）
- `/reports`：汇报中心（待处理、我发起、历史、向上汇报、向下传达）
- `/messages`：消息中心与 Push 订阅
- `/knowledge-base`：知识库
- `/people`：统一人员工作台（管理员 / HR）
- `/departments`：部门管理（仅管理员）

兼容旧入口仍然保留重定向：

- `/dashboard` -> `/overview`
- `/tasks`、`/task-templates` -> `/task-center`
- `/approvals` -> `/reports`
- `/users`、`/profiles` -> `/people`

## 浏览器推送说明

要收到浏览器通知，需要同时满足：

1. 前端消息页完成 Push 订阅
2. 登录后前端能从 `/api/v1/push-subscriptions/config` 读取运行时 Web Push 公钥
3. `backend/.env` 中配置 `WEB_PUSH_PUBLIC_KEY`、`WEB_PUSH_PRIVATE_KEY` 和 `WEB_PUSH_SUBJECT`
4. worker 正在运行
5. 触发的业务场景已经接入通知总线

说明：`frontend/.env` 中的 `VITE_WEB_PUSH_PUBLIC_KEY` 现在只作为兼容兜底配置，标准路径改为后端运行时下发公钥。

当前已接入的浏览器通知场景包括：

- 任务指派
- 任务转派
- 任务抄送
- 模板实例化抄送
- 逾期提醒
- 审批待办 / 审批提醒

## 当前已知边界

- **不支持访客自助注册**
- **不建设独立聊天系统**
- Email / WebSocket 适配器当前为最小实现，重点先放在通知总线与 delivery 语义稳定
- PWA 当前提供安装与 Push 基线，不追求复杂离线编辑
- 当前重构收口已经完成，并已进入后续增强工作流

## 下一步

当前重构主体已经完成，工作流 E 首批也已落地；下一轮优先级建议如下：

1. 工作流 E 的回归、部署收口与模板 / 调度管理深化
2. 重构服务边界与页面状态管理
3. 扩充集成测试 / E2E 验证
4. 明确并实现注册能力
5. 补齐消息附件与更完整的通知适配器
