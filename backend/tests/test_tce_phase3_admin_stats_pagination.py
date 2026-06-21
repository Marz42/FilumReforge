"""TCE Phase 3: department stats, run aggregation, and list pagination."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.enums import (
  TaskPriority,
  TaskSourceType,
  TaskStatus,
  UserRole,
  WorkflowGraphInstanceStatus,
)
from app.core.exceptions import AuthorizationError
from app.models import Department, Profile, Task, WorkflowGraphInstance
from app.services.auth_service import AuthService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workflow_graph_service import WorkflowGraphService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


@pytest.mark.asyncio
async def test_tce_b06_stats_summary_filters_by_department(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="tce-b06-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-TCE-B06",
  )
  user_service = UserService(db_session)
  employee = await user_service.create_user(
    actor=admin,
    email="tce-b06-employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  dept_a = Department(name="内容部", code="CONTENT", sort_order=1, is_active=True)
  dept_b = Department(name="制作部", code="PRODUCTION", sort_order=2, is_active=True)
  db_session.add_all([dept_a, dept_b])
  await db_session.flush()

  profile = Profile(user_id=employee.id, real_name="内容员工", employee_no="EMP-B06-E1", department_id=dept_a.id)
  db_session.add(profile)
  await db_session.flush()
  db_session.add_all(
    [
      Task(
        title="内容部任务",
        creator_id=admin.id,
        assignee_id=employee.id,
        department_id=dept_a.id,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        source_type=TaskSourceType.MANUAL,
      ),
      Task(
        title="制作部任务",
        creator_id=admin.id,
        assignee_id=employee.id,
        department_id=dept_b.id,
        status=TaskStatus.DONE,
        priority=TaskPriority.MEDIUM,
        source_type=TaskSourceType.MANUAL,
      ),
    ]
  )
  await db_session.commit()

  task_service = TaskService(db_session, settings=settings)
  scoped = await task_service.get_task_stats_summary(actor=admin, department_id=dept_a.id)
  assert scoped.total_tasks == 1
  assert scoped.tasks_by_status[TaskStatus.TODO] == 1

  with pytest.raises(AuthorizationError):
    await task_service.get_task_stats_summary(actor=employee, department_id=dept_b.id)


@pytest.mark.asyncio
async def test_tce_b09_inbox_pagination_returns_cursor(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET, task_center_v2_enabled=False)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="tce-b09-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-TCE-B09",
  )
  user_service = UserService(db_session)
  assignee = await user_service.create_user(
    actor=admin,
    email="tce-b09-assignee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  for index in range(3):
    db_session.add(
      Task(
        title=f"inbox-task-{index}",
        creator_id=admin.id,
        assignee_id=assignee.id,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        source_type=TaskSourceType.MANUAL,
      )
    )
  await db_session.commit()

  task_service = TaskService(db_session, settings=settings)
  first_page = await task_service.list_task_inbox(actor=assignee, limit=2)
  assert len(first_page.items) == 2
  assert first_page.has_more is True
  assert first_page.next_cursor is not None

  second_page = await task_service.list_task_inbox(
    actor=assignee,
    limit=2,
    after_task_id=first_page.next_cursor,
  )
  assert len(second_page.items) == 1
  assert second_page.has_more is False


@pytest.mark.asyncio
async def test_tce_b11_list_department_runs(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth = AuthService(db_session, settings)
  admin = await auth.bootstrap_admin(
    email="tce-b11-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-TCE-B11",
  )

  dept = Department(name="内容部", code="CONTENT-B11", sort_order=1, is_active=True)
  db_session.add(dept)
  await db_session.flush()

  instance = WorkflowGraphInstance(
    initiator_user_id=admin.id,
    department_id=dept.id,
    source_type="template",
    context={"run_label": "第 3 周选题会"},
    status=WorkflowGraphInstanceStatus.ACTIVE,
    run_label="第 3 周选题会",
    context_version=1,
    max_iterations=5,
  )
  db_session.add(instance)
  await db_session.commit()

  graph_service = WorkflowGraphService(db_session)
  runs = await graph_service.list_department_runs(department_id=dept.id, limit=10)
  assert len(runs) == 1
  assert runs[0].run_label == "第 3 周选题会"
  assert runs[0].instance_id == instance.id
