---
type: paradigma-session-log
title: Fix Template Scope Tree-Select Binding
description: 修复设计器作用范围 el-tree-select 未按 id 绑定导致始终保存为 global，并校正列表按 scope_mode 过滤。
tags: [session, progress, workflow-template, scope, bugfix]
timestamp: 2026-08-04T11:24:00+08:00
paradigma:
  layer: log
  lifecycle: append-only
  okf_export: optional
  update_policy: append-only
---

# Session Summary

## User Goal

- 手动测试发现可用部门逻辑异常：无论选择哪些部门都显示「已对所有部门可用」。定位后要求完成 P0（修复）与 P1（回归测试）。

## Actions Taken

- 根因：设计器 `el-tree-select` 节点使用 `id`，未设置 `props.value = 'id'`，v-model 无法写入部门 UUID，保存时 `scope_mode` 静默落成 `global`。
- 新增 `departmentTreeSelect` 工具：递归映射部门树、归一化部门 ID、解析 scope_mode。
- 设计器绑定 `:props` / `node-key`，保存时规范化 `scope_department_ids`。
- 列表过滤改为仅当 `scope_mode == departments` 时按部门交集过滤，空部门列表不再被当成全公司可见。
- 补充 util/设计器 Vitest 与后端列表回归用例。

## Files Modified

- `frontend/src/utils/departmentTreeSelect.ts`（新增）
- `frontend/src/views/GraphTemplateDesignerView.vue`
- `frontend/tests/departmentTreeSelect.spec.ts`（新增）
- `frontend/tests/GraphTemplateDesignerView.spec.ts`
- `backend/app/api/routes/workflow_graph_engine.py`
- `backend/tests/test_recent_regressions.py`
- `memory-bank/runtime/active-task.md`

## Decisions Accepted

- 存量误标 `global` 的 ACTIVE 模板继续按 ADR-020：另存新版本后修正，不开放 global→departments 原地缩小。

## Verification

- Frontend：`vitest --run tests/departmentTreeSelect.spec.ts tests/GraphTemplateDesignerView.spec.ts` → 6 passed
- Backend：相关 `test_recent_regressions` 两个 scope 列表用例 → passed

## Follow-ups

- 手动复测：草稿选部门 → 保存/发布 → 「可用部门」应展示部门模式而非「已对所有部门可用」。
- 误存为 global 的已发布模板：另存新版本后重选部门。
