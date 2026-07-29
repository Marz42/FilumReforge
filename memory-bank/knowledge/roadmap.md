---
type: paradigma-plan
title: "Project Filum — 路线图"
description: "宏观里程碑、Iteration 4 完成态、分批发布与历史任务中心改造记录。"
tags:
  - roadmap
  - milestones
  - tc-transform
timestamp: 2026-07-30T01:45:00+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: requires-human-confirmation
  epistemic_status: confirmed
  retrieval_hints:
    zh:
      - 路线图
      - 里程碑
      - TC-Transform
    en:
      - roadmap
      - milestones
  relations:
    related_to:
      - ./domains/task-center.md
---
# Project Filum 路线图

> 🌡️ WARM — 宏观里程碑与当前执行顺序。任务中心历史全貌见 [`domains/task-center.md`](./domains/task-center.md)。

| 字段 | 内容 |
|------|------|
| **当前版本** | `0.92.1`（根目录 `VERSION`）+ Unreleased |
| **版本主题** | 工作流图引擎 Iteration 4 · 模板领域中立与稳定化 |
| **阶段** | **Iteration 4 工程完成** — I4-A–E 已完成；先行发布候选待预发 smoke，I3-F 生产切流仍 gated |
| **最后整理** | 2026-07-30 — I4-E 领域中立迁移与先行发布评估完成 |

---

## ✅ 已完成里程碑

| 里程碑 | 完成 | 关键交付 |
|--------|------|----------|
| Phase A–5 · 重构 · UI IA | done | 模块化单体基线 |
| 工作流图引擎 Phase 11 | done | graph-first · dual-write · outbox |
| 视频工作流 v1 W0–W10 | done | 选题会 · fork · E2E |
| 任务中心 v2 TC-P0–P2+ | done | 三视图 · 统计 Tab · Shell @ `0.89.0` |
| TCE Phase 1–5 | done | 读模型 · 多部门 B-16 · TC-P3 @ 2026-06-21 |
| 图模板设计器 D1–D3 | done | authoring · 拓扑 · dry-run |
| 已发布模板可用部门治理 | done | ADR-020 · ACTIVE 单调扩权 · 审计 · 前端入口 @ 2026-07-30 |
| 视频 Live E2E A–F | done | streaming · 8080 7/7 @ `b3e7918` |
| **TC-Transform Phase 0–2** | done | B-12 · F-28 · F-22 · F-23 · F-21/F-27 · W-08 · F-26 @ `2630feb` |
| **F-24 / F-25** | done | 定时派发 · 附件预览 @ `0.90.0` |
| **生产 hotfix** | done | N3/N5/N7/N10 流转与附件 @ `efa450c` |
| **F-29 管理员治理** | done | 归档 API · 图 Run 终止 · 跟踪督办 · 逾期延期 @ `0.91.0` |
| **Paradigma v0.5.0 三态迁移** | done | runtime/logs/knowledge 三态 · OKF frontmatter · 文档合规 @ `0.92.0` |
| **Task Center P0–P2 审计修复** | done | 锁/CAS · 分页/附件 · 模板评审候选链 @ `0.92.1` |
| **工作流图引擎 Iteration 1–3-F 工程实现** | done | snapshot · graph-v3 · Link/receipt · ownership/UoW · readiness 工具；生产证据仍 gated |
| **模板解耦 Phase 1 + Phase 2 首批** | done / UAT | tags · capabilities · archive · structured authoring |
| **Iteration 4-A–E** | done | Handler Registry · HumanTask/Approval/Deliverable/Notification · 领域中立 capability snapshot |

---

## 任务中心产品架构（三大模块）

| 模块 | 入口 | 改造焦点 |
|------|------|----------|
| **单步任务** | 建立任务 | F-22 抄送 · F-21 跨部门 |
| **任务流** | 任务模板实例化 | **F-28** 多部门池 · F-23 模板链 · F-26 设计器 |
| **任务统计** | stats Tab | **S-01 最小周期统计已实施，待验收** |

决策索引：[`decisions.md`](./decisions/decisions.md) **ADR-009**（单步）· **ADR-010**（任务流）

---

## TC-Transform 交付记录（历史）

以下为已执行阶段记录，不再作为当前排期；细项与代码锚点见 [`domains/task-center.md`](./domains/task-center.md) §6–§13。

### Phase 0 — 架构收口（产品入口已完成，技术债未清零）

| ID | 交付 | 当前状态 |
|----|------|------|
| **B-12** | 移除 Legacy E 产品入口（API · 实例化 · 旧调度） | ✅ 图引擎为唯一产品入口；旧表/ORM 暂留历史兼容 |
| **F-05** | `TaskDetailShell` 完整拆分 | ⚠️ 已抽取部分组件，Shell 仍约 1841 行，保留为技术债 |
| **E2E 基线** | UAT / docker-gui / Playwright live 刷新 | ⚠️ mock 有近期验证；全量 live/docker-gui 待本轮覆盖审查 |

### Phase 1 — 正确性 + 单步补齐（已完成）

