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
  NotificationReceiptType,
  PositionAssignmentType,
  ReportingLineType,
  TaskActionType,
  TaskStatus,
  UserRole,
  UserStatus,
  WorkflowDefinitionStatus,
  WorkflowInstanceStatus,
)
from app.core.exceptions import AuthorizationError, ConflictError
from app.models import AttachmentLink, TaskDependency, TaskLog
from app.integrations.storage.local import LocalStorageAdapter
from app.services.attachment_service import AttachmentService
from app.services.auth_service import AuthService
from app.services.delegation_service import DelegationService
from app.services.department_service import DepartmentService
from app.services.hr_lifecycle_service import HRLifecycleService
from app.services.message_center_service import MessageCenterService
from app.services.notification_service import NotificationService
from app.services.object_storage_service import ObjectStorageService
from app.services.organization_relation_service import OrganizationRelationService
from app.services.profile_service import ProfileService
from app.services.task_automation_service import TaskAutomationService
from app.services.task_service import CommentAttachmentInput, TaskService
from app.services.task_template_service import TaskTemplateService
from app.services.user_service import UserService
from app.services.workflow_engine_service import WorkflowEngineService


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


@pytest.mark.asyncio
async def test_phase4_template_automation_and_message_center_services(db_session) -> None:
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
  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.HR,
  )
  requester = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  watcher = await user_service.create_user(
    actor=admin,
    email="watcher@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="流程部",
    code="workflow-dept",
    manager_id=manager.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=manager.id,
    employee_no="EMP-MGR-001",
    real_name="部门负责人",
    department_id=department.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=requester.id,
    employee_no="EMP-REQ-001",
    real_name="申请员工",
    department_id=department.id,
  )

  notification_queue = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, notification_queue)
  task_service = TaskService(db_session, notification_service)
  task_template_service = TaskTemplateService(db_session, task_service, notification_service)
  task_automation_service = TaskAutomationService(db_session, task_template_service)
  message_center_service = MessageCenterService(db_session)

  template = await task_template_service.create_template(
    actor=admin,
    code="onboard-sop",
    name="入职 SOP",
    category="hr",
    steps=[
      {
        "step_key": "prepare",
        "title": "提交资料",
        "default_assignee_rule": {"type": "initiator"},
      },
      {
        "step_key": "review",
        "title": "经理复核",
        "default_assignee_rule": {"type": "department_manager"},
        "depends_on_step_keys": ["prepare"],
      },
    ],
  )

  tasks = await task_template_service.instantiate_template(
    actor=requester,
    template_id=template.id,
    watcher_user_ids=[watcher.id],
    payload={"department_id": str(department.id)},
  )
  dependency_rows = list(
    await db_session.scalars(
      select(TaskDependency).where(TaskDependency.task_id == tasks[1].id)
    )
  )
  watchers = await task_service.list_task_watchers(actor=admin, task_id=tasks[0].id)
  watcher_messages = await message_center_service.list_messages(actor=watcher)
  read_receipt = await message_center_service.create_receipt(
    actor=watcher,
    message_id=watcher_messages[0].id,
    receipt_type=NotificationReceiptType.READ,
  )
  idempotent_receipt = await message_center_service.create_receipt(
    actor=watcher,
    message_id=watcher_messages[0].id,
    receipt_type=NotificationReceiptType.READ,
  )

  schedule = await task_automation_service.create_schedule(
    actor=admin,
    template_id=template.id,
    cron_expr="*/5 * * * *",
    payload={"department_id": str(department.id)},
  )
  schedule.next_run_at = datetime.now(UTC) - timedelta(minutes=1)
  await db_session.commit()
  executed_count = await task_automation_service.run_due_schedules(now=datetime.now(UTC))
  all_tasks = await task_service.list_tasks(actor=admin)

  assert len(tasks) == 2
  assert tasks[0].source_type.value == "template"
  assert dependency_rows[0].depends_on_task_id == tasks[0].id
  assert [watcher_binding.user_id for watcher_binding in watchers] == [watcher.id]
  assert len([message for message in watcher_messages if message.message_type == "task_cc_added"]) == 2
  assert read_receipt.id == idempotent_receipt.id
  assert executed_count == 1
  assert len(all_tasks) == 4
  assert schedule.next_run_at is not None


