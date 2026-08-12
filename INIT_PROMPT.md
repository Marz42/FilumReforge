# INIT_PROMPT.md — Project Filum 会话模板

> 产品版本见根 `VERSION`；Paradigma 协议版本见 `.paradigma/VERSION`，当前固定为 `0.7.0` / `3422ecf95109d48cfa89036ae96b4085201baef4`。完整规则见 `AGENT_RULES.md`。

---

## 模式 B：已有项目续接（推荐）

```text
你好，这是 Project Filum 的已有项目续接任务。

1. 读取 AGENT_RULES.md。
2. 运行 pd task status 与 pd session status；无 active Task/Session 时先 dry-run，再用 --write 启动。
3. 执行 git log --oneline -n 20 确认最近主线。
4. 将本次意图规划为 path/symbol/keyword/budget，运行 pd context build ... --write 与 pd context verify。
5. 按 Context Manifest 的 selected documents/reasons 读取上下文；不要递归扫描全部 knowledge 或 progress logs。
6. 简要说明当前主线、可能漂移和验证边界，然后推进：{{具体任务}}
7. 收口时按 AGENT_RULES 完成索引、测试、pd check、Checkpoint、Session end 与 Task 状态更新。
```

---

## 模式 C：单任务突击

```text
你好，请按 AGENT_RULES.md 处理以下任务：{{具体任务}}

先恢复 Task/Session，构建并验证 Context Manifest；写代码前说明目标、边界、验证与风险。只改任务范围，完成后更新相关 knowledge，执行范围测试、pd check、最终 Checkpoint 与 Session end，并报告剩余风险。
```

---

## 模式 D：架构决策讨论

```text
你好，我们需要讨论一个架构决策：{{背景}}

请以 architecture、repository contract、相关 domain/contract/ADR 为显式 Context signals，构建并验证 Manifest；给出 2–3 个方案、权衡与推荐。待我确认后再写 ADR；若会改变 API 或数据库 schema，必须单独征得同意。
```

---

## 模式 E：Memory-Bank 对齐审查

```text
你好，请对 Memory-Bank 与实际代码做一次对齐审查。

遵循 .github/prompts/memory-bank-alignment-review.prompt.md，以相关路径和关键词构建 Context；用迁移、模型、服务、路由和测试验证事实。报告写入 memory-bank/history/reports/alignment-assessment-YYYYMMDD.md，并区分已对齐、文档漂移、实现未落地。
```

---

## 模式 G：DESIGN.md 设计器

```text
你好，请创建或完善 DESIGN.md。

把 DESIGN.md、frontend/ 和相关设计知识作为显式 Context signals。分阶段确认视觉方向、颜色、字体、布局与组件；对比度至少满足 WCAG AA 4.5:1。完成后运行范围测试、pd check；如可用，再运行 npx @google/design.md lint DESIGN.md。
```

---

## 模式 H：Paradigma 协议升级/结构迁移

```text
你好，请升级本项目的 Paradigma 协议。

【上游源】{{Paradigma 本地 clone 或可信远程 ref}}

1. 检查 Filum 与上游工作树、版本、commit 和 remote freshness。
2. 运行 pd diagnose --upstream {{路径}}，并先报告 structure/tools/schema/config/protocol 差异。
3. 优先使用固定 migration Profile 的 dry-run/plan；如果 Profile 与 Filum 产品 VERSION 或已有定制冲突，停止 apply，记录差异并制定等价、可审计迁移，不得改写产品版本。
4. 更新 config/schema/tools；协议先改 AGENT_RULES，再同步 Cursor、Copilot、INIT_PROMPT 和相关仓库 Prompt。
5. 通过 pd lifecycle 命令迁移 runtime，不直接编辑 YAML facts 或 generated projections。
6. 重建并验证 index/runtime/catalog/context，运行 pd check、pd agent-adapter check、pd compliance check --profile strict。
7. 记录上游版本/提交、保留差异、未通过门禁和回滚点。
```

---

## 提示词原则

- 明确任务目标、交付物和不允许扩大的边界。
- 用显式 Context signals 替代“把整个 Memory-Bank 全读一遍”。
- Task/Session/Checkpoint 是运行事实；progress log 只在版本、Batch 或人工审计需要时追加。
- 结束时要求报告验证、Task/Session 状态、Memory-Bank 变更与风险。
