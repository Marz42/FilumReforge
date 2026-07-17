"""Standalone Work Item (Iteration 3 downstream adaptation).

Covers the P0 fixes: task-center bucketing / visibility for standalone tasks,
the REVIEW-stage creator closure, standalone delegation, delegate candidates,
and the data invariant that standalone tasks never materialise graph rows.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.enums import (
  TaskAssignmentMode,
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  UserRole,
  UserStatus,
)
from app.core.exceptions import ConflictError
from app.models import Task, TaskLog, WorkflowGraphInstance, WorkflowHumanTaskLink, WorkflowNodeInstance
from app.services.auth_service import AuthService
from app.services.task_action_policy import build_standalone_action_context
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workflow_graph_service import WorkflowGraphService
from sqlalchemy import select

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


def _settings() -> Settings:
  return Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    task_center_v2_enabled=True,
    workflow_standalone_manual_tasks_enabled=True,
  )


def _service(db_session, settings: Settings) -> TaskService:
  return TaskService(
    db_session,
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )


async def _seed(db_session):
  settings = _settings()
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="swi-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-SWI-ADMIN",
  )
  user_service = UserService(db_session)
  creator = await user_service.create_user(
    actor=admin,
    email="swi-creator@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  assignee_a = await user_service.create_user(
    actor=admin,
    email="swi-assignee-a@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  assignee_b = await user_service.create_user(
    actor=admin,
    email="swi-assignee-b@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  return settings, admin, creator, assignee_a, assignee_b


async def _new_standalone_task(db_session, *, creator, assignee, status=TaskStatus.TODO) -> Task:
  task = Task(
    title="独立工作项",
    description=None,
    creator_id=creator.id,
    assignee_id=assignee.id,
    department_id=None,
    status=status,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.MANUAL,
    assignment_mode=TaskAssignmentMode.DIRECT.value,
    extra_metadata={},
  )
  db_session.add(task)
  await db_session.commit()
  await db_session.refresh(task)
  return task


@pytest.mark.asyncio
async def test_standalone_todo_buckets_owner_and_creator(db_session) -> None:
  settings, _admin, creator, assignee_a, _b = await _seed(db_session)
  task = await _new_standalone_task(db_session, creator=creator, assignee=assignee_a)
  service = _service(db_session, settings)

  assignee_inbox = await service.list_task_inbox(actor=assignee_a, limit=50)
  inbox_entry = next(e for e in assignee_inbox.items if e.task_id == task.id)
  assert inbox_entry.execution_mode == "standalone"
  assert inbox_entry.requires_action is True
  assert inbox_entry.action_type == "start_work"
  assert {opt.action for opt in inbox_entry.available_actions} == {"start_work", "delegate_assignment"}

  # Non-management creator must see their own standalone task while it is handled
  # by someone else — the P0 visibility fix.
  creator_tracking = await service.list_task_tracking(actor=creator, limit=50)
  assert any(e.task_id == task.id for e in creator_tracking.items)
  creator_inbox = await service.list_task_inbox(actor=creator, limit=50)
  assert not any(e.task_id == task.id for e in creator_inbox.items)


@pytest.mark.asyncio
async def test_standalone_review_routes_to_creator_inbox(db_session) -> None:
  settings, _admin, creator, assignee_a, _b = await _seed(db_session)
  task = await _new_standalone_task(
    db_session, creator=creator, assignee=assignee_a, status=TaskStatus.REVIEW
  )
  service = _service(db_session, settings)

  creator_inbox = await service.list_task_inbox(actor=creator, limit=50)
  entry = next(e for e in creator_inbox.items if e.task_id == task.id)
  assert entry.requires_action is True
  assert entry.action_type == "review_deliverable"
  assert {opt.action for opt in entry.available_actions} == {
    "approve_deliverable",
    "return_for_rework",
  }

  # REVIEW is the creator's TODO only; it should not be duplicated into TRACKING.
  creator_tracking = await service.list_task_tracking(actor=creator, limit=50)
  assert not any(e.task_id == task.id for e in creator_tracking.items)

  # The assignee is no longer the action owner in REVIEW.
  assignee_inbox = await service.list_task_inbox(actor=assignee_a, limit=50)
  assert not any(e.task_id == task.id for e in assignee_inbox.items)


@pytest.mark.asyncio
async def test_standalone_delegate_transfers_assignee(db_session) -> None:
  settings, _admin, creator, assignee_a, assignee_b = await _seed(db_session)
  task = await _new_standalone_task(db_session, creator=creator, assignee=assignee_a)
  service = _service(db_session, settings)

  updated = await service.delegate_task_assignment(
    actor=assignee_a,
    task_id=task.id,
    assignee_id=assignee_b.id,
    reason="请你接手",
  )
  assert updated.assignee_id == assignee_b.id

  # No graph runtime rows are created by a standalone delegate.
  assert (
    await db_session.scalar(
      select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == task.id)
    )
  ) is None


@pytest.mark.asyncio
async def test_standalone_delegate_forbidden_in_review(db_session) -> None:
  settings, _admin, creator, assignee_a, assignee_b = await _seed(db_session)
  task = await _new_standalone_task(
    db_session, creator=creator, assignee=assignee_a, status=TaskStatus.REVIEW
  )
  service = _service(db_session, settings)

  with pytest.raises(ConflictError):
    await service.delegate_task_assignment(
      actor=assignee_a,
      task_id=task.id,
      assignee_id=assignee_b.id,
      reason="尝试在验收阶段转办",
    )


@pytest.mark.asyncio
async def test_delegate_candidates_exclude_current_assignee(db_session) -> None:
  settings, _admin, creator, assignee_a, assignee_b = await _seed(db_session)
  task = await _new_standalone_task(db_session, creator=creator, assignee=assignee_a)
  service = _service(db_session, settings)

  candidates = await service.list_delegate_candidates(actor=assignee_a, task_id=task.id)
  candidate_ids = {candidate.user_id for candidate in candidates}
  assert assignee_a.id not in candidate_ids


@pytest.mark.asyncio
async def test_created_standalone_task_has_no_graph_rows(db_session) -> None:
  settings, admin, _creator, assignee_a, _b = await _seed(db_session)
  service = _service(db_session, settings)

  task = await service.create_task(
    actor=admin,
    title="通过服务创建的独立任务",
    assignee_id=assignee_a.id,
  )

  refreshed = await db_session.get(Task, task.id)
  assert refreshed.source_type == TaskSourceType.MANUAL
  assert refreshed.assignment_mode == TaskAssignmentMode.DIRECT.value
  metadata = refreshed.extra_metadata or {}
  assert "workflow_graph_instance_id" not in metadata
  assert "workflow_node_instance_id" not in metadata

  assert (
    await db_session.scalar(
      select(WorkflowHumanTaskLink).where(WorkflowHumanTaskLink.task_id == task.id)
    )
  ) is None
  # No graph instance / node instance were materialised in this session.
  assert (await db_session.scalar(select(WorkflowGraphInstance))) is None
  assert (await db_session.scalar(select(WorkflowNodeInstance))) is None


@pytest.mark.asyncio
async def test_create_task_rejects_unsupported_assignment_mode(db_session) -> None:
  """Invariant: standalone manual creation only supports direct assignment.

  A handshake request must fail with a stable business error instead of being
  silently normalised to direct by the DB default.
  """
  settings, admin, _creator, assignee_a, _b = await _seed(db_session)
  service = _service(db_session, settings)

  with pytest.raises(ConflictError, match="unsupported_assignment_mode"):
    await service.create_task(
      actor=admin,
      title="请求未实现的握手模式",
      assignee_id=assignee_a.id,
      assignment_mode=TaskAssignmentMode.HANDSHAKE.value,
    )

  task = await service.create_task(
    actor=admin,
    title="显式 direct",
    assignee_id=assignee_a.id,
    assignment_mode=TaskAssignmentMode.DIRECT.value,
  )
  assert task.assignment_mode == TaskAssignmentMode.DIRECT.value


@pytest.mark.asyncio
async def test_action_context_derivation_is_pure(db_session) -> None:
  """Invariant: task_action_policy derivation must be side-effect free.

  Listing / detail reads call it repeatedly; it must never mutate the Task,
  write audit rows, or return unstable results across calls.
  """
  settings, _admin, creator, assignee_a, _b = await _seed(db_session)
  task = await _new_standalone_task(db_session, creator=creator, assignee=assignee_a)

  snapshot = {
    "status": task.status,
    "assignee_id": task.assignee_id,
    "creator_id": task.creator_id,
    "assignment_mode": task.assignment_mode,
    "extra_metadata": dict(task.extra_metadata or {}),
    "updated_at": task.updated_at,
  }
  log_count_before = len(list(await db_session.scalars(select(TaskLog))))

  first = build_standalone_action_context(task=task, actor=assignee_a, is_management=False)
  second = build_standalone_action_context(task=task, actor=assignee_a, is_management=False)
  assert first == second

  assert task.status == snapshot["status"]
  assert task.assignee_id == snapshot["assignee_id"]
  assert task.creator_id == snapshot["creator_id"]
  assert task.assignment_mode == snapshot["assignment_mode"]
  assert dict(task.extra_metadata or {}) == snapshot["extra_metadata"]
  assert task.updated_at == snapshot["updated_at"]
  assert not db_session.dirty
  assert len(list(await db_session.scalars(select(TaskLog)))) == log_count_before


@pytest.mark.asyncio
async def test_review_fallback_when_creator_offboarded(db_session) -> None:
  """REVIEW routing keeps the creator as owner (creator_id is non-nullable),
  and the task-admin override (ADMIN/HR) is the documented fallback path for
  closing the review when the creator can no longer act.
  """
  settings, admin, creator, assignee_a, _b = await _seed(db_session)
  task = await _new_standalone_task(
    db_session, creator=creator, assignee=assignee_a, status=TaskStatus.REVIEW
  )
  creator.status = UserStatus.SUSPENDED
  await db_session.commit()

  service = _service(db_session, settings)
  reviewed = await service.review_task_deliverable(
    actor=admin,
    task_id=task.id,
    approve=True,
    comment="创建人离职，由管理员代为验收",
  )
  assert reviewed.status == TaskStatus.DONE
