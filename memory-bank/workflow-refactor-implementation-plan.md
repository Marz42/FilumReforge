# Project Filum 工作流重构实施方案

## 1. 计划定位

本文件基于以下事实编写：

- 当前仓库已经完成 Phase A-Phase 5、重构 Step 1-7，并进入工作流 E 的后续深化周期。
- 当前任务域真实基线仍然是 `Task + TaskTemplateInstance + TaskTemplateStepRun`，单任务状态机为 `Todo -> Doing -> Review -> Done`。
- `memory-bank/workflow-refactor.md` 描述的是**目标设计**，不是当前实现事实。

因此，本文件的目标不是重复设计稿，而是把目标设计拆成**可逐阶段实施、可回归、可验收**的工程计划，直到完整实现以下意图：

1. 单步任务与多步任务统一收敛到“工作流实例 + 节点实例”模型。
2. 单步任务补齐握手、交付、验收、返工、防抵赖与责任转移语义。
3. 多步工作流补齐全局上下文、条件路由、AND/OR 汇聚、Notice Node、智能抄送、深度打回与版本迭代。
4. 任务中心改造成以 Inbox 为核心、以当前阻塞与责任链为主视图的工作台。
5. 全链路补齐节点级审计、幂等保护、Outbox 消息可靠投递、转办/接管与并发防御。

## 2. 已确认约束

- 架构继续保持模块化单体，不拆微服务。
- 后端继续使用 FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic。
- 前端继续使用 Vue 3 + TypeScript + Vite + Element Plus。
- 通知仍统一走 `NotificationService.send(message_obj)`，异步执行继续由 ARQ 承担。
- 对象存储、附件体系、组织架构、代理授权、权限体系尽量复用现有实现，不重复发明平行系统。
- 每个阶段必须有明确自动化测试出口与用户验收动作；用户未确认，不进入下一阶段编码。

## 3. 关键决策

### 3.1 双层状态模型

本轮重构不再把“引擎调度状态”和“业务语义状态”混成一个枚举。

1. **节点引擎态**：`Pending / Activated / Acknowledged / Completed / Terminated`。
2. **业务投影态**：面向任务工作台展示，例如 `Draft / Assigned / Accepted / Doing / PendingReview / Done / Returned / Cancelled`。

执行原则：

- 引擎态服务于调度、路由、幂等、并发控制。
- 业务投影态服务于任务中心、统计、责任追踪、用户按钮文案。
- 二者通过投影层映射，避免以后再把“Review”这种调度态与“验收动作”混用。

### 3.2 统一抽象

1. 单步任务 = 一个 `Workflow Instance` + 一个 `Task Node Instance`。
2. 多步任务 = 一个 `Workflow Instance` + 多个 `Node Instance`。
3. 原有 `Task` 在过渡期内保留为兼容读模型 / 查询投影；是否最终保留物理表，延后到切流阶段再决定。

### 3.3 渐进切换策略

1. 先落新模型，再补兼容适配，再切前端入口，最后切默认创建与默认查询。
2. 在新链路稳定前，旧的任务模板和任务中心链路不能被一次性删除。
3. 对高风险能力采用显式 feature flag 或租户级开关，至少覆盖：
   - `WORKFLOW_GRAPH_ENGINE_ENABLED`
   - `TASK_CENTER_V2_ENABLED`
   - `WORKFLOW_WAIT_ANY_ENABLED`
   - `WORKFLOW_DEEP_REJECTION_ENABLED`

### 3.4 文档同步规则

每个阶段完成后，必须同步三类文档：

1. `memory-bank/architecture.md`：记录真实 schema、模块职责和行为事实。
2. `memory-bank/progress.md`：记录阶段状态、验证命令和用户验收结论。
3. 本文件：只在阶段边界变化或顺序调整时更新，不做流水账。

## 4. 路线总览

