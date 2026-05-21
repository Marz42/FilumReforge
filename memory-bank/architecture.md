# Project Filum 架构基线

**版本**: v3.12.0  
**状态**: Phase A–5 与重构 Step 1–7 已完成；工作流图引擎 Phase 3–11-G 与 **Stage 2 Phase 0–6**（含在线 Ubuntu 主机演练）已落地；**Ubuntu 最小回滚演练**仍为待办；**附件**已统一 MIME/大小策略并支持汇报 `attachment_links(report)`；图引擎写接口已 **`session.commit()`** 持久化，实例详情 API 避免 ORM 关系懒加载；**memory-bank** 已重组为 `handbooks/`、`plans/`、`history/`、`archive/outdated/`（见 `memory-bank/README.md`），且仓库内 `.github/*`、`infra/`、`verification-runs/` 等指向上述文档的链接已与新目录对齐；汇报中心「发起向上/向下」已收敛为页头 **「发起汇报」** 弹窗统一入口（`/reports`）  
**适用范围**: 当前仓库代码、完整数据库 schema、Phase 5 已交付基线，以及当前重构执行路径下的工程边界

## 1. 文档定位

本文件是 Project Filum 的**工程实现权威文档**，负责回答四类问题：

1. 当前代码已经实现了什么
2. 当前系统是如何运行的
3. 当前仓库里关键文件分别负责什么
4. 完整数据库 schema 现在是什么、未来还要扩展什么

文档职责分工如下：

- `memory-bank/README.md`：文档索引（手册、计划、历史与归档路径）
- `design-document.md`：产品目标、业务边界、阶段意图
- `architecture.md`：当前工程基线、运行时结构、schema 与模块职责
- `plans/implementation-plan.md`：从当前代码状态出发的未来开发顺序
- `progress.md`：已经完成并经过验证的事项

### 1.1 Stage 2 文档同步约定

当前仓库已完成历史 Phase A-5，本轮后续增强统一归入 `Stage 2` 周期，并以 `memory-bank/plans/improvements-stage2-implementation-plan.md` 作为阶段基线。

- Stage 2 每个阶段完成后，必须先更新本文件，记录当前实现事实、受影响模块职责、结构约束或 schema 变化。
- 随后再更新 `memory-bank/progress.md`，记录阶段状态、验证命令与验收结论。
- 若阶段只改前端表现或页面职责，没有 schema 变化，也必须在本文件记录行为事实，避免实现和文档漂移。

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
- 工作流重构 Phase 10 前端化：`frontend/src/api/workflow-graph.ts` 新增 `getWorkflowGraphInstance`；`frontend/src/types/api.ts` 补充 `WorkflowGraphInstanceDetail` / `WorkflowNodeInstanceSummary` 等图引擎 TS 类型；`TasksView` 打开图任务详情时 fetch 图实例并渲染节点板块列表（标题 / engine_state 标签 / V{n} 角标 / 耗时）；`TaskTemplatesView` 新增出口路由规则编辑器（IF 条件规则 + ELSE 兜底，保存时强制校验 ELSE 存在），并在 `join_mode=any` 步骤保存前弹确认提示；`TaskCenterView` 任务跟踪表格新增逾期标签（due_date < now && status != done）与催办按钮（写入系统催办评论）
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
| `memory-bank/README.md` | 文档索引：手册、实施计划、历史材料与过时归档路径 |
| `memory-bank/design-document.md` | 产品能力、非目标与阶段意图 |
| `memory-bank/architecture.md` | 当前工程基线、完整 schema、模块职责 |
| `memory-bank/plans/implementation-plan.md` | 未来开发顺序、阶段范围与测试出口 |
| `memory-bank/plans/improvements-stage2-implementation-plan.md` | Stage 2 阶段计划与验收出口 |
| `memory-bank/plans/workflow-refactor-implementation-plan.md` | 工作流图引擎重构 Phase 0–11 实施基线 |
| `memory-bank/progress.md` | 已完成事项与验证记录 |
| `memory-bank/tech-stack.md` | 技术选型与已落地 / 规划状态 |
| `memory-bank/handbooks/manual-database-operations.md` | PostgreSQL 手工连接、增删改查注意、Alembic、整库重置与初始化 |
| `memory-bank/handbooks/e2e-gui-verification-automation-runbook.md` | Docker 已启动时 Playwright 自动化子集、报告目录与命令说明 |
| `memory-bank/handbooks/deployment-runbook-ubuntu-2404.md` | Ubuntu 24.04 LTS 生产部署操作手册 |
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
| `backend/app/services/workflow_rule_resolver.py` | 模板与审批流共用的 assignee rule 解析器 |
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
| `frontend/src/views/TaskCenterView.vue` | Step 3 后升级为任务中心聚合页；工作流重构 Phase 1 后默认落在“待处理”，主标签为待处理 / 跟踪 / 备忘 / 模板，建立任务改为页头全局 Drawer，历史任务并入跟踪视图；Step 6 起消费消息来源 `?selected=` |
| `frontend/src/views/TasksView.vue` | Phase 4 任务工作台，Step 3 后作为任务跟踪详情与多视图底座继续复用；Step 6 起支持外部来源指定初始选中任务 |
| `frontend/src/views/TaskTemplatesView.vue` | 工作流 E 结构化设计器首版，支持步骤增删改、JSON 导入、实例快照、模板删除与已有模板编辑 |
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
6. 任务跟踪标签继续复用 `TasksView.vue` 的列表 / 看板 / 甘特图、活动时间线与负载概览；建立任务入口已收敛到任务中心页头全局 Drawer，`TasksView.vue` 在嵌入 tracking 时不再暴露第二个创建入口。

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

