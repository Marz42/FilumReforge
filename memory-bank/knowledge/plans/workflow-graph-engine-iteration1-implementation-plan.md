---
type: paradigma-plan
title: 工作流图引擎 Iteration 1 实施计划
description: "对象级授权、模板作用域、发布定义不可变、Run 快照与 legacy executor 的实施切片。"
tags:
  - plan
  - workflow-graph
  - iteration-1
  - authorization
  - snapshot
timestamp: 2026-07-13T22:30:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: hot
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh:
      - Iteration 1
      - 对象级授权
      - Run 快照
      - legacy executor
    en:
      - iteration 1
      - workflow access policy
      - run snapshot
      - legacy executor
---
# 工作流图引擎 Iteration 1 实施计划

> **状态**：I1-A–E 已实施并通过 SQLite/PostgreSQL 全量验证，待用户验收 Iteration 1。Iteration 1 未改造路径/Join 语义；`WG-GAP-001`–`003` 留给 Iteration 2。

## 0. 实施进度

- [x] I1-A：中心化 `WorkflowAccessPolicy`；实例、事件、子 Run、submission、designer、统计、模板实例列表门闩。
- [x] `AUTH-GAP-001`–`003` 从 7 个 strict xfail 参数实例转为正常回归。
- [x] 正向覆盖发起人、当前/历史办理人、部门经理、正式 watcher 与模板管理经理。
- [x] API 专项 44 项、后端全量回归通过；`workflow_gap` 仅剩 `WG-GAP-001`–`004`。
- [x] I1-B：active/archived 不可变、seed 升级改为派生版本、最终部门 scope 校验。
- [x] I1-C：迁移 `20260713_01` expand scope/snapshot/hash/engine/executor 字段并回填 legacy 标识。
- [x] I1-D：canonical snapshot builder、node-key 边、SHA-256、发布与 Run 创建共用构建器。
- [x] I1-E：新 Run snapshot executor、旧 Run legacy executor、快照完整性闸门和只读盘点脚本。

验证结果：后端非 PostgreSQL 全量通过；`FILUM_REQUIRE_POSTGRES_TESTS=true` 下 5/5 通过且无 skip；`workflow_gap` 仅保留 `WG-GAP-001`–`003` strict xfail。

## 1. 目标与完成定义

Iteration 1 只回答三件事：

1. 谁能读取 Run、事件、子 Run、submission 和模板管理资源；
2. 哪个模板版本能启动、作用于哪个最终部门；
3. Run 启动后执行哪一份不可变定义，以及旧 Run 如何继续运行。

完成时必须满足：

- `AUTH-GAP-001`–`003` 转为正常通过回归，不再 xfail；
- 未授权对象读统一 404，命令越权保持 403/现有稳定错误映射；
- `ACTIVE/ARCHIVED` 模板不能原地修改定义、config、schema 或 scope；
- 创建 Run 先解析最终部门，再校验显式 `scope_mode`；
- 新 Run 持有 canonical snapshot、SHA-256 hash、`engine_version`，只按 snapshot 执行；
- 存量 Run 明确标为 legacy，不被猜测性回填切换；
- 新旧 executor 可并存、可观测、可回滚。

## 2. 实施切片

### I1-A：对象级读取授权

新增中心化 `WorkflowAccessPolicy`，统一保护：

- Run 详情；
- Run Event；
- 子 Run；
- submission；
- designer、模板统计、模板实例列表。

允许关系：Admin/HR、发起人、当前/历史办理人、正式 watcher、管理子树内经理和有效代理。读取无权返回 404。模板管理读取复用 `can_manage_task_templates`。

验证：负向 7 个资源回归；正向覆盖发起人、当前/历史办理人、经理、watcher、Admin/HR。

### I1-B：发布定义不可变与作用域顺序

1. `update_template`、整包保存、导入、结构编辑只允许 `DRAFT`。
2. `ACTIVE` 只允许归档或派生新 draft；`ARCHIVED` 不可回到 draft/active，也不可编辑。
3. 新增显式 `scope_mode`：
   - `global`：忽略/禁止非空部门列表；
   - `departments`：必须至少一个部门，允许范围为列表及产品明确的子树规则；
   - 存量空列表回填 `global`，非空列表回填 `departments`。
