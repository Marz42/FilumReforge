# Project Filum 数据契约

> 🔥 HOT — 数据库表结构、枚举、实体关系与 API 契约索引。
>
> **维护规则**: schema / 枚举变更时**必须**同步更新本文件；宏观流程与模块职责见 [`architecture.md`](./architecture.md)。

**版本**: 与 [`architecture.md`](./architecture.md) 同步（Paradigma Phase 2 自 architecture §8–§13 迁出）  
**事实来源**: `backend/app/models/`、`backend/alembic/versions/`、OpenAPI `/docs`

---

## API 契约索引

- **OpenAPI**: 运行后端后访问 `/docs` 或 `/openapi.json`（权威请求/响应形状）
- **Pydantic Schemas**: `backend/app/schemas/`
- **通用错误**: `backend/app/api/error_handlers.py` 返回 `request_id` + 业务错误码
- **认证**: JWT access token + HttpOnly refresh cookie（`backend/app/api/routes/auth.py`）
- **附件下载**: `GET /api/v1/attachments/{id}/content`（鉴权后流式返回）
- **图引擎**: `backend/app/api/routes/workflow_graph_engine.py`（实例/节点完成/打回/接管等）
- **视频工作流 v1**: `backend/app/schemas/workflow_video.py`、`backend/app/api/routes/workflow_video.py`

> 图引擎七表（`workflow_graph_*`）及视频 v1 增量表（如 `workflow_run_events`）的字段以 **Alembic 迁移与 ORM 模型**为准；本文件 §10 侧重 legacy + 核心业务表，图引擎表见 `backend/app/models/workflow_graph.py`。

---

## 8. 数据库设计原则

- 主键统一使用 `uuid`
- 时间统一使用 `timestamptz`
- 动态业务字段使用 `jsonb`
- 附件统一采用 `attachments + attachment_links`
- 通知统一采用 `notification_messages + notification_deliveries`
- 任务相关沟通固定绑定 `task_comments`
- 高敏档案字段继续允许存放在 `profiles.custom_fields`，但必须由字段定义与权限表驱动展示
- `Leader` 优先通过组织关系与授权推导，不强制引入新的全局角色枚举
- 文档中所有 schema 必须明确标出**当前已实现**或**未来规划阶段**

## 9. 枚举基线

| 枚举 | 取值 | 状态 |
| --- | --- | --- |
| `user_role` | `admin`, `hr`, `employee` | 已实现 |
| `user_status` | `active`, `inactive`, `suspended`, `offboarded` | 已实现 |
| `task_status` | `todo`, `doing`, `review`, `done` | 已实现 |
| `task_priority` | `low`, `medium`, `high`, `urgent` | 已实现 |
| `task_source_type` | `manual`, `template`, `event`, `ai` | 已实现（当前主要使用 `manual`） |
| `task_action_type` | `created`, `assigned`, `status_changed`, `commented`, `attachment_added`, `due_date_changed`, `closed` | 已实现 |
| `comment_format` | `plain_text`, `markdown` | 已实现 |
| `attachment_visibility` | `private`, `internal`, `public` | 已实现 |
| `attachment_status` | `uploaded`, `deleted`, `quarantined` | 已实现 |
| `attachment_target_type` | `task_comment`, `task`, `profile`, `document`, `notification_message`, `report` | 已实现（含汇报附件绑定） |
| `notification_channel` | `email`, `web_push`, `websocket` | 已实现，adapter 第一版已落地 |
| `notification_message_status` | `queued`, `processing`, `completed`, `failed` | 已实现 |
| `notification_delivery_status` | `pending`, `sent`, `failed`, `retrying` | 已实现 |
| `position_assignment_type` | `primary`, `part_time`, `acting` | 已实现 |
| `reporting_line_type` | `solid`, `dotted` | 已实现 |
| `employment_event_type` | `onboard`, `transfer`, `promotion`, `reward`, `discipline`, `offboard`, `rehire` | 已实现 |
| `delegation_scope_type` | `approval`, `task`, `data_access`, `all` | 已实现 |
| `delegation_status` | `pending`, `active`, `expired`, `revoked` | 已实现 |
| `report_direction` | `upward`, `downward` | Step 4 已实现 |
| `report_status` | `in_progress`, `completed`, `returned`, `archived` | Step 4 已实现 |
| `report_route_status` | `queued`, `pending`, `forwarded`, `completed`, `returned` | Step 4 已实现 |
| `workflow_definition_status` | `draft`, `active`, `archived` | 已实现 |
| `workflow_step_type` | `task`, `approval`, `notify` | 已实现 |
| `approval_mode` | `single`, `parallel_all`, `parallel_any` | 已实现 |
| `workflow_instance_status` | `pending`, `in_progress`, `approved`, `rejected`, `returned`, `cancelled`, `completed` | 已实现 |
| `workflow_step_run_status` | `pending`, `approved`, `rejected`, `returned`, `delegated`, `skipped` | 已实现 |
| `notification_receipt_type` | `delivered`, `read`, `acknowledged` | 已实现 |
| `push_subscription_status` | `active`, `expired`, `revoked` | Phase 5 规划 |
| `document_category` | `policy`, `sop`, `announcement`, `faq`, `other` | Phase 5 规划 |
| `document_status` | `draft`, `published`, `archived` | Phase 5 规划 |

