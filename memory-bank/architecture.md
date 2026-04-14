# Project Filum 架构基线

**版本**: v1.2.0  
**状态**: Phase 2 / Collaboration & Stats 已实现并完成用户基础验测  
**适用范围**: 当前仓库代码、数据库基线、本地开发方式、后续 Phase 3~4 演进

## 1. 架构目标

Project Filum 面向 50-100 人规模企业，采用**模块化单体**实现统一的人事、任务、消息与 AI 协同能力。当前阶段的核心目标如下：

- 前后端职责清晰，便于快速交付与长期维护。
- 业务规则集中在服务层，避免路由层和页面层散落逻辑。
- 任务、附件、通知和档案之间保持强关联，满足“工作留痕”。
- Redis 从基础阶段即作为异步通知总线的 broker。
- 附件统一通过对象存储抽象管理，关系库存储元数据与绑定关系。
- AI 作为意图路由器接入业务工具，而不是独立聊天系统。

## 2. 系统边界与模块划分

| 模块               | 责任                                           | 当前状态                                                         |
| ------------------ | ---------------------------------------------- | ---------------------------------------------------------------- |
| IAM                | 用户鉴权、JWT access/refresh、用户状态校验     | Phase 1 已实现；字段级权限与代理授权待后续                       |
| Organization       | 部门树、负责人、组织范围查询                   | Phase 1 已实现；多岗位 / 虚线汇报关系待后续                      |
| HR Profiles        | 员工档案、动态字段、基础生命周期信息           | Phase 1 已实现一人一档与动态字段；全生命周期与敏感字段权限待后续 |
| Workflow           | 任务创建、指派、依赖关系、截止时间维护         | Phase 2 已实现状态机、依赖建模与统计；模板 / 审批流 / 多视图待后续 |
| Task Collaboration | `task_comments`、任务内沟通留痕、日志          | Phase 2 已实现                                                   |
| Notification Bus   | 统一消息模型、异步入队、渠道投递记录           | Phase 2 已实现消息落库、ARQ 入队与提醒扫描；真实渠道适配器待后续 |
| File Storage       | 附件元数据、对象存储适配、业务绑定             | Phase 1 已实现，Phase 2 已扩展到评论附件                         |
| Knowledge Base     | Markdown 文档、向量切块、RAG 检索              | Phase 3 预留                                                     |
| AI Router          | `@系统` / `/` 指令入口、Tool Calling、权限注入 | Phase 3~4 预留                                                   |
| Platform Tools     | 可插拔工具页与后端工具路由                     | Phase 4 预留                                                     |

## 3. 运行时拓扑

```text
[ Browser ]
    |
    v
[ Nginx / Vite Dev Server ]
    |
    v
[ FastAPI ]
    |-- app.api
    |-- app.services
    |-- app.integrations
    |
    +--> PostgreSQL
    +--> Redis / ARQ Queue
    +--> Object Storage Adapter (local now, S3-compatible later)

[ ARQ Worker ]
    |-- app.workers.arq_worker
    |-- app.workers.jobs
    |
    +--> PostgreSQL
    +--> Redis / ARQ Queue
```

### 3.1 当前本地开发路径

当前仓库支持两条本地开发路径：

1. **Compose 路径（推荐）**
   - `postgres`
   - `redis`
   - `backend`
   - `worker`
   - `frontend`
   - `nginx`
   - `backend` 与 `worker` 容器启动时都会自动执行 `alembic upgrade head`

2. **本地直启路径**
   - `backend/.env.example` 默认指向 `localhost`
   - 可通过 `backend/scripts/start-worker.sh` 直接启动 ARQ worker
   - `frontend` 开发模式默认请求同主机 `:8000/api/v1`
   - 如需要，也可以通过 `VITE_DEV_API_PROXY_TARGET` 使用 Vite 代理

### 3.2 统一入口

- Compose 统一入口：`http://127.0.0.1:8080`
- Backend 本地默认端口：`8000`
- Frontend 本地默认端口：`5173`

## 4. 代码组织基线

```text
frontend/
  src/
    api/
    components/
    router/
    stores/
    types/
    utils/
    views/
  tests/

backend/
  app/
    api/
    core/
    integrations/
    models/
    repositories/
    schemas/
    services/
    workers/
  scripts/
  alembic/
  tests/

infra/
  docker/
  nginx/

memory-bank/
  architecture.md
  design-document.md
  implementation-plan.md
  progress.md
```

## 5. 关键文件与目录职责

### 5.1 memory-bank

