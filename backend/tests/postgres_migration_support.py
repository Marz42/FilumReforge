from __future__ import annotations

import asyncio
import os
import re
import uuid
from collections.abc import Coroutine
from typing import TypeVar
from urllib.parse import urlparse, urlunparse

import asyncpg

T = TypeVar("T")
TRUE_VALUES = {"1", "true", "yes", "on"}
DATABASE_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,24}$")


def postgres_admin_dsn() -> str:
  return os.environ.get(
    "POSTGRES_TEST_ADMIN_DSN",
    "postgresql://filum:filum@127.0.0.1:5432/postgres",
  )


def _replace_database(url: str, database: str) -> str:
  parsed = urlparse(url)
  return urlunparse(parsed._replace(path=f"/{database}"))


def to_asyncpg_sqlalchemy_dsn(sync_postgres_url: str) -> str:
  if sync_postgres_url.startswith("postgresql+asyncpg://"):
    return sync_postgres_url
  if sync_postgres_url.startswith("postgresql://"):
    return sync_postgres_url.replace("postgresql://", "postgresql+asyncpg://", 1)
  raise ValueError(f"Unsupported PostgreSQL URL scheme: {sync_postgres_url}")


def postgres_tests_required() -> bool:
  return os.environ.get("FILUM_REQUIRE_POSTGRES_TESTS", "").strip().lower() in TRUE_VALUES


async def provision_ephemeral_database(
  admin_dsn: str,
  *,
  prefix: str = "filum_test",
) -> tuple[str, str, str]:
  """Create an empty database and return (async_sqlalchemy_dsn, sync_dsn, db_name)."""
  if DATABASE_PREFIX_PATTERN.fullmatch(prefix) is None:
    raise ValueError("PostgreSQL test database prefix must be a safe lowercase identifier.")
  database_name = f"{prefix}_{uuid.uuid4().hex}"
  conn = await asyncpg.connect(admin_dsn)
  try:
    await conn.execute(f'CREATE DATABASE "{database_name}"')
  finally:
    await conn.close()

  sync_dsn = _replace_database(admin_dsn, database_name)
  async_dsn = to_asyncpg_sqlalchemy_dsn(sync_dsn)
  return async_dsn, sync_dsn, database_name


async def drop_ephemeral_database(admin_dsn: str, database_name: str) -> None:
  conn = await asyncpg.connect(admin_dsn)
  try:
    await conn.execute(f'ALTER DATABASE "{database_name}" WITH ALLOW_CONNECTIONS false')
    await conn.execute(
      """
      SELECT pg_terminate_backend(pid)
      FROM pg_stat_activity
      WHERE datname = $1 AND pid <> pg_backend_pid()
      """,
      database_name,
    )
    await conn.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
  finally:
    await conn.close()


async def database_exists(admin_dsn: str, database_name: str) -> bool:
  conn = await asyncpg.connect(admin_dsn)
  try:
    return bool(
      await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)",
        database_name,
      )
    )
  finally:
    await conn.close()


async def list_public_tables(sync_postgres_dsn: str) -> set[str]:
  conn = await asyncpg.connect(sync_postgres_dsn)
  try:
    rows = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    return {str(row["tablename"]) for row in rows}
  finally:
    await conn.close()


def run_async(coro: Coroutine[object, object, T]) -> T:
  return asyncio.run(coro)
