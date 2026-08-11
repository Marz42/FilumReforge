---
type: paradigma-known-issue
title: "KI-003: 测试基线漂移"
description: "pytest skip、工作区 mass deletion、Playwright 等测试环境状态。"
tags: ["known-issue", "testing", "baseline", "playwright"]
timestamp: "2026-08-11T23:27:48+08:00"
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
| Playwright core mock | **35/35** @ 2026-08-09 RC1 | `npm run test:e2e`；目标环境/当前主线仍需按发布批次刷新 |
| Playwright multi-account mock | **15/15** @ 2026-06-22 | `npm run test:e2e:workflow-video-multi-account-mock`（A–N） |
| Playwright UAT | **待重跑** | `test:e2e:workflow-video-uat` |
| Playwright live | 未纳入每次基线 | 多账号见 `manuals/workflow-video-v1-multi-account-e2e-guide.md` |
| backend full | **460 collected / 428 passed / 32 skipped / 0 failed** @ 2026-08-09 | skip 为 PostgreSQL/Redis 等登记环境条件；目标环境严格模式仍须重跑 |
| httpx deprecation | **cleared** @ 2026-08-09 RC1 | logout cookie 回归已改用客户端 cookie jar |
| frontend RC2 tag | **64 files / 181 tests PASS** @ 2026-08-11 | type-check / production build PASS |
| frontend current main | **69 files / 197 tests PASS** @ 2026-08-11 | F-05 动作协调后 type-check、production build PASS |
| frontend lint | **ESLint + Oxlint 0 errors** @ 2026-08-11 main | RC1 快照遗留的测试/E2E Oxlint 项已在后续主线清理；RC2 改动文件单独为 0 |
| Ubuntu 最小回滚 | **暂缓** | 原 P0，用户决定上线前再练 |

**本地单元基线 ID**: `2026-08-11-f05-task-detail-action-coordination`；浏览器 E2E 最近完整基线为 `2026-08-09-v0.93.0-rc.1-release-candidate`，RC2/当前主线仍待目标环境刷新。
