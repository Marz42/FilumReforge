---
type: paradigma-plan
title: "Project Filum — 路线图"
description: "宏观里程碑、Iteration 4 完成态、分批发布与历史任务中心改造记录。"
tags:
  - roadmap
  - milestones
  - tc-transform
timestamp: 2026-08-26T00:22:00+08:00
paradigma:
  schema_version: 0.1
  temperature: warm
  lifecycle: evolving
  update_policy: requires-human-confirmation
  epistemic_status: decision
  plan_status: in-progress
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
| **最新试用候选** | `v0.93.0-rc.3`（不可变注释标签，固定 `21975a6`；主开发线位于其后） |
| **版本主题** | 工作流图引擎 Iteration 4 · 模板领域中立与稳定化 |
| **阶段** | **Iteration 5-E 工程完成；目标环境观察/人工签字 → 生产 canary → 稳定观察 → Iteration 6**；隔离 PostgreSQL/Redis、rebuild/full shadow、严格投影 UAT 已补证 |
| **最后整理** | 2026-08-26 — `v0.93.0-rc.3` 固定 `21975a6`；KI-014 只读 Schema Drift 审计与迁移设计已启动，代码/历史 DDL 根因已确认，目标 PostgreSQL 实时统计待只读连接 |

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
| **Paradigma v0.7.0 协议升级** | done | CLI Task/Session/Checkpoint · Context Manifest · catalog · M0–M4 治理修复 @ `3422ecf`；KI-013 保留版本路径差异 |
| **Task Center P0–P2 审计修复** | done | 锁/CAS · 分页/附件 · 模板评审候选链 @ `0.92.1` |
| **工作流图引擎 Iteration 1–3-F 工程实现** | done | snapshot · graph-v3 · Link/receipt · ownership/UoW · readiness 工具；生产证据仍 gated |
| **模板解耦 Phase 1 + Phase 2 首批** | done / UAT | tags · capabilities · archive · structured authoring |
| **Iteration 4-A–E** | done | Handler Registry · HumanTask/Approval/Deliverable/Notification · 领域中立 capability snapshot |
| **模板 scope/依赖数据治理** | done / UAT | 只读审计 · 分级建议 · 父子 scope/旧编码检查 · 前端修正版入口 @ 2026-08-10 |
| **Iteration 4 UAT 验收准备** | done / manual UAT | P-01～P-07 · 模板/部门候选 · S-01 样本 · 明确不代签 @ 2026-08-10 |
| **F-05 详情壳层拆分首批** | done / follow-up | `useTaskDetailData` · 单次初始加载 · last-selection-wins · 独立降级 @ 2026-08-10 |
| **F-05 详情壳层拆分第二批** | done / follow-up | `useTaskDetailActions` · `useTaskAssignmentActions` · 权限/命令分离 @ 2026-08-11 |
| **F-05 详情壳层拆分第三批** | done / follow-up | `useTaskDetailCollaboration` · 附件/评论独立板块 · Shell 1,285 行 @ 2026-08-12 |
| **F-05 详情壳层拆分第四批** | done / follow-up | `TaskDetailActivityTimeline` · 原排序/文案/附件操作 · Shell 1,153 行 @ 2026-08-12 |
| **F-05 详情壳层拆分收口批** | done | `TaskDetailWorkflowPresentation` · `TaskDetailGraphTelemetry` · Shell 838 行 · 73 files / 211 tests @ 2026-08-12 |
| **Iteration 5-A 投影契约与加法迁移** | done | 三类投影契约 · ORM · `20260812_01` Expand-only · PostgreSQL fresh base→head @ 2026-08-23 |
| **Iteration 5-B Projector 与重建基座** | done | `20260812_02` checkpoint · 三源流幂等消费 · 失败隔离 · PostgreSQL 全量重建 97/28/282 @ 2026-08-23 |
| **Iteration 5-C Shadow Comparison** | done / production observation gate | `20260812_03` · 隐私安全差异记录 · final full shadow 407/407 · 本地无差异/缺失/孤儿/lag @ 2026-08-23 |
| **Iteration 5-D 运维与可观测性** | done | `20260812_04` · Admin-only 异常工作台 · PostgreSQL marker 22 passed · runtime_ready=true @ 2026-08-23 |
| **RC2 模板可见性热修** | done / trial retest | 可读/可管理双查询去重 · 逐模板动作授权 · test-first @ 2026-08-11 |
| **KI-009 独立任务动作授权收口** | engineering done / manual retest | standalone 详情只消费 `available_actions` · 状态命令校验当前阶段执行人 · workflow 兼容路径不变 @ 2026-08-12 |
| **Iteration 5-E 受控投影读取** | engineering done / production gated | 投影优先 · 动态回退 · 严格 canary · PostgreSQL rebuild 97/28/282 · full shadow 407/407 · strict live UAT 9/9 @ 2026-08-23 |
| **KI-015 Strict 投影缺口遥测** | engineering done / staging alert gated | inbox/tracking/history 缺口分类 · request/Task ID · 最近 checkpoint · Admin Operations error issue · 非授权 Task 不记录 @ 2026-08-26 |
| **N4 专用评审自审边界** | done | 专用 review node 以真实上游交付人作为自审基准，指定 reviewer 可验收；普通模板交付任务保护不变 @ 2026-08-23 |
| **P0 收口后续非阻断债务** | tracked | KI-014 Phase B（`20260827_01`）工程完成、目标 Phase C 观察与 Phase D 待补；KI-015 已完成；KI-016 logout 在途 401（P2）· KI-017 入口 chunk 体积（P2）仍开放 |

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
| **F-05** | `TaskDetailShell` 完整拆分 | ✅ 数据、动作、资料评论、活动时间线、工作流展示与节点追踪均已抽取，约 1,989 → 838 行 |
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

