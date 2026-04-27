from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.error_tracking import GENERIC_INTERNAL_ERROR_CODE, record_unhandled_exception
from app.core.exceptions import (
  AppValidationError,
  AuthenticationError,
  AuthorizationError,
  ConfigurationError,
  ConflictError,
  NotFoundError,
)
from app.core.request_context import REQUEST_ID_HEADER


def _resolve_request_id(request: Request) -> str | None:
  return getattr(request.state, "request_id", None) or request.headers.get(REQUEST_ID_HEADER)


def _build_error_response(
  *,
  request: Request,
  status_code: int,
  detail: str,
  error_code: str | None = None,
) -> JSONResponse:
  request_id = _resolve_request_id(request)
  payload: dict[str, str] = {"detail": detail}
  if request_id:
    payload["request_id"] = request_id
  if error_code:
    payload["error_code"] = error_code
  response = JSONResponse(status_code=status_code, content=payload)
  if request_id:
    response.headers[REQUEST_ID_HEADER] = request_id
  return response


async def handle_authentication_error(request: Request, exc: AuthenticationError) -> JSONResponse:
  return _build_error_response(request=request, status_code=401, detail=str(exc))


async def handle_validation_error(request: Request, exc: AppValidationError) -> JSONResponse:
  return _build_error_response(request=request, status_code=422, detail=str(exc))


async def handle_authorization_error(request: Request, exc: AuthorizationError) -> JSONResponse:
  return _build_error_response(request=request, status_code=403, detail=str(exc))


async def handle_not_found_error(request: Request, exc: NotFoundError) -> JSONResponse:
  return _build_error_response(request=request, status_code=404, detail=str(exc))


async def handle_conflict_error(request: Request, exc: ConflictError) -> JSONResponse:
  return _build_error_response(request=request, status_code=409, detail=str(exc))


async def handle_configuration_error(request: Request, exc: ConfigurationError) -> JSONResponse:
  return _build_error_response(request=request, status_code=503, detail=str(exc))


async def handle_timeout_error(request: Request, __: TimeoutError) -> JSONResponse:
  return _build_error_response(
    request=request,
    status_code=503,
    detail="数据库连接超时。请先启动 PostgreSQL，再重试登录或管理员初始化。",
  )


async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
  request_id = await record_unhandled_exception(
    request=request,
    exc=exc,
    error_code=GENERIC_INTERNAL_ERROR_CODE,
  )
  request.state.request_id = request_id
  return _build_error_response(
    request=request,
    status_code=500,
    detail="服务器内部错误，请记录请求编号并反馈给开发者。",
    error_code=GENERIC_INTERNAL_ERROR_CODE,
  )


def register_exception_handlers(application: FastAPI) -> None:
  application.add_exception_handler(AppValidationError, handle_validation_error)
  application.add_exception_handler(AuthenticationError, handle_authentication_error)
  application.add_exception_handler(AuthorizationError, handle_authorization_error)
  application.add_exception_handler(NotFoundError, handle_not_found_error)
  application.add_exception_handler(ConflictError, handle_conflict_error)
  application.add_exception_handler(ConfigurationError, handle_configuration_error)
  application.add_exception_handler(TimeoutError, handle_timeout_error)
  application.add_exception_handler(Exception, handle_unhandled_exception)
