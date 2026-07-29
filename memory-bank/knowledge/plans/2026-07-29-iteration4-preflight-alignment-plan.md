---
type: paradigma-plan
title: "Iteration 4 Preflight — 文档对齐、领域中立与前端稳定化"
description: "在 I4-B 前完成事实文档收口、视频模板去特殊化设计和前端问题分级；参与者重叠语义已由 ADR-019 固化。"
tags: ["plan", "workflow-graph", "iteration-4", "alignment", "frontend", "domain-neutral"]
timestamp: 2026-07-29T21:30:31+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["Iteration 4 前置", "文档漂移", "视频去特殊化", "前端问题分级"]
    en: ["iteration 4 preflight", "documentation alignment", "domain neutral workflow"]
---
# Iteration 4 Preflight — 对齐与稳定化计划

## 状态

**in-progress · 用户已批准 P0–P2 · I4-B 暂缓**（2026-07-29）

本计划是 [`workflow-graph-engine-iteration4-handler-plan.md`](./workflow-graph-engine-iteration4-handler-plan.md) 的前置门禁。I4-A 已完成且不回退；以下事项收口后再恢复 I4-B。

## P0 · Memory-Bank 事实对齐

- [x] 将 `active-task` 从 I4-B 直接开发切换为 Preflight。
- [x] 修正 README、roadmap、project brief、data contracts 的版本、焦点与测试基线漂移。
- [x] 更新 Iteration 4 与视频领域文档，不再把视频业务 Handler 作为目标架构。
- [x] 新增 ADR-018，固定“视频流程是普通模板包”。
- [ ] 后续每批实现继续以代码、迁移和可运行测试为事实来源更新文档。

## P1 · 视频模板领域中立设计

- [ ] 盘点后端 Runtime / TaskService / Task Center / API 中的 `run_kind`、模板 code、节点 key 和 `video_*` 分支。
- [ ] 盘点前端详情 Profile、专用面板、动作按钮与状态投影中的视频推断。
- [ ] 将现有行为映射为表单提交、集合关闭、聚合、交付/返工、子 Run 等通用能力候选。
- [ ] 为每个兼容入口定义替代契约、黄金流程回归和退出条件。
- [ ] 在兼容调用归零前不删除现有路径，不宣称领域中立迁移完成。

## P2 · 前端稳定化批次

- [ ] 接收用户逐项反馈，记录复现条件、期望行为、账号/数据上下文与验收标准。
- [ ] 按 P0 数据/权限/错误推进、P1 流程阻塞/状态错误、P2 交互、P3 视觉进行分级。
- [ ] P0/P1 在恢复相关 I4 批次前修复；P2/P3 可独立成批，避免无限期阻塞后端演进。
- [ ] 涉及 `run_kind`、节点 key 或视频 Profile 的问题优先判断为投影/架构问题，不只做局部 CSS 修补。

## P3 · 决策对象与参与者重叠

用户已确认按 [`ADR-019`](../decisions/adr-019-decision-subject-actor-overlap.md) 纳入 Iteration 4 设计：不以用户 ID 相同一刀切，而是区分集合确认、独立交付验收、正式业务审批与多人会签。

- [x] `collection_finalize`：负责人可以同时是集合贡献者。
- [x] `deliverable_acceptance`：同一交付物/版本的提交者不得作为唯一验收人。
- [x] `business_approval`：申请人及决策对象贡献者不得批准。
- [x] `cosign`：可显式允许贡献者参与，但不得成为唯一决定者。
- [x] 严格策略无候选人时阻塞，不自动降级为 `self_review_fallback`。
- [ ] 在 I4-B/I4-C 实施前盘点旧 completion policy、metadata 与测试的映射。

**范围排除**：系统管理员业务边界按 [`KI-011`](../known-issues/ki-011-system-admin-business-boundary.md) 延后，不在 I4 修改。

## 恢复 I4-B 的门禁

- [x] P0 文档对齐校验通过。
- [ ] P1 形成可执行的领域中立迁移清单，并确认 I4 不新增 `VideoHandler`。
- [ ] 已收到的前端 P0/P1 问题完成分级；阻塞项有明确处置。
- [x] 提交者/推进者重叠规则经用户确认并写入 ADR-019 / I4 计划。
- [ ] Iteration 3-F 生产切流门禁仍独立有效。
