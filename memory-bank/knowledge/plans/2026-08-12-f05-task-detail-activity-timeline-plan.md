---
type: paradigma-plan
title: "2026-08-12 F-05 任务详情活动时间线拆分计划"
description: "提取任务详情活动时间线展示，保持排序、文案、内部评论权限和附件操作不变，不混入 KI-010 重设计。"
tags: [plan, completed, f-05, task-center, frontend, activity-timeline]
timestamp: 2026-08-12T00:00:11+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  plan_status: completed
  retrieval_hints:
    zh: [F-05 活动时间线, 任务留痕展示, 时间线拆分]
    en: [F-05 activity timeline, task trace presentation, timeline split]
  relations:
    depends_on:
      - ./2026-08-11-f05-task-detail-materials-comments-plan.md
    related_to:
      - ../domains/task-center.md
      - ../known-issues/ki-010-activity-timeline-redesign.md
---

# F-05 任务详情活动时间线拆分计划

> **计划状态：COMPLETED** — 现有活动时间线展示和日志摘要已离开 Shell；排序、文案、内部备注和附件操作保持不变，KI-010 仍未实施。

## 边界

- 新组件接收 `TaskActivityEntry[]` 与用户标签解析器，渲染现有评论、内部标记、评论附件、任务日志和空状态。
- `TaskDetailShell` 继续决定时间线是否折叠、何时加载数据，以及 Profile/权限和工作流板块顺序。
- 保持服务端返回顺序、时间格式、日志摘要文案、附件预览/下载能力和既有测试标识。
- 工作流 Run Event 和节点列表不在本批迁移；完成后再评估是否需要独立的工作流详情编排批次。

## 测试与完成标准

1. 先覆盖空状态、评论/内部标记/附件和关键日志摘要。
2. 保留 Shell 数据、动作、协作与 `TasksView` 集成回归。
3. 全量 unit、type-check、ESLint、Oxlint 和 build 通过。
4. Shell 不再承担 Task Activity 的逐项模板与日志摘要格式化，但不以机械追求单文件行数作为唯一标准。

# Status

Machine status: completed.
