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

## 当前已知边界

- `TaskTemplatesView.vue` 已支持结构化步骤设计、JSON 导入与实例快照；已有实例的模板当前锁定结构编辑，建议通过新建模板版本承接结构变更
- 模板 / 调度管理动作、更多设计器校验与更大范围回归仍在继续补齐
- 当前 Dockerfile 与 Compose 运行的是 Vite dev server；正式部署应构建静态 `dist/` 并由 Nginx 提供

## 开发命令

```sh
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## 生产部署提醒

- 当前前端上线建议执行 `npm install && npm run build`，再由 Nginx 直接托管 `dist/`
- [../Dockerfile](../Dockerfile) 与 [../infra/docker/docker-compose.yml](../infra/docker/docker-compose.yml) 仍以开发联调为主，不建议把 Vite dev server 直接暴露到公网
- 详细云部署方式请以仓库根目录 [README.md](README.md) 的“云服务器部署”章节为准

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
