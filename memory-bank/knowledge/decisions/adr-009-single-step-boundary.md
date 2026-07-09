---
type: paradigma-decision
title: "ADR-009: 单步任务产品边界"
description: "任务中心两类任务；6项决策。"
tags: ["adr", "单步任务", "产品边界"]
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.1
  temperature: cold
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["单步任务", "产品边界"]
    en: ["single step", "product boundary"]
---
# ADR-009: 单步任务产品边界与能力差距决策

**日期**: 2026-06-23  
**状态**: 已采纳  
**背景**: 设计意图对照代码审查（单步任务 G-01–G-06）；需统一产品边界与 roadmap 排期。

**决策**

1. **任务中心两类任务**：**单步任务**（「建立任务」· `MANUAL` · `graph_manual`）与 **任务流任务**（图模板实例化 · `WorkflowGraph*`）。
2. **单步发布范围**：依 **`Department.manager_id` 管辖子树**（含 Admin/HR 全员、部门 `PUBLISH_ORG_TASK` 本部门）；**不**改用 `ReportingLine`。
3. **跨部门单步（G-01）**：列为 **新产品能力 F-21**（部门路径路由 + 路径节点自动 CC）；深树性能记技术债。
4. **跨部门协作远期（G-02）**：走 **「项目组」**（多部门成员编组），非组织树 hack；单独立项 P4。
5. **自派任务（G-03）**：**不属于任务中心**；个人待办走 **`task_memos` 备忘**，不扩展「建立任务」给普通员工自派。
6. **抄送（G-04）**：手动建立单步任务 **必须支持抄送人** — **F-22**（`TaskCreateRequest.watcher_user_ids` + 发布 Dialog）。
7. **Runtime（G-05）**：**移除 Legacy E runtime**，任务模板与实例化 **仅图引擎** — **B-12**（强化 ADR-005 后果）。

**后果**  
Roadmap P0=B-12；P1=F-22；P2=F-21；文档见 `roadmap.md` · `domains/task-center.md` §6。
