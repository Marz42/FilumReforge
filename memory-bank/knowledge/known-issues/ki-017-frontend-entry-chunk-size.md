---
type: paradigma-known-issue
title: "KI-017: 前端入口 Chunk 仍超过 500 KiB"
description: "生产构建成功，但 Vite 持续报告入口 JavaScript chunk 超过 500 KiB，仍有首屏传输、解析和缓存失效成本。"
tags: [known-issue, frontend, vite, bundle, performance]
timestamp: 2026-08-23T23:25:00+08:00
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
---

# KI-017: 前端入口 Chunk 仍超过 500 KiB

## 状态与优先级

**开放 / 低优先级（P2）/ 非功能阻断。** 当前生产构建正常完成，既有路由和文档解析器也已按需加载；本项关注剩余性能债，而不是通过调高 warning limit 消除提示。

## 现象与证据

2026-08-23 执行 `vite build frontend`：

- `index-*.js`：809.57 kB，gzip 255.70 kB。
- `lib-*.js`：497.25 kB，gzip 125.48 kB。
- Vite 报告至少一个 minified chunk 超过 500 kB。

## 风险

- 低带宽或低性能终端的下载、解析和执行时间仍偏高。
- 入口 chunk 改动会扩大缓存失效范围。
- 后续继续向共享入口引入 UI、编辑器或文档依赖时，包体可能再次快速增长。

## 建议方向

1. 先用 bundle visualizer 确认 `index` 中的 Element Plus、通用详情组件和共享依赖占比。
2. 按路由/能力边界继续拆分重型组件，必要时配置 Rolldown code splitting/manual chunks。
3. 建立 gzip/brotli 预算和 CI 趋势记录；warning limit 只用于表达已经评审过的预算，不作为修复手段。

## 完成标准

- 默认生产构建无 chunk-size warning，或存在带测量依据和负责人批准的显式预算。
- 首屏关键路径和常用 Task Center 路径没有因拆包增加请求瀑布或功能回归。
