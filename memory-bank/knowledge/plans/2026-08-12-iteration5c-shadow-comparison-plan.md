---
type: paradigma-plan
title: "Iteration 5-C 投影 Shadow Comparison 计划"
description: "固定新旧查询影子比较的字段映射、差异分级、抽样、延迟和隐私边界。"
tags: [plan, active, workflow-graph, iteration-5, projection, shadow-comparison]
timestamp: 2026-08-12T14:20:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: hot
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Iteration 5-C, 影子比较, 投影差异, projection lag, 隐私]
    en: [Iteration 5-C, shadow comparison, projection diff, projection lag, privacy]
  relations:
    depends_on:
      - ./2026-08-12-iteration5b-projector-rebuild-plan.md
      - ../contracts/projection-contract.md
    related_to:
      - ./2026-08-11-f05-iteration5-6-sequencing-plan.md
---

# Iteration 5-C 投影 Shadow Comparison 计划

> **计划状态：ENGINEERING COMPLETE / TARGET OBSERVATION PENDING** — 独立后台比较、隐私安全观察表、recent/full 扫描、孤儿识别、30 天保留和测试均已完成；未接入 API 响应，未改变对象授权、用户可见性、ROOT shell 或正式读路径。目标环境持续样本仍是 5-E 前置证据。

## 1. 比较范围与权威侧

| comparison | 旧路径/期望值 | 新路径/实际值 | 核心字段 |
|---|---|---|---|
| `task_center_item` | `TaskService` 动态 graph-first 派生 + Task/Link/Node 源事实 | `task_center_items` | canonical identity、状态四层、当前处理人/动作、阶段、Run 标签、时间、返工/质量、archive/hidden、audience |
| `process_run_summary` | Run 详情现行的 Run/Node/Event/Link 动态聚合 | `process_run_summaries` | 状态/result、当前节点、五类计数、整数进度、时间和 audience |
| `node_timeline_entry` | `workflow_run_events`、`task_logs`、`task_comments` 源事实 | `node_timeline_entries` | source identity、父 Run/Node/Task、事件类型、actor、visibility、业务时间 |

影子比较必须独立读取源事实和投影行；不得为了得到“期望值”先调用 projector 重写实际行，也不得把比较器放进用户 API 请求事务。

## 2. 差异结果与等级

- `match/info`：采样对象存在且约定字段一致。
- `lagging/info`：投影缺失或 revision 落后，但源对象最后变化仍在 60 秒容忍窗口内。
- `difference/warning`：展示、标签、排序时间或非授权指标不一致。
- `difference/error`：状态、动作 owner、父对象、事件语义、计数或 revision 在容忍窗口外不一致。
- `difference/critical`：canonical identity、audience、部门、archive/hidden 或 visibility 不一致，可能扩大/缩小候选可见范围。
- `missing_projection/error`：容忍窗口外仍无投影；`orphan_projection/error` 留给全量审计识别无源投影；扫描本身异常由 worker 回滚本次观察记录并独立报告，不影响业务事实与 projector checkpoint。

每个观察结果只保存 `scan_id`、对象类型/UUID、结果、等级、差异字段名、双方 SHA-256 指纹、双方 revision、lag 毫秒和安全计数元数据。禁止保存字段旧值/新值、评论正文、任务描述、邮箱、附件信息或业务 payload。

## 3. 抽样与延迟口径

- 周期 worker 每 5 分钟运行 `recent`：分别取最近变更的 Task、Run 和三类时间线源，默认每类至多 100/100/200 条；只读源表与投影表。
- 周期 worker 在同一独立事务中清理超过 30 天的影子观察记录；只删除可再生诊断证据，不删除业务源或正式投影。
- 显式 CLI 支持 `--recent` 和 `--full` 且必须二选一。`--full` 用于 5-E 前审计与证据，不默认由周期任务触发。
- revision 使用源业务时间的 UTC 微秒整数；`lag_ms` 是源最新时间与投影 `source_updated_at`/`occurred_at` 的非负差，缺失投影则使用观察时间减源最新时间。
- PostgreSQL 的 `INTEGER` 无法保存微秒 revision；5-C 加法迁移把投影 `source_revision` 与 checkpoint 累计计数提升为 `BIGINT`。SQLite 保持兼容；降级只允许清空可重建投影行后恢复旧类型，不触碰业务源表。

## 4. 实施与完成门禁

1. 先补模型、迁移、比较器、隐私和 worker 失败测试。
2. 实现 flush-only shadow service、独立 ARQ 周期任务和显式扫描 CLI。
3. 校正测试暴露的 projector/旧查询算法差异；不得用忽略字段掩盖确定性错误。
4. 通过 SQLite expand/downgrade、定向测试和后端全量回归，更新投影契约、主计划与进度记录。

完成 5-C 不等于允许切流。真实 PostgreSQL head↔base、目标环境 shadow 样本、持续差异清零和用户批准仍是 5-E 前置门禁。

## 5. 当前验证结果

- `20260812_03` 新增 `projection_shadow_observations`，并把微秒级 `source_revision` 与 checkpoint `processed_count` 修正为 `BIGINT`；Alembic 保持单 head。
- `WorkflowProjectionShadowService` 对照 work item、Run shell、Run summary 与三类时间线源；记录 match/difference/lagging/missing/orphan，按 critical/error/warning/info 分级。
- 观察记录只保存差异字段名、指纹、revision、lag 和计数元数据；自动化测试证明不会写入被比较值、评论正文或业务 payload。
- ARQ 每 5 分钟执行 recent 抽样并清理 30 天前诊断证据；`python -m app.scripts.scan_workflow_projection_shadow --full` 提供切流前显式全量审计。
- shadow 测试暴露并修正 Run 进度的舍入漂移：projector 现在与现行详情 API 一致使用整数向下取整。
- SQLite expand/downgrade、PostgreSQL `20260812_02:20260812_03` 离线 SQL、定向测试及后端全量 **488 collected / 456 passed / 32 skipped / 0 failed** 通过。真实 PostgreSQL head↔base 与目标环境持续观察仍待补。
