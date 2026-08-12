---
type: paradigma-plan
title: "已发布模板可用部门治理与 Paradigma 0.5.0 协议升级"
description: "实现可审计的已发布模板部门范围增量授权，并将 Filum 的 Memory-Bank 运行协议和 Prompt 对齐 Paradigma 0.5.0。"
tags: [plan, workflow-template, authorization, paradigma]
timestamp: 2026-07-30T02:11:00+08:00
paradigma:
  schema_version: "0.2"
  temperature: cold
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  plan_status: completed
  retrieval_hints:
    zh: [模板可用部门, 已发布模板授权, 范围审计, Paradigma 升级]
    en: [template availability, published scope grant, scope audit, Paradigma upgrade]
---

# Goal

> **计划状态：COMPLETED** — 已发布模板可用部门治理与 Paradigma 0.5.0 升级均已交付；本文仅作实施记录。

让已发布工作流模板可以在不创建新定义版本、不破坏父子模板 code 引用的前提下扩大可用部门范围，并把 Filum 的 Agent Memory Runtime 完整升级到 Paradigma `0.5.0` 的三态、阶段 checkpoint 和独立 session log 协议。

# Scope

- 通用模板治理，不识别视频模板、模板 code 或业务节点。
- ACTIVE 模板仅允许扩大范围；草稿仍由设计器完整编辑，归档模板不可授权。
- 范围变更包含权限校验、部门有效性校验、原因和持久化审计历史。
- 前端任务模板列表提供“可用部门”入口、增量授权和历史查看。
- Paradigma 升级覆盖运行目录、协议源、Cursor/Copilot 适配器、启动 Prompt、对齐审查 Prompt 和索引。
- 不在本轮实现已发布模板范围缩减；缩减继续通过新版本完成。

# Approach

1. 将 availability scope 视为可变治理元数据，与不可变工作流定义版本分离。
2. 新增独立 scope event 表，服务层保证 ACTIVE 更新单调扩大，并将模板范围与审计事件同事务提交。
3. 前端只展示允许的扩大操作；后端继续作为最终安全边界。
4. 当时保留的旧汇总现已迁为 `logs/progress/0000-legacy-progress.md`，并由 Paradigma 0.7 log governance 冻结。
5. 协议先更新 `AGENT_RULES.md`，再同步 `INIT_PROMPT.md`、IDE 适配器和仓库 Prompt。

# Tasks

- [x] 盘点模板 scope、父子模板版本引用和现有管理权限。
- [x] 确认 Paradigma 上游最新版与 `0.5.0` 关键协议差异。
- [x] 实现已发布模板 scope 增量授权、审计模型/API 和后端测试。
- [x] 实现任务模板列表的可用部门管理对话框和前端测试。
- [x] 迁移独立 session log 结构并更新协议源与系统 Prompt。
- [x] 执行全量回归、更新契约/架构/进度并提交。

# Status


Machine status: completed.
**completed** — 通用模板范围治理、前端入口、审计、Paradigma 0.5.0 协议与 Prompt 已完成；全量回归通过。
