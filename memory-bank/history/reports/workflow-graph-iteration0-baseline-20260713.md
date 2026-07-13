---
type: paradigma-report
title: "工作流图引擎 Iteration 0 基线报告"
description: "运行时语义、对象权限、跨域写入、事务、Outbox 与后续变更影响的统一基线。"
tags: ["workflow-graph", "iteration-0", "baseline", "authorization", "transactions"]
timestamp: 2026-07-13T20:40:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: cold
  lifecycle: stable
  update_policy: append-only
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["Iteration 0 基线", "权限矩阵", "双写点", "Outbox 风险"]
    en: ["iteration 0 baseline", "authorization matrix", "dual writes", "outbox risk"]
---
# 工作流图引擎 Iteration 0 基线报告

> 结论：Iteration 0 仅建立证据和决策闸门，没有修改 `backend/app/`、Alembic、公共 API、数据库 schema、前端或运行时行为。下列“目标”是后续迭代契约，不代表当前已实现。

## 1. 证据范围与状态

- SQLite 语义/授权证据：`backend/tests/test_workflow_graph_iteration0_gaps.py`。
- PostgreSQL 并发基座：`backend/tests/test_workflow_graph_postgres_concurrency.py`。
- 缺陷策略：`workflow_gap` 默认收集，所有登记缺陷均为 `xfail(strict=True)`；修复导致 XPASS 时测试失败，必须移除相应 xfail。
- PostgreSQL 策略：复用 `POSTGRES_TEST_ADMIN_DSN` 创建随机库并迁移到 head；普通本地环境不可用时允许 skip；`FILUM_REQUIRE_POSTGRES_TESTS=true` 时任何 `postgres` skip 都转换为失败。
- 2026-07-13 本机实测：初次执行时 PostgreSQL 未运行，普通模式按约定 5 项 skip；随后临时启动仓库 Docker PostgreSQL，以 `FILUM_REQUIRE_POSTGRES_TESTS=true` 完成 5/5 强制验收（Alembic 往返、三组并发、临时库清理），无 skip、无 `PG-GAP-*`。验收后已停止容器与 Docker Desktop。

## 2. 运行时语义矩阵

| 场景 | 当前行为 | 目标行为 | 证据编号/现有通过用例 | 修复阶段 |
|---|---|---|---|---|
| exclusive 未选分支 | 未选节点保留 `PENDING`，阻止实例完成 | 未产生分支不进入活动依赖；实际路径完成后实例可收口 | `WG-GAP-001` strict xfail | Iteration 2 |
| exclusive 后 Wait-All 汇合 | 按模板静态入边等待未产生分支 | 只等待本次实际产生的 activation dependency | `WG-GAP-002` strict xfail | Iteration 2 |
| 无匹配路由且无 else | 当前节点完成，后续全 `PENDING`，Run 长期 `ACTIVE`，无诊断 | 非合法终点产生 `failed/no_route` 结果和事件/诊断 | `WG-GAP-003` strict xfail | Iteration 2 |
| active 模板修改 | 在途 Run 继续读实时节点/边，甚至补建节点 | Run 永远执行创建时快照并校验 hash/engine version | `WG-GAP-004` strict xfail | Iteration 1 |
| 同节点顺序重复完成 | 第二次识别 `COMPLETED`，不重复激活或推进版本 | 保持幂等，并扩展为 command receipt/payload 一致性 | `test_phase6_repeat_completion_is_idempotent_and_keeps_single_downstream_activation` | 已通过；Iteration 3 增强 |
| Wait-Any 竞争及迟到提交 | 胜者激活下游，其他上游撤权；旧节点不能再提交 | 保持 | `test_phase8_wait_any_activates_downstream_and_terminates_peer_nodes`、`test_phase11d_wait_any_replay_keeps_single_downstream_activation` | 已通过 |
| Deep-Reject append-only 重放 | 生成新 iteration，旧链撤权；旧节点拒绝再次重放 | 保持，并增加命令幂等/并发收据 | `test_phase9_deep_reject_replays_from_target_with_append_only_iteration`、`test_phase11d_deep_reject_blocks_replay_from_stale_node_after_clone` | 已通过；Iteration 3 增强 |
| iteration 上限 | 超限返回冲突，不再克隆 | 保持 | `test_phase9_deep_reject_blocks_when_iteration_exceeds_max_iterations` | 已通过 |
| Notice 自动完成 | 激活即完成并继续推进 | 保持；通知失败不得回滚 Runtime | `test_phase7_context_conditional_routing_and_notice_auto_completion` | 已通过；Iteration 3/5 解耦 |
| 两上游并发完成 | SQLite 不能证明行锁语义 | PostgreSQL 下 D 仅激活一次、版本只推进一次、无重复行 | PG 专项：`test_two_upstreams_complete_concurrently_activate_join_once` | Iteration 0 已通过 |
| 同节点并发重复完成 | SQLite 不能证明 `FOR UPDATE` 行为 | 完成和下游激活均只推进一次 | PG 专项：`test_same_node_concurrent_duplicate_completion_advances_once` | Iteration 0 已通过 |
| Deep-Reject 与完成竞争 | 此前缺生产方言证据 | 仅一个命令成功，留下 completed 或 replay-active 的单一一致状态 | PG 专项：`test_deep_reject_and_completion_race_leaves_one_consistent_result` | Iteration 0 已通过 |