### 6.13A 工作流 E 模板运行态链路（当前）

1. `TaskTemplatesView.vue` 以结构化表单编辑模板步骤，并通过 JSON 预览 / 导入保持高级入口。
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
| `push_subscription_status` | `active`, `expired`, `revoked` | Phase 5 规划 |
| `document_category` | `policy`, `sop`, `announcement`, `faq`, `other` | Phase 5 规划 |
| `document_status` | `draft`, `published`, `archived` | Phase 5 规划 |

## 10. 全量数据库 Schema

### 10.1 `users`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 用户主键 |
| `email` | `varchar(255)` | UNIQUE, NOT NULL | 登录账号 |
| `password_hash` | `varchar(255)` | NOT NULL | 密码哈希 |
| `role` | `user_role` | NOT NULL | 全局角色 |
| `status` | `user_status` | NOT NULL, DEFAULT `active` | 用户状态 |
| `last_login_at` | `timestamptz` | NULL | 最近登录时间 |
| `invited_by` | `uuid` | FK -> `users.id`, NULL | 邀请创建人 |
| `invitation_token_hash` | `varchar(64)` | NULL | 邀请 token 哈希，仅服务端可见 |
| `invitation_sent_at` | `timestamptz` | NULL | 最近一次生成邀请时间 |
| `invitation_expires_at` | `timestamptz` | NULL | 邀请过期时间 |
| `invitation_revoked_at` | `timestamptz` | NULL | 邀请撤销时间 |
| `invitation_accepted_at` | `timestamptz` | NULL | 邀请完成注册时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_users_email`
- `idx_users_role_status (role, status)`
- `idx_users_invitation_token_hash (invitation_token_hash)`

**设计说明**

- 邀请制注册复用 `users` 主表，不单独引入 invitation 表；账号在被邀请后先保持 `inactive`，待受邀人通过链接设置密码后再切换到 `active`。
- 邀请 token 仅存储哈希值；撤销邀请时保留哈希锚点并写入 `invitation_revoked_at`，便于预览接口稳定返回“已撤销”状态与后续审计。
- 人员工作台允许管理员删除未建档账号，但服务端会拒绝删除已建档或已被其它业务数据引用的用户，避免把标准员工生命周期误做成物理删除。

### 10.2 `refresh_tokens`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 记录主键 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 所属用户 |
| `token_id` | `varchar(64)` | UNIQUE, NOT NULL | JWT `jti` |
| `expires_at` | `timestamptz` | NOT NULL | 过期时间 |
| `revoked_at` | `timestamptz` | NULL | 撤销时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_refresh_tokens_user_id (user_id)`

### 10.3 `departments`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 部门主键 |
| `name` | `varchar(120)` | NOT NULL | 部门名称 |
| `code` | `varchar(64)` | UNIQUE, NOT NULL | 稳定标识 |
| `parent_id` | `uuid` | FK -> `departments.id`, NULL | 上级部门 |
| `manager_id` | `uuid` | FK -> `users.id`, NULL | 部门负责人 |
| `capabilities` | `jsonb` | NOT NULL, DEFAULT `[]` | 部门能力集合，如公告发布、组织任务发布、模板管理 |
| `sort_order` | `int4` | NOT NULL, DEFAULT `0` | 排序 |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` | 是否启用 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `uq_departments_code`
- `uq_departments_parent_name (parent_id, name)`
- `idx_departments_parent_id (parent_id)`

### 10.4 `profiles`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `user_id` | `uuid` | PK, FK -> `users.id` | 与用户一一对应 |
| `employee_no` | `varchar(64)` | UNIQUE, NOT NULL | 员工编号 |
| `real_name` | `varchar(120)` | NOT NULL | 真实姓名 |
| `department_id` | `uuid` | FK -> `departments.id`, NOT NULL | 当前主部门 |
| `job_title` | `varchar(120)` | NULL | 当前展示岗位 |
| `phone` | `varchar(32)` | NULL | 电话 |
| `hire_date` | `date` | NULL | 入职日期 |
| `custom_fields` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 动态档案字段 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_profiles_employee_no`
- `idx_profiles_department_id (department_id)`
- `idx_profiles_custom_fields_gin USING GIN (custom_fields)`

**设计说明**

- `profiles` 仍是“一人一档”的锚点表。
- Phase 3 已通过 `profile_positions`、`reporting_lines`、`employment_events` 与 `delegations` 补齐复杂任职关系和授权关系。

### 10.5 `positions`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 岗位主键 |
| `code` | `varchar(64)` | UNIQUE, NOT NULL | 岗位编码 |
| `name` | `varchar(120)` | NOT NULL | 岗位名称 |
| `level` | `varchar(64)` | NULL | 岗位级别 |
| `metadata` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展配置 |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` | 是否启用 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_positions_code`
- `idx_positions_is_active (is_active)`

