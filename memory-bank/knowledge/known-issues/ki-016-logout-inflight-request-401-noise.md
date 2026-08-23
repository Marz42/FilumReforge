---
type: paradigma-known-issue
title: "KI-016: 登出与多账号切换存在在途请求 401 噪声"
description: "用户登出后，Task Center 等在途请求仍可能触发 refresh 和未处理 Axios 401 rejection，造成控制台噪声与潜在测试抖动。"
tags: [known-issue, frontend, auth, logout, axios, task-center]
timestamp: 2026-08-23T23:25:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [登出 401, 多账号切换, Axios 未处理拒绝, 在途请求]
    en: [logout 401, account switching, unhandled Axios rejection, in-flight request]
  relations:
    related_to:
      - ../domains/architecture/frontend-architecture.md
      - ki-003-test-baseline-drift.md
---

# KI-016: 登出与多账号切换存在在途请求 401 噪声

## 状态与优先级

**开放 / 中低优先级（P2）/ 不阻断当前 UAT。** 2026-08-23 真实后端多账号 Chromium UAT 全部通过，但连续 logout/login 时浏览器控制台重复记录 Task Center 刷新请求的未处理 401。

## 现象与证据

- `useTaskCenterWorkspace` 的 watcher 使用 `void refresh()`，刷新函数没有 catch、请求取消或会话代次检查。
- `http` 拦截器遇到 401 会尝试 refresh；登出已经清除 refresh cookie 时，原请求最终以 rejection 返回。
- `authStore.logout()` 会在 logout API 完成后清空本地会话，但不会取消旧页面已经发出的请求和 polling。
- Live UAT 控制台可见 `listTasksByIds()` / `refreshWorkspace()` 的 `AxiosError: 401`；功能断言仍为 fallback-on 8/8、strict 9/9。

## 风险

- 多账号切换和网络较慢时产生无意义错误噪声，降低真实异常的可见性。
- 未处理 Promise rejection 可能导致未来更严格的浏览器/E2E console gate 失败。
- 旧会话响应若晚于新会话返回，缺少代次保护的组件存在短暂覆盖新状态的可能。

## 当前缓解

- UAT 在 logout 完成后再进入下一账号，业务授权断言以服务端响应为准。
- 401 不改变当前后端授权边界；退出后的旧请求不能读取数据。

## 完成标准

1. 为会话建立 request epoch 或统一 AbortController，logout 时取消旧会话请求和 polling。
2. Composable 将预期的 cancel/logout 401 作为静默终止，但继续上报真实的登录态 401。
3. 增加慢响应下 logout→login 的单元测试和 Playwright console gate，确保旧响应不能覆盖新账号状态。
