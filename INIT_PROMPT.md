# INIT_PROMPT.md — 会话启动模板（Project Filum）

> **使用方式**：根据场景复制对应模板，将 `{{PLACEHOLDER}}` 替换为实际内容后，粘贴到 IDE 对话框。
>
> **协议全文**：`AGENT_RULES.md`  
> **当前版本**：根目录 `VERSION`（SemVer，起始 `0.87.0`）

---

## 模式 B：已有项目续接（推荐）

```
你好，这是一个已有项目（Project Filum）。请按以下步骤操作：

1. 读取 `AGENT_RULES.md`，按知识温度体系加载 memory-bank：
   - 🔥 HOT：design-document、architecture、progress、tech-stack、plans/implementation-plan、根 README
   - 🌡️ WARM：与任务相关的 plans/、handbooks/user-manual、子项目 README
2. 执行 `git log --oneline -n 20` 确认最近主线。
3. 审查文档与代码一致性，简要说明：
   - 哪些信息可能过时
   - 当前应聚焦的主线（以 implementation-plan 为准）
4. 然后我们继续推进：{{具体的下一步任务}}
5. 完成后按 AGENT_RULES Update Phase 更新 progress.md 等文档。
```

---

## 模式 C：单任务突击

```
你好，请按以下步骤操作：

1. 读取 AGENT_RULES.md 中的 🔥 HOT 文件。
2. 理解当前项目状态后，直接执行任务：
   {{具体任务描述}}
3. 执行完成后，按 AGENT_RULES Update Phase 更新相关 memory-bank 文档。
4. 结束时告知："Memory-bank 已更新完毕。本次更新了：[文件列表]"
```

---

## 模式 D：架构决策讨论

```
你好，我们需要做一个架构决策。

【背景】
{{简要描述当前遇到的架构问题或需要决策的事项}}

请按以下步骤操作：

1. 读取 AGENT_RULES.md HOT 文件，以及相关的 plans/*-adr.md（如有）。
2. 给出 2–3 个可行方案及优缺点。
3. 给出推荐方案及理由。
4. 待我确认后，将决策写入对应 ADR 文档（Phase 2 起统一写入 decisions.md）。
```

---

## 模式 E：Memory-Bank 对齐审查

```
你好，请对 memory-bank 与实际代码做一次对齐审查。

1. 严格遵循 `.github/prompts/memory-bank-alignment-review.prompt.md`。
2. 必读：architecture、design-document、progress、implementation-plan、部署 runbook、各 README。
3. 用迁移、模型、服务、路由、测试验证事实。
4. 输出报告到 `memory-bank/history/reports/alignment-assessment-YYYYMMDD.md`。
5. 区分「已对齐」「文档漂移」「实现未落地」，附证据路径。
```

---

## 模式 P：Paradigma 文档重构（维护者）

```
你好，请继续 Project Filum 的 Paradigma 对齐重构。

1. 阅读 `memory-bank/plans/paradigma-memory-bank-refactor-plan.md` 确认当前阶段。
2. 阅读 `AGENT_RULES.md` 中的迁移期路径对照表。
3. 仅执行计划中当前 Phase 的范围，不要越界改动。
4. 完成后更新 progress.md 并说明下一阶段入口。
```

---

## 自定义提示原则

- **始终让 Agent 先读 memory-bank**（按温度分级，不要一次性塞入 architecture 全文上下文外的冗余材料）
- **明确交付物**：填文档、写代码、还是出审查报告
- **约定结束动作**：Update Phase 更新 progress + 告知更新了哪些文件