### 10.6 `profile_positions`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 任职关系主键 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 用户 |
| `position_id` | `uuid` | FK -> `positions.id`, NOT NULL | 岗位 |
| `department_id` | `uuid` | FK -> `departments.id`, NOT NULL | 挂载部门 |
| `assignment_type` | `position_assignment_type` | NOT NULL, DEFAULT `primary` | 任职类型 |
| `is_primary` | `bool` | NOT NULL, DEFAULT `false` | 是否主任职 |
| `starts_at` | `date` | NOT NULL | 生效日期 |
| `ends_at` | `date` | NULL | 结束日期 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_profile_positions_user_id (user_id)`
- `idx_profile_positions_department_id (department_id)`
- `idx_profile_positions_is_primary (user_id, is_primary)`

**约束与说明**

- `uq_profile_positions_assignment (user_id, position_id, department_id, starts_at)`
- CHECK `ends_at IS NULL OR ends_at >= starts_at`
- 一个用户可以拥有多个岗位关系。
- “兼职 / 代理岗 / 多部门挂载”统一通过本表表达。

### 10.7 `reporting_lines`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 汇报线主键 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 员工 |
| `manager_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 上级 |
| `department_id` | `uuid` | FK -> `departments.id`, NULL | 关联部门 |
| `line_type` | `reporting_line_type` | NOT NULL | `solid` / `dotted` |
| `is_primary` | `bool` | NOT NULL, DEFAULT `false` | 是否主要汇报线 |
| `starts_at` | `date` | NOT NULL | 生效日期 |
| `ends_at` | `date` | NULL | 结束日期 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `uq_reporting_lines_relation (user_id, manager_user_id, line_type, department_id, starts_at)`
- CHECK `user_id <> manager_user_id`
- CHECK `ends_at IS NULL OR ends_at >= starts_at`
- `idx_reporting_lines_user_id (user_id)`
- `idx_reporting_lines_manager_user_id (manager_user_id)`

### 10.8 `profile_field_definitions`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 字段定义主键 |
| `field_key` | `varchar(64)` | UNIQUE, NOT NULL | 字段标识 |
| `label` | `varchar(120)` | NOT NULL | 字段名称 |
| `field_type` | `varchar(32)` | NOT NULL | 字段类型 |
| `storage_target` | `varchar(32)` | NOT NULL | `core` / `custom` |
| `is_sensitive` | `bool` | NOT NULL, DEFAULT `false` | 是否高敏 |
| `config` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 展示 / 校验配置 |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` | 是否启用 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_profile_field_definitions_field_key`
- `idx_profile_field_definitions_is_active (is_active)`

### 10.9 `profile_field_permissions`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 权限规则主键 |
| `field_definition_id` | `uuid` | FK -> `profile_field_definitions.id`, NOT NULL | 字段定义 |
| `subject_type` | `varchar(32)` | NOT NULL | 规则主体类型 |
| `subject_value` | `varchar(64)` | NULL | 规则主体值 |
| `can_view` | `bool` | NOT NULL, DEFAULT `false` | 是否可查看 |
| `can_edit` | `bool` | NOT NULL, DEFAULT `false` | 是否可编辑 |
| `scope_filters` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 作用范围 |
| `priority` | `int4` | NOT NULL, DEFAULT `100` | 优先级 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_profile_field_permissions_definition (field_definition_id)`
- `idx_profile_field_permissions_priority (priority)`

**设计说明**

- 规则主体可表达 self / role / reporting_line / department_scope / delegation 等关系。
- 服务层负责将 actor 的角色、汇报线和授权关系解析为最终字段权限。

### 10.10 `employment_events`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 事件主键 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 所属员工 |
| `event_type` | `employment_event_type` | NOT NULL | 事件类型 |
| `effective_date` | `date` | NOT NULL | 生效日期 |
| `title` | `varchar(255)` | NOT NULL | 事件标题 |
| `summary` | `text` | NULL | 简述 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展详情 |
| `task_template_id` | `uuid` | FK -> `task_templates.id`, NULL | 显式联动的任务模板 |
| `workflow_definition_id` | `uuid` | FK -> `workflow_definitions.id`, NULL | 显式联动的审批流定义 |
| `trigger_status` | `varchar(32)` | NOT NULL, DEFAULT `skipped` | 生命周期联动状态 |
| `triggered_at` | `timestamptz` | NULL | 最近一次联动完成时间 |
| `trigger_error` | `text` | NULL | 最近一次联动失败原因 |
| `trigger_attempt_count` | `int4` | NOT NULL, DEFAULT `0` | 联动尝试次数 |
| `triggered_template_instance_id` | `uuid` | FK -> `task_template_instances.id`, NULL | 已生成的模板实例锚点 |
| `triggered_workflow_instance_id` | `uuid` | FK -> `workflow_instances.id`, NULL | 已生成的审批实例锚点 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_employment_events_user_id_date (user_id, effective_date)`
- `idx_employment_events_type (event_type)`

**设计说明**

- 当前首版联动采取“事件写入时显式绑定目标 + worker 异步触发”的保守策略，不阻塞生命周期主事务。
- `triggered_template_instance_id` 与 `triggered_workflow_instance_id` 作为幂等锚点，避免 worker 重试时重复生成实例。
- 规则化的默认映射策略与前端结构化配置仍属于下一轮深化范围。

### 10.11 `delegations`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 授权主键 |
| `delegator_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 委托人 |
| `delegate_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 被委托人 |
| `scope_type` | `delegation_scope_type` | NOT NULL | 授权范围类型 |
| `scope_department_id` | `uuid` | FK -> `departments.id`, NULL | 范围部门 |
| `scope_filters` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 额外范围过滤 |
| `status` | `delegation_status` | NOT NULL, DEFAULT `pending` | 授权状态 |
| `starts_at` | `timestamptz` | NOT NULL | 开始时间 |
| `ends_at` | `timestamptz` | NOT NULL | 结束时间 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- CHECK `delegator_user_id <> delegate_user_id`
- CHECK `ends_at > starts_at`
- `idx_delegations_delegator_status (delegator_user_id, status)`
- `idx_delegations_delegate_status (delegate_user_id, status)`

