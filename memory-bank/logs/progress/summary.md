# Progress Summary

Generated at: 2026-08-12 00:52

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
| [2026-08-11-f05-task-detail-action-coordination.md](2026-08-11-f05-task-detail-action-coordination.md) | 2026-08-11 F-05 任务详情动作协调拆分 | 新增 `useTaskDetailActions`：统一通用状态流转、交付提交/验收、审批驳回、集合关闭、延期、对话框/表单/loading 和动作后刷新。 |
| [2026-08-11-v0.93.0-rc.2-template-visibility-hotfix.md](2026-08-11-v0.93.0-rc.2-template-visibility-hotfix.md) | v0.93.0-rc.2 部门负责人模板可见性热修 | 根因：前端把页面级模板管理能力直接映射为 `scope=manage`，导致全局 ACTIVE 和跨部门共享模板虽可读、可实例化，却从部门负责人列表中消失。 |
| [2026-08-12-f05-task-detail-activity-timeline.md](2026-08-12-f05-task-detail-activity-timeline.md) | 2026-08-12 F-05 任务详情活动时间线拆分 | 新增 `TaskDetailActivityTimeline`，承接空状态、评论、内部备注标记、评论附件、任务日志和摘要格式化。 |
| [2026-08-12-f05-task-detail-materials-comments.md](2026-08-12-f05-task-detail-materials-comments.md) | 2026-08-12 F-05 任务资料附件与评论留痕拆分 | 新增 `useTaskDetailCollaboration`，统一任务资料多文件上传、评论提交、成功/失败状态、表单复位与详情刷新。 |
| [2026-08-12-f05-task-detail-workflow-presentation.md](2026-08-12-f05-task-detail-workflow-presentation.md) | 2026-08-12 F-05 任务详情工作流展示收口 | 新增 `TaskDetailWorkflowPresentation`，按 domain-neutral Profile/capability 选择 Tracking、Run Dashboard、Capture、Deliverable 与 Aggregate 兼容面板，并承接最近 Run Event。 |
| [2026-08-12-iteration5a-projection-contract.md](2026-08-12-iteration5a-projection-contract.md) | 2026-08-12 Iteration 5-A 投影契约与加法迁移 | 新增 HOT `projection-contract.md`，从现有 inbox/tracking/history、Run detail 和 Task activity 反向固定字段来源、canonical identity、授权复核、稳定排序、版本与重建边界。 |
