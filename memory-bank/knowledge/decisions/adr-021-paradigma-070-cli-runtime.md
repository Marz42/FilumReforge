---
type: paradigma-decision
title: "ADR-021: 采用 Paradigma 0.7 CLI 运行态并分离产品版本"
description: "采用 Paradigma 0.7 的 Task/Session/Checkpoint、Context Manifest、Memory catalog 与治理门禁，同时保留 Filum 产品 VERSION 的独立语义。"
tags: [adr, paradigma, runtime, context, governance, versioning]
timestamp: 2026-08-12T20:59:33+08:00
paradigma:
  schema_version: "0.1"
  temperature: cold
  lifecycle: stable
  update_policy: requires-human-confirmation
  epistemic_status: decision
  retrieval_hints:
    zh: [Paradigma 0.7, CLI 运行态, Context Manifest, 产品版本分离]
    en: [Paradigma 0.7, coding runtime, context manifest, product version separation]
  relations:
    supersedes:
      - ./adr-007-paradigma-alignment.md
    constrains:
      - ../contracts/repository-contract.md
    related_to:
      - ../known-issues/ki-013-paradigma-product-version-collision.md
---

# Context

Filum 在 Paradigma 0.5.0 时代把 `active-task.md` 和 session log 当作人工维护状态。Paradigma 0.7.0 已将 Task、Session、Checkpoint YAML 设为事实源，并把 active-task、handoff、Context Manifest、索引与 Memory catalog 设为确定性投影；M0–M4 修复又增加了累计迁移、用户拥有的 Agent 适配器、required Context 预算硬门限、计划机器状态与 append-only 日志治理。

Filum 根 `VERSION` 自 `0.87.0` 起表示产品发布版本。当前上游版本模型和固定升级 Profile 则假定根 `VERSION` 是 Paradigma 发行版本，两者不能共用。

# Decision

- 采用 Paradigma `0.7.0` 与上游提交 `3422ecf95109d48cfa89036ae96b4085201baef4` 的协议、Schema、兼容工具和 M0–M4 治理语义。
- Task、Session、Checkpoint YAML 成为 Coding runtime 事实；`active-task.md`、`handoff.md` 与 `context-manifest.yaml` 只由 `pd` 重建。
- Agent 规则继续由 Filum 用户拥有；`AGENT_RULES.md` 为源，Cursor/Copilot 为语义适配器，`managed_surfaces` 保持空。
- 根 `VERSION` 继续表示 Filum 产品版本；Paradigma 版本独立记录在 `.paradigma/VERSION` 和 config 的 `installed_distribution_version`，不得为通过升级器而改写产品版本。
- 开发工具通过 `requirements-paradigma.txt` 固定到可信 commit，不加入 Filum 后端生产依赖。
- 保留 Filum 的中文、既有文档结构；Schema 不强制上游英文标题模板，但强制 v0.7 frontmatter、枚举与 plan machine status tuple。

# Consequences

- 后续 Agent 通过 Context Builder 选择知识，不再固定扫描所有 HOT 和最近日志；progress log 只用于版本、Batch 或人工审计。
- 既有计划已按 `in-progress` / `completed` / `archived` 写入机器状态，并同步 temperature/epistemic tuple。
- append-only 旧日志被 exact-byte digest 冻结；新 authored log 必须引用 Checkpoint evidence。
- 在上游支持独立发行版本文件前，`pd version`、聚合 `pd check` 和固定 `version-upgrade` Profile 的版本步骤仍会报告根版本冲突；其他 runtime/context/index/catalog/adapter 门禁可独立执行。
- strict compliance 仍会把既有文档缺少 relations 的 warning 当成失败，关系补录应按知识语义逐步完成，不能用虚假统一关系消警。

# Alternatives Considered

- **把根 `VERSION` 改成 0.7.0**：会破坏 Filum 发布、Compose 与 RC 语义，拒绝。
- **复制或修改上游包源码到产品仓库**：会形成不可见 fork 并把文档工具混入业务运行时，拒绝。
- **继续停留在 0.5.0**：无法获得确定性 runtime、Context、迁移与治理修复，拒绝。
- **批量改写 113 份中文文档为上游英文模板**：会制造大规模无业务价值 diff，并可能改变文档语义，拒绝。

# Status

Accepted and implemented on 2026-08-12 with the upstream version-path limitation recorded as KI-013.

# Related Documents

- [Repository Contract](../contracts/repository-contract.md)
- [KI-013](../known-issues/ki-013-paradigma-product-version-collision.md)
- [Historical ADR-007](./adr-007-paradigma-alignment.md)
