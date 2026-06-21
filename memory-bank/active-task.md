# 当前任务

> 🔥 HOT — 下一聚焦项请从 [`roadmap.md`](./roadmap.md) 选取并更新本文件。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | **图任务模板设计器 D1**（F-18） |
| **优先级** | P1 · 产品缺口 |
| **状态** | **D1 ✅** @ 2026-06-21 — D2 边/路由待做 |
| **关联** | [`domains/task-center.md`](./domains/task-center.md) §12 |
| **后置** | F-19（D2 边/路由）· B-12 · F-05 |

---

## D1 工作项

| # | 工作项 | 说明 |
|---|--------|------|
| 1 | 后端 API | create / designer GET / draft PUT / fork / status / validate |
| 2 | `WorkflowGraphTemplateAdminService` | 结构锁定、版本 fork、发布归档同族 active |
| 3 | 前端设计器 | 路由 `/task-templates/:id/edit`，config + 节点表 + 保存/发布 |
| 4 | 列表入口 | `GraphTemplatesPanel`「设计」跳转设计器 |
| 5 | 测试 | pytest D1 + vitest smoke |

**D1 已交付**；下一步 **F-19 D2**（边、routing_rules、拓扑校验）。

---

## TCE Phase 5 完成 ✅

Phase 1–5 已闭合；详见 [`domains/task-center.md`](./domains/task-center.md) §1。

**未纳入 TCE**：**B-12** Legacy E 统一 · **F-05** Shell 拆分 · **F-10–F-12** 抛光。

---

选定子任务后：更新本文件 → 执行 → 测试 → commit → 追加 `progress.md`。