| 阶段 | 名称 | 核心目标 |
| --- | --- | --- |
| Phase 0 | 基线冻结与术语对齐 | 固定双层状态、切换策略、迁移口径、测试边界 |
| Phase 1 | 任务中心信息架构重排 | 先完成前端入口职责调整，降低当前使用成本 |
| Phase 2 | 图引擎核心模型落库 | 落 `Workflow Context / Node / Edge / Deliverable` 等底层 schema |
| Phase 3 | 单步任务接入单节点实例 | 让新建临时任务走单节点实例，但先不切掉旧投影 |
| Phase 4 | 单步任务握手与转办 | 补 `Assigned / Accepted / Rejected / Delegated` 语义 |
| Phase 5 | 单步任务交付、验收、返工 | 补 `PendingReview / Done / Rework` 与交付物快照 |
| Phase 6 | 多步实例 MVP 与 Wait-All | 让模板按新图引擎跑通实例快照、节点激活、会签汇聚 |
| Phase 7 | Context、条件路由与 Notice | 落全局数据总线、条件分支、智能抄送和通知节点 |
| Phase 8 | Wait-Any / 抢单与并发撤权 | 补 OR-Join 与同批次节点自动终止 |
| Phase 9 | 深度打回与版本迭代 | 实现 Append-Only 克隆、指定节点退回、尾链重放 |
| Phase 10 | DAG 设计器与节点级时间线 | 完成表格式 DAG 编排与节点板块详情视图 |
| Phase 11 | 韧性硬化、迁移切流与全量回归 | 补 takeover/outbox/幂等/迁移/全量验收 |

## 5. Phase 0 / 基线冻结与术语对齐

### 5.1 目标

在开始编码前，把最容易反复摇摆的概念和兼容策略先锁死，防止中途重写。

### 5.2 本阶段改动

1. 确认双层状态模型与状态命名表。
2. 明确“单步任务 = 单节点工作流实例”的终局抽象。
3. 明确旧任务数据迁移口径：
   - `todo` 旧任务默认映射为新投影态 `Accepted`
   - `doing` 旧任务映射为 `Doing`
   - `review` 旧任务映射为 `PendingReview`
   - `done` 旧任务映射为 `Done`
4. 确认过渡期兼容原则：旧 `Task` API 先保留，由新引擎驱动投影。
5. 为每一后续阶段预留测试文件命名与 feature flag 方案。

### 5.3 自动化测试

1. 文档一致性人工检查：`workflow-refactor.md`、`architecture.md`、本文件术语一致。
2. 计划自检：每阶段均有“测试出口 + 验收内容”。

### 5.4 用户验收

1. 确认双层状态模型成立。
2. 确认旧任务映射策略可接受。
3. 确认阶段顺序与切换策略不再调整。

## 6. Phase 1 / 任务中心信息架构重排

### 6.1 目标

只改前端结构，不动任务域语义，先把当前页面改成更符合新模型的入口形态。

### 6.2 本阶段改动

1. 移除任务中心顶部统计卡片。
2. 将任务中心页头文案上移，作为首屏说明。
3. 抽离“发布任务”标签，改为页面右上角主按钮或 FAB，使用 Drawer / Modal 创建任务。
4. 调整标签顺序与默认标签：`待处理 -> 任务跟踪（含历史） -> 备忘 -> 任务模板`。
5. 首页、消息中心、深链跳转统一改到新的默认标签行为。

### 6.3 主要涉及文件

- `frontend/src/views/TaskCenterView.vue`
- `frontend/src/views/TasksView.vue`
- `frontend/src/router/index.ts`
- `frontend/tests/TaskCenterView.spec.ts`
- `frontend/tests/TasksView.spec.ts`

### 6.4 自动化测试

1. `npm run test:unit -- --run tests/TaskCenterView.spec.ts tests/TasksView.spec.ts tests/Router.spec.ts`
2. `npm run type-check`
3. `npm run build`

### 6.5 用户验收

1. 默认打开任务中心时直接看到“待处理”。
2. 在任意标签下都能点击“建立任务”弹出创建面板。
3. 历史任务已并入“任务跟踪”，且深链跳转仍可落到正确 tab。

## 7. Phase 2 / 图引擎核心模型落库

### 7.1 目标

落地新引擎的最小底座，但不切业务入口。

### 7.2 本阶段改动

1. 在后端新增或扩展图引擎核心模型：
   - `WorkflowGraphTemplate`
   - `WorkflowGraphTemplateNode`
   - `WorkflowGraphTemplateEdge`
   - `WorkflowGraphInstance`
   - `WorkflowNodeInstance`
   - `WorkflowDeliverable`
   - `WorkflowOutboxEvent`（可先建表，行为在后续阶段启用）
