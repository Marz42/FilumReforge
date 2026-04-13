from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, get_management_user, get_user_service
from app.models import User
from app.schemas.users import UserCreateRequest, UserRead, UserUpdateRequest
from app.services.user_service import UserService

router = APIRouter(prefix="/users")


@router.get("", response_model=list[UserRead])
async def list_users(
  actor: Annotated[User, Depends(get_management_user)],
  user_service: Annotated[UserService, Depends(get_user_service)],
) -> list[UserRead]:
  users = await user_service.list_users(actor=actor)
  return [UserRead.model_validate(user) for user in users]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
  payload: UserCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserRead:
  user = await user_service.create_user(
    actor=actor,
    email=payload.email,
    password=payload.password,
    role=payload.role,
    status=payload.status,
  )
  return UserRead.model_validate(user)


@router.get("/{user_id}", response_model=UserRead)
async def read_user(
  user_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserRead:
  user = await user_service.get_user(actor=actor, user_id=user_id)
  return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
  user_id: UUID,
  payload: UserUpdateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserRead:
  user = await user_service.update_user(
    actor=actor,
    user_id=user_id,
    email=payload.email,
    password=payload.password,
    role=payload.role,
    status=payload.status,
  )
  return UserRead.model_validate(user)
