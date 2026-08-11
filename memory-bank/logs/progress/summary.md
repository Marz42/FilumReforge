# Progress Summary

Generated at: 2026-08-11 22:54

This file summarizes progress logs without deleting or rewriting the source session logs.

| Log | Title | First Signal |
|-----|-------|--------------|
| [2026-07-30-template-availability-paradigma-050.md](2026-07-30-template-availability-paradigma-050.md) | Template Availability Governance and Paradigma 0.5.0 Upgrade | 为普通已发布模板提供可用部门管理并在前端体现；将 Memory-Bank Paradigma 协议和相关 Prompt 升级到上游最新版。 |
| [2026-08-04-fix-template-scope-tree-select.md](2026-08-04-fix-template-scope-tree-select.md) | Fix Template Scope Tree-Select Binding | 手动测试发现可用部门逻辑异常：无论选择哪些部门都显示「已对所有部门可用」。定位后要求完成 P0（修复）与 P1（回归测试）。 |
| [2026-08-09-iteration4-uat-checklist.md](2026-08-09-iteration4-uat-checklist.md) | Iteration 4 UAT Checklist and Scope Fix Commit | 将 Iteration 4 领域中立、运行时与设计器 Phase 2 验收方案落成 checklist，并提交当前工作区更改。 |
| [2026-08-09-security-release-readiness.md](2026-08-09-security-release-readiness.md) | 安全扫描处置与上线准备 | 校准主计划、路线图、架构/数据契约、测试基线、部署手册与当前任务。 |
| [2026-08-09-v0.93.0-rc.1-release-candidate.md](2026-08-09-v0.93.0-rc.1-release-candidate.md) | v0.93.0-rc.1 员工试用候选固定 | 以不可变注释标签、隔离数据环境、RC 热修递增和热修回流为核心，记录员工试用与持续开发分流方案。 |
| [2026-08-10-f05-task-detail-data-coordination.md](2026-08-10-f05-task-detail-data-coordination.md) | 2026-08-10 F-05 任务详情数据协调拆分 | 新增 `useTaskDetailData`，从详情壳层接管七组详情/参考数据和 loading 状态。 |
| [2026-08-10-iteration4-uat-preflight.md](2026-08-10-iteration4-uat-preflight.md) | 2026-08-10 Iteration 4 UAT 验收准备 | 新增只读 `GET /api/v1/workflow-graph/templates/uat-preflight`，聚合模板治理、协同部门、通用/视频模板、设计器草稿与 S-01 当前月样本。 |
| [2026-08-10-template-governance-audit.md](2026-08-10-template-governance-audit.md) | 模板范围与父子依赖数据治理 | `v0.93.0-rc.1` 保持不可变，主开发线在标签之后恢复；KI-011 明确排除在本批次之外。 |
| [2026-08-11-v0.93.0-rc.2-template-visibility-hotfix.md](2026-08-11-v0.93.0-rc.2-template-visibility-hotfix.md) | v0.93.0-rc.2 部门负责人模板可见性热修 | ../../knowledge/decisions/adr-020-published-template-availability-scope.md |