2. 在 `WorkflowGraphInstance` 中加入 `context JSONB`、`context_version`、`max_iterations`。
3. 在 `WorkflowNodeInstance` 中加入：
   - 引擎态
   - 业务投影态
   - 当前 assignee
   - `iteration`
   - `node_instance_version`
   - `activated_at / acknowledged_at / completed_at / terminated_at`
4. 补齐枚举、唯一索引、外键与 `SELECT ... FOR UPDATE` 所需约束。
5. 输出最小 schema 文档草案，供后续阶段引用。

### 7.3 主要涉及文件

- `backend/app/models/task_workflow.py` 或新的图引擎模型文件
- `backend/app/core/enums.py`
- `backend/alembic/versions/*`
- `backend/tests/test_models.py`
- `backend/tests/test_migrations.py`

### 7.4 自动化测试

1. `pytest -q tests/test_models.py -k "workflow_graph or node_instance or deliverable"`
2. `pytest -q tests/test_migrations.py`
3. `python -m compileall app tests`

### 7.5 用户验收

1. 数据库迁移可升级、可回滚。
2. 新模型可以在测试中创建实例、节点、边和交付物，不与旧表冲突。
3. 当前线上功能无回归，旧任务中心仍可正常使用。

## 8. Phase 3 / 单步任务接入单节点实例

### 8.1 目标

让“临时发布任务”开始走新图引擎，但仍保留旧查询投影与旧列表页。

### 8.2 本阶段改动

1. 新建 `WorkflowGraphService` 或同级服务，提供“创建单节点工作流实例”能力。
2. 手动创建任务时，后台不再只写旧 `Task`，而是：
   - 创建一个单节点 `WorkflowGraphInstance`
   - 创建一个 `Task Node Instance`
   - 同步/投影到兼容 `Task` 读模型
3. `TaskCenterService` 和 `TaskService` 保持现有 API，不改前端协议，仅替换数据来源。
4. 增加 `feature flag`，允许按环境切换“旧创建路径 / 新创建路径”。

### 8.3 主要涉及文件

- `backend/app/services/task_service.py`
- `backend/app/services/task_center_service.py`
- `backend/app/api/routes/tasks.py`
- `backend/app/schemas/tasks.py`
- 新增图引擎服务测试文件

### 8.4 自动化测试

1. `pytest -q tests/test_services.py -k "single_node_workflow_creation or task_projection"`
2. `pytest -q tests/test_api.py -k "create_task_api_uses_graph_engine"`
3. `python -m compileall app tests`

### 8.5 用户验收

1. 从“建立任务”弹窗创建的任务仍能出现在现有待办/跟踪列表里。
2. 新建任务后可以在后台查到对应的 `WorkflowGraphInstance` 和 `NodeInstance`。
3. 不开启 feature flag 时，旧链路仍可运行。

## 9. Phase 4 / 单步任务握手与转办

### 9.1 目标

把“派发即开工”的旧逻辑改成“要约 -> 接单 / 拒绝 / 转办”的真实责任握手。

### 9.2 本阶段改动

1. 增加业务投影态：`Assigned / Accepted / Rejected / Delegated`。
2. 为节点补以下动作：
   - `Acknowledge / Accept`
   - `Reject to Issuer`
   - `Delegate`
3. 记录 `acknowledged_at`、拒绝原因、转办原因、转办链日志。
4. 调整任务中心 Inbox：
   - 待确认
   - 已接受未开工
   - 已转办/已拒绝（可在跟踪中看到）
5. 发起人在 Tracking 中可看到：当前是否已接单、谁拒绝了、谁转办了。

### 9.3 主要涉及文件

- `backend/app/services/task_service.py`
- `backend/app/services/task_center_service.py`
- `backend/app/api/routes/tasks.py`
- `frontend/src/views/TaskCenterView.vue`
- `frontend/src/views/TasksView.vue`

### 9.4 自动化测试

1. `pytest -q tests/test_services.py -k "task_accept or task_reject or task_delegate"`
2. `pytest -q tests/test_api.py -k "task_acceptance_api or task_delegate_api"`
3. `npm run test:unit -- --run tests/TaskCenterView.spec.ts tests/TasksView.spec.ts`
4. `npm run type-check`

### 9.5 用户验收

