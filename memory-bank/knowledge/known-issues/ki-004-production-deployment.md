---
type: paradigma-known-issue
title: "KI-004: 生产与部署注意事项"
description: "FRONTEND_APP_URL、文档漂移、最小回滚等生产部署环境问题。"
tags: ["known-issue", "production", "deployment"]
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
    zh: ["生产部署", "环境变量", "回滚"]
    en: ["production", "deployment", "rollback"]
---

# KI-004: 生产与部署注意事项

- `FRONTEND_APP_URL` 生产必填（邀请链接避免 localhost）
- host/systemd 默认 `FORWARDED_ALLOW_IPS=127.0.0.1`；Compose 通过固定私网 IP 只信任 gateway。公网可达 backend 不得信任 `*`
- Nginx 必须覆盖客户端 `X-Forwarded-For`；若前置 CDN/LB，只在 Nginx `real_ip` 配置中加入供应商明确 CIDR
- production Compose 已存在且 development/production `config -q` 于 2026-08-23 当前主线通过；使用可配置的 `FILUM_DOCKER_SUBNET` / `NGINX_INTERNAL_IP`
- 2026-08-23 已在隔离 PostgreSQL 16 完成 `pg_dump -Fc` 恢复、82 Task/24 Run/82 Projection/234 Timeline 计数核对，以及 `20260812_04→03→04` 往返；真实生产仍须记录数据库与附件备份、RPO/RTO、负责人和维护窗口
- 5-E 新增 `TASK_CENTER_PROJECTION_READS_ENABLED` 与 `TASK_CENTER_PROJECTION_FALLBACK_ENABLED`；生产默认 fallback=true，严格 canary 后才允许关闭
- TLS 证书、真实 secret、域名/CORS/refresh cookie 与可信代理必须在目标环境验证，本地不得代签
