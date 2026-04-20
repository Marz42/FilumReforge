# Project Filum 进度记录

## 当前阶段状态

| 阶段 | 状态 | 结论 |
| --- | --- | --- |
| Phase A / 文档与工程基线 | done | 文档入口、脚手架、基础编排已完成 |
| Phase 1 / Foundation | done | 用户、组织、档案、附件、任务基础、异步通知骨架已完成并通过用户点击验证 |
| Phase 2 / Collaboration & Stats | done | 状态机、评论留痕、审计日志、ARQ 提醒 worker、统计与协同任务页已完成并通过用户简单测试 |
| Phase 3 / HR Governance & Org Modeling | done | 代码已实现、修复 PostgreSQL 迁移命名问题，并通过用户手动验测 |
| Phase 4 / Workflow Engine & Messaging | done | 模板、审批流、自动化、消息中心与多视图已完成，并通过用户手动验测 |
| Phase 5 / Knowledge, AI Router & Experience | done | 知识库、RAG、AI Router、Push / PWA 已完成，后续进入文档收口、重构与测试强化 |

## 当前重构执行状态

| 步骤 | 状态 | 结论 |
| --- | --- | --- |
| Step 1 / 壳层导航重构 | done | 用户已确认通过，已完成分组导航、主入口改名、旧路由兼容跳转与聚合入口壳层 |
| Step 2 / 总览模块 | done | 已完成看板、公告、当前任务投影、总览聚合接口、总览页前端、归档 cron 与自动化回归，并通过用户手动验测 |
| Step 3 / 任务中心重构 | done | 已完成任务中心六标签工作台、`task-center` 聚合接口、`task_memos` 领域、权限重构与前后端回归，并通过用户手动验测 |
| Step 4 / 汇报中心落地 | done | 已完成 `report-center` 聚合接口、`reports` / `report_routes` 领域、逐级向上汇报 / 向下传达、可选审批挂接与前后端回归；当前等待用户手动验测 |

## 已完成里程碑

### Phase A / 文档与工程基线

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 文档基线与标准入口 | done | 建立 `architecture.md`、`design-document.md`、`progress.md`、`implementation-plan.md` | 已核对文件存在与引用一致性 |
| 前端脚手架 | done | Vue 3 + TypeScript + Vite + Pinia + Vue Router + Element Plus | 已执行前端单元测试、构建与 lint |
| 后端脚手架 | done | FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic | 已执行 `pytest`、`compileall` |
| 容器化编排 | done | Dockerfile、Compose、Nginx、环境模板 | 已完成配置级检查 |

### Phase 1 / Foundation

#### 1. 模型先行

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 枚举与数据库类型基线 | done | 统一枚举、JSON / enum DB 类型封装 | 已纳入后端测试 |
| 领域模型与 mixin | done | `users`、`departments`、`profiles`、`attachments`、`tasks`、`notification_*` 等模型 | 已执行模型与 metadata 测试 |
| Alembic 迁移 | done | `20260413_01_phase1_foundation.py` | 已执行升级 / 回滚测试 |

#### 2. 服务层封装

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 认证服务 | done | 管理员初始化、登录、refresh、当前用户解析 | 已执行服务测试 |
| 组织与档案服务 | done | 用户、部门、档案管理 | 已执行服务测试 |
| 附件与对象存储 | done | 本地对象存储适配器与附件服务 | 已执行上传 / 删除测试 |
| 任务与通知 | done | 任务创建 / 指派与消息入队骨架 | 已执行服务测试 |

#### 3. API 暴露

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 认证、用户、部门、档案、任务、附件 API | done | 标准 REST 接口与统一依赖注入 | 已执行 API 集成测试 |
| 开发态错误收口 | done | 数据库不可用时返回清晰 `503` 提示 | 已执行错误处理测试 |

