---
type: paradigma-convention
title: "Project Filum — 编码与协作规范"
description: "命名约定、代码风格、测试规范、版本管理 (SemVer)。"
tags:
  - conventions
  - coding
  - testing
  - versioning
timestamp: 2026-07-08T17:34:00+08:00
paradigma:
  schema_version: 0.5.0
  temperature: hot
  lifecycle: stable
  update_policy: agent-editable
  epistemic_status: confirmed
  retrieval_hints:
    zh:
      - 编码规范
      - 命名约定
      - 测试
    en:
      - "coding conventions"
      - naming
      - testing
---
# Project Filum — 编码与协作规范

> 🔥 HOT — 写任何代码前必须遵循。子路径细则见 `.github/instructions/backend.instructions.md`、`.github/instructions/frontend.instructions.md`。

---

## 核心原则

| 原则 | 含义 |
|------|------|
| 单一职责 | 业务逻辑在 `services/`，route 保持薄 |
| 模块化单体 | 不引入微服务假设；跨模块经明确 service 接口 |
| 约定优于配置 | 复用现有 Axios 封装、Pinia、NotificationService 等 |
| 先事实后文档 | 代码/迁移/测试与文档冲突时，以可运行事实为准再更新 memory-bank |
| 最小 diff | 不无关重构；不大段重写 memory-bank |

---

## 技术边界（硬约束）

- **前端**: Vue 3 Composition API + TypeScript + Vite + Element Plus + Pinia + Vue Router；HTTP 统一 `frontend/src/api/`（Axios）
- **后端**: FastAPI + Pydantic v2 + SQLAlchemy 2.0 **Async** + Alembic；worker 为 **ARQ**
- **数据库**: PostgreSQL + JSONB + `pgvector`
- **AI**: 官方 `openai` SDK；**禁止** LangChain
- **通知**: `NotificationService.send(message_obj)`；业务不直连渠道 adapter
- **任务状态机**: `Todo -> Doing -> Review -> Done`（严格）
- **协同**: 工作讨论进 `task_comments`；不建独立聊天
- **档案扩展**: `profiles.custom_fields` JSONB
- **权限**: 角色 + 组织关系 + 字段级权限 + 代理授权

---

## 命名约定

| 场景 | 规范 | 示例 |
|------|------|------|
| Python 模块/函数 | snake_case | `task_service.py`, `get_task_inbox` |
| Python 类 | PascalCase | `TaskService`, `WorkflowGraphService` |
| TS/Vue 组件文件 | PascalCase `.vue` | `TaskCenterView.vue` |
| TS 变量/函数 | camelCase | `taskList`, `fetchTasks` |
| API 路径 | kebab-case 复数资源 | `/api/v1/task-center/...` |
| 常量 | UPPER_SNAKE_CASE | `TASK_CENTER_V2_ENABLED` |

---

## 后端规范

- 路由：`backend/app/api/routes/` 按资源分文件；参数校验 + 权限入口 + 响应组装
- 业务：`backend/app/services/`；数据库写操作包在事务中
- 模型变更：同步 `backend/app/models/` + Alembic 迁移 + **`data-contracts.md`**
- 异常：业务异常抛自定义类，由 `error_handlers.py` 统一转换
- 图引擎 / 工作流 E / 视频 v1：改动前读 `architecture.md` 对应链路与 `progress.md` 边界说明

---

## 前端规范

- 信息架构以 `AppShell.vue` + `router/index.ts` 为准（通用模块 / 特殊模块）
- `views/` 为页面入口；`components/` 为可复用组件；不在 view 内散落裸 fetch
- 页面局部状态用 `ref`/`reactive`；跨页共享用 Pinia
- Push 公钥：`GET /api/v1/push-subscriptions/config`（`VITE_WEB_PUSH_PUBLIC_KEY` 仅 fallback）
- E2E 断言优先使用已有 `data-testid` 锚点

---

## Git 与版本

### 提交格式

```
<type>(<scope>): <subject>
```

| Type | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构 |
| `docs` | 文档 |
| `test` | 测试 |
| `chore` | 构建/工具 |

- **不要默认 commit**；仅用户明确要求时提交
- Windows 下 `backend/scripts/*.sh` 保持 **LF**（`.gitattributes`）

