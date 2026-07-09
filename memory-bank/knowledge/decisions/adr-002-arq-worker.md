---
type: paradigma-decision
title: "ADR-002: 异步 Worker 选型 ARQ"
description: "使用 ARQ 替代 Celery 作为异步 worker 实现。"
tags: ["adr", "worker", "arq", "async"]
timestamp: "2026-07-08T17:34:00+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["ARQ", "异步 worker", "Celery"]
en: ["ARQ", "async worker", "Celery"]
---

# ADR-002: 异步 Worker 选型 ARQ

**日期**: Phase 2  
**状态**: 已采纳

**背景**  
后端已是 async 栈，已有 Redis。

**决策**  
使用 ARQ 替代 Celery 作为 worker 实现。

**后果**  
轻量、与 FastAPI async 契合；生态小于 Celery，当前体量足够。