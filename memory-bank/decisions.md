# 架构决策记录 (ADR)

> 🧊 COLD — 理解「为什么这么设计」时读取。新决策按模板追加。

---

## ADR 模板

```markdown
### ADR-NNN: [标题]

**日期**: YYYY-MM-DD HH:mm
**状态**: 提议 / 已采纳 / 已废弃

**背景** — 为什么需要决策  
**决策** — 我们决定怎么做  
**备选方案** — 未选方案及原因  
**后果** — 正面/负面影响
```

---

## ADR-001: 模块化单体架构

**日期**: 2025（Phase A 起）  
**状态**: 已采纳

**背景**  
50–100 人企业内部系统，HR、工作流、消息、AI 共享权限与组织模型。

**决策**  
坚持模块化单体；用 service 边界与 DB 约束管理复杂度，不拆微服务。

**后果**  
部署简单、事务一致性好；单仓体积与测试面随功能增长需持续治理。

---

## ADR-002: 异步 Worker 选型 ARQ

**日期**: Phase 2  
**状态**: 已采纳

**背景**  
后端已是 async 栈，已有 Redis。

**决策**  
使用 ARQ 替代 Celery 作为 worker 实现。

**后果**  
轻量、与 FastAPI async 契合；生态小于 Celery，当前体量足够。

---

## ADR-003: AI 集成官方 openai SDK

**日期**: Phase 5  
**状态**: 已采纳

**背景**  
需要 Tool Calling 与 Pydantic schema 对接。

**决策**  
使用官方 `openai` Python SDK；不引入 LangChain。

**后果**  
行为可控、抽象层少；工具编排需自研 `LLMRouterService`。

---

## ADR-004: 任务协同不建独立 IM

**日期**: Phase 2  
**状态**: 已采纳

**背景**  
工作讨论需可追溯、绑定业务上下文。

**决策**  
讨论与附件进 `task_comments`；消息中心只做通知/回执。

**后果**  
无实时聊天体验；审计与权限模型清晰。

---

## ADR-005: 工作流双轨（图引擎 + 工作流 E）

**日期**: 工作流重构 Phase 2–11  
**状态**: 已采纳（过渡态）

**背景**  
图引擎 `WorkflowGraphTemplate` 与 legacy `task_templates`（工作流 E）并存。

**决策**  
手动任务 graph dual-write；任务中心读路径默认 graph-first（`TASK_CENTER_V2_ENABLED=true`）；E 模板实例化保持独立直至产品级统一。

**后果**
两套入口需文档与测试双覆盖；迁移 CLI 与 feature flag 回退路径已建立。  
**2026-06-23 更新**（ADR-009）：**B-12 目标明确为删除 Legacy E runtime、仅保留图引擎**；单步抄送 **F-22**、跨部门 **F-21** 已立项。前端单入口 + 图模板设计器已完成；E API **待 P0 删除**。

---

## ADR-006: 视频工作流 v1 运行时与 Feature 开关（W0）

**日期**: 2026-05（W0）  
**状态**: 已采纳  
**详情**: [`plans/workflow-video-v1-w0-adr.md`](./plans/workflow-video-v1-w0-adr.md)

**背景**  
视频 v1 需批次选题会、表单引擎、按题 fork，且不能破坏现有 E 路径。

**决策**

1. 不新建第三套运行时；新发起以 `workflow_graph_*` + `Task` 为主
2. 选题会为图模板 `topic_meeting_batch_v1`，无独立导航入口
3. `WORKFLOW_GRAPH_TEMPLATE_ENGINE_ENABLED` 默认 `false`，仅控制新图模板实例化 API
4. 策略模块：`backend/app/core/workflow_video_policy.py`

**后果**  
W1–W7 期间生产行为与开关关闭时一致；启用开关须配套 seed 与前端 Dialog。

**非决策（留待后续）**

- `instantiate_template` 内部转调 graph（W10 可选）
- 单 Run 内多选题 DAG（已明确不做）

---

## ADR-008: 图模板设计器 authoring 路径

**日期**: 2026-06-21  
**状态**: 已采纳

**背景**  
TCE Phase 5 移除 Legacy E 前端后，图模板仍依赖 seed 脚本维护；需 UI authoring 且不恢复 E 结构化设计器。

**决策**

1. 图模板 authoring 走 `WorkflowGraphTemplateAdminService` + `GraphTemplateDesignerView`（表单 + 表格，非拖拽 DAG）
2. 新建默认 **clone preset**；有实例时结构锁定，改结构须 fork version
3. D2 起边/routing_rules/拓扑校验纳入 draft save；D3 补 DAG 预览、dry-run、JSON 导入导出、Run 统计
4. Legacy E 设计器 **不恢复**；E 后端删除独立跟踪 **B-12**

**后果**  
与 ADR-005 互补：用户可见模板维护单轨图引擎；E runtime 仍并存至 B-12。测试覆盖 `test_workflow_graph_template_designer_d{1,2,3}` + topology。

---

## ADR-007: Memory-Bank Paradigma 对齐

**日期**: 2026-06-17  
**状态**: 已采纳（Phase 0–4 已完成）

**背景**  
Agent 协作需知识温度分层与统一 Update 工作流。

