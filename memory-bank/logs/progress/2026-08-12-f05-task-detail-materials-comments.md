---
type: paradigma-log
title: "2026-08-12 F-05 任务资料附件与评论留痕拆分"
description: "提取附件、评论协调和独立展示板块，保持权限、payload、附件预算与刷新语义不变。"
tags: [progress, frontend, task-center, f-05, refactor, attachment, comment]
timestamp: 2026-08-12T00:00:11+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: append-only
  update_policy: append-only
  epistemic_status: confirmed
  retrieval_hints:
    zh: [F-05 资料评论完成, 附件上传协调, 评论留痕拆分]
    en: [F-05 materials comments complete, attachment upload, comment trace]
---

# F-05 任务资料附件与评论留痕拆分

## Outcome

- 新增 `useTaskDetailCollaboration`，统一任务资料多文件上传、评论提交、成功/失败状态、表单复位与详情刷新。
- 新增 `TaskDetailAttachmentsPanel` 和 `TaskDetailCommentComposer`，保留附件左右拉伸布局、折叠 Profile、内部评论开关、评论附件和既有测试锚点。
- `TaskDetailShell` 继续负责权限/Profile、选中任务、数据加载和页面编排，从约 1,569 行降至约 1,285 行。
- 未改变附件 `target_type=task` / `visibility=private`、评论 payload、文件预算、成功/错误文案或后端授权。

## Test-first and Verification

- 新 composable 不存在时定向测试先按预期失败；实现后 6/6 通过。
- 协作 composable、Shell 数据协调和既有 `TasksView` 集成：3 files / 16 tests PASS。
- 前端全量：70 files / 203 tests PASS。
- type-check、ESLint、Oxlint、production build 与 `git diff --check` PASS。
- 构建仍保留约 809 KB Element Plus 主包既有性能 warning，不由本批引入。

## Assessment and Next

- F-05 尚未完成：Shell 仍约 1,285 行，活动时间线的逐项模板和日志摘要适合形成独立展示边界。
- 下一批只提取现有活动时间线，不混入 KI-010 的事件分组或交互重设计；随后再评估工作流 Run Event/节点/能力面板编排。
- RC2 复测、人工 UAT、I3-F 与生产上线门禁继续独立推进。
