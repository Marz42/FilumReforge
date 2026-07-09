---
type: paradigma-plan
title: "W0 ADR"
description: "视频工作流 v1 W0 架构决策。"
tags:
  - plan
  - W0
  - ADR
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh:
      - W0
      - ADR
    en:
      - w0
      - adr
---
# ADR：视频工作流 v1 运行时与 Feature 开关（W0）

> **【已迁入】** 权威 ADR 条目见 [`../decisions.md`](../decisions.md) **ADR-006**。下文保留 W0 原文供对照。

**状态**：已接受（W0）  
**关联**：[workflow-video-v1-implementation-plan.md](./workflow-video-v1-implementation-plan.md) v2.0

## 背景

图引擎 Phase 0–11-G 已支持手动任务 dual-write 与多节点运行时；工作流 E（`task_templates`）仍是组织任务主实例化路径。视频 v1 引入 **批次选题会 + 按题 fork 制作 Run** 与 **模板表单引擎**（`launch_schema` / `capture_schema` / `aggregate_schema`），需在不大改现有行为的前提下增量上线。

## 决策

1. **不新建第三套运行时**：新发起以 `workflow_graph_*` + `Task` 为主；`TaskTemplateService.instantiate_template` 标 **legacy**，在 W10 前保持可用。
2. **统一入口**：选题会是图模板库中的 `topic_meeting_batch_v1`，**不设**独立「发起选题会」导航或 API 前缀。
3. **Feature 开关**
   - `WORKFLOW_GRAPH_ENGINE_ENABLED`（`workflow_graph_engine_enabled`，默认 `true`）：既有手动任务图投影与节点推进。
   - `WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED`（`workflow_graph_template_engine_enabled`，默认 **`false`**）：**仅**控制新图模板实例化（`POST .../workflow-graph/templates/{id}/runs`、批次/fork 等 W3+ 路径）。默认关闭，避免半成品 API 被误用。
   - `TASK_CENTER_V2_ENABLED`：任务中心 graph-first 读路径（已有）。
4. **策略模块**：`backend/app/core/workflow_video_policy.py` 提供 `use_graph_template_instantiation()` / `use_legacy_task_template_instantiation()`，供路由与服务在 W3 起统一判断。

## 后果

- W1–W7 开发期间，生产与普通开发环境行为与今日一致（E 模板实例化仍可用）。
- 启用模板引擎开关后，仅 **新** 图模板 run 路径生效；须配套 seed 与前端通用实例化 Dialog（W7）。
- 每个 Wn 阶段在 `progress.md` 记录验证命令；W0 测试见 `backend/tests/test_workflow_video_w0_baseline.py`。

## 非决策（留待后续 ADR）

- `workflow_graph_template_engine_enabled=true` 时是否将 `instantiate_template` 内部转调 graph（W10-4 可选）。
- 单 Run 内多选题 DAG（已明确 **不做**，改为按题 fork 子 Run）。
