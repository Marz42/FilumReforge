from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AuthenticationError, AuthorizationError, ConflictError, NotFoundError


def _build_error_response(*, status_code: int, detail: str) -> JSONResponse:
  return JSONResponse(status_code=status_code, content={"detail": detail})


async def handle_authentication_error(_: Request, exc: AuthenticationError) -> JSONResponse:
  return _build_error_response(status_code=401, detail=str(exc))


async def handle_authorization_error(_: Request, exc: AuthorizationError) -> JSONResponse:
  return _build_error_response(status_code=403, detail=str(exc))


async def handle_not_found_error(_: Request, exc: NotFoundError) -> JSONResponse:
  return _build_error_response(status_code=404, detail=str(exc))


async def handle_conflict_error(_: Request, exc: ConflictError) -> JSONResponse:
  return _build_error_response(status_code=409, detail=str(exc))


async def handle_timeout_error(_: Request, __: TimeoutError) -> JSONResponse:
  return _build_error_response(
    status_code=503,
    detail="数据库连接超时。请先启动 PostgreSQL，再重试登录或管理员初始化。",
  )


def register_exception_handlers(application: FastAPI) -> None:
  application.add_exception_handler(AuthenticationError, handle_authentication_error)
  application.add_exception_handler(AuthorizationError, handle_authorization_error)
  application.add_exception_handler(NotFoundError, handle_not_found_error)
  application.add_exception_handler(ConflictError, handle_conflict_error)
  application.add_exception_handler(TimeoutError, handle_timeout_error)
