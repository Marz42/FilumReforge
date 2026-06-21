"""TCE Phase 2: batch task query and snapshot list fields."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

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
from app.models import Task, User, WorkflowGraphInstance, WorkflowNodeInstance
from app.services.auth_service import AuthService
from app.services.task_service import TaskService
from app.services.task_user_facing_state import resolve_task_run_label, resolve_task_user_facing_state
from app.services.user_service import UserService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


@pytest.mark.asyncio
async def test_tce_b04_list_tasks_by_ids_returns_visible_only(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="tce-b04-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-TCE-B04",
  )
  user_service = UserService(db_session)
  employee = await user_service.create_user(
    actor=admin,
    email="tce-b04-employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  visible = Task(
    title="可见任务",
    creator_id=admin.id,
    assignee_id=employee.id,
    status=TaskStatus.TODO,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.MANUAL,
  )
  hidden = Task(
    title="隐藏任务",
    creator_id=admin.id,
    assignee_id=admin.id,
    status=TaskStatus.TODO,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.MANUAL,
  )
  db_session.add_all([visible, hidden])
  await db_session.commit()

  task_service = TaskService(db_session, settings=settings)
  batch = await task_service.list_tasks_by_ids(
    actor=employee,
    task_ids=[visible.id, hidden.id, uuid4()],
  )
  assert [task.id for task in batch] == [visible.id]

  with pytest.raises(ConflictError):
    await task_service.list_tasks_by_ids(actor=employee, task_ids=[uuid4() for _ in range(101)])


@pytest.mark.asyncio
async def test_tce_b05_inbox_includes_run_label_and_user_facing_state(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET, task_center_v2_enabled=True)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="tce-b05-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-TCE-B05",
  )
  user_service = UserService(db_session)
  assignee = await user_service.create_user(
    actor=admin,
    email="tce-b05-assignee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  instance = WorkflowGraphInstance(
    initiator_user_id=admin.id,
    department_id=None,
    source_type="template",
    context={"run_label": "第 12 周选题会"},
    status=WorkflowGraphInstanceStatus.ACTIVE,
    run_label="第 12 周选题会",
    context_version=1,
    max_iterations=5,
  )
  db_session.add(instance)
  await db_session.flush()

  node_instance = WorkflowNodeInstance(
    instance_id=instance.id,
    node_key="N1_PROPOSE",
    title="提交选题",
    engine_state=WorkflowNodeEngineState.ACTIVATED,
    business_state=WorkflowNodeBusinessState.DOING,
    assignee_user_id=assignee.id,
    iteration=1,
  )
  db_session.add(node_instance)
  await db_session.flush()

  projection_task = Task(
    title="第 12 周选题会 / 提交选题",
    creator_id=admin.id,
    assignee_id=assignee.id,
    status=TaskStatus.DOING,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.TEMPLATE,
    extra_metadata={
      "workflow_graph_instance_id": str(instance.id),
      "workflow_node_instance_id": str(node_instance.id),
      "template_node_key": "N1_PROPOSE",
      "ui_profile": "video_n1_capture",
    },
  )
  db_session.add(projection_task)
  await db_session.commit()

  task_service = TaskService(db_session, settings=settings)
  inbox = await task_service.list_task_inbox(actor=assignee, limit=20)
  entry = next(item for item in inbox if item.task_id == projection_task.id)
  assert entry.run_label == "第 12 周选题会"
  assert entry.user_facing_state == "pending"


@pytest.mark.asyncio
async def test_tce_b07_tracking_uses_provided_inbox_exclusion(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET, task_center_v2_enabled=False)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="tce-b07-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-TCE-B07",
  )
  user_service = UserService(db_session)
  assignee = await user_service.create_user(
    actor=admin,
    email="tce-b07-assignee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  inbox_task = Task(
    title="inbox-only",
    creator_id=admin.id,
    assignee_id=assignee.id,
    status=TaskStatus.TODO,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.MANUAL,
  )
  tracking_task = Task(
    title="tracking-only",
    creator_id=assignee.id,
    assignee_id=admin.id,
    status=TaskStatus.DOING,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.MANUAL,
  )
  db_session.add_all([inbox_task, tracking_task])
  await db_session.commit()

  task_service = TaskService(db_session, settings=settings)
  tracking = await task_service.list_task_tracking(
    actor=assignee,
    limit=20,
    exclude_inbox_task_ids={inbox_task.id},
  )
  assert any(item.task_id == tracking_task.id for item in tracking)
  assert all(item.task_id != inbox_task.id for item in tracking)


def test_resolve_task_run_label_prefers_metadata_and_graph_context() -> None:
  assert (
    resolve_task_run_label(
      title="ignored / suffix",
      metadata={"run_label": "Run-A"},
      graph_run_label="Run-B",
    )
    == "Run-A"
  )
  assert resolve_task_run_label(title="Batch / Node", metadata={}, graph_run_label="Graph-Run") == "Graph-Run"
  assert resolve_task_run_label(title="Batch / Node", metadata={}, graph_run_label=None) == "Node"
