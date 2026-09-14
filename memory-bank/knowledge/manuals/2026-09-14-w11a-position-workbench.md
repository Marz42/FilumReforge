---
type: paradigma-manual
title: "W11-A 岗位工作台只读影响预览"
description: "岗位目录聚合任职/汇报影响计数，详情展示任职人员与派生汇报链。"
tags: [w11, position-workbench, hr]
timestamp: 2026-09-14T14:50:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [岗位工作台, 影响预览, W11-A]
    en: [position workbench, impact preview, W11-A]
  relations:
    related_to:
      - ../plans/2026-09-10-integrated-development-and-human-gates-plan.md
      - ./2026-09-14-w11-structured-profile-fields.md
---

# W11-A 岗位工作台

## 范围

- `GET /positions/workbench` 目录 + 影响计数
- `GET /positions/{id}/workbench` 任职明细 + 派生汇报线 + 生效区间
- 人员管理「岗位/汇报」区嵌入 `PositionWorkbenchPanel`

## 验证

- `backend/tests/test_w11_position_workbench.py`
