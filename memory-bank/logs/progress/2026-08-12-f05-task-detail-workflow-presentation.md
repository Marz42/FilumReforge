---
type: paradigma-log
title: "2026-08-12 F-05 任务详情工作流展示收口"
description: "提取 capability 工作流面板、Run Event 与图节点追踪展示，完成 TaskDetailShell 拆分。"
tags: [progress, frontend, task-center, f-05, workflow-presentation, telemetry]
timestamp: 2026-08-12T00:24:05+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: append-only
  update_policy: append-only
  epistemic_status: confirmed
  retrieval_hints:
    zh: [F-05 完成, 工作流展示, Run Event, 图节点追踪]
    en: [F-05 complete, workflow presentation, run events, graph telemetry]
---

# F-05 任务详情工作流展示收口

## Outcome

- 新增 `TaskDetailWorkflowPresentation`，按 domain-neutral Profile/capability 选择 Tracking、Run Dashboard、Capture、Deliverable 与 Aggregate 兼容面板，并承接最近 Run Event。
- 新边界继续向页头暴露 Deliverable `submit()` / `submitting`，原“上传并提交”动作和刷新语义不变。
- 新增 `TaskDetailGraphTelemetry`，承接 compact/full 节点追踪、状态、迭代版本、耗时与终止提示。
- `TaskDetailShell` 从约 1,153 行降至约 838 行，剩余职责为数据/权限/Profile 编排、标准任务表单、关注人、页头和动作对话框；F-05 完成。
- `Video*` 组件仅作为现有展示适配器被组合，没有新增视频专用业务判断。

## Test-first and Verification

- 两个组件不存在时 5 条定向测试先按预期失败；实现后 capability 面板选择、页头句柄、最近三条 Run Event、compact/full 节点追踪全部通过。
- 迁移回归：6 files / 29 tests PASS。
- 前端全量：73 files / 211 tests PASS。
- type-check、ESLint、Oxlint、production build 与 `git diff --check` PASS。
- 构建仍保留约 809 KB Element Plus 主包既有性能 warning，不由本批引入。

## Next

- 主开发线进入 Iteration 5-A：先固定 `task_center_items`、`process_run_summaries`、`node_timeline_entries` 的字段、所有权、授权、排序和重建边界，再做 Expand-only 加法迁移。
- RC2 员工复测、Iteration 4/设计器/S-01 人工 UAT、Iteration 3-F 目标环境证据继续并行，不阻止 5-A～5-D，但阻止 5-E 生产读侧切流。
