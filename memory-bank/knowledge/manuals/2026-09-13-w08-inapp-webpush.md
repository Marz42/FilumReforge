---
type: paradigma-manual
title: "W08 站内消息中心与 Web Push"
description: "记录用户收敛后的 W08 范围、实施步骤、消息状态语义与本地和真实渠道验收边界。"
tags: [w08, messaging, web-push, in-app, delivery]
timestamp: 2026-09-13T22:13:51+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: decision
  retrieval_hints:
    zh: [站内消息中心, Web Push, W08范围, Email延期]
    en: [in-app notifications, web push, delivery status]
  relations:
    related_to:
      - ../plans/2026-09-10-integrated-development-and-human-gates-plan.md
      - ../domains/messaging.md
      - ../contracts/database/messaging-schema.md
---

# W08 范围与执行

2026-09-13 用户明确要求：先优化 Memory-Bank 状态，调整 W08，Email 暂不做，仅优化站内消息中心/Web Push；完成后直接提交。当前状态为范围内实现完成，正在完成最终回归与提交收口；真实渠道验收独立待办。

## 范围

- 站内：本人消息可见性、回执/筛选/计数、头部通知与消息详情状态一致性。
- Web Push：配置、浏览器订阅生命周期、取消/失效订阅、投递结果、失败与重试展示。
- 验证：后端权限与失败路径、前端状态和受控浏览器流程；完成后本地 Git 提交。
- 延期：Email 发送、邀请邮件、邮件供应商回执和 WebSocket 接入/占位适配器专项改造。既有延期风险仍保留，不借本批标记完成。

## 实施与验收顺序

1. 检查现有站内和 Web Push 实现及契约，锁定有证据的问题。
2. 保持 NotificationService 为唯一业务发送入口；在现有结构内修复状态、权限和失败处理。
3. 推送服务受理与用户看见/已读分开，站内消息与回执不依赖推送成功；界面解释与底层证据一致。
4. 覆盖无配置、无订阅、重复操作、失效端点、部分失败、暂时失败和越权路径。
5. 完成回归与 Memory-Bank 一致性检查，再提交这一批。

HG-00 已有本任务明确授权，范围限上述实现、隔离验证与提交。真实 Web Push 外发仍需用户主动订阅，并以明确测试浏览器/收件人为范围；本轮自动验证使用受控端点和 mock，不向已有真实订阅批量推送。目标库迁移、生产部署及业务签字仍遵守原 Gate。

## 证据与剩余项

### 已实现

- 当前浏览器通过 PushManager endpoint 与本人服务端订阅匹配；关闭只撤销这一条。其他设备单独计数。浏览器订阅创建后若服务端保存失败则清理；关闭失败不显示成功；跨账号旧 endpoint 先在浏览器注销，不转移服务端所有权。
- 配置获取失败默认禁用启用/测试按钮；首次安装 Service Worker 等待激活，10 秒超时可重试；权限请求仅由用户主动点击触发。缺失配置/无活跃订阅拒绝测试，队列失败按实际状态提示，站内消息仍可读取。
- Worker 以消息行锁串行化重复消费；重复已受理 delivery 不再发送。每个真实 provider 请求设置 10 秒超时，单设备异常不阻止其他设备尝试；404/410 订阅置 expired；错误仅保留受理/失败/失效设备数，不保存端点或原始 provider 异常。
- Web Push 的 SENT 表示至少一个端点被推送服务受理；全部失败为 FAILED。部分失败仍是 SENT，但 error_message 保存数量警告，界面显示警告。delivered_at 是此次受理处理时间，external_message_id 是本地关联标识，并非 provider 送达凭证。用户已读/确认只来自独立 receipt。
- 新增 POST `/api/v1/messages/{id}/web-push/retry`：仅活跃收件人可调用，越权 404；仅 FAILED Web Push、attempt_count < 5、配置了队列且有活跃订阅可重试。已受理/RETRYING 重复请求不重复入队；不会重发 Email/WebSocket。入队故障计入尝试次数，保留其他渠道已受理状态。
- 站内消息不等同 WebSocket：默认显示全部站内消息，当前渠道筛选仅提供 WebPush；历史 Email/WebSocket 投递记录仍保留。渠道和投递状态同时筛选时必须匹配同一条 delivery；日期统一为 UTC 比较；全局未读/未确认计数不随列表筛选缩减。
- Receipt 使用收件人权限及消息行锁保证重复提交幂等；成功回执通知当前页面内已挂载收件箱刷新，头部未读数随之更新。消息页读取采用会话/最新请求归属，旧筛选结果不会覆盖新结果。
- SW 容错解析载荷，以 message_id 为通知 tag，点击打开同源消息详情并选择对应消息。深链本身不生成已读回执。

### 验证记录

最终测试与治理结果在本节收口后记录。受控端点均为测试域名，测试 sender/mock 不联网发送；Playwright 验证消息深链、失败重试、设置与会话，不能替代真实渠道收取。

### 保留的边界与后续

1. 没有新建按设备投递账本，因此部分失败不开放整条重试，避免成功设备再次收到。若需要对失败设备精确补发，后续先设计持久设备级 attempt/outbox，再单独评审 schema。
2. 行锁保证正常并发只消费一次，但 provider 受理后进程崩溃、数据库未提交仍可能重复；通知 tag 只提供浏览器合并提示，不宣称 exactly-once。数据库提交与队列发布之间的崩溃窗口仍需后续持久 outbox/补偿任务治理。
3. 单次端点请求有超时，串行设备数较多时消息锁持有时间仍会增长；大规模订阅/消息分页性能与跨标签页实时同步不在本批完成声明内。头部轮询仍保留。
4. 无 schema 变更，migration head 保持 `20260827_01`；KI-014 Phase C 目标样本/业务周期和 Phase D 批准仍 pending，不能由本批测试关闭。
5. Email/邀请邮件/WebSocket 真实接入及占位 SENT 问题明确延期；本批不改这些 adapter，不将其历史状态用作真实发送证据。

### Human Gate：真实 WebPush 验收

用户指定测试账号、浏览器和环境并主动启用订阅后再执行；不要自动向生产已有订阅批量推送。操作步骤：

1. 在 API 与 worker 配置同一组 VAPID 参数，确认 HTTPS/浏览器权限、worker 与队列就绪。
2. 用同一测试账号在两台浏览器启用，逐一核对本机状态；关闭 A，确认 B 仍启用、A 服务端订阅 revoked。
3. 由测试账号主动点击测试按钮；该按钮当前按账号向所有活跃订阅发送。分别记录消息 ID、入队结果、受理数量以及每台浏览器实际通知出现的时间。
4. 点击系统通知确认打开对应消息；回执前仍未读，手动已读/确认后核对头部与详情。
5. 仅在受控测试设备演练失效/拒绝/暂时不可用，核对失败说明与整条失败重试；真实收到与 provider 受理分别填写 PASS/FAIL。
6. 保存候选 SHA、浏览器版本、测试账号和结果，由用户/测试负责人确认渠道验收。生产部署、目标库写入与业务 UAT 仍按原 HG-01～HG-07 独立授权。
