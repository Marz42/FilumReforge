from __future__ import annotations

import asyncio
from time import time

import pytest
from fastapi import HTTPException, Request
from redis.exceptions import RedisError
from starlette.requests import Request as StarletteRequest

from app.core.rate_limit import (
  InMemoryRateLimiter,
  RedisRateLimiter,
  _resolve_client_identity,
  build_auth_rate_limit_dependency,
)


class FakeRedis:
  """Minimal async Redis stub that implements the auth rate-limit Lua script."""

  def __init__(self) -> None:
    self.store: dict[str, tuple[int, float | None]] = {}
    self.fail = False
    self.eval_calls = 0

  async def eval(self, script: str, numkeys: int, *keys_and_args: str):
    self.eval_calls += 1
    if self.fail:
      raise RedisError("redis unavailable")
    assert numkeys == 1
    key = keys_and_args[0]
    ttl_seconds = int(keys_and_args[1])
    now = time()
    count, expires_at = self.store.get(key, (0, None))
    if expires_at is not None and expires_at <= now:
      count, expires_at = 0, None
    count += 1
    if count == 1:
      expires_at = now + ttl_seconds
    self.store[key] = (count, expires_at)
    ttl = max(1, int(expires_at - now)) if expires_at is not None else ttl_seconds
    return [count, ttl]

  async def aclose(self) -> None:
    return None


@pytest.mark.asyncio
async def test_redis_rate_limiter_shares_quota_across_instances() -> None:
  redis = FakeRedis()
  left = RedisRateLimiter(redis=redis, key_prefix="filum:auth_rl:", fail_mode="reject")
  right = RedisRateLimiter(redis=redis, key_prefix="filum:auth_rl:", fail_mode="reject")

  for _ in range(3):
    decision = await left.check(key="auth:login:10.0.0.1", limit=5, window_seconds=60)
    assert decision.allowed

  for _ in range(2):
    decision = await right.check(key="auth:login:10.0.0.1", limit=5, window_seconds=60)
    assert decision.allowed

  blocked = await left.check(key="auth:login:10.0.0.1", limit=5, window_seconds=60)
  assert not blocked.allowed
  assert blocked.retry_after is not None
  assert blocked.retry_after >= 1
  assert redis.eval_calls == 6


@pytest.mark.asyncio
async def test_redis_rate_limiter_sets_ttl_and_expires_idle_keys() -> None:
  redis = FakeRedis()
  limiter = RedisRateLimiter(redis=redis, key_prefix="t:", fail_mode="reject")
  await limiter.check(key="auth:login:1.1.1.1", limit=10, window_seconds=30)
  assert len(redis.store) == 1
  key = next(iter(redis.store))
  count, expires_at = redis.store[key]
  assert count == 1
  assert expires_at is not None
  assert expires_at <= time() + 30 + 1


@pytest.mark.asyncio
async def test_redis_rate_limiter_reject_mode_fails_closed() -> None:
  redis = FakeRedis()
  redis.fail = True
  limiter = RedisRateLimiter(redis=redis, key_prefix="t:", fail_mode="reject")
  decision = await limiter.check(key="auth:login:1.1.1.1", limit=10, window_seconds=60)
  assert not decision.allowed
  assert decision.backend_unavailable
  assert decision.retry_after == 60


@pytest.mark.asyncio
async def test_redis_rate_limiter_memory_fail_mode_uses_local_fallback() -> None:
  redis = FakeRedis()
  redis.fail = True
  limiter = RedisRateLimiter(redis=redis, key_prefix="t:", fail_mode="memory")
  for _ in range(2):
    decision = await limiter.check(key="auth:login:2.2.2.2", limit=2, window_seconds=60)
    assert decision.allowed
  blocked = await limiter.check(key="auth:login:2.2.2.2", limit=2, window_seconds=60)
  assert not blocked.allowed
  assert not blocked.backend_unavailable


@pytest.mark.asyncio
async def test_in_memory_rate_limiter_drops_idle_empty_buckets() -> None:
  limiter = InMemoryRateLimiter()
  await limiter.check(key="auth:login:x", limit=5, window_seconds=1)
  assert "auth:login:x" in limiter._hits
  await asyncio.sleep(1.05)
  await limiter.check(key="auth:login:x", limit=5, window_seconds=1)
  # Bucket was rebuilt for the new hit after idle expiry cleanup.
  assert "auth:login:x" in limiter._hits
  assert len(limiter._hits["auth:login:x"]) == 1


@pytest.mark.asyncio
async def test_auth_dependency_returns_503_when_redis_unavailable() -> None:
  redis = FakeRedis()
  redis.fail = True
  limiter = RedisRateLimiter(redis=redis, key_prefix="t:", fail_mode="reject")
  dependency = build_auth_rate_limit_dependency(
    scope="auth:login",
    limit_field="auth_login_rate_limit",
  )

  class _Settings:
    auth_login_rate_limit = 10
    auth_rate_limit_window_seconds = 60

  request = StarletteRequest(
    {
      "type": "http",
      "method": "POST",
      "path": "/api/v1/auth/login",
      "headers": [],
      "client": ("127.0.0.1", 41000),
    }
  )
  request.scope["app"] = type("App", (), {"state": type("State", (), {"auth_rate_limiter": limiter})()})()

  with pytest.raises(HTTPException) as exc_info:
    await dependency(request, _Settings())  # type: ignore[arg-type]

  error = exc_info.value
  assert error.status_code == 503
  assert error.headers is not None
  assert error.headers["Retry-After"] == "60"


def test_auth_rate_limit_ignores_untrusted_forwarded_header_identity() -> None:
  request = Request(
    {
      "type": "http",
      "method": "POST",
      "path": "/api/v1/auth/login",
      "headers": [(b"x-forwarded-for", b"198.51.100.77")],
      "client": ("127.0.0.1", 41000),
    }
  )
  assert _resolve_client_identity(request) == "127.0.0.1"
