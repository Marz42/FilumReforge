# Project Filum 技术栈与落地状态

> **【已迁移】** Paradigma Phase 2 起，技术栈摘要权威来源为 [`project-brief.md`](./project-brief.md) §技术栈。本文件保留完整选型叙述与架构图。

**版本**: v2.1.0  
**核心原则**: 模块化单体 / 类型安全 / 演进式交付 / AI 友好

## 1. 技术选型总览

| 层级 | 选型 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| Frontend Core | Vue 3 + TypeScript + Vite | 已落地 | 当前前端基线 |
| UI | Element Plus | 已落地 | 当前 B 端后台 UI 基线 |
| 状态与路由 | Pinia + Vue Router | 已落地 | 当前前端状态与权限路由 |
| HTTP Client | Axios | 已落地 | 所有前端请求统一出口 |
| Backend Core | FastAPI | 已落地 | 当前 API 框架 |
| Schema / Validation | Pydantic v2 | 已落地 | API 协议与 Tool Schema 基础 |
| ORM | SQLAlchemy 2.0 Async | 已落地 | 当前异步 ORM 基线 |
| Migrations | Alembic | 已落地 | 当前迁移体系 |
| Database | PostgreSQL 15+ + `pgvector` | 已落地 | 主业务数据库与向量检索基线 |
| JSON 扩展 | PostgreSQL JSONB | 已落地 | 档案动态字段与扩展配置 |
| Cache / Queue | Redis | 已落地 | 当前缓存与异步队列 Broker |
| Async Worker | ARQ | 已落地 | 当前 worker 选型与实现 |
| Object Storage | 本地适配器 / 未来 S3 兼容 | 已落地基线 | 当前附件通过对象存储抽象管理 |
| Realtime | WebSocket adapter | 已落地第一版 | 当前为最小 adapter，占位真实实时推送 |
| Browser Push | Web Push (`pywebpush`) | 已落地第一版 | 已有订阅、投递与业务链路接入 |
| PWA | Manifest + 原生 Service Worker | 已落地基线 | 当前未使用插件方案 |
| AI / LLM | 官方 `openai` Python SDK | 已落地第一版 | 已实现 Tool Calling 与知识库检索 |
| Deploy | Docker Compose + Nginx | 已落地 | 当前本地 / 近生产编排基线 |

## 2. 当前已落地技术能力

### 2.1 前端

- Vue 3 Composition API
- TypeScript
- Vite
- Element Plus
- Pinia
- Vue Router
- Axios
- Knowledge Base / Users / Tasks / Messages 等工作台页面
- 原生 Service Worker 与浏览器 Push 订阅

### 2.2 后端

- FastAPI
- Pydantic v2
- SQLAlchemy 2.0 Async
- Alembic
- OpenAI SDK 封装
- Notification adapter factory
- Browser Push / LLM Router / Knowledge Retrieval 服务

### 2.3 存储与中间件

- PostgreSQL
- `pgvector`
- Redis
- ARQ
- 本地文件系统对象存储适配器

### 2.4 基础编排

- Docker Compose
- Nginx
- backend / worker 启动前自动迁移

## 3. 当前尚未完全落地但已确认的技术方向

### 3.1 注册与账号开通

- 自助注册 / 邀请注册 / 审批式注册方案待定
- 目前仍以管理端创建用户为主

### 3.2 消息与通知深化

- Email / WebSocket 外部真实接入
- 消息附件
- 更完整的 delivery 观测与告警

### 3.3 工程质量强化

- 更细粒度的集成测试 / E2E
- 更清晰的前后端模块边界与状态管理

## 4. 关键技术决策

### 4.1 为什么继续坚持模块化单体

- 当前团队规模与业务复杂度不适合引入微服务治理成本
- HR、Workflow、Messaging、AI 之间共享权限、组织和附件能力，单体更容易保持一致性

### 4.2 为什么 worker 固定选 ARQ

- 当前后端本身就是 async 栈
- 已经有 Redis
- 比 Celery 更轻，更接近当前项目体量
- Phase 2 起已经实际落地 ARQ worker 与 cron job

### 4.3 为什么 AI 必须使用官方 `openai` SDK

- Tool Calling / Function Calling 能直接与 Pydantic schema 对接
- 避免 LangChain 带来的抽象层级和不可控行为
- 兼容 OpenAI 风格 API 的国产模型

### 4.4 为什么浏览器推送放在消息与知识能力之后

- 可用的浏览器推送依赖消息总线、回执模型、Push Subscription 持久化与 adapter 分发
- 当前已经完成第一版，但后续仍需继续深化真实渠道接入与前端观测体验

## 5. 当前与后续深化架构图

### 5.1 当前

```text
[ Browser ]
    |
    +--> Vue 3 + Element Plus
    |
[ Nginx / Vite Dev Server ]
    |
[ FastAPI ]
    |-- REST API
    |-- Service Layer
    |-- Workflow Engine
    |-- Message Center
    |-- LLM Router
    |
    +--> PostgreSQL / pgvector
    +--> Redis / ARQ Queue
    +--> Local Storage Adapter
    +--> Email / WebSocket / Web Push Adapters

[ ARQ Worker ]
    |
    +--> Notifications
    +--> Approval Reminders
    +--> Scheduled Tasks
    +--> Embedding Jobs
```

### 5.2 后续深化目标

```text
[ Browser ]
    |-- Vue 3 SPA
    |-- Kanban / Gantt / Inbox / AI Command UI
    |-- Browser Push / PWA
    |
[ Nginx ]
    |
[ FastAPI ]
    |-- 更细粒度服务边界
    |-- 更完整的外部渠道适配
    |
    +--> PostgreSQL / pgvector
    +--> Redis / ARQ Queue
    +--> S3-compatible Storage

[ Test / QA ]
    |-- 集成测试
    |-- E2E smoke
    |-- 场景化 demo 数据
```

## 6. 与文档体系的关系

- `design-document.md`：定义为什么这样选
- `architecture.md`：定义这些技术如何落到当前工程和 schema
- `implementation-plan.md`：定义按什么顺序继续实现
- `progress.md`：记录哪些技术能力已经真正交付
