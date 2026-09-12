---
type: paradigma-known-issue
title: "KI-014: PostgreSQL Alembic autogenerate schema drift"
description: "目标 PostgreSQL 上 alembic check 报告的历史 ORM/DDL 类型、索引与 nullable 漂移。"
tags: [known-issue, postgresql, alembic, schema, migration]
timestamp: 2026-09-12T20:27:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Alembic check, schema drift, PostgreSQL 漂移]
    en: [alembic check, schema drift, PostgreSQL]
  relations:
    planned_by:
      - ../plans/2026-08-26-ki014-schema-drift-remediation-plan.md
    related_to:
      - ../manuals/2026-09-04-ki014-phase-c-observation-checklist.md
---

# KI-014: PostgreSQL Alembic autogenerate schema drift

## 状态

**开放 / Phase C 只读观测工具完成 / 真实数据兼容观察与 contract 待补**。Phase A/B 已由 `61ea3d3` 固定；2026-08-27 又新增强制只读、隐私安全的聚合审计入口，可验证 revision、状态值/大小写、workflow NULL、六个约束及邀请索引可规划性。空隔离库的自动数据库门禁通过但被明确标为 structure-only，不能替代真实目标库状态分布、应用 UAT 和一个完整业务周期，因此仍不能声明 schema drift clean。

## 当前差异

1. `employment_events.trigger_status`：Phase A 已把 ORM 长度和真实物理 check 名对齐；隔离 PostgreSQL `alembic check` 已不再报告该项。
2. `tasks.status` 与 `task_logs.from_status/to_status`：Phase B 已扩到 `VARCHAR(16)` 并添加 validated 兼容 check；应用可读历史大小写、只写小写。真实数据分布和兼容观察仍待目标预发。
3. `users.idx_users_invitation_token_hash`：Phase A 已补 ORM Index；隔离 PostgreSQL 确认索引存在，`alembic check` 不再建议删除。
4. `workflow_graph_instances.engine_version`、`executor_kind` 与 `workflow_graph_templates.scope_mode`：历史 expand migration 保持 nullable，ORM 和运行时将其视为 non-null；应先统计/回填，再 validate check 和 `SET NOT NULL`。

## 风险与边界

- 当前运行时和既有迁移链可工作，且本批未修改上述列；因此不在 5-E P0 读取切换中顺带生成破坏性 migration。
- 未来新增迁移前必须先决定每项以 ORM 还是现有 DDL 为权威，补数据审计、离线 SQL 和 downgrade，再消除 autogenerate drift。
- 发布检查应分别记录“单 head/current/upgrade/downgrade 通过”和“alembic check 尚未 clean”，不得把前者写成后者。
- 2026-08-26 只能复用 2026-08-23 的真实 PostgreSQL drift 输出；默认 `localhost:5432` 拒绝连接且本机无可用 Docker/PostgreSQL runtime，不能把代码审计写成已刷新生产数据证据。

## 建议处理顺序

1. 按 [`KI-014 PostgreSQL Schema Drift 审计与迁移设计`](../plans/2026-08-26-ki014-schema-drift-remediation-plan.md) §3，以只读事务统计 nullable 列、状态 distinct 值、约束与索引。
2. metadata/index、双读兼容和 expand migration 已完成；不得把 enum 大小写归一化和 nullable contract 混入当前批次。
3. 在含真实数据的目标预发按 [`Phase C 观察清单`](../manuals/2026-09-04-ki014-phase-c-observation-checklist.md) 观察新应用只写小写状态且不再产生 NULL 后，独立执行 contract migration。
4. PostgreSQL base→head、head→previous→head、备份恢复和 `alembic check` 全部通过后关闭本项。
