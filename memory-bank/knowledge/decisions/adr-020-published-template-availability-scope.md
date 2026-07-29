---
type: paradigma-decision
title: "ADR-020: 已发布模板可用范围作为可变治理元数据"
description: "规定 ACTIVE 工作流模板可原地扩大部门可用范围，但缩小范围必须发布新版本，并对每次授权持久化审计。"
tags: [adr, workflow-template, authorization, audit]
timestamp: 2026-07-30T02:18:18+08:00
paradigma:
  schema_version: "0.2"
  temperature: cold
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: [已发布模板, 可用部门, 增量授权, 范围审计]
    en: [published template, availability scope, additive grant, scope audit]
  relations:
    informs:
      - ../domains/workflow-graph-engine.md
      - ../contracts/data-contracts.md
    implements:
      - ../plans/2026-07-30-template-availability-paradigma-upgrade-plan.md
---

# Context

工作流定义发布后不可原地修改，避免已有 Run 与模板定义漂移。但 `scope_department_ids` 同时承担模板可见、可发起和子模板执行准入；为新增试用部门而派生父子模板新版本，会改变精确 template code，并可能让已有父 Run 在后续 fork 时找不到已归档子模板。

# Decision

- 将模板 availability scope 视为定义之外的治理元数据。
- ACTIVE 模板允许原地、单调地扩大范围：增加部门，或从部门范围扩大为 global。
- ACTIVE 模板禁止移除部门或从 global 收缩；缩小范围必须通过新模板版本完成。
- 草稿模板继续在设计器中完整编辑 scope；归档模板不可授权。
- 授权目标必须是活跃部门；部门经理只能加入其有效管理范围内的部门，只有全局管理角色可扩大为 global。
- 每次变更必须与模板 scope 同事务写入独立审计事件，包含 actor、前后范围、新增部门、原因和时间。
- 能力保持领域中立；不按视频、模板 code、节点名或 run kind 分支。

# Consequences

- 新部门可使用既有已发布模板，不需要重建模板版本，已有 Run 和 definition snapshot 不变。
- 视频父子模板仍需分别授权；系统不会根据业务命名隐式级联。
- 全局范围一旦发布，不能通过该接口原地缩小。
- 新增一张审计表和两个模板管理 API，部署前必须执行 Alembic migration。

# Alternatives Considered

1. **每次变更都派生模板版本**：保持绝对不可变，但精确 child template code 会影响已有父 Run，运维风险更高。
2. **直接修改数据库 JSON**：能快速扩容，但没有权限、有效性校验与审计，不可接受。
3. **按视频模板自动级联父子模板**：操作方便，但重新引入视频特殊性，违背 ADR-018。

# Status

Accepted — 2026-07-30，用户同意并进入实现。

# Related Documents

- [ADR-018](./adr-018-domain-neutral-workflow-templates.md)
- [实施计划](../plans/2026-07-30-template-availability-paradigma-upgrade-plan.md)
- [工作流图引擎](../domains/workflow-graph-engine.md)
- [数据契约](../contracts/data-contracts.md)