| ID | 交付 | 验收 |
|----|------|------|
| **F-28** | 制作 fork 时 **`copywriters` 池 = 批次发起部门**（或 `instance_department` 语义） | ✅ 已完成 |
| **F-22** | 建立任务 Dialog + `TaskCreateRequest.watcher_user_ids` | ✅ 已完成 |
| **F-10–F-12** | 抛光（PublishDialog 抽出等） | ✅ 已完成 @ 2026-07-09 |

### Phase 2 — 任务流能力扩展（已完成）

| ID | 交付 | 验收 |
|----|------|------|
| **F-23** | **通用模板链**：Run/节点完成 → 配置触发下一 `WorkflowGraphTemplate`；发布时 **防环** | ✅ 已完成 |
| **F-27** | 任务流 **跨部门边界 CC**（组织树 manager，不经负责人门控） | ✅ 已完成 |
| **F-21** | 单步 **跨部门路由 + 路径 CC** | ✅ 已完成；深树性能仍是技术债 |
| **W-08** | streaming 模式 **N2 空壳/engine skip** | ✅ 已完成 |
| **F-26** | 设计器 **`department_pools` 部门选择器** + 逐步去 JSON | ✅ 首批结构化配置已完成 |

### Phase 3 — 体验与共用增强（P3+）

| ID | 交付 | 验收 |
|----|------|------|
| **F-25** | 附件预览/试听（md/docx/xlsx/wav/图片） | ✅ 应用内预览 Dialog · 单步 + 任务流交付物 |
| **F-24** | 部门/子树 **图模板定时实例化** | ✅ schedulable · 双 Tab · 重叠校验 · 通知 · run-now |
| **F-29** | **管理员任务治理**：单条任务归档/作废 · 图 Run 联动终止 · Admin 跟踪督办 · 逾期延期 | ✅ @ `0.91.0` |
| **S-01** | 任务统计：周期、权限、负载、明细 | ✅ implemented · pending UAT |

### Phase 4 — 中长期（P4）

| ID | 交付 |
|----|------|
| **项目组** | 跨部门成员编组派活（G-02；替代组织树 hack） |
| 设计器拖拽化 · S3 · i18n | 见「中长期」表 |

---

## 能力差距速查

### 单步（ADR-009）

| ID | 决策 | 工程项 | 阶段 |
|----|------|--------|------|
| G-04 | 创建须抄送 | F-22 | 1 |
| G-01 | 跨部门 + CC | F-21 | 2 |
| G-03 | 自派 → 备忘 | — | — |
| G-05 | 仅图引擎 | B-12 | 0 |

### 任务流（ADR-010）

| ID | 议题 | 工程项 | 阶段 |
|----|------|--------|------|
| W-09 | A/B 制作链经理不串 | **F-28** | **1** |
| W-03 | 通用完成后触发模板 | F-23 | 2 |
| W-07 | 跨部门 CC（组织树） | F-27 | 2 |
| W-02/W-06 | 模板定 pools · 去 JSON | F-26 | 2–3 |
| W-04 | 部门定时 | **F-24** ✅ | — |
| W-05 | 附件预览 | **F-25** ✅ | — |
| W-08 | streaming/N2 | **W-08** ✅ | — |

### 统计

| ID | 议题 | 阶段 |
|----|------|------|
| S-01 | 最小周期统计 | 待验收 |

---

## 🔥 当前执行顺序

1. **先行发布验证**：以 `8244af0` 为候选，在预发复测参与者重叠语义与前端第一批修复；不拆挑依赖提交。
2. **Iteration 4-E UAT**：验证非视频模板能力声明、旧视频模板兼容 Profile 与历史 Run dual-read。
3. **I3-F 生产门禁**：目标环境 Expand/Contract、Link 回填、恢复/回滚演练、连续 7 天观测与 31/31 报告。
4. **前端后续反馈**：继续按 P0–P3 分级，P2/P3 可独立成批。
5. **明确延期**：系统管理员业务边界治理按 KI-011 在 I4 后单独规划。

**下一 actionable**：核对目标服务器当前 commit，以 `8244af0` 做先行发布预发 smoke；I4-E 单独进入 UAT。内测发布仍按 [`deployment-runbook §21`](./manuals/deployment-runbook-ubuntu-2404.md) 执行。

---

## 并行工作线

- 产品/架构：ADR-019 决策语义映射；视频模板领域中立
- 前端：问题清单待接收并分级；模板解耦 Phase 2 UAT
- 工程质量：I3-F 目标环境证据、F-05、测试覆盖、Legacy E 历史兼容清理；KI-011 延后

历史细计划：[`plans/task-center-enhance.md`](./plans/task-center-enhance.md) · 当前主线：[`plans/implementation-plan.md`](./plans/implementation-plan.md)

---

## 📋 中长期（非任务中心主线）

| 方向 | 说明 |
|------|------|
| 岗位编辑器工作台 | Stage 2 增强 |
| S3 对象存储 | 附件生产化 |
| 国际化 | 产品需求后 |
| Ubuntu 回滚演练 | 暂缓 |
