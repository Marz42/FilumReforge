---
type: paradigma-decision
title: "ADR-010: 任务流产品边界"
description: "任务流8项决策。"
tags: ["adr", "任务流", "产品边界"]
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.1
  temperature: cold
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["任务流", "产品边界"]
    en: ["task flow", "product boundary"]
---
# ADR-010: 任务流产品边界与能力差距决策

**日期**: 2026-06-23  
**状态**: 已采纳  
**背景**: 任务中心三大模块之 **任务流**；设计意图对照代码（W-01–W-09）及多部门/fork 讨论。

**决策**

1. **统一入口**：任务流仅 **图模板实例化**（`POST .../workflow-graph/templates/{id}/runs`）；Legacy E 删除见 **B-12**。
2. **多部门共用模板**：批次 **B-16 `instance_department`** + 制作链 **`department_pools`**（固定目标部门 C 在 **制作模板 config** 定死 UUID）；**F-28** 修复 `copywriters` 池须随 **发起部门** 解析（A→A 经理，B→B 经理）。
3. **模板链（W-03）**：**通用能力 F-23** — Run/节点完成可触发下一图模板；**禁止** A→B→A（发布时环检测 + 运行时 guard）；现状仅 video **fork** 子集。
4. **部门定时（W-04）**：**F-24** — 见 **ADR-011**；不沿用 Legacy `TaskSchedule`+cron；`config.schedulable` + 建立任务「定时派发」Tab。
5. **附件（W-05）**：预览/试听 **F-25** P3+。
6. **设计器（W-06）**：JSON/cron → 表单组件 **F-26**；含 `department_pools` 部门选择器。
7. **跨部门跳转 CC（W-07）**：任务直达执行人、**不经部门负责人门控**；边界 **抄送组织树 manager** — **F-27**（与 F-21 同路由思路）。
8. **任务统计（S-01）**：周期/绩效 **暂不立项**；现状 gap 仅文档化。

**后果**  
改造计划 **TC-Transform** Phase 0–3 见 `roadmap.md`；全貌 `domains/task-center.md` §7–§8。
