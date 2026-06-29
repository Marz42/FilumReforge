# Project Filum

Project Filum 是一个面向 **50–100 人企业** 的模块化单体内部管理平台，统一承载 **人事档案、事务协同、流程 / 汇报、消息中心、知识库与 AI 指令入口**。当前仓库已完成 **Phase A–Phase 5**、重构 **Step 1–Step 7**、**UI 信息架构 Phase A–F**（登录/壳层/任务中心/汇报中心/组织管理/总览 Dashboard），以及工作流图引擎 **Phase 11** 主干与工作流 E 首批能力。

## 当前状态

- **已完成**
  - 用户与会话：管理员初始化、JWT access token、HttpOnly refresh cookie 轮换 / logout 撤销、角色控制
  - 组织与 HR：部门树、一人一档、字段级权限、多岗位、虚线汇报、生命周期事件、代理授权
  - 事务与协同：任务状态机、评论留痕、任务模板、审批流、周期调度、统计；任务中心 **Quick Chips + Master-Detail**（待处理 / 跟踪 / 历史）、列表/看板/甘特视图、页头 **建立任务 Dialog**、全局备忘（列表 + 编辑 Dialog，可选标题）、附件鉴权下载与**应用内预览**（F-25）、独立 **任务模板** 路由；**Admin/HR 跟踪督办**与**逾期延期**（`0.91.0`）；**管理员任务归档** F-29（终止图 Run）
  - 工作流图引擎重构已到 **Phase 11-G**（含 Playwright mock/live 基线）；任务中心默认 **graph-first** 读路径（`task_center_v2_enabled=true`）；详见 `memory-bank/progress.md` 与 `domains/workflow-graph-engine.md`
  - 工作流 E 首批：模板实例运行态、按依赖逐步激活、多人扇出 / 汇聚（`all` / `any`）、模板实例快照、结构化设计器首版与已有模板编辑
  - 总览与汇报：总览看板 / 公告 / 当前任务、逐级向上汇报 / 向下传达、历史归档
  - 消息与通知：通知总线、delivery 记录、消息中心、回执、浏览器推送订阅与 Web Push 链路，以及 Step 6 的来源回跳 / 用户级隔离
  - Knowledge / AI：Markdown 知识库、向量检索、`@系统` / `/` 路由、Tool Calling
  - 前端体验：分组侧栏导航、顶栏 **AI 命令 + 消息铃铛 Drawer + 截止倒计时**、总览 Dashboard 小组件、设置三分栏（资料/安全/通知）、人员宽 Drawer + 部门树 Master-Detail、邀请制登录三场景、Playwright 单元测试与 Docker GUI E2E（18 用例）
- **仍待补齐**
  - 访客公开自助注册与审批式注册（**邀请制注册**已落地：管理员发邀请链接、受邀人设置密码激活；与「完全无注册能力」不同）
  - 生命周期事件的规则化默认联动与前端结构化配置入口（后端已支持事件上**显式绑定**模板 / 审批目标并由 **worker 异步触发**）
  - **工作流 E 与图引擎（`WorkflowGraphTemplate`）的产品级统一**、模板 / 调度管理深化、更强设计器校验（任务中心读侧已默认 graph-first）
  - 通知适配器的真实外部集成深化与更完整的投递观测（当前 Email / WebSocket 为最小实现）
  - **Stage 2 Phase 6** 已收口（在线 Ubuntu 主机演练 + 2026-05-21 测试基线）；**Ubuntu 最小回滚路径**仍待演练

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
- **管理员治理**（`0.91.0`）：单条任务归档（软作废 + 终止图 Run）、Admin/HR 跟踪督办、逾期延期（不阻断推进）