## 10. 全量数据库 Schema

### 10.1 `users`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 用户主键 |
| `email` | `varchar(255)` | UNIQUE, NOT NULL | 登录账号 |
| `password_hash` | `varchar(255)` | NOT NULL | 密码哈希 |
| `role` | `user_role` | NOT NULL | 全局角色 |
| `status` | `user_status` | NOT NULL, DEFAULT `active` | 用户状态 |
| `last_login_at` | `timestamptz` | NULL | 最近登录时间 |
| `invited_by` | `uuid` | FK -> `users.id`, NULL | 邀请创建人 |
| `invitation_token_hash` | `varchar(64)` | NULL | 邀请 token 哈希，仅服务端可见 |
| `invitation_sent_at` | `timestamptz` | NULL | 最近一次生成邀请时间 |
| `invitation_expires_at` | `timestamptz` | NULL | 邀请过期时间 |
| `invitation_revoked_at` | `timestamptz` | NULL | 邀请撤销时间 |
| `invitation_accepted_at` | `timestamptz` | NULL | 邀请完成注册时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_users_email`
- `idx_users_role_status (role, status)`
- `idx_users_invitation_token_hash (invitation_token_hash)`

**设计说明**

- 邀请制注册复用 `users` 主表，不单独引入 invitation 表；账号在被邀请后先保持 `inactive`，待受邀人通过链接设置密码后再切换到 `active`。
- 邀请 token 仅存储哈希值；撤销邀请时保留哈希锚点并写入 `invitation_revoked_at`，便于预览接口稳定返回“已撤销”状态与后续审计。
- 人员工作台允许管理员删除未建档账号，但服务端会拒绝删除已建档或已被其它业务数据引用的用户，避免把标准员工生命周期误做成物理删除。

### 10.2 `refresh_tokens`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 记录主键 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 所属用户 |
| `token_id` | `varchar(64)` | UNIQUE, NOT NULL | JWT `jti` |
| `expires_at` | `timestamptz` | NOT NULL | 过期时间 |
| `revoked_at` | `timestamptz` | NULL | 撤销时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_refresh_tokens_user_id (user_id)`

### 10.3 `departments`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 部门主键 |
| `name` | `varchar(120)` | NOT NULL | 部门名称 |
| `code` | `varchar(64)` | UNIQUE, NOT NULL | 稳定标识 |
| `parent_id` | `uuid` | FK -> `departments.id`, NULL | 上级部门 |
| `manager_id` | `uuid` | FK -> `users.id`, NULL | 部门负责人 |
| `capabilities` | `jsonb` | NOT NULL, DEFAULT `[]` | 部门能力集合，如公告发布、组织任务发布、模板管理 |
| `sort_order` | `int4` | NOT NULL, DEFAULT `0` | 排序 |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` | 是否启用 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `uq_departments_code`
- `uq_departments_parent_name (parent_id, name)`
- `idx_departments_parent_id (parent_id)`

### 10.4 `profiles`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `user_id` | `uuid` | PK, FK -> `users.id` | 与用户一一对应 |
| `employee_no` | `varchar(64)` | UNIQUE, NOT NULL | 员工编号 |
| `real_name` | `varchar(120)` | NOT NULL | 真实姓名 |
| `department_id` | `uuid` | FK -> `departments.id`, NOT NULL | 当前主部门 |
| `job_title` | `varchar(120)` | NULL | 当前展示岗位 |
| `phone` | `varchar(32)` | NULL | 电话 |
| `hire_date` | `date` | NULL | 入职日期 |
| `custom_fields` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 动态档案字段 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_profiles_employee_no`
- `idx_profiles_department_id (department_id)`
- `idx_profiles_custom_fields_gin USING GIN (custom_fields)`

**设计说明**

- `profiles` 仍是“一人一档”的锚点表。
- Phase 3 已通过 `profile_positions`、`reporting_lines`、`employment_events` 与 `delegations` 补齐复杂任职关系和授权关系。

### 10.5 `positions`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 岗位主键 |
| `code` | `varchar(64)` | UNIQUE, NOT NULL | 岗位编码 |
| `name` | `varchar(120)` | NOT NULL | 岗位名称 |
| `level` | `varchar(64)` | NULL | 岗位级别 |
| `metadata` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展配置 |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` | 是否启用 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_positions_code`
- `idx_positions_is_active (is_active)`

