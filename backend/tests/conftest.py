from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-suite-123456")

from app.core.config import get_settings
from app.core.database import get_async_engine, get_session_factory
from app.models import Base


@pytest.fixture(autouse=True)
def clear_cached_settings(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-for-suite-123456")
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
