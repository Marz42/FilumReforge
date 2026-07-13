# 工作流图引擎升级指导报告

## 1. 报告目的

本报告用于指导当前工作流图引擎从“功能较完整的人工作业型 DAG 引擎”升级为一个边界清晰、可持续演进的企业内部工作流平台。

报告重点不在于穷举所有数据表、字段和 API 契约，而在于明确：

1. 各层的职责与设计意图；
2. 理想实现应当具备的结构；
3. 当前实现已经具备的能力；
4. 当前能力与目标结构之间的差距；
5. 后续升级的优先级和实施顺序；
6. 每一阶段的完成标准。

---

## 2. 当前系统的总体判断

当前系统已经具备以下核心能力：

- DAG 模板、模板节点和模板边；
- 模板版本链；
- 流程实例和节点实例；
- 条件边；
- fan-out；
- join all / join any；
- Notice 自动完成；
- 深度打回和 iteration；
- takeover；
- Task 投影；
- Outbox；
- append-only Run Event；
- 周期调度；
- 视频批次和生产流程扩展；
- 任务中心 graph-first 读取。

因此，当前系统并非一个简单任务状态机，而是一个已经具备持久化能力的图流程执行内核。

当前最主要的问题不是功能不足，而是不同职责开始混合：

- NodeInstance 既承担流程节点执行，又承担人工工作状态；
- Task 既是真实工作项，又是流程节点投影；
- Task 与 NodeInstance 双向写入；
- 流程运行时、审批、交付、通知和视频业务逻辑部分混合；
- 查询层通过 graph-first 动态拼装业务状态；
- 部分实验能力只在前端受控，后端未形成真正门闩；
- 运行时的分支、Join、失败恢复和返工语义尚未完全形式化。

当前系统最需要完成的是结构收敛，而不是继续向现有 Service 中增加更多特殊节点和业务分支。

---

## 3. 目标总体架构

建议将系统明确划分为六个核心模块群：

1. 工作项域 Work Item；
2. 流程定义域 Workflow Definition；
3. 流程运行时 Workflow Runtime；
4. 业务能力域 Business Capabilities；
5. 投影与查询域 Projection & Query；
6. 基础设施层 Infrastructure。

整体关系如下：

```text
流程定义域
定义流程蓝图、节点配置和流转规则
        ↓
流程运行时
实例化流程、控制节点和执行路径
        ↓
业务能力域
完成审批、人工任务、交付、通知、Webhook 等具体动作
        ↓
工作项域
承载可分配、可跟踪、可完成的人工工作

所有领域
        ↓ 领域事件
投影与查询域
构建任务中心、流程追踪、时间线和统计读模型

所有模块
        ↓
基础设施层
提供事务、持久化、消息、调度、幂等、监控和外部集成
```

需要注意：

- 工作项域与业务能力域不是严格的上下层关系。人工任务能力通常会创建工作项，审批能力也可能为审批人创建工作项。
- 流程运行时控制的是 Node Execution，而不是直接控制一组 Task。
- 投影与查询域只构建读模型，不拥有业务状态。
- 基础设施不是业务领域，不决定业务规则。

---

# 第一部分：工作项域

## 4. 工作项域的意图

工作项域负责描述：

> 一项可以被独立分配、跟踪、处理、完成和审计的具体工作。

Work Item 是用户协作层面的最小管理单元。它不一定在客观上完全不可拆分，但在系统中必须具备独立生命周期。

典型问题包括：

- 这项工作是什么；
- 谁负责；
- 当前处于什么状态；
- 什么时候开始和截止；
- 是否被阻塞；
- 是否需要交付和验收；
- 最终是否完成、取消或退回；
- 谁做过哪些操作。

工作项域不负责：

- 流程分支和 Join；
- 节点激活；
- 流程下一步走向；
- 审批票数计算；
- Webhook 重试；
- 视频生产的特殊流程逻辑。

---

## 5. 理想实现

### 5.1 Work Item 是独立领域实体

Work Item 应拥有自己的：

