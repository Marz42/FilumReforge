# Project Filum 实施计划

## 1. 目标与理解确认

基于最新 `copilot-instructions.md` 与现有设计文档，项目实施必须严格遵循以下约束：

- 架构采用**模块化单体**，避免微服务拆分。
- 前端固定为 **Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router**。
- 后端固定为 **FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic**。
- LLM 集成必须使用**官方 `openai` Python SDK**，并以 **Function Calling / Tool Calling** 作为核心机制，**禁止引入 LangChain**。
- `profiles.custom_fields` 使用 **PostgreSQL JSONB** 承载动态档案字段。
- 任务状态流转必须严格受控：`Todo -> Doing -> Review -> Done`。
- 通知能力必须收敛到统一总线：业务层仅调用 `NotificationService.send(message_obj)`。
- 所有工作沟通必须绑定 `Task`，通过 `task_comments` 落库，**不能实现独立聊天系统**。
- 附件能力必须走**统一文件对象存储抽象**，数据库预留 `attachments` 表保存元数据与业务引用，二进制文件本体不直接写入业务表。
- 权限模型必须同时覆盖**角色级 RBAC**与**组织树数据级隔离**。
- 知识库能力基于 PostgreSQL + `pgvector`，为后续 RAG 检索服务。
- Phase 1 的 Docker Compose 必须纳入 **Redis**，通知总线从第一阶段开始即走异步链路。
- 实施方案中的**每一个步骤都必须包含测试与验证**，未通过测试的步骤不视为完成。
- 扩展工具池与 `@系统` 指令路由应作为平台能力，在后续阶段演进。

## 2. 当前阶段状态

当前仓库仍处于从规划转向实施的起始阶段，现状如下：

- `memory-bank/architecture.md` 已建立为正式架构记录文件，并补齐了模块边界、核心流程与全量数据库 schema。
- `memory-bank/design-document.md` 已建立为标准设计文档入口；`design-document.md.md` 作为历史草稿保留。
- 文档层基线已具备，但前后端工程脚手架、容器编排与测试运行基线仍待完成。

因此，当前实施重点应转向工程骨架与验证链路建设。

## 3. 实施原则

1. **先文档、后脚手架、再功能**：先统一架构文档、数据库边界、目录结构，再进入模块实现。
2. **按阶段顺序推进**：严格依照 Phase 1 至 Phase 4 逐步落地，不跨阶段提前实现高阶能力。
3. **服务层承载业务逻辑**：FastAPI 路由保持轻量，规则与流程沉淀到 service 层。
4. **数据库模式先行**：先确定领域模型、约束、枚举、索引和迁移策略，再实现接口。
5. **平台能力统一收口**：通知、AI 路由、工具注册等能力必须通过统一抽象暴露，避免业务侧直接耦合底层实现。
6. **附件统一存储抽象**：所有附件统一接入对象存储服务，关系库只保存 `attachments` 元数据、归属与权限控制信息。
7. **测试与实施同步推进**：每一个实施步骤都必须定义并执行对应测试，覆盖单元、集成或冒烟验证之一或组合。

## 4. 实施阶段拆解

### 阶段 A：文档基线与仓库初始化

**目标**：把规划文档转成可实施的工程基线，不改变原有产品四阶段定义。

**主要工作**

- 补齐并标准化文档：
  - 创建 `memory-bank/architecture.md`
  - 创建 `memory-bank/progress.md`
  - 补齐完整数据库 schema、模块边界、核心交互流
  - 将 `design-document.md.md` 整理为指令约定的标准入口文档
- 初始化仓库结构：
  - `frontend/`：Vue 3 应用
  - `backend/`：FastAPI 应用
  - `infra/`：Docker Compose、Nginx、环境模板
  - `memory-bank/`：持续维护架构与设计文档
- 建立基础工程规范：
  - 前后端开发命令
  - 环境变量分层
  - Alembic 初始化
  - 本地联调方式
  - 测试基线与最小验证流程
  - 文件对象存储抽象与 `attachments` 表设计原则

**交付物**

- 可追溯的架构主文档
- 可持续更新的进度记录文件
- 可运行的前后端脚手架
- 首版数据库迁移基线

**测试与验证**

- 文档入口存在性检查：`architecture.md`、`progress.md`、实施计划与设计文档入口必须齐备。
- 文档引用一致性检查：核心文档中的文件名、阶段名、模块名不能互相冲突。
- 基础工程冒烟检查：脚手架命令、目录结构与本地启动说明必须可执行。

### 阶段 1：Foundation

**目标**：完成系统底座，支撑用户、组织、人事档案、任务基础流转与通知骨架。

**范围**

- 用户与认证基础：
  - `users` 模型
  - 登录鉴权与用户状态管理
  - 基础角色枚举：Admin / HR / Employee
