---
type: paradigma-architecture
title: "Project Filum — 系统架构"
description: 模块化单体架构：模块划分、目录结构、交互流程、架构约束。
tags:
  - architecture
  - modules
  - constraints
timestamp: 2026-07-16T21:19:21+08:00
paradigma:
  schema_version: 0.5.0
  temperature: hot
  lifecycle: evolving
  update_policy: requires-human-confirmation
  epistemic_status: confirmed
  retrieval_hints:
    zh:
      - 系统架构
      - 模块划分
      - 目录结构
    en:
      - "system architecture"
      - "module layout"
---
# Project Filum 架构基线

**文档版本**: v3.16.2（与产品 SemVer [`VERSION`](../../VERSION) 独立）
**最后同步**: 2026-07-16 · 下一焦点: [workflow-graph-engine-iteration3f-readiness-gate-plan.md](./plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md)

## 1. 文档定位

本文件是 Project Filum 的**工程架构蓝图**，负责回答：

1. 当前代码已经实现了什么（模块级）
2. 当前系统是如何运行的
3. 当前仓库里关键文件分别负责什么
4. 核心业务流程如何串联

**数据库 schema、枚举与 API 契约** → [`data-contracts.md`](./contracts/data-contracts.md)  
**产品愿景与功能边界** → [`project-brief.md`](./project-brief.md)  
**核心流程** → [`domains/architecture/core-workflows.md`](./domains/architecture/core-workflows.md)

## 2. 当前系统概览

### 2.1 已经完成的阶段

- Phase A / 文档与工程基线
- Phase 1 / Foundation
- Phase 2 / Collaboration & Stats
- Phase 3 / HR Governance & Org Modeling
- Phase 4 / Workflow Engine & Messaging
- Phase 5 / Knowledge, AI Router & Experience

### 2.2 当前已实现能力

