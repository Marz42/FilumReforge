from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic, time
from typing import Annotated, Protocol

from fastapi import Depends, HTTPException, Request, status
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings, get_settings

# Atomic fixed-window counter: INCR and EXPIRE stay together so idle keys expire.
_REDIS_HIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


@dataclass(frozen=True)
class RateLimitDecision:
  allowed: bool
  retry_after: int | None = None
  backend_unavailable: bool = False


class RateLimiter(Protocol):
  async def check(self, *, key: str, limit: int, window_seconds: int) -> RateLimitDecision: ...


class InMemoryRateLimiter:
  """Process-local sliding window; kept for tests and explicit memory backend/fallback."""

  def __init__(self) -> None:
    self._lock = Lock()
    self._hits: dict[str, deque[float]] = {}

  async def check(self, *, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
    if limit <= 0 or window_seconds <= 0:
      return RateLimitDecision(allowed=True)

    now = monotonic()
    cutoff = now - window_seconds

    with self._lock:
      bucket = self._hits.get(key)
      if bucket is None:
        bucket = deque()
        self._hits[key] = bucket
      while bucket and bucket[0] <= cutoff:
        bucket.popleft()
      if not bucket:
        # Drop idle empty buckets so process-local maps do not grow forever.
        self._hits.pop(key, None)
        bucket = deque()
        self._hits[key] = bucket

      if len(bucket) >= limit:
        retry_after = max(1, int(window_seconds - (now - bucket[0])))
        return RateLimitDecision(allowed=False, retry_after=retry_after)

      bucket.append(now)
      return RateLimitDecision(allowed=True)


class RedisRateLimiter:
  """Shared fixed-window limiter for multi-worker auth entrypoints."""

  def __init__(
    self,
    *,
    redis: Redis,
    key_prefix: str,
    fail_mode: str,
    memory_fallback: InMemoryRateLimiter | None = None,
  ) -> None:
    self._redis = redis
    self._key_prefix = key_prefix
    self._fail_mode = fail_mode
    self._memory_fallback = memory_fallback or InMemoryRateLimiter()

  async def aclose(self) -> None:
    await self._redis.aclose()

  async def check(self, *, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
    if limit <= 0 or window_seconds <= 0:
      return RateLimitDecision(allowed=True)

    window_id = int(time()) // window_seconds
    redis_key = f"{self._key_prefix}{key}:{window_id}"
    try:
      result = await self._redis.eval(
        _REDIS_HIT_SCRIPT,
        1,
        redis_key,
        str(window_seconds),
      )
      current = int(result[0])
      ttl = int(result[1])
    except (RedisError, TypeError, ValueError, IndexError):
      if self._fail_mode == "memory":
        return await self._memory_fallback.check(
          key=key,
          limit=limit,
          window_seconds=window_seconds,
        )
      # Fail closed: never silently open the auth entrypoint.
      return RateLimitDecision(
        allowed=False,
        retry_after=max(1, window_seconds),
        backend_unavailable=True,
      )

    if current > limit:
      retry_after = max(1, ttl if ttl > 0 else window_seconds)
      return RateLimitDecision(allowed=False, retry_after=retry_after)
    return RateLimitDecision(allowed=True)


def build_auth_rate_limiter(settings: Settings) -> RateLimiter:
  backend = settings.auth_rate_limit_backend.strip().lower()
  if backend == "redis":
    redis = Redis.from_url(settings.redis_dsn, decode_responses=True)
    return RedisRateLimiter(
      redis=redis,
      key_prefix=settings.auth_rate_limit_key_prefix,
      fail_mode=settings.auth_rate_limit_redis_fail_mode.strip().lower(),
    )
  return InMemoryRateLimiter()


def _resolve_client_identity(request: Request) -> str:
  # Uvicorn rewrites request.client only when the direct peer is listed in
  # --forwarded-allow-ips. Never consume attacker-controlled forwarding
  # headers a second time at the application layer.
  if request.client is not None and request.client.host:
    return request.client.host
  return "unknown"


def build_auth_rate_limit_dependency(*, scope: str, limit_field: str):
  async def dependency(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
  ) -> None:
    limiter = getattr(request.app.state, "auth_rate_limiter", None)
    if limiter is None:
      limiter = build_auth_rate_limiter(settings)
      request.app.state.auth_rate_limiter = limiter

    decision = await limiter.check(
      key=f"{scope}:{_resolve_client_identity(request)}",
      limit=getattr(settings, limit_field),
      window_seconds=settings.auth_rate_limit_window_seconds,
    )
    if decision.allowed:
      return

    if decision.backend_unavailable:
      raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="认证限流服务暂时不可用，请稍后再试。",
        headers={"Retry-After": str(decision.retry_after or 1)},
      )

    raise HTTPException(
      status_code=status.HTTP_429_TOO_MANY_REQUESTS,
      detail="请求过于频繁，请稍后再试。",
      headers={"Retry-After": str(decision.retry_after or 1)},
    )

  return dependency
