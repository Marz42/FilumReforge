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

- 先运行 `pd task status`、`pd session status`，再用本次任务的 path/symbol/keyword/budget 构建并验证 Context Manifest。
- 确认文档分工（Paradigma 温度体系，见 [`memory-bank/README.md`](../../memory-bank/README.md)）：
  - 🔥 `project-brief.md` — 产品摘要
  - 🔥 `architecture.md` — 工程蓝图、流程
  - 🔥 `data-contracts.md` — **schema、枚举、API**（不再写入 architecture 正文）
  - 🔥 `knowledge/index.md`、`conventions.md`、`active-task.md`
  - 🌡️ `roadmap.md`、`plans/`、`domains/`
  - 🧊 `decisions/`、`known-issues/`、`glossary.md`、`knowledge/manuals/`、`logs/progress/` session logs
- 写文档前先核对实现事实；优先用模型、迁移、服务、路由、测试和可运行命令作证据。
- HOT/WARM/COLD 是检索元数据；按 Manifest selections/reasons 读取，不固定递归扫描所有 HOT 或最近日志。
- 继续开发类任务：把 `git log --oneline -n 20`、`plans/implementation-plan.md`、`roadmap.md` 作为主线判断信号。
- 对齐审查区分：已对齐 / 文档漂移 / 实现未落地。
- 重大实现变化：模块流程 → `architecture.md`；schema → `data-contracts.md`；验测 → 独立 session log；产品边界 → `project-brief.md`。
- 先更新 source document，再运行 `pd index rebuild` 与 `pd index verify`；禁止手工维护 generated block。
- Task/Session/Checkpoint YAML 是运行事实；`active-task.md`、`handoff.md`、`context-manifest.yaml` 是投影，不直接编辑。
- 旧 `memory-bank/logs/progress/0000-legacy-progress.md` 是升级前历史汇总，不得修改；新 progress log 仅在版本、Batch 或人工审计需要时追加。
- 收口运行范围测试、`pd check`，写最终 Checkpoint 并结束 Session；strict 门禁用 `pd agent-adapter check` 与 `pd compliance check --profile strict`。
- `archive/`、`history/proposals/` 为历史材料，不作现行事实来源。
