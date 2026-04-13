from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_auth_service, get_current_user
from app.models import User
from app.schemas.auth import (
  AuthSessionRead,
  BootstrapAdminRequest,
  LoginRequest,
  RefreshTokenRequest,
)
from app.schemas.users import UserRead
from app.services.auth_service import AuthService, AuthSession

router = APIRouter(prefix="/auth")


def _build_auth_session_read(auth_session: AuthSession) -> AuthSessionRead:
  return AuthSessionRead(
    access_token=auth_session.access_token,
    refresh_token=auth_session.refresh_token,
    token_type=auth_session.token_type,
    user=UserRead.model_validate(auth_session.user),
  )


@router.post(
  "/bootstrap-admin",
  response_model=UserRead,
  status_code=status.HTTP_201_CREATED,
)
async def bootstrap_admin(
  payload: BootstrapAdminRequest,
  auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRead:
  user = await auth_service.bootstrap_admin(
    email=payload.email,
    password=payload.password,
    real_name=payload.real_name,
    employee_no=payload.employee_no,
  )
  return UserRead.model_validate(user)


@router.post("/login", response_model=AuthSessionRead)
async def login(
  payload: LoginRequest,
  auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionRead:
  auth_session = await auth_service.authenticate(
    email=payload.email,
    password=payload.password,
  )
  return _build_auth_session_read(auth_session)


@router.post("/refresh", response_model=AuthSessionRead)
async def refresh_session(
  payload: RefreshTokenRequest,
  auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionRead:
  auth_session = await auth_service.refresh(refresh_token=payload.refresh_token)
  return _build_auth_session_read(auth_session)


@router.get("/me", response_model=UserRead)
async def read_current_user(
  current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
  return UserRead.model_validate(current_user)