1. **KI-014 Phase C 目标观察**：在含真实数据的预发部署 Phase A/B（`20260827_01`），按 [`Phase C 观察清单`](./manuals/2026-09-04-ki014-phase-c-observation-checklist.md) 复测；未完成观察前不执行 Phase D contract。
2. **真实预发与人工签字**：完成 RC3、Iteration 4、设计器 Phase 2、S-01 与 KI-009 的业务账号验收；2026-08-23 自动化多账号 UAT 是工程证据，不代替业务签字。
3. **Iteration 3-F 连续门禁**：补齐 Link/reconciliation 7 天与 31/31 报告；当前隔离环境 readiness 无 blocker 不能替代连续观察。
4. **生产准备**：注入真实 secret、TLS/域名/可信代理，记录附件与数据库备份 RPO/RTO、负责人、通知和维护窗口。
5. **5-E 生产 canary**：先保持 projection reads + fallback，目标环境 rebuild/full shadow 达标并验证 `strict_projection_gap` 日志采集/通知后分批关闭 fallback；异常时立即回开 fallback。
6. **稳定观察期**：确认 fallback 命中、ROOT shell 新增量、投影差异、lag 和异常 Run 达标。
7. **Iteration 6**：再次单独批准后停止兼容写入并清理 Legacy E/JSON/feature flags；不得与观察期重叠。
8. **生产变更窗口**：完成 secret/TLS/备份恢复/迁移 dry-run/回滚预案后，按上线 checklist 批准部署。
9. **后续专项**：KI-011 按用户决定暂不推进；M-09 与 `run_kind` dual-read 收窄等待策略和生产证据。

**下一 actionable**：把已通过的隔离 PostgreSQL Phase B（`20260827_01`）与严格 5-E 脚本复制到真实预发，按 Phase C 清单复测并保持 fallback 开启；接入并验证 `strict_projection_gap` 告警。之后再提交 Phase D contract 与生产关闭 fallback 的独立批准；Iteration 6 与生产准入仍须另行批准。

---

## 并行工作线

- 产品/架构：验证 ADR-019 与领域中立模板在真实业务样本中的语义，不新增视频特例
- 前端：完成 KI-009、RC2、模板解耦 Phase 2 与 S-01 UAT；继续接收试用反馈
- 工程质量：I3-F 与 Iteration 5 目标环境证据、测试覆盖和可观测性；Legacy E 清理与 KI-011 均延后

历史细计划：[`plans/task-center-enhance.md`](./plans/task-center-enhance.md) · 当前主线：[`plans/implementation-plan.md`](./plans/implementation-plan.md)

---

## 📋 中长期（非任务中心主线）

| 方向 | 说明 |
|------|------|
| 岗位编辑器工作台 | Stage 2 增强 |
| S3 对象存储 | 附件生产化 |
| 国际化 | 产品需求后 |
| Ubuntu 回滚演练 | 暂缓 |

# Status

Machine status: `in-progress`.
