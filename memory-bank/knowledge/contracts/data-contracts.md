---
type: paradigma-contract
title: "Project Filum — 数据契约"
description: "数据库 schema、枚举、实体关系、API 索引。"
tags:
  - contract
  - data
  - schema
  - api
timestamp: 2026-07-11T23:34:27+08:00
paradigma:
  schema_version: 0.5.0
  temperature: hot
  lifecycle: evolving
  update_policy: requires-human-confirmation
  epistemic_status: confirmed
  contract_kind: data
  retrieval_hints:
    zh:
      - 数据契约
      - schema
      - 枚举
      - API
    en:
      - "data contract"
      - schema
      - api
---
# Project Filum 数据契约

> 🔥 HOT — 数据库表结构、枚举、实体关系与 API 契约索引。
>
> **维护规则**: schema / 枚举变更时**必须**同步更新本文件；宏观流程与模块职责见 [`architecture.md`](../architecture.md)。

**版本**: v3.14.0（与 [`architecture.md`](../architecture.md) 同步）
**最后同步**: 2026-07-10 @ `42df37b` · 图模板部门作用范围 `scope_department_ids` · 产品基线 `0.92.0` + Unreleased

**事实来源**: `backend/app/models/`、`backend/alembic/versions/`、OpenAPI `/docs`

---

## API 契约索引

- **OpenAPI**: 运行后端后访问 `/docs` 或 `/openapi.json`（权威请求/响应形状）
- **Pydantic Schemas**: `backend/app/schemas/`
- **通用错误**: `backend/app/api/error_handlers.py` 返回 `request_id` + 业务错误码
- **认证**: JWT access token + HttpOnly refresh cookie（`backend/app/api/routes/auth.py`）
- **附件下载**: `GET /api/v1/attachments/{id}/content`（鉴权后流式返回）
- **图引擎 + 视频 v1 运行时**: `backend/app/api/routes/workflow_graph_engine.py`（前缀 `/api/v1/workflow-graph`）
  - 图实例/节点：`GET/POST .../instances/{id}`、`.../node-instances/{id}/complete|deep-reject|takeover`
  - 图模板管理：`GET/PATCH .../templates/{id}`、`GET .../feature-flags`
  - **图模板设计器（F-18–F-20 @ 2026-06-21）**：`GET .../templates?scope=manage`；`POST .../templates`（clone）；`GET/PUT .../templates/{id}/designer|draft`；`POST .../templates/{id}/versions`；`PATCH .../templates/{id}/status`；`GET .../templates/{id}/validate`；`GET/POST .../templates/{id}/export|import`；`POST .../templates/import`；`POST .../templates/{id}/dry-run`；`GET .../templates/{id}/stats`
  - 视频 v1 表单/批次：`POST .../templates/{id}/runs`、`.../node-instances/{id}/submit-capture`、`.../finalize-topics`、`.../instances/{id}/dispatch-topic`（TC-P1 增量派发）、`.../instances/{id}/reject-captures`、`POST .../tasks/{task_id}/reject-production`（TC-P1-7 制作审核退回）、`.../fork-production-runs` 等
- **视频 v1 Pydantic**: `backend/app/schemas/workflow_video.py`（`launch_schema` / `capture_schema` / `aggregate_schema` 等）
  - **实例化 participant snapshot**（TC-P1-8）：`ParticipantsSnapshotEntry.include_initiator: bool = False` — 默认从 N1 fan-out 排除发起人；服务端校验 `user_ids ⊆ policy` 允许集合，过滤后为空则 409
  - **打回 metadata**（TC-P1-7）：capture 打回写入 task `extra_metadata.latest_rework_reason` + `latest_capture_state: "rejected"` → 前端用户态「已退回」