- 用户、JWT access token、HttpOnly refresh cookie 轮换 / logout 撤销、管理员初始化
- 部门树、部门负责人、组织范围查询
- 员工档案基础 CRUD、字段裁剪视图与 `custom_fields JSONB`
- 岗位目录、多岗位关系、直属 / 虚线汇报线
- 字段定义、字段级权限策略与代理授权生效判断
- 生命周期事件：入职、转岗、晋升、奖惩、离职、返聘，以及显式绑定模板 / 审批目标后的异步联动与状态回写
- 代理授权：创建、撤销、按时间窗自动生效 / 过期
- 任务创建、重新指派、前置依赖建模与开始前依赖校验
- 严格任务状态机：`Todo -> Doing -> Review -> Done`
- 任务评论、内部备注、审计日志、评论附件、活动时间线
- 任务模板、模板步骤依赖建模、模板实例运行态、按依赖逐步激活、多人扇出 / 汇聚、watcher / 抄送与周期调度
- Stage 2 Phase 2 首批前端治理：模板设计器已补步骤编码重复、循环依赖、孤岛步骤、单任务多人负责人规则校验，并新增流转关系邻接预览
- Stage 2 Phase 2 第二批治理：模板已补 `base_code + version + source_template_id` 版本语义、实例化后结构锁定提示与“新建版本”入口；调度已补最近执行时间 / 结果 / 任务数 / 失败消息；模板实例运行态已补整体进度、阻塞 / 就绪统计与步骤迭代批次展示
- Stage 2 Phase 2 收口：模板实例激活入口已按 `TaskTemplateInstance` 行级串行化，补齐 fan-out / join 下游步骤重复激活约束；worker / service 回归已覆盖调度成功与失败状态回写、重复激活入口幂等和模板页构建验证
- Stage 2 Phase 3 首轮实现：生命周期事件已补 `task_template_id` / `workflow_definition_id` 显式联动目标、`trigger_status` / `triggered_at` / `trigger_error` / `trigger_attempt_count` 状态字段，以及 `triggered_*_instance_id` 幂等锚点；`HRLifecycleService` 现在会异步入队 `process_employment_event_job`，由 worker 触发模板实例或审批流并回写结果
- 轻量审批流引擎：流程定义、实例、步骤执行、代理审批、打回 / 驳回
- ARQ worker、逾期提醒扫描、通知消息落库、adapter 分发与异步入队
- 消息中心收件箱、用户回执、审批提醒与系统消息聚合
- Stage 2 Phase 4 首轮深化：消息已接入 `attachment_links(target_type = notification_message)` 附件绑定；消息中心已补来源模块 + 回执状态 + 渠道 + 投递状态 + 时间组合筛选，详情页可见附件、投递尝试次数与失败原因
- Stage 2 Phase 5 首轮实现：认证已补邀请制注册，管理员可创建未启用账号并生成邀请链接；登录页支持邀请预览与设置密码激活；人员工作台“新建账号”对话框支持“直接创建 / 邀请注册”双路径
- Stage 2 Phase 6 补丁增强：人员工作台账号页已明确区分邀请“已手动撤销”与“已完成注册（非撤销）”；管理员可删除未建档且未被业务数据引用的账号
- Step 6 消息联动收口：严格用户级收件箱隔离、消息来源模块 / 来源对象 / 来源回跳、未读 / 已确认状态与聚合筛选
- Inbox-first 任务中心：主筛选 **待处理 / 跟踪 / 历史**；页头 **建立任务** 为居中 **Dialog**（含未保存关闭确认）；筛选摘要卡；`GET /api/v1/tasks/search`；`FilumDateTimePicker` / `FilumDateTimeRangePicker`；全局 **个人备忘** 为右下角浮窗（列表 + 新建/编辑 Dialog，可选 `title`）；任务模板在 `/task-templates`
- 工作流图引擎 schema 现为 **十四表**：十三表运行时/Link/receipt 基线 + `workflow_operational_incidents`。新模板 Run 使用 snapshot format v2 / `graph-v3`；既有 executor 不原地升级。Iteration 3-F 以 `WorkItemWriteService` / `WorkflowRuntimeWriteService` 固化独占写端口，`HumanTaskCoordinator` 只编排同一 UoW，全仓库 AST guard 阻止越界写和内部 commit；Link 支持 iteration/superseded，readiness API/CLI 可查询 fallback、Coordinator/Receipt/Outbox 异常、engine version 与未迁移对象。兼容 JSON 仍双写，目标环境连续 7 天零 fallback 且最终批准前 Iteration 4 保持 blocked
- 工作流重构 Phase 3：后端已新增 `WORKFLOW_GRAPH_ENGINE_ENABLED` 等 feature flag、`WorkflowGraphService` 单节点实例创建服务，并让 `TaskService.create_task_record()` 在手动创建任务且开关开启时走“graph instance + node instance + 兼容 Task 投影”双写路径；兼容 `Task` 行仍是列表与详情载体，`TaskCenterService` 仍委托 `TaskService.list_task_inbox()` 等三接口，但在 `TASK_CENTER_V2_ENABLED=true`（`backend/app/core/config.py` 默认）时上述列表优先使用 `_graph_task_projection_map` 解析 `WorkflowGraphInstance` / `WorkflowNodeInstance` / `WorkflowDeliverable`，未命中图投影时回落既有 legacy 规则
- 工作流重构单节点交付闭环首轮：基于上述 Phase 3 双写链路，`TaskService` / `tasks` API 已新增“提交交付物”“通过验收”“打回返工”动作，交付快照写入 `workflow_deliverables`，兼容 `Task` 投影通过 `extra_metadata` 暴露最近交付说明、最近提交时间、返工原因、返工次数与最近质量评分；`TaskCenterService` / `task-center` API / `TaskCenterView` 已同步投影待验收、最近提交时间、返工次数、质量评分等跟踪信号；同时禁止 graph 手动任务通过通用状态流转接口直接跳过交付 / 验收动作
- 工作流重构 Phase 4：graph 手动任务默认以 `ASSIGNED` 节点业务态创建；`TaskService` / `tasks` API / `TasksView` 已新增“接受任务”“退回协商”“转办”动作，`todo -> doing` 现在要求执行人先确认接单；兼容读取侧继续使用 `Task.extra_metadata` + `TaskCenterService` 投影当前握手阶段、当前处理人与最近协商 / 转办原因
- graph-v3 运行时：显式 `exclusive/inclusive/parallel/first_match`，未选专属路径 `skipped`，Join 只等待实际产生分支，no-route/死 Join 写 failed diagnostics；完成要求合法 End、无活动/悬挂/失败节点。Context patch 使用 expected version + diff event；Deep-Reject 失效旧 traversal/dependency 并阻断旧 iteration；所有节点命令统一 Run→Node 锁顺序
- 工作流重构 Phase 8-9：Wait-Any（`join_mode=any`）并发撤权与幂等保护、被撤权 `TERMINATED` 节点按终态参与实例完成判定；深度打回（`deep_reject_to_upstream`）可达性校验与 append-only 版本链（`iteration+1` 克隆）、超出 `max_iterations` 阻止；`TasksView` 展示 V{n} 版本角标与打回原因
- 工作流重构 Phase 10 前端化：`frontend/src/api/workflow-graph.ts` 新增 `getWorkflowGraphInstance`；`frontend/src/types/api.ts` 补充 `WorkflowGraphInstanceDetail` / `WorkflowNodeInstanceSummary` 等图引擎 TS 类型；`TasksView` 打开图任务详情时 fetch 图实例并渲染节点板块列表（标题 / engine_state 标签 / V{n} 角标 / 耗时）；`TaskCenterView` 任务跟踪表格新增逾期标签（due_date < now && status != done）与催办按钮（写入系统催办评论）；**图模板设计器**（@ 2026-06-21 功能，@ 2026-06-22 UX）：`GraphTemplateDesignerView.vue` 全页 authoring（config/节点/边/routing_rules/校验/发布/导入导出/dry-run），`GraphTemplateDagPreview.vue` 拓扑预览（横/纵、图例、打回正交圆角通道），`GraphTemplatesPanel` 列表 Run 统计 + 空白新建
- 工作流重构 Phase 11-A / routing_rules 旧系统桥接：新建 `backend/app/services/condition_evaluator.py` 作为两套工作流系统（图引擎 + 旧模板系统）共享的条件求值模块，提供 `is_else_condition` / `evaluate_condition` / `evaluate_routing_rules` 函数，支持 `eq/neq/gt/gte/lt/lte/in/not_in/contains/exists` 与嵌套 `all/any`；`WorkflowGraphService` 的内联条件求值方法全部迁移至该模块；`TaskService._activate_ready_template_steps` 新增 `_routing_rules_allow_step_activation` 静态方法，当上游 `TaskTemplateStep.config.routing_rules` 存在时以 `instance.payload` 作为上下文评估条件，仅激活命中目标的下游步骤；无规则时保持完全向后兼容
- 工作流重构 Phase 11-B/11-C/11-D（已完成）：`WorkflowGraphService` 新增 `takeover_node_instance()`（管理员接管节点、写 takeover 审计信息），并引入 `_write_outbox_event()` 在事务内写入 `workflow_outbox_events`；新增 `backend/app/workers/workflow_outbox_worker.py` 消费 outbox 事件，`backend/app/workers/arq_worker.py` 已注册 30 秒定时任务 `process_workflow_outbox_events_job`，对 `PENDING/RETRYING` 事件执行异步投递与指数退避重试，超上限置 `FAILED`；11-D 已补 graph 写接口事务提交、管理员接管后的手动 `Task` 投影同步（执行人 / 握手标签 / 任务中心入口）、`TaskService` 对失效 graph 节点的 accept / reject / delegate 守卫、`complete_node_instance()` 对 `COMPLETED` 重放的幂等返回与对 `TERMINATED` 迟到提交的 409 拦截，以及 Wait-All / Wait-Any 重放、stale deep-reject、complete API 重放稳定快照的回归覆盖；生产环境 `FRONTEND_APP_URL` 也已改为必填，避免邀请注册链接回落到 localhost
- 工作流重构 Phase 11-E/11-F（已完成）：`backend/app/services/legacy_task_graph_migration_service.py`、`backend/app/scripts/migrate_legacy_tasks_to_graph.py` 与 `backend/app/scripts/rollback_legacy_task_migration.py` 已支持 legacy task 批次迁移 / rollback；`TaskService.list_task_inbox()`、`list_task_tracking()`、`list_task_history()` 现已在 `TASK_CENTER_V2_ENABLED` 下默认走 graph-first with legacy fallback，优先解析 `WorkflowGraphInstance` / `WorkflowNodeInstance` / `WorkflowDeliverable`，修正 migrated review task 的责任链展示；`WORKFLOW_GRAPH_ENGINE_ENABLED` 与 `TASK_CENTER_V2_ENABLED` 默认值均已切到 `true`，旧创建 / 旧读侧仅保留为显式关闭开关时的紧急回退
- 工作流重构 Phase 11-G（已完成）：前端已新增 Playwright 基线与真实后端联动基线。`frontend/playwright.config.ts` 现覆盖 mock API 驱动的登录 / 会话恢复 / 任务中心标签切换 / graph-first 详情场景；`frontend/playwright.live.config.ts` 则通过 `frontend/e2e/live/docker-compose.playwright-live.yml` + 隔离 Compose 端口启动 PostgreSQL / Redis / backend / worker / frontend / nginx，并在 backend 容器内执行 `python -m app.scripts.seed_sample_data`，验证真实登录与任务中心建立任务链路。为支撑稳定浏览器断言，`LoginView.vue`、`TaskCenterView.vue`、`TasksView.vue` 已补最小 `data-testid` 锚点；`frontend/README.md` 已同步新增 mock/live 两套 E2E 命令说明
- 汇报中心：向上汇报、向下传达（**统一「发起汇报」弹窗入口**）、逐级流转、历史归档与可选审批挂接
- 任务中心列表 / 看板 / 甘特图多视图与活动时间线 / 负载概览
- S-01 周期统计：Employee 本人、经理/数据代理部门子树、Admin/HR 全局；Asia/Shanghai 周期；SQL 聚合摘要/人员负载/分页明细，排除归档与 graph ROOT
- 文档知识库、RAG 检索、LLM Router 与 Tool Calling
- 浏览器 Push 订阅、Web Push adapter 与 PWA manifest / service worker 基线
- 浏览器后台界面：已切换到“通用模块 / 特殊模块”壳层导航；总览页已落地看板、公告、待办事项、任务跟踪与任务中心快捷入口
- 特殊模块中的 `/people` 已升级为统一人员工作台：左侧人员列表，右侧账号 / 档案 / 岗位汇报 / 生命周期 / 权限视图多标签详情
- 测试数据脚本：可重复生成 demo 组织、档案与账号
- request id、统一 500 错误收口与 `error_events` 诊断链路