- 类型；
- 标题和描述；
- 状态；
- 标准状态类别；
- 负责人；
- 所属团队；
- 项目；
- 优先级；
- 截止时间；
- 参与者；
- 交付要求；
- 状态历史；
- 乐观版本。

### 5.2 工作项类型应显式区分

建议至少区分：

- standalone_task：独立任务；
- process_human_task：流程人工任务；
- approval_task：审批工作入口；
- process_run_shell：流程运行的展示入口；
- system_generated_task：系统生成工作项。

### 5.3 状态变化必须通过命令

关键业务变化不应通过任意 PATCH 完成，而应通过显式命令：

- AssignWorkItem；
- AcceptWorkItem；
- StartWork；
- SubmitForReview；
- CompleteWorkItem；
- ReturnForRework；
- CancelWorkItem；
- DelegateWorkItem；
- TakeOverWorkItem；
- BlockWorkItem；
- UnblockWorkItem。

### 5.4 Work Item 与流程节点应通过正式关联

对于流程人工节点：

```text
NodeExecution
    ↓ HumanTask Handler
WorkItem
```

应建立正式 Link，而不是依靠：

- Task.extra_metadata；
- NodeInstance.config.task_id。

Work Item 与 NodeExecution 各自拥有不同状态：

```text
WorkItem：in_progress / pending_review / completed
NodeExecution：waiting / completed / failed
```

二者不要求一一镜像。

### 5.5 独立任务不应强制创建单节点流程

普通日常任务应直接由 Work Item 域管理。只有真正需要流程协调的任务才关联 NodeExecution。

---

## 6. 当前已实现能力

- 已有 Task 实体；
- 已有任务中心；
- 已有接受、拒绝、转交、办理和验收；
- 已有评论和部分审计；
- 已有 Task 与 NodeInstance 互链；
- 已有普通任务单节点图化；
- 已有 ROOT Task；
- 已有图优先状态解析。

---

## 7. 当前差距

### 高优先级差距

1. Task 与 NodeInstance 都在承担工作写真相，形成双主写。
2. 普通任务被强制创建单节点图实例。
3. 关键关系存储在 JSON 中，缺少外键和唯一性。
4. TaskService 和 WorkflowGraphService 直接理解并修改对方状态。
5. ROOT Task 与普通工作项混用同一语义。
6. 工作状态与流程引擎状态缺少明确边界。

### 目标状态

```text
WorkItemService
只维护工作项状态

WorkflowRuntime
只维护节点和流程状态

HumanTaskCoordinator
在应用层协调跨域操作

workflow_human_task_links
保存正式关联
```

---

# 第二部分：流程定义域

## 8. 流程定义域的意图

流程定义域负责描述：

> 一类工作或系统动作应当如何被组织、连接、分支、汇合和结束。

流程定义是静态蓝图，不保存实际运行状态。

它回答：

- 流程包含哪些节点；
- 节点之间如何连接；
- 节点需要什么业务能力；
- 分支条件是什么；
- Join 策略是什么；
- 启动时需要哪些输入；
- Context 允许保存哪些字段；
- 流程如何结束；
- 谁可以启动和管理流程。

---

## 9. 理想实现

### 9.1 Definition 与 Version 显式分离

```text
ProcessDefinition
    └── ProcessDefinitionVersion
```

ProcessDefinition 表示长期身份，例如“采购申请流程”。

ProcessDefinitionVersion 表示不可变执行版本，例如 V3。

流程实例必须绑定具体版本。

### 9.2 发布版本完全不可变

发布后的以下内容均不可修改：

- 节点；
- 边；
- 条件；
- Assignment Policy；
- Context Schema；
- Input Schema；
- Completion Policy；
- Node Config；
- 业务能力配置；
- UI 组件键。

修改必须创建新 Draft 版本并重新发布。

### 9.3 节点定义只描述步骤，不保存运行状态

Node Definition 可以包含：

- 节点类型；
- Work Item Specification；
- Assignment Policy；
- Retry Policy；
- Cancellation Policy；
- Input / Output Mapping；
- 业务能力配置。

不能包含：

- 当前负责人；
- 当前状态；
- 实际完成时间；
- 本次审批结果。

