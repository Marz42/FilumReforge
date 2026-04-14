# Project Filum 进度记录

## 当前阶段状态

| 阶段 | 状态 | 结论 |
| --- | --- | --- |
| Phase A / 文档与工程基线 | done | 文档入口、脚手架、基础编排已完成 |
| Phase 1 / Foundation | done | 用户、组织、档案、附件、任务基础、异步通知骨架已完成并通过用户点击验证 |
| Phase 2 / Collaboration & Stats | done | 状态机、评论留痕、审计日志、ARQ 提醒 worker、统计与协同任务页已完成并通过用户简单测试 |
| Phase 3 / HR Governance & Org Modeling | done | 代码已实现、修复 PostgreSQL 迁移命名问题，并通过用户手动验测 |
| Phase 4 / Workflow Engine & Messaging | next | 尚未开始，已可作为下一阶段推进 |
| Phase 5 / Knowledge, AI Router & Experience | pending | 尚未开始，排在 HR 与 Workflow 之后 |

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

### Phase 3 验测补记

- Phase 3 代码已经完成，自动化验证链路已全部通过。
- 已完成的自动化验证包括：后端 `pytest`、后端 `compileall`、前端 `test:unit`、`type-check`、`build`、`lint`。
- 用户在首次手动验测时发现 PostgreSQL 外键名超长，导致 `alembic upgrade head` 与 Compose backend 启动失败。
- 修复内容：
  1. 缩短 `profile_field_permissions` 的外键名，满足 PostgreSQL 63 字符限制
  2. 新增 metadata / Alembic identifier 长度回归测试
  3. 在真实 PostgreSQL、backend 容器和 Compose backend 服务路径上完成复测
- 用户已按原复现步骤重新验证，确认问题通过。

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
- 通知消息落库、ARQ 入队、逾期提醒扫描与状态回写
- Compose 本地开发基线（postgres / redis / backend / worker / frontend / nginx）

## 当前明确缺口（非完成项）

| 方向 | 仍未实现的关键能力 | 目标阶段 |
| --- | --- | --- |
| HR 流程自动化 | 生命周期事件与任务模板 / 审批流联动、字段权限可视化管理增强 | Phase 4 |
| Workflow 引擎 | 模板 / SOP、审批流、自动触发、抄送、周期任务 | Phase 4 |
| 消息中心 | 真实渠道适配器、消息回执、消息附件、独立消息收件箱 | Phase 4 |
| 前端体验 | 看板、甘特图、消息中心页面 | Phase 4 |
| Knowledge / AI | 文档库、RAG、`@系统` / `/` 路由、Tool Calling | Phase 5 |
| Push / PWA | 浏览器推送订阅、PWA 安装与体验打磨 | Phase 5 |

## 当前规划焦点

下一阶段优先级已经调整为：

1. **开始 Phase 4 / Workflow & Messaging 设计与实施**
2. **开始 Phase 4 / Workflow & Messaging**
3. **最后进入 Knowledge / AI / Push**

当前已经确认 HR 治理基座可用，后续可以按计划进入模板、审批与消息中心。
