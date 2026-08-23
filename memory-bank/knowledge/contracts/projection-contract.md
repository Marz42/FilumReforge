---
type: paradigma-contract
title: "Iteration 5 投影与查询契约"
description: "三类投影及 projection_checkpoints 的字段来源、身份、授权、排序、所有权、消费与重建边界。"
tags: [contract, projection, task-center, workflow-graph, iteration-5]
timestamp: 2026-08-23T22:55:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: hot
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  contract_kind: data
  retrieval_hints:
    zh: [投影契约, task_center_items, Run 摘要, 节点时间线, 投影授权]
    en: [projection contract, task center items, run summaries, node timeline, projection authorization]
  relations:
    depends_on:
      - ./data-contracts.md
      - ./database/graph-engine-schema.md
    related_to:
      - ../plans/2026-08-12-iteration5a-projection-contract-plan.md
      - ../plans/2026-08-12-iteration5b-projector-rebuild-plan.md
      - ../domains/task-center.md
      - ../domains/workflow-graph-engine.md
---

# Iteration 5 投影与查询契约

> **实现阶段：Iteration 5-E ENGINEERING COMPLETE / PRODUCTION CUTOVER GATED**。任务中心已支持持久投影优先读取、缺失投影动态回退和严格投影 canary；2026-08-23 隔离 PostgreSQL/Redis 上完成 rebuild、full shadow 与严格模式真实多账号 UAT。生产切流仍须真实预发观察、I3-F 连续门禁和发布负责人批准。

## 1. 通用不变量

- Projection 模块是唯一写 owner；Task、Workflow Runtime、API route 和前端不得直接创建或修改投影行。
- 业务命令先提交写模型与事件；投影失败或延迟不得回滚业务命令。
- 每行携带 `projection_schema_version`、`source_revision`、`last_event_id`（可空）与 `projected_at`；重复或旧 revision 不得覆盖更新的数据。
- JSON audience/payload 只用于候选筛选和展示缓存；最终对象授权必须复用现有 Task/Workflow policy，不得凭投影 UUID 直接放行。
- 所有列表/时间线顺序均以业务时间 + UUID 作为最终 tiebreaker；重建后必须保持确定顺序。
- 删除投影不级联删除业务对象；删除业务 Task/Run 可以清理对应投影。可空的用户、部门、节点引用采用 `SET NULL`，保留历史摘要。

## 2. 字段来源矩阵

| 投影 | 输出字段组 | 权威来源 | 说明 |
|---|---|---|---|
| `task_center_items` | 标题、优先级、截止/完成/创建时间 | `tasks`；Run shell 来自 `workflow_graph_instances`/模板快照 | 展示缓存，不替代源对象 |
| `task_center_items` | raw status、engine/business state、阶段、当前处理人 | `tasks` + `workflow_node_instances` + `workflow_graph_instances` + `workflow_human_task_links` | 替代当前 `_graph_task_projection_map` 动态拼装 |
| `task_center_items` | 交付时间、返工次数、质量分 | `workflow_deliverables.payload`；兼容期可回退 Task metadata | 5-C 必须记录 fallback 来源差异 |
| `task_center_items` | audience 候选 | creator/assignee/reviewer/watcher、Run initiator/participant/event actor、部门 | 仅候选；最终走 policy |
| `process_run_summaries` | Run 状态、result、当前节点、父子关系 | `workflow_graph_instances` | Run 身份以 `process_run_id` 唯一 |
| `process_run_summaries` | total/completed/active/pending/blocked/progress | `workflow_node_instances` | 终态包含 completed/skipped/terminated；算法版本随 schema version 固定 |
| `process_run_summaries` | audience 候选 | initiator、节点执行人、历史 actor、正式 watcher、部门管理范围 | 最终读取仍走 `WorkflowAccessPolicy` |
| `node_timeline_entries` | Node/Run 事件 | `workflow_run_events` | source identity = `workflow_run_event` + event UUID |
| `node_timeline_entries` | Task 日志/评论 | `task_logs` / `task_comments` | 正文和附件仍归源表；投影只存摘要与引用 |
| `node_timeline_entries` | 交付/审批/返工/接管 | deliverable payload、approval event、task log/run event | 同一源事实只投影一次 |

## 3. `task_center_items`

