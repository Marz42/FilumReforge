# Filum Frontend

当前前端基于 **Vue 3 + TypeScript + Vite + Pinia + Vue Router + Element Plus**，已完成从早期骨架到后台工作台的重构升级。

## 当前主要界面

- 总览：看板、公告、待办事项、任务跟踪
- 任务中心：模板、发布、待办、跟踪、历史、备忘
- 汇报中心：待处理、我发起、历史、向上汇报、向下传达
- 消息中心：聚合快照、来源回跳、回执、Push 订阅
- 知识库：文档、发布、RAG 查询
- 人员工作台 / 部门管理：管理角色专用

## 开发命令

```sh
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## 验证命令

```sh
npm run test:unit -- --run
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

更多模块边界与当前状态，请以仓库根目录 `README.md` 和 `memory-bank/design-document.md` 为准。
