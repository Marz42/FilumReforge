---
type: paradigma-manual
title: "W11-C 可无损结构化配置"
description: "launch/context/routing 可结构化子集清单；复合 all/any 必须高级 JSON，禁止静默降级。"
tags: [w11, graph-template, authoring, structured-fields]
timestamp: 2026-09-14T15:10:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [结构化配置, W11-C, launch_schema, routing_rules]
    en: [structured authoring, W11-C, launch_schema, routing_rules]
  relations:
    related_to:
      - ../plans/2026-09-10-integrated-development-and-human-gates-plan.md
      - ./2026-09-14-w11-structured-profile-fields.md
      - ./2026-09-14-w11b-template-ia.md
---

# W11-C 可无损结构化配置

设计器分区见 [W11-B](./2026-09-14-w11b-template-ia.md)。本片只固定「哪些字段可进结构化表单」。

## 可无损结构化字段清单

| 区域 | 可结构化 | 必须高级 JSON |
|---|---|---|
| launch_schema | `fields[]` 的 key/label/type/required/policy_ref | 额外字段键、非数组 fields |
| context_schema | flat 或 JSON Schema object properties 标量类型 | 嵌套组合 schema |
| routing_rules | 扁平 IF/ELSE（field/op/value → target） | 嵌套 `all`/`any` 复合条件 |

切换到结构化失败时保留 JSON 模式并提示，禁止静默降级（`structuredCompatible` 守卫）。

## 验证

- `frontend/tests/graphTemplateAuthoring.spec.ts`
- Designer section tabs `data-testid="designer-section-tabs"`