| 路径                                 | 作用                                                      |
| ------------------------------------ | --------------------------------------------------------- |
| `memory-bank/architecture.md`        | 当前架构、数据库 schema、关键文件职责与阶段状态的权威文档 |
| `memory-bank/design-document.md`     | 面向产品与方案层的设计文档标准入口                        |
| `memory-bank/implementation-plan.md` | 分阶段实施计划、顺序约束与测试出口                        |
| `memory-bank/progress.md`            | 里程碑进度、验证结果与用户验测后的补记                    |

### 5.2 backend 入口与核心层

| 路径                                | 作用                                                 |
| ----------------------------------- | ---------------------------------------------------- |
| `backend/app/main.py`               | FastAPI 应用入口，注册路由、异常处理和开发态 CORS    |
| `backend/app/api/router.py`         | 聚合所有 API 路由                                    |
| `backend/app/api/dependencies.py`   | 依赖注入入口：数据库、认证、对象存储、通知、当前用户 |
| `backend/app/api/error_handlers.py` | 统一把业务异常/超时异常映射为 HTTP 响应              |
| `backend/app/core/config.py`        | 应用配置模型与 `get_settings()`                      |
| `backend/app/core/database.py`      | async engine、session factory 与 DB session 依赖     |
| `backend/app/core/security.py`      | 密码哈希、JWT access/refresh 编解码                  |
| `backend/app/core/enums.py`         | 后端统一枚举定义                                     |
| `backend/app/core/db_types.py`      | 跨 PostgreSQL/SQLite 的枚举与 JSON 类型构建器        |
| `backend/app/core/exceptions.py`    | 业务异常定义                                         |

### 5.3 backend 模型与迁移

| 路径                                                        | 作用                                 |
| ----------------------------------------------------------- | ------------------------------------ |
| `backend/app/models/base.py`                                | SQLAlchemy Declarative Base          |
| `backend/app/models/mixins.py`                              | UUID、创建时间、更新时间等通用 mixin |
| `backend/app/models/user.py`                                | 用户模型                             |
| `backend/app/models/auth.py`                                | refresh token 持久化模型             |
| `backend/app/models/department.py`                          | 部门树模型                           |
| `backend/app/models/profile.py`                             | 员工档案模型                         |
| `backend/app/models/attachment.py`                          | 附件元数据与附件绑定模型             |
| `backend/app/models/task.py`                                | 任务、任务依赖、任务日志与任务评论模型 |
| `backend/app/models/notification.py`                        | 通知消息与渠道投递模型               |
| `backend/alembic/versions/20260413_01_phase1_foundation.py` | Phase 1 首个业务迁移                 |
| `backend/alembic/versions/20260414_01_phase2_collaboration.py` | Phase 2 协同与留痕迁移            |

### 5.4 backend 服务与集成

| 路径                                              | 作用                                               |
| ------------------------------------------------- | -------------------------------------------------- |
| `backend/app/services/auth_service.py`            | 管理员初始化、登录、refresh、访问令牌解析          |
| `backend/app/services/user_service.py`            | 用户管理服务                                       |
| `backend/app/services/department_service.py`      | 部门 CRUD、组织树构建                              |
| `backend/app/services/profile_service.py`         | 员工档案 CRUD                                      |
| `backend/app/services/task_service.py`            | 任务创建、状态流转、评论、活动流、统计与逾期查询   |
| `backend/app/services/attachment_service.py`      | 附件上传、查询、删除与业务绑定                     |
| `backend/app/services/notification_service.py`    | 通知消息落库、投递记录创建、ARQ 入队               |
| `backend/app/services/object_storage_service.py`  | 存储适配器统一入口                                 |
| `backend/app/services/access_control.py`          | 活跃账号、管理权限、组织范围、可指派范围校验       |
| `backend/app/integrations/storage/local.py`       | 本地文件系统对象存储适配器                         |
| `backend/app/integrations/notifications/queue.py` | ARQ 队列发布器，负责把消息投递任务入 Redis         |
| `backend/app/workers/jobs.py`                     | 通知消费与逾期提醒扫描的可测试业务入口             |
| `backend/app/workers/arq_worker.py`               | ARQ worker 运行时入口与 cron 配置                  |
| `backend/scripts/start-dev.sh`                    | Compose / 容器开发环境的启动脚本，先迁移再启动 API |
| `backend/scripts/start-worker.sh`                 | 本地或容器内 worker 启动脚本，先迁移再启动 ARQ     |

### 5.5 backend API schema 与路由

