---
type: paradigma-runtime-state
title: Active Task
description: 修复图模板设计器作用范围 tree-select 绑定与列表 scope_mode 过滤。
tags: [runtime, active-task, workflow-template, scope]
timestamp: 2026-08-09T22:09:00+08:00
paradigma:
  layer: runtime
  temperature: hot
  lifecycle: ephemeral
  okf_export: false
  update_policy: agent-editable
  archive_to: /memory-bank/logs/progress/
---

# Active Task

## Task ID

fix-template-scope-tree-select-2026-08-04

## User Request

P0/P1：修复「可用部门」始终显示全公司可用；根因为设计器作用范围 tree-select 未按 `id` 绑定。

## Current Status

completed — 设计器绑定与列表过滤已修复；已补充 Iteration 4 / 领域中立 / 设计器 Phase 2 UAT checklist。

## Checklist

- [x] 定位 tree-select props / 递归部门树问题
- [x] 修复设计器 scope 保存与 tree-select 绑定
- [x] 列表过滤改为尊重 `scope_mode`
- [x] 补充前端 util/设计器与后端列表回归测试
- [x] 更新 active-task 与 session log
- [x] 编写 UAT checklist 手册并提交工作区更改

## Relevant Knowledge

- `memory-bank/knowledge/decisions/adr-020-published-template-availability-scope.md`
- `memory-bank/knowledge/manuals/2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md`
- `frontend/src/utils/departmentTreeSelect.ts`
- `frontend/src/views/GraphTemplateDesignerView.vue`
- `backend/app/api/routes/workflow_graph_engine.py`

## Blockers

- 无。

## Notes

- 已被误存为 `global` 的 ACTIVE 模板需另存新版本后在草稿中重新选部门再发布（ADR-020 禁止从 global 原地缩回）。