工作流 E 首批已落地。图引擎 **Phase 11-G** 已完成；任务中心默认 graph-first（`task_center_v2_enabled=true`）。视频工作流 v1（W0–W10）已硬化，见 `memory-bank/domains/workflow-video-v1.md`。

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
└── memory-bank/    # 设计/架构/进度（根目录）+ handbooks/ + plans/ + history/ + archive/
```

## 文档入口

Agent 协作见 [`AGENT_RULES.md`](AGENT_RULES.md)、[`VERSION`](VERSION)。memory-bank 索引与温度分层见 [`memory-bank/README.md`](memory-bank/README.md)。

| 文件 | 用途 |
| --- | --- |
| [`project-brief.md`](memory-bank/project-brief.md) | 产品愿景、边界、技术栈摘要（🔥） |
| [`architecture.md`](memory-bank/architecture.md) | 工程蓝图、运行时、核心流程（🔥） |
| [`data-contracts.md`](memory-bank/data-contracts.md) | schema、枚举、API 索引（🔥） |
| [`conventions.md`](memory-bank/conventions.md) | 编码与协作规范（🔥） |
| [`active-task.md`](memory-bank/active-task.md) | 当前聚焦任务（🔥） |
| [`progress.md`](memory-bank/progress.md) | 会话摘要、阶段验收、测试基线（🔥） |
| [`roadmap.md`](memory-bank/roadmap.md) | 宏观里程碑（🌡️） |
| [`plans/`](memory-bank/plans/) | 细粒度实施计划（🌡️） |
| [`domains/`](memory-bank/domains/) | 子系统领域文档（🌡️） |
| [`handbooks/`](memory-bank/handbooks/) | 运维与用户手册（🧊） |

完整产品设计/技术选型叙述：[`design-document.md`](memory-bank/design-document.md)、[`tech-stack.md`](memory-bank/tech-stack.md)（摘要已迁入 project-brief）。

- [`handbooks/user-manual.md`](memory-bank/handbooks/user-manual.md)：用户说明书 v1.2
- [`handbooks/manual-database-operations.md`](memory-bank/handbooks/manual-database-operations.md)：PostgreSQL 手工操作
- [`handbooks/e2e-gui-verification-automation-runbook.md`](memory-bank/handbooks/e2e-gui-verification-automation-runbook.md)：Docker + Playwright GUI 验证
- [`infra/docker/E2E-GUI-VERIFICATION.md`](infra/docker/E2E-GUI-VERIFICATION.md)：端到端 GUI 分层验证清单

## 快速开始

### 方式一：Docker Compose（推荐）

```sh
cd infra/docker
cp .env.example .env 2>/dev/null || true
# 编辑 infra/docker/.env，至少填入 JWT_SECRET_KEY
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
# 编辑 backend/.env，至少填入 JWT_SECRET_KEY
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

当前仓库已经具备两条可用的生产部署路径：

- **主机部署**：`前端静态文件 + Nginx + backend/worker systemd + PostgreSQL/Redis`，适合直接落到 Ubuntu 主机。
- **容器部署**：`infra/docker/docker-compose.prod.yml` + `backend/frontend Dockerfile.prod`，适合走容器编排。

推荐优先使用主机部署路径；如果偏好容器编排，可直接使用生产 Compose，而不是把开发态 Compose 暴露到公网。

如果需要一份按真实成功部署整理、可以逐条复制执行的完整操作手册，请直接看 [memory-bank/handbooks/deployment-runbook-ubuntu-2404.md](memory-bank/handbooks/deployment-runbook-ubuntu-2404.md)。该文档覆盖 Ubuntu 24.04 LTS 全新服务器初始化、PostgreSQL/Redis/Nginx/systemd 配置、前端静态文件权限、HTTP/HTTPS 验证、推送通知验证以及后续更新发布流程。完整文档索引见 [memory-bank/README.md](memory-bank/README.md)。

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
CORS_ALLOWED_ORIGINS=https://app.example.com
OPENAI_API_KEY=<可选，不使用 AI 时可留空>
WEB_PUSH_PUBLIC_KEY=<可选，不使用浏览器推送时可留空>
WEB_PUSH_PRIVATE_KEY=<可选，不使用浏览器推送时可留空>
WEB_PUSH_SUBJECT=mailto:ops@example.com
STORAGE_PROVIDER=local
STORAGE_BUCKET=filum-prod
STORAGE_BASE_PATH=/srv/filum/data/storage

