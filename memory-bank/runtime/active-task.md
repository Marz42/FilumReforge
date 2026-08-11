---
type: paradigma-runtime-state
title: Active Task
description: 固定 v0.93.0-rc.2 模板可见性热修并回流主开发线。
tags: [runtime, active-task, release-candidate, employee-trial, hotfix, template-visibility]
timestamp: 2026-08-11T22:40:49+08:00
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

rc-0.93.0-template-visibility-hotfix-2026-08-11

## User Request

针对 `v0.93.0-rc.1` 员工实际试用中发现的“部门负责人看不到本应可用的任务模板”问题，按测试先行完成最小热修，固定 `v0.93.0-rc.2`，并把同一修复回流主开发线。

## Current Status

rc2-ready / trial-retest-pending — 根因与回归已闭合，`v0.93.0-rc.2` 固定后等待员工试用环境升级复测；正式生产准入仍保持独立门禁。

## Checklist

- [x] 在 `v0.93.0-rc.1` 基线上复现：管理模式列表错误取代可读模板列表
- [x] 先增加共享模板可见、可实例化且无越权管理操作的前端回归测试，并确认旧实现失败
- [x] 合并“可读 ACTIVE”与“可管理”两组模板，按模板 ID 精确显示管理动作
- [x] 保持后端对象级授权不变，并验证部门 scope 读取专项
- [x] 执行前端全量单测、类型检查、构建与发布门禁
- [x] 更新版本、Changelog、RC 分流方案、路线图和发布记录
- [x] 创建不可变 `v0.93.0-rc.2` release tag
- [x] 将修复提交回流主开发线，不带入 RC 之后的其他开发内容
- [ ] 在员工试用环境升级到 `v0.93.0-rc.2` 并以真实部门负责人账号复测
- [ ] 在预发/生产目标环境完成 TLS、secret、备份恢复、Linux release script、I4 UAT 与 I3-F 最终证据

## Relevant Knowledge

- `memory-bank/knowledge/plans/2026-08-09-security-release-readiness-plan.md`
- `memory-bank/knowledge/plans/2026-08-09-rc-employee-trial-plan.md`
- `memory-bank/logs/progress/2026-08-11-v0.93.0-rc.2-template-visibility-hotfix.md`
- `memory-bank/knowledge/manuals/deployment-runbook-ubuntu-2404.md`
- `memory-bank/knowledge/manuals/2026-08-09-production-release-checklist.md`
- `memory-bank/knowledge/plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md`
- `memory-bank/knowledge/decisions/adr-020-published-template-availability-scope.md`
- `memory-bank/knowledge/known-issues/ki-011-system-admin-business-boundary.md`

## Blockers

- 无继续开发的代码阻碍。RC2 仍需真实账号复测；目标环境 I3-F 回填、连续 7 天观测、真实 TLS/secret/backup/restore 与人工 UAT 无法由本地代码验证替代，必须保持为正式生产上线外部门禁。

## Notes

- `v0.93.0-rc.1` 继续保留且不得移动；RC2 只包含模板可见性修复及发布材料。
- 前端此前把页面级 `canManage` 直接映射为 `scope=manage`，导致全局/跨部门共享模板虽可读、可实例化，却从部门负责人列表中消失。
- 修复不允许部门负责人修改全局或超出其完整管理范围的模板；管理按钮仅依据管理查询返回的模板 ID 展示。
- RC 环境不得与继续开发环境共用数据库、Redis 或附件存储；已固定标签不得移动。
