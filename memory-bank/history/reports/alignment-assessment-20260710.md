# Project Filum 文档与实现对齐评估

**日期**: 2026-07-10
**审查基线**: `main` @ `42df37b`（`VERSION` = `0.92.0`）
**范围**: HOT memory-bank、implementation-plan/roadmap/progress/changelog、README/部署手册、最近 20 个提交及相关模型/迁移/API/服务/测试

## 1. 结论摘要

整体实现主线清晰，核心架构与最近修复记录基本对齐；主要问题集中在 **0.92.0 后新增 schema 未同步契约**、三态迁移后的旧链接、以及计划/README 中仍残留已完成阶段的旧叙述。

当前主线以 `memory-bank/knowledge/plans/implementation-plan.md` §1 为准：**TC-Transform Phase 0–3 已完成，下一产品主线是 S-01 任务统计（待立项）**。现有统计只覆盖当前任务快照和部门过滤，S-01 仍需先明确周期、rollup、绩效口径与权限边界。

工作区已有用户修改 `INIT_PROMPT.md`，本次审查未触碰。

## 2. 已对齐项

- 模块化单体、Vue 3/FastAPI/PostgreSQL/ARQ/OpenAI SDK 等硬边界与代码一致。
- B-12 的外部 Legacy E API 已移除：`backend/app/api/router.py` 不再挂载 `task_templates`，`backend/tests/test_api.py::test_b12_task_templates_api_is_not_available` 固化 404 行为；F-24 调度由 `WorkflowGraphTemplateScheduleService` 承担。
- 图引擎的条件路由、Context、Notice、Wait-Any 与 graph-first 读侧已落地，证据见 `backend/app/services/workflow_graph_service.py`、`condition_evaluator.py`、`task_service.py` 及相关测试。
- 最近四个修复提交（`7b8bed2`、`7cc6bb4`、`a857fac`、`42df37b`）均已写入 `memory-bank/logs/progress/progress.md`。
- 生产 Dockerfile、Compose、Nginx、启动脚本与发布检查脚本均存在；`.gitattributes` 对 `*.sh` 固定 LF，部署手册主流程与产物一致。

## 3. 问题清单

| 严重度 | 类型 | 问题 | 证据 | 建议 |
|---|---|---|---|---|
| 高 | 文档漂移 | `scope_department_ids` 已新增到图模板 schema，但数据契约未同步 | `backend/alembic/versions/20260709_01_graph_template_scope_departments.py`、`backend/app/models/workflow_graph.py`；`memory-bank/knowledge/contracts/database/graph-engine-schema.md` 无该字段 | 下一次实施前先补 graph-engine contract，并更新 data-contracts 同步时间 |
| 中 | 文档漂移 | implementation-plan §1 已写 S-01，但 §6.6 仍称条件路由、Context、Notice、Wait-Any 和 graph 读侧未实现 | `memory-bank/knowledge/plans/implementation-plan.md` §1/§6.6；对应代码与测试已存在 | 收拢或标记 §6.6 为历史计划，避免把已完成能力列为 backlog |
| 中 | 文档漂移 | roadmap 顶部称 Phase 0–3 完成，但阶段表与“当前执行顺序”仍以 B-12/F-28/F-22 等待办形式呈现 | `memory-bank/knowledge/roadmap.md` | 将旧阶段表标为完成历史，当前执行区只保留 S-01/内测反馈/暂缓项 |
| 中 | 文档漂移 | 根 README 的文档路径、测试基线和“下一步”仍停在三态迁移前/TCE Phase 1 | `README.md` 文档入口、测试基线、下一步；`backend/README.md`、`frontend/README.md` 也引用旧 flat 路径 | 一次性修正三态链接，并用当前基线替换旧 TCE 叙述 |
| 中 | 文档漂移 | `0.92.0` 发布后已有向下兼容 schema/功能与多项修复，但 `[Unreleased]` 为空，版本仍为 `0.92.0` | `git log 6c4b899..HEAD`、`VERSION`、`memory-bank/logs/changelog.md` | 先补 Unreleased；版本建议评估 MINOR，升版须用户确认 |
| 低 | 文档漂移 | data-contracts 与 implementation-plan 内有三态迁移后失效的相对链接/旧路径 | `memory-bank/knowledge/contracts/data-contracts.md`、`memory-bank/knowledge/plans/implementation-plan.md` | 修正为 `knowledge/`、`runtime/`、`logs/` 的真实相对路径 |
| 低 | 表述含混 | 测试数字分散且口径不同：README 仍为 153/106/18，data-contracts 为 252/124/33/48，最新 progress 只记录针对性 E2E 35/35 | 三份文档各自“测试基线” | 下一次发布前跑一次完整质量门，建立单一带 commit 的基线 |

## 4. 建议修复顺序

1. 先修 `scope_department_ids` 数据契约（schema 变更的协议必需项）。
2. 收拢 implementation-plan/roadmap 的历史段落，确保唯一当前主线为 S-01。
3. 修 README 与 HOT/WARM 文档的三态链接、同步 `[Unreleased]`。
4. S-01 立项：先定义统计周期、统计对象、绩效口径、权限和是否需要持久化 rollup，再进入模型/API/UI。
5. 发布前刷新全量测试基线；Ubuntu 最小回滚演练继续按当前决定暂缓。

## 5. 当前主线判定

**当前应聚焦：S-01 任务统计（周期/绩效入口），但必须先产品立项。**

现有 `GET /api/v1/tasks/stats/summary` 与 `/stats/workload` 仅返回当前可见任务的汇总/负载，并支持可选 `department_id`；没有时间范围、周期对比、趋势 rollup 或绩效规则。因此下一步应是 S-01 口径设计，而不是重复建设基础统计页。