### SemVer（`VERSION`）

| 变更 | 动作 |
|------|------|
| 纯文档/注释 | 通常不升版本 |
| Bug 修复（API 不变） | PATCH |
| 向下兼容新功能 | MINOR（建议后用户确认） |
| 不兼容 API/schema | MAJOR（**须用户同意**） |

递增时：更新根目录 `VERSION` + `changelog.md`（Phase 3 起）+ `progress.md` 记录。

---

## 测试与验证

### Backend

```sh
cd backend && pytest -q && python -m compileall app tests
```

### Frontend

```sh
cd frontend && npm run test:unit -- --run && npm run type-check && npm run build
```

只读 lint：`npm exec oxlint .` 与 `npm exec eslint .`（避免 `npm run lint --fix` 污染 diff）

### 发布

```sh
bash scripts/check-release.sh   # Linux 原生目录
```

---

## Agent 协作

- schema/API 破坏性变更 → **先征求用户同意**
- 会话结束 → 追加 `progress.md` 会话摘要（见 `AGENT_RULES.md` Update Phase）
- 对齐审查 → `.github/prompts/memory-bank-alignment-review.prompt.md`

---

## Document Size Limits
HOT 文档（`project-brief.md`、`architecture.md`、`conventions.md`、`repository-contract.md`）每次会话都会被完整读入 Agent 上下文。为控制 token 消耗，应遵守以下阈值：

| 文档类型 | WARN | ERROR | 超出后操作 |
|----------|------|-------|-----------|
| HOT knowledge 文档 | 260 行 | 420 行 | 拆分 |
| `active-task.md` | 160 行 | 260 行 | 归档 |
| Progress index | 160 行 | 260 行 | 压缩 |

### architecture.md 拆分策略
当 `architecture.md` 超过 260 行时，按模块拆分为核心 + 细节：

```text
architecture.md                   ← HOT, 核心骨架 (~100–150 行)
  保留: Overview, Technology Stack, Module Boundaries, Key Constraints,
        Open Questions, Citations
  移出: 每模块的技术选型理由、数据流细节、trade-off 讨论
domains/architecture/             ← WARM, 模块级架构细节
├── frontend-architecture.md
├── backend-architecture.md
├── core-workflows.md
└── infra-architecture.md
```

拆分后，`architecture.md` 的 Module Boundaries 表应包含指向细节文档的路径：

```markdown
| Module | Responsibility | Architecture Detail |
|--------|----------------|---------------------|
| Payment | 支付回调与订单生命周期 | domains/architecture/payment-architecture.md |
```

### contracts/ 拆分策略
当单个 `paradigma-contract` 文档超过 200 行时，按 `contract_kind` 拆分为独立业务域文件：

```text
contracts/
├── index.md                     ← auto-generated
├── repository-contract.md       ← HOT, Paradigma 专用
├── api/                         ← contract_kind: api
│   ├── payment-api.md
│   └── auth-api.md
├── database/                    ← contract_kind: database
│   ├── user-schema.md
│   └── order-schema.md
└── events/                      ← contract_kind: event
    └── order-events.md
```

每个拆分文件保持独立的 OKF frontmatter（独立的 hints/symbols/relations），让 Agent 通过 index 精确路由到相关 contract，避免一次性加载所有 contract。

### 拆分原则
- **按业务域拆分**：同一业务域的 API + DB + Events 放在不同子目录。
- **保持独立可读性**：每个拆分文件应包含完整的 context（Scope / Contract / Schema / Compatibility），Agent 不需要读原文件即可理解。
- **temperature 差异化**：频繁变动的 contract 设为 `warm`，基础设施级 contract 保留 `hot`。
- **拆分后更新 relations**：拆分出的子文件应在 `depends_on` 中引用 `architecture.md`，原文件涉及的跨文档关系应在子文件中重新声明。

---

## 代码审查自检

- [ ] 是否违反 `data-contracts.md` 或既有 API 契约
- [ ] 是否引入与任务无关的修改
- [ ] 通知/LLM/存储是否经统一抽象
- [ ] 是否更新了相关 memory-bank 文件
