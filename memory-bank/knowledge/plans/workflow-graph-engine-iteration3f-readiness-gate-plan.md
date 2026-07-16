---
type: paradigma-plan
title: 工作流图引擎 Iteration 3-F · Iteration 4 硬性准入实施计划
description: "在进入 Handler 化前，补齐写所有权、Link 生命周期、事务原子性、命令幂等、兼容回滚与可观测性硬闸门。"
tags:
  - plan
  - workflow-graph
  - iteration-3f
  - readiness-gate
  - ownership
  - observability
timestamp: 2026-07-16T20:37:13+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Iteration 3-F, Iteration 4 准入, 写所有权, Link superseded, 事务故障注入, 可观测性]
    en: [iteration 3f, iteration 4 gate, write ownership, link superseded, fault injection, observability]
---
# 工作流图引擎 Iteration 3-F · Iteration 4 硬性准入实施计划

> **状态**：方案已形成，尚未实施。Iteration 3 A–E 的代码与迁移保持现状；在本计划全部验收并经用户批准前，禁止启动 Iteration 4 Handler 化。
>
> **审查基线**：2026-07-16 对 31 项硬条件复核结果为 11 项通过、7 项部分具备、13 项未满足。本计划以“31/31 PASS、0 PARTIAL、0 FAIL”为唯一出口。

## 1. 目标与边界

Iteration 3-F 不是新的业务能力迭代，而是 Iteration 3 的强制收口批次。目标是把当前“设计上基本具备”的边界变成数据库约束、全仓库架构测试、PostgreSQL 故障证据和可查询运维事实。

本阶段必须保证：

- Work Item 只能由 Work Item 写端口直接修改；
- Node Execution / Run 只能由 Runtime 写端口直接修改；
- `HumanTaskCoordinator` 只编排两个写端口和同一 UoW，不直接赋值双方 ORM；
- HumanTask 的正式关系只以 Link 为真相，JSON 仅保留兼容 fallback；
- 关键命令的业务修改、Outbox 和成功 Receipt 同事务；
- 任一硬闸门都有自动化测试或可重复的生产查询证据。

本阶段不做：

- 不启动 Handler Registry、Approval Handler、Deliverable Handler 或视频 Handler 迁移；
- 不删除 Task / Node JSON 兼容字段，不删除 Legacy Run 或新表数据；
- 不改变现有 `/tasks` 响应结构，不把 `tasks` 物理改名；
- 不让在途 Run 切换 executor 或 engine version；
- 不以进程内 Counter、人工口头确认或 SQLite 并发结果作为准入证据。

## 2. 已固定的设计决策

### 2.1 写所有权

新增两个明确的内部写端口：

- `WorkItemWriteService`：唯一允许直接创建或修改 `Task`、交付物、Watcher 和 Task Log 的生产服务；
- `WorkflowRuntimeWriteService`：唯一允许直接创建或修改 Run、NodeInstance、Traversal、ActivationDependency 和 Runtime Event 的生产服务。

`TaskService` 和 `WorkflowGraphService` 的公共用例入口可暂时保留，但涉及写入时必须委托对应写端口。`HumanTaskCoordinator` 只能调用两个端口，不得出现 `task.status = ...`、`node.engine_state = ...`、ORM bulk update 或跨域构造器调用。

迁移脚本、Alembic 和测试 fixture 可列入显式例外；生产 `app/services/`、route、worker 不设模糊目录豁免。

### 2.2 Link iteration 与 superseded

`workflow_human_task_links` 扩展：

- `iteration INTEGER`：创建 Link 时复制 NodeInstance iteration，作为关系审计快照；
- `superseded_at TIMESTAMPTZ NULL`；
- `superseded_by_link_id UUID NULL`：自引用新 Link；
- lifecycle 增加 `superseded`。

约束：

