# Project Filum 进度记录

## 当前状态

| 阶段                 | 状态    | 结论                                                      |
| -------------------- | ------- | --------------------------------------------------------- |
| Phase A              | done    | 文档入口、前后端脚手架、基础容器编排已完成                |
| Phase 1 / Foundation | done    | 模型、服务、API、前端对接已完成，并已通过用户实际点击验证 |
| Phase 2+             | pending | 尚未开始，必须在 Phase 1 基线之上继续推进                 |

## Phase A 记录

| 步骤               | 状态 | 产出                                                                                                 | 验证                                                                                           |
| ------------------ | ---- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| 文档基线与标准入口 | done | 新增 `architecture.md`、`design-document.md`，并补齐 schema、模块边界、测试基线                      | 已确认文件存在；文档引用已对齐；旧 `design-document.md.md` 已标记为历史草稿                    |
| 前端脚手架         | done | 初始化 Vue 3 + TypeScript + Vite + Pinia + Vue Router，并接入 Element Plus、Axios 与首页壳           | 已执行 `npm run test:unit -- --run`、`npm run build`、`npm run lint`                           |
| 后端脚手架         | done | 初始化 FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic，并建立健康检查、对象存储/通知抽象骨架 | 已执行 `pytest`、`python -m compileall app`                                                    |
| 容器化编排         | done | 新增 frontend/backend Dockerfile、`docker-compose.yml`、Nginx 代理配置与 `.env.example`              | 已检查关键文件存在与服务声明；已执行 `npx prettier --check ../infra/docker/docker-compose.yml` |

## Phase 1 / Foundation 记录

### 1. 模型先行

| 步骤                 | 状态 | 产出                                                                                                                                                                                                | 验证                               |
| -------------------- | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| 枚举与数据库类型基线 | done | 新增 `backend/app/core/enums.py`、`db_types.py`，统一跨 PostgreSQL / SQLite 的枚举与 JSON 类型                                                                                                      | 已纳入 `pytest`                    |
| 领域模型与 mixin     | done | 新增 `users`、`refresh_tokens`、`departments`、`profiles`、`attachments`、`attachment_links`、`tasks`、`task_dependencies`、`notification_messages`、`notification_deliveries` 对应模型与公共 mixin | 已执行模型测试与 metadata 构建验证 |
| Alembic 迁移         | done | 新增 `20260413_01_phase1_foundation.py`，覆盖 Phase 1 所需表、索引、约束                                                                                                                            | 已执行升级/降级测试                |

### 2. 服务层封装

| 步骤           | 状态 | 产出                                                                  | 验证                         |
| -------------- | ---- | --------------------------------------------------------------------- | ---------------------------- |
| 认证服务       | done | `AuthService` 支持 bootstrap admin、登录、refresh、当前用户解析       | 已执行服务测试               |
| 组织与档案服务 | done | `UserService`、`DepartmentService`、`ProfileService` 支持管理与查询   | 已执行服务测试               |
| 附件与对象存储 | done | `ObjectStorageService`、`AttachmentService`、本地对象存储适配器已接通 | 已执行上传/删除测试          |
| 任务与通知     | done | `TaskService`、`NotificationService`、Redis 队列发布器已接通          | 已执行任务创建与通知入队测试 |

### 3. API 暴露

| 步骤               | 状态 | 产出                                                                            | 验证                |
| ------------------ | ---- | ------------------------------------------------------------------------------- | ------------------- |
| 依赖注入与错误映射 | done | 新增 `dependencies.py`、`error_handlers.py`，统一认证、对象存储、通知与异常响应 | 已执行 API 集成测试 |
| 业务路由           | done | 新增 `auth`、`users`、`departments`、`profiles`、`tasks`、`attachments` 路由    | 已执行 API 集成测试 |
| 开发态错误可读性   | done | 数据库连接超时会返回明确的 `503` 提示，而不是直接暴露长栈追踪                   | 已新增错误处理测试  |

### 4. 前端对接

| 步骤                | 状态 | 产出                                                                                 | 验证                                 |
| ------------------- | ---- | ------------------------------------------------------------------------------------ | ------------------------------------ |
| 会话层与 API Client | done | 新增 `src/api/*`、`auth` store、token 持久化、自动 refresh 逻辑                      | 已执行前端单元测试                   |
| 路由守卫与后台壳    | done | 新增 `AppShell`、登录页、受保护路由与角色路由                                        | 已执行前端单元测试与构建             |
| 业务页面            | done | 完成仪表盘、部门页、档案页、任务页与附件上传对接                                     | 已执行 `type-check`、`build`、`lint` |
| 联调修复            | done | 修复开发代理 404，增加开发态直连后端 fallback，并补齐 Compose 自动迁移与本地启动模板 | 已完成用户实际点击验证               |

## 用户验测后补记

用户在实际点击“初始化管理员”和“登录”时，先后暴露出两类问题：

1. **前端开发代理缺失**：请求命中了前端开发服务器，返回 404。已通过 Vite 代理与开发态直连 fallback 修复。
2. **数据库未启动 / 连接不可用**：后端返回 `TimeoutError`。已通过更明确的 `503` 响应、本地 `.env.example` 修正、Compose 自动迁移脚本与启动文档收口。

在上述修复后，用户确认前端实际点击链路已正常通过。

## 当前可用能力

- 管理员初始化与登录
- JWT access / refresh 会话链路
- 用户管理
- 部门管理与组织树查询
- 员工档案管理（含 `custom_fields`）
- 任务创建、列表与重新指派
- 任务附件上传与对象存储抽象
- 通知消息落库与 Redis 异步入队
- Docker Compose 本地开发基线（postgres / redis / backend / frontend / nginx）

## 环境观察

- Node.js 与 npm 可用，可用于前端开发与验证。
- 系统 Python 未直接暴露 `pip`，本仓库使用 `backend/.venv` 完成后端运行与测试。
- 代理 / 直连 / Compose 三条开发链路都已在代码层明确收口，但 Docker 运行级验证仍需在具备 Docker 的环境执行。