### 2.3 当前明确缺口

- 公开注册 / 审批式注册仍为缺口 — **明确不做**；未来接入邮箱发送邀请链接
- Legacy E 首批能力属于历史基线；B-12 后对外模板实例化与周期调度已统一到图模板/图运行时。旧 `task_templates` 表族、模型和未挂载服务暂保留用于兼容与迁移，后续重点是历史数据清理策略，而非继续扩展 Legacy E
- 工作流重构已完成 Phase 3-11-G：含手动创建 dual-write、交付 / 验收 / 返工、握手 / 转办、多节点推进、Context 写回、条件边与 Notice、智能抄送候选、Wait-Any 撤权、深度打回、routing_rules 桥接、outbox、迁移 CLI、**任务中心列表 graph-first 读路径**（`TASK_CENTER_V2_ENABLED`）、Playwright 基线等。仍待深化的方向：Legacy E 历史表族迁移/清理、全量回归与部署演练；当前产品入口已统一到图模板，不再暴露 `TaskTemplateService` 实例化 API
- 生命周期事件与任务模板 / 审批流的规则化默认联动、前端结构化配置入口仍未落地；当前已支持在事件写入时显式绑定目标并异步触发
- 生产 compose、主机部署脚本与 Nginx 生产配置已落地；**Stage 2 Phase 6** 已记录在线 Ubuntu 主机演练与 2026-05-21 测试基线；**最小回滚路径**仍待演练
- HR 字段权限的可视化规则管理页仍偏基础
- 消息外部渠道深化、失败重试与更完整投递观测
- Email / WebSocket 渠道的外部真实接入仍是最小实现后的下一步
- 更大范围的集成测试、端到端验证扩面；docker-gui / Playwright 与发布 commit 的定期基线刷新
- **视频工作流 v1（W0–W10 已落地，v1 硬化完成）**：排期见 `memory-bank/knowledge/plans/workflow-video-v1-implementation-plan.md` v2.0。产品口径为 **一次选题会（批次 Run）→ 选题清单 `approved_topics[]` → 按题 fork 子 Run（`video_production_per_topic_v1`）**；**无**独立「发起选题会」入口（选题会为图模板之一）。模板引擎增量：**`launch_schema` / `capture_schema` / `aggregate_schema`**（Pydantic：`backend/app/schemas/workflow_video.py`）。**W1 已落库**：`workflow_node_instances.instance_key`；`workflow_graph_instances.run_label` / `parent_instance_id`（迁移 `20260522_01`）。**W2 已落地**：`ParticipantResolutionService`（`participant_policies` + all/subset）、`POST /api/v1/workflow-graph/templates/{id}/preview-participants`；`workflow_rule_resolver` 扩展 `context_var` / `department_pool`。运行时以 `workflow_graph_*` + `Task` 为主；B-12 后 Legacy E 实例化入口已移除。开关：`workflow_graph_template_engine_enabled` 默认 `false`（ADR：`workflow-video-v1-w0-adr.md`）；`backend/app/core/workflow_video_policy.py`。**W8**：运行事件落库表 `workflow_run_events`（迁移 `20260523_01`）、`WorkflowRunEventService`、`GET /api/v1/workflow-graph/instances/{id}/events`；采集/汇总/fork/打回/实例化/节点完成等写入事件（不再使用 `context.run_events`）。**W9**：`workflow_node_activated` 写入 `workflow_outbox_events`（实例化/下游激活）；`GET/PATCH /workflow-graph/templates/{id}` 维护模板 config；`GET /workflow-graph/feature-flags`。**W10**：Playwright mock 纵向 E2E（`frontend/e2e/workflow-video-v1.spec.ts` + `workflow-video-mock.ts`）；后端 `test_workflow_video_w10_regression.py` 聚合 WFK/W5/W8 关键路径；Runbook §6–§7。

