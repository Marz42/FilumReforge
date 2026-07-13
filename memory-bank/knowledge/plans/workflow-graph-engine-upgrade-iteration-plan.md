---
type: paradigma-plan
title: 工作流图引擎稳健升级迭代方案
description: "基于现行九表图引擎、Task 双写与视频工作流的渐进式升级方案。"
tags:
  - plan
  - workflow-graph
  - runtime
  - migration
timestamp: 2026-07-13T22:11:53+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh:
      - 图引擎升级
      - 工作流边界
      - 运行时正确性
      - 双写收口
    en:
      - workflow upgrade
      - runtime correctness
      - work item
      - migration
---
# Project Filum 工作流图引擎稳健升级迭代方案

> **状态**：Iteration 0 已完成并通过用户验收；ADR-012–016 已采纳，下一步进入 Iteration 1。  
> **输入**：根目录 `workflow-graph-engine-upgrade-guidance-report.md`、现行 ORM / Service / API / 测试，以及 [`workflow-graph-engine.md`](../domains/workflow-graph-engine.md) as-built。  
> **与旧计划关系**：[`workflow-refactor-implementation-plan.md`](./workflow-refactor-implementation-plan.md) 记录 Phase 1–11 的历史实施主线；本文只规划其后的结构收敛与正确性升级，不回写历史阶段。

---

## 1. 计划结论

本轮不推倒重写，不先做目录大搬家，也不立即建设完整 BPMN 引擎。升级按以下顺序推进：

1. 先修对象级授权、服务端能力门闩和模板作用域绕过；
2. 冻结发布定义与在途 Run 的执行快照；
3. 用“实际经过的边 / 实际产生的激活”修正条件分支、Join、no-route 和完成语义；
4. 再通过正式 Link、应用协调器和命令幂等收口 Task / NodeInstance 双写；
5. 随后拆分 Approval、Deliverable、Notification、视频等能力；
6. 最后建设正式读模型、恢复工作台与 Legacy 清理。

第一目标不是增加节点类型，而是确保：**现有 Run 不因模板变化而漂移，条件 Join 不死锁，越权用户不能读取 Run，关键命令可以安全重放。**

---

## 2. 当前事实基线

### 2.1 已有且应保留

- 图模板 / 节点 / 边、图实例 / 节点实例；
- 条件边、fan-out、Wait-All、Wait-Any、Notice 自动完成；
- 深度打回、iteration、takeover；
- `context` / `context_version`；
- Outbox、Run Event、图模板周期调度；
- 任务中心 graph-first 用户体验；
- 视频批次、按题 fork 与制作流程能力；
- FastAPI + SQLAlchemy Async + PostgreSQL + Redis / ARQ 的模块化单体技术栈。

### 2.2 已确认风险

| 风险 | 当前事实 | 影响 |
|------|----------|------|
| 发布定义未真正冻结 | active 模板仍可更新 config / scope；运行时继续读取实时模板节点和边 | 在途 Run 行为可能随模板变化 |
| 条件 Join 使用静态入边 | 未命中分支仍为 `PENDING`，Join 等待模板全部上游 | 条件汇合或 no-route 可能永久卡住 |
| 对象级授权不完整 | 若干实例 / 事件 / 子 Run 查询只校验登录 | 内部数据越权读取 |
| 部门 scope 校验时机错误 | 请求未传 department 时先绕过检查，服务内再推导部门 | 模板作用域可能被绕过 |
| Task / Node 双主写 | JSON 双向锚点，双方 Service 直接修改对方状态 | 状态漂移、迁移和故障恢复困难 |
| 状态语义混合 | `ACKNOWLEDGED` 等人工语义进入 engine state | Runtime 与 Human Task 边界不清 |
| 命令幂等不完整 | 节点完成有状态重放，但无 command receipt；创建 Run / 打回等缺统一幂等 | 重试可能重复创建或静默忽略不同 payload |
| 并发验证不足 | 主服务测试使用 SQLite，不能验证 PostgreSQL 行锁 / SKIP LOCKED | 生产并发正确性缺少证据 |

### 2.3 本轮明确不做

