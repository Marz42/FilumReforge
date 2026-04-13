
# 🛠 Project Filum 技术栈选型指南 (Tech Stack)

**版本**: v1.0.0
**核心原则**: 极简架构 (Minimalist) / 类型安全 (Type-Safe) / 极速开发 (Rapid Development) / AI 友好 (AI-Ready)

面对 50~100 人的企业规模，我们拒绝盲目追求大型互联网公司的复杂架构。本技术栈的选择标准是：**成熟度极高、社区生态繁荣、开发体验顺畅、单机或小集群即可稳定支撑。**

---

## 1. 前端技术栈 (Frontend Stack)

前端的目标是快速构建出色的现代化 B 端（后台管理）界面，并具备跨平台与消息推送的潜力。

*   **核心框架**: **Vue 3 (Composition API)**
    *   *选型理由*: 学习曲线平滑，双向绑定和响应式系统非常适合表单密集型的内部事务系统。Composition API 极大地提高了复杂逻辑的代码复用率。
*   **开发语言**: **TypeScript**
    *   *选型理由*: 强类型语言。对于企业级系统，TS 能在编译阶段拦截 80% 的低级错误，保证长期的可维护性。
*   **构建工具**: **Vite**
    *   *选型理由*: 极速的冷启动和热更新(HMR)，相比 Webpack 能节省大量等待时间，提供极致的开发体验。
*   **UI 组件库**: **Element Plus**
    *   *选型理由*: 专门为 Vue 3 打造的企业级 B 端组件库。开箱即用的表格、表单、日期选择器、弹窗，能帮你省去几周的 UI 开发时间。
*   **状态管理 & 路由**: **Pinia** + **Vue Router**
    *   *选型理由*: Vue 3 官方推荐标准组合。Pinia 比旧版的 Vuex 更轻量且原生支持 TypeScript。
*   **跨平台能力**: **Vite PWA Plugin**
    *   *选型理由*: 零额外开发成本。通过 PWA (渐进式 Web 应用) 技术，直接将网页变为可安装的桌面端/移动端应用，并支持浏览器级别的原生消息推送。

---

## 2. 后端技术栈 (Backend Stack)

后端的目标是提供极高的接口响应速度、无缝的 AI/大模型接入能力，以及严谨的数据验证。

*   **核心框架**: **FastAPI (Python 3.10+)**
    *   *选型理由*: 目前最快、最现代的 Python Web 框架。基于 ASGI 异步标准。**最重要的是，它原生支持 OpenAPI 和 Swagger UI，你写完代码，接口文档自动生成**，极大降低了前后端沟通成本。
*   **数据验证与序列化**: **Pydantic v2**
    *   *选型理由*: FastAPI 的核心依赖。通过 Python 类型提示（Type Hints）进行极其严格的输入输出数据校验。完美契合 LLM Function Calling 的 JSON Schema 结构。
*   **ORM (对象关系映射)**: **SQLAlchemy 2.0 (Async)**
    *   *选型理由*: Python 生态中最稳健、最强大的数据库操作库。2.0 版本全面拥抱异步和类型提示。
*   **数据库迁移**: **Alembic**
    *   *选型理由*: 配合 SQLAlchemy 使用，安全地管理数据库表结构的变更和版本控制。
*   **AI/LLM 集成**: **官方 `openai` Python SDK**
    *   *选型理由*: 保持极简。不推荐引入臃肿的 LangChain。当前主流大模型（包括国内的通义千问、DeepSeek、智谱等）全部兼容 OpenAI 的接口标准，使用官方原生 SDK 搭配 Pydantic 处理工具调用 (Tool Calling) 最稳健。

---

## 3. 数据库与中间件 (Database & Middleware)

数据持久化和异步任务是系统的基石，这里的选型绝不妥协，只选工业界经过时间检验的霸主。

*   **关系型主数据库**: **PostgreSQL 15+**
    *   *选型理由*: 地表最强开源关系型数据库。
    *   *绝杀特性*: 原生支持 **JSONB** 类型，非常适合人事档案里那些随时会增减的“自定义字段”，让你既有关系型数据库的安全，又拥有 NoSQL 的灵活。未来还可以直接安装 `pgvector` 插件实现 AI 向量检索。
*   **内存缓存与消息队列**: **Redis**
    *   *选型理由*: 承担三项核心任务：存储用户登录 Session、缓存常用组织架构树、作为异步队列的 Broker（消息代理）。
*   **异步任务调度器**: **Celery** (或者更轻量的 **ARQ**)
    *   *选型理由*: 事务系统中有大量不能阻塞主线程的任务（例如：群发 50 封邮件、生成复杂的统计报表、调用大模型 API 等），必须放入 Redis 队列交由后台 Worker 异步处理。

---

## 4. 部署与运维 (DevOps & Deployment)

100 人的系统不需要复杂的 Kubernetes (K8s)，单台配置稍好的云服务器（例如 4核 8G）加上成熟的容器化方案即可稳如泰山。

*   **容器化引擎**: **Docker + Docker Compose**
    *   *选型理由*: 一键拉起整个运行环境（前端 Nginx、后端 FastAPI、PostgreSQL、Redis）。开发环境与生产环境高度一致，避免“在我的电脑上明明能跑”的尴尬。
*   **反向代理与网关**: **Nginx**
    *   *选型理由*: 极其稳定。负责承接外部 HTTP 请求，处理 HTTPS 证书，并将 API 请求转发给内部的 FastAPI，将前端静态文件直接返回给用户。

---

## 5. 技术架构图览 (Architecture Map)

```text
[ 客户端 Client ]
       |-- Vue 3 SPA (PWA Ready)
       |-- Element Plus UI
       |-- Axios (HTTP 通信)
       |
[ 反向代理 Proxy ]
       |-- Nginx (处理 HTTPS, 静态资源分发)
       |
[ 后端 API 层 ]
       |-- FastAPI (提供 RESTful / WebSocket 接口)
       |-- Pydantic (请求/响应数据校验)
       |-- LLM Router (OpenAI SDK + Tool Calling)
       |
[ 异步处理层 ]
       |-- Celery/ARQ Worker (监听后台任务，如发邮件)
       |-- Email Adapter (SMTP 发送)
       |
[ 数据存储层 ]
       |-- PostgreSQL (核心业务数据、JSONB 扩展档案)
       |-- Redis (缓存、队列通信)
```
