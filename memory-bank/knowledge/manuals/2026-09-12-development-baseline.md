---
type: paradigma-manual
title: "2026-09-12 统一开发基线"
description: "记录本地整合方案、远端 KI-014 观察清单和原有 Phase C 实现的合并边界、验证与后续入口。"
tags: [baseline, git, ki-014, development, handoff]
timestamp: 2026-09-12T20:27:00+08:00
paradigma:
  retrieval_hints:
    zh: [统一开发基线, Git, KI-014]
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  relations:
    related_to:
      - ../plans/2026-09-10-integrated-development-and-human-gates-plan.md
      - ../plans/2026-08-26-ki014-schema-drift-remediation-plan.md
      - ./2026-09-04-ki014-phase-c-observation-checklist.md
      - ./manual-database-operations.md
---

# 2026-09-12 统一开发基线

本次用户授权为合并本地与远端、保存原有未提交工作并同步 GitHub，形成进一步开发的共同起点。这里的基线是开发基线，不是 RC 标签、发布批准或目标数据库验收。

## 合并来源与可恢复性

- 共同起点：`61ea3d3`，KI-014 Phase A/B expand。
- 本地方案：`4820511`，17 个工作包与 9 个 Human Gates 的整合方案。
- 远端文档：`98db3c8`，Phase C 观察清单、历史审计记录与工程收尾状态。
- 合并提交：`bd32fc1`，保留上述两条提交历史；冲突逐项解决，未重写远端历史。
- Phase C 独立提交：`8f98dd4`，保存原有只读工具、测试、配套文档和历史运行记录。源代码与测试恢复后逐字核对备份，未借同步过程修改业务实现。
- 本地备份分支：`codex/backup-before-baseline-sync-20260912`，保留合并前本地提交；带有 `baseline-sync-20260912` 标记的 stash 保留原有 9 个修改/未跟踪文件。该 stash 是恢复备份，不是待再次应用的工作；正常开发不要重复 apply。

## 统一后的状态口径

| 对象 | 统一结论 |
|---|---|
| A/B 工程 | 已完成并提交；权威迁移为 `20260827_01`，类型为 `CompatibleValueEnum` |
| Phase C 工具与清单 | 已保存并接通使用入口；工具提供自动聚合证据，清单要求业务与人工证据 |
| Phase C 目标观察 | 未完成；仍需代表性数据、完整业务周期与应用验证 |
| Phase D contract | 未落地、未执行；观察完成后单独批准 |
| KI-014 总任务 | `blocked`，原因明确限定为目标观察和 contract 等待；不把工程完成等同于整个事项关闭 |
| strict 切流 / Iteration 6 | 原门禁保持开放，未取得本次同步之外的批准 |

远端任务 YAML 的 `completed` 只表达 A/B 工程收尾，与远端自身“C/D 待完成”的文档同时存在。统一时保留本地有效任务事实，通过 `pd task block` 明确剩余工作，再重建生成投影；没有直接拼接状态字段或代填批准。

远端日志提及的 `20260904_01` / `20260904_02` 与 `CaseInsensitiveValueEnum` 是已弃用的并行轨。本次没有恢复这些迁移或创建数据库双 head。历史日志正文保留，仅修复导入日志的类型/append-only 元数据与行尾格式，使其能被当前工具读取。

## 验证与限制

- Phase C、枚举兼容及 SQLite 迁移专项：12 passed，1 个 PostgreSQL 用例明确排除。
- 后端非 PostgreSQL 全量回归：478 passed、10 skipped、22 deselected，耗时 215.34 秒。10 项跳过为既有 Legacy E 测试，22 项 PostgreSQL 测试明确排除；不把跳过或排除项计为通过。
- 本次 Docker daemon 不可用，未重跑 PostgreSQL 集成迁移，也未连接或修改目标数据库。2026-08-27 的隔离 PostgreSQL 结果仍是历史证据。
- 新合入文档的相对链接、运行事实、索引和上下文需在最终提交前验证。既有 Paradigma 产品/协议版本冲突、旧日志元数据和缺失 CI 等问题继续按 W01/W02 处理，不宣称整体发布检查已绿。
- 没有改变前端、API、业务状态机或生产配置；没有部署、执行 contract 或切流。

## 进一步开发入口

1. 以 GitHub `main` 上包含本说明的同步提交为基础拉取或创建开发分支；先检查工作区及远端状态，再开始下一批。
2. 以 [整合方案](../plans/2026-09-10-integrated-development-and-human-gates-plan.md) 为排期入口。本次完成 W00 中的变更归属、历史整合和保存；隔离 PG 严格复核、未来候选身份和发布门禁仍需继续。
3. 工程批次优先 W01/W02；目标访问具备后，按 [Phase C 清单](./2026-09-04-ki014-phase-c-observation-checklist.md) 和 [数据库操作手册](./manual-database-operations.md) 取证。
4. 当前旧任务因目标条件待满足而 blocked。目标观察恢复时先 `pd task unblock`；若转入独立工程任务，按项目 CLI 的任务交接流程处理旧任务，不直接覆盖 active pointer 或将未完成事项标记完成。

精确最终 SHA、远端同步结果与工作区状态以 Git 记录和本次提交后的核对为准，不在同一个提交的正文中伪造自引用 SHA。
