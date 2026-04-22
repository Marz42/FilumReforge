# Project Filum

Project Filum 是一个面向 **50–100 人企业** 的模块化单体内部管理平台，统一承载 **人事档案、事务协同、流程 / 汇报、消息中心、知识库与 AI 指令入口**。当前仓库已经完成 **Phase A–Phase 5** 与重构 **Step 1–Step 7**，当前处于 **Step 7 已实现 / 等待用户验测** 的交付状态，重点已经从“搭骨架”转向“稳定基线后的后续增强”。

## 当前状态

- **已完成**
  - 用户与会话：管理员初始化、JWT access/refresh、角色控制
  - 组织与 HR：部门树、一人一档、字段级权限、多岗位、虚线汇报、生命周期事件、代理授权
  - 事务与协同：任务状态机、评论留痕、任务模板、审批流、周期调度、统计、多视图、六标签任务中心
  - 总览与汇报：总览看板 / 公告 / 当前任务、逐级向上汇报 / 向下传达、历史归档
  - 消息与通知：通知总线、delivery 记录、消息中心、回执、浏览器推送订阅与 Web Push 链路，以及 Step 6 的来源回跳 / 用户级隔离
  - Knowledge / AI：Markdown 知识库、向量检索、`@系统` / `/` 路由、Tool Calling
  - 前端体验：通用模块 / 特殊模块分组导航、统一人员工作台、消息工作台、Push 订阅卡片、PWA manifest / service worker
- **仍待补齐**
  - 公开注册能力
  - 生命周期事件与模板 / 审批流联动
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
- 周期任务调度
- 审批流定义、实例、会签 / 或签 / 驳回 / 打回 / 代理审批
- 列表 / 看板 / 甘特图

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
2. `frontend/.env` 中配置 `VITE_WEB_PUSH_PUBLIC_KEY`
3. `backend/.env` 中配置 `WEB_PUSH_PRIVATE_KEY` 和 `WEB_PUSH_SUBJECT`
4. worker 正在运行
5. 触发的业务场景已经接入通知总线

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
- 当前重构收口已经完成，后续以用户对 Step 7 的最终验测结论为准

## 下一步

当前重构主体已经完成，待你确认 Step 7 验测结论后，下一步建议围绕以下方向继续：

1. 重构服务边界与页面状态管理
2. 扩充集成测试 / E2E 验证
3. 明确并实现注册能力
4. 补齐消息附件与更完整的通知适配器
