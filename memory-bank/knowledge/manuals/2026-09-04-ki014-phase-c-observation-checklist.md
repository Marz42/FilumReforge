---
type: paradigma-manual
title: "KI-014 Phase C 兼容观察清单"
description: "Phase A+B 部署后、Phase D contract 前的双读观察与并行门禁清单。"
tags: [manual, ki-014, observation, phase-c, checklist]
timestamp: 2026-09-13T00:20:00+08:00
paradigma:
  retrieval_hints:
    zh: [KI-014, 兼容观察, Phase C]
  relations:
    related_to:
      - ../plans/2026-08-26-ki014-schema-drift-remediation-plan.md
      - manual-database-operations.md
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: decision
---

# KI-014 Phase C 兼容观察清单

> 部署 Phase A（metadata / `CompatibleValueEnum` 双读）+ Phase B（`20260827_01` expand）之后使用。
> **不关闭** Task Center projection fallback；**不开** Iteration 6；**不执行** Phase D contract。

## 配套工具与状态口径（2026-09-12 整合）

工程基线为 `CompatibleValueEnum` + `20260827_01`，配套只读工具为 `backend/app/scripts/audit_ki014_schema_compatibility.py`。部署前旧 revision 按 KI-014 计划 §3 盘点；工具默认检查 post-expand revision 和六个约束，不能通过修改期望值或 `--no-fail` 把未迁移环境标为通过。

在 `backend` 目录设置环境负责人提供的只读 `POSTGRES_DSN` 后运行 `python -m app.scripts.audit_ki014_schema_compatibility`，兼容部署后的观察加带时区的 `--since`。工具只提供自动聚合证据；本清单 C1–C6、完整业务周期与人工批准仍需单独记录。

原远端任务的 completed 仅表示 A/B 工程收尾。统一基线中 KI-014 总任务保持 blocked，原因是目标观察与独立 contract 尚未完成；此状态不阻止独立的工程开发批次。

## 应用观察（至少一个完整业务周期）

| # | 检查项 | 通过标准 | 隔离环境备注 |
|---|---|---|---|
| C1 | 历史大写 status 可读 | `TODO/DOING/REVIEW/DONE` 映射为 TaskStatus，无解码错误 | `CompatibleValueEnum` 读侧 `lower()` |
| C2 | 新写入仅为小写 | DB 新行 `status` ∈ lowercase set | bind 写 `.value` |
| C3 | `blocked` 可写可读 | VARCHAR(16) + compat check 允许 `blocked`/`BLOCKED` | `20260827_01` 扩宽 |
| C4 | task_logs from/to 双读 | 大写历史 + 小写新写 | 同 TypeDecorator |
| C5 | 邀请 token 索引 | `idx_users_invitation_token_hash` 存在且等值查询可用 | Phase A ORM 声明 |
| C6 | workflow nullable 不再新增 NULL | scope_mode / engine_version / executor_kind 新行非 NULL；nn check validated | Phase B 回填 + nn check |

## 并行门禁（阻塞关 fallback / I6，不阻塞 Phase D 代码设计）

| 工作线 | 状态 |
|---|---|
| 预发 `fallback=true` + rebuild/full shadow | 待目标环境 |
| `strict_projection_gap` 日志告警接入（KI-015） | 待目标环境 |
| RC3 / I4 / 设计器 Phase 2 / S-01 / KI-009 人工签字 | 待业务 |
| I3-F 7 天 / 31/31 | 待目标环境 |

## Phase D 进入条件

- C1–C6 在含真实数据的目标库复测通过
- 确认无未知 status 拼写
- 单独批准 contract 迁移窗口；当前 `main` 仅含 Phase B expand（`20260827_01`），尚未落地 Phase D contract
