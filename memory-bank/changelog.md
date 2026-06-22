# Changelog

> 🌡️ WARM — 版本发布历史（[Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式）。版本号以根目录 `VERSION` 为准。

## [Unreleased]

### Added

- **图模板空白新建**：`POST /workflow-graph/templates` 无 `clone_from_id` 时创建空白 draft；列表「新建模板」
- **DAG 预览增强**：横向/纵向布局、图例、打回独立通道、正交圆角路由
- **E2E 任务中心扩面**：`task-center-interactions.spec.ts`（8 条：握手 accept/协商/转办、验收、结束采集、统计 deep-link、模板入口）；`task-center-interaction-mock.ts`；`npm run test:e2e:task-center` + `playwright.task-center.config.ts`（core 33 + multi-account 15 = 48）
- **E2E 统计 Tab**：`task-center-stats.spec.ts` +2（部门筛选、看板 Run 筛选）
- **E2E multi-account mock**：Phase A–N 全绿（15/15）；mock 补齐 `preview-participants?policy=`、模板 GET config、`user_facing_state`

### Fixed

- **图模板设计器写操作**：AdminService 写库补 `commit()`；复制/改名/发布不再假报「模板不存在」
- **图模板 DAG 预览**：单滚动条；打回虚线贴节点边框；圆角方向修正；箭头不被节点遮挡
- **图模板设计器表格**：节点/边列宽；边表头中文化（打回/优先级/条件 JSON）
- **TaskCenterView** deep-link `selected=` 在 non-search 模式下不再被 sanitize 清除
- **TaskDetailShell** 补 `TASK_CENTER_V2_UI_ENABLED` import

### Changed

- Playwright：`PLAYWRIGHT_DEV_PORT` 可配置；4173 不可用时默认 5173；系统 Chrome channel 回退；`video: off`
- 测试基线：**33/33** core mock · **15/15** multi-account mock（`2026-06-22-main-e2e-core-33`）
- **TCE Phase 5**（B-08/B-13/B-14/B-15, F-13–F-16）：图模板 snapshot 摘要、aggregate_mode、结束采集、user_facing_state 图对齐、移除 TasksView 回退
- **TCE Phase 4**（B-16, F-17）：多部门实例化 policy 实例部门优先、实例化发起部门 UI/校验
- **TCE Phase 3**（B-06/B-09/B-11, F-06/F-09）：部门统计 API、snapshot 分页、Run 聚合 API、统计页部门/Run、看板 Run 筛选
- **TCE Phase 2**（B-04/B-05/B-07, F-01/F-04/F-07）：batch tasks API、snapshot 读模型 `run_label`/`user_facing_state`、tracking inbox 去重、workspace batch hydration、搜索用户态、Run 标签对齐 graph context
- **TCE Phase 1**（B-01/B-02/B-03, F-02/F-03/F-08）：节点投影 inbox 读路径、列表 SQL limit、department 迁移脚本、看板姓名、实例化发起部门、详情操作后 refresh
- memory-bank 全量对齐 **TCE Phase 1**：`active-task`、`roadmap`、`project-brief` @ `0.89.0`；TC-P3 归入 `task-center-enhance` Phase 5

### Added

- 视频制作模板 **seed v3**：N5 合并配音上传、N11 排期 capture、N12 文案会签（`N12_CLOSE` + `N12_COSIGN`）；结案子 Run `archived` 且批次看板默认隐藏
- `seed_workflow_video_templates` 支持 `--copy-dept-code` / `--post-dept-code`（生产环境绑定真实部门）
- Mock 多账号 E2E **阶段 A–N**（15 用例，N1–N12 happy path）
- 前端 Profile：`video_production_multi` / `video_production_platform` / `video_capture_schedule`

### Changed

- 制作链移除 N6 配音审核与配音部握手节点；W4/W6 测试与 E2E mock 状态机同步更新

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
