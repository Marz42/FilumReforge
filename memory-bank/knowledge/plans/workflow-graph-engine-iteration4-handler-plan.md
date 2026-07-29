---
type: paradigma-plan
title: 工作流图引擎 Iteration 4 · 业务能力 Handler 化实施计划
description: "以 Handler Registry 和统一 Capability Result 为起点，逐步接入 HumanTask、Approval、Deliverable、Notification，并把业务模板特殊判断迁出 Runtime 核心。"
tags:
  - plan
  - workflow-graph
  - iteration-4
  - handler
  - capability
timestamp: 2026-07-30T00:56:25+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Iteration 4, Handler 化, Capability Result, HumanTask Handler]
    en: [iteration 4, handler registry, capability result, human task handler]
---
# 工作流图引擎 Iteration 4 · 业务能力 Handler 化实施计划

> **状态**：I4-A 至 I4-D 已完成。HumanTask、Approval、Deliverable 与 Notification 均已通过纯 Handler Result 或边界清晰的应用协调接入；交付版本/验收快照及通知完成策略不再由 Runtime 猜测。前端 P2 第一批 6 项已实现，后续反馈持续接收。Iteration 3-F 的目标环境回填、7 天观测和最终 31/31 报告仍未完成，因此生产切流继续受硬门禁约束。

## 1. 目标

让 Runtime 只依赖统一的节点能力契约与执行结果，不继续扩散审批票数、交付版本、通知渠道或特定业务模板字段等判断。新增能力应通过通用 Handler 或边界清晰的应用服务接入，而不是修改核心路由算法。视频流程按 ADR-018 作为普通模板包；参与者重叠按 ADR-019 的决策对象与动作语义处理。

## 2. 启动时缺口

| ID | 缺口 | 处置 |
|---|---|---|
| GAP-TPL-01 | 模板解耦 Phase 2 交互尚待 UAT | 独立验收，不阻塞纯后端 Handler 契约开发 |
| GAP-TPL-02 | M-09 unarchive 无 sibling ACTIVE / 审计策略 | 保持 deferred |
| GAP-TPL-03 | template `run_kind` dual-read 仍被视频兼容链路使用 | I4-E 前不得删除 |
| GAP-I3F-01 | 目标环境 Expand/Contract、Link 回填、恢复/回滚演练未完成 | 生产切流前补齐 |
| GAP-I3F-02 | 连续 7 天 reconciliation/fallback/incident 证据缺失 | 生产切流前补齐并重启失败窗口 |
| GAP-I3F-03 | 31/31 最终准入报告未生成/批准 | 保持 release gate |
| GAP-ALIGN-01 | README / roadmap / project brief / contracts 焦点与测试基线漂移 | Preflight P0 收口 |
| GAP-DOMAIN-01 | Runtime、TaskService 与前端仍按 `run_kind` / video profile 分支 | 按 ADR-018 盘点并迁为通用能力 |
| GAP-UI-01 | 前端第一批 6 项已实现并完成真实账号首轮 UAT；后续反馈继续接收 | Preflight P2 按 P0–P3 持续分级 |
| GAP-DECISION-01 | 旧 `self_review_fallback` 把集合推进与独立验收混为一谈 | 按 ADR-019 建立语义矩阵并迁移 |
| GAP-ADMIN-01 | Admin 当前仍可进入业务候选/override，与维护角色定义不一致 | **deferred**；KI-011，明确不属于 I4 |

## 3. 分批实施

### I4-A · 契约与注册表

- [x] 定义统一 `WorkflowCapabilityResult`：outcome、engine/business state、结果、诊断与声明式 side effects。
- [x] 定义 Handler 生命周期：definition validation、activate、command、cancel、retry、interruptible、compensation、result mapping。
- [x] 建立按 `WorkflowGraphNodeType` 解析的 Registry；重复注册与缺失 Handler 必须显式失败。
- [x] Runtime 接入结果映射，但保持现有 Task/Notice 行为不变；Approval 继续 legacy，直到 I4-C。

### I4-B · HumanTask