- 不拆微服务；
- 不立即把 `tasks` 物理重命名为 `work_items`；
- 不一次性迁移或重写所有历史 Task / Run；
- 不先建设任意脚本节点、通用低代码平台或完整 BPMN 兼容层；
- 不在正确性收口前继续增加 Timer / Webhook / Signal 等新节点；
- 不在正式投影稳定前删除 ROOT Task 或 graph-first fallback。

---

## 3. 目标边界的项目化解释

六个目标模块作为**逻辑边界**逐步形成，不要求第一阶段就重排整个目录。

| 目标模块 | 本项目近期落点 | 近期不做 |
|----------|----------------|----------|
| Work Item | 先把现有 `Task` 定义为工作项写模型；新增正式 Node Link；新独立任务不再建单节点图 | 立即改表名、重写所有 `/tasks` API |
| Workflow Definition | 冻结 active 版本；Run 保存快照 / hash / engine version | 立即引入庞大的定义元模型 |
| Workflow Runtime | 管理 Instance、Node Execution、实际路径、Context 和完成结果 | 直接管理 Task 评论、审批票数、视频字段 |
| Business Capabilities | Handler 适配 Human Task、Approval、Deliverable、Notice、视频 | 再造第三套审批系统 |
| Projection & Query | 事件驱动 `task_center_items`、run summary、节点时间线 | 业务命令反向修改投影 |
| Infrastructure | UoW、Command Receipt、Outbox 去重、PostgreSQL 并发测试、观测 | 决定业务路由和审批规则 |

### 3.1 三项务实决策

1. **Task 先逻辑升级，不先物理改名**：减少 API、前端、附件、评论、统计的连锁迁移。
2. **先用路径账本，不立即上完整 Token 引擎**：以 `edge traversal / activation dependency` 解决当前条件分支与 Join；等 Subprocess、Signal 或复杂并行确有需求，再升级为通用 Token。
3. **优先复用现有审批引擎**：评估 `WorkflowDefinition / WorkflowInstance / WorkflowStepRun` 能否经 Approval Handler 接入；只有语义确实不兼容时才设计新审批模型。

---

## 4. 全程执行规则

### 4.1 每个迭代的固定步骤

1. 先写行为契约和失败案例；
2. schema / API 变更方案经用户确认后再编码；
3. 采用 Expand → Backfill → Shadow / Dual-read → Cutover → Contract；
4. 新写入口先受后端 capability 控制；
5. 完成自动化验证、迁移演练和人工验收后停止，等待用户确认；
6. 未过退出标准，不进入下一迭代。

### 4.2 兼容与回滚原则

- 已启动 Run 不原地改写执行语义；
- 新旧字段并存期间，新代码须可读取旧数据；
- 先增加 nullable / 默认兼容结构，完成回填后再收紧约束；
- 所有 backfill 均支持 dry-run、批次、checkpoint 和审计输出；
- feature flag 只用于安全切流，不长期代替领域边界；
- 回滚只能切回兼容读写路径，不能删除新数据或覆盖历史事件；
- 删除旧列、JSON 锚点或 Legacy 表族必须是最后阶段的独立变更。

### 4.3 在途 Run 处理原则

- 升级上线时为所有 active Run 固化执行快照和 `engine_version`；
- 若无法证明当前模板与启动时模板一致，将 Run 标记为“快照来源不确定”，进入管理员核查队列；
- 老 Run 使用 legacy executor 语义直至完成、取消或人工迁移；
- 新 Run 才使用路径账本和新 completion policy；
- 禁止为了统一模型批量重放在途业务副作用。

---

## 5. Iteration 0：基线冻结与决策闸门

### 2026-07-13 落地状态

- [x] 独立 `workflow_gap` 套件与 7 个稳定缺陷编号；11 个 strict xfail 参数实例全部命中。
- [x] PostgreSQL 随机数据库、Alembic head、独立 `AsyncSession`、强制无 skip 和清理校验基座。
- [x] 三组图引擎 PostgreSQL 并发测试与临时库无残留测试。
- [x] 统一基线报告：运行时、权限、双写、事务、Outbox、active Run 测量风险、Iteration 1–3 影响。
- [x] ADR-012–ADR-016 已创建，并于 2026-07-13 经用户统一批准转为“已采纳”。
- [x] 临时启动仓库 Docker PostgreSQL，以 `FILUM_REQUIRE_POSTGRES_TESTS=true` 完成 5/5 生产方言验收；测试库均已删除，容器与 Docker Desktop 已停止。
- [x] 用户统一批准 ADR；Iteration 0 决策闸门通过。

