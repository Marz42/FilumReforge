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

- 先确认文档分工： [memory-bank/architecture.md](../../memory-bank/architecture.md) 记录当前工程基线与 schema， [memory-bank/design-document.md](../../memory-bank/design-document.md) 记录产品目标与边界， [memory-bank/progress.md](../../memory-bank/progress.md) 记录完成状态与验测， [memory-bank/plans/implementation-plan.md](../../memory-bank/plans/implementation-plan.md) 记录下一轮工作流。
- 写文档前先核对实现事实；优先用模型、迁移、服务、路由、前端路由/视图、测试和真实运行命令做证据，不把目标设计写成当前已实现。
- 如果任务涉及继续开发、部署、发布或“当前主线是什么”，先看 `git log --oneline -n 20`，再结合 [memory-bank/plans/implementation-plan.md](../../memory-bank/plans/implementation-plan.md) 判断，不要把仓库写回“正在补齐 Phase 5”或“仍在 Step 7 收口”。
- 对齐审查时明确区分三类结论：文档已对齐、文档漂移但实现存在、设计目标存在但实现未落地；不要把三类问题混写。
- 更新 `memory-bank` 时做最小、可验证的改动；重大实现变化优先更新 `architecture.md`，阶段状态和验测变化更新 `progress.md`，目标和路线变化再更新 `design-document.md` 或 `implementation-plan.md`。
- [memory-bank/archive/outdated/design-document.md.md](../../memory-bank/archive/outdated/design-document.md.md) 和 [memory-bank/history/proposals/refactor-plan.md](../../memory-bank/history/proposals/refactor-plan.md) 属于历史材料，可引用为背景，但不能当当前实现事实。
- 如果 README 仍写着“缺 production compose”等与当前工件冲突的描述，应根据实际文件判断为文档漂移，而不是重复过时说法。
