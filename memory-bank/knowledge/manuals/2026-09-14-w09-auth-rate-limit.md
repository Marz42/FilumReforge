---
type: paradigma-manual
title: "W09 跨 worker 认证限流"
description: "记录 Redis 共享认证限流的范围、配置、故障策略、回退开关与本地验证边界。"
tags: [w09, auth, rate-limit, redis]
timestamp: 2026-09-14T12:00:00+08:00
paradigma:
  schema_version: "0.5.0"
  temperature: warm
  lifecycle: evolving
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh: [认证限流, Redis限流, W09, Retry-After]
    en: [auth rate limit, redis rate limit, W09]
  relations:
    related_to:
      - ../plans/2026-09-10-integrated-development-and-human-gates-plan.md
      - ./deployment-runbook-ubuntu-2404.md
---

# W09 跨 worker 认证限流

## 范围

- 共享额度：`AUTH_RATE_LIMIT_BACKEND=redis` 时，login / refresh / bootstrap-admin 使用 Redis 固定窗口原子计数。
- 身份：继续只信任 Uvicorn `--forwarded-allow-ips` 改写后的 `request.client.host`；应用层不读取原始 `X-Forwarded-For`。
- 响应：超限返回 `429` + `Retry-After`；Redis 故障且 `reject` 模式返回 `503` + `Retry-After`。
- 本地默认：`memory`（单进程 / 测试）；生产 Compose 默认 `redis`。

## 配置

| 变量 | 默认 | 说明 |
|---|---|---|
| `AUTH_RATE_LIMIT_BACKEND` | `memory` | `memory` 或 `redis` |
| `AUTH_RATE_LIMIT_KEY_PREFIX` | `filum:auth_rl:` | Redis key 前缀 |
| `AUTH_RATE_LIMIT_REDIS_FAIL_MODE` | `reject` | `reject`=暂拒；`memory`=本地兜底；禁止静默无限放行 |
| `AUTH_RATE_LIMIT_WINDOW_SECONDS` | `60` | 窗口秒数 |
| `AUTH_LOGIN_RATE_LIMIT` / `AUTH_REFRESH_RATE_LIMIT` / `AUTH_BOOTSTRAP_RATE_LIMIT` | 10 / 20 / 5 | 各 scope 上限 |

Key 形状：`{prefix}{scope}:{client}:{window_id}`，首次写入带 `EXPIRE`，空闲 key 不会永久占用。

## 故障与回退

1. **生产默认**：`backend=redis` + `fail_mode=reject`。Redis 不可用时认证入口暂拒（503），不放大攻击面。
2. **紧急回退**：将 `AUTH_RATE_LIMIT_BACKEND=memory` 并滚动重启；多 worker 时额度再次变为进程本地，需在变更单记录误伤/漏拦风险。
3. **受限本地兜底**：仅在明确接受“Redis 宕机期间限流降级为单机”时设 `AUTH_RATE_LIMIT_REDIS_FAIL_MODE=memory`。

## 验证

- 单元：`backend/tests/test_auth_rate_limit.py`（共享额度、TTL、reject/memory 故障、伪造头身份）。
- 回归：既有 login/refresh 429 用例现断言 `Retry-After`。
- 未宣称：真实多机生产 p95、灰度 429 误伤监控；目标环境观察仍独立于本批。

## 明确不做

- 不改变登录业务语义或 JWT/cookie 模型。
- 不在本批关闭 projection fallback、执行 Phase D 或开工 Iteration 6。