1. 被指派人收到任务后，默认先看到“接受 / 退回协商 / 转办”，而不是直接进入 Doing。
2. 发起人能看到任务是否已被接单。
3. 转办后责任链条在任务详情中可见。

## 10. Phase 5 / 单步任务交付、验收、返工

### 10.1 目标

补齐“提交交付物 -> 验收通过 / 打回返工”的闭环，使单步任务具备完整契约语义。

### 10.2 本阶段改动

1. 增加业务投影态：`Doing / PendingReview / Done / ReturnedForRework / Cancelled`。
2. 新增交付提交动作：
   - 必填交付说明或附件
   - 记录 `submitted_at`
   - 生成不可篡改的 `Deliverable Snapshot`
3. 新增验收动作：
   - `Approve Completion`
   - `Return For Rework`
   - 完成质量评价
4. 记录 `rework_count`、最近一次返工原因、完成质量评分。
5. Tracking 中新增“当前阻塞 / 是否待验收 / 返工次数 / 最近提交时间”。

### 10.3 主要涉及文件

- `backend/app/services/task_service.py`
- `backend/app/models/task.py` 或投影模型
- 图引擎 deliverable 服务与 schema
- `frontend/src/views/TasksView.vue`
- `frontend/tests/TasksView.spec.ts`

### 10.4 自动化测试

1. `pytest -q tests/test_services.py -k "task_submit_deliverable or task_review_rework"`
2. `pytest -q tests/test_api.py -k "task_deliverable_api or task_review_api"`
3. `npm run test:unit -- --run tests/TasksView.spec.ts`
4. `npm run type-check`
5. `python -m compileall app tests`

### 10.5 用户验收

1. 执行人无法空着交付说明直接提交验收。
2. 发起人能对交付物进行通过或打回返工。
3. 返工后任务重新回到执行视角，且返工次数可见。

## 11. Phase 6 / 多步实例 MVP 与 Wait-All

### 11.1 目标

让多步模板先基于新图引擎跑通最保守的会签模式，不急着引入复杂路由。

### 11.2 本阶段改动

1. 将现有模板实例化逻辑逐步映射到：
   - 模板快照
   - 节点实例激活
   - `Pending -> Activated -> Completed`
2. 首批只支持：
   - 顺序流转
   - Fan-out
   - AND-Join / Wait-All
3. 节点完成后由引擎负责检查下游入度，并在事务中激活下一节点。
4. 兼容现有模板实例快照视图，不立即重做所有模板页。

### 11.3 主要涉及文件

- `backend/app/services/task_template_service.py`
- `backend/app/services/task_service.py`
- `backend/app/api/routes/task_templates.py`
- `frontend/src/views/TaskTemplatesView.vue`

### 11.4 自动化测试

1. `pytest -q tests/test_services.py -k "workflow_graph_wait_all or template_instance_activation"`
2. `pytest -q tests/test_api.py -k "task_template_graph_api"`
3. `pytest -q tests/test_workers.py -k "workflow_graph_activation"`
4. `npm run test:unit -- --run tests/TaskTemplatesView.spec.ts`
5. `npm run type-check`

### 11.5 用户验收

1. 顺序模板能按新实例快照逐步激活。
2. 会签节点必须等所有并行分支完成后才会推进。
3. 当前模板页仍能看清实例、阻塞点和历史节点。

## 12. Phase 7 / Context、条件路由与 Notice Node

### 12.1 目标

把多步流转从“静态 next step”升级为“依赖全局上下文的条件驱动图”。

### 12.2 本阶段改动

1. 节点完成时支持把字段写入 `Workflow Context`。
2. 路由边支持条件表达：
   - 比较运算
   - 枚举匹配
   - `ELSE` 默认规则
3. 实现 `Notice Node`：触达即完成，不阻塞主链。
4. 接入“智能抄送”算法：
   - 计算汇报线中间领导
   - 前端允许删除/追加
   - 提交后转成并行 Notice Node

### 12.3 主要涉及文件

- 图引擎服务与 edge 规则解析器
- `backend/app/services/organization_relation_service.py`
- `backend/app/services/access_control.py`
- `frontend/src/views/TaskTemplatesView.vue`
- `frontend/src/views/TaskCenterView.vue`

### 12.4 自动化测试

