---
type: paradigma-known-issue
title: "KI-009: Standalone Work Item 详情动作仍走旧契约"
description: "P0 已引入 available_actions，但 standalone 详情主按钮与部分后端状态权限仍允许创建人代执行，干扰 C 业务闭环验收。"
tags: ["known-issue", "standalone", "available_actions", "task-center", "E2E"]
timestamp: "2026-07-20T14:44:00+08:00"
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

# KI-009: Standalone Work Item 详情动作仍走旧契约

> **处置节奏**：先记档，等 **C. 业务闭环**（`E2E-GUI-VERIFICATION.md` C1.x）人工排查完成后再统一修复。  
> **范围**：只收紧 **standalone** 路径；workflow / graph handshake 继续临时双轨，不纳入本 KI 的强制迁移。

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

## 类似问题（同一批待修）

以下均属「standalone 详情仍用旧启发式，未统一消费 `available_actions`」：

1. **开始处理**（TODO→DOING）：创建人可点 — **已确认**
2. **提交交付 / 提交评审**：`canSubmitDeliverable` 仍本地判断 assignee，未读契约（碰巧较接近正确）
3. **验收通过 / 打回**：`canReviewDeliverable` 仍本地判断 creator，未读契约（碰巧较接近正确）
4. **后端状态命令授权**：`transition_task_status` 走 `_can_operate_task`，与 `available_actions` 不一致
5. **防护缺口**：workflow 任务 `available_actions` 常为空；若误把空列表当「无操作」会坏图任务（修复 standalone 时须保留双轨判定）

转办按钮（standalone）已走新契约，**不在本 KI 必改清单内**。

## 建议修复（待 C 闭环排查结束后）

最小必要，不为进 I4 做全量 workflow 迁契约：

1. standalone 详情：「开始处理 / 提交交付 / 验收」只认 `available_actions`
2. standalone 后端：状态变更/提交与契约一致（创建人不能代开工；ADMIN/HR 若保留则显式 override）
3. 保留：`execution_mode === 'workflow'` → legacy graph 路径
4. 补回归：C1.1 创建人跟踪可见且无 `start_work`；L4 待处理有 `start_work`

## 验收时临时规避

- C1.1：L2 只建任务并确认跟踪可见；**不要用 L2 点「开始处理」**
- C1.2+：用 **L4** 账号开工与提交

## 关联

- P0 验收：`memory-bank/history/reports/p0-standalone-work-item-acceptance-20260717.md`
- 手工清单：`infra/docker/E2E-GUI-VERIFICATION.md` §C
- 代码：`frontend/src/components/task-detail/TaskDetailShell.vue`；`backend/app/services/task_service.py`（`_can_operate_task`）；`backend/app/services/task_action_policy.py`
