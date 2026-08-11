---
type: paradigma-log
title: "2026-08-12 F-05 任务详情活动时间线拆分"
description: "提取现有活动时间线和日志摘要展示，保持顺序、内部备注与附件操作不变。"
tags: [progress, frontend, task-center, f-05, refactor, activity-timeline]
timestamp: 2026-08-12T00:12:06+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: append-only
  update_policy: append-only
  epistemic_status: confirmed
  retrieval_hints:
    zh: [F-05 活动时间线完成, 日志摘要, 评论附件]
    en: [F-05 activity timeline complete, log summary, comment attachment]
---

# F-05 任务详情活动时间线拆分

## Outcome

- 新增 `TaskDetailActivityTimeline`，承接空状态、评论、内部备注标记、评论附件、任务日志和摘要格式化。
- `TaskDetailShell` 继续决定折叠状态、数据加载、Profile 和板块顺序，从约 1,285 行降至约 1,153 行。
- 服务端活动顺序、时间格式、用户标签回退、附件操作和摘要文案保持不变。
- 本批未实施 KI-010 的事件分组、摘要或交互重设计。

## Test-first and Verification

- 新组件不存在时定向测试先按预期失败；实现后空状态、评论/附件、关键日志摘要 3/3 通过。
- 时间线组件、Shell 数据协调和既有 `TasksView` 集成：3 files / 13 tests PASS。
- 前端全量：71 files / 206 tests PASS。
- type-check、ESLint、Oxlint、production build 与 `git diff --check` PASS。
- 构建仍保留约 809 KB Element Plus 主包既有性能 warning，不由本批引入。

## Assessment and Next

- F-05 仍需一个收口批：capability 工作流面板、Run Event 与 compact/full 图节点追踪仍在 Shell 内形成高内聚展示职责。
- 下一批须保留页头对 Deliverable 面板 `submit()` / `submitting` 的现有联动，不改变权限、Profile、Runtime 或 capability 语义。
- 收口批通过后，若 Shell 剩余内容仅为权限、标准任务表单、关注人、页头和对话框编排，则结束 F-05 并进入 Iteration 5-A。
