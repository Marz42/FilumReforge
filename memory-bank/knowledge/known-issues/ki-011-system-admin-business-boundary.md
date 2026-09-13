---
type: paradigma-known-issue
title: "KI-011: 系统管理员与业务参与权限尚未解耦"
description: "产品定义 Admin 仅负责系统维护，但当前 MANAGEMENT_ROLES、任务/审批 override 与候选链仍允许其参与业务动作。"
tags: ["known-issue", "admin", "authorization", "workflow", "deferred"]
timestamp: 2026-09-13T00:20:00+08:00
paradigma:
  relations:
    related_to:
      - known-issues.md
  schema_version: 0.5.0
  temperature: cold
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["管理员业务边界", "系统管理员", "管理员不参与业务"]
    en: ["system admin business boundary", "admin override", "admin deferred"]
---
# KI-011: 系统管理员与业务参与权限尚未解耦

## 产品边界

系统管理员只负责账号、系统配置、模板/运行异常维护与技术兜底，不承担交付、验收、审批或其他实际业务责任。部门管理者由组织关系推导，不等于 `UserRole.ADMIN`。

## 当前实现差距

- `MANAGEMENT_ROLES` 包含 `ADMIN`，大量 Task / Workflow 动作以此提供业务 override。
- 模板评审候选链会加入系统管理员，且模板 `created_by` 可能被当作 workflow admin 候选。
- 模板任务验收和旧审批引擎允许管理员绕过指定处理人。
- 现有测试数据和兼容路径有管理员直接参与任务/验收的假设。

## 状态

**deferred · 不属于 Iteration 4**（2026-07-29 用户决定）

Iteration 4 不修改上述行为，避免 Handler 化、决策语义迁移与全局权限重构同时发生。当前文档必须把它标为兼容事实，不能宣称管理员业务边界已经落地。

## 后续专项范围

- 区分系统治理能力与业务管理能力。
- 从业务参与者、执行人、验收人、审批人候选中排除系统管理员。
- 将重新指派、解除技术阻塞、取消异常流程等治理动作放入独立且完整审计的管理端口。
- 迁移依赖 `MANAGEMENT_ROLES` 的 API、前端动作和测试数据。
- 确认模板 authoring/seed/deployment 等维护动作不被误删。

## 退出条件

- Admin 不会进入新业务 Run 的参与者和决策者候选。
- Admin 不通过普通业务 endpoint 作出交付/验收/审批决定。
- 技术治理动作具有独立权限、原因、审计与恢复路径。
- 全仓库测试不再依赖管理员充当业务负责人。
