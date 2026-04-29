# Project Filum 实施计划

## 1. 计划定位

本计划基于当前真实仓库状态编写：

- **Phase A 已完成**
- **Phase 1 / Foundation 已完成**
- **Phase 2 / Collaboration & Stats 已完成**
- **Phase 3 / HR Governance & Org Modeling 已完成并通过用户验测**
- **Phase 4 / Workflow Engine & Messaging 已完成并通过用户验测**
- **Phase 5 / Knowledge, AI Router & Experience 已完成并完成后续补丁**

因此，本文件不再描述“如何实现 Phase 5”，而是从**当前已交付基线**出发，规划下一轮重构、测试与补缺工作。

**当前执行位置**: 当前主线已经从 Step 7 收口转入 **工作流 E 后续深化 / 回归 / 部署工程化 / 文档对齐**；最近一轮已完成模板管理补丁、设置模块拆分与总览 / 任务中心体验收口。本轮新实施周期统一记录在 `memory-bank/improvements-stage2-implementation-plan.md`。

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

- 认证与会话：JWT access token + HttpOnly refresh cookie、管理员初始化、基础角色
- 组织结构：部门树、部门负责人、范围查询
- 人事档案：一人一档、基础字段、`custom_fields JSONB`
- HR 治理：生命周期事件、字段级权限、多岗位、虚线汇报、代理授权
- 任务协同：任务、依赖、严格状态机、评论、日志、附件、统计
- 通知骨架：消息落库、delivery 记录、ARQ 入队、adapter 分发、逾期提醒扫描
- Workflow & Messaging：模板、审批流、周期调度、消息中心、回执、watcher、多视图
- Knowledge / AI：文档库、embedding、RAG、`@系统` / `/` 路由、Tool Calling
- Push / PWA：浏览器订阅管理、Web Push adapter、manifest、service worker
- 前端：登录、分组导航壳层、总览模块（看板 / 公告 / 待办 / 跟踪）、任务中心聚合入口、汇报中心入口、消息中心、设置模块、知识库、统一人员工作台、部门管理
- 测试辅助：测试组织 / demo 账号脚本

### 未实现但已确认的关键缺口

- 公开注册 / 邀请注册 / 审批式注册
- 生命周期事件与模板 / 审批流联动
- 消息附件
- 真实 Email / WebSocket 对外发送接入深化
- 更系统的重构、集成测试、E2E 和稳定性验证

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
- 当前后续增强周期统一按 `memory-bank/improvements-stage2-implementation-plan.md` 推进
- 从 Stage 2 开始，每个阶段完成后都必须先更新 `memory-bank/architecture.md` 记录实现事实，再更新 `memory-bank/progress.md` 记录状态与验证结论
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
| Phase 5 / Knowledge, AI Router & Experience | done | 知识库、RAG、`@系统` 路由、浏览器推送、PWA |

## 6. 下一轮工作流

### 6.1 工作流 A：重构与测试强化

**目标**

在不引入大范围功能漂移的前提下，提高当前 Phase 5 基线的可维护性、可测试性与稳定性。

**重点方向**

- 当前批次：Step 7 已完成并通过用户验测，当前重构成果已收口到 memory-bank、README 体系与全量验证结果；后续增强以新的工作流推进，不再回到 Step 7 收口语境
- 当前批次已补齐的体验修正：总览页任务中心跳转与快捷入口优化、消息中心与设置拆分、任务中心主标签精简、登录页默认凭据清空
- 收敛前端大型页面的状态与副作用
- 梳理服务层边界，减少跨服务耦合
- 明确通知总线、AI Router、知识库、档案治理等关键链路的集成测试覆盖
- 为 demo 数据、Push、AI、worker 增加更稳定的回归路径

### 6.1A 当前已识别的前端治理主题

- 岗位编辑器：基于现有 `positions` / `profile_positions` / `reporting_lines` 能力补一层结构化工作台，输出岗位基础信息、权限能力、可见范围与引用关系，供人员工作台、生命周期事件与模板规则复用。
- 避免直接编辑 JSON：业务表单默认走结构化编辑器，JSON 仅保留为“高级入口”或只读预览；推进顺序优先覆盖人员工作台、档案治理和模板设计器中的原始 JSON 文本域。
- 模板前端迭代：把模板页拆成“模板清单 / 基本信息 / 步骤设计 / 实例运行态 / 调度 / 高级 JSON”六个稳定视区，已实例化模板默认锁定结构并引导新建版本，而不是继续堆叠单页交互。

**测试出口**

- 后端：服务测试、API 集成测试、worker 测试、边界错误路径
- 前端：关键工作台单测、路由 / 权限回归、消息与推送回归
- 视需要补充端到端 smoke 路径

### 6.2 工作流 B：明确并落地注册能力

**当前状态**

- `/users` 已有后端与管理端前端入口
- **访客自助注册仍未实现**

**待决策范围**

1. 公开自助注册
2. 邀请式注册
3. 审批式注册
4. 继续保持仅管理端建用户

**实施顺序**

1. 明确业务边界与默认角色 / 状态
2. 补模型或邀请 token（如方案需要）
3. 服务层封装
4. API 暴露
5. 前端登录 / 注册页联动

**测试出口**

- 重复邮箱、未激活状态、越权、邀请过期、审批通过 / 拒绝等路径

### 6.3 工作流 C：HR 生命周期与事务引擎联动

**目标**

