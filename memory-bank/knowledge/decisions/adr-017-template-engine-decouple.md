---
type: paradigma-decision
title: "ADR-017: 模板引擎业务语义解耦 — Tags 替代 run_kind"
description: "以用户 tags 作分类、以图结构派生 capabilities 作门控，废弃模板级 run_kind 产品类型。"
tags: ["adr", "workflow-graph", "template-engine", "tags", "run_kind"]
timestamp: 2026-07-22T14:45:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["模板引擎解耦", "tags", "run_kind", "TemplateCapabilities", "归档"]
    en: ["template engine decouple", "tags", "run_kind", "capabilities"]
---
# ADR-017: 模板引擎业务语义解耦 — Tags 替代 run_kind

**日期**：2026-07-22  
**状态**：已采纳（Phase 0 设计；实现见 Phase 1+）  
**Spec**：[`docs/superpowers/specs/2026-07-22-template-engine-decouple-design.md`](../../../docs/superpowers/specs/2026-07-22-template-engine-decouple-design.md)  
**领域**：[`domains/task-center.md`](../domains/task-center.md) §7.7 · 契约：[`contracts/database/graph-engine-schema.md`](../contracts/database/graph-engine-schema.md)

## 背景

图模板引擎本质是通用 DAG 运行时（`templates → nodes → edges → instances`）。视频选题会的 batch / production 是其上的一个产品 profile，却被写成模板级 `config.run_kind`，并门控：

- 直接实例化（`production` 禁用）
- 周期调度资格（要求 `batch`）
- 列表/设计器「类型」标签

这把空白画布绑死在单一垂直业务上，与节点真相（`config.kind`、`ui_profile`、fork/`child_template_code`）冲突，并阻碍「同一模板多种图形状」。设计器审计还暴露归档 API 已有、UI 缺失等问题。

## 决策

1. **分类用 tags**：`workflow_graph_templates.tags JSONB`（默认 `[]`）。纯用户词汇；引擎 **永不** 按 tag 值分支。ACTIVE 允许仅改 tags（定义仍不可变）。
2. **门控用 TemplateCapabilities**：服务端从图谱结构 + 显式 opt-in（`schedulable`、`launch_schema`、multi_instance、fork 引用）计算 `can_instantiate_directly` / `can_schedule` / `is_fork_target` 等；API 返回给 UI 与调度共用。
3. **`ui_profile` 保持节点内部机制**：不升格为模板级「类型」；Phase 2 仅做节点 inspector 结构化编辑。
4. **`config.run_kind` deprecated**：旧视频 seed 只读保留；新模板不写。过渡期 dual-read（capabilities 优先，回退 legacy `run_kind`）。实例 `context.run_kind` 可为视频 v1 面板兼容标签。
5. **归档经 UI 可达**：复用已有 `PATCH .../status` → `archived`；列表筛选含已归档；无 unarchive（可选后期）。

## 备选方案

- 继续用 `run_kind` 作系统类型：否决 — 耦合垂直业务，空白模板误标「批次/制作」。
- Tags 放进 `config.tags`：否决 — ACTIVE `config` 不可变，无法做元数据编辑。
- Tag 目录 / 权限路由：否决 — 超出自由标签范围；延后。
- 立即删除 seed `run_kind`：否决 — Phase 1 需 dual-read 保视频 v1 E2E。

## 后果

- **正面**：引擎垂直无关；空白模板不再被产品类型污染；ACTIVE 可改分类；归档可操作；发起/调度门控与图真相对齐。
- **负面/成本**：需 Alembic `tags` 列、capabilities 纯函数、前端去掉类型 radio、过渡 dual-read 与 OpenAPI deprecated 标注。
- **非目标（本 ADR）**：一刀切替换视频 v1 面板；删除 `ui_profile`；unarchive；把 tags 做成权限系统。
- **实现分期**：Phase 1 = 归档 UI + tags + capabilities 门控 + ACTIVE 不可原地改定义；Phase 2 = `ui_profile`/`context_schema`/launch 表单化与收窄 dual-read。