1. `pytest -q tests/test_services.py -k "workflow_context or conditional_routing or notice_node"`
2. `pytest -q tests/test_api.py -k "task_template_routing_rules_api"`
3. `npm run test:unit -- --run tests/TaskTemplatesView.spec.ts tests/TaskCenterView.spec.ts`
4. `npm run type-check`

### 12.5 用户验收

1. 上游节点可把结构化字段写入 Context。
2. 金额类条件能决定去往不同下游节点。
3. 越级派发时，中间领导会被自动列为可编辑知会名单。

## 13. Phase 8 / Wait-Any / 抢单与并发撤权

### 13.1 目标

支持真实企业场景中的或签/抢单，并确保并发撤权安全。

### 13.2 本阶段改动

1. 在模板节点和边配置中补 `join_mode = any`。
2. 任何一个并行分支先完成时：
   - 立即激活下游节点
   - 其余同批次节点置为 `Terminated / Cancelled`
   - 收回办理权限并写系统日志
3. 前端显式提示“该节点为或签 / 抢单模式”。
4. 弱网重放时增加二次提交拦截。

### 13.3 主要涉及文件

- 图引擎汇聚调度服务
- `backend/app/services/task_template_service.py`
- `frontend/src/views/TaskTemplatesView.vue`
- `frontend/src/views/TasksView.vue`

### 13.4 自动化测试

1. `pytest -q tests/test_services.py -k "workflow_wait_any or race_cancellation"`
2. `pytest -q tests/test_api.py -k "workflow_wait_any_api"`
3. `npm run test:unit -- --run tests/TaskTemplatesView.spec.ts tests/TasksView.spec.ts`
4. `npm run type-check`

### 13.5 用户验收

1. 并行三人或签时，只要一人完成，下游立即推进。
2. 另外两人的节点会被系统终止，不能继续提交。
3. 节点详情里能看到“因 or-sign 被系统撤权”的日志。

## 14. Phase 9 / 深度打回与版本迭代

### 14.1 目标

实现设计稿中最重的能力：Append-Only 深度打回、指定节点退回、版本链保存。

### 14.2 本阶段改动

1. 支持当前节点指定退回到任意上游节点。
2. 引擎不物理回退旧节点，而是：
   - 克隆目标节点的新版实例
   - 记录 `iteration`
   - 按策略重放后续尾链
3. 首版固定采用“严谨模式”：退回目标节点后，目标节点及其后续链路重新生成新版本节点。
4. 所有旧节点保留只读历史，不允许覆盖旧交付物与旧意见。
5. 引入 `max_iterations` 保护，防止无限打回。

### 14.3 主要涉及文件

- 图引擎版本迭代服务
- 节点实例克隆与尾链重放逻辑
- `frontend/src/views/TasksView.vue`
- `frontend/src/views/TaskTemplatesView.vue`

### 14.4 自动化测试

1. `pytest -q tests/test_services.py -k "deep_rejection or append_only_iteration"`
2. `pytest -q tests/test_api.py -k "deep_rejection_api"`
3. `pytest -q tests/test_workers.py -k "iteration_replay"`
4. `npm run test:unit -- --run tests/TasksView.spec.ts tests/TaskTemplatesView.spec.ts`
5. `npm run type-check`

### 14.5 用户验收

1. D 可以直接退回到 A。
2. A 重做后会生成 `A-V2`，而不是覆盖旧节点记录。
3. 旧版本交付物、意见、耗时仍可查看。

## 15. Phase 10 / DAG 设计器与节点级时间线

### 15.1 目标

把后端能力完整暴露为业务可用的配置与查看界面。

### 15.2 本阶段改动

1. 模板页升级为完整“表格式 DAG 设计器”：
   - 节点表
   - 路由规则编辑器
   - `join_mode` 配置
   - 驳回/退回规则
   - Context 字段映射
2. 增加前端拓扑校验、规则完备性校验、Context 字段白名单校验。
3. 任务详情页改造成“节点板块式时间线”：
   - 节点标题
   - 节点状态
   - 交付物快照
   - 节点级评论
   - 节点级系统日志
4. Tracking 视图展示 `Current Blocker`、当前持棒人、节点超时、返工次数、催办入口。

### 15.3 主要涉及文件

