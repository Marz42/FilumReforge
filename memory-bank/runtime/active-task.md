---
type: paradigma-runtime-state
title: Active Task
description: 主开发线推进 Iteration 4、设计器 Phase 2 与 S-01 的人工验收闭环。
tags: [runtime, active-task, mainline, iteration-4, uat]
timestamp: 2026-08-10T16:30:00+08:00
paradigma:
  layer: runtime
  temperature: hot
  lifecycle: ephemeral
  okf_export: false
  update_policy: agent-editable
  archive_to: /memory-bank/logs/progress/
---

# Active Task

## Task ID

iteration4-uat-preflight-2026-08-10

## User Request

继续主开发线，在不改动 KI-011、I3-F 生产切流和 RC 标签的前提下，为 Iteration 4、设计器 Phase 2 与 S-01 增加可执行的验收准备检查，并更新人工验收文档。

## Current Status

engineering-complete / manual-uat-pending — “任务模板 → 验收准备”只读检查、候选账号/模板/统计样本提示、自动化测试与文档已完成。检查只判断环境是否可测，不代替员工实际操作和业务签字。

## Checklist

- [x] 延续既定边界：不动 KI-011、I3-F 切流、系统管理员业务边界和 RC 标签
- [x] 增加只读验收准备 API，检查模板治理、协同部门、通用/视频模板、设计器草稿与 S-01 样本
- [x] 识别视频参考模板时按稳定 `base_code` 匹配修订版本，不向 Runtime 增加视频特殊逻辑
- [x] 在任务模板页增加“验收准备”入口，展示阻断、建议、模板候选、部门候选和本月统计样本
- [x] 明确自动检查只代表“可测”，P-07 始终保留人工验收与签字要求
- [x] 补齐后端/前端单元与接口测试
- [x] 完成全量回归、类型检查、构建与 Paradigma 文档校验
- [x] 形成一个独立主线提交（提交完成后以 Git 记录为准）
- [ ] 在目标环境运行“数据检查”和“验收准备”，清零确定错误与 P-01～P-04 阻断
- [ ] 员工按清单完成 Iteration 4 / 设计器 Phase 2 / S-01 UAT，并记录账号、模板、Run ID 与结论

## Relevant Knowledge

- `memory-bank/knowledge/plans/2026-08-09-security-release-readiness-plan.md`
- `memory-bank/knowledge/plans/2026-08-09-rc-employee-trial-plan.md`
- `memory-bank/knowledge/plans/2026-08-10-template-governance-audit-plan.md`
- `memory-bank/knowledge/plans/2026-08-10-iteration4-uat-preflight-plan.md`
- `memory-bank/knowledge/manuals/2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md`
- `memory-bank/knowledge/manuals/deployment-runbook-ubuntu-2404.md`
- `memory-bank/knowledge/manuals/2026-08-09-production-release-checklist.md`
- `memory-bank/knowledge/plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md`
- `memory-bank/knowledge/decisions/adr-020-published-template-availability-scope.md`
- `memory-bank/knowledge/known-issues/ki-011-system-admin-business-boundary.md`

## Blockers

- 无继续开发的代码阻碍。
- 人工 UAT 需要目标环境真实账号、部门、模板和任务样本；系统现在会显式报告缺项，但不会自动造业务数据或代替业务签字。
- I3-F、真实 TLS/secret/backup/restore 与生产变更窗口继续作为外部门禁，不阻断主开发。

## Notes

- `v0.93.0-rc.1` 已固定在 `2260bd5`，主线提交不得移动该标签。
- RC 环境不得与继续开发环境共用数据库、Redis 或附件存储。
- KI-011 按用户决定暂不推进；本批次不扩大系统管理员业务权限，也不改变生产切流状态。