### 10.6 `profile_positions`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 任职关系主键 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 用户 |
| `position_id` | `uuid` | FK -> `positions.id`, NOT NULL | 岗位 |
| `department_id` | `uuid` | FK -> `departments.id`, NOT NULL | 挂载部门 |
| `assignment_type` | `position_assignment_type` | NOT NULL, DEFAULT `primary` | 任职类型 |
| `is_primary` | `bool` | NOT NULL, DEFAULT `false` | 是否主任职 |
| `starts_at` | `date` | NOT NULL | 生效日期 |
| `ends_at` | `date` | NULL | 结束日期 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_profile_positions_user_id (user_id)`
- `idx_profile_positions_department_id (department_id)`
- `idx_profile_positions_is_primary (user_id, is_primary)`

**约束与说明**

- `uq_profile_positions_assignment (user_id, position_id, department_id, starts_at)`
- CHECK `ends_at IS NULL OR ends_at >= starts_at`
- 一个用户可以拥有多个岗位关系。
- “兼职 / 代理岗 / 多部门挂载”统一通过本表表达。

### 10.7 `reporting_lines`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 汇报线主键 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 员工 |
| `manager_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 上级 |
| `department_id` | `uuid` | FK -> `departments.id`, NULL | 关联部门 |
| `line_type` | `reporting_line_type` | NOT NULL | `solid` / `dotted` |
| `is_primary` | `bool` | NOT NULL, DEFAULT `false` | 是否主要汇报线 |
| `starts_at` | `date` | NOT NULL | 生效日期 |
| `ends_at` | `date` | NULL | 结束日期 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `uq_reporting_lines_relation (user_id, manager_user_id, line_type, department_id, starts_at)`
- CHECK `user_id <> manager_user_id`
- CHECK `ends_at IS NULL OR ends_at >= starts_at`
- `idx_reporting_lines_user_id (user_id)`
- `idx_reporting_lines_manager_user_id (manager_user_id)`

### 10.8 `profile_field_definitions`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 字段定义主键 |
| `field_key` | `varchar(64)` | UNIQUE, NOT NULL | 字段标识 |
| `label` | `varchar(120)` | NOT NULL | 字段名称 |
| `field_type` | `varchar(32)` | NOT NULL | 字段类型 |
| `storage_target` | `varchar(32)` | NOT NULL | `core` / `custom` |
| `is_sensitive` | `bool` | NOT NULL, DEFAULT `false` | 是否高敏 |
| `config` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 展示 / 校验配置 |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` | 是否启用 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_profile_field_definitions_field_key`
- `idx_profile_field_definitions_is_active (is_active)`

### 10.9 `profile_field_permissions`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 权限规则主键 |
| `field_definition_id` | `uuid` | FK -> `profile_field_definitions.id`, NOT NULL | 字段定义 |
| `subject_type` | `varchar(32)` | NOT NULL | 规则主体类型 |
| `subject_value` | `varchar(64)` | NULL | 规则主体值 |
| `can_view` | `bool` | NOT NULL, DEFAULT `false` | 是否可查看 |
| `can_edit` | `bool` | NOT NULL, DEFAULT `false` | 是否可编辑 |
| `scope_filters` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 作用范围 |
| `priority` | `int4` | NOT NULL, DEFAULT `100` | 优先级 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_profile_field_permissions_definition (field_definition_id)`
- `idx_profile_field_permissions_priority (priority)`

**设计说明**

- 规则主体可表达 self / role / reporting_line / department_scope / delegation 等关系。
- 服务层负责将 actor 的角色、汇报线和授权关系解析为最终字段权限。

### 10.10 `employment_events`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 事件主键 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 所属员工 |
| `event_type` | `employment_event_type` | NOT NULL | 事件类型 |
| `effective_date` | `date` | NOT NULL | 生效日期 |
| `title` | `varchar(255)` | NOT NULL | 事件标题 |
| `summary` | `text` | NULL | 简述 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展详情 |
| `task_template_id` | `uuid` | FK -> `task_templates.id`, NULL | 显式联动的任务模板 |
| `workflow_definition_id` | `uuid` | FK -> `workflow_definitions.id`, NULL | 显式联动的审批流定义 |
| `trigger_status` | `varchar(32)` | NOT NULL, DEFAULT `skipped` | 生命周期联动状态 |
| `triggered_at` | `timestamptz` | NULL | 最近一次联动完成时间 |
| `trigger_error` | `text` | NULL | 最近一次联动失败原因 |
| `trigger_attempt_count` | `int4` | NOT NULL, DEFAULT `0` | 联动尝试次数 |
| `triggered_template_instance_id` | `uuid` | FK -> `task_template_instances.id`, NULL | 已生成的模板实例锚点 |
| `triggered_workflow_instance_id` | `uuid` | FK -> `workflow_instances.id`, NULL | 已生成的审批实例锚点 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_employment_events_user_id_date (user_id, effective_date)`
- `idx_employment_events_type (event_type)`

