---
type: paradigma-plan
title: "KI-014 PostgreSQL Schema Drift 审计与迁移设计"
description: "用只读证据确认历史 ORM/DDL 漂移，并以可回滚的 expand/contract 批次消除 Alembic autogenerate 差异。"
tags: [plan, active, postgresql, alembic, schema-drift, migration]
timestamp: 2026-09-12T20:27:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: decision
  plan_status: in-progress
  retrieval_hints:
    zh: [KI-014, Schema Drift, Alembic check, 只读审计, expand contract]
    en: [KI-014, schema drift, alembic check, read-only audit, expand contract]
  relations:
    resolves:
      - ../known-issues/ki-014-postgresql-alembic-schema-drift.md
    related_to:
      - ./implementation-plan.md
      - ../roadmap.md
      - ../manuals/2026-09-04-ki014-phase-c-observation-checklist.md
---

# KI-014 PostgreSQL Schema Drift 审计与迁移设计

> **计划状态：PHASE C OBSERVATION TOOLING COMPLETE / TARGET OBSERVATION PENDING**
>
> Phase A/B 已在 `61ea3d3` 固定，隔离 PostgreSQL 已执行 `20260827_01` expand migration。Phase C 的强制只读聚合审计入口已完成并在空隔离库验证；真实数据分布、完整业务周期和人工批准仍必须来自目标预发。

## 1. 目标与完成定义

目标是让 ORM metadata、迁移链和真实 PostgreSQL schema 对同一契约达成一致，并使 `alembic check` 返回 clean。关闭 KI-014 前必须同时满足：

1. 在目标 PostgreSQL 的只读事务中归档列定义、约束、索引、状态 distinct 值与 nullable 计数；
2. 每项漂移明确数据库或 ORM 哪一侧为权威，不直接采用 autogenerate 的破坏性建议；
3. expand、应用兼容、contract 分批实施，生成并审阅离线 SQL，提供 upgrade/downgrade 与回滚边界；
4. PostgreSQL fresh base→head、现存备份恢复→head、head→previous→head、应用回归和 `alembic check` 全部通过；
5. 更新 Known Issue、实施计划、发布检查与 Paradigma 投影文件。

## 2. 当前证据与根因判定

| 漂移组 | 2026-08-23 PostgreSQL 证据 | 当前代码/历史 DDL 根因 | 权威决策 |
|---|---|---|---|
| `employment_events.trigger_status` | `VARCHAR(32)` → ORM non-native Enum | 历史迁移已建 `VARCHAR(32)` 和小写值 check；ORM `build_value_enum` 的推导长度为 10 | 保留数据库 `VARCHAR(32)`、小写值与显式 check；把 ORM metadata 长度对齐到 32，不改线上数据 |
| `tasks.status`、`task_logs.from_status/to_status` | `VARCHAR(6)` → ORM non-native Enum | 早期 DDL 只有小写 `todo/doing/review/done`；当前 `TaskStatus` 增加 7 字符 `blocked`，而 `build_enum` 默认持久化大写成员名 | 以公开枚举 `.value` 和历史 DDL 的小写值为长期契约；先审计大小写混存，再兼容迁移到 `VARCHAR(16)` + 三个独立命名的小写值 check |
| `idx_users_invitation_token_hash` | autogenerate 建议删除数据库索引 | 迁移创建索引，ORM `User.__table_args__` 漏声明；登录邀请按 token hash 等值查询 | 数据库索引为权威；补 ORM `Index`，不得删除线上索引 |
| 三个 workflow graph nullable 列 | DB nullable → ORM non-null | `20260713_01` 以 nullable expand 列和 server default 上线，回填后没有 contract 为 NOT NULL | ORM non-null 业务不变量为权威；先查 NULL、回填、验证约束，再 SET NOT NULL |

额外风险：`TaskLog.from_status` 与 `to_status` 当前复用同名 `task_status` Enum 自动 check，在同一表上不能形成清晰且唯一的约束命名。contract 迁移应关闭这三列的自动 check，改为 `ck_tasks_status_value`、`ck_task_logs_from_status_value`、`ck_task_logs_to_status_value` 三个显式约束。

## 3. 目标环境只读审计

以下查询必须在目标环境以只读账号或 `BEGIN TRANSACTION READ ONLY` 执行；结果只保留聚合计数和 schema 元数据，不导出 token、用户、任务正文或 JSON 内容。

