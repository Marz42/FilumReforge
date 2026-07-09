---
type: paradigma-decision
title: "ADR-004: 任务协同不建独立 IM"
description: "工作讨论与附件绑定 task_comments，消息中心只做通知/回执。"
tags: ["adr", "messaging", "task-comments"]
timestamp: "2026-07-08T17:34:00+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["任务协同", "IM", "task_comments", "消息中心"]
en: ["task collaboration", "messaging"]
---

# ADR-004: 任务协同不建独立 IM

**日期**: Phase 2  
**状态**: 已采纳

**背景**  
工作讨论需可追溯、绑定业务上下文。

**决策**  
讨论与附件进 `task_comments`；消息中心只做通知/回执。

**后果**  
无实时聊天体验；审计与权限模型清晰。