- `iteration >= 1`；
- lifecycle 为 `superseded` 时，`superseded_at` 与 `superseded_by_link_id` 必须存在；
- Link 不得 supersede 自己；
- 继续保留 Task 唯一归属、Node+Task 唯一以及每个 Node 仅一个 active primary 的数据库约束。

Deep-Reject 或重新物化工作项时，旧 Link 保留且标记 superseded，新 iteration 创建新 Work Item + 新 Link；不得把旧 Task 直接移动到新 Node。

### 2.3 持久化异常与观测

新增 `workflow_operational_incidents`，作为低频异常和迁移队列，不代替 Runtime Event：

- category：`link_fallback`、`link_mismatch`、`link_backfill_issue`、`coordinator_failure`、`receipt_conflict`、`outbox_duplicate`、`migration_incomplete`；
- status：`open`、`resolved`、`ignored`；
- severity、fingerprint、occurrence_count、first_seen_at、last_seen_at、resolved_at；
- 可选 instance/node/task/receipt/outbox 外键、engine_version 与脱敏 details JSON；
- fingerprint 唯一，重复观测执行原子 upsert，不制造无限重复行。

异常记录失败不得覆盖原业务异常；Coordinator 回滚、Receipt 冲突和只读 fallback 通过独立、短事务写 incident，并同时保留结构化日志。每日 reconciliation 扫描用于弥补观测写失败和无流量窗口。

### 2.4 fallback 阈值

进入 Iteration 4 前必须同时满足：

- 新创建的 `graph-v3` HumanTask：Link 覆盖率 100%，JSON fallback 为 0；
- 所有 active Run 的可关联 HumanTask：每日 reconciliation 连续 7 天无缺失 Link；
- 全部运行时 Link 解析：连续 7 天 `link_fallback` 新增量为 0；
- open P0/P1 Link / migration incident 为 0；
- 无业务流量不能自动视为通过，必须执行全量 reconciliation 与合成 Link-first 解析。

JSON 兼容写入可保留到 Iteration 6；只要 Link 存在，即使 JSON 不一致也必须以 Link 为准并登记 `link_mismatch`。

## 3. 分批实施

### I3-F1 · 所有权端口与全仓库架构守卫

1. 新增 Work Item / Runtime 两个 flush-only 写端口；commit 只能出现在 API command UoW、worker lease UoW、受控脚本边界。
2. 重构已知越界写点：视频表单、视频返工、图编排、视频实例化、Task 的 Node config 修补等路径。
3. Coordinator 改为纯编排器：同一 Session 中按固定顺序调用端口，不直接操作双方 ORM。
4. 新增 AST 架构测试，扫描 `backend/app/**/*.py`：
   - 属性赋值、构造器、SQLAlchemy `update/delete`、bulk 操作和别名引用；
   - 禁止非 owner 写 Task / NodeExecution；
   - 禁止 owner 反向写另一领域；
   - 禁止 Coordinator 直接写两类 ORM；
   - 禁止命令调用链中出现未登记的内部 `commit()`。
5. allowlist 使用精确文件 + 精确操作，禁止仅按类名字符串或两个 Service 的局部正则扫描。

完成证据：`OWN-01`–`OWN-04` 全部自动化通过，已知跨域文件不再直接赋值。

### I3-F2 · Link 生命周期、异常队列与回填

按 Expand → Backfill → Contract 两个 Alembic revision 实施：

1. Expand revision：新增 Link iteration/superseded 字段和 `workflow_operational_incidents`，字段先 nullable，不改旧读路径。
2. 新建 HumanTask 的同一事务内创建正式 Link；Link 创建失败则 Task/Node 激活整体回滚。
3. 回填器升级为 checkpoint/batch 模式：
   - `--dry-run` 只输出，不写 Link 或 incident；
   - `--apply` 对确定项写 Link，对歧义项 upsert incident；
   - 重复执行不重复创建 Link 或 incident；
   - 输出扫描数、可回填数、异常数、fallback 潜在数与 checkpoint。
