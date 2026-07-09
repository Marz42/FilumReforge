---
type: paradigma-known-issue
title: "KI-005: 图引擎已知问题"
description: "ORM 懒加载导致 500、深度打回 max_iterations 等技术细节。"
tags: ["known-issue", "graph-engine", "ORM", "lazy-load"]
timestamp: "2026-07-08T17:34:00+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["图引擎", "ORM 懒加载", "max_iterations"]
en: ["graph engine", "ORM lazy load"]
---

# KI-005: 图引擎已知问题

## ORM 懒加载导致图实例详情 500

**原因**: `model_validate(ORM)` 触发 `node_instances` 异步懒加载。  
**修复方向**: 详情 API 用显式列 + 已查询集合组装 Pydantic（已实现，见 `workflow_graph_engine.py`）。

## 深度打回与 `max_iterations`

**说明**: 超出上限阻止；旧节点只读；前端展示 V{n} 角标。