### 10.12 `attachments`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 附件主键 |
| `storage_provider` | `varchar(32)` | NOT NULL | 存储提供者 |
| `bucket` | `varchar(128)` | NOT NULL | 逻辑 bucket |
| `object_key` | `varchar(512)` | NOT NULL | 对象存储 key |
| `original_filename` | `varchar(255)` | NOT NULL | 原始文件名 |
| `mime_type` | `varchar(127)` | NOT NULL | MIME 类型 |
| `size_bytes` | `bigint` | NOT NULL | 文件大小 |
| `checksum_sha256` | `char(64)` | NOT NULL | 完整性校验 |
| `uploader_id` | `uuid` | FK -> `users.id`, NOT NULL | 上传者 |
| `visibility` | `attachment_visibility` | NOT NULL, DEFAULT `private` | 可见性 |
| `status` | `attachment_status` | NOT NULL, DEFAULT `uploaded` | 状态 |
| `metadata` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展元数据 |
| `created_at` | `timestamptz` | NOT NULL | 上传时间 |
| `deleted_at` | `timestamptz` | NULL | 软删除时间 |

**约束与索引**

- `uq_attachments_storage_object (storage_provider, bucket, object_key)`
- `idx_attachments_uploader_id (uploader_id)`
- `idx_attachments_status_visibility (status, visibility)`

### 10.13 `attachment_links`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 绑定记录主键 |
| `attachment_id` | `uuid` | FK -> `attachments.id`, NOT NULL | 附件 |
| `target_type` | `attachment_target_type` | NOT NULL | 目标对象类型 |
| `target_id` | `uuid` | NOT NULL | 目标对象主键 |
| `relation` | `varchar(64)` | NOT NULL, DEFAULT `primary` | 绑定关系 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- `uq_attachment_links_binding (attachment_id, target_type, target_id, relation)`
- `idx_attachment_links_target (target_type, target_id)`

**设计说明**

- 当前主要绑定 `task`、`task_comment`、`profile`、`notification_message`。
- 生命周期事件等对象仍属于后续扩展方向。

### 10.14 `tasks`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 任务主键 |
| `title` | `varchar(255)` | NOT NULL | 任务标题 |
| `description` | `text` | NULL | 描述 |
| `creator_id` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `assignee_id` | `uuid` | FK -> `users.id`, NOT NULL | 执行人 |
| `department_id` | `uuid` | FK -> `departments.id`, NULL | 所属部门 |
| `status` | `task_status` | NOT NULL, DEFAULT `todo` | 状态 |
| `priority` | `task_priority` | NOT NULL, DEFAULT `medium` | 优先级 |
| `due_date` | `timestamptz` | NULL | 截止时间 |
| `started_at` | `timestamptz` | NULL | 开始时间 |
| `completed_at` | `timestamptz` | NULL | 完成时间 |
| `parent_task_id` | `uuid` | FK -> `tasks.id`, NULL | 父任务 |
| `template_instance_id` | `uuid` | FK -> `task_template_instances.id`, NULL | 所属模板实例 |
| `template_step_run_id` | `uuid` | FK -> `task_template_step_runs.id`, NULL | 所属模板步骤运行态 |
| `source_type` | `task_source_type` | NOT NULL, DEFAULT `manual` | 来源 |
| `metadata` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展元数据 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `idx_tasks_assignee_status (assignee_id, status)`
- `idx_tasks_department_status (department_id, status)`
- `idx_tasks_due_date (due_date)`

### 10.15 `task_dependencies`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `task_id` | `uuid` | FK -> `tasks.id`, NOT NULL | 当前任务 |
| `depends_on_task_id` | `uuid` | FK -> `tasks.id`, NOT NULL | 前置任务 |
| `dependency_type` | `varchar(32)` | NOT NULL, DEFAULT `blocks` | 依赖类型 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- 主键：`(task_id, depends_on_task_id)`
- CHECK `task_id <> depends_on_task_id`
- `idx_task_dependencies_depends_on_task_id (depends_on_task_id)`

**设计说明**

- 当前已支持依赖建模。
- 后续通过模板和 workflow 引擎补齐自动触发能力。

### 10.16 `task_templates`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 模板主键 |
| `code` | `varchar(64)` | UNIQUE, NOT NULL | 模板编码 |
| `name` | `varchar(120)` | NOT NULL | 模板名称 |
| `category` | `varchar(64)` | NOT NULL | 模板分类 |
| `description` | `text` | NULL | 模板描述 |
| `trigger_type` | `varchar(32)` | NOT NULL, DEFAULT `manual` | 触发类型 |
| `config` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 模板配置 |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` | 是否启用 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_task_templates_code`
- `idx_task_templates_category_active (category, is_active)`

