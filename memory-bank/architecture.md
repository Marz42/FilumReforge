# Project Filum 架构基线

**版本**: v1.0.0  
**状态**: Phase A 基线草案  
**适用范围**: 仓库初始化、架构统一、数据库基线、后续分阶段实现

## 1. 架构目标

Project Filum 面向 50-100 人规模企业，采用**模块化单体**实现统一的人事、任务、消息与 AI 协同能力。系统必须在低运维成本前提下，保证如下目标：

- 前后端职责清晰，便于快速交付与长期维护。
- 业务规则集中在服务层，避免路由层和页面层散落逻辑。
- 任务、评论、日志、通知和附件之间保持强关联，满足“工作留痕”。
- AI 作为意图路由器接入业务工具，而不是独立聊天系统。
- Redis 从基础阶段即作为异步通知总线的 broker。
- 附件统一通过对象存储抽象管理，关系库存储元数据与业务绑定关系。

## 2. 系统边界与模块划分

| 模块 | 责任 | 关键约束 |
| --- | --- | --- |
| IAM | 用户鉴权、角色控制、用户状态管理 | 仅提供认证与授权边界，不承载业务规则 |
| Organization | 部门树、负责人、组织范围查询 | 数据隔离依赖组织树上下文 |
| HR Profiles | 员工档案、动态字段、生命周期事件 | 扩展字段统一使用 `JSONB` |
| Workflow | 任务、状态机、依赖关系、审计日志 | 状态机只允许 `Todo -> Doing -> Review -> Done` |
| Task Collaboration | `task_comments`、附件绑定、工作留痕 | 禁止独立聊天；沟通必须绑定任务上下文 |
| Notification Bus | 统一消息模型、异步投递、渠道适配 | 业务层只能调用 `NotificationService.send(message)` |
| File Storage | 附件元数据、对象存储适配、业务绑定 | 二进制内容不直接写入业务表 |
| Knowledge Base | Markdown 文档、向量切块、RAG 检索 | 使用 PostgreSQL + `pgvector` |
| AI Router | `@系统` / `/` 指令入口、Tool Calling、权限注入 | 使用官方 `openai` SDK 与 Pydantic schema |
| Platform Tools | 工具注册、独立前端视图、后端路由扩展 | 工具能力必须可插拔 |

## 3. 运行时拓扑

```text
[ Browser / PWA ]
        |
        v
[ Nginx ]
   |         \
   |          \-- 静态资源: Vue SPA
   v
[ FastAPI ]
   |-- IAM / Organization / HR / Workflow / AI Router
   |-- NotificationService
   |-- ObjectStorageService
   |
   +--> PostgreSQL 15+
   +--> Redis
   +--> Object Storage Adapter (local/S3 compatible)
```

### 3.1 容器化基线

Phase A 与 Phase 1 的本地开发编排至少包含：

- `postgres`: 主数据库
- `redis`: 缓存与异步 broker
- `backend`: FastAPI 服务
- `frontend`: Vue 3 开发/构建容器
- `nginx`: 反向代理与静态资源分发

## 4. 代码组织基线

