---
type: paradigma-domain
title: "Backend 架构细节"
description: "后端关键文件与 service 职责：API 路由、业务服务、模型、迁移与 worker。"
tags: ["domain", "architecture", "backend", "fastapi"]
timestamp: 2026-07-09T09:30:00+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["后端架构", "FastAPI", "service", "模型"]
    en: ["backend architecture", "fastapi", "services"]
---
# Backend 架构细节

> WARM — 后端文件清单与职责说明。HOT 核心见 [`architecture.md`](../architecture.md)。

### 5.2 backend 当前热点文件

| 路径 | 作用 |
| --- | --- |
| `backend/app/main.py` | FastAPI 入口，注册路由、异常处理、开发态 CORS 与 request id 中间件 |
| `backend/app/api/dependencies.py` | 数据库、认证、附件、通知等依赖注入 |
| `backend/app/api/routes/auth.py` | 认证入口：管理员初始化、登录 / refresh / logout、邀请创建 / 预览 / 激活 / 撤销 |
| `backend/app/api/error_handlers.py` | 统一业务异常 / 500 错误响应，返回 `request_id` 与通用错误码 |
| `backend/app/core/db_types.py` | JSON / enum DB 类型封装；`build_value_enum()` 用于按枚举值持久化 report 领域状态 |
| `backend/app/core/enums.py` | 当前已实现的基础枚举、HR 治理枚举与 Phase 4 workflow / receipt 枚举 |
| `backend/app/core/request_context.py` | request id、actor、scope、stage 与错误上下文的 ContextVar 绑定 |
| `backend/app/core/error_tracking.py` | 未捕获异常日志、上下文脱敏与 `error_events` 持久化 |
| `backend/app/models/profile.py` | 员工档案主模型 |
| `backend/app/models/hr_governance.py` | 岗位、任职关系、汇报线、字段定义、字段权限、生命周期事件、代理授权模型 |
| `backend/app/models/task.py` | 任务、依赖、日志、评论模型 |
| `backend/app/models/task_workflow.py` | Phase 4 模板、审批流、watcher、schedule 数据模型 |
| `backend/app/models/workflow_graph.py` | 工作流重构 Phase 2 图引擎核心模型：graph templates / nodes / edges、instances、node instances、deliverables、outbox events |
| `backend/app/models/notification.py` | 通知消息、delivery 与 receipt 模型 |
| `backend/app/models/error_event.py` | 系统级错误事件模型，记录 request id、scope、stage 与脱敏上下文 |
| `backend/app/services/access_control.py` | 活跃账号、管理权限、组织范围、代理授权与汇报关系解析 |
| `backend/app/services/auth_service.py` | 登录、refresh、会话签发与 Stage 2 Phase 5 邀请制注册编排 |
| `backend/app/services/user_service.py` | 用户 CRUD、Phase 6 未建档账号受限删除 |
| `backend/app/services/profile_service.py` | 档案聚合、字段裁剪、Phase 3 档案读写编排 |
| `backend/app/services/organization_relation_service.py` | 岗位目录、任职关系、汇报线管理 |
| `backend/app/services/profile_field_policy_service.py` | 字段定义初始化、字段权限解析与字段可见 / 可编辑判断 |
| `backend/app/services/hr_lifecycle_service.py` | 生命周期事件登记与档案 / 任职关系联动 |
| `backend/app/services/delegation_service.py` | 代理授权创建、撤销、状态刷新 |
| `backend/app/services/people_management_service.py` | Step 5 人员聚合服务，统一编排 users / profiles 的列表摘要与详情读模型 |
| `backend/app/services/task_service.py` | 任务状态机、评论、日志、统计、交付物提交 / 验收 / 返工，以及 watcher / board / gantt 扩展 |
| `backend/app/services/workflow_graph_service.py` | 工作流重构图引擎服务：负责单节点 dual-write、多节点图实例化、下游节点激活、实例收口、`current_node_key` 维护与实例查询；条件边求值统一委托给 `condition_evaluator`；**写路径**（`complete_node_instance` / `takeover_node_instance` / `deep_reject_to_upstream`）在成功结束时 **`await session.commit()`**；管理员接管后通过 `_sync_manual_task_projection_after_takeover` 同步手动 `Task.assignee_id` 与握手 metadata（`source_type=manual`） |
| `backend/app/services/condition_evaluator.py` | 共享条件求值模块（Phase 11-A 新增）：`is_else_condition` / `evaluate_condition` / `evaluate_routing_rules`，被图引擎（出边路由）与旧模板系统（routing_rules 桥接）共同引用 |
| `backend/app/api/attachment_serializers.py` | 附件读模型序列化：`serialize_attachment_read`（含 `download_url`），供 `attachments` / `report_center` 路由复用 |
| `backend/app/api/routes/workflow_graph_engine.py` | 工作流重构 Phase 6-7 图实例读写入口：模板实例列表、实例详情、节点完成 / 深度打回 / 接管快照；**详情响应**用显式列字段 + 已查询的 `node_instances` 组装 Pydantic，避免 `model_validate(ORM)` 触发 `node_instances` 异步懒加载 |
| `backend/app/services/workflow_rule_resolver.py` | 模板与审批流共用的 assignee rule 解析器（含 `context_var`、`department_pool`） |
| `backend/app/services/participant_resolution_service.py` | 视频 v1 参与者策略解析与 preview 快照构建 |
| `backend/app/services/task_template_service.py` | 模板 CRUD、步骤替换与模板实例化 |
| `backend/app/services/task_center_service.py` | 任务中心聚合服务；当前通过 `TaskService.list_task_inbox()`、`list_task_tracking()`、`list_task_history()` 聚合 graph-first with legacy fallback 结果，输出模板摘要、发布范围、待办、跟踪、历史与备忘 |
| `backend/app/services/legacy_task_graph_migration_service.py` | Phase 11-E 旧任务迁移服务：负责 dry-run、批次迁移、graph 锚点写回、交付物快照补建与 rollback |
| `backend/app/services/task_memo_service.py` | 个人备忘 CRUD 与关联任务校验 |
| `backend/app/models/report.py` | 汇报中心领域模型：`reports`、`report_routes` |
| `backend/app/services/report_service.py` | 汇报生命周期服务，处理逐级流转、代理委托、归档与审批挂接 |
| `backend/app/services/report_center_service.py` | 汇报中心聚合服务，输出待处理、我发起、历史、目标选项与审批选项 |
| `backend/app/services/workflow_engine_service.py` | 流程定义、流程实例、审批动作、打回 / 驳回 / 代理审批 |
| `backend/app/services/task_automation_service.py` | 周期调度、下次执行时间计算与调度触发 |
| `backend/app/services/message_center_service.py` | Step 6 消息聚合服务：按当前用户隔离 inbox，输出来源模块 / 对象 / 回跳、未读 / 已确认状态与筛选统计 |
| `backend/app/services/notification_source.py` | Step 6 通知来源辅助：统一 task / report / announcement / workflow 的来源 payload 与回跳协议 |
| `backend/app/services/notification_service.py` | 消息落库、delivery 记录、队列入队 |
| `backend/app/services/document_service.py` | 知识库文档 CRUD、可见性与附件聚合 |
| `backend/app/services/knowledge_retrieval_service.py` | 文档切块、embedding 重建、RAG 检索 |
| `backend/app/services/tool_registry_service.py` | 内置工具注册、schema 输出与执行入口 |
| `backend/app/services/llm_router_service.py` | `@系统` / `/` 路由、Tool Calling 编排 |
| `backend/app/services/browser_push_service.py` | Push 订阅管理与 Push payload 构造 |
| `backend/app/services/sample_data_service.py` | demo 组织、用户、档案、汇报线与岗位测试数据生成 |
| `backend/app/models/overview.py` | 总览相关模型：看板、看板归档、公告、公告归档 |
| `backend/app/services/board_service.py` | 看板范围、发布限制、可见查询与自动归档 |
| `backend/app/services/announcement_service.py` | 公告发布权限、活跃公告查询、撤下归档与通知广播 |
| `backend/app/services/overview_service.py` | 总览聚合服务，整合看板、公告与任务投影 |
| `backend/app/api/routes/overview.py` | 总览、看板、公告接口 |
| `backend/app/api/routes/hr_governance.py` | Phase 3 岗位、字段定义、字段权限、授权管理接口 |
| `backend/app/api/routes/task_templates.py` | 工作流 E 模板 CRUD、实例化、实例快照与 schedule 接口 |
| `backend/app/api/routes/task_center.py` | 任务中心聚合与备忘接口 |
| `backend/app/api/routes/people_management.py` | Step 5 人员聚合接口，输出统一人员列表与详情工作台数据 |
| `backend/app/api/routes/report_center.py` | 汇报中心聚合、创建与动作接口 |
| `backend/app/api/routes/workflows.py` | 流程定义、实例、待办审批与审批动作接口 |
| `backend/app/api/routes/messages.py` | Step 6 消息中心聚合 / 详情 / 回执接口，`GET /messages` 返回工作台快照而非裸消息列表 |
| `backend/app/api/routes/documents.py` | 文档 CRUD、发布、归档接口 |
| `backend/app/api/routes/knowledge.py` | 检索与知识查询接口 |
| `backend/app/api/routes/ai_router.py` | `@系统` / `/` AI Router 接口 |
| `backend/app/api/routes/push_subscriptions.py` | 浏览器 Push 订阅接口 |
| `backend/app/integrations/notifications/queue.py` | ARQ 入队发布器 |
| `backend/app/integrations/llm/openai_client.py` | OpenAI SDK 统一封装 |
| `backend/app/integrations/notifications/factory.py` | 通知 adapter 构造与分发 |
| `backend/app/integrations/notifications/web_push.py` | Web Push 发送实现 |
| `backend/app/workers/jobs.py` | 通知消费、逾期提醒、周期模板实例化、审批提醒扫描与看板归档 |
| `backend/app/workers/arq_worker.py` | ARQ worker 运行时入口与 cron 配置（含看板归档定时任务） |
| `backend/alembic/versions/20260413_01_phase1_foundation.py` | Phase 1 基线迁移 |
| `backend/alembic/versions/20260414_01_phase2_collaboration.py` | Phase 2 协同迁移 |
| `backend/alembic/versions/20260415_01_phase3_hr_governance.py` | Phase 3 HR 治理迁移 |
| `backend/alembic/versions/20260416_01_phase4_workflow_messaging.py` | Phase 4 workflow / messaging 迁移 |
| `backend/alembic/versions/20260417_01_phase5_knowledge_push.py` | Phase 5 knowledge / push 迁移 |
| `backend/alembic/versions/20260420_03_report_center.py` | Step 4 汇报中心迁移 |
| `backend/alembic/versions/20260421_01_error_events.py` | Step 4 排障新增的 `error_events` 迁移 |
| `backend/alembic/versions/20260422_01_template_runtime.py` | 工作流 E 模板运行态迁移，新增 template instances / step runs 与 task 回链 |
| `backend/alembic/versions/20260429_04_workflow_graph_core.py` | 工作流重构 Phase 2 图引擎核心迁移，新增 graph templates / nodes / edges、instances、node instances、deliverables 与 outbox events |
| `backend/alembic/versions/20260515_01_attachment_target_report.py` | `attachment_links.target_type` 枚举扩展 **`report`**（downgrade 前先删 `report` 类 link） |
| `backend/tests/conftest.py` | 测试夹具；在 import `app` 前将 `backend/` 插入 `sys.path`，支持在**仓库根**执行 `python -m pytest backend/tests` |
| `backend/app/scripts/seed_sample_data.py` | 测试组织与 demo 账号初始化脚本 |
| `backend/app/scripts/migrate_legacy_tasks_to_graph.py` | Phase 11-E 旧任务迁移 CLI，支持 `--batch-id`、`--limit`、`--dry-run` |
| `backend/app/scripts/rollback_legacy_task_migration.py` | Phase 11-E 迁移回滚 CLI，按 `batch_id` 清理 graph 侧记录并恢复任务 metadata |

