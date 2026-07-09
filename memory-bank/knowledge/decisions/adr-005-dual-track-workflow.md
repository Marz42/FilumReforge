---
type: paradigma-decision
title: "ADR-005: 工作流双轨"
description: "图引擎与Legacy E并存至B-12统一。"
tags: ["adr", "工作流双轨", "图引擎"]
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.1
  temperature: cold
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["工作流双轨", "图引擎"]
    en: ["dual track", "graph engine"]
---
# ADR-005: 工作流双轨（图引擎 + 工作流 E）

**日期**: 工作流重构 Phase 2–11  
**状态**: 已采纳（过渡态）

**背景**  
图引擎 `WorkflowGraphTemplate` 与 legacy `task_templates`（工作流 E）并存。

**决策**  
手动任务 graph dual-write；任务中心读路径默认 graph-first（`TASK_CENTER_V2_ENABLED=true`）；E 模板实例化保持独立直至产品级统一。

**后果**  
两套入口需文档与测试双覆盖；迁移 CLI 与 feature flag 回退路径已建立。

**2026-06-23 更新（ADR-009）**：**B-12 目标明确为删除 Legacy E runtime、仅保留图引擎**；单步抄送 **F-22**、跨部门 **F-21** 已立项。前端单入口 + 图模板设计器已完成；E API **待 P0 删除**。
