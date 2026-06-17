# Project Filum 路线图

> 🌡️ WARM — 宏观里程碑与当前版本焦点。细粒度排期见 [`plans/`](./plans/)。

| 字段 | 内容 |
|------|------|
| **当前版本** | `0.87.1`（根目录 `VERSION`） |
| **版本主题** | Paradigma memory-bank 对齐 + 工程质量与多工作流统一 |
| **阶段** | Stage 2 / 工作流深化 / 部署演练 |

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
| Memory-Bank Phase 0–2 | done | 协议层 + HOT 六件套 |

---

## 🚧 进行中 / 下一版焦点

| 优先级 | 主题 | 目标 | 计划入口 |
|--------|------|------|----------|
| P0 | Ubuntu 最小回滚演练 | git 回退 + systemd ± 迁移 rollback dry-run | `progress.md`「当前规划焦点」 |
| P1 | 工作流 E 与图引擎统一 | 产品级单一模板源评估与深化 | `plans/implementation-plan.md` |
| P1 | Memory-Bank Phase 3–4 | WARM/COLD 层、引用修复、对齐审查 | `plans/paradigma-memory-bank-refactor-plan.md` |
| P2 | 生命周期规则化 | 默认映射 + 前端结构化配置 | `plans/improvements-stage2-implementation-plan.md` §11 |
| P2 | 通知渠道深化 | 真实 Email/WebSocket、投递观测 | 同上 |
| P3 | 注册方式扩展 | 公开/审批式注册（产品决策后） | `project-brief.md` |
| P3 | E2E 基线刷新 | Playwright live、docker-gui 与发布 commit 同步 | `handbooks/e2e-gui-verification-automation-runbook.md` |

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
主线（工程质量）───── Stage 2 收尾 / 回滚演练 / 回归扩面
        │
        ├─ 工作流 E ─── 模板/调度深化
        ├─ 图引擎 ───── 与 E 统一、视频 v1 运维
        └─ memory-bank ─ Paradigma Phase 3–4
```

细计划不合并进本表；见 `plans/implementation-plan.md`、`workflow-refactor-implementation-plan.md`、`workflow-video-v1-implementation-plan.md`。
