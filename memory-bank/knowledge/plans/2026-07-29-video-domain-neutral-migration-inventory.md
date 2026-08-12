---
type: paradigma-plan
title: "视频模板领域中立迁移清单"
description: "盘点视频兼容路径，定义通用能力替代契约、黄金回归与退出条件。"
tags: ["plan", "workflow-graph", "domain-neutral", "video-template", "compatibility"]
timestamp: 2026-07-30T01:45:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: cold
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  plan_status: completed
  retrieval_hints:
    zh: ["视频模板去特殊化", "run_kind 退出", "通用工作流能力"]
    en: ["video template neutrality", "run_kind exit", "generic workflow capability"]
---
# 视频模板领域中立迁移清单

> **计划状态：COMPLETED（核心迁移）** — 视频能力已回归普通领域中立模板；兼容适配器和 dual-read 的最终删除转入 Iteration 6，不继续在本文排期。

> **状态（2026-07-30）**：I4-E 核心迁移完成。Runtime、TaskService、Task Center 与前端详情改为 capability snapshot / task capability；视频 seed v5 声明通用能力，旧 API/service/profile 进入兼容窗口。删除 dual-read 仍须等待调用观测归零。

## 目标与边界

视频流程保留为模板包、种子数据和黄金回归，不进入 Runtime 的类型系统。迁移期间保留现有 API、service、metadata 与 `video_*` Profile 作为兼容层；替代契约及回归覆盖到位前不删除旧路径。

## 当前兼容面与替代方向

| 兼容面 | 主要代码入口 | 当前专用判断 | 通用替代契约 | 退出条件 |
|---|---|---|---|---|
| 模板发现与启动 | `workflow_graph_template_admin_service.py`、`task_center_service.py`、`workflow_graph_template_capabilities.py` | `config.run_kind`、视频实例化 service | `capabilities` + `launch_schema` + 模板标签只负责发现/展示 | 新旧模板均只凭能力声明启动；`run_kind` 读取计数为 0 |
| 实例化与排期 | `workflow_video_instantiation_service.py`、`workflow_graph_template_schedule_service.py` | batch/production 分支、视频输入校验 | 通用 launch input validator、参与者策略、scheduled dispatch | 通用实例化与排期覆盖现有 batch/production 黄金用例 |
| 表单与集合关闭 | `workflow_video_form_service.py`、`workflow_orchestration_service.py` | capture/aggregate 专用动作 | structured form submission、collection status、`collection_finalize` | 视频 API 仅作兼容适配；核心服务不引用视频命名 |
| 子 Run 派发 | `workflow_video_fork_service.py`、模板 `child_template_code` | 按视频模板 code 创建 production Run | 通用 child-run dispatch capability + 显式输入映射 | 任意模板可复用；Runtime 不比较模板 code |
| 交付与返工 | `workflow_video_rework_service.py`、`task_service.py` | production metadata / completion policy | Deliverable version、acceptance/rework command、决策对象 | I4-C/D 语义矩阵通过；视频 service 退为薄适配器 |
| Runtime 通知与收口 | `workflow_graph_service.py` | `context.run_kind` 控制通知、production archive/termination | 通用 notification policy、archive policy、terminal policy | Runtime 核心中 `run_kind` 分支归零 |
| Work Item 投影 | `task_service.py`、`task_user_facing_state.py` | batch/production 与 `video_*` Profile 推断 | 后端返回通用 action/layout capability 与 user-facing state | Task 投影不靠 node key、run kind 或视频 Profile 推断业务动作 |
| 前端详情与面板 | `profile.ts`、`user-state.ts`、`TaskDetailShell.vue`、`Video*Panel.vue` | `video_*` Profile 决定布局、按钮和面板 | schema-driven form/collection/tracking/deliverable panels | 同一通用面板可由非视频模板配置复用；旧 Profile 仅兼容映射 |
| 前端模板启动 | `workflowVideoSchema.ts`、`TemplateInstantiateDialog.vue`、`ScheduledDispatchForm.vue` | `run_kind` 和视频 schema 决定输入 | 直接消费 `capabilities`、`launch_schema`、participant policy refs | 新模板不提供 `run_kind` 仍可完成启动与排期 |

## 通用能力候选

- `structured_form_submission`：结构化表单填写、提交、关闭状态。
- `collection_finalize`：确认集合完整并推进；允许协调者同时是贡献者。
- `child_run_dispatch`：按显式模板引用和输入映射创建子 Run。
- `deliverable_submission` / `deliverable_acceptance` / `return_for_rework`：围绕交付版本的动作。
- `participant_assignment` / `schedule_input`：参与者选择与排期输入。
- `notification_policy` / `archive_policy`：通知和归档由声明式策略驱动。
- `tracking_projection`：按 Run/Node/Deliverable 事实生成追踪表，不绑定视频领域。

## 执行顺序

1. I4-B/C/D 先固定 HumanTask、Approval、Deliverable 的通用命令和决策语义。
2. 优先移除 `workflow_graph_service.py` 内的 `run_kind` 行为分支，替换为通用策略字段。
3. 将视频实例化、表单、集合、子 Run、返工 service 拆为通用内核 + 视频兼容适配器。
4. 后端输出通用 UI/action capabilities 后，前端把 `video_*` Profile 改为兼容映射。
5. 新旧模板双读、黄金流程和观测通过后，逐项删除 `run_kind` 与视频专用推断。

## 黄金回归

- Backend：`test_workflow_video_w0_baseline.py` 至 `test_workflow_video_w10_regression.py`、`test_workflow_video_dispatch_*.py`、`test_workflow_video_f28_launch_department_pools.py`。
- Frontend unit/API：`workflowVideoW*.spec.ts`、`workflowVideoSchema.spec.ts`、task-detail profile/user-state tests。
- E2E：选题采集/汇总、两题派发子 Run、多账号协同、退回返工和增量派发 mock/live 场景。
- 新增领域中立对照：至少用一个非视频模板复用表单、集合确认、子 Run 和交付/返工能力，证明行为不依赖视频名称。

## 禁止项

- 不新增 `VideoHandler` 或按模板 code、node key、tags、`video_*` Profile 路由 Runtime。
- 不在兼容调用归零前删除现有 API/service/schema。
- 不把前端视觉 Profile 当作权限、完成策略或决策语义的事实来源。

# Status

Machine status: completed.
