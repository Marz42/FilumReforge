---
type: paradigma-log
title: "2026-08-12 Iteration 5-A 投影契约与加法迁移"
description: "固定 Task Center、Run 摘要和节点时间线投影契约，新增可回滚空表，不切换读路径。"
tags: [progress, workflow-graph, iteration-5, projection, migration, contract]
timestamp: 2026-08-12T00:45:59+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: append-only
  update_policy: append-only
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Iteration 5-A 工程完成, 投影空表, 20260812_01, PostgreSQL 门禁]
    en: [Iteration 5-A engineering complete, projection tables, 20260812_01, PostgreSQL gate]
---

# Iteration 5-A 投影契约与加法迁移

## Outcome

- 新增 HOT `projection-contract.md`，从现有 inbox/tracking/history、Run detail 和 Task activity 反向固定字段来源、canonical identity、授权复核、稳定排序、版本与重建边界。
- 新增 `workflow_projection.py`：`TaskCenterItem`、`ProcessRunSummary`、`NodeTimelineEntry` 三类可清空/重建读模型。
- 新增 Alembic `20260812_01`，只建三张空表、FK、check/unique constraints 与索引；无回填、无 API/前端接入、无读侧切换、无旧结构删除。
- audience JSON 只作候选筛选；Task/Run 最终授权继续复用现有对象级 policy。actor-specific available actions 不持久化，评论正文/附件/完整交付审批仍归源表。
- AST guard 固定未来 Projection 写入只能位于 projector/rebuild owner 文件。

## Test-first and Verification

- 新模型不存在时定向测试先在 import 阶段失败；实现后 canonical subject 唯一、父对象形状、进度约束、source 去重、索引和非事实字段边界通过。
- 模型/迁移/架构定向：7 passed / 1 PostgreSQL skip。
- SQLite pre-head schema：stamp `20260730_01` → upgrade head → downgrade `20260730_01` PASS。
- Alembic 单 head `20260812_01`；新 revision 的 PostgreSQL 离线 SQL生成 PASS；`compileall` PASS。
- 后端最终全量：472 collected / 440 passed / 32 registered skips / 0 failed（约 3m40s）。

## Gate and Next

- 本机 Docker daemon 不可用且无可达 PostgreSQL；真实 PostgreSQL head↔base 仍是 5-A 外部证据门禁，不能用 SQLite 代替。
- 该证据不阻止 5-B 加法开发，但在完成前不得进入 5-E 正式读侧切流。
- 下一批先规划 checkpoint、事件幂等、旧 revision 拒绝覆盖，以及单 subject / 单 Run / 全量 rebuild；投影失败不得回滚业务命令。