### 10.17 `task_template_steps`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 模板步骤主键 |
| `template_id` | `uuid` | FK -> `task_templates.id`, NOT NULL | 所属模板 |
| `step_key` | `varchar(64)` | NOT NULL | 稳定步骤标识 |
| `title` | `varchar(255)` | NOT NULL | 步骤标题 |
| `description` | `text` | NULL | 步骤描述 |
| `step_type` | `varchar(32)` | NOT NULL, DEFAULT `task` | 步骤类型 |
| `assignment_mode` | `varchar(32)` | NOT NULL, DEFAULT `single` | 分配模式：单任务或多人扇出 |
| `join_mode` | `varchar(32)` | NOT NULL, DEFAULT `all` | 汇聚规则：全部完成或任一完成 |
| `default_assignee_rule` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 默认指派规则 |
| `default_due_offset_hours` | `int4` | NULL | 相对超时时间 |
| `sort_order` | `int4` | NOT NULL, DEFAULT `0` | 排序 |
| `config` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展配置 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `uq_task_template_steps_template_key (template_id, step_key)`
- `idx_task_template_steps_template_order (template_id, sort_order)`
- CHECK `assignment_mode in ('single', 'fan_out')`
- CHECK `join_mode in ('all', 'any')`

### 10.18 `task_template_step_dependencies`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `step_id` | `uuid` | FK -> `task_template_steps.id`, NOT NULL | 当前步骤 |
| `depends_on_step_id` | `uuid` | FK -> `task_template_steps.id`, NOT NULL | 前置步骤 |
| `dependency_type` | `varchar(32)` | NOT NULL, DEFAULT `blocks` | 依赖类型 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- 主键：`(step_id, depends_on_step_id)`
- CHECK `step_id <> depends_on_step_id`
- `idx_task_tpl_step_deps_depends_on (depends_on_step_id)`

### 10.18A `task_template_instances`

**实现状态**: 已实现（工作流 E）

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 模板实例主键 |
| `template_id` | `uuid` | FK -> `task_templates.id`, NOT NULL | 所属模板 |
| `initiator_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 发起人 |
| `department_id` | `uuid` | FK -> `departments.id`, NULL | 目标部门 |
| `status` | `varchar(32)` | NOT NULL, DEFAULT `in_progress` | 实例状态 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 实例化上下文 |
| `completed_at` | `timestamptz` | NULL | 实例完成时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- CHECK `status in ('in_progress', 'completed', 'cancelled')`
- `idx_task_tpl_instances_template_status (template_id, status)`
- `idx_task_tpl_instances_initiator_created (initiator_user_id, created_at)`

### 10.18B `task_template_step_runs`

**实现状态**: 已实现（工作流 E）

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 步骤运行态主键 |
| `instance_id` | `uuid` | FK -> `task_template_instances.id`, NOT NULL | 所属模板实例 |
| `template_step_id` | `uuid` | FK -> `task_template_steps.id`, NOT NULL | 所属模板步骤 |
| `assignee_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 当前执行人 |
| `status` | `varchar(32)` | NOT NULL, DEFAULT `active` | step run 状态 |
| `completed_at` | `timestamptz` | NULL | 完成时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `uq_task_tpl_step_runs_instance_step_assignee (instance_id, template_step_id, assignee_user_id)`
- CHECK `status in ('active', 'completed', 'skipped', 'cancelled')`
- `idx_task_tpl_step_runs_instance_status (instance_id, status)`
- `idx_task_tpl_step_runs_assignee_status (assignee_user_id, status)`

