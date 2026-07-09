---
type: paradigma-decision
title: "ADR-008: 图模板设计器"
description: "图模板authoring走表单+表格。"
tags: ["adr", "图模板设计器", "authoring"]
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.1
  temperature: cold
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["图模板设计器", "authoring"]
    en: ["graph template", "designer"]
---
# ADR-008: 图模板设计器 authoring 路径

**日期**: 2026-06-21  
**状态**: 已采纳

**背景**  
TCE Phase 5 移除 Legacy E 前端后，图模板仍依赖 seed 脚本维护；需 UI authoring 且不恢复 E 结构化设计器。

**决策**

1. 图模板 authoring 走 `WorkflowGraphTemplateAdminService` + `GraphTemplateDesignerView`（表单 + 表格，非拖拽 DAG）
2. 新建默认 **clone preset**；有实例时结构锁定，改结构须 fork version
3. D2 起边/routing_rules/拓扑校验纳入 draft save；D3 补 DAG 预览、dry-run、JSON 导入导出、Run 统计
4. Legacy E 设计器 **不恢复**；E 后端删除独立跟踪 **B-12**

**后果**  
与 ADR-005 互补：用户可见模板维护单轨图引擎；E runtime 仍并存至 B-12。测试覆盖 `test_workflow_graph_template_designer_d{1,2,3}` + topology。
