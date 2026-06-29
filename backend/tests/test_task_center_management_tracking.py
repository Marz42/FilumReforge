"""Admin/HR oversight: management tracking visibility and overdue extension."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import Settings
from app.core.enums import (
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  UserRole,
  WorkflowGraphInstanceStatus,
  WorkflowNodeBusinessState,
  WorkflowNodeEngineState,
)
from app.core.exceptions import ConflictError
from app.models import Task, WorkflowGraphInstance, WorkflowNodeInstance
from app.services.auth_service import AuthService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workflow_graph_service import WorkflowGraphService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


async def _seed_employee_graph_task(db_session):
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET, task_center_v2_enabled=True)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="mgmt-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-MGMT-ADMIN",
  )
  user_service = UserService(db_session)
  assignee = await user_service.create_user(
    actor=admin,
    email="mgmt-assignee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  instance = WorkflowGraphInstance(
    initiator_user_id=admin.id,
    department_id=None,
    source_type="template",
    status=WorkflowGraphInstanceStatus.ACTIVE,
    run_label="管理可见性 Run",
    context={"run_kind": "production"},
    context_version=1,
    max_iterations=5,
  )
  db_session.add(instance)
  await db_session.flush()

  node_instance = WorkflowNodeInstance(
    instance_id=instance.id,
    node_key="N3_SCRIPT_WRITE",
    title="撰写脚本",
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.DOING,
    assignee_user_id=assignee.id,
    iteration=1,
    activated_at=datetime.now(UTC),
  )
  db_session.add(node_instance)
  await db_session.flush()

  projection_task = Task(
    title="管理可见性 Run / 撰写脚本",
    description=None,
    creator_id=admin.id,
    assignee_id=assignee.id,
    department_id=None,
    status=TaskStatus.DOING,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.TEMPLATE,
    due_date=datetime.now(UTC) - timedelta(days=1),
    extra_metadata={
      "workflow_graph_instance_id": str(instance.id),
      "workflow_node_instance_id": str(node_instance.id),
      "workflow_node_key": node_instance.node_key,
    },
  )
  db_session.add(projection_task)
  await db_session.flush()
  node_instance.config = {"task_id": str(projection_task.id)}
  await db_session.commit()

  return settings, admin, assignee, projection_task


async def _seed_unrelated_employee_task(db_session):
  settings, admin, assignee, _task = await _seed_employee_graph_task(db_session)
  user_service = UserService(db_session)
  other_admin = await user_service.create_user(
    actor=admin,
    email="other-admin@example.com",
    password="StrongPassword123!",
    role=UserRole.ADMIN,
  )
  return settings, other_admin, assignee, _task


@pytest.mark.asyncio
async def test_management_tracking_marks_unrelated_admin_as_oversight(db_session) -> None:
  settings, other_admin, _assignee, projection_task = await _seed_unrelated_employee_task(db_session)
  task_service = TaskService(
    db_session,
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  admin_tracking = await task_service.list_task_tracking(actor=other_admin, limit=50)
  matched = next(entry for entry in admin_tracking.items if entry.task_id == projection_task.id)

  assert "督办" in matched.relation_types


@pytest.mark.asyncio
async def test_management_tracking_lists_employee_in_progress_task(db_session) -> None:
  settings, admin, assignee, projection_task = await _seed_employee_graph_task(db_session)
  task_service = TaskService(
    db_session,
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  assignee_inbox = await task_service.list_task_inbox(actor=assignee, limit=20)
  admin_tracking = await task_service.list_task_tracking(actor=admin, limit=50)

  assert any(entry.task_id == projection_task.id for entry in assignee_inbox.items)
  assert any(entry.task_id == projection_task.id for entry in admin_tracking.items)


@pytest.mark.asyncio
async def test_management_can_extend_overdue_task_due_date(db_session) -> None:
  settings, admin, _assignee, projection_task = await _seed_employee_graph_task(db_session)
  task_service = TaskService(
    db_session,
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  new_due_date = datetime.now(UTC) + timedelta(days=3)
  updated = await task_service.update_task(
    actor=admin,
    task_id=projection_task.id,
    due_date=new_due_date,
  )

  assert updated.due_date is not None
  assert updated.due_date.replace(tzinfo=UTC) >= new_due_date.replace(tzinfo=UTC) - timedelta(seconds=1)


@pytest.mark.asyncio
async def test_extend_overdue_task_rejects_earlier_due_date(db_session) -> None:
  settings, admin, _assignee, projection_task = await _seed_employee_graph_task(db_session)
  task_service = TaskService(
    db_session,
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  with pytest.raises(ConflictError, match="更晚的截止时间"):
    await task_service.update_task(
      actor=admin,
      task_id=projection_task.id,
      due_date=datetime.now(UTC) - timedelta(days=2),
    )
