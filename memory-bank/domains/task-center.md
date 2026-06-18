# 领域：任务中心 (Task Center)

> 🌡️ WARM — 涉及待办/跟踪/历史、Inbox、备忘、多视图时读取。

**关联 schema**: `data-contracts.md` §10.14–10.18B、§10.23–10.25 · **UI**: `handbooks/user-manual.md`

---

## 职责边界

| 能力 | 说明 |
|------|------|
| Inbox-first | 主标签：待处理 / 跟踪 / 历史 |
| 建立任务 | 页头 Dialog；graph 手动任务 dual-write |
| 搜索 | `GET /api/v1/tasks/search` |
| 多视图 | 列表 / 看板 / 甘特独立组件（**用户态 × Run**）；`filter=stats` 任务统计 Tab — TC-P2 ✅ @ `0.88.0` |
| 个人备忘 | 全局浮窗；`task_memos` |
| 任务模板入口 | `/task-templates` — 图模板列表 + 实例化（@ `0.89.0` 统一命名；Legacy E UI 已移除） |

---

## 读路径（graph-first）

`TASK_CENTER_V2_ENABLED=true`（默认）时：

`TaskCenterService` → `TaskService.list_task_inbox/tracking/history` → `_graph_task_projection_map` → 未命中则 legacy fallback

---

## 任务状态机

严格：`Todo → Doing → Review → Done`  
图手动任务另有握手（接单/协商/转办）与交付/验收/返工动作，不可跳过。

详见 `architecture.md` §6.2、§6.13、§6.13B。

---

## 关键代码

| 路径 | 作用 |
|------|------|
| `backend/app/services/task_center_service.py` | 任务中心聚合 |
| `backend/app/services/task_service.py` | 状态机、评论、图投影 |
| `backend/app/api/routes/task_center.py` | 任务中心 API |
| `frontend/src/views/TaskCenterView.vue` | 主壳层：filter（inbox/tracking/history/stats）+ view（list/board/gantt）+ Master-Detail |
| `frontend/src/views/TasksView.vue` | v2 工作区壳层（~700 行）；详情委托 `TaskDetailShell` |
| `frontend/src/components/task-center/TaskCenterListView.vue` | 列表视图（Run + 用户态列） |
| `frontend/src/components/task-center/TaskCenterBoardView.vue` | 看板（列=用户态，卡片含 Run chip） |
| `frontend/src/components/task-center/TaskCenterGanttView.vue` | 甘特 MVP（`due_at` + Run 色条） |
| `frontend/src/components/task-center/TaskCenterStatsView.vue` | 任务统计（部门汇总 + run_events + 负载表） |
| `frontend/src/components/task-detail/TaskDetailShell.vue` | 详情 Shell：header / profile 面板 / 最近 3 条事件 |
| `frontend/src/components/task-detail/TaskDetailMoreMenu.vue` | 更多菜单：打回 / 退回 / 打开任务统计 |
| `frontend/src/components/` | `FilumDateTimePicker` 等 |

---

## 与图引擎关系

列表/详情可能展示 graph 节点状态、V{n} 角标、交付/返工信号；打开图任务时 fetch `getWorkflowGraphInstance`。

见 [`workflow-graph-engine.md`](./workflow-graph-engine.md)。

---

## 测试锚点

- `data-testid`: `TaskCenterView`、`TasksView` 等（Phase 11-G）
- Playwright: `frontend/playwright.config.ts`、`playwright.live.config.ts`
