---
type: paradigma-known-issue
title: "KI-007: Windows 保留端口导致 Playwright webServer EACCES"
description: "Windows excluded port range 可能覆盖默认 4173，导致 Vite 无法监听。"
tags: ["known-issue", "windows", "playwright", "vite", "port"]
timestamp: "2026-07-10T23:06:39+08:00"
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: ["Playwright EACCES", "4173 端口", "Windows 保留端口"]
    en: ["Playwright EACCES", "excluded port range"]
---

# KI-007: Windows 保留端口导致 Playwright webServer EACCES

## 现象

`npm run test:e2e` 启动 Vite 时返回 `listen EACCES: permission denied 127.0.0.1:4173`，即使进程权限足够也无法监听。

## 确认方式

```powershell
netsh interface ipv4 show excludedportrange protocol=tcp
```

若 `4173` 落在 excluded range（本次为 `4145–4244`），属于 Windows/Hyper-V 端口保留，不是应用权限或 Playwright 用例失败。

## 处理

当前 Playwright 配置支持环境变量覆盖端口：

```powershell
$env:PLAYWRIGHT_DEV_PORT='5300'
npm.cmd run test:e2e
```

选择未被保留且未占用的端口即可。本次改用 `5300` 后 default mock **35/35 PASS**。