4. Deep-Reject、取消、重新物化同步 completed/invalidated/superseded 生命周期。
5. 所有解析入口统一调用 Coordinator resolver；Link 存在时禁止读取 JSON 决定关系。
6. Contract revision：全量扫描无阻塞异常后，把 Link iteration 收紧为 NOT NULL 并启用 superseded CHECK/FK。

完成证据：`LINK-01`–`LINK-06` 全部通过，生产 dry-run/apply 报告可重复且异常进入持久队列。

### I3-F3 · UoW 原子性与 PostgreSQL 故障注入

1. 统一人工任务完成链路：Receipt claim → Work Item 修改 → Runtime 推进 → Runtime Event/Outbox → Receipt success → 单次 commit。
2. 服务内部只允许 `flush()`；失败由命令边界统一 rollback。
3. 成功 Receipt 与业务结果同事务。业务失败 rollback 后可在独立诊断事务保存 failed receipt/incident，但不得留下部分业务结果。
4. PostgreSQL 故障注入点至少覆盖：
   - Work Item 已变更、Node 尚未推进；
   - Node 已推进、Outbox 尚未写；
   - Outbox 已写、Receipt 尚未完成；
   - Receipt 已完成、commit 抛错；
   - Deep-Reject clone 中途失败；
   - takeover 更新后、通知 Outbox 前失败。
5. 每个断点均使用新 Session 复查数据库，断言业务、Link、Event、Outbox、Receipt 要么全部可见，要么业务侧全部不可见。

完成证据：`TX-01`–`TX-04` 全部通过；SQLite 只跑规则测试，原子性以 PostgreSQL 为准。

### I3-F4 · 命令级幂等矩阵

对 create run、complete node、deep reject、takeover、schedule run-now 分别增加 API + PostgreSQL 测试：

- 同 actor/type/id + 同 payload：返回首次响应快照；
- 同 actor/type/id + 不同 payload：409，并登记 `receipt_conflict`；
- 两个独立 Session 并发首次执行：仅一个执行者，另一方等待并重放结果；
- create run 断言 Run/Node/Link 数量不增加；
- complete 断言 Node version、Traversal、下游 activation 不重复；
- deep reject 断言 iteration/clone/Link 不重复；
- takeover 断言 assignee、审计 Event、Outbox 和通知 identity 不重复；
- schedule run-now 断言 schedule execution/Run 不重复。

完成证据：`IDEM-01`–`IDEM-06` 全部通过；不能以通用 Receipt 单测替代五类命令的副作用断言。

### I3-F5 · 兼容、executor 固定与无损回滚

1. standalone Work Item 执行创建、接单、Doing、Review、Done、归档，全程断言无 Run/Node/Link/Runtime Event。
2. 旧单节点 `graph-v2` 与 legacy executor 按既有路径完成，不强制补换 executor。
3. Notice、系统节点和无需人工能力的流程不创建 Task 或 HumanTask Link。
4. Run 创建后 `engine_version`、`executor_kind` 不可由业务命令更新；增加源码守卫和服务测试。
5. 回滚演练：部署旧兼容代码/关闭 standalone 新建开关时，新表、新 Link、Receipt、incident 与 standalone Task 均保留；恢复新代码后可以继续读取和推进。

完成证据：`COMP-01`–`COMP-05` 全部通过，回滚不包含 DELETE/TRUNCATE、历史覆盖或 executor 改写。

### I3-F6 · 运维查询、观察期与最终闸门

新增 `WorkflowIteration4ReadinessService`，并提供两种只读入口：

- Admin-only `GET /api/v1/workflow-graph/admin/iteration4-readiness`；
- `python -m app.scripts.verify_workflow_iteration4_readiness --format json --fail-on-open`。

输出必须包括：

