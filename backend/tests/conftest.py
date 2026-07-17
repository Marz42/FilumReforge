from __future__ import annotations

import sys
from pathlib import Path

# Pytest only applies `pythonpath` from the config file whose directory is the
# rootdir. Invoking `pytest` / `python -m pytest` from the monorepo root skips
# `backend/pyproject.toml`, so ensure the backend package root is importable.
_backend_dir = Path(__file__).resolve().parent.parent
_backend_str = str(_backend_dir)
if _backend_str not in sys.path:
  sys.path.insert(0, _backend_str)

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-suite-123456")

from app.core.config import get_settings
from app.core.database import get_async_engine, get_session_factory
from app.models import Base


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
  """CI strict mode treats every PostgreSQL skip as a failed test."""
  outcome = yield
  report = outcome.get_result()
  require_postgres = os.environ.get("FILUM_REQUIRE_POSTGRES_TESTS", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
  }
  if require_postgres and item.get_closest_marker("postgres") is not None and report.skipped:
    report.outcome = "failed"
    report.longrepr = (
      str(item.fspath),
      0,
      "FILUM_REQUIRE_POSTGRES_TESTS=true forbids skipped PostgreSQL tests.",
    )


@pytest.fixture(autouse=True)
def clear_cached_settings(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-for-suite-123456")
  monkeypatch.setenv("APP_ENV", "development")
  get_settings.cache_clear()
  get_async_engine.cache_clear()
  get_session_factory.cache_clear()
  yield
  get_settings.cache_clear()
  get_async_engine.cache_clear()
  get_session_factory.cache_clear()


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
  engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
  )
  async with engine.begin() as connection:
    await connection.run_sync(Base.metadata.create_all)

  session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
  async with session_factory() as session:
    yield session

  await engine.dispose()
