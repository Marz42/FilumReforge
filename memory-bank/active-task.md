# 当前任务

> 🔥 HOT — 下一聚焦项请从 [`roadmap.md`](./roadmap.md) 选取并更新本文件。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | 任务中心增强 **TCE 主体收尾** |
| **优先级** | P1 · 架构债 |
| **状态** | **Phase 5 ✅** @ 2026-06-21 — **B-12（E 统一）** 仍为独立 backlog |
| **关联** | [`plans/task-center-enhance.md`](./plans/task-center-enhance.md) §7 |
| **后置** | B-12 / F-05 完整 Shell 拆分 |

---

## TCE Phase 5 完成 ✅

| # | ID | 工作项 |
|---|-----|--------|
| 1 | B-08 + F-16 | snapshot `template_summaries` → 图模板摘要 |
| 2 | F-13 | 移除 `TasksView` v2 Legacy 嵌入 |
| 3 | B-13 + F-14 | `aggregate_mode: batch \| streaming` + UI 门控 |
| 4 | B-14 + F-15 | 「结束采集」API + ROOT 按钮 |
| 5 | B-15 | `user_facing_state` 图投影 business_state 对齐 |

**未纳入本 commit**：**B-12** Legacy E 与图引擎完全统一（ADR-005，多 PR）。

---

## 移出 TCE 范围（后续待办）

| ID | 工作项 | 说明 |
|----|--------|------|
| **B-12** | E 与图引擎统一 | ADR-005；Legacy 实例化仍可用 |
| **F-05** | `TaskDetailShell.vue` 完整拆分 | 见 enhance §7 |

---

## Phase 4 完成摘要 ✅

| # | ID | 工作项 |
|---|-----|--------|
| 1 | B-16 | `ParticipantPolicyDefinition.scope`；实例 `department_id` 优先于 seed policy |
| 2 | F-17 | 实例化发起部门默认/必选/预览联动（§6.2.1） |

---

## Phase 5 验收 ✅

- [x] snapshot 无 Legacy E 模板摘要（B-08）
- [x] `TaskCenterView` 无 `TasksView` 回退（F-13）
- [x] 批次模板默认 `aggregate_mode=batch`；streaming 显示 ROOT 增量跟踪（B-13/F-14）
- [x] `POST .../close-capture` + ROOT「结束采集」（B-14/F-15）
- [x] pytest `test_tce_phase5_tc_p3_cleanup.py` + vitest TaskCenter 13/13

选定子任务后：更新本文件 → 执行 → 测试 → commit → 追加 `progress.md`。
