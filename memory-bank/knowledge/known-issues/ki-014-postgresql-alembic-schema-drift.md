---
type: paradigma-known-issue
title: "KI-014: PostgreSQL Alembic autogenerate schema drift"
description: "目标 PostgreSQL 上 alembic check 报告的历史 ORM/DDL 类型、索引与 nullable 漂移。"
tags: [known-issue, postgresql, alembic, schema, migration]
timestamp: 2026-08-26T00:22:00+08:00
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
---

# KI-014: PostgreSQL Alembic autogenerate schema drift

## 状态

**开放 / 审计与迁移设计进行中 / 实时只读数据待补**。2026-08-23 的 PostgreSQL fresh upgrade、22 项方言测试、备份恢复和 `20260812_04 → 20260812_03 → head` 往返均通过；但 `alembic check` 在真实 PostgreSQL dialect 上仍返回非零，不能声明 schema drift clean。2026-08-26 已完成当前 ORM 与历史迁移链的根因分析，并形成独立的 expand/contract 设计；本机 PostgreSQL 不可连接，因此尚未刷新目标库 distinct/NULL/index 统计。

## 当前差异

1. `employment_events.trigger_status`：数据库为带小写值 check 的 `VARCHAR(32)`；ORM value Enum 推导长度为 10。数据库语义为权威，只需 metadata 对齐长度。
2. `tasks.status` 与 `task_logs.from_status/to_status`：历史数据库为小写值 `VARCHAR(6)`，当前 ORM 默认按大写 Enum 成员名持久化，且新增 `blocked` 需要至少 7 字符。必须先审计真实大小写和值集合，再经兼容期统一到小写 `VARCHAR(16)` 和独立命名 check。
3. `users.idx_users_invitation_token_hash`：数据库索引服务真实 token hash 等值查询，ORM metadata 漏声明；应补 ORM Index，不得采纳 autogenerate 的删除建议。
4. `workflow_graph_instances.engine_version`、`executor_kind` 与 `workflow_graph_templates.scope_mode`：历史 expand migration 保持 nullable，ORM 和运行时将其视为 non-null；应先统计/回填，再 validate check 和 `SET NOT NULL`。

## 风险与边界

- 当前运行时和既有迁移链可工作，且本批未修改上述列；因此不在 5-E P0 读取切换中顺带生成破坏性 migration。
- 未来新增迁移前必须先决定每项以 ORM 还是现有 DDL 为权威，补数据审计、离线 SQL 和 downgrade，再消除 autogenerate drift。
- 发布检查应分别记录“单 head/current/upgrade/downgrade 通过”和“alembic check 尚未 clean”，不得把前者写成后者。
- 2026-08-26 只能复用 2026-08-23 的真实 PostgreSQL drift 输出；默认 `localhost:5432` 拒绝连接且本机无可用 Docker/PostgreSQL runtime，不能把代码审计写成已刷新生产数据证据。

## 建议处理顺序

1. 按 [`KI-014 PostgreSQL Schema Drift 审计与迁移设计`](../plans/2026-08-26-ki014-schema-drift-remediation-plan.md) §3，以只读事务统计 nullable 列、状态 distinct 值、约束与索引。
2. 先完成 metadata/index 与 task status 双读兼容，再执行 expand migration；不得把 enum 大小写归一化和 nullable contract 混入首个部署。
3. 观察新应用只写小写状态且不再产生 NULL 后，独立执行 contract migration。
4. PostgreSQL base→head、head→previous→head、备份恢复和 `alembic check` 全部通过后关闭本项。