```sql
BEGIN TRANSACTION READ ONLY;
SHOW transaction_read_only;
SELECT current_database(), current_schema(), current_setting('server_version_num');
SELECT version_num FROM alembic_version;

SELECT table_name, column_name, data_type, character_maximum_length,
       is_nullable, column_default
FROM information_schema.columns
WHERE (table_name, column_name) IN (
  ('employment_events', 'trigger_status'),
  ('tasks', 'status'),
  ('task_logs', 'from_status'),
  ('task_logs', 'to_status'),
  ('workflow_graph_templates', 'scope_mode'),
  ('workflow_graph_instances', 'engine_version'),
  ('workflow_graph_instances', 'executor_kind')
)
ORDER BY table_name, column_name;

SELECT status::text AS value, count(*) FROM tasks GROUP BY status::text ORDER BY value;
SELECT from_status::text AS value, count(*) FROM task_logs GROUP BY from_status::text ORDER BY value;
SELECT to_status::text AS value, count(*) FROM task_logs GROUP BY to_status::text ORDER BY value;
SELECT trigger_status::text AS value, count(*)
FROM employment_events GROUP BY trigger_status::text ORDER BY value;

SELECT
  count(*) FILTER (WHERE scope_mode IS NULL) AS template_scope_mode_nulls
FROM workflow_graph_templates;
SELECT
  count(*) FILTER (WHERE engine_version IS NULL) AS instance_engine_version_nulls,
  count(*) FILTER (WHERE executor_kind IS NULL) AS instance_executor_kind_nulls
FROM workflow_graph_instances;

SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = current_schema()
  AND tablename = 'users'
  AND indexname = 'idx_users_invitation_token_hash';

SELECT c.conrelid::regclass::text AS table_name, c.conname,
       pg_get_constraintdef(c.oid) AS definition, c.convalidated
FROM pg_constraint c
WHERE c.conrelid IN (
  'employment_events'::regclass, 'tasks'::regclass, 'task_logs'::regclass,
  'workflow_graph_templates'::regclass, 'workflow_graph_instances'::regclass
)
ORDER BY table_name, c.conname;
ROLLBACK;
```

审计门禁：发现未知状态值、大小写之外的拼写、NULL 数量无法解释、缺失邀请索引或数据库 revision 不是 `20260812_04` 时停止迁移设计落地，先登记数据修复方案。

### 3.1 隔离 PostgreSQL 只读证据（2026-08-27）

- 默认 compose 数据库 revision 为 `20260722_01`，未用于 KI-014 head 审计，也未升级或改写。
- 复用 Playwright 隔离 PostgreSQL（端口 35432）确认 revision `20260812_04`；事务内 `transaction_read_only=on`。
- 三类 task status 列均为 `VARCHAR(6)`；status distinct 结果为空，未知值计数为 0。该库没有业务行，因此这里只能证明结构和脚本，不代表生产数据分布。
- workflow graph 三个目标列的 NULL 计数均为 0；邀请 token hash 索引存在。
- Phase A 后 `alembic check` 已不再报告 employment trigger 类型或邀请索引差异，只剩 task status 宽度和三个 nullable 差异。
- 实际 employment trigger check 名为 `ck_employment_events_employment_events_trigger_status_check`；ORM metadata 已按真实物理名修正。

## 4. Expand / compatibility / contract 设计

### Phase A — metadata-only 与无损对齐

1. [x] `build_value_enum` 接受显式 `length` / `create_constraint`；`EmploymentEvent.trigger_status` metadata 固定为 32，并以历史迁移中的原名声明显式 check。
2. [x] 在 `User.__table_args__` 声明 `idx_users_invitation_token_hash`；现存 PostgreSQL 不执行 drop/create，fresh schema 由迁移链继续创建。
3. [x] task status 使用 `CompatibleValueEnum(VARCHAR(16))` 过渡类型：读取时接受大小写历史值并映射到 `TaskStatus(value.lower())`，写入只产生小写值。本阶段没有收窄线上 check，也没有批量修改数据。

#### Phase A 工程证据（2026-08-27）

- `backend/app/core/db_types.py`：新增大小写兼容、只写枚举 value 的过渡类型；未知应用值和数据库值 fail-fast。
- `backend/app/models/task.py`：`tasks.status`、`task_logs.from_status/to_status` 暴露为 `VARCHAR(16)` metadata；旧大写和历史小写均可读取。
- `backend/app/models/hr_governance.py`：`trigger_status` 长度与数据库 `VARCHAR(32)` 对齐，check 名保持 `employment_events_trigger_status_check`，不制造第二个自动约束。
- `backend/app/models/user.py`：补齐邀请 token hash 索引声明，不生成删除索引建议。
- `backend/tests/test_db_types.py`：覆盖小写写入、大写兼容读取、未知值拒绝、索引/约束 metadata 和 Alembic type comparison。
- 后端全量 `pytest tests -q --cache-clear` 通过；PostgreSQL 测试因本机数据库不可连接而按既有条件跳过。`alembic heads` 仍为 `20260812_04`。

### Phase B — expand migration

1. [x] `20260827_01` 将 `tasks.status`、`task_logs.from_status/to_status` 扩到 `VARCHAR(16)`；validated check 暂时按 `lower(value)` 接受合法状态，保证旧应用和新应用可同时运行。
2. [x] 对三个 nullable 列执行确定性回填：
   - `scope_mode IS NULL`：`scope_department_ids` 为非空数组时填 `departments`，否则填 `global`；
   - `engine_version IS NULL`：填 `legacy-v1`；
   - `executor_kind IS NULL`：填 `legacy`。
3. [x] 添加临时 `CHECK (... IS NOT NULL) NOT VALID`，随后 `VALIDATE CONSTRAINT`；隔离 PostgreSQL 上六个 KI-014 check 均为 validated。
4. [x] 保留既有 server defaults，避免旧部署在滚动窗口中插入 NULL；是否移除 default 不属于 KI-014。