**设计说明**

- 当前首版联动采取“事件写入时显式绑定目标 + worker 异步触发”的保守策略，不阻塞生命周期主事务。
- `triggered_template_instance_id` 与 `triggered_workflow_instance_id` 作为幂等锚点，避免 worker 重试时重复生成实例。
- 规则化的默认映射策略与前端结构化配置仍属于下一轮深化范围。

### 10.11 `delegations`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 授权主键 |
| `delegator_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 委托人 |
| `delegate_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 被委托人 |
| `scope_type` | `delegation_scope_type` | NOT NULL | 授权范围类型 |
| `scope_department_id` | `uuid` | FK -> `departments.id`, NULL | 范围部门 |
| `scope_filters` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 额外范围过滤 |
| `status` | `delegation_status` | NOT NULL, DEFAULT `pending` | 授权状态 |
| `starts_at` | `timestamptz` | NOT NULL | 开始时间 |
| `ends_at` | `timestamptz` | NOT NULL | 结束时间 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- CHECK `delegator_user_id <> delegate_user_id`
- CHECK `ends_at > starts_at`
- `idx_delegations_delegator_status (delegator_user_id, status)`
- `idx_delegations_delegate_status (delegate_user_id, status)`

### 10.12 `attachments`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 附件主键 |
| `storage_provider` | `varchar(32)` | NOT NULL | 存储提供者 |
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

### 10.13 `attachment_links`

**实现状态**: 已实现

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

- 当前主要绑定 `task`、`task_comment`、`profile`、`notification_message`。
- 生命周期事件等对象仍属于后续扩展方向。

### 10.14 `tasks`

**实现状态**: 已实现

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
| `template_instance_id` | `uuid` | FK -> `task_template_instances.id`, NULL | 所属模板实例 |
| `template_step_run_id` | `uuid` | FK -> `task_template_step_runs.id`, NULL | 所属模板步骤运行态 |
| `source_type` | `task_source_type` | NOT NULL, DEFAULT `manual` | 来源 |
| `metadata` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展元数据 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `idx_tasks_assignee_status (assignee_id, status)`
- `idx_tasks_department_status (department_id, status)`
- `idx_tasks_due_date (due_date)`

### 10.15 `task_dependencies`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `task_id` | `uuid` | FK -> `tasks.id`, NOT NULL | 当前任务 |
| `depends_on_task_id` | `uuid` | FK -> `tasks.id`, NOT NULL | 前置任务 |
| `dependency_type` | `varchar(32)` | NOT NULL, DEFAULT `blocks` | 依赖类型 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- 主键：`(task_id, depends_on_task_id)`
- CHECK `task_id <> depends_on_task_id`
- `idx_task_dependencies_depends_on_task_id (depends_on_task_id)`

**设计说明**

- 当前已支持依赖建模。
- 后续通过模板和 workflow 引擎补齐自动触发能力。

### 10.16 `task_templates`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 模板主键 |
| `code` | `varchar(64)` | UNIQUE, NOT NULL | 模板编码 |
| `name` | `varchar(120)` | NOT NULL | 模板名称 |
| `category` | `varchar(64)` | NOT NULL | 模板分类 |
| `description` | `text` | NULL | 模板描述 |
| `trigger_type` | `varchar(32)` | NOT NULL, DEFAULT `manual` | 触发类型 |
| `config` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 模板配置 |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` | 是否启用 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_task_templates_code`
- `idx_task_templates_category_active (category, is_active)`

### 10.17 `task_template_steps`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 模板步骤主键 |
| `template_id` | `uuid` | FK -> `task_templates.id`, NOT NULL | 所属模板 |
| `step_key` | `varchar(64)` | NOT NULL | 稳定步骤标识 |
| `title` | `varchar(255)` | NOT NULL | 步骤标题 |
| `description` | `text` | NULL | 步骤描述 |
| `step_type` | `varchar(32)` | NOT NULL, DEFAULT `task` | 步骤类型 |
| `assignment_mode` | `varchar(32)` | NOT NULL, DEFAULT `single` | 分配模式：单任务或多人扇出 |
| `join_mode` | `varchar(32)` | NOT NULL, DEFAULT `all` | 汇聚规则：全部完成或任一完成 |
| `default_assignee_rule` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 默认指派规则 |
| `default_due_offset_hours` | `int4` | NULL | 相对超时时间 |
| `sort_order` | `int4` | NOT NULL, DEFAULT `0` | 排序 |
| `config` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展配置 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `uq_task_template_steps_template_key (template_id, step_key)`
- `idx_task_template_steps_template_order (template_id, sort_order)`
- CHECK `assignment_mode in ('single', 'fan_out')`
- CHECK `join_mode in ('all', 'any')`

