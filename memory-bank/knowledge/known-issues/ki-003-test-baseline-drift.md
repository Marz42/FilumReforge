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
| backend full | **460 collected / 428 passed / 32 skipped / 0 failed** @ 2026-08-09 | skip 为 PostgreSQL/Redis 等登记环境条件；目标环境严格模式仍须重跑 |
| httpx deprecation | 1 warning @ 2026-08-09 | 测试对 per-request cookie 的用法将弃用；不影响当前结果，后续更新测试客户端写法 |
| frontend unit | **64 files / 180 tests PASS** @ 2026-08-09 | type-check / production build PASS |
| eslint | 21 existing errors @ 2026-08-09 | release script 定义为 warning；集中在未使用符号、prop mutation、computed side effect |
| Ubuntu 最小回滚 | **暂缓** | 原 P0，用户决定上线前再练 |

**本地单元基线 ID**: `2026-08-09-security-release-readiness`；浏览器 E2E 基线仍沿用 `2026-06-22-main-e2e-core-33`，待预发刷新。
