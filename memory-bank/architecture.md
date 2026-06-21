# Project Filum 架构基线

**文档版本**: v3.12.2（工程基线修订号，与产品 SemVer [`VERSION`](../VERSION) `0.89.0` 独立）  
**最后同步**: 2026-06-21 @ TCE Phase 5 + 图模板设计器 D1–D3 · 产品基线 `0.89.0`  
**状态摘要**: Phase A–5、重构 Step 1–7、UI IA A–F、工作流图引擎 Phase 11-G、视频工作流 v1 W0–W10、Stage 2 Phase 0–6、任务中心 v2 TC-P0–P2+ @ `0.89.0` 均已落地；**下一工程焦点**为 [`plans/task-center-enhance.md`](./plans/task-center-enhance.md) Phase 1。**Ubuntu 最小回滚演练**与 **Docker A–F 手工实测**仍为待办。细节见 [`progress.md`](./progress.md) 与 [`roadmap.md`](./roadmap.md)。  
**适用范围**: 当前仓库代码、完整数据库 schema、Phase 5 已交付基线，以及当前重构执行路径下的工程边界

## 1. 文档定位

本文件是 Project Filum 的**工程架构蓝图**，负责回答：

1. 当前代码已经实现了什么（模块级）
2. 当前系统是如何运行的
3. 当前仓库里关键文件分别负责什么
4. 核心业务流程如何串联

**数据库 schema、枚举与 API 契约** → [`data-contracts.md`](./data-contracts.md)  
**产品愿景与功能边界** → [`project-brief.md`](./project-brief.md)

文档职责分工如下：

- `memory-bank/README.md`：文档索引（温度体系）
- `project-brief.md`：产品目标、受众、功能边界、技术栈摘要
- `architecture.md`：工程基线、运行时、模块职责、核心流程（本文件）
- `data-contracts.md`：schema、枚举、实体关系、API 索引
- `conventions.md`：编码与协作规范
- 当前任务 → 更新 [active-task.md](./active-task.md)
- `plans/implementation-plan.md`：宏观开发顺序
- `progress.md`：阶段验收与会话摘要

### 1.1 Stage 2 文档同步约定

当前仓库已完成历史 Phase A-5，本轮后续增强统一归入 `Stage 2` 周期，并以 `memory-bank/plans/improvements-stage2-implementation-plan.md` 作为阶段基线。

