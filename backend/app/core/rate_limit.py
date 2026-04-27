from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings


class InMemoryRateLimiter:
  def __init__(self) -> None:
    self._lock = Lock()
    self._hits: dict[str, deque[float]] = {}

  def check(self, *, key: str, limit: int, window_seconds: int) -> int | None:
    if limit <= 0 or window_seconds <= 0:
      return None

    now = monotonic()
    cutoff = now - window_seconds

    with self._lock:
      bucket = self._hits.setdefault(key, deque())
      while bucket and bucket[0] <= cutoff:
        bucket.popleft()

      if len(bucket) >= limit:
        retry_after = max(1, int(window_seconds - (now - bucket[0])))
        return retry_after

      bucket.append(now)
      return None


def _resolve_client_identity(request: Request) -> str:
  forwarded_for = request.headers.get("x-forwarded-for")
  if forwarded_for:
    return forwarded_for.split(",", 1)[0].strip() or "unknown"
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
      limiter = InMemoryRateLimiter()
      request.app.state.auth_rate_limiter = limiter

    retry_after = limiter.check(
      key=f"{scope}:{_resolve_client_identity(request)}",
      limit=getattr(settings, limit_field),
      window_seconds=settings.auth_rate_limit_window_seconds,
    )
    if retry_after is None:
      return

    raise HTTPException(
      status_code=status.HTTP_429_TOO_MANY_REQUESTS,
      detail="请求过于频繁，请稍后再试。",
      headers={"Retry-After": str(retry_after)},
    )

  return dependency