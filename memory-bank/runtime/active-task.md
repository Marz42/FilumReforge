---
type: paradigma-runtime-state
title: "当前任务 (Active Task)"
description: "Project Filum 当前唯一聚焦任务。"
tags:
  - runtime
  - active-task
timestamp: 2026-07-15T20:38:43+08:00
paradigma:
  schema_version: 0.5.0
  layer: runtime
  temperature: hot
  lifecycle: ephemeral
  okf_export: False
  update_policy: agent-editable
  archive_to: memory-bank/logs/progress/
---
# 当前任务

> 🔥 HOT — **Iteration 2 已验收并提交；Iteration 3 已启动，I3-A 基座完成、I3-B 双写/Link-first 已开始。**见 [`Iteration 3 实施计划`](../knowledge/plans/workflow-graph-engine-iteration3-implementation-plan.md)。

---

## 任务卡片

| 字段 | 内容 |
|------|------|
| **任务标题** | 工作流图引擎结构收敛与运行时正确性升级 |
| **优先级** | P0 基线 |
| **状态** | Iteration 3 · I3-A 完成 · I3-B 双写/回填进行中 |
| **关联** | 定义冻结 · 对象级授权 · 条件 Join · 双写收口 · 投影恢复 |

---

## 最近完成 ✅

| 交付 | 说明 |
|------|------|
| Iteration 3-A @ 2026-07-15 | HumanTask Link/command receipt 两张真相表与服务基座；新手动兼容/模板投影双写 Link；Task 投影 Link-first；SQLite 全量、PostgreSQL 12/12 通过 |
| Iteration 2 @ 2026-07-15 | 新 Run 切换 `snapshot/graph-v3`；持久化 traversal/activation dependency；显式 routing mode；skip/no-route/End 完成语义；Deep-Reject 失效旧路径；Context expected version；不可变 branch identity；后端全量、PostgreSQL 10/10、前端 type-check 通过 |
| Iteration 1 / I1-B–E @ 2026-07-13 | active/archived 不可变、显式 scope、seed 派生版本、Run canonical snapshot/hash、snapshot/legacy 双 executor、只读 legacy 盘点；SQLite 全量与 PostgreSQL 5/5 通过 |
| Iteration 1 / I1-A @ 2026-07-13 | `WorkflowAccessPolicy` 统一保护 7 类资源；AUTH-GAP 三组转正；API 44 项与后端全量通过 |
| ADR 验收 @ 2026-07-13 | 用户统一采纳 ADR-012–016；Iteration 0 决策闸门通过 |
| Iteration 0 基线 @ 2026-07-13 | 7 个缺陷编号/11 strict xfail、PostgreSQL 并发基座、统一基线报告、ADR-012–016；无业务/schema/API/前端变更 |
| 图引擎稳健升级方案 @ 2026-07-13 | 按项目事实重排为安全/版本冻结 → 路径语义 → 写所有权 → Handler → 投影/运维 → Legacy 清理 |
| Docker 前端依赖同步 @ 2026-07-13 | lockfile 哈希变化时自动 `npm ci` 刷新命名卷；修复旧卷缺少 `mammoth` |
| S-01 实施 @ 2026-07-11 | Employee 本人/经理子树/Admin-HR 全局；上海周期；DB 聚合；5 指标、人员表、明细下钻 |
| S-01 实施计划 @ 2026-07-11 | 权限、最小功能、周期/指标口径、API、阶段与 4–5 日预估；待审批 |
| npm 安全基线 @ 2026-07-11 | `npm ci` / `npm audit` 0 vulnerabilities；移除无修复版 `xlsx`，Excel 预览改为安全数据渲染 |
| 任务中心实现探索 @ 2026-07-11 | 输出 S-01 读模型/口径、搜索一致性、壳层拆分与测试建议 |
| 测试基线恢复 @ 2026-07-10 | backend 293 collected；Vitest 54/143；Playwright 35/35；type-check/build PASS |
| 近期直接回归 @ 2026-07-10 | scope/delete/MIME/附件继承/关闭采集投影 + PublishTaskDialog/CapturePanel |
| 文档/契约对齐 @ 2026-07-10 | 补 `scope_department_ids` 契约；收拢主计划/路线图/README/Unreleased |
| 测试覆盖审查 @ 2026-07-10 | 确认无覆盖率/CI；backend venv 失效；frontend 依赖缺失；近期六组回归待补 |
| Paradigma v0.5.0 三态迁移 @ `0.92.0` | runtime/logs/knowledge 三态结构落定；OKF YAML frontmatter 全量 |
| 注册决策 @ `0.92.0` | 公开/审批式注册明确不做，仅邀请制 |
| **F-29 管理员归档** @ `0.91.0` | `POST /tasks/{id}/archive` · 终止图 Run · 详情「更多 → 归档任务…」 |
| **Admin 跟踪督办** @ `0.91.0` | Admin/HR 跟踪 Tab 全量未完成任务 · 关联方式「督办」 |
| **逾期延期** @ `0.91.0` | 跟踪/详情延期入口 · 逾期不阻断推进 · 须设更晚截止时间 |
| **N10→N11 误归档** | `efa450c` materialize 尾节点 + 出边 node_key 回退 |
| **N7 剪辑师列表** | `314bb6f` post_production 池 + instance_id |
| **F-25 / F-24** | 附件预览 · 周期调度 @ `0.90.0` |

---

**下一 actionable**：继续 I3-B：对存量关系执行 dry-run 异常报告与受控回填，补 lifecycle 同步和 fallback 指标；之后进入 Coordinator 写所有权切换与 standalone Task。S-01 统计 Tab 仍保留为待用户验收事项。
