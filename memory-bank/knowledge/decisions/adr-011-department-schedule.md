---
type: paradigma-decision
title: "ADR-011: 部门周期调度"
description: "部门图模板周期调度。"
tags: ["adr", "部门调度", "F-24"]
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.1
  temperature: cold
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["部门调度", "F-24"]
    en: ["department schedule", "F-24"]
---
# ADR-011: 部门图模板周期调度（F-24 / W-04）

**日期**: 2026-06-23  
**状态**: 已采纳  
**背景**: 产品审阅 F-24 细化方案；替代 Legacy E `TaskSchedule`（B-12 已 no-op）。

**决策**

1. **实体**：`workflow_graph_template_schedules` — 绑定 **ACTIVE** 且 `config.schedulable=true` 的图模板。
2. **范围**：`scope_mode=self` 或 `subtree`（递归含所有 **active** 子部门）；可 **exclude_department_ids** / **exclude_user_ids**；参与人 **all/subset** 可编辑。
3. **触发**：部门 **manager** 为 actor；每部门每 tick 一个 **batch** Run；**禁止** streaming / production 模板。
4. **重叠**：`skip_if_active` 固定开启；**发布/启用调度时**校验目标部门无同模板 ACTIVE Run。
5. **入口**：任务中心 **建立任务** Dialog → Tab「单步任务 | **定时派发**」。
6. **通知**：创建/更新启用时向相关部门 manager 发送「您有一个新的周期任务，下一次开始于 …」。
7. **立即执行**：`POST .../schedules/{id}/run-now` 允许。
8. **Worker**：复用 `run_due_task_schedules_job`，ARQ cron 每 5 分钟扫描。

**后果**  
API `/workflow-graph/schedules`；设计器 **schedulable** 开关；Legacy `/task-templates/schedules` 废弃。
