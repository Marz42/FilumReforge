---
type: paradigma-plan
title: "2026-08-12 F-05 任务详情工作流展示收口计划"
description: "提取 capability 工作流面板、Run Event 与图节点追踪展示，保留权限、动作和页头提交语义。"
tags: [plan, completed, f-05, task-center, frontend, workflow-presentation, telemetry]
timestamp: 2026-08-12T00:12:06+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [F-05 工作流面板, Run Event, 图节点追踪, 壳层收口]
    en: [F-05 workflow panels, run events, graph telemetry, shell completion]
  relations:
    depends_on:
      - ./2026-08-12-f05-task-detail-activity-timeline-plan.md
    related_to:
      - ../domains/task-center.md
      - ./2026-08-11-f05-iteration5-6-sequencing-plan.md
---

# F-05 任务详情工作流展示收口计划

> **计划状态：COMPLETED** — capability 工作流面板、Run Event 与图节点追踪已离开 Shell；Runtime、capability、Profile、权限、动作及页头提交语义保持不变，F-05 至此结束。

## 边界

- 提取 capability 驱动的 Tracking、Run Dashboard、Capture、Deliverable、Aggregate 面板及 Run Event 展示。
- 新边界继续向页头暴露现有 Deliverable `submit()` / `submitting` 句柄，保持“上传并提交”按钮行为。
- 提取 compact/full 两种图节点追踪展示，消除 Shell 内重复节点卡片模板。
- Shell 保留权限/Profile 计算、动作 composable、标准任务交付/验收表单、关注人、页头、延期和动作对话框。
- `Video*` 命名组件仍只是兼容展示适配器；本批不新增视频专用业务判断，也不重命名后端契约。

## 测试与完成标准

1. 测试先行覆盖 capability 面板选择、Run Event 紧凑模式、节点状态/版本/终止提示和页头提交句柄。
2. 保留 F-05 数据、动作、协作、活动时间线和任务中心集成回归。
3. 全量 unit、type-check、ESLint、Oxlint 和 build 通过。
4. Shell 剩余职责均属于详情壳层编排；若无新的独立高内聚板块，结束 F-05 并进入 Iteration 5-A。
