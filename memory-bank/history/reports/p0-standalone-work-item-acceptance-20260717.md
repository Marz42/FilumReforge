# P0 Standalone Work Item — 上线前验收报告

**日期**: 2026-07-17  
**范围**: Iteration 3 下游适配 — standalone Task 作为一等工作项（任务中心分桶、动作契约、转办、跨部门候选）  
**状态**: **P0 批冻结就绪** — 可进入批次二（Nginx / Markdown），**不建议在未完成本报告证据留存前推生产**

---

## 1. 架构原则确认（已落地）

| 原则 | 证据 |
|------|------|
| standalone 不重新图化 | 场景 A/C E2E + `test_created_standalone_task_has_no_graph_rows` |
| `assignment_mode` 一等字段 | 迁移 `20260717_01` + 创建/读取 DTO |
| 当前行动人与状态分离 | `current_action_owner_id` / `action_type` / `requires_action` |
| 前端 standalone 消费 `available_actions` | `TaskDetailShell.vue` + `domain/task-detail/actions.ts` |
| workflow 暂保持 legacy graph 双轨 | 未改 workflow 前端动作推导；graph 回归套件全绿 |
| 转办不触碰 Runtime | standalone delegate 无 Link/Node/Instance |
| 候选与命令授权一致 | 场景 D E2E |
| REVIEW 创建人 TODO 闭环 | 场景 A/B/F |
| 转办后旧办理人失权 | 场景 C/E |

### 默认值（已确认）

```text
standalone assignment_mode: direct
standalone delegate authority:
  actor == current_assignee
  OR actor has task_admin_override (ADMIN/HR)
workflow action rendering: legacy graph path (temporary dual-track)
```

---

## 2. 最低回归矩阵 — 自动化证据

### 场景 A–F：API 级 E2E

**文件**: `backend/tests/test_standalone_work_item_e2e.py`  
**运行**: `pytest tests/test_standalone_work_item_e2e.py -q`  
**结果**: **14 passed**

| 场景 | 覆盖 |
|------|------|
| A | L2 创建 → L4 TODO → 开工 → 提交 → L2 REVIEW TODO → 验收 → 双方 History；无图行 |
| B | 退回返工 → L4 再提交 → 再验收；审计历史 append-only |
| C | TODO/DOING 转办；REVIEW 稳定 409；ADMIN 转办 `delegated_by_admin` 审计 |
| D | managed/organization 候选；伪造跨部门拒绝；转办候选与命令一致 |
| E | 顺序冲突：双 delegate、delegate+stale submit |
| F | REVIEW 不重复进 Tracking；creator=assignee/watcher/admin 不重复 |

### 场景 E：PostgreSQL 真并发

**文件**: `backend/tests/test_standalone_work_item_postgres_concurrency.py`  
**运行**: `POSTGRES_TEST_ADMIN_DSN=postgresql://filum:filum@127.0.0.1:5433/postgres pytest -m postgres -q`  
**结果**: **22 passed**（含 graph 并发基线 + 5 项 standalone 并发）

| 并发用例 | 预期 |
|----------|------|
| assignee + ADMIN 同时转办 | 仅一次 transfer；败方 `ConflictError` |
| 重复 delegate 并发 | 仅一条 delegate 审计 |
| delegate vs submit | 仅一方成功 |
| delegate vs start_work | 状态一致、无重复 delegate |
| submit 与 creator inbox 并发读 | 提交后 creator inbox 含 REVIEW |

**实现要点**: standalone 状态命令在 `TaskService` 使用 `SELECT … FOR UPDATE` + assignee compare-and-set，防止双转办静默覆盖。

### 场景 G：图任务兼容

**策略**: 不重复造轮子；依赖现有 graph / task-center 回归：

- `test_api.py` phase3/4/5 手动任务图路径
- `test_workflow_graph_iteration3*.py`
- `test_tce_phase1_graph_projection_inbox.py` 等

**全量后端**: `pytest -q` → **311 passed**, 1 warning（既有 httpx cookie deprecation）

### 单元 / 不变量

**文件**: `backend/tests/test_standalone_work_item.py`  
**新增**:

- `unsupported_assignment_mode` 稳定拒绝 handshake
- `task_action_policy` 纯派生（无 Task 突变、无审计写入）
- REVIEW 创建人离职时 ADMIN 验收兜底

---

## 3. 迁移回滚演练

**用例**: `tests/test_migrations.py::test_alembic_upgrade_and_downgrade`  
**结果**: head 升级表集合包含 `tasks`；`20260717_01`（`assignment_mode` CHECK）在 PostgreSQL ephemeral 库 upgrade→downgrade 通过。

---

## 4. 本批额外修复（测试驱动）

| 问题 | 修复 |
|------|------|
| 转办目标为 suspended 用户返回 401 | 改为 `ConflictError`（409），避免前端误判会话失效 |
| assignee 与 ADMIN 并发双转办均成功 | delegate 增加 assignee CAS + 行锁 |

---

## 5. 已知限制 / 后续批次

| 项 | 说明 |
|----|------|
| handshake 指派模式 | 创建接口显式拒绝；完整状态机不在 P0 |
| REVIEW reviewer 显式字段 | 当前依赖 `creator_id`（非空）；离职兜底为 ADMIN/HR |
| workflow `available_actions` | 仍为空，前端走 graph legacy；需 shadow comparison 后再迁移 |
| 批次二 | Nginx 64m、Markdown + DOMPurify + XSS 测试 — **独立提交/验收** |

---

## 6. 退出标准核对

- [x] API 级最低回归矩阵（A–F）
- [x] 并发转办 PostgreSQL 测试
- [x] PostgreSQL 专项套件（`-m postgres` strict）
- [x] 迁移回滚演练（Alembic head↔base）
- [x] 验收报告留存（本文档）
- [ ] **P0 批 git 冻结提交**（待用户 review 后 commit/tag）
- [ ] 批次二（Nginx / Markdown）

---

## 7. 建议执行命令（复现）

```powershell
cd backend
python -m pytest tests/test_standalone_work_item_e2e.py tests/test_standalone_work_item.py -q

$env:POSTGRES_TEST_ADMIN_DSN='postgresql://filum:filum@127.0.0.1:5433/postgres'
$env:FILUM_REQUIRE_POSTGRES_TESTS='true'
python -m pytest -m postgres -q

python -m pytest -q
```
