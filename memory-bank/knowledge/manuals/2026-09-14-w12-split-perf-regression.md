---
type: paradigma-manual
title: "W12 职责拆分、组织树测量与关键回归"
description: "TaskService/WorkflowGraphService query mixin 拆分；组织树 build_tree 规模样本；critical_path 回归入口。"
tags: [w12, architecture, performance, regression]
timestamp: 2026-09-14T15:30:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [W12, TaskService拆分, 组织树性能, 关键回归]
    en: [W12, TaskService split, org tree perf, critical path]
  relations:
    related_to:
      - ../plans/2026-09-10-integrated-development-and-human-gates-plan.md
      - ../domains/architecture/backend-architecture.md
---

# W12

## A/B 拆分

- `TaskServiceQueryMixin` ← list/inbox/board/stats/gantt 等读模型；门面仍为 `TaskService`
- `WorkflowGraphQueryMixin` ← get/list instance/template/department runs；命令/outbox 仍在 `WorkflowGraphService`
- 公共 API 与 write owner 不变；不因拆文件跨域写

## C 组织树

- `DepartmentService.build_tree` 已是单次列表 + O(n) children_map
- 样本：20×25 深链 ≈ 501 节点；本地 `build_tree` < 50ms（见 `test_w12_org_tree_perf.py`）
- **结论：** 无证据支持引入缓存；部门变更路径保持现有写后读一致性，不做受控缓存

## D 关键回归入口

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -m critical_path -q
```

覆盖通知/W08、worker 投影、HR/W10、知识库与 AI 相关既有用例（按 marker 聚合，不扩大 AI 写权限）。