```text
frontend/
  src/
    api/
    components/
    router/
    stores/
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

## 5. 核心流程

### 5.1 异步通知总线

1. 业务服务生成统一 `message` 对象。
2. `NotificationService.send(message)` 将消息写入 `notification_messages` 并推入 Redis。
3. Worker 消费消息，按策略展开为一个或多个 `notification_deliveries`。
4. 渠道适配器负责实际发送 Email/Web 推送。
5. 投递结果回写数据库，供审计与重试使用。

### 5.2 附件上传与绑定

1. 前端申请上传或直接上传附件。
2. 后端通过 `ObjectStorageService` 选择具体存储提供者。
3. 存储成功后写入 `attachments` 元数据。
4. 通过 `attachment_links` 将附件绑定到具体业务对象。
5. 与工作协同相关的附件必须绑定到 `task_comments`，从而自然归属于任务上下文。

### 5.3 AI Router

1. 前端拦截 `@系统` 或 `/` 指令。
2. 后端构造工具列表，工具 schema 由 Pydantic v2 模型生成。
3. LLM 决策调用工具。
4. 后端执行工具并返回结构化 JSON。
5. LLM 基于原始结果组织最终自然语言回复。

## 6. 数据库设计原则

- 主键统一使用 `uuid`。
- 时间统一使用 `timestamptz`。
- 动态业务字段使用 `jsonb`，禁止在字符串字段中堆叠 JSON。
- 附件采用**元数据表 + 业务绑定表**，避免直接在业务表中存储对象存储细节。
- 通知采用**消息表 + 渠道投递表**，支持异步、重试与审计。
- 泛型绑定（如 `attachment_links.target_id`）由服务层做完整性校验。

## 7. 枚举基线

| 枚举 | 取值 |
| --- | --- |
| `user_role` | `admin`, `hr`, `employee` |
| `user_status` | `active`, `inactive`, `suspended`, `offboarded` |
| `task_status` | `todo`, `doing`, `review`, `done` |
| `task_priority` | `low`, `medium`, `high`, `urgent` |
| `task_source_type` | `manual`, `template`, `event`, `ai` |
| `task_action_type` | `created`, `assigned`, `status_changed`, `commented`, `attachment_added`, `due_date_changed`, `closed` |
| `comment_format` | `plain_text`, `markdown` |
| `attachment_visibility` | `private`, `internal`, `public` |
| `attachment_status` | `uploaded`, `deleted`, `quarantined` |
| `attachment_target_type` | `task_comment`, `task`, `profile`, `document` |
| `notification_channel` | `email`, `web_push`, `websocket` |
| `notification_message_status` | `queued`, `processing`, `completed`, `failed` |
| `notification_delivery_status` | `pending`, `sent`, `failed`, `retrying` |
| `document_category` | `policy`, `sop`, `announcement`, `faq`, `other` |
| `document_status` | `draft`, `published`, `archived` |

## 8. 全量数据库 Schema

### 8.1 `users`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 用户主键 |
| `email` | `varchar(255)` | UNIQUE, NOT NULL | 登录账号 |
| `password_hash` | `varchar(255)` | NOT NULL | 密码哈希 |
| `role` | `user_role` | NOT NULL | RBAC 角色 |
| `status` | `user_status` | NOT NULL, DEFAULT `active` | 用户状态 |
| `last_login_at` | `timestamptz` | NULL | 最近登录时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_users_email`
- `idx_users_role_status (role, status)`

### 8.2 `departments`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 部门主键 |
| `name` | `varchar(120)` | NOT NULL | 部门名称 |
| `code` | `varchar(64)` | UNIQUE, NOT NULL | 稳定标识 |
| `parent_id` | `uuid` | FK -> `departments.id`, NULL | 上级部门 |
| `manager_id` | `uuid` | FK -> `users.id`, NULL | 部门负责人 |
| `sort_order` | `int4` | NOT NULL, DEFAULT `0` | 排序 |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` | 是否启用 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `uq_departments_code`
- `uq_departments_parent_name (parent_id, name)`
- `idx_departments_parent_id (parent_id)`

### 8.3 `profiles`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `user_id` | `uuid` | PK, FK -> `users.id` | 与用户一一对应 |
| `employee_no` | `varchar(64)` | UNIQUE, NOT NULL | 员工编号 |
| `real_name` | `varchar(120)` | NOT NULL | 真实姓名 |
| `department_id` | `uuid` | FK -> `departments.id`, NOT NULL | 所属部门 |
| `job_title` | `varchar(120)` | NULL | 岗位 |
| `phone` | `varchar(32)` | NULL | 电话 |
| `hire_date` | `date` | NULL | 入职日期 |
| `custom_fields` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 动态档案字段 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_profiles_employee_no`
- `idx_profiles_department_id (department_id)`
- `idx_profiles_custom_fields_gin USING GIN (custom_fields)`

### 8.4 `attachments`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 附件主键 |
| `storage_provider` | `varchar(32)` | NOT NULL | 存储提供者，如 `local`、`s3` |
| `bucket` | `varchar(128)` | NOT NULL | 逻辑 bucket |
| `object_key` | `varchar(512)` | NOT NULL | 对象存储 key |
| `original_filename` | `varchar(255)` | NOT NULL | 原始文件名 |
| `mime_type` | `varchar(127)` | NOT NULL | MIME 类型 |
| `size_bytes` | `bigint` | NOT NULL | 文件大小 |
| `checksum_sha256` | `char(64)` | NOT NULL | 完整性校验 |
| `uploader_id` | `uuid` | FK -> `users.id`, NOT NULL | 上传者 |
| `visibility` | `attachment_visibility` | NOT NULL, DEFAULT `private` | 可见性 |
| `status` | `attachment_status` | NOT NULL, DEFAULT `uploaded` | 状态 |
| `metadata` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展元数据 |
| `created_at` | `timestamptz` | NOT NULL | 上传时间 |
| `deleted_at` | `timestamptz` | NULL | 软删除时间 |

