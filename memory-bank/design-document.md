# Project Filum 设计文档

**版本**: v1.0.0  
**状态**: Draft / 规划中  
**目标受众**: 产品、设计、前后端研发

## 1. 项目概述

Project Filum 是一个面向 50-100 人规模企业的轻量级内部管理平台，目标是在一套系统中统一承载：

- **人**：用户、档案、组织结构、权限边界
- **事**：任务流转、协同留痕、统计分析
- **信息**：通知、制度文档、AI 驱动的自然语言入口

系统定位不是“大而全的 OA”，而是围绕日常协同高频场景提供一套**可快速实施、低维护成本、AI 原生**的内部平台。

## 2. 设计原则

1. **模块化单体优先**
   - 明确反对微服务过早拆分。
   - 通过代码模块边界获得低耦合，而不是通过部署单元切碎系统。

2. **抽象优于直连**
   - 业务层不直接操作邮件、Web 推送、对象存储或 LLM 平台。
   - 所有外部能力都通过统一服务抽象接入。

3. **AI 是交互路由器**
   - `@系统` 与 `/` 指令的目标是把自然语言转成结构化系统操作。
   - LLM 负责理解意图和组织回答，不直接承载业务真相。

4. **工作必须可追溯**
   - 所有工作沟通、评论、附件必须绑定具体任务上下文。
   - 禁止脱离任务的独立聊天能力。

## 3. 技术栈约束

| 层级 | 固定选型 |
| --- | --- |
| Frontend | Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router |
| Backend | Python 3.10+ + FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic |
| AI | 官方 `openai` Python SDK |
| Database | PostgreSQL 15+ |
| Cache / Broker | Redis |
| Async Worker | Celery 或 ARQ |
| Deployment | Docker Compose + Nginx |

**补充约束**

- 不使用 LangChain。
- 所有 HTTP 请求统一由 Axios 发起。
- 前端使用 Composition API 与 `<script setup>`。
- 动态档案字段统一放入 `profiles.custom_fields (JSONB)`。

## 4. 核心模块

### 4.1 组织与人事

- 用户鉴权、账号状态、角色控制
- 部门树结构与负责人关联
- 员工档案与自定义字段
- 员工生命周期事件驱动后续任务

### 4.2 任务与协同

- 任务创建、指派、截止日期管理
- 状态机：`Todo -> Doing -> Review -> Done`
- 评论、日志、附件绑定任务形成工作留痕
- 统计维度包括完成率、超时趋势、负载分布

### 4.3 通知总线

- 业务侧统一调用 `NotificationService.send(message_obj)`
- Redis 作为异步 broker
- Email / WebPush / WebSocket 通过 adapter 接入
- 消息发送过程可审计、可追踪、可重试

### 4.4 文件对象存储

- 建立统一 `attachments` 元数据模型
- 通过 `ObjectStorageService` 选择具体存储实现
- 通过业务绑定表把附件映射到 `task_comments`、`documents` 等对象
- 不在业务表中直接存二进制内容

### 4.5 知识库与 AI Router

- 文档内容使用 Markdown 存储
- `document_embeddings` 使用 `pgvector` 保存切块向量
- AI Router 通过 Tool Calling 调用后端注册工具
- 回答制度类问题时优先执行 RAG 检索

### 4.6 工具注册平台

- 工具必须同时具备前端入口与后端路由
- 工具 schema 对 AI Router 可见
- 工具需要权限边界和组织上下文注入能力

## 5. 关键设计约束

### 5.1 通知必须异步

从 Phase 1 开始，Docker Compose 中就要包含 Redis。通知总线默认异步执行，避免邮件、推送或未来渠道阻塞主业务请求。

### 5.2 附件必须统一建模

附件不是任务表或评论表上的随意字段，而是统一对象存储元数据能力：

- `attachments`：存储对象元数据
- `attachment_links`：存储业务绑定关系
- 与工作相关的附件必须挂在 `task_comments` 上

### 5.3 AI 必须建立在结构化工具之上

- 工具入参、出参以 Pydantic v2 模型定义
- LLM 调用的是注册工具，而不是直接拼接 SQL 或任意代码
- LLM 返回自然语言前，必须先拿到后端真实结构化数据

## 6. 数据模型总览

当前规划中的核心表包括：

- `users`
- `departments`
- `profiles`
- `attachments`
- `attachment_links`
- `tasks`
- `task_dependencies`
- `task_logs`
- `task_comments`
- `notification_messages`
- `notification_deliveries`
- `documents`
- `document_embeddings`

详细字段、约束与索引以 `memory-bank/architecture.md` 为准。

## 7. 分阶段路线

### Phase 1 - Foundation

- 初始化前后端工程
- 用户、部门、人事档案 CRUD
- 任务基础能力
- Redis 异步通知总线骨架

### Phase 2 - Collaboration & Stats

- 严格任务状态机
- `task_comments` 与附件留痕
- `task_logs`
- 超时提醒与 BI 统计

### Phase 3 - Knowledge & AI Brain

- Markdown 知识库 CRUD
- 向量切块与相似度检索
- AI Router 与 Tool Calling

### Phase 4 - Platform & Tools Registry

- 工具注册标准
- `@系统` 多工具协同
- PWA 与部署打磨

## 8. 测试要求

实施过程中的每一步都必须包含验证，而不是只写文档或代码：

- 文档阶段：验证命名、引用、文件完整性
- 脚手架阶段：验证目录、依赖安装、最小应用可运行
- 后端阶段：验证健康检查、测试命令、导入链路
- 容器阶段：验证 compose 配置、依赖关系与基础连通性

## 9. 当前文档角色

- `design-document.md`：产品与设计意图、阶段边界、核心约束
- `architecture.md`：工程实现基线、完整数据库 schema、模块与运行时边界
- `implementation-plan.md`：实施顺序与测试出口
- `progress.md`：已完成步骤与验证记录
