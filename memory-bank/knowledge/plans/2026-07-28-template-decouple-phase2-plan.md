---
type: paradigma-plan
title: "Template Engine Decouple — Phase 2 Structured Authoring"
description: "M-06–M-08 structured authoring rollout and optional M-09 policy gate."
tags: ["plan", "workflow-graph", "template-engine", "phase-2", "structured-authoring"]
timestamp: 2026-07-28T10:47:27+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["模板引擎解耦 Phase 2", "结构化编辑", "ui_profile", "context_schema"]
    en: ["template decouple phase 2", "structured authoring", "context schema"]
---

# Template Engine Decouple — Phase 2

> **计划状态：COMPLETED（工程）** — M-06～M-08 已实现；人工界面验收由统一 UAT 清单跟踪，M-09 和 dual-read 收窄不属于本计划续做项。

## 目标

在不改变图运行时语义的前提下，把模板设计器中最常用的原始 JSON 编辑改为结构化表单，同时保留高级 JSON 作为完整表达能力的逃生口。

## 当前状态

**in-progress · first implementation complete · pending UAT**（2026-07-28）

| 项 | 状态 | 当前落地 |
|---|---|---|
| M-06 Node `ui_profile` | implemented | 常用 profile 下拉 + allow-create 自定义；仍定位为节点 Action Profile |
| M-07 `context_schema` | implemented | detail/draft save 向后兼容 API 增量；JSON Schema/flat 常用键编辑 + 高级 JSON |
| M-08 `launch_schema` | implemented | fields 结构化编辑；复杂结构自动保留在高级 JSON |
| M-08 `routing_rules` | implemented | 常用 IF/ELSE、操作符、目标节点表单；嵌套 `all/any` 保留高级 JSON |
| M-09 unarchive | deferred | 可选能力；尚未确认 sibling ACTIVE 冲突与审计策略，不在本批次擅自开启 |
| 2.5 收窄 dual-read | deferred | 视频 v1 仍依赖实例兼容标签；保留 template `run_kind` dual-read |

## 实施边界

- 不新增数据库迁移；`context_schema` 使用既有 JSONB 列。
- `WorkflowGraphTemplateDraftSaveRequest.context_schema` 为可选字段；旧客户端省略时不清空已有值。
- ACTIVE/ARCHIVED 定义仍不可原地修改；Phase 1 的 tags-only 例外不变。
- 结构化编辑器只接管可无损表达的常用形状；检测到复合/扩展字段时默认进入高级 JSON。
- tags、`ui_profile` 和表单文案不参与引擎行为门控。

## 验收清单

- [x] 节点可选择常用 `ui_profile` 或输入自定义值。
- [x] `context_schema` 可结构化编辑、保存、读取并随导出包保留。
- [x] `launch_schema.fields` 可结构化编辑并保留 JSON 模式。
- [x] 常用 routing IF/ELSE 可结构化编辑；复合条件不被降级重写。
- [x] Frontend unit/type-check/build 通过。
- [x] 视频工作流 mock E2E 2/2 通过。
- [x] Backend 全量与 DB-backed 专项通过。
- [ ] 用户界面验收。
- [ ] 决定是否实施 M-09 unarchive。
- [ ] 视频面板解除兼容依赖后再批准收窄 `run_kind` dual-read。

## 下一步

1. 用户验收设计器交互与字段文案。
2. 按真实模板样本补充更多结构化控件，不扩张引擎契约。
3. 单独决策 M-09；如批准，先定义 archived → active 的 sibling ACTIVE 处理与审计规则。
