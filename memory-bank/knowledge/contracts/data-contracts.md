---
type: paradigma-contract
title: "Project Filum — 数据契约"
description: "数据库 schema、枚举、实体关系、API 索引。"
tags:
  - contract
  - data
  - schema
  - api
timestamp: 2026-08-12T12:05:50+08:00
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

**版本**: v3.22.0（与 [`architecture.md`](../architecture.md) 同步）
**最后同步**: 2026-08-11 · RC2 模板可见/可管理边界 · 最新试用候选 `v0.93.0-rc.2`

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
  - Iteration 4 准入：Admin-only `GET .../admin/iteration4-readiness`；无管理权限统一 404
  - 图模板管理：`GET/PATCH .../templates/{id}`、`GET .../feature-flags`
  - **图模板设计器（F-18–F-20 @ 2026-06-21）**：`GET .../templates?scope=manage`；`POST .../templates`（clone）；`GET/PUT .../templates/{id}/designer|draft`；`POST .../templates/{id}/versions`；`PATCH .../templates/{id}/status`；`GET .../templates/{id}/validate`；`GET/POST .../templates/{id}/export|import`；`POST .../templates/import`；`POST .../templates/{id}/dry-run`；`GET .../templates/{id}/stats`
  - **模板数据治理（2026-08-10）**：`GET .../templates/governance-audit` 对调用者可管理的 ACTIVE/DRAFT 模板执行只读检查，返回 `error|warning|review` 分级、模板/问题/建议、`edit_draft|create_new_version|review_configuration` 修正动作，以及可选引用编码、建议编码和受影响部门。检查覆盖 global 人工确认、global 残留部门编号、空 departments、缺失/停用部门、顶层/节点 `child_template_code`、`on_complete.next_template_code`、旧版本引用与父子 scope 不兼容；接口不自动修改数据。
  - **Iteration 4 UAT 验收准备（2026-08-10）**：`GET .../templates/uat-preflight` 对具备模板管理权限的调用者返回 `preflight_ready`、固定为真的 `manual_uat_required`、`checks[]`、模板/部门候选与当前月 S-01 样本计数。P-01～P-06 检查治理错误、负责人 + 至少 3 名活跃成员、非视频通用 ACTIVE 模板、视频参考模板包、设计器草稿和统计样本；P-07 始终要求人工验收。接口只读，普通员工或越权对象统一 404；`preflight_ready` 不表示 UAT 已通过。
  - **ADR-017 Phase 1/2（2026-07-28）**：summary/detail/designer 返回 `tags` + `capabilities`；manage list 支持 `status` + `q`；`PATCH .../templates/{id}/tags`；designer/detail 返回既有 `context_schema`，draft save 可选写入且省略时保留原值；常用 `ui_profile` / launch / routing 结构化 authoring 不改变运行时契约
  - **ADR-020 已发布模板可用部门治理（2026-07-30）**：`PATCH .../templates/{id}/availability-scope` 仅允许 ACTIVE 模板增加部门或扩大为 global，请求必须提供 `reason`；部门经理新增目标限其有效管理范围，扩大为 global 仅允许全局管理角色；`GET .../templates/{id}/availability-scope/events` 返回 actor、前后范围、新增部门、原因与时间。草稿继续由 designer 修改，归档模板和 ACTIVE 范围缩减均拒绝。
  - **安全读取/管理策略（2026-08-09）**：ACTIVE global 对所有活跃用户可读；ACTIVE departments 仅对所属部门或有效管理部门可读；DRAFT/ARCHIVED 只对可管理者可读。部门模板管理员只能读取、派生、编辑、导入/导出、发布、归档或删除其完整 scope 位于有效管理范围内的模板；越权对象统一 404。`department-pool-member-options` 同时校验 template 与可选 instance 的对象读权限。
  - 视频 v1 表单/批次：`POST .../templates/{id}/runs`、`.../node-instances/{id}/submit-capture`、`.../finalize-topics`、`.../instances/{id}/dispatch-topic`（TC-P1 增量派发）、`.../instances/{id}/reject-captures`、`POST .../tasks/{task_id}/reject-production`（TC-P1-7 制作审核退回）、`.../fork-production-runs` 等
- **视频 v1 Pydantic**: `backend/app/schemas/workflow_video.py`（`launch_schema` / `capture_schema` / `aggregate_schema` 等）
  - **实例化 participant snapshot**（TC-P1-8）：`ParticipantsSnapshotEntry.include_initiator: bool = False` — 默认从 N1 fan-out 排除发起人；服务端校验 `user_ids ⊆ policy` 允许集合，过滤后为空则 409
  - **打回 metadata**（TC-P1-7）：capture 打回写入 task `extra_metadata.latest_rework_reason` + `latest_capture_state: "rejected"` → 前端用户态「已退回」
