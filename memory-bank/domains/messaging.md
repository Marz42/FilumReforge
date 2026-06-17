# 领域：消息与通知 (Messaging)

> 🌡️ WARM — 涉及消息中心、通知总线、回执、Push 时读取。

**关联 schema**: `data-contracts.md` §10.26–10.29

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
