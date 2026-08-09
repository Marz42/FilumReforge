---
type: paradigma-log
title: "模板范围与父子依赖数据治理"
description: "恢复主开发线，补齐模板数据检查、修正版入口与回归测试。"
tags: [progress, workflow-template, availability-scope, governance, frontend]
timestamp: 2026-08-10T00:22:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: append-only
  update_policy: append-only
  epistemic_status: confirmed
  retrieval_hints:
    zh: [模板数据检查, 父子模板, 可用部门, 主开发线]
    en: [template governance audit, dependency scope, mainline]
---

# 模板范围与父子依赖数据治理

## Outcome

- `v0.93.0-rc.1` 保持不可变，主开发线在标签之后恢复；KI-011 明确排除在本批次之外。
- 新增只读模板治理服务与管理 API，只返回调用者可管理的 ACTIVE/DRAFT 模板问题。
- 检查覆盖 intentional global 人工确认、global 残留部门编号、空 departments、缺失/停用部门。
- 同时解析模板 config、节点 `aggregate_schema.on_confirm` 与通用 `on_complete`，发现目标缺失、旧 `child_template_code` 和父子可用范围不兼容。
- 任务模板页新增“数据检查”；草稿问题可直接打开设计器，ACTIVE 问题只允许派生新版本修正。
- 上线清单 B-06 已改为使用该入口执行、由业务负责人确认 global、以确定错误归零作为验收证据。

## Verification

| Gate | Result |
|------|--------|
| Backend targeted | 9/9 PASS（治理审计 4 + 已发布范围治理 5） |
| Backend full | 464 collected / 432 passed / 32 target-environment skipped / 0 failed |
| Frontend targeted | 2 files / 5 tests PASS |
| Frontend full | 65 files / 182 tests PASS |
| Frontend type-check | PASS |
| Frontend production build | PASS；最大入口包仍约 809 KB warning |
| Frontend lint | oxlint + ESLint full PASS，0 error；同步清理 24 项既有测试/E2E 静态告警 |
| Backend syntax | `compileall app tests` PASS |

## Follow-up

- 在开发/预发真实数据上执行“数据检查”，业务负责人决定哪些 global 是明确授权。
- 对确定错误按“草稿直接改 / ACTIVE 新版本改”处理；子模板换版本后同步修正父模板引用。
- 完成 Iteration 4 / 设计器 Phase 2 / S-01 人工 UAT，再从反馈中选择下一批主线开发。
