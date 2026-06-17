# Filum Frontend

当前前端基于 **Vue 3 + TypeScript + Vite + Pinia + Vue Router + Element Plus**，已完成从早期骨架到后台工作台的重构升级。当前重构 Step 1-7 已完成并通过用户验测；工作流 E 的前端首批实现也已落地，包含结构化模板设计器、实例运行态可视化与已有模板编辑。

## 当前主要界面

- 总览：看板、公告、待办事项、任务跟踪
- 任务中心：待办、跟踪、发布、模板、备忘；历史任务并入跟踪视图
- 汇报中心：待处理、我发起、历史、向上汇报、向下传达
- 消息中心：聚合快照、来源回跳、回执
- 设置：浏览器 Push 订阅、PWA 与通知权限说明
- 知识库：文档、发布、RAG 查询
- 人员工作台 / 部门管理：管理角色专用

## 当前会话模型

- access token 只保存在前端内存，不再写入 `localStorage`
- 页面初始化通过 `/api/v1/auth/refresh` + HttpOnly refresh cookie 恢复会话
- Axios 默认开启 `withCredentials`，更适合同源部署或已正确配置 CORS / cookie 的反向代理场景

## 当前已知边界

- `TaskTemplatesView.vue` 已支持结构化步骤设计、JSON 导入与实例快照；已有实例的模板当前锁定结构编辑，建议通过新建模板版本承接结构变更
- 模板 / 调度管理动作、更多设计器校验与更大范围回归仍在继续补齐
- 开发 Compose 运行的是 Vite dev server；生产部署请改用 `Dockerfile.prod`、`frontend/nginx.frontend.conf` 与 `infra/docker/docker-compose.prod.yml`，或直接构建静态 `dist/` 后交给 Nginx 托管

## 开发命令

```sh
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## 浏览器端 E2E

- 已接入 Playwright 基线，当前覆盖登录、会话恢复、任务中心标签切换，以及 graph-first 任务详情中的节点追踪面板。
- 当前 E2E 以浏览器真实交互为目标，但默认通过 `frontend/e2e/fixtures.ts` 对 `/api/v1` 请求做 mock，不依赖本地 backend / PostgreSQL / Redis 联动启动。
- 默认使用 Chromium，并由 Playwright 自动拉起 Vite dev server 到 `http://127.0.0.1:4173`。
- 另提供一套 live backend 场景：`playwright.live.config.ts` 会通过开发 Compose 在隔离端口启动 PostgreSQL / Redis / backend / worker / frontend / nginx，并在 backend 容器内执行 `python -m app.scripts.seed_sample_data`，用于验证真实 API、登录与任务创建链路。

```sh
npx playwright install chromium
npm run test:e2e
npm run test:e2e:live
```

## 生产部署提醒

- 当前前端上线可选两条路径：执行 `npm install && npm run build` 后由 Nginx 直接托管 `dist/`，或使用 `Dockerfile.prod` 配合 `infra/docker/docker-compose.prod.yml`
- `Dockerfile` 与 `infra/docker/docker-compose.yml` 仍以开发联调为主，不建议把 Vite dev server 直接暴露到公网
- 详细云部署方式请以仓库根目录 [README.md](README.md) 的“云服务器部署”章节或 `infra/docker/README.md` 为准

## 验证命令

```sh
npm run test:unit -- --run
npm run test:e2e
npm run test:e2e:live
npm run type-check
npm run build
npm run lint
```

## 当前关键目录

- `src/router/`：路由与兼容重定向
- `src/stores/`：Pinia store（认证、全局项目状态）
- `src/api/`：Axios API client
- `src/views/`：总览、任务中心、汇报中心、消息中心、知识库、人员工作台
- `src/components/`：壳层、命令栏、Push 订阅卡片等
- `tests/`：前端单元测试

更多模块边界与当前状态见 [`README.md`](../README.md)、[`memory-bank/project-brief.md`](../memory-bank/project-brief.md)、[`memory-bank/domains/task-center.md`](../memory-bank/domains/task-center.md)。
