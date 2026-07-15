---
type: paradigma-plan
title: 工作流图引擎 Iteration 3 实施计划
description: "HumanTask Link、Work Item/Runtime 写所有权、standalone Task、命令幂等、事件信封与 Outbox 去重。"
tags:
  - plan
  - workflow-graph
  - iteration-3
  - human-task
  - idempotency
timestamp: 2026-07-15T20:38:43+08:00
paradigma:
  schema_version: 0.5.0
  temperature: hot
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Iteration 3, HumanTask Link, 写所有权, command receipt, standalone task]
    en: [iteration 3, human task link, command receipt, write ownership]
---
# 工作流图引擎 Iteration 3 实施计划

> **状态**：2026-07-15 已完成 I3-A 基座并启动 I3-B 的新写双写/Link-first；Iteration 2 已由用户验收并提交为 `853fca1`。本迭代采用 expand → dual-write/backfill → Link-first → ownership cutover 的顺序，不在同一批次删除 JSON 兼容锚点。

## 1. 目标与不变量

Iteration 3 把 `Task`（Work Item）与 `WorkflowNodeInstance`（Node Execution）从双主写收敛为各自拥有状态、由应用层协调：

- `tasks` 与 `/tasks` API 保留；普通任务最终默认 standalone，不再隐式创建单节点 Run。
- HumanTask 与 Work Item 的业务关系由 `workflow_human_task_links` 持久化；一个 Node 可关联一个 primary 与多个 supporting/observer Work Item，一个 Work Item 只属于一个 Node。
- Runtime 只直接修改 Run/Node/Traversal/Dependency；TaskService 只直接修改 Task/Deliverable/Watcher/Log。
- 跨边界推进由 `HumanTaskCoordinator` 转译 capability result 与 runtime command。
- 外部可重放命令以 `(actor_key, command_type, command_id)` 唯一；payload 使用 canonical JSON SHA-256 判同。
- 同一 command + 同一 payload 返回首次结果；同一 command + 不同 payload 返回 409。
- 存量 `graph-v2`/`graph-v3` Run 与旧手动单节点 Run 不原地转换执行语义。

## 2. 分批实施

### I3-A · Expand-only 基座（完成）

- [x] 新增 `workflow_human_task_links` 与 FK、生命周期、角色、primary 唯一约束。
- [x] 新增 `workflow_command_receipts` 与 actor/type/id 唯一约束、payload hash、首次结果槽位。
- [x] 建立 `HumanTaskCoordinator` 的 Link ensure/resolve/backfill-report 基座。
- [x] 建立 `WorkflowCommandReceiptService` 的 claim/replay/complete/fail 基座。
- [x] 单元测试、Alembic head↔base、PostgreSQL 约束验证。

本批不改 API 行为、不切换普通任务默认路径、不停止 JSON 写入。

### I3-B · 双写、回填与 Link-first

- [x] Runtime 新激活 HumanTask 时创建 Task + Link，并继续写 `Task.metadata` / `Node.config.task_id`。
- [x] 新建旧手动图任务时补 `source=manual_compat` Link。
- 回填器交叉校验 Task metadata、Node config、Instance source；异常只报告，不猜测修复。
- [x] Task 图投影读侧 Link-first、JSON fallback；fallback 记录结构化日志。
- [ ] 对存量数据执行 dry-run 报告、人工处置歧义后正式回填，并建立 fallback 命中率聚合指标。
- 完成、取消、Deep-Reject 时同步 Link lifecycle，不删除历史 Link。

### I3-C · 写所有权与 standalone Task

- `HumanTaskCoordinator` 成为唯一跨域协调入口。
- Task 完成产生 capability result，由 Coordinator 调 Runtime command；TaskService 不再直接写 Node。
- Runtime 激活/接管/撤权产生协调命令；Runtime service 不再直接写 Task。
- `WORKFLOW_STANDALONE_MANUAL_TASKS_ENABLED` 独立开关先灰度、后默认开启；已创建的 standalone Task 不因回滚开关被删除。

### I3-D · 命令与事件幂等

- command receipt 覆盖 create run、complete node、deep reject、takeover、schedule run-now。
- 事件补齐 event/aggregate version、command、causation、correlation、actor、occurred_at。
- API 接收稳定 command id；未提供时由边界层生成，但客户端重试只有复用 id 才获得幂等保证。

### I3-E · Outbox 去重与收口

- Outbox 以 event id 建立消费去重账本。
- 去除 `NotificationService.send()` 内部 commit 与 Outbox 状态提交之间的重复窗口。
- 演练通知已发送但 worker 崩溃、重复 worker、重试耗尽和恢复。
- fallback 长期为零且恢复演练通过后，才停止新写 JSON；删除兼容字段属于后续独立 contract 阶段。

## 3. 迁移与回滚边界

- `20260715_02` 只建表与约束，不对存量 JSON 做不可逆 SQL 猜测回填。
- I3-B 回填器默认 dry-run；报告无歧义项后再在同一事务写 Link。
- 代码回滚时保留 Link/receipt 表；数据库 downgrade 只用于发布前迁移演练。
- standalone 开关回滚只影响新建路径，既有 standalone Work Item 继续按 Task 状态机运行。

## 4. 验收矩阵

- Link：FK、一个 Task 仅一个 Node、一个 Node 仅一个 active primary、supporting 可多条、lifecycle 保留历史。
- Backfill：三锚点一致才写；UUID 无效、Node 缺失、Instance 不匹配、Node config 不匹配均进入报告。
- Receipt：同 payload 重放、异 payload冲突、并发 claim 单记录、首次成功/失败结果稳定返回。
- Ownership：源码扫描与测试证明 TaskService/Runtime 不再跨域直接赋值。
- Standalone：创建、接单、流转、交付/验收、归档不依赖 Run。
- Outbox：相同 event id 只产生一次通知副作用。

## 5. 停止条件

- 无法在不猜测的情况下将存量 Task 唯一关联到 Node；
- Coordinator 接入需要破坏现有 `/tasks` 返回结构；
- command receipt 与业务事务不能保持同一提交边界；
- PostgreSQL 并发下仍可产生双 primary Link 或重复命令副作用。

触发时保持 dual-write/旧路径，不提前删除兼容锚点，并把证据登记为 `I3-GAP-*`。
