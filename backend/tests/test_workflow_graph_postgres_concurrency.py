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
  TaskPriority,
  TaskSourceType,
  WorkflowGraphInstanceStatus,
  WorkflowGraphTemplateStatus,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError
from app.models import (
  User,
  Task,
  WorkflowCommandReceipt,
  WorkflowEdgeTraversal,
  WorkflowGraphInstance,
  WorkflowGraphTemplate,
  WorkflowGraphTemplateEdge,
  WorkflowGraphTemplateNode,
  WorkflowNodeInstance,
  WorkflowNodeActivationDependency,
  WorkflowOutboxEvent,
  WorkflowRunEvent,
)
from app.services.auth_service import AuthService
from app.services.workflow_graph_service import WorkflowGraphService
from app.services.human_task_coordinator import HumanTaskCoordinator
from app.services.workflow_command_receipt_service import WorkflowCommandReceiptService
from app.services.workflow_command_executor import WorkflowCommandExecutor
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
  edges: tuple[tuple, ...],
  node_keys: tuple[str, ...],
  join_modes: dict[str, str] | None = None,
  routing_modes: dict[str, str] | None = None,
  context: dict | None = None,
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
    routing_modes = routing_modes or {}
    template_nodes = {
      key: WorkflowGraphTemplateNode(
        template_id=template.id,
        node_key=key,
        title=key,
        sort_order=index,
        join_mode=join_modes.get(key, "all"),
        routing_mode=routing_modes.get(key, "inclusive"),
      )
      for index, key in enumerate(node_keys, start=1)
    }
    session.add_all(template_nodes.values())
    await session.flush()
    session.add_all(
      WorkflowGraphTemplateEdge(
        template_id=template.id,
        from_node_id=template_nodes[edge[0]].id,
        to_node_id=template_nodes[edge[1]].id,
        condition=dict(edge[2]) if len(edge) > 2 else {},
        priority=int(edge[3]) if len(edge) > 3 else 0,
      )
      for edge in edges
    )
    await session.flush()

    result = await WorkflowGraphService(session).create_multi_node_instance(
      template_id=template.id,
      initiator_id=admin.id,
      context=context,
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
async def test_command_receipt_concurrent_claim_creates_one_record(pg_session_factory) -> None:
  seed = await _seed_graph(
    pg_session_factory,
    node_keys=("A",),
    edges=(),
  )
  command_id = f"pg-command-{uuid4().hex}"
  payload = {"node_instance_id": seed.nodes["A"], "result": "completed"}

  async def claim_once() -> bool:
    async with pg_session_factory() as session:
      service = WorkflowCommandReceiptService(session)
      claim = await service.claim(
        command_id=command_id,
        command_type="complete_node",
        payload=payload,
        actor_user_id=seed.actor_id,
      )
      if not claim.is_replay:
        await service.complete(receipt=claim.receipt, result={"status": "completed"})
      await session.commit()
      return claim.is_replay

  replay_flags = await asyncio.gather(claim_once(), claim_once())
  assert sorted(replay_flags) == [False, True]
  async with pg_session_factory() as session:
    count = await session.scalar(
      select(func.count(WorkflowCommandReceipt.id)).where(
        WorkflowCommandReceipt.command_id == command_id
      )
    )
    assert count == 1


@pytest.mark.asyncio
async def test_command_executor_concurrent_replay_applies_node_once(pg_session_factory) -> None:
  seed = await _seed_graph(pg_session_factory, node_keys=("A",), edges=())
  command_id = f"pg-execute-{uuid4().hex}"
  payload = {"node_instance_id": str(seed.nodes["A"])}

  async def execute_once() -> dict[str, object]:
    async with pg_session_factory() as session:
      async def operation() -> dict[str, object]:
        await WorkflowGraphService(session).complete_node_instance(
          node_instance_id=seed.nodes["A"],
          actor_id=seed.actor_id,
          commit=False,
        )
        return {
          "instance_id": str(seed.instance_id),
          "node_instance_id": str(seed.nodes["A"]),
        }

      return await WorkflowCommandExecutor(session).execute(
        command_id=command_id,
        command_type="complete_node",
        payload=payload,
        operation=operation,
        actor_user_id=seed.actor_id,
        aggregate_type="workflow_run",
      )

  results = await asyncio.gather(execute_once(), execute_once())
  assert results[0] == results[1]

  async with pg_session_factory() as session:
    node = await session.get(WorkflowNodeInstance, seed.nodes["A"])
    receipt_count = await session.scalar(
      select(func.count(WorkflowCommandReceipt.id)).where(
        WorkflowCommandReceipt.command_id == command_id
      )
    )
    events = list(
      await session.scalars(
        select(WorkflowRunEvent).where(
          WorkflowRunEvent.instance_id == seed.instance_id,
          WorkflowRunEvent.event_type == "node_completed",
        )
      )
    )

  assert node is not None
  assert node.engine_state == WorkflowNodeEngineState.COMPLETED
  assert node.node_instance_version == 2
  assert receipt_count == 1
  assert len(events) == 1
  assert events[0].command_id == command_id


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
@pytest.mark.parametrize("fault_point", ["after_work_item", "after_node", "after_outbox"])
async def test_i3f_command_fault_injection_rolls_back_all_business_writes(
  pg_session_factory,
  fault_point: str,
) -> None:
  seed = await _seed_graph(pg_session_factory, node_keys=("A",), edges=())
  command_id = f"pg-i3f-fault-{fault_point}-{uuid4().hex}"
  title = f"rollback-{command_id}"

  async with pg_session_factory() as session:
    async def operation() -> dict[str, object]:
      task = Task(
        title=title,
        creator_id=seed.actor_id,
        assignee_id=seed.actor_id,
        priority=TaskPriority.MEDIUM,
        source_type=TaskSourceType.MANUAL,
        extra_metadata={},
      )
      session.add(task)
      await session.flush()
      if fault_point == "after_work_item":
        raise RuntimeError(fault_point)

      node = await session.get(WorkflowNodeInstance, seed.nodes["A"], with_for_update=True)
      assert node is not None
      node.engine_state = WorkflowNodeEngineState.COMPLETED
      node.node_instance_version += 1
      await session.flush()
      if fault_point == "after_node":
        raise RuntimeError(fault_point)

      session.add(
        WorkflowOutboxEvent(
          instance_id=seed.instance_id,
          node_instance_id=seed.nodes["A"],
          event_type="workflow_node_activated",
          payload={},
        )
      )
      await session.flush()
      raise RuntimeError(fault_point)

    with pytest.raises(RuntimeError, match=fault_point):
      await WorkflowCommandExecutor(session).execute(
        command_id=command_id,
        command_type="complete_node",
        payload={"node_instance_id": str(seed.nodes["A"])},
        operation=operation,
        actor_user_id=seed.actor_id,
      )

  async with pg_session_factory() as session:
    node = await session.get(WorkflowNodeInstance, seed.nodes["A"])
    assert node is not None
    assert node.engine_state == WorkflowNodeEngineState.ACTIVATED
    assert node.node_instance_version == 1
    assert await session.scalar(select(func.count(Task.id)).where(Task.title == title)) == 0
    assert await session.scalar(
      select(func.count(WorkflowOutboxEvent.id)).where(
        WorkflowOutboxEvent.instance_id == seed.instance_id
      )
    ) == 0
    receipt = await session.scalar(
      select(WorkflowCommandReceipt).where(WorkflowCommandReceipt.command_id == command_id)
    )
    assert receipt is not None
    assert receipt.status == "failed"


@pytest.mark.asyncio
@pytest.mark.workflow_i4_gate
async def test_i3f_commit_failure_rolls_back_success_receipt_and_node(pg_session_factory) -> None:
  seed = await _seed_graph(pg_session_factory, node_keys=("A",), edges=())
  command_id = f"pg-i3f-commit-fault-{uuid4().hex}"

  async with pg_session_factory() as session:
    original_commit = session.commit
    commit_attempts = 0

    async def fail_first_commit() -> None:
      nonlocal commit_attempts
      commit_attempts += 1
      if commit_attempts == 1:
        raise RuntimeError("commit-fault")
      await original_commit()

    session.commit = fail_first_commit  # type: ignore[method-assign]

    async def operation() -> dict[str, object]:
      node = await session.get(WorkflowNodeInstance, seed.nodes["A"], with_for_update=True)
      assert node is not None
      node.engine_state = WorkflowNodeEngineState.COMPLETED
      node.node_instance_version += 1
      await session.flush()
      return {"node_instance_id": str(node.id)}

    with pytest.raises(RuntimeError, match="commit-fault"):
      await WorkflowCommandExecutor(session).execute(
        command_id=command_id,
        command_type="complete_node",
        payload={"node_instance_id": str(seed.nodes["A"])},
        operation=operation,
        actor_user_id=seed.actor_id,
      )

  async with pg_session_factory() as session:
    node = await session.get(WorkflowNodeInstance, seed.nodes["A"])
    assert node is not None
    assert node.engine_state == WorkflowNodeEngineState.ACTIVATED
    assert node.node_instance_version == 1
    receipt = await session.scalar(
      select(WorkflowCommandReceipt).where(WorkflowCommandReceipt.command_id == command_id)
    )
    assert receipt is not None
    assert receipt.status == "failed"


@pytest.mark.asyncio
async def test_human_task_link_concurrent_primary_claim_allows_one(pg_session_factory) -> None:
  seed = await _seed_graph(
    pg_session_factory,
    node_keys=("A",),
    edges=(),
  )
  task_ids: list[UUID] = []
  async with pg_session_factory() as session:
    for title in ("primary-a", "primary-b"):
      task = Task(
        title=title,
        creator_id=seed.actor_id,
        assignee_id=seed.actor_id,
        priority=TaskPriority.MEDIUM,
        source_type=TaskSourceType.TEMPLATE,
        extra_metadata={},
      )
      session.add(task)
      await session.flush()
      task_ids.append(task.id)
    await session.commit()

  async def link_once(task_id: UUID) -> str:
    async with pg_session_factory() as session:
      try:
        await HumanTaskCoordinator(session).ensure_link(
          task_id=task_id,
          node_instance_id=seed.nodes["A"],
        )
        await session.commit()
        return "created"
      except ConflictError:
        await session.rollback()
        return "conflict"

  outcomes = await asyncio.gather(*(link_once(task_id) for task_id in task_ids))
  assert sorted(outcomes) == ["conflict", "created"]


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
    dependency_count = await session.scalar(
      select(func.count(WorkflowNodeActivationDependency.id)).where(
        WorkflowNodeActivationDependency.node_instance_id == seed.nodes["D"],
        WorkflowNodeActivationDependency.status == "satisfied",
      )
    )
    assert instance is not None and instance.executor_kind == "snapshot"
    assert instance.engine_version == "graph-v3"
    assert (instance.definition_snapshot or {}).get("format_version") == 2
    assert len(instance.definition_hash or "") == 64
    assert downstream is not None
    assert downstream.engine_state == WorkflowNodeEngineState.ACTIVATED
    assert downstream.node_instance_version == 2
    assert downstream_count == 1
    assert dependency_count == 2


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
    traversal_count = await session.scalar(
      select(func.count(WorkflowEdgeTraversal.id)).where(
        WorkflowEdgeTraversal.source_node_instance_id == seed.nodes["A"],
      )
    )
    dependency_count = await session.scalar(
      select(func.count(WorkflowNodeActivationDependency.id)).where(
        WorkflowNodeActivationDependency.node_instance_id == seed.nodes["B"],
      )
    )
    assert upstream is not None and downstream is not None
    assert upstream.engine_state == WorkflowNodeEngineState.COMPLETED
    assert upstream.node_instance_version == 2
    assert downstream.engine_state == WorkflowNodeEngineState.ACTIVATED
    assert downstream.node_instance_version == 2
    assert downstream_count == 1
    assert traversal_count == 1
    assert dependency_count == 1


@pytest.mark.asyncio
async def test_exclusive_join_ignores_unproduced_branch_on_postgres(pg_session_factory) -> None:
  seed = await _seed_graph(
    pg_session_factory,
    node_keys=("A", "B", "C", "D"),
    edges=(
      ("A", "B", {"field": "route", "operator": "eq", "value": "B"}, 0),
      ("A", "C", {"else": True}, 1),
      ("B", "D"),
      ("C", "D"),
    ),
    join_modes={"D": "all"},
    routing_modes={"A": "exclusive"},
    context={"route": "B"},
  )
  await _complete(pg_session_factory, seed.nodes["A"], seed.actor_id)
  await _complete(pg_session_factory, seed.nodes["B"], seed.actor_id)

  async with pg_session_factory() as session:
    skipped = await session.get(WorkflowNodeInstance, seed.nodes["C"])
    downstream = await session.get(WorkflowNodeInstance, seed.nodes["D"])
    assert skipped is not None and skipped.engine_state == WorkflowNodeEngineState.SKIPPED
    assert downstream is not None and downstream.engine_state == WorkflowNodeEngineState.ACTIVATED


@pytest.mark.asyncio
async def test_no_route_fails_with_diagnostic_on_postgres(pg_session_factory) -> None:
  seed = await _seed_graph(
    pg_session_factory,
    node_keys=("A", "B"),
    edges=(("A", "B", {"field": "route", "operator": "eq", "value": "B"}, 0),),
    routing_modes={"A": "exclusive"},
    context={"route": "none"},
  )
  await _complete(pg_session_factory, seed.nodes["A"], seed.actor_id)

  async with pg_session_factory() as session:
    instance = await session.get(WorkflowGraphInstance, seed.instance_id)
    assert instance is not None and instance.status == WorkflowGraphInstanceStatus.FAILED
    assert instance.result == "failed"
    assert instance.diagnostics["code"] == "no_route"


async def _complete_with_context_patch(
  factory,
  node_instance_id: UUID,
  actor_id: UUID,
  value: str,
) -> None:
  async with factory() as session:
    await WorkflowGraphService(session).complete_node_instance(
      node_instance_id=node_instance_id,
      actor_id=actor_id,
      context_updates={"decision": value},
      expected_context_version=1,
    )


@pytest.mark.asyncio
async def test_concurrent_context_patches_conflict_on_same_version(pg_session_factory) -> None:
  seed = await _seed_graph(
    pg_session_factory,
    node_keys=("A", "B", "C"),
    edges=(("A", "B"), ("A", "C")),
  )
  await _complete(pg_session_factory, seed.nodes["A"], seed.actor_id)

  results = await asyncio.gather(
    _complete_with_context_patch(pg_session_factory, seed.nodes["B"], seed.actor_id, "B"),
    _complete_with_context_patch(pg_session_factory, seed.nodes["C"], seed.actor_id, "C"),
    return_exceptions=True,
  )
  assert sum(not isinstance(result, BaseException) for result in results) == 1
  conflicts = [result for result in results if isinstance(result, BaseException)]
  assert len(conflicts) == 1 and isinstance(conflicts[0], ConflictError)

  async with pg_session_factory() as session:
    instance = await session.get(WorkflowGraphInstance, seed.instance_id)
    assert instance is not None and instance.context_version == 2


@pytest.mark.asyncio
async def test_wait_any_winner_revokes_late_concurrent_submit(pg_session_factory) -> None:
  seed = await _seed_graph(
    pg_session_factory,
    node_keys=("A", "B", "C", "D"),
    edges=(("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")),
    join_modes={"D": "any"},
  )
  await _complete(pg_session_factory, seed.nodes["A"], seed.actor_id)
  results = await asyncio.gather(
    _complete(pg_session_factory, seed.nodes["B"], seed.actor_id),
    _complete(pg_session_factory, seed.nodes["C"], seed.actor_id),
    return_exceptions=True,
  )
  assert sum(not isinstance(result, BaseException) for result in results) == 1
  assert any(isinstance(result, ConflictError) for result in results)

  async with pg_session_factory() as session:
    downstream = await session.get(WorkflowNodeInstance, seed.nodes["D"])
    upstreams = [
      await session.get(WorkflowNodeInstance, seed.nodes[node_key])
      for node_key in ("B", "C")
    ]
    assert downstream is not None and downstream.engine_state == WorkflowNodeEngineState.ACTIVATED
    assert {node.engine_state for node in upstreams if node is not None} == {
      WorkflowNodeEngineState.COMPLETED,
      WorkflowNodeEngineState.TERMINATED,
    }


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


@pytest.mark.asyncio
async def test_deep_reject_invalidates_path_and_blocks_old_iteration_on_postgres(
  pg_session_factory,
) -> None:
  seed = await _seed_graph(
    pg_session_factory,
    node_keys=("A", "B", "C"),
    edges=(("A", "B"), ("B", "C")),
  )
  await _complete(pg_session_factory, seed.nodes["A"], seed.actor_id)
  await _complete(pg_session_factory, seed.nodes["B"], seed.actor_id)
  async with pg_session_factory() as session:
    await WorkflowGraphService(session).deep_reject_to_upstream(
      node_instance_id=seed.nodes["C"],
      actor_id=seed.actor_id,
      target_node_key="B",
      reason="Iteration 2 stale iteration proof",
    )

  with pytest.raises(ConflictError, match="旧 iteration"):
    await _complete(pg_session_factory, seed.nodes["C"], seed.actor_id)

  async with pg_session_factory() as session:
    traversal = await session.scalar(
      select(WorkflowEdgeTraversal).where(
        WorkflowEdgeTraversal.source_node_instance_id == seed.nodes["B"],
      )
    )
    stale_dependency_count = await session.scalar(
      select(func.count(WorkflowNodeActivationDependency.id)).where(
        WorkflowNodeActivationDependency.instance_id == seed.instance_id,
        WorkflowNodeActivationDependency.status == "invalidated",
      )
    )
    assert traversal is not None and traversal.status == "invalidated"
    assert stale_dependency_count and stale_dependency_count >= 1


def test_ephemeral_database_drop_leaves_no_residue(postgres_database: PostgresDatabase) -> None:
  _, _, database_name = run_async(
    provision_ephemeral_database(postgres_database.admin_dsn, prefix="filum_drop_i0")
  )
  try:
    assert run_async(database_exists(postgres_database.admin_dsn, database_name))
  finally:
    run_async(drop_ephemeral_database(postgres_database.admin_dsn, database_name))
  assert not run_async(database_exists(postgres_database.admin_dsn, database_name))
