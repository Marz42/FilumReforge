---
type: paradigma-known-issue
title: "KI-015: Strict 投影缺口缺少请求侧显式遥测"
description: "Task Center strict 模式的 fail-closed 缺口现已具备请求侧结构化日志、维度计数和 Admin Operations 诊断。"
tags: [known-issue, task-center, projection, observability, iteration-5e]
timestamp: 2026-08-26T00:10:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [strict 投影缺失, fail-closed, 任务隐藏, 投影遥测]
    en: [strict projection missing, fail closed, hidden task, projection telemetry]
  relations:
    related_to:
      - ../contracts/projection-contract.md
    depends_on:
      - ../plans/2026-08-12-iteration5d-operations-observability-plan.md
---

# KI-015: Strict 投影缺口缺少请求侧显式遥测

## 状态与优先级

**已解决（P1 engineering complete）@ 2026-08-26。** Strict 模式继续停止动态回退，缺失或 schema 无效的图任务不会伪装成 legacy 条目；inbox、tracking、history 现在会同步记录请求侧缺口，并由 Admin-only Operations Dashboard 展示。

## 现象与证据

- `TaskService._strict_projection_missing()` 在 inbox、tracking、history 三个列表入口继续统一 fail-closed。
- `TaskService._graph_task_projection_state()` 将缺口分类为 `missing`、`unsupported_schema`、`invalid_projection`，并携带实际 schema version（若存在）。
- `StrictProjectionTelemetry` 记录 `surface/reason/projection_schema_version/task_id/request_id`；error 级结构化日志供跨进程采集与告警，进程内有界计数和最近样本供 Operations 页面读取。
- Operations Dashboard 增加 `strict_projection_gap_count`、维度聚合、最近样本和最近成功 checkpoint，并在存在缺口时生成 `strict_projection_gap` error issue。
- Task Center 的成功响应和 fail-closed 语义没有变化；Task ID 只会在列表可见性查询通过后记录，并且详细样本只通过 Admin-only Operations API 暴露。

## 风险

- Canary 期间单个投影损坏可能表现为任务暂时消失，业务反馈早于运维告警。
- 若仅观察 HTTP 成功率，接口仍返回 200，常规可用性监控无法识别数据不完整。
- 直接在业务响应中回退会破坏 strict 语义，因此不能用恢复 legacy 展示来掩盖该问题。

## 已落地设计

1. 每次 strict 缺口都产生 `strict_projection_gap` error 日志，可按 surface、reason、schema version 建立目标环境告警。
2. Operations 页面展示进程累计值、最近 100 个样本、Task/Request ID 与最新 checkpoint 状态，支持从用户反馈回溯到重建进度。
3. 生产首次部署仍保持 `TASK_CENTER_PROJECTION_FALLBACK_ENABLED=true`；关闭前执行全量 rebuild/full shadow 并验证目标环境日志告警。
4. Strict canary 出现条目缺失时仍应立即恢复 fallback，随后按 Task/Run 重建和排障，不能通过 legacy 内容掩盖。

## 验证证据

- 后端针对性回归覆盖三类 surface、missing/unsupported schema 分类、request ID、最近 checkpoint 和 Operations error issue。
- 回归证明非关联用户的列表请求不会为不可见 Task 生成遥测样本。
- 2026-08-26 本地全量 backend pytest 通过；frontend 75 files / 217 tests、type-check 与 production build 通过。
- 本轮没有执行真实预发日志采集器、告警路由或生产 canary；这些仍属于发布门禁，不作为本地工程完成证据。

## 完成标准

- [x] 增加按列表 surface、缺失原因和 projection schema version 分类的计数器与结构化日志。
- [x] Operations 页面显示 strict 请求侧缺口，并关联 Task ID、request/trace ID 与最近 checkpoint。
- [x] 增加“缺投影仍正常返回列表，但监控必然记录缺口”的回归测试。
- [x] 非关联用户不会为不可见 Task 产生遥测；详细样本仅在 Admin-only Operations 边界返回。

## 运行边界

- Operations 计数与最近样本是进程级、有界内存视图，进程重启后归零，也不负责多 worker 聚合。
- 生产的跨 worker 持久告警应消费 `strict_projection_gap` 结构化日志；在真实预发完成采集规则和通知路由验证前，不能宣称生产告警已经生效。