- **领域详述**: 图引擎见 [`domains/workflow-graph-engine.md`](../domains/workflow-graph-engine.md)；视频 v1 见 [`domains/workflow-video-v1.md`](../domains/workflow-video-v1.md)；任务中心见 [`domains/task-center.md`](../domains/task-center.md)
- **TCE + 设计器已落地契约**（@ 2026-06-21，见 [`domains/task-center.md`](../domains/task-center.md)）：`GET /api/v1/tasks?ids=`；snapshot `run_label` / `user_facing_state` / 分页；`GET /workflow-graph/runs?department_id=`；`POST .../close-capture`；实例 `aggregate_mode` / `capture_closed` in context；设计器 designer/draft/publish/validate/export/import/dry-run/stats API
- **S-01 周期统计契约**（2026-07-11 批准）：`GET /api/v1/tasks/stats/scopes|summary|workload|details`；统一 `start_date` / `end_date`（Asia/Shanghai、含首尾日期、最长 366 天）、`department_id?`、`include_subtree`；Employee 仅本人，经理/数据代理限有效管理范围，Admin/HR 全局；排除 `metadata.admin_archived=true` 与 `metadata.workflow_graph_root_task=true`。指标为新增、完成、到期、逾期、已成熟截止任务的按期完成率、当前未完成；details 以 `metric` + UUID cursor 分页。
- **图模板部门作用范围**（@ 2026-07-09）：`workflow_graph_templates.scope_department_ids JSONB NOT NULL DEFAULT []`；空数组表示不限制部门，非空时管理列表与实例化按有效管理部门校验；迁移 `20260709_01_graph_template_scope_departments.py`
- **F-29 管理员归档**（@ 2026-06-23）：`POST /api/v1/tasks/{task_id}/archive`（admin，`TaskArchiveRequest.reason` → `TaskArchiveResponse`）；任务 `extra_metadata.admin_archived` / `admin_archived_at` / `admin_archive_reason` / `admin_archive_source_task_id`；图实例 context `admin_archived*` + 节点 TERMINATED + instance CANCELLED
- **任务 PATCH 逾期延期**（@ 2026-06-23）：已逾期任务 `due_date` 变更须晚于原截止时间（ConflictError）

> §10.1–10.40 为 legacy 与核心业务表完整字段；§10.41–10.49 为图引擎九表与运行事件**摘要**（完整列定义以 ORM + Alembic 为准；领域总览见 [`domains/workflow-graph-engine.md`](../domains/workflow-graph-engine.md)）。

---

## 8. 数据库设计原则

- 主键统一使用 `uuid`
- 时间统一使用 `timestamptz`
- 动态业务字段使用 `jsonb`
- 附件统一采用 `attachments + attachment_links`
- 通知统一采用 `notification_messages + notification_deliveries`
- 任务相关沟通固定绑定 `task_comments`
- 高敏档案字段继续允许存放在 `profiles.custom_fields`，但必须由字段定义与权限表驱动展示
- `Leader` 优先通过组织关系与授权推导，不强制引入新的全局角色枚举
- 文档中所有 schema 必须明确标出**当前已实现**或**未来规划阶段**

## 9. 枚举基线

