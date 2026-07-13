---
type: paradigma-decision
title: "ADR-015: 通过 Handler 复用现有审批引擎"
description: "提议以 Handler 适配 WorkflowDefinition 审批能力，而非新建第三套审批模型。"
tags: ["adr", "approval", "handler", "workflow", "proposal"]
timestamp: 2026-07-13T22:11:53+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["审批 Handler", "审批引擎复用"]
    en: ["approval handler", "approval engine reuse"]
---
# ADR-015: 通过 Handler 复用现有审批引擎

**日期**：2026-07-13  
**状态**：已采纳（2026-07-13 用户统一批准 ADR-012–016）

## 背景

项目已有 `WorkflowDefinition / WorkflowInstance / WorkflowStepRun` 审批模型。图节点若再次内建投票、会签和审批历史，将形成第三套难以统一的审批状态机。

## 提议决策

1. 图 Runtime 只管理 Approval 节点的激活、等待和结果，不复制审批领域内部状态。
2. Approval Handler 在节点激活时创建或关联现有审批实例，并以稳定 correlation/idempotency key 防止重复创建。
3. 审批引擎以明确结果事件回传 approved/rejected/cancelled；Runtime 在同一应用协调边界内消费结果并推进路径。
4. 先完成语义映射验证；只有现有引擎无法表达的已确认需求，才提出审批模型扩展。

## 备选方案

- 在图节点配置中直接实现新审批状态机：短期直观，长期造成规则、权限和审计分叉，否决。
- 把所有图都迁回旧审批引擎：无法承载通用 Task、Notice、视频等节点，否决。

## 后果

- Handler 必须定义取消、重试、回调重复和历史查询契约。
- 该决策属于后续业务能力拆分，不在 Iteration 0–3 内提前实施。
