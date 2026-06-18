# 当前任务

> 🔥 HOT — 下一聚焦项请从 [`roadmap.md`](./roadmap.md) 选取并更新本文件。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | 任务中心 v2 重做 · TC-P0（Action Profile + 详情减法） |
| **优先级** | P0 · 路线图下一焦点 |
| **状态** | TC-P0 首 PR 已实现 @ `feat/task-center-p0-profile`；待合并 / Docker 截图验收 |
| **关联** | [`plans/task-center-v2-implementation-plan.md`](./plans/task-center-v2-implementation-plan.md)、[`plans/workflow-video-v1-ui-simplification-design.md`](./plans/workflow-video-v1-ui-simplification-design.md)、[`demos/workflow-task-center-v2.1-demo.html`](./demos/workflow-task-center-v2.1-demo.html) |

---

## 当前阶段：TC-P0

| # | 工作项 | 状态 |
|---|--------|------|
| P0-1 | `TaskDetailProfile` + 用户态映射 | 已完成 |
| P0-2 | `TaskDetailShell` 骨架 | 部分（逻辑并入 TasksView + compact meta） |
| P0-3 | `VideoCapturePanel` N1 单表单 | 已完成 |
| P0-4 | ROOT/N2 submissions 进度 x/y | 已完成 |
| P0-5 | ROOT Profile 裁剪 | 已完成 |
| P0-6 | Master 列表 Run 列 | 已完成 |
| P0-7 | 实例化 → 跟踪 Tab | 已完成 |
| P0-8 | vitest + Playwright 回归 | 进行中 |

---

## 验收清单（TC-P0）

- [x] N1 详情仅 **1 个主按钮**「提交选题」，无「提交交付物」
- [x] N2 / ROOT 展示 **x/y 采集进度** 与待交人
- [x] 批次 ROOT 无交付/评论主表单
- [x] 列表可区分 Run（`run_label` 或等价列）
- [x] 详情首屏仅核心元数据 + **更多** 菜单（compact meta；评论默认折叠）
- [x] `type-check` + vitest 127/127 + mock E2E 7/7

---

## 后续阶段（见实施计划）

| 阶段 | 概要 |
|------|------|
| **TC-P1** | `dispatch_topic` API + `VideoTrackingPanel` 增量派发 |
| **TC-P2** | 看板/甘特/统计入口 + `TasksView` 拆分 |

---

## Paradigma 对齐状态

**Phase 0–4 已全部完成**（2026-06-17）。任务中心 v2 设计 v2.1 + Demo 评审完成（2026-06-18）。

---

选定子任务后：更新上表状态 → 执行 → 追加 `progress.md` 会话摘要。