**决策**  
采用 Paradigma 协议；保留 `handbooks/` 路径（≈ `manuals/`）；`VERSION` 从 `0.87.0` 起 SemVer；不采用 `.template.md` 双文件机制。

**后果**  
文档迁移分 Phase 进行；`design-document`/`tech-stack` 保留只读完整版。

---

## ADR-009: 单步任务产品边界与能力差距决策

**日期**: 2026-06-23  
**状态**: 已采纳  
**背景**: 设计意图对照代码审查（单步任务 G-01–G-06）；需统一产品边界与 roadmap 排期。

**决策**

1. **任务中心两类任务**：**单步任务**（「建立任务」· `MANUAL` · `graph_manual`）与 **任务流任务**（图模板实例化 · `WorkflowGraph*`）。
2. **单步发布范围**：依 **`Department.manager_id` 管辖子树**（含 Admin/HR 全员、部门 `PUBLISH_ORG_TASK` 本部门）；**不**改用 `ReportingLine`。
3. **跨部门单步（G-01）**：列为 **新产品能力 F-21**（部门路径路由 + 路径节点自动 CC）；深树性能记技术债。
4. **跨部门协作远期（G-02）**：走 **「项目组」**（多部门成员编组），非组织树 hack；单独立项 P4。
5. **自派任务（G-03）**：**不属于任务中心**；个人待办走 **`task_memos` 备忘**，不扩展「建立任务」给普通员工自派。
6. **抄送（G-04）**：手动建立单步任务 **必须支持抄送人** — **F-22**（`TaskCreateRequest.watcher_user_ids` + 发布 Dialog）。
7. **Runtime（G-05）**：**移除 Legacy E runtime**，任务模板与实例化 **仅图引擎** — **B-12**（强化 ADR-005 后果）。

**后果**  
Roadmap P0=B-12；P1=F-22；P2=F-21；文档见 [`roadmap.md`](./roadmap.md) · [`domains/task-center.md`](./domains/task-center.md) §6。

---

## ADR-010: 任务流产品边界与能力差距决策

**日期**: 2026-06-23  
**状态**: 已采纳  
**背景**: 任务中心三大模块之 **任务流**；设计意图对照代码（W-01–W-09）及多部门/fork 讨论。

**决策**

1. **统一入口**：任务流仅 **图模板实例化**（`POST .../workflow-graph/templates/{id}/runs`）；Legacy E 删除见 **B-12**。
2. **多部门共用模板**：批次 **B-16 `instance_department`** + 制作链 **`department_pools`**（固定目标部门 C 在 **制作模板 config** 定死 UUID）；**F-28** 修复 `copywriters` 池须随 **发起部门** 解析（A→A 经理，B→B 经理）。
3. **模板链（W-03）**：**通用能力 F-23** — Run/节点完成可触发下一图模板；**禁止** A→B→A（发布时环检测 + 运行时 guard）；现状仅 video **fork** 子集。
4. **部门定时（W-04）**：**F-24** — 见 **ADR-011**；不沿用 Legacy `TaskSchedule`+cron；`config.schedulable` + 建立任务「定时派发」Tab。
5. **附件（W-05）**：预览/试听 **F-25** P3+。
6. **设计器（W-06）**：JSON/cron → 表单组件 **F-26**；含 `department_pools` 部门选择器。
7. **跨部门跳转 CC（W-07）**：任务直达执行人、**不经部门负责人门控**；边界 **抄送组织树 manager** — **F-27**（与 F-21 同路由思路）。
8. **任务统计（S-01）**：周期/绩效 **暂不立项**；现状 gap 仅文档化。

**后果**  
改造计划 **TC-Transform** Phase 0–3 见 [`roadmap.md`](./roadmap.md)；全貌 [`domains/task-center.md`](./domains/task-center.md) §7–§8。

---

## ADR-011: 部门图模板周期调度（F-24 / W-04）

**日期**: 2026-06-23  
**状态**: 已采纳  
**背景**: 产品审阅 F-24 细化方案；替代 Legacy E `TaskSchedule`（B-12 已 no-op）。

**决策**

1. **实体**：`workflow_graph_template_schedules` — 绑定 **ACTIVE** 且 `config.schedulable=true` 的图模板。
2. **范围**：`scope_mode=self` 或 `subtree`（递归含所有 **active** 子部门）；可 **exclude_department_ids** / **exclude_user_ids**；参与人 **all/subset** 可编辑。
3. **触发**：部门 **manager** 为 actor；每部门每 tick 一个 **batch** Run；**禁止** streaming / production 模板。
4. **重叠**：`skip_if_active` 固定开启；**发布/启用调度时**校验目标部门无同模板 ACTIVE Run。
5. **入口**：任务中心 **建立任务** Dialog → Tab「单步任务 | **定时派发**」。
6. **通知**：创建/更新启用时向相关部门 manager 发送「您有一个新的周期任务，下一次开始于 …」。
7. **立即执行**：`POST .../schedules/{id}/run-now` 允许。
8. **Worker**：复用 `run_due_task_schedules_job`，ARQ cron 每 5 分钟扫描。

**后果**  
API `/workflow-graph/schedules`；设计器 **schedulable** 开关；Legacy `/task-templates/schedules` 废弃。
