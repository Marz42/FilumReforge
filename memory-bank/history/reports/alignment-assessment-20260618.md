# Project Filum 文档与实现对齐评估

**日期**: 2026-06-18  
**审查范围**: 工作区恢复、全量测试复跑、memory-bank 对齐更新；`git HEAD` = `98ad370`  
**关联**: [`progress.md`](../../progress.md)、[`roadmap.md`](../../roadmap.md)、[`alignment-assessment-20260617.md`](./alignment-assessment-20260617.md)

---

## 1. 结论摘要

| 维度 | 判断 |
|------|------|
| **整体对齐度** | **高** — `HEAD` 代码与 memory-bank 主干一致 |
| **工作区状态** | **已修复** — 409 文件误删后 `git restore .` 恢复 |
| **测试基线** | **212 passed, 1 skipped** + vitest 119 + Playwright mock 9/9 |
| **本次更新** | `architecture` v3.12.1、`data-contracts` 图引擎摘要、测试基线、损坏链接 |

**一句话**: 实现与文档重新对齐；`data-contracts` 已补图引擎表摘要与 Phase 5 状态；剩余缺口为 Docker A–F 实测、migration PostgreSQL 环境、docker-gui/live 基线刷新。

---

## 2. 对齐项

### 2.1 工作区与代码

- `git restore .` 后工作树干净 @ `98ad370`
- 路由、模型、迁移与 `architecture.md` §5.2 一致
- Feature flags：`workflow_graph_engine_enabled=true`、`task_center_v2_enabled=true`、`workflow_graph_template_engine_enabled=false`（默认）

### 2.2 Memory-bank

- HOT 六件套已更新同步日期与测试数字
- `data-contracts.md` 新增 §10.41–48、图引擎枚举、模板版本字段、`report` 附件说明
- `active-task.md` 增加验收 checklist
- 损坏的 `[active-task.md]` 链接（`\x07` 控制字符）已修复

### 2.3 测试

| 层 | 结果 |
|----|------|
| pytest | 212 passed, 1 skipped（Alembic 往返，PostgreSQL 不可用） |
| vitest | 39 files / 119 tests |
| Playwright mock | 9/9 |

---

## 3. 问题清单

| # | 严重度 | 类型 | 问题 | 建议 |
|---|--------|------|------|------|
| 1 | 高 | 环境 | 工作区曾 409 文件误删 | 跑测试/部署前检查 `git status` |
| 2 | 低 | 测试 | migration 1 skip | 启动 Compose postgres 或修正 `POSTGRES_TEST_ADMIN_DSN` |
| 3 | 中 | 实现缺失 | Docker A–F 手工实测未完成 | 继续 `active-task.md` |
| 4 | 中 | 实现缺失 | docker-gui / playwright_live 未重跑 | 大版本前刷新 |
| 5 | 低 | 文档 | `data-contracts` 图引擎仍为摘要级 | 可按域拆表或链 ORM（非阻塞） |
| 6 | 中 | 产品 backlog | E/图引擎统一、生命周期规则 UI | 见 `roadmap.md` P1–P2 |

---

## 4. 本次文档变更

| 文件 | 变更 |
|------|------|
| `architecture.md` | v3.12.1 文首、Dialog 入口、active-task 链接 |
| `data-contracts.md` | API 索引、§9 枚举、§10.16 版本字段、§10.41–48、Phase 5 状态、§12 基线 |
| `progress.md` | 会话摘要、测试基线表、已知问题 |
| `active-task.md` | 状态 + 验收 checklist |
| `known-issues.md` | 基线数字、误删坑位 |
| 本报告 | 新增 |

---

## 5. 证据索引

| 主题 | 路径 |
|------|------|
| 测试基线 | `memory-bank/progress.md` §测试基线 |
| 图引擎 ORM | `backend/app/models/workflow_graph.py` |
| 图/视频 API | `backend/app/api/routes/workflow_graph_engine.py` |
| 迁移 skip | `backend/tests/test_migrations.py` L101 |
| 上轮评估 | `alignment-assessment-20260617.md` |
