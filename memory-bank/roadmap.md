# Project Filum 路线图

> 🌡️ WARM — 宏观里程碑与当前版本焦点。细粒度排期见 [`plans/`](./plans/)。

| 字段 | 内容 |
|------|------|
| **当前版本** | `0.89.0`（根目录 `VERSION`） |
| **版本主题** | 任务中心 v2 IA 2.0（三视图 + 任务统计 + Shell 拆分） |
| **阶段** | Stage 2 / 工作流深化 / **任务中心增强（TCE）** |

---

## ✅ 已完成里程碑

| 里程碑 | 完成 | 关键交付 |
|--------|------|----------|
| Phase A | done | 文档入口、脚手架、Docker Compose |
| Phase 1 Foundation | done | 用户、部门、档案、附件、任务基础 |
| Phase 2 Collaboration | done | 状态机、评论留痕、ARQ、统计 |
| Phase 3 HR Governance | done | 生命周期、字段权限、多岗位、代理 |
| Phase 4 Workflow & Messaging | done | 模板 E、审批流、消息中心、多视图 |
| Phase 5 Knowledge & AI | done | 知识库、RAG、`@系统`、Push、PWA |
| 重构 Step 1–7 | done | IA 壳层、任务中心、汇报、人员工作台 |
| UI IA Phase A–F | done | 登录/壳层/任务/汇报/组织/总览 |
| 工作流图引擎 Phase 11 | done | dual-write、多节点、outbox、graph-first 读路径 |
| 工作流 E 首批 | done | 模板实例运行态、扇出/汇聚、设计器 |
| Stage 2 Phase 0–6 | done | 模板治理、生命周期联动、邀请注册、消息深化 |
| 视频工作流 v1 W0–W10 | done | 选题会、表单引擎、按题 fork、E2E 硬化 |
| Memory-Bank Phase 0–4 | done | 协议层 + HOT/WARM/COLD + 对齐审查 |
| 任务中心 v2 设计 | done | UX 规格 v2.1 + 交互 Demo 评审通过（2026-06-18） |
| 任务中心 v2 TC-P0 | done | Action Profile、N1 单表单、Run 列、用户态 @ `7bc242c` |
| 任务中心 v2 TC-P1 | done | `dispatch_topic`、VideoTrackingPanel、打回/退回、participant 收口 |
| 任务中心 v2 TC-P2 | done | 三视图 + 统计 Tab + `TaskDetailShell` + `ui_profile` @ `0.88.0` |
| 任务中心 v2 TC-P2+ | done | Legacy E UI 移除、图模板单入口 @ `0.89.0` |

---

## 🔥 下一焦点（P0）

| 优先级 | 主题 | 目标 | 计划入口 |
|--------|------|------|----------|
| **P0** | **任务中心架构债** | B-12 Legacy E 统一 · F-05 Shell 拆分 · E2E 基线刷新 | [`active-task.md`](./active-task.md) · [`domains/task-center.md`](./domains/task-center.md) §10 |

**TCE 阶段切片**

| 阶段 | 交付概要 | 状态 |
|------|----------|------|
| Phase 1 | B-01/B-03/B-02 + F-02/F-03/F-08（PR-A/PR-B） | ✅ **完成** |
| Phase 2 | batch API、snapshot 字段、hydration（B-04–B-07, F-01, F-04, F-07） | ✅ **完成** |
| Phase 3 | 部门统计、Shell 拆分、分页（B-06, B-09–B-11, F-06, F-09） | ✅ **完成** |
| Phase 4 | 多文案部门共用模板（B-16, F-17 §6.2.1） | ✅ **完成** |
| Phase 5 | **TC-P3**（aggregate_mode、结束采集）+ 清理 | ✅ **完成**（B-12 另立项） |

**TC-P0–P2 切片（已完成）**

| 阶段 | 交付概要 | 状态 |
|------|----------|------|
| TC-P0 | Profile + N1 单表单 + 进度文案 + 列表 Run 列 | ✅ |
| TC-P1 | `dispatch_topic` + 跟踪页增量派发 + submit_mode/退回 | ✅ |
| TC-P2 | 看板/甘特/统计入口 + `TasksView` 拆分 | ✅ @ `0.88.0` |

---

## 🚧 并行 / 后续焦点

| 优先级 | 主题 | 目标 | 计划入口 |
|--------|------|------|----------|
| P1 | 工作流 E 与图引擎统一 | 产品级单一模板源（**B-12** backlog） | `task-center-enhance.md` §8 · ADR-005 |
| P2 | 生命周期规则化 | 默认映射 + 前端结构化配置 | `plans/improvements-stage2-implementation-plan.md` §11 |
| P2 | 通知渠道深化 | 真实 Email/WebSocket、投递观测 | 同上 |
| P2 | Docker 图模板实测收尾 | A–F 手工 / live E2E | `handbooks/workflow-video-v1-docker-runbook.md` |
| P3 | 注册方式扩展 | 公开/审批式注册（产品决策后） | `project-brief.md` |
| P3 | E2E 基线刷新 | Playwright live、docker-gui、UAT 与发布 commit 同步 | `handbooks/e2e-gui-verification-automation-runbook.md` |
| 暂缓 | Ubuntu 最小回滚演练 | git 回退 + systemd ± 迁移 rollback dry-run | `deployment-runbook-ubuntu-2404.md` §21.8 |

---

## 📋 计划中（中长期）

| 方向 | 说明 | 触发条件 |
|------|------|----------|
| 岗位编辑器工作台 | 结构化岗位权限与可见范围 | Stage 2 后续增强 |
| S3 兼容对象存储 | 附件存储生产化 | 部署规模扩大 |
| 工作流设计器拖拽化 | 非当前首版目标 | 结构化设计器稳定后 |
| 国际化 | 多语言 UI | 产品需求明确 |

---

## 并行工作线

```
主线（产品）────────── 任务中心增强 TCE（Phase 1 就绪 → PR-A/PR-B）
        │
        ├─ 视频 v1 ──── 选题会模板运维；Phase 4 多部门实例化（§6）
        ├─ 工作流 E ─── 后端待删；统一评估 → TCE Phase 5（TC-P3）
        ├─ 工程质量 ─── Docker 实测 / E2E live 基线 / B-03 迁移
        └─ memory-bank ─ Paradigma 维护
```

细计划见 [`plans/task-center-enhance.md`](./plans/task-center-enhance.md)、[`plans/task-center-v2-implementation-plan.md`](./plans/task-center-v2-implementation-plan.md)、[`plans/implementation-plan.md`](./plans/implementation-plan.md)。
