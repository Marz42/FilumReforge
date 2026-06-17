# 领域：工作流图引擎 (Workflow Graph Engine)

> 🌡️ WARM — 涉及 `WorkflowGraphTemplate`、节点推进、条件边、outbox 时读取。

**计划**: `plans/workflow-refactor-implementation-plan.md` · **ADR**: `decisions.md` ADR-005

---

## 数据模型（七表 + outbox）

`workflow_graph_templates` / `_nodes` / `_edges` / `workflow_graph_instances` / `workflow_node_instances` / `workflow_deliverables` / `workflow_outbox_events`

字段权威来源：`backend/app/models/workflow_graph.py`、Alembic `20260429_04_workflow_graph_core.py` 及后续迁移。

---

## Feature Flags

| 开关 | 默认 | 作用 |
|------|------|------|
| `WORKFLOW_GRAPH_ENGINE_ENABLED` | `true` | 手动任务 dual-write、节点推进 |
| `TASK_CENTER_V2_ENABLED` | `true` | 任务中心 graph-first 读路径 |

配置：`backend/app/core/config.py`

---

## 能力阶段（摘要）

| Phase | 能力 |
|-------|------|
| 3 | 单节点 dual-write |
| 4–5 | 交付/验收/返工、握手 |
| 6–7 | 多节点、条件边、Context、Notice |
| 8–9 | Wait-Any、深度打回、迭代版本 |
| 10 | 前端图详情、路由规则编辑器 |
| 11 | routing_rules 桥接、outbox、迁移 CLI、Playwright |

---

## 关键服务与 API

| 路径 | 作用 |
|------|------|
| `WorkflowGraphService` | 实例化、推进、完成、打回、接管 |
| `condition_evaluator.py` | 共享条件求值（图 + E routing_rules） |
| `workflow_graph_engine.py` | REST 入口 |
| `workflow_outbox_worker.py` | 异步 outbox 消费 |
| `legacy_task_graph_migration_service.py` | 旧任务迁移/回滚 |

---

## 与 工作流 E 的边界

- **E**: `task_templates` + `TaskTemplateService.instantiate_template`
- **图**: `POST .../workflow-graph/templates/{id}/runs` 等
- **现状**: 双轨并存；读侧已 graph-first；**统一**为产品 backlog

---

## 核心流程

见 `architecture.md` §6.13B：模板定义 → 实例化 → 节点激活 → 完成/条件路由 → fan-out/join → outbox 通知。

---

## 调试提示

- 写路径须 `session.commit()` 后跨请求可见
- 详情 API 避免 ORM 懒加载 `node_instances`
- 见 `known-issues.md` 图引擎小节