- Stage 2 每个阶段完成后：schema 变化 → 先更新 `data-contracts.md`；模块/流程事实 → 更新本文件；验测 → 更新 `progress.md`。

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
- 工作流重构 Phase 2：图引擎核心 schema 已落库，新增 `workflow_graph_templates`、`workflow_graph_template_nodes`、`workflow_graph_template_edges`、`workflow_graph_instances`、`workflow_node_instances`、`workflow_deliverables`、`workflow_outbox_events` 七张表，以及图模板状态、图实例状态、节点引擎态、节点业务投影态、outbox 事件状态枚举；Phase 3 起已接入手动任务的 graph dual-write；任务中心待办 / 跟踪 / 历史在默认 `TASK_CENTER_V2_ENABLED=true` 下为 graph-first with legacy fallback（见 Phase 11-F）；工作流 E（`task_templates` / `TaskTemplateService.instantiate_template`）仍为独立运行时，与 `WorkflowGraphTemplate` 多节点图并存，尚未合并为单一模板源
- 工作流重构 Phase 3：后端已新增 `WORKFLOW_GRAPH_ENGINE_ENABLED` 等 feature flag、`WorkflowGraphService` 单节点实例创建服务，并让 `TaskService.create_task_record()` 在手动创建任务且开关开启时走“graph instance + node instance + 兼容 Task 投影”双写路径；兼容 `Task` 行仍是列表与详情载体，`TaskCenterService` 仍委托 `TaskService.list_task_inbox()` 等三接口，但在 `TASK_CENTER_V2_ENABLED=true`（`backend/app/core/config.py` 默认）时上述列表优先使用 `_graph_task_projection_map` 解析 `WorkflowGraphInstance` / `WorkflowNodeInstance` / `WorkflowDeliverable`，未命中图投影时回落既有 legacy 规则
- 工作流重构单节点交付闭环首轮：基于上述 Phase 3 双写链路，`TaskService` / `tasks` API 已新增“提交交付物”“通过验收”“打回返工”动作，交付快照写入 `workflow_deliverables`，兼容 `Task` 投影通过 `extra_metadata` 暴露最近交付说明、最近提交时间、返工原因、返工次数与最近质量评分；`TaskCenterService` / `task-center` API / `TaskCenterView` 已同步投影待验收、最近提交时间、返工次数、质量评分等跟踪信号；同时禁止 graph 手动任务通过通用状态流转接口直接跳过交付 / 验收动作
- 工作流重构 Phase 4：graph 手动任务默认以 `ASSIGNED` 节点业务态创建；`TaskService` / `tasks` API / `TasksView` 已新增“接受任务”“退回协商”“转办”动作，`todo -> doing` 现在要求执行人先确认接单；兼容读取侧继续使用 `Task.extra_metadata` + `TaskCenterService` 投影当前握手阶段、当前处理人与最近协商 / 转办原因
- 工作流重构 Phase 6-7：`WorkflowGraphService` 已支持基于 `WorkflowGraphTemplate` 创建多节点图实例、按入度激活起始节点、在节点完成后推进顺序流 / fan-out / wait-all join，并通过实例级行锁、节点版本号和稳定 `current_node_key` 解析保证幂等收口；同时已支持节点完成时 `context_updates` 写回实例 `context`、条件边求值（含 `else` 默认路由）与 `Notice Node` 触达即完成；`workflow_graph_engine` API 已提供模板实例列表、实例详情、节点完成快照与智能抄送候选计算
- 工作流重构 Phase 8-9：Wait-Any（`join_mode=any`）并发撤权与幂等保护、深度打回（`deep_reject_to_upstream`）可达性校验与 append-only 版本链（`iteration+1` 克隆）、超出 `max_iterations` 阻止；`TasksView` 展示 V{n} 版本角标与打回原因
- 工作流重构 Phase 10 前端化：`frontend/src/api/workflow-graph.ts` 新增 `getWorkflowGraphInstance`；`frontend/src/types/api.ts` 补充 `WorkflowGraphInstanceDetail` / `WorkflowNodeInstanceSummary` 等图引擎 TS 类型；`TasksView` 打开图任务详情时 fetch 图实例并渲染节点板块列表（标题 / engine_state 标签 / V{n} 角标 / 耗时）；`TaskCenterView` 任务跟踪表格新增逾期标签（due_date < now && status != done）与催办按钮（写入系统催办评论）；**图模板设计器**（@ 2026-06-21）：`GraphTemplateDesignerView.vue` 全页 authoring（config/节点/边/routing_rules/校验/发布/导入导出/dry-run），`GraphTemplateDagPreview.vue` 拓扑预览，`GraphTemplatesPanel` 列表 Run 统计
- 工作流重构 Phase 11-A / routing_rules 旧系统桥接：新建 `backend/app/services/condition_evaluator.py` 作为两套工作流系统（图引擎 + 旧模板系统）共享的条件求值模块，提供 `is_else_condition` / `evaluate_condition` / `evaluate_routing_rules` 函数，支持 `eq/neq/gt/gte/lt/lte/in/not_in/contains/exists` 与嵌套 `all/any`；`WorkflowGraphService` 的内联条件求值方法全部迁移至该模块；`TaskService._activate_ready_template_steps` 新增 `_routing_rules_allow_step_activation` 静态方法，当上游 `TaskTemplateStep.config.routing_rules` 存在时以 `instance.payload` 作为上下文评估条件，仅激活命中目标的下游步骤；无规则时保持完全向后兼容
- 工作流重构 Phase 11-B/11-C/11-D（已完成）：`WorkflowGraphService` 新增 `takeover_node_instance()`（管理员接管节点、写 takeover 审计信息），并引入 `_write_outbox_event()` 在事务内写入 `workflow_outbox_events`；新增 `backend/app/workers/workflow_outbox_worker.py` 消费 outbox 事件，`backend/app/workers/arq_worker.py` 已注册 30 秒定时任务 `process_workflow_outbox_events_job`，对 `PENDING/RETRYING` 事件执行异步投递与指数退避重试，超上限置 `FAILED`；11-D 已补 graph 写接口事务提交、管理员接管后的手动 `Task` 投影同步（执行人 / 握手标签 / 任务中心入口）、`TaskService` 对失效 graph 节点的 accept / reject / delegate 守卫、`complete_node_instance()` 对 `COMPLETED` 重放的幂等返回与对 `TERMINATED` 迟到提交的 409 拦截，以及 Wait-All / Wait-Any 重放、stale deep-reject、complete API 重放稳定快照的回归覆盖；生产环境 `FRONTEND_APP_URL` 也已改为必填，避免邀请注册链接回落到 localhost
- 工作流重构 Phase 11-E/11-F（已完成）：`backend/app/services/legacy_task_graph_migration_service.py`、`backend/app/scripts/migrate_legacy_tasks_to_graph.py` 与 `backend/app/scripts/rollback_legacy_task_migration.py` 已支持 legacy task 批次迁移 / rollback；`TaskService.list_task_inbox()`、`list_task_tracking()`、`list_task_history()` 现已在 `TASK_CENTER_V2_ENABLED` 下默认走 graph-first with legacy fallback，优先解析 `WorkflowGraphInstance` / `WorkflowNodeInstance` / `WorkflowDeliverable`，修正 migrated review task 的责任链展示；`WORKFLOW_GRAPH_ENGINE_ENABLED` 与 `TASK_CENTER_V2_ENABLED` 默认值均已切到 `true`，旧创建 / 旧读侧仅保留为显式关闭开关时的紧急回退
- 工作流重构 Phase 11-G（已完成）：前端已新增 Playwright 基线与真实后端联动基线。`frontend/playwright.config.ts` 现覆盖 mock API 驱动的登录 / 会话恢复 / 任务中心标签切换 / graph-first 详情场景；`frontend/playwright.live.config.ts` 则通过 `frontend/e2e/live/docker-compose.playwright-live.yml` + 隔离 Compose 端口启动 PostgreSQL / Redis / backend / worker / frontend / nginx，并在 backend 容器内执行 `python -m app.scripts.seed_sample_data`，验证真实登录与任务中心建立任务链路。为支撑稳定浏览器断言，`LoginView.vue`、`TaskCenterView.vue`、`TasksView.vue` 已补最小 `data-testid` 锚点；`frontend/README.md` 已同步新增 mock/live 两套 E2E 命令说明
- 汇报中心：向上汇报、向下传达（**统一「发起汇报」弹窗入口**）、逐级流转、历史归档与可选审批挂接
- 任务中心列表 / 看板 / 甘特图多视图与活动时间线 / 负载概览
- 任务完成率 / 逾期率 / 负载统计
- 文档知识库、RAG 检索、LLM Router 与 Tool Calling
- 浏览器 Push 订阅、Web Push adapter 与 PWA manifest / service worker 基线
- 浏览器后台界面：已切换到“通用模块 / 特殊模块”壳层导航；总览页已落地看板、公告、待办事项、任务跟踪与任务中心快捷入口
- 特殊模块中的 `/people` 已升级为统一人员工作台：左侧人员列表，右侧账号 / 档案 / 岗位汇报 / 生命周期 / 权限视图多标签详情
- 测试数据脚本：可重复生成 demo 组织、档案与账号
- request id、统一 500 错误收口与 `error_events` 诊断链路

