# Active Task: Iteration 4 完成 — 分批发布与 I3-F 生产门禁

**Status:** I4-A–I4-E complete · pre-I4E release candidate evaluated · production cutover gated
**Plan:** memory-bank/knowledge/plans/workflow-graph-engine-iteration4-handler-plan.md
**Preflight:** memory-bank/knowledge/plans/2026-07-29-iteration4-preflight-alignment-plan.md

## Current gaps
- [x] 视频模板领域中立依赖盘点与兼容退出清单
- [x] 前端反馈第一批 6 项已实现并经用户首轮验测修正（消息一键已读、隐藏 AI 入口、任务排序、详情拆分、跟踪/历史精简列表行）
- [x] 前端第一批真实登录态视觉 UAT 已用 `123@example.com` / `admin@example.com` 完成；类型检查、构建与 174 项单测通过
- [x] ADR-019 已确认；旧 completion policy / `self_review_fallback` / Deliverable contributor / 测试入口已盘点
- [ ] 系统管理员业务边界改造 deferred（KI-011），不属于 Iteration 4
- [ ] 模板解耦 Phase 2 设计器交互与文案待用户 UAT
- [ ] M-09 unarchive 待 sibling ACTIVE 冲突与审计策略决策
- [x] Runtime / TaskService / Task Center / 前端行为分支已迁为 capability snapshot / task capability；`run_kind` / `video_*` 只在兼容适配器双读
- [ ] 公共 API、历史 Run 与旧客户端对兼容字段的调用归零后，再删除 `run_kind` / `ui_profile` dual-read
- [ ] Iteration 3-F 目标环境 Expand/Contract、Link 回填与恢复/回滚演练
- [ ] 连续 7 天 Link reconciliation 100%、runtime JSON fallback 0、open P0/P1 incident 0
- [ ] Iteration 3-F 最终 31/31 准入报告与用户批准

## Iteration 4
- [x] 用户授权启动开发；未将尚缺的生产准入证据记为通过
- [x] I4-A：Node Handler Registry + unified Capability Result
- [x] Preflight P0：memory-bank 事实对齐与 ADR-018 入库
- [x] Preflight P3：ADR-019 决策对象与参与者重叠规则入库
- [x] Preflight P1：视频作为普通模板包；迁移清单已形成，不新增 `VideoHandler`
- [x] Preflight P2：第一批前端问题均属交互/视觉稳定化，无新增 P0 数据/权限或 P1 状态推进阻塞
- [x] I4-B：HumanTask 激活/完成/取消/重试已统一消费 Capability Result；Link/RunEvent/Outbox 同 UoW 回滚与参与者重叠合法场景已覆盖
- [x] I4-C：Approval 默认 Registry、旧审批实例幂等关联、动作前 overlap 校验、当前 Deliverable 版本事实、结果回传/重复回调、轮次/票数/代理审计与同 UoW 通知边界已完成
- [x] I4-D：Deliverable 多版本/accepted snapshot、Notification queued/sent/all-channels-success 策略，以及失败/重试/取消统一 Capability Result 已完成
- [x] I4-E：领域中立 capability snapshot、runtime policy、task capability、非视频对照与兼容适配层完成

## Release boundary
- Iteration 4 工程开发已完成；前端 P2 后续反馈继续独立分级。
- 前序能力建议以 `8244af0` 作为先行发布候选；尚未实际部署，需先核对服务器 commit 并完成预发 smoke。
- 管理员业务权限解耦延后；I4 不改变现有 Admin 兼容行为。
- Iteration 4 可进行向下兼容的代码开发和本地验证。
- Iteration 3-F 硬门禁未完成前，不做生产切流、不删除兼容路径、不宣称 runtime readiness 已通过。
