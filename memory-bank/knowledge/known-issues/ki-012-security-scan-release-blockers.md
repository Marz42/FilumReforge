---
type: paradigma-known-issue
title: "KI-012: 2026-08-09 安全扫描发现与上线阻断项"
description: "记录 Security Issue(temp) 六项发现的当前代码复核、处置状态、验证和残余风险。"
tags: [known-issue, security, release, authorization, rate-limit, attachment]
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
    zh: [安全扫描, 上线阻断, IDOR, 可信代理, OOXML]
    en: [security scan, release blocker, IDOR, trusted proxy, OOXML]
---

# Context

用户提供的 `Security Issue(temp)` 是对提交 `d4a1d9d` 的全仓库静态扫描；报告未执行项目测试。扫描共报告 6 项：3 Medium、3 Low。处置以 2026-08-09 当前工作树复核为准，原始临时扫描目录不提交到仓库。

# Findings

| ID | 严重度 | 问题 | 当前代码复核 | 上线判定 |
|----|--------|------|--------------|----------|
| SEC-01 | Medium / high confidence | 登录限流直接信任客户端 `X-Forwarded-For`，生产 Uvicorn 信任任意代理 | **fixed**：应用只读可信 `request.client`；Nginx 覆盖 forwarding header；host/Compose 仅信任明确代理 IP | cleared locally |
| SEC-02 | Medium / medium confidence | 部门池成员选项读取任意 `instance_id`，未调用实例对象级读策略 | **fixed**：template 与可选 instance 均先走对象读策略 | cleared locally |
| SEC-03 | Medium / high confidence | 部门范围模板管理员可按 ID 修改范围外模板 | **fixed**：所有 template ID 写入口与 scope 赋值统一对象级 manage/assign policy | cleared locally |
| SEC-04 | Low / medium confidence | smart-notice 可查询任意用户之间的汇报链 UUID | **fixed**：限制为目标本人、目标的有效汇报/部门管理者或全局管理角色；仅把 payload initiator 写成自己不足以放行 | cleared locally |
| SEC-05 | Low / medium confidence | DOCX/XLSX 在浏览器完整解析后才截断展示，缺少压缩包展开/条目预算 | **fixed**：入库前执行 OOXML 条目、展开大小、单条目、压缩比、路径与加密检查 | cleared locally |
| SEC-06 | Low / medium confidence | 模板列表/详情未统一执行 availability scope 读取策略 | **fixed**：list/detail/preview/pool 共享读取 predicate；空 departments 不可见 | cleared locally |

# Required Remediation

- SEC-01：Nginx 覆盖客户端 forwarded chain；应用限流只读取 Uvicorn 经可信代理处理后的 `request.client.host`；host 部署默认仅信任 loopback，Compose 仅在后端不暴露且 gateway 覆盖头的条件下信任内部来源。
- SEC-02：带 `instance_id` 的成员选项先调用 `WorkflowAccessPolicy.ensure_can_read_instance`，未授权统一 404。
- SEC-03：所有按 template ID 的设计、校验、导入、导出、状态和删除入口统一走对象级 manage policy；新建/导入 scope 也不得越出部门管理范围。
- SEC-04：仅目标本人、全局管理角色、目标部门有效管理者或目标的有效汇报上级可计算 smart-notice 候选；未来若普通发起人需要此能力，必须绑定可验证的任务/Run 上下文，不能只信任 payload UUID。
- SEC-05：上传时检查 OOXML 条目数、总展开字节数、单条目字节数和异常压缩比；超限拒绝上传，避免文件进入前端解析器。
- SEC-06：共享模板 read predicate 同时覆盖 list/detail；ACTIVE global 对所有活跃用户可读，departments 仅对所属/有效管理部门可读，DRAFT/ARCHIVED 只对可管理者可读。

# Release Exit

- 6 项已有直接回归或静态配置测试，3 个 Medium 均已 fixed。
- RC2 保持同一安全修复集合且没有放宽模板对象级授权。2026-08-23 当前主线 Backend **499 collected / 0 failed**，另有 PostgreSQL marker 22/22；Frontend **75 files / 217 tests**、type-check、build、core mock 35/35、多账号 mock 15/15 通过；development/production Compose config 通过。
- 目标环境仍需验证真实反向代理来源、TLS、secret、备份恢复、I3-F 与 UAT；本地全绿不能替代这些证据。

# Residual Risk

- 认证限流仍为每个 Uvicorn worker 的内存窗口；当前解决的是可伪造来源绕过，若未来提高 worker 数量或遭遇高强度攻击，应迁移为 Redis 共享限流。
- OOXML 预算限制最坏解析规模，但不替代客户端性能优化或恶意文档沙箱。
- 目标环境代理/CDN 必须使用明确可信 CIDR；不得把公网可达后端配置为 `FORWARDED_ALLOW_IPS=*`。

# Status

**fixed locally · production verification pending**（2026-08-11，最新试用候选 `v0.93.0-rc.2`）。安全代码阻断已清除；TLS/secret/备份恢复/I4 UAT/I3-F 等上线门禁仍开放。
