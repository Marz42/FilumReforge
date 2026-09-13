---
type: paradigma-plan
title: "安全问题处置与上线准备计划"
description: "校准项目文档，复核并修复安全扫描发现，建立可执行的上线门禁与残余风险记录。"
tags: [plan, security, release, authorization, hardening]
timestamp: 2026-09-13T00:20:00+08:00
paradigma:
  relations:
    related_to:
      - implementation-plan.md
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  plan_status: completed
  retrieval_hints:
    zh: [安全问题, 上线准备, 发布门禁, 对象授权]
    en: [security findings, release readiness, authorization, hardening]
---

# Goal

> **计划状态：COMPLETED（本地工程）** — 安全修复和本地门禁已完成；目标环境 TLS、secret、备份恢复、迁移和生产批准继续由上线清单跟踪。

让当前主分支达到“可进入目标环境预发与生产准入验证”的状态：现行文档与代码一致，扫描发现均有当前代码复核、修复或明确风险接受，自动化门禁可重复执行，无法由本地证明的目标环境事项保持显式阻断。

# Scope

- 修正主计划、路线图、测试基线和 Paradigma 日志协议漂移。
- 复核 `Security Issue(temp)` 针对 `d4a1d9d` 的 6 项发现。
- 修复认证限流可信代理、工作流对象授权与 OOXML 预览资源边界。
- 更新安全基线、部署手册和上线检查清单。
- 执行 backend/frontend/Memory-Bank/Alembic/release script 门禁。
- 不直接连接或部署生产环境；不把本地测试替代 I3-F 七天观测、真实备份恢复或人工 UAT。

# Approach

1. 以当前代码与可执行测试而非扫描报告文字作为行为事实。
2. 对对象访问统一复用服务端策略，未授权读取使用 404 隐藏对象存在性。
3. 可信代理链在入口覆盖伪造头，并让应用只消费 Uvicorn 校验后的 client identity。
4. 对压缩文档在进入浏览器解析器前施加压缩包条目数、展开字节数和单条目预算。
5. 自动化全绿只代表“本地可发布”；生产准入继续要求目标环境证据。

# Tasks

- [x] D1：校准 implementation-plan、roadmap、data-contracts 与 progress 引用。
- [x] S1：归档 6 项安全发现的严重度、证据、当前状态、修复与验证。
- [x] S2：修复认证限流 X-Forwarded-For 信任链。
- [x] S3：修复实例成员选项、模板写、模板读与 reporting-chain 对象授权。
- [x] S4：补 OOXML 解压/解析资源预算。
- [x] R1：执行 backend/frontend 全量、type-check/build、compileall、Compose config、Alembic head 与 Paradigma 检查；ESLint 21 项既有 warning 单列。
- [x] R2：执行 Windows 等价 release P0 并记录结果；Linux 原生 `check-release.sh` 与目标环境检查保留到预发/服务器。
- [x] R3：更新部署手册、上线 checklist、active-task、session log 与项目状态。

# Exit Criteria

- 6 项安全发现全部为 fixed/partially-fixed/risk-accepted，并有测试或明确证据。
- Medium 发现不得以未处置状态进入预发。
- Backend/frontend/Memory-Bank 门禁通过，Alembic 保持单 head。
- 生产配置不信任任意来源的 forwarded headers。
- 上线清单明确列出迁移、secret、TLS、备份/恢复、UAT、I3-F 31/31 与七天观测。

# Status


Machine status: completed.
**engineering complete · external gates pending** — 本地安全修复和自动化门禁完成；生产部署仍须完成上线 checklist 中的目标环境证据。
