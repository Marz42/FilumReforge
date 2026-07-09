---
type: paradigma-domain
title: "核心流程"
description: "各子系统运行时流程：JWT 会话、任务协同、通知总线、附件绑定、HR 生命周期、审批流、消息中心、AI 路由、Push、图引擎、汇报中心、错误追踪。"
tags: ["domain", "architecture", "workflows", "runtime"]
timestamp: 2026-07-09T09:30:00+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["核心流程", "运行时", "链路", "JWT"]
    en: ["core workflows", "runtime", "JWT"]
---
# 核心流程

> WARM — 各子系统运行时流程细节。HOT 核心见 [`architecture.md`](../architecture.md)。

## 6. 核心流程

### 6.1 JWT 会话链路（当前）

1. `/api/v1/auth/bootstrap-admin` 初始化管理员。
2. 登录由 `AuthService.authenticate()` 校验密码并签发 access token，同时通过 `/api/v1/auth/login` 写入 HttpOnly refresh cookie。
3. 管理端可通过 `AuthService.create_invitation()` 创建未启用账号并生成注册链接；前端登录页通过 `/api/v1/auth/invitations/preview` 预览邀请邮箱、角色与有效期。
4. 邀请用户通过 `/api/v1/auth/invitations/accept` 设置密码并激活账号，服务同时签发 access token 与 refresh cookie；该路径会写入 `invitation_accepted_at` 并清空 token 哈希，这表示“已完成注册”而不是“已撤销”。
5. refresh token 的 `jti` 落库到 `refresh_tokens`；`/api/v1/auth/refresh` 从 cookie 读取 refresh token 并执行轮换。
6. 前端由 `http.ts` 只注入内存态 access token，401 时通过 `withCredentials` 自动尝试 refresh。
7. `/api/v1/auth/logout` 会撤销当前 refresh token，并清理 refresh cookie。
8. 管理员对待处理邀请执行 `/api/v1/auth/invitations/{user_id}/revoke` 时，仅写入 `invitation_revoked_at`，用于表示“管理员手动撤销邀请”；前端账号页据此与“已完成注册”作显式区分。

### 6.2 任务协同链路（当前）

1. 任务创建时自动写入 `task_logs(created / assigned)`。
2. 状态流转统一由服务层校验，只允许 `Todo -> Doing -> Review -> Done`。
3. 评论通过 `multipart/form-data` 创建，附件绑定到 `attachment_links(target_type = task_comment)`。
4. 活动流由 `task_comments` 与 `task_logs` 聚合生成。

### 6.3 通知总线链路（当前）

1. 业务服务构造 `NotificationMessage`。
2. `NotificationService.send()` 写入 `notification_messages` 与 `notification_deliveries`。
3. `RedisNotificationQueuePublisher` 通过 ARQ 把消息投递任务入 Redis。
4. `app.workers.arq_worker` 消费任务并回写状态。
5. 逾期任务扫描通过 cron 任务触发。

### 6.4 附件绑定链路（当前）

1. 前端上传文件（`el-upload` + `before-upload` 预检；`POST /api/v1/attachments`）。
2. `AttachmentService` 校验 **MIME 白名单**（图片、PDF、`.xlsx`、`.txt`/`.md`、`.docx`、`.mp3`/`.wav`；`audio/x-wav` 归一为 `audio/wav`）与 **魔数 / 文本编码**；按类型限制大小：**文本类（plain/markdown/docx）≤10MB**，**音频 ≤50MB**，**其余允许类型 ≤25MB**。
3. 通过 `ObjectStorageService` 写入对象存储，写入 `attachments` 元数据。
4. 使用 `attachment_links` 绑定到任务、档案、评论、消息、**汇报（`report`）** 等业务对象。
5. `GET /attachments`：对 `task` / `task_comment` / `report` 目标在通过对应读权限校验后，**不按 uploader 过滤**，便于参与人查看任务与汇报资料附件。
6. `GET /attachments/{attachment_id}/content`：鉴权后流式返回文件内容；`download_url` 指向该路径（`backend/app/api/attachment_content.py`）；前端通过 blob 下载，避免未鉴权直链。
7. 前端统一预检：`frontend/src/constants/attachments.ts`（`ATTACHMENT_ACCEPT`、`validateAttachmentFile`、`attachmentMimeIsInlineViewable`）；任务 / 知识库 / 汇报创建页在 `el-upload` 的 `before-upload` 与后端规则对齐；任务资料上传区使用 **`data-testid="tasks-attachment-upload"`** 包裹层（便于 E2E 与 Element Plus 内部 file input 解耦）。

### 6.5 字段级权限解析链路（当前 / Phase 3）

