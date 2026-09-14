---
type: paradigma-manual
title: "W11 首片：档案/岗位 JSON 改为结构化字段编辑"
description: "人员管理页用 RecordFieldsEditor 替代原始 JSON 文本框，保留高级 JSON 入口与未知字段 round-trip。"
tags: [w11, hr, people-management, structured-fields]
timestamp: 2026-09-14T13:20:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [W11, 结构化字段, 动态字段, JSON 编辑]
    en: [W11, structured fields, custom_fields, JSON editor]
  relations:
    related_to:
      - ../plans/2026-09-10-integrated-development-and-human-gates-plan.md
      - ../domains/hr-org.md
---

# W11 首片：结构化字段编辑

## 范围

- 人员管理：档案动态字段、岗位扩展配置、生命周期载荷改为表单编辑
- 已发布的 `custom` 字段定义渲染为带标签输入；其余键作为可删附加行
- 保留「高级 JSON」入口；未知字段 round-trip 不丢失

## 不做（本片）

- 独立岗位工作台读模型/影响范围预览（W11 项 1）
- 模板页信息架构重组（W11 项 3–5）
- ProfilesView 遗留页同步（未挂路由）

## 验证

- `frontend/tests/recordFields.spec.ts`
- `frontend/tests/RecordFieldsEditor.spec.ts`
- `frontend/tests/PeopleManagementView.spec.ts`
