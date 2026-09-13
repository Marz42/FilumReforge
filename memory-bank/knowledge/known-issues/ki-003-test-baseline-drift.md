---
type: paradigma-known-issue
title: "KI-003: 测试基线漂移"
description: "pytest skip、工作区 mass deletion、Playwright 等测试环境状态。"
tags: ["known-issue", "testing", "baseline", "playwright"]
timestamp: 2026-09-13T00:20:00+08:00
paradigma:
  relations:
    related_to:
      - known-issues.md
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
| Playwright core mock | **35/35** @ 2026-08-23 P0 closure | 当前主线刷新通过 |
| Playwright multi-account mock | **15/15** @ 2026-08-23 P0 closure | A–N 当前主线刷新通过 |
| Playwright UAT | **待重跑** | `test:e2e:workflow-video-uat` |
| Playwright live | **8/8 fallback on + 9/9 strict projection** @ 2026-08-23 | 真实 PostgreSQL/Redis、真实后端、四类业务账号；strict 额外覆盖 KI-009 三身份授权 |
| backend current main | **499 collected / 0 failed** @ 2026-08-23 | 全量默认套件；另有 PostgreSQL marker 22/22 严格通过 |
| httpx deprecation | **cleared** @ 2026-08-09 RC1 | logout cookie 回归已改用客户端 cookie jar |
| frontend RC2 tag | **64 files / 181 tests PASS** @ 2026-08-11 | type-check / production build PASS |
| frontend current main | **75 files / 217 tests PASS** @ 2026-08-12 | Iteration 5-D + KI-009 动作契约后 type-check、production build PASS |
| frontend lint | **ESLint + Oxlint 0 errors** @ 2026-08-12 main | RC1 快照遗留的测试/E2E Oxlint 项已在后续主线清理；RC2 改动文件单独为 0 |
| Ubuntu 最小回滚 | **暂缓** | 原 P0，用户决定上线前再练 |

**本地基线 ID**: `2026-08-23-p0-closure-iteration5e`；单元、mock 与隔离 production-dialect live 已刷新。真实业务人员签字与生产观察仍独立待办。

**Iteration 5-A～E 数据库门禁**：隔离 PostgreSQL 单 head `20260812_04`、22 项 marker、最终 rebuild 97/28/282、full shadow 407/407、备份恢复与 `04→03→04` 均通过；严格 5-E UAT 9/9。目标环境仍须积累持续样本。另见 KI-014：`alembic check` 存在历史 ORM/DDL drift，不能标记为 clean。
