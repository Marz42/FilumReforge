# Changelog

> 🌡️ WARM — 版本发布历史（[Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式）。版本号以根目录 `VERSION` 为准。

## [Unreleased]

### Added

- （无）

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
