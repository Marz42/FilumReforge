---
type: paradigma-progress-log
title: "KI-014 Schema Drift 并行轨记录（已与 origin Phase B 对齐）"
description: "记录 2026-09-04 本地并行 expand/contract 轨；2026-09-07 rebase 后以 origin `20260827_01` + CompatibleValueEnum 为权威。"
tags: [progress, ki-014, postgresql, alembic, schema-drift]
timestamp: 2026-09-07T10:20:00+08:00
paradigma:
  layer: log
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: append-only
  update_policy: append-only
  epistemic_status: verified
  relations:
    related_to:
      - ../../knowledge/known-issues/ki-014-postgresql-alembic-schema-drift.md
      - ../../knowledge/plans/2026-08-26-ki014-schema-drift-remediation-plan.md
      - ../../knowledge/manuals/2026-09-04-ki014-phase-c-observation-checklist.md
---

# KI-014 Schema Drift 并行轨记录（已与 origin Phase B 对齐）

## 背景

2026-09-04 本地曾并行实现 `20260904_01` expand / `20260904_02` contract 与 `CaseInsensitiveValueEnum`。
2026-09-07 与 `origin/main` rebase 时确认远端已落地权威 Phase B：`20260827_01` + `CompatibleValueEnum`。
并行迁移与重复类型实现已丢弃，避免双 head / 双契约。

## 当前权威状态

- Phase A：`CompatibleValueEnum`、`build_value_enum(length=...)`、邀请索引 ORM、employment trigger metadata 对齐
- Phase B：`20260827_01` — VARCHAR(16)、`lower(value)` compat check、nullable 回填 + nn check
- Phase C：观察清单已入库；目标预发真实数据观察待补
- Phase D：未合入；`alembic check` 在 Phase B 后仍可有预期三个 nullable diff

## 边界

- 未关 projection fallback；未开 Iteration 6。
- 不得把本机 Docker / 已废弃的 `20260904_*` 证据写成生产切流完成。