| 路径                                    | 作用                                      |
| --------------------------------------- | ----------------------------------------- |
| `backend/app/api/routes/auth.py`        | 管理员初始化、登录、refresh、当前用户接口 |
| `backend/app/api/routes/users.py`       | 用户查询、创建、更新接口                  |
| `backend/app/api/routes/departments.py` | 部门列表、树、创建、更新接口              |
| `backend/app/api/routes/profiles.py`    | 档案列表、详情、创建、更新接口            |
| `backend/app/api/routes/tasks.py`       | 任务列表、详情、创建、更新、状态流转、评论、活动流与统计接口 |
| `backend/app/api/routes/attachments.py` | 附件上传、查询、删除接口                  |
| `backend/app/schemas/auth.py`           | 认证请求/响应 schema                      |
| `backend/app/schemas/users.py`          | 用户协议模型                              |
| `backend/app/schemas/departments.py`    | 部门协议模型                              |
| `backend/app/schemas/profiles.py`       | 档案协议模型                              |
| `backend/app/schemas/tasks.py`          | 任务、任务评论、活动流与统计协议模型      |
| `backend/app/schemas/attachments.py`    | 附件协议模型                              |
| `backend/app/schemas/messages.py`       | 通知消息 schema                           |
| `backend/app/schemas/storage.py`        | 对象存储描述模型                          |

### 5.6 frontend

| 路径                                     | 作用                                                        |
| ---------------------------------------- | ----------------------------------------------------------- |
| `frontend/src/main.ts`                   | Vue 应用入口，初始化 Pinia、路由、Element Plus 与未授权回调 |
| `frontend/src/router/index.ts`           | 路由声明、登录守卫、角色守卫                                |
| `frontend/src/router/meta.d.ts`          | 路由元信息类型声明                                          |
| `frontend/src/api/http.ts`               | Axios 实例、token 注入、自动 refresh、开发态 API 地址解析   |
| `frontend/src/api/tasks.ts`              | 任务、状态流转、评论、活动流与统计 API Client               |
| `frontend/src/api/session.ts`            | token 持久化与未授权通知                                    |
| `frontend/src/stores/auth.ts`            | 登录态、用户信息、会话恢复                                  |
| `frontend/src/stores/app.ts`             | 应用标题与阶段状态                                          |
| `frontend/src/components/AppShell.vue`   | 后台整体壳与主导航                                          |
| `frontend/src/views/LoginView.vue`       | 登录与管理员初始化页面                                      |
| `frontend/src/views/HomeView.vue`        | Phase 1 仪表盘                                              |
| `frontend/src/views/DepartmentsView.vue` | 部门管理页                                                  |
| `frontend/src/views/ProfilesView.vue`    | 档案管理页                                                  |
| `frontend/src/views/TasksView.vue`       | 协同任务中心：任务列表、详情、状态流转、评论、时间线、统计   |
| `frontend/src/types/api.ts`              | 前端共享 API 类型                                           |
| `frontend/src/utils/errors.ts`           | 前端统一错误文案提取                                        |
| `frontend/src/utils/formatters.ts`       | 时间格式化工具                                              |
| `frontend/tests/TasksView.spec.ts`       | 任务协同页渲染与交互回归测试                                |

### 5.7 infra

| 路径                              | 作用                                                             |
| --------------------------------- | ---------------------------------------------------------------- |
| `infra/docker/docker-compose.yml` | 本地开发编排，包含 postgres / redis / backend / worker / frontend / nginx |
| `infra/docker/.env.example`       | Compose 端口与数据库账号模板                                     |
| `infra/docker/README.md`          | Compose 启动说明与本地直启说明                                   |
| `infra/nginx/default.conf`        | 统一入口代理：`/api/` 到 backend，其余流量到 frontend            |

## 6. 核心流程

### 6.1 JWT 会话链路

1. 首次进入系统时通过 `/api/v1/auth/bootstrap-admin` 初始化管理员。
2. 登录时由 `AuthService.authenticate()` 校验密码，签发 access / refresh token。
3. refresh token 会落库到 `refresh_tokens`，用于后续轮换与撤销。
4. 前端请求由 `http.ts` 注入 access token；401 时自动尝试 refresh。
5. `get_current_user` 依赖统一解析当前用户并做状态校验。

### 6.2 异步通知总线

1. 业务服务生成统一 `NotificationMessage` schema。
2. `NotificationService.send()` 将消息写入 `notification_messages`。
3. 为每个渠道生成 `notification_deliveries` 记录。
4. `RedisNotificationQueuePublisher` 通过 ARQ `enqueue_job()` 将消息元数据推入 Redis。
5. `app.workers.arq_worker` 消费 `process_notification_message` 任务并回写 delivery / message 状态。
6. 逾期任务扫描通过 cron 任务定时调用 `enqueue_overdue_task_reminders()`。
7. 当前真实 Email / WebPush / WebSocket 渠道适配器仍未接通，worker 主要负责异步消费与状态回写。

### 6.3 任务协同与留痕