### 10.19 `workflow_definitions`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 流程定义主键 |
| `code` | `varchar(64)` | UNIQUE, NOT NULL | 流程编码 |
| `name` | `varchar(120)` | NOT NULL | 流程名称 |
| `scope_type` | `varchar(64)` | NOT NULL | 业务范围 |
| `status` | `workflow_definition_status` | NOT NULL, DEFAULT `draft` | 定义状态 |
| `version` | `int4` | NOT NULL, DEFAULT `1` | 版本号 |
| `config` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 流程配置 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_workflow_definitions_code`
- `idx_workflow_definitions_scope_status (scope_type, status)`

### 10.20 `workflow_steps`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 流程步骤主键 |
| `definition_id` | `uuid` | FK -> `workflow_definitions.id`, NOT NULL | 所属流程 |
| `step_key` | `varchar(64)` | NOT NULL | 稳定步骤标识 |
| `name` | `varchar(120)` | NOT NULL | 步骤名称 |
| `step_type` | `workflow_step_type` | NOT NULL | 步骤类型 |
| `approval_mode` | `approval_mode` | NULL | 审批模式 |
| `assignee_rule` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 指派规则 |
| `reject_target_step_key` | `varchar(64)` | NULL | 驳回目标步骤 |
| `sort_order` | `int4` | NOT NULL, DEFAULT `0` | 排序 |
| `config` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展配置 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `uq_workflow_steps_definition_key (definition_id, step_key)`
- `idx_workflow_steps_definition_order (definition_id, sort_order)`

### 10.21 `workflow_instances`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 流程实例主键 |
| `definition_id` | `uuid` | FK -> `workflow_definitions.id`, NOT NULL | 使用的流程定义 |
| `source_type` | `varchar(64)` | NOT NULL | 来源类型 |
| `source_id` | `uuid` | NULL | 来源对象 ID |
| `initiator_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 发起人 |
| `status` | `workflow_instance_status` | NOT NULL, DEFAULT `pending` | 实例状态 |
| `current_step_key` | `varchar(64)` | NULL | 当前步骤 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 业务上下文 |
| `started_at` | `timestamptz` | NOT NULL | 开始时间 |
| `completed_at` | `timestamptz` | NULL | 完成时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_workflow_instances_source (source_type, source_id)`
- `idx_workflow_instances_status (status)`

### 10.22 `workflow_step_runs`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 步骤执行主键 |
| `instance_id` | `uuid` | FK -> `workflow_instances.id`, NOT NULL | 所属实例 |
| `step_id` | `uuid` | FK -> `workflow_steps.id`, NOT NULL | 所属步骤 |
| `assignee_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 执行人 |
| `delegated_from_user_id` | `uuid` | FK -> `users.id`, NULL | 被代理来源人 |
| `status` | `workflow_step_run_status` | NOT NULL, DEFAULT `pending` | 执行状态 |
| `acted_at` | `timestamptz` | NULL | 操作时间 |
| `comment` | `text` | NULL | 审批意见 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展上下文 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_workflow_step_runs_instance_status (instance_id, status)`
- `idx_workflow_step_runs_assignee_status (assignee_user_id, status)`

### 10.23 `task_watchers`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 关注人主键 |
| `task_id` | `uuid` | FK -> `tasks.id`, NOT NULL | 任务 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 用户 |
| `relation` | `varchar(32)` | NOT NULL, DEFAULT `cc` | 关系类型 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 添加人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- `uq_task_watchers_binding (task_id, user_id, relation)`
- `idx_task_watchers_user_id (user_id)`

### 10.24 `task_schedules`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 调度主键 |
| `template_id` | `uuid` | FK -> `task_templates.id`, NOT NULL | 对应模板 |
| `owner_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 创建者 |
| `cron_expr` | `varchar(128)` | NOT NULL | 调度表达式 |
| `timezone` | `varchar(64)` | NOT NULL, DEFAULT `UTC` | 时区 |
| `next_run_at` | `timestamptz` | NULL | 下次运行时间 |
| `is_active` | `bool` | NOT NULL, DEFAULT `true` | 是否启用 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展参数 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_task_schedules_active_next_run (is_active, next_run_at)`
- `idx_task_schedules_owner_user_id (owner_user_id)`

### 10.25 `task_memos`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 备忘主键 |
| `owner_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 备忘所属用户 |
| `related_task_id` | `uuid` | FK -> `tasks.id`, NULL | 关联任务 |
| `title` | `varchar(200)` | NULL | 可选标题（迁移 `20260519_01`） |
| `content` | `text` | NOT NULL | 备忘正文 |
| `is_pinned` | `bool` | NOT NULL, DEFAULT `false` | 是否置顶 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_task_memos_owner_user_id (owner_user_id)`
- `idx_task_memos_related_task_id (related_task_id)`
- `idx_task_memos_owner_user_id_is_pinned (owner_user_id, is_pinned)`

### 10.26 `notification_messages`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 消息主键 |
| `source_type` | `varchar(64)` | NOT NULL | 业务来源 |
| `source_id` | `uuid` | NULL | 来源对象 ID |
| `recipient_user_id` | `uuid` | FK -> `users.id`, NULL | 收件用户 |
| `recipient_email` | `varchar(255)` | NULL | 直接收件地址 |
| `message_type` | `varchar(64)` | NOT NULL | 消息类型 |
| `title` | `varchar(255)` | NOT NULL | 标题 |
| `body_text` | `text` | NOT NULL | 文本体 |
| `body_html` | `text` | NULL | HTML 体 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 附加上下文 |
| `status` | `notification_message_status` | NOT NULL, DEFAULT `queued` | 消息状态 |
| `scheduled_at` | `timestamptz` | NULL | 计划发送时间 |
| `enqueued_at` | `timestamptz` | NULL | 入队时间 |
| `completed_at` | `timestamptz` | NULL | 完成时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_notification_messages_status_scheduled_at (status, scheduled_at)`
- `idx_notification_messages_recipient_user_id (recipient_user_id)`

**设计说明**

- 当前用于异步通知总线。
- Phase 4 已在此基础上扩展“消息中心 / 回执”能力，而不是再造一套平行消息表。
- Stage 2 Phase 4 继续沿用该表作为消息中心主存储，并通过 `attachment_links` 绑定消息附件；筛选维度覆盖来源模块、回执状态、渠道、投递状态与创建时间。

### 10.27 `notification_deliveries`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 投递主键 |
| `message_id` | `uuid` | FK -> `notification_messages.id`, NOT NULL | 所属消息 |
| `channel` | `notification_channel` | NOT NULL | 投递渠道 |
| `adapter_name` | `varchar(64)` | NOT NULL | 适配器标识 |
| `status` | `notification_delivery_status` | NOT NULL, DEFAULT `pending` | 投递状态 |
| `attempt_count` | `int4` | NOT NULL, DEFAULT `0` | 尝试次数 |
| `external_message_id` | `varchar(255)` | NULL | 外部平台 ID |
| `error_message` | `text` | NULL | 失败信息 |
| `attempted_at` | `timestamptz` | NULL | 最近尝试时间 |
| `delivered_at` | `timestamptz` | NULL | 成功时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_notification_deliveries_message_id (message_id)`
- `idx_notification_deliveries_status_channel (status, channel)`

### 10.28 `notification_receipts`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 回执主键 |
| `message_id` | `uuid` | FK -> `notification_messages.id`, NOT NULL | 消息 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 用户 |
| `receipt_type` | `notification_receipt_type` | NOT NULL | 回执类型 |
| `note` | `text` | NULL | 回执说明 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- `uq_notification_receipts_binding (message_id, user_id, receipt_type)`
- `idx_notification_receipts_user_id_created_at (user_id, created_at)`

### 10.29 `push_subscriptions`

**实现状态**: Phase 5 规划

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 订阅主键 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 用户 |
| `endpoint` | `text` | UNIQUE, NOT NULL | 浏览器推送端点 |
| `p256dh_key` | `text` | NOT NULL | 公钥 |
| `auth_key` | `text` | NOT NULL | 鉴权密钥 |
| `status` | `push_subscription_status` | NOT NULL, DEFAULT `active` | 订阅状态 |
| `user_agent` | `text` | NULL | 浏览器信息 |
| `last_seen_at` | `timestamptz` | NULL | 最近活跃时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_push_subscriptions_endpoint`
- `idx_push_subscriptions_user_status (user_id, status)`