**约束与索引**

- `uq_attachments_storage_object (storage_provider, bucket, object_key)`
- `idx_attachments_uploader_id (uploader_id)`
- `idx_attachments_status_visibility (status, visibility)`

### 8.5 `attachment_links`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 绑定记录主键 |
| `attachment_id` | `uuid` | FK -> `attachments.id`, NOT NULL | 附件 |
| `target_type` | `attachment_target_type` | NOT NULL | 目标对象类型 |
| `target_id` | `uuid` | NOT NULL | 目标对象主键 |
| `relation` | `varchar(64)` | NOT NULL, DEFAULT `primary` | 绑定关系 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- `uq_attachment_links_binding (attachment_id, target_type, target_id, relation)`
- `idx_attachment_links_target (target_type, target_id)`

**设计说明**

- `attachment_links` 采用泛型引用，完整性由服务层校验。
- 与任务协同相关的附件必须绑定到 `task_comments`，即 `target_type = 'task_comment'`。

### 8.6 `tasks`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 任务主键 |
| `title` | `varchar(255)` | NOT NULL | 任务标题 |
| `description` | `text` | NULL | 描述 |
| `creator_id` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `assignee_id` | `uuid` | FK -> `users.id`, NOT NULL | 执行人 |
| `department_id` | `uuid` | FK -> `departments.id`, NULL | 所属部门 |
| `status` | `task_status` | NOT NULL, DEFAULT `todo` | 状态 |
| `priority` | `task_priority` | NOT NULL, DEFAULT `medium` | 优先级 |
| `due_date` | `timestamptz` | NULL | 截止时间 |
| `started_at` | `timestamptz` | NULL | 开始时间 |
| `completed_at` | `timestamptz` | NULL | 完成时间 |
| `parent_task_id` | `uuid` | FK -> `tasks.id`, NULL | 父任务 |
| `source_type` | `task_source_type` | NOT NULL, DEFAULT `manual` | 来源 |
| `metadata` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展元数据 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `idx_tasks_assignee_status (assignee_id, status)`
- `idx_tasks_department_status (department_id, status)`
- `idx_tasks_due_date (due_date)`

### 8.7 `task_dependencies`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `task_id` | `uuid` | FK -> `tasks.id`, NOT NULL | 当前任务 |
| `depends_on_task_id` | `uuid` | FK -> `tasks.id`, NOT NULL | 前置任务 |
| `dependency_type` | `varchar(32)` | NOT NULL, DEFAULT `blocks` | 依赖类型 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- 主键：`(task_id, depends_on_task_id)`
- CHECK `task_id <> depends_on_task_id`

### 8.8 `task_logs`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 日志主键 |
| `task_id` | `uuid` | FK -> `tasks.id`, NOT NULL | 所属任务 |
| `operator_id` | `uuid` | FK -> `users.id`, NOT NULL | 操作人 |
| `action_type` | `task_action_type` | NOT NULL | 动作类型 |
| `from_status` | `task_status` | NULL | 原状态 |
| `to_status` | `task_status` | NULL | 新状态 |
| `detail` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 详细信息 |
| `created_at` | `timestamptz` | NOT NULL | 记录时间 |

**索引**

- `idx_task_logs_task_id_created_at (task_id, created_at DESC)`
- `idx_task_logs_operator_id (operator_id)`