1. 创建任务时，`TaskService` 会自动写入 `created` / `assigned` 两类 `task_logs`。
2. 状态流转统一经过服务层校验，只允许 `Todo -> Doing -> Review -> Done`。
3. 评论通过 `multipart/form-data` 创建，评论附件绑定到 `attachment_links(target_type = task_comment)`。
4. 任务活动流由 `task_comments` 与 `task_logs` 聚合按时间排序返回。
5. 统计接口直接基于 `tasks`、`task_logs` 与部门信息做查询型聚合，不额外维护汇总表。

### 6.4 附件上传与绑定

1. 前端上传文件到 `/api/v1/attachments`。
2. `AttachmentService` 通过 `ObjectStorageService` 写入对象存储。
3. 存储成功后写入 `attachments` 元数据。
4. 通过 `attachment_links` 将附件绑定到任务、档案等业务对象。
5. 与任务协同相关的评论附件已绑定到 `task_comments`；任务级附件仍保留用于基础资料。

### 6.5 前端与后端联调链路

1. Compose 模式下，浏览器访问 `nginx`，再转发到 backend / frontend。
2. 前端开发模式下，优先使用 `VITE_API_BASE_URL`；未配置时默认解析到同主机 `:8000/api/v1`。
3. 如启用 Vite 代理，可通过 `VITE_DEV_API_PROXY_TARGET` 指向 backend。
4. 开发态后端开启 CORS，防止本地直连时被浏览器拦截。

### 6.6 AI Router（预留）

1. 前端拦截 `@系统` 或 `/` 指令。
2. 后端构造工具列表，工具 schema 由 Pydantic v2 模型生成。
3. LLM 决策调用工具。
4. 后端执行工具并返回结构化 JSON。
5. LLM 组织最终自然语言回复。

## 7. 阶段映射

| 阶段    | 已落地内容                                                   |
| ------- | ------------------------------------------------------------ |
| Phase A | 文档基线、前后端脚手架、基础编排                             |
| Phase 1 | 用户、部门、档案、附件、任务、通知总线、JWT 会话、前端后台壳 |
| Phase 2 | 严格状态机、`task_comments`、`task_logs`、ARQ 超时提醒、任务统计与协同页 |
| Phase 3 | 知识库、嵌入、RAG                                            |
| Phase 4 | AI Router 深化、工具注册表、PWA / Web Push                   |

## 8. 数据库设计原则

- 主键统一使用 `uuid`。
- 时间统一使用 `timestamptz`。
- 动态业务字段使用 `jsonb`。
- 附件采用**元数据表 + 绑定表**。
- 通知采用**消息表 + 渠道投递表**。
- 泛型绑定（如 `attachment_links.target_id`）由服务层保证完整性。
- 当前代码已实现到 `task_logs` / `task_comments` / `notification_deliveries`；知识库相关表仍属于后续阶段预留。

## 9. 枚举基线

| 枚举                           | 取值                                                                                                   | 状态                             |
| ------------------------------ | ------------------------------------------------------------------------------------------------------ | -------------------------------- |
| `user_role`                    | `admin`, `hr`, `employee`                                                                              | 已实现                           |
| `user_status`                  | `active`, `inactive`, `suspended`, `offboarded`                                                        | 已实现                           |
| `task_status`                  | `todo`, `doing`, `review`, `done`                                                                      | 已实现（服务层严格状态机已落地） |
| `task_priority`                | `low`, `medium`, `high`, `urgent`                                                                      | 已实现                           |
| `task_source_type`             | `manual`, `template`, `event`, `ai`                                                                    | 已实现                           |
| `attachment_visibility`        | `private`, `internal`, `public`                                                                        | 已实现                           |
| `attachment_status`            | `uploaded`, `deleted`, `quarantined`                                                                   | 已实现                           |
| `attachment_target_type`       | `task_comment`, `task`, `profile`, `document`                                                          | 已实现                           |
| `notification_channel`         | `email`, `web_push`, `websocket`                                                                       | 已实现                           |
| `notification_message_status`  | `queued`, `processing`, `completed`, `failed`                                                          | 已实现                           |
| `notification_delivery_status` | `pending`, `sent`, `failed`, `retrying`                                                                | 已实现                           |
| `task_action_type`             | `created`, `assigned`, `status_changed`, `commented`, `attachment_added`, `due_date_changed`, `closed` | 已实现                           |
| `comment_format`               | `plain_text`, `markdown`                                                                               | 已实现                           |
| `document_category`            | `policy`, `sop`, `announcement`, `faq`, `other`                                                        | 预留                             |
| `document_status`              | `draft`, `published`, `archived`                                                                       | 预留                             |

## 10. 全量数据库 Schema

### 10.1 `users`

**实现状态**: Phase 1 已实现