若 PostgreSQL 专项暴露新的生产方言缺陷，先登记 `PG-GAP-*` 且 strict xfail；Iteration 0 不修生产代码。

## 3. API 对象权限矩阵（目标契约）

记号：`R` 可读；`C` 可执行当前节点命令；`M` 模板管理；`—` 无权。无权读取具体对象统一伪装为 404；已定位对象但无命令权限为 403。

| 主体 | Run/节点详情 | 事件/子 Run/submission | 节点完成 | designer/统计/实例列表 | 创建 Run |
|---|---:|---:|---:|---:|---:|
| 匿名 | 401 | 401 | 401 | 401 | 401 |
| 无关员工 | 404 | 404 | 403 | 404 | 仅有能力且 scope 合法 |
| Run 发起人 | R | R | 仅同时为当前办理人时 C | 需 M | scope 合法时可创建 |
| 当前办理人 | R | R | C | 需 M | 另行校验能力/scope |
| 历史办理人 | R | R | 403 | 需 M | 另行校验能力/scope |
| 正式 watcher | R | R | 403 | 需 M | 另行校验能力/scope |
| 部门经理 | 管理子树内 R | 管理子树内 R | 仅当前办理人时 C | 有模板管理能力且 scope 在子树内 M | 先解析最终部门，再校验子树与模板 scope |
| 有效代理 | 仅委托 scope/子树内 R | 同左 | 仅被委托且为当前办理人时 C | 仅显式委托模板管理能力时 M | 仅委托能力与 scope 内 |
| HR | 全局 R | 全局 R | 必须先 takeover | 全局 M | 全局，仍校验模板配置完整性 |
| Admin | 全局 R | 全局 R | 必须先 takeover | 全局 M | 全局，仍校验模板配置完整性 |

固定策略：

1. 未登录统一 401。
2. 无权读取具体对象统一 404，避免泄露对象存在性。
3. 已找到对象但无权执行命令返回 403。
4. Admin/HR 保持当前全局管理能力。
5. 部门经理和有效代理只覆盖管理子树/委托范围。
6. Run 发起人、当前或历史办理人、正式 watcher 可读。
7. 节点完成只允许当前办理人；Admin/HR 也必须先 takeover。
8. designer、统计、模板实例列表要求模板管理能力。
9. 创建 Run 必须先解析最终部门，再校验模板 `scope_mode` 和部门集合。

当前负向证据：`AUTH-GAP-001` 复现实例详情越权；`AUTH-GAP-002` 分别复现事件、子 Run、submission 越权；`AUTH-GAP-003` 分别复现 designer、统计和模板实例列表越权。

## 4. 跨域写入清单

### 4.1 TaskService → NodeInstance

| 写点 | Task 入口/位置 | NodeInstance 变化 | 风险 |
|---|---|---|---|
| 状态投影同步 | `TaskService._sync_graph_projection_for_task_status` | 写 `engine_state`、`business_state`、`acknowledged_at`、`completed_at`，手动任务完成时还可推进图 | Task 状态机直接拥有 Runtime 状态 |
| 握手同步 | `TaskService._sync_graph_projection_for_handshake_state` | 写办理人、激活/已受理状态、业务状态和时间 | Task 握手与 Runtime 命令并发时可能覆盖 |
| 任务状态/交付/审核入口 | `update_task_status`、`submit_task_deliverable` 及接受/拒绝/转派路径 | 先改 Task，再调用上述同步并由同一 Service commit | 缺显式 UoW/command receipt，职责耦合 |
| 图配置补写 | TaskService 图投影路径中的 `node_instance.config` 更新 | JSON 写入握手/深拒等元数据 | schema 不显式，难做关系约束和迁移 |

