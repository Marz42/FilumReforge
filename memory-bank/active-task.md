# 当前任务

> 🔥 HOT — 下一聚焦项请从 [`roadmap.md`](./roadmap.md) 选取并更新本文件。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | 任务中心增强 · **TCE Phase 2**（性能 + 读模型一致） |
| **优先级** | **P0** · 路线图下一焦点 |
| **状态** | **待启动** — Phase 1 ✅ @ 2026-06-21 |
| **关联** | [`plans/task-center-enhance.md`](./plans/task-center-enhance.md)、[`domains/task-center.md`](./domains/task-center.md) |
| **后置** | TCE Phase 2–5；**TC-P3**（E 与图引擎统一）见 enhance **Phase 5** |

---

## 当前阶段：TCE Phase 2（下一）

**目标**：batch hydration、snapshot 读模型字段、tracking 去重。

| # | ID | 工作项 | 状态 |
|---|-----|--------|------|
| 1 | **B-04** | batch tasks API | 未开始 |
| 2 | **B-05** | snapshot `run_label` + `user_facing_state` | 未开始 |
| 3 | **B-07** | tracking/inbox 去重收敛 | 未开始 |
| 4 | **F-01** | workspace batch hydration | 未开始 |
| 5 | **F-04** | 搜索用户态投影 | 未开始 |
| 6 | **F-07** | Run 标签读 `context.run_label` | 未开始 |

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
| Phase 2 | 性能 + 读模型一致（B-04–B-07, F-01, F-04, F-07） | enhance §4 |
| Phase 3 | 管理端 + 可维护（B-06, B-09–B-11, F-05, F-06, F-09） | enhance §4 |
| Phase 4 | 多文案部门共用模板（B-16, F-17 §6.2.1） | enhance §6 |
| Phase 5 | TC-P3 + 清理（B-12–B-15, F-13–F-16） | enhance §2 P3 |

---

## 前置（已完成）

- [x] TC-P0–P2 @ `0.88.0`–`0.89.0`（三视图 + 统计 + Shell + 图模板单入口）
- [x] 增强排期落盘 + 多部门方案 §6.2.1 确认
- [x] memory-bank 全量对齐 @ 2026-06-21

---

## Phase 1 验收 ✅

- [x] N1 完成后待办与图节点 DONE 一致（B-01）
- [x] 图操作后 refresh（F-08）
- [x] 看板显示姓名（F-02）
- [x] department 迁移脚本（B-03）
- [x] pytest `test_tce_phase1_graph_projection_inbox.py`

选定子任务后：更新 Phase 2 表状态 → 执行 → 测试 → commit → 追加 `progress.md`。
