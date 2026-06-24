# Project Filum 路线图

> 🌡️ WARM — 宏观里程碑与**任务中心改造计划**。全貌见 [`domains/task-center.md`](./domains/task-center.md)。

| 字段 | 内容 |
|------|------|
| **当前版本** | `0.89.0`（根目录 `VERSION`） |
| **版本主题** | 任务中心三大模块对齐（单步 · 任务流 · 统计） |
| **阶段** | **TC-Transform Phase 2** — 任务流能力扩展 |
| **最后整理** | 2026-06-23 — Phase 0–1 完成 · Phase 2 启动 |

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
| 视频 Live E2E A–F | done | streaming · 8080 7/7 @ `b3e7918` |

---

## 任务中心产品架构（三大模块）

| 模块 | 入口 | 改造焦点 |
|------|------|----------|
| **单步任务** | 建立任务 | F-22 抄送 · F-21 跨部门 |
| **任务流** | 任务模板实例化 | **F-28** 多部门池 · F-23 模板链 · F-26 设计器 |
| **任务统计** | stats Tab | S-01 周期/绩效（暂缓立项） |

决策索引：[`decisions.md`](./decisions.md) **ADR-009**（单步）· **ADR-010**（任务流）

---

## 改造计划（TC-Transform）

按依赖排序；细项与代码锚点见 [`domains/task-center.md`](./domains/task-center.md) §6–§13。

### Phase 0 — 架构收口（P0）· 立即

| ID | 交付 | 验收 |
|----|------|------|
| **B-12** | 删除 Legacy E runtime（`task_templates` API · `TaskTemplateService` · Legacy 定时） | 实例化/调度仅图引擎；迁移或归档历史 E 实例 |
| **F-05** | `TaskDetailShell` 完整拆分 | 可维护性；行为不变 |
| **E2E 基线** | UAT / docker-gui / Playwright live 与 `b3e7918` 同步 | CI/手工 runbook 绿 |

### Phase 1 — 正确性 + 单步补齐（P1）· Phase 0 后

| ID | 交付 | 验收 |
|----|------|------|
| **F-28** | 制作 fork 时 **`copywriters` 池 = 批次发起部门**（或 `instance_department` 语义） | B 部 Run → N4/N12 → B 部经理；A → A；`post_production` 仍固定 C |
| **F-22** | 建立任务 Dialog + `TaskCreateRequest.watcher_user_ids` | 创建即 `TaskWatcher` + 通知 |
| **F-10–F-12** | 抛光（PublishDialog 抽出等） | 可选并行 |

**F-28 为阻塞项**：多文案部共用模板的产品承诺；优先于 F-23。

### Phase 2 — 任务流能力扩展（P2）

| ID | 交付 | 验收 |
|----|------|------|
| **F-23** | **通用模板链**：Run/节点完成 → 配置触发下一 `WorkflowGraphTemplate`；发布时 **防环** | 不限于 video fork；拒绝 A→B→A |
| **F-27** | 任务流 **跨部门边界 CC**（组织树 manager，不经负责人门控） | 与 F-21 共享路由内核 |
| **F-21** | 单步 **跨部门路由 + 路径 CC** | 组织树；深树性能记 tech debt |
| **W-08** | streaming 模式 **N2 空壳/engine skip** | ROOT-only 增量派发 UX 一致 |
| **F-26** | 设计器 **`department_pools` 部门选择器** + 逐步去 JSON | 含 launch_schema/routing 表单化 |

### Phase 3 — 体验与共用增强（P3+）

| ID | 交付 | 验收 |
|----|------|------|
| **F-25** | 附件预览/试听（md/docx/xlsx/wav/图片） | ✅ 应用内预览 Dialog · 单步 + 任务流交付物 |
| **F-24** | 部门/子树 **图模板定时实例化** | ✅ schedulable · 双 Tab · 重叠校验 · 通知 · run-now |
| **S-01** | 任务统计：周期 rollup + 绩效入口 | 产品立项后；可独立路由 |

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
| W-05 | 附件预览 | F-25 | 3 |
| W-08 | streaming/N2 | TBD | 2 |

### 统计

| ID | 议题 | 阶段 |
|----|------|------|
| S-01 | 周期/绩效 | 暂缓 |

---

## 🔥 当前执行顺序（推荐）

```
B-12 ─┬─► F-28 ─► F-22
      ├─► F-05
      └─► E2E 基线
              │
              ▼
      F-23 · F-27/F-21 · W-08 · F-26
              │
              ▼
      F-25 · F-24 · S-01（立项后）
```

**下一 actionable**：**S-01** 任务统计周期/绩效（产品立项后）。

---

## 并行工作线

```
主线 ─── TC-Transform Phase 0→1→2
  ├─ 架构 B-12 / F-05
  ├─ 任务流 F-28 → F-23
  ├─ 单步 F-22 → F-21
  ├─ 设计器 F-26
  └─ 质量 E2E / Docker live
```

细计划：[`plans/task-center-enhance.md`](./plans/task-center-enhance.md) · [`plans/implementation-plan.md`](./plans/implementation-plan.md)

---

## 📋 中长期（非任务中心主线）

| 方向 | 说明 |
|------|------|
| 岗位编辑器工作台 | Stage 2 增强 |
| S3 对象存储 | 附件生产化 |
| 国际化 | 产品需求后 |
| Ubuntu 回滚演练 | 暂缓 |
