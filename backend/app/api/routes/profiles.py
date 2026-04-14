from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
  get_current_user,
  get_delegation_service,
  get_hr_lifecycle_service,
  get_management_user,
  get_organization_relation_service,
  get_profile_service,
)
from app.models import User
from app.schemas.profiles import (
  DelegationRead,
  EmploymentEventCreateRequest,
  EmploymentEventRead,
  ProfileCreateRequest,
  ProfilePositionCreateRequest,
  ProfilePositionRead,
  ProfileRead,
  ProfileUpdateRequest,
  ReportingLineCreateRequest,
  ReportingLineRead,
)
from app.services.delegation_service import DelegationService
from app.services.hr_lifecycle_service import HRLifecycleService
from app.services.organization_relation_service import OrganizationRelationService
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profiles")


@router.get("", response_model=list[ProfileRead])
async def list_profiles(
  actor: Annotated[User, Depends(get_current_user)],
  profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> list[ProfileRead]:
  profiles = await profile_service.list_profile_views(actor=actor)
  return [ProfileRead.model_validate(profile) for profile in profiles]


@router.get("/{user_id}", response_model=ProfileRead)
async def read_profile(
  user_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  profile_service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileRead:
  profile = await profile_service.get_profile_view(actor=actor, user_id=user_id)
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
  profile_view = await profile_service.get_profile_view(actor=actor, user_id=profile.user_id)
  return ProfileRead.model_validate(profile_view)


@router.patch("/{user_id}", response_model=ProfileRead)
async def update_profile(
  user_id: UUID,
  payload: ProfileUpdateRequest,
  actor: Annotated[User, Depends(get_current_user)],
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
  profile_view = await profile_service.get_profile_view(actor=actor, user_id=profile.user_id)
  return ProfileRead.model_validate(profile_view)


@router.get("/{user_id}/positions", response_model=list[ProfilePositionRead])
async def list_profile_positions(
  user_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  profile_service: Annotated[ProfileService, Depends(get_profile_service)],
  organization_relation_service: Annotated[
    OrganizationRelationService,
    Depends(get_organization_relation_service),
  ],
) -> list[ProfilePositionRead]:
  await profile_service.get_profile(actor=actor, user_id=user_id)
  positions = await organization_relation_service.list_profile_positions(user_id=user_id)
  return [ProfilePositionRead.model_validate(position) for position in positions]


@router.post("/{user_id}/positions", response_model=ProfilePositionRead, status_code=status.HTTP_201_CREATED)
async def create_profile_position(
  user_id: UUID,
  payload: ProfilePositionCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  organization_relation_service: Annotated[
    OrganizationRelationService,
    Depends(get_organization_relation_service),
  ],
) -> ProfilePositionRead:
  assignment = await organization_relation_service.assign_position(
    actor=actor,
    user_id=user_id,
    position_id=payload.position_id,
    department_id=payload.department_id,
    assignment_type=payload.assignment_type,
    is_primary=payload.is_primary,
    starts_at=payload.starts_at,
    ends_at=payload.ends_at,
  )
  return ProfilePositionRead.model_validate(assignment)


@router.get("/{user_id}/reporting-lines", response_model=list[ReportingLineRead])
async def list_profile_reporting_lines(
  user_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  profile_service: Annotated[ProfileService, Depends(get_profile_service)],
  organization_relation_service: Annotated[
    OrganizationRelationService,
    Depends(get_organization_relation_service),
  ],
) -> list[ReportingLineRead]:
  await profile_service.get_profile(actor=actor, user_id=user_id)
  reporting_lines = await organization_relation_service.list_reporting_lines(user_id=user_id)
  return [ReportingLineRead.model_validate(reporting_line) for reporting_line in reporting_lines]


@router.post(
  "/{user_id}/reporting-lines",
  response_model=ReportingLineRead,
  status_code=status.HTTP_201_CREATED,
)
async def create_profile_reporting_line(
  user_id: UUID,
  payload: ReportingLineCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  organization_relation_service: Annotated[
    OrganizationRelationService,
    Depends(get_organization_relation_service),
  ],
) -> ReportingLineRead:
  reporting_line = await organization_relation_service.create_reporting_line(
    actor=actor,
    user_id=user_id,
    manager_user_id=payload.manager_user_id,
    line_type=payload.line_type,
    department_id=payload.department_id,
    is_primary=payload.is_primary,
    starts_at=payload.starts_at,
    ends_at=payload.ends_at,
  )
  return ReportingLineRead.model_validate(reporting_line)


@router.get("/{user_id}/events", response_model=list[EmploymentEventRead])
async def list_profile_events(
  user_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  profile_service: Annotated[ProfileService, Depends(get_profile_service)],
  hr_lifecycle_service: Annotated[HRLifecycleService, Depends(get_hr_lifecycle_service)],
) -> list[EmploymentEventRead]:
  await profile_service.get_profile(actor=actor, user_id=user_id)
  events = await hr_lifecycle_service.list_events(user_id=user_id)
  return [EmploymentEventRead.model_validate(event) for event in events]


@router.post("/{user_id}/events", response_model=EmploymentEventRead, status_code=status.HTTP_201_CREATED)
async def create_profile_event(
  user_id: UUID,
  payload: EmploymentEventCreateRequest,
  actor: Annotated[User, Depends(get_management_user)],
  hr_lifecycle_service: Annotated[HRLifecycleService, Depends(get_hr_lifecycle_service)],
) -> EmploymentEventRead:
  event = await hr_lifecycle_service.create_event(
    actor=actor,
    user_id=user_id,
    event_type=payload.event_type,
    effective_date=payload.effective_date,
    title=payload.title,
    summary=payload.summary,
    payload=payload.payload,
  )
  return EmploymentEventRead.model_validate(event)


@router.get("/{user_id}/delegations", response_model=list[DelegationRead])
async def list_profile_delegations(
  user_id: UUID,
  actor: Annotated[User, Depends(get_current_user)],
  profile_service: Annotated[ProfileService, Depends(get_profile_service)],
  delegation_service: Annotated[DelegationService, Depends(get_delegation_service)],
) -> list[DelegationRead]:
  await profile_service.get_profile(actor=actor, user_id=user_id)
  delegations = await delegation_service.list_profile_delegations(user_id=user_id)
  return [DelegationRead.model_validate(delegation) for delegation in delegations]
