from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import get_session_factory
from app.core.request_context import REQUEST_ID_HEADER, get_request_context
from app.models import ErrorEvent

logger = logging.getLogger(__name__)

GENERIC_INTERNAL_ERROR_CODE = "internal_error"


def _normalize_uuid(value: object) -> UUID | None:
  if not isinstance(value, str) or not value:
    return None
  try:
    return UUID(value)
  except ValueError:
    return None


def _sanitize_scalar(value: object) -> object:
  if value is None or isinstance(value, (bool, int, float)):
    return value
  if isinstance(value, str):
    text = value.strip()
    if len(text) <= 160:
      return text
    return f"{text[:157]}..."
  return str(value)


def _resolve_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
  session_factory = getattr(request.app.state, "error_tracking_session_factory", None)
  if session_factory is not None:
    return session_factory
  return get_session_factory()


def sanitize_error_context(value: object) -> object:
  if isinstance(value, dict):
    sanitized: dict[str, object] = {}
    for key, item in value.items():
      normalized_key = key.lower()
      if normalized_key in {"password", "token", "refresh_token", "authorization", "access_token"}:
        continue
      sanitized[key] = sanitize_error_context(item)
    return sanitized
  if isinstance(value, list):
    return [sanitize_error_context(item) for item in value[:20]]
  return _sanitize_scalar(value)


async def record_unhandled_exception(
  *,
  request: Request,
  exc: Exception,
  error_code: str = GENERIC_INTERNAL_ERROR_CODE,
) -> str:
  context = get_request_context()
  request_id = (
    context.get("request_id")
    or getattr(request.state, "request_id", None)
    or request.headers.get(REQUEST_ID_HEADER)
    or uuid4().hex
  )
  actor_user_id = _normalize_uuid(context.get("actor_user_id"))
  source_id = _normalize_uuid((context.get("error_context") or {}).get("source_id"))
  event_context = sanitize_error_context(context.get("error_context") or {})

  logger.exception(
    "Unhandled API exception request_id=%s scope=%s stage=%s path=%s actor_user_id=%s",
    request_id,
    context.get("error_scope") or "api.unhandled",
    context.get("error_stage"),
    request.url.path,
    actor_user_id,
    exc_info=exc,
  )

  try:
    async with _resolve_session_factory(request)() as session:
      session.add(
        ErrorEvent(
          request_id=request_id,
          scope=context.get("error_scope") or "api.unhandled",
          actor_user_id=actor_user_id,
          source_type=(context.get("error_context") or {}).get("source_type"),
          source_id=source_id,
          http_method=request.method,
          path=request.url.path,
          error_type=exc.__class__.__name__,
          error_message=str(exc),
          error_code=error_code,
          stage=context.get("error_stage"),
          context_json=event_context if isinstance(event_context, dict) else {"value": event_context},
        )
      )
      await session.commit()
  except Exception as persistence_exc:  # noqa: BLE001
    logger.exception(
      "Failed to persist error event request_id=%s path=%s",
      request_id,
      request.url.path,
      exc_info=persistence_exc,
    )

  return request_id