- [x] HumanTask 激活返回等待 Work Item 的能力结果。
- [x] 完成/取消/重试统一映射到 Runtime 状态，不由 Handler 直接写 ORM。
- [x] 完成、取消、重试结果经 `HumanTaskCoordinator` 与 owner-only Runtime write port 应用，并同步 Link。
- [x] Work Item / Link / RunEvent / Outbox 保持同一 caller-owned UoW；重试已覆盖 flush 后整体 rollback，管理员归档仍由 `TaskService` 在同一事务收口 Work Item。
- [x] 将普通完成与 `collection_finalize` 分开建模；集合负责人可同时是集合贡献者。
- [x] 命令结果携带决策语义、决策对象、贡献者和 actor overlap 诊断，不由 Runtime 根据 assignee 相等关系猜测。
- [x] 覆盖 A/B/C 均提交、A 汇总推进，以及 A 前序贡献但处理不同下游交付的合法场景。

### I4-C · Approval

- [x] 纯 Approval Handler / 决策策略已按 ADR-019 映射 `deliverable_acceptance`、`business_approval` 与 `cosign`；`collection_finalize` 保持 HumanTask 命令；默认 Registry 已在旧审批引擎桥接完成后启用 Approval。
- [x] 贡献者事实优先取当前 Deliverable submitter/signature，其次才回退到显式配置、源节点执行人或业务流程发起人；返工更新当前交付后会重新解析。
- [x] 严格策略无合法候选人时返回可诊断 BLOCKED；`TaskService` 不再按候选数量自动启用 `self_review_fallback`，历史 fallback metadata 也不能绕过严格验收。
- [x] 已适配现有 `WorkflowDefinition / WorkflowInstance / WorkflowStepRun`：节点激活按 correlation key 幂等关联审批实例，旧审批动作经 API bridge 自动回传 Runtime。
- [x] RunEvent 固化 approval round/mode、decision、每票状态、代理来源、当前交付签名与策略诊断；重复成功回调和重复阻断均幂等。
- [x] 业务拒绝映射为 `REJECTED`，策略阻断映射为 `SUSPENDED/PENDING_REVIEW`，不与技术失败混同；票数仍由旧审批引擎计算，Runtime 只消费结果。
- [x] 最小矩阵：同版本提交者独自验收阻断；不同决策对象允许；贡献者会签非唯一决定者按显式策略允许；返工新版本重算贡献者。

### I4-D · Deliverable / Notification

- [x] Deliverable 以兼容 JSON v2 保存带 version/signature 的 submission/review 历史，并固定 accepted submission snapshot；下游附件继承优先读取被接受版本。
- [x] Notification 明确 `queued`、`sent`、`all_channels_success` 三种完成策略；默认保持最严格的全渠道成功，worker 按消息全部 delivery 判定而非当前任务子集。
- [x] Deliverable / Notification 的失败、重试、取消与补偿进入统一 Capability Result；通知失败重投已消费 `retry_failed_deliveries` side effect，旧 API 与数据库 schema 不变。

### I4-E · 领域中立化与兼容迁移

- [ ] 盘点 Runtime / TaskService / Task Center / API / 前端内 `run_kind`、模板 code、节点 key、`ui_profile` 与视频字段分支。
- [ ] 抽取结构化表单、集合关闭、聚合、交付/返工、子 Run 等可跨业务复用的能力。
- [ ] 禁止新增 `VideoHandler`；视频保留为模板包、种子数据、兼容适配和黄金流程回归。
- [ ] 兼容依赖归零后再收窄 template `run_kind` dual-read。

## 4. 兼容与门禁

- 本阶段首批不改数据库 schema，不新增破坏性 API，不删除既有 executor 或兼容 JSON。
- Handler 返回纯结果，由 Runtime owner 应用状态；Handler 不直接写 `WorkflowNodeInstance`。
- tags、模板 code、节点 key 与 UI Profile 不得成为 Runtime 业务分支依据。
- Iteration 4 不修改 `UserRole.ADMIN`、`MANAGEMENT_ROLES`、管理员候选链/override 或相关兼容测试；管理员业务边界按 KI-011 延后。
- Iteration 3-F 未完成前只开发、测试、shadow 验证，不做生产切流。
- 任何需要 schema/API 的后续批次仍按仓库协议单独评审。

## 5. I4-A 验收

- Registry 能稳定解析 HumanTask/Approval/Notice，未知/重复能力有确定错误。
- HumanTask、Approval 与 Notice 的生命周期/命令映射有纯单测。
- `WorkflowGraphService` 的相关状态迁移消费统一 Capability Result，既有行为回归不变。
- I3-F 写所有权 AST guard、Backend 全量与 compileall 通过。