### 10.18 `task_template_step_dependencies`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `step_id` | `uuid` | FK -> `task_template_steps.id`, NOT NULL | 当前步骤 |
| `depends_on_step_id` | `uuid` | FK -> `task_template_steps.id`, NOT NULL | 前置步骤 |
| `dependency_type` | `varchar(32)` | NOT NULL, DEFAULT `blocks` | 依赖类型 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- 主键：`(step_id, depends_on_step_id)`
- CHECK `step_id <> depends_on_step_id`
- `idx_task_tpl_step_deps_depends_on (depends_on_step_id)`

### 10.18A `task_template_instances`

**实现状态**: 已实现（工作流 E）

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 模板实例主键 |
| `template_id` | `uuid` | FK -> `task_templates.id`, NOT NULL | 所属模板 |
| `initiator_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 发起人 |
| `department_id` | `uuid` | FK -> `departments.id`, NULL | 目标部门 |
| `status` | `varchar(32)` | NOT NULL, DEFAULT `in_progress` | 实例状态 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 实例化上下文 |
| `completed_at` | `timestamptz` | NULL | 实例完成时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- CHECK `status in ('in_progress', 'completed', 'cancelled')`
- `idx_task_tpl_instances_template_status (template_id, status)`
- `idx_task_tpl_instances_initiator_created (initiator_user_id, created_at)`

### 10.18B `task_template_step_runs`

**实现状态**: 已实现（工作流 E）

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 步骤运行态主键 |
| `instance_id` | `uuid` | FK -> `task_template_instances.id`, NOT NULL | 所属模板实例 |
| `template_step_id` | `uuid` | FK -> `task_template_steps.id`, NOT NULL | 所属模板步骤 |
| `assignee_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 当前执行人 |
| `status` | `varchar(32)` | NOT NULL, DEFAULT `active` | step run 状态 |
| `completed_at` | `timestamptz` | NULL | 完成时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `uq_task_tpl_step_runs_instance_step_assignee (instance_id, template_step_id, assignee_user_id)`
- CHECK `status in ('active', 'completed', 'skipped', 'cancelled')`
- `idx_task_tpl_step_runs_instance_status (instance_id, status)`
- `idx_task_tpl_step_runs_assignee_status (assignee_user_id, status)`

### 10.19 `workflow_definitions`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 流程定义主键 |
| `code` | `varchar(64)` | UNIQUE, NOT NULL | 流程编码 |
| `name` | `varchar(120)` | NOT NULL | 流程名称 |
| `scope_type` | `varchar(64)` | NOT NULL | 业务范围 |
| `status` | `workflow_definition_status` | NOT NULL, DEFAULT `draft` | 定义状态 |
| `version` | `int4` | NOT NULL, DEFAULT `1` | 版本号 |
| `config` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 流程配置 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_workflow_definitions_code`
- `idx_workflow_definitions_scope_status (scope_type, status)`

### 10.20 `workflow_steps`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 流程步骤主键 |
| `definition_id` | `uuid` | FK -> `workflow_definitions.id`, NOT NULL | 所属流程 |
| `step_key` | `varchar(64)` | NOT NULL | 稳定步骤标识 |
| `name` | `varchar(120)` | NOT NULL | 步骤名称 |
| `step_type` | `workflow_step_type` | NOT NULL | 步骤类型 |
| `approval_mode` | `approval_mode` | NULL | 审批模式 |
| `assignee_rule` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 指派规则 |
| `reject_target_step_key` | `varchar(64)` | NULL | 驳回目标步骤 |
| `sort_order` | `int4` | NOT NULL, DEFAULT `0` | 排序 |
| `config` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展配置 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `uq_workflow_steps_definition_key (definition_id, step_key)`
- `idx_workflow_steps_definition_order (definition_id, sort_order)`

### 10.21 `workflow_instances`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 流程实例主键 |
| `definition_id` | `uuid` | FK -> `workflow_definitions.id`, NOT NULL | 使用的流程定义 |
| `source_type` | `varchar(64)` | NOT NULL | 来源类型 |
| `source_id` | `uuid` | NULL | 来源对象 ID |
| `initiator_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 发起人 |
| `status` | `workflow_instance_status` | NOT NULL, DEFAULT `pending` | 实例状态 |
| `current_step_key` | `varchar(64)` | NULL | 当前步骤 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 业务上下文 |
| `started_at` | `timestamptz` | NOT NULL | 开始时间 |
| `completed_at` | `timestamptz` | NULL | 完成时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_workflow_instances_source (source_type, source_id)`
- `idx_workflow_instances_status (status)`

### 10.22 `workflow_step_runs`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 步骤执行主键 |
| `instance_id` | `uuid` | FK -> `workflow_instances.id`, NOT NULL | 所属实例 |
| `step_id` | `uuid` | FK -> `workflow_steps.id`, NOT NULL | 所属步骤 |
| `assignee_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 执行人 |
| `delegated_from_user_id` | `uuid` | FK -> `users.id`, NULL | 被代理来源人 |
| `status` | `workflow_step_run_status` | NOT NULL, DEFAULT `pending` | 执行状态 |
| `acted_at` | `timestamptz` | NULL | 操作时间 |
| `comment` | `text` | NULL | 审批意见 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展上下文 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_workflow_step_runs_instance_status (instance_id, status)`
- `idx_workflow_step_runs_assignee_status (assignee_user_id, status)`

### 10.23 `task_watchers`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 关注人主键 |
| `task_id` | `uuid` | FK -> `tasks.id`, NOT NULL | 任务 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 用户 |
| `relation` | `varchar(32)` | NOT NULL, DEFAULT `cc` | 关系类型 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 添加人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- `uq_task_watchers_binding (task_id, user_id, relation)`
- `idx_task_watchers_user_id (user_id)`

### 10.24 `task_schedules`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 调度主键 |
| `template_id` | `uuid` | FK -> `task_templates.id`, NOT NULL | 对应模板 |
| `owner_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 创建者 |
| `cron_expr` | `varchar(128)` | NOT NULL | 调度表达式 |
| `timezone` | `varchar(64)` | NOT NULL, DEFAULT `UTC` | 时区 |
| `next_run_at` | `timestamptz` | NULL | 下次运行时间 |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` | 是否启用 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展参数 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_task_schedules_active_next_run (is_active, next_run_at)`
- `idx_task_schedules_owner_user_id (owner_user_id)`

