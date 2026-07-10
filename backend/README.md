# Filum Backend

当前后端基于 **FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic + Redis / ARQ**，已不再是 Phase A 骨架，而是承载当前完整业务基线的服务端实现。当前重构 Step 1-7 已完成并通过用户验测；工作流 E 的首批后端实现也已落地，包括模板实例运行态、逐步激活与多人扇出 / 汇聚语义。

## 当前覆盖能力

- 认证与会话：管理员初始化、JWT access token、HttpOnly refresh cookie 轮换 / logout 撤销、当前用户解析
- 组织与人事：部门树、档案、字段级权限、多岗位、汇报线、生命周期、代理授权
- 总览与协同：看板、公告、任务、评论、活动流、统计
- 流程与汇报：任务模板、模板实例运行态、逐步激活、fan-out / join、workflow engine、汇报中心、消息中心、通知回执
- workflow graph 重构：Phase 2–11 主干，覆盖 dual-write、交付/验收/返工、握手/转办、多节点推进、Context、条件路由、Notice、Wait-Any、深度打回、outbox 与 graph-first 读取
- Knowledge / AI：文档库、RAG、LLM Router、Tool Calling
- Push / Worker：浏览器推送、通知投递、embedding job、周期任务与提醒扫描

## 当前已知边界

- 生命周期事件的规则化默认联动与前端配置入口仍未落地；当前已支持显式绑定目标后的异步触发
- B-12 已移除 Legacy E 对外 API、实例化与旧调度路径；旧表族/ORM 暂留历史兼容
- 视频工作流 v1 已落地（W0–W10）；`workflow_graph_template_engine_enabled` 默认 `false`，启用图模板实例化须显式开开关
- 生产部署产物已落地；Ubuntu **最小回滚路径**仍待演练（见 `memory-bank/knowledge/roadmap.md`）

## 初始化

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# 编辑 .env，至少填入 JWT_SECRET_KEY
alembic upgrade head
```

## 本地运行

```sh
. .venv/bin/activate
./scripts/start-dev.sh
```

## 启动 worker

```sh
. .venv/bin/activate
./scripts/start-worker.sh
```

## 生产部署提醒

- [scripts/start-dev.sh](scripts/start-dev.sh) 使用 `uvicorn --reload`，只适合开发环境
- 正式部署可走两条路径：直接运行 `uvicorn app.main:app --host 127.0.0.1 --port 8000` + `arq app.workers.arq_worker.WorkerSettings`，或使用 `Dockerfile.prod` / `scripts/start-prod.sh` / `infra/docker/docker-compose.prod.yml`
- `backend` 与 `worker` 必须共享同一份 `.env` 配置和同一个 `STORAGE_BASE_PATH`
- 当前会话模型使用 HttpOnly refresh cookie；如前后端不是同源部署，需要显式配置 `CORS_ALLOWED_ORIGINS`，并按运行形态校准 `AUTH_REFRESH_COOKIE_*`
- 详细云服务器部署步骤请以仓库根目录 [README.md](../README.md) 的“云服务器部署”章节为准

## 验证

```sh
. .venv/bin/activate
pytest -q
python -m compileall app tests
```

## 常用脚本

```sh
. .venv/bin/activate
python -m app.scripts.seed_sample_data --password 'FilumTest123!'
python -m app.scripts.seed_workflow_video_templates \
  --copy-dept-code video-copywriting \
  --post-dept-code video-post
```

生产环境部门 code 非 demo 三件套时，**必须**指定 `--copy-dept-code` 与 `--post-dept-code`（`--voice-dept-code` 可省略，默认同文案部）。

更多系统级说明见 [`README.md`](../README.md)、[`project-brief.md`](../memory-bank/knowledge/project-brief.md)、[`architecture.md`](../memory-bank/knowledge/architecture.md)、[`data-contracts.md`](../memory-bank/knowledge/contracts/data-contracts.md)。
