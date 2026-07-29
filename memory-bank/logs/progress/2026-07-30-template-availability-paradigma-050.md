---
type: paradigma-session-log
title: Template Availability Governance and Paradigma 0.5.0 Upgrade
description: 通用已发布模板可用部门治理、前端入口与 Paradigma 0.5.0 运行协议升级的交付记录。
tags: [session, progress, workflow-template, authorization, paradigma]
timestamp: 2026-07-30T02:32:40+08:00
paradigma:
  layer: log
  lifecycle: append-only
  okf_export: optional
  update_policy: append-only
---

# Session Summary

## User Goal

- 为普通已发布模板提供可用部门管理并在前端体现；将 Memory-Bank Paradigma 协议和相关 Prompt 升级到上游最新版。

## Actions Taken

- 新增 ACTIVE 模板范围单调扩大 API、独立审计事件表与 Alembic migration。
- 新增任务模板列表“可用部门”对话框，可增量授权、扩大为全局并查看操作历史。
- 固化权限边界：部门经理仅能新增其有效管理范围；扩大为 global 仅限全局管理角色。
- 将协议源、INIT_PROMPT、Cursor/Copilot 适配器切换到三态、checkpoint、知识索引和独立 session log 流程。
- 记录 Paradigma Harness `0.5.0` 与上游 main commit `c4c5e06b1ace2a510dbe365819776258de9e3e51`。

## Files Read

- `AGENT_RULES.md`、`INIT_PROMPT.md`、`.paradigma/config.yaml` 与本地 Harness 工具。
- 模板模型、访问策略、管理服务、任务模板前端面板与现有测试。
- Paradigma 官方仓库 README、VERSION、AGENT_RULES、INIT_PROMPT 与 commit history。

## Files Modified

- `backend/app/`、`backend/alembic/versions/`、`backend/tests/`：范围治理、审计、迁移与测试。
- `frontend/src/`、`frontend/tests/`：管理对话框、API/types、入口与测试。
- `AGENT_RULES.md`、`INIT_PROMPT.md`、`.cursor/`、`.github/`、`.paradigma/`：0.5.0 协议和 Prompt。
- `memory-bank/`：ADR-020、计划、契约、架构、索引与运行状态。

## Decisions Proposed

- 将 availability scope 作为定义之外的可变治理元数据。
- 发布后只允许扩大范围；缩小范围通过新版本完成。
- 不按视频模板或父子模板 code 做隐式级联。

## Decisions Accepted

- 上述三项已按用户确认实现并写入 ADR-020。

## Knowledge Updates

- Backend 全量：449 collected，10 skipped，0 failed；`compileall` PASS；Alembic 单 head `20260730_01`。
- Frontend 全量：63 files / 177 tests PASS；`vue-tsc --build`、production build、变更文件 Oxlint/ESLint PASS。
- 旧 `logs/progress/progress.md` 冻结为升级前历史；后续每次会话新增独立 append-only 日志。

## Follow-ups

- 部署此功能时先应用 Alembic migration `20260730_01`。
- 视频工作流的批次模板和制作模板仍需分别授权所需部门，不自动级联。
- 系统管理员不参与业务的角色边界仍按既定计划延后实现。

