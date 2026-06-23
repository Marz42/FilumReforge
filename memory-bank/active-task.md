# 当前任务

> 🔥 HOT — 下一聚焦项请从 [`roadmap.md`](./roadmap.md) 选取并更新本文件。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | 任务中心 backlog（B-12 / F-05） |
| **优先级** | P1 · 架构债 |
| **状态** | **Live E2E A–F ✅** @ 2026-06-23 · 视频工作流四问题修复 ✅ · 设计器 UX 抛光 ✅ @ 2026-06-22 |
| **关联** | [`domains/task-center.md`](./domains/task-center.md) §12 · [`progress.md`](./progress.md)「测试基线」 |

---

## 最近完成 ✅

| 交付 | 说明 |
|------|------|
| **Live E2E A–F（8080 streaming）** @ 2026-06-23 | `PLAYWRIGHT_LIVE_SKIP_STACK=1` + 8080 栈；Phase C-D 增量派发；**7/7 passed**；报告 `verification-runs/workflow-video-live-2026-06-23_06-26-25` |
| **视频工作流四问题修复** | 选题去重/fork 锁；投影 `department_id` + ROOT 提交拦截；制作 ROOT 步骤导航；WAV 上传；`test_workflow_video_dispatch_fixes.py` 5 passed |
| **视频 streaming 派发补丁** @ `bf75e31` | 默认 streaming；制作 ROOT 指派经理；待办排除 graph 壳层；跟踪列「当前步骤/处理人」 |
| **设计器 UX 抛光** | 写操作 commit 修复；空白新建；DAG 横向/图例/打回通道；单滚动条；节点/边表列宽与中文化；打回虚线贴边框 + 圆角/箭头可见 |
| **E2E 扩面** | core **33/33**；multi-account mock **15/15**（A–N）；`npm run test:e2e:task-center` |
| **交互覆盖** | 握手 accept/协商/转办、验收、结束采集、统计 deep-link、看板 Run 筛选 |
| **产品修复** | `TaskCenterView` deep-link `selected` 保留；`TaskDetailShell` `TASK_CENTER_V2_UI_ENABLED` import |

## 模板设计器 ✅

| Phase | 交付 |
|-------|------|
| **D1** | clone/draft/publish/validate + 全页设计器 |
| **D2** | 边表、routing、拓扑校验 |
| **D3** | DAG 预览、dry-run、JSON 导入导出、Run 统计 |

**后续**：**B-12** Legacy E 统一 · **F-05** Shell 拆分 · UAT/docker-gui E2E 重跑 · domains 文档同步（inbox 壳层/跟踪列/streaming 派发）

---

选定子任务后：更新上表 → 执行 → 测试 → commit → 追加 `progress.md`。