### 9.4 路由模式必须显式

建议支持：

- exclusive；
- inclusive；
- parallel；
- first_match。

不能仅通过边 priority 隐式推断。

### 9.5 完成策略必须显式

推荐显式 Start / End 节点。

End 节点应携带结果：

- success；
- approved；
- rejected；
- cancelled。

不能仅依赖“没有活跃节点”判断流程完成。

### 9.6 Context 应类型化

应区分：

- Input Schema；
- Process Context Schema；
- Node Input Mapping；
- Node Output Mapping。

节点不应默认拥有对整个 Context 的任意读写权。

### 9.7 节点类型应可扩展

核心只保留稳定节点类型：

- HumanTask；
- Approval；
- Notice；
- Timer；
- Webhook；
- WaitSignal；
- Subprocess；
- Start；
- End；
- Split / Join。

垂直业务节点通过 Handler 注册，例如：

- video.capture；
- video.aggregate；
- video.production。

---

## 10. 当前已实现能力

- WorkflowGraphTemplate；
- WorkflowGraphTemplateNode；
- WorkflowGraphTemplateEdge；
- base_code + version + source_template_id；
- draft / active / archived；
- 条件边；
- priority；
- else；
- context_schema；
- assignment_mode；
- join_mode；
- assignee_rule；
- validate；
- dry-run；
- import/export；
- DAG 预览；
- 部门作用域。

---

## 11. 当前差距

1. Definition 与 Version 仍是隐式关系。
2. 发布版本不一定完全不可变。
3. config 承担过多非类型化配置。
4. launch_schema、participant_policies、assignee_rule 分散。
5. routing_rules 与运行时 Edge Condition 概念重复。
6. 缺少显式 Routing Mode。
7. 缺少显式 Completion Policy。
8. Start / End 仍主要依赖零入度和无活动节点推断。
9. scope_department_ids 的空数组语义不够安全。
10. 节点类型仍是固定枚举，视频业务通过特殊逻辑扩展。

---

# 第三部分：流程运行时

## 12. 流程运行时的意图

流程运行时是某个已发布流程定义版本的一次持久化执行。

它负责：

- 创建流程实例；
- 创建和激活节点执行；
- 维护流程 Context；
- 处理条件分支；
- 处理并行和 Join；
- 等待人工任务、审批、Timer、Signal 或外部动作；
- 接收节点结果；
- 推进后续路径；
- 处理失败、重试、暂停和取消；
- 判断流程最终状态与结果；
- 保存完整运行历史。

流程运行时的核心管理对象是：

```text
ProcessInstance
+
NodeExecution
+
ExecutionToken
+
ProcessContext
```

不是简单的一组 Task。

---

## 13. 理想实现

### 13.1 ProcessInstance

应记录：

- definition_version_id；
- status；
- result；
- business_key；
- Context；
- Context version；
- started_by；
- started_at；
- completed_at；
- aggregate version。

建议状态：

- pending；
- active；
- suspended；
- completed；
- failed；
- cancelled；
- terminated。

### 13.2 NodeExecution

应记录：

- 对应 Node Definition；
- engine state；
- iteration / generation；
- 激活、完成和终止时间；
- 执行结果；
- 版本。

建议状态：

- pending；
- ready；
- activated；
- waiting；
- running；
- retrying；
- completed；
- failed；
- skipped；
- cancelled；
- terminated；
- superseded。

### 13.3 Execution Token

Token 用于表达本次运行实际经过的路径。

它负责解决：

- 条件分支；
- 并行分裂；
- Join 实际等待集合；
- Wait-Any；
- 返工后的旧分支失效；
- 取消传播；
- 子流程返回。

Join 应等待实际产生的 Token，而不是模板静态入度。

### 13.4 Context Patch

节点不应直接合并任意 JSON。

应使用：

- expectedContextVersion；
- 显式 Patch；
- 字段级冲突检测；
- Context Diff 事件。

### 13.5 显式完成与失败语义

流程完成必须满足明确条件：

- 到达合法 End；
- 无悬挂 Token；
- 无 failed 节点；
- 无无法满足的 Join；
- 无 no-route 异常。

