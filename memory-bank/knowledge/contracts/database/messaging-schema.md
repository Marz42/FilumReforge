---
type: paradigma-contract
title: "消息与推送 Schema"
description: "通知消息、投递记录、回执、浏览器 Push 订阅。"
tags: ["contract", "database", "schema", "messaging", "push"]
timestamp: 2026-09-13T22:13:51+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["消息Schema", "通知", "Push"]
    en: ["messaging schema", "notification", "push"]
  contract_kind: "database"
  relations:
    depends_on: ["../data-contracts.md"]
---
# 消息与推送 Schema

> WARM — 通知消息、投递记录、回执、浏览器 Push 订阅。 完整 schema 见 [`data-contracts.md`](.../data-contracts.md)。

### 10.26 `notification_messages`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 消息主键 |
| `source_type` | `varchar(64)` | NOT NULL | 业务来源 |
| `source_id` | `uuid` | NULL | 来源对象 ID |
| `recipient_user_id` | `uuid` | FK -> `users.id`, NULL | 收件用户 |
| `recipient_email` | `varchar(255)` | NULL | 直接收件地址 |
| `message_type` | `varchar(64)` | NOT NULL | 消息类型 |
| `title` | `varchar(255)` | NOT NULL | 标题 |
| `body_text` | `text` | NOT NULL | 文本体 |
| `body_html` | `text` | NULL | HTML 体 |
| `payload` | `jsonb` | NOT NULL, DEFAULT `'{}'::jsonb` | 附加上下文 |
| `status` | `notification_message_status` | NOT NULL, DEFAULT `queued` | 消息状态 |
| `scheduled_at` | `timestamptz` | NULL | 计划发送时间 |
| `enqueued_at` | `timestamptz` | NULL | 入队时间 |
| `completed_at` | `timestamptz` | NULL | 完成时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_notification_messages_status_scheduled_at (status, scheduled_at)`
- `idx_notification_messages_recipient_user_id (recipient_user_id)`

**设计说明**

- 当前用于异步通知总线。
- Phase 4 已在此基础上扩展“消息中心 / 回执”能力，而不是再造一套平行消息表。
- Stage 2 Phase 4 继续沿用该表作为消息中心主存储，并通过 `attachment_links` 绑定消息附件；筛选维度覆盖来源模块、回执状态、渠道、投递状态与创建时间。


### 10.27 `notification_deliveries`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 投递主键 |
| `message_id` | `uuid` | FK -> `notification_messages.id`, NOT NULL | 所属消息 |
| `channel` | `notification_channel` | NOT NULL | 投递渠道 |
| `adapter_name` | `varchar(64)` | NOT NULL | 适配器标识 |
| `status` | `notification_delivery_status` | NOT NULL, DEFAULT `pending` | 投递状态 |
| `attempt_count` | `int4` | NOT NULL, DEFAULT `0` | 尝试次数 |
| `external_message_id` | `varchar(255)` | NULL | 外部平台 ID |
| `error_message` | `text` | NULL | 失败信息 |
| `attempted_at` | `timestamptz` | NULL | 最近尝试时间 |
| `delivered_at` | `timestamptz` | NULL | 成功时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**索引**

- `idx_notification_deliveries_message_id (message_id)`
- `idx_notification_deliveries_status_channel (status, channel)`


### 10.28 `notification_receipts`

**实现状态**: 已实现

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 回执主键 |
| `message_id` | `uuid` | FK -> `notification_messages.id`, NOT NULL | 消息 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 用户 |
| `receipt_type` | `notification_receipt_type` | NOT NULL | 回执类型 |
| `note` | `text` | NULL | 回执说明 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |

**约束与索引**

- `uq_notification_receipts_binding (message_id, user_id, receipt_type)`
- `idx_notification_receipts_user_id_created_at (user_id, created_at)`


### 10.29 `push_subscriptions`

**实现状态**: 已实现（Phase 5）

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | `uuid` | PK | 订阅主键 |
| `user_id` | `uuid` | FK -> `users.id`, NOT NULL | 用户 |
| `endpoint` | `text` | UNIQUE, NOT NULL | 浏览器推送端点 |
| `p256dh_key` | `text` | NOT NULL | 公钥 |
| `auth_key` | `text` | NOT NULL | 鉴权密钥 |
| `status` | `push_subscription_status` | NOT NULL, DEFAULT `active` | 订阅状态 |
| `user_agent` | `text` | NULL | 浏览器信息 |
| `last_seen_at` | `timestamptz` | NULL | 最近活跃时间 |
| `created_at` | `timestamptz` | NOT NULL | 创建时间 |
| `updated_at` | `timestamptz` | NOT NULL | 更新时间 |

**索引**

- `uq_push_subscriptions_endpoint`
- `idx_push_subscriptions_user_status (user_id, status)`



## W08 增量语义（2026-09-13，无 DDL 变更）

- WebPush delivery 的 sent 表示至少一个端点被推送服务受理；error_message 在部分失败时保存脱敏数量警告。external_message_id 为本地关联 ID，delivered_at 为处理受理时间，均非终端送达回执。全失败为 failed；404/410 订阅置 expired。
- POST `/api/v1/messages/{id}/web-push/retry` 返回 202 + MessageRead，仅本人可调用；仅重试 WebPush failed 且 attempt_count < 5，需可用队列发布器及活跃订阅。其他渠道及已受理记录不重发；重复 retrying 请求不重新入队；缺前置条件返回业务错误，入队失败仍通过返回消息状态表达。
- NotificationReceipt 的唯一键保持不变；创建前锁定消息行并校验收件人。回执与渠道状态独立，推送受理或通知点击不自动产生 read。
- GET `/api/v1/messages` 的 channel + delivery_status 匹配同一 delivery；不指定 channel 时沿用全渠道聚合状态，统计未读数以本人全部站内消息为口径。
- 订阅 endpoint 所有权不跨账号转移；关闭当前浏览器仅 revoke 对应订阅，其他设备不受影响。
- 保持 migration head `20260827_01`。Email/WebSocket 适配器延期，以上受理证据语义不能反推其外发已实现。详见 [W08 手册](../../manuals/2026-09-13-w08-inapp-webpush.md)。