### 目标

在 schema 变更前建立可复现证据，冻结新增特殊逻辑，并确认后续关键决策。

### 实施项

- 建立运行时语义测试矩阵：exclusive、inclusive、parallel、first-match、Wait-All、Wait-Any、else、no-route、返工与迟到提交；
- 增加当前缺陷复现：条件分支完成后实例卡住、条件分支汇合静态 Join、active 模板 config 改变在途行为；
- 形成 Run / Template / Event / Submission 的对象级授权矩阵；
- 盘点所有 `TaskService -> NodeInstance` 和 `Runtime -> Task` 写点；
- 盘点所有 Service 内 commit、Outbox 外部副作用和重复消费窗口；
- 暂停向通用 Runtime 增加新节点类型或视频特殊判断；
- 形成 ADR：定义快照、路径账本、Work Item Link、审批复用、老 Run executor 策略。

### 验证

- SQLite 快速语义测试；
- PostgreSQL 专项测试环境可创建、隔离和清理；
- 权限矩阵覆盖匿名、普通员工、办理人、发起人、部门经理、HR、Admin；
- 缺陷复现不得只依靠人工说明，必须有测试或可重复脚本。

### 退出标准

- 本文 §12 的待确认决策全部批准；
- P0 失败案例可以稳定复现；
- 后续 schema 与 API 影响清单明确；
- 尚未修改生产业务语义。

---

## 6. Iteration 1：P0 安全边界与执行版本冻结

### 目标

先保证“谁能看、谁能做、Run 按哪个版本执行”。

### 实施项

1. 建立统一 `WorkflowAccessPolicy`：
   - Run 可见性：发起人、当前 / 历史办理人、正式 watcher、有效管理范围、Admin / HR 的明确规则；
   - 写命令单独校验，不因可读自动获得操作权；
   - 实例、事件、子 Run、submission、模板统计统一复用策略。
2. 部门 scope 改为“先解析最终 department，再校验模板 scope”；建议引入显式 `scope_mode=global|departments`，避免空数组承担安全语义。
3. Wait-Any、Deep-Reject 等能力在服务端真正闸住；拒绝状态返回稳定错误码。
4. active / archived 定义全面不可变：节点、边、条件、config、schema、scope、能力配置均不得直接更新。
5. Run 固化：
   - definition snapshot；
   - definition hash；
   - definition version；
   - engine version；
   - 启动时校验结果。
6. 运行时停止通过当前模板补节点或重新绑定实时边；仅 legacy executor 可保留兼容行为。

### 数据迁移原则

- 新字段先允许为空；
- completed / cancelled 历史 Run 可延迟归档快照；
- active Run 优先回填并输出差异报告；
- 回填完成后，新 Run 的 snapshot / hash / engine version 改为 NOT NULL。

### 退出标准

- 未授权用户无法读取或枚举 Run 相关对象；
- 省略 department 不能绕过 scope；
- 修改模板不会改变已启动新 Run 的节点、边、规则和配置；
- 发布版本只能归档或派生新 draft，不能回退编辑；
- 权限与不可变性测试全部通过。

---

## 7. Iteration 2：P0 运行时路径与完成语义

### 目标

让条件分支、并行、Join、返工和实例结束有可证明的持久化语义。

### 建议最小模型

名称为预案，实施前须完成 schema 评审：

- `workflow_edge_traversals`：记录某次 iteration 中边为 `taken / not_taken` 及条件求值证据；
- `workflow_node_activations` 或 activation dependency：记录节点为何被产生、等待哪些实际上游；
- Node engine state 增加最小必要值：`skipped / failed / suspended`；
- Process result：`success / approved / rejected / cancelled / terminated`；
- 可选 `workflow_node_attempts`：技术重试与业务返工分离。

