---
type: paradigma-decision
title: "ADR-006: 视频工作流 v1"
description: "视频v1以graph+Task为主。"
tags: ["adr", "视频工作流", "Feature开关"]
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.1
  temperature: cold
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["视频工作流", "Feature开关"]
    en: ["video workflow", "feature flag"]
---
# ADR-006: 视频工作流 v1 运行时与 Feature 开关（W0）

**日期**: 2026-05（W0）  
**状态**: 已采纳  
**详情**: `plans/workflow-video-v1-w0-adr.md`

**背景**  
视频 v1 需批次选题会、表单引擎、按题 fork，且不能破坏现有 E 路径。

**决策**

1. 不新建第三套运行时；新发起以 `workflow_graph_*` + `Task` 为主
2. 选题会为图模板 `topic_meeting_batch_v1`，无独立导航入口
3. `WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED` 默认 `false`，仅控制新图模板实例化 API
4. 策略模块：`backend/app/core/workflow_video_policy.py`

**后果**  
W1–W7 期间生产行为与开关关闭时一致；启用开关须配套 seed 与前端 Dialog。

**非决策（留待后续）**
- `instantiate_template` 内部转调 graph（W10 可选）
- 单 Run 内多选题 DAG（已明确不做）
