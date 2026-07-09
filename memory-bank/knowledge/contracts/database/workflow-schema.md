---
type: paradigma-contract
title: "工作流与审批 Schema"
description: "流程定义、步骤、实例、步骤运行态。"
tags: ["contract", "database", "schema", "workflow", "approval"]
timestamp: 2026-07-09T09:30:00+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["工作流Schema", "审批", "流程"]
    en: ["workflow schema", "approval"]
  contract_kind: "database"
  relations:
    depends_on: ["../data-contracts.md"]
---
# 工作流与审批 Schema

> WARM — 流程定义、步骤、实例、步骤运行态。 完整 schema 见 [`data-contracts.md`](.../data-contracts.md)。

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


