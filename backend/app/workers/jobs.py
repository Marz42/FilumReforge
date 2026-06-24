from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings, get_settings
from app.core.enums import (
  DEFAULT_USER_NOTIFICATION_CHANNELS,
  NotificationChannel,
  NotificationDeliveryStatus,
  NotificationMessageStatus,
  DocumentStatus,
  UserStatus,
  WorkflowStepRunStatus,
)
from app.models import NotificationMessage as NotificationMessageModel
from app.models import Document, WorkflowInstance, WorkflowStepRun
from app.services.board_service import BoardService
from app.integrations.llm.openai_client import OpenAIClient
from app.integrations.notifications.base import NotificationAdapter
from app.integrations.notifications.factory import build_notification_adapters
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
from app.services.hr_lifecycle_service import HRLifecycleService
from app.services.notification_service import NotificationService
from app.services.task_service import TaskService
from app.services.workflow_engine_service import WorkflowEngineService
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
  settings: Settings | None = None,
  adapters: dict[NotificationChannel, NotificationAdapter] | None = None,
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

  resolved_settings = settings or get_settings()
  adapter_map = adapters or build_notification_adapters(session=session, settings=resolved_settings)
  now = datetime.now(UTC)
  message.status = NotificationMessageStatus.PROCESSING
  all_successful = True
  for delivery in deliveries:
    if delivery.status == NotificationDeliveryStatus.SENT:
      continue
    delivery.attempt_count += 1
    delivery.attempted_at = now
    delivery.error_message = None

    adapter = adapter_map.get(delivery.channel)
    if adapter is None:
      delivery.status = NotificationDeliveryStatus.FAILED
      delivery.error_message = f"未配置通知通道适配器：{delivery.channel.value}"
      all_successful = False
      continue

    try:
      external_message_id = await adapter.send(
        message=message,
        delivery=delivery,
      )
    except Exception as exc:  # noqa: BLE001
      delivery.status = NotificationDeliveryStatus.FAILED
      delivery.error_message = str(exc)
      all_successful = False
      continue

    delivery.status = NotificationDeliveryStatus.SENT
    delivery.external_message_id = external_message_id
    delivery.delivered_at = now

  message.status = (
    NotificationMessageStatus.COMPLETED
    if all_successful
    else NotificationMessageStatus.FAILED
  )
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
          channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
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


async def run_due_task_schedules(
  *,
  session: AsyncSession,
  queue_publisher=None,  # noqa: ANN001
) -> int:
  """Run due F-24 graph template schedules (replaces Legacy E no-op)."""
  from app.core.config import get_settings
  from app.services.notification_service import NotificationService
  from app.services.task_service import TaskService
  from app.services.workflow_graph_template_schedule_service import WorkflowGraphTemplateScheduleService
  from app.services.workflow_video_instantiation_service import WorkflowVideoInstantiationService

  settings = get_settings()
  notification_service = NotificationService(session, queue_publisher)
  task_service = TaskService(session, notification_service=notification_service, settings=settings)
  instantiation_service = WorkflowVideoInstantiationService(
    session,
    task_service=task_service,
    settings=settings,
  )
  schedule_service = WorkflowGraphTemplateScheduleService(
    session,
    notification_service=notification_service,
    instantiation_service=instantiation_service,
  )
  return await schedule_service.run_due_schedules()


