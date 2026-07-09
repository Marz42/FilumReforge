---
type: paradigma-known-issue
title: "KI-003: 测试基线漂移"
description: "pytest skip、工作区 mass deletion、Playwright 等测试环境状态。"
tags: ["known-issue", "testing", "baseline", "playwright"]
timestamp: "2026-07-08T17:34:00+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["测试基线", "pytest", "Playwright", "E2E"]
en: ["test baseline", "pytest", "playwright"]
---

# KI-003: 测试基线漂移

| 项 | 状态 | 说明 |
|----|------|------|
| pytest migration skip | 1 skipped @ `98ad370` | `test_migrations.py` 需 PostgreSQL；凭据错误时 skip，非失败 |
| 工作区 mass deletion | 2026-06-18 已恢复 | 409 文件 `D` → `git restore .`；跑测试前务必 `git status` |
| docker-gui 18/18 | 沿用 2026-05-20 基线 | 本机未重跑时需 Compose 栈 |
| Playwright core mock | **33/33** @ 2026-06-22 | `npm run test:e2e`；含 `task-center-interactions` + designer |
| Playwright multi-account mock | **15/15** @ 2026-06-22 | `npm run test:e2e:workflow-video-multi-account-mock`（A–N） |
| Playwright UAT | **待重跑** | `test:e2e:workflow-video-uat` |
| Playwright live | 未纳入每次基线 | 多账号见 `manuals/workflow-video-v1-multi-account-e2e-guide.md` |
| eslint | 8 errors | 非 release 阻塞，待清理未使用变量 |
| Ubuntu 最小回滚 | **暂缓** | 原 P0，用户决定上线前再练 |

**基线 ID**: `2026-06-22-main-e2e-core-33`