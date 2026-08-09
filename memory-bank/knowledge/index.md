# Knowledge Index

<!-- BEGIN PARADIGMA AUTO-INDEX -->
<!-- checksum: 96b09f1de8b4785b -->
<!-- generated_by: pd-sync-index.py -->

| Path | Type | Title | Hints | Symbols | Relations |
|------|------|-------|-------|---------|-----------|
| [architecture.md](architecture.md) | `paradigma-architecture` | Project Filum — 系统架构 | 系统架构<br>模块划分<br>目录结构 ... | - | - |
| [contracts/data-contracts.md](contracts/data-contracts.md) | `paradigma-contract` | Project Filum — 数据契约 | 数据契约<br>schema<br>枚举 ... | - | - |
| [contracts/database/core-schema.md](contracts/database/core-schema.md) | `paradigma-contract` | 核心 Schema (IAM / 组织 / HR) | 核心Schema<br>IAM<br>HR ... | - | depends_on:../data-contracts.md |
| [contracts/database/error-schema.md](contracts/database/error-schema.md) | `paradigma-contract` | 错误诊断 Schema | 错误Schema<br>诊断<br>error schema ... | - | depends_on:../data-contracts.md |
| [contracts/database/graph-engine-schema.md](contracts/database/graph-engine-schema.md) | `paradigma-contract` | 图引擎 Schema | 图引擎Schema<br>graph<br>DAG ... | - | depends_on:../data-contracts.md |
| [contracts/database/knowledge-media-schema.md](contracts/database/knowledge-media-schema.md) | `paradigma-contract` | 知识库与附件 Schema | 知识库Schema<br>附件<br>文档 ... | - | depends_on:../data-contracts.md |
| [contracts/database/messaging-schema.md](contracts/database/messaging-schema.md) | `paradigma-contract` | 消息与推送 Schema | 消息Schema<br>通知<br>Push ... | - | depends_on:../data-contracts.md |
| [contracts/database/overview-schema.md](contracts/database/overview-schema.md) | `paradigma-contract` | 总览 Schema | 总览Schema<br>看板<br>公告 ... | - | depends_on:../data-contracts.md |
| [contracts/database/report-schema.md](contracts/database/report-schema.md) | `paradigma-contract` | 汇报中心 Schema | 汇报Schema<br>路由<br>report schema ... | - | depends_on:../data-contracts.md |
| [contracts/database/task-collaboration-schema.md](contracts/database/task-collaboration-schema.md) | `paradigma-contract` | 任务与协同 Schema | 任务Schema<br>模板<br>评论 ... | - | depends_on:../data-contracts.md |
| [contracts/database/workflow-schema.md](contracts/database/workflow-schema.md) | `paradigma-contract` | 工作流与审批 Schema | 工作流Schema<br>审批<br>流程 ... | - | depends_on:../data-contracts.md |
| [contracts/repository-contract.md](contracts/repository-contract.md) | `paradigma-contract` | Project Filum — 仓库契约 | 仓库契约<br>目录协议<br>子项目 ... | - | - |
| [conventions.md](conventions.md) | `paradigma-convention` | Project Filum — 编码与协作规范 | 编码规范<br>命名约定<br>测试 ... | - | - |
| [decisions/adr-001-modular-monolith.md](decisions/adr-001-modular-monolith.md) | `paradigma-decision` | ADR-001: 模块化单体架构 | 模块化单体<br>架构决策<br>modular monolith ... | - | - |
| [decisions/adr-002-arq-worker.md](decisions/adr-002-arq-worker.md) | `paradigma-decision` | ADR-002: 异步 Worker 选型 ARQ | ARQ<br>异步 worker<br>Celery | - | - |
| [decisions/adr-003-openai-sdk.md](decisions/adr-003-openai-sdk.md) | `paradigma-decision` | ADR-003: AI 集成官方 openai SDK | openai SDK<br>AI 集成<br>LangChain | - | - |
| [decisions/adr-004-no-standalone-im.md](decisions/adr-004-no-standalone-im.md) | `paradigma-decision` | ADR-004: 任务协同不建独立 IM | 任务协同<br>IM<br>task_comments ... | - | - |
| [decisions/adr-005-dual-track-workflow.md](decisions/adr-005-dual-track-workflow.md) | `paradigma-decision` | ADR-005: 工作流双轨 | 工作流双轨<br>图引擎<br>dual track ... | - | - |
| [decisions/adr-006-video-workflow-flag.md](decisions/adr-006-video-workflow-flag.md) | `paradigma-decision` | ADR-006: 视频工作流 v1 | 视频工作流<br>Feature开关<br>video workflow ... | - | - |
| [decisions/adr-007-paradigma-alignment.md](decisions/adr-007-paradigma-alignment.md) | `paradigma-decision` | ADR-007: Memory-Bank Paradigma 对齐 | Paradigma 对齐<br>Memory-Bank<br>文档重构 | - | - |
| [decisions/adr-008-graph-template-designer.md](decisions/adr-008-graph-template-designer.md) | `paradigma-decision` | ADR-008: 图模板设计器 | 图模板设计器<br>authoring<br>graph template ... | - | - |
| [decisions/adr-009-single-step-boundary.md](decisions/adr-009-single-step-boundary.md) | `paradigma-decision` | ADR-009: 单步任务产品边界 | 单步任务<br>产品边界<br>single step ... | - | - |
| [decisions/adr-010-task-flow-boundary.md](decisions/adr-010-task-flow-boundary.md) | `paradigma-decision` | ADR-010: 任务流产品边界 | 任务流<br>产品边界<br>task flow ... | - | - |
| [decisions/adr-011-department-schedule.md](decisions/adr-011-department-schedule.md) | `paradigma-decision` | ADR-011: 部门周期调度 | 部门调度<br>F-24<br>department schedule ... | - | - |
| [decisions/adr-012-immutable-definition-run-snapshot.md](decisions/adr-012-immutable-definition-run-snapshot.md) | `paradigma-decision` | ADR-012: 发布定义不可变与 Run 快照 | 发布定义不可变<br>Run 快照<br>定义哈希 ... | - | - |
| [decisions/adr-013-edge-traversal-activation-dependency.md](decisions/adr-013-edge-traversal-activation-dependency.md) | `paradigma-decision` | ADR-013: 路径账本优先于完整 Token 引擎 | 路径账本<br>激活依赖<br>条件 Join ... | - | - |
| [decisions/adr-014-task-work-item-link-boundary.md](decisions/adr-014-task-work-item-link-boundary.md) | `paradigma-decision` | ADR-014: 保留 Task 接口并建立正式工作项 Link | Task 工作项<br>节点 Link<br>双写收口 ... | - | - |
| [decisions/adr-015-approval-handler-reuse.md](decisions/adr-015-approval-handler-reuse.md) | `paradigma-decision` | ADR-015: 通过 Handler 复用现有审批引擎 | 审批 Handler<br>审批引擎复用<br>approval handler ... | - | - |
| [decisions/adr-016-object-authorization-scope-legacy-executor.md](decisions/adr-016-object-authorization-scope-legacy-executor.md) | `paradigma-decision` | ADR-016: 对象级授权、显式 scope 与 legacy executor | 对象级授权<br>scope_mode<br>legacy executor ... | - | - |
| [decisions/adr-017-template-engine-decouple.md](decisions/adr-017-template-engine-decouple.md) | `paradigma-decision` | ADR-017: 模板引擎业务语义解耦 — Tags 替代 run_kind | 模板引擎解耦<br>tags<br>run_kind ... | - | - |
| [decisions/adr-018-domain-neutral-workflow-templates.md](decisions/adr-018-domain-neutral-workflow-templates.md) | `paradigma-decision` | ADR-018: 工作流模板领域中立 — 视频流程作为普通模板包 | 工作流领域中立<br>视频普通模板<br>去视频特殊化 ... | - | - |
| [decisions/adr-019-decision-subject-actor-overlap.md](decisions/adr-019-decision-subject-actor-overlap.md) | `paradigma-decision` | ADR-019: 按决策对象与动作语义处理参与者重叠 | 参与者重叠<br>集合确认<br>独立验收 ... | - | - |
| [decisions/adr-020-published-template-availability-scope.md](decisions/adr-020-published-template-availability-scope.md) | `paradigma-decision` | ADR-020: 已发布模板可用范围作为可变治理元数据 | 已发布模板<br>可用部门<br>增量授权 ... | - | informs:../domains/workflow-graph-engine.md<br>informs:../contracts/data-contracts.md<br>implements:../plans/2026-07-30-template-availability-paradigma-upgrade-plan.md |
| [decisions/decisions.md](decisions/decisions.md) | `paradigma-decision` | ADR 合集 (已拆分) | ADR<br>决策<br>合辑 ... | - | - |
| [domains/architecture/backend-architecture.md](domains/architecture/backend-architecture.md) | `paradigma-domain` | Backend 架构细节 | 后端架构<br>FastAPI<br>service ... | - | - |
| [domains/architecture/core-workflows.md](domains/architecture/core-workflows.md) | `paradigma-domain` | 核心流程 | 核心流程<br>运行时<br>链路 ... | - | - |
| [domains/architecture/frontend-architecture.md](domains/architecture/frontend-architecture.md) | `paradigma-domain` | Frontend 架构细节 | 前端架构<br>Vue<br>组件 ... | - | - |
| [domains/architecture/infra-architecture.md](domains/architecture/infra-architecture.md) | `paradigma-domain` | Infra 架构细节 | 基础设施<br>Docker<br>Nginx ... | - | - |
| [domains/hr-org.md](domains/hr-org.md) | `paradigma-domain` | 领域：组织与人事 (HR & Org) | 组织<br>人事<br>权限 ... | - | - |
| [domains/knowledge-ai.md](domains/knowledge-ai.md) | `paradigma-domain` | 领域：知识库与 AI (Knowledge & AI) | 知识库<br>AI<br>LLM ... | - | - |
| [domains/messaging.md](domains/messaging.md) | `paradigma-domain` | 领域：消息与通知 (Messaging) | 消息<br>通知<br>回执 ... | - | - |
| [domains/task-center.md](domains/task-center.md) | `paradigma-domain` | 领域：任务中心 (Task Center) | 任务中心<br>Inbox<br>跟踪 ... | - | - |
| [domains/workflow-graph-engine.md](domains/workflow-graph-engine.md) | `paradigma-domain` | 领域：工作流图引擎 (Workflow Graph Engine) | 图引擎<br>工作流<br>模板 ... | - | - |
| [domains/workflow-video-v1.md](domains/workflow-video-v1.md) | `paradigma-domain` | 参考模板包：视频工作流 v1 (Workflow Video v1) | 视频工作流<br>选题会<br>W0 ... | - | - |
| [glossary.md](glossary.md) | `paradigma-glossary` | Project Filum — 术语表 | 术语表<br>缩写<br>glossary ... | - | - |
| [known-issues/ki-001-environment-toolchain.md](known-issues/ki-001-environment-toolchain.md) | `paradigma-known-issue` | KI-001: 环境与工具链问题 | 环境问题<br>工具链<br>Windows ... | - | - |
| [known-issues/ki-002-architecture-boundaries.md](known-issues/ki-002-architecture-boundaries.md) | `paradigma-known-issue` | KI-002: 架构边界（易误判非 Bug） | 架构边界<br>Legacy E<br>图引擎 ... | - | - |
| [known-issues/ki-003-test-baseline-drift.md](known-issues/ki-003-test-baseline-drift.md) | `paradigma-known-issue` | KI-003: 测试基线漂移 | 测试基线<br>pytest<br>Playwright ... | - | - |
| [known-issues/ki-004-production-deployment.md](known-issues/ki-004-production-deployment.md) | `paradigma-known-issue` | KI-004: 生产与部署注意事项 | 生产部署<br>环境变量<br>回滚 ... | - | - |
| [known-issues/ki-005-graph-engine-issues.md](known-issues/ki-005-graph-engine-issues.md) | `paradigma-known-issue` | KI-005: 图引擎已知问题 | 图引擎<br>ORM 懒加载<br>max_iterations | - | - |
| [known-issues/ki-006-report-center-history.md](known-issues/ki-006-report-center-history.md) | `paradigma-known-issue` | KI-006: 汇报中心历史问题 | 汇报中心<br>PostgreSQL enum<br>ORM | - | - |
| [known-issues/ki-007-windows-playwright-excluded-port.md](known-issues/ki-007-windows-playwright-excluded-port.md) | `paradigma-known-issue` | KI-007: Windows 保留端口导致 Playwright webServer EACCES | Playwright EACCES<br>4173 端口<br>Windows 保留端口 ... | - | - |
| [known-issues/ki-008-docker-frontend-dependency-volume.md](known-issues/ki-008-docker-frontend-dependency-volume.md) | `paradigma-known-issue` | KI-008: Docker 前端依赖命名卷可能滞后于 lockfile | Vite import-analysis<br>Docker 缺少依赖<br>node_modules 命名卷 ... | - | - |
| [known-issues/ki-009-standalone-action-dual-track.md](known-issues/ki-009-standalone-action-dual-track.md) | `paradigma-known-issue` | KI-009: Standalone Work Item 详情动作仍走旧契约 | standalone<br>开始处理<br>创建人 ... | - | - |
| [known-issues/ki-010-activity-timeline-redesign.md](known-issues/ki-010-activity-timeline-redesign.md) | `paradigma-known-issue` | KI-010: 活动时间线需重做为更有指向性的留痕 | 活动时间线<br>折叠<br>留痕 ... | - | - |
| [known-issues/ki-011-system-admin-business-boundary.md](known-issues/ki-011-system-admin-business-boundary.md) | `paradigma-known-issue` | KI-011: 系统管理员与业务参与权限尚未解耦 | 管理员业务边界<br>系统管理员<br>管理员不参与业务 ... | - | - |
| [known-issues/ki-012-security-scan-release-blockers.md](known-issues/ki-012-security-scan-release-blockers.md) | `paradigma-known-issue` | KI-012: 2026-08-09 安全扫描发现与上线阻断项 | 安全扫描<br>上线阻断<br>IDOR ... | - | - |
| [known-issues/known-issues.md](known-issues/known-issues.md) | `paradigma-known-issue` | 已知问题合辑 (已拆分) | 已知问题<br>合辑<br>known issue | - | - |
| [manuals/2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md](manuals/2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md) | `paradigma-manual` | Iteration 4 · 领域中立 / 运行时 / 设计器 Phase 2 验收 Checklist | Iteration 4 验收<br>领域中立 UAT<br>设计器 Phase 2 ... | - | depends_on:../decisions/adr-018-domain-neutral-workflow-templates.md<br>depends_on:../decisions/adr-019-decision-subject-actor-overlap.md<br>depends_on:../plans/workflow-graph-engine-iteration4-handler-plan.md<br>depends_on:../plans/2026-07-28-template-decouple-phase2-plan.md |
| [manuals/2026-08-09-production-release-checklist.md](manuals/2026-08-09-production-release-checklist.md) | `paradigma-manual` | 2026-08-09 生产上线准入 Checklist | 生产上线<br>发布准入<br>安全检查 ... | - | depends_on:../plans/2026-08-09-rc-employee-trial-plan.md<br>depends_on:../known-issues/ki-012-security-scan-release-blockers.md<br>depends_on:../plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md<br>depends_on:2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md ... |
| [manuals/deployment-runbook-ubuntu-2404.md](manuals/deployment-runbook-ubuntu-2404.md) | `paradigma-manual` | 部署手册 (Ubuntu 24.04) | 部署<br>deployment | - | - |
| [manuals/e2e-gui-verification-automation-runbook.md](manuals/e2e-gui-verification-automation-runbook.md) | `paradigma-manual` | E2E GUI 验证手册 | E2E<br>e2e | - | - |
| [manuals/manual-database-operations.md](manuals/manual-database-operations.md) | `paradigma-manual` | 数据库操作手册 | 数据库<br>database | - | - |
| [manuals/project-presentation-guide.md](manuals/project-presentation-guide.md) | `paradigma-manual` | 项目讲解说明书 | 讲解<br>演示<br>onboarding ... | - | - |
| [manuals/user-manual.md](manuals/user-manual.md) | `paradigma-manual` | 用户说明书 v1.2 | 用户说明<br>user<br>guide | - | - |
| [manuals/workflow-graph-engine-iteration3f-test-runbook.md](manuals/workflow-graph-engine-iteration3f-test-runbook.md) | `paradigma-manual` | 工作流图引擎 Iteration 3-F 测试操作手册 | Iteration 3-F 测试<br>Iteration 4 准入<br>PostgreSQL 强制测试 ... | - | depends_on:../plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md<br>depends_on:../contracts/database/graph-engine-schema.md |
| [manuals/workflow-video-v1-collaborative-uat-guide.md](manuals/workflow-video-v1-collaborative-uat-guide.md) | `paradigma-manual` | 视频协同 UAT 指南 | 视频<br>UAT<br>video ... | - | - |
| [manuals/workflow-video-v1-docker-runbook.md](manuals/workflow-video-v1-docker-runbook.md) | `paradigma-manual` | 视频 Docker 冒烟手册 | 视频<br>Docker<br>video ... | - | - |
| [manuals/workflow-video-v1-multi-account-e2e-guide.md](manuals/workflow-video-v1-multi-account-e2e-guide.md) | `paradigma-manual` | 多账号 E2E 指南 | 多账号<br>E2E<br>multi-account ... | - | - |
| [plans/2026-07-21-template-self-review-fix-plan.md](plans/2026-07-21-template-self-review-fix-plan.md) | `paradigma-plan` | Template Self-Review Deadlock Fix | 模板自审<br>验收人<br>self-review ... | - | - |
| [plans/2026-07-22-template-decouple-phase1-plan.md](plans/2026-07-22-template-decouple-phase1-plan.md) | `paradigma-plan` | Template Engine Decouple — Phase 1 Implementation Plan | 模板引擎解耦<br>Phase 1<br>tags ... | - | - |
| [plans/2026-07-28-template-decouple-phase2-plan.md](plans/2026-07-28-template-decouple-phase2-plan.md) | `paradigma-plan` | Template Engine Decouple — Phase 2 Structured Authoring | 模板引擎解耦 Phase 2<br>结构化编辑<br>ui_profile ... | - | - |
| [plans/2026-07-29-iteration4-preflight-alignment-plan.md](plans/2026-07-29-iteration4-preflight-alignment-plan.md) | `paradigma-plan` | Iteration 4 Preflight — 文档对齐、领域中立与前端稳定化 | Iteration 4 前置<br>文档漂移<br>视频去特殊化 ... | - | - |
| [plans/2026-07-29-video-domain-neutral-migration-inventory.md](plans/2026-07-29-video-domain-neutral-migration-inventory.md) | `paradigma-plan` | 视频模板领域中立迁移清单 | 视频模板去特殊化<br>run_kind 退出<br>通用工作流能力 ... | - | - |
| [plans/2026-07-30-template-availability-paradigma-upgrade-plan.md](plans/2026-07-30-template-availability-paradigma-upgrade-plan.md) | `paradigma-plan` | 已发布模板可用部门治理与 Paradigma 0.5.0 协议升级 | 模板可用部门<br>已发布模板授权<br>范围审计 ... | - | - |
| [plans/2026-08-09-rc-employee-trial-plan.md](plans/2026-08-09-rc-employee-trial-plan.md) | `paradigma-plan` | v0.93.0-rc.1 员工试用与持续开发分流方案 | RC 试用<br>员工内测<br>发布标签 ... | - | depends_on:../manuals/2026-08-09-production-release-checklist.md<br>depends_on:../known-issues/ki-012-security-scan-release-blockers.md<br>related_to:../roadmap.md |
| [plans/2026-08-09-security-release-readiness-plan.md](plans/2026-08-09-security-release-readiness-plan.md) | `paradigma-plan` | 安全问题处置与上线准备计划 | 安全问题<br>上线准备<br>发布门禁 ... | - | - |
| [plans/2026-08-10-iteration4-uat-preflight-plan.md](plans/2026-08-10-iteration4-uat-preflight-plan.md) | `paradigma-plan` | 2026-08-10 Iteration 4 UAT 验收准备计划 | Iteration 4 验收准备<br>UAT 前置检查<br>S-01 验收 ... | - | depends_on:2026-08-10-template-governance-audit-plan.md<br>depends_on:../manuals/2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md |
| [plans/2026-08-10-template-governance-audit-plan.md](plans/2026-08-10-template-governance-audit-plan.md) | `paradigma-plan` | 模板范围与父子依赖数据治理计划 | 模板数据检查<br>可用部门<br>父子模板 ... | - | depends_on:../decisions/adr-020-published-template-availability-scope.md<br>depends_on:./2026-08-09-rc-employee-trial-plan.md<br>validates:../manuals/2026-08-09-production-release-checklist.md |
| [plans/implementation-plan.md](plans/implementation-plan.md) | `paradigma-plan` | 实施计划主线 | 实施计划<br>implementation | - | - |
| [plans/improvements-stage2-implementation-plan.md](plans/improvements-stage2-implementation-plan.md) | `paradigma-plan` | Stage 2 改进计划 | Stage2<br>stage2 | - | - |
| [plans/paradigma-memory-bank-refactor-plan.md](plans/paradigma-memory-bank-refactor-plan.md) | `paradigma-plan` | Paradigma 对齐方案 | Paradigma<br>paradigma | - | - |
| [plans/s01-task-statistics-plan.md](plans/s01-task-statistics-plan.md) | `paradigma-plan` | S-01 任务统计实施计划（已批准） | S-01<br>任务统计计划<br>统计口径 ... | - | - |
| [plans/task-center-enhance.md](plans/task-center-enhance.md) | `paradigma-plan` | TCE 增强计划 | TCE<br>tce | - | - |
| [plans/task-center-v2-implementation-plan.md](plans/task-center-v2-implementation-plan.md) | `paradigma-plan` | TC v2 实施计划 | TC<br>v2<br>task ... | - | - |
| [plans/tc-p2-views-stats-plan.md](plans/tc-p2-views-stats-plan.md) | `paradigma-plan` | TC-P2 落地计划 | TC-P2<br>tc-p2 | - | - |
| [plans/ui-information-architecture-plan.md](plans/ui-information-architecture-plan.md) | `paradigma-plan` | UI IA 计划 | UI<br>IA<br>ui ... | - | - |
| [plans/ui-refactor-spec-v2.md](plans/ui-refactor-spec-v2.md) | `paradigma-plan` | UI 重构规格 v2 | UI<br>重构<br>ui ... | - | - |
| [plans/workflow-graph-engine-iteration1-implementation-plan.md](plans/workflow-graph-engine-iteration1-implementation-plan.md) | `paradigma-plan` | 工作流图引擎 Iteration 1 实施计划 | Iteration 1<br>对象级授权<br>Run 快照 ... | - | - |
| [plans/workflow-graph-engine-iteration2-implementation-plan.md](plans/workflow-graph-engine-iteration2-implementation-plan.md) | `paradigma-plan` | 工作流图引擎 Iteration 2 实施计划 | Iteration 2<br>路径语义<br>traversal ... | - | - |
| [plans/workflow-graph-engine-iteration3-implementation-plan.md](plans/workflow-graph-engine-iteration3-implementation-plan.md) | `paradigma-plan` | 工作流图引擎 Iteration 3 实施计划 | Iteration 3<br>HumanTask Link<br>写所有权 ... | - | - |
| [plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md](plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md) | `paradigma-plan` | 工作流图引擎 Iteration 3-F · Iteration 4 硬性准入实施计划 | Iteration 3-F<br>Iteration 4 准入<br>写所有权 ... | - | - |
| [plans/workflow-graph-engine-iteration4-handler-plan.md](plans/workflow-graph-engine-iteration4-handler-plan.md) | `paradigma-plan` | 工作流图引擎 Iteration 4 · 业务能力 Handler 化实施计划 | Iteration 4<br>Handler 化<br>Capability Result ... | - | - |
| [plans/workflow-graph-engine-upgrade-iteration-plan.md](plans/workflow-graph-engine-upgrade-iteration-plan.md) | `paradigma-plan` | 工作流图引擎稳健升级迭代方案 | 图引擎升级<br>工作流边界<br>运行时正确性 ... | - | - |
| [plans/workflow-refactor-implementation-plan.md](plans/workflow-refactor-implementation-plan.md) | `paradigma-plan` | 工作流重构计划 | 工作流重构<br>workflow<br>refactor | - | - |
| [plans/workflow-video-v1-implementation-plan.md](plans/workflow-video-v1-implementation-plan.md) | `paradigma-plan` | 视频 v1 实施计划 | 视频<br>v1<br>video ... | - | - |
| [plans/workflow-video-v1-ui-simplification-design.md](plans/workflow-video-v1-ui-simplification-design.md) | `paradigma-plan` | UI 简化设计 | UI<br>简化<br>ui ... | - | - |
| [plans/workflow-video-v1-w0-adr.md](plans/workflow-video-v1-w0-adr.md) | `paradigma-plan` | W0 ADR | W0<br>ADR<br>w0 ... | - | - |
| [project-brief.md](project-brief.md) | `paradigma-project-brief` | Project Filum — 项目身份卡片 | 项目愿景<br>受众<br>功能边界 ... | - | - |
| [roadmap.md](roadmap.md) | `paradigma-plan` | Project Filum — 路线图 | 路线图<br>里程碑<br>TC-Transform ... | - | related_to:./domains/task-center.md |

<!-- END PARADIGMA AUTO-INDEX -->
