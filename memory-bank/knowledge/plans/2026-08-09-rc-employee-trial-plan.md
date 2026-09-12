---
type: paradigma-plan
title: "v0.93.0-rc.x 员工试用与持续开发分流方案"
description: "固定不可变 RC、隔离员工试用环境，并让后续开发与 RC 热修互不污染。"
tags: [plan, release-candidate, employee-trial, branching, hotfix]
timestamp: 2026-09-10T23:49:41+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: decision
  plan_status: in-progress
  retrieval_hints:
    zh: [RC 试用, 员工内测, 发布标签, 持续开发, 热修]
    en: [release candidate, employee trial, immutable tag, hotfix, continued development]
  relations:
    depends_on:
      - ../manuals/2026-08-09-production-release-checklist.md
      - ../known-issues/ki-012-security-scan-release-blockers.md
    related_to:
      - ../roadmap.md
      - ./2026-09-10-integrated-development-and-human-gates-plan.md
---

# v0.93.0-rc.x 员工试用与持续开发分流方案

> **2026-09-10 当前执行口径**：最新已记录候选为 `v0.93.0-rc.3`（`21975a6`）；KI-014 A/B 提交 `61ea3d3` 及 Phase C 工作区不包含在该旧标签内。后续候选按 [整合方案 W00/W05 与 HG-04/05](./2026-09-10-integrated-development-and-human-gates-plan.md) 重新固定和验收。下文 RC1/RC2 的准入范围保留为历史记录，不能套用到新 SHA。

## 1. 决策与目标

以单一 release commit 创建不可变注释标签 `v0.93.0-rc.1`，将它部署到员工试用环境；试用期间主开发线可以继续前进，但试用环境只能部署明确的 RC 标签，不能跟随分支头自动更新。

该 RC 用于收集真实协同反馈和形成 UAT 证据，**不等于生产上线批准**，也不解除 I3-F、真实 secret/TLS、备份恢复和生产变更窗口等硬门禁。

## 2. 环境与数据隔离

- RC 环境拥有独立 PostgreSQL、Redis、附件存储和环境变量，不与继续开发环境共用数据卷或数据库。
- RC 只使用合成或经批准的试用数据；反馈中不得粘贴 secret、令牌或敏感人事内容。
- 部署记录必须同时保存标签、解析后的 commit、部署时间、操作者和数据库迁移 head。
- `health` 返回的 `version` 必须与当次获批候选标签一致；新增修复使用新不可变候选，不移动旧标签。

## 3. 代码分流与热修规则

| 场景 | 处理规则 |
|------|----------|
| 后续正常开发 | 从 RC 之后继续开发；不得移动或覆盖 `v0.93.0-rc.1` |
| RC 发现缺陷 | 从对应 RC 标签切出短期热修，完成最小改动与回归 |
| 需要重新发布 | 创建新 commit 和递增标签 `v0.93.0-rc.2`、`rc.3`；旧标签永久保留 |
| 热修回流 | 热修必须合回主开发线，避免后续版本重新引入问题 |
| 数据契约变化 | 优先向下兼容 Expand；在 I3-F Contract 获批前不得收缩兼容层 |

## 4. RC 准入范围

`v0.93.0-rc.1` 只吸收已完成的 Iteration 4-A–E、安全加固、已确认前端修复、文档校准和低风险质量清理；`v0.93.0-rc.2` 在该基线上仅增加部门负责人模板可见性热修及对应测试/发布材料。以下事项不为固定 RC 而强行完成：

- F-05 `TaskDetailShell` 大型拆分；
- S-01 与 Iteration 4 的人工 UAT；
- 只在目标 PostgreSQL/Redis、Linux、TLS、secret、备份恢复环境才能形成的证据；
- KI-011 系统管理员业务边界重构；
- 需要产品选择或会扩大兼容风险的新功能。

这些事项不阻碍继续开发，但其中标记为生产硬门禁的项目仍阻碍正式生产切流。

## 5. 员工试用反馈协议

每条反馈至少记录：RC 标签、发生时间、账号角色/所属部门、任务或模板类型、操作步骤、预期与实际结果、截图/日志、是否可稳定复现。问题按以下等级处理：

- **P0**：安全泄漏、数据破坏、无法登录或核心协同全局不可用——立即停止试用并回滚；
- **P1**：核心任务流无法继续或错误授权——暂停受影响流程，优先发 RC 热修；
- **P2/P3**：局部功能或体验问题——进入后续开发排期，除非修复风险极低，不移动已固定 RC。

系统管理员只负责环境和账号维护，不作为业务验收人；集合确认、独立验收与审批按 ADR-019 的真实业务角色测试。

## 6. 执行顺序

1. 每个候选统一固定 `VERSION`、Changelog、应用健康版本、独立 release commit 与注释标签；新候选号在完成变更范围审阅后确定。
2. 在隔离环境从标签部署，运行 Linux release gate、迁移检查和核心 smoke。
3. 开放员工试用，按统一反馈协议收集问题；I4/S-01 人工结果单独留证。
4. P0/P1 走 RC 热修线；其余问题进入主开发线。
5. 达到试用退出条件后决定下一 RC 或正式版，生产批准仍按生产 checklist 独立执行。

## 7. 当前状态

- 已记录版本：RC1/RC2 历史发布保留，RC3 在 `21975a6` 固定；后续提交和未提交改动需新候选及相应回归。
- 员工试用：RC1 开始实际测试是既有历史；当前目标部署版本、模板可见性复测及 I4/S-01/KI-009 签字按 W05 重新记录，不将历史部署状态写成当前确认。
- 生产准入：未批准；目标环境与人工证据仍待完成。

# Status

Machine status: in-progress.
