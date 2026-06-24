"""B-12: Legacy E task template runtime removal (TC-Transform Phase 0)."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.config import Settings
from app.core.enums import EmploymentEventType, UserRole, WorkflowDefinitionStatus
from app.core.exceptions import ConflictError
from app.services.auth_service import AuthService
from app.services.hr_lifecycle_service import HRLifecycleService
from app.services.profile_service import ProfileService
from app.services.user_service import UserService
from app.services.workflow_engine_service import WorkflowEngineService
from app.services.notification_service import NotificationService
from app.workers.jobs import run_due_task_schedules

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


class InMemoryQueuePublisher:
  def __init__(self) -> None:
    self.jobs: list[tuple[str, tuple[str, ...]]] = []

  async def enqueue(self, job_name: str, *args: str) -> None:
    self.jobs.append((job_name, args))


@pytest.mark.asyncio
async def test_b12_hr_lifecycle_rejects_task_template_id_on_create(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  lifecycle_service = HRLifecycleService(db_session)

  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-B12-001",
    real_name="生命周期员工",
    department_id=admin_profile.department_id,
  )

  with pytest.raises(ConflictError, match="B-12"):
    await lifecycle_service.create_event(
      actor=admin,
      user_id=employee.id,
      event_type=EmploymentEventType.ONBOARD,
      effective_date=date(2025, 5, 1),
      title="办理入职",
      payload={"department_id": str(admin_profile.department_id)},
      task_template_id=admin.id,
    )


@pytest.mark.asyncio
async def test_b12_hr_lifecycle_allows_workflow_definition_target(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  queue_publisher = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, queue_publisher)
  workflow_engine_service = WorkflowEngineService(db_session, notification_service)
  lifecycle_service = HRLifecycleService(
    db_session,
    workflow_engine_service=workflow_engine_service,
    job_queue_publisher=queue_publisher,
  )

  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-B12-002",
    real_name="生命周期员工",
    department_id=admin_profile.department_id,
  )

  definition = await workflow_engine_service.create_definition(
    actor=admin,
    code="lifecycle-b12-workflow",
    name="入职审批",
    scope_type="employment_event",
    status=WorkflowDefinitionStatus.ACTIVE,
    steps=[
      {
        "step_key": "approve",
        "name": "确认入职",
        "step_type": "approval",
        "assignee_rule": {"type": "user", "user_id": str(admin.id)},
      }
    ],
  )

  event = await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.ONBOARD,
    effective_date=date(2025, 5, 1),
    title="办理入职",
    payload={"department_id": str(admin_profile.department_id)},
    workflow_definition_id=definition.id,
  )

  assert event.trigger_status.value == "pending"
  assert event.workflow_definition_id == definition.id


@pytest.mark.asyncio
async def test_b12_run_due_task_schedules_is_noop(db_session) -> None:
  executed_count = await run_due_task_schedules(session=db_session)
  assert executed_count == 0
