# 当前任务

> 🔥 HOT — 下一聚焦项请从 [`roadmap.md`](./roadmap.md) 选取并更新本文件。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | 任务中心 v2 重做 · **TC-P2**（视图拆分 + 任务统计） |
| **优先级** | P0 · 路线图下一焦点 |
| **状态** | TC-P2 **进行中** @ `feat/task-center-p2-views-stats`（Phase 0–3 已实现；P2-7 ui_profile 待做） |
| **关联** | [`plans/tc-p2-views-stats-plan.md`](./plans/tc-p2-views-stats-plan.md)（**P2 落地计划**）、[`plans/task-center-v2-implementation-plan.md`](./plans/task-center-v2-implementation-plan.md) §TC-P2、[`plans/workflow-video-v1-ui-simplification-design.md`](./plans/workflow-video-v1-ui-simplification-design.md) §11.3 |

---

## 当前阶段：TC-P2

| # | 工作项 | 状态 |
|---|--------|------|
| P2-1 | 路由 `/task-center/stats` 或 Tab「统计」 | 已完成 |
| P2-2 | `TaskCenterStatsView` | 已完成（MVP） |
| P2-3 | `TaskCenterListView.vue` | 已完成 |
| P2-4 | `TaskCenterBoardView.vue` | 已完成 |
| P2-5 | `TaskCenterGanttView.vue` | 已完成 |
| P2-6 | 详情迁出（引擎追踪 / 全量事件 → 统计页） | 已完成（v2 下隐藏 BatchRunDashboard；video 仅 3 条事件） |
| P2-7 | `config.ui_profile` | 未开始 |
| P2-8 | `TasksView` 瘦身 → 委托 `TaskDetailShell` | 已完成 |

---

## TC-P1 收尾（工程，非功能阻塞）

- [x] 提交 P1-7/P1-8 变更并合并 main @ `578c149`
- [ ] （可选）`git push origin main`
- [ ] （可选）live 多账号 E2E、Docker A–F 手工实测

---

## 验收清单（TC-P2 · = 设计 §11.3）

- [x] 三视图独立组件且与 Demo §7.2 一致
- [x] 统计入口可看全量事件与部门汇总
- [x] 详情仅保留最近 3 条事件摘要

---

选定子任务后：更新上表状态 → 执行 → 追加 `progress.md` 会话摘要。
