---
type: paradigma-log
title: "2026-08-10 F-05 任务详情数据协调拆分"
description: "记录 TaskDetailShell 首批数据加载拆分、竞态修复和验证结果。"
tags: [progress, frontend, task-center, f-05]
timestamp: 2026-08-10T17:05:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: cold
  lifecycle: append-only
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [F-05 实施记录, 任务详情数据协调]
    en: [F-05 implementation log, task detail data coordination]
---

# 2026-08-10 F-05 任务详情数据协调拆分

## 完成

- 新增 `useTaskDetailData`，从详情壳层接管七组详情/参考数据和 loading 状态。
- 移除 `onMounted initialize` 与 immediate watch 对同一初始任务的重复请求。
- 加入请求版本门闩，旧任务请求晚到时不能覆盖用户的新选择。
- 新任务主记录先显示；旧附件、时间线、关注人和图事件先清空，避免跨任务短暂串显。
- 附件、关注人、活动时间线、图实例/事件继续独立降级；主任务读取失败会清空旧详情并给出统一错误。
- `TaskDetailShell.vue` 从约 1,989 行降至约 1,895 行；F-05 总体仍未完成。

## 验证

- 新增 2 个测试文件、6 项定向用例；既有任务详情/任务中心回归共同通过。
- Frontend：68 个测试文件、190 项测试全部通过。
- `vue-tsc --build`、oxlint、ESLint 与 Vite production build 通过。
- Build 仍报告既有 809 KB Element Plus 主包告警，本批未扩大该包体积级别。

## 下一步

继续 F-05 动作提交协调拆分；人工 Iteration 4 / 设计器 / S-01 UAT 仍按独立目标环境工作线推进。
