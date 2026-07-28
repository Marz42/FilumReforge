---
type: paradigma-plan
title: 工作流图引擎 Iteration 4 · 业务能力 Handler 化实施计划
description: "以 Handler Registry 和统一 Capability Result 为起点，逐步把 HumanTask、Approval、Deliverable、Notification 与视频业务判断移出 Runtime 核心。"
tags:
  - plan
  - workflow-graph
  - iteration-4
  - handler
  - capability
timestamp: 2026-07-28T11:35:18+08:00
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

> **状态**：2026-07-28 经用户明确授权启动开发；I4-A 已完成并通过全量回归，I4-B 待继续。Iteration 3-F 的目标环境回填、7 天观测和最终 31/31 报告仍未完成，因此本阶段只允许向下兼容开发与本地验证，生产切流继续受硬门禁约束。

## 1. 目标

让 Runtime 只依赖统一的节点能力契约与执行结果，不继续扩散审批票数、交付版本、通知渠道或视频字段等业务判断。新增能力应通过注册 Handler 接入，而不是修改核心路由算法。

## 2. 启动时缺口

| ID | 缺口 | 处置 |
|---|---|---|
| GAP-TPL-01 | 模板解耦 Phase 2 交互尚待 UAT | 独立验收，不阻塞纯后端 Handler 契约开发 |
| GAP-TPL-02 | M-09 unarchive 无 sibling ACTIVE / 审计策略 | 保持 deferred |
| GAP-TPL-03 | template `run_kind` dual-read 仍被视频兼容链路使用 | I4-E 前不得删除 |
| GAP-I3F-01 | 目标环境 Expand/Contract、Link 回填、恢复/回滚演练未完成 | 生产切流前补齐 |
| GAP-I3F-02 | 连续 7 天 reconciliation/fallback/incident 证据缺失 | 生产切流前补齐并重启失败窗口 |
| GAP-I3F-03 | 31/31 最终准入报告未生成/批准 | 保持 release gate |

## 3. 分批实施

### I4-A · 契约与注册表

- [x] 定义统一 `WorkflowCapabilityResult`：outcome、engine/business state、结果、诊断与声明式 side effects。
- [x] 定义 Handler 生命周期：definition validation、activate、command、cancel、retry、interruptible、compensation、result mapping。
- [x] 建立按 `WorkflowGraphNodeType` 解析的 Registry；重复注册与缺失 Handler 必须显式失败。
- [x] Runtime 接入结果映射，但保持现有 Task/Notice 行为不变；Approval 继续 legacy，直到 I4-C。

### I4-B · HumanTask

- [x] HumanTask 激活返回等待 Work Item 的能力结果。
- [ ] 完成/取消/重试统一映射到 Runtime 状态，不由 Handler 直接写 ORM。
- [ ] 复用 `HumanTaskCoordinator` 与 owner-only write ports，不绕过 I3-F AST guard。
- [ ] Work Item / Link / RunEvent / Outbox 保持同一 UoW。

### I4-C · Approval

- [ ] 先适配现有 `WorkflowDefinition / WorkflowInstance / WorkflowStepRun`。
- [ ] 固化 round、decision、票数与代理审批审计。
- [ ] 区分业务拒绝与技术失败；不在 Runtime 核心计算审批票数。

### I4-D · Deliverable / Notification

- [ ] Deliverable 支持 submission/review 多版本并保留 accepted submission。
- [ ] Notification 明确 queued/sent/all-channels-success 完成策略。
- [ ] 失败、重试、取消与补偿进入统一 Capability Result。

### I4-E · 视频能力迁移

- [ ] 盘点 Runtime / TaskService 内 `run_kind`、`ui_profile` 与视频字段分支。
- [ ] 分批迁入 video handler / projection handler，保留黄金流程回归。
- [ ] 兼容依赖归零后再收窄 template `run_kind` dual-read。

## 4. 兼容与门禁

- 本阶段首批不改数据库 schema，不新增破坏性 API，不删除既有 executor 或兼容 JSON。
- Handler 返回纯结果，由 Runtime owner 应用状态；Handler 不直接写 `WorkflowNodeInstance`。
- Iteration 3-F 未完成前只开发、测试、shadow 验证，不做生产切流。
- 任何需要 schema/API 的后续批次仍按仓库协议单独评审。

## 5. I4-A 验收

- Registry 能稳定解析 HumanTask/Notice，未知/重复能力有确定错误。
- HumanTask 与 Notice 的 activate/complete/cancel/retry 映射有纯单测。
- `WorkflowGraphService` 的相关状态迁移消费统一 Capability Result，既有行为回归不变。
- I3-F 写所有权 AST guard、Backend 全量与 compileall 通过。
