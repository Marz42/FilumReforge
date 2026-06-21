# 当前任务

> 🔥 HOT — 下一聚焦项请从 [`roadmap.md`](./roadmap.md) 选取并更新本文件。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | 任务中心增强 · **TCE Phase 3**（管理端 + 可维护） |
| **优先级** | **P0** · 路线图下一焦点 |
| **状态** | **待启动** — Phase 2 ✅ @ 2026-06-21 |
| **关联** | [`plans/task-center-enhance.md`](./plans/task-center-enhance.md)、[`domains/task-center.md`](./domains/task-center.md) |
| **后置** | TCE Phase 4–5；**TC-P3**（E 与图引擎统一）见 enhance **Phase 5** |

---

## 当前阶段：TCE Phase 3（下一）

**目标**：管理端筛选、统计口径、可维护性。

| # | ID | 工作项 | 状态 |
|---|-----|--------|------|
| 1 | **B-06** | 管理端 snapshot 筛选 API | 未开始 |
| 2 | **B-09** | tracking 关系类型后端聚合 | 未开始 |
| 3 | **B-10** | stats 口径与 snapshot 对齐 | 未开始 |
| 4 | **B-11** | 列表字段 schema 文档化 | 未开始 |
| 5 | **F-05** | 管理端筛选 UI | 未开始 |
| 6 | **F-06** | stats 视图读 snapshot | 未开始 |
| 7 | **F-09** | workspace 错误/空态统一 | 未开始 |

---

## Phase 2 完成摘要 ✅

| # | ID | 工作项 |
|---|-----|--------|
| 1 | B-04 | `GET /tasks?ids=` + `list_tasks_by_ids`（上限 100） |
| 2 | B-05 | snapshot `run_label` + `user_facing_state`（`task_user_facing_state.py`） |
| 3 | B-07 | tracking 传入 inbox exclusion，去掉 `limit*2` 二次 inbox |
| 4 | F-01 | workspace `listTasksByIds` batch hydration |
| 5 | F-04 | 搜索列用户态标签 |
| 6 | F-07 | Run 标签优先 snapshot / `context.run_label` |

---

## Phase 1 完成摘要 ✅

| # | ID | 工作项 |
|---|-----|--------|
| 1 | B-01 | graph 读路径扩展到节点投影任务 |
| 2 | B-03 | `migrate_graph_projection_task_departments.py` |
| 3 | B-02 | inbox/tracking SQL 候选集 LIMIT |
| 4 | F-08 | 详情 `@action-done` → refresh |
| 5 | F-02 | 看板 assigneeLabel |
| 6 | F-03 | 实例化发起部门（默认 + 可改） |

---

## 后续阶段（概览）

| 阶段 | 主题 | 入口 |
|------|------|------|
| Phase 3 | 管理端 + 可维护（B-06, B-09–B-11, F-05, F-06, F-09） | enhance §4 |
| Phase 4 | 多文案部门共用模板（B-16, F-17 §6.2.1） | enhance §6 |
| Phase 5 | TC-P3 + 清理（B-12–B-15, F-13–F-16） | enhance §2 P3 |

---

## 前置（已完成）

- [x] TC-P0–P2 @ `0.88.0`–`0.89.0`（三视图 + 统计 + Shell + 图模板单入口）
- [x] 增强排期落盘 + 多部门方案 §6.2.1 确认
- [x] memory-bank 全量对齐 @ 2026-06-21
- [x] TCE Phase 1 @ 2026-06-21
- [x] TCE Phase 2 @ 2026-06-21

---

## Phase 2 验收 ✅

- [x] workspace 仅 batch 拉可见任务（F-01 / B-04）
- [x] snapshot / 搜索含 `run_label` + `user_facing_state`（B-05 / F-04 / F-07）
- [x] tracking 不再重复 inbox 候选（B-07）
- [x] pytest `test_tce_phase2_batch_and_snapshot.py` + Phase 1 回归；vitest TaskCenter 13/13

选定子任务后：更新 Phase 3 表状态 → 执行 → 测试 → commit → 追加 `progress.md`。
