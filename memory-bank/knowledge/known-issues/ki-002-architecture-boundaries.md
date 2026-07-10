---
type: paradigma-known-issue
title: "KI-002: 架构边界（易误判非 Bug）"
description: "Legacy E 历史兼容、TCE 技术债、设计器状态等架构层面的已知状态。"
tags: ["known-issue", "architecture", "legacy-e", "graph-engine", "tce"]
timestamp: "2026-07-10T22:00:55+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
  related_to:
    - ../decisions/adr-005-dual-track-workflow.md
    - ../decisions/adr-009-single-step-boundary.md
    - ../domains/task-center.md
  retrieval_hints:
    zh: ["架构边界", "Legacy E", "图引擎", "TCE", "B-12"]
en: ["architecture boundary", "legacy E", "graph engine"]
---

# KI-002: 架构边界（易误判非 Bug）

## Legacy E 历史兼容边界

**说明**: B-12 已移除 `task_templates` 对外 API、实例化入口和旧调度执行路径，图模板是唯一产品入口；旧表族、ORM 与未挂载服务暂留用于历史数据兼容，不应误判为仍有两个产品运行入口。
**参考**: `decisions/adr-005-dual-track-workflow.md`、`domains/workflow-graph-engine.md`

## Legacy 工作流 E 后端（产品入口已删除，历史清理待定）

**说明**（@ ADR-009 G-05 · 2026-06-23）:

| 层 | 状态 |
|----|------|
| 前端模板页 | **已移除** Legacy E Tab / CRUD；唯一入口为图模板列表 + 实例化（用户可见名「任务模板」） |
| 后端 `task_templates` API | **已移除**；API 回归测试固定返回 404 |
| `TaskTemplateService` / ORM / 表族 | 未挂载服务与数据结构暂留历史兼容，不再承载产品入口 |
| 迁移 | 历史 E 实例仍需迁移、只读归档或最终删除方案 |

**实例化路径**（当前事实）: `POST /api/v1/workflow-graph/templates/{id}/runs` **唯一**

## 单步任务已知缺口（ADR-009）

| 缺口 | 状态 | 跟踪 |
|------|------|------|
| 创建时抄送人 | **F-22 ✅** | `TaskCreateRequest.watcher_user_ids` + Dialog 多选 |
| 跨部门点对点 + 路径 CC | **F-21 ✅** | 组织树 manager 路径 CC；深树性能为技术债 |
| 自派任务 | **不在任务中心** | 走 `task_memos` 备忘（G-03） |
| 派活 vs 汇报线 | **依部门 manager 子树** | 汇报线不改；远期 **项目组 P4** |

## 任务流已知缺口（ADR-010）

| 缺口 | 状态 | 跟踪 |
|------|------|------|
| copywriters 池与发起部门脱钩 | **F-28 ✅** | fork 时 copywriters = 发起部门 |
| 通用完成后触发模板 | **F-23 ✅** | `config.on_complete` + 发布防环 |
| 跨部门边界 CC | **F-27 ✅** | 投影任务 boundary_cc |
| department_pools 设计器 UI | **F-26 ✅** | pools 部门选择器 |
| 部门定时图模板 | **F-24 ✅** | ADR-011 · `/workflow-graph/schedules` |
| streaming N2 空壳待办 | **W-08 ✅** | aggregate engine skip |

## 任务中心 TCE（Phase 1–5 ✅）

**说明**: Task Center Enhance 已落地；F-10–F-12 已完成，S-01 暂缓；F-05 完整 Shell 拆分仍是技术债。

## 图模板设计器（F-18–F-20 ✅）

| 层 | 状态 |
|----|------|
| 前端 | `/task-templates/:id/edit` 全页设计器；DAG 预览、dry-run、JSON 导入导出 |
| 后端 | `WorkflowGraphTemplateAdminService` + topology 校验 |
| Legacy E 设计器 | **不恢复**；B-12 已移除产品入口，历史表族暂留兼容 |

## 图模板实例化：发起部门（TCE Phase 4 ✅）

- **B-16**：`ParticipantPolicyDefinition.scope` 默认 `instance_department`；实例 `department_id` 优先于 seed policy。
- **F-17**：Dialog 默认/必选/可改发起部门；preview 与 submit 显式传 `department_id`。

## 生产 seed：`seed_version` 升级与外键冲突（已修复 @ `0.90.0`）

**现象**（@ `0.89.0` 及更早）：已有视频 Run 时重跑 `seed_workflow_video_templates`，DELETE template nodes 触发 `fk_wf_node_instances_template_node`。  
**处理**：升级到 `19608f0` 或更高；有历史 Run 时 seed 改为按 `node_key` 原地同步拓扑与 config。

## 视频 v1 图模板开关默认关闭

**说明**: `WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED` 默认 `false`；批次/fork API 需显式开启。  
**参考**: `decisions/adr-006-video-workflow-flag.md`

## 生命周期联动为显式绑定

**说明**: 非规则化默认映射；事件须带 `task_template_id` / `workflow_definition_id` 才 worker 触发。  
**参考**: `domains/hr-org.md`
