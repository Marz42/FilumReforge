from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import (
  AttachmentStatus,
  AttachmentTargetType,
  CommentFormat,
  DelegationScopeType,
  EmploymentEventType,
  NotificationChannel,
  PositionAssignmentType,
  ReportingLineType,
  TaskActionType,
  TaskStatus,
  UserRole,
  UserStatus,
)
from app.core.exceptions import AuthorizationError, ConflictError
from app.models import AttachmentLink, TaskLog
from app.integrations.storage.local import LocalStorageAdapter
from app.services.attachment_service import AttachmentService
from app.services.auth_service import AuthService
from app.services.delegation_service import DelegationService
from app.services.department_service import DepartmentService
from app.services.hr_lifecycle_service import HRLifecycleService
from app.services.notification_service import NotificationService
from app.services.object_storage_service import ObjectStorageService
from app.services.organization_relation_service import OrganizationRelationService
from app.services.profile_service import ProfileService
from app.services.task_service import CommentAttachmentInput, TaskService
from app.services.user_service import UserService


class InMemoryQueuePublisher:
  def __init__(self) -> None:
    self.payloads: list[dict[str, str]] = []

  async def publish(self, payload):  # noqa: ANN001
    self.payloads.append(payload)


TEST_JWT_SECRET = "test-secret-key-with-32-bytes-minimum!!"


@pytest.mark.asyncio
async def test_auth_service_bootstrap_login_and_refresh(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET, storage_base_path="./.storage-test")
  auth_service = AuthService(db_session, settings)

  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )
  session = await auth_service.authenticate(email="admin@example.com", password="StrongPassword123!")
  refreshed = await auth_service.refresh(refresh_token=session.refresh_token)
  access_user = await auth_service.get_user_from_access_token(session.access_token)

  assert admin.role == UserRole.ADMIN
  assert session.token_type == "bearer"
  assert refreshed.access_token != session.access_token
  assert access_user.id == admin.id


@pytest.mark.asyncio
async def test_department_profile_and_user_services(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  department_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)

  hr_user = await user_service.create_user(
    actor=admin,
    email="hr@example.com",
    password="StrongPassword123!",
    role=UserRole.HR,
  )
  department = await department_service.create_department(
    actor=admin,
    name="人事部",
    code="hr-dept",
    manager_id=hr_user.id,
  )
  profile = await profile_service.create_profile(
    actor=admin,
    user_id=hr_user.id,
    employee_no="EMP-HR-001",
    real_name="人事专员",
    department_id=department.id,
    custom_fields={"skills": ["recruiting"]},
  )

  users = await user_service.list_users(actor=admin)
  departments = await department_service.list_departments(actor=admin)
  profiles = await profile_service.list_profiles(actor=admin)

  assert hr_user in users
  assert department in departments
  assert profile in profiles
  assert profile.custom_fields["skills"] == ["recruiting"]


@pytest.mark.asyncio
async def test_attachment_service_upload_and_soft_delete(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  with TemporaryDirectory() as tmp_dir:
    storage_service = ObjectStorageService(
      LocalStorageAdapter(base_path=tmp_dir, bucket="filum-test")
    )
    attachment_service = AttachmentService(db_session, storage_service)

    attachment = await attachment_service.upload_attachment(
      actor=admin,
      filename="spec.pdf",
      content_type="application/pdf",
      content=b"pdf-content",
      target_type=AttachmentTargetType.TASK,
      target_id=admin.id,
    )
    deleted = await attachment_service.delete_attachment(actor=admin, attachment_id=attachment.id)

    file_path = Path(tmp_dir) / "filum-test" / attachment.object_key
    assert attachment.original_filename == "spec.pdf"
    assert deleted.status == AttachmentStatus.DELETED
    assert not file_path.exists()


@pytest.mark.asyncio
async def test_task_service_creates_task_and_enqueues_notification(db_session) -> None:
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
  notification_queue = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, notification_queue)
  task_service = TaskService(db_session, notification_service)

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
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=admin_profile.department_id,
  )

  task = await task_service.create_task(
    actor=admin,
    title="完成档案初始化",
    assignee_id=employee.id,
  )
  tasks_for_employee = await task_service.list_tasks(actor=employee)
  task_logs = list(
    await db_session.scalars(select(TaskLog).where(TaskLog.task_id == task.id).order_by(TaskLog.created_at.asc()))
  )

  assert task in tasks_for_employee
  assert len(notification_queue.payloads) == 1
  assert notification_queue.payloads[0]["message_type"] == "task_assigned"
  assert [log.action_type for log in task_logs] == [TaskActionType.CREATED, TaskActionType.ASSIGNED]


