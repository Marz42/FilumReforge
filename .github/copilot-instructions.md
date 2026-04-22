# Copilot Instructions — Project Filum (FilumReforge)

## 当前仓库状态

本仓库不是规划态项目，当前已经完成 Phase A、Phase 1-5，并完成重构 Step 1-7 的实现；最新交付状态以 `memory-bank/architecture.md`、`memory-bank/progress.md`、根目录 `README.md` 为准。

开始任何实现、评审或文档更新前，先确认以下文档分工，不要把它们混用：

- `memory-bank/architecture.md`：当前工程基线、运行结构、完整 schema、关键模块职责
- `memory-bank/design-document.md`：产品目标、业务边界、非目标、后续增强方向
- `memory-bank/progress.md`：阶段和重构步骤的完成状态、验证记录
- `memory-bank/implementation-plan.md`：从当前已交付基线出发的下一轮工作流
- 根目录 `README.md`、`backend/README.md`、`frontend/README.md`：运行、验证、目录入口

优先链接这些文档，不要把现有文档整段复制进新的说明文件。

## 必须遵守的工作方式

- 使用简体中文和开发者沟通。
- 写代码前至少阅读 `memory-bank/architecture.md` 和 `memory-bank/design-document.md`。
- 如果任务涉及阶段状态、交付边界、是否已验测，还要同步查看 `memory-bank/progress.md`。
- 如果文档和代码冲突，先以实际代码、迁移、测试和可运行命令为行为事实，再明确记录是“文档漂移”还是“实现缺口”。
- 不要默认提交 git commit；只有用户明确要求时才提交。
- 不要大段重写 `memory-bank`；仅在确认事实后做最小、可验证的更新。

## 当前技术与边界

- 架构固定为模块化单体，不要引入微服务拆分假设。
- 前端固定为 Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router。
- 后端固定为 FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic。
- 异步 worker 已固定为 ARQ，不再使用 Celery 作为当前实现描述。
- AI 集成固定为官方 `openai` Python SDK；不要引入 LangChain。
- 数据库为 PostgreSQL + JSONB + `pgvector`。
- 所有前端 HTTP 请求统一通过 Axios；所有后端业务逻辑优先放在 service 层，route 保持薄。

## 项目特有约束

- 通知统一走 `NotificationService.send(message_obj)`，业务层不要直连 Email、WebSocket、Web Push。
- 任务状态机必须保持严格流转：`Todo -> Doing -> Review -> Done`。
- 工作沟通必须绑定任务上下文，相关评论和附件进入 `task_comments`，不要设计独立工作聊天系统。
- 档案动态字段进入 `profiles.custom_fields`，不要把可变字段硬塞进固定列。
- LLM 是意图路由器，不是业务真相；工具 schema 优先复用 Pydantic v2。
- 权限控制必须同时考虑角色、组织关系、字段级权限和代理授权。

## 代码导航

- `backend/app/main.py`：FastAPI 入口、CORS、request id 中间件、异常处理注册
- `backend/app/api/routes/`：API 路由层；关键聚合入口包括 `overview.py`、`task_center.py`、`report_center.py`、`messages.py`、`people_management.py`
- `backend/app/services/`：核心业务编排，优先在这里查真实行为
- `backend/app/models/` 与 `backend/alembic/versions/`：领域模型和数据库事实来源
- `frontend/src/router/`：当前路由和兼容重定向
- `frontend/src/views/`：总览、任务中心、汇报中心、消息中心、知识库、人员工作台等主工作台
- `frontend/tests/`、`backend/tests/`：当前行为的回归证据

## 已验证的常用命令

### Backend

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
pytest -q
python -m compileall app tests
./scripts/start-dev.sh
./scripts/start-worker.sh
```

### Frontend

```sh
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
npm run test:unit -- --run
npm run type-check
npm run build
npm run lint
```

### Compose

```sh
cd infra/docker
docker compose -f docker-compose.yml up --build -d
```

## memory-bank 对齐审查约定

如果任务是“确认 memory-bank 和实际实现是否对齐”或“输出架构/实现评估报告”，按下面顺序执行：

1. 先读 `memory-bank/architecture.md`、`design-document.md`、`progress.md`、`implementation-plan.md`
2. 再核对根目录 `README.md`、`backend/README.md`、`frontend/README.md`
3. 用迁移、模型、服务、路由、前端路由/视图、测试确认事实
4. 区分三类结论：
	- 文档已对齐
	- 文档漂移但实现存在
	- 设计目标存在但实现未落地
5. 如果用户要求写报告，把报告放到 `memory-bank/`，并明确列出证据文件、问题等级、建议动作

不要把“目标设计”误写成“当前已实现”，也不要因为 memory-bank 写了某能力就直接假定代码里已经存在。

## 文档更新原则

- 重大实现变化后，优先更新 `memory-bank/architecture.md`。
- 如果阶段状态、验测结论或交付边界变化，再更新 `memory-bank/progress.md`。
- 如果产品目标、非目标或路线图变化，再更新 `memory-bank/design-document.md` 或 `memory-bank/implementation-plan.md`。
- 更新文档时引用真实文件和真实命令，不写无法从仓库验证的描述。