### 2.3 当前明确缺口

- 公开注册 / 审批式注册仍未落地；邀请制注册已落地
- 工作流 E 首批已经落地，且 Stage 2 Phase 2 已完成模板设计器拓扑校验、模板版本语义、调度最近执行结果、实例进度展示与 fan-out / join 重复激活约束收口；后续重点转向生命周期事件联动、实例历史深挖与全量回归 / 部署收口
- 工作流重构已完成 Phase 3-11-G：含手动创建 dual-write、交付 / 验收 / 返工、握手 / 转办、多节点推进、Context 写回、条件边与 Notice、智能抄送候选、Wait-Any 撤权、深度打回、routing_rules 桥接、outbox、迁移 CLI、**任务中心列表 graph-first 读路径**（`TASK_CENTER_V2_ENABLED`）、Playwright 基线等。仍待产品化深化的方向：工作流 E 与图模板 / 调度的进一步统一、全量回归与部署演练；`TaskTemplateService` 仍未改为从 `WorkflowGraphTemplate` 一步实例化（两套入口并存属已知架构边界，而非“读侧未切换”）
- 生命周期事件与任务模板 / 审批流的规则化默认联动、前端结构化配置入口仍未落地；当前已支持在事件写入时显式绑定目标并异步触发
- 生产 compose、主机部署脚本与 Nginx 生产配置已落地；**Stage 2 Phase 6** 已记录在线 Ubuntu 主机演练与 2026-05-21 测试基线；**最小回滚路径**仍待演练
- HR 字段权限的可视化规则管理页仍偏基础
- 消息外部渠道深化、失败重试与更完整投递观测
- Email / WebSocket 渠道的外部真实接入仍是最小实现后的下一步
- 更大范围的集成测试、端到端验证扩面；docker-gui / Playwright 与发布 commit 的定期基线刷新
- **视频工作流 v1（W0–W10 已落地，v1 硬化完成）**：排期见 `memory-bank/plans/workflow-video-v1-implementation-plan.md` v2.0。产品口径为 **一次选题会（批次 Run）→ 选题清单 `approved_topics[]` → 按题 fork 子 Run（`video_production_per_topic_v1`）**；**无**独立「发起选题会」入口（选题会为图模板之一）。模板引擎增量：**`launch_schema` / `capture_schema` / `aggregate_schema`**（Pydantic：`backend/app/schemas/workflow_video.py`）。**W1 已落库**：`workflow_node_instances.instance_key`；`workflow_graph_instances.run_label` / `parent_instance_id`（迁移 `20260522_01`）。**W2 已落地**：`ParticipantResolutionService`（`participant_policies` + all/subset）、`POST /api/v1/workflow-graph/templates/{id}/preview-participants`；`workflow_rule_resolver` 扩展 `context_var` / `department_pool`。运行时仍以 `workflow_graph_*` + `Task` 为主；`task_templates` 实例化保持 **legacy**（图模板为 v1 主路径，ADR 可选 W10+ 转调）。开关：`workflow_graph_template_engine_enabled` 默认 `false`（ADR：`workflow-video-v1-w0-adr.md`）；`backend/app/core/workflow_video_policy.py`。**W8**：运行事件落库表 `workflow_run_events`（迁移 `20260523_01`）、`WorkflowRunEventService`、`GET /api/v1/workflow-graph/instances/{id}/events`；采集/汇总/fork/打回/实例化/节点完成等写入事件（不再使用 `context.run_events`）。**W9**：`workflow_node_activated` 写入 `workflow_outbox_events`（实例化/下游激活）；`GET/PATCH /workflow-graph/templates/{id}` 维护模板 config；`GET /workflow-graph/feature-flags`；任务模板页 E·Legacy 与图模板 Tab 并存。**W10**：Playwright mock 纵向 E2E（`frontend/e2e/workflow-video-v1.spec.ts` + `workflow-video-mock.ts`）；后端 `test_workflow_video_w10_regression.py` 聚合 WFK/W5/W8 关键路径；Runbook §6–§7。

