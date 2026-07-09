---
description: "Use when updating memory-bank, README files, architecture notes, progress records, implementation plans, deployment runbooks, or writing alignment assessments and implementation reports."
name: "Filum Docs Alignment"
applyTo:
  - "README.md"
  - "backend/README.md"
  - "frontend/README.md"
  - "infra/docker/README.md"
  - "memory-bank/**/*.md"
---

# Filum Docs Alignment

- 先确认文档分工（Paradigma 温度体系，见 [`memory-bank/README.md`](../../memory-bank/README.md)）：
  - 🔥 `project-brief.md` — 产品摘要
  - 🔥 `architecture.md` — 工程蓝图、流程
  - 🔥 `data-contracts.md` — **schema、枚举、API**（不再写入 architecture 正文）
  - 🔥 `conventions.md`、`active-task.md`、`progress.md`
  - 🌡️ `roadmap.md`、`plans/`、`domains/`
  - 🧊 `decisions.md`、`known-issues.md`、`glossary.md`、`knowledge/manuals/`
- 写文档前先核对实现事实；优先用模型、迁移、服务、路由、测试和可运行命令作证据。
- 继续开发类任务：先看 `git log --oneline -n 20` 与 `plans/implementation-plan.md`、`roadmap.md`。
- 对齐审查区分：已对齐 / 文档漂移 / 实现未落地。
- 重大实现变化：模块流程 → `architecture.md`；schema → `data-contracts.md`；验测 → `progress.md`；产品边界 → `project-brief.md`。
- `archive/`、`history/proposals/` 为历史材料，不作现行事实来源。
