from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.enums import (
  NotificationChannel,
  NotificationDeliveryStatus,
  NotificationMessageStatus,
  UserRole,
)
from app.models import NotificationDelivery, NotificationMessage
from app.services.auth_service import AuthService
from app.services.department_service import DepartmentService
from app.services.notification_service import NotificationService
from app.services.profile_service import ProfileService
from app.services.task_service import TaskService
from app.services.user_service import UserService
from app.workers.jobs import enqueue_overdue_task_reminders, process_notification_message_payload
from app.schemas.messages import NotificationMessage as NotificationMessageSchema


class InMemoryQueuePublisher:
  def __init__(self) -> None:
    self.payloads: list[dict[str, object]] = []

  async def publish(self, payload: dict[str, object]) -> None:
    self.payloads.append(payload)


TEST_JWT_SECRET = "test-secret-key-with-32-bytes-minimum!!"


@pytest.mark.asyncio
async def test_process_notification_message_payload_marks_deliveries_sent(db_session) -> None:
  settings = Settings(jwt_secret_key=TEST_JWT_SECRET)
  auth_service = AuthService(db_session, settings)
  admin = await auth_service.bootstrap_admin(
    email="admin@example.com",
    password="StrongPassword123!",
    real_name="管理员",
    employee_no="EMP-ROOT",
  )

  queue_publisher = InMemoryQueuePublisher()
  notification_service = NotificationService(db_session, queue_publisher)
  message = await notification_service.send(
    NotificationMessageSchema(
      source_type="task",
      source_id=admin.id,
      recipient_user_id=admin.id,
      recipient_email=admin.email,
      message_type="task_assigned",
      title="收到任务",
      body_text="请处理任务。",
      channels=[NotificationChannel.EMAIL, NotificationChannel.WEBSOCKET],
    )
  )
  processed_message = await process_notification_message_payload(
    session=db_session,
    payload=queue_publisher.payloads[0],
  )
  deliveries = list(
    await db_session.scalars(
      select(NotificationDelivery)
      .where(NotificationDelivery.message_id == message.id)
      .order_by(NotificationDelivery.created_at.asc())
    )
  )

  assert processed_message is not None
  assert processed_message.status == NotificationMessageStatus.COMPLETED
  assert len(deliveries) == 2
  assert all(delivery.status == NotificationDeliveryStatus.SENT for delivery in deliveries)
  assert all(delivery.attempt_count == 1 for delivery in deliveries)


@pytest.mark.asyncio
async def test_enqueue_overdue_task_reminders_is_idempotent(db_session) -> None:
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
  employee = await user_service.create_user(
    actor=admin,
    email="employee@example.com",
    password="StrongPassword123!",
    role=UserRole.EMPLOYEE,
  )
  department = await department_service.create_department(
    actor=admin,
    name="研发部",
    code="engineering",
    manager_id=admin.id,
  )
  await profile_service.create_profile(
    actor=admin,
    user_id=employee.id,
    employee_no="EMP-001",
    real_name="研发工程师",
    department_id=department.id,
  )

  task_service = TaskService(db_session)
  overdue_task = await task_service.create_task(
    actor=admin,
    title="补发逾期提醒",
    assignee_id=employee.id,
    department_id=department.id,
    due_date=datetime.now(UTC) - timedelta(hours=2),
  )

  queue_publisher = InMemoryQueuePublisher()
  first_created_count = await enqueue_overdue_task_reminders(
    session=db_session,
    queue_publisher=queue_publisher,
  )
  second_created_count = await enqueue_overdue_task_reminders(
    session=db_session,
    queue_publisher=queue_publisher,
  )
  reminder_count = await db_session.scalar(
    select(func.count(NotificationMessage.id)).where(
      NotificationMessage.source_id == overdue_task.id,
      NotificationMessage.message_type == "task_overdue_reminder",
    )
  )

  assert first_created_count == 2
  assert second_created_count == 0
  assert reminder_count == 2
  assert len(queue_publisher.payloads) == 2
