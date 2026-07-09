---
type: paradigma-contract
title: "总览 Schema"
description: "看板卡片、看板归档、公告、公告归档。"
tags: ["contract", "database", "schema", "overview", "board"]
timestamp: 2026-07-09T09:30:00+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["总览Schema", "看板", "公告"]
    en: ["overview schema", "board", "announcement"]
  contract_kind: "database"
  relations:
    depends_on: ["../data-contracts.md"]
---
# 总览 Schema

> WARM — 看板卡片、看板归档、公告、公告归档。 完整 schema 见 [`data-contracts.md`](.../data-contracts.md)。

### 10.34 `board_cards`

**实现状态**: 重构 Step 2 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 看板卡片主键 |
| `scope_department_id` | `uuid` | FK -> `departments.id`, NULL | 可见范围部门，NULL 表示公司级 |
| `author_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 发布人 |
| `title` | `varchar(120)` | NOT NULL | 主题 |
| `content_md` | `text` | NOT NULL | 内容 |
| `expires_at` | `timestamptz` | NOT NULL | 到期时间 |
| `created_at` | `timestamptz` | NOT NULL | 发布时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `idx_board_cards_scope_department_id (scope_department_id)`
- `idx_board_cards_author_user_id (author_user_id)`
- `idx_board_cards_expires_at (expires_at)`


### 10.35 `board_card_archives`

**实现状态**: 重构 Step 2 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 归档主键 |
| `original_card_id` | `uuid` | UNIQUE, NOT NULL | 原活跃卡片 ID |
| `scope_department_id` | `uuid` | FK -> `departments.id`, NULL | 原范围部门 |
| `author_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 原发布人 |
| `title` | `varchar(120)` | NOT NULL | 主题快照 |
| `content_md` | `text` | NOT NULL | 内容快照 |
| `published_at` | `timestamptz` | NOT NULL | 原发布时间 |
| `expires_at` | `timestamptz` | NOT NULL | 原到期时间 |
| `archived_at` | `timestamptz` | NOT NULL | 归档时间 |

**约束与索引**

- `uq_board_card_archives_original_card_id`
- `idx_board_card_archives_scope_department_id (scope_department_id)`
- `idx_board_card_archives_archived_at (archived_at DESC)`


### 10.36 `announcements`

**实现状态**: 重构 Step 2 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 公告主键 |
| `publisher_department_id` | `uuid` | FK -> `departments.id`, NOT NULL | 发布部门 |
| `author_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 发布人 |
| `title` | `varchar(160)` | NOT NULL | 公告标题 |
| `content_md` | `text` | NOT NULL | 公告内容 |
| `published_at` | `timestamptz` | NOT NULL | 发布时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**约束与索引**

- `idx_announcements_publisher_department_id (publisher_department_id)`
- `idx_announcements_published_at (published_at DESC)`


### 10.37 `announcement_archives`

**实现状态**: 重构 Step 2 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 归档主键 |
| `original_announcement_id` | `uuid` | UNIQUE, NOT NULL | 原活跃公告 ID |
| `publisher_department_id` | `uuid` | FK -> `departments.id`, NOT NULL | 原发布部门 |
| `author_user_id` | `uuid` | FK -> `users.id`, NOT NULL | 原发布人 |
| `title` | `varchar(160)` | NOT NULL | 标题快照 |
| `content_md` | `text` | NOT NULL | 内容快照 |
| `published_at` | `timestamptz` | NOT NULL | 原发布时间 |
| `archived_at` | `timestamptz` | NOT NULL | 撤下归档时间 |

**约束与索引**

- `uq_announcement_archives_original_announcement_id`
- `idx_announcement_archives_publisher_department_id (publisher_department_id)`
- `idx_announcement_archives_archived_at (archived_at DESC)`


