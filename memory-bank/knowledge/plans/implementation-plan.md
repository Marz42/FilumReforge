---
type: paradigma-plan
title: 实施计划主线
description: "FilumReforge 总体实施计划。"
tags:
  - plan
  - 实施计划
timestamp: 2026-09-10T23:49:41+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: decision
  plan_status: in-progress
  retrieval_hints:
    zh:
      - 实施计划
    en:
      - implementation
  relations:
    related_to:
      - ./2026-09-10-integrated-development-and-human-gates-plan.md
---
# Project Filum 实施计划

> **下一轮执行入口（2026-09-10）**：[开发与 Human Gates 整合方案](./2026-09-10-integrated-development-and-human-gates-plan.md) 将本文件 A–F 工作流、P0 审查问题、I3-F/I5/I6、业务验收和延期方向映射为 W00～W16。跨计划顺序、责任、证据和人工批准以整合方案为入口，精确契约继续参照专题。方案编写不表示代码修复或外部 Gate 已完成。

## 1. 计划定位

本计划基于当前真实仓库状态编写：

- **Phase A 已完成**
- **Phase 1 / Foundation 已完成**
- **Phase 2 / Collaboration & Stats 已完成**
- **Phase 3 / HR Governance & Org Modeling 已完成并通过用户验测**
- **Phase 4 / Workflow Engine & Messaging 已完成并通过用户验测**
- **Phase 5 / Knowledge, AI Router & Experience 已完成并完成后续补丁**

因此，本文件不再描述“如何实现 Phase 5”，而是从**当前已交付基线**出发，规划下一轮重构、测试与补缺工作。

**当前执行位置**: **工作流图引擎 Iteration 4 A–E、F-05、Iteration 5-A～E、KI-015 请求侧缺口遥测与 2026-08 安全修复均已完成本地工程实现**；`v0.93.0-rc.3` 已在 `21975a6` 固定。5-E 已提供投影优先读取、动态回退和严格 canary，隔离 PostgreSQL/Redis 上完成 22 项方言测试、97/28/282 最终全量重建、407/407 full shadow、fallback on 8/8 与 strict 9/9 真实 UAT，以及备份恢复和 `04→03→04` 演练。KI-015 进一步补齐三类列表 surface 的缺口分类、结构化日志、Admin Operations 诊断和隐私回归。KI-014 Phase A/B 工程已完成：metadata/index 对齐、TaskStatus 双读/小写写入及 `20260827_01` expand migration 已通过 SQLite/PostgreSQL 往返；真实数据兼容观察与独立 contract migration 仍待目标预发。生产关闭 fallback、真实环境日志告警、ROOT shell 收缩和 Iteration 6 仍受真实预发持续观察、I3-F 连续门禁及人工批准约束。目标环境 I4/设计器/S-01/KI-009 人工 UAT与生产 TLS/secret 仍并行推进。KI-011 按用户决定暂不推进。详见 [`2026-08-26-ki014-schema-drift-remediation-plan.md`](./2026-08-26-ki014-schema-drift-remediation-plan.md)、[`2026-08-11-f05-iteration5-6-sequencing-plan.md`](./2026-08-11-f05-iteration5-6-sequencing-plan.md) 与 [`../contracts/projection-contract.md`](../contracts/projection-contract.md)。

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

- 认证与会话：JWT access token + HttpOnly refresh cookie、管理员初始化、基础角色；**邀请制注册**（邀请创建 / 预览 / 接受 / 撤销，`backend/app/api/routes/auth.py`）
- 组织结构：部门树、部门负责人、范围查询
- 人事档案：一人一档、基础字段、`custom_fields JSONB`
- HR 治理：生命周期事件、字段级权限、多岗位、虚线汇报、代理授权；审批定义显式绑定后的 worker 触发与状态回写已有实现。Legacy E 任务模板绑定已被服务拒绝，图模板替代入口由整合方案 W10 补齐，再做规则化 UI。
- 任务协同：任务、依赖、严格状态机、评论、日志、附件、统计
- 通知骨架：消息落库、delivery 记录、ARQ 入队、adapter 分发、逾期提醒扫描
- Workflow & Messaging：模板、审批流、周期调度、消息中心、回执、watcher、多视图
- 工作流重构图引擎：手动任务 graph dual-write、多节点推进、Context 写回、条件边（含 else）、Notice Node、智能抄送候选、Wait-Any、深度打回、outbox、**任务中心列表 graph-first**（`TASK_CENTER_V2_ENABLED` 默认 `true`，`backend/app/core/config.py`）、迁移 CLI（Phase 11-A–11-F）；详见 `memory-bank/logs/progress/summary.md`、最近独立 session log 与 `memory-bank/knowledge/plans/workflow-refactor-implementation-plan.md`
- Knowledge / AI：文档库、embedding、RAG、`@系统` / `/` 路由、Tool Calling
- Push / PWA：浏览器订阅管理、Web Push adapter、manifest、service worker
- 前端：登录、分组导航壳层、总览模块（看板 / 公告 / 待办 / 跟踪）、任务中心聚合入口、汇报中心入口、消息中心、设置模块、知识库、统一人员工作台、部门管理；Playwright mock / live E2E 基线（Phase 11-G）
- 消息中心深化：消息附件绑定、多维筛选与投递失败展示（Stage 2 Phase 4）
- 测试辅助：测试组织 / demo 账号脚本

