---
type: paradigma-progress
title: "Iteration 5-C Shadow Comparison 工程完成"
description: "完成隐私安全投影影子比较、观察持久化、周期抽样、全量审计与 BIGINT 修正。"
tags: [progress, workflow-graph, iteration-5, projection, shadow-comparison]
timestamp: 2026-08-12T16:40:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: verified
  relations:
    depends_on:
      - ../../knowledge/plans/2026-08-12-iteration5c-shadow-comparison-plan.md
      - ../../knowledge/contracts/projection-contract.md
---

# Iteration 5-C Shadow Comparison 工程完成

## 交付

- 新增 `projection_shadow_observations` 与 `20260812_03`；观察行包含 scan/subject、outcome、severity、差异字段名、指纹、revision、lag 和安全元数据。
- 修正 5-B PostgreSQL 风险：三类投影 `source_revision` 和 checkpoint `processed_count` 改为 `BIGINT`，避免 UTC 微秒 revision 溢出。
- `WorkflowProjectionShadowService` 独立从源事实派生 Task Center work item、Run shell、Run summary 和三类 Timeline 快照，不调用 projector 改写实际行。
- 支持 match/difference/lagging/missing/orphan，60 秒默认 lag 容忍和 critical/error/warning/info 分级；观察表不保存字段值、正文或业务 payload。
- ARQ 每 5 分钟 recent 抽样，自动清理 30 天前观察；CLI 要求显式 `--recent`/`--full`，full 用于切流前审计。
- shadow 测试发现并修复 Run progress 的舍入漂移：统一为现行详情 API 的整数向下取整。

## 验证

- 失败测试先行：模型/隐私、三投影族一致、字段篡改、lag 容忍、整数进度、worker 故障隔离和独立注册均覆盖。
- SQLite pre-projection expand→head→downgrade PASS；Alembic 单 head `20260812_03`。
- PostgreSQL `20260812_02:20260812_03` 离线 SQL PASS，生成 `INTEGER→BIGINT` 与 JSONB 观察表 DDL。
- `compileall` PASS；后端全量 **488 collected / 456 passed / 32 skipped / 0 failed**。

## 未改变与后续门禁

- 未切换 `/tasks`、Task Center、Run detail 或 Timeline 正式读路径；未改变对象授权、ROOT Task、兼容 JSON/Link 或业务命令事务。
- 真实 PostgreSQL head↔base、目标环境 rebuild + full shadow 和持续差异/lag 样本仍待补，阻止 5-E。
- 下一开发批为 Iteration 5-D 运维与可观测性；先固定动作授权、重放幂等、指标和 trace 口径。
