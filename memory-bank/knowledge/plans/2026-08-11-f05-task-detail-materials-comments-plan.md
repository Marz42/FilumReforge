---
type: paradigma-plan
title: "2026-08-11 F-05 任务资料与评论留痕拆分计划"
description: "从 TaskDetailShell 提取附件、评论与留痕协调，保持权限、上传预算、刷新时机和 UI 语义不变。"
tags: [plan, completed, f-05, task-center, frontend, attachment, comment]
timestamp: 2026-08-11T23:42:43+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  plan_status: completed
  retrieval_hints:
    zh: [F-05 资料附件, 评论留痕, 上传协调, 任务详情拆分]
    en: [F-05 attachments, comments, activity trace, task detail split]
  relations:
    depends_on:
      - ./2026-08-11-f05-task-detail-action-coordination-plan.md
    related_to:
      - ../domains/task-center.md
---

# F-05 任务资料与评论留痕拆分计划

> **计划状态：COMPLETED** — F-05 第三批已交付；附件、评论和留痕协调已离开 Shell，API、权限和页面语义保持不变。下一批见活动时间线拆分计划。

## 边界

- Shell 继续负责选中任务、权限/Profile、详情板块编排和跨板块刷新。
- 新边界接管附件选择/上传/复位、评论输入/提交/复位，以及对应 loading/error 状态。
- 附件可见性、文件大小/数量/类型预算、内部评论权限和 `actionDone`/reload 时机保持不变。
- 不在本批重设计活动时间线，不改变评论文案、附件布局和 API payload。

## 测试先行

1. 先覆盖上传成功、上传失败、空选择、文件复位和刷新。
2. 覆盖评论成功、评论失败、空白评论拒绝、输入复位和刷新。
3. 保留 `TaskDetailShellData`、`TasksView` 与现有动作协调回归。
4. 完成全量 unit、type-check、ESLint、Oxlint 和 build。

## 完成标准

- Shell 不再直接组织附件上传和评论提交命令；
- 权限条件、模板绑定和页面结构没有变化；
- 新边界规模可维护，不把附件与评论之外的职责吸入新巨石；
- 完成后重新盘点活动时间线/工作流面板，决定 F-05 是否还需第四批。

# Status

Machine status: completed.