## 3. 模块边界与状态映射

| 模块 | 责任 | 当前状态 | 下一阶段重点 |
| --- | --- | --- | --- |
| IAM | 账号、JWT、基础 RBAC、会话安全 | 已实现 Phase 3 增强版；Stage 2 Phase 5 已补邀请制注册、注册链接校验与激活 | 公开注册 / 审批式注册决策与更细粒度账号开通流程 |
| Organization | 部门树、部门负责人、组织范围 | 已实现 Phase 3 增强版 | 被 Workflow / Messaging 消费 |
| HR Profiles | 主档案、动态字段、基础资料 | 已实现 Phase 3 增强版 | 与模板 / 审批联动 |
| HR Governance | 奖惩、晋升、离职、授权与关系模型 | 已实现 | 事件与模板 / 审批联动 |
| Workflow Core | 任务、依赖、状态机、统计 | 已实现 Phase 4 增强版；任务开始前可阻止未满足依赖的流转 | 与模板实例运行态、Knowledge / AI / 生命周期自动化联动 |
| Workflow Engine | 图模板、审批、自动触发、周期调度，以及图引擎核心 schema | 已实现增强版；Phase 2–11 已覆盖图 schema、dual-write、交付验收、握手、多节点推进、Context、条件路由、Notice、Wait-Any、深度打回、outbox 与 graph-first；B-12 已移除 Legacy E 产品入口，`task_templates` 表族仅保留兼容 | Legacy E 历史数据清理策略、模板 / 调度管理深化、全量回归 |
| Task Collaboration | 评论、日志、评论附件、时间线、watcher | 已实现 Phase 4 增强版 | 与消息中心、推送渠道打通 |
| Notification Bus | 消息落库、delivery 记录、ARQ 入队、逾期扫描 | 已实现 Phase 4 增强版 | 真实渠道适配器、浏览器推送 |
| Messaging Center | 收件箱、确认回执、审批提醒聚合 | 已实现 Step 6 增强版；Stage 2 Phase 4 已补消息附件、渠道 / 投递状态 / 时间筛选与失败详情展示 | 渠道融合、推送 |
| File Storage | 附件元数据、对象存储抽象、业务绑定 | 已实现 | 扩展到消息 / 生命周期事件附件 |
| Knowledge Base | Markdown 文档、向量检索、RAG | 已实现基础版 | 文档治理、检索质量与运营化 |
| AI Router | `@系统` / `/` 指令路由、Tool Calling | 已实现基础版 | 工具面扩展与安全 / 观测增强 |
| Frontend Experience | 浏览器后台、分组导航、总览模块、统一人员工作台、Inbox-first 任务中心、汇报中心、消息中心、设置模块、Push / PWA，以及 Playwright mock/live 双轨浏览器回归 | 重构 Step 1-7 与工作流重构 Phase 1-11-G 已完成并通过当前自动化验证 | 部署近似环境演练、更多真实业务场景 E2E 扩面 |
| Platform Tools | 内置工具注册与暴露 | 已实现基础版 | 工具面扩展与治理 |