| 字段            | 类型           | 约束                       | 说明         |
| --------------- | -------------- | -------------------------- | ------------ |
| `id`            | `uuid`         | PK                         | 用户主键     |
| `email`         | `varchar(255)` | UNIQUE, NOT NULL           | 登录账号     |
| `password_hash` | `varchar(255)` | NOT NULL                   | 密码哈希     |
| `role`          | `user_role`    | NOT NULL                   | RBAC 角色    |
| `status`        | `user_status`  | NOT NULL, DEFAULT `active` | 用户状态     |
| `last_login_at` | `timestamptz`  | NULL                       | 最近登录时间 |
| `created_at`    | `timestamptz`  | NOT NULL                   | 创建时间     |
| `updated_at`    | `timestamptz`  | NOT NULL                   | 更新时间     |

**索引**

- `uq_users_email`
- `idx_users_role_status (role, status)`

### 10.2 `refresh_tokens`

**实现状态**: Phase 1 已实现

| 字段         | 类型          | 约束                       | 说明      |
| ------------ | ------------- | -------------------------- | --------- |
| `id`         | `uuid`        | PK                         | 记录主键  |
| `user_id`    | `uuid`        | FK -> `users.id`, NOT NULL | 所属用户  |
| `token_id`   | `varchar(64)` | UNIQUE, NOT NULL           | JWT `jti` |
| `expires_at` | `timestamptz` | NOT NULL                   | 过期时间  |
| `revoked_at` | `timestamptz` | NULL                       | 撤销时间  |
| `created_at` | `timestamptz` | NOT NULL                   | 创建时间  |

**索引**

- `idx_refresh_tokens_user_id (user_id)`

### 10.3 `departments`

**实现状态**: Phase 1 已实现

| 字段         | 类型           | 约束                         | 说明       |
| ------------ | -------------- | ---------------------------- | ---------- |
| `id`         | `uuid`         | PK                           | 部门主键   |
| `name`       | `varchar(120)` | NOT NULL                     | 部门名称   |
| `code`       | `varchar(64)`  | UNIQUE, NOT NULL             | 稳定标识   |
| `parent_id`  | `uuid`         | FK -> `departments.id`, NULL | 上级部门   |
| `manager_id` | `uuid`         | FK -> `users.id`, NULL       | 部门负责人 |
| `sort_order` | `int4`         | NOT NULL, DEFAULT `0`        | 排序       |
| `is_active`  | `bool`         | NOT NULL, DEFAULT `true`     | 是否启用   |
| `created_at` | `timestamptz`  | NOT NULL                     | 创建时间   |
| `updated_at` | `timestamptz`  | NOT NULL                     | 更新时间   |

**约束与索引**

- `uq_departments_code`
- `uq_departments_parent_name (parent_id, name)`
- `idx_departments_parent_id (parent_id)`

### 10.4 `profiles`

**实现状态**: Phase 1 已实现

| 字段            | 类型           | 约束                             | 说明           |
| --------------- | -------------- | -------------------------------- | -------------- |
| `user_id`       | `uuid`         | PK, FK -> `users.id`             | 与用户一一对应 |
| `employee_no`   | `varchar(64)`  | UNIQUE, NOT NULL                 | 员工编号       |
| `real_name`     | `varchar(120)` | NOT NULL                         | 真实姓名       |
| `department_id` | `uuid`         | FK -> `departments.id`, NOT NULL | 所属部门       |
| `job_title`     | `varchar(120)` | NULL                             | 岗位           |
| `phone`         | `varchar(32)`  | NULL                             | 电话           |
| `hire_date`     | `date`         | NULL                             | 入职日期       |
| `custom_fields` | `jsonb`        | NOT NULL, DEFAULT `'{}'::jsonb`  | 动态档案字段   |
| `created_at`    | `timestamptz`  | NOT NULL                         | 创建时间       |
| `updated_at`    | `timestamptz`  | NOT NULL                         | 更新时间       |

**索引**

- `uq_profiles_employee_no`
- `idx_profiles_department_id (department_id)`
- `idx_profiles_custom_fields_gin USING GIN (custom_fields)`

### 10.5 `attachments`

**实现状态**: Phase 1 已实现

| 字段                | 类型                    | 约束                            | 说明                         |
| ------------------- | ----------------------- | ------------------------------- | ---------------------------- |
| `id`                | `uuid`                  | PK                              | 附件主键                     |
| `storage_provider`  | `varchar(32)`           | NOT NULL                        | 存储提供者，如 `local`、`s3` |
| `bucket`            | `varchar(128)`          | NOT NULL                        | 逻辑 bucket                  |
| `object_key`        | `varchar(512)`          | NOT NULL                        | 对象存储 key                 |
| `original_filename` | `varchar(255)`          | NOT NULL                        | 原始文件名                   |
| `mime_type`         | `varchar(127)`          | NOT NULL                        | MIME 类型                    |
| `size_bytes`        | `bigint`                | NOT NULL                        | 文件大小                     |
| `checksum_sha256`   | `char(64)`              | NOT NULL                        | 完整性校验                   |
| `uploader_id`       | `uuid`                  | FK -> `users.id`, NOT NULL      | 上传者                       |
| `visibility`        | `attachment_visibility` | NOT NULL, DEFAULT `private`     | 可见性                       |
| `status`            | `attachment_status`     | NOT NULL, DEFAULT `uploaded`    | 状态                         |
| `metadata`          | `jsonb`                 | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展元数据                   |
| `created_at`        | `timestamptz`           | NOT NULL                        | 上传时间                     |
| `deleted_at`        | `timestamptz`           | NULL                            | 软删除时间                   |