“没有活跃节点”只能作为检查条件之一，不能直接代表成功。

### 13.6 人工恢复能力

运行时应支持：

- suspend；
- resume；
- retry node；
- skip node；
- cancel process；
- patch context；
- takeover；
- reproject；
- replay outbox；
- inspect join；
- inspect route evaluation。

---

## 14. 当前已实现能力

- WorkflowGraphInstance；
- WorkflowNodeInstance；
- context / context_version；
- 零入度激活；
- 条件边；
- fan-out；
- join all；
- join any；
- Notice 自动完成；
- 行锁；
- node_instance_version；
- 节点完成幂等返回；
- deep reject；
- iteration；
- max_iterations；
- takeover；
- parent_instance_id；
- Run Event；
- Outbox。

---

## 15. 当前差距

### 运行正确性差距

1. 缺少 Execution Token。
2. Join 可能依赖静态入度，无法精确表达实际激活分支。
3. Wait-Any 直接终止 peer，缺少取消策略。
4. Deep Reject 缺少完整后代失效和补偿语义。
5. current_node_key 无法表达 DAG 多活动节点。
6. instance_key 使用办理人 UUID，与 takeover 语义冲突。
7. Context 合并缺少显式 Patch 和冲突控制。
8. 缺少 failed、suspended、skipped 等状态。
9. 无活跃节点可能被误判为完成。
10. 缺少节点执行 Attempt 和技术重试模型。
11. 缺少明确 Start / End 和流程结果。
12. Feature Flag 尚未形成后端真正 Capability Policy。

---

# 第四部分：业务能力域

## 16. 业务能力域的意图

业务能力域负责：

> 某一类具体业务动作如何被执行、如何判断成功、如何保存自身数据，以及如何向流程运行时报告结果。

流程运行时回答：

- 什么时候调用；
- 等待什么结果；
- 结果之后走向哪里。

业务能力回答：

- 具体怎样执行；
- 谁可以执行；
- 如何判断完成；
- 失败如何处理；
- 数据如何保存；
- 是否支持取消和补偿。

业务能力通过 Node Handler 与流程运行时连接。

---

## 17. 理想实现

### 17.1 Node Handler 作为适配层

统一 Handler 契约应支持：

- validate_definition；
- activate；
- handle_command；
- cancel；
- retry；
- compensate；
- map_result。

Handler 只负责：

- 读取节点配置；
- 调用具体业务能力；
- 建立 Link；
- 将能力结果转换为 Runtime Command。

Handler 不应承载复杂业务规则。

### 17.2 Human Task

HumanTask 节点包含 Work Item Specification。

节点激活时：

- 解析标题；
- 解析负责人；
- 计算截止时间；
- 创建 Work Item；
- 创建正式 Link；
- 运行时进入 waiting。

### 17.3 Approval

应有独立模型：

- ApprovalRequest；
- ApprovalParticipant；
- ApprovalDecision；
- Approval Round。

应支持：

- any one；
- all；
- m of n；
- sequential；
- manager chain；
- delegation；
- add approver；
- resubmission。

流程运行时只接收 approved / rejected / cancelled 等最终结果。

### 17.4 Deliverable

交付物应支持多版本：

- Submission；
- Review；
- accepted_submission_id；
- supersedes_submission_id。

不能仅使用节点 1:1 交付快照。

### 17.5 Notification

通知能力负责：

- 模板渲染；
- 收件人解析；
- 渠道；
- 去重；
- 重试；
- 发送记录。

Notice 节点应明确：

- 入队即完成；
- 发送成功完成；
- 所有渠道成功完成。

### 17.6 Webhook / External Action

应支持：

- 认证；
- 超时；
- 重试；
- 幂等；
- 响应映射；
- 错误分类；
- 人工重试；
- 敏感字段脱敏。

### 17.7 Timer / Signal / Subprocess

- Timer：恢复已有流程，不等于周期启动新流程；
- Signal：等待外部事件；
- Subprocess：父节点等待子流程结果，不等于简单 on_complete 链式启动。

