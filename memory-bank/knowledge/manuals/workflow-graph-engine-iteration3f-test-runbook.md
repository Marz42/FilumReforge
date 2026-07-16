---
type: paradigma-manual
title: 工作流图引擎 Iteration 3-F 测试操作手册
description: "I3-F 自动化验证、PostgreSQL 强制测试、Link 回填和 Iteration 4 七天准入观测操作步骤。"
tags:
  - manual
  - workflow-graph
  - iteration-3f
  - testing
  - postgres
  - readiness
timestamp: 2026-07-16T22:07:09+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [Iteration 3-F 测试, Iteration 4 准入, PostgreSQL 强制测试, Link 回填, readiness]
    en: [iteration 3f test, iteration 4 readiness, postgres gate, link backfill]
  relations:
    depends_on:
      - ../plans/workflow-graph-engine-iteration3f-readiness-gate-plan.md
      - ../contracts/database/graph-engine-schema.md
---
# 工作流图引擎 Iteration 3-F 测试操作手册

本手册用于验证 I3-F 工程实现，并在目标环境收集 Iteration 4 的硬性准入证据。工程测试通过不等于准入完成；目标环境仍需连续 7 天满足 Link 覆盖、零 runtime fallback 和零 open P0/P1 incident，并由用户批准最终报告。

## 1. 安全边界与前置条件

- 从仓库根目录 `F:\Lab\FilumReforge` 开始；Windows 命令使用 PowerShell。
- Backend 虚拟环境已安装开发依赖：`backend\.venv\Scripts\python.exe` 可执行。
- PostgreSQL 专项使用 `POSTGRES_TEST_ADMIN_DSN` 连接管理库，并创建/删除随机 `filum_*` 测试数据库。账号必须拥有 `CREATE DATABASE`、终止测试库连接和 `DROP DATABASE` 权限。
- `POSTGRES_TEST_ADMIN_DSN` 必须使用 libpq 形式 `postgresql://.../postgres`；不要写 `postgresql+asyncpg://`。
- 只连接专用开发/测试 PostgreSQL 集群，禁止把自动化测试指向生产集群。
- 目标环境回填前先做数据库备份；不对生产环境执行 `alembic downgrade`、`DELETE` 或 `TRUNCATE`。
- 测试期间不得设置 `POSTGRES_DSN` 指向需要保留的业务库；测试 fixture 会自行创建随机库并覆盖应用连接。

快速确认环境：

```powershell
git status --short
.\backend\.venv\Scripts\python.exe --version
docker version
```

## 2. 开发机自动化验证

### 2.1 快速 I3-F 闸门

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q -m workflow_i4_gate -rxX
```

预期：所有非 PostgreSQL I3-F 用例通过；未配置 PostgreSQL 时，带 `postgres` marker 的用例可以 skip。不得出现 XPASS、未知失败或架构守卫违规。

架构守卫可单独运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_workflow_graph_iteration3f_architecture.py
```

它扫描 `backend/app/**/*.py`，检查 Work Item/Runtime owner、跨域构造与 Coordinator 内部 commit；测试还包含故意违规样例，证明扫描器本身能够拦截越界写入。

### 2.2 Backend 全量与语法检查

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q app tests
```

预期：全量测试绿色；普通本地执行只允许已登记的 PostgreSQL skip。若 `.test-tmp` 被残留进程锁住，可指定新的临时目录：

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp .test-tmp\i3f-manual
```

### 2.3 前端兼容检查

I3-F 不改变前端 API 消费面，但必须确认类型契约未漂移：

```powershell
Set-Location ..\frontend
node node_modules\vue-tsc\bin\vue-tsc.js --build
Set-Location ..
```

预期：退出码为 0，无 TypeScript 错误。

## 3. PostgreSQL 强制专项

### 3.1 启动专用 PostgreSQL

如果已有测试 PostgreSQL，可跳过本节。使用项目 Compose 时：

```powershell
Set-Location infra\docker
$env:POSTGRES_PORT='55433'
docker compose -f docker-compose.yml up -d postgres
docker compose -f docker-compose.yml ps postgres
Set-Location ..\..
```

也可以使用独立临时容器：

```powershell
docker run --name filum-i3f-postgres --rm -d `
  -e POSTGRES_USER=filum `
  -e POSTGRES_PASSWORD=filum `
  -e POSTGRES_DB=postgres `
  -p 55433:5432 pgvector/pgvector:pg16
```

