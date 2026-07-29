---
type: paradigma-decision
title: "ADR-018: 工作流模板领域中立 — 视频流程作为普通模板包"
description: "图引擎只承载通用工作流能力；视频流程作为模板配置、种子数据与呈现扩展，不成为 Runtime 特殊类型。"
tags: ["adr", "workflow-graph", "domain-neutral", "video-template", "handler"]
timestamp: 2026-07-29T21:30:31+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["工作流领域中立", "视频普通模板", "去视频特殊化", "通用能力"]
    en: ["domain neutral workflow", "video template pack", "remove video special cases"]
---
# ADR-018: 工作流模板领域中立 — 视频流程作为普通模板包

**日期**：2026-07-29
**状态**：已采纳；兼容迁移待实施
**关联**：[`adr-017-template-engine-decouple.md`](./adr-017-template-engine-decouple.md) · [`workflow-graph-engine-iteration4-handler-plan.md`](../plans/workflow-graph-engine-iteration4-handler-plan.md)

## 背景

视频工作流 v1 以选题会、多人采集、汇总、按题 fork、制作交付和返工验证了图引擎纵向能力，但当前 Runtime、TaskService、任务中心投影和前端详情仍按 `run_kind`、模板/节点编码及 `video_*` UI Profile 分支。这使一个业务模板获得了引擎级特殊性，并扩大了模板设计器与通用运行时的耦合。

ADR-017 已废弃模板级 `run_kind` 产品类型。本 ADR 进一步固定运行时边界：视频流程是普通图模板包，不是新的引擎节点类型或领域 Handler。

## 决策

1. **图引擎领域中立**：Runtime 只识别通用节点、状态、路径、上下文、交付、审批、通知、聚合与子 Run 等能力，不识别“视频”“选题”“制作”等业务词汇。
2. **视频作为模板包**：视频流程的节点、表单 schema、部门池、模板链、文案与默认配置保留在模板种子/导出包及业务示例中。
3. **不新增 `VideoHandler`**：Iteration 4 不通过业务专用 Handler 延续特殊性。需要抽取的行为必须先命名为可被其他模板复用的通用能力。
4. **呈现与行为分离**：`ui_profile` 可选择前端渲染组件，但不得决定 Runtime 状态迁移、权限、归档、通知或可实例化能力；核心后端不维护业务专用 UI Profile 枚举作为行为依据。
5. **兼容迁移而非一次删除**：现有视频 API、service、`run_kind` dual-read 和前端专用面板先作为兼容层保留；通过依赖盘点、通用能力抽取、双轨回归和调用归零后再删除。
6. **模板不靠名称驱动行为**：模板 code、节点 key、tags 和展示文案不得成为核心运行时分支条件。

## 通用能力候选

- 结构化表单提交与校验
- 多参与者采集与集合关闭
- 聚合确认与结果映射
- Deliverable 多版本提交、验收与返工
- 子模板 / 子 Run 派生及幂等
- 参与者解析、部门池与通知

候选项只有在契约可跨业务复用并通过评审后，才进入 Handler 或应用服务；本 ADR 不预先规定必须新增哪些节点类型。

## 后果

- **正面**：新业务可复用同一引擎；视频垂直流程不再污染核心语义；前后端能力边界更稳定。
- **成本**：需要迁移现有视频专用路由、service、状态投影和前端面板；兼容期会暂时保留双路实现。
- **约束**：不得以“先搬进 VideoHandler、以后再通用化”作为过渡完成态。
- **非目标**：本次不删除视频功能、不改模板数据、不立即改变公共 API，也不取消针对视频模板包的 E2E 黄金流程。

## 验收方向

- 通用 Runtime / TaskService 不再按 `run_kind`、模板 code 或节点 key 识别视频流程。
- 视频模板仍能通过通用能力完成现有黄金流程。
- 视频专用兼容入口有明确调用计数、替代契约与退出条件。
- 新增另一类非视频模板可复用同一表单、聚合、子 Run 与返工能力，无需修改 Runtime。
