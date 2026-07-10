---
type: paradigma-contract
title: "图引擎 Schema"
description: "workflow_graph_* 表族：模板、节点、边、实例、交付物、outbox、运行事件。"
tags: ["contract", "database", "schema", "graph-engine"]
timestamp: 2026-07-10T22:00:55+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["图引擎Schema", "graph", "DAG"]
    en: ["graph engine schema", "DAG"]
  contract_kind: "database"
  relations:
    depends_on: ["../data-contracts.md"]
---
# 图引擎 Schema

> WARM — workflow_graph_* 表族：模板、节点、边、实例、交付物、outbox、运行事件。契约索引见 [`data-contracts.md`](../data-contracts.md)。

### 10.41–10.48 图引擎与运行事件（摘要）

> **实现状态**: 已实现（工作流重构 Phase 2–11；视频 v1 增量见迁移 `20260522_01`、`20260523_01`；部门作用范围见 `20260709_01`）。
> **ORM**: `backend/app/models/workflow_graph.py` · **迁移**: `20260429_04_workflow_graph_core.py` 及后续

| 表 | 职责 | 关键字段 / 约束 |
| --- | --- | --- |
| `workflow_graph_templates` | DAG 模板定义 | `code`、`base_code`+`version`、`status`、`context_schema`、`config`、`source_template_id`、`scope_department_ids JSONB NOT NULL DEFAULT []`（空数组表示不限制部门） |
| `workflow_graph_template_nodes` | 模板节点 | `node_key`、`node_type`、`assignment_mode`、`join_mode`、`assignee_rule`、`config` |
| `workflow_graph_template_edges` | 条件边 | `from_node_id`、`to_node_id`、`condition`、`priority`、`is_reject_path` |
| `workflow_graph_instances` | 运行实例 | `context`+`context_version`、`status`、`current_node_key`、`run_label`、`parent_instance_id`（批次/fork） |
| `workflow_node_instances` | 节点运行态 | `node_key`、`instance_key`、`iteration`、`engine_state`、`business_state`、`assignee_user_id` |
| `workflow_deliverables` | 节点交付快照 | `node_instance_id`（UNIQUE）、`summary`、`payload`、`submitted_at` |
| `workflow_outbox_events` | 可靠异步投递 | `event_type`、`status`、`attempt_count`、`available_at`、`last_error` |
| `workflow_run_events` | Append-only 运行事件 | `instance_id`、`event_type`、`actor_user_id`、`payload`、`created_at`（W8） |

**关系补充**

- `workflow_graph_templates 1:N workflow_graph_template_nodes / edges / instances`
- `workflow_graph_instances 1:N workflow_node_instances / outbox_events / run_events`
- `workflow_graph_instances N:1 workflow_graph_instances`（`parent_instance_id` 子 Run fork）
- `workflow_node_instances 1:1 workflow_deliverables`（按节点快照）
- 兼容 `Task` 投影通过 `extra_metadata` / `source_id` 与 graph 锚点互链（见 `architecture.md` §6.13B）
- **TC-P2** 模板节点 `config.ui_profile`（可选）：`video_n1_capture` \| `video_n2_aggregate` \| `video_production_step` \| `video_batch_root` \| `graph_manual` 等；实例化写入 `Task.extra_metadata.ui_profile`，前端 `profile.ts` 优先读取

