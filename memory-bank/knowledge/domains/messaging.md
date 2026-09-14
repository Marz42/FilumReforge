---
type: paradigma-domain
title: "领域：消息与通知 (Messaging)"
description: 消息中心、通知推送、回执确认。
tags:
  - domain
  - 消息
  - 通知
  - 回执
timestamp: 2026-09-13T22:13:51+08:00
paradigma:
  relations:
    related_to:
      - ../architecture.md
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh:
      - 消息
      - 通知
      - 回执
    en:
      - messaging
      - notification
---
# 领域：消息与通知 (Messaging)

> 🌡️ WARM — 涉及消息中心、通知总线、回执、Push 时读取。

**关联 schema**: [消息数据契约](../contracts/database/messaging-schema.md) §10.26–10.29

---

## 职责分离

| 系统 | 用途 |
|------|------|
| `task_comments` | 任务协同留痕（**不是**消息中心） |
| `notification_messages` | 通知、审批提醒、系统消息 |
| `notification_deliveries` | 渠道投递状态 |
| `notification_receipts` | 已读/已确认回执 |
| `push_subscriptions` | 浏览器 Push 订阅 |

---

## 通知总线流程

1. 业务构造 `NotificationMessage`
2. `NotificationService.send()` 落库 + delivery
3. ARQ 入队 → worker → adapter（email / websocket / web_push）
4. 逾期扫描 cron

**硬约束**: 业务层禁止直连 adapter。

详见 `architecture.md` §6.3、§6.8、§6.10。

---

## 消息中心（Stage 2 Phase 4）

- 附件：`attachment_links(target_type=notification_message)`
- 筛选：来源模块、回执状态、渠道、投递状态、时间范围
- 详情：投递尝试、失败原因、附件列表

---

## 关键代码

| 路径 | 作用 |
|------|------|
| `backend/app/services/notification_service.py` | 发送总线 |
| `backend/app/services/message_center_service.py` | 收件箱聚合 |
| `backend/app/workers/arq_worker.py` | 消费与 cron |
| `frontend/src/views/MessagesView.vue` | 消息中心 UI |

---

## 缺口

- Email / WebSocket **真实**外部接入仍为最小实现
- delivery 观测与告警待深化

---

## 调试

- Push 公钥：`GET /api/v1/push-subscriptions/config`
- `WEB_PUSH_*` 须在 backend **与** worker 同时配置

## W08 当前实现与范围（2026-09-13）

站内消息以 notification_messages 为事实源，回执不依赖推送成功。WebPush 支持当前浏览器独立关闭、404/410 失效清理、部分受理警告及本人全失败重试（最多累计 5 次尝试）；SENT 只表示至少一个 provider 端点受理，不代表全部设备收到或已读。渠道+状态筛选匹配同一 delivery，回执后更新挂载收件箱的未读数。正常并发消费/回执/重试使用消息行锁串行化。

Email/邀请邮件/WebSocket 真实接入与占位状态改造延期。真实浏览器送达、崩溃窗口补偿和设备级精确补发仍须独立验证/设计。详见 [W08 实施与验收](../manuals/2026-09-13-w08-inapp-webpush.md)。