等待 `pg_isready` 成功后再运行测试：

```powershell
docker exec filum-i3f-postgres pg_isready -U filum -d postgres
```

### 3.2 强制执行，禁止 skip

```powershell
Set-Location backend
$env:POSTGRES_TEST_ADMIN_DSN='postgresql://filum:filum@127.0.0.1:55433/postgres'
$env:FILUM_REQUIRE_POSTGRES_TESTS='true'

.\.venv\Scripts\python.exe -m pytest -q -m "workflow_i4_gate and postgres" -rs
.\.venv\Scripts\python.exe -m pytest -q -m postgres -rs
```

验收要求：

- 两条命令退出码均为 0；
- 第二条 PostgreSQL 全集当前基线为 **17/17 PASS、0 skip**；
- Alembic 能升级至 head；
- 并发首次 command 只有一个执行者；
- Work Item、Node、Outbox、Receipt 各故障点不会留下半完成；
- 临时数据库测试完成后无残留数据库。

`FILUM_REQUIRE_POSTGRES_TESTS=true` 会把任何 PostgreSQL skip 转成失败。测试结束后清理当前终端变量：

```powershell
Remove-Item Env:POSTGRES_TEST_ADMIN_DSN -ErrorAction SilentlyContinue
Remove-Item Env:FILUM_REQUIRE_POSTGRES_TESTS -ErrorAction SilentlyContinue
Set-Location ..
```

如果使用独立临时容器：

```powershell
docker stop filum-i3f-postgres
```

## 4. 目标环境迁移与 Link 回填

本节只在获批的联调、预发布或生产变更窗口执行。推荐分阶段升级，不直接一次 `upgrade head`：

### 4.1 Expand

```powershell
Set-Location backend
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe upgrade 20260716_01
.\.venv\Scripts\alembic.exe current
```

确认已新增 Link lineage 字段和 `workflow_operational_incidents`，应用仍保持 Link + JSON 兼容双写。

### 4.2 分批 dry-run

```powershell
.\.venv\Scripts\python.exe -m app.scripts.backfill_workflow_human_task_links --batch-size 500
```

输出字段：

- `scanned`：本批扫描数量；
- `eligible`：锚点一致、可以安全回填的数量；
- `created`：dry-run 必须为 0；
- `existing`：已有 Link 数量；
- `issues`：不可猜测修复的异常；
- `checkpoint_task_id`：下一批的 `--after-task-id`；
- `has_anomalies`：本批是否存在异常。

继续下一批：

```powershell
.\.venv\Scripts\python.exe -m app.scripts.backfill_workflow_human_task_links `
  --batch-size 500 `
  --after-task-id '<上一批 checkpoint_task_id>'
```

dry-run 不写 Link 或 incident。保存每批 JSON 输出；当 `scanned` 小于批大小或 checkpoint 不再推进时结束扫描。

### 4.3 Apply

确认备份、变更窗口和 dry-run 结果后，使用相同批次与 checkpoint 加 `--apply`：

```powershell
.\.venv\Scripts\python.exe -m app.scripts.backfill_workflow_human_task_links `
  --apply `
  --batch-size 500
```

Apply 会写入确定 Link，并把歧义项幂等 upsert 为 `link_backfill_issue` incident；存在异常时仍可能返回 `mode=apply_with_anomalies`，不能把“命令成功”当作“异常已解决”。重复执行不得重复创建 Link 或 incident。

### 4.4 Contract

只有 Link iteration 无空值、回填异常已处置且 readiness 无相关 blocker 后执行：

```powershell
.\.venv\Scripts\alembic.exe upgrade 20260716_02
.\.venv\Scripts\alembic.exe current
```

Contract revision 会把 Link iteration 收紧为 NOT NULL，并启用 iteration/superseded CHECK。如果仍有空 iteration，迁移会主动失败；此时停止发布并回到 reconciliation，不得手工伪造关系。

## 5. Readiness 查询与七天观测

### 5.1 CLI 单次快照

CLI 使用当前环境的 `POSTGRES_DSN`：

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m app.scripts.verify_workflow_iteration4_readiness `
  --format json `
  --fail-on-open
