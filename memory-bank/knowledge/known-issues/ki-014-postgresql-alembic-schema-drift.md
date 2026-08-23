---
type: paradigma-known-issue
title: "KI-014: PostgreSQL Alembic autogenerate schema drift"
description: "目标 PostgreSQL 上 alembic check 报告的历史 ORM/DDL 类型、索引与 nullable 漂移。"
tags: [known-issue, postgresql, alembic, schema, migration]
timestamp: 2026-08-23T22:55:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Alembic check, schema drift, PostgreSQL 漂移]
    en: [alembic check, schema drift, PostgreSQL]
---

# KI-014: PostgreSQL Alembic autogenerate schema drift

## 状态

**开放 / 非本批 P0 回归阻断**。2026-08-23 的 PostgreSQL fresh upgrade、22 项方言测试、备份恢复和 `20260812_04 → 20260812_03 → head` 往返均通过；但 `alembic check` 在真实 PostgreSQL dialect 上仍返回非零，不能声明 schema drift clean。

## 当前差异

1. `employment_events.trigger_status` 与 `tasks/task_logs` 状态列：数据库为 `VARCHAR`，ORM 元数据声明 `native_enum=False` Enum/check 语义。
2. `users.idx_users_invitation_token_hash`：数据库存在索引，ORM metadata 未声明，autogenerate 建议删除。
3. `workflow_graph_instances.engine_version`、`executor_kind` 与 `workflow_graph_templates.scope_mode`：数据库 nullable，ORM 声明 non-null。

## 风险与边界

- 当前运行时和既有迁移链可工作，且本批未修改上述列；因此不在 5-E P0 读取切换中顺带生成破坏性 migration。
- 未来新增迁移前必须先决定每项以 ORM 还是现有 DDL 为权威，补数据审计、离线 SQL 和 downgrade，再消除 autogenerate drift。
- 发布检查应分别记录“单 head/current/upgrade/downgrade 通过”和“alembic check 尚未 clean”，不得把前者写成后者。

## 建议处理顺序

1. 只读统计 nullable 列的真实空值和状态列的 distinct 值。
2. 补齐或移除 ORM 索引声明，确认邀请 token 查询计划。
3. 用独立 expand/contract migration 对齐 nullable 与 enum/check，不与 Iteration 6 删除混批。
4. PostgreSQL base→head、head→base、备份恢复和 `alembic check` 全部通过后关闭本项。