**约束与索引**

- `uq_attachments_storage_object (storage_provider, bucket, object_key)`
- `idx_attachments_uploader_id (uploader_id)`
- `idx_attachments_status_visibility (status, visibility)`

### 10.6 `attachment_links`

**实现状态**: Phase 1 已实现

| 字段            | 类型                     | 约束                             | 说明         |
| --------------- | ------------------------ | -------------------------------- | ------------ |
| `id`            | `uuid`                   | PK                               | 绑定记录主键 |
| `attachment_id` | `uuid`                   | FK -> `attachments.id`, NOT NULL | 附件         |
| `target_type`   | `attachment_target_type` | NOT NULL                         | 目标对象类型 |
| `target_id`     | `uuid`                   | NOT NULL                         | 目标对象主键 |
| `relation`      | `varchar(64)`            | NOT NULL, DEFAULT `primary`      | 绑定关系     |
| `created_by`    | `uuid`                   | FK -> `users.id`, NOT NULL       | 创建人       |
| `created_at`    | `timestamptz`            | NOT NULL                         | 创建时间     |

**约束与索引**

- `uq_attachment_links_binding (attachment_id, target_type, target_id, relation)`
- `idx_attachment_links_target (target_type, target_id)`

**设计说明**

- `attachment_links` 采用泛型引用，完整性由服务层校验。
- 与任务协同相关的附件在 Phase 2 中应优先绑定到 `task_comments`。

### 10.7 `tasks`

**实现状态**: Phase 1 已实现

| 字段             | 类型               | 约束                            | 说明       |
| ---------------- | ------------------ | ------------------------------- | ---------- |
| `id`             | `uuid`             | PK                              | 任务主键   |
| `title`          | `varchar(255)`     | NOT NULL                        | 任务标题   |
| `description`    | `text`             | NULL                            | 描述       |
| `creator_id`     | `uuid`             | FK -> `users.id`, NOT NULL      | 创建人     |
| `assignee_id`    | `uuid`             | FK -> `users.id`, NOT NULL      | 执行人     |
| `department_id`  | `uuid`             | FK -> `departments.id`, NULL    | 所属部门   |
| `status`         | `task_status`      | NOT NULL, DEFAULT `todo`        | 状态       |
| `priority`       | `task_priority`    | NOT NULL, DEFAULT `medium`      | 优先级     |
| `due_date`       | `timestamptz`      | NULL                            | 截止时间   |
| `started_at`     | `timestamptz`      | NULL                            | 开始时间   |
| `completed_at`   | `timestamptz`      | NULL                            | 完成时间   |
| `parent_task_id` | `uuid`             | FK -> `tasks.id`, NULL          | 父任务     |
| `source_type`    | `task_source_type` | NOT NULL, DEFAULT `manual`      | 来源       |
| `metadata`       | `jsonb`            | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展元数据 |
| `created_at`     | `timestamptz`      | NOT NULL                        | 创建时间   |
| `updated_at`     | `timestamptz`      | NOT NULL                        | 更新时间   |

**约束与索引**

- `idx_tasks_assignee_status (assignee_id, status)`
- `idx_tasks_department_status (department_id, status)`
- `idx_tasks_due_date (due_date)`

### 10.8 `task_dependencies`

**实现状态**: Phase 1 已实现

| 字段                 | 类型          | 约束                       | 说明     |
| -------------------- | ------------- | -------------------------- | -------- |
| `task_id`            | `uuid`        | FK -> `tasks.id`, NOT NULL | 当前任务 |
| `depends_on_task_id` | `uuid`        | FK -> `tasks.id`, NOT NULL | 前置任务 |
| `dependency_type`    | `varchar(32)` | NOT NULL, DEFAULT `blocks` | 依赖类型 |
| `created_at`         | `timestamptz` | NOT NULL                   | 创建时间 |

**约束与索引**

- 主键：`(task_id, depends_on_task_id)`
- CHECK `task_id <> depends_on_task_id`
- `idx_task_dependencies_depends_on_task_id (depends_on_task_id)`

**设计说明**