# 可选：refresh cookie 调优
# AUTH_REFRESH_COOKIE_NAME=filum_refresh_token
# AUTH_REFRESH_COOKIE_PATH=/api/v1/auth
# AUTH_REFRESH_COOKIE_DOMAIN=
# AUTH_REFRESH_COOKIE_SAMESITE=strict
# AUTH_REFRESH_COOKIE_SECURE=true
```

约束说明：

- `backend` 与 `worker` 必须使用同一份 `.env`
- `STORAGE_BASE_PATH` 必须对 `backend` 和 `worker` 都可读写
- 当前会话模型为“前端内存态 access token + HttpOnly refresh cookie”；如前后端跨站点部署，需要同时核对 `CORS_ALLOWED_ORIGINS` 与 `AUTH_REFRESH_COOKIE_*` 相关配置
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

**当前测试基线**（commit `36c6a77`，2026-05-21）：见 [`memory-bank/progress.md`](memory-bank/progress.md)「测试基线」— 后端 **153** pytest、前端 **106** vitest、Docker GUI 沿用 **18/18**（2026-05-20）。

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

### Docker GUI E2E（需 `infra/docker` 栈运行于 `http://127.0.0.1:8080`）

```sh
cd frontend
npm run test:e2e:docker-gui
```

报告与截图默认写入仓库根目录 `verification-runs/docker-gui-<时间戳>/`。详见 `memory-bank/handbooks/e2e-gui-verification-automation-runbook.md`。

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

| 路径 | 说明 |
| --- | --- |
| `/login` | 日常登录 / 邀请激活 / 空库系统初始化（三场景自动切换） |
| `/overview` | 总览 Dashboard：消息预览、公告/白板、待办与待审汇报、快捷入口 |
| `/task-center` | 任务中心：`filter=inbox\|tracking\|history`，`view=list\|board\|gantt`，`selected=` 深链 |
| `/task-templates` | 任务模板管理（管理员 / HR，侧栏「特殊模块」） |
| `/reports` | 汇报中心：Master-Detail + 撰写汇报 Drawer |
| `/messages` | 消息全页（侧栏无入口；主入口为顶栏铃铛 Drawer） |
| `/knowledge-base` | 知识库 |
| `/settings/profile` · `/security` · `/notifications` | 设置：个人资料、改密、推送/PWA |
| `/people` | 人员管理（管理员 / HR）：列表 + 宽 Drawer 锚点导航 |
| `/departments` | 部门管理（仅管理员）：树 + 详情分栏 |

兼容旧书签（自动跳转）：

- `/dashboard` → `/overview`
- `/tasks` → `/task-center?filter=tracking`
- `/approvals` → `/reports`
- `/users`、`/profiles` → `/people`（保留 `tab` 查询参数映射）

操作细节见 [`memory-bank/handbooks/user-manual.md`](memory-bank/handbooks/user-manual.md)。

## 浏览器推送说明

要收到浏览器通知，需要同时满足：

1. 在 **设置 → 通知偏好**（或全页 `/messages`）完成 Push 订阅
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

- **不支持访客自助注册**（**邀请制注册**已支持：由管理员创建邀请并由受邀人激活）
- **不建设独立聊天系统**
- Email / WebSocket 适配器当前为最小实现，重点先放在通知总线与 delivery 语义稳定
- PWA 当前提供安装与 Push 基线，不追求复杂离线编辑
- UI 信息架构 Phase A–F 已交付；消息主入口为顶栏铃铛，非侧栏一级菜单

## 下一步

1. **任务中心增强 TCE Phase 1** — graph 读模型、操作后 refresh、看板可读、测试服 department 迁移（[`memory-bank/plans/task-center-enhance.md`](memory-bank/plans/task-center-enhance.md) · [`active-task.md`](memory-bank/active-task.md)）
2. TCE Phase 2–4 — batch hydration、部门统计、多文案部门共用图模板
3. **TCE Phase 5 / TC-P3** — 工作流 E 与图引擎统一（ADR-005）
4. 生命周期规则 UI 与默认映射；通知适配器真实外发
5. **Ubuntu 最小回滚路径演练** — 暂缓，上线前再补

进度与验测记录见 [`memory-bank/progress.md`](memory-bank/progress.md)。
