---
type: paradigma-plan
title: "模板范围与父子依赖数据治理计划"
description: "为主开发线补齐只读数据盘点、分级修正建议和安全的新版本处理入口。"
tags: [plan, workflow-template, availability-scope, governance, iteration-4]
timestamp: 2026-08-10T00:20:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [模板数据检查, 可用部门, 父子模板, 修正版]
    en: [template governance, availability scope, template dependency, repair version]
  relations:
    depends_on:
      - ../decisions/adr-020-published-template-availability-scope.md
      - ./2026-08-09-rc-employee-trial-plan.md
    validates:
      - ../manuals/2026-08-09-production-release-checklist.md
---

# 模板范围与父子依赖数据治理计划

> **计划状态：COMPLETED（工程）** — 只读审计、分级建议和修正版入口已交付；目标环境数据清零由 UAT/上线清单跟踪。

## 目标

让模板管理员不用直接查数据库，也能盘点上线清单 B-06 的真实风险，并沿现有版本治理规则安全修正：草稿原地编辑，ACTIVE 模板只派生新版本，不自动缩权、不隐式修改父子模板。

## 本批边界

- 覆盖 ACTIVE/DRAFT 模板的可用范围和模板依赖。
- 读取全部模板版本只用于判断目标是否已归档、是否存在新 ACTIVE 版本。
- `global` 只能报告为“需人工确认”，系统不猜测应该授权哪些部门。
- 不改动 KI-011、系统管理员业务边界、I3-F 生产切流或 `v0.93.0-rc.1` 标签。

## 检查规则

| 分类 | 检查 | 分级 |
|------|------|------|
| 可用范围 | ACTIVE global 是否为明确授权 | review |
| 可用范围 | global 仍残留部门编号 | warning |
| 可用范围 | departments 为空、部门缺失或已停用 | error |
| 模板依赖 | 顶层/节点 `child_template_code` 不存在、未发布或指向旧版本 | error |
| 模板依赖 | `on_complete.next_template_code` 无 ACTIVE 目标 | error |
| 模板依赖 | 父模板可用范围不是子模板范围的子集 | error |

## 交付

- Backend：`WorkflowGraphTemplateGovernanceService` 与 `GET /api/v1/workflow-graph/templates/governance-audit`。
- Frontend：任务模板页“数据检查”入口、分级问题列表、打开草稿/新建修正版动作。
- Safety：接口只读；所有 ACTIVE 修正继续复用版本派生 API。
- Tests：后端规则测试、前端报告与动作测试，并纳入全量单元/类型/构建回归。

## 验收

1. 目标环境报告能够列出 intentional global 待确认项和确定错误。
2. 业务负责人逐项确认 global 授权。
3. 草稿直接修正；ACTIVE 通过新版本修正并重新发布。
4. 父模板引用新子版本时同步更新 `child_template_code`，再次检查为 `error=0`。

## 状态

工程实现、本地自动化验证与提交已完成；等待目标环境/用户验收。
