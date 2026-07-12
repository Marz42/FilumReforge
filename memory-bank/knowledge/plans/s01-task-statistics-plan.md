---
type: paradigma-plan
title: "S-01 任务统计实施计划（已批准）"
description: "Project Filum 任务中心最小周期统计：权限、功能、口径、时间与实施阶段。"
tags:
  - plan
  - task-center
  - statistics
timestamp: 2026-07-11T23:34:27+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: decision
  retrieval_hints:
    zh:
      - S-01
      - 任务统计计划
      - 统计口径
    en:
      - task statistics
      - statistics plan
---
# S-01 任务统计实施计划（已批准）

> 2026-07-11：用户已确认 §10 六项默认决策，进入实施。

## 1. 目标与边界

在任务中心现有「统计」Tab 上提供可核对的周期统计，帮助员工了解本人任务，帮助经理/Admin/HR 了解授权范围内的任务负载和逾期情况。

首版只做：**周期筛选、摘要指标、人员负载、明细下钻**。使用数字卡片和表格，不做复杂图表、个人排名、绩效打分、导出或缓存。

## 2. 权限

| 角色 | 可见范围 | 人员负载表 |
|------|----------|------------|
| Employee | 仅本人任务 | 仅本人一行 |
| 部门经理 | 自己管理的部门及子树；可切换具体部门 | 可见授权范围内成员 |
| Admin / HR | 全公司；可切换部门及子树 | 可见所选范围内成员 |
| 有效数据访问代理 | 叠加委托人的授权部门范围 | 与代理范围一致 |

规则：权限全部由后端校验；普通员工不能通过传 `department_id` 查看同部门其他人。首版不展示质量评分、返工排名或绩效分。

## 3. 时间规则

- 默认周期：**本月**。
- 快捷选项：本周、本月、上月；支持自定义日期，最长 366 天。
- 业务时区：**Asia/Shanghai**；数据库仍存 UTC。
- UI 的开始/结束日期均含当天；后端转换为 `[开始日 00:00, 结束日次日 00:00)`。
- 周：周一至周日；月：自然月。
- 历史周期按 `created_at`、`completed_at`、`due_date` 复算，不依赖当前页面状态。

## 4. 统计对象与去重

- 单步任务：每个 `tasks.id` 计 1 个任务。
- 图任务：每个可执行节点的兼容 Task 投影计 1 个任务。
- `workflow_graph_root_task=true` 的 Run 壳任务不计入任务指标，Run 仍在现有 Run 区域观察。
- 管理员归档任务（`admin_archived=true`）不计入。
- 同一任务只按唯一 `tasks.id` 计一次；评论、附件、返工迭代不增加任务数。
- 无截止时间任务计入新增/完成/当前未完成，但不进入到期、逾期和按期完成率。

## 5. 指标口径

| 指标 | 定义 |
|------|------|
| 新增任务 | `created_at` 落在周期内 |
| 完成任务 | `completed_at` 落在周期内 |
| 到期任务 | `due_date` 落在周期内 |
| 逾期任务 | 到期任务中，完成时间晚于截止时间；或截止时间已过仍未完成 |
| 按期完成率 | 已到截止时点的任务中，`completed_at <= due_date` 的比例；尚未到期任务不进入分母 |
| 当前未完成 | 查询时仍为 Todo / Doing / Review 的任务 |

人员负载表展示：人员、当前未完成、新增、完成、到期、逾期、按期完成率。它是工作量观察，不是绩效排名。

## 6. 页面功能

1. 顶部筛选：周期、范围（本人/部门）、是否包含子部门。
2. 五个摘要数字：新增、完成、到期、逾期、按期完成率。
3. 人员负载表；点击人员或摘要数字打开明细表。
4. 明细字段：任务标题、执行人、部门、来源、Run、截止时间、完成时间、是否逾期；点击进入现有任务详情。
5. 保留现有部门 Run 与事件时间线，不在 S-01 首版扩展。

不做：趋势图、饼图、排行榜、绩效分、Excel 导出、定时报表。

## 7. 后端与 API

优先扩展现有接口，保持向后兼容：

- `GET /tasks/stats/summary`
- `GET /tasks/stats/workload`
- 新增 `GET /tasks/stats/details`（分页明细）

统一参数：`start_date`、`end_date`、`department_id?`、`include_subtree=false`；明细另加 `metric`、`assignee_id?`、`cursor?`、`limit`。

统计改为 SQL/数据库侧聚合，不再先 `list_tasks()` 全量加载后用 Python 计数。首版预计不新增表；根据查询计划决定是否补 `created_at` / `completed_at` 索引，若需要则单独提交 Alembic 迁移并更新契约。

## 8. 实施阶段与时间

| 阶段 | 内容 | 预计 |
|------|------|------|
| 0. 契约与测试样例 | 固化权限、时区、口径、API 响应与边界样例 | 0.5 天 |
| 1. 后端 | DB 侧 summary/workload/details、权限与分页 | 1.5–2 天 |
| 2. 前端 | 筛选、数字卡、负载表、明细下钻 | 1–1.5 天 |
| 3. 回归与文档 | pytest、Vitest、Playwright smoke、memory-bank | 1 天 |

合计：约 **4–5 个工作日**。每阶段完成后更新 progress；API/schema 事实同步 data-contracts/architecture。

## 9. 验收

- 员工只能看到本人；经理只能看到管理范围；Admin/HR 可查看全局。
- 本周/本月/上月与自定义日期边界在 Asia/Shanghai 下正确。
- 无截止、尚未到期、按期完成、晚完成、过期未完成、归档、Run ROOT 均有直接测试。
- 摘要、人员表和明细可逐条复算一致。
- 统计查询不加载全部可见 Task ORM 对象。
- 前端不新增复杂图表；移动/窄屏下表格仍可使用。

## 10. 审批项

请确认以下默认决策：

1. Employee 仅看本人，不看同部门汇总。
2. 默认本月，周从周一开始，时区 Asia/Shanghai。
3. 使用“按期完成率”，不使用模糊的“完成率”。
4. Run ROOT 不计任务数；可执行节点 Task 计数。
5. 首版无排名、评分、导出和复杂图表。
6. 预计 4–5 个工作日，按契约 → 后端 → 前端 → 回归推进。

## 11. 实施状态

**implemented · pending UAT** @ 2026-07-11：Phase 0–3 已完成；后端全量、前端全量与 Playwright stats 专项通过，等待用户验收。
