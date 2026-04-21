from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any
from uuid import UUID

REQUEST_ID_HEADER = "X-Request-ID"

_request_context: ContextVar[dict[str, Any]] = ContextVar("request_context", default={})


def bind_request_context(*, request_id: str, http_method: str, path: str) -> Token[dict[str, Any]]:
  return _request_context.set(
    {
      "request_id": request_id,
      "http_method": http_method,
      "path": path,
      "error_context": {},
    }
  )


def reset_request_context(token: Token[dict[str, Any]]) -> None:
  _request_context.reset(token)


def get_request_context() -> dict[str, Any]:
  return dict(_request_context.get())


def update_request_context(**kwargs: Any) -> None:
  context = get_request_context()
  for key, value in kwargs.items():
    if value is None:
      context.pop(key, None)
      continue
    context[key] = value
  _request_context.set(context)


def set_request_actor(*, user_id: UUID, email: str) -> None:
  update_request_context(actor_user_id=str(user_id), actor_email=email)


def set_error_scope(scope: str) -> None:
  update_request_context(error_scope=scope)


def set_error_stage(stage: str) -> None:
  update_request_context(error_stage=stage)


def merge_error_context(values: dict[str, Any] | None) -> None:
  if not values:
    return
  context = get_request_context()
  error_context = dict(context.get("error_context") or {})
  error_context.update(values)
  context["error_context"] = error_context
  _request_context.set(context)