@pytest.mark.asyncio
async def test_phase4_workflow_engine_supports_delegation_and_return_flow(db_session) -> None:
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
  delegation_service = DelegationService(db_session)
  manager = await user_service.create_user(
    actor=admin,
    email="manager@example.com",
    password="StrongPassword123!",
    role=UserRole.HR,
  )
  delegate = await user_service.create_user(
    actor=admin,
    email="delegate@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  requester = await user_service.create_user(
    actor=admin,
    email="requester@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="审批部",
    code="approval-dept",
    manager_id=manager.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=manager.id,
    employee_no="EMP-MGR-002",
    real_name="审批经理",
    department_id=department.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=requester.id,
    employee_no="EMP-REQ-002",
    real_name="申请人",
    department_id=department.id,
  )

  await delegation_service.create_delegation(
    actor=manager,
    delegator_user_id=manager.id,
    delegate_user_id=delegate.id,
    scope_type=DelegationScopeType.APPROVAL,
    scope_department_id=department.id,
    starts_at=datetime.now(UTC) - timedelta(hours=1),
    ends_at=datetime.now(UTC) + timedelta(days=2),
  )

  notification_queue = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, notification_queue)
  workflow_engine_service = WorkflowEngineService(db_session, notification_service)

  definition = await workflow_engine_service.create_definition(
    actor=admin,
    code="leave-approval",
    name="请假审批",
    scope_type="leave_request",
    status=WorkflowDefinitionStatus.ACTIVE,
    steps=[
      {
        "step_key": "draft",
        "name": "申请提交",
        "step_type": "task",
        "assignee_rule": {"type": "initiator"},
      },
      {
        "step_key": "approve",
        "name": "经理审批",
        "step_type": "approval",
        "assignee_rule": {"type": "department_manager"},
        "reject_target_step_key": "draft",
      },
    ],
  )

  instance = await workflow_engine_service.start_workflow(
    actor=requester,
    definition_id=definition.id,
    source_type="leave_request",
    payload={"department_id": str(department.id)},
  )
  draft_step_run = next(
    step_run
    for step_run in instance.step_runs
    if step_run.step is not None and step_run.step.step_key == "draft" and step_run.status.value == "pending"
  )
  instance = await workflow_engine_service.act_step_run(
    actor=requester,
    step_run_id=draft_step_run.id,
    action="approve",
  )
  delegated_step_run = next(
    step_run
    for step_run in instance.step_runs
    if step_run.step is not None and step_run.step.step_key == "approve" and step_run.status.value == "pending"
  )
  assert delegated_step_run.assignee_user_id == delegate.id
  assert delegated_step_run.delegated_from_user_id == manager.id

  returned_instance = await workflow_engine_service.act_step_run(
    actor=delegate,
    step_run_id=delegated_step_run.id,
    action="return",
    comment="补充说明",
  )
  returned_draft_step_run = next(
    step_run
    for step_run in returned_instance.step_runs
    if (
      step_run.step is not None
      and step_run.step.step_key == "draft"
      and step_run.status.value == "pending"
      and step_run.payload.get("iteration") == 2
    )
  )
  assert returned_instance.status == WorkflowInstanceStatus.RETURNED

  resubmitted_instance = await workflow_engine_service.act_step_run(
    actor=requester,
    step_run_id=returned_draft_step_run.id,
    action="approve",
  )
  delegated_step_run = next(
    step_run
    for step_run in resubmitted_instance.step_runs
    if (
      step_run.step is not None
      and step_run.step.step_key == "approve"
      and step_run.status.value == "pending"
      and step_run.payload.get("iteration") == 2
    )
  )
  completed_instance = await workflow_engine_service.act_step_run(
    actor=delegate,
    step_run_id=delegated_step_run.id,
    action="approve",
  )

  assert completed_instance.status == WorkflowInstanceStatus.APPROVED
  assert any(payload["message_type"] == "workflow_action_required" for payload in notification_queue.payloads)
  assert any(payload["message_type"] == "workflow_returned" for payload in notification_queue.payloads)