#### 4. 前端对接

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 会话层与路由守卫 | done | token 持久化、自动 refresh、受保护路由 | 已执行单元测试 |
| 基础后台页面 | done | 仪表盘、部门页、档案页、任务页、附件上传 | 已执行 `type-check`、`build`、`lint` |
| 联调修复 | done | 修复开发代理 404、本地 / Compose 启动链路 | 已完成用户实际点击验证 |

### Phase 2 / Collaboration & Stats

#### 1. 模型先行

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 枚举与协同模型 | done | `TaskActionType`、`CommentFormat`、`TaskLog`、`TaskComment` | 已执行模型与迁移相关测试 |
| Alembic 迁移 | done | `20260414_01_phase2_collaboration.py` | 已执行升级 / 回滚测试 |

#### 2. 服务层封装

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 状态机与审计 | done | 严格任务状态机、自动维护开始/完成时间、自动日志 | 已执行合法 / 非法流转测试 |
| 评论与活动流 | done | 评论、内部备注、评论附件、活动流聚合 | 已执行权限、附件与排序测试 |
| 统计查询 | done | 完成率、逾期率、状态分布、负载查询 | 已执行样例口径测试 |

#### 3. Worker 与异步提醒

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| ARQ Worker | done | `jobs.py`、`arq_worker.py`、`start-worker.sh` | 已执行 worker 单元测试 |
| 编排补齐 | done | Compose 新增 `worker` 服务 | 已完成配置级检查 |

#### 4. API 暴露

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 任务协同接口 | done | 状态流转、评论、活动流、统计接口 | 已执行 API 集成测试 |

#### 5. 前端对接

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 协同任务页 | done | 统计卡片、状态按钮、评论区、评论附件、活动时间线、负载概览 | 已执行 `test:unit`、`type-check`、`build`、`lint` |
| 用户基础验测 | done | 用户进行了简单测试并确认“看上去基本没有问题” | 已完成阶段性文档收口 |

### Phase 3 / HR Governance & Org Modeling

#### 1. 模型先行

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| HR 治理枚举与模型 | done | `positions`、`profile_positions`、`reporting_lines`、`profile_field_*`、`employment_events`、`delegations` | 已执行模型持久化测试 |
| Alembic 迁移 | done | `20260415_01_phase3_hr_governance.py` | 已执行升级 / 回滚测试 |

#### 2. 服务层封装

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 组织关系与字段权限 | done | `OrganizationRelationService`、`ProfileFieldPolicyService`、扩展 `access_control.py` | 已执行权限矩阵与代理授权测试 |
| 生命周期与授权 | done | `HRLifecycleService`、`DelegationService`、重构 `ProfileService` | 已执行生命周期事件与状态联动测试 |

#### 3. API 暴露

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 档案治理接口 | done | `profiles` 子资源接口、`hr_governance` 路由 | 已执行 API 集成测试 |

#### 4. 前端对接

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 档案治理工作台 | done | 多标签档案页、岗位 / 汇报线 / 生命周期 / 授权表单 | 已执行 `test:unit`、`type-check`、`build`、`lint` |

#### 5. 当前阶段闸门

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 用户手动验测 | done | 用户已按复现路径重新验证迁移与 Compose 启动链路 | 已完成自动化验证与用户手动验测 |

### Phase 4 / Workflow Engine & Messaging

#### 1. 模型先行

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| Workflow / Messaging 枚举与模型 | done | `task_templates`、`workflow_*`、`task_watchers`、`task_schedules`、`notification_receipts` | 已执行模型与 metadata 测试 |
| Alembic 迁移 | done | `20260416_01_phase4_workflow_messaging.py` | 已执行升级 / 回滚与约束回归测试 |

#### 2. 服务层封装

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 模板 / 审批 / 自动化服务 | done | `TaskTemplateService`、`WorkflowEngineService`、`TaskAutomationService`、`workflow_rule_resolver.py` | 已执行服务测试 |
| 消息中心与任务扩展 | done | `MessageCenterService`、`TaskService` watcher / board / gantt 扩展 | 已执行服务测试 |

