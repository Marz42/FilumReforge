---
type: paradigma-contract
title: "图引擎 Schema"
description: "图引擎十四表：定义、运行、路径账本、HumanTask Link、命令回执、运维异常、outbox、事件与调度。"
tags: ["contract", "database", "schema", "graph-engine"]
timestamp: 2026-07-16T21:19:21+08:00
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

> WARM — **十四表** as-built：定义 / 运行 / traversal / activation dependency / HumanTask Link / command receipt / operational incident / 交付 / outbox / 运行事件 / 周期调度。领域总览见 [`domains/workflow-graph-engine.md`](../../domains/workflow-graph-engine.md)。契约索引见 [`data-contracts.md`](../data-contracts.md)。

### 10.41–10.49 图引擎与运行事件（摘要）

> **实现状态**: 已实现（工作流重构 Phase 2–11；Iteration 1–3F 迁移见 `20260713_01`、`20260715_01`、`20260715_02`、`20260715_03`、`20260716_01`、`20260716_02`；周期调度 F-24）。
> **ORM**: `backend/app/models/workflow_graph.py` · **迁移**: `20260429_04_workflow_graph_core.py` 及后续

| 表 | 职责 | 关键字段 / 约束 |
| --- | --- | --- |
| `workflow_graph_templates` | DAG 模板定义 | `code`、`base_code`+`version`、`status`、`context_schema`、`config`、`tags JSONB NOT NULL DEFAULT '[]'`（用户分类标签，零行为影响；DRAFT/ACTIVE 可改）、`source_template_id`、`scope_mode ∈ {global,departments}`、`scope_department_ids`；ACTIVE/ARCHIVED **定义**不可原地编辑（tags 为元数据例外，见 ADR-017） |
| `workflow_graph_template_nodes` | 模板节点 | 上述字段 + `routing_mode ∈ {exclusive,inclusive,parallel,first_match}` |
| `workflow_graph_template_edges` | 条件边 | `from_node_id`、`to_node_id`、`condition`、`priority`、`is_reject_path`（前进路由排除 reject 边） |
| `workflow_graph_instances` | 运行实例 | 上述运行字段 + snapshot/hash、executor/engine、`result`、`diagnostics`；新 Run=`snapshot/graph-v3`，既有 graph-v2/legacy 不原地切换 |
| `workflow_node_instances` | 节点运行态 | 唯一 `(instance_id,node_key,instance_key,iteration)`；engine state 含 `skipped/failed/suspended`；`instance_key` 为不可变分支身份 |
| `workflow_edge_traversals` | 实际路径账本 | 源 NodeInstance + iteration + from/to key；`taken/not_taken/invalidated`；条件、Context 摘要/version、选择证据 |
| `workflow_node_activation_dependencies` | 激活依赖账本 | 目标/源 NodeInstance + traversal；`waiting/satisfied/cancelled/invalidated`；解释 Join 实际等待来源 |
| `workflow_human_task_links` | Work Item ↔ NodeExecution 正式关系 | FK 到 Run/Node/Task；一个 Task 唯一归属一个 Node；每 Node 仅一个 active primary；`iteration >= 1`；支持 supporting/observer 与 completed/invalidated/superseded 历史链 |
| `workflow_command_receipts` | 工作流命令幂等账本 | 唯一 `(actor_key,command_type,command_id)`；canonical payload SHA-256；`processing/succeeded/failed` 与首次 result/error |
| `workflow_operational_incidents` | 持久化运维异常与迁移队列 | fingerprint 唯一幂等聚合；category/status/severity/count/时间窗；可关联 Run/Node/Task/Receipt/Outbox，保存脱敏 details |
| `workflow_deliverables` | 节点交付快照 | `node_instance_id`（UNIQUE）、`summary`、`payload`、`submitted_at` |
| `workflow_outbox_events` | 可靠异步投递 | `event_type`、`status`、`attempt_count`、`available_at`、`last_error` |
| `workflow_run_events` | Append-only 运行事件 | `event_type` + event/aggregate version、command/causation/correlation、actor、payload、`occurred_at`/`created_at` |
| `workflow_graph_template_schedules` | 图模板周期调度 | `cron_expr`、`timezone`、`scope_department_id`、`scope_mode ∈ {self,subtree}`、`participant_mode`、`next_run_at`、last-run 元数据 |

**关系补充**

- `workflow_graph_templates 1:N workflow_graph_template_nodes / edges / instances / schedules`
- `workflow_graph_instances 1:N workflow_node_instances / edge_traversals / activation_dependencies / human_task_links / operational_incidents / outbox_events / run_events`
- `workflow_graph_instances N:1 workflow_graph_instances`（`parent_instance_id` 子 Run fork）
- `workflow_node_instances 1:1 workflow_deliverables`（按节点快照）
- 新写 HumanTask 投影同时写 `workflow_human_task_links` 与兼容 `Task.extra_metadata` / `Node.config.task_id`；读取 Link-first、JSON fallback。Link 存在而 JSON 不一致时以 Link 为准并登记 `link_mismatch`；fallback/回填歧义进入 operational incident。存量回填须三锚点交叉校验，不猜测修复（见 [`core-workflows.md`](../../domains/architecture/core-workflows.md) §6.13B）
- **TC-P2** 模板节点 `config.ui_profile`（可选）：`video_n1_capture` \| `video_n2_aggregate` \| `video_production_step` \| `video_batch_root` \| `graph_manual` 等；实例化写入 `Task.extra_metadata.ui_profile`，前端 `profile.ts` 优先读取。属 **节点内部运行时机制**，不是模板级产品类型（ADR-017）
- **TemplateCapabilities**（计算字段，非持久列；ADR-017）：`can_instantiate_directly` / `can_schedule` / `is_fork_target` / `has_multi_instance` / `has_launch_entry` / `derived_hints[]` — 由图谱结构（拓扑起点、`multi_instance`+`expand_from`、fork 引用）+ 显式 opt-in（`schedulable`、`launch_schema`）派生；list/detail/designer API 返回。用户 **tags 不参与** 任何门控
- **`config.run_kind`**（**deprecated / legacy**）：历史 JSONB 键 `batch` \| `production`，曾作模板级产品类型与发起/调度门控。旧视频 seed 只读保留；新模板不写。过渡期 dual-read：capabilities 优先，不可用时回退 `run_kind`。实例 `context.run_kind` 可为视频 v1 面板兼容标签。见 [`domains/task-center.md`](../../domains/task-center.md) §7.7 · spec `2026-07-22-template-engine-decouple-design.md`
- **运行时路由**用边 `condition`（`condition_evaluator`）；节点 `config.routing_rules` 仅设计时拓扑校验，不驱动图前进
- Snapshot 内节点按 `(sort_order,node_key)`、边按 `(from_node_key,priority,to_node_key)` 排序；边以 node key 表达运行语义，canonical JSON 使用 UTF-8/排序键/紧凑分隔符后计算 SHA-256
- `definition_snapshot` 对存量 legacy Run 保持 nullable；不得猜测性回填。只读盘点入口：`python -m app.scripts.report_workflow_legacy_runs`
- Iteration 3-F 通过 `WorkItemWriteService` / `WorkflowRuntimeWriteService` 和全仓库 AST guard 固化写所有权；五类关键 API command receipt 与 RunEvent 信封保持不变。`notification_messages.deduplication_key=workflow_outbox:{event_id}` 唯一，重复命中登记 `outbox_duplicate`。Admin readiness API 与 CLI 可查询 fallback、冲突、失败、engine version 和未迁移对象；目标环境连续 7 天零 fallback 仍是 Iteration 4 前置闸门。
