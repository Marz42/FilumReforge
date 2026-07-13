---
type: paradigma-decision
title: "ADR-012: 发布定义不可变与 Run 快照"
description: "提议冻结已发布图定义，并让 Run 持有可校验的执行快照与引擎版本。"
tags: ["adr", "workflow-graph", "snapshot", "proposal"]
timestamp: 2026-07-13T22:11:53+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["发布定义不可变", "Run 快照", "定义哈希"]
    en: ["immutable definition", "run snapshot", "definition hash"]
---
# ADR-012: 发布定义不可变与 Run 快照

**日期**：2026-07-13  
**状态**：已采纳（2026-07-13 用户统一批准 ADR-012–016）

## 背景

当前 `ACTIVE` 图模板仍可更新部分字段，运行时也会重新读取实时节点和边，并在需要时补建节点实例。因此模板修改可改变在途 Run；`WG-GAP-004` 已将该事实固化为严格 xfail。

## 提议决策

1. 已发布版本的执行定义不可原地修改；修改必须产生新版本。
2. Run 创建时保存完整执行快照，包括节点、边、条件、分配规则、必要的表单/Handler 配置和模板版本标识。
3. 快照使用明确的 canonical JSON 规则序列化，再计算 SHA-256；禁止直接对数据库 JSON 的非规范文本求哈希。
4. Run 保存 `definition_hash` 与 `engine_version`；恢复、重放和诊断均以 Run 自身快照为准。
5. 历史在途 Run 不臆造快照：按可验证程度分批回填，无法证明等价者使用 legacy executor。

## 备选方案

- 继续运行时读取实时模板：实现简单，但无法保证可重现性，否决。
- 只保存 `template_id/version`：仍允许关联内容被原地修改，不足以证明实际执行定义，否决。

## 后果

- Iteration 1 需要新增快照、哈希和引擎版本字段及发布校验；具体 schema/API 必须另行审批。
- 快照会增加存储，但换来在途稳定、审计可解释和确定性恢复。
- 本 ADR 已通过 Iteration 0 验收；具体生产 schema 仍按 Iteration 1 的迁移与回滚方案实施。
