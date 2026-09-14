---
type: paradigma-manual
title: "W10 HR 生命周期显式图模板绑定"
description: "记录 employment_events 对 workflow_graph_template 的显式绑定、版本快照、幂等 Run，以及人员管理前端选择器与触发状态展示。"
tags: [w10, hr, lifecycle, graph-template]
timestamp: 2026-09-14T13:30:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [HR生命周期, 图模板绑定, W10, employment_events]
    en: [HR lifecycle, graph template bind, W10]
  relations:
    related_to:
      - ../plans/2026-09-10-integrated-development-and-human-gates-plan.md
      - ../domains/hr-org.md
---

# W10：显式图模板绑定

## 后端（首片）

- 加法列：`workflow_graph_template_id`、`workflow_graph_template_version`、`triggered_workflow_graph_instance_id`
- 创建事件时可显式绑定已发布且可直接实例化的图模板；版本在创建时快照
- Worker `process_employment_event_job` 调用 `instantiate_graph_template`；已有 Run ID 则幂等跳过
- 旧审批流 `workflow_definition_id` 继续兼容；`task_template_id` 仍拒绝（B-12）

## 前端（本片）

- 人员管理「生命周期」页：可选绑定图模板与审批流程
- 事件列表展示 `trigger_status`、图 Run ID、审批实例 ID、`trigger_error`
- 创建时把当前模板 `version` 一并提交（与后端快照一致）

## 不做

- 规则匹配 / 优先级 / dry-run UI（HG-08）
- 目标预发观察或 Phase D

## 配置与注意

- 需要 `WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED=true`
- `payload.participants_snapshot` 应按模板 `participant_policies` 提供；缺省回落到 `assignees=[subject]`
- 离职后主体用户可能不再是部门活跃成员；办理人池应使用仍活跃的 HR 部门成员

## 验证

- `backend/tests/test_w10_hr_graph_template_bind.py`
- `frontend/tests/PeopleManagementView.spec.ts`（含绑定字段提交）
- 既有审批联动幂等回归仍通过