### 10.25 `task_memos`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 备忘主键 |
| `owner_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 备忘所属用户 |
| `related_task_id` | `uuid` | FK -> `tasks.id`, NULL | 关联任务 |
| `title` | `varchar(200)` | NULL | 可选标题（迁移 `20260519_01`） |
| `content` | `text` | NOT NULL | 备忘正文 |
| `is_pinned` | `bool` | NOT NULL, DEFAULT `false` | 是否置顶 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_task_memos_owner_user_id (owner_user_id)`
- `idx_task_memos_related_task_id (related_task_id)`
- `idx_task_memos_owner_user_id_is_pinned (owner_user_id, is_pinned)`

### 10.26 `notification_messages`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 消息主键 |
| `source_type` | `varchar(64)` | NOT NULL | 业务来源 |
| `source_id` | `uuid` | NULL | 来源对象 ID |
| `recipient_user_id` | `uuid` | FK -> `users.id`, NULL | 收件用户 |
| `recipient_email` | `varchar(255)` | NULL | 直接收件地址 |
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

**设计说明**

- 当前用于异步通知总线。
- Phase 4 已在此基础上扩展“消息中心 / 回执”能力，而不是再造一套平行消息表。
- Stage 2 Phase 4 继续沿用该表作为消息中心主存储，并通过 `attachment_links` 绑定消息附件；筛选维度覆盖来源模块、回执状态、渠道、投递状态与创建时间。

### 10.27 `notification_deliveries`

**实现状态**: 已实现

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
| `delivered_at` | `timestamptz` | NULL | 成功时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_notification_deliveries_message_id (message_id)`
- `idx_notification_deliveries_status_channel (status, channel)`

### 10.28 `notification_receipts`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 回执主键 |
| `message_id` | `uuid` | FK -> `notification_messages.id`, NOT NULL | 消息 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 用户 |
| `receipt_type` | `notification_receipt_type` | NOT NULL | 回执类型 |
| `note` | `text` | NULL | 回执说明 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- `uq_notification_receipts_binding (message_id, user_id, receipt_type)`
- `idx_notification_receipts_user_id_created_at (user_id, created_at)`

### 10.29 `push_subscriptions`

**实现状态**: Phase 5 规划

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 订阅主键 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 用户 |
| `endpoint` | `text` | UNIQUE, NOT NULL | 浏览器推送端点 |
| `p256dh_key` | `text` | NOT NULL | 公钥 |
| `auth_key` | `text` | NOT NULL | 鉴权密钥 |
| `status` | `push_subscription_status` | NOT NULL, DEFAULT `active` | 订阅状态 |
| `user_agent` | `text` | NULL | 浏览器信息 |
| `last_seen_at` | `timestamptz` | NULL | 最近活跃时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_push_subscriptions_endpoint`
- `idx_push_subscriptions_user_status (user_id, status)`

### 10.30 `task_logs`

**实现状态**: 已实现

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

### 10.31 `task_comments`

**实现状态**: 已实现

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

**约束与索引**

- CHECK `length(trim(content)) > 0`
- `idx_task_comments_task_id_created_at (task_id, created_at ASC)`
- `idx_task_comments_user_id (user_id)`

### 10.32 `documents`

**实现状态**: Phase 5 规划

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

### 10.33 `document_embeddings`

**实现状态**: Phase 5 规划

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
- 向量索引：`ivfflat` 或 `hnsw`