### 实施项

1. 显式 routing mode：`exclusive / inclusive / parallel / first_match`；
2. 路由求值写入 traversal，保存条件输入摘要、结果和选中原因；
3. 未选分支标记 skipped 或不产生 activation，不能永久保持普通 pending；
4. Join 只等待本次实际产生的 activation dependency；
5. Wait-Any 引入取消策略：仅撤权、业务取消、外部补偿分别声明；
6. no-route、无法满足的 Join、悬挂 activation 进入 failed / diagnostic，不得静默 active；
7. 新版本定义使用显式 Start / End；旧定义在启动快照时派生兼容 Start / End；
8. 完成策略至少检查合法 End、无悬挂 activation、无 failed 节点、无死 Join；
9. `current_node_key` 明确降级为展示字段，运行时以活动节点集合为准；
10. `instance_key` 改为不可变分支身份，不再等同当前办理人 UUID；
11. Deep-Reject 使相关旧 activation / traversal 失效，旧 iteration 永远不能继续推进；
12. Context 命令携带 expected version 和受控 patch，记录 context diff。

### PostgreSQL 必测场景

- 两个并发上游同时尝试激活同一下游；
- exclusive 单分支汇合 Wait-All；
- inclusive 两分支汇合 Wait-All；
- no-route；
- Wait-Any 获胜与迟到提交；
- Deep-Reject 后旧 iteration 迟到完成；
- 同一 Context version 的冲突 patch；
- 事务重试后不重复产生 activation / traversal。

### 退出标准

- Join 不等待未产生的分支；
- no-route 不会被误判成功，也不会无诊断地卡住；
- 同一逻辑节点每个 iteration 只产生一次有效 activation；
- 旧 iteration 无法修改 Context 或推进下游；
- 任一节点激活、跳过、取消和完成均可解释。

---

## 8. Iteration 3：P0/P1 写所有权与命令幂等收口

### 目标

把 Work Item 与 Node Execution 从“双主写”改为“各自拥有状态、应用层协调”。

### 实施项

1. 新增正式 `workflow_human_task_links`：
   - FK 到 Task / NodeInstance；
   - link role / lifecycle；
   - 唯一性按节点能力确定；
   - JSON 锚点仅作兼容读，不再是新写真相。
2. 建立 `HumanTaskCoordinator`：
   - Runtime 激活 HumanTask → 创建 Work Item + Link；
   - Work Item 命令完成 → 产生能力结果 → Runtime Command；
   - TaskService 不再直接写 NodeInstance；Runtime 不再直接写 Task。
3. 新建普通任务默认成为 standalone Work Item，不创建单节点图；旧手动图任务继续兼容直至自然结束。
4. engine state 只表达执行控制；接受、办理、待验收等留在 Work Item / capability 状态。
5. 建立 `command_receipts`，至少覆盖：
   - create run；
   - complete node；
   - deep reject；
   - takeover；
   - schedule run-now；
   - subprocess / webhook callback（后续启用时）。
6. 重放同一 command 返回首次结果；同一 command id 携带不同 payload 必须冲突。
7. 统一事件信封：event / aggregate version、command、causation、correlation、actor、occurred_at。
8. Outbox 消费增加 event-id 去重；修正通知消息已 commit、Outbox 未标 dispatched 的重复窗口。

### 迁移与切流

- 回填 Link 时交叉校验 Task metadata、Node config 和 Instance source_id；不一致进入异常表 / 报告；
- 新写先同时写 Link 与兼容 JSON；
- 读侧先 Link-first、JSON fallback，并记录 fallback 命中率；
- fallback 长期为零且完成恢复演练后，停止写 JSON；
- standalone 新路径独立 feature flag，可快速回到兼容创建路径，但不删除已创建 Work Item。

### 退出标准

- 新业务关系都有 FK / 唯一性约束；
- Work Item 与 NodeExecution 只有各自模块能直接修改；
- 创建 Run 和关键节点命令可安全重放；
- 普通任务不依赖 Runtime 仍能完成完整生命周期；
- 纯系统 Runtime 不依赖 Task 也可执行。

---

