---
type: paradigma-runtime-state
title: Active Task
description: 已发布模板可用部门治理与 Paradigma 0.5.0 协议升级。
tags: [runtime, active-task, workflow-template, paradigma]
timestamp: 2026-07-30T02:32:40+08:00
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

template-availability-paradigma-050

## User Request

实现通用的已发布模板可用部门管理并在前端体现；将 Memory-Bank Paradigma 协议升级到上游最新版并更新相关系统 Prompt。

## Current Status

completed — 通用模板 scope 治理和 Paradigma 0.5.0 协议升级均已完成并通过全量回归，等待下一项用户任务。

## Checklist

- [x] 盘点模板 scope、父子模板引用和管理权限
- [x] 核对 Paradigma 上游最新版 `0.5.0`
- [x] 实现 ACTIVE 模板 scope 单调扩大与审计 API
- [x] 实现前端可用部门管理与审计历史
- [x] 升级三态运行协议、独立 session logs 与系统 Prompt
- [x] 完成全量测试、文档同步和提交

## Relevant Knowledge

- `memory-bank/knowledge/plans/2026-07-30-template-availability-paradigma-upgrade-plan.md`
- `memory-bank/knowledge/domains/workflow-graph-engine.md`
- `memory-bank/knowledge/contracts/data-contracts.md`
- `memory-bank/knowledge/decisions/adr-018-domain-neutral-workflow-templates.md`
- `docs/rfc/paradigma-okf-compatible-runtime.md`

## Blockers

- 无。上游参考克隆的 fast-forward 曾因网络审批超时未完成；本次版本和协议差异已通过官方 GitHub 主分支核验并记录 commit。

## Notes

- Iteration 4 A–E 已完成；I3-F 生产门禁、系统管理员业务边界和先行发布仍按原计划保留。
- 已发布模板原地缩小范围继续禁止，避免改变进行中或尚待派生子 Run 的授权语义。
