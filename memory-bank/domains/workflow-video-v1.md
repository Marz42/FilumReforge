# 领域：视频工作流 v1 (Workflow Video v1)

> 🌡️ WARM — 涉及选题会、批次 Run、按题 fork、表单引擎时读取。

**计划**: `plans/workflow-video-v1-implementation-plan.md` v2.0 · **ADR**: `decisions.md` ADR-006 · **运维**: `handbooks/workflow-video-v1-*.md`  
**UI 迭代（v2 草案）**: [`plans/workflow-video-v1-ui-simplification-design.md`](../plans/workflow-video-v1-ui-simplification-design.md) · Demo: [`demos/workflow-task-detail-v2.html`](../demos/workflow-task-detail-v2.html)

---

## 产品口径

```
选题会（批次 Run）→ approved_topics[] → 按题 fork 子 Run（video_production_per_topic_v1）
```

- **无**独立「发起选题会」导航；选题会为图模板 `topic_meeting_batch_v1`
- **无**单 Run 内多选题 DAG；改为按题 fork

---

## 表单引擎

| Schema | 阶段 |
|--------|------|
| `launch_schema` | 发起/实例化 |
| `capture_schema` | 节点采集 |
| `aggregate_schema` | 汇总定稿 |

Pydantic：`backend/app/schemas/workflow_video.py`  
服务：`WorkflowVideoFormService`、`WorkflowVideoInstantiationService`、`WorkflowVideoForkService`、`WorkflowVideoReworkService`

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

`backend/app/api/routes/workflow_video.py`（与 `workflow_graph_engine` 协同）

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

`task_templates` 实例化标 **legacy**；图模板为 v1 主路径。W10 可选：开关开启时 E 内部转调 graph（未决）。
