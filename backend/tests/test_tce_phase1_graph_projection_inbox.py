"""TCE Phase 1: graph projection tasks should use node instance state in inbox."""

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
from app.models import Task, WorkflowGraphInstance, WorkflowNodeInstance
from app.services.auth_service import AuthService
from app.services.task_service import TaskService
from app.services.user_service import UserService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


@pytest.mark.asyncio
async def test_tce_b01_inbox_uses_node_projection_task_graph_state(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET, task_center_v2_enabled=True)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="tce-b01-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-TCE-B01",
  )
  user_service = UserService(db_session)
  assignee = await user_service.create_user(
    actor=admin,
    email="tce-b01-assignee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  instance = WorkflowGraphInstance(
    initiator_user_id=admin.id,
    department_id=None,
    source_type="template",
    status=WorkflowGraphInstanceStatus.ACTIVE,
    run_label="测试批次",
    context={},
    context_version=1,
    max_iterations=5,
  )
  db_session.add(instance)
  await db_session.flush()

  node_instance = WorkflowNodeInstance(
    instance_id=instance.id,
    node_key="N1_PROPOSE",
    title="提交选题",
    engine_state=WorkflowNodeEngineState.COMPLETED,
    business_state=WorkflowNodeBusinessState.DONE,
    assignee_user_id=assignee.id,
    iteration=1,
    completed_at=datetime.now(UTC),
  )
  db_session.add(node_instance)
  await db_session.flush()

  projection_task = Task(
    title="测试批次 / 提交选题",
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
  await db_session.commit()

  task_service = TaskService(db_session, settings=settings)
  inbox_page = await task_service.list_task_inbox(actor=assignee, limit=20)
  assert all(entry.task_id != projection_task.id for entry in inbox_page.items)