### 17.8 视频业务应扩展化

视频采集、聚合、批次和生产应作为独立扩展模块，通过注册的 Node Handler、Projection Handler 和 UI Renderer 接入核心引擎。

核心引擎不应直接判断 run_kind 或 video profile。

---

## 18. 当前已实现能力

- task / approval / notice 节点类型；
- Task 投影；
- WorkflowDeliverable；
- Notice 自动完成；
- Outbox；
- 视频采集、聚合、批次、生产；
- parent Run；
- fork；
- on_complete；
- Schedule；
- takeover。

---

## 19. 当前差距

1. Approval 尚未形成独立 ApprovalRequest / Decision。
2. Deliverable 仍主要是节点 1:1 快照。
3. Human Task 与 NodeInstance 仍是双向写。
4. Notification 与 Notice 的完成语义未形式化。
5. Timer 节点未实现。
6. Webhook 通用能力未形成。
7. Signal 订阅未实现。
8. Subprocess 尚未形成正式父子等待语义。
9. Automation 逻辑分散在多个 Service。
10. 视频能力侵入通用 Runtime、事件和 UI 分支。
11. 缺少统一 Capability Result。
12. 缺少 interruptible、side_effect、compensation 等能力声明。

---

# 第五部分：投影与查询域

## 20. 投影与查询域的意图

投影与查询域负责：

> 将多个领域中面向写入、规范化的数据，转换为面向用户展示、筛选、排序、分页、统计和时间线的读取模型。

它回答：

- 用户现在应该看到什么；
- 如何快速查询；
- 如何统一展示不同领域对象；
- 如何构建任务中心和流程追踪；
- 如何形成统计和工作负载视图。

它不回答：

- 任务是否能完成；
- 节点是否应该激活；
- 审批是否通过；
- 流程下一步走哪里。

---

## 21. 理想实现

### 21.1 写模型与读模型分离

写模型保证业务正确性：

- work_items；
- process_instances；
- node_executions；
- approval_requests；
- deliverable_submissions。

读模型保证查询效率：

- task_center_items；
- process_run_summaries；
- node_timeline_entries；
- workload_snapshots；
- process_metrics。

### 21.2 Task Center 统一投影

Task Center 可以统一显示：

- standalone Work Item；
- Human Task；
- Approval；
- Process Run；
- System Alert。

但不意味着这些对象都是真实 Task。

process_run 可以直接由 ProcessInstance 投影，不必创建 ROOT Task。

### 21.3 展示状态与业务状态分离

Task Center 可保存：

- display_status；
- state_category；
- requires_action；
- action_type。

这些只是展示语义，不能反向修改业务状态。

### 21.4 事件驱动更新

推荐：

- 命令响应直接返回最新业务对象；
- Task Center、时间线和统计采用异步投影；
- 支持投影幂等；
- 支持 checkpoint；
- 支持重建；
- 支持检测投影延迟。

### 21.5 节点级统一时间线

应聚合：

- Node Event；
- Work Item Activity；
- Comment；
- Deliverable；
- Approval；
- System Log；
- Rework；
- Takeover。

不能继续由前端分别查询多个来源并拼装。

---

## 22. 当前已实现能力

- Task 统一列表和详情载体；
- graph-first 解析；
- GraphTaskProjection；
- inbox / tracking / history；
- ROOT Task；
- Run Event 时间线；
- 部门 Run 统计；
- ui_profile；
- 视频专用详情面板。

---

## 23. 当前差距

1. Task 同时是写模型和读模型。
2. graph-first 在查询时动态拼装多个业务表。
3. JSON 锚点成为查询关键依赖。
4. ROOT Task 是伪业务对象。
5. 节点时间线、Task 评论、交付和审批记录仍分散。
6. ui_profile 是隐式 JSON 契约。
7. 缺少正式 task_center_items。
8. 缺少 projector checkpoint。
9. 缺少投影重建。
10. 缺少统一 process_run_summary。
11. 缺少工作负载和流程指标读模型。
12. 查询层对 Runtime 内部模型了解过多。

---

# 第六部分：基础设施层

