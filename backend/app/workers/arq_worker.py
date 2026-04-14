from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.integrations.notifications.queue import (
  PROCESS_NOTIFICATION_MESSAGE_JOB,
  RedisNotificationQueuePublisher,
)
from app.workers.jobs import enqueue_overdue_task_reminders, process_notification_message_payload

OVERDUE_REMINDER_JOB = "enqueue_overdue_task_reminders"


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
  session_factory: async_sessionmaker[AsyncSession] = ctx["session_factory"]  # type: ignore[assignment]
  async with session_factory() as session:
    await process_notification_message_payload(session=session, payload=payload)


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


_settings = get_settings()


class WorkerSettings:
  functions = [process_notification_message, enqueue_overdue_task_reminders_job]
  cron_jobs = [
    cron(
      enqueue_overdue_task_reminders_job,
      name=OVERDUE_REMINDER_JOB,
      minute={0, 15, 30, 45},
      run_at_startup=True,
      unique=True,
    )
  ]
  on_startup = startup
  on_shutdown = shutdown
  redis_settings = RedisSettings.from_dsn(_settings.redis_dsn)
  queue_name = _settings.redis_notification_queue
  max_jobs = 10
  keep_result = 0
  allow_abort_jobs = False