### 10.30 `task_logs`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 日志主键 |
| `task_id` | `uuid` | FK -> `tasks.id`, NOT NULL | 所属任务 |
| `operator_id` | `uuid` | FK -> `users.id`, NOT NULL | 操作人 |
| `action_type` | `task_action_type` | NOT NULL | 动作类型 |
| `from_status` | `task_status` | NULL | 原状态 |
| `to_status` | `task_status` | NULL | 新状态 |
| `detail` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 详细信息 |
| `created_at` | `timestamptz` | NOT NULL | 记录时间 |

**索引**

- `idx_task_logs_task_id_created_at (task_id, created_at DESC)`
- `idx_task_logs_operator_id (operator_id)`

### 10.31 `task_comments`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 评论主键 |
| `task_id` | `uuid` | FK -> `tasks.id`, NOT NULL | 所属任务 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 评论人 |
| `content` | `text` | NOT NULL | 评论内容 |
| `content_format` | `comment_format` | NOT NULL, DEFAULT `markdown` | 内容格式 |
| `is_internal` | `bool` | NOT NULL, DEFAULT `false` | 是否内部备注 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- CHECK `length(trim(content)) > 0`
- `idx_task_comments_task_id_created_at (task_id, created_at ASC)`
- `idx_task_comments_user_id (user_id)`

### 10.32 `documents`

**实现状态**: Phase 5 规划

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 文档主键 |
| `title` | `varchar(255)` | NOT NULL | 标题 |
| `slug` | `varchar(255)` | UNIQUE, NOT NULL | 稳定 URL 标识 |
| `category` | `document_category` | NOT NULL | 分类 |
| `status` | `document_status` | NOT NULL, DEFAULT `draft` | 状态 |
| `content_md` | `text` | NOT NULL | Markdown 内容 |
| `author_id` | `uuid` | FK -> `users.id`, NOT NULL | 作者 |
| `version` | `int4` | NOT NULL, DEFAULT `1` | 版本号 |
| `published_at` | `timestamptz` | NULL | 发布时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_documents_slug`
- `idx_documents_category_status (category, status)`

### 10.33 `document_embeddings`

**实现状态**: Phase 5 规划

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 向量主键 |
| `document_id` | `uuid` | FK -> `documents.id`, NOT NULL | 所属文档 |
| `chunk_index` | `int4` | NOT NULL | 分块序号 |
| `chunk_text` | `text` | NOT NULL | 切块内容 |
| `token_count` | `int4` | NULL | token 数 |
| `embedding_model` | `varchar(128)` | NOT NULL | 嵌入模型 |
| `embedding` | `vector(1536)` | NOT NULL | 向量数据 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- `uq_document_embeddings_chunk (document_id, chunk_index)`
- 向量索引：`ivfflat` 或 `hnsw`

### 10.34 `board_cards`

**实现状态**: 重构 Step 2 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 看板卡片主键 |
| `scope_department_id` | `uuid` | FK -> `departments.id`, NULL | 可见范围部门，NULL 表示公司级 |
| `author_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 发布人 |
| `title` | `varchar(120)` | NOT NULL | 主题 |
| `content_md` | `text` | NOT NULL | 内容 |
| `expires_at` | `timestamptz` | NOT NULL | 到期时间 |
| `created_at` | `timestamptz` | NOT NULL | 发布时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `idx_board_cards_scope_department_id (scope_department_id)`
- `idx_board_cards_author_user_id (author_user_id)`
- `idx_board_cards_expires_at (expires_at)`

### 10.35 `board_card_archives`

**实现状态**: 重构 Step 2 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 归档主键 |
| `original_card_id` | `uuid` | UNIQUE, NOT NULL | 原活跃卡片 ID |
| `scope_department_id` | `uuid` | FK -> `departments.id`, NULL | 原范围部门 |
| `author_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 原发布人 |
| `title` | `varchar(120)` | NOT NULL | 主题快照 |
| `content_md` | `text` | NOT NULL | 内容快照 |
| `published_at` | `timestamptz` | NOT NULL | 原发布时间 |
| `expires_at` | `timestamptz` | NOT NULL | 原到期时间 |
| `archived_at` | `timestamptz` | NOT NULL | 归档时间 |

**约束与索引**

- `uq_board_card_archives_original_card_id`
- `idx_board_card_archives_scope_department_id (scope_department_id)`
- `idx_board_card_archives_archived_at (archived_at DESC)`

### 10.36 `announcements`

**实现状态**: 重构 Step 2 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 公告主键 |
| `publisher_department_id` | `uuid` | FK -> `departments.id`, NOT NULL | 发布部门 |
| `author_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 发布人 |
| `title` | `varchar(160)` | NOT NULL | 公告标题 |
| `content_md` | `text` | NOT NULL | 公告内容 |
| `published_at` | `timestamptz` | NOT NULL | 发布时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `idx_announcements_publisher_department_id (publisher_department_id)`
- `idx_announcements_published_at (published_at DESC)`

### 10.37 `announcement_archives`

