# Project Filum 文档与实现对齐评估

**日期**: 2026-06-17  
**审查范围**: Paradigma memory-bank Phase 4 收口；`git log` 至 `3b3e39a`  
**关联**: [`progress.md`](../../progress.md)、[`roadmap.md`](../../roadmap.md)、[`alignment-assessment-20260521.md`](./alignment-assessment-20260521.md)

---

## 1. 结论摘要

| 维度 | 判断 |
|------|------|
| **整体对齐度** | **高** — 核心能力与 memory-bank 主干一致 |
| **Paradigma 重构** | Phase 0–4 已完成；HOT/WARM/COLD 分工清晰，schema 单一来源为 `data-contracts.md` |
| **主要问题类型** | 子 README 与部分 plans 存在**文档漂移**（Phase 4 已修复）；测试基线**滞后于** workflow-video 提交 |
| **实现缺口** | 与 2026-05-21 评估一致：回滚演练、E/图引擎统一、公开注册、真实通知渠道 |

**一句话**: 实现事实与 `architecture.md` / `domains/` / `data-contracts.md` 对齐良好；根与子 README 在 Phase 4 已同步新文档分工；`progress.md` 测试基线 commit 早于近期 workflow-video 系列提交，建议下次大版本前刷新。

---

## 2. 对齐项

### 2.1 Memory-Bank 体系（Paradigma）

- 🔥 HOT 六件套齐全：`project-brief`、`architecture`、`data-contracts`、`conventions`、`active-task`、`progress`
- 🌡️ `roadmap`、`changelog`、`domains/*`、`plans/*` 已落地
- 🧊 `decisions`、`known-issues`、`glossary`、`handbooks/` 已落地
- `AGENT_RULES.md`、`.cursor/rules/memory-bank-protocol.mdc`、`.github/instructions/` 指向一致

### 2.2 阶段与交付状态

- Phase A–5、Step 1–7、UI IA A–F、Stage 2 Phase 0–6：`progress.md` 与 `roadmap.md` 一致
- 工作流图引擎 Phase 11-G：`workflow-refactor-implementation-plan.md`、`domains/workflow-graph-engine.md` 与代码（`WorkflowGraphService`、`task_center_v2_enabled` 默认 `true`）一致
- 视频工作流 v1 W0–W10：`progress.md` 阶段表与 `git log` `dea816c`…`3b3e39a` 提交序列一致

### 2.3 架构与模块

- 模块化单体、ARQ、NotificationService 总线：`conventions.md` 与 `backend/app/services/notification_service.py` 一致
- 任务状态机、`task_comments` 协同模型：与 `TaskService` 一致
- 双轨工作流（E + 图引擎）：`decisions.md` ADR-005、`known-issues.md` 明确标注，非实现缺失

### 2.4 数据库 / Schema

- 核心业务表：`data-contracts.md` §10 与 `backend/app/models/` 一致（抽样：`users`、`tasks`、`workflow_graph_*` 模型存在）
- 图引擎迁移：`backend/alembic/versions/20260429_04_workflow_graph_core.py` 及后续迁移存在
- 视频 v1：`20260522_01`、`20260523_01` 等迁移与 `domains/workflow-video-v1.md` 叙述一致

### 2.5 部署工件

- `infra/docker/docker-compose.prod.yml`、`backend/Dockerfile.prod`、`frontend/Dockerfile.prod`、`scripts/check-release.sh` 均存在
- `handbooks/deployment-runbook-ubuntu-2404.md` 与上述工件一致

### 2.6 API / 前端入口

- 任务中心 graph-first：`backend/app/core/config.py` `task_center_v2_enabled: bool = True`
- 图引擎 API：`backend/app/api/routes/workflow_graph_engine.py`
- 前端路由：`frontend/src/router/index.ts` 与 `user-manual.md` v1.2 一致

---

## 3. 问题清单

| # | 严重度 | 类型 | 问题 | 证据 | 建议 |
|---|--------|------|------|------|------|
| 1 | 中 | 文档漂移 | `progress.md` 测试基线停在 `36c6a77`（2026-05-21），未含 workflow-video W0–W10 及后续 fix | `progress.md`「测试基线」；`git log` 至 `3b3e39a` | 下次发布前重跑 pytest/vitest 并更新 baseline_id |
| 2 | 中 | 文档漂移 | 根 `README.md` 曾写 Phase 11-F、user-manual v1.1、schema 在 architecture | Phase 4 已修复 | ✅ 已修复 |
| 3 | 中 | 文档漂移 | `backend/README.md` 称 graph 读侧未切换 | `backend/README.md` L19 旧文 | ✅ Phase 4 已修复 |
| 4 | 低 | 文档漂移 | 多份 plans 仍写「schema 更新 architecture」 | `implementation-plan.md` 等 | ✅ Phase 4 已改为 data-contracts |
| 5 | 低 | 表述含混 | `architecture.md` 状态行仍极长（版本 v3.12.0 内嵌） | `architecture.md` L3–4 | 可选：状态摘要迁至 `roadmap`，architecture 只保留日期 |
| 6 | 中 | 实现缺失 | Ubuntu 最小回滚路径未演练 | `progress.md`「当前规划焦点」 | 按 roadmap P0 执行 |
| 7 | 中 | 实现缺失 | 工作流 E 与图引擎产品级统一 | `project-brief.md`、`roadmap.md` | 产品 backlog，非文档错误 |
| 8 | 低 | 实现缺失 | docker-gui / Playwright 未随最新 commit 重跑 | `known-issues.md` | 大版本前刷新 |

**历史材料**: `history/`、`archive/` 中旧路径引用**不视为漂移**；文首已标注时点/归档。

---

## 4. 建议修复顺序

1. ✅ **Phase 4 已完成**：根/README、子 README、docs-alignment、plans 内 schema 分工指向
2. **下次功能发布前**：刷新 `progress.md` 测试基线（含 workflow-video pytest 子集）
3. **P0 工程**：Ubuntu 最小回滚演练 → 写入 `progress.md` + `known-issues.md`
4. **可选**：将 `architecture.md` 文首状态横幅缩短，细节链到 `roadmap`/`progress`

---

## 5. 证据索引

| 主题 | 路径 |
|------|------|
| 文档索引 | `memory-bank/README.md` |
| Schema | `memory-bank/data-contracts.md` |
| 图引擎 | `memory-bank/domains/workflow-graph-engine.md`、`backend/app/services/workflow_graph_service.py` |
| 视频 v1 | `memory-bank/domains/workflow-video-v1.md`、`backend/app/core/workflow_video_policy.py` |
| Feature flags | `backend/app/core/config.py` |
| 部署 | `infra/docker/docker-compose.prod.yml`、`scripts/check-release.sh` |
| 最近提交 | `git log --oneline -n 20` → `3b3e39a` |
| 上轮评估 | `history/reports/alignment-assessment-20260521.md` |

---

## 6. Phase 4 修复记录（本次）

- `README.md` — 文档入口表、Phase 11-G、workflow-video 指针
- `backend/README.md`、`frontend/README.md` — memory-bank 新路径与边界修正
- `.github/instructions/docs-alignment.instructions.md` — Paradigma 分工
- `plans/implementation-plan.md`、`workflow-refactor-implementation-plan.md`、`improvements-stage2-implementation-plan.md`、`workflow-video-v1-implementation-plan.md`
- `handbooks/manual-database-operations.md`、`handbooks/user-manual.md`
- `archive/README.md`、`design-document.md`、`progress.md`（Stage 2 同步约定）