#### Phase B 工程证据（2026-08-27）

- PostgreSQL 离线 SQL 已审阅：只包含三次确定性回填、三列 `VARCHAR(16)` expand、六个 `NOT VALID → VALIDATE` check 和 revision 更新；无 drop/table rewrite/状态归一化。
- 隔离 PostgreSQL `20260812_04 → 20260827_01 → 20260812_04 → 20260827_01` 通过；最终 revision 为新单 head。
- 动态临时 PostgreSQL 完成 fresh base→head→base 方言测试并自动销毁。
- SQLite 使用当前 metadata + stamp 策略完成 `previous→head→previous→head`，第二次 upgrade 实际覆盖 `VARCHAR(6)→16`。
- 后端全量测试通过。Phase B 后 `alembic check` 只剩三个 nullable diff，符合 Phase D 才执行 `SET NOT NULL` 的设计。

### Phase C — compatibility deploy 与观察

部署可双读 task status、只写小写值的应用版本，观察至少一个完整业务周期：

- 未知值解码计数为 0；
- 新写入不再出现大写状态；
- `BLOCKED` 任务与 task log 可正常创建、读取和回放；
- 邀请 token 查询命中索引，认证行为无回归；
- 三个 workflow graph 列不再产生 NULL。

#### Phase C 工程入口（2026-08-27）

- [x] 新增 `backend/app/scripts/audit_ki014_schema_compatibility.py`，从环境变量读取 DSN，不接受命令行明文连接串。
- [x] 审计在 `SET TRANSACTION READ ONLY` 后执行并最终 rollback；输出仅含 revision、schema 元数据、聚合状态计数、NULL 计数、约束及索引健康度。
- [x] `--since` 必须带时区，用于区分观察窗口内的新写入；窗口内未知或非小写状态、workflow NULL 均使自动门禁失败。
- [x] 邀请索引以 `pg_index` 的 valid/ready 状态和强制禁用 seqscan 的 `EXPLAIN` 验证“可被规划器使用”；这不宣称真实认证流量已经命中索引。
- [x] 空隔离库运行自动数据库门禁通过，但报告明确标记 `structure_only_empty_status_tables`、`representative_data_claimed=false` 和 `phase_d_ready=false`。
- [ ] 在含代表性数据的目标预发执行部署前基线与至少一个完整业务周期的 `--since` 观察。
- [ ] 完成 `BLOCKED` 创建/读取/日志回放及邀请认证行为 UAT，并由责任人批准 Phase D。

### Phase D — contract migration

1. 在事务内确认所有 task status `lower(value)` 均属于 `todo/doing/review/blocked/done`，再把合法大写值归一化为小写。
2. 删除过渡 check，添加三个独立命名且只接受小写值的约束；先 `NOT VALID`，再 validate。
3. 对 workflow graph 三个临时非空 check 执行 `ALTER COLUMN ... SET NOT NULL`，再删除临时 check。
4. 将应用 metadata 固定为 `VARCHAR(16)` + 显式小写 check，移除过渡双读逻辑。

contract 后不允许直接回滚到只识别大写 Enum 名称的旧二进制。应用回滚窗口必须停在 Phase C；Phase D 后采用向前修复，数据库 downgrade 仅在验证过的维护窗口内执行。

## 5. 迁移验证矩阵

| 层级 | 必须验证 |
|---|---|
| 静态 | migration review、`alembic heads` 单 head、离线 PostgreSQL SQL 无非预期 drop/table rewrite |
| SQLite | fresh base→head、previous→head、head→previous→head；batch mode 能创建/删除显式约束 |
| PostgreSQL | fresh base→head、目标备份恢复→head、每阶段锁时长与 row count、downgrade 演练 |
| 数据 | 状态值集合、NULL 计数、约束 validated、邀请索引存在且查询计划合理 |
| 应用 | Task 状态转换/日志、BLOCKED、邀请接受、workflow graph template/instance 创建与读取 |
| 漂移 | Phase A/B/C 分别记录预期剩余 diff；Phase D 后 `alembic check` clean |

## 6. 当前下一步

1. 部署前按 §3 只读审计和 [Phase C 观察清单](../manuals/2026-09-04-ki014-phase-c-observation-checklist.md) 盘点目标预发；旧 revision 的基线不得当成 post-expand 工具通过。未知状态或不可解释 NULL 必须停止。
2. 经批准部署 Phase A 应用与 `20260827_01` 后，以环境变量配置只读 `POSTGRES_DSN`，运行 `python -m app.scripts.audit_ki014_schema_compatibility`；再以带时区的 `--since` 重复审计至少一个完整业务周期，结合清单验证旧值可读、新写入小写、`BLOCKED` 可落库和三个 workflow 字段无新增 NULL。
3. 归档观察结果并单独批准 Phase D contract；没有观察证据时不得执行状态归一化或 `SET NOT NULL`。
4. Phase D 后再要求真实 PostgreSQL `alembic check` clean 并关闭 KI-014。

# Status

Machine status: in-progress.