### 10.34 `board_cards`

**实现状态**: 重构 Step 2 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 看板卡片主键 |
| `scope_department_id` | `uuid` | FK -> `departments.id`, NULL | 可见范围部门，NULL 表示公司级 |
| `author_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 发布人 |
| `title` | `varchar(120)` | NOT NULL | 主题 |
| `content_md` | `text` | NOT NULL | 内容 |
| `expires_at` | `timestamptz` | NOT NULL | 到期时间 |
| `created_at` | `timestamptz` | NOT NULL | 发布时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `idx_board_cards_scope_department_id (scope_department_id)`
- `idx_board_cards_author_user_id (author_user_id)`
- `idx_board_cards_expires_at (expires_at)`

### 10.35 `board_card_archives`

**实现状态**: 重构 Step 2 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 归档主键 |
| `original_card_id` | `uuid` | UNIQUE, NOT NULL | 原活跃卡片 ID |
| `scope_department_id` | `uuid` | FK -> `departments.id`, NULL | 原范围部门 |
| `author_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 原发布人 |
| `title` | `varchar(120)` | NOT NULL | 主题快照 |
| `content_md` | `text` | NOT NULL | 内容快照 |
| `published_at` | `timestamptz` | NOT NULL | 原发布时间 |
| `expires_at` | `timestamptz` | NOT NULL | 原到期时间 |
| `archived_at` | `timestamptz` | NOT NULL | 归档时间 |

**约束与索引**

- `uq_board_card_archives_original_card_id`
- `idx_board_card_archives_scope_department_id (scope_department_id)`
- `idx_board_card_archives_archived_at (archived_at DESC)`

### 10.36 `announcements`

**实现状态**: 重构 Step 2 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 公告主键 |
| `publisher_department_id` | `uuid` | FK -> `departments.id`, NOT NULL | 发布部门 |
| `author_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 发布人 |
| `title` | `varchar(160)` | NOT NULL | 公告标题 |
| `content_md` | `text` | NOT NULL | 公告内容 |
| `published_at` | `timestamptz` | NOT NULL | 发布时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `idx_announcements_publisher_department_id (publisher_department_id)`
- `idx_announcements_published_at (published_at DESC)`

### 10.37 `announcement_archives`

**实现状态**: 重构 Step 2 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 归档主键 |
| `original_announcement_id` | `uuid` | UNIQUE, NOT NULL | 原活跃公告 ID |
| `publisher_department_id` | `uuid` | FK -> `departments.id`, NOT NULL | 原发布部门 |
| `author_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 原发布人 |
| `title` | `varchar(160)` | NOT NULL | 标题快照 |
| `content_md` | `text` | NOT NULL | 内容快照 |
| `published_at` | `timestamptz` | NOT NULL | 原发布时间 |
| `archived_at` | `timestamptz` | NOT NULL | 撤下归档时间 |

**约束与索引**

- `uq_announcement_archives_original_announcement_id`
- `idx_announcement_archives_publisher_department_id (publisher_department_id)`
- `idx_announcement_archives_archived_at (archived_at DESC)`

### 10.38 `reports`

**实现状态**: Step 4 已实现；2026-04-21 已修复 PostgreSQL enum 持久化不一致问题

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 汇报主键 |
| `direction` | `report_direction` | NOT NULL | `upward` / `downward` |
| `status` | `report_status` | NOT NULL, DEFAULT `in_progress` | 汇报状态 |
| `title` | `varchar(255)` | NOT NULL | 主题 |
| `content_md` | `text` | NOT NULL | 正文 |
| `initiator_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 发起人 |
| `target_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 最终目标人 |
| `current_recipient_user_id` | `uuid` | FK -> `users.id`, NULL | 当前处理人 |
| `current_route_sequence` | `int` | NULL | 当前节点序号 |
| `workflow_definition_id` | `uuid` | FK -> `workflow_definitions.id`, NULL | 挂接的审批流定义 |
| `workflow_instance_id` | `uuid` | FK -> `workflow_instances.id`, NULL | 挂接的审批实例 |
| `completed_at` | `timestamptz` | NULL | 完成时间 |
| `returned_at` | `timestamptz` | NULL | 退回时间 |
| `archived_at` | `timestamptz` | NULL | 归档时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_reports_initiator_status (initiator_user_id, status)`
- `idx_reports_current_recipient (current_recipient_user_id, status)`
- `idx_reports_target_status (target_user_id, status)`

### 10.39 `report_routes`

**实现状态**: Step 4 已实现；状态枚举与数据库约束已统一为按枚举值持久化

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 路由节点主键 |
| `report_id` | `uuid` | FK -> `reports.id`, NOT NULL | 所属汇报 |
| `sequence_no` | `int` | NOT NULL | 节点序号 |
| `sender_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 上一跳发送人 |
| `recipient_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 预期接收人 |
| `assigned_user_id` | `uuid` | FK -> `users.id`, NULL | 实际处理人（含代理） |
| `status` | `report_route_status` | NOT NULL, DEFAULT `queued` | 节点状态 |
| `activated_at` | `timestamptz` | NULL | 激活时间 |
| `acted_at` | `timestamptz` | NULL | 处理时间 |
| `note` | `text` | NULL | 节点备注 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_report_routes_sequence (report_id, sequence_no)`
- `idx_report_routes_assigned_status (assigned_user_id, status)`
- `idx_report_routes_report_status (report_id, status)`

