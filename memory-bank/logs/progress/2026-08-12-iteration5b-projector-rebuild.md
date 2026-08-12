---
type: paradigma-progress-log
title: "2026-08-12 Iteration 5-B Projector 与重建基座"
description: "以现有三条持久化事实流建立独立 checkpoint、幂等投影、失败隔离和单对象/全量重建。"
tags: [progress, workflow-graph, iteration-5, projection, projector, rebuild]
timestamp: 2026-08-12T12:05:50+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: stable
  update_policy: append-only
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Iteration 5-B 工程完成, 20260812_02, projector, checkpoint, rebuild]
    en: [Iteration 5-B engineering complete, 20260812_02, projector, checkpoint, rebuild]
  relations:
    implements:
      - ../../knowledge/plans/2026-08-12-iteration5b-projector-rebuild-plan.md
    depends_on:
      - ../../knowledge/contracts/projection-contract.md
      - ./2026-08-12-iteration5a-projection-contract.md
---

# Iteration 5-B Projector 与重建基座

## 完成内容

- 新增 `ProjectionCheckpoint` 与 Alembic `20260812_02`，按 projection+stream 唯一，cursor 使用稳定时间+UUID，记录 idle/running/failed、累计处理、尝试、最近成功和错误摘要。
- 未创建第二条事件总线：Projector 直接消费已经提交的 `workflow_run_events`、`task_logs`、`task_comments`，三条源流独立推进。
- `WorkflowProjectionService` 负责 actor-neutral Task/Process Run/Timeline 幂等 upsert；默认阻止旧 source revision 覆盖新结果，显式 rebuild 可强制刷新派生文案和 audience。
- `WorkflowProjectionRebuildService` 支持单 Task、单 Run 和全量重建；全量开始先捕获三个源流高水位，事务内清空/重建后锚定 checkpoint，高水位后的事件留给增量消费。
- 新增 `python -m app.scripts.rebuild_workflow_projections`，要求显式三选一 `--task-id`、`--run-id` 或 `--all`，作为可审计的运维重建入口。
- ARQ 新增独立 `process_workflow_projection_events_job`；某流失败时回滚该流并在新事务登记失败，其他流继续，业务 Task/Run/Event/Log/Comment 不被修改。
- Projection 写 owner AST guard 扩展到 checkpoint；正式 Task Center 读路径、ROOT shell、JSON fallback 和兼容写入保持不变。

## 自动化证据

- test-first 定向：模型/迁移/owner、projector/rebuild/CLI、worker 失败隔离及现有 task-center 图投影共 18 tests PASS。
- 后端全量：479 collected / 447 passed / 32 registered skips / 0 failed。
- Alembic 单 head `20260812_02`；SQLite 从 `20260730_01` expand 到 head 再 downgrade PASS；`20260812_01:20260812_02` PostgreSQL 离线 SQL PASS。
- `python -m compileall -q app` 与 `git diff --check` PASS。

## 保留门禁与下一步

- 本机仍无 Docker/PostgreSQL，`20260812_01/02` 真实 PostgreSQL head↔base 需目标环境补证；这阻止 5-E 正式读侧切流，不阻止 5-C/5-D 加法开发。
- 下一开发批为 Iteration 5-C：先固定字段映射、差异分级、采样、lag 与隐私边界，再实现新旧查询 shadow comparison；只记录差异，不影响用户响应。
- KI-011、员工 RC2/I4/设计器/S-01 UAT 与 I3-F 目标环境证据继续按既定并行线处理。
