---
type: paradigma-runtime-state
title: Active Task
description: 固定 v0.93.0-rc.1 员工试用候选并保留生产门禁。
tags: [runtime, active-task, release-candidate, employee-trial]
timestamp: 2026-08-09T23:40:00+08:00
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

rc-0.93.0-employee-trial-2026-08-09

## User Request

将已完成的 Iteration 4、安全加固、前端修复和低风险质量清理固定为 `v0.93.0-rc.1`，供隔离环境员工试用；后续开发继续推进，生产门禁保持独立。

## Current Status

rc-fixed / trial-deployment-pending — 本地完整门禁通过，版本与发布材料已固定为 `v0.93.0-rc.1`；等待隔离员工试用环境部署。

## Checklist

- [x] 校准 implementation-plan、roadmap、测试基线和当前文档中的旧 progress 协议引用
- [x] 将 6 项扫描发现归档为可追踪的安全上线清单
- [x] 修复可信代理/认证限流身份问题
- [x] 修复工作流实例、模板读写与组织关系对象授权
- [x] 限制 OOXML 预览解析资源预算
- [x] 执行本地全量回归、静态配置检查、Alembic head 与等价 release gate
- [x] 更新上线状态、残余风险与目标环境操作清单
- [x] 记录 RC 不可变标签、隔离环境、持续开发与热修回流规则
- [x] 固定版本、完成最终回归并创建 `v0.93.0-rc.1`
- [ ] 在隔离员工试用环境从该标签部署并核对 health version
- [ ] 在预发/生产目标环境完成 TLS、secret、备份恢复、Linux release script、I4 UAT 与 I3-F 最终证据

## Relevant Knowledge

- `memory-bank/knowledge/plans/2026-08-09-security-release-readiness-plan.md`
- `memory-bank/knowledge/plans/2026-08-09-rc-employee-trial-plan.md`
- `memory-bank/knowledge/manuals/deployment-runbook-ubuntu-2404.md`
- `memory-bank/knowledge/manuals/2026-08-09-production-release-checklist.md`
- `memory-bank/knowledge/plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md`
- `memory-bank/knowledge/decisions/adr-020-published-template-availability-scope.md`
- `memory-bank/knowledge/known-issues/ki-011-system-admin-business-boundary.md`

## Blockers

- 无继续开发的代码阻碍。目标环境 I3-F 回填、连续 7 天观测、真实 TLS/secret/backup/restore 与人工 UAT 无法由本地代码验证替代，必须保持为生产上线外部门禁。

## Notes

- 安全扫描针对 `d4a1d9d`；2026-08-09 当前工作树已闭合 6 项发现。
- `Security Issue(temp)` 是用户提供的临时扫描材料，原始文件不作为运行时产物提交；权威处置结论写入 Memory-Bank。
- RC 环境不得与继续开发环境共用数据库、Redis 或附件存储；已固定标签不得移动。
