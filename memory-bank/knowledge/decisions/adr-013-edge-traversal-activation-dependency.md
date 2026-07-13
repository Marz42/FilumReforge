---
type: paradigma-decision
title: "ADR-013: 路径账本优先于完整 Token 引擎"
description: "提议先用 edge traversal 与 activation dependency 修复条件分支和 Join。"
tags: ["adr", "workflow-graph", "runtime", "proposal"]
timestamp: 2026-07-13T22:11:53+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["路径账本", "激活依赖", "条件 Join"]
    en: ["edge traversal", "activation dependency", "conditional join"]
---
# ADR-013: 路径账本优先于完整 Token 引擎

**日期**：2026-07-13  
**状态**：已采纳（2026-07-13 用户统一批准 ADR-012–016）

## 背景

当前 exclusive 分支只激活命中下游，未命中节点仍保持 `PENDING`；Join 却按模板静态入边等待，实例完成也按全部节点状态判断。`WG-GAP-001` 至 `WG-GAP-003` 已复现这一不一致。

## 提议决策

1. 先持久化实际 edge traversal 与节点 activation dependency。
2. Join 只等待本 Run 中实际产生、且属于当前激活批次的依赖；未产生分支不构成等待条件。
3. 没有命中边且当前节点不是合法终点时，产生明确 `no_route` 失败结果和可查询诊断。
4. 实例完成由实际路径账本和活动依赖决定，不以“模板所有节点必须完成”为长期语义。
5. 当前阶段不建设通用 Token 表；当 Subprocess、Signal、复杂并行取消或 BPMN 互操作成为真实需求时再复审。

## 备选方案

- 立即引入完整 Token 引擎：能力更强，但迁移面和状态空间远超当前缺陷所需，暂不采用。
- 用 `SKIPPED` 批量改写所有未选节点：可缓解部分完成判断，但无法可靠表达每次 traversal/iteration 的依赖来源，不作为核心模型。

## 后果

- Iteration 2 需要路径/依赖持久化、no-route 结果以及 PostgreSQL 并发验证。
- 未来若升级为 Token，路径账本仍可作为审计与迁移输入。
