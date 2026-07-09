---
type: paradigma-plan
title: "Paradigma 对齐方案"
description: "Memory-Bank Phase 0–8 重构方案。"
tags:
  - plan
  - Paradigma
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh:
      - Paradigma
    en:
      - paradigma
---
# Memory-Bank 文档系统重构方案（Paradigma 对齐）

**版本**: v1.0  
**日期**: 2026-06-17  
**状态**: Phase 4 已完成（2026-06-17）；Paradigma 对齐 **Phase 0–4 全部完成**  
**参考基座**: [Marz42/paradigma](https://github.com/Marz42/paradigma)（本地参考克隆 `paradigma/`，已加入 `.gitignore`，不纳入 git）

### 已确认决策（2026-06-17）

| 项 | 决定 |
|----|------|
| `knowledge/manuals/` 命名 | **保留**；仅在 README 标注与 Paradigma `manuals/` 等价 |
| `VERSION` 起始 | **`0.87.0`**（对应当前 87 次提交）；之后按 SemVer |
| `paradigma/` 克隆 | **保留本地参考**；`/paradigma/` 已写入 `.gitignore` |

---

## 1. 背景与目标

### 1.1 现状问题

当前 FilumReforge 的 `memory-bank/` 在 2026-05-14 已完成一次目录重组（`knowledge/manuals/`、`plans/`、`history/`、`archive/`），工程文档质量高、与实现对齐紧密，但存在以下 **Agent 协作层面** 的痛点：

| 痛点 | 表现 |
|------|------|
| 无知识温度分层 | Agent 每次需自行判断读哪些文件；HOT 层过重（`architecture.md` 1600+ 行） |
| 无统一工作流协议 | 规范分散在 `.github/copilot-instructions.md`、各 `*.instructions.md`、`README.md` |
| 职责边界模糊 | `architecture.md` 同时承担蓝图、schema、模块职责、变更日志 |
| 无 `active-task` 焦点 | 当前任务散落在 `plans/*.md` 与 `progress.md` 阶段表中 |
| 无 ADR 集中归档 | 决策散落在 `plans/*-adr.md`、`history/proposals/` |
| 无会话摘要规范 | `progress.md` 以阶段验收为主，缺少 Paradigma 式「每次对话一条」的轻量日志 |

### 1.2 重构目标

借鉴 Paradigma 的 **知识温度体系 + 四阶段工作流 + 模板/运行时分离**，在 **不丢失现有文档价值** 的前提下：

1. 建立清晰的 **HOT / WARM / COLD** 加载策略，降低 Agent 上下文负担
2. 引入 `AGENT_RULES.md` + Cursor Rule 作为 **单一协议源头**
3. 拆分巨型文档，使 `architecture.md` 回归「系统蓝图」定位
4. 保留 Filum 特有的 `plans/` 细粒度实施计划与 `templates/` 工作流 JSON
5. 与现有 `.github/prompts/memory-bank-alignment-review.prompt.md` 对齐审查流程

### 1.3 非目标

- **不**把 Paradigma 的通用 `conventions.md` 原样覆盖 Filum 已在 `.github/instructions/` 中沉淀的技术约束
- **不**采用 Paradigma 模板库的 `.gitignore` 排除 runtime `.md` 机制（Filum 是已有项目，所有 memory-bank 文件应继续 git 跟踪）
- **不**一次性删除 `history/`、`archive/` 历史材料
- **不**在本轮重构中改动业务代码

---

## 2. 两套体系对照

### 2.1 Paradigma 核心模型

```
协议层: AGENT_RULES.md → .cursor/rules/memory-bank-protocol.mdc
入口层: INIT_PROMPT.md（模式 A/B/C/D/F）
记忆层: memory-bank/ 按 🔥HOT / 🌡️WARM / 🧊COLD 分层
版本层: VERSION + changelog.md
工作流: Read → Plan → Execute → Update（对话结束必写 progress）
```

### 2.2 Filum 现行模型

```
协议层: .github/copilot-instructions.md + backend/frontend.instructions.md
入口层: 无统一 INIT_PROMPT；靠 Copilot/Cursor 规则隐式引导
记忆层: memory-bank/ 按「文档类型」分目录（根 / handbooks / plans / history / archive）
版本层: 各文档内嵌版本号（如 architecture v3.12.0），无根目录 VERSION
工作流: 文档对齐审查 prompt；无强制会话结束更新 progress
```

---

## 3. 目标目录结构

```
FilumReforge/
├── AGENT_RULES.md                          # 【新增】IDE 无关协议原文（Filum 定制版）
├── INIT_PROMPT.md                          # 【新增】会话启动模板（含模式 B 续接）
├── VERSION                                   # 【新增】SemVer 单一来源（建议从 v3.12.0 或 v4.0.0 起）
├── .cursor/rules/
│   └── memory-bank-protocol.mdc              # 【新增】Cursor 适配器
│
└── memory-bank/
    │
    ├── 🔥 HOT — 每次对话必读 ─────────────────
    ├── project-brief.md                    # 【新增】由 design-document + tech-stack 摘要提炼
    ├── conventions.md                      # 【新增】Filum 编码/协作规范（从 .github 提炼）
    ├── architecture.md                     # 【瘦身】仅保留蓝图：模块划分、目录树、交互流程、约束
    ├── data-contracts.md                   # 【新增】从 architecture §6 schema + API 契约拆出
    ├── active-task.md                      # 【新增】当前唯一聚焦任务
    ├── progress.md                         # 【改造】保留阶段验收表 + 追加会话摘要区
    ├── README.md                           # 【更新】按温度体系重写索引
    │
    ├── 🌡️ WARM — 按需加载 ─────────────────
    ├── roadmap.md                          # 【新增】宏观里程碑（Phase/Stage 总览）
    ├── changelog.md                        # 【新增】Keep a Changelog 格式版本历史
    ├── plans/                              # 【保留】细粒度实施计划（Filum 特色）
    │   ├── implementation-plan.md
    │   ├── workflow-video-v1-implementation-plan.md
    │   └── ...
    ├── domains/                            # 【新增】按子系统拆分的领域文档
    │   ├── hr-org.md
    │   ├── task-center.md
    │   ├── workflow-graph-engine.md
    │   ├── workflow-video-v1.md
    │   ├── messaging.md
    │   └── knowledge-ai.md
    │
    ├── 🧊 COLD — 排查时读取 ─────────────────
    ├── decisions.md                        # 【新增】集中 ADR（迁入 workflow-video-v1-w0-adr 等）
    ├── known-issues.md                     # 【新增】从 progress 测试基线/遗留项提炼
    ├── glossary.md                         # 【新增】Filum 专有术语（Task E、graph-first 等）
    ├── manuals/                            # 【迁移】原 knowledge/manuals/ 重命名
    │   ├── deployment-runbook-ubuntu-2404.md
    │   ├── user-manual.md
    │   └── ...
    ├── history/                            # 【保留】时点报告与历史提案
    ├── archive/                            # 【保留】已废弃材料
    └── templates/                          # 【保留】工作流 JSON 样例（非 Markdown）
```

> **命名说明**: `knowledge/manuals/` → `manuals/` 是为与 Paradigma 术语对齐；可通过 README 保留旧路径别名说明一个版本周期，减少外链断裂。

---

## 4. 文档映射与迁移策略

### 4.1 一对一映射

| 现行文件 | 目标 | 动作 |
|----------|------|------|
| `design-document.md` | `project-brief.md` | **提炼迁移**：愿景、受众、功能边界、非目标 → project-brief；设计原则可保留摘要或链到 domains |
| `tech-stack.md` | `project-brief.md` §技术栈 + `architecture.md` §技术栈总览 | **合并后归档**：tech-stack 文首标【已归档】，指向新位置 |
| `architecture.md` | `architecture.md`（瘦）+ `data-contracts.md` + `domains/*.md` | **拆分**：§6 schema → data-contracts；各模块细节 → domains |
| `progress.md` | `progress.md` + `known-issues.md` + `roadmap.md` | **重组**：阶段表 → roadmap；测试基线/遗留 → known-issues；底部新增「会话摘要」区 |
| `knowledge/manuals/*` | `manuals/*` | **重命名目录** + README 留 redirect |
| `plans/workflow-video-v1-w0-adr.md` | `decisions.md` ADR 条目 | **迁入** 并原文件留 stub 链接 |
| `.github/copilot-instructions.md` | `AGENT_RULES.md` + `conventions.md` + `.cursor/rules/` | **提炼**，copilot-instructions 改为简短指针 |

### 4.2 保留不动的目录

| 目录/文件 | 理由 |
|-----------|------|
| `plans/` | Filum 多线并行（Stage 2、workflow-video-v1、UI IA），细计划比单一 roadmap 更实用 |
| `history/` | 对齐审查报告（`alignment-assessment-*.md`）是有价值的时点快照 |
| `archive/` | 已标注【已归档】，防止误引用 |
| `templates/*.json` | 项目特有工作流种子，Paradigma 无对应物 |

### 4.3 需新建的 `.template.md`（可选）

Paradigma 用 `.template.md` 供 greenfield 复制；Filum 作为 **已有项目** 建议：

- **方案 A（推荐）**: 直接维护 runtime `.md`，**不引入** `.template.md` 双文件机制，降低维护成本
- **方案 B**: 仅为 `active-task`、`progress` 会话区提供 `.template.md` 作为格式参考，不启用 `.gitignore` 排除

---

## 5. 各 HOT 文件内容边界（拆分原则）

### 5.1 `project-brief.md`（目标 ≤ 300 行）

从 `design-document.md` 提取：

- 产品定位、目标受众（50–100 人企业）
- MVP / 当前阶段功能边界与非目标
- 技术栈一览表（来自 tech-stack）
- 成功指标与风险（摘要）
- **禁止**放入：完整 schema、模块文件路径清单

### 5.2 `architecture.md`（目标 ≤ 400 行）

保留：

- 文档定位与分工说明（更新为 Paradigma 文件引用）
- 系统概览、模块划分表
- 顶层目录结构（前后端/infra）
- 前后端交互宏观流程（mermaid）
- 架构约束（模块化单体、adapter 边界等）
- 各 domain 文档索引

迁出：

- 完整数据库 schema → `data-contracts.md`
- 单模块实现细节 → `domains/*.md`

### 5.3 `data-contracts.md`（新建，承接原 architecture §6）

- ER 关系图（核心表）
- 枚举定义
- 通用 API 响应信封
- 跨模块关键 API 契约索引（细节可链到 backend OpenAPI）
- **维护规则**: schema 迁移后必须同步此文件（写入 AGENT_RULES Update Phase）

### 5.4 `conventions.md`（新建）

从以下来源提炼 Filum 专属规范（非 Paradigma 通用 Vue/FastAPI 模板）：

- `.github/copilot-instructions.md` 技术边界
- `.github/instructions/backend.instructions.md`
- `.github/instructions/frontend.instructions.md`
- Git 提交规范、测试命令、版本管理（SemVer）

### 5.5 `active-task.md`（新建）

- 同一时间 **只有一个** 活跃任务
- 从 `plans/implementation-plan.md` 当前段落 + 用户意图提炼
- 任务完成 → 摘要写入 `progress.md` 会话区 → 开启下一任务

### 5.6 `progress.md`（改造）

结构调整为两区：

```markdown
## 会话摘要（Paradigma 格式，Agent 每次对话追加）
### 2026-06-17 14:30 - [标题]
**完成事项** / **踩坑** / **遗留** / **下一步**

## 阶段验收与测试基线（保留现有内容）
... 现有 W0–W10、Stage 2、pytest 基线表 ...
```

---

## 6. Agent 协议迁移

### 6.1 新增文件

| 文件 | 内容来源 |
|------|----------|
| `AGENT_RULES.md` | Paradigma 协议骨架 + Filum 文档路径定制 + 简体中文 |
| `INIT_PROMPT.md` | Paradigma 模式 B/C 为主（已有项目续接/单任务突击）；模式 F 不适用 |
| `.cursor/rules/memory-bank-protocol.mdc` | 从 AGENT_RULES 同步，`alwaysApply: true` |

### 6.2 改造现有 `.github` 文件

| 文件 | 改造 |
|------|------|
| `copilot-instructions.md` | 缩短为「读 AGENT_RULES + HOT 文件」指针，避免双源漂移 |
| `memory-bank-alignment-review.prompt.md` | 必读列表增加 `data-contracts.md`、`project-brief.md`；报告路径仍为 `history/reports/` |
| `docs-alignment.instructions.md` | 同步新文件分工 |

### 6.3 四阶段工作流（Filum 定制）

1. **Read**: HOT 全读；任务涉及 workflow-video / UI IA 时读对应 `plans/` + `domains/`
2. **Plan**: 中文简述；**data-contracts 变更须用户确认**（与现 copilot-instructions 一致）
3. **Execute**: 遵循 conventions；不无关重构
4. **Update**: 必写 progress 会话摘要；实质修改同步 architecture / data-contracts / active-task / decisions

---

## 7. 分阶段实施计划

### Phase 0 — 准备（0.5 天）✅

- [x] 评审本方案，确认保留 `knowledge/manuals/`（仅 README 标注与 `manuals/` 等价）
- [x] `paradigma/` 保留本地参考；`/paradigma/` 已加入 `.gitignore`
- [x] `VERSION` 起始 `0.87.0`（87 次提交）

### Phase 1 — 协议层（1 天）✅

- [x] 创建 `AGENT_RULES.md`、`INIT_PROMPT.md`、`.cursor/rules/memory-bank-protocol.mdc`
- [x] 创建根目录 `VERSION`（`0.87.0`）
- [x] 精简 `copilot-instructions.md` 为指针
- [x] `memory-bank/README.md` 增加 Paradigma 协议指针与 `handbooks`≈`manuals` 说明
- [x] memory-bank 正文（architecture 等）未改动

### Phase 2 — HOT 层拆分（2–3 天）✅

- [x] 新建 `project-brief.md`（从 design-document + tech-stack 提炼）
- [x] 新建 `conventions.md`
- [x] 新建 `data-contracts.md`（从 architecture §8–§13 拆出，含 schema/枚举/关系）
- [x] 瘦身 `architecture.md`（~1656 → ~558 行）
- [x] 新建 `active-task.md`（当前：Phase 3 入口）
- [x] `progress.md` 已有会话摘要区
- [x] 更新 `memory-bank/README.md` 为温度体系索引
- [x] `design-document.md`、`tech-stack.md` 文首【已迁移】横幅
- [x] 更新 `AGENT_RULES.md`、Cursor Rule、copilot-instructions、`.github/instructions/`

### Phase 3 — WARM / COLD 层（2 天）✅

- [x] 新建 `roadmap.md`、`changelog.md`（`0.87.0` 起）
- [x] 新建 `domains/` 首批 6 篇
- [x] 新建 `decisions.md`、`known-issues.md`、`glossary.md`
- [x] `workflow-video-v1-w0-adr.md` 增加迁入 `decisions.md` 指针
- [x] 更新 `README.md`、`AGENT_RULES.md`、Cursor Rule、`active-task.md`（Phase 4 入口）
- [x] 保留 `knowledge/manuals/`（未重命名为 manuals）

### Phase 4 — 引用修复与验证（1–2 天）✅

- [x] 更新根 `README.md`、`backend/README.md`、`frontend/README.md` 文档链接与边界描述
- [x] 更新 `.github/instructions/docs-alignment.instructions.md`
- [x] plans / handbooks / archive 内 schema 表述指向 `data-contracts.md`
- [x] 对齐审查 `history/reports/alignment-assessment-20260617.md`
- [x] `VERSION` → `0.87.1`；`design-document` / `tech-stack` 已标【已迁移】

### Phase 5 — 持续运营

- [ ] 每次 Agent 会话结束写 progress 会话摘要
- [ ] 每个 Stage/W 阶段完成：更新 roadmap + domains + data-contracts
- [ ] 协议变更：先改 `AGENT_RULES.md`，再同步 `.mdc` 与 copilot-instructions

---

## 8. 风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 巨型 architecture 拆分遗漏 | Agent 读到过时 schema | Phase 2 用 `rg` 对比拆分前后章节；对齐审查报告验证 |
| 外链断裂（handbooks 重命名） | CI/文档链接 404 | Phase 4 全仓库搜索；可暂留 `knowledge/manuals/README.md` stub 指向 manuals |
| 双协议源漂移 | Agent 行为不一致 | copilot-instructions 只保留指针；变更只走 AGENT_RULES |
| progress 体积持续增长 | HOT 层过重 | 会话摘要超过 50 条时归档到 `history/reports/session-log-YYYY.md` |
| 与 Paradigma 后续版本分叉 | 难以吸收上游改进 | AGENT_RULES 文首标注「基于 paradigma @ commit xxx 定制」 |

---

## 9. 验收标准

重构完成当且仅当：

1. Agent 新会话可通过 `.cursor/rules/memory-bank-protocol.mdc` 自动加载 Filum 定制协议
2. HOT 层 6 个文件合计 **< 2000 行**（当前仅 architecture 已超 1600）
3. `memory-bank/README.md` 明确标注 🔥/🌡️/🧊 与加载策略
4. 全仓库无断裂的 `knowledge/manuals/` 引用（或均有 redirect）
5. 对齐审查报告结论为「文档分工清晰，schema 单一来源为 data-contracts.md」
6. 现有 `plans/`、`history/`、`templates/` 功能不受影响

---

## 10. 建议的首次 `active-task.md` 内容

评审通过 Phase 1 后，建议将首个 active-task 设为：

> **任务**: Memory-Bank Paradigma 对齐 — Phase 1 协议层落地  
> **完成标准**: AGENT_RULES + Cursor Rule + VERSION 就绪；copilot-instructions 已改为指针；无 memory-bank 正文变动

---

## 附录 A — paradigma/ 本地参考

`paradigma/` 为本地只读参考克隆，已通过 `.gitignore` 排除，不会进入 git 历史。需要更新参考时可在仓库根目录重新 `git pull`（在 `paradigma/` 内）或删除后重新 clone。

## 附录 B — domains 首批切分建议

| 文件 | 来源（architecture.md 章节） | 关联 plans |
|------|------------------------------|------------|
| `hr-org.md` | HR、组织、权限、生命周期 | implementation-plan Stage 2 |
| `task-center.md` | 任务中心、Inbox-first | ui-refactor-spec-v2 |
| `workflow-graph-engine.md` | 图引擎 Phase 3–11 | workflow-refactor-implementation-plan |
| `workflow-video-v1.md` | 视频工作流 | workflow-video-v1-implementation-plan |
| `messaging.md` | 消息、通知、回执 | improvements-stage2 |
| `knowledge-ai.md` | 知识库、AI Router | design-document §3.5 |

## 附录 C — 与 Paradigma 的差异保留清单（Filum 特色）

| 能力 | 说明 |
|------|------|
| `plans/` 目录 | 多线并行实施的必要粒度，不合并进单一 roadmap |
| `history/reports/alignment-assessment-*.md` | 工程化对齐审查，Paradigma 无此物 |
| `templates/*.json` | 工作流种子数据 |
| `.github/instructions/*.instructions.md` | 可保留为 conventions 的补充细节 |
| 内嵌文档版本号 | 迁移期可与根 `VERSION` 并存，最终以 VERSION + changelog 为准 |