1. `profiles` 保存基础字段与 `custom_fields`。
2. `profile_field_definitions` 定义字段元信息。
3. `profile_field_permissions` 定义谁能看 / 改哪些字段。
4. `access_control.py` 解析部门范围、汇报线和代理授权。
5. `ProfileFieldPolicyService` 结合角色、self、直属 / 虚线上级与代理关系裁剪字段。
6. `ProfileService` 输出按 actor 过滤后的档案视图。

### 6.6 HR 生命周期链路（当前 / Phase 3）

1. 前端在档案治理页登记生命周期事件。
2. `HRLifecycleService` 写入 `employment_events`，并记录可选 `task_template_id` / `workflow_definition_id`、触发状态、错误信息与已生成实例锚点。
3. 事件按类型联动主岗位、汇报线、用户状态与档案摘要。
4. 若事件显式绑定模板或审批流目标，服务会异步入队 `process_employment_event_job`。
5. worker 通过 `HRLifecycleService.process_event_automation()` 触发模板实例化或审批流启动，并将成功 / 失败结果、尝试次数与生成实例 ID 回写到事件本身。

### 6.7 审批流链路（当前 / Phase 4）

1. 前端创建或触发事务。
2. 系统根据 `task_templates` / `workflow_definitions` 生成实例。
3. `workflow_instances` 与 `workflow_step_runs` 驱动审批与回退。
4. 结果回写任务、消息中心与通知总线。

### 6.8 消息中心链路（当前 / Phase 4）

1. 业务消息继续写入 `notification_messages`。
2. 如消息需要补充文件上下文，附件通过 `attachment_links(target_type = notification_message)` 绑定到消息本身，而不是继续只放在 payload 中。
3. `MessageCenterService` 聚合消息、附件、投递记录与回执记录，并支持来源模块、回执状态、渠道、投递状态、时间范围组合筛选。
4. 前端消息中心读取收件箱，详情页展示附件、投递尝试次数、最近错误，并通过 `notification_receipts` 写入 `read / acknowledged` 回执。

### 6.9 AI 路由链路（当前 / Phase 5）

1. 前端拦截 `@系统` 或 `/`。
2. 后端 `LLMRouterService` 构造工具清单。
3. LLM 决策调用工具。
4. 后端执行工具并返回结构化结果。
5. LLM 组织最终自然语言回复。

### 6.10 浏览器推送链路（当前 / Phase 5）

1. 前端注册 `sw.js` 并请求浏览器通知权限。
2. `PushSubscriptionCard` 创建 / 撤销浏览器订阅。
3. 后端 `push_subscriptions` 持久化活跃订阅。
4. 业务服务通过 `NotificationService.send()` 进入通知总线。
5. `NotificationService` 会按目标用户是否存在活跃订阅过滤 `WEB_PUSH` delivery。
6. worker 调用 `WebPushNotificationAdapter` 发送浏览器推送。

### 6.11 测试数据链路（当前）

1. `python -m app.scripts.seed_sample_data` 读取当前配置与数据库连接。
2. 若系统尚无管理员，则自动初始化 `admin@example.com`。
3. 创建或更新 demo 部门、岗位、用户、档案、任职关系与汇报线。
4. 输出可直接用于手工测试的账号清单。

### 6.12 总览模块链路（已完成并通过验测）

1. `HomeView.vue` 进入 `/overview` 后调用 `GET /overview`。
2. `OverviewService` 聚合看板、公告、待办事项、任务跟踪与可发布范围。
3. `BoardService` 根据当前用户的组织路径返回公司级 + 路径级看板，并限制每人最多 2 张活跃卡片。
4. `AnnouncementService` 基于 `departments.capabilities` 控制公告发布权限，并在发布时向可见用户写入系统消息。
5. ARQ worker 定时执行过期看板归档，把活跃卡片快照写入 `board_card_archives`。

### 6.13 任务中心链路（已完成并通过验测）

1. `TaskCenterView.vue` 进入 `/task-center` 后调用 `GET /task-center`，默认落在“待处理”，并兼容旧的 `?tab=tasks` / `?tab=history` -> `tracking`、`?tab=publish` -> 默认入口。
2. `TaskCenterService` 聚合模板摘要、发布权限、发布部门 / 用户选项、待办、跟踪、历史与个人备忘；待办 / 跟踪 / 历史仍委托 `TaskService.list_task_inbox()`、`list_task_tracking()`、`list_task_history()`，在默认 `TASK_CENTER_V2_ENABLED=true` 时上述方法内部优先使用 `_graph_task_projection_map` 等 graph-first 逻辑，兼容 `Task` 行作为投影与 legacy 回退载体，而非“仅扫描裸 `Task` 表语义”。
3. `TaskTemplateService` 与 `TaskAutomationService` 使用“管理角色 + 部门负责人 + 部门能力”判断模板管理与组织任务发布权限。
4. `TaskService` 输出 `list_task_inbox()`、`list_task_tracking()` 与 `list_task_history()`，前端据此拆分待办 / 跟踪，并在跟踪视图中附带历史任务区块。
5. `TaskMemoService` 负责 `task_memos` 的新增、编辑、删除，并校验关联任务是否对当前用户可见。
6. 任务跟踪标签继续复用 `TasksView.vue` 的列表 / 看板 / 甘特图、活动时间线与负载概览；建立任务入口已收敛到任务中心页头 **Dialog**，`TasksView.vue` 在嵌入 tracking 时不再暴露第二个创建入口。

