"""Scenario E: true concurrent command races for standalone Work Items.

Runs against an ephemeral PostgreSQL database (production dialect) so that the
row-lock ordering in TaskService is exercised for real. Complements the
API-level conflict tests in test_standalone_work_item_e2e.py, which run on
SQLite and can only verify sequential conflict semantics.

Invariant under test: for racing state commands on one standalone task, only
one legal state change wins; the loser receives a stable business error
(authorization or conflict), never a silent lost update or a duplicated
delegate audit record.
"""

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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.core.enums import (
  TaskAssignmentMode,
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  UserRole,
)
from app.core.exceptions import AuthorizationError, ConflictError
from app.models import Task, TaskLog
from app.services.auth_service import AuthService
from app.services.task_service import TaskService
from app.services.user_service import UserService
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
TEST_JWT_SECRET = "standalone-pg-concurrency-secret-32b!"


@dataclass(slots=True)
class PostgresDatabase:
  admin_dsn: str
  async_dsn: str
  database_name: str


@pytest.fixture(scope="module")
def postgres_database() -> PostgresDatabase:
  admin_dsn = postgres_admin_dsn()
  database_name: str | None = None
  old_postgres_dsn = os.environ.get("POSTGRES_DSN")
  try:
    async_dsn, _, database_name = run_async(
      provision_ephemeral_database(admin_dsn, prefix="filum_swi_pg")
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
class SeedUsers:
  admin_id: UUID
  creator_id: UUID
  worker_a_id: UUID
  worker_b_id: UUID
  worker_c_id: UUID


def _settings() -> Settings:
  return Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    task_center_v2_enabled=True,
    workflow_standalone_manual_tasks_enabled=True,
  )


def _service(session: AsyncSession) -> TaskService:
  return TaskService(
    session,
    settings=_settings(),
    workflow_graph_service=WorkflowGraphService(session),
  )


async def _seed_users(factory: async_sessionmaker[AsyncSession]) -> SeedUsers:
  suffix = uuid4().hex[:10]
  async with factory() as session:
    from app.models import User

    # The module-scoped database is shared across tests: bootstrap the admin
    # only once and reuse it afterwards.
    admin = await session.scalar(
      select(User).where(User.role == UserRole.ADMIN).order_by(User.created_at.asc()).limit(1)
    )
    if admin is None:
      admin = await AuthService(session, _settings()).bootstrap_admin(
        email=f"swi-pg-admin-{suffix}@example.com",
        password="StrongPassword123!",
        real_name="管理员",
        employee_no=f"SWI-PG-{suffix}",
      )
    user_service = UserService(session)
    users = []
    for label in ("creator", "worker-a", "worker-b", "worker-c"):
      users.append(
        await user_service.create_user(
          actor=admin,
          email=f"swi-pg-{label}-{suffix}@example.com",
          password="StrongPassword123!",
          role=UserRole.EMPLOYEE,
        )
      )
    await session.commit()
    return SeedUsers(
      admin_id=admin.id,
      creator_id=users[0].id,
      worker_a_id=users[1].id,
      worker_b_id=users[2].id,
      worker_c_id=users[3].id,
    )


async def _seed_task(
  factory: async_sessionmaker[AsyncSession],
  users: SeedUsers,
  *,
  status: TaskStatus = TaskStatus.TODO,
) -> UUID:
  async with factory() as session:
    task = Task(
      title=f"PG 并发任务 {uuid4().hex[:8]}",
      creator_id=users.creator_id,
      assignee_id=users.worker_a_id,
      status=status,
      priority=TaskPriority.MEDIUM,
      source_type=TaskSourceType.MANUAL,
      assignment_mode=TaskAssignmentMode.DIRECT.value,
      extra_metadata={},
    )
    session.add(task)
    await session.commit()
    return task.id


async def _get_user(session: AsyncSession, user_id: UUID):
  from app.models import User

  user = await session.get(User, user_id)
  assert user is not None
  return user


async def _delegate(
  factory: async_sessionmaker[AsyncSession],
  *,
  actor_id: UUID,
  task_id: UUID,
  assignee_id: UUID,
  reason: str,
) -> Exception | None:
  async with factory() as session:
    try:
      actor = await _get_user(session, actor_id)
      await _service(session).delegate_task_assignment(
        actor=actor,
        task_id=task_id,
        assignee_id=assignee_id,
        reason=reason,
      )
      return None
    except Exception as exc:  # noqa: BLE001 - collected for assertion
      return exc


async def _submit(
  factory: async_sessionmaker[AsyncSession],
  *,
  actor_id: UUID,
  task_id: UUID,
) -> Exception | None:
  async with factory() as session:
    try:
      actor = await _get_user(session, actor_id)
      await _service(session).submit_task_deliverable(
        actor=actor,
        task_id=task_id,
        summary="并发提交",
      )
      return None
    except Exception as exc:  # noqa: BLE001
      return exc


async def _start_work(
  factory: async_sessionmaker[AsyncSession],
  *,
  actor_id: UUID,
  task_id: UUID,
) -> Exception | None:
  async with factory() as session:
    try:
      actor = await _get_user(session, actor_id)
      await _service(session).transition_task_status(
        actor=actor,
        task_id=task_id,
        target_status=TaskStatus.DOING,
      )
      return None
    except Exception as exc:  # noqa: BLE001
      return exc


async def _task_state(factory: async_sessionmaker[AsyncSession], task_id: UUID) -> Task:
  async with factory() as session:
    task = await session.get(Task, task_id)
    assert task is not None
    return task


async def _delegate_log_count(factory: async_sessionmaker[AsyncSession], task_id: UUID) -> int:
  async with factory() as session:
    logs = list(await session.scalars(select(TaskLog).where(TaskLog.task_id == task_id)))
  return sum(1 for log in logs if (log.detail or {}).get("action") == "delegated")


