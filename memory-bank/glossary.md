# 项目术语表

> 🧊 COLD — 防止 Agent 与协作者理解偏差。

| 术语 | 含义 |
|------|------|
| **Project Filum** | 本仓库产品名（FilumReforge） |
| **模块化单体** | 单部署单元，多清晰模块边界；非微服务 |
| **Phase A–5** | 历史五阶段交付（Foundation → Knowledge/AI） |
| **Stage 2** | Phase 5 之后的增强周期（`improvements-stage2-implementation-plan.md`） |
| **Step 1–7** | UI/信息架构重构步骤（壳层、任务中心、汇报等） |
| **IA Phase A–F** | UI 信息架构里程碑（登录→总览 Dashboard） |
| **工作流 E** | Legacy `task_templates` / `TaskTemplateService` 模板运行时 |
| **图引擎** | `WorkflowGraphTemplate` / `WorkflowGraphService` 多节点 DAG 运行时 |
| **graph-first** | 任务中心列表优先解析图投影（`TASK_CENTER_V2_ENABLED`） |
| **TC-P0–P2** | 任务中心 v2 壳层实施阶段 @ `0.88.0`–`0.89.0` |
| **TC-P3** | E 与图引擎统一、aggregate_mode、结束采集 — 已并入 **TCE Phase 5** |
| **TCE** | Task Center Enhance；[`plans/task-center-enhance.md`](./plans/task-center-enhance.md) |
| **发起部门** | 图模板实例化 `WorkflowGraphInstance.department_id`；默认 Profile 部门（enhance §6.2.1） |
| **dual-write** | 手动建任务时同时写 `Task` 与 graph node instance |
| **工作流 E 与图引擎统一** | 产品级单一模板源目标；当前双轨并存 |
| **Inbox-first** | 任务中心主筛选：待处理 / 跟踪 / 历史 |
| **握手** | 图任务接单/协商/转办（accept / reject / delegate） |
| **深度打回** | `deep_reject_to_upstream`；克隆 iteration+1 版本链 |
| **Wait-All / Wait-Any** | 多节点汇聚：`join_mode=all` / `any` |
| **routing_rules** | 模板步骤条件路由；`condition_evaluator` 共享求值 |
| **outbox** | `workflow_outbox_events` 异步投递与重试 |
| **视频工作流 v1** | 批次选题会 → `approved_topics[]` → 按题 fork 制作 Run |
| **选题会** | 图模板 `topic_meeting_batch_v1`；非独立导航入口 |
| **launch/capture/aggregate schema** | 视频 v1 表单引擎三阶段 Pydantic 契约 |
| **Run** | `WorkflowGraphInstance` 一次图实例化运行 |
| **fork** | 按选题生成子 Run（`video_production_per_topic_v1`） |
| **legacy E** | `TaskTemplateService.instantiate_template` 路径 |
| **NotificationService** | 唯一通知发送入口；业务不直连渠道 |
| **消息中心** | 收件箱 + 回执；**不是**任务聊天 |
| **task_comments** | 任务绑定讨论与附件；协同留痕真相源 |
| **字段级权限** | `profile_field_permissions` 驱动档案裁剪 |
| **代理授权** | `delegations`；审批/任务/数据范围委托 |
| **邀请制注册** | 管理员发链接、受邀人设密激活；非公开注册 |
| **memory-bank** | 外部记忆文档目录 |
| **HOT / WARM / COLD** | 知识温度：每次必读 / 按需 / 排查时 |
| **handbooks** | 运维手册目录（≈ Paradigma `manuals/`） |
| **alignment-assessment** | 文档与实现对齐审查报告 |
