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

**in-progress · P0/P1/P3 已完成 · I4-B 已恢复 · P2 第一批已实现并持续接收**（2026-07-29）

本计划是 [`workflow-graph-engine-iteration4-handler-plan.md`](./workflow-graph-engine-iteration4-handler-plan.md) 的前置门禁。I4-A 已完成且不回退；以下事项收口后再恢复 I4-B。

## P0 · Memory-Bank 事实对齐

- [x] 将 `active-task` 从 I4-B 直接开发切换为 Preflight。
- [x] 修正 README、roadmap、project brief、data contracts 的版本、焦点与测试基线漂移。
- [x] 更新 Iteration 4 与视频领域文档，不再把视频业务 Handler 作为目标架构。
- [x] 新增 ADR-018，固定“视频流程是普通模板包”。
- [ ] 后续每批实现继续以代码、迁移和可运行测试为事实来源更新文档。

## P1 · 视频模板领域中立设计

- [x] 盘点后端 Runtime / TaskService / Task Center / API 中的 `run_kind`、模板 code、节点 key 和 `video_*` 分支。
- [x] 盘点前端详情 Profile、专用面板、动作按钮与状态投影中的视频推断。
- [x] 将现有行为映射为表单提交、集合关闭、聚合、交付/返工、子 Run 等通用能力候选。
- [x] 为兼容入口定义替代契约、黄金流程回归和退出条件；详见 [`视频模板领域中立迁移清单`](./2026-07-29-video-domain-neutral-migration-inventory.md)。
- [ ] 在兼容调用归零前不删除现有路径，不宣称领域中立迁移完成。

## P2 · 前端稳定化批次

- [x] 第一批 6 项反馈已接收并实现：铃铛一键已读、隐藏 AI 命令入口、任务列表双排序、详情字段拆分、全宽附件区、跟踪与历史精简列表行。
- [x] 第一批未发现数据/权限或错误推进问题；归入 P2 交互与 P3 视觉稳定化，不阻塞 I4-B 后端纵切。
- [x] 第一批通过 `vue-tsc --build`、production build 与前端全量 62 文件 / 174 项单测；使用 `123@example.com` 和 `admin@example.com` 完成真实登录态视觉 UAT。
- [ ] 后续反馈继续记录复现条件、期望行为、账号/数据上下文与验收标准，并按 P0–P3 即时分级。
- [ ] P0/P1 在恢复相关 I4 批次前修复；P2/P3 可独立成批，避免无限期阻塞后端演进。
- [ ] 涉及 `run_kind`、节点 key 或视频 Profile 的问题优先判断为投影/架构问题，不只做局部 CSS 修补。

## P3 · 决策对象与参与者重叠

用户已确认按 [`ADR-019`](../decisions/adr-019-decision-subject-actor-overlap.md) 纳入 Iteration 4 设计：不以用户 ID 相同一刀切，而是区分集合确认、独立交付验收、正式业务审批与多人会签。

- [x] `collection_finalize`：负责人可以同时是集合贡献者。
- [x] `deliverable_acceptance`：同一交付物/版本的提交者不得作为唯一验收人。
- [x] `business_approval`：申请人及决策对象贡献者不得批准。
- [x] `cosign`：可显式允许贡献者参与，但不得成为唯一决定者。
- [x] 严格策略无候选人时阻塞，不自动降级为 `self_review_fallback`。
- [x] 完成旧 completion policy、metadata、自审测试与 Deliverable contributor 事实入口盘点；I4-B 先落 `collection_finalize`，I4-C 再迁严格验收。

**范围排除**：系统管理员业务边界按 [`KI-011`](../known-issues/ki-011-system-admin-business-boundary.md) 延后，不在 I4 修改。

## 恢复 I4-B 的门禁

- [x] P0 文档对齐校验通过。
- [x] P1 形成可执行的领域中立迁移清单，并确认 I4 不新增 `VideoHandler`。
- [x] 前端第一批 6 项已实现且无 P0/P1；反馈入口继续开放，新增反馈按 P0–P3 即时分级。
- [x] 提交者/推进者重叠规则经用户确认并写入 ADR-019 / I4 计划。
- [ ] Iteration 3-F 生产切流门禁仍独立有效。