- Link-first、fallback、mismatch、未关联 HumanTask 与 superseded 链；
- Coordinator failure incident；
- Receipt conflict incident 与 receipt 状态；
- Outbox failed/retrying、dedup 命中与最老事件；
- Run 按 engine version / executor / status 的数量；
- 缺 snapshot、缺 engine version、缺 Link、open 回填异常等未完成迁移对象；
- 31 项 gate 的 `pass/fail`、阈值、证据时间窗和样本 ID。

Readiness API 只返回必要 ID 和聚合，不泄露 payload、人员隐私或完整业务 context；CLI 仅用于受控运维环境。

完成证据：`OBS-01`–`OBS-06` 全部通过，并生成最终准入报告。

## 4. Gate 追踪矩阵

| ID | 硬性条件 | 实施批次 | 必需证据 |
|---|---|---|---|
| OWN-01 | Work Item 仅 Work Item 模块直接修改 | F1 | 全仓库 AST guard + 已知越界回归 |
| OWN-02 | NodeExecution 仅 Runtime 直接修改 | F1 | 全仓库 AST guard + Runtime writer 测试 |
| OWN-03 | 跨域操作仅经 Coordinator | F1/F3 | 调用边界测试 + UoW 集成测试 |
| OWN-04 | 自动化架构测试阻止越界写入 | F1 | 对故意违规 fixture 的反向测试 |
| LINK-01 | 新流程 HumanTask 全部创建 Link | F2 | 各激活入口 + DB 数量断言 |
| LINK-02 | Link 有数据库唯一约束 | F2 | PostgreSQL 约束竞争测试 |
| LINK-03 | Link 支持 iteration/superseded | F2 | migration + lifecycle/Deep-Reject 测试 |
| LINK-04 | Link 回填有异常队列 | F2/F6 | incident 幂等 upsert + 查询 |
| LINK-05 | JSON fallback 达到阈值 | F2/F6 | 连续 7 天 0 fallback + 全量扫描 |
| LINK-06 | Link 与 JSON 不一致时 Link 为准 | F2 | mismatch 回归 + incident |
| TX-01 | Task 完成与 Node 推进不半完成 | F3 | PostgreSQL 六断点回滚测试 |
| TX-02 | 事务故障注入通过 | F3 | `workflow_i4_gate and postgres` |
| TX-03 | Outbox 与业务修改同事务 | F3 | commit 前/后可见性断言 |
| TX-04 | 成功 Receipt 与业务结果同事务 | F3 | Receipt/业务原子可见性断言 |
| IDEM-01 | create run 重放不创建第二个 Run | F4 | API + 并发计数 |
| IDEM-02 | complete node 重放不二次推进 | F4 | version/traversal/activation 计数 |
| IDEM-03 | deep reject 重放不增加 iteration | F4 | clone/iteration/Link 计数 |
| IDEM-04 | takeover 重放不重复通知 | F4 | Event/Outbox/message identity 计数 |
| IDEM-05 | 同 command ID 异 payload 冲突 | F4/F6 | 409 + receipt_conflict incident |
| IDEM-06 | 并发首次执行只有一个执行者 | F4 | 独立 Session PostgreSQL 测试 |
| COMP-01 | standalone 全生命周期无 Runtime | F5 | 完整生命周期表级断言 |
| COMP-02 | 旧单节点图正常完成 | F5 | graph-v2/legacy 回归 |
| COMP-03 | Notice/系统流程无需 Task | F5 | 无 Task/Link 断言 |
| COMP-04 | 同一 Run 不切换 executor | F5/F6 | 不可变守卫 + 分组查询 |
| COMP-05 | 回滚不删除新数据 | F5 | downgrade-free 代码回滚演练 |
| OBS-01 | 可查询 Link fallback | F2/F6 | incident + readiness 查询 |
| OBS-02 | 可查询 Coordinator 失败 | F3/F6 | coordinator_failure 查询 |
| OBS-03 | 可查询 Receipt 冲突 | F4/F6 | receipt_conflict 查询 |
| OBS-04 | 可查询 Outbox 重复与失败 | F4/F6 | outbox 状态 + duplicate incident |
| OBS-05 | 可按 engine version 统计 Run | F6 | readiness 聚合测试 |
| OBS-06 | 可识别全部未完成迁移对象 | F2/F6 | reconciliation + fail-on-open |

