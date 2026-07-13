from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.core.enums import (
  WorkflowGraphInstanceStatus,
  WorkflowGraphTemplateStatus,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError
from app.models import (
  User,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
)
from app.services.auth_service import AuthService
from app.services.workflow_graph_service import WorkflowGraphService
from tests.postgres_migration_support import (
  database_exists,
  drop_ephemeral_database,
  postgres_admin_dsn,
  postgres_tests_required,
  provision_ephemeral_database,
  run_async,
)

pytestmark = pytest.mark.postgres

BASE_DIR = Path(__file__).resolve().parents[1]
TEST_JWT_SECRET = "iteration-0-postgres-secret-32-bytes!"


@dataclass(slots=True)
class PostgresDatabase:
  admin_dsn: str
  async_dsn: str
  database_name: str


@pytest.fixture(scope="module")
def postgres_database() -> PostgresDatabase:
  """Provision PostgreSQL, migrate to head, and prove teardown removes the database."""
  admin_dsn = postgres_admin_dsn()
  database_name: str | None = None
  old_postgres_dsn = os.environ.get("POSTGRES_DSN")
  try:
    async_dsn, _, database_name = run_async(
      provision_ephemeral_database(admin_dsn, prefix="filum_graph_i0")
    )
  except Exception as exc:
    message = f"PostgreSQL test database unavailable: {type(exc).__name__}: {exc}"
    if postgres_tests_required():
      pytest.fail(message)
    pytest.skip(message)

  os.environ["POSTGRES_DSN"] = async_dsn
  get_settings.cache_clear()
  alembic_config = Config(str(BASE_DIR / "alembic.ini"))
  alembic_config.set_main_option("script_location", str(BASE_DIR / "alembic"))

  try:
    command.upgrade(alembic_config, "head")
    yield PostgresDatabase(
      admin_dsn=admin_dsn,
      async_dsn=async_dsn,
      database_name=database_name,
    )
  finally:
    get_settings.cache_clear()
    if old_postgres_dsn is None:
      os.environ.pop("POSTGRES_DSN", None)
    else:
      os.environ["POSTGRES_DSN"] = old_postgres_dsn
    if database_name is not None:
      run_async(drop_ephemeral_database(admin_dsn, database_name))
      assert not run_async(database_exists(admin_dsn, database_name)), (
        f"PostgreSQL test database was not removed: {database_name}"
      )


@pytest_asyncio.fixture
async def pg_session_factory(postgres_database: PostgresDatabase):
  engine = create_async_engine(postgres_database.async_dsn, pool_pre_ping=True)
  factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
  try:
    yield factory
  finally:
    await engine.dispose()


@dataclass(slots=True)
class SeedIds:
  actor_id: UUID
  instance_id: UUID
  nodes: dict[str, UUID]


async def _seed_graph(
  factory: async_sessionmaker[AsyncSession],
  *,
  edges: tuple[tuple[str, str], ...],
  node_keys: tuple[str, ...],
  join_modes: dict[str, str] | None = None,
) -> SeedIds:
  async with factory() as session:
    admin = await session.scalar(select(User).order_by(User.created_at.asc()).limit(1))
    if admin is None:
      admin = await AuthService(
        session,
        Settings(jwt_secret_key=TEST_JWT_SECRET),
      ).bootstrap_admin(
        email=f"pg-i0-{uuid4().hex}@example.com",
        password="StrongPassword123!",
        real_name="PostgreSQL Iteration 0",
        employee_no=f"PG-I0-{uuid4().hex[:10]}",
      )
    code = f"pg-i0-{uuid4().hex}"
    template = WorkflowGraphTemplate(
      code=code,
      base_code=code,
      version=1,
      name="PostgreSQL 并发基线",
      status=WorkflowGraphTemplateStatus.ACTIVE,
      created_by=admin.id,
    )
    session.add(template)
    await session.flush()

    join_modes = join_modes or {}
    template_nodes = {
      key: WorkflowGraphTemplateNode(
        template_id=template.id,
        node_key=key,
        title=key,
        sort_order=index,
        join_mode=join_modes.get(key, "all"),
      )
      for index, key in enumerate(node_keys, start=1)
    }
    session.add_all(template_nodes.values())
    await session.flush()
    session.add_all(
      WorkflowGraphTemplateEdge(
        template_id=template.id,
        from_node_id=template_nodes[from_key].id,
        to_node_id=template_nodes[to_key].id,
      )
      for from_key, to_key in edges
    )
    await session.flush()

    result = await WorkflowGraphService(session).create_multi_node_instance(
      template_id=template.id,
      initiator_id=admin.id,
    )
    await session.commit()
    return SeedIds(
      actor_id=admin.id,
      instance_id=result.instance.id,
      nodes={item.node_key: item.id for item in result.node_instances},
    )


async def _complete(factory, node_instance_id: UUID, actor_id: UUID) -> None:
  async with factory() as session:
    await WorkflowGraphService(session).complete_node_instance(
      node_instance_id=node_instance_id,
      actor_id=actor_id,
    )


@pytest.mark.asyncio
async def test_two_upstreams_complete_concurrently_activate_join_once(pg_session_factory) -> None:
  seed = await _seed_graph(
    pg_session_factory,
    node_keys=("A", "B", "C", "D"),
    edges=(("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")),
    join_modes={"D": "all"},
  )
  await _complete(pg_session_factory, seed.nodes["A"], seed.actor_id)

  await asyncio.gather(
    _complete(pg_session_factory, seed.nodes["B"], seed.actor_id),
    _complete(pg_session_factory, seed.nodes["C"], seed.actor_id),
  )

  async with pg_session_factory() as session:
    instance = await session.get(WorkflowGraphInstance, seed.instance_id)
    downstream = await session.scalar(
      select(WorkflowNodeInstance).where(WorkflowNodeInstance.id == seed.nodes["D"])
    )
    downstream_count = await session.scalar(
      select(func.count(WorkflowNodeInstance.id)).where(
        WorkflowNodeInstance.instance_id == seed.instance_id,
        WorkflowNodeInstance.node_key == "D",
        WorkflowNodeInstance.iteration == 1,
      )
    )
    assert instance is not None and instance.executor_kind == "snapshot"
    assert instance.engine_version == "graph-v2"
    assert (instance.definition_snapshot or {}).get("format_version") == 1
    assert len(instance.definition_hash or "") == 64
    assert downstream is not None
    assert downstream.engine_state == WorkflowNodeEngineState.ACTIVATED
    assert downstream.node_instance_version == 2
    assert downstream_count == 1


@pytest.mark.asyncio
async def test_same_node_concurrent_duplicate_completion_advances_once(pg_session_factory) -> None:
  seed = await _seed_graph(
    pg_session_factory,
    node_keys=("A", "B"),
    edges=(("A", "B"),),
  )

  await asyncio.gather(
    _complete(pg_session_factory, seed.nodes["A"], seed.actor_id),
    _complete(pg_session_factory, seed.nodes["A"], seed.actor_id),
  )

  async with pg_session_factory() as session:
    upstream = await session.get(WorkflowNodeInstance, seed.nodes["A"])
    downstream = await session.get(WorkflowNodeInstance, seed.nodes["B"])
    downstream_count = await session.scalar(
      select(func.count(WorkflowNodeInstance.id)).where(
        WorkflowNodeInstance.instance_id == seed.instance_id,
        WorkflowNodeInstance.node_key == "B",
        WorkflowNodeInstance.iteration == 1,
      )
    )
    assert upstream is not None and downstream is not None
    assert upstream.engine_state == WorkflowNodeEngineState.COMPLETED
    assert upstream.node_instance_version == 2
    assert downstream.engine_state == WorkflowNodeEngineState.ACTIVATED
    assert downstream.node_instance_version == 2
    assert downstream_count == 1


async def _deep_reject(factory, seed: SeedIds) -> UUID:
  async with factory() as session:
    return await WorkflowGraphService(session).deep_reject_to_upstream(
      node_instance_id=seed.nodes["B"],
      actor_id=seed.actor_id,
      target_node_key="A",
      reason="Iteration 0 PostgreSQL race",
    )


@pytest.mark.asyncio
async def test_deep_reject_and_completion_race_leaves_one_consistent_result(pg_session_factory) -> None:
  seed = await _seed_graph(
    pg_session_factory,
    node_keys=("A", "B"),
    edges=(("A", "B"),),
  )
  await _complete(pg_session_factory, seed.nodes["A"], seed.actor_id)

  results = await asyncio.gather(
    _complete(pg_session_factory, seed.nodes["B"], seed.actor_id),
    _deep_reject(pg_session_factory, seed),
    return_exceptions=True,
  )
  successes = [result for result in results if not isinstance(result, BaseException)]
  failures = [result for result in results if isinstance(result, BaseException)]
  assert len(successes) == 1
  assert len(failures) == 1
  assert isinstance(failures[0], ConflictError)

  async with pg_session_factory() as session:
    instance = await session.get(WorkflowGraphInstance, seed.instance_id)
    node_instances = list(
      await session.scalars(
        select(WorkflowNodeInstance)
        .where(WorkflowNodeInstance.instance_id == seed.instance_id)
        .order_by(WorkflowNodeInstance.iteration, WorkflowNodeInstance.node_key)
      )
    )
    assert instance is not None
    if instance.status == WorkflowGraphInstanceStatus.COMPLETED:
      assert len(node_instances) == 2
      assert all(item.engine_state == WorkflowNodeEngineState.COMPLETED for item in node_instances)
    else:
      assert instance.status == WorkflowGraphInstanceStatus.ACTIVE
      iteration_two = [item for item in node_instances if item.iteration == 2]
      assert {item.node_key for item in iteration_two} == {"A", "B"}
      assert next(item for item in iteration_two if item.node_key == "A").engine_state == (
        WorkflowNodeEngineState.ACTIVATED
      )
      assert next(item for item in node_instances if item.id == seed.nodes["B"]).engine_state == (
        WorkflowNodeEngineState.TERMINATED
      )


def test_ephemeral_database_drop_leaves_no_residue(postgres_database: PostgresDatabase) -> None:
  _, _, database_name = run_async(
    provision_ephemeral_database(postgres_database.admin_dsn, prefix="filum_drop_i0")
  )
  try:
    assert run_async(database_exists(postgres_database.admin_dsn, database_name))
  finally:
    run_async(drop_ephemeral_database(postgres_database.admin_dsn, database_name))
  assert not run_async(database_exists(postgres_database.admin_dsn, database_name))
