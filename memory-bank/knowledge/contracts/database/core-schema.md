---
type: paradigma-contract
title: "核心 Schema (IAM / 组织 / HR)"
description: "用户认证、部门、档案、岗位、汇报线、字段权限、生命周期事件、代理授权。"
tags: ["contract", "database", "schema", "iam", "hr", "org"]
timestamp: 2026-07-09T09:30:00+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["核心Schema", "IAM", "HR", "部门", "档案"]
    en: ["core schema", "IAM", "HR", "department"]
  contract_kind: "database"
  relations:
    depends_on: ["../data-contracts.md"]
---
# 核心 Schema (IAM / 组织 / HR)

> WARM — 用户认证、部门、档案、岗位、汇报线、字段权限、生命周期事件、代理授权。 完整 schema 见 [`data-contracts.md`](.../data-contracts.md)。

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


