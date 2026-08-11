---
type: paradigma-log
title: "2026-08-11 F-05 任务详情动作协调拆分"
description: "提取任务动作与接单转办 composable，保持权限、payload、提示和刷新语义不变。"
tags: [progress, frontend, task-center, f-05, refactor, actions]
timestamp: 2026-08-11T23:27:48+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: append-only
  update_policy: append-only
  epistemic_status: confirmed
  retrieval_hints:
    zh: [F-05 动作协调完成, 任务动作 composable, 接单转办]
    en: [F-05 action coordination complete, task actions, assignment actions]
---

# F-05 任务详情动作协调拆分

## Outcome

- 新增 `useTaskDetailActions`：统一通用状态流转、交付提交/验收、审批驳回、集合关闭、延期、对话框/表单/loading 和动作后刷新。
- 新增 `useTaskAssignmentActions`：隔离接单、退回协商、standalone 候选读取和 workflow/standalone 转办文案。
- `TaskDetailShell` 继续唯一负责权限、Profile 和模板条件；API payload、后端最终授权、成功/失败提示与 `actionDone` 时机不变。
- Shell 从约 1,895 行降至约 1,569 行；没有制造新的超 400 行动作文件（304 / 178 行）。

## Test-first and Verification

- 新 composable 不存在时定向测试先按预期失败；实现后 6/6 通过。
- 动作 composable、Shell 数据协调和既有 `TasksView` 集成：3 files / 16 tests PASS。
- 前端全量：69 files / 197 tests PASS。
- type-check、ESLint、Oxlint、production build 与 `git diff --check` PASS。
- 构建仍保留约 809 KB Element Plus 主包既有性能 warning，不由本批引入。

## Next

继续拆分任务资料附件和评论/留痕板块，重点保持附件可见性、文件预算、内部评论权限与刷新边界；RC2 复测、人工 UAT 和 I3-F 外部门禁继续独立推进。