**身份**：唯一 `(subject_type, subject_id)`；`subject_type ∈ {work_item, process_run, system_alert}`。`item_kind ∈ {standalone, human_task, approval, process_run, system_alert}`。work item 必须关联 `task_id`，process run 必须关联 `process_run_id`。

**持久字段组**：

- 引用：`task_id`、`process_run_id`、`node_instance_id`；
- 展示：`title`、`priority`、`raw_status`、`engine_state`、`business_state`、`user_facing_state`、`current_stage_label`、`current_handler_label`、`run_label`；
- 责任：`creator_user_id`、`assignee_user_id`、`current_action_owner_user_id`、`department_id`；
- 动作提示：`execution_mode`、`assignment_mode`、`requires_action`、`action_type`；具体 `available_actions` 继续由请求 actor 的 policy 计算，不持久化为全局真相；
- 跟踪指标：`latest_deliverable_submitted_at`、`rework_count`、`review_quality_score`；
- 时间与状态：`source_created_at`、`source_updated_at`、`due_at`、`completed_at`、`is_archived`、`hidden_for_non_management`；
- 候选范围：`audience_user_ids`、`audience_department_ids` JSON 数组。

**索引顺序**：action owner/status/due、department/status/due、process run、history completed/id。Inbox 沿用“有截止时间优先 → 截止时间 → 优先级 → 创建时间倒序 → UUID”；Tracking 沿用 status/due/priority/UUID；History 使用 completed time + UUID 倒序。

## 4. `process_run_summaries`

**身份**：`process_run_id` 唯一并关联 `workflow_graph_instances.id`。

**持久字段组**：template/parent/source/department/initiator 引用，`run_label`，engine `status`/`result`，`current_node_key`/`current_stage_label`，节点五类计数与 `progress_percent`，`started_at`/`completed_at`/`latest_event_at`，audience JSON 数组及通用投影元数据。

**计数约束**：所有 count 非负，`progress_percent` 为 0～100；completed 计数包括 `completed/skipped/terminated`，blocked 仅表示需要人工/运维处理的业务或引擎阻塞，不把普通 pending 算作 blocked。

## 5. `node_timeline_entries`

**身份**：唯一 `(source_type, source_id)`；`entry_type ∈ {node_event, work_item_activity, comment, deliverable, approval, rework, takeover, system}`。

**持久字段组**：Run/Node/Task 引用，source/event/actor，`visibility ∈ {public, internal, management}`，`title`、`summary`、非权威 `payload`，`occurred_at` 及通用投影元数据。评论正文、附件、完整交付和审批记录仍从源对象读取。

**顺序与过滤**：Run 时间线按 `occurred_at, id`；Task 时间线同样按 `occurred_at, id`。读取前先授权 Task/Run，再过滤 internal/management；非管理角色不得因投影存在而看到内部备注。

## 6. 授权契约

| 读取对象 | 候选筛选 | 最终授权 |
|---|---|---|
| Task Center work item | action owner、creator、assignee、reviewer、watcher、部门 audience | 现有 `TaskService` 可见性/动作 policy |
| Process Run summary | initiator、participant、historical actor、watcher、部门 audience | `WorkflowAccessPolicy.ensure_can_read_instance` |
| Node timeline | 父 Task/Run audience | 先授权父对象，再按 `visibility` 过滤 |
| 管理视角 | 管理部门/全局管理候选 | 延续现有 `MANAGEMENT_ROLES` 与部门授权；KI-011 未决边界不在投影层扩大 |

投影 API 不允许接收任意 UUID 后直接 `session.get(projection)` 返回；必须先解析 canonical subject 并执行对象级 policy，未授权继续使用 404 隐藏存在性。

## 7. 版本与重建

- 初始 `projection_schema_version = 1`，`source_revision >= 0`；无显式 revision 的源事实由 projector 生成确定性 revision，但不得使用处理时间覆盖事件顺序。
- `last_event_id` 是幂等/诊断锚点，不建立跨多种事件表的 FK。
- 5-B rebuild 已支持单 Task、单 Run 和全量三种范围；单对象先清理对应时间线再幂等重投，全量在同一事务清空/重投，不修改源业务表。
- 全量重建开始时分别捕获 Run Event、Task Log、Task Comment 的高水位，成功后 checkpoint 定位到该高水位；之后到达的数据由增量消费补齐，重建窗口不丢事件。
- schema 升级采用 expand → projector/shadow/operations → cutover → contract；`20260812_01` 新增三类读模型，`20260812_02` 新增 checkpoint，`20260812_03` 新增 shadow observation 并将微秒 revision/累计计数提升为 `BIGINT`，`20260812_04` 增加 Outbox/incident 运维审计和 Run Event trace 标识。downgrade 不触碰业务源表；`03` 降级会清空可重建投影行后恢复旧整数类型。

