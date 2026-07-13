---
type: paradigma-decision
title: "ADR-014: 保留 Task 接口并建立正式工作项 Link"
description: "提议保留 tasks 与 /tasks，新独立任务不创建图，并用正式 Link 关联节点工作项。"
tags: ["adr", "task", "work-item", "workflow-graph", "proposal"]
timestamp: 2026-07-13T22:11:53+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["Task 工作项", "节点 Link", "双写收口"]
    en: ["task work item", "node link", "dual write"]
---
# ADR-014: 保留 Task 接口并建立正式工作项 Link

**日期**：2026-07-13  
**状态**：已采纳（2026-07-13 用户统一批准 ADR-012–016）

## 背景

`Task` 已承载评论、附件、统计和任务中心契约，直接改名或替换成本很高；同时 Task 与 `WorkflowNodeInstance` 目前通过 JSON 元数据互相锚定，双方 Service 都会跨域改写状态。

## 提议决策

1. 保留 `tasks` 表和 `/tasks` 公共 API，把 Task 视为现阶段工作项写模型。
2. 新建 standalone Task 时不再隐式创建单节点图；存量兼容行为按迁移闸门处理。
3. 引入正式 Link，允许一个节点关联零到多个工作项，并保存 link role、生命周期和必要的幂等键。
4. Link 替代 JSON 作为关系真相；JSON 锚点仅保留迁移期兼容读取。
5. Runtime 发布领域事件/Handler 请求，应用协调器负责原子地推进节点与工作项；禁止双方 Service 长期互写内部状态。

## 备选方案

- 立即把 `tasks` 重命名为 `work_items`：API、前端和数据迁移连锁过大，否决。
- 维持一节点一 Task 的外键：无法覆盖视频多参与人、多交付工作项和未来非人工节点，否决。

## 后果

- Iteration 3 才实施 Link、UoW 和写所有权收口，需独立 schema/API 审批。
- 现有 Task 客户端保持兼容；迁移期间需要关系一致性检查和回填报告。
