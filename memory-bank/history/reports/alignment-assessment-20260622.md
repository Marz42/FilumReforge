# Project Filum 文档与实现对齐评估

**日期**: 2026-06-22  
**审查范围**: 会话启动 — HOT/WARM memory-bank 加载、`git log -20`、文档漂移扫描  
**关联**: [`progress.md`](../../progress.md)、[`active-task.md`](../../active-task.md)、[`alignment-assessment-20260618.md`](./alignment-assessment-20260618.md)

---

## 1. 结论摘要

| 维度 | 判断 |
|------|------|
| **整体对齐度** | **高** — `HEAD` `e0e5128` 与 memory-bank 主干一致 |
| **工作区状态** | 干净（`main` @ `e0e5128`） |
| **测试基线** | pytest 252 collected · vitest 45/124 · Playwright core 33/33 · task-center 48/48（见 `progress.md`） |
| **本次修正** | 文首「下一焦点仍写 TCE Phase 1」类状态摘要；`project-brief` TCE 进行中 → done |

**一句话**: TCE + 图模板设计器已交付；剩余为 B-12/F-05 架构债与 E2E 基线刷新，非产品闭环缺口。

---

## 2. 最近 git 主线（`git log --oneline -n 20`）

| Commit | 主题 |
|--------|------|
| `e0e5128` | fix(task-templates): guard designer against forward edge cycles |
| `cb30bb5` | docs(memory-bank): sync designer UX polish |
| `6c0f9c0`–`1537d81` | 设计器 DAG 预览/表格/打回通道 UX 抛光 |
| `522cfb1`–`dc08acc` | 图模板设计器 D1–D3 |
| `ae0ce55`–`0bebc2b` | TCE Phase 1–5 |

---

## 3. 对齐项（已对齐）

| 主题 | 证据 |
|------|------|
| TCE Phase 1–5 | `task_service` graph 投影、batch API、部门统计、多部门实例化、TC-P3 清理 — commits `0bebc2b`…`ae0ce55` |
| 图模板设计器 D1–D3 | `WorkflowGraphTemplateAdminService`、`GraphTemplateDesignerView`、`workflow_graph_template_topology.py` |
| 设计器 UX 抛光 | AdminService `commit()`、空白新建、DAG 横/纵/图例/打回通道 — `e0e5128` |
| Feature flags | `TASK_CENTER_V2_ENABLED=true`（默认）；`workflow_graph_template_engine_enabled=false`（视频 v1 ADR）— `backend/app/core/config.py` |
| Legacy E 后端仍存 | `backend/app/api/routes/task_templates.py` — 与 B-12 backlog 一致 |
| 任务中心产品闭环 | `domains/task-center.md` §1 结论与 E2E 48/48 基线 |

---

## 4. 文档漂移（已修正 / 仍开放）

| # | 严重度 | 类型 | 问题 | 处置 |
|---|--------|------|------|------|
| 1 | 中 | 文档漂移 | `architecture.md` 文首写「下一焦点 TCE Phase 1」 | ✅ 已改为 B-12/F-05 |
| 2 | 中 | 文档漂移 | `project-brief.md` TCE「进行中」 | ✅ 已标 done |
| 3 | 中 | 文档漂移 | `progress.md`「当前规划焦点」仍列 TCE Phase 1–5 待做 | ✅ 已更新 |
| 4 | 低 | 文档漂移 | `roadmap.md` P0 仍写 TCE Phase 1 | ✅ 已改为架构债 P0 |
| 5 | 低 | 文档漂移 | `decisions.md` ADR-007「Phase 3 进行中」 | ✅ 已改为 Phase 0–4 完成 |
| 6 | 低 | 文档 | `implementation-plan.md` §1 执行位置偏 2026-05 | ✅ 已刷新；全文未逐段审计 |
| 7 | 中 | 实现 backlog | B-12 Legacy E API 未删 | 预期 — `active-task.md` |
| 8 | 中 | 测试 | UAT / docker-gui / playwright live 未重跑 | 发布前刷新 |
| 9 | 低 | 测试 | Alembic 往返 skip（无 PostgreSQL） | 配置 `POSTGRES_TEST_ADMIN_DSN` |
| 10 | 暂缓 | 运维 | Ubuntu 最小回滚演练 | 上线前 |

---

## 5. 当前应聚焦主线

1. **B-12** — `task_templates` / `TaskTemplateService` 与图引擎 runtime 统一（ADR-005）
2. **F-05** — `TaskDetailShell.vue` 拆分
3. **E2E 基线** — `test:e2e:workflow-video-uat`、docker-gui、playwright live
4. P2 并行：生命周期规则化 UI、通知渠道深化

---

## 6. 证据索引

| 主题 | 路径 |
|------|------|
| 当前任务 | `memory-bank/active-task.md` |
| 任务中心域 | `memory-bank/domains/task-center.md` |
| 设计器后端 | `backend/app/services/workflow_graph_template_admin_service.py` |
| 设计器前端 | `frontend/src/views/GraphTemplateDesignerView.vue` |
| Legacy E API | `backend/app/api/routes/task_templates.py` |
| 测试基线 | `memory-bank/progress.md` §测试基线 |
