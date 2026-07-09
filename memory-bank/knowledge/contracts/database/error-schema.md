---
type: paradigma-contract
title: "错误诊断 Schema"
description: "error_events 错误事件追踪与诊断。"
tags: ["contract", "database", "schema", "error"]
timestamp: 2026-07-09T09:30:00+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["错误Schema", "诊断"]
    en: ["error schema", "diagnostics"]
  contract_kind: "database"
  relations:
    depends_on: ["../data-contracts.md"]
---
# 错误诊断 Schema

> WARM — error_events 错误事件追踪与诊断。 完整 schema 见 [`data-contracts.md`](.../data-contracts.md)。

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