## 5. Schema、API 与兼容影响

计划中的 schema 变更均为向下兼容 Expand：

- `workflow_human_task_links` 增加 iteration/superseded 字段和约束；
- 新增 `workflow_operational_incidents`；
- Contract revision 只在回填与扫描全绿后收紧 Link iteration/CHECK。

API 仅新增 Admin-only readiness 只读接口；现有 Task、Run、模板和命令响应保持兼容。新增 pytest marker：`workflow_i4_gate`，默认 pytest 仍收集这些测试。

实现 schema/API 前必须单独确认精确 migration、Pydantic 响应和权限设计；本计划本身不授权直接删除列、停写 JSON 或改变公共响应。

## 6. 验证命令

```powershell
cd backend
pytest -q
pytest -q -m workflow_i4_gate -rxX
$env:FILUM_REQUIRE_POSTGRES_TESTS='true'
pytest -q -m "workflow_i4_gate and postgres" -rs
python -m compileall app tests
python -m app.scripts.verify_workflow_iteration4_readiness --format json --fail-on-open
```

随后执行前端既有单元测试、type-check/build，以及 memory-bank 全量检查。任何 PostgreSQL skip、strict xfail、未知 warning 或 readiness open P0/P1 都视为失败。

## 7. 发布、观察与回滚顺序

1. **Expand**：先上 nullable 字段和 incident 表；迁移 head↔base 演练。
2. **Ownership cutover**：部署写端口/Coordinator/UoW，保留 Link+JSON 双写。
3. **Backfill**：目标环境 dry-run，处理歧义后分批 apply，每批有 checkpoint。
4. **Contract**：全量扫描通过后收紧 Link iteration 与 superseded 约束。
5. **Observe**：连续 7 天 reconciliation 100%、runtime fallback 0、open P0/P1 incident 0。
6. **Gate review**：生成 `memory-bank/history/reports/workflow-graph-iteration3f-gate-YYYYMMDD.md`，逐项附测试和查询证据。
7. **用户批准**：只有用户确认 31/31 PASS 后，才更新状态并启动 Iteration 4。

代码回滚只切回兼容读写实现；保留新列、新表、Link、Receipt、incident 和 standalone Work Item。数据库 downgrade 仅用于发布前迁移演练，不作为线上回滚手段。

## 8. 停止条件

出现任一情况立即停止切流，不进入观察期：

- 仍有无法归属的生产跨域写点；
- 任一新 graph-v3 HumanTask 可在无 Link 情况下提交；
- 回填需要猜测 Task/Node 关系；
- 故障注入出现半完成或 Receipt/Outbox 孤儿；
- 同一 command 并发产生两个业务副作用；
- readiness 数据只能依赖单进程内存；
- 回滚必须删除新数据、覆盖事件或更换在途 Run executor。

触发后保持现有兼容路径，登记 `I3F-GAP-*` 与 operational incident，修订计划和证据后重新验收。

## 9. 完成定义

Iteration 3-F 只有同时满足以下条件才能标记完成：

- Gate 矩阵 31/31 PASS，0 PARTIAL、0 FAIL；
- Backend 全量、PostgreSQL 强制专项、compileall、前端基线全部通过；
- 架构测试扫描整个生产 Python 源码且无宽泛豁免；
- 目标环境回填、Contract migration、恢复和无损代码回滚演练完成；
- 连续 7 天 Link reconciliation 100%、runtime JSON fallback 0；
- open P0/P1 operational incident 为 0；
- 最终准入报告由用户批准。

在此之前，Iteration 4 始终保持 blocked，而不是“带已知缺口并行启动”。