- `frontend/src/views/TaskTemplatesView.vue`
- `frontend/src/views/TasksView.vue`
- `frontend/src/views/TaskCenterView.vue`
- `frontend/tests/TaskTemplatesView.spec.ts`
- `frontend/tests/TaskCenterView.spec.ts`
- `frontend/tests/TasksView.spec.ts`

### 15.4 自动化测试

1. `npm run test:unit -- --run tests/TaskTemplatesView.spec.ts tests/TaskCenterView.spec.ts tests/TasksView.spec.ts`
2. `npm run type-check`
3. `npm run build`

### 15.5 用户验收

1. 非技术用户可通过表格完成 DAG 配置，不需要直接写 JSON。
2. 非法路由、无兜底规则、错误 Context 字段会在提交前被拦下。
3. 打开任务详情页时，可以按节点看到完整责任链与版本链。

## 16. Phase 11 / 韧性硬化、迁移切流与全量回归

### 16.1 目标

完成从当前新链路可用到新链路可默认启用的最后一公里。本阶段拆分为 7 个子阶段（11-A 至 11-G），按依赖顺序逐步交付。

### 16.2 子阶段总览

| 子阶段 | 名称 | 核心目标 | 状态 |
| --- | --- | --- | --- |
| 11-A | routing_rules 旧系统桥接 | 将前端写入 TaskTemplateStep.config 的 routing_rules 接入后端条件激活逻辑 | done |
| 11-B | Takeover（管理员接管节点） | 管理员可强制接管任意节点实例，写审计日志，通知原执行人 | not_started |
| 11-C | Outbox Pattern 可靠投递 | 启用 workflow_outbox_events 消费 worker，实现节点事件异步补偿 | not_started |
| 11-D | 幂等与并发防御加固 | 补齐节点重复提交、Wait-All 双激活、Wait-Any 双提交的防御边界 | not_started |
| 11-E | 旧数据迁移脚本 | 编写旧 Task / TaskTemplateStepRun 到 WorkflowNodeInstance 的迁移与回滚脚本 | not_started |
| 11-F | 默认路径切流 | 将默认创建路径与任务中心查询切换到新引擎 | not_started |
| 11-G | 文档收口与全量回归 | 更新 architecture.md / progress.md / README，执行全量回归与生产近似部署演练 | not_started |

---

### 16.3 Phase 11-A / routing_rules 旧系统桥接

**完成状态：done（2026-04-30）**

#### 目标

前端（`TaskTemplatesView`）通过路由规则编辑器把 `routing_rules` 写入 `TaskTemplateStep.config`；后端 `TaskService._activate_ready_template_steps` 在判断是否激活下游步骤时，需评估上游步骤的 `routing_rules`，仅激活条件匹配的目标步骤。

#### 本阶段改动

1. 新建 `backend/app/services/condition_evaluator.py`：`is_else_condition` / `evaluate_condition` / `evaluate_routing_rules` 三个函数；支持 `eq/neq/gt/gte/lt/lte/in/not_in/contains/exists` 与嵌套 `all/any`。
2. `WorkflowGraphService` 删除内联的条件求值方法，改为引用 `condition_evaluator` 模块函数。
3. `TaskService._activate_ready_template_steps` 新增 `_routing_rules_allow_step_activation` 静态方法：评估上游步骤的 `routing_rules`，`step_key` 不在命中集合中时跳过激活；无规则时完全向后兼容。
4. 使用 `instance.payload` 作为 `routing_context`。

#### 主要涉及文件

- `backend/app/services/condition_evaluator.py`（新建）
- `backend/app/services/workflow_graph_service.py`
- `backend/app/services/task_service.py`
- `backend/tests/test_services.py`

#### 验证命令

```powershell
d:/Repos/FilumReforge/.venv/Scripts/python.exe -m pytest -q "d:/Repos/FilumReforge/backend/tests/test_services.py" -k "phase11a" --tb=short
```

预期：`2 passed`（条件匹配激活目标步骤 + ELSE 回落激活）。

#### 验证结论

2 个集成测试全部通过；全量回归无新增失败（仅两个预存在失败与本阶段无关）。

---

### 16.4 Phase 11-B / Takeover（管理员接管节点）

**完成状态：not_started**

#### 目标

