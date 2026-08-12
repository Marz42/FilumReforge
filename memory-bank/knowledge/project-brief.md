---
type: paradigma-project-brief
title: "Project Filum — 项目身份卡片"
description: "面向 50–100 人企业的模块化单体内部管理平台。"
tags:
  - project-brief
  - vision
  - filum
timestamp: 2026-07-30T01:45:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: hot
  lifecycle: stable
  update_policy: requires-human-confirmation
  epistemic_status: confirmed
  retrieval_hints:
    zh:
      - 项目愿景
      - 受众
      - 功能边界
      - 技术栈
    en:
      - "project vision"
      - audience
      - scope
      - "tech stack"
---
# Project Filum — 项目身份卡片

> 🔥 HOT — 核心愿景、受众、功能边界与技术栈摘要。详细产品设计见 [`design-document.md`](./design-document.md)（历史完整版）。

| 字段 | 内容 |
|------|------|
| **项目名称** | Project Filum（FilumReforge） |
| **一句话描述** | 面向 50–100 人企业的模块化单体内部管理平台，统一承载人事、任务协同、流程/汇报、消息、知识库与 AI 指令入口 |
| **项目类型** | Web 应用（B 端后台 + PWA 基线） |
| **最新试用候选** | `v0.93.0-rc.2`（SemVer 预发布标签；主开发线继续前进） |
| **当前阶段** | **Iteration 4 员工试用 RC** — 固定候选与后续开发分流；正式 UAT 与 I3-F 生产门禁仍待收口 |

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

### 当前缺口（优先级见 `active-task.md`、`roadmap.md` 与最近独立 session log）

| 项 | 状态 |
|----|------|
| 邀请制注册 | done（**公开注册/审批式注册不做**；未来接入邮箱发送邀请链接） |
| 任务中心 v2 壳层（TC-P0–P2） | done @ `0.88.0` |
| 图模板单入口 / Legacy E UI 移除 | done @ `0.89.0` |
| **任务中心增强**（读模型、性能、统计、多部门模板） | **done** @ 2026-06-21 — [`plans/task-center-enhance.md`](./plans/task-center-enhance.md) Phase 1–5 |
| **图模板设计器**（D1–D3 + UX 抛光） | **done** @ 2026-06-22 |
| **已发布模板可用部门治理**（ADR-020） | **done** @ 2026-07-30 — ACTIVE 单调扩权、审计历史、前端入口 |
| 公开 / 审批式注册 | **明确不做** — 仅邀请制注册；未来接入邮箱发送邀请链接 |
| 工作流 E 与图引擎产品级统一 | **done** @ `0.90.0` — B-12 Legacy E runtime 已移除 |
| 单步任务创建抄送 | **done** @ `0.90.0` — F-22 |
| 任务流多部门 copywriters 池 | **done** @ `0.90.0` — F-28 |
| 跨部门单步路由 | **done** @ `0.90.0` — F-21 |
| 通用模板链 + 防环 | **done** @ `0.90.0` — F-23 |
| 部门定时图模板 · 附件预览 | **done** @ `0.90.0` — F-24 / F-25 |
| **F-29 管理员任务归档** · Admin 跟踪督办 · 逾期延期 | **done** @ `0.91.0` |
| Paradigma v0.7.0 CLI runtime · Context/计划/日志治理 | **done** @ upstream `3422ecf`；版本路径兼容见 KI-013 |
| Task Center P0–P2 审计修复 · 模板任务防自审 | **done** @ `0.92.1` |
| 模板引擎解耦 Phase 1 | **done** @ Unreleased — tags / capabilities / archive / ACTIVE lock |
| 模板引擎解耦 Phase 2 首批 | **implemented · pending UAT** — structured authoring |
| 图引擎 Iteration 1–3-F | **工程实现完成 · 生产准入 gated** — 目标环境/7 天/31 项证据待补 |
| 图引擎 Iteration 4-A–E | **done** — Handler、版本交付、通知策略、领域中立 capability snapshot / task capability |
| 2026-08 安全上线加固 | **engineering done · production verification pending** — 六项扫描发现已修复并回归；目标环境准入见上线 checklist |
| 图引擎 Iteration 4 Preflight | **done** — ADR-018 / 文档对齐 / 前端第一批稳定化 |
| 决策对象与参与者重叠 | **ADR-019 implemented** — 集合负责人可贡献并推进；同版本独立验收仍职责分离 |
| 系统管理员仅维护、不参与业务 | **产品边界 confirmed · implementation deferred** — KI-011，不属于 I4 |
| Ubuntu 最小回滚演练 | **暂缓**（上线前再补） |
| 真实 Email / WebSocket 外部接入深化 | 待深化 |
| 生命周期规则化默认映射 + 前端配置入口 | 待补齐 |

### 明确不做

- 独立 IM / 工作聊天系统
- LangChain 引入
- 过早微服务拆分
- 标准离职流程中的「物理删除员工」
- 公开自助注册 / 审批式注册（仅保留邀请制注册）

---

## 设计原则（摘要）

1. **模块化单体优先** — 清晰模块边界，不靠部署单元切碎系统  
2. **抽象先于直连** — 通知、存储、LLM、Push 经 service/adapter/worker  
3. **HR 数据安全** — 角色 + 组织关系 + 字段级权限三层叠加  
4. **工作沟通可追溯** — `task_comments`，消息中心只做通知/回执  
5. **AI 是路由器** — Tool Calling + 后端服务为真相来源  
6. **模板领域中立** — 业务流程由普通图模板组合通用能力，Runtime 不按业务名称、tags、模板 code 或 UI Profile 分支

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
| 阶段进度与验测 | `logs/progress/summary.md` + 最近独立 session log |
| 排期与计划 | `plans/` |
| 部署运维 | `knowledge/manuals/`（≈ Paradigma `manuals/`） |

---

## 成功指标（定性）

- 核心工作台（任务中心、汇报、消息、人员）可稳定日常使用  
- `pytest` + 前端单测 + 关键 E2E 基线可复现  
- memory-bank 与实现可通过对齐审查验证  
