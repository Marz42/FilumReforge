---
type: paradigma-contract
title: "汇报中心 Schema"
description: "汇报主表、路由节点。"
tags: ["contract", "database", "schema", "report"]
timestamp: 2026-07-09T09:30:00+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["汇报Schema", "路由"]
    en: ["report schema", "route"]
  contract_kind: "database"
  relations:
    depends_on: ["../data-contracts.md"]
---
# 汇报中心 Schema

> WARM — 汇报主表、路由节点。 完整 schema 见 [`data-contracts.md`](.../data-contracts.md)。

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


