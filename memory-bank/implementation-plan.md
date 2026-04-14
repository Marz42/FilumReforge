# Project Filum 实施计划

## 1. 计划定位

本计划基于当前真实仓库状态编写：

- **Phase A 已完成**
- **Phase 1 / Foundation 已完成**
- **Phase 2 / Collaboration & Stats 已完成**
- **Phase 3 / HR Governance & Org Modeling 已完成并通过用户验测**
- **Phase 4 / Workflow Engine & Messaging 已完成并通过用户验测**

因此，本文件不再从“仓库初始化”开始叙述，而是从 **Phase 4 之后的真实开发起点** 出发，重排后续实施路线。

## 2. 已确认约束

- 架构固定为**模块化单体**
- 前端固定为 **Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router**
- 后端固定为 **FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic**
- AI 集成固定为**官方 `openai` Python SDK**
- 通知总线统一走 `NotificationService.send(message_obj)`
- 缓存 / 队列使用 **Redis**
- 异步 worker 选型固定为 **ARQ**
- 任务相关沟通必须绑定 `task_comments`
- 每一步都必须包含测试与验证

## 3. 当前基线

### 已实现

- 认证与会话：JWT access / refresh、管理员初始化、基础角色
- 组织结构：部门树、部门负责人、范围查询
- 人事档案：一人一档、基础字段、`custom_fields JSONB`
- HR 治理：生命周期事件、字段级权限、多岗位、虚线汇报、代理授权
- 任务协同：任务、依赖、严格状态机、评论、日志、附件、统计
- 通知骨架：消息落库、delivery 记录、ARQ 入队、逾期提醒扫描
- Workflow & Messaging：模板、审批流、周期调度、消息中心、回执、watcher、多视图
- 前端：登录、部门、档案治理页、模板中心、审批中心、消息中心、Phase 4 任务工作台

### 未实现但已确认的关键缺口

- 生命周期事件与模板 / 审批流联动
- 消息附件
- 真实 Email / WebSocket / Web Push 渠道
- 文档知识库、RAG、LLM Router、浏览器推送 / PWA

## 4. 执行原则

### 4.1 固定推进顺序

后续每个阶段继续遵循：

1. **模型先行**
2. **服务层封装**
3. **异步执行器 / 适配器补齐（如阶段需要）**
4. **API 暴露**
5. **前端对接**

### 4.2 文档同步原则

- 开始一个新阶段前，先更新 `memory-bank/architecture.md` 中对应的 schema 预案
- 阶段完成且用户验测通过后，再更新 `memory-bank/progress.md`
- 若阶段边界发生变化，先更新本文件，再开始编码

### 4.3 验收闸门

- 每个阶段结束后必须停下，等待用户验证
- 用户未确认前，不进入下一阶段

## 5. 路线总览

| 阶段 | 状态 | 核心目标 |
| --- | --- | --- |
| Phase A | done | 文档与脚手架基线 |
| Phase 1 / Foundation | done | 用户、组织、档案、附件、任务基础、异步通知骨架 |
| Phase 2 / Collaboration & Stats | done | 状态机、评论留痕、日志、提醒、统计、协同页 |
| Phase 3 / HR Governance & Org Modeling | done | HR 生命周期、字段级权限、组织关系、代理授权 |
| Phase 4 / Workflow Engine & Messaging | done | 模板、审批流、自动触发、消息中心、多视图 |
| Phase 5 / Knowledge, AI Router & Experience | next | 知识库、RAG、`@系统` 路由、浏览器推送、PWA |

## 6. Phase 3 / HR Governance & Org Modeling

**当前状态**：代码已完成，自动化测试与用户手动验测均已通过。

### 6.1 目标

把当前“基础档案 CRUD”升级为可支撑真实企业管理的 HR 基座，重点解决：

- 档案全生命周期
- 字段级权限
- 多岗位与汇报关系
- 代理 / 授权

### 6.2 范围

#### 模型与迁移

- 扩展 / 新增：
  - `positions`
  - `profile_positions`
  - `reporting_lines`
  - `profile_field_definitions`
  - `profile_field_permissions`
  - `employment_events`
  - `delegations`
- 继续保留 `profiles.custom_fields`，但由字段定义与策略表驱动权限与展示

#### 服务层

- `HRLifecycleService`
  - 入职
  - 转岗
  - 晋升
  - 奖惩
  - 离职
- `ProfileFieldPolicyService`
  - 解析字段可见 / 可编辑权限
- `OrganizationRelationService`
  - 多岗位
  - 直属 / 虚线汇报
- `DelegationService`
  - 创建、启用、失效临时授权

#### API 层

- 岗位、汇报线、生命周期事件、授权管理接口
- 档案读取接口返回按当前 actor 过滤后的字段
- HR 管理接口支持“离职标记”，不提供删除员工实体的标准流程

