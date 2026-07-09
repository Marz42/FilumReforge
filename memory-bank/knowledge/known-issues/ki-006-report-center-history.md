---
type: paradigma-known-issue
title: "KI-006: 汇报中心历史问题"
description: "PostgreSQL enum 持久化与 ORM 不一致（已修复）。"
tags: ["known-issue", "report-center", "postgresql", "enum"]
timestamp: "2026-07-08T17:34:00+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["汇报中心", "PostgreSQL enum", "ORM"]
en: ["report center", "enum persistence"]
---

# KI-006: 汇报中心历史问题

**现象**: PostgreSQL enum 持久化与 ORM 不一致（2026-04 已修复）。  
**处理**: `build_value_enum()` 按枚举值持久化；见 `backend/app/core/db_types.py`。