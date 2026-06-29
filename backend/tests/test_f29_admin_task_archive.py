"""F-29: admin archive task terminates workflow run and hides projection tasks."""

from __future__ import annotations

from datetime import UTC, datetime

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
from app.core.exceptions import AuthorizationError, ConflictError
from app.models import Task, WorkflowGraphInstance, WorkflowNodeInstance
from app.services.auth_service import AuthService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workflow_graph_service import WorkflowGraphService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


async def _seed_projection_task(db_session):
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET, task_center_v2_enabled=True)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="f29-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-F29-ADMIN",
  )
  user_service = UserService(db_session)
  assignee = await user_service.create_user(
    actor=admin,
    email="f29-assignee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  instance = WorkflowGraphInstance(
    initiator_user_id=admin.id,
    department_id=None,
    source_type="template",
    status=WorkflowGraphInstanceStatus.ACTIVE,
    run_label="测试 Run",
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
    title="测试 Run / 撰写脚本",
    description=None,
    creator_id=admin.id,
    assignee_id=assignee.id,
    department_id=None,
    status=TaskStatus.DOING,
    priority=TaskPriority.MEDIUM,
    source_type=TaskSourceType.TEMPLATE,
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

  return settings, admin, assignee, instance, node_instance, projection_task


@pytest.mark.asyncio
async def test_f29_admin_archive_cancels_graph_run_and_marks_tasks(db_session) -> None:
  settings, admin, assignee, instance, node_instance, projection_task = await _seed_projection_task(
    db_session
  )
  task_service = TaskService(
    db_session,
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  archived_task, archived_count, cancelled_ids = await task_service.archive_task_by_admin(
    actor=admin,
    task_id=projection_task.id,
    reason="测试误发，管理员作废",
  )

  await db_session.refresh(instance)
  await db_session.refresh(node_instance)
  await db_session.refresh(projection_task)

  assert archived_count == 1
  assert cancelled_ids == [instance.id]
  assert instance.status == WorkflowGraphInstanceStatus.CANCELLED
  assert instance.cancelled_at is not None
  assert (instance.context or {}).get("admin_archived") is True
  assert node_instance.engine_state == WorkflowNodeEngineState.TERMINATED
  assert projection_task.status == TaskStatus.DONE
  assert projection_task.extra_metadata.get("admin_archived") is True
  assert archived_task.id == projection_task.id

  inbox_page = await task_service.list_task_inbox(actor=assignee, limit=20)
  assert all(entry.task_id != projection_task.id for entry in inbox_page.items)


@pytest.mark.asyncio
async def test_f29_admin_archive_requires_admin_role(db_session) -> None:
  settings, admin, assignee, _instance, _node, projection_task = await _seed_projection_task(db_session)
  task_service = TaskService(
    db_session,
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  with pytest.raises(AuthorizationError):
    await task_service.archive_task_by_admin(
      actor=assignee,
      task_id=projection_task.id,
      reason="不应成功",
    )


@pytest.mark.asyncio
async def test_f29_admin_archive_hides_from_history(db_session) -> None:
  settings, admin, assignee, _instance, _node, projection_task = await _seed_projection_task(db_session)
  task_service = TaskService(
    db_session,
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  await task_service.archive_task_by_admin(
    actor=admin,
    task_id=projection_task.id,
    reason="历史过滤测试",
  )

  history_page = await task_service.list_task_history(actor=assignee, limit=20)
  assert all(entry.task_id != projection_task.id for entry in history_page.items)


@pytest.mark.asyncio
async def test_f29_graph_stage_label_avoids_node_instance_parent_lazy_load(db_session) -> None:
  settings, admin, assignee, instance, node_instance, projection_task = await _seed_projection_task(
    db_session
  )
  task_service = TaskService(
    db_session,
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )
  task = await task_service.get_task(actor=admin, task_id=projection_task.id)
  node_instance.instance = None

  label = task_service._build_graph_stage_label(
    task=task,
    instance=instance,
    node_instance=node_instance,
  )
  assert "撰写脚本" in label


@pytest.mark.asyncio
async def test_f29_admin_archive_is_idempotent(db_session) -> None:
  settings, admin, _assignee, _instance, _node, projection_task = await _seed_projection_task(db_session)
  task_service = TaskService(
    db_session,
    settings=settings,
    workflow_graph_service=WorkflowGraphService(db_session),
  )

  await task_service.archive_task_by_admin(
    actor=admin,
    task_id=projection_task.id,
    reason="首次归档",
  )

  with pytest.raises(ConflictError, match="任务已归档"):
    await task_service.archive_task_by_admin(
      actor=admin,
      task_id=projection_task.id,
      reason="重复归档",
    )
