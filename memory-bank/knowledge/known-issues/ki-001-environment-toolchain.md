---
type: paradigma-known-issue
title: "KI-001: 环境与工具链问题"
description: "Windows 开发环境下跨平台工具链兼容性问题。"
tags: ["known-issue", "environment", "toolchain", "windows"]
timestamp: "2026-07-08T17:34:00+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["环境问题", "工具链", "Windows", "CRLF"]
en: ["environment", "toolchain", "windows"]
---

# KI-001: 环境与工具链问题

## Windows 下 `check-release.sh` 失败

**现象**: Git Bash/WSL 直跑 `scripts/check-release.sh` 因 `node_modules` 跨平台绑定或 PATH 无 `python` 失败。  
**处理**: 在 **Linux 原生目录**（Ubuntu 主机或 WSL 内完整 `npm ci`）执行；Windows 可跑等价 P0：`pytest`、`compileall`、前端 `test:unit`/`type-check`/`build`。

## `backend/scripts/*.sh` CRLF

**现象**: 容器内 `/bin/sh\r` 启动失败。  
**处理**: 保持 LF；仓库 `.gitattributes` 已约束 `*.sh text eol=lf`。

## 前端 `npm run lint` 副作用

**现象**: `--fix` 污染 diff。  
**处理**: 只读校验用 `npm exec oxlint .` 与 `npm exec eslint .`。

## Windows 沙箱无法访问系统 pytest Temp

**现象**: 沙箱运行 pytest 时，`tmp_path` 可能落到交互用户的 `%LOCALAPPDATA%\Temp\pytest-of-*`，因 Windows ACL 返回 `PermissionError: [WinError 5]`；pytest 自身创建的临时子目录会关闭 ACL 继承，Git 扫描未忽略目录时也可能提示拒绝访问。
**处理**: `backend/tests/conftest.py` 将 Python `tempfile` 根目录固定到仓库内 `backend/.test-tmp/`；根 `.gitignore` 忽略该目录。后续使用普通 pytest 命令即可，不再逐次传 `--basetemp`。该目录只保存测试临时产物，不应提交。

## Web Push 公钥来源

**现象**: 仅配置 `VITE_WEB_PUSH_PUBLIC_KEY` 与线上一致性漂移。  
**处理**: 以 `GET /api/v1/push-subscriptions/config` 为准；env 仅 fallback。
