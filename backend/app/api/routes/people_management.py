from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import get_management_user, get_people_management_service
from app.models import User
from app.schemas.people_management import (
  PeopleManagementActionsRead,
  PeopleManagementDetailRead,
  PeopleManagementPersonRead,
  PeopleManagementRead,
  PeopleManagementSummaryRead,
)
from app.schemas.profiles import EmploymentEventRead, ProfileRead
from app.schemas.users import UserRead
from app.services.people_management_service import PeopleManagementService

router = APIRouter(prefix="/people-management")


@router.get("", response_model=PeopleManagementRead)
async def read_people_management(
  actor: Annotated[User, Depends(get_management_user)],
  people_management_service: Annotated[
    PeopleManagementService,
    Depends(get_people_management_service),
  ],
) -> PeopleManagementRead:
  snapshot = await people_management_service.list_people(actor=actor)
  return PeopleManagementRead(
    summary=PeopleManagementSummaryRead(**snapshot.summary),
    people=[PeopleManagementPersonRead(**item) for item in snapshot.people],
  )


@router.get("/{user_id}", response_model=PeopleManagementDetailRead)
async def read_people_management_detail(
  user_id: UUID,
  actor: Annotated[User, Depends(get_management_user)],
  people_management_service: Annotated[
    PeopleManagementService,
    Depends(get_people_management_service),
  ],
) -> PeopleManagementDetailRead:
  snapshot = await people_management_service.get_person_detail(actor=actor, user_id=user_id)
  return PeopleManagementDetailRead(
    summary=PeopleManagementPersonRead(**snapshot.summary),
    account=UserRead.model_validate(snapshot.account),
    profile=ProfileRead.model_validate(snapshot.profile) if snapshot.profile is not None else None,
    actions=PeopleManagementActionsRead(**snapshot.actions),
    primary_manager_user_id=snapshot.primary_manager_user_id,
    primary_manager_label=snapshot.primary_manager_label,
    latest_employment_event=(
      EmploymentEventRead.model_validate(snapshot.latest_employment_event)
      if snapshot.latest_employment_event is not None
      else None
    ),
  )
