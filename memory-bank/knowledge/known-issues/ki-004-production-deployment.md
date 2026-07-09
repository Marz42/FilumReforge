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
- README 若写「缺 production compose」与 `docker-compose.prod.yml` 冲突 → **文档漂移**，以实际文件为准
- 在线 Ubuntu 演练已记录（Stage 2 Phase 6）；**最小回滚路径**暂缓至上线前