- **领域详述**: 图引擎见 [`domains/workflow-graph-engine.md`](../domains/workflow-graph-engine.md)；视频 v1 见 [`domains/workflow-video-v1.md`](../domains/workflow-video-v1.md)；任务中心见 [`domains/task-center.md`](../domains/task-center.md)
- **ADR-018 领域中立边界**：上述视频专用 schema/API 是当前兼容事实，不是新的引擎类型；迁移目标是表单、集合、聚合、交付/返工和子 Run 等通用能力。迁移完成前不破坏现有公共 API。
- **ADR-019 决策语义边界**：集合确认、独立交付验收、正式业务审批与多人会签具有不同参与者重叠规则；贡献者优先按 Deliverable 当前 submitter/version/signature 判断。I4-B/C 已完成语义映射与旧审批桥接；Admin 兼容行为不在 I4 修改。
- **I4-D Deliverable JSON v2（无 schema/API 破坏）**：现有 `workflow_deliverables.payload` 双写 `latest_submission` / `submission_history` 兼容字段，并增加 `schema_version=2`、`current_submission_version`、`review_history`、`accepted_submission_version`、`accepted_submission_signature` 与不可变 `accepted_submission` 快照；每条 review 绑定 submission version/signature。
- **I4-D Notification completion policy**：`NotificationMessage.payload.completion_policy` 可选 `queued|sent|all_channels_success`，省略时默认 `all_channels_success`；消息完成按全部 delivery 计算，worker 的 delivery 子集不得提前完成整条消息。
- **I4-E template capability snapshot（JSON，无 schema/API 破坏）**：新 Run 的 `context.capability_snapshot` 固化 `schema_version=1`、`capabilities[]`、`runtime.notify_on_node_activation|archive_on_completion|archive_on_cancel`、`instantiation_mode=direct|child_only` 与 `source=explicit|legacy_run_kind|default`。Runtime 只消费快照；旧 `run_kind` 仅由兼容适配器推导等价快照。
- **I4-E task capability（Task metadata JSON）**：模板节点 `config.task_capability` / ROOT `config.root_task_capability` 投影为 `Task.extra_metadata.task_capability`，字段为 `surface=run_overview|structured_form|collection|deliverable|review|manual`、`submit_mode?`、`state_policy`、`variant?`、`features{}`、`root_visibility`。前端布局与后端用户态按此契约解析；`ui_profile` / 节点 key 推断只保留在兼容适配器。
- **TCE + 设计器已落地契约**（@ 2026-06-21，见 [`domains/task-center.md`](../domains/task-center.md)）：`GET /api/v1/tasks?ids=`；snapshot `run_label` / `user_facing_state` / 分页；`GET /workflow-graph/runs?department_id=`；`POST .../close-capture`；实例 `aggregate_mode` / `capture_closed` in context；设计器 designer/draft/publish/validate/export/import/dry-run/stats API
- **S-01 周期统计契约**（2026-07-11 批准）：`GET /api/v1/tasks/stats/scopes|summary|workload|details`；统一 `start_date` / `end_date`（Asia/Shanghai、含首尾日期、最长 366 天）、`department_id?`、`include_subtree`；Employee 仅本人，经理/数据代理限有效管理范围，Admin/HR 全局；排除 `metadata.admin_archived=true` 与 `metadata.workflow_graph_root_task=true`。指标为新增、完成、到期、逾期、已成熟截止任务的按期完成率、当前未完成；details 以 `metric` + UUID cursor 分页。
- **图模板部门作用范围**：显式 `scope_mode=global|departments`；`global` 不允许部门列表，`departments` 至少一个部门；Run 创建先解析最终部门再校验 scope（迁移 `20260713_01`）。ACTIVE 模板可通过 ADR-020 治理接口单调扩大范围且不增加定义版本，审计写入 `workflow_graph_template_scope_events`（迁移 `20260730_01`）；缩小范围仍须发布新版本。
- **附件 OOXML 安全预算**：DOCX/XLSX 入库前最多 2,000 个 ZIP 条目、64 MiB 总展开大小、32 MiB 单条目、200:1 单条目压缩比；拒绝加密条目与绝对/上级路径。预算校验发生在对象存储与浏览器预览之前。
- **graph-v3 路径契约**（@ 2026-07-15）：节点 `routing_mode`；Run `result`/`diagnostics`；`workflow_edge_traversals` 与 `workflow_node_activation_dependencies` 保存实际路径和激活原因；complete Context patch 可携带 `expected_context_version`，graph-v3 有 patch 时必填。
- **F-29 管理员归档**（@ 2026-06-23）：`POST /api/v1/tasks/{task_id}/archive`（admin，`TaskArchiveRequest.reason` → `TaskArchiveResponse`）；任务 `extra_metadata.admin_archived` / `admin_archived_at` / `admin_archive_reason` / `admin_archive_source_task_id`；图实例 context `admin_archived*` + 节点 TERMINATED + instance CANCELLED
- **任务 PATCH 逾期延期**（@ 2026-06-23）：已逾期任务 `due_date` 变更须晚于原截止时间（ConflictError）
- **P1-10 模板任务防自审**（@ 2026-07-17）：模板图任务进入评审时排除执行人，按直属上级 → 部门负责人 → 工作流管理员 → 系统管理员选择验收人；无人可选则 `tasks.status=blocked`、`blocked_reason=no_eligible_reviewer`。系统管理员可调用 `PUT /api/v1/tasks/{id}/reassign-reviewer`（`{reviewer_id}`）显式恢复评审；排除与改派均写 `task_logs.detail`。