### 4.2 Runtime/视频编排 → Task

| 写点 | 位置 | Task 变化 | 风险 |
|---|---|---|---|
| takeover 投影 | `WorkflowGraphService._sync_manual_task_projection_after_takeover` | 直接写 `assignee_id`、metadata、`updated_at` | Runtime 反向写 Task |
| 通用编排创建/推进 | `WorkflowOrchestrationService` | 创建 Task；写 REVIEW/DOING/DONE、办理人和 metadata | 同时写 Task 与 NodeInstance，边界依赖 Service 内 commit |
| 视频实例化投影 | `WorkflowVideoInstantiationService` | 为节点/ROOT 创建 Task，补 parent/status/metadata | 一节点/多任务关系隐藏在 JSON |
| 视频表单提交 | `WorkflowVideoFormService` | 同时把 NodeInstance 与 Task 标为完成；聚合关闭时批量完成 Task | Runtime 与交付业务双写 |
| 视频返工 | `WorkflowVideoReworkService` | 重开 Task 并重激活 NodeInstance | 竞争失败时恢复语义依赖单 session |

结论：当前不存在单一写所有者；`workflow_graph_instance_id` / `workflow_node_instance_id` 等 JSON 元数据承担事实关系，数据库无法保证一对多 Link 的完整性。ADR-014 提议在 Iteration 3 用正式 Link、应用协调器和 UoW 收口。

## 5. commit、跨服务事务与 rollback 边界

| 边界 | 当前事实 | 失败窗口/判断 |
|---|---|---|
| `WorkflowGraphService.complete_node_instance` | 锁节点和实例，完成、激活下游、Run Event、Outbox 在同一 session，方法末尾 commit；已完成重放也主动 commit | 核心推进原子性较好，但 Service 自行 commit，难由更高层组合 |
| `deep_reject_to_upstream` / takeover | Service 内自行 commit | 与外层 Task/Handler 组合时无法统一提交；需要 UoW |
| 图实例创建 | `create_multi_node_instance` 只 flush、不 commit | 原子性由调用者决定；直接调用者必须明确提交/回滚 |
| `TaskService` 命令 | 多数公开命令内部 commit；同 session 内直接改 Task 和 NodeInstance | 单次调用可原子，但跨 Service 调用常含隐式 commit，组合边界不透明 |
| 视频 Form/Rework/Instantiation/Orchestration | 多数方法末尾 commit，同时写多个领域模型 | 当前依赖共享 session；中途调用带 commit 的服务会切断事务 |
| 模板 Admin | `_commit_with_conflict_translation` 统一 commit，IntegrityError 时 rollback | 仅覆盖模板写冲突；运行时与模板发布没有统一不可变闸门 |
| rollback | 业务 Service 仅少量捕获 IntegrityError 后 rollback；请求级未见显式统一 UoW | 未捕获异常通常由 session 上下文关闭回滚，但跨内部 commit 无法撤回 |

Iteration 3 的目标不是机械删除所有 commit，而是：应用命令入口拥有事务；领域 Service 只 flush；外部副作用只通过 Outbox；冲突映射和 rollback 在 UoW 边界统一。

## 6. Outbox 与通知失败窗口

1. Runtime 在当前事务写 `workflow_outbox_events(PENDING)`，这一点与节点状态原子。
2. Worker 先查询 ID，再逐事件 `FOR UPDATE SKIP LOCKED`；每事件独立 session，能避免批次级连带回滚。
3. Worker 递增 attempt 后调用 `NotificationService.send()`；该方法内部先 commit 通知消息/投递，再尝试队列发布。
4. `NotificationService.send()` 返回后，worker 才更新 Outbox 状态并再次 commit。
5. 因此若“通知已 commit/已发布”后进程崩溃、Outbox 状态尚未 commit，同一 Outbox 会重试并创建第二条通知。
6. `workflow_outbox_events` 没有业务去重键/唯一约束；通知消息也未以 outbox event id 建立唯一 inbox/receipt。
7. 发布失败会把 Notification 标为 failed 并 commit，但 Outbox dispatch 的成功/重试语义与通知内部提交仍耦合，恢复窗口不清晰。

