# 当前任务

> 🔥 HOT — 下一聚焦项请从 [`roadmap.md`](./roadmap.md) 选取并更新本文件。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | 任务中心增强 · **TCE Phase 1**（正确性 + 测试服） |
| **优先级** | **P0** · 路线图下一焦点 |
| **状态** | **就绪 · 待开 PR-A** — 文档已对齐 @ 2026-06-21；基线 `0.89.0` |
| **关联** | [`plans/task-center-enhance.md`](./plans/task-center-enhance.md)、[`domains/task-center.md`](./domains/task-center.md) |
| **后置** | TCE Phase 2–5；**TC-P3**（E 与图引擎统一）见 enhance **Phase 5** |

---

## 当前阶段：TCE Phase 1

**目标**：列表/详情状态一致、操作后刷新、看板可读；测试服历史 `department_id` 正确。

| # | ID | 工作项 | 状态 |
|---|-----|--------|------|
| 1 | **B-01** | graph 读路径扩展到节点投影任务（N1/N3/N7…） | 未开始 |
| 2 | **B-03** | 历史图投影任务 `department_id` 迁移脚本 | 未开始 |
| 3 | **B-02** | inbox/tracking DB 层 LIMIT | 未开始 |
| 4 | **F-08** | 工作流操作后 refresh snapshot | 未开始 |
| 5 | **F-02** | 看板显示执行人姓名 | 未开始 |
| 6 | **F-03** | 实例化 Dialog「发起部门」占位（完整见 Phase 4 · F-17） | 未开始 |

---

## 建议 PR 切分

| PR | 范围 | 验收要点 |
|----|------|----------|
| **PR-A** | B-01 + B-04 + F-01 + F-08 | 待办状态与详情一致；hydration 不拉全量；提交后列表更新 |
| **PR-B** | F-02 + F-03 + B-03 | 看板可读；实例化显式部门；测试服 department 迁移 |

> Phase 1 表格含 B-02/F-02/F-03；**PR-A 可先做 B-01/F-08**，B-04/F-01 属 Phase 2 但文档建议并入 PR-A 形成最小 UX 闭环。

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

## 验收清单（Phase 1）

- [ ] N1 完成后待办 status/stage 与详情 `business_state` 一致（B-01）
- [ ] 图操作后待办/跟踪 Tab 无需 F5（F-08）
- [ ] 看板卡片显示执行人姓名非 UUID（F-02）
- [ ] 测试服 N7+ 任务 `department_id` = 受理人部门（B-03 + 投影修复）
- [ ] pytest：inbox graph 投影节点任务

---

选定子任务后：更新上表状态 → 开分支（建议 `feat/tce-phase1-pr-a`）→ 执行 → 追加 `progress.md` 会话摘要。