#### 前端

- 档案页重构为多 Tab：
  - 基础信息
  - 任职关系
  - 生命周期事件
  - 敏感字段区
  - 授权与代理

### 6.3 建议实现顺序

1. **模型与 Alembic**
2. **字段权限与组织关系服务**
3. **生命周期 / 授权服务**
4. **API**
5. **前端**

### 6.4 测试与验证

- 迁移测试：新增表、索引、枚举、外键
- 权限测试：self / leader / dotted leader / HR / admin / delegate 的字段可见性
- 生命周期测试：入职、转岗、离职事件与状态流转
- API 集成测试：按角色返回不同字段
- 前端测试：敏感字段隐藏 / 展示、任职关系编辑、授权管理

### 6.5 阶段闸门

- Phase 3 已完成并满足进入 Phase 4 的前置条件

## 7. Phase 4 / Workflow Engine & Messaging

**当前状态**：代码、自动化验证与用户手动验测均已通过。

### 7.1 目标

把当前“任务协同中枢”升级为企业事务引擎，补齐：

- 模板 / SOP
- 审批流
- 自动触发
- 抄送 / 定时任务
- 消息中心与回执
- 多视图

### 7.2 范围

#### 模型与迁移

- 新增：
  - `task_templates`
  - `task_template_steps`
  - `task_template_step_dependencies`
  - `workflow_definitions`
  - `workflow_steps`
  - `workflow_instances`
  - `workflow_step_runs`
  - `task_watchers`
  - `task_schedules`
  - `notification_receipts`
- 视实现需要扩展 `attachment_links.target_type`，以支持消息附件

#### 服务层

- `TaskTemplateService`
  - 模板 CRUD
  - 实例化任务群
- `WorkflowEngineService`
  - 串行审批
  - 会签 / 或签
  - 驳回 / 打回重做
- `TaskAutomationService`
  - 前后置触发
  - 周期任务生成
- `MessageCenterService`
  - 消息回执
  - 收件箱聚合

#### Worker / Adapter

- 模板定时实例化
- 审批超时提醒
- 周期任务调度
- Email / WebSocket 渠道适配器第一版

#### API 层

- 模板管理
- 审批动作
- 消息中心 / 回执
- 任务多视图数据接口

#### 前端

- 模板管理页
- 审批中心
- 消息中心
- 任务列表 / 看板 / 甘特图

### 7.3 建议实现顺序

1. **模型与 Alembic**
2. **模板 / 审批 / 自动化服务**
3. **worker 与 adapter**
4. **API**
5. **前端**

### 7.4 测试与验证

- 模板实例化测试
- 审批路径测试：串行 / 会签 / 或签 / 驳回 / 打回
- 自动触发与周期任务测试
- 消息回执与收件箱聚合测试
- Adapter 冒烟测试
- 前端视图测试：列表 / 看板 / 甘特图渲染与交互

### 7.5 阶段闸门

- 已完成用户验测，可以进入 Phase 5

## 8. Phase 5 / Knowledge, AI Router & Experience

### 8.1 目标

在 HR / Workflow 基座稳定之后，再引入知识库、AI 路由与浏览器推送体验。

### 8.2 范围

#### 模型与迁移

- `documents`
- `document_embeddings`
- `push_subscriptions`

#### 服务层

- 文档管理与版本化
- 文档切块 / 嵌入 / 检索
- `LLMRouterService`
  - `@系统`
  - `/`
  - Tool Calling
- `BrowserPushService`
  - 浏览器订阅管理
  - Web Push 发送

#### API 层

- 文档 CRUD
- 检索接口
- AI Router 入口
- 推送订阅管理

#### 前端

- 知识库页面
- `@系统` / `/` 输入拦截
- AI 执行结果展示
- 浏览器推送授权与订阅
- PWA 安装与体验打磨

### 8.3 建议实现顺序

1. **模型与 Alembic**
2. **知识库与检索服务**
3. **LLM Router 与 push 服务**
4. **API**
5. **前端**

### 8.4 测试与验证

- 文档 CRUD 测试
- 嵌入与检索测试
- Tool Calling 合约测试
- `@系统` 路由集成测试
- 浏览器推送订阅 / 回执测试
- PWA 冒烟测试

## 9. 未来数据库优先级

建议按以下顺序补齐后续 schema：

1. `push_subscriptions`
2. `documents`
3. `document_embeddings`

## 10. 跨阶段通用规则

- `architecture.md` 必须持续维护完整 schema 与模块边界
- `progress.md` 只在阶段验测通过后更新
- 新功能优先复用现有附件、通知、权限抽象
- 所有敏感流程必须由服务层兜底，前端只做辅助限制
- 若后续需求再次改变阶段边界，先修改本文件，再开始编码
