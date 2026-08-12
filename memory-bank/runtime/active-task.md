---
type: paradigma-runtime-state
title: Active Task
description: Iteration 5-A/B 工程完成；等待 PostgreSQL 迁移证据，下一开发批为 5-C Shadow Comparison。
tags: [runtime, active-task, mainline, workflow-graph, iteration-5, projection]
timestamp: 2026-08-12T12:05:50+08:00
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

iteration5b-projector-rebuild-2026-08-12

## User Request

检查 Memory-Bank 后继续主开发：在 5-A 三类读模型契约上完成 checkpoint、幂等 projector、失败隔离、单 Task/单 Run/全量高水位 rebuild，并保持用户读路径不变。

## Current Status

Iteration 5-A/B engineering-complete / PostgreSQL evidence pending — 三类读模型外新增 `ProjectionCheckpoint` 和单 head `20260812_02`；复用 Run Event、Task Log、Task Comment 三条持久化事实流，完成逐流幂等消费、失败隔离、单 Task/单 Run/全量高水位重建、显式重建 CLI 和 ARQ 周期任务。SQLite expand/downgrade、PostgreSQL 增量离线 SQL、模型/架构/worker 测试及后端 479 项全量回归通过；本机无可用 Docker/PostgreSQL，生产方言 head↔base 测试保持登记 skip。用户读路径、ROOT shell 和兼容写入均未改变，下一批为 5-C shadow comparison。

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
- [x] 固定 F-05 → Iteration 5 → 稳定观察 → Iteration 6 的正式顺序
- [x] 将过时计划明确标为 completed 或 legacy，并生成计划状态目录
- [x] F-05 第三批：先写测试，再提取任务资料附件与评论/留痕协调
- [x] 完成 70 files / 203 tests、type-check、ESLint、Oxlint 与 build
- [x] 重新评估活动时间线/工作流面板：活动时间线需要第四批，工作流编排在其后复评
- [x] F-05 第四批：测试先行提取现有活动时间线展示，不混入 KI-010 重设计
- [x] 完成 71 files / 206 tests、type-check、ESLint、Oxlint 与 build
- [x] 复评剩余职责：工作流面板、Run Event 与图节点追踪适合作为 F-05 收口批
- [x] F-05 收口批：测试先行提取工作流展示边界并确认 Shell 只保留壳层编排
- [x] 完成 73 files / 211 tests、type-check、ESLint、Oxlint 与 build；F-05 正式结项
- [x] Iteration 5-A：盘点任务中心、Run 摘要与节点时间线字段来源及对象授权入口
- [x] 固定三类投影的身份、状态、授权、游标、版本、owner 与重建契约
- [x] 新增 SQLAlchemy 模型和 Expand-only Alembic 迁移，不回填、不切读
- [x] 增加模型/迁移/owner 边界测试，并完成 SQLite expand/downgrade 与 PostgreSQL 增量离线 SQL
- [x] Iteration 5-B：固定三源流 checkpoint、稳定时间+UUID cursor 与失败/重建语义
- [x] 测试先行实现幂等 Task/Run/Timeline projector，旧 revision 默认拒绝覆盖
- [x] 实现单 Task、单 Run 与捕获源流高水位的全量重建
- [x] 实现独立 ARQ 周期消费；单流失败另事务记录且不阻断其他流或业务事实
- [x] 完成 Alembic 单 head `20260812_02`、PostgreSQL 增量离线 SQL与后端 479 collected / 447 passed / 32 skipped / 0 failed
- [ ] 在可用 PostgreSQL 上执行 Alembic head↔base 严格专项，确认生产方言约束与回滚
- [ ] Iteration 5-C：单独计划字段映射、差异分级、采样/lag 口径与隐私边界，再实现只记录不切流的 shadow comparison
- [ ] 在目标环境运行“数据检查”和“验收准备”，清零确定错误与 P-01～P-04 阻断
- [ ] 员工按清单完成 Iteration 4 / 设计器 Phase 2 / S-01 UAT，并记录账号、模板、Run ID 与结论

## Relevant Knowledge

- `memory-bank/knowledge/plans/2026-08-09-security-release-readiness-plan.md`
- `memory-bank/knowledge/plans/2026-08-09-rc-employee-trial-plan.md`
- `memory-bank/knowledge/plans/2026-08-10-template-governance-audit-plan.md`
- `memory-bank/knowledge/plans/2026-08-10-iteration4-uat-preflight-plan.md`
- `memory-bank/knowledge/plans/2026-08-10-f05-task-detail-data-coordination-plan.md`
- `memory-bank/knowledge/plans/2026-08-11-f05-task-detail-action-coordination-plan.md`
- `memory-bank/knowledge/plans/2026-08-11-f05-task-detail-materials-comments-plan.md`
- `memory-bank/knowledge/plans/2026-08-12-f05-task-detail-activity-timeline-plan.md`
- `memory-bank/knowledge/plans/2026-08-12-f05-task-detail-workflow-presentation-plan.md`
- `memory-bank/knowledge/plans/2026-08-12-iteration5a-projection-contract-plan.md`
- `memory-bank/knowledge/plans/2026-08-12-iteration5b-projector-rebuild-plan.md`
- `memory-bank/knowledge/plans/2026-08-11-f05-iteration5-6-sequencing-plan.md`
- `memory-bank/knowledge/plans/plan-status-catalog.md`
- `memory-bank/knowledge/manuals/2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md`
- `memory-bank/knowledge/manuals/deployment-runbook-ubuntu-2404.md`
- `memory-bank/knowledge/manuals/2026-08-09-production-release-checklist.md`
- `memory-bank/knowledge/plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md`
- `memory-bank/knowledge/decisions/adr-020-published-template-availability-scope.md`
- `memory-bank/knowledge/known-issues/ki-011-system-admin-business-boundary.md`

## Blockers

- 无继续开发的代码阻碍。
- Iteration 5-A/B 无代码阻碍，工程实现已完成。
- 本机 Docker daemon 不存在且没有可达 PostgreSQL；生产方言 head↔base 是 5-A 的剩余验证门禁，不能用 SQLite 代替。
- 该外部证据不阻止 5-C/5-D 的加法与影子代码开发，但在证据完成前不得进行 5-E 读侧切流。
- 人工 UAT 仍需要目标环境真实账号、部门、模板和任务样本；系统不会自动造业务数据或代替业务签字。
- I3-F、真实 TLS/secret/backup/restore 与生产变更窗口继续作为外部门禁，不阻断主开发。

## Notes

- `v0.93.0-rc.1` 保留在 `2260bd5`；部门负责人模板可见性热修已固定为 `v0.93.0-rc.2`（release commit `4d15829`），两个标签均不得移动。
- 热修功能提交已回流主线为 `d7927bc`；未把 RC1 之后的主线功能反向带入 RC2。
- RC 环境不得与继续开发环境共用数据库、Redis 或附件存储。
- KI-011 按用户决定暂不推进；Iteration 5-A 不扩大系统管理员业务权限，也不改变生产切流状态。
