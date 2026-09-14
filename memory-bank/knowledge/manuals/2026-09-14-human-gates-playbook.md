---
type: paradigma-manual
title: "Human Gates 执行手册（HG-00～HG-08）"
description: "从 HG-00 起的签字顺序、每 Gate 最小证据、禁止事项与仓库内报告路径；Agent 可准备材料，不得代签。"
tags: [human-gate, playbook, release, ki-014]
timestamp: 2026-09-14T15:23:19+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: decision
  retrieval_hints:
    zh: [Human Gate, HG-00, HG-01, 门禁手册]
    en: [human gate, playbook, HG-00, HG-01]
  relations:
    related_to:
      - ../plans/2026-09-10-integrated-development-and-human-gates-plan.md
      - ./gates/HG-00-batch-scope.yaml
      - ./gates/HG-01-target-access.yaml
      - ./2026-09-04-ki014-phase-c-observation-checklist.md
      - ./2026-08-09-production-release-checklist.md
---

# Human Gates 执行手册

> Agent 只准备证据与草稿报告；`approver` / `approved_at` / `decision: APPROVED` 必须由责任人填写。  
> 正式报告目录：[gates/](./gates/)。字段模板见整合方案 §3.2。

## 顺序

```text
HG-00 批次范围
  → HG-01 目标只读访问与样本
    → HG-02 预发写入 / 兼容部署
      → 完整业务周期观察（可与 I3-F 7 天同环境重叠，不可互替）
        → HG-03 KI-014 contract  ‖  HG-04 业务 UAT
          → HG-05 生产部署（fallback 开）
            → HG-06 Strict canary
              → HG-07 兼容退出 / W15
HG-08 延期产品决策（可提前；不打开 HG-01～07 环境权限）
```

## 谁签什么

| Gate | 责任人 | 最小证据 | 通过后允许 |
|------|--------|----------|------------|
| HG-00 | 产品 / 技术 | 批次清单、排除项、候选 SHA | 指定工程批次开工记录 |
| HG-01 | 环境 / 数据 | 环境 ID、只读权限、样本代表性、证据落点 | **只读**取证 |
| HG-02 | 环境 / 数据库 | SHA、revision、迁移顺序、备份恢复、锁预算、回退 | 获批预发写入动作 |
| HG-03 | 数据库 / 技术 | 周期观察、写入方清单、精确 contract SQL | 明确环境执行 Phase D |
| HG-04 | 业务验收人 | W05 用例与真实角色证据 | 候选业务验收通过 |
| HG-05 | 发布 | 上线清单、I3-F、HG-04、TLS/secret/备份 | 部署所列 SHA（fallback 开） |
| HG-06 | 发布 / 业务 | 生产 shadow、流量样本、告警演练、灰度范围 | 按批关 fallback |
| HG-07 | 数据库 / 产品 / 技术 | 精确对象清单、稳定窗口 | 停写 / 收窄 / 删除所列对象 |
| HG-08 | 产品 | W16/W10-rules 选项勾选与成本 | 仅启动被选中专项 |

## 禁止事项

1. **隔离证据 ≠ 目标证据**：`2026-09-04` Gate 0 / Docker L2 审计不得升级为 HG-01 L3。
2. **`alembic upgrade` 通过 ≠ `alembic check` clean**。
3. **工程完成 ≠ 业务签字 ≠ 生产批准**（HG-04 / HG-05 分列）。
4. **HG-02 Link contract ≠ HG-03 KI-014 contract**（分列 revision 与允许动作）。
5. **保持 fallback 的已批部署 ≠ strict 切流完成**。
6. **禁止**把真实 `POSTGRES_DSN` / 密码写入 Git；DSN 仅本机 env 或密钥库。
7. **禁止**在 HG-01 未 APPROVED 前连接目标库做审计（本手册准备阶段除外的“命令说明”不算执行）。

## HG-00（本轮）

- 报告：[gates/HG-00-batch-scope.yaml](./gates/HG-00-batch-scope.yaml) · 说明：[gates/HG-00-batch-scope.md](./gates/HG-00-batch-scope.md)
- 状态：**READY_FOR_REVIEW**（W01/W02、W07–W13 @ `a1eec25`）
- 签字回复：审批人显示名/角色 + ISO 时间 + 是否同意 approved/excluded actions

## HG-01 接入（待填）

报告：[gates/HG-01-target-access.yaml](./gates/HG-01-target-access.yaml)

请提供（脱敏，**不要**贴完整 DSN）：

| 字段 | 说明 |
|------|------|
| `environment_id` | 如 `staging-filum-pg` |
| `reachability` | VPN / jump / 本机隧道 |
| `readonly_role` | SELECT + READ ONLY；无 DDL/DML |
| `sample_representativeness` | 是否覆盖完整业务周期样本 |
| `sensitive_data_handling` | 聚合/脱敏规则 |
| `evidence_storage` | 如 `verification-runs/`（gitignore）+ 仓库内脱敏手册路径 |
| `dsn_location` | 仅写“本机 env 名 / 密钥库条目名”，不写连接串 |

签字流程：填完接入 → `READY_FOR_REVIEW` → 责任人 `APPROVED` → **才**允许执行：

```powershell
cd backend
# $env:POSTGRES_DSN = '<read-only DSN from secret store — do not commit>'
.\.venv\Scripts\python.exe -m app.scripts.audit_ki014_schema_compatibility
```

若目标尚未到达 expand revision `20260827_01`，改用 [KI-014 计划 §3](../plans/2026-08-26-ki014-schema-drift-remediation-plan.md) 部署前只读 SQL，不得用 `--no-fail` 伪装 post-expand 门禁通过。人工项仍按 [Phase C 清单](./2026-09-04-ki014-phase-c-observation-checklist.md) C1–C6 记录。

## HG-02 及之后

骨架已落盘，**本轮不填变更包、不申请写入**。HG-01 取证完成后再开变更包会话（精确 SHA、revision、锁预算、回退）。

| 报告 | 初始状态 |
|------|----------|
| [HG-02-staging-write.yaml](./gates/HG-02-staging-write.yaml) | OPEN |
| [HG-03-ki014-contract.yaml](./gates/HG-03-ki014-contract.yaml) | OPEN |
| [HG-04-business-uat.yaml](./gates/HG-04-business-uat.yaml) | OPEN |
| [HG-05-prod-deploy.yaml](./gates/HG-05-prod-deploy.yaml) | OPEN |
| [HG-06-strict-canary.yaml](./gates/HG-06-strict-canary.yaml) | OPEN |
| [HG-07-compat-exit.yaml](./gates/HG-07-compat-exit.yaml) | OPEN |
| [HG-08-deferred-product.yaml](./gates/HG-08-deferred-product.yaml) | OPEN（可提前勾选） |

## 证据层级速查

| 级别 | 能证明 | 不能替代 |
|------|--------|----------|
| L0 | 代码/文档/配置结构 | 运行行为 |
| L1 | 本地回归 | 真实 PG 数据分布 |
| L2 | 隔离 PostgreSQL/Redis | 目标周期与业务签字 |
| L3 | 目标预发只读/获批写入观察 | 生产部署授权 |
| L4 | 获批生产范围行为 | 另一次 contract / 扩围 |
