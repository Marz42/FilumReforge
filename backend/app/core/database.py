from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


@lru_cache
def get_async_engine():
  settings = get_settings()
  return create_async_engine(settings.postgres_dsn, future=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
  return async_sessionmaker(
    bind=get_async_engine(),
    class_=AsyncSession,
    expire_on_commit=False,
  )


async def get_db_session() -> AsyncIterator[AsyncSession]:
  async with get_session_factory()() as session:
    yield session


async def dispose_async_engine() -> None:
  await get_async_engine().dispose()
