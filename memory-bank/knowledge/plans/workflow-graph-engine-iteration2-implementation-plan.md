---
type: paradigma-plan
title: 工作流图引擎 Iteration 2 实施计划
description: "条件路径、持久化 traversal、activation dependency、Join、no-route、Deep-Reject 与 Context 并发语义。"
tags:
  - plan
  - workflow-graph
  - iteration-2
  - routing
  - join
timestamp: 2026-07-15T09:30:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: hot
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Iteration 2, 路径语义, traversal, activation dependency, no-route]
    en: [iteration 2, edge traversal, activation dependency, workflow routing]
---
# 工作流图引擎 Iteration 2 实施计划

> **状态**：2026-07-15 实施完成并通过自动化验证，等待用户验收。只改造新建的 `graph-v3` Run；既有 `graph-v2` snapshot Run 与 `legacy-v1` Run 保持原 executor 语义，不原地升级。

## 0. 落地结果

- [x] 迁移 `20260715_01` 增加 routing/result/diagnostics、两张路径账本表与必要状态。
- [x] graph-v3 snapshot format v2；graph-v2/legacy executor 不生成推测性路径证据。
- [x] exclusive/inclusive/parallel/first-match、skipped、Wait-All/Wait-Any、no-route 与合法 End 收口。
- [x] Deep-Reject 失效旧 traversal/dependency，并阻断旧 iteration 完成和显式推进。
- [x] Context patch 要求 expected version，记录 diff event；多人 fan-out 使用不可变 `branch:NNNN` identity。
- [x] 统一 Run→Node 锁顺序，消除 Wait-Any PostgreSQL 竞态死锁。
- [x] `WG-GAP-001`–`003` 全部转正；后端全量、PostgreSQL 10/10、前端 type-check、Vitest 146 项与 production build 通过。

Iteration 3 的 HumanTask Link、写所有权与 command receipt 未提前实施。

## 1. 精确范围

本迭代完成以下 P0 语义：

1. 模板节点显式 `routing_mode=exclusive|inclusive|parallel|first_match`，存量回填 `inclusive`。
2. 新增 `workflow_edge_traversals`，按源 NodeInstance 持久化每条出边 `taken|not_taken|invalidated`、条件结果、Context 摘要与选择原因。
3. 新增 `workflow_node_activation_dependencies`，记录目标 activation 由哪条 taken traversal / 哪个上游产生。
4. 节点新增 `skipped|failed|suspended`；Run 新增 `failed` 状态、`result` 与结构化 `diagnostics`。
5. 未选路径递归标记 `skipped`；Join 忽略未产生路径，只等待本 iteration 实际可达且未跳过的上游。
6. 无匹配路由立即失败并写 `no_route` 诊断，不允许静默完成或永久 active。
7. Snapshot v2 写入兼容 Start/End 集合；完成必须到达合法 End，且不存在悬挂节点、failed 节点或等待 dependency。
8. Deep-Reject 失效旧 traversal/dependency；旧 iteration 永不再推进。
9. Context patch 对 `graph-v3` 要求 `expected_context_version`，冲突返回 409，并写 `context_patched` diff 事件。
10. `current_node_key` 只作为活动节点集合的展示投影。

不在本迭代实施：Task/Node 写所有权、HumanTask Link、command receipt、Handler 化和 standalone Task；这些仍属于 Iteration 3–4。

## 2. 兼容与切流

| Run | 行为 |
| --- | --- |
| 新建模板 Run | `engine_version=graph-v3`，snapshot format v2，启用 traversal/activation 路径语义 |
| 既有 snapshot Run | 保持 `graph-v2`，继续 Iteration 1 executor，不生成猜测性 traversal |
| legacy Run | 保持 `legacy-v1` 实时模板兼容路径 |

迁移只 expand：新增列/表、扩展 check constraint；不回填历史 traversal，不切换存量 Run。回滚代码时保留新表；数据库 downgrade 仅用于发布前演练。

## 3. 数据模型

- `workflow_graph_template_nodes.routing_mode varchar(16)`：非空，默认 `inclusive`。
- `workflow_graph_instances.result varchar(32)`：nullable；`success|approved|rejected|cancelled|terminated|failed`。
- `workflow_graph_instances.diagnostics JSONB`：新 Run 默认 `{}`。
- `workflow_edge_traversals`：Run、源节点实例、iteration、from/to key、状态、条件证据、Context version、失效时间；唯一 `(source_node_instance_id,to_node_key)`。
- `workflow_node_activation_dependencies`：Run、目标节点实例、源节点实例、traversal、状态；唯一 `(node_instance_id,source_node_instance_id)`。

## 4. 运行时规则

- `exclusive/first_match`：优先级顺序选第一条命中边；无命中才取第一条 else。
- `inclusive`：选择全部命中边；无命中才取 else。
- `parallel`：无条件边全部产生；带条件边仍保存逐边求值证据，未命中不产生 activation。
- 未选分支的专属可达节点 `skipped`；同时可由已选分支到达的 Join 不跳过。
- Wait-All 等待本 iteration 中实际产生且未 skipped/terminated 的上游；Wait-Any 获胜后默认 `revoke`，终止仍可操作 peer 并记录策略。
- leaf 完成后只有满足兼容 End 与无悬挂状态时才能成功收口。

## 5. 验证矩阵

- 转正 `WG-GAP-001`–`003`。
- SQLite：exclusive/inclusive/parallel/first-match、skip 传播、End 完成、no-route、Context version、Deep-Reject 失效。
- PostgreSQL：并发 Join 单次 activation、exclusive/inclusive Join、no-route、Wait-Any 迟到、Deep-Reject 旧 iteration、Context 冲突、重复推进不重复 traversal/dependency、Alembic 往返。
- 回归：视频批次/制作流、Notice、Task 投影、模板链、Iteration 1 snapshot 不漂移。

## 6. 停止条件

- `graph-v3` 推进仍需实时模板；
- Join 的激活原因无法仅由 snapshot、NodeInstance、traversal/dependency 解释；
- PostgreSQL 并发产生重复有效 activation/traversal；
- 为修路径语义必须提前改造 Task 写所有权。

满足停止条件时保留 `graph-v2` 默认，不扩大到 Iteration 3。
