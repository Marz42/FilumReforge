---
description: "Use when editing FastAPI routes, backend services, SQLAlchemy models, Alembic migrations, Pydantic schemas, ARQ worker jobs, or Python tests under backend/."
name: "Filum Backend"
applyTo:
  - "backend/**/*.py"
  - "backend/alembic.ini"
  - "backend/pyproject.toml"
---

# Filum Backend

- 先读 [memory-bank/architecture.md](../../memory-bank/architecture.md) 和 [memory-bank/design-document.md](../../memory-bank/design-document.md)；涉及阶段状态或工作流 E 当前边界时，再读 [memory-bank/progress.md](../../memory-bank/progress.md) 与 [memory-bank/implementation-plan.md](../../memory-bank/implementation-plan.md)。
- 后端真实行为优先看 [backend/app/services](../../backend/app/services)；路由层保持薄，只做参数校验、权限入口和响应组装，不把业务编排堆进 `api/routes`。
- 数据库相关修改必须同时核对 [backend/app/models](../../backend/app/models) 和 [backend/alembic/versions](../../backend/alembic/versions)；文档与代码冲突时，以模型、迁移、测试和可运行命令为准。
- 通知统一走 `NotificationService.send(message_obj)`；不要在业务服务里直连 Email、WebSocket 或 Web Push adapter。
- 任务状态流转必须保持 `Todo -> Doing -> Review -> Done`；工作沟通、说明和附件进入 `task_comments`，不要引入独立工作聊天链路。
- 档案扩展字段进入 `profiles.custom_fields`；高敏字段和档案可见性必须同时考虑角色、组织关系、字段级策略和代理授权。
- AI 相关逻辑把 LLM 当意图路由器，不当业务真相；优先复用 Pydantic v2 schema 与既有 `ToolRegistryService` / `LLMRouterService` 抽象。
- 工作流 E 或生命周期联动改动，先确认当前主线是否在“模板 / 调度管理深化、回归、部署收口”，不要把仓库描述回 Step 1-7 收口阶段。
- 验证优先使用 [backend/README.md](../../backend/README.md) 中的命令；常见回归是 `pytest -q`、`python -m compileall app tests`、必要时 `alembic upgrade head`。
