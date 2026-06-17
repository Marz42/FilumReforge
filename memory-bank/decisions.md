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

## ADR-007: Memory-Bank Paradigma 对齐

**日期**: 2026-06-17  
**状态**: 已采纳（Phase 3 进行中）

**背景**  
Agent 协作需知识温度分层与统一 Update 工作流。

**决策**  
采用 Paradigma 协议；保留 `handbooks/` 路径（≈ `manuals/`）；`VERSION` 从 `0.87.0` 起 SemVer；不采用 `.template.md` 双文件机制。

**后果**  
文档迁移分 Phase 进行；`design-document`/`tech-stack` 保留只读完整版。
