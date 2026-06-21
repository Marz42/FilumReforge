# 当前任务

> 🔥 HOT — 下一聚焦项请从 [`roadmap.md`](./roadmap.md) 选取并更新本文件。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | 任务中心增强 · **TCE Phase 5**（TC-P3 + 清理） |
| **优先级** | **P0** · 路线图下一焦点 |
| **状态** | **待启动** — Phase 4 ✅ @ 2026-06-21 |
| **关联** | [`plans/task-center-enhance.md`](./plans/task-center-enhance.md) §2 P3、§7 后续待办 |
| **后置** | —（TCE 主体收尾） |

---

## 当前阶段：TCE Phase 5（下一）

**目标**：Legacy E 与图引擎统一、清理与收尾。

| # | ID | 工作项 | 状态 |
|---|-----|--------|------|
| 1 | **B-12** | TC-P3-1：E 与图引擎统一 | 未开始 |
| 2 | **B-13** | TC-P3-2：`aggregate_mode` | 未开始 |
| 3 | **B-14** | TC-P3-3：「结束采集」API | 未开始 |
| 4 | **B-15** | 后端统一 `user_facing_state` | 未开始 |
| 5 | **F-13–F-16** | 前端清理与 Legacy 移除 | 未开始 |

---

## 移出 TCE 范围（后续待办）

| ID | 工作项 | 说明 |
|----|--------|------|
| **F-05** | `TaskDetailShell.vue` 完整拆分 | 见 enhance §7；**不在 TCE 本轮** |

---

## Phase 4 完成摘要 ✅

| # | ID | 工作项 |
|---|-----|--------|
| 1 | B-16 | `ParticipantPolicyDefinition.scope`；实例 `department_id` 优先于 seed policy |
| 2 | F-17 | 实例化发起部门默认/必选/预览联动（§6.2.1） |

---

## Phase 3 完成摘要 ✅

| # | ID | 工作项 |
|---|-----|--------|
| 1 | B-06 | 部门统计 API |
| 2 | B-09 | 列表 cursor 分页 |
| 3 | B-11 | 部门 Run 聚合 API |
| 4 | F-06 | 统计页部门 + Run |
| 5 | F-09 | 看板 Run 筛选 |

---

## Phase 4 验收 ✅

- [x] 同一 template，实例 `department_id=A/B` 参与人互不交叉（B-16）
- [x] Dialog 显式传 `department_id`；多部门可改、Admin 无默认时必选（F-17）
- [x] pytest `test_tce_phase4_multi_department_instantiation.py` + W2 回归

选定子任务后：更新 Phase 5 表状态 → 执行 → 测试 → commit → 追加 `progress.md`。
