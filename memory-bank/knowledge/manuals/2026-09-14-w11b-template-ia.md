---
type: paradigma-manual
title: "W11-B 模板页六分区信息架构"
description: "GraphTemplatesPanel 保留清单；设计器用 el-tabs 组织基本信息/步骤节点/运行态/调度/高级配置，不重建 M-06～M-08。"
tags: [w11, template-ia, graph-template-designer]
timestamp: 2026-09-14T15:10:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [模板清单, 设计器分区, W11-B]
    en: [template list, designer sections, W11-B]
  relations:
    related_to:
      - ../plans/2026-09-10-integrated-development-and-human-gates-plan.md
      - ./2026-09-14-w11-structured-profile-fields.md
      - ./2026-09-14-w11a-position-workbench.md
---

# W11-B 模板页信息架构

## 范围

1. **清单** — `GraphTemplatesPanel`（列表/筛选/实例化入口）
2. **基本信息** — 名称、说明、标签、能力、部门作用范围
3. **步骤/节点** — 拓扑预览、节点表、节点 config/routing、边
4. **运行态** — 实例/锁定只读摘要、汇总模式、launch/context schema、根执行人与汇总节点
5. **调度** — schedulable、on_complete 链
6. **高级配置** — participant_policies、department_pools；导入导出仍走页头既有 API

## 约束

- 复用 `frontend/src/api/workflow-graph.ts` 草稿/发布/版本锁定/导入导出/dry-run
- ACTIVE 定义只读由后端权威；前端 `definitionLocked` / `graphLocked` 不变
- 不重建 M-06～M-08

## 验证

```bash
cd frontend
npm run test:unit -- --run tests/GraphTemplatesPanel.spec.ts tests/GraphTemplateDesignerView.spec.ts
```