#### 3. Worker 与 API

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| Worker 调度与提醒 | done | 周期模板实例化、审批提醒扫描、ARQ cron 注册 | 已执行 worker 单元测试 |
| 模板 / 审批 / 消息 API | done | `task_templates`、`workflows`、`messages` 路由及 `tasks` 多视图 / watcher 接口 | 已执行 API 集成测试 |

#### 4. 前端对接

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| Workflow 工作台 | done | `TaskTemplatesView.vue`、`ApprovalsView.vue`、`MessagesView.vue` | 已执行前端单元测试 |
| 任务中心多视图 | done | `TasksView.vue` 扩展列表 / 看板 / 甘特图与关注人 | 已执行 `test:unit`、`type-check`、`build`、`lint` |

#### 5. 当前阶段闸门

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 用户手动验测 | done | 用户已确认 Phase 4 通过，可进入下一阶段 | 已完成自动化验证与用户手动验测 |

### Phase 5 / Knowledge, AI Router & Experience

#### 1. 模型先行

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| Knowledge / Push 模型与迁移 | done | `documents`、`document_embeddings`、`push_subscriptions`、`20260417_01_phase5_knowledge_push.py` | 已执行模型、metadata、迁移与配置测试 |
| 编排与数据库基线 | done | Compose PostgreSQL 切换到 `pgvector/pgvector:pg16`，补齐 OpenAI / VAPID 配置项 | 已完成配置级检查与测试覆盖 |

#### 2. 服务层封装

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 文档与检索服务 | done | `DocumentService`、`KnowledgeRetrievalService`、文档附件与 embedding 重建 | 已执行服务测试 |
| AI Router 与工具注册 | done | `ToolRegistryService`、`LLMRouterService`、`@系统` / `/` 路由编排 | 已执行服务与 API 测试 |
| Push 与通知渠道 | done | `BrowserPushService`、Web Push adapter、通知 adapter factory | 已执行服务、worker 与 API 测试 |

#### 3. Worker / API / 前端

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| Worker 与 adapter | done | 文档 embedding job、通知投递分发、Web Push 发送 | 已执行 worker 单元测试 |
| API 层 | done | `documents`、`knowledge`、`ai_router`、`push_subscriptions` 路由与 schema | 已执行 API 集成测试 |
| 前端工作台 | done | 知识库页、命令栏、Push 订阅卡片、PWA 基线 | 已执行 `test:unit`、`type-check`、`build`、`lint` |

#### 4. 阶段后续补丁

| 步骤 | 状态 | 产出 | 验证 |
| --- | --- | --- | --- |
| 浏览器通知业务链路补齐 | done | 任务指派、转派、抄送、逾期提醒、审批提醒已接入 `WEB_PUSH`，并做订阅感知过滤 | 已执行后端与前端全量回归 |
| 用户管理入口补齐 | done | 新增 `/users` 工作台、侧边栏导航与前端测试 | 已执行前端全量验证 |
| 测试数据脚本 | done | `SampleDataService`、`python -m app.scripts.seed_sample_data`、可重复 demo 组织与账号 | 已执行服务测试并实际生成测试数据 |

## 用户验测补记

### Phase 1 验测补记

用户在点击“初始化管理员”和“登录”时，先后暴露出两类问题：

1. 前端开发代理缺失，导致请求命中前端开发服务器并返回 404。
2. 数据库未启动 / 连接不可用，导致后端抛出长链路超时异常。

对应修复已经落地：

- 增加 Vite 代理与开发态直连 fallback
- 补齐 `.env.example`、Compose 自动迁移与更明确的 `503` 错误提示

### Phase 2 验测补记

- 用户进行了简单功能测试，反馈“看上去基本上没有问题”。
- 因此当前 `memory-bank` 已按 **Phase 2 已完成** 的事实收口。

## 重构执行补记

### Step 2 / 总览模块

