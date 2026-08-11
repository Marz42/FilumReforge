---
type: paradigma-plan
title: "实施计划状态目录"
description: "区分现行计划、已完成实施记录与已被取代的 Legacy 方案，避免历史计划被误作当前排期。"
tags: [plan, governance, active, completed, legacy]
timestamp: 2026-08-11T23:42:43+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [计划状态, 现行计划, 已完成计划, Legacy 计划]
    en: [plan status, active plan, completed plan, legacy plan]
  relations:
    related_to:
      - ../roadmap.md
      - ./implementation-plan.md
---

# 实施计划状态目录

> 本目录只说明“哪份计划还能指导下一步”。`COMPLETED` 文件保留验收边界和工程历史；`LEGACY` 文件仅用于考古，不得把其中未勾选条目重新带回排期。真实实现以领域文档、契约和代码为准。

## ACTIVE — 仍指导执行

| 计划 | 当前用途 |
|---|---|
| `implementation-plan.md` | 总体实施主线 |
| `workflow-graph-engine-upgrade-iteration-plan.md` | 图引擎 Iteration 0～6 总计划；当前指向 I5/I6 |
| `2026-08-11-f05-iteration5-6-sequencing-plan.md` | F-05 → I5 → 稳定观察 → I6 的正式顺序 |
| `workflow-graph-engine-iteration3f-readiness-gate-plan.md` | 仍开放的目标环境与生产切流门禁 |
| `2026-08-09-rc-employee-trial-plan.md` | `v0.93.0-rc.2` 员工复测与主线分流 |

## COMPLETED — 已完成的实施记录

| 计划 | 完成边界 / 后续去向 |
|---|---|
| `2026-07-21-template-self-review-fix-plan.md` | 自行验收死锁修复完成 |
| `2026-07-22-template-decouple-phase1-plan.md` | 模板解耦 Phase 1 完成 |
| `2026-07-28-template-decouple-phase2-plan.md` | 工程实现完成；人工 UAT 由统一清单跟踪 |
| `2026-07-29-iteration4-preflight-alignment-plan.md` | I4 前置对齐完成 |
| `2026-07-29-video-domain-neutral-migration-inventory.md` | 领域中立核心迁移完成；兼容删除转入 I6 |
| `2026-07-30-template-availability-paradigma-upgrade-plan.md` | 部门治理与 Paradigma 0.5.0 升级完成 |
| `2026-08-09-security-release-readiness-plan.md` | 本地安全修复完成；外部门禁转入上线清单 |
| `2026-08-10-f05-task-detail-data-coordination-plan.md` | F-05 数据协调批次完成 |
| `2026-08-10-iteration4-uat-preflight-plan.md` | UAT 准备工具完成；人工执行转入 UAT 清单 |
| `2026-08-10-template-governance-audit-plan.md` | 数据检查与修正版入口完成 |
| `2026-08-11-f05-task-detail-action-coordination-plan.md` | F-05 动作协调批次完成 |
| `paradigma-memory-bank-refactor-plan.md` | 三态迁移与 0.5.0 协议升级完成 |
| `s01-task-statistics-plan.md` | 工程实现完成；人工验收由统一清单跟踪 |
| `task-center-enhance.md` | TCE Phase 1～5 完成 |
| `task-center-v2-implementation-plan.md` | TC-P0～P2 完成 |
| `tc-p2-views-stats-plan.md` | 三视图与统计批次完成 |
| `ui-information-architecture-plan.md` | IA Phase A～F 完成 |
| `ui-refactor-spec-v2.md` | UI 重构规格已交付 |
| `workflow-graph-engine-iteration1-implementation-plan.md` | Iteration 1 工程完成 |
| `workflow-graph-engine-iteration2-implementation-plan.md` | Iteration 2 工程完成 |
| `workflow-graph-engine-iteration3-implementation-plan.md` | Iteration 3 A～E 完成；3-F 外部门禁单列 |
| `workflow-graph-engine-iteration4-handler-plan.md` | Iteration 4 A～E 工程完成 |
| `workflow-refactor-implementation-plan.md` | 历史 Phase 1～11 主干完成 |
| `workflow-video-v1-w0-adr.md` | W0 决策和实施完成；现行领域边界见 ADR-018 |

## LEGACY — 已被新计划或架构取代

| 计划 | 被什么取代 |
|---|---|
| `improvements-stage2-implementation-plan.md` | `implementation-plan.md` 与当前路线图；残余方向已进入中长期队列 |
| `workflow-video-v1-implementation-plan.md` | 领域中立图模板、Iteration 4 Handler 与 ADR-018 |
| `workflow-video-v1-ui-simplification-design.md` | 当前任务中心与模板设计器实现 |

## 维护规则

- 新计划默认标为 `ACTIVE`；完成后改为 `COMPLETED`，并把仍开放的工作迁到新的 active 计划或清单。
- 计划被架构决策或新主计划取代时标为 `LEGACY`，不得仅因仍有未勾选项而继续执行。
- `COMPLETED` / `LEGACY` 文档使用 `lifecycle: stable`；active 主计划使用 `lifecycle: evolving`。
- `logs/progress/` 是事实日志，不参与计划状态迁移，也不回写历史数字。
