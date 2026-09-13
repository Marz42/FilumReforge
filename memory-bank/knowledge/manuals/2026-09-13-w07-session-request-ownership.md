---
type: paradigma-manual
title: "W07 会话与请求竞态修复"
description: "记录会话代次、请求取消、最后一次响应生效、轮询清理及多账号浏览器回归的实现与证据边界。"
tags: [w07, session, cancellation, task-center, frontend]
timestamp: 2026-09-13T16:27:10+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [会话代次, 旧响应, 退出登录, 竞态修复]
    en: [session epoch, cancellation, stale response, logout]
  relations:
    related_to:
      - ../known-issues/ki-016-logout-inflight-request-401-noise.md
      - ../plans/2026-09-10-integrated-development-and-human-gates-plan.md
      - ../domains/architecture/frontend-architecture.md
---

# W07 会话与请求竞态修复

用户要求“提交然后继续开发”。先将已验证 W01/W02 提交为 `791a3d5`，随后按整合方案推进可独立实施的 W07。此次没有推送远端、部署应用或执行目标数据库变更。

## 实现

- `api/session` 维护递增会话代次和每代 AbortController。清除会话立即使旧请求失效；正常 access-token refresh 不改变会话身份。
- JSON 请求、长时上传和需要会话归属的 raw auth 请求绑定发起代次；晚到的成功或失败都检查归属。响应结束移除 signal 监听，调用方取消与会话取消同时生效。
- refresh promise 按代次共享；旧 promise 的成功、失败和 finally 都不能覆盖或清空新代次的刷新。真实当前会话 401/403 继续触发授权失效处理；refresh 网络/服务器故障继续报错，不能一律冒充会话过期。
- 未持有内存 access token 时不再发送受保护请求，避免退出后的后台工作自动触发 refresh。启动恢复、密码登录、邀请激活、bootstrap 后续登录均有代次检查。
- 退出立即清空用户/token 并进入登录页。logout 的网络请求单独完成；下一次密码登录/邀请激活等待其响应，避免旧 logout 的 cookie 响应晚于新登录。旧 logout 回调不能清空或跳转覆盖新会话。
- `useLatestRequest` 统一请求号、调用方取消、会话失效和组件销毁。任务中心 workspace、snapshot、搜索及分页仅接受对应当前请求；权限缓存有独立请求号，不让旧 promise 恢复旧权限。
- watcher 的失败转为可见错误状态；loading/error 的写入同样受请求归属约束。筛选、禁用、退出和卸载会撤销旧工作；消息轮询在退出和卸载时停止。
- 公共 `showError` 只静默 Axios cancellation，保留真实错误、请求编号及原有 fallback 文案。相关页面采用同一入口，避免取消上传或离开页面后弹出无意义错误。

后端 HTTP API、数据库和业务权限规则未变化。取消网络等待不等于撤销服务器已经受理的写操作；实际服务端 token 撤销、cookie 行为和上传结果仍以目标环境事实为准。

## 验证

- 前端全量单元/组件回归：77 个文件、234 项通过；后续补充退出细节和同一轮事件中的恢复竞态后，相关 8 文件 46 项通过。
- 类型检查、ESLint、Oxlint 和生产构建通过。既有大入口 chunk 提示保留，性能优化仍属 W13。
- Playwright 登录、外壳、任务中心及新竞态用例共 14 项通过；进一步延迟 logout 响应后，两项竞态用例再次通过。
- 浏览器用例在不整页刷新的 logout → 新账号 login 中检查旧数据不再显示、无 error toast 和无 pageerror；同时验证登录等待旧 logout 响应，以及慢 inbox 不覆盖快 tracking。
- HTTP 单测覆盖旧成功/上传响应、跨会话 refresh、真实 401、refresh 503、调用方在刷新期间取消；缓存和轮询单测覆盖晚响应、清理与停止。

以上浏览器验证使用受控 mock API，不能替代真实后端多账号 UAT。新增 `session-races.spec.ts` 已加入默认 Playwright 集合与 CI smoke 入口，发布后需确认 hosted CI。

## 后续

W07 本地实现可审阅，后续可单独提交。KI-014 目标观察与 Phase D 仍保持原门禁；W08 通知真实状态、W09 共享限流可作为下一批本地工程方向，实际外发和生产操作仍需对应授权。