## 8. Checkpoint 与消费实现

- `projection_checkpoints` 以 `(projection_name, stream_name)` 唯一；cursor 必须同时具有 `cursor_occurred_at` 与 `cursor_source_id`，状态为 `idle/running/failed`，并记录累计处理量、尝试次数、最近成功时间和错误摘要。
- 当前 projection 名为 `workflow_query_v1`；三个独立源流为 `workflow_run_events`、`task_logs`、`task_comments`，均按来源业务时间 + UUID 稳定推进。
- `WorkflowProjectionService` 和 `WorkflowProjectionRebuildService` 是唯一写 owner，均为 flush-only；ARQ 的 `process_workflow_projection_events_job` 每 30 秒在独立事务中逐流消费。
- 某一源流失败时只回滚该流当批投影/checkpoint，并在新事务记录 `failed`；其他流继续推进。原 Task、Run、Log、Comment 与 Run Event 不被 projector 修改。
- 5-B 暂时复用 `TaskService` 已验证的动态图任务派生逻辑作为过渡适配器；5-C 已实现独立源事实快照与投影快照比较，但只有目标环境持续样本达到门禁且 5-E 单独获批后，才允许读侧替换或进一步解耦。

## 9. Shadow Comparison 实现

- `projection_shadow_observations` 以 scan+comparison+subject 唯一，保存 match/difference/lagging/missing/orphan、严重级别、差异字段名、双方 SHA-256 指纹、revision 与 lag；不保存字段值、正文、邮箱、附件或业务 payload。
- Task Center 对照 work item 与 Run shell，Run summary 对照现行动态计数，Timeline 对照三类源事实的身份/父对象/actor/visibility/事件语义；最终授权仍不在 shadow 层判定。
- 周期 worker 每 5 分钟 recent 抽样，60 秒为默认 lag 容忍；观察证据保留 30 天。全量审计必须显式运行 `python -m app.scripts.scan_workflow_projection_shadow --full`。
- 5-C 已把 Run progress 固定为与现行详情 API 一致的整数向下取整；确定性差异必须修 projector/契约，不得通过忽略字段消音。

## 10. Iteration 5-E 读取与回退契约

- `TASK_CENTER_PROJECTION_READS_ENABLED=true` 时，graph-backed Task Center 条目先读取 `task_center_items`；关闭时保留原动态 graph-first 路径，作为紧急回滚开关。
- `TASK_CENTER_PROJECTION_FALLBACK_ENABLED=true` 时，缺失、未知 schema 或非法状态的条目按单 Task 动态派生并补入本次响应；不会写回投影，也不会改变业务源数据。
- 严格 canary 使用 `PROJECTION_READS=true`、`FALLBACK=false`。进入该模式前必须先全量 rebuild，再执行 full shadow；严格模式出现缺失时不得伪装为 legacy 条目，应回开 fallback 并重建/排障。
- 投影只缓存 title/priority/due/status/stage/handler/run label/user-facing state 等展示字段；`available_actions` 仍由请求 actor 的实时 policy 计算，不能从投影缓存恢复权限。
- `process_run` 投影状态映射固定为：active/pending → DOING，completed/cancelled → DONE，failed/terminated → BLOCKED。未知值视为不可用投影并进入回退或严格缺失处理。

### 2026-08-23 本地生产方言证据

- PostgreSQL marker：22 passed，严格要求目标数据库测试不允许 skip。
- 最终 rebuild：97 Task、28 Run、282 Timeline。
- full shadow：407 compared / 407 matched；difference、missing、orphan、lagging 均为 0，scan `0d490838-580a-411b-b2b1-bbef0aa8a664`。
- fallback 开启完成真实后端 Chromium UAT 8/8；严格模式完成核心/工作流 8/8 + KI-009 standalone 三身份 1/1。覆盖新建 standalone、创建/执行/验收授权、批次实例化、三账号采集、fork、交付和独立 N4 审核。
- 以上为隔离本机证据，不替代生产连续观察与人工批准。
