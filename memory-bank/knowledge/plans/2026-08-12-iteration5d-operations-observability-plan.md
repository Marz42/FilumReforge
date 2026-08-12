---
type: paradigma-plan
title: "Iteration 5-D 工作流运维与可观测性计划"
description: "固定工作流异常对象、管理员动作授权、人工重放幂等、指标与统一 trace 契约。"
tags: [plan, active, workflow-graph, iteration-5, operations, observability]
timestamp: 2026-08-12T14:25:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: decision
  plan_status: in-progress
  retrieval_hints:
    zh: [Iteration 5-D, 工作流运维, Outbox 重放, 卡死 Run, projection lag, trace]
    en: [Iteration 5-D, workflow operations, outbox replay, stalled run, projection lag, trace]
  relations:
    depends_on:
      - ./2026-08-12-iteration5c-shadow-comparison-plan.md
      - ../contracts/projection-contract.md
    related_to:
      - ./2026-08-11-f05-iteration5-6-sequencing-plan.md
      - ../domains/workflow-graph-engine.md
---

# Iteration 5-D 工作流运维与可观测性计划

> **计划状态：ENGINEERING COMPLETE / TARGET EVIDENCE PENDING**
> **前置条件**：Iteration 5-A/B/C 工程实现完成；5-E 读侧切流保持关闭。
> **目标**：让系统管理员能定位异常、执行受控恢复并留下审计证据，同时为 5-E 提供可量化的投影健康指标。

## 1. 边界与权限

- 运维工作台与全部运维动作仅对 `admin` 开放；无权限用户统一返回 404，避免暴露运行时拓扑和异常详情。
- 系统管理员只维护系统，不参与任务交付或业务审批。5-D 的动作只改变运行时技术状态，不获得任何业务验收权。
- 本批不切换 Task Center、Run shell、Timeline 的正式读路径，不停止兼容写入，不删除旧结构。
- UI 和 API 不回显交付物、评论、附件正文或完整事件 payload；链路页只显示标识符、事件类型、时间和 payload 字段名。

## 2. 运维对象与异常口径

工作台聚合以下数据源，而不是复制一套新的异常账本：

1. `workflow_operational_incidents`：展示现有持久化 incident，并支持带原因的 `resolved/ignored` 处置；同一 fingerprint 再次出现时自动重新打开并清空旧处置人/原因。
2. `workflow_outbox_events`：列出 `FAILED` 事件；管理员可填写原因后手动重放。重放把事件恢复到 `RETRYING`、清零自动重试计数并记录操作人、时间、原因和累计人工重放次数。
3. Runtime 派生异常：
   - `failed_run` / `no_route`：Run 为 `failed`，细分类读取 `diagnostics.code`；
   - `stalled_run`：Run 为 `active`，不存在 `ACTIVATED/ACKNOWLEDGED` 节点，且 Runtime 最后更新时间超过阈值；正常等待人工处理的节点不算卡死；
   - `join_wait`：Join activation dependency 仍为 `waiting`，展示等待时长但不自动判定业务故障；
   - `context_conflict`：失败 command receipt 的错误信息为 Context version 冲突；
   - `suspended_node`：Runtime 节点处于 `SUSPENDED`，区分策略阻断与管理员人工挂起。

默认卡死阈值为 30 分钟，API 可在 5–1440 分钟内调整；阈值只影响诊断展示，不自动修改业务状态。

## 3. 受控动作

- Outbox 重放、节点重试、节点人工挂起/恢复、incident 处置均要求原因，并使用 `X-Command-ID` 进入 durable command receipt；相同 actor、命令类型、command id 和 payload 重放只返回既有结果。
- 节点重试仅接受 Runtime `FAILED/SUSPENDED` 的已注册 Handler，复用现有 `retry_node_instance()`，不绕过 Handler。
- 人工挂起只接受可中断 Handler 的 `ACTIVATED/ACKNOWLEDGED` 节点；原 engine/business state、操作人、原因和时间写入节点配置。恢复只接受带人工挂起标记的节点，并恢复原状态；策略阻断产生的 `SUSPENDED` 不能借该入口绕过审批策略。
- 自动节点（如 Notice）不可人工挂起。已完成、终止或取消的 Run 不可执行恢复动作。
- 所有动作追加 Runtime event；Task projection 仍由既有 projector 消费事件刷新，不在运维路由直接写读模型。

## 4. 指标与 trace 契约

指标快照至少包含：

- Run：`active/failed/pending/completed/cancelled/terminated` 数量、卡死 Run 数、挂起节点数；
- Join：waiting dependency 数及最老等待秒数；
- Outbox：各状态数量、backlog（`pending/retrying/failed`）及最老积压秒数；
- Projection：各 stream checkpoint 状态、累计处理数、源事件 backlog、最后成功时间与 lag 秒数；
- Shadow：最新 scan 的 outcome/severity 汇总，作为 5-E 门禁证据，不在 5-D 自动放行。

新 Runtime event 可持久化 `request_id`、`command_id`、`correlation_id`、`instance_id`、`node_instance_id` 和 `task_id`。历史事件字段允许为空，不猜测回填。管理员可按上述任一标识精确检索；结果不返回 payload 值。

## 5. 交付顺序与验收

1. 先补迁移、schema/service/API 的失败测试和权限测试。
2. 实现指标快照、异常列表、trace 检索及四类受控动作。
3. 新增管理员“工作流运维”前端入口，覆盖指标、异常、Outbox、incident 与 trace；危险动作均需填写原因并二次确认。
4. 执行 Alembic 单 head、SQLite upgrade/downgrade、后端全量、前端测试/typecheck/build、Memory-Bank 检查。
5. 工程完成后仍将 5-E 标为 blocked，直到 PostgreSQL head↔base、rebuild/full shadow、目标环境持续样本和人工批准全部完成。

## 5.1 完成证据

- Admin-only dashboard/trace/action API 与前端“工作流运维”入口完成；员工/HR 前后端均不可进入。
- `20260812_04` 完成 Outbox/incident 人工审计字段和 Run Event trace 标识；历史值保持 nullable，不猜测回填。
- SQLite pre-projection expand→head→downgrade、PostgreSQL `20260812_03:20260812_04` 增量离线 SQL通过；Alembic 单 head 前进至 `20260812_04`。
- 后端全量与前端 74 files / 214 tests 通过；前端 type-check 和 production build 通过。
- 正式 Task Center/Run/Timeline 读路径、ROOT shell、业务授权与兼容写入均未切换。

## 6. 非目标

- 不让管理员代替负责人完成、验收或审批业务任务。
- 不自动重放 FAILED Outbox，不自动恢复卡死 Run，不自动忽略 incident。
- 不在日志或前端展示敏感业务 payload。
- 不实现 Iteration 6 的兼容层删除。

# Status

Machine status: in-progress.