管理员可以强制接管卡住的节点实例，绕过正常握手语义，并写入可追溯的审计日志。

#### 本阶段改动

1. 后端新增 `WorkflowGraphService.takeover_node_instance()`：校验节点处于 `ACTIVATED` 或 `ACKNOWLEDGED`；强制切换 `assignee_id`；在 `config` 写入 takeover 审计标记（时间、操作人、原因）；通知原执行人。
2. 新增 `WorkflowNodeTakeoverRequest` schema。
3. `workflow_graph_engine` 路由新增 `POST /api/v1/workflow-graph/node-instances/{id}/takeover`。
4. 前端 `TasksView` 管理员角色下在节点板块显示"接管"按钮，弹确认对话框，调用新接口。

#### 主要涉及文件

- `backend/app/services/workflow_graph_service.py`
- `backend/app/schemas/workflow_graph.py`
- `backend/app/api/routes/workflow_graph_engine.py`
- `frontend/src/views/TasksView.vue`
- `frontend/tests/TasksView.spec.ts`

#### 用户验收

1. 管理员打开任意卡住的节点，看到"接管"入口。
2. 接管后节点 assignee 切换，原执行人收到通知。
3. 节点详情中有系统接管审计日志。

---

### 16.5 Phase 11-C / Outbox Pattern 可靠投递

**完成状态：not_started**

#### 目标

启用 `workflow_outbox_events` 表的 worker 消费逻辑，使节点事件在数据库写入成功后能被 ARQ worker 可靠异步投递，防止通知丢失。

#### 本阶段改动

1. ARQ worker 新增 `process_workflow_outbox_events` 任务，定期扫描 `PENDING` 事件投递到 `NotificationService`。
2. `WorkflowGraphService` 在关键节点动作时写入 outbox 事件（表结构已预留，本阶段启用写入逻辑）。
3. 失败事件更新 `retry_count` 与 `error_message`，超上限标记 `DEAD_LETTER`。
4. ARQ 定时任务注册补充该任务（扫描间隔建议 30 秒）。

#### 主要涉及文件

- `backend/app/workers/workflow_outbox_worker.py`（新建）
- `backend/app/services/workflow_graph_service.py`
- `backend/app/workers/main.py`
- `backend/tests/test_workers.py`

---

### 16.6 Phase 11-D / 幂等与并发防御加固

**完成状态：not_started**

#### 目标

补齐图引擎在极端并发场景下的防御边界。

#### 本阶段改动

1. **节点重复提交防御**：`complete_node_instance()` 当节点已处于 `COMPLETED`/`TERMINATED` 时幂等返回，不报错也不重复推进下游。
2. **Wait-All 双激活防御**：`_activate_downstream_nodes()` 检查目标节点是否已非 `PENDING`，已激活则跳过；依赖行锁。
3. **Wait-Any 双提交防御**：补压测场景测试，确认已有保护生效（两并行节点同时完成时只有一个推进下游）。
4. **转办与打回并发冲突**：依赖行锁确保 `delegate_node()` 与 `deep_reject_to_upstream()` 在同一节点上不并发执行。

---

### 16.7 Phase 11-E / 旧数据迁移脚本

**完成状态：not_started**

#### 目标

编写旧链路任务数据到图引擎模型的迁移脚本，支持 `--dry-run` 与回滚。

#### 本阶段改动

1. 新建 `backend/app/scripts/migrate_legacy_tasks_to_graph.py`：扫描非图引擎 `Task`，创建对应单节点 `WorkflowGraphInstance + WorkflowNodeInstance`；状态映射：`todo→ACTIVATED/Accepted`，`doing→ACKNOWLEDGED/Doing`，`review→COMPLETED/PendingReview`，`done→COMPLETED/Done`；支持 `--dry-run`。
2. 新建 `backend/app/scripts/rollback_legacy_task_migration.py`：按 `source_id` 删除图引擎记录，不删原 `Task`。

---

### 16.8 Phase 11-F / 默认路径切流

**完成状态：not_started**

#### 目标

将默认创建路径与任务中心读取路径切换到新引擎，旧链路 feature flag 仅作紧急回退。

#### 本阶段改动