### 6.13B 图引擎核心与运行时链路（Phase 2-6 当前基线）

1. `workflow_graph_templates`、`workflow_graph_template_nodes`、`workflow_graph_template_edges` 构成新的 DAG 模板定义层，支持模板版本链、节点类型、受控 `assignment_mode` / `join_mode` 和条件边存储。
2. `workflow_graph_instances` 与 `workflow_node_instances` 构成新的运行态层：实例保存 `context`、`context_version`、`max_iterations` 和来源锚点；节点实例保存引擎态、业务投影态、当前办理人、`iteration`、`node_instance_version` 以及激活 / 确认 / 完成 / 终止时间戳。
3. `workflow_deliverables` 为节点交付物快照预留独立表，不再要求后续阶段把结构化交付物塞回任务评论或任务扩展字段。
4. `workflow_outbox_events` 已接入 Phase 11-C 的 worker 消费逻辑：`process_workflow_outbox_events` 扫描 `PENDING/RETRYING` 事件，成功置 `DISPATCHED`，失败按 `attempt_count + available_at` 退避重试，超上限置 `FAILED` 并记录 `last_error`。
5. Phase 3 新增 `WorkflowGraphService.create_single_node_instance()`，在 `WORKFLOW_GRAPH_ENGINE_ENABLED=true` 且 `TaskSourceType=manual` 时，由 `TaskService.create_task_record()` 先创建 graph instance / node instance，再同步创建兼容 `Task`、`TaskDependency` 和 `TaskLog`，并在 `WorkflowGraphInstance.source_id` 与 `Task.extra_metadata` 中互写锚点。
6. 在上述单节点 dual-write 基线上，`TaskService.submit_task_deliverable()` 与 `review_task_deliverable()` 已补交付说明 / 附件校验、`WorkflowDeliverable` 快照持久化、返工计数与最近返工原因回写，并把 graph node / instance 与兼容 `Task.status` 同步推进到 `review`、`done` 或返工后的 `doing`。
7. `TaskService.accept_task()`、`reject_task()`、`delegate_task()` 已把 graph 手动任务的业务态推进补齐到“待确认 / 已接受待开工 / 已拒绝待调整 / 待验收”投影语义，并继续通过兼容 `Task.extra_metadata` 对读取侧暴露握手上下文。
8. Phase 6 新增 `WorkflowGraphService.create_multi_node_instance()` 与 `complete_node_instance()`：基于 `WorkflowGraphTemplate` 一次性创建全部节点实例，仅激活无入度起始节点；后续在事务内按模板边关系推进顺序流、fan-out 和 wait-all join，并在所有节点完成后把 `WorkflowGraphInstance.status` 收口到 `COMPLETED`。
9. Phase 6 的图实例收口逻辑已补实例级 `SELECT ... FOR UPDATE`、节点版本号递增、重复完成幂等保护，以及基于模板 `sort_order` 的稳定 `current_node_key` 解析，避免 fan-out 场景下因激活顺序不稳定导致前端当前节点指示漂移。
10. Phase 7 在 `complete_node_instance()` 上补 `context_updates` 输入，节点完成时可把结构化字段写入 `WorkflowGraphInstance.context` 并递增 `context_version`；出边路由支持 `eq/neq/gt/gte/lt/lte/in/not_in/contains/exists` 与 `else` 默认分支，未命中普通规则时走 `else`。
11. Phase 7 补齐 `Notice Node` 触达即完成：Notice 节点被激活后会在同一事务链中自动置为 `COMPLETED` 并继续推进下游，不阻塞主链路。
12. `backend/app/api/routes/workflow_graph_engine.py` 现提供 `GET /workflow-graph/templates/{template_id}/instances`、`GET /workflow-graph/instances/{instance_id}`、`POST /workflow-graph/node-instances/{node_instance_id}/complete`、`POST /workflow-graph/node-instances/{node_instance_id}/deep-reject`、`POST /workflow-graph/node-instances/{node_instance_id}/takeover`、`POST /workflow-graph/smart-notice-candidates` 等端点，返回图实例与节点实例快照、节点统计和 `progress_percent`；写操作由 `WorkflowGraphService` 提交事务后跨请求可见。
13. **任务中心读路径（Phase 11-F，与代码一致）**：`TaskService.list_task_inbox()`、`list_task_tracking()`、`list_task_history()` 在 `TASK_CENTER_V2_ENABLED=true`（`Settings` 默认值，见 `backend/app/core/config.py`）下对具备图锚点的任务优先解析 `WorkflowGraphInstance` / `WorkflowNodeInstance` / `WorkflowDeliverable`，再与未迁移的 legacy 任务合并排序；`TaskCenterService.get_task_center()` 仍调用上述三方法，前端 `GET /task-center` 协议保持稳定。Phase 11-E 迁移 CLI 与 Phase 11-F 默认切流已在仓库落地；深度打回等写路径见 Phase 9 / 11-D。若环境显式关闭 `TASK_CENTER_V2_ENABLED`，则回退为纯 legacy 列表语义。**批次 ROOT shell**（`@ 0.91.1`）：`_resolve_graph_task_status` 对 `run_kind=batch` 的 ROOT 以图实例生命周期判定完成态，避免 streaming N2 skip 导致派发前误入历史。

