---
type: paradigma-decision
title: "ADR-019: 按决策对象与动作语义处理参与者重叠"
description: "不以人员身份相等一刀切自审；区分集合推进、独立交付验收、正式业务审批和多人会签。"
tags: ["adr", "workflow-graph", "approval", "human-task", "actor-overlap", "decision-subject"]
timestamp: 2026-07-29T21:42:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["参与者重叠", "集合确认", "独立验收", "正式审批", "自审语义"]
    en: ["actor overlap", "decision subject", "collection finalize", "deliverable acceptance"]
---
# ADR-019: 按决策对象与动作语义处理参与者重叠

**日期**：2026-07-29
**状态**：已采纳；纳入 Iteration 4-B / 4-C 设计
**关联**：[`adr-015-approval-handler-reuse.md`](./adr-015-approval-handler-reuse.md) · [`workflow-graph-engine-iteration4-handler-plan.md`](../plans/workflow-graph-engine-iteration4-handler-plan.md)

## 背景

原有模板任务防自审逻辑以执行人、验收人是否为同一用户为主要判断，并在找不到其他候选人时通过 `self_review_fallback` 自动允许自审。这能避免部分流程死锁，却把不同业务语义混为一谈。

合法场景：部门管理者 A 发起多人任务流，A/B/C 各提交一份内容，全部完成后由 A 汇总并推进。A 同时是集合贡献者和集合负责人，但 A 的后续动作面向整个集合及下一阶段，不等同于独立验收自己提交的单份交付。

因此，是否允许同一用户参与不能只看用户 ID 是否相等，必须结合动作语义、决策对象、交付版本与决策权重。

## 决策

### 1. 决策语义分类

| 决策语义 | 含义 | 默认重叠规则 |
|---|---|---|
| `collection_finalize` | 确认多人集合完整、汇总结果并推进 | 负责人可同时是集合贡献者 |
| `deliverable_acceptance` | 对明确交付物/版本作独立质量验收 | 同一交付物/版本的提交者不得作为唯一验收人 |
| `business_approval` | 对申请、权限、财务、人事等业务事项作正式批准 | 申请人及决策对象贡献者不得批准 |
| `cosign` | 多人会签或投票 | 可配置贡献者参与，但贡献者不得成为唯一决定者 |

### 2. 按决策对象判断

- 优先以 Deliverable 的 `submitted_by_user_id`、submission history 与版本标识判断贡献者。
- 没有正式交付记录时，才回退到节点执行人、Task assignee 或流程发起人。
- 用户在前序节点参与过，不代表不能处理所有后续节点；只有后续决策对象与其贡献存在直接关系时才应用重叠限制。
- 验收人修改并提交新版本后，成为该版本贡献者，不得继续作为该版本的唯一独立验收人。

### 3. 策略不得随候选人数量改变

- `self_review_fallback` 不再作为目标策略模型。
- 找不到合法处理人时进入可诊断的 `BLOCKED`，不得把严格验收自动降级为允许自审。
- 模板/节点必须显式表达决策语义；兼容期可双读旧字段，但需记录迁移状态和退出条件。

### 4. Runtime 与 Handler 边界

- Runtime 只应用 Handler 返回的通用结果，不直接推断“是否自审”。
- HumanTask / Approval 应消费同一决策策略与贡献者事实，避免 TaskService、旧审批引擎和图 Handler 各自实现不同规则。
- `collection_finalize` 可以是 HumanTask 命令，不必伪装成 Approval。
- Approval Handler 继续按 ADR-015 复用现有审批引擎，但需先映射本 ADR 的决策语义。

## 系统管理员边界

用户已确认系统管理员是维护角色，不承担交付或实际业务责任。但相关代码目前广泛依赖 `MANAGEMENT_ROLES`、管理员候选链和管理员 override；**管理员业务边界改造不属于 Iteration 4 本批次**，延后为独立治理项 [`KI-011`](../known-issues/ki-011-system-admin-business-boundary.md)。

Iteration 4 不修改 `UserRole.ADMIN`、`MANAGEMENT_ROLES`、管理员候选/绕过或现有管理员兼容测试。ADR-019 的 I4 验收矩阵聚焦普通业务参与者和组织关系负责人；管理员行为须在后续专项中重新设计和迁移。

## 兼容与迁移

- 先盘点 `on_aggregate_confirmed`、`on_review_approved`、旧审批步骤与 `self_review_fallback` 的真实调用。
- 新模板必须显式选择决策语义；旧模板在完成映射前保持兼容并输出诊断，不静默猜测正式审批语义。
- 本 ADR 不要求数据库迁移；若需要新增持久字段或公共 API，须按仓库协议单独评审。
- 不删除现有测试，而是先新增语义矩阵，再逐批替换与旧目标冲突的测试。

## 最小验收矩阵

- A/B/C 均提交，A 负责集合确认：允许。
- A 独自验收 A 提交的同一交付版本：拒绝或阻塞。
- A 在前序贡献，但后续验收 B 的独立交付：允许。
- 贡献者参与多人会签且不是唯一决定者：按显式策略允许。
- 严格验收无合法候选人：阻塞，不自动启用 fallback。
- 返工产生新版本后：按新版本贡献者重新计算重叠关系。

## 后果

- **正面**：合法协同不再被粗粒度自审规则误伤；独立验收和正式审批仍可保持职责分离。
- **成本**：需要建立决策对象/贡献者事实解析，并迁移旧 metadata fallback 与测试。
- **风险控制**：管理员边界明确延后，避免 I4 同时改动通用 Handler 与全局权限体系。
