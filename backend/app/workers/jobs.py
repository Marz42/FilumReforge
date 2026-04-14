from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import (
  NotificationChannel,
  NotificationDeliveryStatus,
  NotificationMessageStatus,
  UserStatus,
)
from app.models import NotificationMessage as NotificationMessageModel
from app.services.notification_service import NotificationService
from app.services.task_service import TaskService
from app.schemas.messages import NotificationMessage


def _normalize_datetime(value: datetime) -> datetime:
  if value.tzinfo is None:
    return value.replace(tzinfo=UTC)
  return value.astimezone(UTC)


def _parse_uuid(value: object, *, field_name: str) -> UUID:
  if not isinstance(value, str):
    raise ValueError(f"{field_name} 必须是字符串 UUID。")
  return UUID(value)


async def process_notification_message_payload(
  *,
  session: AsyncSession,
  payload: dict[str, object],
) -> NotificationMessageModel | None:
  message_id = _parse_uuid(payload.get("message_id"), field_name="message_id")
  raw_delivery_ids = payload.get("delivery_ids", [])
  if not isinstance(raw_delivery_ids, list):
    raise ValueError("delivery_ids 必须是 UUID 字符串列表。")
  delivery_ids = [
    _parse_uuid(delivery_id, field_name="delivery_id")
    for delivery_id in raw_delivery_ids
  ]
  delivery_id_set = set(delivery_ids)

  message = await session.scalar(
    select(NotificationMessageModel)
    .options(selectinload(NotificationMessageModel.deliveries))
    .where(NotificationMessageModel.id == message_id)
  )
  if message is None:
    return None

  deliveries = [
    delivery
    for delivery in message.deliveries
    if not delivery_ids or delivery.id in delivery_id_set
  ]
  if not deliveries:
    return message

  now = datetime.now(UTC)
  message.status = NotificationMessageStatus.PROCESSING
  for delivery in deliveries:
    if delivery.status == NotificationDeliveryStatus.SENT:
      continue
    delivery.status = NotificationDeliveryStatus.SENT
    delivery.attempt_count += 1
    delivery.attempted_at = now
    delivery.delivered_at = now

  message.status = NotificationMessageStatus.COMPLETED
  message.completed_at = now
  await session.commit()
  await session.refresh(message)
  return message


async def enqueue_overdue_task_reminders(
  *,
  session: AsyncSession,
  queue_publisher=None,  # noqa: ANN001
) -> int:
  task_service = TaskService(session)
  notification_service = NotificationService(session, queue_publisher)
  overdue_tasks = await task_service.list_overdue_tasks()

  created_count = 0
  for task in overdue_tasks:
    recipients = []
    if task.assignee is not None and task.assignee.status == UserStatus.ACTIVE:
      recipients.append(task.assignee)
    manager = task.department.manager if task.department is not None else None
    if (
      manager is not None
      and manager.status == UserStatus.ACTIVE
      and all(existing.id != manager.id for existing in recipients)
    ):
      recipients.append(manager)

    for recipient in recipients:
      existing = await session.scalar(
        select(NotificationMessageModel.id).where(
          NotificationMessageModel.source_type == "task",
          NotificationMessageModel.source_id == task.id,
          NotificationMessageModel.message_type == "task_overdue_reminder",
          NotificationMessageModel.recipient_user_id == recipient.id,
        )
      )
      if existing is not None:
        continue

      due_date_text = _normalize_datetime(task.due_date).isoformat() if task.due_date is not None else None
      await notification_service.send(
        NotificationMessage(
          source_type="task",
          source_id=task.id,
          recipient_user_id=recipient.id,
          recipient_email=recipient.email,
          message_type="task_overdue_reminder",
          title=f"任务已逾期：{task.title}",
          body_text=f"任务「{task.title}」已超过截止时间，请尽快处理。",
          channels=[NotificationChannel.WEBSOCKET, NotificationChannel.EMAIL],
          payload={
            "task_id": str(task.id),
            "task_title": task.title,
            "due_date": due_date_text,
            "recipient_user_id": str(recipient.id),
          },
        )
      )
      created_count += 1

  return created_count
