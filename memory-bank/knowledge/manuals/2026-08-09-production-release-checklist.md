---
type: paradigma-manual
title: "2026-08-09 生产上线准入 Checklist"
description: "把本地工程就绪、预发验收与生产变更窗口分开的可勾选上线清单。"
tags: [manual, release, production, checklist, security, readiness]
timestamp: 2026-08-09T23:01:59+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [生产上线, 发布准入, 安全检查, 回滚清单]
    en: [production release, readiness checklist, security gate, rollback]
  relations:
    depends_on:
      - ../plans/2026-08-09-rc-employee-trial-plan.md
      - ../known-issues/ki-012-security-scan-release-blockers.md
      - ../plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md
      - 2026-08-09-iteration4-domain-neutral-designer-uat-checklist.md
      - deployment-runbook-ubuntu-2404.md
---

# 2026-08-09 生产上线准入 Checklist

> 当前结论：**本地工程候选已就绪，生产准入尚未批准**。只有 A–D 全部完成并记录负责人、时间和证据后，才允许执行 E。

> 员工试用例外：可将固定的 `v0.93.0-rc.1` 部署到数据隔离的 RC 环境收集反馈；这不执行生产 E，也不把 B–D 自动标记为完成。分流与热修规则见 [`RC 员工试用方案`](../plans/2026-08-09-rc-employee-trial-plan.md)。

## A. 固定发布候选

| ID | 检查 | 结果 |
|----|------|------|
| A-01 | 审阅当前 diff，确认不包含 `Security Issue(temp)` 原始扫描材料或真实 secret | [x] |
| A-02 | 创建单一 release commit/tag，记录 commit SHA | [x] |
| A-03 | Backend 460 collected、0 failed；Frontend 64 files/180 tests、type-check、build 通过 | [x] |
| A-04 | `compileall`、Compose `config -q`、Alembic 单 head `20260730_01`、Paradigma 5/5、`git diff --check` 通过 | [x] |
| A-05 | 记录剩余非阻断项：32 个目标环境 skip 与 809 KB Element Plus 主包；httpx deprecation、ESLint 21 errors 已在 RC 清理 | [x] |

## B. 预发环境

| ID | 检查 | 结果 |
|----|------|------|
| B-01 | 使用 A-02 的同一 SHA 部署；Linux 原生执行 `bash scripts/check-release.sh` | [ ] |
| B-02 | 生产形态 PostgreSQL/Redis 用例在严格模式运行，不允许登记用例静默 skip | [ ] |
| B-03 | `alembic current/heads/check` 一致，升级前后抽样核对关键表与 Run | [ ] |
| B-04 | 真实反向代理只信任明确 peer；外部伪造 XFF 不改变认证限流 identity | [ ] |
| B-05 | I4 / 设计器 Phase 2 UAT checklist 全部必过项完成 | [ ] |
| B-06 | 在“任务模板 → 数据检查”执行 scope/依赖盘点：intentional global 已由业务负责人确认，空 departments、缺失/停用部门、旧 `child_template_code`、父子范围不兼容均通过草稿或新版本处理；复查 `error=0` | [ ] |

## C. I3-F 硬门禁

| ID | 检查 | 结果 |
|----|------|------|
| C-01 | 目标环境 Expand → Link dry-run/apply → Contract 顺序完成 | [ ] |
| C-02 | 连续 7 天 reconciliation 100%、runtime fallback 新增 0、open P0/P1 incident 0 | [ ] |
| C-03 | 最终 31/31 报告为 PASS，0 PARTIAL、0 FAIL | [ ] |
| C-04 | 用户批准 I3-F 报告；兼容层收缩/生产切流才可解除 blocked | [ ] |

## D. 生产变更窗口

| ID | 检查 | 结果 |
|----|------|------|
| D-01 | JWT、数据库、Redis、VAPID/AI（如启用）使用生产 secret；仓库与日志无泄漏 | [ ] |
| D-02 | TLS 证书、续期、CORS origin、refresh cookie Secure/SameSite、域名验证通过 | [ ] |
| D-03 | 数据库与附件存储完成备份，并实际验证可恢复；记录 RPO/RTO 与负责人 | [ ] |
| D-04 | 回滚目标 SHA、数据库回滚边界、停止写入条件、通知渠道与维护窗口已确认 | [ ] |
| D-05 | 生产 `.env` 配置 `FORWARDED_ALLOW_IPS` 为明确代理 IP/CIDR，公网后端不使用 `*` | [ ] |

## E. 部署与观察

| ID | 检查 | 结果 |
|----|------|------|
| E-01 | 按 deployment runbook 发布同一 SHA，执行迁移并启动 backend/worker/frontend/gateway | [ ] |
| E-02 | healthz、登录/刷新/登出、任务发起/提交/集合确认/独立验收、消息已读、附件预览冒烟通过 | [ ] |
| E-03 | 观察认证 429、HTTP 4xx/5xx、worker retry/outbox、数据库连接与存储错误 | [ ] |
| E-04 | 达到观察窗口且无回滚触发条件后，由发布负责人签字关闭 | [ ] |

## 当前阻断

- A 已完成；员工试用环境只允许部署固定标签，不得部署未命名的分支头。
- B、C、D 均依赖真实预发/生产环境与人工确认，本地不能代签。
- 在 C-04 前可以进行向下兼容预发/UAT，但不得据此宣布 I3-F 生产切流完成。
