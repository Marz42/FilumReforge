from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from uuid import uuid4

from app.api.error_handlers import register_exception_handlers
from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.request_context import REQUEST_ID_HEADER, bind_request_context, reset_request_context


class RequestContextMiddleware:
  def __init__(self, app: ASGIApp) -> None:
    self.app = app

  async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] != "http":
      await self.app(scope, receive, send)
      return

    headers = Headers(scope=scope)
    request_id = headers.get(REQUEST_ID_HEADER) or uuid4().hex
    scope.setdefault("state", {})
    scope["state"]["request_id"] = request_id
    token = bind_request_context(
      request_id=request_id,
      http_method=scope["method"],
      path=scope["path"],
    )

    async def send_with_request_id(message: Message) -> None:
      if message["type"] == "http.response.start":
        mutable_headers = MutableHeaders(scope=message)
        mutable_headers[REQUEST_ID_HEADER] = request_id
      await send(message)

    try:
      await self.app(scope, receive, send_with_request_id)
    finally:
      reset_request_context(token)


def create_app() -> FastAPI:
  settings = get_settings()

  application = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
  )
  application.state.error_tracking_session_factory = get_session_factory()
  application.add_middleware(RequestContextMiddleware)
  if settings.app_env == "development":
    application.add_middleware(
      CORSMiddleware,
      allow_origin_regex=r"https?://[^/]+(?::\d+)?$",
      allow_credentials=False,
      allow_methods=["*"],
      allow_headers=["*"],
    )
  register_exception_handlers(application)

  application.include_router(api_router, prefix=settings.api_v1_prefix)

  @application.get("/healthz", include_in_schema=False)
  async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

  return application


app = create_app()
