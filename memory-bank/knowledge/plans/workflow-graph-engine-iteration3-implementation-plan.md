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
timestamp: 2026-07-16T20:37:13+08:00
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

> **状态**：2026-07-15 已完成并提交 I3-A–E 代码实施；I3-A 基座提交为 `79b8c42`，B–E 提交为 `27c9cb3`。2026-07-16 复核确认现有所有权测试、Link 生命周期、故障注入和观测尚不足以进入 Iteration 4，现由强制 [`Iteration 3-F`](./workflow-graph-engine-iteration3f-readiness-gate-plan.md) 收口。

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
- [x] 回填器交叉校验 Task metadata、Node config、Instance source；默认 dry-run，异常只报告，不猜测修复。
- [x] Task 图投影读侧 Link-first、JSON fallback；fallback 记录结构化日志。
- [x] Link-first/JSON fallback 记录进程内聚合计数，供观测接入；生产存量 dry-run、人工处置与正式回填待部署执行。
- [x] 完成、取消、Deep-Reject 时同步 Link lifecycle，不删除历史 Link。

### I3-C · 写所有权与 standalone Task

- [x] `HumanTaskCoordinator` 承接 Task 状态/握手与 Runtime 状态、接管、review/aggregate 等跨域同步。
- [x] TaskService 不再直接修改既有 NodeInstance；Runtime 的 Task 更新通过 Coordinator。
- [x] `WORKFLOW_STANDALONE_MANUAL_TASKS_ENABLED` 独立开关默认开启；关闭时仅让新任务回到兼容图路径，既有 standalone Task 不受影响。
- [x] Standalone Task 支持接受、Todo → Doing → Review → Done、交付/验收，不依赖 Run。

### I3-D · 命令与事件幂等

- [x] command receipt 覆盖 create run、complete node、deep reject、takeover、schedule run-now。
- [x] 事件补齐 event/aggregate version、command、causation、correlation、actor、occurred_at（迁移 `20260715_03`）。
- [x] API 接收/回显 `X-Command-ID`；未提供时由边界层生成，客户端重试须复用 id。

### I3-E · Outbox 去重与收口

- [x] Outbox event id 映射为 `notification_messages.deduplication_key` 唯一键。
- [x] Worker 在通知持久化提交中同时写 processing visibility lease；若仍落入崩溃窗口，重试复用同一 message/delivery identity，队列下游可按 delivery id 幂等。
- [x] 自动化演练上述崩溃窗口及既有重试耗尽路径。
- fallback 长期为零且恢复演练通过后，才停止新写 JSON；删除兼容字段属于后续独立 contract 阶段。

### I3-F · Iteration 4 硬性准入收口（已设计，待实施）

- [ ] 两个领域独占写端口；Coordinator 不直接写 Task/Node ORM。
- [ ] 全仓库 AST 所有权/commit 架构守卫替代局部源码扫描。
- [ ] Link iteration/superseded、持久异常队列和生产回填闭环。
- [ ] PostgreSQL 事务故障注入与五类命令副作用级幂等测试。
- [ ] standalone/legacy/Notice/executor/无损回滚兼容矩阵。
- [ ] Admin readiness 查询、CLI verifier、连续 7 天 Link 覆盖和零 fallback。
- [ ] 31 项最终准入报告经用户批准。

I3-F 未完成前，I3 A–E 的“自动化通过”只证明已实现能力，不代表 Iteration 4 准入。

### 自动化证据（2026-07-15）

- Backend 非 PostgreSQL 全量：PASS（仅跳过已登记 PostgreSQL用例）。
- PostgreSQL 强制执行：13/13 PASS，含 Alembic head↔base、并发 command 一次执行、Link primary 约束与图并发。
- API 命令重放、standalone 生命周期、事件信封、Outbox 稳定身份专项：PASS。
- 前端 `vue-tsc --build`：PASS。

## 3. 迁移与回滚边界

- `20260715_02` 只建表与约束，不对存量 JSON 做不可逆 SQL 猜测回填。
- I3-B 回填器默认 dry-run；报告无歧义项后再在同一事务写 Link。
- 代码回滚时保留 Link/receipt 表；数据库 downgrade 只用于发布前迁移演练。
- standalone 开关回滚只影响新建路径，既有 standalone Work Item 继续按 Task 状态机运行。

## 4. 验收矩阵

- Link：FK、一个 Task 仅一个 Node、一个 Node 仅一个 active primary、supporting 可多条、lifecycle 保留历史。
- Backfill：三锚点一致才写；UUID 无效、Node 缺失、Instance 不匹配、Node config 不匹配均进入报告。
- Receipt：同 payload 重放、异 payload冲突、并发 claim 单记录、首次成功/失败结果稳定返回。
- Ownership：当前局部源码扫描不足；由 I3-F 全仓库 AST guard 和两个独占写端口重新验收。
- Standalone：创建、接单、流转、交付/验收、归档不依赖 Run。
- Outbox：相同 event id 只产生一次通知副作用。

## 5. 停止条件

- 无法在不猜测的情况下将存量 Task 唯一关联到 Node；
- Coordinator 接入需要破坏现有 `/tasks` 返回结构；
- command receipt 与业务事务不能保持同一提交边界；
- PostgreSQL 并发下仍可产生双 primary Link 或重复命令副作用。
- 任一 Iteration 4 硬闸门只能标记 PARTIAL，或只能依赖进程内 Counter/人工说明。

触发时保持 dual-write/旧路径，不提前删除兼容锚点，并把证据登记为 `I3F-GAP-*`；Iteration 4 继续 blocked。
