from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.integrations.notifications.queue import (
  PROCESS_NOTIFICATION_MESSAGE_JOB,
  RedisNotificationQueuePublisher,
)
from app.workers.jobs import (
  archive_expired_board_cards,
  enqueue_overdue_task_reminders,
  enqueue_pending_workflow_reminders,
  process_employment_event_automation,
  process_notification_message_payload,
  rebuild_all_document_embeddings,
  rebuild_document_embeddings,
  run_due_task_schedules,
)
from app.workers.workflow_outbox_worker import process_workflow_outbox_events

OVERDUE_REMINDER_JOB = "enqueue_overdue_task_reminders"
WORKFLOW_REMINDER_JOB = "enqueue_pending_workflow_reminders"
TASK_SCHEDULE_JOB = "run_due_task_schedules"
BOARD_ARCHIVE_JOB = "archive_expired_board_cards"
REBUILD_DOCUMENT_EMBEDDINGS_JOB = "rebuild_document_embeddings_job"
REBUILD_ALL_DOCUMENT_EMBEDDINGS_JOB = "rebuild_all_document_embeddings_job"
PROCESS_EMPLOYMENT_EVENT_JOB = "process_employment_event_job"
WORKFLOW_OUTBOX_JOB = "process_workflow_outbox_events_job"


async def startup(ctx: dict[str, object]) -> None:
  settings = get_settings()
  engine = create_async_engine(settings.postgres_dsn)
  ctx["settings"] = settings
  ctx["engine"] = engine
  ctx["session_factory"] = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def shutdown(ctx: dict[str, object]) -> None:
  engine = ctx.get("engine")
  if engine is not None:
    await engine.dispose()


async def process_notification_message(ctx: dict[str, object], payload: dict[str, object]) -> None:
  settings: Settings = ctx["settings"]  # type: ignore[assignment]
  session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]  # type: ignore[assignment]
  async with session_factory() as session:
    await process_notification_message_payload(
      session=session,
      payload=payload,
      settings=settings,
    )


async def enqueue_overdue_task_reminders_job(ctx: dict[str, object]) -> int:
  settings: Settings = ctx["settings"]  # type: ignore[assignment]
  session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]  # type: ignore[assignment]
  queue_publisher = RedisNotificationQueuePublisher(
    redis_dsn=settings.redis_dsn,
    queue_name=settings.redis_notification_queue,
  )
  async with session_factory() as session:
    return await enqueue_overdue_task_reminders(
      session=session,
      queue_publisher=queue_publisher,
    )


async def enqueue_pending_workflow_reminders_job(ctx: dict[str, object]) -> int:
  settings: Settings = ctx["settings"]  # type: ignore[assignment]
  session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]  # type: ignore[assignment]
  queue_publisher = RedisNotificationQueuePublisher(
    redis_dsn=settings.redis_dsn,
    queue_name=settings.redis_notification_queue,
  )
  async with session_factory() as session:
    return await enqueue_pending_workflow_reminders(
      session=session,
      queue_publisher=queue_publisher,
    )


async def run_due_task_schedules_job(ctx: dict[str, object]) -> int:
  settings: Settings = ctx["settings"]  # type: ignore[assignment]
  session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]  # type: ignore[assignment]
  queue_publisher = RedisNotificationQueuePublisher(
    redis_dsn=settings.redis_dsn,
    queue_name=settings.redis_notification_queue,
  )
  async with session_factory() as session:
    return await run_due_task_schedules(
      session=session,
      queue_publisher=queue_publisher,
    )


async def archive_expired_board_cards_job(ctx: dict[str, object]) -> int:
  session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]  # type: ignore[assignment]
  async with session_factory() as session:
    return await archive_expired_board_cards(session=session)


async def rebuild_document_embeddings_job(ctx: dict[str, object], document_id: str) -> int:
  settings: Settings = ctx["settings"]  # type: ignore[assignment]
  session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]  # type: ignore[assignment]
  async with session_factory() as session:
    return await rebuild_document_embeddings(
      session=session,
      document_id=document_id,
      settings=settings,
    )


async def rebuild_all_document_embeddings_job(ctx: dict[str, object]) -> int:
  settings: Settings = ctx["settings"]  # type: ignore[assignment]
  session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]  # type: ignore[assignment]
  async with session_factory() as session:
    return await rebuild_all_document_embeddings(
      session=session,
      settings=settings,
    )


async def process_employment_event_job(ctx: dict[str, object], event_id: str) -> bool:
  settings: Settings = ctx["settings"]  # type: ignore[assignment]
  session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]  # type: ignore[assignment]
  queue_publisher = RedisNotificationQueuePublisher(
    redis_dsn=settings.redis_dsn,
    queue_name=settings.redis_notification_queue,
  )
  async with session_factory() as session:
    return await process_employment_event_automation(
      session=session,
      event_id=event_id,
      queue_publisher=queue_publisher,
    )


async def process_workflow_outbox_events_job(ctx: dict[str, object]) -> int:
  settings: Settings = ctx["settings"]  # type: ignore[assignment]
  session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]  # type: ignore[assignment]
  queue_publisher = RedisNotificationQueuePublisher(
    redis_dsn=settings.redis_dsn,
    queue_name=settings.redis_notification_queue,
  )
  return await process_workflow_outbox_events(
    session_factory=session_factory,
    queue_publisher=queue_publisher,
  )


_settings = get_settings()


class WorkerSettings:
  functions = [
    process_notification_message,
    enqueue_overdue_task_reminders_job,
    enqueue_pending_workflow_reminders_job,
    run_due_task_schedules_job,
    archive_expired_board_cards_job,
    rebuild_document_embeddings_job,
    rebuild_all_document_embeddings_job,
    process_employment_event_job,
    process_workflow_outbox_events_job,
  ]
  cron_jobs = [
    cron(
      enqueue_overdue_task_reminders_job,
      name=OVERDUE_REMINDER_JOB,
      minute={0, 15, 30, 45},
      run_at_startup=True,
      unique=True,
    ),
    cron(
      enqueue_pending_workflow_reminders_job,
      name=WORKFLOW_REMINDER_JOB,
      minute={10, 40},
      run_at_startup=True,
      unique=True,
    ),
    cron(
      archive_expired_board_cards_job,
      name=BOARD_ARCHIVE_JOB,
      minute={12, 42},
      run_at_startup=True,
      unique=True,
    ),
    cron(
      process_workflow_outbox_events_job,
      name=WORKFLOW_OUTBOX_JOB,
      second={0, 30},
      run_at_startup=True,
      unique=True,
    ),
    cron(
      run_due_task_schedules_job,
      name=TASK_SCHEDULE_JOB,
      minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
      run_at_startup=True,
      unique=True,
    ),
  ]
  on_startup = startup
  on_shutdown = shutdown
  redis_settings = RedisSettings.from_dsn(_settings.redis_dsn)
  queue_name = _settings.redis_notification_queue
  max_jobs = 10
  keep_result = 0
  allow_abort_jobs = False
