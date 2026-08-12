---
type: paradigma-plan
title: "Iteration 5-A 投影契约与加法迁移计划"
description: "先固定任务中心、Run 摘要和节点时间线投影的字段、所有权、授权与重建边界，再以可回滚迁移增加读模型结构。"
tags: [plan, active, workflow-graph, iteration-5, projection, contract, migration]
timestamp: 2026-08-12T12:05:50+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Iteration 5-A, 投影契约, task_center_items, process_run_summaries, node_timeline_entries]
    en: [Iteration 5-A, projection contract, task center items, process run summaries, node timeline]
  relations:
    depends_on:
      - ./2026-08-12-f05-task-detail-workflow-presentation-plan.md
      - ./2026-08-11-f05-iteration5-6-sequencing-plan.md
    related_to:
      - ../contracts/data-contracts.md
      - ../contracts/database/graph-engine-schema.md
      - ../domains/workflow-graph-engine.md
      - ../domains/task-center.md
---

# Iteration 5-A 投影契约与加法迁移计划

> **计划状态：ENGINEERING COMPLETE / POSTGRES EVIDENCE PENDING** — 契约、模型与 `20260812_01` Expand-only 迁移已完成；SQLite expand/downgrade 和全量回归通过。本机无 Docker/PostgreSQL，生产方言 head↔base 专项仍须在目标环境执行。未切换 Task Center 读路径，未停止 graph-first/ROOT shell/兼容写入，也未改变业务命令事务。

## 1. 目标边界

- `task_center_items` 统一表达 standalone Work Item、HumanTask、Approval、Process Run shell 与系统告警在任务中心所需的稳定字段。
- `process_run_summaries` 保存 Run 列表/详情的阶段、进度、阻塞、责任人和聚合计数，不要求查询时动态扫描 Runtime 内部表。
- `node_timeline_entries` 以稳定事件身份聚合 Node Event、Work Item Activity、评论、交付、审批、返工与接管记录。
- 三类投影均声明来源身份、来源修订、投影 schema 版本、最近事件与投影时间，允许后续幂等覆盖或清空重建。
- Projection 模块是唯一写 owner；Task/Workflow/API 只能读投影或发布源事件，不得把投影反写业务模型。

## 2. 先固定的契约

1. **身份与唯一性**：为每种投影定义 canonical subject key；时间线使用 source type + source id/event id 去重。
2. **授权快照**：保存 owner/assignee/creator、部门范围和可见性所需索引字段；最终授权仍由现行业务策略裁决，不能只凭投影中的 UUID 放行对象直读。
3. **状态语义**：区分原始 engine/work-item 状态与用户态分组，禁止把 UI 文案写成唯一事实。
4. **顺序与游标**：列表和时间线必须提供稳定时间戳 + UUID tiebreaker；重建后分页顺序保持确定。
5. **可重建性**：投影不拥有评论、附件、交付或审批正文；缺失投影可由写模型和事件重建，删除投影不得删除业务事实。
6. **版本与降级**：记录 projection schema version；未知版本或 lag 只触发 shadow/fallback，不得使业务命令失败。

## 3. 实施批次

1. 盘点当前 inbox/tracking/history、Run 统计、详情时间线的真实字段与对象授权入口，形成字段来源矩阵。
2. 在数据契约中固定三类投影的列、枚举、索引、唯一约束、FK/删除策略、owner 与重建语义。
3. 新增 SQLAlchemy 模型和 Alembic **Expand-only** 迁移；迁移只建表/索引，不回填、不切读、不删除旧结构。
4. 增加模型/迁移/架构边界测试，证明唯一性、稳定排序、可清空和投影写 owner 约束。
5. 完成 SQLite 单元与 PostgreSQL 迁移专项；形成 5-A 独立提交。Projector、checkpoint、rebuild 命令从 5-B 开始。

## 4. 非目标与门禁

- 本阶段不创建生产投影数据、不比较新旧结果、不增加前端入口。
- 不改变现有 `/tasks` API 响应，不让 Task Center 查询新表。
- 不停止 ROOT Task、JSON anchor、Link-first fallback 或 graph-first 查询。
- 任何读侧切流、双写停止或 Legacy 删除都不属于 5-A；分别受 5-E、稳定观察期与 Iteration 6 门禁约束。

## 5. 完成标准

- 字段来源矩阵和三类投影契约无未解释的权限/状态/排序字段。
- Expand/rollback 迁移可执行，现有数据库和 API 行为不变。
- 模型、迁移与 owner 边界测试通过；涉及数据库约束的结论由 PostgreSQL 专项确认。
- 文档明确把 checkpoint/projector/rebuild 交给 5-B，把 shadow comparison 交给 5-C。

## 6. 当前验证结果

- `task_center_items`、`process_run_summaries`、`node_timeline_entries` ORM/约束/索引已实现；Projection AST guard 固定未来唯一写 owner 文件。
- 5-A revision 为 `20260812_01`；5-B 追加 checkpoint 后仓库单 head 已前移至 `20260812_02`。两段 PostgreSQL 增量离线 SQL 均可生成。
- SQLite pre-head schema 上的 stamp → upgrade → downgrade 通过，证明三表可加可撤且未触碰旧表。
- 模型/迁移/架构定向 7 passed / 1 PostgreSQL skip；完整后端回归通过。
- 尚缺真实 PostgreSQL `head → base` 证据；本机 Docker daemon 不可用，因此本计划保持 active gate，不把 SQLite 当作生产约束结论。
