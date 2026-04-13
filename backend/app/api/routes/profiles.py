from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_user, get_management_user, get_profile_service
from app.models import User
from app.schemas.profiles import ProfileCreateRequest, ProfileRead, ProfileUpdateRequest
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profiles")


@router.get("", response_model=list[ProfileRead])
async def list_profiles(
  actor: Annotated[User, Depends(get_current_user)],
  profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> list[ProfileRead]:
  profiles = await profile_service.list_profiles(actor=actor)
  return [ProfileRead.model_validate(profile) for profile in profiles]


@router.get("/{user_id}", response_model=ProfileRead)
async def read_profile(
  user_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileRead:
  profile = await profile_service.get_profile(actor=actor, user_id=user_id)
  return ProfileRead.model_validate(profile)


@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
async def create_profile(
  payload: ProfileCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileRead:
  profile = await profile_service.create_profile(
    actor=actor,
    user_id=payload.user_id,
    employee_no=payload.employee_no,
    real_name=payload.real_name,
    department_id=payload.department_id,
    job_title=payload.job_title,
    phone=payload.phone,
    hire_date=payload.hire_date,
    custom_fields=payload.custom_fields,
  )
  return ProfileRead.model_validate(profile)


@router.patch("/{user_id}", response_model=ProfileRead)
async def update_profile(
  user_id: UUID,
  payload: ProfileUpdateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileRead:
  profile = await profile_service.update_profile(
    actor=actor,
    user_id=user_id,
    employee_no=payload.employee_no,
    real_name=payload.real_name,
    department_id=payload.department_id,
    job_title=payload.job_title,
    phone=payload.phone,
    hire_date=payload.hire_date,
    custom_fields=payload.custom_fields,
  )
  return ProfileRead.model_validate(profile)
