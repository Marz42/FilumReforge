"""F-21 / F-27: cross-department routing and boundary CC tests."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.enums import UserRole
from app.services.auth_service import AuthService
from app.services.cross_department_routing_service import resolve_cross_department_boundary_cc_user_ids
from app.services.department_service import DepartmentService
from app.services.profile_service import ProfileService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.services.workflow_graph_service import WorkflowGraphService

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


@pytest.mark.asyncio
async def test_f21_cross_department_create_task_with_path_cc(db_session) -> None:
  auth = AuthService(db_session, Settings(jwt_secret_key=TEST_JWT_SECRET))
  admin = await auth.bootstrap_admin(
    email="f21-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-F21-ROOT",
  )
  user_service = UserService(db_session)
  dept_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)

  division_manager = await user_service.create_user(
    actor=admin,
    email="f21-division-mgr@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  dept_a_manager = await user_service.create_user(
    actor=admin,
    email="f21-dept-a-mgr@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  dept_b_worker = await user_service.create_user(
    actor=admin,
    email="f21-dept-b-worker@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  division = await dept_service.create_department(
    actor=admin,
    name="事业部",
    code="f21-division",
    manager_id=division_manager.id,
  )
  dept_a = await dept_service.create_department(
    actor=admin,
    name="文案 A",
    code="f21-dept-a",
    parent_id=division.id,
    manager_id=dept_a_manager.id,
  )
  dept_b = await dept_service.create_department(
    actor=admin,
    name="文案 B",
    code="f21-dept-b",
    parent_id=division.id,
    manager_id=None,
  )

  for user, employee_no, real_name, department_id in (
    (division_manager, "EMP-F21-DIV", "事业部经理", division.id),
    (dept_a_manager, "EMP-F21-A-M", "A 部经理", dept_a.id),
    (dept_b_worker, "EMP-F21-B-W", "B 部员工", dept_b.id),
  ):
    await profile_service.create_profile(
      actor=admin,
      user_id=user.id,
      employee_no=employee_no,
      real_name=real_name,
      department_id=department_id,
      custom_fields={},
    )

  cc_ids = await resolve_cross_department_boundary_cc_user_ids(
    db_session,
    origin_department_id=dept_a.id,
    target_department_id=dept_b.id,
    exclude_user_ids={dept_a_manager.id, dept_b_worker.id},
  )
  assert division_manager.id in cc_ids

  task_service = TaskService(
    db_session,
    settings=Settings(
      jwt_secret_key=TEST_JWT_SECRET,
      workflow_graph_engine_enabled=True,
      workflow_standalone_manual_tasks_enabled=False,
    ),
    workflow_graph_service=WorkflowGraphService(db_session),
  )
  task = await task_service.create_task(
    actor=dept_a_manager,
    title="跨部门单步",
    assignee_id=dept_b_worker.id,
    department_id=dept_b.id,
  )
  watchers = await task_service.list_task_watchers(actor=dept_a_manager, task_id=task.id)
  watcher_user_ids = {watcher.user_id for watcher in watchers}
  assert division_manager.id in watcher_user_ids
