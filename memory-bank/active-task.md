# 当前任务

> 🔥 HOT — 下一聚焦项请从 [`roadmap.md`](./roadmap.md) 选取并更新本文件。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | 任务中心 v2 重做 · TC-P1（增量派发 + 后端收口） |
| **优先级** | P0 · 路线图下一焦点 |
| **状态** | TC-P0 已合并 @ `7bc242c`；TC-P1 核心（P1-1–P1-5、P1-9 mock）已实现 @ `feat/task-center-p0-profile` |
| **关联** | [`plans/task-center-v2-implementation-plan.md`](./plans/task-center-v2-implementation-plan.md)、[`plans/workflow-video-v1-ui-simplification-design.md`](./plans/workflow-video-v1-ui-simplification-design.md) |

---

## 当前阶段：TC-P1

| # | 工作项 | 状态 |
|---|--------|------|
| P1-1 | `dispatch_topic` API | 已完成 |
| P1-2 | `WorkflowVideoFormService.dispatch_topic()` | 已完成 |
| P1-3 | `VideoTrackingPanel` | 已完成 |
| P1-4 | N1 单条校验 | 已完成 |
| P1-5 | Capture → Task `DONE` | 已完成 |
| P1-6 | `submit_mode=file` / `VideoProductionPanel` | 已完成 |
| P1-7 | 更多菜单 · 退回 | 未开始 |
| P1-8 | 实例化 participant 默认 | 未开始 |
| P1-9 | E2E 增量派发 mock | 已完成 |

---

## 验收清单（TC-P1）

- [x] 2/3 时可 dispatch，子 Run 与待办出现（mock E2E）
- [x] 重复 dispatch 409 + UI 禁用（pytest + forked_topics）
- [x] 文件节点「上传并提交」（P1-6）
- [ ] 更多退回 → 用户态「已退回」（P1-7）
- [x] N1 提交后 Task 为 done（非 review）

---

## 后续阶段

| 阶段 | 概要 |
|------|------|
| **TC-P2** | 看板/甘特/统计入口 + `TasksView` 拆分 |

---

选定子任务后：更新上表状态 → 执行 → 追加 `progress.md` 会话摘要。