### 5.3 frontend 当前热点文件

| 路径 | 作用 |
| --- | --- |
| `frontend/src/api/http.ts` | Axios 实例、token 注入、自动 refresh |
| `frontend/src/stores/auth.ts` | 登录态与会话恢复 |
| `frontend/src/stores/app.ts` | 当前阶段标识与全局项目状态文案 |
| `frontend/src/views/LoginView.vue` | 登录与管理员初始化 |
| `frontend/src/views/HomeView.vue` | 当前总览页；已承载看板、公告、待办事项、任务跟踪与快捷入口，并消费 `?announcement=` 来源回跳高亮 |
| `frontend/src/views/PeopleManagementView.vue` | Step 5 统一人员工作台：左侧人员列表，右侧账号 / 档案 / 岗位汇报 / 生命周期 / 权限视图详情 |
| `frontend/src/views/UsersView.vue` | 原用户管理工作台，当前保留为回归参考与兼容底座 |
| `frontend/src/api/people-management.ts` | Step 5 人员聚合 API client |
| `frontend/src/api/profiles.ts` | Phase 3 档案、岗位、生命周期、授权 API client |
| `frontend/src/views/ProfilesView.vue` | 原 Phase 3 档案治理工作台，当前保留为回归参考与兼容底座 |
| `frontend/src/views/KnowledgeBaseView.vue` | 知识库页面 |
| `frontend/src/views/TaskCenterView.vue` | 任务中心聚合页：`filter`（inbox/tracking/history/**stats**）+ `view`（list/board/gantt）；Master-Detail 列表/看板/甘特由 `TaskCenter*View` 子组件承载；详情区用 `TaskDetailShell`（TC-P2） |
| `frontend/src/views/TasksView.vue` | TC-P2 后瘦身为 workspace 壳层（~700 行）；详情、对话框与 profile 面板委托 `TaskDetailShell.vue`；legacy 全列表路径仍保留 |
| `frontend/src/components/task-center/TaskCenterListView.vue` | TC-P2 列表视图（Run + 用户态） |
| `frontend/src/components/task-center/TaskCenterBoardView.vue` | TC-P2 看板（列=用户态） |
| `frontend/src/components/task-center/TaskCenterGanttView.vue` | TC-P2 甘特 MVP |
| `frontend/src/components/task-center/TaskCenterStatsView.vue` | TC-P2 任务统计 Tab |
| `frontend/src/components/task-detail/TaskDetailShell.vue` | TC-P2 详情 Shell（header / meta / profile 面板 / 最近 3 条 run_events） |
| `frontend/src/views/TaskTemplatesView.vue` | 图模板页壳层：`GraphTemplatesPanel` 列表 + 实例化 Dialog；Legacy E 结构化设计器已移除 |
| `frontend/src/views/GraphTemplateDesignerView.vue` | 图模板全页设计器（`/task-templates/:id/edit`）：config/节点/边/校验/发布/导入导出/dry-run |
| `frontend/src/components/workflow/GraphTemplateDagPreview.vue` | 设计器拓扑 SVG 预览（横/纵布局、图例、打回通道、边框锚点） |
| `frontend/src/components/workflow/GraphTemplatesPanel.vue` | 图模板列表、设计/复制/改名、Run（30d）统计列 |
| `backend/app/services/workflow_graph_template_admin_service.py` | 图模板设计器 AdminService：clone/draft/publish/validate/import/export/dry-run/stats |
| `backend/app/services/workflow_graph_template_topology.py` | 模板拓扑校验：可达性/环路、ELSE 边、reject 路径、routing_rules |
| `frontend/src/views/ReportsView.vue` | 汇报中心工作台：待处理 / 我发起 / 历史三主标签；**「发起汇报」** 页头入口打开弹窗，在弹窗内选择向上汇报或向下传达并填写表单（深链 `?tab=upward|downward` 仍可自动打开对应表单）；消费消息来源 `?selected=` 高亮 |
| `frontend/src/views/MessagesView.vue` | Step 6 升级后的消息工作台：统计卡、未读 / 未确认 / 来源筛选、我的回执状态与“回到来源”入口 |
| `frontend/src/views/SettingsView.vue` | 设置页：承载浏览器 Push / PWA 订阅管理，支持多浏览器 / 多设备活跃订阅说明 |
| `frontend/src/api/overview.ts` | 总览、看板、公告 API client |
| `frontend/src/api/report-center.ts` | 汇报中心聚合、创建与动作 API client |
| `frontend/src/components/CommandBar.vue` | 全局命令入口，承载 `@系统` / `/` |
| `frontend/src/components/PushSubscriptionCard.vue` | 浏览器 Push 订阅管理卡片 |
| `frontend/src/components/AppShell.vue` | 全局壳层导航；Step 1 后改为“通用模块 / 特殊模块”分组结构 |
| `frontend/src/router/index.ts` | 路由表；Step 1 后主入口改为 `/overview`、`/task-center`、`/reports`、`/people`，并保留旧地址兼容跳转 |
| `frontend/tests/HomeView.spec.ts` | 总览展示与发布动作单测 |
| `frontend/tests/TaskCenterView.spec.ts` | Step 3 与工作流重构 Phase 1 的任务中心单测，覆盖默认 tab、旧 query 兼容与页头建立任务入口 |
| `frontend/src/api/task-center.ts` | 任务中心聚合与备忘 API client |
| `frontend/src/api/tasks.ts` | 任务、状态流转、评论、活动流、统计、watcher、多视图 API client |
| `frontend/src/api/task-templates.ts` | 模板、实例化与 schedule API client |
| `frontend/src/api/workflows.ts` | 审批定义、流程实例与审批动作 API client |
| `frontend/src/api/messages.ts` | 收件箱与回执 API client |
| `frontend/src/api/documents.ts` | 文档 CRUD API client |
| `frontend/src/api/knowledge.ts` | 检索 / 知识查询 API client |
| `frontend/src/api/ai.ts` | AI Router API client |
| `frontend/src/api/push.ts` | Push 订阅 API client |
| `frontend/src/utils/pwa.ts` | Service worker 注册与 Push 工具函数 |
| `frontend/src/types/api.ts` | 前端共享 API 类型 |
| `frontend/tests/UsersView.spec.ts` | 用户管理页回归测试 |
| `frontend/tests/ProfilesView.spec.ts` | Phase 3 档案治理页回归测试 |
| `frontend/tests/PeopleManagementView.spec.ts` | Step 5 统一人员工作台单测 |
| `frontend/tests/TasksView.spec.ts` | Phase 4 任务多视图与 watcher 回归测试；工作流重构 Phase 1 起补充嵌入任务中心 tracking 时隐藏独立创建入口的断言 |
| `frontend/tests/TaskTemplatesView.spec.ts` | 模板工作台回归测试 |
| `frontend/tests/ApprovalsView.spec.ts` | Step 4 汇报中心工作台回归测试 |
| `frontend/tests/MessagesView.spec.ts` | 消息中心回归测试 |
| `frontend/tests/KnowledgeBaseView.spec.ts` | 知识库页回归测试 |
| `frontend/tests/PushSubscriptionCard.spec.ts` | Push 订阅卡片回归测试 |
| `frontend/tests/Router.spec.ts` | Step 1 与工作流重构 Phase 1 的路由兼容跳转与导航权限回归测试，覆盖 `/task-center` 默认落点与旧 `/tasks` 兼容 |

### 5.4 infra

| 路径 | 作用 |
| --- | --- |
| `infra/docker/docker-compose.yml` | 本地开发编排：postgres / redis / backend / worker / frontend / nginx |
| `infra/docker/docker-compose.prod.yml` | 生产编排：无 bind mount、无 `--reload`、前后端使用生产镜像 |
| `backend/Dockerfile.prod` | 后端生产镜像构建 |
| `frontend/Dockerfile.prod` | 前端生产镜像构建 |
| `infra/nginx/default.conf` | `/api/` 到 backend，其余到 frontend |
| `backend/scripts/start-dev.sh` | API 启动脚本 |
| `backend/scripts/start-prod.sh` | API 生产启动脚本 |
| `backend/scripts/start-worker.sh` | Worker 启动脚本 |
| `infra/nginx/nginx.prod.conf` | 主机部署 Nginx 生产模板 |
| `infra/nginx/nginx.compose.prod.conf` | Compose 内部 gateway Nginx 生产配置 |
| `scripts/check-release.sh` | 发布前验证脚本 |

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

## 7. 阶段映射

| 阶段 | 状态 | 已落地或目标内容 |
| --- | --- | --- |
| Phase A | done | 文档入口、脚手架、基础编排 |
| Phase 1 / Foundation | done | 用户、部门、档案、附件、任务基础、异步通知骨架 |
| Phase 2 / Collaboration & Stats | done | 状态机、评论留痕、日志、ARQ 提醒、统计与协同页 |
| Phase 3 / HR Governance & Org Modeling | done | 生命周期、字段权限、多岗位、汇报线、代理授权 |
| Phase 4 / Workflow Engine & Messaging | done | 模板、审批流、自动触发、消息中心、多视图 |
| Phase 5 / Knowledge, AI Router & Experience | done | 知识库、RAG、`@系统` 路由、Push、PWA |

## 8. 数据契约（已迁出）

数据库设计原则、枚举基线、全量表结构、实体关系与 schema 维护规则已迁至 **[data-contracts.md](../../contracts/data-contracts.md)**。

本文件仅保留运行时、模块与流程层面的工程基线。修改 schema 时**先更新 data-contracts.md**，再在本文件记录受影响的模块或流程事实（如有）。

## 9. 当前验证基线

详见 [progress.md](../../../logs/progress/progress.md) 测试基线表与 [data-contracts.md](../../contracts/data-contracts.md) §维护规则。

## 10. 维护规则

- 宏观架构、运行时、模块职责、核心流程 → 更新本文件
- schema、枚举、实体关系 → 更新 [data-contracts.md](../../contracts/data-contracts.md)
- 阶段状态与验测 → 更新 [progress.md](../../../logs/progress/progress.md)
- 产品边界 → 更新 [project-brief.md](../../project-brief.md)
- 当前任务 → 更新 [active-task.md](../../../runtime/active-task.md)

