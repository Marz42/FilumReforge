---
type: paradigma-contract
title: "知识库与附件 Schema"
description: "文档、向量嵌入、附件存储、附件绑定。"
tags: ["contract", "database", "schema", "knowledge", "attachment"]
timestamp: 2026-07-09T09:30:00+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["知识库Schema", "附件", "文档"]
    en: ["knowledge schema", "attachment", "document"]
  contract_kind: "database"
  relations:
    depends_on: ["../data-contracts.md"]
---
# 知识库与附件 Schema

> WARM — 文档、向量嵌入、附件存储、附件绑定。 完整 schema 见 [`data-contracts.md`](.../data-contracts.md)。

### 10.12 `attachments`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 附件主键 |
| `storage_provider` | `varchar(32)` | NOT NULL | 存储提供者 |
| `bucket` | `varchar(128)` | NOT NULL | 逻辑 bucket |
| `object_key` | `varchar(512)` | NOT NULL | 对象存储 key |
| `original_filename` | `varchar(255)` | NOT NULL | 原始文件名 |
| `mime_type` | `varchar(127)` | NOT NULL | MIME 类型 |
| `size_bytes` | `bigint` | NOT NULL | 文件大小 |
| `checksum_sha256` | `char(64)` | NOT NULL | 完整性校验 |
| `uploader_id` | `uuid` | FK -> `users.id`, NOT NULL | 上传者 |
| `visibility` | `attachment_visibility` | NOT NULL, DEFAULT `private` | 可见性 |
| `status` | `attachment_status` | NOT NULL, DEFAULT `uploaded` | 状态 |
| `metadata` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 扩展元数据 |
| `created_at` | `timestamptz` | NOT NULL | 上传时间 |
| `deleted_at` | `timestamptz` | NULL | 软删除时间 |

**约束与索引**

- `uq_attachments_storage_object (storage_provider, bucket, object_key)`
- `idx_attachments_uploader_id (uploader_id)`
- `idx_attachments_status_visibility (status, visibility)`


### 10.13 `attachment_links`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 绑定记录主键 |
| `attachment_id` | `uuid` | FK -> `attachments.id`, NOT NULL | 附件 |
| `target_type` | `attachment_target_type` | NOT NULL | 目标对象类型 |
| `target_id` | `uuid` | NOT NULL | 目标对象主键 |
| `relation` | `varchar(64)` | NOT NULL, DEFAULT `primary` | 绑定关系 |
| `created_by` | `uuid` | FK -> `users.id`, NOT NULL | 创建人 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- `uq_attachment_links_binding (attachment_id, target_type, target_id, relation)`
- `idx_attachment_links_target (target_type, target_id)`

**设计说明**

- 当前主要绑定 `task`、`task_comment`、`profile`、`document`、`notification_message`、**`report`**。
- 生命周期事件等对象仍属于后续扩展方向。


### 10.32 `documents`

**实现状态**: 已实现（Phase 5）

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 文档主键 |
| `title` | `varchar(255)` | NOT NULL | 标题 |
| `slug` | `varchar(255)` | UNIQUE, NOT NULL | 稳定 URL 标识 |
| `category` | `document_category` | NOT NULL | 分类 |
| `status` | `document_status` | NOT NULL, DEFAULT `draft` | 状态 |
| `content_md` | `text` | NOT NULL | Markdown 内容 |
| `author_id` | `uuid` | FK -> `users.id`, NOT NULL | 作者 |
| `version` | `int4` | NOT NULL, DEFAULT `1` | 版本号 |
| `published_at` | `timestamptz` | NULL | 发布时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_documents_slug`
- `idx_documents_category_status (category, status)`


### 10.33 `document_embeddings`

**实现状态**: 已实现（Phase 5）

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 向量主键 |
| `document_id` | `uuid` | FK -> `documents.id`, NOT NULL | 所属文档 |
| `chunk_index` | `int4` | NOT NULL | 分块序号 |
| `chunk_text` | `text` | NOT NULL | 切块内容 |
| `token_count` | `int4` | NULL | token 数 |
| `embedding_model` | `varchar(128)` | NOT NULL | 嵌入模型 |
| `embedding` | `vector(1536)` | NOT NULL | 向量数据 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- `uq_document_embeddings_chunk (document_id, chunk_index)`
- 向量索引：`ivfflat` 或 `hnsw`