1. 更新 `.env.example` 与 `.env.prod.example`：`WORKFLOW_GRAPH_ENGINE_ENABLED=true` 作为默认值显式注明。
2. `TaskCenterService` 读取路径优先从 `WorkflowNodeInstance` 投影。
3. 确认任务列表、详情、评论、日志、附件、模板实例化均在新链路完整覆盖。
4. 保留 `TASK_CENTER_V2_ENABLED` 作为紧急回退开关至少 30 天。

#### 主要涉及文件

- `backend/.env.example`
- `infra/docker/.env.prod.example`
- `backend/app/services/task_center_service.py`
- `backend/app/services/task_service.py`

---

### 16.9 Phase 11-G / 文档收口与全量回归

**完成状态：not_started**

#### 目标

Phase 11 各子阶段完成后执行最终全量回归并更新所有文档。

#### 本阶段改动

1. 更新 `memory-bank/architecture.md`：记录 Phase 11 新增模块（condition_evaluator、takeover、outbox worker、迁移脚本）与切流后系统基线。
2. 更新 `memory-bank/progress.md`：记录 Phase 11 各子阶段验证结论。
3. 更新 `README.md`、`backend/README.md`：删除旧链路保留相关说明，补充切流后运行基线。
4. 更新 `memory-bank/deployment-runbook-ubuntu-2404.md`：补充迁移脚本执行步骤。
5. 执行完整生产近似部署演练：`bash scripts/check-release.sh`（Ubuntu 24.04 / Docker 近似环境）。

#### 自动化测试出口

```powershell
d:/Repos/FilumReforge/.venv/Scripts/python.exe -m pytest -q "d:/Repos/FilumReforge/backend/tests/" --tb=line
d:/Repos/FilumReforge/.venv/Scripts/python.exe -m compileall backend/app backend/tests
# frontend
npm run test:unit -- --run
npm run type-check
npm run build
npm exec oxlint .
npm exec eslint .
```

#### 用户验收

1. 新建单步任务与多步任务全部走新引擎，旧任务仍可查看。
2. 极端场景下不会出现重复激活、重复审批或责任链断裂。
3. 全量回归通过后，可关闭旧链路 feature flag。

---

### 16.10 已知预存在问题（需在 Phase 11-G 前修复）

以下两个测试失败与 Phase 11 工作无关，属于遗留问题，应在 Phase 11-G 全量回归前修复：

| 测试 | 失败原因 | 优先级 |
| --- | --- | --- |
| `test_settings.py::test_default_settings_align_with_phase_a_baseline` | 测试校验 `workflow_graph_engine_enabled` 默认值为 `False`，但 `backend/.env` 已设为 `True`；测试未加载 `.env` 导致不一致 | 中 |
| `test_api.py::test_task_collaboration_and_stats_api_flow` | `accept` 接口返回 409，测试数据初始化与图引擎双写路径的状态预期存在偏差 | 中 |

**修复建议**：
- `test_default_settings_align_with_phase_a_baseline`：更新测试期望值以反映 `WORKFLOW_GRAPH_ENGINE_ENABLED=true` 当前基线，或使测试隔离于 `.env` 文件。
- `test_task_collaboration_and_stats_api_flow`：审查 `accept` 接口前置状态假设，对齐图引擎启用后节点初始业务投影态（`Assigned`）。
## 17. 阶段间硬性闸门

1. 每个阶段结束后先跑对应自动化测试，再交用户验收。
2. 用户未确认前，不进入下一阶段编码。
3. 任何触及 schema 的阶段完成后，必须先更新 `architecture.md`。
4. 任何改变阶段状态的阶段完成后，必须更新 `progress.md`。
5. 如果某阶段发现双层状态模型或切换策略需要改动，必须先更新本文件，再继续编码。
6. 用户确认后，commit更改到git，说明本阶段更改的内容。

## 18. 建议的首批落地顺序

如果只启动第一轮实现，建议先做以下三个阶段：

1. Phase 1 / 任务中心信息架构重排
2. Phase 2 / 图引擎核心模型落库
3. Phase 3 / 单步任务接入单节点实例

原因：

- 这三步能最快把“页面方向”“底层模型”“新旧链路兼容策略”固定下来。
- 它们尚未引入最危险的 Deep Rejection 和 Wait-Any 并发撤权问题。
- 做完这三步后，后续每个动作都能围绕新引擎追加，而不是继续在旧状态机上堆补丁。