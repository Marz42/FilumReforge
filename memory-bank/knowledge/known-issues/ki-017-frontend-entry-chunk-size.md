---
type: paradigma-known-issue
title: "KI-017: 前端入口 Chunk 仍超过 500 KiB"
description: "W13 已将入口 index gzip 降至约 12.66 kB；剩余超大 chunk 为 element-plus / doc-preview 独立包，继续观察而非调高 warning limit。"
tags: [known-issue, frontend, vite, bundle, performance]
timestamp: 2026-09-14T15:45:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Vite chunk 过大, 前端包体积, 入口 JS, 首屏性能]
    en: [Vite chunk warning, frontend bundle size, entry JavaScript, startup performance]
  relations:
    related_to:
      - ../domains/architecture/frontend-architecture.md
      - ../manuals/2026-09-14-w13-bundle-test-hygiene.md
---

# KI-017: 前端入口 Chunk 体积

## 状态与优先级

**降级 / 监控中（P2）。** W13 `manualChunks` 后入口 `index-*.js` 已降至约 **39.75 kB / gzip 12.66 kB**（历史 809.57 / 255.70）。仍可能对 `element-plus` / `doc-preview` 报告 >500 kB chunk warning；不以调高 `chunkSizeWarningLimit` 作为修复。

## 历史证据（2026-08-23）

- `index-*.js`：809.57 kB，gzip 255.70 kB。
- `lib-*.js`：497.25 kB，gzip 125.48 kB。

## 当前证据（2026-09-14）

见 [W13 手册](../manuals/2026-09-14-w13-bundle-test-hygiene.md)。CI 可用 `npm run test:bundle-budget` 守住入口 gzip 预算。

## 剩余风险

- Element Plus 全量 vendor 仍偏大；后续可继续按路由按需注册组件。
- 文档预览库应保持动态 import，避免回流入口。

## 完成标准（更新）

- 入口 JS gzip 显著低于历史 255.70 kB 基线，并由 budget 脚本守住。
- 大库独立 chunk；不靠提高 warning limit 消音。