async def enqueue_pending_workflow_reminders(
  *,
  session: AsyncSession,
  queue_publisher=None,  # noqa: ANN001
) -> int:
  notification_service = NotificationService(session, queue_publisher)

  pending_step_runs = list(
    await session.scalars(
      select(WorkflowStepRun)
      .options(
        selectinload(WorkflowStepRun.assignee),
        selectinload(WorkflowStepRun.step),
        selectinload(WorkflowStepRun.instance)
        .selectinload(WorkflowInstance.definition),
      )
      .where(WorkflowStepRun.status == WorkflowStepRunStatus.PENDING)
      .order_by(WorkflowStepRun.created_at.asc())
    )
  )

  created_count = 0
  now = datetime.now(UTC)
  for step_run in pending_step_runs:
    assignee = step_run.assignee
    instance = step_run.instance
    step = step_run.step
    if assignee is None or assignee.status != UserStatus.ACTIVE or instance is None or step is None:
      continue

    reminder_after_hours = int(step.config.get("reminder_after_hours") or 24)
    if _normalize_datetime(step_run.created_at) > now - timedelta(hours=reminder_after_hours):
      continue

    existing = await session.scalar(
      select(NotificationMessageModel.id).where(
        NotificationMessageModel.source_type == "workflow_step_run",
        NotificationMessageModel.source_id == step_run.id,
        NotificationMessageModel.message_type == "workflow_pending_reminder",
        NotificationMessageModel.recipient_user_id == assignee.id,
      )
    )
    if existing is not None:
      continue

    await notification_service.send(
      NotificationMessage(
        source_type="workflow_step_run",
        source_id=step_run.id,
        recipient_user_id=assignee.id,
        recipient_email=assignee.email,
        message_type="workflow_pending_reminder",
        title=f"审批待处理提醒：{instance.definition.name}",
        body_text=f"流程「{instance.definition.name}」的步骤「{step.name}」仍待处理，请尽快完成。",
        channels=list(DEFAULT_USER_NOTIFICATION_CHANNELS),
        payload={
          "workflow_instance_id": str(instance.id),
          "workflow_definition_id": str(instance.definition_id),
          "step_run_id": str(step_run.id),
          "step_key": step.step_key,
        },
      )
    )
    created_count += 1

  return created_count


async def process_employment_event_automation(
  *,
  session: AsyncSession,
  event_id: UUID | str,
  queue_publisher=None,  # noqa: ANN001
) -> bool:
  resolved_event_id = _parse_uuid(event_id, field_name="event_id") if isinstance(event_id, str) else event_id
  notification_service = NotificationService(session, queue_publisher)
  workflow_engine_service = WorkflowEngineService(session, notification_service)
  lifecycle_service = HRLifecycleService(
    session,
    workflow_engine_service=workflow_engine_service,
    job_queue_publisher=queue_publisher,
  )
  event = await lifecycle_service.process_event_automation(event_id=resolved_event_id)
  return event.trigger_status.value == "succeeded"


async def rebuild_document_embeddings(
  *,
  session: AsyncSession,
  document_id: UUID | str,
  settings: Settings | None = None,
  openai_client: OpenAIClient | None = None,
) -> int:
  resolved_settings = settings or get_settings()
  resolved_document_id = (
    _parse_uuid(document_id, field_name="document_id")
    if isinstance(document_id, str)
    else document_id
  )
  retrieval_service = KnowledgeRetrievalService(
    session,
    resolved_settings,
    openai_client or OpenAIClient(resolved_settings),
  )
  embeddings = await retrieval_service.rebuild_document_embeddings(
    document_id=resolved_document_id,
  )
  return len(embeddings)


async def rebuild_all_document_embeddings(
  *,
  session: AsyncSession,
  settings: Settings | None = None,
  openai_client: OpenAIClient | None = None,
) -> int:
  resolved_settings = settings or get_settings()
  retrieval_service = KnowledgeRetrievalService(
    session,
    resolved_settings,
    openai_client or OpenAIClient(resolved_settings),
  )
  document_ids = list(
    await session.scalars(
      select(Document.id)
      .where(Document.status.in_([DocumentStatus.DRAFT, DocumentStatus.PUBLISHED]))
      .order_by(Document.updated_at.asc())
    )
  )
  rebuilt_count = 0
  for document_id in document_ids:
    await retrieval_service.rebuild_document_embeddings(document_id=document_id)
    rebuilt_count += 1
  return rebuilt_count


async def archive_expired_board_cards(
  *,
  session: AsyncSession,
) -> int:
  board_service = BoardService(session)
  return await board_service.archive_expired_cards()
