---
type: paradigma-contract
title: "Project Filum — 仓库契约"
description: "仓库级契约边界：目录协议、子项目分工、Git 工作流与 CI/CD 规范。"
tags: ["contract", "repository", "ci-cd"]
timestamp: "2026-07-08T17:34:00+08:00"
paradigma:
  schema_version: "0.1"
  temperature: hot
  lifecycle: evolving
  update_policy: requires-human-confirmation
  epistemic_status: confirmed
  contract_kind: repository
  retrieval_hints:
    zh: ["仓库契约", "目录协议", "子项目", "CI/CD"]
    en: ["repository contract", "directory protocol"]
---

# Scope

FilumReforge 为模块化单体仓库。本契约定义顶层目录协议、子项目分工边界与 Git/CI 工作流。

# Contract

| 目录 | 用途 | 维护者 |
|------|------|--------|
| `backend/` | FastAPI 后端 | 后端开发 |
| `frontend/` | Vue 3 前端 | 前端开发 |
| `infra/docker/` | Docker Compose 部署 | DevOps |
| `scripts/` | 发布/检查脚本 | DevOps |
| `memory-bank/` | Paradigma 外部记忆 | Agent + 开发者 |

详见 `backend/README.md`、`frontend/README.md`、`infra/docker/README.md`。

# Breaking Change Policy

- 数据库 schema 变更：需 Alembic 迁移 + 更新 `data-contracts.md`
- API 破坏性变更：MAJOR 版本升级 + 更新 `data-contracts.md`
- 目录协议变更：更新本文件 + `architecture.md`