- 组织架构：
  - `departments` 树结构
  - 负责人绑定与组织树查询
- 人事档案：
  - `profiles` 模型
  - typed columns + `custom_fields JSONB`
  - 人员与部门归属联动
- 附件与文件存储基线：
  - `attachments` 表
  - `ObjectStorageService` / Storage Adapter 抽象
  - 文件元数据、权限与业务引用策略
- 任务基础能力：
  - `tasks` 创建、指派、截止日期管理
  - 基础列表查询与详情展示
- 通知总线骨架：
  - 统一 Message 对象
  - `NotificationService.send(...)`
  - Docker Compose 首版即纳入 Redis
  - 基于 Redis Broker/Queue 的异步通知链路
  - Email / Web 通知适配器接口预留

**建议交付顺序**

1. 数据模型与 Alembic 初版迁移
2. 后端基础模块、对象存储抽象与 service 层骨架
3. 前端登录、组织、人事、任务基础页面
4. Docker Compose + Redis + 异步通知总线最小可用链路

**测试与验证**

- 数据库迁移测试：核心表、外键、索引与枚举可正确迁移与回滚。
- 认证与权限测试：角色权限、登录流程与基础访问控制有效。
- 组织与档案测试：部门树查询、`custom_fields JSONB` 读写正确。
- 任务基础测试：创建、指派、截止日期更新与详情查询正确。
- 附件基线测试：`attachments` 元数据写入、对象存储抽象上传/下载接口与授权校验正确。
- 通知异步测试：消息可进入 Redis 队列并被 Worker/消费者正确处理。

### 阶段 2：Collaboration & Stats

**目标**：把任务真正变成协同中枢，补齐流程控制、留痕与统计。

**范围**

- 严格任务状态机：
  - `Todo -> Doing -> Review -> Done`
  - 服务端校验非法跳转
- 工作留痕：
  - `task_comments`
  - `task_comments` 与 `attachments` 的关联关系
  - 任务详情页内评论流
- 审计追踪：
  - `task_logs`
  - 状态变化、指派变更、评论等事件记录
- 超时提醒：
  - Celery 或 ARQ 后台任务
  - 基于通知总线发出提醒
- BI 统计：
  - 任务完成率
  - 个人/部门负载
  - 超时趋势

**关键要求**

- 不实现独立 IM/聊天模块。
- 所有评论、沟通、附件都必须绑定任务上下文。

**测试与验证**

- 状态机测试：仅允许 `Todo -> Doing -> Review -> Done` 的合法流转。
- 留痕测试：评论、附件关联、日志记录都能按任务完整追溯。
- 提醒任务测试：超时扫描、入队、发送结果与失败重试链路可验证。
- BI 测试：统计口径与基础样本数据结果一致。

### 阶段 3：Knowledge & AI Brain

**目标**：建立可检索的公司知识库，并让 AI 能安全调用内部工具。

**范围**

- 文档知识库：
  - `documents` CRUD
  - Markdown 存储
  - 分类、作者、版本基础信息
- 向量化能力：
  - `document_embeddings`
  - 文档切块、嵌入生成、相似度检索
- AI Router 第一版：
  - `@系统` / `/` 指令入口
  - 基于 Pydantic v2 的工具 schema
  - 工具注册与调用分发
- 面向知识问答的 RAG：
  - 优先召回内部制度/SOP
  - 组织自然语言答案

**关键要求**

- AI 是“意图路由器”，不是自由聊天机器人。
- 工具调用返回原始结构化数据，再由模型组织最终文本。

**测试与验证**

- 文档 CRUD 测试：Markdown 文档新增、修改、删除、分类正确。
- 向量流程测试：切块、嵌入、入库与相似度检索结果可验证。
- Tool Calling 合约测试：Pydantic schema、工具注册与调用返回结构稳定。
- RAG 测试：问答结果能正确引用制度/SOP 检索来源。

### 阶段 4：Platform & Tools Registry

**目标**：把 AI 与工具体系平台化，并完善最终可用性。

**范围**

- 扩展工具池标准：
  - 前端独立工具视图规范
  - 后端专属 router/service 规范
  - 注册到 LLM 工具目录
- 深化 `@系统` 能力：
  - 多工具协同
  - 更细粒度权限校验
  - 组织上下文与用户上下文注入
- 体验完善：
  - B 端后台 UI 打磨
  - PWA 安装能力
  - Web 推送完善
- 部署完善：
  - Docker Compose 集成全链路服务
  - Nginx 反向代理与生产配置

**测试与验证**

- 工具注册测试：新增工具可被平台发现、鉴权并执行。
- 多工具协同测试：`@系统` 场景下可完成跨工具路由与结果整合。
- 前端体验测试：关键后台页面、PWA 安装与推送能力通过冒烟验证。
- 部署冒烟测试：Docker Compose 全链路启动、Nginx 转发与关键健康检查通过。