## 24. 基础设施层的意图

基础设施层负责：

> 为所有领域提供一致、可靠、可重试、可恢复、可监控的技术运行环境。

它包括：

- PostgreSQL；
- ORM；
- Repository；
- Unit of Work；
- Outbox；
- Job Queue；
- Scheduler；
- Idempotency；
- Lock；
- Observability；
- Audit；
- Object Storage；
- Integration Gateway；
- Authentication；
- Feature Flag / Capability Policy。

基础设施不决定业务规则。

---

## 25. 理想实现

### 25.1 统一事务边界

应用层协调器控制事务。

Service 不应随意 commit。

典型事务：

```text
完成 Work Item
→ 完成 NodeExecution
→ 更新 Context
→ 激活下游
→ 写 Domain Event
→ 写 Outbox
→ Commit
```

### 25.2 模块表所有权

一个 PostgreSQL 实例即可，但每个模块只修改自己拥有的表。

跨模块通过公开接口和应用协调器交互。

### 25.3 统一事件信封

所有跨模块事件应包含：

- event_id；
- event_type；
- schema_version；
- aggregate_id；
- aggregate_version；
- actor；
- command_id；
- causation_id；
- correlation_id；
- occurred_at；
- payload。

### 25.4 Command Idempotency

需要统一 command receipt，覆盖：

- 创建 Run；
- 节点完成；
- Deep Reject；
- Takeover；
- Schedule；
- Subprocess；
- Webhook 回调。

### 25.5 Outbox 可靠投递

应支持：

- SKIP LOCKED；
- 消费去重；
- 指数退避；
- 最大重试；
- Dead Letter；
- 人工重放；
- 外部副作用幂等。

### 25.6 Scheduler 与 Timer 分离

- Schedule：启动新流程；
- Timer：恢复已有流程节点。

### 25.7 Capability Policy

能力控制应分为：

- Deployment Flag；
- Tenant Capability；
- Definition Capability。

服务端必须真正阻断，前端仅控制展示。

### 25.8 可观测性

日志和 Trace 应围绕：

- request_id；
- command_id；
- correlation_id；
- process_instance_id；
- node_execution_id；
- work_item_id。

应监控：

- 活跃流程；
- 失败节点；
- Join 等待；
- Outbox backlog；
- 最老 Outbox 消息年龄；
- 投影延迟；
- Dead Letter；
- 卡死流程。

---

## 26. 当前已实现能力

- PostgreSQL；
- ORM；
- 九表图引擎；
- node_instance_version；
- 行锁；
- Outbox；
- ARQ Worker；
- Run Event；
- Template Schedule；
- Feature Flag；
- 部分状态幂等；
- 部分审计和统计。

---

## 27. 当前差距

1. 事务边界仍可能分散，存在 Service 内 commit。
2. 缺少统一 Unit of Work。
3. 缺少统一 Command Receipt。
4. 缺少完整 Consumer Deduplication。
5. failed Outbox 尚未形成完整 Dead Letter 运维能力。
6. 缺少统一 Event Envelope。
7. 缺少 correlation / causation 链。
8. Feature Flag 服务端门闩不完整。
9. 缺少投影 checkpoint。
10. 缺少节点级 Timer。
11. 缺少人工重放和恢复控制台。
12. 缺少围绕流程实例和节点执行的完整可观测性。
13. 外部集成凭据、重试、熔断和幂等尚未统一。
14. 附件和对象存储治理在当前概述中未明确。

---

# 第七部分：跨层设计原则

## 28. 单一写真相

每个领域对象必须有唯一所有者：

- Work Item 状态由 Work Item 域拥有；
- Node Execution 状态由 Runtime 拥有；
- Approval 状态由 Approval 域拥有；
- Task Center 状态由投影域派生。

禁止两个模块同时维护同一业务状态。

---

## 29. 命令负责修改，事件负责传播

命令：

- 带有明确意图；
- 需要权限和状态校验；
- 修改领域对象。

事件：

- 描述已经发生的事实；
- 用于投影、通知、自动化和跨模块衔接。

事件不能替代业务命令。