4. Run 创建流程固定为：解析 actor/输入 → 解析最终 department → 校验 capability/管理范围 → 校验模板 scope → 创建 Run。

### I1-C：schema expand

新增字段，首个 revision 保持兼容：

| 表 | 字段 | Expand 约束 | 新写目标 |
|---|---|---|---|
| `workflow_graph_templates` | `scope_mode varchar(16)` | nullable，回填后加 check | `global|departments` |
| `workflow_graph_instances` | `definition_snapshot jsonb/json` | nullable | 新 executor 必填 |
| `workflow_graph_instances` | `definition_hash varchar(64)` | nullable | canonical JSON SHA-256 |
| `workflow_graph_instances` | `engine_version varchar(32)` | nullable | 首版 `graph-v2` |
| `workflow_graph_instances` | `executor_kind varchar(16)` | nullable，check | `legacy|snapshot` |

不把 snapshot 外置为新表：当前定义规模有限，Run 内 JSON 能减少执行期 join，并使恢复数据自包含。

### I1-D：canonical snapshot

建立单一 snapshot builder：

- 固定 `format_version`；
- 模板标识、base code、version；
- context schema、config、scope；
- 节点按 `(sort_order,node_key)` 排序；
- 边按 `(from_node_key,priority,to_node_key)` 排序；
- UUID 不作为运行语义主键，快照内边使用 node key；
- JSON 使用 UTF-8、键排序、紧凑分隔符、禁止 NaN，再计算 SHA-256。

发布校验和 Run 创建都调用同一个 builder；测试证明同义输入 hash 稳定、语义变化 hash 改变。

### I1-E：executor 路由与回填

- 新 Run：`executor_kind=snapshot`、`engine_version=graph-v2`，snapshot/hash 同事务写入。
- 存量 Run：回填 `executor_kind=legacy`、`engine_version=legacy-v1`；snapshot/hash 保持 null。
- snapshot executor 禁止调用“按实时模板补建节点/重新绑定边”的兼容逻辑。
- legacy executor 保留当前行为，并增加日志/指标以统计 active legacy Run。
- 只读回填报告列出 active legacy Run 数量、模板版本、缺失模板和不可证明定义；Iteration 1 不强切旧 Run。

## 3. API 与兼容性

HTTP 路径保持不变。预期响应变化：

- 过去越权成功的对象读取改为 404；
- 模板管理读对无能力用户改为 404；
- active/archived 原地编辑改为 409；
- scope 不匹配的 Run 创建稳定失败，不再因省略 department 绕过。

模板读模型增加 `scope_mode`；Run 详情中的 snapshot/hash/engine 信息默认仅管理/诊断接口暴露，普通任务中心不返回完整 snapshot。

## 4. 迁移与发布顺序

1. 部署兼容读取字段的代码和 nullable 列；
2. 回填模板 `scope_mode` 与存量 Run executor 标识；
3. 开启新 Run snapshot 写入，同时保留 legacy 读取；
4. PostgreSQL 校验 hash、并发创建和迁移可逆性；
5. 观察新写无 null、legacy 数量只降不升；
6. 后续 revision 再收紧新定义约束，不对存量 snapshot 强制 NOT NULL。

回滚时：停止创建 snapshot Run，代码退回 legacy 路由；新增列保留，不立即 drop。已创建 snapshot Run 必须继续由兼容版本执行，不能丢弃快照降级。

## 5. 测试矩阵

- SQLite：Policy 全角色、404/403、模板状态机、scope 解析顺序、canonical hash、snapshot 不漂移。
- PostgreSQL：Alembic upgrade/downgrade、JSONB snapshot、并发创建、active legacy 回填、临时库无残留。
- API：匿名 401、对象读 404、命令 403、管理资源 404、Run 创建 scope 负向。
- 回归：Iteration 0 全量、任务中心、视频实例化、调度 run-now、Deep-Reject/Wait-Any 旧行为。

## 6. 停止条件

- 无法从现有关系可靠识别 watcher/历史办理人；
- snapshot executor 仍需读取实时模板才能推进；
- migration 无法在 PostgreSQL 往返；
- 新旧 executor 不能明确区分；
- active 模板仍存在任何绕过 Admin Service 的公开写入口。

遇到停止条件时不扩大范围到 Iteration 2；先补证据、修订设计或保留 legacy 路由。