### 未实现但已确认的关键缺口

- **访客公开自助注册**与**审批式注册**（**明确不做**；邀请制已落地，未来接入邮箱发送邀请链接）
- 生命周期事件的**规则化默认映射**与**前端结构化配置入口**（显式绑定 + worker 触发已落地）
- 真实 Email / WebSocket 对外发送接入深化（当前仍为最小 / 占位适配器为主）
- **Legacy E 历史表族清理**：B-12 已移除 `task_templates` 对外 API、实例化入口与旧调度路径；表/ORM/未挂载服务暂保留用于历史数据兼容，后续需明确迁移和删除策略
- 更系统的重构、集成测试、E2E 扩面；**Ubuntu 最小回滚演练**；docker-gui / Playwright 基线定期刷新（历史基线见冻结的 `logs/progress/0000-legacy-progress.md`，新证据由 Checkpoint 持有）

独立迭代（不并入 Stage 2 串行表内阶段）的积压主题已汇总至 `memory-bank/knowledge/plans/improvements-stage2-implementation-plan.md` **§11**。

## 4. 执行原则

### 4.1 固定推进顺序

后续每个阶段继续遵循：

1. **模型先行**
2. **服务层封装**
3. **异步执行器 / 适配器补齐（如阶段需要）**
4. **API 暴露**
5. **前端对接**

### 4.2 文档同步原则

- 开始一个新阶段前，先更新 `memory-bank/knowledge/contracts/data-contracts.md`（schema 预案）与 `memory-bank/knowledge/architecture.md`（模块/流程事实）
- 每个阶段完成后先更新 `data-contracts.md`（若有 schema 变化）与 `architecture.md`，再创建 `memory-bank/logs/progress/YYYY-MM-DD-<task>.md` 独立 session log
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

### 6.2 工作流 B：注册能力

**已决策**

- 公开自助注册、审批式注册：**明确不做**。
- 当前仅保留**邀请制注册**（管理端生成邀请链接）。
- 未来：接入邮箱发送邀请链接（当前为管理端复制链接手动分发的 MVP）。

**实施顺序**

1. 未来接入 SMTP / 邮件网关服务，邀请创建后自动发送邮件
2. 邀请链接支持过期时间、一次性使用等完整安全策略

**测试出口**

- 邮箱发送失败 / 退信处理、邀请过期、重复使用检测

### 6.3 工作流 C：HR 生命周期与事务引擎联动

**目标**

把当前“显式绑定目标后异步触发”的生命周期事件，升级为“规则化默认联动 + 可配置事件驱动任务 / 审批流”。

**重点方向**

- 入职自动生成模板任务
- 离职自动生成交接 / 回收 / 审批流
- 晋升 / 转岗驱动权限、岗位、模板和消息联动
- 先补 Legacy E 下线后的图模板显式绑定替代入口，再将联动目标下沉为可配置规则与前端入口（整合方案 W10）

**测试出口**

- 生命周期事件到任务 / 审批实例的端到端联动测试
- 幂等与重复触发保护

### 6.4 工作流 D：消息中心深化

**目标**

在现有消息总线稳定的基础上，补齐真实业务使用深度。

**重点方向**

- Email / WebSocket 外部集成
- Push 失败可观测性
- 前端消息中心更细粒度筛选和状态展示
- 更完整的消息生命周期观测与重试管理

**测试出口**

- delivery 状态一致性
- 附件绑定与权限控制
- adapter 失败 / 重试 / 过期订阅处理

### 6.5 工作流 E：任务模板与多步骤协作（图引擎主线）

**目标**

以 `WorkflowGraphTemplate` / 图运行时作为唯一产品入口，持续完善领域中立的多步骤协作、模板治理和结构化设计器。Legacy E 只保留历史兼容与迁移职责，不再承接新业务功能。

