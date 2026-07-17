---
type: paradigma-log
title: 版本变更日志
description: "Project Filum SemVer 版本发布历史。"
tags:
  - changelog
  - version
  - release
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: cold
  lifecycle: append-only
  update_policy: append-only
  epistemic_status: confirmed
---
# Changelog

> 🌡️ WARM — 版本发布历史（[Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式）。版本号以根目录 `VERSION` 为准。

## [Unreleased]

### Fixed

- P1-10 模板图任务防自审：执行人从验收候选排除，按直属上级 → 部门负责人 → 工作流管理员 → 系统管理员兜底；无人可选时持久化 `blocked/no_eligible_reviewer`，并提供管理员审计改派 API

### Added

- Iteration 3-F 测试操作手册：开发/CI、PostgreSQL 强制专项、Expand/Backfill/Contract 与连续 7 天 readiness 证据流程
- Iteration 3-F：Work Item/Runtime 独占写端口、全仓库 AST ownership/commit guard、Admin readiness API 与 CLI verifier
- Link iteration/superseded 生命周期与持久 `workflow_operational_incidents` 异常队列（Expand/Contract 迁移 `20260716_01`、`20260716_02`）
- PostgreSQL UoW 故障注入、命令副作用重放、Link-first mismatch、Outbox duplicate 与兼容回滚自动化证据
- Iteration 3 B–E：Link dry-run 回填/生命周期/观测、standalone Work Item 默认路径、统一 command executor 与 RunEvent 信封、Outbox event-id 通知去重（迁移 `20260715_03`）
- Iteration 3-A 写所有权/幂等基座：`workflow_human_task_links`、`workflow_command_receipts`、`HumanTaskCoordinator` 与 command receipt service（迁移 `20260715_02`）
- 新手动兼容任务与模板 HumanTask 投影双写正式 Link；Task 图投影读取 Link-first、JSON fallback
- 工作流 graph-v3 路径账本：`workflow_edge_traversals`、`workflow_node_activation_dependencies`、显式 routing mode、Run result/diagnostics（迁移 `20260715_01`）
- graph-v3 Context expected version/diff event、Deep-Reject 路径失效与不可变 fan-out branch identity
- 工作流模板显式 `scope_mode`；Run canonical definition snapshot、SHA-256、`engine_version` 与 snapshot/legacy executor 双路由（迁移 `20260713_01`）
- 工作流 active legacy Run 只读盘点脚本 `report_workflow_legacy_runs`
- S-01 任务周期统计：权限范围、上海时区日期筛选、新增/完成/到期/逾期/按期完成率、人员负载和分页明细下钻
- 图模板管理员删除能力；存在 Run 的模板拒绝删除
- 图模板 `scope_department_ids` 部门作用范围（迁移 `20260709_01`），设计器与实例化入口同步按部门过滤
- 图模板设计器补 `participant_policies`、`root_assignee_var`、`aggregate_node_key`、`run_kind` 等结构化字段

### Changed

- HumanTask 跨域写入统一由 Coordinator 编排两个 flush-only writer；Link 存在时为唯一关系真相，JSON 不一致登记 incident
- Link 回填器支持 checkpoint/batch，确定项与歧义 incident 可在同次 apply 中安全、幂等落库
- ACTIVE/ARCHIVED 图模板改为发布后不可变；模板 seed 更新改为归档旧版本并派生新的 ACTIVE 版本
- 任务统计 summary/workload 从全量 ORM 加载后 Python 计数改为数据库侧条件聚合；旧总量字段保持兼容
- 建立任务弹窗抽取为 `PublishTaskDialog.vue`；采集组件统一为 `CapturePanel.vue`
- `aggregate_mode` 空白模板默认值对齐为 `streaming`
- 前端安全依赖升级：Axios `1.18.1`、Vite `8.1.4`；Excel 预览从无安全修复版本的 `xlsx` 切换到 `read-excel-file`

### Fixed

- 条件分支未选节点不再永久 pending；Join 不再等待未产生分支；no-route 进入 failed 并写结构化诊断
- 统一 Run→Node 行锁顺序，消除 PostgreSQL Wait-Any 并发完成死锁
- Excel 附件预览改为 Vue 文本插值渲染，并限制为前 500 行/100 列，避免不可信单元格 HTML 注入与超大表格渲染阻塞
- 修复附件服务模块导入时 MIME 常量定义顺序导致的 `NameError`，并覆盖 `.md`/`.docx` 通用 MIME 推断
- 修复 Wait-Any 被撤权节点阻止图实例完成、手动单节点验收后实例仍 active
- 图模板 seed 不再原地同步 ACTIVE 拓扑，避免在途 Run 定义漂移
- 修复同一 AsyncSession 中新增 watcher 后关系集合未刷新，以及上游交付附件继承构造无效 `AttachmentLink` 的问题
- 修复图模板 schedule CheckConstraint 在命名约定下超过 PostgreSQL 63 字符限制
- 修复 PublishTaskDialog 类型边界及 AppShell/TaskCenter refactor 后测试漂移；新增 PublishTaskDialog/CapturePanel 组件回归
- 修复模板部门池非法 UUID、种子 scope 推导与 `seed_version` 丢失等 P0/P1 配置问题
- 修复 `PublishTaskDialog` v-model、重复 `onMounted` 与 Playwright capture 锚点
- 关闭采集后同步兼容 Task 投影，并让下游任务继承交付物附件可见性
- 修复 `.md` / `.docx` 通用 MIME 上传推断，以及附件继承路径的 SQLAlchemy `MissingGreenlet`

## [0.92.0] — 2026-07-08

### Added
- 引入 Paradigma v0.5.0 工具链（`.paradigma/tools/` 8 个脚本 + schema + config）
- 引入 `memory-bank-template/` 三态模板源、`docs/rfc/`、`DESIGN.md`

### Changed
- **Memory-Bank 结构迁移**：flat → `runtime/` / `logs/` / `knowledge/` 三态
- `knowledge/manuals/` → `knowledge/manuals/`；decisions/known-issues 拆分为独立文件
- 全量 `knowledge/` 文档 OKF YAML frontmatter
- `AGENT_RULES.md` + Cursor Rule 更新至 Paradigma v0.5.0 协议 + 三态路径

### Fixed
- 内部交叉引用路径修复；`pd-sync-index.py` 首次生成 7 个索引

---

## [0.91.2] - 2026-06-23

### Fixed

- **任务中心 500**：批次 ROOT 投影修复误用不存在的 `WorkflowGraphInstanceStatus.SUSPENDED`；改为 `ACTIVE`/`PENDING`

---

## [0.91.1] - 2026-06-23

### Fixed

- **批次 ROOT 误进历史**：streaming 选题会批次在全部采集提交后、派发前，批次 ROOT 任务不再被 graph 投影判为 `DONE`；以图实例 `ACTIVE`/`COMPLETED` 为准，阶段文案「汇总派发：待确认派发」

---

## [0.91.0] - 2026-06-23

### Added

- **F-29** 管理员单条任务归档：`POST /api/v1/tasks/{task_id}/archive`（admin only）；软归档 `extra_metadata.admin_archived*`；联动终止 `WorkflowGraphInstance`（批次 ROOT 含子 Run）；inbox/tracking/history 过滤；任务详情「更多 → 归档任务…」
- **Admin/HR 跟踪督办**：`list_task_tracking` 对 `MANAGEMENT_ROLES` 展示全量未完成任务（关联方式「督办」）
- **逾期延期**：跟踪列表与任务详情 Admin/HR「延期…」；`PATCH /tasks/{id}` 已逾期任务须设更晚 `due_date`（逾期不阻断提交/验收）

### Fixed

- **归档后 MissingGreenlet**：`_build_graph_stage_label` 不再访问 `node_instance.instance` 懒加载；`_build_visible_task_statement` 预加载 `watchers`
- **N10 完成后误归档**（`efa450c`）：materialize 尾节点 · 出边 `node_key` 回退
- **N7 指派剪辑师列表错部门**（`314bb6f`）：默认 `post_production` 池
- **N3 脚本提交 / N5 多文件上传**：deliverable AttachmentLink · 上传超时

---

## [0.90.0] - 2026-06-23

### Added

- **TC-Transform Phase 0–2**：B-12 Legacy E 移除 · F-28 多文案部实例部门 · F-22 抄送 · F-23 模板链 · F-21/F-27 跨部门 · W-08 streaming N2 skip · F-26 设计器 pools
- **F-24** 部门图模板周期调度：`workflow_graph_template_schedules` · schedulable · 建立任务「定时派发」Tab · Worker ARQ cron · ADR-011
- **F-25** 应用内附件预览：image / PDF / txt / md / docx / xlsx / 音频 · 全局 `AttachmentPreviewDialog`
- 定时派发 UI：`scheduleCron.ts`（每天/每周/每月 → cron）；设计器 active 模板「保存设置」

### Fixed

- **生产 seed**：`seed_version` 升级时若已有 Run 引用 template nodes，改为按 `node_key` 原地同步（避免 `fk_wf_node_instances_template_node`）
- **TaskDetailShell** 补 `resolveStatusLabel` 导入；**vue-tsc** 通过（tag types · DAG preview · 设计器 row click）

### Changed

- 部署手册 §21.3.1：多文案部共用模板说明 · `.env` 显式 `WORKFLOW_GRAPH_*` · seed 行为与历史 Run 边界
- E2E task-center **39/39**；后端 TC-Transform 相关测试绿

---

## [0.89.0] - 2026-06-18

### Changed

- **任务模板** 前端统一为图模板单入口（`/task-templates`）；移除 Legacy E Tab 与 CRUD/设计器 UI
- 用户可见文案统一为「任务模板」；任务中心页头按钮由「模板管理」改为「任务模板」
- Legacy 工作流 E 后端 API / 运行中实例 **保留**；文档标注 **待删除**（TC-P3）

### Removed

- `TaskTemplatesView.vue` 中工作流 E 模板管理 UI（~2000 行）

---

## [0.88.0] - 2026-06-18

### Added

- **TC-P2** 任务中心：`TaskCenterListView` / `BoardView` / `GanttView` 独立三视图（用户态 × Run）
- **TC-P2** `filter=stats` + `TaskCenterStatsView`（部门汇总、run_events、负载表）；`/task-center/stats` redirect
- **TC-P2** `TaskDetailShell.vue`；`TasksView` 瘦身为 workspace 壳层
- **TC-P2** `config.ui_profile`：模板节点配置 → 实例化 metadata → 前端 Profile 优先读取
- **TC-P2** E2E：`task-center-stats.spec.ts`；board/gantt 断言；workflow-video 适配 v2 UI
- Playwright 本地 Chrome：`.playwright-browsers/` + `playwright.config.ts` 自动检测

### Changed

- v2 UI 下隐藏 `BatchRunDashboard`；详情 video 仅展示最近 3 条 run_events
- `memory-bank`：TC-P2 验收勾选、roadmap/active-task 切换至 TC-P3

---

## [0.87.1] - 2026-06-17

### Added

- Memory-Bank Phase 3 WARM/COLD：`roadmap`、`changelog`、`domains/`、`decisions`、`known-issues`、`glossary`
- 对齐审查报告 `history/reports/alignment-assessment-20260617.md`

### Changed

- 根/README、子 README、plans、handbooks 引用指向 Paradigma 文档分工（schema → `data-contracts.md`）
- `backend/README.md` 修正图引擎 graph-first 与 workflow-video 边界描述

## [0.87.0] - 2026-06-17

### Added

- 根目录 `VERSION` 文件，SemVer 基线（对应当前 87 次提交）
- Memory-Bank 外部记忆协议（基于 [paradigma](https://github.com/Marz42/paradigma) 定制）

### Notes

- 此版本号为 **文档体系与协作协议** 基线，不代表产品功能大版本发布
- 产品功能交付历史见 `progress.md` 与 `roadmap.md`