把当前“记录事件”升级为“事件驱动任务 / 审批流”。

**重点方向**

- 入职自动生成模板任务
- 离职自动生成交接 / 回收 / 审批流
- 晋升 / 转岗驱动权限、岗位、模板和消息联动

**测试出口**

- 生命周期事件到任务 / 审批实例的端到端联动测试
- 幂等与重复触发保护

### 6.4 工作流 D：消息中心深化

**目标**

在现有消息总线稳定的基础上，补齐真实业务使用深度。

**重点方向**

- 消息附件
- Email / WebSocket 外部集成
- Push 失败可观测性
- 前端消息中心更细粒度筛选和状态展示

**测试出口**

- delivery 状态一致性
- 附件绑定与权限控制
- adapter 失败 / 重试 / 过期订阅处理

### 6.5 工作流 E：结构化任务模板与多步骤协作

**目标**

在已完成“模板实例驱动的逐步激活”“多人扇出 / 汇聚”“结构化模板设计器首版”的基础上，继续把工作流 E 收口为可回归、可部署、可持续扩展的稳定能力，使模板可以稳定覆盖“参与选题会后多人提交”“前置完成后再激活下游”的实际协作场景。

**当前状态**

- 后端已完成 `TaskTemplateInstance` / `TaskTemplateStepRun`、`assignment_mode` / `join_mode`、`tasks` 对模板运行态的回链字段，以及对应 Alembic 迁移
- `TaskTemplateService` / `TaskService` 已切到“实例驱动激活”模式：实例化只激活首批就绪步骤，任务完成后会自动推进下游
- API 已补结构化步骤字段、模板实例快照与实例列表接口
- `TaskTemplatesView.vue` 已升级为结构化设计器首版，支持步骤增删改、JSON 导入、实例快照与已有模板编辑
- 当前重心已从“从 0 到 1 实现”切到“全量回归、部署收口、模板管理深化与生命周期联动”

**已确认决策**

1. 激活策略采用“模板实例 / 步骤运行态独立建模 + 仅为已激活步骤创建真实任务”，不采用“预创建全部任务再锁定”
2. 多人汇聚规则首版支持可配置 `all` / `any`
3. 设计器首版采用结构化表单，不做完整拖拽式流程图；保留 JSON 预览 / 导入作为高级入口

**下一批顺序**

1. 验证与部署收口
	- 执行 backend / frontend 全量回归，确认工作流 E 首批实现与现有基线没有回归冲突
	- 持续同步 `memory-bank`、README 与云服务器部署指南，避免文档继续漂移
	- 已完成的部署工程化产物（可直接使用）：
	  - `backend/scripts/start-prod.sh`：生产启动脚本，无 `--reload`，支持 `BIND_HOST` / `WORKERS` 调参
	  - `backend/Dockerfile.prod`：生产后端镜像，仅安装 core 依赖
	  - `frontend/Dockerfile.prod`：多阶段构建，`nginx:alpine` 托管静态产物
	  - `frontend/nginx.frontend.conf`：SPA 感知的缓存策略（sw.js、assets、fallback）
	  - `infra/docker/docker-compose.prod.yml`：生产 Compose，无 bind mount，无 `--reload`，Redis 持久化
	  - `infra/docker/.env.prod.example`：Compose 生产 env 模板
	  - `backend/.env.production.example`：systemd 部署 env 模板
	  - `infra/nginx/nginx.prod.conf`：host-level Nginx 模板，含 HTTPS/TLS、gzip、SPA fallback、安全 headers
	  - `infra/nginx/nginx.compose.prod.conf`：Compose 内部 gateway Nginx 配置
	  - `scripts/check-release.sh`：发布前全量验证脚本（pytest、compileall、type-check、build、lint、alembic check）
	- 近期已完成核心回归：backend `pytest -q`、`python -m compileall app tests`，frontend `npm run test:unit -- --run`、`npm run type-check`
	- 发布前一键校验与上线演练仍待执行；执行命令：`bash scripts/check-release.sh`
2. 模板管理深化
	- 继续补模板 / 调度更完整的管理动作与更强设计器校验，而不是停留在“可创建 / 可实例化”的首版能力
3. 业务联动
	- 将生命周期事件与任务模板 / 审批流联动，形成真正的事件驱动事务入口
4. 稳定性与测试强化
	- 扩展 workflow E 相关 API / 集成测试与更大范围的前端交互回归

**测试出口**

- 当前已完成验证：backend `pytest -q /app/tests/test_services.py /app/tests/test_api.py`、`pytest -q`、`python -m compileall app tests`；frontend `npm run test:unit -- --run tests/TaskTemplatesView.spec.ts`、`npm run test:unit -- --run`、`npm run type-check`
- 发布前补充验证：frontend `npm run build`；如需一键收口，执行 `bash scripts/check-release.sh`
- 前端 lint 若仅做只读校验，优先执行 `npm exec oxlint .` 与 `npm exec eslint .`，避免 `npm run lint` 的 `--fix` 副作用混入回归结果

## 7. 跨阶段通用规则

- `architecture.md` 必须持续维护完整 schema 与模块边界
- `progress.md` 在阶段验测通过或关键 follow-up 收口后更新
- 新功能优先复用现有附件、通知、权限抽象
- 所有敏感流程必须由服务层兜底，前端只做辅助限制
- 若后续需求再次改变阶段边界，先修改本文件，再开始编码
