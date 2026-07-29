---
type: paradigma-domain
title: "参考模板包：视频工作流 v1 (Workflow Video v1)"
description: "视频 v1 普通图模板包及当前兼容实现：选题会批次、表单、聚合与 fork。"
tags:
  - domain
  - 视频工作流
  - 选题会
  - W0
timestamp: 2026-07-30T01:45:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh:
      - 视频工作流
      - 选题会
      - W0
    en:
      - "video workflow"
      - W0
---
# 参考模板包：视频工作流 v1 (Workflow Video v1)

> 🌡️ WARM — 涉及选题会、批次 Run、按题 fork、表单/聚合兼容链路时读取。视频流程是普通图模板包，不是引擎领域类型。

**计划**: `plans/workflow-video-v1-implementation-plan.md` v2.0 · **ADR**: `decisions.md` ADR-006 · **运维**: `knowledge/manuals/workflow-video-v1-*.md`  
**UI 迭代（v2 草案）**: [`plans/workflow-video-v1-ui-simplification-design.md`](../plans/workflow-video-v1-ui-simplification-design.md) · Demo: [`demos/workflow-task-detail-v2.html`](../demos/workflow-task-detail-v2.html)

**当前架构**：[`ADR-018`](../decisions/adr-018-domain-neutral-workflow-templates.md) 已由 I4-E 落地。视频仅提供 seed v5 模板、schema、兼容 API 与黄金回归；Runtime / TaskService / 前端详情核心按 capability snapshot / task capability 工作，不按视频业务词汇分支。

---

## 产品口径

```
选题会（批次 Run）→ approved_topics[] → 按题 fork 子 Run（video_production_per_topic_v1 · seed v5）
```

- **无**独立「发起选题会」导航；选题会为图模板 `topic_meeting_batch_v1`
- **无**单 Run 内多选题 DAG；改为按题 fork
- 制作链 **10 节点**（N3–N5、N7–N12_COSIGN）
- **多文案部门**：**同一图模板、实例级发起部门**（文案 A/B 各发起 → 统一后期部）— **F-28 / B-16 / F-17 ✅**；seed 的 `--copy-dept-code` 仅默认文案池，实例化 Dialog 选发起部门为准

### 生产模板刷新

```bash
cd backend && source .venv/bin/activate
python -m app.scripts.seed_workflow_video_templates \
  --copy-dept-code <文案部code> \
  --post-dept-code <后期部code>
```

Demo 环境可省略参数（须存在 `video-copywriting` / `video-voice` / `video-post`）。详见 [workflow-video-v1-docker-runbook.md](../manuals/workflow-video-v1-docker-runbook.md) 与 [deployment-runbook-ubuntu-2404.md §21.3.1](../manuals/deployment-runbook-ubuntu-2404.md)。

---

## 当前表单/聚合兼容实现

| Schema | 阶段 |
|--------|------|
| `launch_schema` | 发起/实例化 |
| `capture_schema` | 节点采集 |
| `aggregate_schema` | 汇总定稿 |

Pydantic：`backend/app/schemas/workflow_video.py`  
兼容服务：`WorkflowVideoFormService`、`WorkflowVideoInstantiationService`、`WorkflowVideoForkService`、`WorkflowVideoReworkService`。通用入口为 `WorkflowTemplateInstantiationService`；模板声明 `workflow_capabilities` / `runtime_policy`，节点声明 `task_capability`。兼容服务不构成视频专用引擎层。

**TC-P1 运行时扩展**（2026-06-18）：

| API | 说明 |
|-----|------|
| `POST .../instances/{id}/dispatch-topic` | 增量派发单题 → fork 子 Run |
| `POST .../instances/{id}/reject-captures` | N1 采集打回 |
| `POST .../tasks/{task_id}/reject-production` | 制作审核节点退回 |
| `ParticipantsSnapshotEntry.include_initiator` | 实例化 snapshot；默认 `false` 排除发起人 fan-out |

详见 `data-contracts.md` API 索引。

---

## Feature 开关

| 开关 | 默认 | 作用 |
|------|------|------|
| `WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED` | **`false`** | 新图模板实例化（W3+ 路径） |

策略：`backend/app/core/workflow_video_policy.py`

---

## 阶段状态

W0–W10 **done**（见 `progress.md`「视频工作流 v1」表）

W0–W10 视频黄金流程与 I4-E 领域中立内核均已完成；旧公共 API、历史 Run 和旧客户端字段仍在兼容窗口，尚未满足删除 dual-read 的条件。

| 阶段 | 交付摘要 |
|------|----------|
| W1 | `instance_key`、`run_label`、`parent_instance_id` |
| W2 | `ParticipantResolutionService`、preview-participants |
| W3–W4 | 图实例化 v2、编排钩子 |
| W5/WFK | 定向返工、按题 fork |
| W6–W7 | 双模板种子、前端表单/看板 |
| W8–W9 | `workflow_run_events`、outbox 激活通知 |
| W10 | Playwright + 回归硬化 |

---

## 关键 API 前缀

`backend/app/api/routes/workflow_graph_engine.py`（前缀 `/api/v1/workflow-graph`；当前同时承载通用图 API 与视频兼容动作）

---

## 测试入口

```sh
# 后端 W0 示例
pytest -q tests/test_workflow_video_w0_baseline.py
# 前端 E2E
npm run test:e2e:workflow-video
```

---

## 与 legacy E

`task_templates` 实例化标 **legacy**；图模板为当前产品主路径。B-12 后 Legacy E 产品入口已移除，旧表族仅保留历史兼容。

## 领域中立迁移边界

- 不改变视频模板当前业务口径与黄金流程。
- 不新增 `VideoHandler` 或视频节点类型。
- `run_kind`、模板 code、节点 key 与 `video_*` Profile 已集中为兼容信号，不得重新进入核心行为分支。
- 公共 API 与历史数据继续双读/双写；调用观测归零后再删除兼容字段。
- 非视频“合同材料收集”模板测试已复用结构化表单、集合与子 Run capability，证明核心契约不依赖视频命名。
