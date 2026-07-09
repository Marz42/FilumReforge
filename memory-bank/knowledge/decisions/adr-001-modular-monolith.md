---
type: paradigma-decision
title: "ADR-001: 模块化单体架构"
description: "坚持模块化单体架构。"
tags: ["adr", "模块化单体", "架构决策"]
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.1
  temperature: cold
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["模块化单体", "架构决策"]
    en: ["modular monolith", "architecture"]
---
# ADR-001: 模块化单体架构

**日期**: 2025（Phase A 起）  
**状态**: 已采纳

**背景**  
50–100 人企业内部系统，HR、工作流、消息、AI 共享权限与组织模型。

**决策**  
坚持模块化单体；用 service 边界与 DB 约束管理复杂度，不拆微服务。

**后果**  
部署简单、事务一致性好；单仓体积与测试面随功能增长需持续治理。