def _is_stable_business_error(exc: Exception | None) -> bool:
  return isinstance(exc, (AuthorizationError, ConflictError))


@pytest.mark.asyncio
async def test_concurrent_delegate_by_assignee_and_admin_single_transfer(
  pg_session_factory,
) -> None:
  users = await _seed_users(pg_session_factory)
  task_id = await _seed_task(pg_session_factory, users)

  results = await asyncio.gather(
    _delegate(
      pg_session_factory,
      actor_id=users.worker_a_id,
      task_id=task_id,
      assignee_id=users.worker_b_id,
      reason="执行人转办",
    ),
    _delegate(
      pg_session_factory,
      actor_id=users.admin_id,
      task_id=task_id,
      assignee_id=users.worker_c_id,
      reason="管理员调度",
    ),
  )

  failures = [result for result in results if result is not None]
  assert len(failures) == 1, f"exactly one delegate must lose, got: {results}"
  assert _is_stable_business_error(failures[0]), repr(failures[0])
  assert await _delegate_log_count(pg_session_factory, task_id) == 1
  final = await _task_state(pg_session_factory, task_id)
  assert final.assignee_id in {users.worker_b_id, users.worker_c_id}


@pytest.mark.asyncio
async def test_concurrent_duplicate_delegate_commands_apply_once(pg_session_factory) -> None:
  users = await _seed_users(pg_session_factory)
  task_id = await _seed_task(pg_session_factory, users)

  results = await asyncio.gather(
    *(
      _delegate(
        pg_session_factory,
        actor_id=users.worker_a_id,
        task_id=task_id,
        assignee_id=users.worker_b_id,
        reason="重复提交的转办",
      )
      for _ in range(2)
    )
  )

  failures = [result for result in results if result is not None]
  assert len(failures) == 1, f"duplicate delegate must apply once, got: {results}"
  assert _is_stable_business_error(failures[0]), repr(failures[0])
  assert await _delegate_log_count(pg_session_factory, task_id) == 1
  final = await _task_state(pg_session_factory, task_id)
  assert final.assignee_id == users.worker_b_id


@pytest.mark.asyncio
async def test_concurrent_delegate_and_submit_only_one_wins(pg_session_factory) -> None:
  users = await _seed_users(pg_session_factory)
  task_id = await _seed_task(pg_session_factory, users, status=TaskStatus.DOING)

  delegate_result, submit_result = await asyncio.gather(
    _delegate(
      pg_session_factory,
      actor_id=users.worker_a_id,
      task_id=task_id,
      assignee_id=users.worker_b_id,
      reason="转办与提交竞争",
    ),
    _submit(pg_session_factory, actor_id=users.worker_a_id, task_id=task_id),
  )

  # Legal outcomes: submit wins → task in REVIEW, delegate rejected;
  # delegate wins → task transferred, stale submit rejected.
  final = await _task_state(pg_session_factory, task_id)
  if delegate_result is None and submit_result is None:
    pytest.fail("delegate and submit must not both succeed on the same snapshot")
  if delegate_result is None:
    assert final.assignee_id == users.worker_b_id
    assert final.status == TaskStatus.DOING
    assert _is_stable_business_error(submit_result), repr(submit_result)
  else:
    assert final.status == TaskStatus.REVIEW
    assert final.assignee_id == users.worker_a_id
    assert _is_stable_business_error(delegate_result), repr(delegate_result)


@pytest.mark.asyncio
async def test_concurrent_delegate_and_start_work_stay_consistent(pg_session_factory) -> None:
  users = await _seed_users(pg_session_factory)
  task_id = await _seed_task(pg_session_factory, users)

  delegate_result, start_result = await asyncio.gather(
    _delegate(
      pg_session_factory,
      actor_id=users.worker_a_id,
      task_id=task_id,
      assignee_id=users.worker_b_id,
      reason="转办与开工竞争",
    ),
    _start_work(pg_session_factory, actor_id=users.worker_a_id, task_id=task_id),
  )

  # The delegate must land exactly once; start_work may legally succeed only
  # if it was ordered before the transfer.
  assert delegate_result is None or _is_stable_business_error(delegate_result)
  assert start_result is None or _is_stable_business_error(start_result)
  final = await _task_state(pg_session_factory, task_id)
  if delegate_result is None:
    assert final.assignee_id == users.worker_b_id
    assert await _delegate_log_count(pg_session_factory, task_id) == 1
  else:
    assert final.assignee_id == users.worker_a_id
    assert final.status == TaskStatus.DOING


@pytest.mark.asyncio
async def test_review_transition_concurrent_with_creator_inbox_query(pg_session_factory) -> None:
  users = await _seed_users(pg_session_factory)
  task_id = await _seed_task(pg_session_factory, users, status=TaskStatus.DOING)

  async def creator_inbox_ids() -> set[UUID]:
    async with pg_session_factory() as session:
      creator = await _get_user(session, users.creator_id)
      page = await _service(session).list_task_inbox(actor=creator, limit=50)
      return {entry.task_id for entry in page.items}

  submit_result, _, inbox_after_gather = await asyncio.gather(
    _submit(pg_session_factory, actor_id=users.worker_a_id, task_id=task_id),
    creator_inbox_ids(),
    creator_inbox_ids(),
  )
  assert submit_result is None, repr(submit_result)

  # Deterministic outcome once the write committed: creator owns the review.
  final_inbox = await creator_inbox_ids()
  assert task_id in final_inbox
  assert isinstance(inbox_after_gather, set)
  final = await _task_state(pg_session_factory, task_id)
  assert final.status == TaskStatus.REVIEW