## 3. 模块边界与状态映射

| 模块 | 责任 | 当前状态 | 下一阶段重点 |
| --- | --- | --- | --- |
| IAM | 账号、JWT、基础 RBAC、会话安全 | 已实现 Phase 3 增强版；Stage 2 Phase 5 已补邀请制注册、注册链接校验与激活 | 公开注册 / 审批式注册决策与更细粒度账号开通流程 |
| Organization | 部门树、部门负责人、组织范围 | 已实现 Phase 3 增强版 | 被 Workflow / Messaging 消费 |
| HR Profiles | 主档案、动态字段、基础资料 | 已实现 Phase 3 增强版 | 与模板 / 审批联动 |
| HR Governance | 奖惩、晋升、离职、授权与关系模型 | 已实现 | 事件与模板 / 审批联动 |
| Workflow Core | 任务、依赖、状态机、统计 | 已实现 Phase 4 增强版；任务开始前可阻止未满足依赖的流转 | 与模板实例运行态、Knowledge / AI / 生命周期自动化联动 |
| Workflow Engine | 模板、审批、自动触发、周期调度，以及图引擎核心 schema | 已实现增强版；模板实例运行态、逐步激活、多人扇出 / 汇聚、实例快照与结构化设计器首版已落地；工作流重构 Phase 2 已补图引擎核心表与双层节点状态枚举，Phase 3-5 已补手动创建任务的 graph dual-write、交付验收与握手语义，Phase 6 已补多节点实例化、顺序流 / fan-out / wait-all 推进、实例查询与节点完成接口，Phase 7 已补 Context 写回、条件边路由（含 else）与 Notice Node 自动完成，Phase 8 已补 Wait-Any 抢单推进、同批并发节点自动撤权与撤权后二次提交拦截；Phase 9 已补深度打回（`deep_reject_to_upstream`）、Append-Only 版本链克隆、max_iterations 上限阻断、旧节点只读保留、前端迭代版本标签与打回原因展示；Phase 11-F 起任务中心列表默认 graph-first | 模板 E 与图引擎统一化评估、模板 / 调度管理深化、全量回归 |
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

