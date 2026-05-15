---
description: "Use when editing Vue components, Pinia stores, Vue Router config, Axios API wrappers, Vite config, or frontend tests under frontend/."
name: "Filum Frontend"
applyTo:
  - "frontend/**/*.ts"
  - "frontend/**/*.vue"
  - "frontend/package.json"
---

# Filum Frontend

- 先读 [memory-bank/architecture.md](../../memory-bank/architecture.md) 和 [memory-bank/design-document.md](../../memory-bank/design-document.md)；需要确认当前界面主线或工作流 E 边界时，再看 [memory-bank/progress.md](../../memory-bank/progress.md) 与 [memory-bank/plans/implementation-plan.md](../../memory-bank/plans/implementation-plan.md)。
- 当前信息架构以 [frontend/src/components/AppShell.vue](../../frontend/src/components/AppShell.vue) 和 [frontend/src/router/index.ts](../../frontend/src/router/index.ts) 为准；修改导航、入口或模块分组时，保留既有“通用模块 / 特殊模块”和兼容重定向事实。
- 所有 HTTP 请求统一走 [frontend/src/api](../../frontend/src/api) 的 Axios 封装；不要在 view 或组件里直接散落请求实现。
- 共享状态优先进入 Pinia store；页面局部交互状态留在视图或组合式逻辑中，不要把一次性 UI 状态提升成全局单例。
- `views/` 是工作台页面入口，`components/` 放可复用壳层和通用组件；保持这个分层，不把大型页面逻辑无序下沉到通用组件。
- 模板、消息、人员工作台等聚合页面尽量复用现有路由、类型和 API 结构，不要绕开后端聚合接口重新拼装一套前端事实。
- 浏览器 Push 公钥以 `GET /api/v1/push-subscriptions/config` 为标准来源；`VITE_WEB_PUSH_PUBLIC_KEY` 只是 fallback，不要把它当唯一事实源。
- 验证命令优先按 [frontend/README.md](../../frontend/README.md) 执行；只读校验优先 `npm exec oxlint .` 和 `npm exec eslint .`，避免 `npm run lint` 的 `--fix` 副作用污染 diff。
