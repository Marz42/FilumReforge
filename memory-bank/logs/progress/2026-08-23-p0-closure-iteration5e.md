---
type: paradigma-progress-log
title: "2026-08-23 P0 收口与 Iteration 5-E 严格投影验证"
description: "记录 PostgreSQL/Redis、5-E 读切换、多账号 UAT、N4 修复、恢复演练和剩余外部门禁。"
tags: [progress, p0, iteration-5e, postgresql, uat, release]
timestamp: 2026-08-23T22:55:00+08:00
paradigma:
  schema_version: "0.5.0"
  layer: log
  temperature: cold
  lifecycle: append-only
  update_policy: append-only
  epistemic_status: confirmed
  retrieval_hints:
    zh: [P0 收口, 5-E, 严格投影, 备份恢复, 多账号 UAT]
    en: [P0 closure, iteration 5E, strict projection, backup restore, multi-account UAT]
  relations:
    related_to:
      - ../../knowledge/contracts/projection-contract.md
      - ../../knowledge/manuals/2026-08-09-production-release-checklist.md
      - ../../knowledge/known-issues/ki-009-standalone-action-dual-track.md
---

# 2026-08-23 P0 收口与 Iteration 5-E 严格投影验证

## 交付

- Task Center graph-backed 条目改为 `task_center_items` 投影优先读取；支持总开关与缺失投影动态回退，默认安全配置为 reads=true、fallback=true。
- 严格 canary 使用 fallback=false；缺失/无效投影 fail-closed，不会伪装成 legacy 条目；投影仍不缓存 actor-specific `available_actions`，动作继续走实时 policy。
- 修复图模板实例化默认部门异步竞态。
- 修复专用 N4 review node 自审基准：review task 的 reviewer/assignee 不再被误当作上游交付执行人。
- Live UAT 以 instance detail `task_id` 和唯一 `run_label` 精确映射，历史运行不会污染当轮任务选择。
- 新增 KI-009 standalone 创建者/执行人/验收人真实后端 Chromium 用例。

## 生产方言与投影证据

| 检查 | 结果 |
|------|------|
| PostgreSQL marker | 22 passed，`FILUM_REQUIRE_POSTGRES_TESTS=true` |
| fresh migration | base → `20260812_04 (head)` |
| Iteration 4 readiness | runtime_ready=true；0 blocker / 0 incomplete object |
| final rebuild | Task=97、Run=28、Timeline=282 |
| final full shadow | compared=407、match=407；difference/missing/orphan/lagging=0；scan=`0d490838-580a-411b-b2b1-bbef0aa8a664` |
| fallback on live | 核心/视频多账号 8/8 |
| strict 5-E live | 核心/视频多账号 8/8；KI-009 standalone 1/1 |

## 恢复与回滚

- 容器内 `pg_dump -Fc` 后恢复到临时数据库。
- 恢复计数：tasks=82、workflow_graph_instances=24、task_center_items=82、node_timeline_entries=234。
- 恢复库执行 `20260812_04 → 20260812_03 → 20260812_04`，版本与记录数不变。
- development / production Compose `config -q` 均通过。

## 回归

- Backend：499 collected，全量 0 failed；compileall 通过。
- Frontend：75 files / 217 tests、type-check、production build 通过。
- Playwright：core mock 35/35；workflow multi-account mock 15/15；strict live 合计 9/9。
- 改动前端文件 ESLint / Oxlint 0 error。

## 未代签的外部门禁

- 真实预发/生产 TLS、域名、CORS、refresh cookie、真实 secret 与可信代理来源。
- 数据库与附件生产备份的 RPO/RTO、负责人、通知渠道和维护窗口。
- Iteration 3-F 连续 7 天、31/31 报告与业务/发布负责人签字。
- RC2、I4、设计器、S-01 的真实员工业务验收。
- KI-014：目标 PostgreSQL `alembic check` 的历史 ORM/DDL drift 尚未清理；当前迁移链和恢复演练通过不等于 drift clean。

## 下一步

1. 在真实预发以 fallback=true 部署同一候选，重跑 rebuild/full shadow 并积累持续样本。
2. 完成人工 checklist 和 I3-F 连续门禁后，审批小流量 fallback=false canary。
3. 稳定观察达到门槛后再单独审批 Iteration 6；不在本批删除兼容表、列或写路径。