- 已新增部门能力字段 `departments.capabilities`，用于公告发布等能力控制。
- 已新增 `board_cards`、`board_card_archives`、`announcements`、`announcement_archives`。
- 已新增总览聚合接口、看板发布 / 归档、公告发布 / 撤下，以及待办 / 跟踪任务投影。
- 已重写 `HomeView.vue`，首页现在显示看板、公告、待办事项、任务跟踪和任务中心快捷入口。
- 已补齐后端 `pytest`、`compileall` 与前端 `test:unit`、`type-check`、`build`、`lint` 回归。
- 用户已确认 Step 2 通过，当前已作为 Step 3 的进入基线。

### Step 3 / 任务中心重构

- 已新增 `task_memos` 表、迁移、模型关系与 CRUD 服务。
- 已新增 `/api/v1/task-center` 与 `/api/v1/task-center/memos`，统一输出模板摘要、发布权限、待办、跟踪、历史与备忘。
- 已将模板管理与模板实例化权限从“仅管理角色”扩展为“管理角色 + 部门负责人 + 部门能力”。
- 已将前端 `TaskCenterView.vue` 重构为六标签工作台：任务模板、发布任务、待办事项、任务跟踪、历史任务、备忘。
- 已保留 `TasksView.vue` 的活动时间线、任务协同详情与负载概览，并作为任务跟踪详情区复用。
- 已完成后端 `pytest` / `compileall` 与前端 `test:unit`、`type-check`、`build`、`lint` 回归。
- 用户已确认 Step 3 通过，因此当前重构基线已推进为 **Step 3 done / Step 4 start**。

### Step 4 / 汇报中心落地

- 已新增 `reports`、`report_routes` 表、迁移、模型关系与 API schema。
- 已新增 `/api/v1/report-center`、`/api/v1/report-center/reports` 与动作接口，支持发起、流转、退回、归档。
- 已新增 `ReportService`、`ReportCenterService`，支持逐级向上汇报、逐级向下传达、代理委托、可选挂接 workflow instance。
- 已将 `/reports` 页面升级为真正的汇报中心，支持待处理、我发起、历史归档、发起向上汇报、发起向下传达五个标签。
- 已通过通知总线把新汇报 / 新传达接入消息中心与浏览器推送链路。
- 已完成后端 `pytest` / `compileall` 与前端 `test:unit`、`type-check`、`build`、`lint` 回归。
- 当前停在 Step 4，等待用户手动验测后再决定是否进入 Step 5。

### Phase 3 验测补记

- Phase 3 代码已经完成，自动化验证链路已全部通过。
- 已完成的自动化验证包括：后端 `pytest`、后端 `compileall`、前端 `test:unit`、`type-check`、`build`、`lint`。
- 用户在首次手动验测时发现 PostgreSQL 外键名超长，导致 `alembic upgrade head` 与 Compose backend 启动失败。
- 修复内容：
  1. 缩短 `profile_field_permissions` 的外键名，满足 PostgreSQL 63 字符限制
  2. 新增 metadata / Alembic identifier 长度回归测试
  3. 在真实 PostgreSQL、backend 容器和 Compose backend 服务路径上完成复测
- 用户已按原复现步骤重新验证，确认问题通过。

### Phase 4 验测补记

- Phase 4 代码已经完成，自动化验证链路已全部通过。
- 已完成的自动化验证包括：后端 `pytest`、后端 `compileall`、前端 `test:unit`、`type-check`、`build`、`lint`。
- 本阶段新增的关键能力包括：
  1. 任务模板与周期调度
  2. 轻量审批流引擎（串行 / 会签 / 或签 / 打回 / 驳回 / 代理审批）
  3. 消息中心与用户回执
  4. 任务中心列表 / 看板 / 甘特图多视图与 watcher
- 用户已确认 Phase 4 通过，因此当前文档状态已推进为 **Phase 4 done / Phase 5 next**。

### Phase 5 验测补记

- Phase 5 主体代码已经完成，自动化验证链路已全部通过。
- 已完成的自动化验证包括：后端 `pytest`、后端 `compileall`、前端 `test:unit`、`type-check`、`build`、`lint`。
- 本阶段新增的关键能力包括：
  1. Markdown 知识库与文档附件
  2. embedding 重建、RAG 检索与 `pgvector`
  3. `@系统` / `/` 路由与 Tool Calling
  4. 浏览器 Push 订阅、Web Push adapter 与 PWA 基线