### 8.9 `task_comments`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 评论主键 |
| `task_id` | `uuid` | FK -> `tasks.id`, NOT NULL | 所属任务 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 评论人 |
| `content` | `text` | NOT NULL | 评论内容 |
| `content_format` | `comment_format` | NOT NULL, DEFAULT `markdown` | 内容格式 |
| `is_internal` | `bool` | NOT NULL, DEFAULT `false` | 是否内部备注 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_task_comments_task_id_created_at (task_id, created_at ASC)`
- `idx_task_comments_user_id (user_id)`

### 8.10 `notification_messages`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 消息主键 |
| `source_type` | `varchar(64)` | NOT NULL | 业务来源，如 `task` |
| `source_id` | `uuid` | NULL | 来源对象 ID |
| `recipient_user_id` | `uuid` | FK -> `users.id`, NULL | 收件用户 |
| `recipient_email` | `varchar(255)` | NULL | 直接邮件收件地址 |
| `message_type` | `varchar(64)` | NOT NULL | 消息类型 |
| `title` | `varchar(255)` | NOT NULL | 标题 |
| `body_text` | `text` | NOT NULL | 文本体 |
| `body_html` | `text` | NULL | HTML 体 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 附加上下文 |
| `status` | `notification_message_status` | NOT NULL, DEFAULT `queued` | 消息状态 |
| `scheduled_at` | `timestamptz` | NULL | 计划发送时间 |
| `enqueued_at` | `timestamptz` | NULL | 入队时间 |
| `completed_at` | `timestamptz` | NULL | 完成时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_notification_messages_status_scheduled_at (status, scheduled_at)`
- `idx_notification_messages_recipient_user_id (recipient_user_id)`

### 8.11 `notification_deliveries`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 投递主键 |
| `message_id` | `uuid` | FK -> `notification_messages.id`, NOT NULL | 所属消息 |
| `channel` | `notification_channel` | NOT NULL | 投递渠道 |
| `adapter_name` | `varchar(64)` | NOT NULL | 适配器标识 |
| `status` | `notification_delivery_status` | NOT NULL, DEFAULT `pending` | 投递状态 |
| `attempt_count` | `int4` | NOT NULL, DEFAULT `0` | 尝试次数 |
| `external_message_id` | `varchar(255)` | NULL | 外部平台 ID |
| `error_message` | `text` | NULL | 失败信息 |
| `attempted_at` | `timestamptz` | NULL | 最近尝试时间 |
| `delivered_at` | `timestamptz` | NULL | 成功送达时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_notification_deliveries_message_id (message_id)`
- `idx_notification_deliveries_status_channel (status, channel)`

### 8.12 `documents`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 文档主键 |
| `title` | `varchar(255)` | NOT NULL | 标题 |
| `slug` | `varchar(255)` | UNIQUE, NOT NULL | 稳定 URL 标识 |
| `category` | `document_category` | NOT NULL | 分类 |
| `status` | `document_status` | NOT NULL, DEFAULT `draft` | 状态 |
| `content_md` | `text` | NOT NULL | Markdown 内容 |
| `author_id` | `uuid` | FK -> `users.id`, NOT NULL | 作者 |
| `version` | `int4` | NOT NULL, DEFAULT `1` | 版本号 |
| `published_at` | `timestamptz` | NULL | 发布时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_documents_slug`
- `idx_documents_category_status (category, status)`

### 8.13 `document_embeddings`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 向量主键 |
| `document_id` | `uuid` | FK -> `documents.id`, NOT NULL | 所属文档 |
| `chunk_index` | `int4` | NOT NULL | 分块序号 |
| `chunk_text` | `text` | NOT NULL | 切块内容 |
| `token_count` | `int4` | NULL | token 数 |
| `embedding_model` | `varchar(128)` | NOT NULL | 嵌入模型 |
| `embedding` | `vector(1536)` | NOT NULL | 向量数据 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- `uq_document_embeddings_chunk (document_id, chunk_index)`
- 向量索引：`ivfflat` 或 `hnsw`，按 PostgreSQL/pgvector 版本选择

## 9. 关系说明

- `users 1:1 profiles`
- `departments 1:N profiles`
- `departments 1:N tasks`
- `tasks 1:N task_comments`
- `tasks 1:N task_logs`
- `tasks N:N tasks` 通过 `task_dependencies`
- `attachments N:N 业务对象` 通过 `attachment_links`
- `notification_messages 1:N notification_deliveries`
- `documents 1:N document_embeddings`

## 10. 测试基线

Phase A 之后，仓库应具备如下验证能力：

- 前端：至少可执行单元测试或基础示例测试，以及 `build` 冒烟。
- 后端：至少可执行 `pytest` 与基础健康检查测试。
- 编排：至少可执行配置级检查；若本地 Docker 可用，则执行 `docker compose config` 与服务启动冒烟。
- 文档：关键文件存在性与命名一致性可脚本化验证。

## 11. 维护规则

- 每完成一个里程碑，必须同步更新本文件。
- 新增表时，需要同步记录字段、约束、索引、用途与所在阶段。
- 若实现与本基线偏离，必须先修改本文件，再实施代码变更。
