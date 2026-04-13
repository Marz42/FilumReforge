from __future__ import annotations

import json
from typing import Any, Protocol

from redis.asyncio import Redis


class NotificationQueuePublisher(Protocol):
  async def publish(self, payload: dict[str, Any]) -> None: ...


class RedisNotificationQueuePublisher:
  def __init__(self, *, redis_dsn: str, queue_name: str) -> None:
    self._redis_dsn = redis_dsn
    self._queue_name = queue_name

  async def publish(self, payload: dict[str, Any]) -> None:
    client = Redis.from_url(self._redis_dsn, decode_responses=True)
    try:
      await client.lpush(self._queue_name, json.dumps(payload))
    finally:
      await client.aclose()
