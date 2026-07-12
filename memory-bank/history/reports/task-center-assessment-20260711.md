---
type: paradigma-assessment
title: "任务中心实现探索与下一步建议（2026-07-11）"
description: "基于当前前后端实现、测试和主计划，对任务中心的产品与工程优先级给出建议。"
tags:
  - assessment
  - task-center
  - stats
timestamp: 2026-07-11T22:11:25+08:00
paradigma:
  schema_version: 0.5.0
  temperature: cold
  lifecycle: append-only
  update_policy: append-only
  epistemic_status: confirmed
---
# 任务中心实现探索与下一步建议

## 结论

当前任务中心不是缺一个新壳层，而是已经具备可用的 inbox / tracking / history、列表/看板/甘特、任务详情、单步发布和基础统计。下一产品主线应继续以 implementation-plan 的 **S-01 任务统计**为准，但第一步不是增加图表，而是建立可解释、可扩展的统计读模型与口径契约。

建议顺序：**S-01 口径与 DB 侧聚合 → 统计体验闭环 → 搜索/列表一致性 → F-05 组件拆分**。绩效语义应最后确认，不宜直接用任务数量或完成率评价个人。

## 当前实现事实

| 区域 | 当前事实 | 证据 |
|------|----------|------|
| 聚合入口 | `GET /task-center` 一次返回权限、模板、发布选项、三类各 50 条列表和备忘 | `backend/app/services/task_center_service.py` |
| 工作区 | 前端再按 snapshot ID 批量拉取完整 Task，投影为列表/看板/甘特 | `frontend/src/composables/useTaskCenterWorkspace.ts` |
| 搜索 | 独立 `/tasks/search`，不继承当前 inbox/tracking/history 过滤；前端补造部分展示字段 | `TaskCenterView.vue` · `tasks.py` |
| 统计 | summary/workload 支持可选部门，无时间范围/粒度；服务先 `list_tasks()` 再 Python 聚合 | `TaskService.get_task_stats_summary/get_task_workload` |
| Run 观察 | 部门 Run 列表 + 单 Run 事件时间线已可用 | `TaskCenterStatsView.vue` |
| 甘特 | 仅展示有 due_date 的任务，起点取 started_at/created_at；不展示依赖或关键路径 | `TaskCenterGanttView.vue` |
| 复杂度 | `TaskCenterView.vue` 951 行；`TaskDetailShell.vue` 1841 行 | 当前源码行数 |
| 测试 | stats 后端有基础 API/service/权限测试；前端 StatsView 无直接组件测试 | `backend/tests` · `frontend/tests` |
| 设计基准 | 根 `DESIGN.md` 仍是空模板，当前只能沿用已有 Filum token/组件习惯 | `DESIGN.md` |

## 推荐实施顺序

### P0：先完成 S-01 口径卡与读模型契约

产品需确认四件事：

1. 时间口径：按创建、截止、完成中的哪一个归属周期；跨周期未完成任务如何计算。
2. 粒度：首版建议日/周/月，不先做季度专属逻辑；API 使用明确的 `date_from` / `date_to` / `grain`。
3. 组织范围：部门自身还是部门子树；员工仅看自己、经理看管理子树、Admin/HR 的全局范围需明确。
4. 状态口径：归档/取消、图 ROOT、节点 Task、单步 Task 如何去重；逾期以周期结束时快照还是当前状态计算。

工程上应新增 DB 侧聚合查询/读模型，避免 `list_tasks()` 全量加载后在 Python 计数。首版返回 `period + scope + counts + rates`，并保留口径版本字段，测试覆盖时区边界、空周期、跨周期、取消/归档和权限范围。

### P1：完成统计页面的可用闭环

- 周期、部门范围和 Run 选择进入 URL query，支持分享和刷新恢复。
- summary、workload、runs 分离 loading/error，不使用一个 `loading` 覆盖三组并发请求。
- 增加趋势图前先提供可核对的明细下钻；所有指标可跳回对应任务集合。
- 为 `TaskCenterStatsView` 增加直接 Vitest，覆盖部门切换、空状态、失败和竞态；增加一个 Playwright stats smoke。
- 绩效只做“入口/辅助证据”，不直接产出个人排名；若要 KPI，需另立产品与权限决策。

### P1：统一搜索与列表语义

当前搜索跨越所有可见任务，且返回结构缺 due_date/run/relation 等字段，前端以占位值补造。建议让搜索 API 接收 `filter`、`cursor` 和必要范围参数，并直接返回统一的 Task Center row read model，避免搜索结果与当前 Tab 标签、排序、分页不一致。

### P2：收敛首屏载荷与前端状态

对 50–100 人规模当前 snapshot 尚可工作，但它同时预取三类列表，随后又进行 Task hydration。建议将 bootstrap 元数据（权限/发布选项）与活动 Tab 分页拆开，或让分页接口直接返回工作区所需完整 row，减少首屏无用数据与双请求。实施前先用真实内测数据测量响应体和查询数。

### P2：执行 F-05 拆分

- `TaskCenterView`：提取 route/query 控制、搜索、分页和督办/延期动作 composable。
- `TaskDetailShell`：按 action profile 拆为基础详情、握手、交付/验收、图运行态、视频专用面板；保留一个薄 orchestrator。
- 拆分必须保持现有 graph-first/user-facing-state 行为，并以现有 144 个前端测试和 Playwright 35/35 为回归基线。

### P3：重新命名或深化“甘特”

当前实现更接近“起止时间条”，没有依赖、时间刻度、关键路径或排程编辑。短期可命名为“时间线”；若保留“甘特”，应补依赖线、时间轴缩放、无截止任务策略和可访问性。

## 不建议现在做

- 不先增加个人绩效排行榜。
- 不为统计引入第二套任务事实表而绕过 graph-first 投影。
- 不在没有真实响应体/查询测量前提前做缓存。
- 不把 F-05 大拆分与 S-01 schema/API 同一个提交混做。

## 验收建议

S-01 第一批以“一个经理查看某部门某周：总量、完成、逾期、状态分布、人员负载，并能下钻到一致任务集合”为闭环。指标结果需能由明细逐条复算；权限、时区、取消/归档、ROOT/节点去重均有直接回归。
