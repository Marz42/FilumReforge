# memory-bank 文档索引

本目录是 Project Filum 的**外部记忆系统**，已对齐 Paradigma `0.7.0` 与上游 `3422ecf`：Task/Session/Checkpoint YAML 为运行事实，active-task/handoff/Context Manifest、索引和 Memory catalog 为可重建投影，并启用 M0–M4 迁移与治理修复。协议见 [`AGENT_RULES.md`](../AGENT_RULES.md)；产品版本见根 [`VERSION`](../VERSION)，协议版本独立见 [`.paradigma/VERSION`](../.paradigma/VERSION)。

> **当前实施焦点（2026-09-10）**：[开发与 Human Gates 整合方案](./knowledge/plans/2026-09-10-integrated-development-and-human-gates-plan.md) 统一 P0 修复、目标验证、RC/UAT、生产批准和后续工作。F-05、Iteration 5-A～E、KI-015 工程已完成；KI-014 A/B 已提交，C 工具待目标代表性数据观察，D contract 单独批准。最新已记录候选为 RC3；包含后续改动的新候选需重新固定 SHA/tag。生产保持 fallback 部署、strict canary、稳定观察和 Iteration 6 分别留证，不代签。[当前 Task](./runtime/active-task.md) · [投影契约](./knowledge/contracts/projection-contract.md) · [UAT 清单](./knowledge/manuals/2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md) · [上线清单](./knowledge/manuals/2026-08-09-production-release-checklist.md)

> **`knowledge/manuals/` ≈ Paradigma `manuals/`**：路径名保留 `knowledge/manuals/`，语义为部署运维与测试操作手册。

---

## 🔥 HOT — Context Builder 必需候选

HOT/WARM/COLD 是检索元数据，不再要求每次固定扫描。新会话先恢复 Task/Session，再根据用户意图用 `pd context build` 生成清单，并按 Manifest 的选择理由读取。

| 文件 | 用途 |
| --- | --- |
| [project-brief.md](./knowledge/project-brief.md) | 产品愿景、受众、功能边界、技术栈摘要 |
| [architecture.md](./knowledge/architecture.md) | 工程蓝图：模块、运行时、核心流程、关键文件 |
| [data-contracts.md](./knowledge/contracts/data-contracts.md) | schema、枚举、实体关系、API 索引 |
| [conventions.md](./knowledge/conventions.md) | 编码与协作规范 |
| [active-task.md](./runtime/active-task.md) | 当前 Task 的 generated 人类投影；事实在 runtime YAML |
| [knowledge/index.md](./knowledge/index.md) | generated 长期知识路由入口 |

---

## 🌡️ WARM — 按需加载

| 路径 | 用途 |
| --- | --- |
| [roadmap.md](./knowledge/roadmap.md) | 宏观里程碑与版本焦点 |
| [changelog.md](./logs/changelog.md) | SemVer 发布历史 |
| [logs/progress/](./logs/progress/) | 版本、Batch 或人工审计日志；旧 `0000-legacy-progress.md` 为冻结基线 |
| [domains/](./knowledge/domains/) | 子系统领域文档 |
| [plans/](./knowledge/plans/) | 细粒度实施计划；先看 [计划状态目录](./knowledge/plans/plan-status-catalog.md)，不要把 completed/legacy 文档当成现行排期 |
| [plans/tc-p2-views-stats-plan.md](./knowledge/plans/tc-p2-views-stats-plan.md) | TC-P2 落地计划（三视图 + 统计 + Shell） |
| [plans/task-center-enhance.md](./knowledge/plans/task-center-enhance.md) | **TCE Phase 1–5 ✅** · F-18–F-20 ✅ · **P0 B-12** · **P1 F-22** · **P2 F-21**
| [plans/task-center-v2-implementation-plan.md](./knowledge/plans/task-center-v2-implementation-plan.md) | TC-P0–P2 ✅；TC-P3 已并入 TCE Phase 5 |
| [plans/workflow-video-v1-ui-simplification-design.md](./knowledge/plans/workflow-video-v1-ui-simplification-design.md) | 任务协同 UI 简化规格 v2.1（P0–P2 ✅ @ `0.88.0`） |
| [demos/workflow-task-detail-v2.html](./demos/workflow-task-detail-v2.html) | 单页 HTML 交互 Demo（浏览器直接打开） |
| [design-document.md](./design-document.md) | 完整产品设计（摘要见 project-brief） |
| [tech-stack.md](./tech-stack.md) | 完整技术选型（摘要见 project-brief） |
| [knowledge/manuals/user-manual.md](./knowledge/manuals/user-manual.md) | 用户说明书 v1.2 |

