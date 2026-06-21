# memory-bank 文档索引

本目录是 Project Filum 的**外部记忆系统**（Paradigma 对齐 Phase 0–4 已完成）。协议见 [`AGENT_RULES.md`](../AGENT_RULES.md)、[`VERSION`](../VERSION)（`0.89.0`）。

> **当前实施焦点**：[`active-task.md`](./active-task.md) → **TCE Phase 1** · 排期 [`plans/task-center-enhance.md`](./plans/task-center-enhance.md)

> **`handbooks/` ≈ Paradigma `manuals/`**：路径名保留 `handbooks/`，语义为部署运维与测试操作手册。

---

## 🔥 HOT — 每次对话必读

| 文件 | 用途 |
| --- | --- |
| [project-brief.md](./project-brief.md) | 产品愿景、受众、功能边界、技术栈摘要 |
| [architecture.md](./architecture.md) | 工程蓝图：模块、运行时、核心流程、关键文件 |
| [data-contracts.md](./data-contracts.md) | schema、枚举、实体关系、API 索引 |
| [conventions.md](./conventions.md) | 编码与协作规范 |
| [active-task.md](./active-task.md) | 当前唯一聚焦任务 |
| [progress.md](./progress.md) | 会话摘要 + 阶段验收与测试基线 |

---

## 🌡️ WARM — 按需加载

| 路径 | 用途 |
| --- | --- |
| [roadmap.md](./roadmap.md) | 宏观里程碑与版本焦点 |
| [changelog.md](./changelog.md) | SemVer 发布历史 |
| [domains/](./domains/) | 子系统领域文档 |
| [plans/](./plans/) | 细粒度实施计划 |
| [plans/tc-p2-views-stats-plan.md](./plans/tc-p2-views-stats-plan.md) | TC-P2 落地计划（三视图 + 统计 + Shell） |
| [plans/task-center-enhance.md](./plans/task-center-enhance.md) | **当前排期** — 任务中心增强 TCE（Phase 1–5 · 含多部门模板 §6） |
| [plans/task-center-v2-implementation-plan.md](./plans/task-center-v2-implementation-plan.md) | TC-P0–P2 ✅；TC-P3 已并入 TCE Phase 5 |
| [plans/workflow-video-v1-ui-simplification-design.md](./plans/workflow-video-v1-ui-simplification-design.md) | 任务协同 UI 简化规格 v2.1（P0–P2 ✅ @ `0.88.0`） |
| [demos/workflow-task-detail-v2.html](./demos/workflow-task-detail-v2.html) | 单页 HTML 交互 Demo（浏览器直接打开） |
| [design-document.md](./design-document.md) | 完整产品设计（摘要见 project-brief） |
| [tech-stack.md](./tech-stack.md) | 完整技术选型（摘要见 project-brief） |
| [handbooks/user-manual.md](./handbooks/user-manual.md) | 用户说明书 v1.2 |

### domains/ 索引

| 文件 | 子系统 |
| --- | --- |
| [hr-org.md](./domains/hr-org.md) | 组织、档案、权限、生命周期 |
| [task-center.md](./domains/task-center.md) | 任务中心、Inbox、多视图 |
| [workflow-graph-engine.md](./domains/workflow-graph-engine.md) | 图引擎 Phase 3–11 |
| [workflow-video-v1.md](./domains/workflow-video-v1.md) | 视频工作流 v1 |
| [messaging.md](./domains/messaging.md) | 消息、通知、回执 |
| [knowledge-ai.md](./domains/knowledge-ai.md) | 知识库、AI Router |

---

## 🧊 COLD — 排查时读取

| 路径 | 用途 |
| --- | --- |
| [decisions.md](./decisions.md) | 架构决策记录 (ADR) |
| [known-issues.md](./known-issues.md) | 已知坑位与环境陷阱 |
| [glossary.md](./glossary.md) | 项目专有术语 |

### [handbooks/](./handbooks/) — 操作手册

| 文件 | 用途 |
| --- | --- |
| [deployment-runbook-ubuntu-2404.md](./handbooks/deployment-runbook-ubuntu-2404.md) | Ubuntu 24.04 生产部署 |
| [manual-database-operations.md](./handbooks/manual-database-operations.md) | PostgreSQL 手工操作与迁移 |
| [e2e-gui-verification-automation-runbook.md](./handbooks/e2e-gui-verification-automation-runbook.md) | Docker GUI + Playwright 验证 |
| [workflow-video-v1-docker-runbook.md](./handbooks/workflow-video-v1-docker-runbook.md) | 视频工作流 v1 Docker 冒烟 |
| [workflow-video-v1-collaborative-uat-guide.md](./handbooks/workflow-video-v1-collaborative-uat-guide.md) | W0–W10 协同 UAT |
| [workflow-video-v1-multi-account-e2e-guide.md](./handbooks/workflow-video-v1-multi-account-e2e-guide.md) | 多账号 Live/Mock E2E |

### [history/](./history/) — 存档

| 路径 | 用途 |
| --- | --- |
| [history/reports/](./history/reports/) | 对齐审查报告（`alignment-assessment-YYYYMMDD.md`） |
| [history/proposals/](./history/proposals/) | 历史方案（非现行排期） |

### [archive/outdated/](./archive/outdated/) — 已废弃

见 [archive/README.md](./archive/README.md)。文首均有 **【已归档】** 横幅。

### 其他

- [templates/](./templates/)：工作流步骤 JSON 样例
- [demos/](./demos/)：UI/交互原型（HTML，非生产代码）

---

## 维护约定

| 变更类型 | 更新文件 |
| --- | --- |
| schema / 枚举 / API 契约 | `data-contracts.md` |
| 模块、运行时、流程 | `architecture.md` |
| 产品边界 | `project-brief.md` |
| 编码规范 | `conventions.md` |
| 当前任务 | `active-task.md` |
| 阶段验测、会话结束 | `progress.md` |
| 排期与阶段出口 | `roadmap.md` + `plans/`（**当前**: [`task-center-enhance.md`](./plans/task-center-enhance.md)） |
| ADR / 坑位 / 术语 | `decisions.md` / `known-issues.md` / `glossary.md` |
| 运维步骤 | `handbooks/` |