**当前状态**

- B-12 已移除 Legacy E 对外入口；图模板、图 Run 与节点实例是当前产品主线
- 图模板设计器已具备结构化 authoring、拓扑校验、草稿/发布、导入导出和 dry-run
- 已发布模板具备 `global / departments` 可用范围、部门经理治理与审计历史
- Iteration 4 已完成 HumanTask、Approval、Deliverable、Notification Handler 化与领域中立 capability snapshot
- Iteration 4 UAT Preflight、数据治理审计和 S-01 样本准备已落地，正式人工 UAT 尚待目标环境完成

**已确认决策**

1. 视频能力是普通模板能力组合，不允许 Runtime 按模板编码、`run_kind` 或视频节点键分支
2. 集合确认、交付验收、正式审批按 ADR-019 分别定义参与者重叠规则
3. 结构化表单是默认 authoring 入口；高级 JSON 只作兼容与精细配置
4. Legacy E API/Service 不再恢复为产品入口，其表族清理只能在 Iteration 6 单独批准后执行

**当前开放项**

1. 完成 RC2、Iteration 4、设计器 Phase 2、S-01 与 KI-009 人工 UAT；本地自动化 UAT 不代签
2. 把已通过的 5-A～E PostgreSQL/rebuild/full shadow/strict canary 流程复制到真实预发并积累持续样本；补齐 Iteration 3-F 7 天与 31/31 证据
3. `run_kind` / M-09 dual-read 收窄继续等待生产证据与单独策略，不抢跑 Iteration 6
4. 生命周期规则化默认映射和前端配置入口作为后续业务增强，不回填到 Legacy E
5. KI-015 strict 投影缺口请求侧遥测已完成；KI-014 Phase A/B 已完成，下一门禁是含真实数据的目标预发只读复核与 compatibility observation，之后才执行独立 contract；再处理 KI-016 logout 在途请求，KI-017 包体优化进入前端性能批次

**测试出口**

- 工程回归：backend 全量 pytest + compileall；frontend Vitest + type-check + build + 只读 lint
- 人工 UAT：使用真实部门负责人、执行人和验收人，记录模板、Run/Task ID、账号与时间
- 目标环境：PostgreSQL/Redis 严格模式与上线 checklist；本地 SQLite 通过不得替代

### 6.6 工作流 F：图引擎运行时深化（已完成主干）

**目标**

把 workflow graph 从“后端可运行原型 + 兼容 Task 投影”推进到具备条件路由、上下文写回、完整节点类型与 graph-first 读侧的稳定运行时。

**当前状态**

- Phase 2–11-G 主干已完成：图模板/实例 schema、dual-write、交付/验收/返工、接单/协商/转办、多节点推进、Wait-All/Wait-Any、Context 写回、条件边、Notice Node、智能抄送、深度打回、outbox、迁移 CLI 与 graph-first 读取
- `TaskService` / `TaskCenterService` 仍使用兼容 `Task` 作为 UI 投影载体，但默认读取会优先解析 graph runtime，未命中时才 legacy fallback
- B-12 已移除 Legacy E 对外入口；旧表族与服务代码暂留作历史兼容，不代表双产品入口仍并存

**后续深化**

1. 补齐 Iteration 3-F 与 5-A～E 的真实预发迁移、重建、shadow、严格 canary 和运维持续证据
2. 生产先以 5-E fallback 开启部署；证据齐全并获单独批准后分批关闭 fallback
3. 完成稳定观察，确认 fallback 命中、差异、lag 与异常 Run 达标
4. 仅在再次单独批准后进入 Iteration 6，归档/删除 Legacy E 与兼容锚点
5. 主线闭环后再排生命周期规则化、设计器增强等新能力

**测试出口**

- backend：保持条件分支、Context 冲突、Notice、Wait-Any、幂等完成、graph snapshot 与迁移回归
- frontend：保持任务中心、详情、设计器和视频流程的 unit + Playwright mock/live 双轨覆盖

## 7. 跨阶段通用规则

- `architecture.md` 必须持续维护完整 schema 与模块边界
- 阶段验测通过或关键 follow-up 收口后写 Checkpoint；版本、Batch 或人工审计需要时再创建 session log；旧 `logs/progress/0000-legacy-progress.md` 不得修改
- 新功能优先复用现有附件、通知、权限抽象
- 所有敏感流程必须由服务层兜底，前端只做辅助限制
- 若后续需求再次改变阶段边界，先修改本文件，再开始编码

# Status

Machine status: in-progress.