- 用户在阶段后续使用中发现：
  1. 业务消息尚未完整接入浏览器推送
  2. 前端缺少用户管理入口
- 对应 follow-up 已完成：
  1. 补齐任务与审批相关 Web Push 业务链路，并改为订阅感知 delivery 创建
  2. 新增 `/users` 用户管理页与导航入口
  3. 新增测试组织 / demo 用户初始化脚本，便于后续测试
- 当前文档基线已按 **Phase 5 done** 收口，下一步等待用户确认后进入更深入的重构与测试。

## 当前可用能力

- 管理员初始化、登录、JWT access / refresh 会话
- 用户管理
- 部门树与组织范围查询
- 员工档案基础 CRUD（含 `custom_fields`）
- 多岗位 / 兼职 / 虚线汇报维护
- 档案字段级权限裁剪（self / leader / delegate / HR / admin）
- 生命周期事件：入职、转岗、晋升、奖惩、离职、返聘
- 代理授权创建、撤销与按时间窗生效
- 档案治理工作台
- 任务创建、重新指派、前置依赖建模
- 严格任务状态机
- 任务评论、内部备注、评论附件、活动时间线
- 任务完成率 / 逾期率 / 负载统计
- 任务模板、模板实例化与周期任务调度
- 审批流定义、审批实例、待办审批与代理审批
- 任务 watcher / 抄送
- 任务中心列表 / 看板 / 甘特图多视图
- 通知消息落库、ARQ 入队、adapter 分发、逾期提醒扫描与状态回写
- 消息中心收件箱、消息回执与浏览器推送订阅
- 文档知识库、文档附件、embedding 重建、RAG 检索
- `@系统` / `/` 命令入口与 Tool Calling
- PWA manifest / service worker 基线
- 用户管理工作台（`/users`）
- 测试组织 / demo 用户初始化脚本
- Compose 本地开发基线（postgres / redis / backend / worker / frontend / nginx）

## 当前明确缺口（非完成项）

| 方向 | 仍未实现或需继续深化的关键能力 | 当前判断 |
| --- | --- | --- |
| 注册与账号开通 | 公开注册 / 邀请注册 / 审批式注册方案仍未定 | 待明确设计后实现 |
| HR 流程自动化 | 生命周期事件与任务模板 / 审批流联动、字段权限可视化管理增强 | 后续增强 |
| 消息渠道深化 | 消息附件、真实 Email / WebSocket 发送接入、delivery 观测增强 | 后续增强 |
| 工程质量 | 更细的重构、集成测试、E2E 路径与性能 / 稳定性验证 | 下一轮重点 |

## 当前规划焦点

当前建议优先级已经调整为：

1. **基于 Phase 5 现状做重构与测试强化**
2. **明确并落地注册能力**
3. **补齐消息附件与更真实的渠道适配**
4. **推进生命周期事件与模板 / 审批流联动**

## 重构执行补记

### Step 1 / 壳层导航重构

- 用户已确认 Step 1 通过。
- 本步骤已完成：
  1. 左侧导航按“通用模块 / 特殊模块”分组
  2. 主入口路由调整为 `/overview`、`/task-center`、`/reports`、`/people`
  3. 旧地址 `/dashboard`、`/tasks`、`/task-templates`、`/approvals`、`/users`、`/profiles` 已接入兼容跳转
  4. 新增 `TaskCenterView.vue` 与 `PeopleManagementView.vue` 两个聚合壳层，避免任务模板、用户页、档案页在重构早期失去入口
  5. `部门管理` 收紧为仅管理员可见，`人员管理` 对 `admin / hr` 可见
- 已完成验证：
  - 前端单元测试
  - 路由兼容跳转测试
  - `type-check`
  - `build`
  - `lint`