- 当前已支持前置依赖关系建模，并在创建任务时校验依赖任务存在。
- 尚未实现“前置任务完成后自动触发后置任务”的自动调度。

### 10.9 `notification_messages`

**实现状态**: Phase 1 已实现

| 字段                | 类型                          | 约束                            | 说明                |
| ------------------- | ----------------------------- | ------------------------------- | ------------------- |
| `id`                | `uuid`                        | PK                              | 消息主键            |
| `source_type`       | `varchar(64)`                 | NOT NULL                        | 业务来源，如 `task` |
| `source_id`         | `uuid`                        | NULL                            | 来源对象 ID         |
| `recipient_user_id` | `uuid`                        | FK -> `users.id`, NULL          | 收件用户            |
| `recipient_email`   | `varchar(255)`                | NULL                            | 直接邮件收件地址    |
| `message_type`      | `varchar(64)`                 | NOT NULL                        | 消息类型            |
| `title`             | `varchar(255)`                | NOT NULL                        | 标题                |
| `body_text`         | `text`                        | NOT NULL                        | 文本体              |
| `body_html`         | `text`                        | NULL                            | HTML 体             |
| `payload`           | `jsonb`                       | NOT NULL, DEFAULT `'{}'::jsonb` | 附加上下文          |
| `status`            | `notification_message_status` | NOT NULL, DEFAULT `queued`      | 消息状态            |
| `scheduled_at`      | `timestamptz`                 | NULL                            | 计划发送时间        |
| `enqueued_at`       | `timestamptz`                 | NULL                            | 入队时间            |
| `completed_at`      | `timestamptz`                 | NULL                            | 完成时间            |
| `created_at`        | `timestamptz`                 | NOT NULL                        | 创建时间            |

**索引**

- `idx_notification_messages_status_scheduled_at (status, scheduled_at)`
- `idx_notification_messages_recipient_user_id (recipient_user_id)`

### 10.10 `notification_deliveries`

**实现状态**: Phase 1 已实现

| 字段                  | 类型                           | 约束                                       | 说明         |
| --------------------- | ------------------------------ | ------------------------------------------ | ------------ |
| `id`                  | `uuid`                         | PK                                         | 投递主键     |
| `message_id`          | `uuid`                         | FK -> `notification_messages.id`, NOT NULL | 所属消息     |
| `channel`             | `notification_channel`         | NOT NULL                                   | 投递渠道     |
| `adapter_name`        | `varchar(64)`                  | NOT NULL                                   | 适配器标识   |
| `status`              | `notification_delivery_status` | NOT NULL, DEFAULT `pending`                | 投递状态     |
| `attempt_count`       | `int4`                         | NOT NULL, DEFAULT `0`                      | 尝试次数     |
| `external_message_id` | `varchar(255)`                 | NULL                                       | 外部平台 ID  |
| `error_message`       | `text`                         | NULL                                       | 失败信息     |
| `attempted_at`        | `timestamptz`                  | NULL                                       | 最近尝试时间 |
| `delivered_at`        | `timestamptz`                  | NULL                                       | 成功送达时间 |
| `created_at`          | `timestamptz`                  | NOT NULL                                   | 创建时间     |

**索引**

- `idx_notification_deliveries_message_id (message_id)`
- `idx_notification_deliveries_status_channel (status, channel)`

### 10.11 `task_logs`

**实现状态**: Phase 2 已实现

| 字段          | 类型               | 约束                            | 说明     |
| ------------- | ------------------ | ------------------------------- | -------- |
| `id`          | `uuid`             | PK                              | 日志主键 |
| `task_id`     | `uuid`             | FK -> `tasks.id`, NOT NULL      | 所属任务 |
| `operator_id` | `uuid`             | FK -> `users.id`, NOT NULL      | 操作人   |
| `action_type` | `task_action_type` | NOT NULL                        | 动作类型 |
| `from_status` | `task_status`      | NULL                            | 原状态   |
| `to_status`   | `task_status`      | NULL                            | 新状态   |
| `detail`      | `jsonb`            | NOT NULL, DEFAULT `'{}'::jsonb` | 详细信息 |
| `created_at`  | `timestamptz`      | NOT NULL                        | 记录时间 |

**索引**

- `idx_task_logs_task_id_created_at (task_id, created_at DESC)`
- `idx_task_logs_operator_id (operator_id)`

**设计说明**

- `task_logs` 只由服务层自动写入，用于记录创建、指派、状态变更、评论、附件与截止时间变更。

### 10.12 `task_comments`

**实现状态**: Phase 2 已实现

