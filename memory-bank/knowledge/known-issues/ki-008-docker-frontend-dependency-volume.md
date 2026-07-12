---
type: paradigma-known-issue
title: "KI-008: Docker 前端依赖命名卷可能滞后于 lockfile"
description: "开发 Compose 的 node_modules 命名卷会遮蔽镜像依赖，旧卷可能缺少新包。"
tags: ["known-issue", "docker", "compose", "frontend", "node-modules"]
timestamp: "2026-07-13T00:19:00+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["Vite import-analysis", "Docker 缺少依赖", "node_modules 命名卷"]
    en: ["Vite import analysis", "stale node_modules volume", "Docker missing dependency"]
---

# KI-008: Docker 前端依赖命名卷可能滞后于 lockfile

## 现象

宿主源码与 lockfile 已包含新依赖，但开发 Compose 中 Vite 报 `Failed to resolve import`；容器内 `npm ls <package> --depth=0` 为空。

## 原因

开发栈将源码 bind mount 到 `/app`，同时将 `frontend-node-modules` 命名卷挂载到 `/app/node_modules`。命名卷会遮蔽镜像内的依赖，而且已有卷不会因镜像重建自动复制新增包。

## 当前处理

`frontend/Dockerfile` 安装 `filum-frontend-dev` 入口脚本。脚本比较当前 `package-lock.json` 与依赖卷中的哈希标记，仅在变化时执行 `npm ci`，然后启动 Vite。

正常修复命令：

```powershell
docker compose -f infra/docker/docker-compose.yml up -d --build frontend
```

无需为了单个前端依赖删除包含其他服务数据的全部 Compose volumes。