```text
[ Browser ]
    |-- Vue 3 SPA
    |-- Kanban / Gantt / Inbox / Knowledge / AI Command UI
    |-- Browser Push / PWA
    |
    v
[ Nginx ]
    |
    v
[ FastAPI ]
    |-- 更细粒度服务边界
    |-- 更完整的通知适配与注册能力
    |
    +--> PostgreSQL / pgvector
    +--> Redis / ARQ Queue
    +--> Object Storage

[ Test / QA ]
    |-- 集成测试
    |-- E2E smoke
    |-- 场景化 demo 数据
```

### 4.3 当前本地开发路径

1. **Compose 路径（推荐）**
   - `postgres`
   - `redis`
   - `backend`
   - `worker`
   - `frontend`
   - `nginx`
   - `backend` 与 `worker` 启动时都会执行 `alembic upgrade head`

2. **本地直启路径**
   - `backend/.env.example` 默认指向 `localhost`
   - `backend/scripts/start-worker.sh` 可直接启动 ARQ worker
   - `frontend` 默认请求同主机 `:8000/api/v1`
   - 可通过 `VITE_DEV_API_PROXY_TARGET` 使用代理

## 5. 代码组织与关键文件职责

### 5.1 memory-bank

| 路径 | 作用 |
| --- | --- |
| `memory-bank/README.md` | 文档索引（🔥/🌡️/🧊 温度体系） |
| `memory-bank/project-brief.md` | 产品愿景、受众、功能边界、技术栈摘要 |
| `memory-bank/architecture.md` | 工程基线、运行时、模块职责、核心流程（本文件） |
| `memory-bank/data-contracts.md` | schema、枚举、实体关系、API 索引 |
| `memory-bank/conventions.md` | 编码与协作规范 |
| `memory-bank/active-task.md` | 当前唯一聚焦任务 |
| `memory-bank/progress.md` | 阶段验收与会话摘要 |
| `memory-bank/design-document.md` | 【已迁移】完整产品设计叙述；权威摘要见 `project-brief.md` |
| `memory-bank/tech-stack.md` | 【已迁移】技术选型详情；权威摘要见 `project-brief.md` |
| `memory-bank/plans/improvements-stage2-implementation-plan.md` | Stage 2 阶段计划与验收出口 |
| `memory-bank/plans/workflow-refactor-implementation-plan.md` | 工作流图引擎重构 Phase 0–11 实施基线 |
| `memory-bank/plans/workflow-video-v1-implementation-plan.md` | 视频工作流 v1（批次选题会 + 表单引擎 + 按题 fork）实施清单 v2 |
| `memory-bank/plans/workflow-video-v1-w0-adr.md` | 视频 v1 W0：图模板引擎开关与 legacy E 路径 ADR |
| `memory-bank/handbooks/deployment-runbook-ubuntu-2404.md` | Ubuntu 24.04 LTS 生产部署操作手册 |
| `memory-bank/domains/*.md` | 子系统领域文档（HR、任务中心、图引擎、视频 v1、消息、知识库/AI） |
| `memory-bank/roadmap.md` | 宏观里程碑与当前版本焦点 |
| `memory-bank/history/` | 时点评估报告与历史方案提案（非现行排期唯一来源） |
| `memory-bank/archive/outdated/` | **已废弃**草稿或重复文件；勿作产品/实现依据 |

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
| `frontend/src/components/workflow/GraphTemplateDagPreview.vue` | 设计器拓扑 SVG 预览 |
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
13. **任务中心读路径（Phase 11-F，与代码一致）**：`TaskService.list_task_inbox()`、`list_task_tracking()`、`list_task_history()` 在 `TASK_CENTER_V2_ENABLED=true`（`Settings` 默认值，见 `backend/app/core/config.py`）下对具备图锚点的任务优先解析 `WorkflowGraphInstance` / `WorkflowNodeInstance` / `WorkflowDeliverable`，再与未迁移的 legacy 任务合并排序；`TaskCenterService.get_task_center()` 仍调用上述三方法，前端 `GET /task-center` 协议保持稳定。Phase 11-E 迁移 CLI 与 Phase 11-F 默认切流已在仓库落地；深度打回等写路径见 Phase 9 / 11-D。若环境显式关闭 `TASK_CENTER_V2_ENABLED`，则回退为纯 legacy 列表语义。

