---
type: paradigma-progress
title: "KI-015 Strict 投影请求侧遥测工程完成"
description: "完成 Task Center strict 缺口分类、结构化日志、Operations 诊断、隐私边界和全量回归。"
tags: [progress, task-center, projection, observability, iteration-5e, known-issue]
timestamp: 2026-08-26T00:10:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: verified
  relations:
    resolves:
      - ../../knowledge/known-issues/ki-015-strict-projection-missing-telemetry.md
    related_to:
      - ../../knowledge/contracts/projection-contract.md
      - ../../knowledge/plans/implementation-plan.md
---

# KI-015 Strict 投影请求侧遥测工程完成

## 交付

- 新增线程安全、有界的 `StrictProjectionTelemetry`：按 surface、reason、projection schema version 计数，并保留最近 100 个请求样本。
- strict inbox、tracking、history 列表将不可用投影分类为 `missing`、`unsupported_schema`、`invalid_projection`；每次 fail-closed 都产生 `strict_projection_gap` error 日志。
- 日志和样本关联已通过可见性查询的 Task ID 与 `X-Request-ID`；不记录标题、正文、邮箱、附件或业务 payload。
- Admin-only Operations Dashboard 新增缺口总数、维度聚合、最近样本、最近成功 checkpoint，以及 `strict_projection_gap` error issue。
- 前端工作流运维页新增 Strict 缺口指标、维度标签和 Task/Request/checkpoint 最近样本表；对滚动发布中的旧响应保持缺字段兼容。
- 投影 schema version 改为 Task Center 与 projector 共用同一个常量，避免读写侧版本判断漂移。

## 不变量与边界

- strict fail-closed 语义不变：缺口仍从业务列表隐藏，不恢复 legacy 内容，也不改变 HTTP/列表成功响应。
- 只有列表查询已经判定为当前 actor 可见的 Task 才会产生含 Task ID 的遥测；Operations API 继续只允许 Admin，非 Admin 返回 404。
- Dashboard 数据是单进程、有界内存视图，重启后归零；跨 worker、持久告警以结构化 error 日志作为数据源。
- 本轮没有接入真实预发日志采集、通知渠道或生产 canary；这些仍须在 fallback 开启时完成目标环境验证。

## 自动化验证

- 后端针对性：projection、Operations、API 三组测试通过，覆盖三 surface、missing/unsupported schema、request ID、checkpoint、error issue 与不可见 Task 不记录。
- 后端全量：**500 collected / 468 passed / 32 skipped / 0 failed**；skipped 为既有 PostgreSQL 条件测试，本轮未把 skip 当成目标环境证据。
- 前端：**75 files / 217 tests passed**；`vue-tsc --build` 通过。
- Production build 通过；入口仍为 809.57 kB / gzip 255.69 kB，对应 KI-017，未通过提高告警阈值掩盖。
- `git diff --check` 在代码阶段通过；文档和 Paradigma projection 在最终收口时重新验证。

## 后续门禁

1. 真实预发接入 `strict_projection_gap` 日志采集，按 surface/reason/schema version 验证查询、阈值和通知路由。
2. 在 fallback 开启时人工制造可恢复的测试缺口，确认 Operations 页面、日志告警、Task/Request/checkpoint 排障链路和恢复操作。
3. 与 rebuild、full shadow、I3-F 连续证据和人工 UAT 一起提交 fallback=false 小流量 canary 批准。
4. KI-014、KI-016、KI-017 保持独立问题，不把本轮完成扩大解释为数据库 drift、登出请求或包体问题已解决。
