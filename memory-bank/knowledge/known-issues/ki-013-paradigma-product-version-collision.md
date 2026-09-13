---
type: paradigma-known-issue
title: "KI-013: Paradigma 与 Filum 根 VERSION 语义冲突"
description: "Paradigma 0.7 固定升级与版本门禁把根 VERSION 当作协议发行版本，而 Filum 用它表示产品发布版本。"
tags: [known-issue, paradigma, versioning, migration, compliance]
timestamp: 2026-09-13T00:21:27+08:00
paradigma:
  schema_version: "0.1"
  temperature: cold
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Paradigma 版本冲突, 产品 VERSION, 升级 Profile, pd check]
    en: [Paradigma version collision, product VERSION, upgrade profile, pd check]
  relations:
    caused_by:
      - ../decisions/adr-007-paradigma-alignment.md
    related_to:
      - ../decisions/adr-021-paradigma-070-cli-runtime.md
---

# 当前处理（2026-09-13）

W02 新增仓库入口 `python scripts/pd.py`，在不改动 site-packages 和根产品 VERSION 的前提下，让固定 Paradigma 0.7.0 的版本读取使用既有 `.paradigma/VERSION` 配置。协议文件缺失、路径越界、协议版本与 config 不一致、工具版本未经评审升级仍失败。legacy `.paradigma/tools/` 入口采用相同适配。版本门禁已由本地回归证明可通过；CI 文件、日志元数据和文档关联同步修复。

适配范围限于本项目版本读取与检查；**不声称上游累计 version-upgrade Profile 已兼容**，也不自动执行协议升级。该上游能力仍待支持，后续升级必须重新评审适配器。以下是保留的原始问题与背景。

# Symptom

- `pd migration version-upgrade plan --expected-source-version 0.5.0` 拒绝 Filum：检测到根 `VERSION=0.93.0-rc.1`，而不是协议版本。
- `pd version` 与聚合 `pd check` 报 `PD_VERSION_DISTRIBUTION_DRIFT`：config 为 Paradigma `0.7.0`，根版本为 Filum 产品 `0.93.0-rc.1`。

# Impact

官方累计升级 Profile 不能直接应用于 Filum，也不能把聚合 `pd check` 作为单一全绿门禁。Task/Session/Checkpoint、runtime、Context、index、catalog、Agent adapter 和日志治理本身不受影响，可独立验证。原审查时尚无 CI；W01 已新增 `.github/workflows/check.yml`，使用项目版本适配入口，不再绕过版本检查。

# Root Cause

Paradigma 0.7 的 `read_distribution_version()` 与 version-upgrade `_recognize_source()` 都硬编码读取仓库根 `VERSION`。Filum 在早期 ADR-007 中已把同一文件定义为产品 SemVer，配置目前没有受支持的发行版本路径字段。

# Workaround

- 保留根 `VERSION`，绝不为了协议升级改写产品/RC 版本。
- 用 `.paradigma/VERSION`、`installed_distribution_version` 与 `paradigma_upstream_commit` 独立固定协议身份。
- 使用 `requirements-paradigma.txt` 安装固定 commit 的开发工具。
- 分别执行 `pd config validate`、`pd runtime verify`、`pd context verify`、`pd index verify`、`pd catalog verify`、`pd agent-adapter check` 和合规子门禁；对聚合版本步骤保留已知失败证据。
- strict lint 当前有 64 个 `relations` 缺失 warning（含本次新增 KI-014）；关系应按真实语义逐步补录，不用虚假统一边消警。完成后再启用仓库级 strict CI。

# Permanent Fix

上游应允许在 config 中声明发行版本文件，或让安装/升级 Profile 只比较 `installed_distribution_version` 与显式 upstream identity，不再占用衍生产品的根 `VERSION`。修复后先在 dry-run 中验证不会写 Filum 产品版本，再移除项目兼容字段。

# Related Documents

- [ADR-021](../decisions/adr-021-paradigma-070-cli-runtime.md)
- [Repository Contract](../contracts/repository-contract.md)

# Status

**项目版本检查已适配；上游升级 Profile 兼容缺口仍开放。** 首次确认于 Paradigma `3422ecf` / 2026-08-12。
