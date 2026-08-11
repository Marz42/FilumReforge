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
timestamp: 2026-07-30T01:45:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Iteration 4, Handler 化, Capability Result, HumanTask Handler]
    en: [iteration 4, handler registry, capability result, human task handler]
---
# 工作流图引擎 Iteration 4 · 业务能力 Handler 化实施计划

> **计划状态：COMPLETED（工程）** — I4-A～E 已交付；人工 UAT 与生产准入仍按独立清单执行，不在本文继续开发。

> **状态**：I4-A 至 I4-E 已完成。HumanTask、Approval、Deliverable 与 Notification 已统一接入能力结果；模板行为由领域中立 capability snapshot、runtime policy 与 task capability 驱动，视频字段仅留在兼容适配器和模板包。前端 P2 第一批 6 项已实现。Iteration 3-F 的目标环境回填、7 天观测和最终 31/31 报告仍未完成，因此生产切流继续受硬门禁约束。

## 1. 目标

让 Runtime 只依赖统一的节点能力契约与执行结果，不继续扩散审批票数、交付版本、通知渠道或特定业务模板字段等判断。新增能力应通过通用 Handler 或边界清晰的应用服务接入，而不是修改核心路由算法。视频流程按 ADR-018 作为普通模板包；参与者重叠按 ADR-019 的决策对象与动作语义处理。

## 2. 启动时缺口

| ID | 缺口 | 处置 |
|---|---|---|
| GAP-TPL-01 | 模板解耦 Phase 2 交互尚待 UAT | 独立验收，不阻塞纯后端 Handler 契约开发 |
| GAP-TPL-02 | M-09 unarchive 无 sibling ACTIVE / 审计策略 | 保持 deferred |
| GAP-TPL-03 | template `run_kind` dual-read 仍被旧 API/历史 Run 使用 | 已收口到兼容适配器；调用归零前不删除 |
| GAP-I3F-01 | 目标环境 Expand/Contract、Link 回填、恢复/回滚演练未完成 | 生产切流前补齐 |
| GAP-I3F-02 | 连续 7 天 reconciliation/fallback/incident 证据缺失 | 生产切流前补齐并重启失败窗口 |
| GAP-I3F-03 | 31/31 最终准入报告未生成/批准 | 保持 release gate |
| GAP-ALIGN-01 | README / roadmap / project brief / contracts 焦点与测试基线漂移 | Preflight P0 收口 |
| GAP-DOMAIN-01 | Runtime、TaskService 与前端曾按 `run_kind` / video profile 分支 | I4-E 已迁为 capability snapshot / task capability；旧值仅兼容读取 |
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

- [x] 完成 Runtime / TaskService / Task Center / API / 前端的领域专用分支盘点；核心行为不再按 `run_kind`、模板 code、节点 key 或 `video_*` Profile 分支。
- [x] 抽取 capability snapshot、runtime policy 与 task capability，覆盖结构化表单、集合关闭、聚合、交付/返工和子 Run 派发；新增非视频“合同材料收集”对照测试。
- [x] 未新增 `VideoHandler`；视频 seed v5 只声明通用能力，现有专用 API/service 保留为兼容适配与黄金回归入口。
- [x] template `run_kind` / `ui_profile` dual-read 已集中到后端与前端兼容适配器；公共 API、历史 Run 和旧前端依赖归零前不删除。

## 4. 兼容与门禁

- 本阶段首批不改数据库 schema，不新增破坏性 API，不删除既有 executor 或兼容 JSON。
- Handler 返回纯结果，由 Runtime owner 应用状态；Handler 不直接写 `WorkflowNodeInstance`。
- tags、模板 code、节点 key 与 UI Profile 不得成为 Runtime 业务分支依据。
- Iteration 4 不修改 `UserRole.ADMIN`、`MANAGEMENT_ROLES`、管理员候选链/override 或相关兼容测试；管理员业务边界按 KI-011 延后。
- Iteration 3-F 未完成前只开发、测试、shadow 验证，不做生产切流。
- 任何需要 schema/API 的后续批次仍按仓库协议单独评审。

## 5. I4-E 前序能力先行发布评估

- `8244af0` 仅保留为历史分批评估点，不再作为当前上线候选；当前候选必须包含 I4-A–E、模板部门治理与 2026-08-09 安全加固的完整固定提交。
- 当前安全批次无 Alembic schema 变更和前端依赖锁变更；修改可信代理配置、对象授权与 OOXML 入库预算，部署前必须同步 Nginx/`FORWARDED_ALLOW_IPS` 配置。
- 不建议只 cherry-pick 单个“自审批”提交：`23d7f68`、`2485cb0`、`5056f94`、`f30d658` 存在 Handler/bridge 顺序依赖；完整截止点风险更低。
- 上线前先核对服务器实际 commit，在预发复测 A/B/C 提交后 A 集合确认、同版本提交者不得独自验收、消息一键已读与任务列表/详情；保持现有 feature flags，不启用新的 I3-F 生产切流。
- 回滚为纯代码回滚；无需数据库 downgrade。正式发布与回滚窗口仍按部署手册执行。

## 6. I4-A 验收

- Registry 能稳定解析 HumanTask/Approval/Notice，未知/重复能力有确定错误。
- HumanTask、Approval 与 Notice 的生命周期/命令映射有纯单测。
- `WorkflowGraphService` 的相关状态迁移消费统一 Capability Result，既有行为回归不变。
- I3-F 写所有权 AST guard、Backend 全量与 compileall 通过。
