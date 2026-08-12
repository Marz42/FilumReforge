---
type: paradigma-progress
title: "KI-009 独立任务动作授权收口"
description: "统一 standalone 详情与后端状态命令的 available_actions 契约，保留 workflow 兼容路径。"
tags: [progress, task-center, standalone, authorization, ki-009]
timestamp: 2026-08-12T22:35:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: verified
  relations:
    depends_on:
      - ../../knowledge/known-issues/ki-009-standalone-action-dual-track.md
      - ../../knowledge/contracts/data-contracts.md
---

# KI-009 独立任务动作授权收口

## 交付

- `TaskDetailShell` 的 standalone“开始处理 / 提交交付 / 验收 / 打回”改为消费服务端 `available_actions`；空动作列表是明确的无操作权限。
- workflow/graph 详情继续走既有 handshake、Handler 与角色 fallback，不把当前常见的空 `available_actions` 误解释为禁止动作。
- `transition_task_status()` 对 standalone 按 TODO/DOING/REVIEW 映射 `start_work` / `submit_deliverable` / `approve_deliverable`，复用 `build_standalone_action_context()` 做服务端兜底。
- 创建者仍可在“任务跟踪”看到所建任务，但不能代指派员工开工；执行人提交后也不能自验收，进入 REVIEW 后由创建者/验收责任人推进。
- 现行 Admin/HR `task_admin_override` 未在本项移除，继续由 KI-011 单独治理。

## 测试先行证据

- 新增后端失败用例先复现“创建者可启动他人任务”，修复后补充“执行人不能自验收”；旧服务测试同步改为由创建者完成 REVIEW→DONE。
- 新增前端 domain 测试先复现 standalone 空动作仍被本地角色判断放行，再固定 standalone 权威动作与 workflow fallback。
- 后端全量：**496 collected / 464 passed / 32 skipped / 0 failed**；skip 为已登记的 PostgreSQL/Redis 环境条件项。
- 前端全量：**75 files / 217 tests PASS**；type-check、ESLint、Oxlint 与 production build PASS。
- `python -m compileall app tests` PASS；production build 仅保留既有 809 KB 主包体积 warning。

## 文档与边界

- 修正总体计划、图引擎计划、路线图和项目身份卡片的阶段漂移；Legacy E 不再被描述为下一产品开发线。
- 当前顺序固定为员工 RC2 复测/UAT与目标环境证据 → 5-E 单独批准 → 稳定观察 → Iteration 6 单独批准。
- KI-009 状态更新为“工程已修、待多账号人工复测”，并加入生产准入 Checklist B-08。

## 尚待外部证据

- 真实浏览器多账号复测、RC2 员工试用观察、Iteration 4/设计器/S-01 UAT。
- 目标 PostgreSQL/Redis 严格测试、Iteration 3-F 7 天/31 项、Iteration 5 rebuild/full shadow/运维样本。
- 上述外部项不阻止继续开发，但继续阻止 5-E、Iteration 6 与生产准入结论。

**Checkpoint**：`CHECKPOINT-20260812-KI009-ACTION-AUTH`