| 字段             | 类型             | 约束                         | 说明         |
| ---------------- | ---------------- | ---------------------------- | ------------ |
| `id`             | `uuid`           | PK                           | 评论主键     |
| `task_id`        | `uuid`           | FK -> `tasks.id`, NOT NULL   | 所属任务     |
| `user_id`        | `uuid`           | FK -> `users.id`, NOT NULL   | 评论人       |
| `content`        | `text`           | NOT NULL                     | 评论内容     |
| `content_format` | `comment_format` | NOT NULL, DEFAULT `markdown` | 内容格式     |
| `is_internal`    | `bool`           | NOT NULL, DEFAULT `false`    | 是否内部备注 |
| `created_at`     | `timestamptz`    | NOT NULL                     | 创建时间     |
| `updated_at`     | `timestamptz`    | NOT NULL                     | 更新时间     |

**索引**

- `idx_task_comments_task_id_created_at (task_id, created_at ASC)`
- `idx_task_comments_user_id (user_id)`

**设计说明**

- 评论支持 `plain_text` / `markdown` 两种格式。
- 评论附件通过 `attachment_links(target_type = task_comment)` 关联。

### 10.13 `documents`

**实现状态**: Phase 3 预留，当前未实现

| 字段           | 类型                | 约束                       | 说明          |
| -------------- | ------------------- | -------------------------- | ------------- |
| `id`           | `uuid`              | PK                         | 文档主键      |
| `title`        | `varchar(255)`      | NOT NULL                   | 标题          |
| `slug`         | `varchar(255)`      | UNIQUE, NOT NULL           | 稳定 URL 标识 |
| `category`     | `document_category` | NOT NULL                   | 分类          |
| `status`       | `document_status`   | NOT NULL, DEFAULT `draft`  | 状态          |
| `content_md`   | `text`              | NOT NULL                   | Markdown 内容 |
| `author_id`    | `uuid`              | FK -> `users.id`, NOT NULL | 作者          |
| `version`      | `int4`              | NOT NULL, DEFAULT `1`      | 版本号        |
| `published_at` | `timestamptz`       | NULL                       | 发布时间      |
| `created_at`   | `timestamptz`       | NOT NULL                   | 创建时间      |
| `updated_at`   | `timestamptz`       | NOT NULL                   | 更新时间      |

**索引**

- `uq_documents_slug`
- `idx_documents_category_status (category, status)`

### 10.14 `document_embeddings`

**实现状态**: Phase 3 预留，当前未实现

| 字段              | 类型           | 约束                           | 说明     |
| ----------------- | -------------- | ------------------------------ | -------- |
| `id`              | `uuid`         | PK                             | 向量主键 |
| `document_id`     | `uuid`         | FK -> `documents.id`, NOT NULL | 所属文档 |
| `chunk_index`     | `int4`         | NOT NULL                       | 分块序号 |
| `chunk_text`      | `text`         | NOT NULL                       | 切块内容 |
| `token_count`     | `int4`         | NULL                           | token 数 |
| `embedding_model` | `varchar(128)` | NOT NULL                       | 嵌入模型 |
| `embedding`       | `vector(1536)` | NOT NULL                       | 向量数据 |
| `created_at`      | `timestamptz`  | NOT NULL                       | 创建时间 |

**约束与索引**

- `uq_document_embeddings_chunk (document_id, chunk_index)`
- 向量索引：`ivfflat` 或 `hnsw`

## 11. 关系说明

- `users 1:1 profiles`
- `users 1:N refresh_tokens`
- `departments 1:N profiles`
- `departments 1:N tasks`
- `tasks N:N tasks` 通过 `task_dependencies`
- `attachments N:N 业务对象` 通过 `attachment_links`
- `notification_messages 1:N notification_deliveries`
- `tasks 1:N task_comments`
- `tasks 1:N task_logs`
- `documents 1:N document_embeddings`（Phase 3 预留）

## 12. 当前验证基线

截至 Phase 2 文档收尾，当前仓库至少具备如下验证能力：

- backend：
  - `pytest`（覆盖 models / migrations / services / api / workers）
  - `python -m compileall app`
- frontend：
  - `npm run test:unit -- --run`
  - `npm run type-check`
  - `npm run build`
  - `npm run lint`
- 用户验测：
  - Phase 1 的“初始化管理员”和“登录”已实际点击验证通过
  - Phase 2 的任务协同页已完成用户简单测试，确认“基本没有问题”
- 编排：
  - Compose 文件已包含 `worker` 服务，可做配置级检查
  - 真实 Redis + ARQ worker 进程级 smoke test、以及完整 Compose 运行级验证，仍建议在具备 Docker 的环境中执行

## 13. 维护规则

- 每完成一个里程碑，必须同步更新本文件。
- 新增表时，需要同步记录字段、约束、索引、用途、当前实现阶段。
- 若实现与本基线偏离，必须先修改本文件，再实施代码变更。
- 新增关键入口文件时，应补充到“关键文件与目录职责”部分，保证后续开发者能快速定位代码。
