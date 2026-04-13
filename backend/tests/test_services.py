from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.core.config import Settings
from app.core.enums import AttachmentStatus, AttachmentTargetType, NotificationChannel, UserRole
from app.integrations.storage.local import LocalStorageAdapter
from app.services.attachment_service import AttachmentService
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.notification_service import NotificationService
from app.services.object_storage_service import ObjectStorageService
from app.services.profile_service import ProfileService
from app.services.task_service import TaskService
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

  assert task in tasks_for_employee
  assert len(notification_queue.payloads) == 1
  assert notification_queue.payloads[0]["message_type"] == "task_assigned"