## 9. Iteration 4：P1 业务能力 Handler 化

### 目标

让 Runtime 只理解能力契约和结果，不理解审批票数、交付版本、通知渠道和视频字段。

### 实施顺序

1. Node Handler Registry 与统一 Capability Result；
2. HumanTask Handler（基于 Iteration 3）；
3. Approval Handler：优先适配现有轻量审批引擎，补足 round / decision 审计；
4. Deliverable：Submission / Review 多版本，保留 accepted submission；
5. Notification：明确“入队 / 发送成功 / 全渠道成功”完成策略；
6. 视频能力：逐步从 Runtime / TaskService 分支迁入独立 handler 与 projection handler；
7. 再按真实产品需求引入 Timer、Webhook、Signal、Subprocess。

每个 Handler 至少声明：definition validation、activate、command、cancel、retry、side effect、interruptible、compensation、result mapping。

### 退出标准

- Runtime 无审批人数、交付版本、通知渠道和 video profile 的业务判断；
- 能力数据可独立审计；
- Handler 失败可区分业务失败与技术失败；
- 新增能力无需修改 Runtime 核心路由算法。

---

## 10. Iteration 5：P1/P2 投影、查询与运维

### 目标

在写模型稳定后替换运行时动态 graph-first 拼装，并建立可恢复运维能力。

### 实施项

- `task_center_items`：统一 standalone、HumanTask、Approval、Process Run shell 和系统告警；
- `process_run_summaries`；
- `node_timeline_entries`：聚合 Node Event、Work Item Activity、评论、交付、审批、返工、接管；
- projector checkpoint、幂等消费、单对象 / 单 Run 重建；
- 新旧列表 shadow comparison，记录字段差异和延迟；
- ROOT Task 先转为 projection shell，稳定后停止创建；
- Outbox FAILED 运维页、人工重放、消费者去重查询；
- 卡死 Run / no-route / Join wait / Context conflict 工作台；
- Metrics：active / failed / suspended Run、Join 等待年龄、Outbox backlog、最老消息、projection lag；
- Trace / log 统一携带 request、command、correlation、instance、node、work item id。

### 退出标准

- Task Center 不需查询时动态拼装 Runtime 内部表；
- 投影可清空后重建且结果一致；
- 投影失败不回滚业务命令；
- ROOT Task 退出不影响已有深链和历史查询；
- 运维人员可以诊断、重试、暂停、恢复和审计异常 Run。

---

## 11. Iteration 6：收缩兼容层与 Legacy 清理

### 前置条件

- 新路径稳定运行达到约定观察期；
- Link fallback、graph-first fallback 和 ROOT shell 新增量均为零；
- PostgreSQL 并发测试、投影重建、备份恢复和回滚演练通过；
- 历史 / active Run 数量与迁移报告经用户确认。

### 实施项

- 停止写 Task / Node JSON 关键锚点；
- 移除 Runtime 对 Task 的直接写入和 TaskService 对 Node 的直接写入；
- 下线动态 graph-first 查询；
- 清理不再挂载的 Legacy E 服务、表族和 feature flags；
- 删除兼容列 / 表前单独提供归档、导出和回滚方案；
- 同步用户手册、运维手册、契约、ADR 和架构文档。

### 退出标准

- 六个逻辑模块的表所有权和依赖方向可自动检查；
- 关键 JSON 锚点不再承担业务关系；
- 无运行入口依赖 Legacy E；
- 全量测试、部署近似 E2E、迁移 / 回滚演练通过。

---

## 12. 实施前待用户确认的决策

以下为推荐默认值；未确认前不进入 schema / API 编码。

