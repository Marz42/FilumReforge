from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import get_auth_service, get_current_user
from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError
from app.core.rate_limit import build_auth_rate_limit_dependency
from app.models import User
from app.schemas.auth import (
  AuthSessionRead,
  BootstrapStatusRead,
  BootstrapAdminRequest,
  InvitationAcceptRequest,
  InvitationCreateRequest,
  InvitationPreviewRead,
  InvitationRead,
  LoginRequest,
)
from app.schemas.users import UserRead
from app.services.auth_service import AuthService, AuthSession

router = APIRouter(prefix="/auth")

bootstrap_rate_limit = build_auth_rate_limit_dependency(
  scope="auth:bootstrap-admin",
  limit_field="auth_bootstrap_rate_limit",
)
login_rate_limit = build_auth_rate_limit_dependency(
  scope="auth:login",
  limit_field="auth_login_rate_limit",
)
refresh_rate_limit = build_auth_rate_limit_dependency(
  scope="auth:refresh",
  limit_field="auth_refresh_rate_limit",
)


def _build_auth_session_read(auth_session: AuthSession) -> AuthSessionRead:
  return AuthSessionRead(
    access_token=auth_session.access_token,
    token_type=auth_session.token_type,
    user=UserRead.model_validate(auth_session.user),
  )


def _set_refresh_cookie(*, response: Response, settings: Settings, refresh_token: str) -> None:
  response.set_cookie(
    key=settings.auth_refresh_cookie_name,
    value=refresh_token,
    httponly=True,
    secure=settings.auth_refresh_cookie_secure,
    samesite=settings.auth_refresh_cookie_samesite,
    path=settings.auth_refresh_cookie_path,
    domain=settings.auth_refresh_cookie_domain,
    max_age=settings.jwt_refresh_token_days * 24 * 60 * 60,
  )


def _clear_refresh_cookie(*, response: Response, settings: Settings) -> None:
  response.delete_cookie(
    key=settings.auth_refresh_cookie_name,
    path=settings.auth_refresh_cookie_path,
    domain=settings.auth_refresh_cookie_domain,
    secure=settings.auth_refresh_cookie_secure,
    httponly=True,
    samesite=settings.auth_refresh_cookie_samesite,
  )


@router.post(
  "/bootstrap-admin",
  response_model=UserRead,
  status_code=status.HTTP_201_CREATED,
  dependencies=[Depends(bootstrap_rate_limit)],
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


@router.get("/bootstrap-status", response_model=BootstrapStatusRead)
async def read_bootstrap_status(
  auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> BootstrapStatusRead:
  return BootstrapStatusRead(bootstrap_required=await auth_service.is_bootstrap_required())


@router.post("/login", response_model=AuthSessionRead, dependencies=[Depends(login_rate_limit)])
async def login(
  payload: LoginRequest,
  response: Response,
  auth_service: Annotated[AuthService, Depends(get_auth_service)],
  settings: Annotated[Settings, Depends(get_settings)],
) -> AuthSessionRead:
  auth_session = await auth_service.authenticate(
    email=payload.email,
    password=payload.password,
  )
  _set_refresh_cookie(response=response, settings=settings, refresh_token=auth_session.refresh_token)
  return _build_auth_session_read(auth_session)


@router.post("/invitations", response_model=InvitationRead, status_code=status.HTTP_201_CREATED)
async def create_invitation(
  payload: InvitationCreateRequest,
  actor: Annotated[User, Depends(get_current_user)],
  auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> InvitationRead:
  invitation = await auth_service.create_invitation(
    actor=actor,
    email=payload.email,
    role=payload.role,
  )
  return InvitationRead(
    user=UserRead.model_validate(invitation.user),
    invite_url=invitation.invite_url,
    expires_at=invitation.expires_at,
  )


@router.get("/invitations/preview", response_model=InvitationPreviewRead)
async def preview_invitation(
  token: str,
  auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> InvitationPreviewRead:
  user = await auth_service.get_invitation_preview(token=token)
  return InvitationPreviewRead(
    user_id=user.id,
    email=user.email,
    role=user.role,
    expires_at=user.invitation_expires_at,
  )


@router.post("/invitations/accept", response_model=AuthSessionRead)
async def accept_invitation(
  payload: InvitationAcceptRequest,
  response: Response,
  auth_service: Annotated[AuthService, Depends(get_auth_service)],
  settings: Annotated[Settings, Depends(get_settings)],
) -> AuthSessionRead:
  auth_session = await auth_service.accept_invitation(
    token=payload.token,
    password=payload.password,
  )
  _set_refresh_cookie(response=response, settings=settings, refresh_token=auth_session.refresh_token)
  return _build_auth_session_read(auth_session)


@router.post("/invitations/{user_id}/revoke", response_model=UserRead)
async def revoke_invitation(
  user_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRead:
  user = await auth_service.revoke_invitation(actor=actor, user_id=user_id)
  return UserRead.model_validate(user)


@router.post("/refresh", response_model=AuthSessionRead, dependencies=[Depends(refresh_rate_limit)])
async def refresh_session(
  request: Request,
  response: Response,
  auth_service: Annotated[AuthService, Depends(get_auth_service)],
  settings: Annotated[Settings, Depends(get_settings)],
) -> AuthSessionRead:
  refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
  if not refresh_token:
    raise AuthenticationError("缺少刷新令牌。")
  auth_session = await auth_service.refresh(refresh_token=refresh_token)
  _set_refresh_cookie(response=response, settings=settings, refresh_token=auth_session.refresh_token)
  return _build_auth_session_read(auth_session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
  request: Request,
  auth_service: Annotated[AuthService, Depends(get_auth_service)],
  settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
  refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
  if refresh_token:
    await auth_service.revoke_refresh_token(refresh_token=refresh_token)

  response = Response(status_code=status.HTTP_204_NO_CONTENT)
  _clear_refresh_cookie(response=response, settings=settings)
  return response


@router.get("/me", response_model=UserRead)
async def read_current_user(
  current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
  return UserRead.model_validate(current_user)
