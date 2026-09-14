---
type: paradigma-manual
title: "W13 前端包体拆分与测试卫生"
description: "记录入口 gzip 基线对比、manualChunks 拆分、bundle budget 脚本与 mountApp 测试辅助。"
tags: [w13, frontend, bundle, vitest, ki-017]
timestamp: 2026-09-14T15:45:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [W13, 包体, manualChunks, mountApp]
    en: [W13, bundle budget, manualChunks, mountApp]
  relations:
    related_to:
      - ../plans/2026-09-10-integrated-development-and-human-gates-plan.md
      - ../known-issues/ki-017-frontend-entry-chunk-size.md
---

# W13

## 测量（2026-09-14，`vite build`）

历史基线（KI-017）：entry **809.57 kB / gzip 255.70 kB**。

本轮拆分后（节选）：

| chunk | raw kB | gzip kB |
|---|---:|---:|
| `index-*.js` | 39.75 | **12.66** |
| `vue-vendor-*.js` | 30.77 | 12.06 |
| `vendor-*.js` | 128.92 | 45.97 |
| `element-plus-*.js` | 954.01 | 306.74 |
| `doc-preview-*.js` | 519.81 | 130.96 |
| `TaskCenterView-*.js` | 150.36 | 40.57 |

入口 gzip 相对 255.70 kB 下降约 **95%**（远超 −20% 建议目标）。Element Plus / 文档预览已拆出独立 chunk；仍可能触发 Vite >500kB 警告（element-plus / doc-preview），不以调高 `chunkSizeWarningLimit` 消音。

## 工程

- [`vite.config.ts`](../../../frontend/vite.config.ts)：`manualChunks` → `vue-vendor` / `element-plus` / `doc-preview` / `vendor`
- [`scripts/check-bundle-budget.mjs`](../../../frontend/scripts/check-bundle-budget.mjs)：`npm run test:bundle-budget`（默认入口 gzip 预算 220 kB）
- [`tests/helpers/mountApp.ts`](../../../frontend/tests/helpers/mountApp.ts)：统一 Pinia/router/Element Plus mount

## 验证

```powershell
cd frontend
npm run build-only
npm run test:bundle-budget
npm run test:unit -- --run tests/mountApp.spec.ts
```