## 5. 数据库实施优先级

建议按以下顺序沉淀数据库基线，并在 `architecture.md` 中维护完整 schema：

1. `users`
2. `departments`
3. `profiles`
4. `attachments`
5. `tasks`
6. `task_logs`
7. `task_comments`
8. `documents`
9. `document_embeddings`

配套补充内容：

- 枚举：用户角色、用户状态、任务状态、通知渠道、文档分类
- 约束：外键、唯一索引、组织树父子关系约束
- 索引：任务查询、部门查询、文档检索、向量索引
- 对象存储字段：`storage_provider`、`bucket`、`object_key`、`original_filename`、`mime_type`、`size_bytes`、`checksum`、`uploader_id`
- 审计字段：`created_at`、`updated_at`、必要的 `created_by` / `updated_by`

## 6. 工程目录建议

```text
frontend/
  src/
    api/
    stores/
    router/
    views/
    components/
  tests/

backend/
  app/
    api/
    core/
    models/
    schemas/
    services/
    repositories/
    workers/
    integrations/
  tests/

infra/
  docker/
  nginx/

memory-bank/
  architecture.md
  progress.md
  design-document.md
  implementation-plan.md
```

## 7. 跨阶段通用工作项

- 鉴权、RBAC 与组织树数据隔离贯穿所有阶段。
- 所有新里程碑完成后，同步更新 `memory-bank/architecture.md`。
- 每完成一个实施步骤后，同步更新 `memory-bank/progress.md`。
- 每个阶段结束后进行一次文档、迁移与接口边界回顾。
- 每个实施步骤都必须保留对应测试结果或测试结论，作为推进下一步的前置条件。
- 通知、AI、工具池能力都必须通过统一抽象层接入，避免后续返工。

## 8. 建议的执行步骤（每步含测试）

1. **标准化文档入口与记录文件**
   - 实施内容：创建 `architecture.md`、`progress.md`，统一 `memory-bank` 的文档入口与命名规则，整理设计文档正式入口。
   - 测试与验证：检查核心文件存在性、文档交叉引用与阶段命名一致性。

2. **初始化工程脚手架与容器编排**
   - 实施内容：建立 `frontend/`、`backend/`、`infra/` 基础目录与本地开发入口，首版 Docker Compose 纳入 PostgreSQL、Redis、API、Web。
   - 测试与验证：容器编排冒烟检查、API 健康检查、Redis 连通性与前端基础访问验证。

3. **落地数据库基线与迁移体系**
   - 实施内容：设计并落地 `users`、`departments`、`profiles`、`attachments`、`tasks`、`task_logs`、`task_comments`、`documents`、`document_embeddings` 首版 schema 与 Alembic 基线。
   - 测试与验证：迁移升降级测试、外键与唯一约束测试、`attachments` 元数据与业务引用样例验证。

4. **完成 Phase 1 基础业务链路**
   - 实施内容：实现登录鉴权、RBAC、组织树、人事档案 CRUD、任务创建/指派，以及基于 Redis 的异步通知总线。
   - 测试与验证：认证权限测试、组织树范围测试、JSONB 档案测试、任务基础接口测试、通知入队/消费测试。

5. **完成 Phase 2 协同与统计能力**
   - 实施内容：实现严格状态机、任务评论留痕、附件绑定、审计日志、超时提醒与基础 BI。
   - 测试与验证：状态流转测试、评论与附件追溯测试、提醒任务链路测试、统计结果校验。

6. **完成 Phase 3 知识库与 AI Router**
   - 实施内容：实现文档 CRUD、切块嵌入、向量检索、`@系统` 指令入口与 Tool Calling 路由。
   - 测试与验证：知识库 CRUD 测试、嵌入检索测试、工具调用合约测试、RAG 检索结果验证。

7. **完成 Phase 4 平台化与部署打磨**
   - 实施内容：实现工具注册标准、深化 AI 路由、完善后台体验、PWA 能力与生产部署配置。
   - 测试与验证：工具注册测试、多工具协同冒烟测试、PWA 功能测试、全链路部署冒烟测试。

## 9. 完成标准

该计划完成后，项目实施应满足以下标准：

- 任一开发者可依据 `memory-bank` 文档直接开始分阶段编码。
- 阶段边界、依赖顺序、核心约束与禁止事项均清晰可见。
- 数据库、附件存储、通知、AI、任务协同五条主线在计划中已提前收口。
- `progress.md` 可用于同步记录完成步骤，`architecture.md` 可用于持续沉淀架构基线。
- 每一步都有明确的测试与验证出口。
- 后续编码时不会偏离“模块化单体 + 统一抽象 + 分阶段交付”的总体方向。
