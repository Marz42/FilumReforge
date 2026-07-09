# Copilot Instructions — Project Filum (FilumReforge)

> **完整协议**: [`AGENT_RULES.md`](../AGENT_RULES.md) | **Cursor**: `.cursor/rules/memory-bank-protocol.mdc`

## 🔥 HOT（每次对话必读）

`memory-bank/knowledge/project-brief.md` · `memory-bank/knowledge/architecture.md` · `memory-bank/knowledge/contracts/data-contracts.md` · `memory-bank/knowledge/conventions.md` · `memory-bank/runtime/active-task.md` · `memory-bank/logs/progress/progress.md`

## 工作方式

简体中文 | 写代码前读 HOT | schema 破坏性变更须用户同意 | 不默认 commit | 会话结束追加 `progress.md`

## 专项入口

| 任务 | 文件 |
|------|------|
| 会话启动 | `INIT_PROMPT.md` |
| 对齐审查 | `.github/prompts/memory-bank-alignment-review.prompt.md` |
| ADR / 术语 / 坑位 | `memory-bank/decisions.md` 等 |
| 子系统细节 | `memory-bank/domains/*.md` |
| 部署 | `memory-bank/knowledge/manuals/deployment-runbook-ubuntu-2404.md` |

技术细节见 `memory-bank/conventions.md` 与 `backend/README.md`、`frontend/README.md`。
