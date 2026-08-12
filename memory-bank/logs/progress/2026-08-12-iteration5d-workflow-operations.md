---
type: paradigma-progress
title: "Iteration 5-D 工作流运维与可观测性工程完成"
description: "完成管理员异常工作台、受控恢复、投影健康、统一 trace 与运维审计迁移。"
tags: [progress, workflow-graph, iteration-5, operations, observability]
timestamp: 2026-08-12T14:25:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: verified
  relations:
    depends_on:
      - ../../knowledge/plans/2026-08-12-iteration5d-operations-observability-plan.md
      - ../../knowledge/contracts/projection-contract.md
---

# Iteration 5-D 工作流运维与可观测性工程完成

## 交付

- 新增 Admin-only `GET /workflow-graph/admin/operations`：聚合 Run 状态、failed/stalled/no-route、挂起/失败节点、Join wait、Context conflict、Outbox backlog、projection checkpoint/lag、最新 shadow 和持久 incident。
- 新增受控动作：FAILED Outbox 人工重放、incident `resolved/ignored`、节点 retry、可中断 active 节点 suspend 及人工挂起 resume。动作必须填写原因并通过 durable command receipt 幂等执行。
- 人工挂起保存原 engine/business state、操作人、时间和原因；resume 只接受 `operational_suspension.status=active`，不会把审批策略产生的 `SUSPENDED` 当成人工挂起恢复。
- `20260812_04` 为 Outbox 增加人工重放审计，为 incident 增加 resolver/note，为 Run Event 增加 nullable request/node/task trace 标识；历史行不猜测回填。
- 新增 Admin-only `GET /workflow-graph/admin/operations/traces`，可按 request/command/correlation/Run/Node/Task 精确过滤；响应只返回 payload 字段名，不返回业务值。
- 前端增加“工作流运维”导航与页面，覆盖指标、异常、FAILED Outbox、incident、投影健康、节点受控动作和 trace；员工/HR 不显示入口，后端同样返回 404。

## 权限与不变量

- 系统管理员的动作是技术恢复，不是业务交付、验收或审批；5-D 没有扩大业务对象授权。
- 正式 Task Center/Run/Timeline 仍走现行动态 graph-first 路径；未切换 5-E、未停止兼容写入、未改变 ROOT shell。
- 派生异常直接来自 Runtime/receipt/dependency/checkpoint，不复制为新的业务异常账本。

## 验证

- 测试先行覆盖 dashboard 指标/隐私、Outbox 审计、incident reopen、节点挂起恢复边界、trace 信封、Admin-only API、前端重放与路由权限。
- Alembic 单 head `20260812_04`；SQLite pre-projection expand→head→downgrade PASS。
- PostgreSQL `20260812_03:20260812_04` 增量离线 SQL PASS；真实 PostgreSQL head↔base 仍待目标环境补证。
- 后端全量 **494 collected / 462 passed / 32 skipped / 0 failed**；前端 Vitest **74 files / 214 tests PASS**，type-check、ESLint、Oxlint 与 production build PASS。

## 后续门禁

- 5-E 是下一阶段但保持 blocked：必须先在真实 PostgreSQL 升至 `20260812_04`，执行 projection rebuild + full shadow，保留持续差异/lag 样本并校验 5-D 运维看板。
- RC2 员工复测、Iteration 4/设计器/S-01 人工 UAT、I3-F 7 天观测和生产上线清单继续独立推进。
- 上述证据齐全后仍需用户单独批准 5-E；不得把工程完成等同于生产切流批准。