@pytest.mark.asyncio
async def test_task_service_enforces_status_transitions_and_records_logs(db_session) -> None:
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
  notification_service = NotificationService(db_session, InMemoryQueuePublisher())
  task_service = TaskService(db_session, notification_service)

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
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=admin_profile.department_id,
  )

  task = await task_service.create_task(
    actor=admin,
    title="推进 Phase 2",
    assignee_id=employee.id,
  )

  with pytest.raises(ConflictError):
    await task_service.transition_task_status(
      actor=employee,
      task_id=task.id,
      target_status=TaskStatus.DONE,
    )

  doing_task = await task_service.transition_task_status(
    actor=employee,
    task_id=task.id,
    target_status=TaskStatus.DOING,
  )
  review_task = await task_service.transition_task_status(
    actor=employee,
    task_id=task.id,
    target_status=TaskStatus.REVIEW,
  )
  assert review_task.status == TaskStatus.REVIEW
  done_task = await task_service.transition_task_status(
    actor=employee,
    task_id=task.id,
    target_status=TaskStatus.DONE,
  )
  task_logs = list(
    await db_session.scalars(select(TaskLog).where(TaskLog.task_id == task.id).order_by(TaskLog.created_at.asc()))
  )

  assert doing_task.started_at is not None
  assert done_task.completed_at is not None
  assert [log.action_type for log in task_logs][-3:] == [
    TaskActionType.STATUS_CHANGED,
    TaskActionType.STATUS_CHANGED,
    TaskActionType.STATUS_CHANGED,
  ]


@pytest.mark.asyncio
async def test_task_service_comments_attachments_and_stats(db_session) -> None:
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
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=admin_profile.department_id,
  )

  with TemporaryDirectory() as tmp_dir:
    storage_service = ObjectStorageService(
      LocalStorageAdapter(base_path=tmp_dir, bucket="filum-test")
    )
    attachment_service = AttachmentService(db_session, storage_service)
    notification_service = NotificationService(db_session, InMemoryQueuePublisher())
    task_service = TaskService(db_session, notification_service, attachment_service)

    overdue_task = await task_service.create_task(
      actor=admin,
      title="补充服务层",
      assignee_id=employee.id,
      due_date=datetime.now(UTC) - timedelta(days=1),
    )

    active_task = await task_service.create_task(
      actor=admin,
      title="整理评论流",
      assignee_id=employee.id,
    )
    active_task = await task_service.transition_task_status(
      actor=employee,
      task_id=active_task.id,
      target_status=TaskStatus.DOING,
    )
    active_task = await task_service.transition_task_status(
      actor=employee,
      task_id=active_task.id,
      target_status=TaskStatus.REVIEW,
    )
    active_task = await task_service.transition_task_status(
      actor=employee,
      task_id=active_task.id,
      target_status=TaskStatus.DONE,
    )

    comment = await task_service.create_task_comment(
      actor=admin,
      task_id=active_task.id,
      content="请补充审计日志。",
      content_format=CommentFormat.MARKDOWN,
      is_internal=True,
      attachments=[
        CommentAttachmentInput(
          filename="review.md",
          content_type="text/markdown",
          content=b"# review",
        )
      ],
    )
    comments_for_admin = await task_service.list_task_comments(actor=admin, task_id=active_task.id)
    comments_for_employee = await task_service.list_task_comments(actor=employee, task_id=active_task.id)
    activity = await task_service.list_task_activity(actor=admin, task_id=active_task.id)
    summary = await task_service.get_task_stats_summary(actor=admin)
    workload = await task_service.get_task_workload(actor=admin)
    comment_logs = list(
      await db_session.scalars(
        select(TaskLog).where(TaskLog.task_id == active_task.id).order_by(TaskLog.created_at.asc())
      )
    )
    comment_attachment_link = await db_session.scalar(
      select(AttachmentLink).where(
        AttachmentLink.target_type == AttachmentTargetType.TASK_COMMENT,
        AttachmentLink.target_id == comment.id,
      )
    )

    assert comment in comments_for_admin
    assert comments_for_employee == []
    assert any(entry.entry_type == "comment" for entry in activity)
    assert any(entry.entry_type == "log" for entry in activity)
    assert comment_attachment_link is not None
    assert any(log.action_type == TaskActionType.COMMENTED for log in comment_logs)
    assert any(log.action_type == TaskActionType.ATTACHMENT_ADDED for log in comment_logs)
    assert summary.total_tasks == 2
    assert summary.completed_tasks == 1
    assert summary.overdue_tasks == 1
    assert summary.tasks_by_status[TaskStatus.DONE] == 1
    assert len(workload) == 1
    assert workload[0].assignee_id == employee.id
    assert workload[0].total_tasks == 2
    assert workload[0].completed_tasks == 1
    assert workload[0].overdue_tasks == 1

    with pytest.raises(AuthorizationError):
      await task_service.create_task_comment(
        actor=employee,
        task_id=active_task.id,
        content="这是内部备注",
        is_internal=True,
      )