**实现状态**: 重构 Step 2 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 归档主键 |
| `original_announcement_id` | `uuid` | UNIQUE, NOT NULL | 原活跃公告 ID |
| `publisher_department_id` | `uuid` | FK -> `departments.id`, NOT NULL | 原发布部门 |
| `author_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 原发布人 |
| `title` | `varchar(160)` | NOT NULL | 标题快照 |
| `content_md` | `text` | NOT NULL | 内容快照 |
| `published_at` | `timestamptz` | NOT NULL | 原发布时间 |
| `archived_at` | `timestamptz` | NOT NULL | 撤下归档时间 |

**约束与索引**

- `uq_announcement_archives_original_announcement_id`
- `idx_announcement_archives_publisher_department_id (publisher_department_id)`
- `idx_announcement_archives_archived_at (archived_at DESC)`

### 10.38 `reports`

**实现状态**: Step 4 已实现；2026-04-21 已修复 PostgreSQL enum 持久化不一致问题

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 汇报主键 |
| `direction` | `report_direction` | NOT NULL | `upward` / `downward` |
| `status` | `report_status` | NOT NULL, DEFAULT `in_progress` | 汇报状态 |
| `title` | `varchar(255)` | NOT NULL | 主题 |
| `content_md` | `text` | NOT NULL | 正文 |
| `initiator_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 发起人 |
| `target_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 最终目标人 |
| `current_recipient_user_id` | `uuid` | FK -> `users.id`, NULL | 当前处理人 |
| `current_route_sequence` | `int` | NULL | 当前节点序号 |
| `workflow_definition_id` | `uuid` | FK -> `workflow_definitions.id`, NULL | 挂接的审批流定义 |
| `workflow_instance_id` | `uuid` | FK -> `workflow_instances.id`, NULL | 挂接的审批实例 |
| `completed_at` | `timestamptz` | NULL | 完成时间 |
| `returned_at` | `timestamptz` | NULL | 退回时间 |
| `archived_at` | `timestamptz` | NULL | 归档时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `idx_reports_initiator_status (initiator_user_id, status)`
- `idx_reports_current_recipient (current_recipient_user_id, status)`
- `idx_reports_target_status (target_user_id, status)`

### 10.39 `report_routes`

**实现状态**: Step 4 已实现；状态枚举与数据库约束已统一为按枚举值持久化

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 路由节点主键 |
| `report_id` | `uuid` | FK -> `reports.id`, NOT NULL | 所属汇报 |
| `sequence_no` | `int` | NOT NULL | 节点序号 |
| `sender_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 上一跳发送人 |
| `recipient_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 预期接收人 |
| `assigned_user_id` | `uuid` | FK -> `users.id`, NULL | 实际处理人（含代理） |
| `status` | `report_route_status` | NOT NULL, DEFAULT `queued` | 节点状态 |
| `activated_at` | `timestamptz` | NULL | 激活时间 |
| `acted_at` | `timestamptz` | NULL | 处理时间 |
| `note` | `text` | NULL | 节点备注 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_report_routes_sequence (report_id, sequence_no)`
- `idx_report_routes_assigned_status (assigned_user_id, status)`
- `idx_report_routes_report_status (report_id, status)`

### 10.40 `error_events`

**实现状态**: Step 4 排障补充，已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 错误事件主键 |
| `request_id` | `varchar(64)` | NOT NULL | 请求编号 |
| `scope` | `varchar(128)` | NOT NULL | 业务或模块范围，如 `report_center.create_report` |
| `actor_user_id` | `uuid` | FK -> `users.id`, NULL | 当前用户 |
| `source_type` | `varchar(64)` | NULL | 业务对象类型 |
| `source_id` | `uuid` | NULL | 业务对象主键 |
| `http_method` | `varchar(16)` | NULL | 请求方法 |
| `path` | `varchar(255)` | NULL | 请求路径 |
| `error_type` | `varchar(255)` | NOT NULL | Python 异常类型 |
| `error_message` | `text` | NOT NULL | 错误信息 |
| `error_code` | `varchar(64)` | NULL | 统一错误码 |
| `stage` | `varchar(64)` | NULL | 失败阶段 |
| `context_json` | `json/jsonb` | NOT NULL | 脱敏后的上下文摘要 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_error_events_request_id (request_id)`
- `idx_error_events_scope_created_at (scope, created_at)`
- `idx_error_events_actor_user_id (actor_user_id, created_at)`
- `idx_error_events_source_binding (source_type, source_id)`

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

## 12. 当前验证基线

截至当前文档版本，仓库至少具备如下验证能力：

- backend：
  - `pytest`（覆盖 models / migrations / services / api / workers）
  - `python -m compileall app tests`
- frontend：
  - `npm run test:unit -- --run`
  - `npm run type-check`
  - `npm run build`
  - `npm run lint`
- 用户验测：
  - Phase 1：实际点击“初始化管理员”和“登录”通过
  - Phase 2：用户简单测试反馈“看上去基本没有问题”
- 编排：
  - Compose 文件可做配置级检查
  - `worker` 已纳入编排
  - 完整 Docker 运行级验证仍建议在具备 Docker 的环境执行

## 13. 维护规则

- 每完成一个里程碑，必须同步更新本文件
- 新增表、枚举或关键运行时组件时，必须同步记录其状态与所属阶段
- “当前已实现”与“未来规划”必须明确区分，禁止混写
- 若阶段边界调整，先更新 `implementation-plan.md`，再回写本文件