## 4. 运行时拓扑

### 4.1 当前运行时

```text
[ Browser ]
    |
    v
[ Nginx / Vite Dev Server ]
    |
    v
[ FastAPI ]
    |-- app.api
    |-- app.services
    |-- Workflow Engine
    |-- Message Center
    |-- LLM Router
    |-- app.integrations
    |
    +--> PostgreSQL / pgvector
    +--> Redis / ARQ Queue
    +--> Object Storage Adapter (local now, S3-compatible later)
    +--> Email / WebSocket / Web Push Adapters

[ ARQ Worker ]
    |-- app.workers.arq_worker
    |-- app.workers.jobs
    |-- Scheduled Tasks / Approval Reminders
    |-- Notification Delivery / Embedding Jobs
    |
    +--> PostgreSQL / pgvector
    +--> Redis / ARQ Queue
```

### 4.2 后续增强运行时

> 见 §2.2 已实现能力与 §2.3 缺口；远期拓扑以当前运行时为基础扩展通知适配、对象存储与测试面。

### 4.3 当前本地开发路径

1. **Compose 路径（推荐）**
   - `postgres`
   - `redis`
   - `backend`
   - `worker`
   - `frontend`
   - `nginx`
   - `backend` 与 `worker` 启动时都会执行 `alembic upgrade head`
   - `frontend` 使用独立 `node_modules` 命名卷；入口脚本比较 `package-lock.json` 哈希，仅在锁文件变化时执行 `npm ci` 同步依赖