```

退出码：

- `0`：当前快照 `runtime_ready=true`；
- `1`：存在 blocker；JSON 仍会输出，需按 `blockers` 和样本对象排查。

关键字段：

- `incident_counts`：按 category/status/severity 聚合；
- `outbox_counts`：关注 `failed`；
- `receipt_counts`：关注长期 `processing`；
- `engine_version_counts`：按 engine/executor/status 统计 Run；
- `incomplete_objects`：缺 Link 或 active Run executor 元数据不完整的样本；
- `blockers`：本次准入阻塞原因。

### 5.2 Admin API

使用现有 Admin access token：

```powershell
$headers = @{ Authorization = "Bearer $env:FILUM_ADMIN_ACCESS_TOKEN" }
Invoke-RestMethod `
  -Method Get `
  -Uri 'http://localhost:8000/api/v1/workflow-graph/admin/iteration4-readiness' `
  -Headers $headers | ConvertTo-Json -Depth 8
```

Admin 应返回 200；普通 Employee 应返回 404，避免泄露运维对象存在性。

### 5.3 连续七天证据

每天在固定时段执行全量 Link reconciliation、合成 Link-first 解析和 readiness CLI，并保存带日期的 JSON。示例：

```powershell
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
New-Item -ItemType Directory -Force '..\memory-bank\history\reports\i3f-readiness-evidence' | Out-Null
.\.venv\Scripts\python.exe -m app.scripts.verify_workflow_iteration4_readiness `
  --format json `
  --fail-on-open 2>&1 | Tee-Object `
  "..\memory-bank\history\reports\i3f-readiness-evidence\readiness-$stamp.json"
if ($LASTEXITCODE -ne 0) { throw 'Iteration 4 readiness blocker detected.' }
```

连续 7 个自然日均须满足：

- 新 graph-v3 HumanTask Link 覆盖率 100%；
- active Run 可关联 HumanTask reconciliation 无缺失 Link；
- 新增 `link_fallback` 为 0，合成 Link-first 解析也不触发 fallback；
- open error/critical Link 或 migration incident 为 0；
- failed Outbox 为 0，Receipt 无长期 processing；
- active Run 无 executor/snapshot 元数据缺口。

当前 CLI 是单次数据库快照，不自行计算“连续 7 天”。每天的输出、回填报告和测试日志必须纳入最终准入报告；任一天失败，修复后重新开始完整 7 天窗口。

## 6. 故障排查

| 现象 | 处理 |
|---|---|
| PostgreSQL 测试 skip 后失败 | 检查 admin DSN、端口、凭据和 CREATE/DROP DATABASE 权限；强制模式下不得取消 `FILUM_REQUIRE_POSTGRES_TESTS` 来绕过 |
| 临时数据库删除失败 | 结束残留 pytest/Python 进程，确认测试集群无业务连接，再重新运行清理用例；不要在生产集群手工批量终止连接 |
| Contract migration 报 iteration 为空 | 停止迁移，重跑 Expand 后 reconciliation/backfill，处理异常队列；禁止猜测 UPDATE |
| readiness 报 task_without_link | 用 backfill dry-run 校验三锚点，确定项 apply，歧义项由人工核对业务事实 |
| `receipt_conflict` | 核对客户端是否复用了 command ID 却改变 payload；保留 incident 与原 receipt，不覆盖首次结果 |
| `coordinator_failure` 或 failed Outbox | 先核对业务/Receipt/Outbox 是否原子回滚，再按 incident fingerprint 和关联 ID 排查根因 |
| Link 与 JSON 不一致 | 以 Link 为准；保留 `link_mismatch` incident，禁止用 JSON 覆盖正式 Link |

## 7. 最终验收记录

最终报告至少附上：

1. Backend 全量、`workflow_i4_gate`、PostgreSQL 17/17、compileall、前端 type-check 和 memory-bank 检查日志；
2. Expand/Contract 迁移版本与目标环境备份/恢复证据；
3. 所有 backfill 批次、checkpoint、异常处置和重复执行幂等结果；
4. 连续 7 天 readiness JSON 与 Link reconciliation 结果；
5. OWN/LINK/TX/IDEM/COMP/OBS 31 项逐项 PASS 证据；
6. 无损代码回滚演练结果；
7. 用户最终批准记录。

在上述证据齐全前，Iteration 3-F 不能标记完成，Iteration 4 不能启动。