### 10.40 `error_events`

**实现状态**: Step 4 排障补充，已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 错误事件主键 |
| `request_id` | `varchar(64)` | NOT NULL | 请求编号 |
| `scope` | `varchar(128)` | NOT NULL | 业务或模块范围，如 `report_center.create_report` |
| `actor_user_id` | `uuid` | FK -> `users.id`, NULL | 当前用户 |
| `source_type` | `varchar(64)` | NULL | 业务对象类型 |
| `source_id` | `uuid` | NULL | 业务对象主键 |
| `http_method` | `varchar(16)` | NULL | 请求方法 |
| `path` | `varchar(255)` | NULL | 请求路径 |
| `error_type` | `varchar(255)` | NOT NULL | Python 异常类型 |
| `error_message` | `text` | NOT NULL | 错误信息 |
| `error_code` | `varchar(64)` | NULL | 统一错误码 |
| `stage` | `varchar(64)` | NULL | 失败阶段 |
| `context_json` | `json/jsonb` | NOT NULL | 脱敏后的上下文摘要 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_error_events_request_id (request_id)`
- `idx_error_events_scope_created_at (scope, created_at)`
- `idx_error_events_actor_user_id (actor_user_id, created_at)`
- `idx_error_events_source_binding (source_type, source_id)`

## 11. 关系说明

- `users 1:1 profiles`
- `users 1:N refresh_tokens`
- `departments 1:N profiles`
- `departments 1:N board_cards`
- `departments 1:N announcements`
- `users N:N positions` 通过 `profile_positions`
- `users N:N users` 通过 `reporting_lines`
- `users 1:N reports`（initiator / target / current_recipient 三种角色）
- `reports 1:N report_routes`
- `users 1:N error_events`（actor_user）
- `profiles 1:N employment_events`
- `task_templates 1:N employment_events`（显式生命周期联动目标）
- `workflow_definitions 1:N employment_events`（显式生命周期联动目标）
- `profile_field_definitions 1:N profile_field_permissions`
- `users N:N users` 通过 `delegations`
- `tasks N:N tasks` 通过 `task_dependencies`
- `users 1:N task_memos`
- `tasks 1:N task_memos`
- `task_templates 1:N task_template_steps`
- `task_templates 1:N task_template_instances`
- `task_template_steps N:N task_template_steps` 通过 `task_template_step_dependencies`
- `task_template_steps 1:N task_template_step_runs`
- `task_template_instances 1:N task_template_step_runs`
- `task_template_instances 1:N tasks`
- `workflow_definitions 1:N workflow_steps`
- `workflow_definitions 1:N workflow_instances`
- `task_template_instances 1:N employment_events`（triggered_template_instance_id 回链）
- `workflow_instances 1:N employment_events`（triggered_workflow_instance_id 回链）
- `workflow_instances 1:N workflow_step_runs`
- `tasks 1:N task_comments`
- `tasks 1:N task_logs`
- `notification_messages 1:N notification_deliveries`
- `notification_messages 1:N notification_receipts`
- `notification_messages 1:N attachment_links`（逻辑绑定，`target_type = notification_message`）
- `documents 1:N document_embeddings`
- `board_cards 1:1 board_card_archives`
- `announcements 1:1 announcement_archives`
- `attachments N:N 业务对象` 通过 `attachment_links`

## 12. 当前验证基线

截至当前文档版本，仓库至少具备如下验证能力：

- backend：
  - `pytest`（覆盖 models / migrations / services / api / workers）
  - `python -m compileall app tests`
- frontend：
  - `npm run test:unit -- --run`
  - `npm run type-check`
  - `npm run build`
  - `npm run lint`
- 用户验测：
  - Phase 1：实际点击“初始化管理员”和“登录”通过
  - Phase 2：用户简单测试反馈“看上去基本没有问题”
- 编排：
  - Compose 文件可做配置级检查
  - `worker` 已纳入编排
  - 完整 Docker 运行级验证仍建议在具备 Docker 的环境执行

## 13. 维护规则

- 每完成一个里程碑，必须同步更新本文件
- 新增表、枚举或关键运行时组件时，必须同步记录其状态与所属阶段
- “当前已实现”与“未来规划”必须明确区分，禁止混写
- 若阶段边界调整，先更新 `implementation-plan.md`，再回写本文件