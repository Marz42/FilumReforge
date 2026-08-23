---
type: paradigma-known-issue
title: "KI-009: Standalone Work Item 动作授权双轨"
description: "Standalone 详情和状态命令曾绕过 available_actions；工程修复与真实多账号 live UAT 已通过。"
tags: ["known-issue", "standalone", "available_actions", "task-center", "E2E"]
timestamp: "2026-08-23T22:55:00+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["standalone", "开始处理", "创建人", "available_actions", "C1.1", "旧契约"]
    en: ["standalone", "start_work", "creator", "available_actions", "legacy action"]
---

# KI-009: Standalone Work Item 动作授权双轨

> **当前状态**：🟢 **工程已修复，真实多账号 live UAT 已通过；业务人工签字仍按发布 checklist 执行**。
> **范围**：只收紧 **standalone** 路径；workflow / graph handshake 继续兼容，不纳入本 KI 的强制迁移。现行 Admin/HR override 不在本项修改，继续由 KI-011 单独治理。

## 现象（C1.1）

- L2（创建人）指派任务给 L4 后，任务正确出现在 L2 **任务跟踪**。
- 但 L2 打开详情仍可点击 **「开始处理」**，且后端会接受该状态变更。
- 按产品契约：TODO/DOING 执行责任属于 **assignee**；创建人在 REVIEW 前不应代开工。

## 根因（迁移不完整，非分桶错误）

P0 已落地：

- 后端 `task_action_policy` / 列表与详情 DTO 的 `available_actions`
- standalone 转办与候选接口按新契约

但详情主路径仍双轨：

| 层 | 旧逻辑 | 后果 |
|----|--------|------|
| 前端 `canAdvanceSelectedTask` | `creator \|\| assignee \|\| Admin/HR` | 创建人看到「开始处理」 |
| 前端 `NEXT_STATUS_ACTIONS` + `canAdvanceSelectedTaskByStatus` | 按 status 推按钮，不读 `available_actions` | 绕过契约 |
| 后端 `_can_operate_task` | 含 `creator_id` | 创建人 PATCH status 成功 |

新契约侧：`start_work` 仅 assignee 或 `task_admin_override`（ADMIN/HR）。创建人 L2 不在其中。

## 同批问题与修复结果

以下均属「standalone 详情曾使用旧启发式，未统一消费 `available_actions`」：

1. **开始处理**（TODO→DOING）：standalone 只在含 `start_work` 时显示；后端同步复核
2. **提交交付 / 提交评审**：standalone 只在含 `submit_deliverable` 时显示
3. **验收通过 / 打回**：standalone 只在含 `approve_deliverable` / `return_for_rework` 时显示
4. **后端状态命令授权**：`transition_task_status` 按当前阶段映射动作并使用同一 policy context 校验
5. **workflow 兼容防护**：workflow 任务仍使用原 handshake/Handler 判断，不把空 `available_actions` 当作无权限

转办按钮（standalone）已走新契约，**不在本 KI 必改清单内**。

## 已实施修复（2026-08-12）

按最小必要范围实施，不为修 standalone 顺带改写 workflow 契约：

1. `canUseTaskDetailAction()` 对 standalone 以 `available_actions` 为权威，对 workflow 保留显式 fallback
2. `transition_task_status()` 对 standalone 复用 `build_standalone_action_context()`；创建者关系不再等同于阶段执行权限
3. ADMIN/HR 继续通过现行 `task_admin_override` 显式进入 policy；是否移除由 KI-011 决定
4. test-first 回归覆盖创建者不能启动他人任务、standalone 空动作权威、单一动作授权和 workflow fallback

## 人工复测要求

1. L2 创建 standalone 并指派 L4：L2 在“跟踪”可见，但无“开始处理/提交”动作，直接调用状态接口也应被拒绝
2. L4 在“待处理”可开始并提交；进入 REVIEW 后 L2 可验收通过或打回
3. 打回后 L4 可再次提交，L2 可完成验收
4. 抽样一个 workflow 模板任务，确认接单、交付、验收按钮没有因空 `available_actions` 消失

工程修复部署后不再需要“创建者避免点击”的临时规避。

## 2026-08-23 自动化实证

隔离 PostgreSQL/Redis + 真实后端 + Chromium 串行切换 `demo.platform.lead`（创建者/验收人）与 `demo.engineer.a`（执行人），完成以下闭环：

1. 创建者发布并在 Tracking 可见，`available_actions=[]`，详情无“开始处理”按钮；
2. 执行人在 Inbox 可见并开始处理、提交交付物；
3. 任务进入 REVIEW 后创建者出现“验收通过”并完成任务；
4. 用例 `standalone-action-authorization-live.spec.ts` 1/1 通过，且运行在 5-E 严格投影模式（fallback=false）。

这条自动化已关闭工程复测缺口；真实员工业务语义确认仍不能由自动化代签。

## 关联

- P0 验收：`memory-bank/history/reports/p0-standalone-work-item-acceptance-20260717.md`
- 手工清单：`infra/docker/E2E-GUI-VERIFICATION.md` §C
- 代码：`frontend/src/components/task-detail/TaskDetailShell.vue`；`backend/app/services/task_service.py`（`_can_operate_task`）；`backend/app/services/task_action_policy.py`
