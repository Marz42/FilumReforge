---
type: paradigma-plan
title: "F-05 至工作流图引擎 Iteration 5/6 实施顺序"
description: "记录已完成的 F-05，并固定 Iteration 5 投影运维建设、稳定观察与 Iteration 6 兼容层清理的顺序和门禁。"
tags: [plan, active, f-05, workflow-graph, iteration-5, iteration-6, sequencing]
timestamp: 2026-08-12T12:05:50+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [F-05 后续顺序, Iteration 5, Iteration 6, 投影, Legacy 清理]
    en: [F-05 sequence, Iteration 5, Iteration 6, projection, legacy cleanup]
  relations:
    depends_on:
      - ./2026-08-11-f05-task-detail-action-coordination-plan.md
    related_to:
      - ./workflow-graph-engine-upgrade-iteration-plan.md
      - ./workflow-graph-engine-iteration3f-readiness-gate-plan.md
      - ./2026-08-09-rc-employee-trial-plan.md
---

# F-05 至 Iteration 5/6 实施顺序

> **计划状态：ACTIVE** — F-05、Iteration 5-A/B/C 工程完成，下一开发批为 Iteration 5-D 运维与可观测性。RC2 复测、Iteration 4/设计器/S-01 人工 UAT、Iteration 3-F/5-A-C PostgreSQL 取证及目标环境 shadow 观察作为并行门禁，不改变开发顺序，但会阻止生产切流、停止兼容写入和删除旧结构。

## 1. 已确认的主开发顺序

1. **完成 F-05（已完成）**：数据、动作、任务资料附件、评论与留痕、活动时间线、工作流面板和节点追踪均已拆出；UI、权限、API 与业务语义不变。
2. **Iteration 5-A — 投影契约与加法迁移（工程完成 / PG 证据待补）**：已固定三类读模型契约并落地 `20260812_01`。
3. **Iteration 5-B — Projector 基座（工程完成 / PG 证据待补）**：已实现 `20260812_02` checkpoint、三源流幂等消费、失败隔离和单 Task/单 Run/全量高水位重建。
4. **Iteration 5-C — Shadow Comparison（工程完成 / 目标环境观察待补）**：新旧查询独立并行，记录字段差异、缺失/孤儿项和延迟；不切换用户读路径。
5. **Iteration 5-D — 运维与可观测性（下一批）**：建设 Outbox FAILED/重放、卡死 Run、no-route、Join wait、Context conflict 工作台，以及 projection lag、backlog 和统一 trace。
6. **Iteration 5-E — 受控读侧切换**：满足门禁并经批准后，让任务中心读取正式投影；ROOT Task 先降为 projection shell，稳定后才停止新增。
7. **稳定观察期**：确认 Link fallback、graph-first fallback、ROOT shell 新增量和投影差异达到 Iteration 6 前置标准。
8. **Iteration 6 — 单独批准的破坏性清理**：停止 JSON/双写锚点、移除跨模块直接写入和动态 graph-first 查询，归档后清理 Legacy E 服务、表、列与 feature flags。

## 2. 并行工作线与硬门禁

| 工作线 | 可以与什么并行 | 阻止什么 |
|---|---|---|
| RC2 员工复测 | F-05、Iteration 5-A～D | 未复测通过不得把 RC2 问题视为关闭 |
| Iteration 4 / 设计器 / S-01 人工 UAT | F-05、Iteration 5-A～D | 未签字不得标记业务验收通过 |
| Iteration 3-F 目标环境证据 | F-05、Iteration 5-A～D | 未完成 7 天观测和 31/31 报告，不得生产切流或收缩兼容层 |
| secret/TLS/备份恢复/迁移与回滚演练 | 可与开发并行 | 未通过不得进入生产变更窗口 |

Iteration 5-A～D 是加法、影子和运维建设，可以在外部门禁执行期间开发。Iteration 5-E 涉及生产读路径与 ROOT shell 行为，必须在对应目标环境证据齐全后单独批准。Iteration 6 不与稳定观察期重叠。

## 3. Iteration 6 的进入条件

- 新投影路径达到约定稳定观察期；
- Link fallback、graph-first fallback 和 ROOT shell 新增量均为零；
- PostgreSQL 并发、投影重建、备份恢复和回滚演练通过；
- 历史与 active Run 数量、迁移和归档报告经用户确认；
- 对兼容列/表的删除范围和恢复方式获得单独批准。

## 4. 暂不插队的事项

- KI-011 系统管理员业务边界继续延后；
- M-09 unarchive 与 `run_kind` dual-read 收窄等待策略和生产证据；
- 项目组、完整拖拽设计器、S3、i18n 等产品增强保留在中长期队列，不抢占 Iteration 5 主线；
- Timer、Webhook、Signal、Subprocess 等新节点能力不在正确性、投影和运维收口前扩张。

## 5. 阶段交付规则

- 每一子阶段先固定契约和失败语义，再实现服务/API/前端；
- 先写测试，至少覆盖幂等、对象授权、重复消费、重建和降级路径；
- 每批独立提交、独立进度记录，不把生产切流与功能开发混进同一提交；
- 任何删除、停止兼容写入或数据改写都必须提供归档、恢复与回滚证据。
