---
type: paradigma-plan
title: "Iteration 5-B 投影消费与重建基座计划"
description: "基于现有持久化运行事件、任务留痕与评论流，建立独立 checkpoint、幂等 projector 和单对象/单 Run/全量重建能力。"
tags: [plan, active, workflow-graph, iteration-5, projection, projector, rebuild]
timestamp: 2026-08-12T12:05:50+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: hot
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Iteration 5-B, 投影消费, checkpoint, 幂等重建, projector]
    en: [Iteration 5-B, projection consumer, checkpoint, idempotent rebuild, projector]
  relations:
    depends_on:
      - ./2026-08-12-iteration5a-projection-contract-plan.md
      - ../contracts/projection-contract.md
    related_to:
      - ../contracts/database/graph-engine-schema.md
      - ../domains/workflow-graph-engine.md
      - ../domains/task-center.md
---

# Iteration 5-B 投影消费与重建基座计划

> **计划状态：ENGINEERING COMPLETE / POSTGRES EVIDENCE PENDING** — checkpoint、projector、三种重建、显式 CLI 和独立 ARQ 消费均已完成；SQLite 迁移与 479 项后端回归通过。未切换 Task Center 读路径；`20260812_01/02` 的真实 PostgreSQL head↔base 证据继续作为 5-E 切流前门禁并行补齐。

## 1. 目标边界

- 复用已经随业务事务落库的 `workflow_run_events`、`task_logs`、`task_comments`，不新建第二条业务事件总线。
- 为三个源流分别维护稳定的 `(occurred_at, source_id)` checkpoint；一个源流的迟滞或失败不覆盖另一个源流的进度。
- 由 Projection 服务独占创建、更新和清空 `TaskCenterItem`、`ProcessRunSummary`、`NodeTimelineEntry` 与 checkpoint。
- 提供单 Task、单 Run 和全量重建；重复消费、重复重建不制造重复行，较旧来源修订不得覆盖较新结果。
- Projector 在业务命令提交后运行。投影失败只能记录失败和等待重试，不得回滚或伪装业务命令已经失败。

## 2. 消费与事务语义

1. **源流**：Run Event、Task Log、Task Comment 各自按业务时间和 UUID 稳定排序；仅消费 checkpoint 之后的数据。
2. **独占进度**：消费事务锁定对应 checkpoint；同一 projection/stream 同时只有一个消费者推进，成功提交才移动游标。
3. **失败隔离**：批次内异常回滚该批投影和 checkpoint；随后用独立事务写入 `failed`、错误摘要和尝试次数。原业务表不被修改。
4. **幂等写入**：任务项按 canonical subject、Run 摘要按 run id、时间线按 source type + source id upsert；相同或更旧修订默认不覆盖，显式 rebuild 可强制刷新派生文案与 audience。
5. **安全边界**：投影 audience 只是候选集合，禁止把 actor-specific `available_actions` 或最终放行结论持久化；对象读取仍由现有 Task/Workflow 策略授权。

## 3. 投影范围

- **TaskCenterItem**：独立任务投影为 `standalone`；图节点工作项投影为 `human_task` 或 `approval`；Run root shell 投影为 `process_run`。状态同时保留 raw、engine、business 与 user-facing 四层语义。
- **ProcessRunSummary**：从 Run、Node、正式 Link 与 Run Event 聚合阶段、进度、阻塞、完成时间和候选 audience。
- **NodeTimelineEntry**：Run Event、Task Log、Task Comment 只投影索引与安全摘要；评论正文、附件、交付与审批事实仍由原业务表拥有。

## 4. 重建语义

- **单 Task**：重建任务中心项和该任务的 Log/Comment 时间线；若存在正式 HumanTask Link，同时刷新所属 Run 摘要。
- **单 Run**：重建 Run 摘要、Run Event 时间线，以及该 Run 的 root/linked Task 投影与任务时间线。
- **全量**：事务开始时捕获三个源流的高水位；清空读模型后从当前写模型重建，完成后将 checkpoint 定位到捕获的高水位。高水位之后的新事件留给增量消费者，避免重建窗口丢事件。
- 全量重建失败整体回滚，不留下“半张新表 + 已推进游标”的状态。

## 5. 实施顺序与测试先行

1. 新增 `projection_checkpoints` 模型与 `20260812_02` Expand-only 迁移，补约束、索引、owner guard 和迁移回滚测试。
2. 先写 projector/rebuild 失败测试，覆盖重复运行、稳定游标、旧修订保护、失败不影响源事实和全量重建高水位。
3. 实现 `WorkflowProjectionService` 与 `WorkflowProjectionRebuildService`；当前阶段允许复用 `TaskService` 已验证的图工作项动态派生逻辑作为过渡适配器。
4. 增加 ARQ 周期任务，只调度投影消费，不与通知 Outbox 状态共用 checkpoint 或重试状态。
5. 完成定向和全量回归，更新契约、任务状态和计划目录，形成独立提交。

## 6. 非目标与完成门禁

- 不把现有 `/tasks`、Run 详情或活动时间线读路径切到投影表；shadow comparison 属于 5-C。
- 不删除 ROOT Task、JSON anchor、Link-first fallback 或任何兼容写路径。
- 不把通知 Outbox 改造成通用事件总线，也不让通知投递状态决定投影进度。
- 完成标准：迁移可加可撤；三个源流可增量推进和安全重试；三种重建入口幂等；Projection 写 owner guard 通过；现有功能和全量测试无回归。

## 7. 当前验证结果

- 新增 `projection_checkpoints` 和 `20260812_02`；时间+UUID cursor 成对、projection+stream 唯一、状态/计数约束及索引通过模型与 SQLite expand/downgrade 测试。
- 三源流增量消费、单 Task/单 Run/全量高水位重建、重复运行无重复、旧 revision 拒绝覆盖及显式 rebuild 强制刷新均有自动化覆盖。
- 模拟 Task Log 投影失败时，原始 Log 保持不变、该流登记 `failed`，Run Event 与 Comment 流继续推进；证明失败不反向影响业务事实或其他源流。
- ARQ 已注册独立 `process_workflow_projection_events_job`，与通知 Outbox 分开调度、checkpoint 和重试状态。
- Alembic 单 head `20260812_02`；PostgreSQL 增量离线 SQL、`compileall`、定向 18 tests 与后端全量 479 collected / 447 passed / 32 skipped / 0 failed 通过。
- 真实 PostgreSQL head↔base 仍因本机无 Docker/PostgreSQL 待目标环境补证；该证据阻止 5-E，不阻止 5-C shadow comparison 开发。
