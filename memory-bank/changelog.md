# Changelog

> 🌡️ WARM — 版本发布历史（[Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式）。版本号以根目录 `VERSION` 为准。

## [Unreleased]

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