@pytest.mark.asyncio
async def test_phase3_services_filter_fields_for_manager_and_delegate(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  department_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)
  organization_relation_service = OrganizationRelationService(db_session)
  delegation_service = DelegationService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  delegate = await user_service.create_user(
    actor=admin,
    email="delegate@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  department = await department_service.create_department(
    actor=admin,
    name="运营部",
    code="operations",
    manager_id=manager.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=manager.id,
    employee_no="EMP-MANAGER-001",
    real_name="直属主管",
    department_id=department.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="普通员工",
    department_id=department.id,
  )

  position = await organization_relation_service.create_position(
    actor=admin,
    code="ops-specialist",
    name="运营专员",
  )
  await organization_relation_service.assign_position(
    actor=admin,
    user_id=employee.id,
    position_id=position.id,
    department_id=department.id,
    assignment_type=PositionAssignmentType.PRIMARY,
    is_primary=True,
    starts_at=date(2025, 1, 1),
  )
  await organization_relation_service.create_reporting_line(
    actor=admin,
    user_id=employee.id,
    manager_user_id=manager.id,
    department_id=department.id,
    line_type=ReportingLineType.SOLID,
    is_primary=True,
    starts_at=date(2025, 1, 1),
  )

  await profile_service.update_profile(
    actor=admin,
    user_id=employee.id,
    custom_fields={
      "salary": 32000,
      "performance": "A",
      "hobby": "摄影",
    },
  )

  await delegation_service.create_delegation(
    actor=manager,
    delegator_user_id=manager.id,
    delegate_user_id=delegate.id,
    scope_type=DelegationScopeType.DATA_ACCESS,
    starts_at=datetime.now(UTC) - timedelta(hours=1),
    ends_at=datetime.now(UTC) + timedelta(days=7),
  )

  employee_view = await profile_service.get_profile_view(actor=employee, user_id=employee.id)
  manager_view = await profile_service.get_profile_view(actor=manager, user_id=employee.id)
  delegate_view = await profile_service.get_profile_view(actor=delegate, user_id=employee.id)

  assert employee_view["employee_no"] == "EMP-001"
  assert "hobby" in employee_view["custom_fields"]
  assert "salary" not in employee_view["custom_fields"]
  assert "performance" not in employee_view["custom_fields"]

  assert manager_view["custom_fields"]["performance"] == "A"
  assert "salary" not in manager_view["custom_fields"]
  assert any(
    field["field_key"] == "performance" and field["can_edit"] is True
    for field in manager_view["visible_fields"]
  )

  assert delegate_view["custom_fields"]["performance"] == "A"
  assert "salary" not in delegate_view["custom_fields"]


@pytest.mark.asyncio
async def test_phase3_services_apply_lifecycle_events(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  user_service = UserService(db_session)
  department_service = DepartmentService(db_session)
  profile_service = ProfileService(db_session)
  organization_relation_service = OrganizationRelationService(db_session)
  lifecycle_service = HRLifecycleService(db_session)

  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )

  department = await department_service.create_department(
    actor=admin,
    name="产品部",
    code="product",
    manager_id=manager.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-PRODUCT-001",
    real_name="产品同学",
    department_id=department.id,
  )

  specialist_position = await organization_relation_service.create_position(
    actor=admin,
    code="product-specialist",
    name="产品专员",
  )
  lead_position = await organization_relation_service.create_position(
    actor=admin,
    code="product-lead",
    name="产品负责人",
  )

  promotion_event = await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.PROMOTION,
    effective_date=date(2025, 2, 1),
    title="晋升产品负责人",
    payload={
      "position_id": str(lead_position.id),
      "department_id": str(department.id),
      "manager_user_id": str(manager.id),
      "job_title": "产品负责人",
      "assignment_type": PositionAssignmentType.PRIMARY.value,
      "is_primary": True,
    },
  )

  offboard_event = await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.OFFBOARD,
    effective_date=date(2025, 3, 1),
    title="办理离职",
    payload={},
  )

  rehire_event = await lifecycle_service.create_event(
    actor=admin,
    user_id=employee.id,
    event_type=EmploymentEventType.REHIRE,
    effective_date=date(2025, 4, 1),
    title="返聘为产品专员",
    payload={
      "position_id": str(specialist_position.id),
      "department_id": str(department.id),
      "assignment_type": PositionAssignmentType.PRIMARY.value,
      "is_primary": True,
    },
  )

  updated_profile = await profile_service.get_profile(actor=admin, user_id=employee.id)
  positions = await organization_relation_service.list_profile_positions(user_id=employee.id)
  events = await lifecycle_service.list_events(user_id=employee.id)
  employee_row = await db_session.get(type(employee), employee.id)

  assert promotion_event.event_type == EmploymentEventType.PROMOTION
  assert offboard_event.event_type == EmploymentEventType.OFFBOARD
  assert rehire_event.event_type == EmploymentEventType.REHIRE
  assert updated_profile.job_title == "产品专员"
  assert employee_row is not None
  assert employee_row.status == UserStatus.ACTIVE
  assert len(events) == 3
  assert any(position.position_id == lead_position.id for position in positions)
  assert any(position.position_id == specialist_position.id and position.is_primary for position in positions)
