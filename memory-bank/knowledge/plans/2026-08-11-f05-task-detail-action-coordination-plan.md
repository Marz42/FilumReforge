---
type: paradigma-plan
title: "2026-08-11 F-05 任务详情动作协调拆分计划"
description: "从 TaskDetailShell 提取状态流转、交付验收、握手转办和管理动作的提交状态与命令协调。"
tags: [plan, frontend, task-center, f-05, refactor, actions]
timestamp: 2026-08-11T23:15:47+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  plan_status: completed
  retrieval_hints:
    zh: [F-05 动作协调, 任务动作提交, 交付验收, 握手转办]
    en: [F-05 action coordination, task commands, deliverable review, delegation]
  relations:
    depends_on:
      - 2026-08-10-f05-task-detail-data-coordination-plan.md
    related_to:
      - ../domains/task-center.md
---

# F-05 任务详情动作协调拆分计划

> **计划状态：COMPLETED** — 动作与接单/转办协调已经提取；下一批见资料附件与评论留痕拆分计划。

## 问题

数据协调首批完成后，`TaskDetailShell.vue` 仍约 1,895 行，并直接维护状态流转、交付提交/验收、审批驳回、接单握手、转办、集合关闭和延期的表单、loading、API 调用、消息与刷新。页面编排和命令副作用耦合，使后续资料/评论板块拆分容易重复刷新或改变既有动作语义。

## 本批边界

- 新增 `useTaskDetailActions`，集中管理通用状态流转、交付提交/验收、审批驳回、接单/退回/转办、集合关闭、延期和动作后刷新。
- composable 接收当前任务、图实例、用户/候选项和刷新回调；不自行读取任务详情，不复制权限判断。
- Shell 继续负责“按钮是否出现/是否可用”的权限与 Profile 推导；composable 只执行已经由 UI 触发的命令，并保留后端最终授权。
- 评论、任务资料附件、关注人以及它们的上传/提交状态留在 Shell，作为下一批独立板块拆分范围。
- 不修改 API、payload、成功/失败文案、对话框交互、`actionDone` 时机或 graph-first/standalone 分流。

## 回归出口

- composable 单测覆盖：状态流转、交付验收、驳回原因校验、standalone 候选加载与转办、动作失败不刷新且 loading 复位。
- 既有 `TasksView` 验收与握手集成测试、`TaskDetailShellData` 单次加载回归保持通过。
- 前端全量单测、type-check、ESLint、Oxlint 与 production build 通过。
- `TaskDetailShell.vue` 只保留动作权限推导和模板绑定，动作命令实现不再内联。

## 后续 F-05

下一批优先拆出“任务资料附件”和“评论与留痕”板块及其上传状态；之后重新评估 Shell 余下的活动时间线/工作流面板编排。F-05 完成标准仍是职责边界清晰，不以机械追求单文件行数为唯一指标。

## 实施结果

- `TaskDetailShell.vue` 从约 1,895 行降至约 1,569 行；模板和权限计算保持在 Shell。
- `useTaskDetailActions.ts` 304 行，负责通用命令、表单、loading 与动作后刷新；`useTaskAssignmentActions.ts` 178 行，负责接单/退回/转办及候选加载。
- 新增 6 项 composable 回归；前端全量 69 files / 197 tests、type-check、ESLint、Oxlint 与 production build 通过。

# Status

Machine status: completed.
