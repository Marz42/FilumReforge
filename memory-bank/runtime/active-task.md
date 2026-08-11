---
type: paradigma-runtime-state
title: Active Task
description: 主开发线推进 F-05 第二批，提取任务详情动作提交协调。
tags: [runtime, active-task, mainline, task-center, frontend, f-05]
timestamp: 2026-08-11T23:27:48+08:00
paradigma:
  layer: runtime
  temperature: hot
  lifecycle: ephemeral
  okf_export: false
  update_policy: agent-editable
  archive_to: /memory-bank/logs/progress/
---

# Active Task

## Task ID

f05-task-detail-action-coordination-2026-08-11

## User Request

完成 Memory-Bank 漂移修正后继续主开发线；在数据协调首批基础上，从 `TaskDetailShell.vue` 提取动作提交状态与命令协调，保持现有界面、权限和业务语义不变。

## Current Status

engineering-complete / follow-up-planned — Memory-Bank 漂移已校准；F-05 第二批已用 `useTaskDetailActions` + `useTaskAssignmentActions` 收口命令、副作用和提交状态，Shell 保留权限/Profile 与页面编排。全量 69 files / 197 tests、type-check、双 lint、build 通过；F-05 总体仍为进行中。

## Checklist

- [x] 延续既定边界：不动 KI-011、I3-F 切流、系统管理员业务边界和 RC 标签
- [x] 盘点 `TaskDetailShell` 加载职责，确认首次打开存在两条加载路径且快速切换缺少旧请求失效保护
- [x] 提取 `useTaskDetailData`，统一主任务、附件、活动、关注人、图实例/事件和用户/部门参考数据
- [x] 新任务主记录优先显示，可选数据独立降级；切换时先清空旧任务附属数据
- [x] 用请求版本保证 last-selection-wins，清空选择会使在途请求失效
- [x] 增加 composable 单测与壳层首次/切换加载回归
- [x] F-05 完成时为 68 files / 190 tests；RC2 回流后为 68 files / 191 tests，type-check 通过
- [x] 更新 Paradigma 索引并形成本批独立提交（提交完成后以 Git 记录为准）
- [x] 对齐 RC2、当前主线测试/lint 基线及任务中心/数据契约活文档
- [x] 固定动作协调边界：Shell 保留权限/Profile，composable 接管命令、副作用与提交状态
- [x] 新增 `useTaskDetailActions` 单测并迁移状态流转、交付、握手/转办、集合关闭与延期
- [x] 避免制造新巨石：通用动作 composable 304 行，接单/转办 composable 178 行
- [x] 完成 69 files / 197 tests、type-check、ESLint、Oxlint、build 并更新 F-05 进度记录
- [ ] F-05 下一批：提取任务资料附件与评论/留痕板块
- [ ] 在目标环境运行“数据检查”和“验收准备”，清零确定错误与 P-01～P-04 阻断
- [ ] 员工按清单完成 Iteration 4 / 设计器 Phase 2 / S-01 UAT，并记录账号、模板、Run ID 与结论

## Relevant Knowledge

- `memory-bank/knowledge/plans/2026-08-09-security-release-readiness-plan.md`
- `memory-bank/knowledge/plans/2026-08-09-rc-employee-trial-plan.md`
- `memory-bank/knowledge/plans/2026-08-10-template-governance-audit-plan.md`
- `memory-bank/knowledge/plans/2026-08-10-iteration4-uat-preflight-plan.md`
- `memory-bank/knowledge/plans/2026-08-10-f05-task-detail-data-coordination-plan.md`
- `memory-bank/knowledge/plans/2026-08-11-f05-task-detail-action-coordination-plan.md`
- `memory-bank/knowledge/manuals/2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md`
- `memory-bank/knowledge/manuals/deployment-runbook-ubuntu-2404.md`
- `memory-bank/knowledge/manuals/2026-08-09-production-release-checklist.md`
- `memory-bank/knowledge/plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md`
- `memory-bank/knowledge/decisions/adr-020-published-template-availability-scope.md`
- `memory-bank/knowledge/known-issues/ki-011-system-admin-business-boundary.md`

## Blockers

- 无继续开发的代码阻碍。
- F-05 第二批无代码阻碍；下一批资料/评论板块仍须保持附件可见性、上传预算、内部评论权限和刷新时机不变。
- 人工 UAT 仍需要目标环境真实账号、部门、模板和任务样本；系统不会自动造业务数据或代替业务签字。
- I3-F、真实 TLS/secret/backup/restore 与生产变更窗口继续作为外部门禁，不阻断主开发。

## Notes

- `v0.93.0-rc.1` 保留在 `2260bd5`；部门负责人模板可见性热修已固定为 `v0.93.0-rc.2`（release commit `4d15829`），两个标签均不得移动。
- 热修功能提交已回流主线为 `d7927bc`；未把 RC1 之后的主线功能反向带入 RC2。
- RC 环境不得与继续开发环境共用数据库、Redis 或附件存储。
- KI-011 按用户决定暂不推进；本批次不扩大系统管理员业务权限，也不改变生产切流状态。
