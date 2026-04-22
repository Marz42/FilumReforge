# Filum Backend

当前后端基于 **FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic + Redis / ARQ**，已不再是 Phase A 骨架，而是承载当前完整业务基线的服务端实现。

## 当前覆盖能力

- 认证与会话：管理员初始化、JWT access / refresh、当前用户解析
- 组织与人事：部门树、档案、字段级权限、多岗位、汇报线、生命周期、代理授权
- 总览与协同：看板、公告、任务、评论、活动流、统计
- 流程与汇报：任务模板、workflow engine、汇报中心、消息中心、通知回执
- Knowledge / AI：文档库、RAG、LLM Router、Tool Calling
- Push / Worker：浏览器推送、通知投递、embedding job、周期任务与提醒扫描

## 初始化

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
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
```

更多系统级说明请以仓库根目录 `README.md` 和 `memory-bank/architecture.md` 为准。
