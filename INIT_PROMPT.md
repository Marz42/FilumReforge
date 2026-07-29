# INIT_PROMPT.md — 会话启动模板（Project Filum）

> **使用方式**：根据场景复制对应模板，将 `{{PLACEHOLDER}}` 替换为实际内容后，粘贴到 IDE 对话框。
>
> **协议全文**：`AGENT_RULES.md`  
> **当前版本**：根目录 `VERSION`（SemVer，起始 `0.87.0`）
> **Paradigma Harness**：`0.5.0`；运行态/日志/知识三态分离，使用独立 session logs。

---

## 模式 B：已有项目续接（推荐）

```
你好，这是一个已有项目（Project Filum）。请按以下步骤操作：

1. 读取 `AGENT_RULES.md`，按以下顺序加载 memory-bank：
   - `runtime/active-task.md`
   - `knowledge/index.md`
   - 🔥 HOT：project-brief、architecture、data-contracts、repository-contract、conventions
   - 🌡️ WARM：与任务相关的 roadmap、domains/、plans/、knowledge/manuals/、子项目 README
   - `logs/progress/` 下最近的 session log
2. 执行 `git log --oneline -n 20` 确认最近主线。
3. 审查文档与代码一致性，简要说明：
   - 哪些信息可能过时
   - 当前应聚焦的主线（以 implementation-plan 为准）
4. 然后我们继续推进：{{具体的下一步任务}}
5. 完成后按 AGENT_RULES Update Phase 创建独立 session log、同步知识与索引并运行质量门禁。
```

---

## 模式 C：单任务突击

```
你好，请按以下步骤操作：

1. 读取 `runtime/active-task.md`、`knowledge/index.md` 和 AGENT_RULES.md 中的 🔥 HOT 文件。
2. 理解当前项目状态后，直接执行任务：
   {{具体任务描述}}
3. 执行过程中遵循 Plan/Execution checkpoints；完成后按 Update Phase 更新 runtime/logs/knowledge。
4. 结束时告知："Memory-bank 已更新完毕。本次更新了：[文件列表]"
```

---

## 模式 D：架构决策讨论

```
你好，我们需要做一个架构决策。

【背景】
{{简要描述当前遇到的架构问题或需要决策的事项}}

请按以下步骤操作：

1. 读取 active-task、knowledge/index、architecture、repository contract 和相关 decisions。
2. 给出 2–3 个可行方案及优缺点。
3. 给出推荐方案及理由。
4. 待我确认后，将决策写入对应 ADR 文档（Phase 2 起统一写入 decisions.md）。
```

---

## 模式 E：Memory-Bank 对齐审查

```
你好，请对 memory-bank 与实际代码做一次对齐审查。

1. 严格遵循 `.github/prompts/memory-bank-alignment-review.prompt.md`。
2. 必读：active-task、knowledge/index、project-brief、architecture、data-contracts、repository-contract、最近 session log、roadmap、部署 runbook、各 README。
3. 用迁移、模型、服务、路由、测试验证事实。
4. 输出报告到 `memory-bank/history/reports/alignment-assessment-YYYYMMDD.md`。
5. 区分「已对齐」「文档漂移」「实现未落地」，附证据路径。
```

---

## 模式 P：Paradigma 文档重构（维护者）

```
你好，请继续 Project Filum 的 Paradigma 对齐重构。

1. 阅读 `memory-bank/knowledge/plans/paradigma-memory-bank-refactor-plan.md` 确认当前阶段。
2. 阅读 `AGENT_RULES.md` 中的迁移期路径对照表。
3. 仅执行计划中当前 Phase 的范围，不要越界改动。
4. 完成后创建独立 session log、更新 active-task 并说明下一阶段入口。
```

---

## 模式 G：DESIGN.md 设计器

```
你好，我需要创建或完善项目视觉设计规范 DESIGN.md。

1. 读取 active-task、knowledge/index、HOT knowledge 和现有 DESIGN.md。
2. 先确认项目类型、视觉风格、参考产品和品牌色。
3. 分阶段确认 Overview、Colors、Typography、Layout & Spacing、Components、Do's and Don'ts。
4. 颜色对比度至少满足 WCAG AA 4.5:1；组件引用已定义 token。
5. 写入 DESIGN.md 后运行 `python .paradigma/tools/pd-check-all.py`；如可用，再运行 `npx @google/design.md lint DESIGN.md`。
6. 后续 UI 任务将 DESIGN.md 作为 WARM 参考。
```

---

## 模式 H：Paradigma Harness 升级/结构迁移

```
你好，请升级本项目的 Paradigma Harness。

【上游源路径或仓库】{{Paradigma 最新源}}

1. 读取 AGENT_RULES、active-task、knowledge/index 和当前 `.paradigma/config.yaml`。
2. 运行 `python .paradigma/tools/pd-diagnose.py --upstream {{本地上游路径}} --json`；若仅有远程仓库，先核对官方 VERSION、主分支提交与协议文件。
3. 先列出 structure/tools/schema/config/protocol 差异，不覆盖项目定制内容。
4. 升级工具和 schema，补齐 `runtime/`、`logs/progress/`、`knowledge/` 三态结构。
5. 协议先改 AGENT_RULES，再同步 INIT_PROMPT、Cursor/Copilot 与其他系统 Prompt。
6. 运行 `pd-sync-index.py --write` 和 `pd-check-all.py`，记录上游版本/提交与保留差异。
```

---

## 自定义提示原则

- **始终让 Agent 先读 memory-bank**（按温度分级，不要一次性塞入 architecture 全文上下文外的冗余材料）
- **明确交付物**：填文档、写代码、还是出审查报告
- **约定结束动作**：Update Phase 创建独立 session log、更新 active-task/knowledge、同步索引并告知更新文件
