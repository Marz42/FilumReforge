# Project Filum 技术栈与落地状态

**版本**: v1.1.0  
**核心原则**: 极简架构 / 类型安全 / 演进式交付 / AI 友好

## 1. 技术选型总览

| 层级 | 选型 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| Frontend Core | Vue 3 + TypeScript + Vite | 已落地 | 当前前端基线 |
| UI | Element Plus | 已落地 | 当前 B 端后台 UI 基线 |
| 状态与路由 | Pinia + Vue Router | 已落地 | 当前前端状态与权限路由 |
| HTTP Client | Axios | 已落地 | 所有前端请求统一出口 |
| Backend Core | FastAPI | 已落地 | 当前 API 框架 |
| Schema / Validation | Pydantic v2 | 已落地 | API 协议与未来 Tool Schema 基础 |
| ORM | SQLAlchemy 2.0 Async | 已落地 | 当前异步 ORM 基线 |
| Migrations | Alembic | 已落地 | 当前迁移体系 |
| Database | PostgreSQL 15+ | 已落地 | 主业务数据库 |
| JSON 扩展 | PostgreSQL JSONB | 已落地 | 当前档案动态字段能力 |
| Cache / Queue | Redis | 已落地 | 当前缓存与异步队列 Broker |
| Async Worker | ARQ | 已落地 | 当前 worker 选型与实现 |
| Object Storage | 本地适配器 / 未来 S3 兼容 | 已落地基线 | 当前附件通过对象存储抽象管理 |
| Realtime | WebSocket | 规划中 | 当前仅有渠道枚举与消息骨架 |
| Browser Push | Web Push | 规划中 | Phase 5 目标 |
| PWA | Vite PWA Plugin | 规划中 | Phase 5 目标 |
| AI / LLM | 官方 `openai` Python SDK | 规划中 | Phase 5 目标，禁止 LangChain |
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

### 2.2 后端

- FastAPI
- Pydantic v2
- SQLAlchemy 2.0 Async
- Alembic

### 2.3 存储与中间件

- PostgreSQL
- Redis
- ARQ
- 本地文件系统对象存储适配器

### 2.4 基础编排

- Docker Compose
- Nginx

## 3. 当前尚未落地但已确认的技术方向

### 3.1 Phase 3 / HR Governance

- 基于现有 PostgreSQL schema 扩展岗位、汇报线、生命周期事件、字段权限与授权表
- 继续使用 JSONB 作为动态字段承载层，但通过 metadata / policy 表补齐字段级权限

### 3.2 Phase 4 / Workflow & Messaging

- 基于现有 FastAPI + ARQ 实现模板实例化、审批流与自动触发
- 先落地 Email / WebSocket 渠道适配器，再补完整消息中心
- 前端增加列表 / 看板 / 甘特图视图

### 3.3 Phase 5 / Knowledge, AI Router & Experience

- PostgreSQL + `pgvector`
- 官方 `openai` SDK + Pydantic Tool Schema
- 浏览器 Push Subscription + Web Push
- PWA 安装体验

## 4. 关键技术决策

### 4.1 为什么继续坚持模块化单体

- 当前团队规模与业务复杂度不适合引入微服务治理成本
- HR、Workflow、Messaging、AI 之间共享权限、组织和附件能力，单体更容易保持一致性

### 4.2 为什么 worker 固定选 ARQ

- 当前后端本身就是 async 栈
- 已经有 Redis
- 比 Celery 更轻，更接近当前项目体量
- Phase 2 已经实际落地 ARQ worker 与 cron job

### 4.3 为什么 AI 必须使用官方 `openai` SDK

- Tool Calling / Function Calling 能直接与 Pydantic schema 对接
- 避免 LangChain 带来的抽象层级和不可控行为
- 兼容 OpenAI 风格 API 的国产模型

### 4.4 为什么浏览器推送排在 Phase 5

- 真正可用的浏览器推送依赖：
  - 消息中心
  - 回执模型
  - Push Subscription 持久化
  - Web Push 渠道适配器
- 在 Workflow / Messaging 基座没补齐前，先做推送会导致消息语义不稳定

## 5. 当前与目标架构图

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
    |
    +--> PostgreSQL
    +--> Redis / ARQ Queue
    +--> Local Storage Adapter

[ ARQ Worker ]
    |
    +--> PostgreSQL
    +--> Redis / ARQ Queue
```

### 5.2 目标

```text
[ Browser ]
    |-- Vue 3 SPA
    |-- Kanban / Gantt / Inbox / AI Command UI
    |-- Browser Push / PWA
    |
[ Nginx ]
    |
[ FastAPI ]
    |-- REST API
    |-- Workflow Engine
    |-- Message Center
    |-- LLM Router
    |
    +--> PostgreSQL / pgvector
    +--> Redis / ARQ Queue
    +--> Object Storage
    +--> Email / WebSocket / Web Push Adapters

[ ARQ Worker ]
    |-- Notifications
    |-- Scheduled Tasks
    |-- Approval Reminders
    |-- LLM / Embedding Jobs
```

## 6. 与文档体系的关系

- `design-document.md`：定义为什么这样选
- `architecture.md`：定义这些技术如何落到当前工程和 schema
- `implementation-plan.md`：定义按什么顺序继续实现
- `progress.md`：记录哪些技术能力已经真正交付
