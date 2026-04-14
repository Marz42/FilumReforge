from __future__ import annotations

from typing import Any, Protocol

from arq import create_pool
from arq.connections import RedisSettings


class NotificationQueuePublisher(Protocol):
  async def publish(self, payload: dict[str, Any]) -> None: ...


PROCESS_NOTIFICATION_MESSAGE_JOB = "process_notification_message"


class RedisNotificationQueuePublisher:
  def __init__(self, *, redis_dsn: str, queue_name: str) -> None:
    self._redis_settings = RedisSettings.from_dsn(redis_dsn)
    self._queue_name = queue_name

  async def publish(self, payload: dict[str, Any]) -> None:
    client = await create_pool(self._redis_settings)
    try:
      await client.enqueue_job(
        PROCESS_NOTIFICATION_MESSAGE_JOB,
        payload,
        _queue_name=self._queue_name,
      )
    finally:
      await client.aclose()
