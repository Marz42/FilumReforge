---
type: paradigma-progress
title: "KI-014 Gate 0 只读 Schema Drift 审计"
description: "在隔离 Docker PostgreSQL（fresh upgrade 至 20260812_04，含既有卷数据）执行 §3 只读审计并确认迁移门禁。"
tags: [progress, ki-014, postgresql, alembic, schema-drift, audit]
timestamp: 2026-09-04T15:45:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: verified
  relations:
    related_to:
      - ../../knowledge/known-issues/ki-014-postgresql-alembic-schema-drift.md
      - ../../knowledge/plans/2026-08-26-ki014-schema-drift-remediation-plan.md
---

# KI-014 Gate 0 只读 Schema Drift 审计

## 环境

- Docker `pgvector/pgvector:pg16` via `infra/docker`（host port `5433`）
- Database `filum` / schema `public` / `server_version_num=160013`
- `alembic upgrade` → `20260812_04 (head)`
- `BEGIN TRANSACTION READ ONLY` / `transaction_read_only=on`；结果仅聚合与 schema 元数据

## 门禁结果

| 检查 | 结果 |
|------|------|
| `alembic_version` = `20260812_04` | PASS |
| status 值仅为已知状态的大小写变体 | PASS（见下；无未知拼写） |
| `idx_users_invitation_token_hash` 存在 | PASS |
| workflow graph NULL 计数可解释 | PASS（三列均为 0） |

## 列定义（脱敏）

| table.column | data_type | length | nullable | default |
|---|---|---|---|---|
| employment_events.trigger_status | varchar | 32 | NO | skipped |
| tasks.status | varchar | 6 | NO | todo |
| task_logs.from_status / to_status | varchar | 6 | YES | — |
| workflow_graph_templates.scope_mode | varchar | 16 | YES | global |
| workflow_graph_instances.engine_version | varchar | 32 | YES | legacy-v1 |
| workflow_graph_instances.executor_kind | varchar | 16 | YES | legacy |

## Distinct 值（聚合）

- `tasks.status`: `DOING` 5 · `DONE` 34 · `REVIEW` 2 · `TODO` 5（**全部大写成员名**；无 `blocked`/`BLOCKED`）
- `task_logs.from_status`: 大写 `DOING/DONE/REVIEW/TODO` + NULL 102
- `task_logs.to_status`: 大写 `DOING/DONE/REVIEW` + NULL 102
- `employment_events.trigger_status`: 0 行

## NULL 计数

- `scope_mode` nulls = 0
- `engine_version` nulls = 0
- `executor_kind` nulls = 0

## `alembic check`（预期非 clean）

确认与 KI-014 一致的漂移：

1. `trigger_status` VARCHAR(32) → ORM value Enum（长度推导偏短）
2. `tasks`/`task_logs` status VARCHAR(6) → ORM Enum 成员名（大写 TODO…）
3. 建议删除 `idx_users_invitation_token_hash`（ORM 漏声明）
4. 三列 DB nullable → ORM non-null

## 结论

Gate 0 **通过**。可进入 Phase A metadata / 双读兼容；Phase B expand 必须先把 status 扩到 `VARCHAR(16)` 才能安全写入 `blocked` 并容纳大小写兼容期。现存 status 以**大写**为主，contract 归一化到小写前必须完成兼容观察。

本审计库为本地 Docker 隔离卷（含历史试用数据），**不得**写成生产/预发切流证据。