14. **任务中心增强（TCE，@ 2026-06-21）**：Phase 1–5 已落地（读模型、batch hydration、部门统计、多部门实例化、TC-P3 清理）；**图模板设计器 D1–D3** 已落地（`WorkflowGraphTemplateAdminService` + `GraphTemplateDesignerView`）。仍开放 backlog：**B-12**（Legacy E 后端）、**F-05**（Shell 拆分）、**F-10–F-12**（抛光）— 见 [`domains/task-center.md`](./domains/task-center.md) §10。

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

数据库设计原则、枚举基线、全量表结构、实体关系与 schema 维护规则已迁至 **[data-contracts.md](./data-contracts.md)**。

本文件仅保留运行时、模块与流程层面的工程基线。修改 schema 时**先更新 data-contracts.md**，再在本文件记录受影响的模块或流程事实（如有）。

## 9. 当前验证基线

详见 [progress.md](./progress.md) 测试基线表与 [data-contracts.md](./data-contracts.md) §维护规则。

## 10. 维护规则

- 宏观架构、运行时、模块职责、核心流程 → 更新本文件
- schema、枚举、实体关系 → 更新 [data-contracts.md](./data-contracts.md)
- 阶段状态与验测 → 更新 [progress.md](./progress.md)
- 产品边界 → 更新 [project-brief.md](./project-brief.md)
- 当前任务 → 更新 [active-task.md](./active-task.md)
