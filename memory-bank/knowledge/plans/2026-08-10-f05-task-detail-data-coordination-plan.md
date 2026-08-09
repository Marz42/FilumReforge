---
type: paradigma-plan
title: "2026-08-10 F-05 任务详情数据协调拆分计划"
description: "从 TaskDetailShell 提取详情加载与刷新协调，消除重复请求和快速切换竞态。"
tags: [plan, frontend, task-center, f-05, refactor]
timestamp: 2026-08-10T17:05:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [F-05 壳层拆分, 任务详情加载, 快速切换竞态]
    en: [F-05 shell split, task detail loading, selection race]
  relations:
    related_to:
      - ../domains/task-center.md
---

# F-05 任务详情数据协调拆分计划

## 问题

`TaskDetailShell.vue` 同时承担数据请求、动作提交、业务权限推导和页面编排。拆分前约 1,989 行，其中详情初始化同时由 `onMounted` 和 immediate watch 触发；任务快速切换时也没有防止较慢旧请求覆盖新选择。

## 本批范围

- 提取 `useTaskDetailData`，集中管理主任务、附件、活动时间线、关注人、图实例/事件、用户和部门参考数据。
- 首次打开只加载任务一次；任务 ID 变化时只启动一次新请求。
- 每次请求使用递增版本；只有最后选择可以写回状态。
- 主任务成功后立即显示，并清空上一任务的附属数据；附件/关注人/活动/图数据独立加载和降级。
- 保留原有活动时间线失败提示、管理角色用户列表和非管理用户本人列表语义。
- 不修改 API、权限、任务动作、模板能力或页面布局。

## 测试出口

- composable：完整加载、快速切换 last-selection-wins、可选数据失败降级、管理/员工参考用户范围。
- 壳层：首次任务只请求一次，切换后只增加一次请求。
- 既有 `TasksView` 握手、开始处理、深度打回版本等集成回归保持通过。
- 前端全量测试、type-check、只读 lint 与 production build 通过。

## 后续 F-05

本批不宣告 F-05 完成。下一批优先把动作提交状态与命令处理提取为 composable，再评估把任务资料/评论展示表单拆成独立板块；每批均保持行为不变并单独提交。