2. **本地直启路径**
   - `backend/.env.example` 默认指向 `localhost`
   - `backend/scripts/start-worker.sh` 可直接启动 ARQ worker
   - `frontend` 默认请求同主机 `:8000/api/v1`
   - 可通过 `VITE_DEV_API_PROXY_TARGET` 使用代理

## 5. 代码组织与关键文件职责

### 5.1 memory-bank

> 完整文件清单已按模块拆分：
> - Backend 热点文件 → [`domains/architecture/backend-architecture.md`](./domains/architecture/backend-architecture.md)
> - Frontend 热点文件 → [`domains/architecture/frontend-architecture.md`](./domains/architecture/frontend-architecture.md)
> - Infra 文件 → [`domains/architecture/infra-architecture.md`](./domains/architecture/infra-architecture.md)


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

数据库设计原则、枚举基线、全量表结构、实体关系与 schema 维护规则已迁至 **[data-contracts.md](./contracts/data-contracts.md)**。

本文件仅保留运行时、模块与流程层面的工程基线。修改 schema 时**先更新 data-contracts.md**，再在本文件记录受影响的模块或流程事实（如有）。

## 9. 当前验证基线

详见 [progress.md](../logs/progress/progress.md) 测试基线表与 [data-contracts.md](./contracts/data-contracts.md) §维护规则。

## 10. 维护规则

- 宏观架构、模块职责 → 更新本文件
- 后端/前端/Infra 文件清单 → 更新 `domains/architecture/` 子文件
- 核心流程 → 更新 `domains/architecture/core-workflows.md`
- schema、枚举、实体关系 → 更新 [data-contracts.md](./contracts/data-contracts.md)
- 阶段状态与验测 → 更新 [progress.md](../logs/progress/progress.md)
- 产品边界 → 更新 [project-brief.md](./project-brief.md)
- 当前任务 → 更新 [active-task.md](../runtime/active-task.md)
