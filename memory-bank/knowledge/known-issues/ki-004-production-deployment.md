---
type: paradigma-known-issue
title: "KI-004: 生产与部署注意事项"
description: "FRONTEND_APP_URL、文档漂移、最小回滚等生产部署环境问题。"
tags: ["known-issue", "production", "deployment"]
timestamp: "2026-07-08T17:34:00+08:00"
paradigma:
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
- production Compose 已存在且 `config -q` 于 2026-08-09 通过；使用可配置的 `FILUM_DOCKER_SUBNET` / `NGINX_INTERNAL_IP`
- 在线 Ubuntu 演练有历史记录；本轮发布仍需按生产上线 checklist 重新验证备份恢复与回滚