后续目标：Outbox event 拥有稳定 dedup key；Notification consumer 建 inbox/唯一约束；`send` 不在调用者事务内自行 commit；状态更新和重试区分“消息已持久化”“已入队”“渠道已投递”。这属于 Iteration 3/5，Iteration 0 不修。

## 7. active Run、版本关联与快照回填风险

### 7.1 当前可确认结构

- Run 仅通过 `workflow_graph_instances.template_id` 关联模板行。
- 模板有 `base_code/version/status`，但 Run 没有执行快照、canonical hash 或 `engine_version`。
- Runtime 会读取实时模板边/节点，并可能为在途 Run 补建缺失节点。
- 因而仅凭 `template_id` 不能证明某个 Run 从创建到现在执行的是同一份定义。

### 7.2 数量状态

仓库、本地 SQLite 和本次临时 Docker PostgreSQL 测试数据都不能代表部署数据；本阶段未获得目标部署数据库只读连接。因此 **ACTIVE Run 数量、按模板版本分布、无模板关联数量均为“待目标环境测量”**，不得填 0。

进入 Iteration 1 前应在目标环境只读执行并保存结果：

```sql
SELECT status, count(*) FROM workflow_graph_instances GROUP BY status;
SELECT t.base_code, t.version, count(*)
FROM workflow_graph_instances i
LEFT JOIN workflow_graph_templates t ON t.id = i.template_id
WHERE i.status = 'active'
GROUP BY t.base_code, t.version
ORDER BY count(*) DESC;
SELECT count(*) FROM workflow_graph_instances
WHERE status = 'active' AND template_id IS NULL;
```

### 7.3 回填分级

- 可证明：发布版本从未原地变更，且完整节点/边仍在，可生成 snapshot + hash 并标注回填来源。
- 部分可证明：NodeInstance config 有局部副本但边/条件不可还原，不得冒充完整快照。
- 不可证明：模板被改、删或运行时补建过节点；固定 `legacy executor` 直至收口。
- 回填必须 dry-run、出报告、可回滚；不得在 Iteration 1 直接批量猜测。

## 8. Iteration 1–3 schema/API 影响清单（待后续逐项审批）

| 阶段 | 可能的 schema 影响 | 可能的 API/行为影响 | 兼容与闸门 |
|---|---|---|---|
| Iteration 1：授权与定义冻结 | 模板显式 `scope_mode`；Run `definition_snapshot`、`definition_hash`、`engine_version`、executor 标识；可能需要 watcher/历史办理关系的正式来源 | 对象读 401/404、命令 403；active 版本禁止原地编辑；创建 Run 先解析最终部门再验 scope | Expand 字段先 nullable；旧 Run legacy executor；API 负向契约先测试；迁移单独审批 |
| Iteration 2：实际路径语义 | edge traversal、activation dependency、运行失败结果/诊断；必要唯一约束 | no-route 明确失败；Join/完成按实际路径；事件/详情可能新增只读诊断字段 | 只对新 engine_version 启用；旧 Run 继续 legacy；PG 并发测试必须通过 |
| Iteration 3：写所有权与幂等 | Node↔Task 正式 Link；command receipt/idempotency key；Outbox dedup/inbox；可能新增版本列 | 创建/完成/打回支持幂等键；Task JSON 锚点降级为兼容字段；公共 `/tasks` 保留 | Expand→backfill→shadow compare→cutover→contract；standalone Task 不新建图需 feature/capability 闸门 |

本清单不是迁移授权。每个阶段在编码前必须提交具体 schema、API、回填、回滚和发布顺序供用户确认。

## 9. Iteration 0 决策闸门

已形成但仍为“提议”的 ADR：

- ADR-012：发布定义不可变、Run 快照、canonical JSON SHA-256、`engine_version`；
- ADR-013：edge traversal + activation dependency，暂不建设完整 Token；
- ADR-014：保留 `tasks`/`/tasks`，standalone Task 不建图，正式 Link 支持节点关联多个工作项；
- ADR-015：通过 Handler 复用现有审批引擎；
- ADR-016：对象级授权、显式 `scope_mode`、存量在途 Run 使用 legacy executor。

## 10. 验收结论

2026-07-13，用户统一批准 ADR-012–016。五份 ADR 已转为“已采纳”，Iteration 0 的测试、文档、PostgreSQL 与决策闸门全部通过。Iteration 1 可以开始，但仍须遵守渐进迁移、兼容和回滚约束。