### domains/ 索引

| 文件 | 子系统 |
| --- | --- |
| [hr-org.md](./knowledge/domains/hr-org.md) | 组织、档案、权限、生命周期 |
| [task-center.md](./knowledge/domains/task-center.md) | 任务中心全貌：完成度、模块地图、典型场景（**主文档**） |
| [workflow-graph-engine.md](./knowledge/domains/workflow-graph-engine.md) | 图引擎 Phase 3–11 / Iteration 1–4 |
| [workflow-video-v1.md](./knowledge/domains/workflow-video-v1.md) | 视频参考模板包与现有兼容实现 |
| [messaging.md](./knowledge/domains/messaging.md) | 消息、通知、回执 |
| [knowledge-ai.md](./knowledge/domains/knowledge-ai.md) | 知识库、AI Router |

---

## 🧊 COLD — 排查时读取

| 路径 | 用途 |
| --- | --- |
| [decisions.md](./decisions/decisions.md) | 架构决策记录 (ADR) |
| [known-issues.md](./known-issues/known-issues.md) | 已知坑位与环境陷阱 |
| [glossary.md](./glossary.md) | 项目专有术语 |

### [knowledge/manuals/](./manuals/) — 操作手册

| 文件 | 用途 |
| --- | --- |
| [deployment-runbook-ubuntu-2404.md](./manuals/deployment-runbook-ubuntu-2404.md) | Ubuntu 24.04 生产部署 |
| [manual-database-operations.md](./manuals/manual-database-operations.md) | PostgreSQL 手工操作与迁移 |
| [e2e-gui-verification-automation-runbook.md](./manuals/e2e-gui-verification-automation-runbook.md) | Docker GUI + Playwright 验证 |
| [workflow-video-v1-docker-runbook.md](./manuals/workflow-video-v1-docker-runbook.md) | 视频工作流 v1 Docker 冒烟 |
| [workflow-video-v1-collaborative-uat-guide.md](./manuals/workflow-video-v1-collaborative-uat-guide.md) | W0–W10 协同 UAT |
| [workflow-video-v1-multi-account-e2e-guide.md](./manuals/workflow-video-v1-multi-account-e2e-guide.md) | 多账号 Live/Mock E2E |
| [2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md](./knowledge/manuals/2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md) | Iteration 4 / 设计器 Phase 2 / S-01 人工验收 |
| [2026-08-09-production-release-checklist.md](./knowledge/manuals/2026-08-09-production-release-checklist.md) | 预发、I3-F 与生产上线准入 |

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
| 当前 Task / Session / Checkpoint | 仅通过 `pd task` / `pd session` 命令写 runtime YAML；Markdown 为投影 |
| 版本、Batch、人工审计 | `logs/progress/YYYY-MM-DD-<task>.md` append-first 日志，Evidence 仅引用 Checkpoint |
| 排期与阶段出口 | `roadmap.md` + [计划状态目录](./knowledge/plans/plan-status-catalog.md)（**当前**: [`2026-08-11-f05-iteration5-6-sequencing-plan.md`](./knowledge/plans/2026-08-11-f05-iteration5-6-sequencing-plan.md)） |
| ADR / 坑位 / 术语 | `decisions.md` / `known-issues.md` / `glossary.md` |
| 运维步骤 | `knowledge/manuals/` |

generated runtime、Context、index 与 cache 不手工修改。更新 source 文档后运行 `pd index rebuild` / `pd index verify`，再运行 `pd check`；按需运行 `pd runtime verify`、`pd catalog verify`，最终门禁运行 `pd agent-adapter check` 与 `pd compliance check --profile strict`。Task 完成前先写最终 Checkpoint 并结束 Session，再执行 `pd task complete --write`；YAML runtime 不使用 legacy archive 脚本。
