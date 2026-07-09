---
type: paradigma-contract
title: "任务与协同 Schema"
description: "任务、依赖、评论、日志、模板、实例、备忘、watcher、调度。"
tags: ["contract", "database", "schema", "task", "collaboration"]
timestamp: 2026-07-09T09:30:00+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["任务Schema", "模板", "评论", "备忘"]
    en: ["task schema", "template", "comments"]
  contract_kind: "database"
  relations:
    depends_on: ["../data-contracts.md"]
---
# 任务与协同 Schema

> WARM — 任务、依赖、评论、日志、模板、实例、备忘、watcher、调度。 完整 schema 见 [`data-contracts.md`](.../data-contracts.md)。

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
| `code` | `varchar(64)` | UNIQUE, NOT NULL | 模板编码（对外稳定标识） |
| `base_code` | `varchar(64)` | NOT NULL | 版本族编码（Stage 2 Phase 2） |
| `version` | `int4` | NOT NULL, DEFAULT `1` | 模板版本号 |
| `name` | `varchar(120)` | NOT NULL | 模板名称 |
| `category` | `varchar(64)` | NOT NULL | 模板分类 |
| `description` | `text` | NULL | 模板描述 |
| `trigger_type` | `varchar(32)` | NOT NULL, DEFAULT `manual` | 触发类型 |
| `config` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 模板配置 |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` | 是否启用 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `source_template_id` | `uuid` | FK -> `task_templates.id`, NULL | 来源模板（新建版本链） |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_task_templates_code`
- `uq_task_templates_base_version (base_code, version)`
- `idx_task_templates_base_code (base_code)`
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


