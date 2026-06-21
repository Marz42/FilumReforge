# 当前任务

> 🔥 HOT — 下一聚焦项请从 [`roadmap.md`](./roadmap.md) 选取并更新本文件。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | 任务中心增强 · **TCE Phase 4**（多文案部门共用模板） |
| **优先级** | **P0** · 路线图下一焦点 |
| **状态** | **待启动** — Phase 3 ✅ @ 2026-06-21 |
| **关联** | [`plans/task-center-enhance.md`](./plans/task-center-enhance.md) §6、[`domains/task-center.md`](./domains/task-center.md) |
| **后置** | TCE Phase 5（TC-P3 + 清理） |

---

## 当前阶段：TCE Phase 4（下一）

**目标**：实例级发起部门 + 多文案部共用模板。

| # | ID | 工作项 | 状态 |
|---|-----|--------|------|
| 1 | **B-16** | 实例化 API 持久化 `department_id` + 参与人池 | 未开始 |
| 2 | **F-17** | 实例化 Dialog 完整交互（§6.2.1） | 未开始 |

---

## Phase 3 完成摘要 ✅

| # | ID | 工作项 |
|---|-----|--------|
| 1 | B-06 | `stats/summary` + `stats/workload` 支持 `department_id` 与权限校验 |
| 2 | B-09 | inbox/tracking/history cursor 分页 + `/task-center/{inbox,tracking,history}` |
| 3 | B-11 | `GET /workflow-graph/runs?department_id=` 部门 Run 一览 |
| 4 | F-05 | 抽出 `TaskDetailActionDialogs.vue`（Shell 对话框拆分第一步） |
| 5 | F-06 | 统计页部门筛选 + Run 列表/事件 |
| 6 | F-09 | 看板 Run 筛选下拉 |

---

## Phase 2 完成摘要 ✅

| # | ID | 工作项 |
|---|-----|--------|
| 1 | B-04 | `GET /tasks?ids=` batch hydration |
| 2 | B-05 | snapshot `run_label` + `user_facing_state` |
| 3 | B-07 | tracking inbox 去重 |
| 4 | F-01/F-04/F-07 | batch hydration、搜索用户态、Run 标签 |

---

## 后续阶段（概览）

| 阶段 | 主题 | 入口 |
|------|------|------|
| Phase 4 | 多文案部门共用模板（B-16, F-17 §6.2.1） | enhance §6 |
| Phase 5 | TC-P3 + 清理（B-12–B-15, F-13–F-16） | enhance §2 P3 |

---

## Phase 3 验收 ✅

- [x] 非 Admin 仅能查 managed 部门统计（B-06）
- [x] snapshot 返回 pagination；列表可 load more（B-09）
- [x] 统计页 Run 来自 `/workflow-graph/runs`（B-11 / F-06）
- [x] 看板 Run 筛选（F-09）
- [x] pytest `test_tce_phase3_admin_stats_pagination.py` + Phase 1–2 回归；vitest TaskCenter 13/13

选定子任务后：更新 Phase 4 表状态 → 执行 → 测试 → commit → 追加 `progress.md`。
