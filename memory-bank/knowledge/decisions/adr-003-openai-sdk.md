---
type: paradigma-decision
title: "ADR-003: AI 集成官方 openai SDK"
description: "使用官方 openai Python SDK 进行 AI 集成；不引入 LangChain。"
tags: ["adr", "ai", "openai", "sdk"]
timestamp: "2026-07-08T17:34:00+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["openai SDK", "AI 集成", "LangChain"]
en: ["openai SDK", "AI integration"]
---

# ADR-003: AI 集成官方 openai SDK

**日期**: Phase 5  
**状态**: 已采纳

**背景**  
需要 Tool Calling 与 Pydantic schema 对接。

**决策**  
使用官方 `openai` Python SDK；不引入 LangChain。

**后果**  
行为可控、抽象层少；工具编排需自研 `LLMRouterService`。