---
type: paradigma-runtime-state
title: Active Task
description: 主开发线推进模板可用范围与父子模板依赖的数据治理。
tags: [runtime, active-task, mainline, template-governance]
timestamp: 2026-08-10T00:20:00+08:00
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

mainline-template-governance-2026-08-10

## User Request

在不改动 KI-011、I3-F 生产切流和 RC 标签的前提下恢复主开发，优先补齐模板可用范围数据盘点、父子模板引用检查与安全修正入口。

## Current Status

committed / uat-pending — 模板数据检查后端、前端入口、修正版派生路径和自动化测试已完成并提交；等待用户/目标环境验收。`v0.93.0-rc.1` 保持不可变，员工试用部署仍可并行。

## Checklist

- [x] 明确本批次边界：不动 KI-011、I3-F 切流、系统管理员业务边界和 RC 标签
- [x] 增加只读模板治理审计：global 人工确认、空 departments、缺失/停用部门
- [x] 检查模板配置与节点配置中的 `child_template_code`，以及 `on_complete.next_template_code`
- [x] 检查旧子模板编码和父子模板可用部门不兼容
- [x] 在模板管理页加入“数据检查”，支持打开草稿或安全派生修正版
- [x] 补齐后端与前端自动化测试并完成全量单元回归、类型检查、构建和变更文件 lint
- [x] 更新数据契约、架构、路线图、上线清单与会话记录
- [ ] 在目标环境执行“数据检查”，由业务负责人确认 intentional global 并处理真实数据问题
- [ ] 员工完成 Iteration 4 / 设计器 Phase 2 / S-01 UAT，主线再按反馈进入下一批

## Relevant Knowledge

- `memory-bank/knowledge/plans/2026-08-09-security-release-readiness-plan.md`
- `memory-bank/knowledge/plans/2026-08-09-rc-employee-trial-plan.md`
- `memory-bank/knowledge/plans/2026-08-10-template-governance-audit-plan.md`
- `memory-bank/knowledge/manuals/deployment-runbook-ubuntu-2404.md`
- `memory-bank/knowledge/manuals/2026-08-09-production-release-checklist.md`
- `memory-bank/knowledge/plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md`
- `memory-bank/knowledge/decisions/adr-020-published-template-availability-scope.md`
- `memory-bank/knowledge/known-issues/ki-011-system-admin-business-boundary.md`

## Blockers

- 无继续开发的代码阻碍。真实模板哪些应为 global、哪些部门应获授权属于业务决策，审计工具只报告与引导新版本修正，不自动替用户决定。
- I3-F、真实 TLS/secret/backup/restore 与人工 UAT 继续作为外部门禁，不阻断主开发。

## Notes

- `v0.93.0-rc.1` 已固定在 `2260bd5`，主线提交不得移动该标签。
- RC 环境不得与继续开发环境共用数据库、Redis 或附件存储。
- KI-011 按用户决定暂不推进；本批次不扩大系统管理员业务权限，也不改变生产切流状态。
