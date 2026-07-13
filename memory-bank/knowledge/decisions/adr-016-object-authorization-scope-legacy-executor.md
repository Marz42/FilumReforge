---
type: paradigma-decision
title: "ADR-016: 对象级授权、显式 scope 与 legacy executor"
description: "提议统一 Run 对象授权，显式模板 scope_mode，并让存量在途 Run 使用 legacy executor。"
tags: ["adr", "authorization", "scope", "legacy-executor", "proposal"]
timestamp: 2026-07-13T22:11:53+08:00
paradigma:
  schema_version: 0.5.0
  temperature: warm
  lifecycle: stable
  update_policy: read-only
  epistemic_status: decision
  retrieval_hints:
    zh: ["对象级授权", "scope_mode", "legacy executor"]
    en: ["object authorization", "scope mode", "legacy executor"]
---
# ADR-016: 对象级授权、显式 scope 与 legacy executor

**日期**：2026-07-13  
**状态**：已采纳（2026-07-13 用户统一批准 ADR-012–016）

## 背景

实例、事件、子 Run、submission 和模板管理读接口存在只校验登录、不校验对象关系的路径；模板空部门列表也无法明确区分“全局”与“未配置”。存量在途 Run 没有可信执行快照，不能安全假装为新引擎数据。

## 提议决策

1. 统一对象级 Policy：匿名 401；具体对象无读取权限 404；对象已定位但无命令权限 403。
2. Admin/HR 保持全局管理能力；部门经理和有效代理只覆盖管理子树。
3. Run 发起人、当前/历史办理人、正式 watcher 可读；节点完成只允许当前办理人，Admin 必须先 takeover。
4. designer、统计和模板实例列表要求模板管理能力。
5. 模板新增显式 `scope_mode=global|departments`；创建 Run 必须先解析最终部门，再校验模板 scope。
6. 新快照 Run 使用新版 executor；无法可靠回填快照的在途 Run 固定使用 legacy executor，直至自然收口或显式迁移。

## 备选方案

- 所有已登录员工都可读、只限制写：不符合内部最小权限原则，否决。
- 用空数组隐式表示 global：容易与未配置/迁移缺失混淆，否决。
- 强制把所有在途 Run 切到新 executor：定义不可证明等价，风险不可接受，否决。

## 后果

- Iteration 1 涉及 Policy、scope schema/API 与 legacy 路由，必须先获用户批准。
- 需要统一 API 负向测试，并记录历史办理人与 watcher 的正式数据来源。
