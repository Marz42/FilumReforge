from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.enums import (
  AttachmentStatus,
  AttachmentTargetType,
  CommentFormat,
  NotificationChannel,
  TaskActionType,
  TaskStatus,
  UserRole,
)
from app.core.exceptions import AuthorizationError, ConflictError
from app.models import AttachmentLink, TaskLog
from app.integrations.storage.local import LocalStorageAdapter
from app.services.attachment_service import AttachmentService
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.notification_service import NotificationService
from app.services.object_storage_service import ObjectStorageService
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
