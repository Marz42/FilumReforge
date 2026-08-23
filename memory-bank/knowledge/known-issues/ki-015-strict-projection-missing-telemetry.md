---
type: paradigma-known-issue
title: "KI-015: Strict 投影缺口缺少请求侧显式遥测"
description: "Task Center strict 模式会 fail-closed 隐藏缺投影的图任务，但请求侧尚无结构化计数、日志或用户可见降级提示。"
tags: [known-issue, task-center, projection, observability, iteration-5e]
timestamp: 2026-08-23T23:25:00+08:00
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

**开放 / 中优先级（P1）/ 不阻断 5-E 工程交付。** Strict 模式已经正确停止动态回退，缺失或 schema 无效的图任务也不会伪装成 legacy 条目；但列表请求当前只是跳过条目，没有同步产生结构化事件或指标。

## 现象与证据

- `TaskService._strict_projection_missing()` 在 inbox、tracking、history 三个列表入口统一 fail-closed。
- 列表层命中该条件后直接 `continue`，调用方只能看到条目减少，无法从响应或日志区分“没有业务任务”和“投影缺口”。
- Full shadow、rebuild 与 Operations 指标能够离线发现差异，但尚未形成请求侧的即时缺口信号。

## 风险

- Canary 期间单个投影损坏可能表现为任务暂时消失，业务反馈早于运维告警。
- 若仅观察 HTTP 成功率，接口仍返回 200，常规可用性监控无法识别数据不完整。
- 直接在业务响应中回退会破坏 strict 语义，因此不能用恢复 legacy 展示来掩盖该问题。

## 当前缓解

1. 生产首次部署保持 `TASK_CENTER_PROJECTION_FALLBACK_ENABLED=true`。
2. 关闭 fallback 前执行全量 rebuild 和 full shadow，并持续观察 lag/backlog。
3. Strict canary 出现条目缺失时立即恢复 fallback，随后按 Task/Run 重建和排障。

## 完成标准

- 增加按列表 surface、缺失原因和 projection schema version 分类的计数器或结构化日志。
- Operations 页面/告警能显示 strict 请求侧缺口，并关联 Task ID、trace ID 与最近 checkpoint。
- 增加“缺投影仍返回 200，但监控必然记录缺口”的回归测试；不得泄露无权查看的 Task 标识。
