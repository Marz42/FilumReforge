# Active Task: Workflow Graph Engine — Iteration 4 Handler 化

**Status:** in-progress · I4-A complete · I4-B next · production cutover gated
**Plan:** memory-bank/knowledge/plans/workflow-graph-engine-iteration4-handler-plan.md

## Current gaps
- [ ] 模板解耦 Phase 2 设计器交互与文案待用户 UAT
- [ ] M-09 unarchive 待 sibling ACTIVE 冲突与审计策略决策
- [ ] 视频兼容依赖解除后再收窄 template `run_kind` dual-read
- [ ] Iteration 3-F 目标环境 Expand/Contract、Link 回填与恢复/回滚演练
- [ ] 连续 7 天 Link reconciliation 100%、runtime JSON fallback 0、open P0/P1 incident 0
- [ ] Iteration 3-F 最终 31/31 准入报告与用户批准

## Iteration 4
- [x] 用户授权启动开发；未将尚缺的生产准入证据记为通过
- [x] I4-A：Node Handler Registry + unified Capability Result
- [ ] I4-B：HumanTask Handler 接入既有 Coordinator / Work Item 边界
- [ ] I4-C：Approval Handler 适配现有轻量审批引擎
- [ ] I4-D：Deliverable / Notification Handler
- [ ] I4-E：视频能力从 Runtime / TaskService 分支迁入 handler / projection handler

## Release boundary
- Iteration 4 可进行向下兼容的代码开发和本地验证。
- Iteration 3-F 硬门禁未完成前，不做生产切流、不删除兼容路径、不宣称 runtime readiness 已通过。
