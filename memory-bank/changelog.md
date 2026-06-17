# Changelog

> 🌡️ WARM — 版本发布历史（[Keep a Changelog](https://keepachangelog.com/zh-CN/) 格式）。版本号以根目录 `VERSION` 为准。

## [Unreleased]

### Added

- Paradigma 对齐 memory-bank：HOT 层（`project-brief`、`data-contracts`、`conventions`、`active-task`）
- Paradigma Phase 3：WARM/COLD 层（`roadmap`、`changelog`、`domains/`、`decisions`、`known-issues`、`glossary`）
- `AGENT_RULES.md`、`INIT_PROMPT.md`、`.cursor/rules/memory-bank-protocol.mdc`

### Changed

- `architecture.md` 瘦身；schema 迁至 `data-contracts.md`
- `design-document.md`、`tech-stack.md` 标记【已迁移】，摘要迁至 `project-brief.md`

---

## [0.87.1] - 2026-06-17

### Added

- Memory-Bank Phase 3 WARM/COLD：`roadmap`、`changelog`、`domains/`、`decisions`、`known-issues`、`glossary`
- 对齐审查报告 `history/reports/alignment-assessment-20260617.md`

### Changed

- 根/README、子 README、plans、handbooks 引用指向 Paradigma 文档分工（schema → `data-contracts.md`）
- `backend/README.md` 修正图引擎 graph-first 与 workflow-video 边界描述

## [0.87.0] - 2026-06-17

### Added

- 根目录 `VERSION` 文件，SemVer 基线（对应当前 87 次提交）
- Memory-Bank 外部记忆协议（基于 [paradigma](https://github.com/Marz42/paradigma) 定制）

### Notes

- 此版本号为 **文档体系与协作协议** 基线，不代表产品功能大版本发布
- 产品功能交付历史见 `progress.md` 与 `roadmap.md`
