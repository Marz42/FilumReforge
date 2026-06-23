# Project Filum 文档与实现对齐评估

**日期**: 2026-06-23  
**审查范围**: 会话启动 — 远端拉取、HOT/WARM 加载、`git log -20`、文档漂移扫描  
**关联**: [`progress.md`](../../progress.md)、[`active-task.md`](../../active-task.md)、[`alignment-assessment-20260622.md`](./alignment-assessment-20260622.md)

---

## 1. 结论摘要

| 维度 | 判断 |
|------|------|
| **整体对齐度** | **高** — `HEAD` `bf75e31` 与 memory-bank 主干一致 |
| **工作区状态** | 干净（`main` @ `bf75e31`，自 `e0e5128` fast-forward） |
| **测试基线** | pytest 252+ · vitest 45/124 · Playwright core 33/33 · task-center 48/48；`test_workflow_video_dispatch_fixes.py` 新增 @ `bf75e31` |
| **本次修正** | `progress.md` 会话摘要；`active-task.md` 最近完成；`architecture.md` 文首同步 |

**一句话**: TCE + 设计器 + 视频 streaming 派发补丁已交付；工程主线仍为 B-12/F-05 与 E2E 基线刷新。

---

## 2. 最近 git 主线（`git log --oneline -n 20`）

| Commit | 主题 |
|--------|------|
| **`bf75e31`** | fix(task-center): streaming video dispatch, dedupe inbox shells, tracking labels |
| `e0e5128` | fix(task-templates): guard designer against forward edge cycles |
| `cb30bb5` | docs(memory-bank): sync designer UX polish |
| `6c0f9c0`–`1537d81` | 设计器 DAG 预览/表格/打回通道 UX 抛光 |
| `522cfb1`–`dc08acc` | 图模板设计器 D1–D3 |
| `ae0ce55`–`345e574` | TCE Phase 1–5 |

---

## 3. 对齐项（已对齐）

| 主题 | 证据 |
|------|------|
| TCE Phase 1–5 | `task_service` graph 投影、batch API、部门统计、多部门实例化 — commits `345e574`…`ae0ce55` |
| 图模板设计器 D1–D3 + UX | `WorkflowGraphTemplateAdminService`、`GraphTemplateDesignerView`、`e0e5128` 环路守卫 |
| 视频 streaming 派发补丁 | `task_service` inbox/tracking 过滤；`workflow_video_form_service.dispatch_topic`；种子 `aggregate_mode` 默认 streaming — `bf75e31` |
| Feature flags | `TASK_CENTER_V2_ENABLED=true`（默认）；`workflow_graph_template_engine_enabled=false`（视频 v1 ADR） |
| Legacy E 后端仍存 | `backend/app/api/routes/task_templates.py` — 与 B-12 backlog 一致 |
| 宏观排期 | `implementation-plan.md` §1、`roadmap.md` P0、`active-task.md` 均指向 B-12/F-05 |

---

## 4. 文档漂移（仍开放 / 低优先级）

| # | 严重度 | 类型 | 问题 | 建议 |
|---|--------|------|------|------|
| 1 | 低 | 文档 | `domains/task-center.md` 未写跟踪列「当前步骤/处理人」、inbox graph 壳层排除 | 下次改域文档时补 § |
| 2 | 低 | 文档 | `domains/workflow-video-v1.md` 未写制作 ROOT 指派经理（非脚本作者） | 同上 |
| 3 | 低 | 文档 | `alignment-assessment-20260622.md` HEAD 仍标 `e0e5128` | 历史快照，以本报告为准 |
| 4 | 低 | 文档 | `implementation-plan.md` §6 正文仍含 Step 7 / 模板六视区等历史治理主题 | 非阻塞；§1 执行位置已刷新 |
| 5 | 低 | 文档 | `roadmap.md` 版本主题仍写「TC-P2 IA 2.0」 | 与 P0「架构债」略脱节，可择机改标题 |
| 6 | 中 | 实现 backlog | B-12 Legacy E API 未删 | 预期 — `active-task.md` |
| 7 | 中 | 测试 | UAT / docker-gui / playwright live 未重跑 | 发布前刷新 |
| 8 | 暂缓 | 运维 | Ubuntu 最小回滚演练 | 上线前 |

---

## 5. 当前应聚焦主线（以 `implementation-plan.md` 为准）

1. **B-12** — `task_templates` / `TaskTemplateService` 与图引擎 runtime 统一（ADR-005）
2. **F-05** — `TaskDetailShell.vue` 完整拆分（~1800 行）
3. **E2E 基线** — `test:e2e:workflow-video-uat`、docker-gui、playwright live
4. P2 并行：生命周期规则化 UI、通知渠道深化；回滚演练暂缓

---

## 6. 证据索引

| 主题 | 路径 |
|------|------|
| 视频 dispatch 补丁 | `backend/tests/test_workflow_video_dispatch_fixes.py` |
| inbox/tracking 过滤 | `backend/app/services/task_service.py` |
| 跟踪列 UI | `frontend/src/components/task-center/TaskCenterListView.vue` |
| 当前任务 | `memory-bank/active-task.md` |
| 宏观计划 | `memory-bank/plans/implementation-plan.md` §1 |