| 枚举 | 取值 | 状态 |
| --- | --- | --- |
| `user_role` | `admin`, `hr`, `employee` | 已实现 |
| `user_status` | `active`, `inactive`, `suspended`, `offboarded` | 已实现 |
| `task_status` | `todo`, `doing`, `review`, `done` | 已实现 |
| `task_priority` | `low`, `medium`, `high`, `urgent` | 已实现 |
| `task_source_type` | `manual`, `template`, `event`, `ai` | 已实现（当前主要使用 `manual`） |
| `task_action_type` | `created`, `assigned`, `status_changed`, `commented`, `attachment_added`, `due_date_changed`, `closed` | 已实现 |
| `comment_format` | `plain_text`, `markdown` | 已实现 |
| `attachment_visibility` | `private`, `internal`, `public` | 已实现 |
| `attachment_status` | `uploaded`, `deleted`, `quarantined` | 已实现 |
| `attachment_target_type` | `task_comment`, `task`, `profile`, `document`, `notification_message`, `report` | 已实现（含汇报附件绑定） |
| `notification_channel` | `email`, `web_push`, `websocket` | 已实现，adapter 第一版已落地 |
| `notification_message_status` | `queued`, `processing`, `completed`, `failed` | 已实现 |
| `notification_delivery_status` | `pending`, `sent`, `failed`, `retrying` | 已实现 |
| `position_assignment_type` | `primary`, `part_time`, `acting` | 已实现 |
| `reporting_line_type` | `solid`, `dotted` | 已实现 |
| `employment_event_type` | `onboard`, `transfer`, `promotion`, `reward`, `discipline`, `offboard`, `rehire` | 已实现 |
| `delegation_scope_type` | `approval`, `task`, `data_access`, `all` | 已实现 |
| `delegation_status` | `pending`, `active`, `expired`, `revoked` | 已实现 |
| `report_direction` | `upward`, `downward` | Step 4 已实现 |
| `report_status` | `in_progress`, `completed`, `returned`, `archived` | Step 4 已实现 |
| `report_route_status` | `queued`, `pending`, `forwarded`, `completed`, `returned` | Step 4 已实现 |
| `workflow_definition_status` | `draft`, `active`, `archived` | 已实现 |
| `workflow_step_type` | `task`, `approval`, `notify` | 已实现 |
| `approval_mode` | `single`, `parallel_all`, `parallel_any` | 已实现 |
| `workflow_instance_status` | `pending`, `in_progress`, `approved`, `rejected`, `returned`, `cancelled`, `completed` | 已实现 |
| `workflow_step_run_status` | `pending`, `approved`, `rejected`, `returned`, `delegated`, `skipped` | 已实现 |
| `notification_receipt_type` | `delivered`, `read`, `acknowledged` | 已实现 |
| `push_subscription_status` | `active`, `expired`, `revoked` | 已实现（Phase 5） |
| `document_category` | `policy`, `sop`, `announcement`, `faq`, `other` | 已实现（Phase 5） |
| `document_status` | `draft`, `published`, `archived` | 已实现（Phase 5） |
| `workflow_graph_template_status` | `draft`, `active`, `archived` | 已实现（图引擎 Phase 2） |
| `workflow_graph_node_type` | `task`, `approval`, `notice` | 已实现 |
| `workflow_graph_instance_status` | `pending`, `active`, `completed`, `cancelled`, `terminated` | 已实现 |
| `workflow_node_engine_state` | `pending`, `activated`, `acknowledged`, `completed`, `terminated` | 已实现 |
| `workflow_node_business_state` | `draft`, `assigned`, `accepted`, `rejected`, `delegated`, `doing`, `pending_review`, `done`, `returned_for_rework`, `cancelled` | 已实现 |
| `workflow_outbox_event_status` | `pending`, `retrying`, `dispatched`, `failed` | 已实现（Phase 11-C） |

## 10. 全量数据库 Schema

> 完整 schema 已按业务域拆分为独立文件。新表/变更请更新对应子文件：
>
| 业务域 | 文件 |
|--------|------|
| IAM / 组织 / HR | [`database/core-schema.md`](./database/core-schema.md) |
| 任务与协同 | [`database/task-collaboration-schema.md`](./database/task-collaboration-schema.md) |
| 工作流与审批 | [`database/workflow-schema.md`](./database/workflow-schema.md) |
| 图引擎 | [`database/graph-engine-schema.md`](./database/graph-engine-schema.md) |
| 消息与推送 | [`database/messaging-schema.md`](./database/messaging-schema.md) |
| 知识库与附件 | [`database/knowledge-media-schema.md`](./database/knowledge-media-schema.md) |
| 总览 | [`database/overview-schema.md`](./database/overview-schema.md) |
| 汇报中心 | [`database/report-schema.md`](./database/report-schema.md) |
| 错误诊断 | [`database/error-schema.md`](./database/error-schema.md) |

## 11. 关系说明

