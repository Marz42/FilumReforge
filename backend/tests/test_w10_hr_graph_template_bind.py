"""W10 tests: employment event explicit graph-template binding."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.config import Settings
from app.core.enums import (
  EmploymentEventTriggerStatus,
  EmploymentEventType,
  UserRole,
  UserStatus,
  WorkflowGraphTemplateStatus,
)
from app.core.exceptions import ConflictError
from app.models import WorkflowGraphTemplate, WorkflowGraphTemplateNode
from app.services.auth_service import AuthService
from app.services.hr_lifecycle_service import HRLifecycleService, PROCESS_EMPLOYMENT_EVENT_JOB
from app.services.notification_service import NotificationService
from app.services.profile_service import ProfileService
from app.services.user_service import UserService
from app.services.workflow_engine_service import WorkflowEngineService
from app.services.workflow_video_instantiation_service import WorkflowTemplateInstantiationService
from tests.test_services import InMemoryQueuePublisher

TEST_JWT_SECRET = "test-jwt-secret-key-for-suite-123456"


def _enabled_settings() -> Settings:
  return Settings(
    jwt_secret_key=TEST_JWT_SECRET,
    workflow_graph_template_engine_enabled=True,
  )


async def _seed_direct_graph_template(db_session, *, admin, department_id, code: str, name: str):
  template = WorkflowGraphTemplate(
    code=code,
    base_code=code,
    version=1,
    name=name,
    status=WorkflowGraphTemplateStatus.ACTIVE,
    config={
      "instantiation_mode": "direct",
      "run_kind": "batch",
      "participant_policies": {
        "assignees": {
          "type": "department_members",
          "department_id": str(department_id),
        }
      },
    },
    created_by=admin.id,
  )
  db_session.add(template)
  await db_session.flush()
  node = WorkflowGraphTemplateNode(
    template_id=template.id,
    node_key="HANDLE",
    title="办理",
    sort_order=1,
    config={
      "kind": "single",
      "participant_policy_ref": "assignees",
      "task_capability": {
        "surface": "structured_form",
        "submit_mode": "form",
        "state_policy": "submission",
      },
    },
  )
  db_session.add(node)
  await db_session.flush()
  return template


async def _seed_lifecycle_actor(db_session):
  settings = _enabled_settings()
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="w10-admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-W10-ROOT",
  )
  user_service = UserService(db_session)
  profile_service = ProfileService(db_session)
  employee = await user_service.create_user(
    actor=admin,
    email="w10-employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-W10-001",
    real_name="新员工",
    department_id=admin_profile.department_id,
  )
  queue_publisher = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, queue_publisher)
  workflow_engine_service = WorkflowEngineService(db_session, notification_service)
  graph_service = WorkflowTemplateInstantiationService(db_session, settings=settings)
  lifecycle_service = HRLifecycleService(
    db_session,
    workflow_engine_service=workflow_engine_service,
    graph_instantiation_service=graph_service,
    job_queue_publisher=queue_publisher,
    settings=settings,
  )
  return {
    "admin": admin,
    "employee": employee,
    "department_id": admin_profile.department_id,
    "lifecycle_service": lifecycle_service,
    "queue_publisher": queue_publisher,
  }


@pytest.mark.asyncio
async def test_lifecycle_graph_bind_onboard_idempotent(db_session) -> None:
  seed = await _seed_lifecycle_actor(db_session)
  admin = seed["admin"]
  employee = seed["employee"]
  department_id = seed["department_id"]
  lifecycle_service = seed["lifecycle_service"]
  queue_publisher = seed["queue_publisher"]

  onboard_template = await _seed_direct_graph_template(
    db_session, admin=admin, department_id=department_id, code="hr-onboard-v1", name="入职办理"
  )

  onboard = await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.ONBOARD,
    effective_date=date(2026, 9, 1),
    title="办理入职",
    payload={
      "department_id": str(department_id),
      "participants_snapshot": {
        "assignees": {"mode": "subset", "user_ids": [str(employee.id)]},
      },
    },
    workflow_graph_template_id=onboard_template.id,
    workflow_graph_template_version=1,
  )
  assert onboard.trigger_status == EmploymentEventTriggerStatus.PENDING
  assert onboard.workflow_graph_template_version == 1
  assert queue_publisher.jobs[-1] == (PROCESS_EMPLOYMENT_EVENT_JOB, (str(onboard.id),))

  first = await lifecycle_service.process_event_automation(event_id=onboard.id)
  second = await lifecycle_service.process_event_automation(event_id=onboard.id)
  assert first.trigger_status == EmploymentEventTriggerStatus.SUCCEEDED
  assert first.triggered_workflow_graph_instance_id is not None
  assert second.triggered_workflow_graph_instance_id == first.triggered_workflow_graph_instance_id


@pytest.mark.asyncio
async def test_lifecycle_graph_bind_transfer_and_offboard(db_session) -> None:
  seed = await _seed_lifecycle_actor(db_session)
  admin = seed["admin"]
  employee = seed["employee"]
  department_id = seed["department_id"]
  lifecycle_service = seed["lifecycle_service"]

  from app.services.department_service import DepartmentService
  from app.services.profile_service import ProfileService

  dept_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)
  hr_department = await dept_service.create_department(
    actor=admin,
    name="人事办理组",
    code="hr-ops-w10",
    manager_id=admin.id,
  )
  admin_profile = await profile_service.get_profile(actor=admin, user_id=admin.id)
  await profile_service.update_profile(
    actor=admin,
    user_id=admin.id,
    department_id=hr_department.id,
    employee_no=admin_profile.employee_no,
    real_name=admin_profile.real_name,
  )

  transfer_template = await _seed_direct_graph_template(
    db_session, admin=admin, department_id=department_id, code="hr-transfer-v1", name="转岗办理"
  )
  offboard_template = await _seed_direct_graph_template(
    db_session, admin=admin, department_id=hr_department.id, code="hr-offboard-v1", name="离职办理"
  )

  transfer = await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.TRANSFER,
    effective_date=date(2026, 9, 10),
    title="办理转岗",
    payload={
      "department_id": str(department_id),
      "job_title": "专员",
      "participants_snapshot": {
        "assignees": {"mode": "subset", "user_ids": [str(employee.id)]},
      },
    },
    workflow_graph_template_id=transfer_template.id,
  )
  transfer = await lifecycle_service.process_event_automation(event_id=transfer.id)
  assert transfer.trigger_status == EmploymentEventTriggerStatus.SUCCEEDED, transfer.trigger_error
  assert transfer.triggered_workflow_graph_instance_id is not None

  offboard = await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.OFFBOARD,
    effective_date=date(2026, 9, 20),
    title="办理离职",
    payload={
      "department_id": str(hr_department.id),
      "participants_snapshot": {
        "assignees": {"mode": "subset", "user_ids": [str(admin.id)], "include_initiator": True},
      },
    },
    workflow_graph_template_id=offboard_template.id,
  )
  offboard = await lifecycle_service.process_event_automation(event_id=offboard.id)
  assert offboard.trigger_status == EmploymentEventTriggerStatus.SUCCEEDED, offboard.trigger_error
  assert offboard.triggered_workflow_graph_instance_id is not None
  refreshed = await db_session.get(type(employee), employee.id)
  assert refreshed is not None
  assert refreshed.status == UserStatus.OFFBOARDED


@pytest.mark.asyncio
async def test_lifecycle_graph_bind_rejects_archived_template(db_session) -> None:
  seed = await _seed_lifecycle_actor(db_session)
  admin = seed["admin"]
  employee = seed["employee"]
  lifecycle_service = seed["lifecycle_service"]

  template = await _seed_direct_graph_template(
    db_session,
    admin=admin,
    department_id=seed["department_id"],
    code="hr-archived-v1",
    name="已归档",
  )
  template.status = WorkflowGraphTemplateStatus.ARCHIVED
  await db_session.flush()

  with pytest.raises(ConflictError, match="已发布"):
    await lifecycle_service.create_event(
      actor=admin,
      user_id=employee.id,
      event_type=EmploymentEventType.ONBOARD,
      effective_date=date(2026, 9, 1),
      title="办理入职",
      workflow_graph_template_id=template.id,
    )


@pytest.mark.asyncio
async def test_lifecycle_graph_bind_rejects_version_mismatch(db_session) -> None:
  seed = await _seed_lifecycle_actor(db_session)
  admin = seed["admin"]
  employee = seed["employee"]
  lifecycle_service = seed["lifecycle_service"]
  template = await _seed_direct_graph_template(
    db_session,
    admin=admin,
    department_id=seed["department_id"],
    code="hr-version-v1",
    name="版本校验",
  )

  with pytest.raises(ConflictError, match="版本不匹配"):
    await lifecycle_service.create_event(
      actor=admin,
      user_id=employee.id,
      event_type=EmploymentEventType.ONBOARD,
      effective_date=date(2026, 9, 1),
      title="办理入职",
      workflow_graph_template_id=template.id,
      workflow_graph_template_version=99,
    )
