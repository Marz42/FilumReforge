# memory-bank 文档索引

本目录存放 Project Filum 的**设计、架构、进度、计划与运维手册**。以下为现行目录结构（2026-05-14 起生效）；历史材料已迁入子目录，**勿**再以旧路径引用。

## 根目录（现行权威）

| 文件 | 用途 |
| --- | --- |
| [architecture.md](./architecture.md) | 工程实现权威：模块、运行时、schema、与实现对齐的事实 |
| [design-document.md](./design-document.md) | 产品目标、边界、非目标 |
| [progress.md](./progress.md) | 阶段完成状态、验证记录、已知问题 |
| [tech-stack.md](./tech-stack.md) | 技术选型与落地状态 |

## [handbooks/](./handbooks/) — 操作手册（可复制执行）

| 文件 | 用途 |
| --- | --- |
| [handbooks/deployment-runbook-ubuntu-2404.md](./handbooks/deployment-runbook-ubuntu-2404.md) | Ubuntu 24.04 LTS 生产部署全流程 |
| [handbooks/manual-database-operations.md](./handbooks/manual-database-operations.md) | PostgreSQL 手工操作、迁移、整库重置 |
| [handbooks/e2e-gui-verification-automation-runbook.md](./handbooks/e2e-gui-verification-automation-runbook.md) | Docker GUI + Playwright 自动化验证与报告 |
| [handbooks/user-manual.md](./handbooks/user-manual.md) | **用户说明书** v1.2（IA Phase A–F + 体验补丁） |
| [handbooks/workflow-video-v1-docker-runbook.md](./handbooks/workflow-video-v1-docker-runbook.md) | 视频工作流 v1 双模板种子与 Docker 冒烟复现 |

## [plans/](./plans/) — 实施计划（排期与阶段出口）

| 文件 | 用途 |
| --- | --- |
| [plans/implementation-plan.md](./plans/implementation-plan.md) | 从当前代码出发的下一轮工作流与主线说明 |
| [plans/improvements-stage2-implementation-plan.md](./plans/improvements-stage2-implementation-plan.md) | Stage 2 周期阶段计划 |
| [plans/workflow-refactor-implementation-plan.md](./plans/workflow-refactor-implementation-plan.md) | 工作流图引擎重构 Phase 0–11 实施与验收基线 |
| [plans/workflow-video-v1-implementation-plan.md](./plans/workflow-video-v1-implementation-plan.md) | 视频工作流 v1（批次选题会、模板表单引擎、按题 fork） |
| [plans/workflow-video-v1-w0-adr.md](./plans/workflow-video-v1-w0-adr.md) | 视频 v1 W0 feature 开关与运行时 ADR |
| [plans/ui-information-architecture-plan.md](./plans/ui-information-architecture-plan.md) | UI 信息架构里程碑总览（IA-0…IA-4） |
| [plans/ui-refactor-spec-v2.md](./plans/ui-refactor-spec-v2.md) | **UI 重构实施规格 v2**（Phase A–F 逐步验收，依据 user-manual 审阅批注） |

## [history/reports/](./history/reports/) — 时点评估与阶段报告（存档）

新建对齐审查报告时，默认文件名 `alignment-assessment-YYYYMMDD.md` 放在本目录（与 `.github/prompts/memory-bank-alignment-review.prompt.md` 一致）。

| 文件 | 用途 |
| --- | --- |
| [history/reports/alignment-assessment-20260422.md](./history/reports/alignment-assessment-20260422.md) | 2026-04-22 文档与实现对齐评估快照 |
| [history/reports/alignment-assessment-20260521.md](./history/reports/alignment-assessment-20260521.md) | 2026-05-21 Stage 2 Phase 6 收口、测试基线与 IA 后补丁对齐 |
| [history/reports/phase11g-progress-report-20260506.md](./history/reports/phase11g-progress-report-20260506.md) | Phase 11-G 收口报告快照 |

## [history/proposals/](./history/proposals/) — 历史方案与提案（非现行排期）

| 文件 | 用途 |
| --- | --- |
| [history/proposals/refactor-plan.md](./history/proposals/refactor-plan.md) | Step 1–7 启动前的信息架构重构方案（提案语境） |
| [history/proposals/workflow-refactor.md](./history/proposals/workflow-refactor.md) | 图节点化工作流目标设计（与现行双轨并存叙述对照用） |
| [history/proposals/workflow-refactor-script.md](./history/proposals/workflow-refactor-script.md) | 任务中心/握手等产品讨论笔记 |
| [history/proposals/improvments-phase2.md](./history/proposals/improvments-phase2.md) | Stage 2 前置改进讨论稿（文件名保留历史拼写） |

## [archive/outdated/](./archive/outdated/) — **已废弃 / 勿作依据**

见 [archive/README.md](./archive/README.md)。内含重复文件名草稿、已被 `progress`/`plans` 替代的清单等；文首均有 **【已归档】** 横幅。

## 其他

- [templates/](./templates/)：工作流步骤 JSON 样例（非 Markdown 叙述文档）

---

**约定**：重大实现变化 → 先更新 `architecture.md`；阶段状态与验测 → `progress.md`；路线与阶段范围 → `plans/` 下对应计划；运维步骤 → `handbooks/`。