---

## 30. 模块化单体优先

对于 200 人以内系统，不建议微服务化。

目标是：

- 单部署单元；
- 单 PostgreSQL；
- 清晰模块边界；
- 明确 Repository 所有权；
- 应用协调器；
- 事件驱动投影；
- Worker 处理异步任务。

只有在组织规模、独立扩容或部署隔离真正出现时再拆服务。

---

## 31. 不开放任意脚本

条件、自动化和节点配置应使用受控 DSL 或 JSON Schema。

不允许用户执行：

- 任意 JavaScript；
- 任意 SQL；
- 任意服务器代码。

---

## 32. 所有发布定义必须可重放和解释

系统必须能够回答：

- 为什么某节点被激活；
- 为什么某条边被选中；
- Join 正在等待哪些 Token；
- 哪个 Work Item 对应哪个节点；
- 哪次返工使旧结果失效；
- 哪个命令修改了 Context；
- 哪个事件更新了投影。

---

# 第八部分：建议升级路线

## 33. 阶段一：结构收敛

目标：停止架构继续恶化，不增加新的特殊同步逻辑。

实施：

1. 明确六大模块；
2. 建立模块目录和依赖规则；
3. Definition / Version 显式化；
4. 发布版本完全不可变；
5. 建立 workflow_human_task_links；
6. 停止通过 JSON 维护关键关系；
7. 禁止 TaskService 直接修改 NodeInstance；
8. 禁止 Runtime 直接修改 Task；
9. 建立 HumanTaskCoordinator；
10. 后端真正执行 Capability Policy；
11. 将 ROOT Task 明确标记为 process_run_shell；
12. current_node_key 降级为展示字段。

完成标准：

- Work Item 与 NodeExecution 写入口分离；
- 发布版本无法被修改；
- 所有关键跨域关系有正式 Link；
- 实验能力在服务端可真正关闭。

---

## 34. 阶段二：运行时正确性

目标：保证 DAG 在并发、条件分支、Join 和返工下正确。

实施：

1. 引入 Execution Token 或 Activation Dependency；
2. 明确 exclusive / inclusive / parallel / first_match；
3. Join 只等待实际激活分支；
4. 引入显式 Start / End；
5. 增加 completion policy；
6. 增加 failed / suspended / skipped；
7. Context 改为版本化 Patch；
8. Wait-Any 增加取消策略；
9. Deep Reject 增加后代失效；
10. 增加 NodeExecutionAttempt；
11. 增加 no-route 和 deadlock 诊断；
12. 所有关键命令增加幂等。

完成标准：

- 并发上游不会重复激活下游；
- Join 不会等待未激活分支；
- 无路由不会被误判完成；
- 旧 iteration 不能继续推进；
- 技术失败可重试和恢复。

---

## 35. 阶段三：业务能力独立化

目标：让 Runtime 不理解审批、交付、视频和外部集成细节。

实施：

1. Node Handler Registry；
2. HumanTask Handler；
3. ApprovalRequest / Decision；
4. DeliverableSubmission / Review；
5. Notification Capability；
6. Timer Handler；
7. Webhook Handler；
8. Signal Handler；
9. Subprocess Handler；
10. 视频业务扩展化；
11. Capability Result 统一；
12. cancellation / compensation 声明。

完成标准：

- Runtime 只处理节点状态和执行路径；
- 每种能力有独立数据模型；
- 视频业务不再通过 Runtime 特殊判断；
- 审批和交付历史可独立审计。

---

## 36. 阶段四：投影和查询重构

目标：替代动态 graph-first 拼装。

实施：

1. 建立 task_center_items；
2. 建立 process_run_summaries；
3. 建立 node_timeline_entries；
4. 建立 projector checkpoint；
5. 支持单对象和单流程投影重建；
6. 事件驱动更新；
7. 新旧投影 shadow comparison；
8. ROOT Task 改为 process_run 投影；
9. 建立工作负载和流程指标；
10. 逐步移除 graph-first 动态查询。

完成标准：

