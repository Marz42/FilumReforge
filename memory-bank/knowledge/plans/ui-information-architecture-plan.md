---
type: paradigma-plan
title: "UI IA 计划"
description: "UI IA Phase A–F 实施计划。"
tags:
  - plan
  - UI
  - IA
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh:
      - UI
      - IA
    en:
      - ui
      - ia
---
# UI 信息架构重构规划（里程碑）

本文件为 UI 重构里程碑总览；**IA-0…IA-5（Phase A–F）已于 2026-05 交付**，细节见 [`ui-refactor-spec-v2.md`](./ui-refactor-spec-v2.md) 与用户说明书 [`knowledge/manuals/user-manual.md`](../manuals/user-manual.md) v1.1。

## 1. 目标

- 降低「同一能力多入口、多命名」带来的认知成本。
- 让**任务**、**汇报**、**人员**、**消息**四条主线的动线在壳层导航与页面内 Tab 上更可预测。
- 为 Playwright 保留或补充稳定 `data-testid`，避免纯文案定位。

## 2. 原痛点与当前状态（2026-05）

以下痛点已在 Phase A–F 中处理；保留条目供回归对照。

| 原痛点 | 当前实现 |
| --- | --- |
| 任务中心四 Tab 割裂 | Quick Chips（inbox/tracking/history）+ Master-Detail；模板迁 `/task-templates`，备忘为全局浮窗 |
| 汇报两步发起 | 单一「撰写汇报」Drawer，收件人下拉隐式方向 |
| 人员五 Tab 详情 | 列表 + 宽 Drawer + 锚点导航（`detailTab` 深链） |
| 消息占侧栏 | 顶栏铃铛 Drawer + `/messages` 全页；总览消息预览 widget |

## 3. 分期建议

> **v2 细化**：逐步实施步骤、组件拆分、URL 迁移与 E2E 清单见 **[`ui-refactor-spec-v2.md`](./ui-refactor-spec-v2.md)**（Phase A–F）。下表保留里程碑编号与 v2 阶段映射。

| 阶段 | 范围 | 产出 | v2 映射 |
| --- | --- | --- | --- |
| IA-0 | 走查 + 用户动线文档 | **已完成**：[`knowledge/manuals/user-manual.md`](../manuals/user-manual.md) v1 + 审阅批注 | — |
| IA-1 | 登录、设置、壳层、消息降级 | 三场景登录、设置三分栏、铃铛 Drawer、侧栏去消息 | Phase A + B |
| IA-2 | 任务中心 | Quick Chips + Master-Detail；模板/备忘迁出 | Phase C |
| IA-3 | 汇报中心 | Master-Detail + 「撰写汇报」抽屉 | Phase D |
| IA-4 | 人员、部门、总览 | 人员宽抽屉；部门树；Dashboard 小组件 | Phase E + F **done** |

## 4. 与测试的协调

- 任何导航或 `data-testid` 变更需同步更新：`frontend/e2e/docker-gui-verification/`、`frontend/e2e/task-center.spec.ts`、`infra/docker/E2E-GUI-VERIFICATION.md`。
- 优先在 **IA-0** 冻结一版「锚点清单」，再动 UI。

## 5. 非目标（本里程碑）

- 不改变后端领域模型与 API 契约（除非配合 UX 必须增加字段）。
- 不与图引擎 / 工作流 E 运行时合并同一次发布。
