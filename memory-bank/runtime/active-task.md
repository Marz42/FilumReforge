# Active Task: Iteration 4-C — Approval Handler 适配

**Status:** in-progress · I4-A/I4-B complete · I4-C next · production cutover gated
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
- [ ] 视频兼容依赖解除后再收窄 template `run_kind` dual-read
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
- [ ] I4-C：Approval Handler 适配现有轻量审批引擎并消费 ADR-019 决策策略
- [ ] I4-D：Deliverable / Notification Handler
- [ ] I4-E：领域中立化；把视频专用分支迁为通用能力与兼容适配层

## Release boundary
- Preflight P0/P1/P3 已通过，I4-B 已恢复；前端 P2 持续接收并独立分级。
- 管理员业务权限解耦延后；I4 不改变现有 Admin 兼容行为。
- Iteration 4 可进行向下兼容的代码开发和本地验证。
- Iteration 3-F 硬门禁未完成前，不做生产切流、不删除兼容路径、不宣称 runtime readiness 已通过。