- Task Center 查询不再读取 Runtime 内部表进行动态拼装；
- 投影失败不影响业务事务；
- 所有投影可重建；
- 节点时间线统一展示。

---

## 37. 阶段五：基础设施和运维完善

目标：使系统可长期可靠运行。

实施：

1. Unit of Work；
2. 统一 Event Envelope；
3. Command Receipt；
4. Consumer Deduplication；
5. Outbox Dead Letter；
6. 人工重放；
7. Scheduler / Timer 统一基础设施；
8. 结构化日志；
9. Metrics；
10. Trace；
11. 流程异常工作台；
12. Integration Gateway；
13. 对象存储治理；
14. 备份恢复演练。

完成标准：

- 任意业务命令可追踪；
- 任意 Outbox 消息可重放；
- 任意投影可重建；
- 卡死流程可诊断；
- 外部调用可幂等重试；
- 数据库和附件可恢复。

---

# 第九部分：优先级建议

## 38. P0：立即处理

1. 后端 Capability Policy；
2. 发布版本完全不可变；
3. Work Item 与 NodeInstance 双主写收口；
4. 正式 Link 表；
5. 无活跃节点不等于完成；
6. Join 条件分支语义验证；
7. 创建 Run、完成节点、Deep Reject 幂等；
8. 禁止旧 iteration 迟到提交。

## 39. P1：核心正确性

1. Execution Token；
2. Context Patch；
3. failed / suspended；
4. Wait-Any 取消策略；
5. Deep Reject 后代失效；
6. NodeExecutionAttempt；
7. 明确 Start / End；
8. 统一命令与事件信封。

## 40. P2：领域独立化

1. Approval；
2. Deliverable 多版本；
3. Handler Registry；
4. Notification；
5. Timer；
6. Webhook；
7. Subprocess；
8. 视频扩展化。

## 41. P3：查询与运维

1. task_center_items；
2. 节点统一时间线；
3. 投影重建；
4. Dead Letter；
5. Runtime 操作控制台；
6. Metrics 和 Trace；
7. Legacy 清理。

---

# 第十部分：升级后的目标状态

完成上述升级后，系统应具备以下清晰边界：

```text
Work Item
负责一件具体人工工作的生命周期

Workflow Definition
负责静态流程蓝图和不可变版本

Workflow Runtime
负责实例、节点、Token、Context 和执行路径

Business Capabilities
负责审批、交付、通知、Timer、Webhook、子流程等具体能力

Projection & Query
负责任务中心、流程追踪、时间线和统计

Infrastructure
负责事务、持久化、事件、调度、幂等、监控和外部集成
```

最终应能够通过以下问题验证边界：

- 删除 Workflow Runtime 后，独立任务是否仍可运行？
- 删除 Work Item 后，Runtime 是否仍能执行纯系统流程？
- Runtime 是否不需要理解审批人数和交付版本？
- Task Center 是否可以通过重建投影恢复？
- 发布流程版本是否完全不可修改？
- 任何节点激活是否都有可解释原因？
- 任何业务命令是否都有幂等和审计记录？
- 任何失败流程是否都可暂停、诊断和恢复？

如果这些问题的答案均为“是”，说明系统已经从一个强耦合图任务引擎，演进为边界清晰、可靠且可扩展的工作流平台。

---

## 42. 结论

当前图引擎的基础是可靠且有价值的，不建议推倒重写。

应保留：

- 模板、实例、节点实例；
- 条件边；
- fan-out / join；
- iteration；
- Outbox；
- Run Event；
- Schedule；
- Task Center 现有用户体验；
- 视频流程已积累的业务能力。

升级工作的核心是重新定义所有权和边界：

1. Work Item 与 NodeExecution 不再互为镜像；
2. Definition Version 发布后完全不可变；
3. Runtime 只负责执行控制；
4. 审批、交付、通知和视频成为独立能力；
5. Task Center 成为正式读取投影；
6. 基础设施提供统一事务、幂等、消息和可观测性。

推荐先完成结构收敛与运行时正确性，再增加新节点类型和业务流程。否则每增加一种能力，都会继续扩大双写、隐式状态和特殊分支的维护成本。
