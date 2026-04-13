# Filum Backend

Phase A 后端骨架基于 **FastAPI + Pydantic v2 + SQLAlchemy 2.0 Async + Alembic**，并预留 Redis 通知总线与对象存储抽象的接入点。

## 初始化

```sh
PYENV_PYTHON="$HOME/.pyenv/versions/3.12.12/bin/python"
$PYENV_PYTHON -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## 本地运行

```sh
. .venv/bin/activate
uvicorn app.main:app --reload
```

## 验证

```sh
. .venv/bin/activate
pytest
python -m compileall app
```