| 决策 | 推荐默认 | 影响 |
|------|----------|------|
| 在途 Run | 固化当前可见模板为 legacy snapshot；差异不确定者进入人工核查 | 避免原地改写业务语义 |
| 执行路径模型 | 先 edge traversal + activation dependency，不先做通用 Token | 降低首轮复杂度 |
| Task 命名 | 逻辑视为 Work Item，保留 `tasks` 表与 `/tasks` API | 降低破坏性迁移 |
| 独立任务 | 新建 standalone 不创建图；旧手动图任务不批量转换 | 收口不扩大迁移风险 |
| Approval | 优先适配既有审批引擎 | 避免第三套审批模型 |
| Template scope | 显式 `global / departments`；默认 departments 或创建时必选 | 消除空数组默认开放风险 |
| Start / End | 新定义强制显式；旧定义在快照时派生 | 保持历史兼容 |
| Context | expected version + 受控 patch；拒绝全量任意 merge | 防止并发覆盖 |
| Command id | 客户端 / 调用方提供，服务端按 actor + command type + id 唯一 | 可验证重放 |
| 旧兼容删除 | 单独迭代、单独批准，不随功能上线自动删除 | 保证可回滚 |

---

## 13. 测试与质量闸门

### 13.1 分层测试

- SQLite：纯规则、schema validation、映射和快速服务测试；
- PostgreSQL：锁、唯一约束、并发激活、SKIP LOCKED、事务重试、迁移；
- API：对象级授权、幂等、稳定错误码、兼容响应；
- Worker：重复消费、崩溃恢复、退避、FAILED / replay；
- Frontend：flag、权限按钮、Run 诊断、投影延迟提示；
- E2E：standalone Work Item、流程 HumanTask、条件 Join、返工、恢复、历史查询。

### 13.2 每阶段通用命令

```sh
cd backend
pytest -q
python -m compileall app tests

cd ../frontend
npm run test:unit -- --run
npm run type-check
npm run build
```

涉及数据库锁、迁移和并发的阶段必须额外运行 PostgreSQL 专项测试；不能以 SQLite 通过代替。

### 13.3 禁止切流条件

- 存在未解释的 Run 状态差异；
- shadow projection 存在持续性字段差异；
- active Run 无 snapshot / engine version；
- 权限矩阵存在 UUID 直读路径；
- 同一 command 重放可能产生第二个业务对象；
- 回滚需要删除数据或覆盖历史事件；
- PostgreSQL 并发测试未执行。

---

## 14. 风险与控制

| 风险 | 控制措施 |
|------|----------|
| 在途 Run 已受模板原地更新影响 | 快照回填差异报告 + 人工核查，不伪造历史 |
| 双写收口期间状态不一致 | Link-first shadow read + reconciliation job + fallback 指标 |
| 新旧 executor 并存复杂 | Instance 固化 engine version；禁止同一 Run 中途换 executor |
| 权限收紧导致既有页面 403 | 先记录 only / shadow policy，再按角色灰度启用 |
| Join 重构影响视频流程 | 视频模板建立黄金快照和按节点语义回归；新旧 executor 双轨 |
| Outbox 去重改变通知行为 | 先定义“业务事件一次、渠道可重试”边界，再加唯一消费键 |
| 投影延迟影响用户体验 | 命令返回写模型快照；UI 显示同步中；支持单对象 reproject |
| 计划范围过大 | 每个 Iteration 独立批准、独立迁移、独立退出，不跨阶段顺手重构 |

---

## 15. 总体验收标准

完成本计划后，系统应满足：

- 发布定义不可修改，在途 Run 完全绑定启动时快照；
- 任意 Run / Event / Submission 均有对象级授权；
- 任意节点激活都能解释由哪条实际路径、哪个命令产生；
- Join 只等待实际产生的分支，no-route 和死 Join 可诊断；
- Work Item 与 Node Execution 各自拥有状态，通过 Link 和 Coordinator 协作；
- standalone Task 不依赖 Runtime，纯系统 Runtime 不依赖 Task；
- 关键命令具备一致的幂等收据和审计链；
- Approval / Deliverable / Notification / 视频由 Handler 接入 Runtime；
- Task Center 和时间线来自可重建投影；
- 任意 Outbox 消息、投影和异常 Run 均可诊断与恢复；
- Legacy 删除有独立批准、备份和回滚证据。

---

## 16. 下一步

1. 用户审阅并确认 §12 决策；
2. 批准后仅启动 Iteration 0，不提前创建新表；
3. Iteration 0 输出失败案例、权限矩阵、写点清单和 ADR；
4. 再提交 Iteration 1 的精确 schema / API 变更清单，等待二次批准后编码。
