
> **Filum CLI 入口（W02）**：本文中的 `pd` 指 `python scripts/pd.py`（Windows 可用 `backend\.venv\Scripts\python.exe scripts/pd.py`）。它只适配固定 Paradigma 0.7.0 的协议版本路径；上游裸 `pd` 不识别 Filum 根产品 VERSION 的区别。所有 dry-run / write 规则保持不变。
# Copilot Instructions — Project Filum

> 完整协议以 [`AGENT_RULES.md`](../AGENT_RULES.md) 为准；本文件只映射 Paradigma `0.7.0` 最小操作语义。

## 启动

1. 运行 `pd task status` 与 `pd session status`；需要新 Task/Session 时先 dry-run，再以 `--write` 执行。
2. 将任务转成 path/symbol/keyword/budget，运行 `pd context build ... --write` 和 `pd context verify`。
3. 只读取 Context Manifest 选择的文档与理由；前端任务把 `DESIGN.md` 作为显式 path signal。

## 执行

- Task、Session、Checkpoint YAML 是事实；`active-task.md`、`handoff.md`、`context-manifest.yaml` 是 generated projection，不直接编辑。
- 长期事实写 knowledge；阻塞、暂停、恢复和完成通过 `pd task block/unblock/suspend/resume/complete/abort`。
- 可恢复边界使用 `pd session checkpoint`；只修改任务范围，保留用户既有改动。
- 简体中文；破坏性 API/schema 变更先征得用户同意；不默认 commit。

## 收口

1. 更新受影响的 knowledge/ADR/contract/known issue/changelog。
2. 运行 `pd index rebuild`、`pd index verify`、范围测试、`pd check`；按需运行 `pd runtime verify`、`pd catalog rebuild/verify`。
3. 最终运行 `pd agent-adapter check` 与 `pd compliance check --profile strict`。
4. source 变化后重建并验证 Context Manifest；写最终 Checkpoint，随后 `pd session end --write`。
5. Task 完成时在 Session end 后 `pd task complete --write`；否则保持 active 或明确 block/suspend。

专项入口：会话模板见 `INIT_PROMPT.md`；对齐审查见 `.github/prompts/memory-bank-alignment-review.prompt.md`；工程规范见 `memory-bank/knowledge/conventions.md`。
