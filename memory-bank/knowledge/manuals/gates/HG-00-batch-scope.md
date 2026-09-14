---
type: paradigma-manual
title: "HG-00 批次范围回写说明"
description: "配套 gates/HG-00-batch-scope.yaml：将已落地的 W01/W02、W07–W13 工程批次纳入 HG-00 范围记录，待人工确认后 APPROVED。"
tags: [human-gate, hg-00, batch-scope]
timestamp: 2026-09-14T15:23:19+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [HG-00, 批次范围, Human Gate]
    en: [HG-00, batch scope, human gate]
  relations:
    related_to:
      - ./HG-00-batch-scope.yaml
      - ../2026-09-14-human-gates-playbook.md
      - ../../plans/2026-09-10-integrated-development-and-human-gates-plan.md
---

# HG-00 批次范围回写

## 状态

**READY_FOR_REVIEW** — 正式字段见 [HG-00-batch-scope.yaml](./HG-00-batch-scope.yaml)。Agent 不代签；请产品/技术负责人确认后填写 `approver` 与 `approved_at`，再将 `decision` 改为 `APPROVED`。

## 拟纳入范围

| 包 | 边界 |
|---|---|
| W01/W02 | CI / 发布检查 / 文档治理（`791a3d5`） |
| W07 | 会话与任务请求竞态（`26e44fb`） |
| W08 | **仅**站内消息中心 + Web Push；Email / 邀请邮件 / WebSocket **排除** |
| W09 | Redis 共享认证限流 |
| W10-bind | HR 生命周期显式图模板绑定（BE+FE）；**规则 UI 排除** |
| W11 | 岗位工作台 / 模板分区与结构化守卫 |
| W12 | 服务拆分 / 组织树测量 / critical_path 回归 |
| W13 | 入口包体拆分 / bundle-budget / mountApp |

候选锚点：`commit_sha = a1eec25`（完整 SHA 见 YAML）。

## 签字时请回复

1. 审批人显示名或角色（例如「产品/技术负责人」）
2. 批准时间（可用确认当下的 ISO 时间戳）
3. 是否同意 YAML 中的 `approved_actions` / `excluded_actions`
