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

## 代码审查自检

- [ ] 是否违反 `data-contracts.md` 或既有 API 契约
- [ ] 是否引入与任务无关的修改
- [ ] 通知/LLM/存储是否经统一抽象
- [ ] 是否更新了相关 memory-bank 文件