- `users 1:1 profiles`
- `users 1:N refresh_tokens`
- `departments 1:N profiles`
- `departments 1:N board_cards`
- `departments 1:N announcements`
- `users N:N positions` 通过 `profile_positions`
- `users N:N users` 通过 `reporting_lines`
- `users 1:N reports`（initiator / target / current_recipient 三种角色）
- `reports 1:N report_routes`
- `users 1:N error_events`（actor_user）
- `profiles 1:N employment_events`
- `task_templates 1:N employment_events`（显式生命周期联动目标）
- `workflow_definitions 1:N employment_events`（显式生命周期联动目标）
- `profile_field_definitions 1:N profile_field_permissions`
- `users N:N users` 通过 `delegations`
- `tasks N:N tasks` 通过 `task_dependencies`
- `users 1:N task_memos`
- `tasks 1:N task_memos`
- `task_templates 1:N task_template_steps`
- `task_templates 1:N task_template_instances`
- `task_template_steps N:N task_template_steps` 通过 `task_template_step_dependencies`
- `task_template_steps 1:N task_template_step_runs`
- `task_template_instances 1:N task_template_step_runs`
- `task_template_instances 1:N tasks`
- `workflow_definitions 1:N workflow_steps`
- `workflow_definitions 1:N workflow_instances`
- `task_template_instances 1:N employment_events`（triggered_template_instance_id 回链）
- `workflow_instances 1:N employment_events`（triggered_workflow_instance_id 回链）
- `workflow_instances 1:N workflow_step_runs`
- `tasks 1:N task_comments`
- `tasks 1:N task_logs`
- `notification_messages 1:N notification_deliveries`
- `notification_messages 1:N notification_receipts`
- `notification_messages 1:N attachment_links`（逻辑绑定，`target_type = notification_message`）
- `documents 1:N document_embeddings`
- `board_cards 1:1 board_card_archives`
- `announcements 1:1 announcement_archives`
- `attachments N:N 业务对象` 通过 `attachment_links`
- `workflow_graph_templates 1:N workflow_graph_instances`
- `workflow_graph_instances 1:N workflow_node_instances` / `workflow_run_events` / `workflow_outbox_events`
- `workflow_graph_instances N:1 workflow_graph_instances`（`parent_instance_id` 子 Run）
- `workflow_node_instances 1:1 workflow_deliverables`

## 12. 当前验证基线

权威数字见 [`progress.md`](../../logs/progress/progress.md)「测试基线」表（2026-06-22 @ E2E 扩面）：

- backend：`pytest` **252 collected**（含设计器 **15** 项：`test_workflow_graph_template_designer_d{1,2,3}` + `test_workflow_graph_template_topology`）；`test_migrations.py` 需本机 PostgreSQL + `POSTGRES_TEST_ADMIN_DSN`（否则 1 skipped）；`compileall` PASS
- frontend：vitest **45 文件 / 124 用例**（含 `GraphTemplateDesignerView.spec.ts`）；`type-check` / `build` PASS
- Playwright core mock：**33/33**（`npm run test:e2e`：login / task-center* / task-center-interactions / designer / workflow-video-v1 等）
- Playwright task-center 全集：**48/48**（`npm run test:e2e:task-center` = core 33 + multi-account mock 15）
- 未纳入每次刷新：`test:e2e:all`（UAT + docker-gui）、`playwright_live`、Ubuntu 回滚演练；**待办清单**见 [`progress.md`](../../logs/progress/progress.md)「E2E 待办（Backlog）」

> **2026-07-10 更新**：dev 环境已重建；当前工作区 backend **293 collected / 282 passed / 11 skipped**，Vitest **54 文件 / 143 用例**，Playwright default mock **35/35**，type-check/build PASS。仍无 pytest/Vitest 覆盖率插件或 CI；详见 `memory-bank/history/reports/test-coverage-assessment-20260710.md`。

## 13. 维护规则

- 每完成一个里程碑，必须同步更新本文件
- 新增表、枚举或关键运行时组件时，必须同步记录其状态与所属阶段
- “当前已实现”与“未来规划”必须明确区分，禁止混写
- 若阶段边界调整，先更新 `implementation-plan.md`，再回写本文件
