---
type: paradigma-decision
title: "ADR-007: Memory-Bank Paradigma 对齐"
description: "采用 Paradigma 协议进行文档系统重构；Phase 0–4 已完成。"
tags: ["adr", "memory-bank", "paradigma", "documentation"]
timestamp: "2026-07-08T17:34:00+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["Paradigma 对齐", "Memory-Bank", "文档重构"]
en: ["paradigma alignment", "memory bank"]
---

# ADR-007: Memory-Bank Paradigma 对齐

**日期**: 2026-06-17  
**状态**: 已采纳（Phase 0–4 已完成；Phase 5–8 进行中）

**背景**  
Agent 协作需知识温度分层与统一 Update 工作流。

**决策**  
采用 Paradigma 协议；保留 `knowledge/manuals/` 路径（≈ `manuals/`，后续迁移）；`VERSION` 从 `0.87.0` 起 SemVer；不采用 `.template.md` 双文件机制。

**后果**  
文档迁移分 Phase 进行；`design-document`/`tech-stack` 保留只读完整版。