> §10.1–10.40 为 legacy 与核心业务表完整字段；§10.41 起为图引擎十四表与运行事件**摘要**（完整列定义以 ORM + Alembic 为准；领域总览见 [`domains/workflow-graph-engine.md`](../domains/workflow-graph-engine.md)）。

---

## 8. 数据库设计原则

- 主键统一使用 `uuid`
- 时间统一使用 `timestamptz`
- 动态业务字段使用 `jsonb`
- 附件统一采用 `attachments + attachment_links`
- 通知统一采用 `notification_messages + notification_deliveries`；工作流 Outbox 通过 `notification_messages.deduplication_key` 按 event id 去重；消息完成策略默认要求全部 delivery 成功
- 任务相关沟通固定绑定 `task_comments`
- 高敏档案字段继续允许存放在 `profiles.custom_fields`，但必须由字段定义与权限表驱动展示
- `Leader` 优先通过组织关系与授权推导，不强制引入新的全局角色枚举
- 文档中所有 schema 必须明确标出**当前已实现**或**未来规划阶段**

## 9. 枚举基线

| 枚举 | 取值 | 状态 |
| --- | --- | --- |
| `user_role` | `admin`, `hr`, `employee` | 已实现 |
| `user_status` | `active`, `inactive`, `suspended`, `offboarded` | 已实现 |
| `task_status` | `todo`, `doing`, `review`, `blocked`, `done` | 已实现（`blocked` 仅用于模板图任务评审诊断） |
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
| `workflow_graph_instance_status` | `pending`, `active`, `completed`, `cancelled`, `terminated`, `failed` | 已实现 |
| `workflow_node_engine_state` | `pending`, `activated`, `acknowledged`, `completed`, `terminated`, `skipped`, `failed`, `suspended` | 已实现 |
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
| Iteration 5 投影读模型 | [`projection-contract.md`](./projection-contract.md) |
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
- `workflow_graph_templates 1:N workflow_graph_template_scope_events`；每条事件 N:1 `users` actor
- `workflow_graph_instances 1:N workflow_node_instances` / `workflow_edge_traversals` / `workflow_node_activation_dependencies` / `workflow_human_task_links` / `workflow_operational_incidents` / `workflow_run_events` / `workflow_outbox_events`
- `workflow_command_receipts` 以 `(actor_key,command_type,command_id)` 唯一；五类关键 API 命令与业务写同事务提交
- `workflow_operational_incidents` 以 fingerprint 唯一聚合 Link fallback/mismatch/backfill、Coordinator、Receipt、Outbox 与迁移异常
- `workflow_graph_instances N:1 workflow_graph_instances`（`parent_instance_id` 子 Run）
- `workflow_node_instances 1:1 workflow_deliverables`
- `tasks / workflow_graph_instances / workflow_node_instances` 派生 `task_center_items`；投影可重建且不反向拥有业务事实
- `workflow_graph_instances 1:1 process_run_summaries`；`workflow_graph_instances 1:N node_timeline_entries`
- `projection_checkpoints` 以 projection+stream 唯一，独立跟踪 `workflow_run_events` / `task_logs` / `task_comments`；checkpoint 不是业务事实，也不与通知 Outbox 共用状态

## 12. 当前验证基线

最新权威结果见 [`progress summary`](../../logs/progress/summary.md) 与最近独立 session log（2026-08-09 @ 安全与上线准备）：

- backend：Iteration 5-B 后基线 **479 collected / 447 passed / 32 skipped / 0 failed**；skip 为登记的 PostgreSQL/Redis 等环境条件用例；Alembic 单 head `20260812_02`
- Iteration 4-E / Handler / 视频黄金流程定向：**66 PASS**
- frontend：Vitest **73 文件 / 211 用例 PASS**；`vue-tsc --build`、production build、ESLint 与 Oxlint PASS
- 模板解耦 Phase 2：Backend DB-backed **11/11**、TemplateCapabilities **6/6**、视频 mock E2E **2/2**
- 未纳入每次刷新：live/docker-gui、目标环境 I3-F 7 天 readiness、Ubuntu 回滚演练

## 13. 维护规则

- 每完成一个里程碑，必须同步更新本文件
- 新增表、枚举或关键运行时组件时，必须同步记录其状态与所属阶段
- “当前已实现”与“未来规划”必须明确区分，禁止混写
- 若阶段边界调整，先更新 `implementation-plan.md`，再回写本文件