14. **任务中心增强（TCE，@ 2026-06-21）**：Phase 1–5 已落地（读模型、batch hydration、部门统计、多部门实例化、TC-P3 清理）；**图模板设计器 D1–D3** 已落地（`WorkflowGraphTemplateAdminService` + `GraphTemplateDesignerView`）。仍开放 backlog：**B-12**（Legacy E 后端）、**F-05**（Shell 拆分）、**F-10–F-12**（抛光）— 见 [`domains/task-center.md`](../domains/task-center.md) §10。

### 6.13A 工作流 E 模板运行态链路（Legacy，无 UI）

> **用户可见 authoring** 已迁至图模板设计器（`GraphTemplateDesignerView` + `WorkflowGraphTemplateAdminService`）；下列 E 链路仍供历史实例与 B-12 迁移参考。

1. ~~`TaskTemplatesView.vue` 结构化表单编辑~~ → 已移除；图模板走 `/task-templates/:id/edit`。
2. `POST /task-templates/{template_id}/instantiate` 由 `TaskTemplateService.instantiate_template()` 创建 `task_template_instances` 记录，并触发首批就绪步骤激活。
3. `TaskService.activate_template_instance_steps()` 根据依赖、`assignment_mode` 与 `join_mode` 创建 `task_template_step_runs` 和真实任务；未来步骤保持为实例快照中的 `ready` / `blocked` 状态，而不会提前混入任务列表。
4. 模板关联任务完成后，`TaskService` 会回写步骤运行态，并在满足 `all` / `any` 汇聚条件时自动激活下游步骤。
5. `GET /task-templates/{template_id}/instances` 返回步骤快照、阻塞依赖、step run 与关联任务，前端据此展示当前激活步骤、未来步骤和实例任务。
6. 当前仅允许删除“从未实例化过”的模板；已有实例的模板仍可更新名称、描述等元数据，但步骤结构会在前后端同时被锁定，避免破坏历史运行态。

### 6.14 汇报中心链路（Step 4 已完成并通过验测）

1. `ReportsView.vue` 进入 `/reports` 后调用 `GET /report-center`，默认落在“待处理”，同时保留 `/approvals` -> `/reports` 的兼容跳转。
2. `ReportCenterService` 聚合待处理、我发起、历史归档、向上 / 向下目标选项，以及可选审批流定义。
3. `ReportService` 基于 `reporting_lines` 的主汇报线计算逐级路径，生成 `reports` / `report_routes`，并处理继续流转、退回与归档。
4. 路由节点激活时会解析 `DelegationScopeType.ALL` 的有效代理，把当前处理人切换为代理人，并经 `NotificationService` 写入消息中心与浏览器推送链路。
5. 如用户选择挂接审批流，`ReportService` 会同步启动 `workflow_instance`，并将其绑定到 `report.workflow_instance_id`。
6. `reports` / `report_routes` 领域枚举现在按 `enum.value` 持久化，确保 ORM 写库值与 PostgreSQL check constraint 的小写枚举值一致。

### 6.15 错误追踪与诊断链路

1. `RequestContextMiddleware` 为每个 HTTP 请求生成或透传 `X-Request-ID`，并把 request id 写入响应头。
2. `get_current_user()` 会把当前用户写入 request context；`ReportService.create_report()` 会持续标记 `scope`、`stage` 与脱敏业务上下文。
3. 所有未捕获异常都会经 `handle_unhandled_exception()` 统一返回带 `request_id` / `error_code` 的 500，并把错误详情写入 `error_events`。



## 维护规则

与 [`architecture.md`](../architecture.md) §10 同步维护。
