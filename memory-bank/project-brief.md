# Project Filum — 项目身份卡片

> 🔥 HOT — 核心愿景、受众、功能边界与技术栈摘要。详细产品设计见 [`design-document.md`](./design-document.md)（历史完整版）。

| 字段 | 内容 |
|------|------|
| **项目名称** | Project Filum（FilumReforge） |
| **一句话描述** | 面向 50–100 人企业的模块化单体内部管理平台，统一承载人事、任务协同、流程/汇报、消息、知识库与 AI 指令入口 |
| **项目类型** | Web 应用（B 端后台 + PWA 基线） |
| **当前版本** | `0.89.0`（根目录 `VERSION`，SemVer） |
| **当前阶段** | 正式运营基线已交付；**TCE Phase 1–5 + 图模板设计器 D1–D3** 已落地；设计器 UX 抛光 @ 2026-06-22 |

---

## 核心愿景

在**一个模块化单体**内统一承载：

- **人**：账号、组织、人事档案、字段级权限与代理授权
- **事**：任务、模板（工作流 E）、图引擎工作流、审批、汇报、协同留痕
- **信息**：消息通知、回执、浏览器推送、知识库、AI 意图路由（`@系统` / `/`）

与通用 OA 的差异：HR 数据安全优先（字段级权限 + 关系型授权）；工作沟通绑定任务上下文，不建独立 IM；LLM 为意图路由器而非业务真相。

---

## 核心受众

| 画像 | 核心诉求 |
|------|----------|
| **Admin** | 账号、系统配置、异常兜底 |
| **HR** | 档案、生命周期、字段权限维护（不可物理删除员工） |
| **Employee / Leader** | 任务中心、汇报、消息、知识库；Leader 由组织关系推导 |
| **研发/运维** | 可验证部署路径、memory-bank 与代码对齐 |

---

## 技术栈摘要

| 层级 | 选型 | 状态 |
|------|------|------|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router + Axios | 已落地 |
| 后端 | FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic | 已落地 |
| 数据 | PostgreSQL 15+ + JSONB + `pgvector` | 已落地 |
| 队列 | Redis + **ARQ**（非 Celery） | 已落地 |
| AI | 官方 `openai` Python SDK（非 LangChain） | 已落地 |
| 部署 | Docker Compose + Nginx | 已落地 |

详情见 [`tech-stack.md`](./tech-stack.md) 与 [`architecture.md`](./architecture.md)。

---

## 功能边界

### 已交付（摘要）

Phase A–5、重构 Step 1–7、UI IA A–F、工作流图引擎 Phase 11、工作流 E 首批、视频工作流 v1（W0–W10）、Stage 2 Phase 0–6。

### 当前缺口（优先级见 `active-task.md` / `progress.md`「当前规划焦点」）

| 项 | 状态 |
|----|------|
| 邀请制注册 | done |
| 任务中心 v2 壳层（TC-P0–P2） | done @ `0.88.0` |
| 图模板单入口 / Legacy E UI 移除 | done @ `0.89.0` |
| **任务中心增强**（读模型、性能、统计、多部门模板） | **done** @ 2026-06-21 — [`plans/task-center-enhance.md`](./plans/task-center-enhance.md) Phase 1–5 |
| **图模板设计器**（D1–D3 + UX 抛光） | **done** @ 2026-06-22 |
| 公开 / 审批式注册 | 待产品决策 |
| 工作流 E 与图引擎产品级统一 | **backlog B-12**（ADR-005） |
| Ubuntu 最小回滚演练 | **暂缓**（上线前再补） |
| 真实 Email / WebSocket 外部接入深化 | 待深化 |
| 生命周期规则化默认映射 + 前端配置入口 | 待补齐 |

### 明确不做

- 独立 IM / 工作聊天系统
- LangChain 引入
- 过早微服务拆分
- 标准离职流程中的「物理删除员工」

---

## 设计原则（摘要）

1. **模块化单体优先** — 清晰模块边界，不靠部署单元切碎系统  
2. **抽象先于直连** — 通知、存储、LLM、Push 经 service/adapter/worker  
3. **HR 数据安全** — 角色 + 组织关系 + 字段级权限三层叠加  
4. **工作沟通可追溯** — `task_comments`，消息中心只做通知/回执  
5. **AI 是路由器** — Tool Calling + 后端服务为真相来源  

完整阐述见 [`design-document.md`](./design-document.md) §2。

---

## 文档地图

| 问题 | 读哪里 |
|------|--------|
| 产品目标与非目标 | 本文件 + `design-document.md` |
| 系统如何运行、模块职责 | `architecture.md` |
| 表结构、枚举、API | `data-contracts.md` |
| 编码规范 | `conventions.md` |
| 当前在做什么 | `active-task.md` |
| 阶段进度与验测 | `progress.md` |
| 排期与计划 | `plans/` |
| 部署运维 | `handbooks/`（≈ Paradigma `manuals/`） |

---

## 成功指标（定性）

- 核心工作台（任务中心、汇报、消息、人员）可稳定日常使用  
- `pytest` + 前端单测 + 关键 E2E 基线可复现  
- memory-bank 与实现可通过对齐审查验证  
