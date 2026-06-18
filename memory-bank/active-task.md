# 当前任务

> 🔥 HOT — 下一聚焦项请从 [`roadmap.md`](./roadmap.md) 选取并更新本文件。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | 任务中心 v2 · **TC-P3**（工作流 E 与图引擎统一） |
| **优先级** | P1 · 路线图下一焦点 |
| **状态** | **待启动** — Legacy E 前端已移除 @ `0.89.0`；TC-P2 @ `0.88.0` |
| **关联** | [`plans/task-center-v2-implementation-plan.md`](./plans/task-center-v2-implementation-plan.md) §TC-P3、[`plans/implementation-plan.md`](./plans/implementation-plan.md)、[`decisions.md`](./decisions.md) ADR-005 |

---

## 当前阶段：TC-P3（规划）

| # | 工作项 | 状态 |
|---|--------|------|
| P3-1 | 工作流 E 与图模板运行时统一评估 | 未开始 |
| P3-2 | N2 `aggregate_mode` 产品开关（batch / streaming） | 未开始 |
| P3-3 | 「结束采集」产品开关 | 未开始 |

---

## TC-P3 前置（@ `0.89.0`）

- [x] 前端 `/task-templates` 移除 Legacy E Tab；统一用户可见名「任务模板」
- [x] 后端 E API 文档标注 **待删除**（`known-issues.md` / ADR-005）

---

## TC-P2 收尾（工程，非功能阻塞）

- [x] P2-6 详情迁出（v2 隐藏 BatchRunDashboard；video 仅 3 条事件）
- [x] P2-7 `config.ui_profile`（seed + 实例化 metadata + 前端 override）
- [x] E2E：task-center / stats / workflow-video-v1 绿
- [ ] （可选）`git push origin main`
- [ ] （可选）live 多账号 E2E、Docker A–F 手工实测

---

## 验收清单（TC-P2 · = 设计 §11.3）— 已完成

- [x] 三视图独立组件且与 Demo §7.2 一致
- [x] 统计入口可看全量事件与部门汇总
- [x] 详情仅保留最近 3 条事件摘要

---

选定子任务后：更新上表状态 → 执行 → 追加 `progress.md` 会话摘要。
